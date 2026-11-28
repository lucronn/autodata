"""Verify Banktwo authored registration, source storage and refresh in a headed browser."""

from contextlib import ExitStack
from hashlib import sha256
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest

if os.environ.get("AUTODATA_REQUIRE_WORKSHOP_SIMULATION_BROWSER") != "1":
    pytest.skip("requires the isolated headed Workshop fixture", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/tests"))

from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.banktwo_authored_article_registry import register_banktwo_authored_articles
from autodata_ingestion.catalog_coverage import refresh_catalog_jobs
from autodata_ingestion.source_job_persistence import ensure_article_job
from lifecycle_support import LifecycleRuntime, fresh_database
from test_catalog_api_integration import serve
from test_paid_catalog_api_integration import configure_scoped_runtime


def digest(value):
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def install_markup(runtime):
    supplier = runtime.servers["banktwo"]
    base = "/api/v1/content/carids/42"
    index_path = base + "/guid/fixture-index"
    child_path = base + "/guid/fixture-procedure"
    media_path = base + "/svgs/fixture-drawing?locale=en-US&region=US"
    parent_markup = (
        f'<ol><li>Inspect the seal. See <a href="{index_path}">Pump service options</a>.</li></ol>'
        f'<p>Remove the pump.</p><img src="{media_path}">'
    )
    index_markup = f'<h2>Pump service options</h2><p><a href="{child_path}">Pump seal removal</a></p>'
    child_markup = f'<p>Disconnect the pump.</p><img src="{media_path}"><p>Remove the pump seal.</p>'
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="10"><rect width="16" height="10"/></svg>'
    supplier.body(json.dumps({
        "car": {"id": "42"}, "_embedded": {"data": {"article": {"content": parent_markup}}},
    }).encode(), "application/hal+json", assets=["drawing"],
                  asset_bindings=[{"source_url": media_path, "resource_ref": "drawing"}])
    resources = {
        "index": ("fixture-index", "Pump service options", index_markup),
        "child": ("fixture-procedure", "Pump seal removal", child_markup),
    }
    for ref, (guid, title, markup) in resources.items():
        resource = json.dumps({
            "id": guid, "title": title, "_embedded": {"car": {"id": "42"}, "data": {"content": markup}},
        }).encode()
        supplier.body(resource, "application/hal+json", ref=ref,
                      assets=["drawing"] if ref == "child" else [],
                      asset_bindings=[{"source_url": media_path, "resource_ref": "drawing"}] if ref == "child" else [])
    supplier.body(svg, "image/svg+xml", ref="drawing", kind="asset")
    original = supplier.response
    paths = {
        "body": (parent_markup, index_path, index_markup, "index"),
        "index": (index_markup, child_path, child_markup, "child"),
    }

    def respond(path, request_payload=None):
        endpoint = urlsplit(path).path
        if endpoint.endswith("/article-search"):
            assert endpoint == "/v1/vehicles/vehicle%3Afixture/article-search"
            ref = request_payload["parent_resource_ref"]
            markup, child, _, child_ref = paths[ref]
            assert request_payload["markup_sha256"] == digest(markup)
            assert request_payload["authored_path_sha256"] == digest(child)
            title = resources[child_ref][1]
            return 200, supplier.envelope(complete=True, articles=[
                {"opaque_ref": child_ref, "resource_ref": child_ref, "title": title},
            ])
        status, payload = original(path, request_payload)
        if status == 200 and endpoint.startswith("/v1/resources/"):
            ref = endpoint.rsplit("/", 1)[-1]
            if ref in resources:
                payload["source_locator"] = "https://source.invalid" + base + "/guid/" + resources[ref][0]
        return status, payload

    supplier.response = respond
    return index_path, child_path, svg


def register_fixture_chain(runtime, index_path, child_path, *, model_client=None, rewrite_child=True):
    repo, parent = runtime.repo, runtime.article_id
    with repo.connect() as conn:
        profile = conn.execute("SELECT target_rewrite_profile_version FROM canonical_articles WHERE canonical_article_id=%s",
                               (parent,)).fetchone()["target_rewrite_profile_version"]
    ensure_article_job(repo, parent, normalization_version="ordered-article-v1", rewrite_profile_version=profile)

    def run(job_id, client):
        assert run_article_worker_once(repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=client, job_id=job_id)

    def state(article):
        with repo.connect() as conn:
            return conn.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article,)).fetchone()

    def register(article, path):
        origin = state(article)
        result = register_banktwo_authored_articles(
            repo, article, origin["current_source_revision_id"], path_digests=[digest(path)],
            connector=runtime.registry["banktwo"], object_store=runtime.objects,
        )
        (authored, target), = result
        assert authored == digest(path)
        return target

    run(state(parent)["current_job_id"], model_client)
    index = register(parent, index_path)
    same_job = state(index)["current_job_id"]
    stored_objects = {item.object_name for item in runtime.objects.client.list_objects(runtime.bucket, recursive=True)}
    assert register(parent, index_path) == index and state(index)["current_job_id"] == same_job
    assert {item.object_name for item in runtime.objects.client.list_objects(runtime.bucket, recursive=True)} == stored_objects
    run(same_job, model_client)
    child = register(index, child_path)
    run(state(child)["current_job_id"], model_client if rewrite_child else None)
    if model_client:
        with repo.connect() as conn:
            rows = conn.execute("""
                SELECT canonical_article_id,title,availability,content_origin,canonical_revision_id,processing_error_code
                FROM catalog_article_current WHERE canonical_article_id=ANY(%s)
            """, ([parent, index, child],)).fetchall()
        assert len(rows) == 3, json.dumps(rows, default=str)
        for row in rows:
            published = row["canonical_article_id"] != child or rewrite_child
            assert row["availability"] == "available", row["title"]
            assert row["content_origin"] == ("canonical" if published else "source"), row["title"]
            assert bool(row["canonical_revision_id"]) == published, row["title"]
        assert model_client.calls == (2 if rewrite_child else 1)
    return index, child


def authored_guid_reader_fixture(runtime, *, rewrite_child=True):
    index_path, child_path, svg = install_markup(runtime)

    class Model:
        _model = "fixture-banktwo-guid"
        calls = 0

        def complete_json(self, prompt):
            self.calls += 1
            rewrites = {
                "Inspect the seal. See Pump service options.": "Check the seal. Refer to Pump service options.",
                "Remove the pump.": "Take off the pump.",
                "Disconnect the pump.": "Begin by disconnecting the pump.",
                "Remove the pump seal.": "Take off the pump seal.",
            }
            return {
                "introduction": "This service information covers the pump and its seal.",
                "replacements": [
                    {"block_id": slot["block_id"], "path": slot["path"],
                     "action": slot["required_action"],
                     "text": slot["text"] if slot["required_action"] == "retain" else rewrites[slot["text"]],
                     "reason": "Keep the authored wording." if slot["required_action"] == "retain" else ""}
                    for slot in json.loads(prompt)["slots"]
                ],
            }

    index, child = register_fixture_chain(runtime, index_path, child_path, model_client=Model(), rewrite_child=rewrite_child)
    with runtime.repo.connect() as conn:
        result = conn.execute("""
            SELECT s.source_revision_id, s.resource_manifest FROM canonical_articles a
            JOIN canonical_article_source_revisions s ON s.source_revision_id=a.current_source_revision_id
            WHERE a.canonical_article_id=%s
        """, (child,)).fetchone()
    image, = [item for item in result["resource_manifest"] if item["role"] == "asset"]
    assert image["derived_from_sha256"] == digest(svg)
    return {"index": str(index), "child": str(child), "source_revision": str(result["source_revision_id"]),
            "figure_sha256": image["sha256"], "child_published": rewrite_child}


def verify_registration(runtime, scope, index_path, child_path, svg):
    repo, parent = runtime.repo, runtime.article_id
    index, child = register_fixture_chain(runtime, index_path, child_path)
    with repo.connect() as conn:
        referrals = conn.execute(
            """SELECT parent_article_id, target_article_id, inline_slots FROM banktwo_authored_article_referrals
               WHERE parent_article_id=ANY(%s)""", ([parent, index],),
        ).fetchall()
        by_parent = {row["parent_article_id"]: row for row in referrals}
        assert by_parent[parent]["target_article_id"] == index and by_parent[index]["target_article_id"] == child
        assert [row["label"] for row in by_parent[parent]["inline_slots"]] == ["Pump service options"]
        assert [row["label"] for row in by_parent[index]["inline_slots"]] == ["Pump seal removal"]
        source = conn.execute("""
            SELECT s.source_revision_id,source_document,resource_manifest FROM canonical_articles a
            JOIN canonical_article_source_revisions s ON s.source_revision_id=a.current_source_revision_id
            WHERE a.canonical_article_id=%s
        """, (child,)).fetchone()
    blocks = source["source_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["paragraph", "image", "paragraph"]
    original, = [item for item in source["resource_manifest"] if item["role"] == "asset_original"]
    projected, = [item for item in source["resource_manifest"] if item["role"] == "asset"]
    assert original["sha256"] == digest(svg) == projected["derived_from_sha256"]
    from autodata_ingestion.source_media_replay import _source_replay_row

    with repo.connect() as conn:
        stored = _source_replay_row(conn.cursor(), source["source_revision_id"])
    raster, = [item for item in stored["resource_provenance"] if item["role"] == "asset"]
    png = runtime.objects.get_object(raster["object_key"], max_bytes=64_000)
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and digest(png) == projected["sha256"]

    def refresh():
        job, = refresh_catalog_jobs(repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=UUID(scope["configuration"]),
                                    actor="fixture", reason="verify authored targets", provider="banktwo")
        assert run_article_worker_once(repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=None, job_id=job.job_id)

    def membership():
        with repo.connect() as conn:
            return {row["membership_status"] for row in conn.execute(
                "SELECT membership_status FROM canonical_articles WHERE canonical_article_id=ANY(%s)",
                ([parent, index, child],),
            ).fetchall()}
    refresh()
    assert membership() == {"active"}
    runtime.servers["banktwo"].pages = [{"complete": True, "articles": []}]
    refresh()
    assert membership() == {"retired"}
    return {"registered": 2, "idempotent": True, "figure_placement": 1, "stored_raster": True,
            "retained_after_refresh": True, "retired_with_parent": True}


@pytest.mark.parametrize("engine", ("chromium", "webkit"))
def test_banktwo_authored_referrals_browser(fresh_database, engine):
    from playwright.sync_api import sync_playwright

    assert os.environ.get("DISPLAY")
    with ExitStack() as stack, sync_playwright() as playwright:
        runtime = LifecycleRuntime(fresh_database(), stack)
        stack.callback(runtime.close)
        scope = configure_scoped_runtime(runtime, "banktwo")
        index_path, child_path, svg = install_markup(runtime)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                raw = b"<!doctype html><title>Banktwo author registration fixture</title>"
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                raw = json.dumps(verify_registration(runtime, scope, index_path, child_path, svg)).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(raw)

        origin = stack.enter_context(serve(Handler))
        executable = (os.environ["WORKSHOP_HEADED_WEBKIT_EXECUTABLE"] if engine == "webkit"
                      else os.environ["AUTODATA_WORKSHOP_SIMULATION_CHROMIUM"])
        with getattr(playwright, engine).launch(headless=False, executable_path=executable) as browser:
            page = browser.new_page()
            assert page.goto(origin).ok
            receipt = page.evaluate("async () => (await fetch('/register', {method:'POST'})).json()")
    assert receipt["registered"] == 2 and receipt["stored_raster"] and receipt["retired_with_parent"]
    print("WORKSHOP_BANKTWO_AUTHORED_REFERRALS " + json.dumps({"engine": engine, "headed": True, **receipt}))
