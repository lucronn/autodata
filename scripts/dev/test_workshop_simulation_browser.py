"""Exercise simulated checkout through the normal Workshop on the isolated API fixture."""

import asyncio
from contextlib import ExitStack, asynccontextmanager
from hashlib import sha256
from io import BytesIO
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
from lifecycle_support import LifecycleRuntime, fresh_database, seed_configuration, seed_vehicle
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


def labelled_market_fixture(runtime):
    misplaced = seed_configuration(runtime.repo, runtime.vehicle, engine_displacement_l="5.3")
    verified = seed_configuration(runtime.repo, runtime.vehicle, engine_displacement_l="3.6")
    with runtime.repo.connect() as connection:
        for identifier, label in ((misplaced, "Cheyenne 2WD Mexico"), (verified, "Verified model (Mexico)")):
            connection.execute("""
                UPDATE vehicle_identity_bases SET model=%s, reviewer_state='pending'
                WHERE vehicle_identity_base_id=(
                    SELECT vehicle_identity_base_id FROM vehicle_configurations WHERE vehicle_configuration_id=%s
                )
            """, (label, identifier))
        connection.execute("""
            INSERT INTO vehicle_identity_observations(observation_key, vehicle_id, vehicle_identity_base_id,
              vehicle_configuration_id, source_snapshot_id, extraction_evidence_id, source_locator,
              evidence_locator, evidence_confidence, reviewer_state, raw_observation, canonical_observation,
              resolution_status)
            SELECT 'market-fixture', vehicle_id, vehicle_identity_base_id, vehicle_configuration_id,
              source_snapshot_id, extraction_evidence_id, 'fixture', 'fixture', 1, 'pending',
              '{"region":"US","source_region":"US"}'::jsonb, '{}'::jsonb, 'matched'
            FROM vehicle_configurations WHERE vehicle_configuration_id=%s
        """, (verified,))
    return str(misplaced), str(verified)


async def verify_labelled_market_picker(page, origin, misplaced, verified):
    from playwright.async_api import expect

    base = origin + "/v1/catalog/years/2024/makes/example/models"
    await page.goto(origin + "/workshop/?year=2024&make=example")
    await expect(page.locator('#model option[value="verified-model-mexico"]')).to_be_attached()
    await expect(page.locator('#model option[value="cheyenne-2wd-mexico"]')).to_have_count(0)
    for model, identifier, market_unverified in (
        ("cheyenne-2wd-mexico", misplaced, True), ("verified-model-mexico", verified, False)
    ):
        reply = await page.evaluate("""async path => {
            const response = await fetch(path);
            if (!response.ok) throw new Error(String(response.status));
            return response.json();
        }""", f"{base}/{model}/configurations?region=US&stored_only=1")
        row, = reply["items"]
        assert row["id"] == identifier
        assert row.get("engine_variant_market_unverified", False) is market_unverified
    await page.goto(f"{origin}/workshop/?configuration={misplaced}&region=US")
    await expect(page.locator("#activity-text")).to_have_text(
        "This saved vehicle choice is unavailable in the selected region."
    )
    await expect(page.locator("#purchase")).to_be_hidden()


async def verify_late_grouped_models(page, origin):
    from playwright.async_api import expect

    model_path = "/v1/catalog/years/2024/makes/example/models"
    group = "base-sport-touring"
    group_path = f"{model_path}/{group}/configurations"
    base_path = f"{model_path}/base/configurations"
    engine = str(uuid4())
    group_requested = False
    resumed_reads = []
    release_siblings = asyncio.Event()

    def selector(items, *, complete=True):
        return {"version": "v1", "items": items, "complete": complete, "hydrating": not complete}

    async def models(route):
        if group_requested:
            resumed_reads.append(parse_qs(urlsplit(route.request.url).query).get("stored_only"))
        complete = len(resumed_reads) >= 2
        items = [{"id": group, "name": "Base/Sport/Touring"}]
        if resumed_reads:
            items.append({"id": "base", "name": "Base"})
        if complete:
            await release_siblings.wait()
            items.extend({"id": name.lower(), "name": name} for name in ("Sport", "Touring"))
        await route.fulfill(json=selector(items, complete=complete))

    async def group_engines(route):
        nonlocal group_requested
        group_requested = True
        await route.fulfill(json=selector([]))

    async def base_engines(route):
        await route.fulfill(json=selector([{"id": engine, "year": 2024, "make": "Example",
            "model": "Base", "engine": "2.0 L", "region": "US", "complete": True}]))

    requests = {
        model_path: models,
        group_path: group_engines,
        base_path: base_engines,
    }
    for path, handler in requests.items():
        await page.route(f"{origin}{path}?*", handler)
    try:
        await page.goto(f"{origin}/workshop/?year=2024&make=example")
        await page.locator("#model").select_option(group)
        alternatives = page.locator("#model-alternatives")
        base = alternatives.get_by_role("button", name="Base", exact=True)
        await expect(alternatives.get_by_role("button")).to_have_text(["Base"])
        await base.focus()
        release_siblings.set()
        await expect(alternatives.get_by_role("button")).to_have_text(["Base", "Sport", "Touring"])
        await expect(base).to_be_focused()
        await base.click()
        await expect(page.locator("#model")).to_have_value("base")
        await expect(page.locator(f'#configuration option[value="{engine}"]')).to_have_text("2.0 L")
        await expect(page.locator("#configuration")).to_be_enabled()
        await expect(alternatives).to_be_hidden()
        assert resumed_reads == [["1"], ["1"]]
    finally:
        release_siblings.set()
        for path, handler in requests.items():
            await page.unroute(f"{origin}{path}?*", handler)


async def verify_pending_saved_article(owner, origin, configuration, article, expected_text):
    from playwright.async_api import expect

    detail = f"{origin}/v1/catalog/vehicles/{configuration}/articles/{article}"
    preparing = asyncio.Event()
    release_prepare = asyncio.Event()
    detail_requests = []
    tab = await owner.new_page()

    async def read_article(route):
        startup = "workshop-retained-reader-session" in route.request.headers.get("prefer", "")
        detail_requests.append(startup)
        if not startup:
            await route.fallback()
            return
        reply = await route.fetch()
        assert reply.ok and reply.headers.get("workshop-reader-session")
        await preparing.wait()
        await route.fulfill(response=reply)

    async def prepare_article(route):
        assert route.request.method == "POST"
        preparing.set()
        await release_prepare.wait()
        await route.fallback()

    try:
        await tab.route(f"{detail}?*", read_article)
        await tab.route(f"{detail}/prepare?*", prepare_article)
        await tab.goto(f"{origin}/workshop?configuration={configuration}&region=US&article={article}", wait_until="commit")
        await asyncio.wait_for(preparing.wait(), timeout=5)
        await expect(tab.locator("#article-content")).to_contain_text(expected_text, timeout=5000)
        image = tab.locator("#article-content img").first
        assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
        assert detail_requests == [True]
        async with tab.expect_response(
            lambda reply: reply.request.method == "POST" and urlsplit(reply.url).path.endswith("/prepare"),
        ) as prepared:
            release_prepare.set()
        assert (await prepared.value).ok
    finally:
        preparing.set()
        release_prepare.set()
        await tab.close()


def authored_model_index_fixture(runtime, scope, *, competing_fitment=False):
    from threading import Event, Thread

    from psycopg.types.json import Jsonb
    from PIL import Image
    from autodata_ingestion.article_lifecycle_types import ArticleKey, article_id
    from autodata_ingestion.catalog_index_worker import run_catalog_worker

    vehicle = seed_vehicle(runtime.repo)
    configuration = seed_configuration(runtime.repo, vehicle, engine_displacement_l=6.0)
    make, model, authored = "Cadillac Truck", "Escalade Esv Awd", "Escalade/ESV AWD"
    ref, document = "vehicle:fixture-cadillac-awd-6", "cold-procedure"
    title = "Fixture pump service"
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicles SET model_year=2005,make=%s,model=%s WHERE vehicle_id=%s",
                     (make, model, vehicle))
        conn.execute("""UPDATE vehicle_identity_bases SET model_year=2005,make=%s,model=%s
                        WHERE vehicle_id=%s""", (make, model, vehicle))
        conn.execute("""INSERT INTO vehicle_identity_observations
            (observation_key,vehicle_id,vehicle_identity_base_id,vehicle_configuration_id,source_snapshot_id,
             extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state,
             raw_observation,canonical_observation,resolution_status)
            SELECT %s,vehicle_id,vehicle_identity_base_id,vehicle_configuration_id,source_snapshot_id,
                   extraction_evidence_id,'fixture','fixture',1,'pending',%s,%s,'matched'
              FROM vehicle_configurations WHERE vehicle_configuration_id=%s""",
            (uuid4().hex, Jsonb({"model": authored, "provider_mappings": [
                {"provider": "autoapitwo", "entity_type": "car", "provider_id": ref},
            ]}), Jsonb({"region": "US"}), configuration))
        assert conn.execute(
            "SELECT count(*) AS n FROM catalog_article_provider_scopes WHERE vehicle_configuration_id=%s",
            (configuration,),
        ).fetchone()["n"] == 0
    for server in runtime.servers.values():
        server.candidates = []
    banktwo = runtime.servers["banktwo"]
    banktwo.pages = [
        {"complete": False, "next_cursor": "1", "articles": [
            {"opaque_ref": document, "title": title, "resource_ref": "cold-body",
             "asset_resource_refs": ["figure"]},
        ]},
        {"complete": True, "articles": [{"opaque_ref": "later-entry", "title": "Related service",
                                        "resource_ref": "other-body"}]},
    ]
    banktwo.body(json.dumps({"blocks": [
        {"kind": "warning", "text": "Do not reuse the seal."},
        {"kind": "step", "number": 1, "text": "Remove the pump.",
         "images": [{"asset_resource_ref": "figure", "alt": "Pump figure"}]},
        {"kind": "step", "number": 2, "text": "Install the replacement."},
    ]}).encode(), "application/json", ref="cold-body", assets=["figure"])
    illustration = BytesIO()
    Image.new("RGB", (180, 90), "navy").save(illustration, format="PNG")
    banktwo.body(illustration.getvalue(), "image/png", ref="figure", kind="asset")
    pending_page, allow_page = Event(), Event()
    runtime.stack.callback(allow_page.set)
    original_response = banktwo.response
    model_queries = []
    resolution_queries = []

    def response(path, payload=None):
        parsed = urlsplit(path)
        if (parsed.path == "/v1/vehicle-resolutions" and payload
            and payload.get("year") == 2005 and payload.get("make") == make
            and payload.get("model") == model and payload.get("configuration") == "6.0L"):
            resolution_queries.append(model)
            candidates = [{"opaque_ref": ref, "label": "V8-6.0L VIN N", "confidence": 1.0}] if competing_fitment else []
            return 200, banktwo.envelope(selector=payload, candidates=candidates)
        if parsed.path == "/v1/catalog/configurations":
            query = parse_qs(parsed.query)
            if query.get("year") != ["2005"] or query.get("make") != [make]:
                return original_response(path, payload)
            model_queries.extend(query["model"])
            rows = [{"opaque_ref": ref, "year": 2005, "make": make, "model": authored, "region": "US",
                     "drivetrain": "AWD", "label": "V8-6.0L VIN N"}] if query["model"] == [authored] else []
            if rows and competing_fitment:
                rows.append({**rows[0], "opaque_ref": "vehicle:unbound-cadillac-6"})
            return 200, banktwo.envelope(scope="configurations", complete=True, items=rows)
        if parsed.path.endswith("/articles") and parse_qs(parsed.query).get("cursor") == ["1"]:
            pending_page.set()
            assert allow_page.wait(18), "first page did not reach the browser"
        return original_response(path, payload)

    banktwo.response = response
    stop = Event()
    preparation = Thread(target=run_catalog_worker, args=(runtime.repo,), kwargs={
        "registry": runtime.registry, "object_store": runtime.objects, "prepare_orders": True, "stop": stop,
    }, name="workshop-catalog-preparation-fixture", daemon=True)

    def stop_preparation():
        stop.set()
        allow_page.set()
        preparation.join(5)
        assert not preparation.is_alive()

    runtime.stack.callback(stop_preparation)
    preparation.start()
    identifier = article_id(ArticleKey("banktwo", vehicle, configuration, ref, document))
    scope.update(configuration=str(configuration), article=str(identifier), authored_index={
        "vehicle": vehicle, "configuration": configuration, "repository": runtime.repo, "title": title,
        "model": authored, "queries": model_queries, "pending": pending_page, "release": allow_page,
        "resolution_queries": resolution_queries, "expected_resolution_queries": [model] if competing_fitment else [],
        "body_sha": sha256(banktwo.resources["cold-body"][0]).hexdigest(),
        "figure_sha": sha256(banktwo.resources["figure"][0]).hexdigest(),
        "figure_dimensions": (180, 90),
    })
    return scope


def hold_unrelated_bankone_catalog(runtime):
    from threading import Event
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs

    make = "Fixture Queue Supplier"
    active, release, finished, overlapping = Event(), Event(), Event(), Event()
    bankone = runtime.servers["bankone"]
    original_response = bankone.response
    runtime.stack.callback(release.set)

    def response(path, payload=None):
        if urlsplit(path).path == "/v1/vehicle-resolutions" and payload:
            if payload.get("make") == make:
                active.set()
                release.wait(8)
                finished.set()
            elif active.is_set() and not release.is_set():
                overlapping.set()
        return original_response(path, payload)

    bankone.response = response

    def start():
        vehicle = seed_vehicle(runtime.repo)
        with runtime.repo.connect() as conn:
            conn.execute("UPDATE vehicles SET make=%s,model='Held catalog scope' WHERE vehicle_id=%s", (make, vehicle))
        ensure_article_catalog_jobs(runtime.repo, vehicle_id=vehicle, vehicle_configuration_id=None)
        assert active.wait(6), "the unrelated Bankone resolution did not start"

    def verify():
        assert active.is_set() and not finished.is_set()
        assert not overlapping.is_set(), "a second Bankone resolution overlapped the first"
        release.set()

    return start, verify


def hold_banktwo_continuation(runtime, configuration):
    from threading import Event

    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs

    active, release, overlapping = Event(), Event(), Event()
    runtime.stack.callback(release.set)
    supplier = runtime.servers["banktwo"]
    original_response = supplier.response
    make = "Earlier Fixture Index"
    ref = "fixture-earlier-index"
    page_count = 12
    requests = []
    earlier_job = None

    def response(path, payload=None):
        parsed = urlsplit(path)
        if parsed.path == "/v1/vehicle-resolutions" and payload and payload.get("make") == make:
            return 200, supplier.envelope(selector=payload, candidates=[
                {"opaque_ref": ref, "label": "Base", "confidence": 1.0},
            ])
        if parsed.path != f"/v1/vehicles/{ref}/articles":
            if active.is_set() and not release.is_set():
                overlapping.set()
            return original_response(path, payload)
        cursor = int(parse_qs(parsed.query).get("cursor", ["0"])[0])
        requests.append(cursor)
        if cursor == 1:
            active.set()
            assert release.wait(10), "the paid scope did not reach the queue"
        complete = cursor == page_count - 1
        page = supplier.envelope(complete=complete, articles=[{
            "opaque_ref": f"entry-{cursor}", "title": "Earlier index entry", "resource_ref": f"body-{cursor}",
        }])
        if not complete:
            page["next_cursor"] = str(cursor + 1)
        return 200, page

    supplier.response = response

    def start():
        nonlocal earlier_job
        vehicle = seed_vehicle(runtime.repo)
        with runtime.repo.connect() as conn:
            conn.execute("UPDATE vehicles SET make=%s WHERE vehicle_id=%s", (make, vehicle))
        _, banktwo = ensure_article_catalog_jobs(runtime.repo, vehicle_id=vehicle, vehicle_configuration_id=None)
        earlier_job = banktwo.job_id
        assert active.wait(6), "the earlier index did not start its second page"

    def admit_paid_scope():
        until = time.monotonic() + 5
        while time.monotonic() < until:
            with runtime.repo.connect() as conn:
                row = conn.execute("""SELECT j.status FROM source_fetch_jobs j
                    JOIN catalog_article_provider_scopes s ON s.current_job_id=j.source_fetch_job_id
                    WHERE s.vehicle_configuration_id=%s AND s.provider_slug='banktwo'""",
                    (configuration,)).fetchone()
            if row and row["status"] == "pending":
                assert not overlapping.is_set()
                release.set()
                return
            time.sleep(.05)
        raise AssertionError("the paid scope was not queued")

    def earlier_state():
        with runtime.repo.connect() as conn:
            return conn.execute("""SELECT s.catalog_provider_scope_id,s.status,s.row_count,
                       j.status AS job_status,j.lease_owner,j.lease_token,j.retry_count
                FROM source_fetch_jobs j JOIN catalog_article_provider_scopes s
                  ON s.current_job_id=j.source_fetch_job_id
                WHERE j.source_fetch_job_id=%s""", (earlier_job,)).fetchone()

    def verify_handoff():
        row = earlier_state()
        assert row["job_status"] == "pending" and row["lease_owner"] is None
        assert 2 <= row["row_count"] < page_count and row["retry_count"] == 0
        return row["row_count"]

    def verify_completion():
        until = time.monotonic() + 6
        while time.monotonic() < until:
            row = earlier_state()
            if row["job_status"] == "completed":
                break
            time.sleep(.05)
        assert row["status"] == "complete" and row["row_count"] == page_count
        assert row["lease_token"] > 1 and row["retry_count"] == 1 and requests == list(range(page_count))
        with runtime.repo.connect() as conn:
            pages = conn.execute("""SELECT page_number,cursor_in,cursor_out,complete
                FROM catalog_article_index_pages WHERE catalog_provider_scope_id=%s ORDER BY page_number""",
                (row["catalog_provider_scope_id"],)).fetchall()
            articles = conn.execute("""SELECT a.source_article_ref,a.source_sort_order FROM canonical_articles a
                JOIN catalog_article_provider_scopes s USING (scope_key,provider_slug)
                WHERE s.catalog_provider_scope_id=%s ORDER BY a.source_sort_order""",
                (row["catalog_provider_scope_id"],)).fetchall()
        assert pages == [
            {"page_number": number, "cursor_in": str(number) if number else None,
             "cursor_out": str(number + 1) if number < page_count - 1 else None,
             "complete": number == page_count - 1}
            for number in range(page_count)
        ]
        assert articles == [
            {"source_article_ref": f"entry-{number}", "source_sort_order": number * 1000}
            for number in range(page_count)
        ]

    return start, admit_paid_scope, verify_handoff, verify_completion


async def verify_reserved_figure(image, gate, dimensions):
    from playwright.async_api import expect

    measure = """image => {
        const box = image.getBoundingClientRect();
        return [box.width, box.height, image.closest('figure').getBoundingClientRect().height];
    }"""
    try:
        await expect(image).to_have_attribute("width", str(dimensions[0]))
        await expect(image).to_have_attribute("height", str(dimensions[1]))
        assert await image.evaluate("image => !image.complete && image.naturalWidth === 0")
        reserved = await image.evaluate(measure)
    finally:
        gate.set()
    assert tuple(await image.evaluate("""async image => {
        await image.decode();
        return [image.naturalWidth, image.naturalHeight];
    }""")) == dimensions
    await expect(image.locator("xpath=ancestor::figure[1]").locator(".figure-size")).to_be_visible()
    loaded = await image.evaluate(measure)
    assert all(abs(before - after) <= 4 for before, after in zip(reserved, loaded, strict=True)), (reserved, loaded)


@asynccontextmanager
async def retry_workshop_entry(browser, url, storage, fixture_route, *, persistent=False, stalled=False):
    from playwright.async_api import expect

    context = await browser.new_context(ignore_https_errors=True, service_workers="block", storage_state=storage)
    entry_path = urlsplit(url).path
    navigations, writes = [], []
    failed_entries = set()
    automatic_retry = asyncio.Event()
    release_app = asyncio.Event()
    fail_count = 2 if persistent else 1

    def app_request(url):
        return urlsplit(url).path.endswith("/app.mjs")

    async def block_app(route):
        if stalled:
            await release_app.wait()
            await route.fallback()
        elif len(navigations) <= fail_count:
            failed_entries.add(len(navigations))
            await route.abort("connectionreset")
        else:
            await route.fallback()

    def track_entry(request):
        path = urlsplit(request.url).path
        if path == entry_path and request.is_navigation_request():
            navigations.append(request.url)
            if len(navigations) == 2:
                automatic_retry.set()
        if path.startswith(("/auth/", "/v1/", "/workshop/")) and request.method not in ("GET", "HEAD", "OPTIONS"):
            writes.append((request.method, path))

    try:
        await context.route("**/*", fixture_route)
        page = await context.new_page()
        page.on("request", track_entry)
        await page.route(app_request, block_app)
        await page.goto(url, wait_until="commit")
        recovery = page.locator("#workshop-startup-recovery")
        if stalled:
            await expect(recovery.get_by_role("button", name="Try again")).to_be_visible(timeout=7000)
            await expect(recovery).to_have_attribute("data-tone", "loading")
            assert navigations == [url]
            release_app.set()
        else:
            await asyncio.wait_for(automatic_retry.wait(), timeout=5)
        if persistent:
            await expect(recovery).to_be_visible(timeout=5000)
            assert navigations == [url, url]
            async with page.expect_request(lambda request: request.is_navigation_request() and request.url == url):
                await recovery.get_by_role("button", name="Try again").click()
        await expect(recovery).to_be_hidden()
        yield page
        await page.wait_for_function("!history.state?.workshopPickerStartupRetry")
        if stalled:
            assert navigations == [url] and not failed_entries
        else:
            assert navigations == [url] * (fail_count + 1)
            assert failed_entries == set(range(1, fail_count + 1))
        assert not writes
    finally:
        release_app.set()
        await context.close()


async def verify_paid_checkout_startup_retry(browser, origin, storage, fixture_route, order, article, engine):
    from playwright.async_api import expect

    url = f"{origin}/workshop?order={order['order_id']}"
    order_status = f"{origin}/v1/workshop/orders/{order['order_id']}"
    for manual in (False, True):
        context = await browser.new_context(ignore_https_errors=True, service_workers="block", storage_state=storage)
        navigations, writes, order_reads = [], [], []
        release_app = asyncio.Event()

        async def hold_first_app(route):
            if len(navigations) == 1:
                await release_app.wait()
            await route.fallback()

        def track(request):
            if request.is_navigation_request() and urlsplit(request.url).path == "/workshop":
                navigations.append(request.url)
            if request.url == order_status and request.method == "GET":
                order_reads.append(request)
            if urlsplit(request.url).path.startswith(("/auth/", "/v1/", "/workshop/")) and request.method not in (
                "GET", "HEAD", "OPTIONS",
            ):
                writes.append(request)

        try:
            await context.route("**/*", fixture_route)
            page = await context.new_page()
            page.on("request", track)
            await page.route(lambda address: urlsplit(address).path.endswith("/app.mjs"), hold_first_app)
            start = time.monotonic()
            await page.goto(url, wait_until="commit")
            recovery = page.locator("#workshop-startup-recovery")
            retry = recovery.get_by_role("button", name="Try again")
            await expect(retry).to_be_visible(timeout=7000)
            retry_ms = round((time.monotonic() - start) * 1000)
            await expect(recovery).to_have_attribute("data-tone", "loading")
            await expect(recovery.get_by_role("alert")).to_have_text("Workshop is taking longer to check this payment.")
            assert navigations == [url] and not order_reads and not writes
            if manual:
                position = await retry.bounding_box()
                assert position
                # WebKit can wait for a stable frame while the app module is held.
                await page.mouse.click(position["x"] + position["width"] / 2, position["y"] + position["height"] / 2)
            else:
                release_app.set()
            await expect(page.locator(f'#articles a[href*="{article}"]')).to_be_visible(timeout=15000)
            await expect(recovery).to_be_hidden()
            params = parse_qs(urlsplit(page.url).query)
            assert params.get("configuration") == [order["configuration_id"]] and params.get("region") == [order["region"]]
            assert len(order_reads) == 1
            response = await order_reads[0].response()
            assert response and response.ok
            status = await response.json()
            assert status["state"] == "paid" and all(
                status[key] == order[key] for key in ("order_id", "configuration_id", "region")
            )
            assert navigations == [url] * (2 if manual else 1) and not writes
            print("WORKSHOP_CHECKOUT_STARTUP " + json.dumps({
                "engine": engine, "headed": True, "manual_retry": manual, "retry_ms": retry_ms,
                "index_ms": round((time.monotonic() - start) * 1000),
                "existing_paid_order_verified": True, "order_reads": len(order_reads), "startup_writes": len(writes),
            }), flush=True)
        finally:
            release_app.set()
            await context.close()


async def verify_public_demo_read(browser, fixture, configuration, article, expected_text, figure_sha, engine):
    from playwright.async_api import expect

    main = "https://autodata.cars.tk"
    direct = "https://autodata.curtis.click"
    saved = f"{main}/workshop?configuration={configuration}&region=US&article={article}&demo=1"
    index = f"/v1/catalog/vehicles/{configuration}/articles"
    article_path = f"{index}/{article}"

    for fallback in (False, True):
        context = await browser.new_context(ignore_https_errors=True, service_workers="block")
        requests, results = [], []
        direct_read_started = None
        fallback_started_ms = None
        fallback_started = asyncio.Event()

        async def relay(route):
            nonlocal direct_read_started, fallback_started_ms
            url = urlsplit(route.request.url)
            origin = f"{url.scheme}://{url.netloc}"
            if origin not in (main, direct):
                await route.abort()
                return
            request_path = url.path + (f"?{url.query}" if url.query else "")
            headers = await route.request.all_headers()
            if url.path in (article_path, index):
                requests.append((origin, url.path, route.request.method))
            if origin == direct and url.path == article_path:
                assert parse_qs(url.query) == {"region": ["US"], "demo": ["1"], "fitment": ["1"]}
                assert "cookie" not in headers and "authorization" not in headers and "prefer" not in headers
                if fallback:
                    direct_read_started = time.monotonic()
                    await fallback_started.wait()
                    await route.abort("timedout")
                    return
            headers.pop("host", None)
            headers["x-workshop-fixture-demo"] = "1"
            if origin == main and url.path == article_path:
                if fallback:
                    assert direct_read_started is not None
                    fallback_started_ms = round(1000 * (time.monotonic() - direct_read_started))
                    fallback_started.set()
                await asyncio.sleep(0.25)
            response = await route.fetch(url=fixture + request_path, headers=headers, max_redirects=0)
            if url.path == article_path and response.ok:
                payload = await response.json()
                results.append((origin, headers.get("origin"), response.headers, payload))
            await route.fulfill(response=response)

        try:
            await context.route("**/*", relay)
            page = await context.new_page()
            started = time.monotonic()
            await page.goto(saved, wait_until="commit")
            await expect(page.locator("#article-content")).to_contain_text(expected_text, timeout=12000)
            first_text_ms = round((time.monotonic() - started) * 1000)
            await expect(page.locator("#reader-engine")).to_have_text("US")
            image = page.locator("#article-content img").first
            await image.scroll_into_view_if_needed()
            await expect(image).to_be_visible()
            assert await image.evaluate("image => image.decode().then(() => image.naturalWidth > 0)")
            decoded = await image.evaluate("""async image => {
                const response = await fetch(image.currentSrc);
                const bytes = await response.arrayBuffer();
                return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
                    .map(byte => byte.toString(16).padStart(2, '0')).join('');
            }""")
            assert decoded == figure_sha
            assert page.url == saved and requests == ([(direct, article_path, "GET")] +
                                                      ([(main, article_path, "GET")] if fallback else []))
            resolved_origin, caller, response_headers, payload = results[0]
            assert len(results) == 1 and resolved_origin == (main if fallback else direct)
            assert payload["configuration"]["id"] == configuration and payload["configuration"]["region"] == "US"
            assert payload["article"]["id"] == article and payload["article"]["canonical_revision_id"]
            assert response_headers["cache-control"] == "private, no-store"
            if not fallback:
                assert caller == main and response_headers.get("access-control-allow-origin") == main
                assert "access-control-allow-credentials" not in response_headers
                assert "workshop-demo-fitment" in response_headers["preference-applied"]
            else:
                assert 200 <= fallback_started_ms < 1000
            print("WORKSHOP_PUBLIC_DEMO_TRANSPORT " + json.dumps({
                "engine": engine, "headed": True, "fallback": fallback, "first_text_ms": first_text_ms,
                "fallback_started_ms": fallback_started_ms, "exact_scope_and_figure_verified": True,
            }), flush=True)
        finally:
            fallback_started.set()
            await context.close()

    context = await browser.new_context(ignore_https_errors=True, service_workers="block")
    try:
        info = await context.request.get(fixture + "/__fixture/demo-origins")
        addresses = await info.json()
        detail = fixture + "/__fixture/demo-article?region=US&fitment=1"
        page = await context.new_page()
        async def read(url):
            return await page.evaluate("""async url => {
                try {
                    const reply = await fetch(url, {credentials:'omit', cache:'no-store'});
                    const body = await reply.json();
                    return {status:reply.status, article:body.article?.id, configuration:body.configuration?.id};
                } catch (error) {
                    return {blocked:error instanceof TypeError};
                }
            }""", url)

        await page.goto(addresses["main"], wait_until="domcontentloaded")
        assert await read(detail + "&demo=1") == {"status": 200, "article": article, "configuration": configuration}
        assert await read(detail) == {"blocked": True}
        assert await read(detail + "&demo=1&region=US") == {"blocked": True}
        assert await read(detail.replace("region=US", "region=") + "&demo=1") == {"blocked": True}
        await page.goto(addresses["outside"], wait_until="domcontentloaded")
        assert await read(detail + "&demo=1") == {"blocked": True}
        print("WORKSHOP_PUBLIC_DEMO_CORS " + json.dumps({
            "engine": engine, "headed": True, "direct_read_matches": True,
            "ordinary_private_detail_blocked": True, "outside_origin_blocked": True,
        }), flush=True)
    finally:
        await context.close()


async def verify_figure_transport_retry(browser, url, storage, fixture_route, detail, digest):
    context = await browser.new_context(ignore_https_errors=True, service_workers="block", storage_state=storage)
    image_prefix = "/v1/catalog/images/v2."
    reads = []
    media = []
    detail_path = urlsplit(detail).path
    source_path = detail_path + "/source"

    async def route_image(route):
        media.append(route.request.url)
        if len(media) == 1:
            await route.abort("connectionreset")
        else:
            await route.fallback()

    def image_response(response):
        return response.ok and urlsplit(response.url).path.startswith(image_prefix)

    try:
        await context.route("**/*", fixture_route)
        page = await context.new_page()
        page.on("request", lambda request: reads.append(urlsplit(request.url).path)
                if request.method == "GET" and urlsplit(request.url).path in (detail_path, source_path) else None)
        await page.route(lambda url: urlsplit(url).path.startswith(image_prefix), route_image)
        async with page.expect_response(image_response) as pending:
            assert (await page.goto(url, wait_until="commit")).ok
            await page.locator("#article-content img").first.scroll_into_view_if_needed()
        await page.wait_for_function("document.querySelector('#article-content img')?.naturalWidth > 0")
        assert len(media) == 2 and media[0] == media[1] and reads == [detail_path]
        assert sha256(await (await pending.value).body()).hexdigest() == digest

        media.clear()
        async with page.expect_response(image_response) as pending:
            await page.locator("#open-original").click()
            await page.locator("#source-review-frame img").first.scroll_into_view_if_needed()
        await page.wait_for_function("document.querySelector('#source-review-frame img')?.naturalWidth > 0")
        assert len(media) == 2 and media[0] == media[1] and reads == [detail_path, source_path]
        assert sha256(await (await pending.value).body()).hexdigest() == digest
    finally:
        await context.close()


async def exercise_simulated_payment(origin, scope, customer_account, repair=None, table_variant=None, table_repair=None):
    from playwright.async_api import async_playwright, expect

    configuration = scope["configuration"]
    article = scope["article"]
    route = f"{origin}/workshop/?configuration={configuration}&region=US"
    detail = f"{origin}/v1/catalog/vehicles/{configuration}/articles/{article}?region=US"
    quote = f"{origin}/v1/workshop/quote?configuration_id={configuration}&region=US"
    checkout_path = "/v1/workshop/checkout-sessions"
    cold_index = scope.get("authored_index")
    bankone_hold = scope.get("bankone_hold")
    banktwo_hold = scope.get("banktwo_hold")
    picker_values = (("year", "2005"), ("make", "cadillac-truck"), ("model", "escalade-esv-awd")) if cold_index else (
        ("year", "2024"), ("make", "example"), ("model", "car"),
    )

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
            media_gate = None

            async def route_fixture(request_route):
                if media_gate and urlsplit(request_route.request.url).path.startswith("/v1/catalog/images/"):
                    await media_gate.wait()
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
            market = scope.get("labelled_market")
            if market:
                await verify_labelled_market_picker(page, origin, *market)
            if scope.get("late_group_models"):
                await verify_late_grouped_models(page, origin)
            if repair is None and table_variant is None:
                picker_started = time.monotonic()
                await page.goto(f"{origin}/workshop/")
                for field, value in (*picker_values, ("configuration", configuration)):
                    await page.locator(f"#{field}").select_option(value)
                expected = {field: [value] for field, value in picker_values}
                expected.update(configuration=[configuration], region=["US"])
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
            if cold_index:
                await expect(page.locator("#purchase-selection")).to_have_text(
                    "2005 / Cadillac Truck / Escalade Esv Awd / 6.0 L / US"
                )
                picker_ms = round((time.monotonic() - picker_started) * 1000)
            await api_signin(page)
            if market:
                misplaced, verified = market
                for identifier, expected in ((misplaced, 404), (verified, 200)):
                    offer = await owner.request.get(f"{origin}/v1/workshop/quote?configuration_id={identifier}&region=US")
                    assert offer.status == expected
                    if expected == 200:
                        assert (await offer.json())["purchasable"] is True
                refused = await page.evaluate("""async ([configuration, key]) => {
                    const session = await fetch('/auth/session');
                    if (!session.ok) throw new Error(String(session.status));
                    const {csrf_token} = await session.json();
                    const response = await fetch('/v1/workshop/checkout-sessions', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'Idempotency-Key': key,
                                  'X-CSRF-Token': csrf_token},
                        body: JSON.stringify({configuration_id: configuration, region: 'US',
                            expected_mode: 'simulation', terms_version: 'workshop-v1'}),
                    });
                    return [response.status, (await response.json()).error?.code];
                }""", [misplaced, str(uuid4())])
                assert refused == [409, "CONFIGURATION_MARKET_UNVERIFIED"]
                print(f"WORKSHOP_LABELLED_MARKET headed={engine} refused={refused[0]} verified_offer=200", flush=True)
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
            if bankone_hold:
                await asyncio.to_thread(bankone_hold[0])
            if banktwo_hold:
                await asyncio.to_thread(banktwo_hold[0])

            purchase_started = time.monotonic()
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
            checkout_ms = round((time.monotonic() - purchase_started) * 1000)
            assert result["state"] == "owned"
            assert result["configuration_id"] == configuration and result["region"] == "US"
            assert result["library_item_id"] == result["order_id"] and not result.get("checkout_url")
            assert urlsplit(page.url).path.rstrip("/") == "/workshop"

            library_started = time.monotonic()
            await page.locator("#my-vehicles").click()
            await expect(page.locator("#library-items > li")).to_have_count(1)
            library_ms = round((time.monotonic() - library_started) * 1000)
            reload_started = time.monotonic()
            await page.reload()
            await expect(page.locator("#library-items > li")).to_have_count(1)
            library_reload_ms = round((time.monotonic() - reload_started) * 1000)
            await expect(page.locator("#library-items h3")).to_contain_text(
                "Escalade" if cold_index else "Paid selected"
            )
            if repair is None and table_variant is None and not banktwo_hold:
                await api_control(owner, origin, "control/start-workers")
            index_started = time.monotonic()
            await page.get_by_role("button", name="Open articles", exact=True).click()
            if banktwo_hold:
                await asyncio.to_thread(banktwo_hold[1])
            article_link = page.locator(f'#articles a[href*="{article}"]')
            if cold_index:
                try:
                    await expect(article_link).to_contain_text(cold_index["title"], timeout=15000)
                except AssertionError:
                    with cold_index["repository"].connect() as conn:
                        states = conn.execute("""SELECT s.provider_slug,s.status,s.row_count,s.error_code,j.status AS job_status
                            FROM catalog_article_provider_scopes s LEFT JOIN source_fetch_jobs j
                                ON j.source_fetch_job_id=s.current_job_id
                            WHERE s.vehicle_configuration_id=%s ORDER BY s.provider_slug""",
                            (cold_index["configuration"],)).fetchall()
                    print(json.dumps({"cold_index_states": states, "fixture_model_queries": cold_index["queries"],
                                      "second_page_requested": cold_index["pending"].is_set()}), flush=True)
                    raise
                first_index_ms = round((time.monotonic() - index_started) * 1000)
                if bankone_hold:
                    bankone_hold[1]()
                assert await asyncio.to_thread(cold_index["pending"].wait, 3)
                if banktwo_hold:
                    earlier_rows = await asyncio.to_thread(banktwo_hold[2])
                assert cold_index["queries"] == [cold_index["model"]]
                assert cold_index["resolution_queries"] == cold_index["expected_resolution_queries"]
                with cold_index["repository"].connect() as conn:
                    rows = conn.execute("""SELECT s.status,s.row_count,p.complete,b.adapter_name
                        FROM catalog_article_provider_scopes s
                        JOIN catalog_article_index_pages p USING(catalog_provider_scope_id)
                        JOIN source_snapshots b ON b.source_snapshot_id=p.source_snapshot_id
                        WHERE s.vehicle_configuration_id=%s AND s.provider_slug='banktwo'""",
                        (cold_index["configuration"],)).fetchall()
                    assert rows == [{"status": "running", "row_count": 1, "complete": False, "adapter_name": "banktwo"}]
                cold_index["release"].set()
                if banktwo_hold:
                    await asyncio.to_thread(banktwo_hold[3])
                    await api_control(owner, origin, "control/start-workers")
                    print("WORKSHOP_CATALOG_PAGE_HANDOFF " + json.dumps({
                        "engine": engine, "headed": True, "first_index_ms": first_index_ms,
                        "earlier_rows_at_visibility": earlier_rows, "earlier_index_completed_in_order": True,
                    }), flush=True)
            article_started = time.monotonic()
            if cold_index:
                media_gate = asyncio.Event()
            await article_link.click()
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
            if cold_index:
                await verify_reserved_figure(image, media_gate, cold_index["figure_dimensions"])
            await expect(image).to_be_visible()
            assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
            reader_ms = round((time.monotonic() - article_started) * 1000)
            assert (await owner.request.get(detail)).status == 200
            media = await image.evaluate("(node) => node.currentSrc")
            assert urlsplit(media).netloc == urlsplit(origin).netloc
            assert urlsplit(media).path.startswith("/v1/catalog/images/v2.")
            asset = await owner.request.get(media)
            assert asset.status == 200 and asset.headers["content-type"].startswith("image/png")
            if scope.get("pending_saved_reader"):
                await verify_pending_saved_article(owner, origin, configuration, article, expected_text)
            if cold_index:
                assert sha256(await asset.body()).hexdigest() == cold_index["figure_sha"]
                await expect(page.locator("#article-content")).to_contain_text("Fit the replacement unit.")
                await expect(page.locator("#article-content")).to_contain_text("Do not reuse the seal.")
                await expect(page.locator("#article-content")).not_to_contain_text("Remove the pump.")
                rendered = await page.locator("#article-content").inner_text()
                assert rendered.index("Do not reuse the seal.") < rendered.index("Take off the pump.") < rendered.index("Fit the replacement unit.")
                figure_step = "(node) => node.closest('.procedure-step, li')?.textContent ?? ''"
                assert "Take off the pump." in await image.evaluate(figure_step)
                media_gate = asyncio.Event()
                await page.locator("#open-original").click()
                await expect(page.locator("#source-review-frame")).to_contain_text("Remove the pump.")
                await expect(page.locator("#source-review-frame")).to_contain_text("Do not reuse the seal.")
                await expect(page.locator("#reference-data")).to_contain_text(cold_index["body_sha"])
                source_image = page.locator("#source-review-frame img").first
                await verify_reserved_figure(source_image, media_gate, cold_index["figure_dimensions"])
                assert await source_image.evaluate("(img) => img.decode().then(() => img.naturalWidth > 0)")
                assert "Remove the pump." in await source_image.evaluate(figure_step)
                original_image = await owner.request.get(await source_image.evaluate("(img) => img.currentSrc"))
                assert original_image.ok and sha256(await original_image.body()).hexdigest() == cold_index["figure_sha"]
                async def wait_complete():
                    for _ in range(150):
                        with cold_index["repository"].connect() as conn:
                            finished = conn.execute("""SELECT status,row_count FROM catalog_article_provider_scopes
                                WHERE vehicle_configuration_id=%s AND provider_slug='banktwo'""",
                                (cold_index["configuration"],)).fetchone()
                        if finished == {"status": "complete", "row_count": 2}:
                            return
                        await asyncio.sleep(.05)
                    raise AssertionError(finished)
                await wait_complete()

                warm_started = time.monotonic()
                await page.locator("#my-vehicles").click()
                await expect(page.locator("#library-items h3")).to_contain_text("Escalade")
                warm_library_ms = round((time.monotonic() - warm_started) * 1000)
                warm_started = time.monotonic()
                await page.get_by_role("button", name="Open articles", exact=True).click()
                await expect(article_link).to_contain_text(cold_index["title"])
                warm_index_ms = round((time.monotonic() - warm_started) * 1000)
                warm_started = time.monotonic()
                await article_link.click()
                await expect(page.locator("#article-kind")).to_have_text("Workshop article")
                await expect(page.locator("#article-content")).to_contain_text(expected_text)
                await expect(image).to_be_visible()
                assert await image.evaluate("(node) => node.decode().then(() => node.naturalWidth > 0)")
                warm_reader_ms = round((time.monotonic() - warm_started) * 1000)
                assert "Take off the pump." in await image.evaluate(figure_step)
                print("WORKSHOP_AUTHORED_MODEL_INDEX " + json.dumps({
                    "engine": engine, "headed": True, "scope": configuration, "article": article,
                    "revision": os.environ.get("AUTODATA_R3_CANDIDATE_SHA"),
                    "picker_ms": picker_ms, "checkout_ms": checkout_ms,
                    "library_ms": library_ms, "library_reload_ms": library_reload_ms,
                    "first_index_ms": first_index_ms, "reader_ms": reader_ms,
                    "warm_library_ms": warm_library_ms, "warm_index_ms": warm_index_ms, "warm_reader_ms": warm_reader_ms,
                    "generic_resolution_reads": len(cold_index["resolution_queries"]),
                    "independent_supplier_still_running_when_index_visible": bool(bankone_hold),
                    "stored_page_before_completion": True, "complete_rows": 2,
                    "source_prose_warning_order_and_asset_matched": True, "figure_placement_and_source_sha_matched": True,
                    "reader_and_original_reserved_figure_space": True,
                }), flush=True)
                if scope.get("retry_workshop_entry"):
                    storage = await owner.storage_state()
                    await verify_public_demo_read(browser, origin, configuration, article, expected_text,
                                                  cold_index["figure_sha"], engine)
                    await verify_paid_checkout_startup_retry(browser, origin, storage, route_fixture, result, article, engine)
                    await verify_figure_transport_retry(browser, page.url, storage, route_fixture, detail, cold_index["figure_sha"])
                    print(json.dumps({"case": "workshop-figure-transport-retry", "engine": engine, "headed": True,
                                      "reader_and_original_verified": True}), flush=True)
                    async with retry_workshop_entry(browser, page.url, storage, route_fixture) as saved:
                        await expect(saved.locator("#article-content")).to_contain_text(expected_text)
                        await saved.locator("#article-content img").first.scroll_into_view_if_needed()
                        await saved.wait_for_function("document.querySelector('#article-content img')?.naturalWidth > 0")
                        recovered_url = await saved.locator("#article-content img").first.evaluate("node => node.currentSrc")
                        recovered_image = await saved.request.get(recovered_url)
                        assert recovered_image.ok and sha256(await recovered_image.body()).hexdigest() == cold_index["figure_sha"]
                    async with retry_workshop_entry(browser, page.url, storage, route_fixture, stalled=True) as saved:
                        await expect(saved.locator("#article-content")).to_contain_text(expected_text)
                        recovered = saved.locator("#article-content img").first
                        await recovered.scroll_into_view_if_needed()
                        assert await recovered.evaluate("image => image.decode().then(() => image.naturalWidth > 0)")
                    await page.locator("#my-vehicles").click()
                    await expect(page.locator("#library-items > li")).to_have_count(1)
                    for persistent in (False, True):
                        async with retry_workshop_entry(browser, page.url, storage, route_fixture, persistent=persistent) as saved:
                            await expect(saved.locator("#library-items > li")).to_have_count(1)
                            await expect(saved.locator("#library-items h3")).to_contain_text("Escalade")
                    print(json.dumps({"case": "workshop-entry-recovery", "engine": engine, "headed": True,
                                      "protected_article_and_library_verified": True,
                                      "stalled_article_completed_without_reload": True,
                                      "initial_failure_automatically_retried": True,
                                      "second_failure_used_manual_retry": True, "startup_writes": 0}), flush=True)

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


@pytest.mark.parametrize("variant", [
    "payment", "list-starts", "authored-table", "archived-table", "source-table", "labelled-market", "late-group-models",
    "authored-model-index", "authored-model-index-competing-fitment", "authored-model-index-held-bankone",
    "authored-model-index-held-banktwo",
])
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
        if variant == "labelled-market":
            scope["labelled_market"] = labelled_market_fixture(runtime)
        if variant == "late-group-models":
            scope["late_group_models"] = True
        if variant == "payment":
            scope["pending_saved_reader"] = True
        if variant.startswith("authored-model-index"):
            scope = authored_model_index_fixture(runtime, scope, competing_fitment=variant.endswith("-competing-fitment"))
        if variant == "authored-model-index":
            scope["retry_workshop_entry"] = True
        if variant == "authored-model-index-held-bankone":
            scope["bankone_hold"] = hold_unrelated_bankone_catalog(runtime)
        if variant == "authored-model-index-held-banktwo":
            scope["banktwo_hold"] = hold_banktwo_continuation(runtime, scope["configuration"])
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
            AUTODATA_WORKSHOP_BROWSER_PUBLIC_DEMO=("1" if variant == "authored-model-index" else ""),
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
