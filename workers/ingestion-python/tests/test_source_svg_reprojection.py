"""Source-only SVG reprojection through the private archive and real lifecycle rows."""

from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from autodata_ingestion import source_revision_reprojection as reprojection
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.source_job_persistence import refresh_article_job
from autodata_ingestion.source_svg_archive import stage_svg_archive
from lifecycle_support import apply_migration, fresh_database
from test_source_revision_reprojection import reprojection_cli
from test_source_svg_recovery import _legacy, raster
from test_source_table_replay import source_state


def _stage(repo, tmp_path):
    article, revision, objects, assets = _legacy(repo, legacy_fallback=True)
    provider = assets["archived-figure"].provider
    root = tmp_path.resolve()
    root.chmod(0o700)
    archive = root / "private-svg"

    class Connector:
        def read_resource(self, ref, *, timeout):
            assert 0 < timeout <= 6
            return assets[ref]

    connector = Connector()
    connector.provider = provider
    stage_svg_archive(repo, article, revision, registry={provider: connector}, destination=archive)
    return article, revision, objects, archive


def _preview(cli, repo, fixture, capsys):
    article, revision, objects, archive = fixture
    argv = ["--article-id", str(article), "--source-revision-id", str(revision), "--svg-archive", str(archive)]
    assert cli.main([*argv, "--dry-run"], repo=repo, object_store=objects) == 0
    receipt = json.loads(capsys.readouterr().out)
    argv += ["--apply", "--actor", "fixture", "--reason", "Restore bound figures"]
    expected = {
        "--expected-observation-id": "source_observation_id",
        "--expected-fingerprint": "source_fingerprint",
        "--expected-body-sha256": "body_sha256",
        "--expected-document-sha256": "document_sha256",
        "--expected-corrected-fingerprint": "corrected_source_fingerprint",
        "--expected-provenance-sha256": "provenance_sha256",
    }
    for flag, field in expected.items():
        argv.extend((flag, receipt[field]))
    return receipt, argv


def test_source_only_svg_preview_apply_and_idempotency(fresh_database, tmp_path, raster, reprojection_cli, capsys):
    repo = fresh_database(through=42)
    fixture = _stage(repo, tmp_path)
    article, revision, objects, archive = fixture
    prior, original_objects = source_state(repo, article), deepcopy(objects.data)
    receipt, argv = _preview(reprojection_cli, repo, fixture, capsys)
    assert receipt["status"] == "preview" and receipt["requires_canonical_repair"] is False
    assert receipt["restored_figure_count"] == 1 and receipt["projection_version"] == "source-projection-v5"
    assert receipt["current_canonical_revision_id"] is None
    assert receipt["corrected_source_fingerprint"] != receipt["source_fingerprint"]
    assert source_state(repo, article) == prior and objects.data == original_objects
    with pytest.raises(ValueError, match="SCHEMA_REQUIRED"):
        reprojection_cli.main(argv, repo=repo, object_store=objects)
    for migration in (43, 44, 45):
        apply_migration(repo, migration)
    for flag in ("--expected-observation-id", "--expected-fingerprint", "--expected-body-sha256",
                 "--expected-document-sha256", "--expected-corrected-fingerprint", "--expected-provenance-sha256"):
        invalid = list(argv)
        invalid[invalid.index(flag) + 1] = str(uuid4()) if flag == "--expected-observation-id" else "0" * 64
        with pytest.raises(ValueError, match="PREVIEW_BINDING_MISMATCH"):
            reprojection_cli.main(invalid, repo=repo, object_store=objects)
    with pytest.raises(SystemExit):
        reprojection_cli.main(argv[:-2], repo=repo, object_store=objects)
    capsys.readouterr()
    asset_file = archive / "asset-00.json"
    asset_file.chmod(0o644)
    with pytest.raises(ValueError, match="CONTENT_REVIEW_PRIVATE_PATH_REQUIRED"):
        reprojection_cli.main(argv, repo=repo, object_store=objects)
    asset_file.chmod(0o600)
    assert source_state(repo, article) == prior and objects.data == original_objects

    _, expected_capture, expected_blobs = reprojection.preview_svg_reprojection(
        repo, revision, object_store=objects, svg_archive=archive,
    )
    objects.seeding = True
    assert reprojection_cli.main(argv, repo=repo, object_store=objects) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "applied"
    assert objects.data == {**original_objects, **{key: payload for key, (payload, _) in expected_blobs.items()}}
    current = source_state(repo, article)
    assert current["revision_count"] == prior["revision_count"] + 1
    assert current["request_generation"] == prior["request_generation"] + 1
    assert current["current_canonical_revision_id"] is None
    assert str(current["current_source_revision_id"]) == result["source_revision_id"]
    with repo.connect() as conn:
        view = conn.execute("""SELECT content_origin,document FROM catalog_article_current
                               WHERE canonical_article_id=%s""", (article,)).fetchone()
        assert view == {"content_origin": "source", "document": expected_capture.source_document}
        old = conn.execute("""SELECT source_document FROM canonical_article_source_revisions
                              WHERE source_revision_id=%s""", (revision,)).fetchone()
        assert any(block.get("unavailable_reason") == "source image reference is missing"
                   for block in old["source_document"]["blocks"])
        observation = conn.execute("""SELECT resource_provenance FROM canonical_article_source_observations
                                      WHERE source_revision_id=%s""", (result["source_revision_id"],)).fetchone()
        assert digest_json(observation["resource_provenance"]) == receipt["provenance_sha256"]
    objects.seeding = False
    assert reprojection_cli.main(argv, repo=repo, object_store=objects) == 0
    assert json.loads(capsys.readouterr().out) == {**result, "status": "already_applied"}
    assert source_state(repo, article) == current


@pytest.mark.parametrize("guard", ["active_job", "canonical_anchor"])
def test_source_only_svg_respects_existing_owner(fresh_database, tmp_path, raster, reprojection_cli, capsys, guard):
    repo = fresh_database(through=45)
    fixture = _stage(repo, tmp_path)
    article, revision, objects, _ = fixture
    receipt, argv = _preview(reprojection_cli, repo, fixture, capsys)
    assert receipt["requires_canonical_repair"] is False
    if guard == "active_job":
        refresh_article_job(repo, article, actor="fixture", reason="Queue a normal source job")
    else:
        canonical = uuid4()
        with repo.connect() as conn:
            conn.execute("""
                INSERT INTO canonical_article_revisions(canonical_article_revision_id,canonical_article_id,
                    source_revision_id,transformation_key,normalization_version,rewrite_profile_version,status,
                    normalized_source_document,normalized_source_hash,canonical_document,canonical_body,
                    canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,
                    model_metadata,published_at)
                SELECT %s,s.canonical_article_id,s.source_revision_id,j.transformation_key,
                    j.normalization_version,j.rewrite_profile_version,'published',
                    s.source_document,repeat('a',64),s.source_document,s.source_body,s.source_steps,s.source_images,
                    '{"passed":true,"changed_slots":["fixture"],"evidence_ids":["fixture"]}',
                    repeat('b',64),repeat('c',64),'{"model":"fixture","profile_version":"technical-prose-v1"}',now()
                FROM canonical_article_source_revisions s JOIN source_fetch_jobs j USING(source_revision_id)
                WHERE s.source_revision_id=%s
            """, (canonical, revision))
            conn.execute("UPDATE canonical_articles SET current_canonical_revision_id=%s WHERE canonical_article_id=%s",
                         (canonical, article))
        receipt, _ = _preview(reprojection_cli, repo, fixture, capsys)
        assert receipt["requires_canonical_repair"] is True and receipt["current_canonical_revision_id"] == str(canonical)
    prior, original_objects = source_state(repo, article), deepcopy(objects.data)
    with pytest.raises(ValueError, match="ACTIVE_NORMAL_JOB" if guard == "active_job" else "CANONICAL_ANCHOR"):
        reprojection_cli.main(argv, repo=repo, object_store=objects)
    assert source_state(repo, article) == prior and objects.data == original_objects


def test_source_only_svg_rechecks_rights_and_rolls_back(fresh_database, tmp_path, raster, reprojection_cli, capsys, monkeypatch):
    repo = fresh_database(through=45)
    fixture = _stage(repo, tmp_path)
    article, revision, objects, _ = fixture
    _, argv = _preview(reprojection_cli, repo, fixture, capsys)
    prior = source_state(repo, article)
    png_sha = sha256(raster).hexdigest()
    verify = reprojection._verify_stored_svg_reprojection

    def withdrawn_at_persistence(cur, source_revision_id, job_id, captured):
        cur.execute("UPDATE source_snapshots SET takedown_status='expired' WHERE content_sha256=%s", (png_sha,))
        verify(cur, source_revision_id, job_id, captured)

    objects.seeding = True
    with monkeypatch.context() as fault:
        fault.setattr(reprojection, "_verify_stored_svg_reprojection", withdrawn_at_persistence)
        with pytest.raises(ValueError, match="WITHDRAWN"):
            reprojection_cli.main(argv, repo=repo, object_store=objects)
    assert source_state(repo, article) == prior
    with repo.connect() as conn:
        assert conn.execute("SELECT 1 FROM source_snapshots WHERE content_sha256=%s", (png_sha,)).fetchone() is None
        jobs = conn.execute("""SELECT count(*) AS count FROM source_fetch_jobs WHERE canonical_article_id=%s
                              AND checkpoint @> '{"svg_reprojection":true}'""", (article,)).fetchone()
        assert jobs["count"] == 0
    assert reprojection_cli.main(argv, repo=repo, object_store=objects) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "applied"
