"""Exercise a retained media publication through the actual paid Go HTTP API."""

from contextlib import ExitStack
import json
from pathlib import Path
import os
import subprocess

from autodata_ingestion import article_content_review
from autodata_ingestion.published_media_publication import publish_retained_media_repair
from lifecycle_support import fresh_database, runtime
from test_paid_catalog_api_integration import PaidBridge, configure_scoped_runtime, serve
from test_published_media_publication import _allowlist, _preview, _seed


ROOT = Path(__file__).resolve().parents[3]
CASE = "TestPostgresPaidCatalogRetainedMediaPublication"


def test_published_retained_media_actual_http(runtime, monkeypatch, tmp_path, capsys):
    provider = "banktwo"
    allowlist = _allowlist(tmp_path)
    scope = configure_scoped_runtime(runtime, provider)
    # The historical fixture seeds with the old prose profile before upgrading.
    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
            ("technical-prose-v1", runtime.article_id),
        )
    original, model = _seed(runtime, monkeypatch, provider, article_content_review.PROFILE, allowlist)
    assert original["review_status"] == "APPROVED"
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
    artifact = Path("/artifacts")
    case_dir = artifact / "published-media-http"
    case_dir.mkdir(mode=0o700)
    with ExitStack() as stack:
        ensure = stack.enter_context(serve(bridge.ensure_handler()))
        control = stack.enter_context(serve(bridge.control_handler()))
        allowed = ("PATH", "GOTOOLCHAIN", "GOPROXY", "GOFLAGS", "CGO_ENABLED", "GOMODCACHE", "GOCACHE", "GOTMPDIR")
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update(
            AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION="1",
            AUTODATA_CATALOG_INTEGRATION_REQUIRED="1",
            AUTODATA_LIFECYCLE_TEST="1",
            AUTODATA_CATALOG_TEST_DSN=f"postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{runtime.repo.database_name}?sslmode=disable",
            AUTODATA_CATALOG_TEST_ENSURE_URL=ensure,
            AUTODATA_CATALOG_TEST_CONTROL_URL=control,
            AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
            AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),
            AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
            AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles["bankone"]),
            AUTODATA_CATALOG_TEST_PROVIDER=provider,
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
        with (case_dir / "go.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(
                ["go", "test", "-count=1", "-v", "-run", f"^{CASE}$", "-timeout=45s", "."],
                cwd=ROOT / "apps/api-go", env=env, stdout=log, stderr=subprocess.STDOUT, timeout=100,
            )
        assert process.returncode == 0, (errors, (case_dir / "go.log").read_text())
    assert not errors and len(publications) == 1 and model.calls == 1
    assert runtime.counters() == {**calls_before, "schedule": calls_before["schedule"] + 1}
    receipt = json.loads((case_dir / "go-measurement.json").read_text())
    assert len(receipt["assertion_results"]) == 7 and all(receipt["assertion_results"].values())
    assert receipt["reader_calls"] == 4
