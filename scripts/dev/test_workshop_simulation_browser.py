"""Exercise simulated checkout through the normal Workshop on the isolated API fixture."""

import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest

if os.environ.get("AUTODATA_REQUIRE_WORKSHOP_SIMULATION_BROWSER") != "1":
    pytest.skip("explicit isolated Workshop simulation browser fixture only", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/tests"))

from autodata_ingestion.commerce_service import configured_commerce
from lifecycle_support import LifecycleRuntime, fresh_database
from test_catalog_api_integration import Bridge, GO_NAMES, serve
from test_paid_catalog_api_integration import configure_scoped_runtime
from workshop_browser_smoke import API_CASES, APIFixture, api_control, api_measure, api_signin, fixture_origin


async def exercise_simulated_payment(origin, scope, customer_account):
    from playwright.async_api import async_playwright, expect

    configuration = scope["configuration"]
    article = scope["article"]
    route = f"{origin}/workshop/?configuration={configuration}&region=US"
    detail = f"{origin}/v1/catalog/vehicles/{configuration}/articles/{article}?region=US"
    checkout_path = "/v1/workshop/checkout-sessions"

    async with async_playwright() as playwright:
        executable = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_CHROMIUM")
        browser = await playwright.chromium.launch(**({"executable_path": executable} if executable else {}))
        try:
            owner = await browser.new_context(ignore_https_errors=True, service_workers="block")
            transport = APIFixture(origin, API_CASES[1])
            stripe = []

            async def route_fixture(request_route):
                host = urlsplit(request_route.request.url).hostname or ""
                if host == "stripe.com" or host.endswith(".stripe.com"):
                    stripe.append(host)
                    await request_route.abort()
                else:
                    await transport.route(request_route)

            await owner.route("**/*", route_fixture)
            page = await owner.new_page()
            assert (await owner.request.get(detail)).status == 401
            await page.goto(route)
            await api_signin(page)
            assert (await owner.request.get(detail)).status == 403
            configuration_response = await owner.request.get(origin + "/workshop/purchase-config.json")
            assert configuration_response.status == 200
            purchase_configuration = await configuration_response.json()
            assert purchase_configuration["enabled"] is True and purchase_configuration["checkout_mode"] == "simulation"
            await expect(page.locator("#purchase-price")).to_have_text("No charge · simulated $20 USD")
            purchase = page.get_by_role("button", name="Simulate purchase", exact=True)
            await expect(purchase).to_be_enabled()
            await page.locator("#agreement").check()
            before = await api_measure(owner, origin)
            assert before["workshop_orders"] == before["entitlements"] == 0

            async with page.expect_response(
                lambda response: response.request.method == "POST"
                and urlsplit(response.url).path == checkout_path,
            ) as pending:
                await purchase.click()
            checkout = await pending.value
            request = checkout.request
            assert checkout.status == 200
            assert request.post_data_json == {
                "configuration_id": configuration,
                "region": "US",
                "terms_version": "workshop-v1",
                "expected_mode": "simulation",
            }
            assert UUID(request.headers["idempotency-key"])
            result = await checkout.json()
            assert result["state"] == "owned"
            assert result["configuration_id"] == configuration and result["region"] == "US"
            assert result["library_item_id"] == result["order_id"] and not result.get("checkout_url")
            assert urlsplit(page.url).path.rstrip("/") == "/workshop"

            await page.locator("#my-vehicles").click()
            await expect(page.locator("#library-items > li")).to_have_count(1)
            await page.reload()
            await expect(page.locator("#library-items > li")).to_have_count(1)
            await expect(page.locator("#library-items h3")).to_contain_text("Paid selected")
            await api_control(owner, origin, "control/start-workers")
            await page.get_by_role("button", name="Open articles", exact=True).click()
            await page.locator(f'#articles a[href*="{article}"]').click()
            await expect(page.locator("#article-kind")).to_have_text("Workshop article", timeout=18000)
            await expect(page.locator("#article-content")).to_contain_text("Take off the pump.")
            image = page.locator("#article-content img").first
            await expect(image).to_be_visible()
            assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
            assert (await owner.request.get(detail)).status == 200
            media = await image.evaluate("(node) => node.currentSrc")
            assert urlsplit(media).netloc == urlsplit(origin).netloc
            assert urlsplit(media).path.startswith("/v1/catalog/images/v2.")
            asset = await owner.request.get(media)
            assert asset.status == 200 and asset.headers["content-type"].startswith("image/png")

            other = await browser.new_context(ignore_https_errors=True, service_workers="block")
            other_transport = APIFixture(origin, API_CASES[1])
            other_transport.account = "other"
            await other.route("**/*", other_transport.route)
            other_page = await other.new_page()
            await other_page.goto(route)
            await api_signin(other_page)
            other_config = await other.request.get(origin + "/workshop/purchase-config.json")
            assert other_config.status == 200 and (await other_config.json())["enabled"] is True
            assert (await other.request.get(detail)).status == 403
            assert (await other.request.get(media)).status in (401, 403, 404)
            after = await api_measure(owner, origin)
            assert after["workshop_orders"] == after["workshop_checkout_requests"] == after["entitlements"] == 1
            assert after["orders"] == [{
                "order_id": result["order_id"], "state": "paid", "owner": customer_account,
                "configuration_id": configuration, "region": "US",
            }]
            assert stripe == [] and transport.unexpected == [] and other_transport.unexpected == []
            assert (await owner.request.post(origin + "/__fixture/stop")).status == 204
        finally:
            await browser.close()


def test_simulated_payment_preserves_workshop_library_article_and_media(fresh_database, monkeypatch, tmp_path):
    from autodata_ingestion.http_service import make_handler

    repo = fresh_database()
    account = str(uuid4())
    with repo.connect() as conn:
        conn.execute(
            "INSERT INTO customer_accounts(customer_account_id, firebase_project_id, firebase_uid) "
            "VALUES (%s, 'fixture-project', 'fixture-user')", (account,),
        )

    with ExitStack() as stack:
        runtime = LifecycleRuntime(repo, stack)
        stack.callback(runtime.close)
        provider = "banktwo"
        scope = configure_scoped_runtime(runtime, provider)
        scope["article"] = str(runtime.article_id)
        bridge = Bridge(runtime, GO_NAMES[0])
        for name, value in {
            **runtime.env,
            "AUTODATA_ENV": "test",
            "AUTODATA_PUBLIC_ORIGIN": "https://fixture.invalid",
            "AUTODATA_COMMERCE_MODE": "simulation",
            "AUTODATA_COMMERCE_READ_ONLY_MODE": "stripe_test",
            "AUTODATA_STRIPE_ACCOUNT_ID": "acct_fixture",
            "AUTODATA_STRIPE_PRICE_ID": "price_fixture",
            "AUTODATA_INGESTION_INTERNAL_TOKEN": "fixture-r3-internal",
        }.items():
            monkeypatch.setenv(name, value)
        commerce = configured_commerce(connection_factory=repo.connect)
        ensure = stack.enter_context(serve(make_handler(internal_token="fixture-r3-internal", commerce=commerce)))
        control = stack.enter_context(serve(bridge.control_handler()))
        ready = tmp_path / "ready.json"
        go_env = {name: os.environ[name] for name in (
            "PATH", "HOME", "GOTOOLCHAIN", "GOPROXY", "GOFLAGS", "CGO_ENABLED", "GOMODCACHE", "GOCACHE", "GOTMPDIR",
        ) if name in os.environ}
        go_env.update(
            AUTODATA_WORKSHOP_BROWSER_FIXTURE="1",
            AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION="1",
            AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION="1",
            AUTODATA_CATALOG_INTEGRATION_REQUIRED="1",
            AUTODATA_LIFECYCLE_TEST="1",
            AUTODATA_WORKSHOP_BROWSER_SIMULATION="1",
            AUTODATA_WORKSHOP_BROWSER_READY=str(ready),
            AUTODATA_CATALOG_TEST_DSN=f"postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable",
            AUTODATA_CATALOG_TEST_ENSURE_URL=ensure,
            AUTODATA_CATALOG_TEST_CONTROL_URL=control,
            AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
            AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),
            AUTODATA_CATALOG_TEST_ARTICLE_ID=scope["article"],
            AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles["bankone"]),
            AUTODATA_CATALOG_TEST_PROVIDER=provider,
            AUTODATA_CATALOG_TEST_CANDIDATE_SHA=os.environ["AUTODATA_R3_CANDIDATE_SHA"],
            AUTODATA_CATALOG_TEST_CASE_DIR=str(tmp_path),
            AUTODATA_PAID_TEST_CONFIGURATION_ID=scope["configuration"],
            AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID=scope["adjacent"],
            AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID=scope["other_region"],
            AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID=scope["unscoped"],
            AUTODATA_S3_ENDPOINT="minio:9000",
            AUTODATA_S3_ACCESS_KEY="fixture",
            AUTODATA_S3_SECRET_KEY="fixture",
            AUTODATA_SOURCE_BUCKET=runtime.bucket,
        )
        fixture_test = "^TestWorkshopBrowserFixtureHTTP$"
        binary = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_GO_BINARY")
        if binary:
            command = [binary, "-test.count=1", "-test.run", fixture_test, "-test.timeout=90s"]
        else:
            command = ["go", "test", "-count=1", "-run", fixture_test, "-timeout=90s", "."]
        go = subprocess.Popen(command, cwd=ROOT / "apps/api-go", env=go_env, start_new_session=True)
        try:
            deadline = time.monotonic() + 35
            while not ready.exists():
                assert go.poll() is None and time.monotonic() < deadline, "simulation fixture did not start"
                time.sleep(0.05)
            metadata = json.loads(ready.read_bytes())
            assert metadata["kind"] == "api-fixture" and metadata["scope"]["article"] == scope["article"]
            asyncio.run(asyncio.wait_for(exercise_simulated_payment(fixture_origin(metadata["origin"]), scope, account), 45))
            assert go.wait(timeout=5) == 0
            with repo.connect() as conn:
                events = conn.execute(
                    "SELECT event_type, payload->>'amount_charged_minor' AS charged "
                    "FROM payment_events",
                ).fetchall()
            assert events == [{"event_type": "workshop.checkout.simulated", "charged": "0"}]
        finally:
            if go.poll() is None:
                os.killpg(go.pid, signal.SIGTERM)
                try:
                    go.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(go.pid, signal.SIGKILL)
                    go.wait(timeout=5)
