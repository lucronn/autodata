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
from urllib.parse import parse_qs, urljoin, urlsplit
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


def authored_table_fixture(runtime, monkeypatch, tmp_path, variant):
    from autodata_ingestion import source_article_capture
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    from autodata_ingestion.procedure_rewrite_auto import PROFILE
    from autodata_ingestion.source_job_persistence import refresh_article_job
    from test_retained_banktwo_notice_publication import NoticeModel

    markup = (
        '<p>Remove the pump.</p><table><caption>Service check</caption>'
        '<thead><tr><th rowspan="2">Assembly</th><th scope="colgroup" colspan="2">Inspection</th></tr>'
        '<tr><th scope="col">Item</th><th scope="col">Illustration</th></tr></thead>'
        '<tbody><tr><th scope="row">'
        '<table><tbody><tr><th scope="row">Pump</th><td>Seat</td></tr></tbody></table>'
        '</th><td>Seal</td>'
        '<td><img data-resource-ref="figure" alt="Pump figure"></td></tr></tbody></table>'
    )
    runtime.servers["banktwo"].body(
        json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode(),
        "application/hal+json", assets=["figure"],
    )
    source_only = variant == "source-table"
    model = None if source_only else NoticeModel()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="capture authored table",
                        rewrite_profile_version="technical-prose-v1" if source_only else PROFILE)
    capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        kwargs.update(keep_html_table_cell_headers=False, keep_html_table_spans=False)
        return capture(*args, **kwargs)

    with monkeypatch.context() as capture_scope:
        if variant != "authored-table":
            capture_scope.setattr(source_article_capture, "capture_source_article", legacy_capture)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=model)
    before = runtime.read_current()
    assert before["content_origin"] == ("source" if source_only else "canonical"), runtime.diagnostics()
    if variant == "authored-table":
        assert model.calls == 1
        return None

    if source_only:
        from autodata_ingestion.article_lifecycle_types import digest_json
        from autodata_ingestion.source_revision_reprojection import apply_table_reprojection
        from autodata_ingestion.source_table_geometry import preview_table_geometry

        binding, captured = preview_table_geometry(runtime.repo, before["source_revision_id"], object_store=runtime.objects)
        args = dict(object_store=runtime.objects, expected_observation_id=binding.source_observation_id,
                    expected_fingerprint=binding.source_fingerprint, expected_body_sha256=binding.body_sha256,
                    expected_document_sha256=digest_json(captured.source_document), actor="fixture",
                    reason="Restore the archived supplier header roles and spans.", geometry=True)

        def restore():
            state = apply_table_reprojection(runtime.repo, runtime.article_id, before["source_revision_id"], **args)
            assert state["status"] == "applied"
            assert apply_table_reprojection(runtime.repo, runtime.article_id, before["source_revision_id"], **args) == {
                **state, "status": "already_applied",
            }
            assert runtime.read_current()["canonical_revision_id"] is None
            return state
    else:
        from autodata_ingestion.published_media_publication import (
            preview_published_media_repair, publish_retained_media_repair,
        )
        from test_published_media_publication import _allowlist

        destination = tmp_path / "geometry-review"
        preview_published_media_repair(runtime.repo, runtime.article_id, before["source_revision_id"],
                                       object_store=runtime.objects, destination=destination,
                                       table_geometry=True, fixture_mode=True)
        expected = json.loads((destination / "manifest.json").read_text())
        assert expected["model_calls"] == 0
        args = dict(expected=expected, object_store=runtime.objects, reviewer_id="media-reviewer",
                    allowlist=_allowlist(tmp_path), rationale="Match the retained supplier table headers and spans.",
                    fixture_mode=True)

        def restore():
            with pytest.raises(ValueError, match="PUBLISHED_MEDIA_REPAIR_STALE"):
                publish_retained_media_repair(runtime.repo, **{
                    **args, "expected": {**expected, "repaired_published_document_hash": "0" * 64},
                })

            def interrupt(point):
                assert point == "inside_publication" and runtime.read_current() == before
                raise RuntimeError("interrupt archived geometry publication")

            with pytest.raises(RuntimeError, match="interrupt archived geometry publication"):
                publish_retained_media_repair(runtime.repo, hooks=interrupt, **args)
            assert runtime.read_current() == before
            state = publish_retained_media_repair(runtime.repo, **args)
            assert state["status"] == "published"
            assert publish_retained_media_repair(runtime.repo, **args) == {**state, "status": "already_published"}
            assert model.calls == 1
            return state
    return before, restore


async def verify_authored_table(page, detail, *, restored=True):
    from playwright.async_api import expect

    expected = [
        [["TH", 2, 1, None, "Assembly"], ["TH", 1, 2, "colgroup", "Inspection"]],
        [["TH", 1, 1, "col", "Item"], ["TH", 1, 1, "col", "Illustration"]],
        [["TH", 1, 1, "row", ""], ["TD", 1, 1, None, "Seal"], ["TD", 1, 1, None, ""]],
    ]
    if not restored:
        expected = [[["TD", 1, 1, None, cell[-1]] for cell in row] for row in expected]

    async def check(content):
        table = content.locator("table").first
        await expect(table.locator("caption")).to_have_text("Service check")
        assert await table.evaluate("""table => [...table.rows].map(row => [...row.cells].map(cell => {
            const ownContent = cell.cloneNode(true);
            ownContent.querySelectorAll('figure, table, .source-reference').forEach(node => node.remove());
            return [cell.tagName, cell.rowSpan, cell.colSpan, cell.getAttribute('scope'), ownContent.textContent.trim()];
        }))""") == expected
        nested = table.locator("table")
        await expect(nested.locator("tr > *").first).to_have_text("Pump")
        nested_header = ["TH", "row", "Pump"] if restored else ["TD", None, "Pump"]
        assert await nested.locator("tr > *").evaluate_all(
            "cells => cells.map(cell => [cell.tagName, cell.getAttribute('scope'), cell.textContent.trim()])"
        ) == [nested_header, ["TD", None, "Seat"]]
        image = table.locator("tr:last-child td:last-child figure img")
        await expect(image).to_have_attribute("alt", "Pump figure")
        assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
        asset = await page.context.request.get(await image.evaluate("(node) => node.currentSrc"))
        assert asset.ok
        return sha256(await asset.body()).hexdigest()

    await page.set_viewport_size({"width": 320, "height": 850})
    reader = page.locator("#article-content")
    reader_asset = await check(reader)
    assert await reader.locator(".table-scroll").first.evaluate(
        "node => node.getBoundingClientRect().right <= document.documentElement.clientWidth"
    )
    async with page.expect_response(lambda response: urlsplit(response.url).path == urlsplit(detail).path + "/source") as pending:
        await page.locator("#open-original").click()
    response = await pending.value
    assert response.ok
    source = (await response.json())["source"]
    assert await check(page.locator("#source-review-frame")) == reader_asset
    raw_page = await page.context.new_page()
    try:
        raw = await raw_page.goto(urljoin(detail, source["url"]))
        assert raw.ok
        assert await check(raw_page.locator("body")) == reader_asset
    finally:
        await raw_page.close()
    await page.locator("#back-to-article").click()
    return reader_asset


async def exercise_simulated_payment(origin, scope, customer_account, repair=None, table_variant=None, table_repair=None):
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
            if repair is None and table_variant is None:
                await page.goto(f"{origin}/workshop/")
                for field, value in (("year", "2024"), ("make", "example"), ("model", "car"),
                                     ("configuration", configuration)):
                    await page.locator(f"#{field}").select_option(value)
                expected = {"year": ["2024"], "make": ["example"], "model": ["car"],
                            "configuration": [configuration], "region": ["US"]}
                assert parse_qs(urlsplit(page.url).query) == expected
                await page.go_back()
                await expect(page.locator("#configuration")).to_have_value("")
                await expect(page.locator("#purchase")).to_be_hidden()
                assert parse_qs(urlsplit(page.url).query) == {
                    field: expected[field] for field in ("year", "make", "model")
                }
                await page.go_forward()
                assert parse_qs(urlsplit(page.url).query) == expected
            else:
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
            if repair is None and table_variant is None:
                await api_control(owner, origin, "control/start-workers")
            await page.get_by_role("button", name="Open articles", exact=True).click()
            await page.locator(f'#articles a[href*="{article}"]').click()
            article_kind = "Stored source" if table_variant == "source-table" else "Workshop article"
            await expect(page.locator("#article-kind")).to_have_text(article_kind, timeout=18000)
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
            if table_repair is not None:
                before, restore = table_repair
                previous_digest = await verify_authored_table(page, detail, restored=False)
                result_pins = await asyncio.to_thread(restore)
                await page.reload()
                await expect(page.locator("#article-kind")).to_have_text(article_kind)
                assert await verify_authored_table(page, detail) == previous_digest
                article = (await (await owner.request.get(detail)).json())["article"]
                assert article["source_revision_id"] == result_pins["source_revision_id"] != str(before["source_revision_id"])
                assert article.get("canonical_revision_id") == result_pins.get("canonical_revision_id")
                print(json.dumps({"case": table_variant, "engine": engine, "headed": True,
                                  "header_cells": 6, "spans": 2, "figure_sha256": previous_digest,
                                  "idempotent": True, "zero_model_replay": True}), flush=True)
            if table_variant == "authored-table":
                digest = await verify_authored_table(page, detail)
                print(json.dumps({"case": "authored-table", "engine": engine, "headed": True,
                                  "header_cells": 6, "spans": 2, "figure_sha256": digest}), flush=True)
            expected_text = "Remove the pump." if table_variant == "source-table" else "Take off the pump."
            await expect(page.locator("#article-content")).to_contain_text(expected_text)
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


@pytest.mark.parametrize("variant", ["payment", "list-starts", "authored-table", "archived-table", "source-table"])
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
        table_variant = variant if variant in ("authored-table", "archived-table", "source-table") else None
        table_repair = authored_table_fixture(runtime, monkeypatch, tmp_path, table_variant) if table_variant else None
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
                table_variant=table_variant, table_repair=table_repair,
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
