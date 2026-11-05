"""Offline byte replay and isolated PostgreSQL source-only acceptance."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4
import json
import time
import pytest
from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext
from autodata_ingestion.source_connector_client import SourceEnvelopeV1
from autodata_ingestion.source_article_capture import capture_source_article


XML = '<maintenance_schedule title="Service"><operation id="o" name="Inspect"><component id="c" name="Belt"><notes>Check belt.</notes></component></operation></maintenance_schedule>'


class Objects:
    def __init__(self):
        self.data = {}; self.puts = 0; self.gets = []
    def put_object(self, key, payload, media):
        self.puts += 1; self.data[key] = payload
    def get_object(self, key, *, max_bytes):
        self.gets.append((key, max_bytes))
        payload = self.data[key]
        if len(payload) > max_bytes: raise ValueError("SOURCE_BODY_TOO_LARGE")
        return payload


@pytest.fixture
def saved_source(monkeypatch):
    raw = json.dumps({"_embedded": {"data": {"article": {"content": XML}}}}).encode()
    context = SourceArticleContext(ArticleKey("banktwo", uuid4(), None, "vehicle", "article"),
        {"year": 2024, "make": "Example", "model": "Car"},
        {"title": "Service", "resource_ref": "body"}, uuid4(), uuid4(), ("evidence",))
    envelope = SourceEnvelopeV1("request", "banktwo", "provider-rev", "2026-11-01T00:00:00Z",
        "fixture:body", {"kind": "article", "sha256": sha256(raw).hexdigest(),
                         "media_type": "application/hal+json"}, raw_resource=raw)
    class Client:
        provider = "banktwo"
        def read_resource(self, ref, *, timeout):
            assert ref == "body"; return envelope
    objects = Objects()
    captured = capture_source_article(context, registry={"banktwo": Client()}, object_store=objects)
    objects.puts = 0
    stored = SimpleNamespace(**{**captured.__dict__, "projection_version": "source-projection-v1",
        "source_revision_id": uuid4(), "source_body": XML,
        "source_document": {"blocks": [{"type": "paragraph", "text": XML}]}})
    binding = {**deepcopy(captured.resource_provenance[0]),
        "body_provider_revision": "provider-rev", "resource_provenance": deepcopy(captured.resource_provenance),
        "content_sha256": sha256(raw).hexdigest(), "snapshot_id": captured.body_source_snapshot_id}
    class Repo:
        def connect(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self, **kw): return self
        def execute(self, *args): return self
        def fetchone(self): return binding
    from autodata_ingestion import source_revision_reprojection as replay
    monkeypatch.setattr(replay, "load_source_revision", lambda repo, source_id: stored)
    return SimpleNamespace(repo=Repo(), stored=stored, binding=binding, captured=captured, objects=objects,
                           raw=raw, replay=replay)


def test_offline_hal_xml_replay_preserves_all_raw_bindings_without_writes(saved_source):
    f = saved_source
    result = f.replay.reproject_stored_source(f.repo, f.stored.source_revision_id, object_store=f.objects)
    assert result.projection_version == "source-projection-v2"
    assert result.source_body.splitlines() == ["Service", "Inspect (o)", "Belt (c)", "Check belt."]
    for name in ("source_fingerprint", "body_source_snapshot_id", "resource_manifest", "resource_provenance",
                 "evidence_manifest", "captured_at", "context"):
        assert getattr(result, name) == getattr(f.stored, name)
    assert f.objects.puts == 0 and len(f.objects.gets) == 1


@pytest.mark.parametrize("damage", ["extra_manifest", "failed_manifest", "asset_ref", "labor_ref", "image",
    "missing_blob", "bad_hash", "bad_key", "bad_media", "bad_provider", "bad_ref", "bad_snapshot",
    "bad_provenance", "bad_fingerprint", "unknown_version", "oversized"])
def test_offline_replay_fails_closed(saved_source, damage):
    f = saved_source
    if damage == "extra_manifest": f.stored.resource_manifest.append({"role": "asset"})
    elif damage == "failed_manifest": f.stored.resource_manifest[0]["failure_code"] = "NOT_FOUND"
    elif damage in ("asset_ref", "labor_ref"):
        f.stored.context.descriptor["asset_resource_refs" if damage == "asset_ref" else "labor_resource_ref"] = ["extra"] if damage == "asset_ref" else "labor"
    elif damage == "image":
        # Keep every immutable raw binding internally consistent: parsed image is the reason to reject.
        raw = b'<p>Inspect belt.</p><img src="https://fixture.invalid/image">'
        digest = sha256(raw).hexdigest(); key = "sources/" + digest[:16] + "/" + digest
        from autodata_ingestion.source_article_capture import snapshot_id
        from autodata_ingestion.article_lifecycle_types import digest_json
        f.stored.resource_manifest[:] = [{"role": "body", "opaque_ref": "body", "sha256": digest, "media_type": "text/html"}]
        f.binding.update(sha256=digest, content_sha256=digest, object_key=key, media_type="text/html", snapshot_id=snapshot_id(digest))
        f.binding["resource_provenance"][0].update(sha256=digest, object_key=key, media_type="text/html", source_snapshot_id=str(snapshot_id(digest)))
        f.stored.body_source_snapshot_id = snapshot_id(digest)
        f.stored.source_fingerprint = digest_json({"provider": "banktwo", "body_ref": "body", "body_sha256": digest,
            "body_media_type": "text/html", "resource_manifest": f.stored.resource_manifest})
        f.objects.data[key] = raw
    elif damage == "missing_blob": f.objects.data.clear()
    elif damage == "bad_hash": f.objects.data[f.binding["object_key"]] = b"changed"
    elif damage == "bad_key": f.binding["object_key"] = "incorrect"
    elif damage == "bad_media": f.binding["resource_provenance"][0]["media_type"] = "text/plain"
    elif damage == "bad_provider": f.binding["resource_provenance"][0]["provider"] = "bankone"
    elif damage == "bad_ref": f.binding["resource_provenance"][0]["opaque_ref"] = "other"
    elif damage == "bad_snapshot": f.binding["snapshot_id"] = uuid4()
    elif damage == "bad_provenance": f.binding["resource_provenance"].clear()
    elif damage == "bad_fingerprint": f.stored.source_fingerprint = "0" * 64
    elif damage == "unknown_version": f.stored.projection_version = "future"
    elif damage == "oversized": f.objects.data[f.binding["object_key"]] = b"x" * (1024 * 1024 + 1)
    with pytest.raises((ValueError, KeyError)):
        f.replay.reproject_stored_source(f.repo, f.stored.source_revision_id, object_store=f.objects)
    assert f.objects.puts == 0


def test_offline_replay_bounds_total_deadline(saved_source):
    f = saved_source
    def slow(key, *, max_bytes):
        time.sleep(.2); return f.raw
    f.objects.get_object = slow
    before = time.monotonic()
    with pytest.raises(ValueError, match="DEADLINE"):
        f.replay.reproject_stored_source(f.repo, f.stored.source_revision_id, object_store=f.objects, deadline_seconds=.03)
    assert time.monotonic() - before < .15


def test_bounded_object_read_closes_response_and_rejects_size():
    from autodata_ingestion.worker import ArticleObjectStore
    from io import BytesIO
    class Response(BytesIO):
        released = False
        def release_conn(self): self.released = True
    store = ArticleObjectStore.__new__(ArticleObjectStore); store.bucket = "fixture"
    for payload, limit, fails in [(b"abc", 3, False), (b"abcd", 3, True)]:
        response = Response(payload)
        store.client = SimpleNamespace(get_object=lambda *a: response)
        if fails:
            with pytest.raises(ValueError): store.get_object("key", max_bytes=limit)
        else: assert store.get_object("key", max_bytes=limit) == payload
        assert response.closed and response.released


# These tests run only inside the isolated lifecycle Compose stack.
from lifecycle_support import runtime, fresh_database


def seed_v1(runtime, monkeypatch, *, xml=True):
    from autodata_ingestion import source_article_capture as capture_module
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    original = capture_module.capture_source_article
    if xml:
        runtime.article_id = runtime.articles["banktwo"]
        runtime.servers["banktwo"].body(json.dumps({"_embedded": {"data": {"article": {"content": XML}}}}).encode(), "application/hal+json")
    def historical(*args, **kwargs):
        captured = original(*args, **kwargs)
        if xml:
            document = deepcopy(captured.source_document)
            document["blocks"] = [{"block_id": "historical", "type": "paragraph", "text": XML,
                                   "evidence_ids": list(captured.context.evidence_ids)}]
            captured = replace(captured, source_document=document, source_body=XML, source_steps=[])
        return replace(captured, projection_version="source-projection-v1")
    monkeypatch.setattr(capture_module, "capture_source_article", historical)
    runtime.ensure()
    run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                           object_store=runtime.objects, model_client=None)
    monkeypatch.setattr(capture_module, "capture_source_article", original)
    runtime.reset_counters()
    return runtime.read_current()["source_revision_id"]


def all_rows(repo):
    with repo.connect() as conn:
        return {table: conn.execute("SELECT * FROM " + table).fetchall() for table in (
            "canonical_articles", "source_fetch_jobs", "canonical_article_source_revisions",
            "canonical_article_source_observations", "canonical_article_revisions", "publication_events",
            "canonical_article_rewrite_attempts", "source_snapshots", "source_artifacts")}


def test_source_only_atomic_apply_preview_idempotency_and_later_normal_owner(runtime, monkeypatch):
    from autodata_ingestion.source_revision_reprojection import reproject_stored_source, apply_source_reprojection
    from autodata_ingestion.article_lifecycle_store import load_source_revision
    old_id = seed_v1(runtime, monkeypatch)
    before = all_rows(runtime.repo)
    captured = reproject_stored_source(runtime.repo, old_id, object_store=runtime.objects)
    assert all_rows(runtime.repo) == before
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
    applied = apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured,
                                        actor="fixture", reason="offline correction")
    assert applied["status"] == "applied"
    state = runtime.read_current()
    assert state["source_revision_id"] != old_id and state["content_origin"] == "source"
    assert state["canonical_revision_id"] is None and "Check belt." in state["body"]
    assert "<maintenance_schedule" in load_source_revision(runtime.repo, old_id).source_body
    assert load_source_revision(runtime.repo, state["source_revision_id"]).projection_version == "source-projection-v2"
    with runtime.repo.connect() as conn:
        job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (state["job_id"],)).fetchone()
        assert job["status"] == "needs_review" and job["error_code"] == "SOURCE_ONLY_REPROJECTION"
        assert job["transformation_key"] is None and not job["retryable"]
        assert job["lease_owner"] is None and job["lease_expires_at"] is None
        assert job["checkpoint"]["source_only_reprojection"] is True
    after = all_rows(runtime.repo)
    repeated = apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured,
                                          actor="fixture", reason="offline correction")
    assert repeated["status"] == "already_applied" and all_rows(runtime.repo) == after
    for table, rows in before.items():
        if table not in ("canonical_articles",): assert all(row in after[table] for row in rows)
    # A normal refresh can own the v2 transformation key; source-only never reserves it.
    from autodata_ingestion.source_job_persistence import claim_source_job, fail_source_job
    from autodata_ingestion.article_lifecycle_store import store_captured_source
    runtime.refresh(); lease = claim_source_job(runtime.repo, worker_id=uuid4())
    from autodata_ingestion.article_lifecycle import _capture_context
    normal = capture_source_article(_capture_context(runtime.repo, lease), registry=runtime.registry, object_store=runtime.objects)
    assert store_captured_source(runtime.repo, lease, normal) == state["source_revision_id"]
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT transformation_key FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (lease.job_id,)).fetchone()["transformation_key"] is not None
    fail_source_job(runtime.repo, lease, code="FIXTURE_DONE", retryable=False)
    with pytest.raises(ValueError, match="CURRENT_SOURCE_CHANGED"):
        apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured, actor="fixture", reason="stale preview")


@pytest.mark.parametrize("point", ["job_created", "source_inserted", "pointer_updated"])
def test_source_only_failures_roll_back_entire_transaction(runtime, monkeypatch, point):
    from autodata_ingestion import source_revision_reprojection as replay
    from autodata_ingestion import article_lifecycle_store as store
    old_id = seed_v1(runtime, monkeypatch)
    captured = replay.reproject_stored_source(runtime.repo, old_id, object_store=runtime.objects)
    before = all_rows(runtime.repo)
    # Database trigger injection tests the real transaction, rather than a test hook.
    with runtime.repo.connect() as conn:
        if point == "job_created": table, timing = "source_fetch_jobs", "AFTER INSERT"
        elif point == "source_inserted": table, timing = "canonical_article_source_revisions", "AFTER INSERT"
        else: table, timing = "canonical_articles", "AFTER UPDATE OF current_source_revision_id"
        conn.execute("CREATE FUNCTION fail_reprojection() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$")
        conn.execute("CREATE TRIGGER fail_reprojection " + timing + " ON " + table + " FOR EACH ROW EXECUTE FUNCTION fail_reprojection()")
    import psycopg
    with pytest.raises(psycopg.Error):
        replay.apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured, actor="fixture", reason="rollback")
    assert all_rows(runtime.repo) == before


def test_source_only_queue_exclusion_exact_claim_and_pointer_race(runtime, monkeypatch):
    from autodata_ingestion import source_revision_reprojection as replay
    from autodata_ingestion.source_job_persistence import claim_source_job, claim_source_only_job, LeaseLost
    old_id = seed_v1(runtime, monkeypatch)
    captured = replay.reproject_stored_source(runtime.repo, old_id, object_store=runtime.objects)
    # A pending unrelated normal job must remain untouched by exact-ID apply.
    from autodata_ingestion.source_job_persistence import ensure_article_job
    other = runtime.articles["bankone"]
    unrelated = ensure_article_job(runtime.repo, other, normalization_version="ordered-article-v1", rewrite_profile_version="technical-prose-v1")
    with runtime.repo.connect() as conn:
        with conn.cursor() as cur, pytest.raises(LeaseLost):
            claim_source_only_job(cur, unrelated.job_id, other, worker_id=uuid4())
    replay.apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured, actor="fixture", reason="target only")
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT status FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (unrelated.job_id,)).fetchone()["status"] == "pending"
        job = runtime.current_job_id()
        conn.execute("UPDATE source_fetch_jobs SET status='pending' WHERE source_fetch_job_id=%s", (job,))
    assert claim_source_job(runtime.repo, worker_id=uuid4()).job_id == unrelated.job_id
    assert claim_source_job(runtime.repo, worker_id=uuid4()) is None
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='processing',retry_count=max_attempts,lease_owner=%s,heartbeat_at=clock_timestamp(),lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s", (uuid4(),job))
    assert claim_source_job(runtime.repo, worker_id=uuid4()) is None
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT status FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job,)).fetchone()["status"] == "processing"
    with pytest.raises((ValueError, KeyError)):
        replay.apply_source_reprojection(runtime.repo, runtime.article_id, uuid4(), captured, actor="fixture", reason="race")


@pytest.fixture
def reprojection_cli():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "scripts/dev/reproject_article_source.py"
    spec = importlib.util.spec_from_file_location("reproject_cli", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_cli_defaults_to_preview_with_safe_output(saved_source, reprojection_cli, capsys, monkeypatch):
    f = saved_source; cli = reprojection_cli
    monkeypatch.setattr(cli, "reproject_stored_source", lambda *a, **kw: f.captured)
    cli.main(["--article-id", str(__import__('autodata_ingestion.article_lifecycle_types', fromlist=['article_id']).article_id(f.captured.context.key)),
              "--source-revision-id", str(f.stored.source_revision_id)], repo=f.repo, object_store=f.objects)
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "preview"
    assert "Check belt" not in output and "fixture:body" not in output and "provider-rev" not in output


def test_cli_apply_requires_preview_binding_and_actor_reason(saved_source, reprojection_cli, monkeypatch):
    f = saved_source; cli = reprojection_cli
    from autodata_ingestion.article_lifecycle_types import article_id
    args = ["--article-id", str(article_id(f.captured.context.key)), "--source-revision-id", str(f.stored.source_revision_id), "--apply"]
    with pytest.raises(SystemExit): cli.main(args, repo=f.repo, object_store=f.objects)
    monkeypatch.setattr(cli, "reproject_stored_source", lambda *a, **kw: f.captured)
    calls = []
    monkeypatch.setattr(cli, "apply_source_reprojection", lambda *a, **kw: calls.append(a) or {"status": "applied"})
    args += ["--actor", "fixture", "--reason", "offline", "--expected-fingerprint", "0" * 64,
             "--expected-body-sha256", f.binding["content_sha256"]]
    with pytest.raises(ValueError, match="PREVIEW_BINDING"):
        cli.main(args, repo=f.repo, object_store=f.objects)
    assert calls == []
    args[-3] = f.captured.source_fingerprint
    cli.main(args, repo=f.repo, object_store=f.objects)
    assert len(calls) == 1


def test_apply_rejects_active_normal_refresh_and_changed_preview(runtime, monkeypatch):
    from autodata_ingestion import source_revision_reprojection as replay
    old_id = seed_v1(runtime, monkeypatch)
    captured = replay.reproject_stored_source(runtime.repo, old_id, object_store=runtime.objects)
    before = all_rows(runtime.repo)
    with pytest.raises(ValueError, match="PREVIEW_BINDING"):
        replay.apply_source_reprojection(runtime.repo, runtime.article_id, old_id,
            replace(captured, source_fingerprint="0" * 64), actor="fixture", reason="bad preview")
    assert all_rows(runtime.repo) == before
    runtime.refresh()
    before = all_rows(runtime.repo)
    with pytest.raises(ValueError, match="ACTIVE_NORMAL_JOB"):
        replay.apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured,
                                        actor="fixture", reason="normal refresh active")
    assert all_rows(runtime.repo) == before


def test_offline_deadline_includes_repository_reads(saved_source, monkeypatch):
    f = saved_source
    def slow_load(*args):
        time.sleep(.2); return f.stored
    monkeypatch.setattr(f.replay, "load_source_revision", slow_load)
    started = time.monotonic()
    with pytest.raises(ValueError, match="DEADLINE"):
        f.replay.reproject_stored_source(f.repo, f.stored.source_revision_id, object_store=f.objects,
                                         deadline_seconds=.03)
    assert time.monotonic() - started < .15


def test_replay_retains_legacy_blob_id_without_rewriting_evidence_identity(saved_source):
    f = saved_source
    deterministic_id = str(f.stored.body_source_snapshot_id)
    saved_id = uuid4()
    f.stored.body_source_snapshot_id = saved_id
    f.stored.context = replace(f.stored.context, evidence_ids=(deterministic_id,))
    f.stored.evidence_manifest = [{"evidence_id": deterministic_id, "body_source_snapshot_id": str(saved_id)}]
    f.binding["snapshot_id"] = saved_id
    f.binding["resource_provenance"][0]["source_snapshot_id"] = str(saved_id)
    captured = f.replay.reproject_stored_source(f.repo, f.stored.source_revision_id, object_store=f.objects)
    assert captured.body_source_snapshot_id == saved_id
    assert captured.evidence_manifest == f.stored.evidence_manifest
    assert captured.context.evidence_ids == (deterministic_id,)


def test_repeat_apply_of_v2_current_source_is_idempotent(runtime, monkeypatch):
    from autodata_ingestion import source_revision_reprojection as replay
    old_id = seed_v1(runtime, monkeypatch)
    captured = replay.reproject_stored_source(runtime.repo, old_id, object_store=runtime.objects)
    replay.apply_source_reprojection(runtime.repo, runtime.article_id, old_id, captured,
                                     actor="fixture", reason="v1 correction")
    current_id = runtime.read_current()["source_revision_id"]
    v2 = replay.reproject_stored_source(runtime.repo, current_id, object_store=runtime.objects)
    first = replay.apply_source_reprojection(runtime.repo, runtime.article_id, current_id, v2,
                                              actor="fixture", reason="v2 replay")
    before = all_rows(runtime.repo)
    second = replay.apply_source_reprojection(runtime.repo, runtime.article_id, current_id, v2,
                                               actor="fixture", reason="v2 replay")
    assert first["source_revision_id"] == second["source_revision_id"] == str(current_id)
    assert second["status"] == "already_applied" and all_rows(runtime.repo) == before
