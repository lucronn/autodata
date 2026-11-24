"""Publish a same-body legacy Bankone SVG refresh without interrupting the reader."""
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

import pytest
from PIL import ImageColor, Image
from psycopg.errors import LockNotAvailable

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_document import project_ordered_document
from autodata_ingestion.article_lifecycle import run_article_job, run_article_worker_once
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, ArticleKey, SourceArticleContext, digest_json
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite import build_rewrite_prompt
from autodata_ingestion.procedure_rewrite_auto import render_auto
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.published_media_repair import _render_technical_v1
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
from autodata_ingestion.source_job_persistence import (
    claim_source_job, ensure_article_job, refresh_article_job, source_bound_rewrite_source_allowed,
)
from autodata_ingestion.source_table_replay import load_table_replay_binding
from lifecycle_support import fresh_database, seed_configuration, seed_snapshot, seed_vehicle
from test_article_transform import Model


TECHNICAL_PROFILE = "technical-prose-v1"
NORMALIZATION = "ordered-article-v1"
REFS = tuple(f"fixture-graphic-{index}" for index in range(1, 13))
HTML = (
    "<p>Remove the shield.</p>"
    + "".join(
        f'<mtr-image id="{index}" alt="Fixture alignment diagram {index}"></mtr-image>'
        f"<p>Install the replacement fastener at station {index}.</p>"
        for index in range(1, 13)
    )
).encode()


def _sha(payload):
    return sha256(payload).hexdigest()


def _svg(index):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{24 + index}" height="12">'
        '<rect width="100%" height="100%" fill="red"/></svg>'
    ).encode()


def _locator(index):
    return "bankone:asset:" + _sha(
        json.dumps({"kind": "graphic", "id": str(index)}, separators=(",", ":")).encode()
    )[:24]


def _envelope(reference, payload, media, locator, *, refs=()):
    return SourceEnvelopeV1(
        str(uuid4()), "bankone", "fixture-source-one", "2026-11-24T09:00:00Z", locator,
        {"kind": "article" if reference == "body" else "asset", "media_type": media,
         "sha256": _sha(payload), **({"asset_resource_refs": list(refs)} if refs else {})},
        raw_resource=payload,
    )


class Connector:
    provider = "bankone"

    def __init__(self, *, legacy, body=HTML):
        self.legacy = legacy
        self.body = body
        self.calls = Counter()
        self.assets = {
            ref: _envelope(ref, _svg(index), "image/svg+xml", _locator(index))
            for index, ref in enumerate(REFS, 1)
        }

    def read_resource(self, reference, *, timeout):
        assert timeout > 0
        self.calls[reference] += 1
        if reference == "body":
            return _envelope("body", self.body, "text/html", "bankone:fixture-body", refs=REFS)
        if self.legacy:
            raise SourceConnectorError("UNSUPPORTED_ASSET_MEDIA")
        return self.assets[reference]


class MemoryObjects:
    def __init__(self):
        self.data = {}

    def put_object(self, key, data, media):
        assert self.data.get(key, (data, media)) == (data, media)
        self.data[key] = (data, media)


class RecordingModel(Model):
    def __init__(self, *, reject=False):
        self.calls = []
        self.reject = reject

    def complete_json(self, prompt):
        self.calls.append(prompt)
        if self.reject:
            return {"replacements": []}
        request = json.loads(prompt)
        if request.get("profile_version") == AUTOMATIC_REWRITE_PROFILE:
            return {
                "introduction": "This article describes service information.",
                "replacements": [
                    {"block_id": slot["block_id"], "path": slot["path"],
                     "action": slot["required_action"], "reason": "Preserve the exact source wording.",
                     "text": slot["text"] if slot["required_action"] == "retain" else
                     slot["text"].replace("Remove", "Take off").replace("Install", "Fit")}
                    for slot in request["slots"]
                ],
            }
        return super().complete_json(prompt)


def _legacy_capture(context, connector, objects):
    captured = capture_source_article(context, registry={"bankone": connector}, object_store=objects)
    assert captured.projection_version == "source-projection-v2"
    figures = captured.source_document["blocks"][-len(REFS):]
    for index, (ref, block) in enumerate(zip(REFS, figures, strict=True), 1):
        assert block["image_id"] == digest_json({"provider": "bankone", "ref": ref})
        assert block["status"] == "unavailable"
        # Represent the legacy projection shape: recorded useful alt and the generic fallback reason.
        block.update(alt=f"Fixture alignment diagram {index}", unavailable_reason="source image reference is missing")
    return replace(captured, source_images=project_ordered_document(captured.source_document)["images"])


def _localize_fixture(monkeypatch):
    originals = {_svg(index): index for index in range(1, 13)}

    def convert(payload, *, timeout):
        assert timeout > 0
        index = originals[payload]
        output = BytesIO()
        Image.new("RGB", (24 + index, 12), ImageColor.getrgb("red")).save(output, format="PNG")
        return output.getvalue()

    monkeypatch.setattr("autodata_ingestion.source_article_capture.rasterize_svg", convert)


def _state(repo, article_id):
    with repo.connect() as conn:
        row = conn.execute(
            """SELECT
                a.current_source_revision_id AS source, a.current_canonical_revision_id AS canonical,
                v.source_revision_id AS served_source, v.canonical_revision_id AS served_canonical,
                v.content_origin AS origin, v.processing_state AS phase, v.document, v.images,
                (SELECT count(*) FROM publication_events WHERE canonical_article_id=a.canonical_article_id) AS events
            FROM canonical_articles a JOIN catalog_article_current v USING(canonical_article_id)
            WHERE a.canonical_article_id=%s""", (article_id,),
        ).fetchone()
    return dict(row)


def _job(repo, job_id):
    with repo.connect() as conn:
        return conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()


def _old_source_rows(repo, source_id):
    with repo.connect() as conn:
        source = conn.execute(
            "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s", (source_id,),
        ).fetchone()
        observations = conn.execute(
            "SELECT * FROM canonical_article_source_observations WHERE source_revision_id=%s", (source_id,),
        ).fetchall()
    return source, observations


def _assert_original_served(state, baseline):
    assert state["source"] == state["served_source"] == baseline["source"]
    assert state["canonical"] == state["served_canonical"] == baseline["canonical"]
    assert state["origin"] == "canonical" and state["events"] == 1
    assert (state["document"], state["images"]) == (baseline["document"], baseline["images"])


class WorkerStopped(Exception):
    pass


@pytest.mark.parametrize(("profile", "outcome"), (
    pytest.param(TECHNICAL_PROFILE, "success", id="technical-publication"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "resume", id="automatic-resume"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "reject", id="automatic-failure-dedupe"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "capture-rights", id="automatic-capture-rights"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "changed-body", id="exact-refresh-changed-body"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "withdraw", id="automatic-withdrawal"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "concurrent-old-rights", id="automatic-locks-old-resolution"),
    pytest.param(AUTOMATIC_REWRITE_PROFILE, "stale", id="automatic-owner-changed"),
))
def test_same_body_legacy_svg_refresh_keeps_published_pair_until_atomic_swap(fresh_database, monkeypatch, profile, outcome):
    repo = fresh_database()
    _localize_fixture(monkeypatch)
    vehicle_id = seed_vehicle(repo)
    configuration_id = seed_configuration(repo, vehicle_id)
    key = ArticleKey("bankone", vehicle_id, configuration_id, "fixture-vehicle", "fixture-article")
    descriptor_id = seed_snapshot(repo, b"fixture descriptor")
    resolution_id = seed_snapshot(repo, b"fixture resolution")
    descriptor = {"resource_ref": "body", "title": "Fixture fastener inspection"}
    article = store.upsert_article_descriptor(repo, key, descriptor, descriptor_id, 0, rewrite_profile_version=profile)
    context = SourceArticleContext(
        key, {"make": "Example", "model": "Car", "year": 2024, "region": "US"},
        descriptor, descriptor_id, resolution_id, (str(descriptor_id), str(resolution_id)),
    )
    objects = MemoryObjects()
    old_connector = Connector(legacy=True)
    old_capture = _legacy_capture(context, old_connector, objects)
    original_job = ensure_article_job(repo, article, normalization_version=NORMALIZATION, rewrite_profile_version=profile)
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=original_job.job_id)
    old_source_id = store.store_captured_source(repo, lease, old_capture)
    old_model = RecordingModel()
    run_article_job(repo, lease, registry={"bankone": old_connector}, object_store=objects, model_client=old_model)
    baseline = _state(repo, article)
    assert baseline["source"] == baseline["served_source"] == old_source_id
    assert baseline["canonical"] == baseline["served_canonical"] and baseline["canonical"] is not None
    assert baseline["origin"] == "canonical" and baseline["events"] == 1 and len(old_model.calls) == 1
    with repo.connect() as conn, conn.cursor() as cur:
        metadata = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article,)).fetchone()
        assert source_bound_rewrite_source_allowed(cur, metadata, old_source_id)
        old_binding = load_table_replay_binding(cur, old_source_id)
        old_canonical, _, _, old_attempt, old_reply, old_prompt_version, _ = _publication_evidence(
            cur, metadata, old_binding, fixture_mode=False, lock=False,
        )
        old_event = cur.execute("SELECT * FROM publication_events WHERE canonical_article_id=%s", (article,)).fetchone()
    assert old_attempt["prompt_hash"] == _sha(old_model.calls[0].encode())
    assert old_attempt["input_hash"] == digest_json(old_canonical["normalized_source_document"])
    assert old_attempt["response_hash"] == digest_json(old_reply)
    old_normal = old_canonical["normalized_source_document"]
    if profile == AUTOMATIC_REWRITE_PROFILE:
        replayed = render_auto(old_normal, old_reply, profile_version=profile, prompt_version=old_prompt_version)
    else:
        replayed = _render_technical_v1(old_normal, old_reply)
    assert replayed == old_canonical["canonical_document"]
    old_source_rows = _old_source_rows(repo, old_source_id)
    old_owner = _job(repo, original_job.job_id)
    old_objects = dict(objects.data)
    if outcome == "capture-rights":
        withheld = seed_snapshot(repo, _svg(1))
        with repo.connect() as conn:
            conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s",
                         (withheld,))
    if outcome == "concurrent-old-rights":
        fresh_resolution_id = seed_snapshot(repo, b"fixture newer resolution")
        with repo.connect() as conn:
            conn.execute("""INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,
                vehicle_configuration_id,scope_key,provider_slug,source_vehicle_ref,resolution_source_snapshot_id)
                VALUES (%s,%s,%s,%s,'bankone',%s,%s)""",
                (uuid4(), vehicle_id, configuration_id, key.scope_key, key.source_vehicle_ref, fresh_resolution_id))

    expected_pair = {}
    if outcome in ("resume", "changed-body", "concurrent-old-rights"):
        expected_pair = {
            "expected_source_revision_id": old_source_id,
            "expected_published_revision_id": baseline["canonical"],
        }
    if outcome == "resume":
        with pytest.raises(ValueError, match="^LEGACY_SVG_REFRESH_BINDING_INVALID$"):
            refresh_article_job(repo, article, actor="fixture", reason="stale figure refresh",
                                expected_source_revision_id=old_source_id, expected_published_revision_id=uuid4())
        assert _state(repo, article) == baseline
    refreshed = refresh_article_job(repo, article, actor="fixture", reason="same-digest figure refresh", **expected_pair)
    if expected_pair:
        assert _job(repo, refreshed.job_id)["checkpoint"]["require_positioned_svg_refresh"] == {
            "source_revision_id": str(old_source_id), "canonical_revision_id": str(baseline["canonical"]),
        }
    _assert_original_served(_state(repo, article), baseline)
    body = HTML.replace(b"Remove the shield.", b"Remove the lower shield.", 1) if outcome == "changed-body" else HTML
    connector = Connector(legacy=False, body=body)
    model = RecordingModel(reject=outcome == "reject")
    staged_jobs = []
    publication_checks = []
    capture_error = {
        "capture-rights": "STAGED_MEDIA_REFRESH_SOURCE_UNAVAILABLE",
        "changed-body": "LEGACY_SVG_REFRESH_BINDING_INVALID",
    }.get(outcome)

    def observe(point):
        if point == "after_source_commit":
            _assert_original_served(_state(repo, article), baseline)
            assert not model.calls
            if capture_error:
                return
            job = _job(repo, refreshed.job_id)
            assert job["source_revision_id"] not in (None, old_source_id)
            assert job["checkpoint"]["staged_media_refresh"] == {
                "version": 1, "source_revision_id": str(job["source_revision_id"]),
                "prior_source_revision_id": str(old_source_id),
                "prior_canonical_revision_id": str(baseline["canonical"]),
            }
            staged_jobs.append(job)
        if point == "after_model_result_commit" and outcome == "resume":
            _assert_original_served(_state(repo, article), baseline)
            raise WorkerStopped
        if point == "before_publication" and outcome == "withdraw":
            with repo.connect() as conn:
                snapshot = conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                    WHERE content_sha256=(SELECT resource_manifest->1->>'sha256'
                        FROM canonical_article_source_revisions WHERE source_revision_id=%s)
                    RETURNING source_snapshot_id""", (staged_jobs[0]["source_revision_id"],)).fetchone()
            assert snapshot is not None
        if point == "before_publication" and outcome == "stale":
            with repo.connect() as conn:
                conn.execute("""UPDATE canonical_articles SET request_generation=request_generation+1
                    WHERE canonical_article_id=%s""", (article,))
        if point == "inside_publication":
            # This independent reader must see the original pair until the worker commits both pointers.
            _assert_original_served(_state(repo, article), baseline)
            if outcome == "concurrent-old-rights":
                _, (fresh_observation,) = _old_source_rows(repo, staged_jobs[0]["source_revision_id"])
                assert old_source_rows[1][0]["resolution_source_snapshot_id"] == resolution_id
                assert fresh_observation["resolution_source_snapshot_id"] == fresh_resolution_id != resolution_id
                with pytest.raises(LockNotAvailable, match="lock timeout"), repo.connect() as withdrawal:
                    withdrawal.execute("SET LOCAL lock_timeout = '150ms'")
                    withdrawal.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                        WHERE source_snapshot_id=%s""", (resolution_id,))
            publication_checks.append(point)

    def run(model_client=model):
        return run_article_worker_once(
            repo, worker_id=uuid4(), registry={"bankone": connector}, object_store=objects,
            model_client=model_client, hooks=observe, job_id=refreshed.job_id,
        )

    if outcome == "resume":
        with pytest.raises(WorkerStopped):
            run()
        with repo.connect() as conn:
            conn.execute("""UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second'
                WHERE source_fetch_job_id=%s""", (refreshed.job_id,))
        assert run(None)
    else:
        assert run()
    final = _state(repo, article)
    if capture_error:
        _assert_original_served(final, baseline)
        with repo.connect() as conn:
            assert conn.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
                WHERE source_fetch_job_id=%s""", (refreshed.job_id,)).fetchone() is None
        assert model.calls == []
        rejected = _job(repo, refreshed.job_id)
        assert (rejected["status"], rejected["error_code"]) == ("dead_letter", capture_error)
        assert rejected["source_revision_id"] is None and rejected["transformation_key"] is None
        assert connector.calls["body"] == 1 and not publication_checks
        assert _job(repo, original_job.job_id) == old_owner
        assert _old_source_rows(repo, old_source_id) == old_source_rows
        return
    [staged] = staged_jobs
    assert len(model.calls) == 1
    assert connector.calls == Counter(("body", *REFS))
    new_source_id = staged["source_revision_id"]
    source = store.load_source_revision(repo, new_source_id)
    assert source.body_source_snapshot_id == old_capture.body_source_snapshot_id
    assert source.resource_manifest[0]["sha256"] == _sha(HTML)
    assert source.source_fingerprint != old_capture.source_fingerprint
    source_blocks = source.source_document["blocks"]
    assert [block["type"] for block in source_blocks] == ["paragraph", *(["image", "paragraph"] * len(REFS))]
    figures = source_blocks[1::2]
    assert all(block["status"] == "available" for block in figures)
    assert len(figures) == len(source.source_images) == 12
    originals = [entry for entry in source.resource_manifest if entry["role"] == "asset_original"]
    derivatives = [entry for entry in source.resource_manifest if entry["role"] == "asset"]
    assert [d["derived_from_sha256"] for d in derivatives] == [a["sha256"] for a in originals]
    for index, (figure, raster) in enumerate(zip(figures, derivatives, strict=True), 1):
        assert figure["alt"] == f"Fixture alignment diagram {index}"
        payload, mime = objects.data[figure["storage_key"]]
        assert mime == figure["media_type"] == "image/png"
        assert _sha(payload) == figure["content_sha256"] == raster["sha256"]
        with Image.open(BytesIO(payload)) as img:
            assert img.size == (24 + index, 12)

    normal = normalize_procedure_article(source.as_article(), resource_manifest=source.resource_manifest)["normalized_document"]
    assert digest_json(normal) != old_attempt["input_hash"]
    prompt = build_rewrite_prompt(normal, context=source.context.vehicle, profile_version=profile)
    assert prompt == model.calls[0] and _sha(prompt.encode()) != old_attempt["prompt_hash"]
    with repo.connect() as conn:
        persisted_old = conn.execute(
            "SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s", (baseline["canonical"],),
        ).fetchone()
        assert persisted_old == old_canonical
        persisted_attempt = conn.execute(
            "SELECT * FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s", (old_attempt["rewrite_attempt_id"],),
        ).fetchone()
        assert persisted_attempt == old_attempt
        refreshed_attempts = conn.execute("""SELECT * FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s""", (refreshed.job_id,)).fetchall()
        published = {
            row["canonical_article_revision_id"]: row for row in conn.execute("""
                SELECT * FROM publication_events WHERE canonical_article_id=%s""", (article,)).fetchall()
        }
    [refreshed_attempt] = refreshed_attempts
    assert refreshed_attempt["prompt_hash"] == _sha(prompt.encode())
    assert refreshed_attempt["response_hash"] == digest_json(refreshed_attempt["response"])
    refreshed_job = _job(repo, refreshed.job_id)
    assert refreshed_job["transformation_key"] != old_canonical["transformation_key"]
    assert _job(repo, original_job.job_id) == old_owner
    assert _old_source_rows(repo, old_source_id) == old_source_rows
    assert all(objects.data[key] == value for key, value in old_objects.items())
    assert published.pop(baseline["canonical"]) == old_event

    if outcome in ("success", "resume", "concurrent-old-rights"):
        assert final["source"] == final["served_source"] == new_source_id
        assert final["canonical"] == final["served_canonical"] and final["canonical"] != baseline["canonical"]
        assert final["origin"] == "canonical" and final["events"] == 2
        assert publication_checks == ["inside_publication"]
        assert list(published) == [final["canonical"]]
        assert published[final["canonical"]]["payload"]["source_revision_id"] == str(new_source_id)
        canonical_blocks = final["document"]["blocks"]
        if profile == AUTOMATIC_REWRITE_PROFILE:
            canonical_blocks = canonical_blocks[1:]
        assert [block["type"] for block in canonical_blocks] == [block["type"] for block in source_blocks]
        assert [block["alt"] for block in canonical_blocks if block["type"] == "image"] == [
            figure["alt"] for figure in figures
        ]
        if outcome == "concurrent-old-rights":
            with repo.connect() as conn:
                conn.execute("SET LOCAL lock_timeout = '150ms'")
                revoked = conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                    WHERE source_snapshot_id=%s AND takedown_status='active' RETURNING source_snapshot_id""",
                    (resolution_id,)).fetchone()
            assert revoked == {"source_snapshot_id": resolution_id}
            assert _state(repo, article) == final
    else:
        _assert_original_served(final, baseline)
        assert not publication_checks and not published
        assert refreshed_job["checkpoint"]["staged_media_refresh"] == staged["checkpoint"]["staged_media_refresh"]
        if outcome == "withdraw":
            assert refreshed_job["error_code"] == "STAGED_MEDIA_REFRESH_SOURCE_UNAVAILABLE"

    if outcome == "reject":
        retry = refresh_article_job(repo, article, actor="fixture", reason="check failed derivative fingerprint again")
        assert retry.job_id != refreshed.job_id
        assert run_article_worker_once(
            repo, worker_id=uuid4(), registry={"bankone": connector}, object_store=objects,
            model_client=model, job_id=retry.job_id,
        )
        _assert_original_served(_state(repo, article), baseline)
        assert len(model.calls) == 1
        reuse = _job(repo, retry.job_id)["checkpoint"]
        assert reuse["reused_terminal_result"] is True
        assert reuse["reused_transformation_job_id"] == str(refreshed.job_id)
