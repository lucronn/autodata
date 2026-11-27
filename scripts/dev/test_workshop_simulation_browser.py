"""Exercise simulated checkout through the normal Workshop on the isolated API fixture."""

import asyncio
from contextlib import ExitStack
from hashlib import sha256
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


def retained_list_start_fixture(runtime, monkeypatch):
    from autodata_ingestion import source_article_capture
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    from autodata_ingestion.procedure_rewrite_auto import PROFILE
    from autodata_ingestion.retained_banktwo_notice_publication import (
        preview_banktwo_list_start_publication, publish_banktwo_list_start,
    )
    from autodata_ingestion.source_job_persistence import refresh_article_job
    from test_retained_banktwo_notice_publication import NoticeModel

    markup = (
        '<h2>CorrectionPump alignment</h2>'
        '<ol start="1. "><li>Remove the pump.<img data-resource-ref="figure" alt="Pump figure"></li></ol>'
        '<ol start="7. "><li>Install the replacement.</li></ol>'
    )
    runtime.servers["banktwo"].body(
        json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode(),
        "application/hal+json", assets=["figure"],
    )
    capture = source_article_capture.capture_source_article

    def old_capture(*args, **kwargs):
        kwargs["keep_banktwo_dotted_list_starts"] = False
        return capture(*args, **kwargs)

    model = NoticeModel()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="publish pre-repair source",
                        rewrite_profile_version=PROFILE)
    with monkeypatch.context() as historical:
        historical.setattr(source_article_capture, "capture_source_article", old_capture)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=model)
    prior = runtime.read_current()
    assert prior["content_origin"] == "canonical" and model.calls == 1, runtime.diagnostics()
    manifest = preview_banktwo_list_start_publication(
        runtime.repo, prior["source_revision_id"], object_store=runtime.objects,
    )

    def publish():
        args = dict(expected=manifest, object_store=runtime.objects, actor="fixture",
                    reason="Restore authored list starts in the archived procedure.")
        with pytest.raises(ValueError, match="BANKTWO_NOTICE_PUBLICATION_STALE"):
            publish_banktwo_list_start(runtime.repo, **{**args, "expected": {
                **manifest, "repaired_published_document_hash": "0" * 64,
            }})

        def interrupt(point):
            assert point == "inside_publication" and runtime.read_current() == prior
            raise RuntimeError("fixture interruption")

        with pytest.raises(RuntimeError, match="fixture interruption"):
            publish_banktwo_list_start(runtime.repo, hooks=interrupt, **args)
        assert runtime.read_current() == prior
        result = publish_banktwo_list_start(runtime.repo, **args)
        assert result["status"] == "published"
        assert publish_banktwo_list_start(runtime.repo, **args) == {**result, "status": "already_published"}
        with runtime.repo.connect() as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM publication_events WHERE canonical_article_revision_id=%s",
                (result["canonical_revision_id"],),
            ).fetchone()["n"] == 1
            assert conn.execute(
                "SELECT count(*) AS n FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s",
                (result["job_id"],),
            ).fetchone()["n"] == 0
        assert model.calls == 1
        return result

    return prior, publish


async def verify_list_start_reader(page, owner, detail, expected, pins, *, original=False):
    from playwright.async_api import expect

    if original:
        async with page.expect_response(lambda response: urlsplit(response.url).path == urlsplit(detail).path + "/source") as pending:
            await page.locator("#open-original").click()
        response = await pending.value
        assert response.ok
        source = (await response.json())["source"]
        assert f"source_revision_id={pins['source_revision_id']}" in source["url"]
        content = page.locator("#source-review-frame")
        await expect(content).to_contain_text("Remove the pump.")
    else:
        response = await owner.request.get(detail)
        assert response.ok
        article = (await response.json())["article"]
        assert all(article[name] == str(pins[name]) for name in ("source_revision_id", "canonical_revision_id"))
        content = page.locator("#article-content")
        await expect(content).to_contain_text("Take off the pump.")
    await expect(content.locator("ol")).to_have_count(2)
    assert await content.locator("ol").evaluate_all("lists => lists.map(list => list.start)") == expected
    image = content.locator("ol:first-of-type > li figure img")
    assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
    asset = await owner.request.get(await image.evaluate("(node) => node.currentSrc"))
    assert asset.ok and asset.headers["content-type"].startswith("image/png")
    digest = sha256(await asset.body()).hexdigest()
    if original:
        await page.locator("#back-to-article").click()
    return digest


async def exercise_simulated_payment(origin, scope, customer_account, repair=None):
    from playwright.async_api import async_playwright, expect

    configuration = scope["configuration"]
    article = scope["article"]
    route = f"{origin}/workshop/?configuration={configuration}&region=US"
    detail = f"{origin}/v1/catalog/vehicles/{configuration}/articles/{article}?region=US"
    quote = f"{origin}/v1/workshop/quote?configuration_id={configuration}&region=US"
    checkout_path = "/v1/workshop/checkout-sessions"

    async with async_playwright() as playwright:
        engine = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_ENGINE", "chromium")
        if engine == "webkit":
            executable = os.environ.get("WORKSHOP_HEADED_WEBKIT_EXECUTABLE")
            browser_type = playwright.webkit
        else:
            assert engine == "chromium"
            executable = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_CHROMIUM")
            browser_type = playwright.chromium
        browser = await browser_type.launch(headless=False, **({"executable_path": executable} if executable else {}))
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
            guest_quote = await owner.request.get(quote)
            assert guest_quote.ok and (await guest_quote.json())["purchasable"] is False
            await page.goto(route)
            await expect(page.locator("#purchase-message")).to_have_text(
                "Sign in with Google to simulate purchase. No payment is collected."
            )
            await api_signin(page)
            assert (await owner.request.get(detail)).status == 403
            owner_quote = await owner.request.get(quote)
            assert owner_quote.ok and (await owner_quote.json())["purchasable"] is True
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
            if repair is None:
                await api_control(owner, origin, "control/start-workers")
            await page.get_by_role("button", name="Open articles", exact=True).click()
            await page.locator(f'#articles a[href*="{article}"]').click()
            await expect(page.locator("#article-kind")).to_have_text("Workshop article", timeout=18000)
            if repair is not None:
                prior, publish = repair
                previous_reader = await verify_list_start_reader(page, owner, detail, [1, 1], prior)
                previous_original = await verify_list_start_reader(page, owner, detail, [1, 1], prior, original=True)
                corrected = await asyncio.to_thread(publish)
                await page.reload()
                corrected_reader = await verify_list_start_reader(page, owner, detail, [1, 7], corrected)
                corrected_original = await verify_list_start_reader(page, owner, detail, [1, 7], corrected, original=True)
                assert previous_reader == previous_original == corrected_reader == corrected_original
                print(json.dumps({"case": "banktwo-list-starts", "engine": engine, "headed": True,
                                  "starts": [1, 7], "figure_sha256": corrected_reader,
                                  "publication_retry_and_rollback_verified": True}), flush=True)
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


@pytest.mark.parametrize("variant", ["payment", "list-starts"])
def test_simulated_payment_preserves_workshop_library_article_and_media(fresh_database, monkeypatch, tmp_path, variant):
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
        repair = retained_list_start_fixture(runtime, monkeypatch) if variant == "list-starts" else None
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
            asyncio.run(asyncio.wait_for(exercise_simulated_payment(
                fixture_origin(metadata["origin"]), scope, account, repair=repair,
            ), 45))
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
