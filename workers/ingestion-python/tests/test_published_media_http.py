"""Exercise retained media publication through the actual paid Go HTTP API."""

import asyncio
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import os
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

import pytest
from PIL import Image

from autodata_ingestion import article_content_review, source_article_capture
from autodata_ingestion.commerce_service import configured_commerce
from autodata_ingestion.http_service import make_handler
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.published_media_publication import (
    preview_published_media_repair,
    publish_retained_media_repair,
)
from autodata_ingestion.source_job_persistence import refresh_article_job
from autodata_ingestion.source_svg_archive import read_svg_archive, stage_svg_archive
from lifecycle_support import fresh_database, runtime
from test_paid_catalog_api_integration import PaidBridge, configure_scoped_runtime, serve
from test_published_media_publication import FixtureModel, _allowlist, _preview, _run, _seed


ROOT = Path(__file__).resolve().parents[3]
CASE = "TestPostgresPaidCatalogRetainedMediaPublication"
SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
       b'<rect width="24" height="24" fill="green"/></svg>')
pytestmark = pytest.mark.skipif(
    os.environ.get("AUTODATA_REQUIRE_PUBLISHED_MEDIA_HTTP") != "1",
    reason="requires the isolated paid HTTP runner",
)


def _paid_go_env(runtime, scope, bridge, ensure, control, case_dir, tmp_path):
    allowed = ("PATH", "GOTOOLCHAIN", "GOPROXY", "GOFLAGS", "CGO_ENABLED", "GOMODCACHE", "GOCACHE", "GOTMPDIR")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    go_home = tmp_path / "go-home"
    go_home.mkdir(mode=0o700)
    other_provider = "bankone" if runtime.provider == "banktwo" else "banktwo"
    env.update(
        HOME=str(go_home),
        AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION="1",
        AUTODATA_CATALOG_INTEGRATION_REQUIRED="1",
        AUTODATA_LIFECYCLE_TEST="1",
        AUTODATA_CATALOG_TEST_DSN=f"postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{runtime.repo.database_name}?sslmode=disable",
        AUTODATA_CATALOG_TEST_ENSURE_URL=ensure,
        AUTODATA_CATALOG_TEST_CONTROL_URL=control,
        AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
        AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),
        AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
        AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles[other_provider]),
        AUTODATA_CATALOG_TEST_PROVIDER=runtime.provider,
        AUTODATA_CATALOG_TEST_CANDIDATE_SHA=os.environ["AUTODATA_R3_CANDIDATE_SHA"],
        AUTODATA_CATALOG_TEST_CASE_DIR=str(case_dir),
        AUTODATA_PAID_TEST_CONFIGURATION_ID=scope["configuration"],
        AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID=scope["adjacent"],
        AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID=scope["other_region"],
        AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID=scope["unscoped"],
        AUTODATA_S3_ENDPOINT="minio:9000",
        AUTODATA_S3_ACCESS_KEY="fixture",
        AUTODATA_S3_SECRET_KEY="fixture",
        AUTODATA_SOURCE_BUCKET=runtime.bucket,
    )
    return env


@pytest.mark.parametrize(("file_format", "media_type"), [
    ("PNG", "image/png"),
    ("JPEG", "image/jpeg"),
    ("GIF", "image/gif"),
    ("WEBP", "image/webp"),
    ("SVG", "image/png"),
])
def test_published_retained_media_actual_http(runtime, monkeypatch, tmp_path, capsys, file_format, media_type):
    provider = "banktwo"
    allowlist = _allowlist(tmp_path)
    scope = configure_scoped_runtime(runtime, provider)
    # The historical fixture seeds with the old prose profile before upgrading.
    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
            ("technical-prose-v1", runtime.article_id),
        )
    is_svg = file_format == "SVG"
    if is_svg:
        figure, upstream_media = SVG, "image/svg+xml"
    else:
        stream = BytesIO()
        Image.new("RGB", (24, 24), "green").save(stream, format=file_format)
        figure, upstream_media = stream.getvalue(), media_type
    server = runtime.servers[provider]
    register_resource = server.body

    def register_with_fixture_figure(payload, mime="text/html", *, ref="body", kind="article", assets=()):
        if ref == "figure" and kind == "asset":
            payload, mime = figure, upstream_media
        return register_resource(payload, mime, ref=ref, kind=kind, assets=assets)

    # Use the same historical placement and content review with each provider asset.
    with monkeypatch.context() as fixture:
        fixture.setattr(server, "body", register_with_fixture_figure)
        original, model = _seed(runtime, monkeypatch, provider, article_content_review.PROFILE, allowlist)
    assert original["review_status"] == "APPROVED"
    original_svg_sha256 = ""
    if is_svg:
        [image] = original["images"]
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT resource_manifest FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (original["source_revision_id"],),
            ).fetchone()
            observation = conn.execute(
                """SELECT resource_provenance FROM canonical_article_source_observations
                   WHERE source_revision_id=%s ORDER BY request_generation DESC LIMIT 1""",
                (original["source_revision_id"],),
            ).fetchone()
        [svg_root] = [item for item in observation["resource_provenance"] if item["role"] == "asset_original"]
        [derivative] = [item for item in source["resource_manifest"] if item["role"] == "asset"]
        [provenance] = [item for item in observation["resource_provenance"] if item["role"] == "asset"]
        original_svg_sha256 = sha256(figure).hexdigest()
        assert svg_root["media_type"] == "image/svg+xml" and svg_root["sha256"] == original_svg_sha256
        assert provenance["derived_from_sha256"] == original_svg_sha256 and derivative["media_type"] == "image/png"
        assert runtime.objects.get_object(svg_root["object_key"], max_bytes=1 << 20) == figure
        figure = runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20)
        assert sha256(figure).hexdigest() == derivative["sha256"]
        with Image.open(BytesIO(figure)) as decoded:
            assert decoded.format == "PNG" and decoded.size == (24, 24)
            assert decoded.convert("RGB").getpixel((12, 12)) == (0, 128, 0)
    figure_sha256 = sha256(figure).hexdigest()
    _, manifest = _preview(runtime, original, tmp_path, capsys)
    calls_before = runtime.counters()
    publications = []
    errors = []

    class RepairBridge(PaidBridge):
        def control_handler(self):
            parent = super().control_handler()
            bridge = self

            class Handler(parent):
                def do_POST(self):
                    if self.path != "/paid-fixture/publish-retained-media":
                        return super().do_POST()
                    if (self.headers.get("X-R3-Fixture-Token") != bridge.token or
                            self.headers.get("Content-Length", "0") != "0"):
                        self.send_error(403, "Invalid fixture control")
                        return
                    try:
                        assert not publications
                        published = publish_retained_media_repair(
                            runtime.repo,
                            expected=manifest,
                            object_store=runtime.objects,
                            reviewer_id="media-reviewer",
                            allowlist=allowlist,
                            rationale="Matched the retained image to the exact procedure and original source.",
                            fixture_mode=True,
                        )
                        assert published["status"] == "published"
                        publications.append(published)
                    except Exception as error:
                        errors.append(type(error).__name__ + ": " + str(error))
                        self.send_error(500, "Fixture publication failed")
                        return
                    self.send_response(200)
                    self.send_header("Content-Length", "0")
                    self.end_headers()

            return Handler

    bridge = RepairBridge(runtime)
    case_dir = Path("/artifacts") / "published-media-http" / file_format.lower()
    case_dir.parent.mkdir(mode=0o700, exist_ok=True)
    case_dir.mkdir(mode=0o700)
    with ExitStack() as stack:
        ensure = stack.enter_context(serve(bridge.ensure_handler()))
        control = stack.enter_context(serve(bridge.control_handler()))
        env = _paid_go_env(runtime, scope, bridge, ensure, control, case_dir, tmp_path)
        env.update(
            AUTODATA_PAID_TEST_FIGURE_MEDIA_TYPE=media_type,
            AUTODATA_PAID_TEST_FIGURE_SHA256=figure_sha256,
            AUTODATA_PAID_TEST_ORIGINAL_SVG_SHA256=original_svg_sha256,
        )
        with (case_dir / "go.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(
                ["go", "test", "-count=1", "-v", "-run", f"^{CASE}$", "-timeout=45s", "."],
                cwd=ROOT / "apps/api-go", env=env, stdout=log, stderr=subprocess.STDOUT, timeout=100,
            )
        assert process.returncode == 0, (errors, (case_dir / "go.log").read_text())
    assert not errors and len(publications) == 1 and model.calls == 1
    assert runtime.counters() == {**calls_before, "schedule": calls_before["schedule"] + 1}
    receipt = json.loads((case_dir / "go-measurement.json").read_text())
    assert len(receipt["assertion_results"]) == 8 + is_svg and all(receipt["assertion_results"].values())
    assert receipt["reader_calls"] == 4
    image_requests = [
        request for request in receipt["http_observations"]
        if request["path"].startswith("/v1/catalog/images/")
    ]
    expected_statuses = [200, 200, 404, 404, 200, 200, 404, 404]
    if is_svg:
        expected_statuses += [410, 410, 404, 404]
    assert [request["status"] for request in image_requests] == expected_statuses + [403, 403]
    for request in image_requests:
        if request["status"] == 200:
            assert request["headers"]["Content-Type"] == media_type
            assert request["body_sha256"] == figure_sha256
            assert request["reader_after"] == request["reader_before"] + 1
        else:
            assert request["reader_after"] == request["reader_before"]


async def _read_recovered_svg(origin, scope, repair):
    from playwright.async_api import async_playwright, expect
    from workshop_browser_smoke import API_CASES, APIFixture, api_signin, fixture_origin

    fixture_origin(origin)
    configuration, article = scope["configuration"], scope["article"]
    workshop = f"{origin}/workshop/?configuration={configuration}&region=US"
    reader = f"{workshop}&article={article}"
    detail = f"{origin}/v1/catalog/vehicles/{configuration}/articles/{article}?region=US"
    async with async_playwright() as playwright:
        executable = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_CHROMIUM")
        options = {"executable_path": executable} if executable else {}
        browser = await playwright.chromium.launch(**options)
        try:
            owner = await browser.new_context(ignore_https_errors=True, service_workers="block")
            owner_transport = APIFixture(origin, API_CASES[1])
            await owner.route("**/*", owner_transport.route)
            page = await owner.new_page()
            await page.goto(workshop)
            await api_signin(page)
            await expect(page.get_by_role("button", name="Simulate purchase")).to_be_enabled()
            await page.locator("#agreement").check()
            await page.get_by_role("button", name="Simulate purchase").click()
            await expect(page.locator(f'#articles a[href*="{article}"]')).to_be_visible()
            await page.goto(reader)
            figure = page.locator("#article-content figure")
            await expect(figure.locator(".image-missing")).to_have_text("Illustration unavailable.")
            await expect(figure.locator("img")).to_have_count(0)
            paragraph_placement = """node => [...node.parentElement.children]
                .filter(sibling => sibling === node || sibling.tagName === "P")
                .map(sibling => sibling === node ? null : sibling.textContent.trim())"""
            positions = await figure.evaluate(paragraph_placement)
            assert positions[-3:] == ["Take off the pump.", "Fit the replacement unit.", None]
            prior = await owner.request.get(detail)
            assert prior.status == 200
            before = (await prior.json())["article"]

            publication = await asyncio.to_thread(repair)
            await page.reload()
            image = figure.locator("img")
            await expect(image).to_be_visible()
            await expect(figure.locator(".image-missing")).to_have_count(0)
            assert await figure.evaluate(paragraph_placement) == positions
            assert await image.evaluate("""async node => {
                await node.decode();
                return [node.naturalWidth, node.naturalHeight];
            }""") == [24, 24]
            media = urlsplit(await image.evaluate("node => node.currentSrc"))
            assert (media.scheme, media.netloc) == ("https", urlsplit(origin).netloc)
            assert media.path.startswith("/v1/catalog/images/v2.")
            asset = await owner.request.get(media.geturl())
            assert asset.status == 200 and asset.headers["content-type"] == "image/png"
            with Image.open(BytesIO(await asset.body())) as decoded:
                assert decoded.format == "PNG" and decoded.size == (24, 24)
                assert decoded.convert("RGB").getpixel((12, 12)) == (0, 128, 0)
            current = await owner.request.get(detail)
            assert current.status == 200
            after = (await current.json())["article"]
            for revision in ("source_revision_id", "canonical_revision_id"):
                assert after[revision] == publication[revision] and before[revision] != after[revision]
            raw_svg_sha = sha256(SVG).hexdigest()
            assert raw_svg_sha not in json.dumps(after) and "image/svg+xml" not in json.dumps(after)
            assert (await owner.request.get(f"{origin}/v1/catalog/images/{raw_svg_sha}")).status == 404

            visitor = await browser.new_context(ignore_https_errors=True, service_workers="block")
            assert (await visitor.request.get(detail)).status == 401
            media_status = (await visitor.request.get(media.geturl())).status
            assert media_status == 401
            other_transport = APIFixture(origin, API_CASES[1])
            other_transport.account = "other"
            await visitor.route("**/*", other_transport.route)
            other = await visitor.new_page()
            await other.goto(workshop)
            await api_signin(other)
            assert (await visitor.request.get(detail)).status == 403
            media_status = (await visitor.request.get(media.geturl())).status
            assert media_status == 404
            assert owner_transport.unexpected == [] and other_transport.unexpected == []
            assert (await owner.request.post(origin + "/__fixture/stop")).status == 204
        finally:
            await browser.close()


@pytest.mark.skipif(
    os.environ.get("AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION") != "1",
    reason="requires the isolated Chromium and paid HTTP runner",
)
@pytest.mark.parametrize(("provider", "projection_version"), [
    ("bankone", "source-projection-v1"),
    ("banktwo", "source-projection-v2"),
])
def test_retained_svg_recovery_visible_in_paid_reader(runtime, monkeypatch, tmp_path, provider, projection_version):
    scope = configure_scoped_runtime(runtime, provider)
    scope["article"] = str(runtime.article_id)
    server = runtime.servers[provider]
    server.body(
        b"<p>Remove the pump.</p><p>Install the replacement.</p>",
        "text/html", assets=["figure"],
    )
    server.body(b"legacy unsupported figure", "application/octet-stream", ref="figure", kind="asset")
    capture = source_article_capture.capture_source_article
    legacy_reason = "source image reference is missing"

    def retained_projection(*args, **kwargs):
        captured = capture(*args, **kwargs)
        [figure] = [block for block in captured.source_document["blocks"] if block["type"] == "image"]
        assert figure["unavailable_reason"] == "UNSUPPORTED_ASSET_MEDIA"
        figure["unavailable_reason"] = legacy_reason
        _, _, images = source_article_capture.project_document(captured.source_document)
        return replace(captured, projection_version=projection_version, source_images=images)

    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
            ("technical-prose-v1", runtime.article_id),
        )
    model = FixtureModel()
    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", retained_projection)
        runtime.ensure()
        _run(runtime, None)
        refresh_article_job(runtime.repo, runtime.article_id, actor="fixture",
                            reason="publish a rewrite of the retained source", rewrite_profile_version=AUTO_PROFILE)
        _run(runtime, model)
    original = runtime.read_current()
    assert original["canonical_revision_id"] and model.calls == 1
    source_id = original["source_revision_id"]
    with runtime.repo.connect() as conn:
        retained = conn.execute(
            "SELECT projection_version FROM canonical_article_source_revisions WHERE source_revision_id=%s",
            (source_id,),
        ).fetchone()
    assert retained["projection_version"] == projection_version
    [placeholder] = [block for block in original["document"]["blocks"] if block["type"] == "image"]
    assert placeholder["unavailable_reason"] == legacy_reason

    server.body(SVG, "image/svg+xml", ref="figure", kind="binary" if provider == "bankone" else "asset")
    runtime.reset_counters()
    tmp_path.chmod(0o700)
    archive = tmp_path / "svg-archive"
    stage = stage_svg_archive(runtime.repo, runtime.article_id, source_id,
                              registry=runtime.registry, destination=archive)
    assert stage["status"] == "prepared" and stage["asset_count"] == 1
    assert runtime.counters() == {"source": 0, "asset": 1, "model": 0, "schedule": 0}
    archive_manifest = archive / "archive.json"
    saved_manifest = archive_manifest.read_text()
    altered_manifest = json.loads(saved_manifest)
    altered_manifest["resources"][0]["sha256"] = "0" * 64
    archive_manifest.write_text(json.dumps(altered_manifest))
    with pytest.raises(ValueError, match="^SOURCE_SVG_ARCHIVE_RESOURCE_INVALID$"):
        read_svg_archive(runtime.repo, source_id, archive)
    archive_manifest.write_text(saved_manifest)
    preview = tmp_path / "approval"
    result = preview_published_media_repair(
        runtime.repo, runtime.article_id, source_id, object_store=runtime.objects,
        destination=preview, fixture_mode=True, svg_archive=archive,
    )
    assert result["status"] == "preview"
    assert runtime.read_current()["canonical_revision_id"] == original["canonical_revision_id"]
    manifest = json.loads((preview / "manifest.json").read_bytes())
    allowlist = _allowlist(tmp_path)

    def repair():
        publication = publish_retained_media_repair(
            runtime.repo, expected=manifest, object_store=runtime.objects,
            reviewer_id="media-reviewer", allowlist=allowlist,
            rationale="Compared the recovered illustration with its retained source position.",
            fixture_mode=True, svg_archive=archive,
        )
        assert publication["status"] == "published"
        with runtime.repo.connect() as conn:
            original_svg = conn.execute(
                "SELECT object_key FROM source_snapshots WHERE content_sha256=%s",
                (sha256(SVG).hexdigest(),),
            ).fetchone()
        assert runtime.objects.get_object(original_svg["object_key"], max_bytes=4096) == SVG
        return publication

    monkeypatch.syspath_prepend(str(ROOT / "scripts/dev"))
    for name, value in {
        "AUTODATA_ENV": "test",
        "AUTODATA_PUBLIC_ORIGIN": "https://fixture.invalid",
        "AUTODATA_COMMERCE_MODE": "simulation",
        "AUTODATA_COMMERCE_READ_ONLY_MODE": "stripe_test",
        "AUTODATA_STRIPE_ACCOUNT_ID": "acct_fixture",
        "AUTODATA_STRIPE_PRICE_ID": "price_fixture",
        "AUTODATA_INGESTION_INTERNAL_TOKEN": "fixture-r3-internal",
    }.items():
        monkeypatch.setenv(name, value)
    commerce = configured_commerce(connection_factory=runtime.repo.connect)
    bridge = PaidBridge(runtime)
    ready = tmp_path / "ready.json"
    with ExitStack() as stack:
        ensure = stack.enter_context(serve(make_handler(internal_token="fixture-r3-internal", commerce=commerce)))
        control = stack.enter_context(serve(bridge.control_handler()))
        env = _paid_go_env(runtime, scope, bridge, ensure, control, tmp_path, tmp_path)
        env.update(
            AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION="1",
            AUTODATA_WORKSHOP_BROWSER_FIXTURE="1",
            AUTODATA_WORKSHOP_BROWSER_SIMULATION="1",
            AUTODATA_WORKSHOP_BROWSER_READY=str(ready),
        )
        fixture = "^TestWorkshopBrowserFixtureHTTP$"
        binary = os.environ.get("AUTODATA_WORKSHOP_SIMULATION_GO_BINARY")
        if binary:
            command = [binary, "-test.count=1", "-test.run", fixture, "-test.timeout=90s"]
        else:
            command = ["go", "test", "-count=1", "-run", fixture, "-timeout=90s", "."]
        go = subprocess.Popen(command, cwd=ROOT / "apps/api-go", env=env, start_new_session=True)
        try:
            deadline = time.monotonic() + 35
            while not ready.exists():
                assert go.poll() is None and time.monotonic() < deadline, "paid Workshop fixture did not start"
                time.sleep(0.05)
            metadata = json.loads(ready.read_bytes())
            assert metadata["kind"] == "api-fixture" and metadata["scope"]["article"] == scope["article"]
            asyncio.run(asyncio.wait_for(_read_recovered_svg(metadata["origin"], scope, repair), 45))
            assert go.wait(timeout=5) == 0
        finally:
            if go.poll() is None:
                os.killpg(go.pid, signal.SIGTERM)
                try:
                    go.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(go.pid, signal.SIGKILL)
                    go.wait(timeout=5)
    counts = runtime.counters()
    assert (counts["source"], counts["asset"], counts["model"]) == (0, 1, 0)
    assert model.calls == 1
