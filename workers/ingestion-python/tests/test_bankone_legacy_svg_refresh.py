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
from psycopg.types.json import Jsonb

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_document import build_ordered_document, project_ordered_document
from autodata_ingestion.article_lifecycle import run_article_job, run_article_worker_once
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, ArticleKey, SourceArticleContext, digest_json
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite import build_rewrite_prompt
from autodata_ingestion.procedure_rewrite_auto import render_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.published_media_repair import _render_technical_v1
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
from autodata_ingestion.source_job_persistence import (
    claim_source_job, ensure_article_job, refresh_article_job, source_bound_rewrite_source_allowed,
)
from autodata_ingestion.source_table_replay import load_table_replay_binding
from autodata_ingestion.staged_media_reply_recovery import (
    CHECKPOINT, METHOD, _combine, audit_published_staged_media_reply, recover_staged_media_reply,
)
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


class FailedRefreshModel(RecordingModel):
    def complete_json(self, prompt):
        reply = super().complete_json(prompt)
        reply["introduction"] = "Tighten the fasteners to 90 Nm."
        reply["replacements"][0]["text"] = json.loads(prompt)["slots"][0]["text"]
        return reply


@pytest.mark.parametrize("heading", ["Removal", "Installation"])
def test_staged_reply_replay_only_remaps_an_exact_authored_heading(heading):
    article = {"article_id": "fixture", "evidence_ids": ["fixture-source"]}
    instructions = [
        {"kind": "paragraph", "text": "Remove the shield."},
        {"kind": "paragraph", "text": "Install the cover."},
    ]
    prior = build_ordered_document(article, [{"kind": "paragraph", "text": "Removal"}, *instructions])
    fresh = build_ordered_document(article, [{"kind": "heading", "level": 2, "text": heading}, *instructions])

    def reply(source, intro, wording):
        return {"introduction": intro, "replacements": [
            {**slot, "action": "rewrite", "text": text, "reason": ""}
            for slot, text in zip(prose_slots(source), wording, strict=True)
        ]}

    earlier = reply(prior, "This article describes service information.",
                    ["Removal instructions", "Take off the shield.", "Fit the cover."])
    failed = reply(fresh, "Tighten the cover to 90 Nm.", ["Remove the shield.", "Fit the cover."])
    args = (prior, earlier, "full-prose-auto-prompt-v2", fresh, failed, "full-prose-auto-prompt-v55")
    if heading != "Removal":
        with pytest.raises(ValueError, match="^STAGED_MEDIA_REPLY_RECOVERY_SLOT_DRIFT$"):
            _combine(*args)
        return
    document, validation, evidence = _combine(*args)
    assert validation.passed and evidence["restored_source_heading"] is True
    assert evidence["carried_slots"] == [{"prior_path": "/blocks/1/text", "replacement_path": "/blocks/1/text"}]
    assert document["blocks"][1]["type"] == "heading" and document["blocks"][1]["text"] == "Removal"
    assert document["blocks"][2]["text"] == "Take off the shield."


@pytest.mark.parametrize("outcome", [
    "publish", "stale-binding", "fresh-withdrawal", "prior-withdrawal",
    "prior-transcript", "failed-transcript", "failed-origin",
])
def test_recover_staged_media_from_two_immutable_attempts(fresh_database, monkeypatch, outcome):
    repo = fresh_database()
    _localize_fixture(monkeypatch)
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle)
    key = ArticleKey("bankone", vehicle, configuration, "fixture-vehicle", "fixture-article")
    descriptor_id = seed_snapshot(repo, b"fixture descriptor")
    old_resolution = seed_snapshot(repo, b"fixture original resolution")
    fresh_resolution = seed_snapshot(repo, b"fixture new resolution")
    descriptor = {"resource_ref": "body", "title": "Fixture fastener inspection"}
    article = store.upsert_article_descriptor(repo, key, descriptor, descriptor_id, 0)
    context = SourceArticleContext(
        key, {"make": "Example", "model": "Car", "year": 2024, "region": "US"},
        descriptor, descriptor_id, old_resolution, (str(descriptor_id), str(old_resolution)),
    )
    objects = MemoryObjects()
    old_connector = Connector(legacy=True)
    baseline_job = ensure_article_job(
        repo, article, normalization_version=NORMALIZATION, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=baseline_job.job_id)
    old_source = store.store_captured_source(repo, lease, _legacy_capture(context, old_connector, objects))
    old_model = RecordingModel()
    with monkeypatch.context() as historical:
        historical.setattr(auto, "build_auto_prompt", lambda document, *, context, profile_version:
                           auto._build_auto_prompt_v2(document, context=context))
        run_article_job(repo, lease, registry={"bankone": old_connector}, object_store=objects, model_client=old_model)
    assert json.loads(old_model.calls[0])["prompt_version"] == "full-prose-auto-prompt-v2"
    baseline = _state(repo, article)
    assert baseline["source"] == old_source and baseline["canonical"] is not None
    prior_review = uuid4()
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_reviews
            (canonical_article_review_id,canonical_article_revision_id,authorized_reviewer_id,decision,reason)
            VALUES (%s,%s,'fixture-reviewer','APPROVED','Fixture approval on the historical article.')""",
            (prior_review, baseline["canonical"]))
        conn.execute("""INSERT INTO catalog_article_provider_scopes
            (catalog_provider_scope_id,vehicle_id,vehicle_configuration_id,scope_key,provider_slug,
             source_vehicle_ref,resolution_source_snapshot_id)
            VALUES (%s,%s,%s,%s,'bankone','fixture-vehicle',%s)""",
            (uuid4(), vehicle, configuration, key.scope_key, fresh_resolution))
    refreshed = refresh_article_job(
        repo, article, actor="fixture", reason="restore the exact authored positions",
        expected_source_revision_id=old_source, expected_published_revision_id=baseline["canonical"],
    )
    connector, failed_model = Connector(legacy=False), FailedRefreshModel()
    assert run_article_worker_once(
        repo, worker_id=uuid4(), registry={"bankone": connector}, object_store=objects,
        model_client=failed_model, job_id=refreshed.job_id,
    )
    failed_job = _job(repo, refreshed.job_id)
    assert (failed_job["status"], failed_job["phase"], failed_job["error_code"]) == (
        "dead_letter", "validating", "REWRITE_TECHNICAL_MUTATION",
    )
    _assert_original_served(_state(repo, article), baseline)
    arguments = dict(
        expected_job_id=refreshed.job_id, expected_source_revision_id=failed_job["source_revision_id"],
        expected_published_revision_id=baseline["canonical"], actor="fixture-operator", reason="reuse the exact archived replies",
    )

    def rows():
        with repo.connect() as conn:
            revision = conn.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s",
                                    (failed_job["transformation_key"],)).fetchone()
            attempts = conn.execute("""SELECT * FROM canonical_article_rewrite_attempts
                WHERE source_fetch_job_id IN (%s,%s) ORDER BY created_at""",
                (baseline_job.job_id, refreshed.job_id)).fetchall()
            approvals = conn.execute("""SELECT * FROM canonical_article_reviews
                WHERE canonical_article_revision_id IN (%s,%s) ORDER BY reviewed_at""",
                (baseline["canonical"], revision["canonical_article_revision_id"])).fetchall()
        return revision, attempts, approvals

    with repo.connect() as conn:
        if outcome == "stale-binding":
            arguments["expected_published_revision_id"] = uuid4()
        elif outcome == "fresh-withdrawal":
            conn.execute("""UPDATE source_snapshots SET takedown_status='takedown' WHERE content_sha256=(
                SELECT resource_manifest->1->>'sha256' FROM canonical_article_source_revisions WHERE source_revision_id=%s)""",
                (failed_job["source_revision_id"],))
        elif outcome == "prior-withdrawal":
            conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s", (old_resolution,))
        elif outcome in ("prior-transcript", "failed-transcript"):
            owner = baseline_job.job_id if outcome == "prior-transcript" else refreshed.job_id
            conn.execute("UPDATE canonical_article_rewrite_attempts SET response_hash=%s WHERE source_fetch_job_id=%s",
                         ("f" * 64, owner))
        elif outcome == "failed-origin":
            # A self-consistent hash cannot transform a different terminal failure into the recorded one.
            reply = FailedRefreshModel().complete_json(failed_model.calls[0])
            reply["introduction"] = "This article describes service information."
            conn.execute("""UPDATE canonical_article_rewrite_attempts
                SET response=%s,response_hash=%s WHERE source_fetch_job_id=%s""",
                (Jsonb(reply), digest_json(reply), refreshed.job_id))
    original_rows = rows()
    before_state = _state(repo, article)
    connector_calls = connector.calls.copy()
    if outcome != "publish":
        with pytest.raises(ValueError):
            recover_staged_media_reply(repo, article, **arguments)
        assert rows() == original_rows
        assert _job(repo, refreshed.job_id) == failed_job
        assert _state(repo, article) == before_state
        return

    def interrupt(point):
        assert point == "inside_publication"
        assert _state(repo, article) == before_state
        raise WorkerStopped

    with pytest.raises(WorkerStopped):
        recover_staged_media_reply(repo, article, hooks=interrupt, **arguments)
    assert rows() == original_rows and _job(repo, refreshed.job_id) == failed_job
    assert _state(repo, article) == before_state

    revision_id = recover_staged_media_reply(repo, article, **arguments)
    revision, attempts, approvals = rows()
    assert revision_id == original_rows[0]["canonical_article_revision_id"]
    assert (attempts, approvals) == original_rows[1:]
    assert revision["model_metadata"]["transformation_method"] == METHOD
    evidence = revision["model_metadata"][CHECKPOINT]
    assert evidence["new_model_dispatches"] == 0 and evidence["carried_introduction"] is True
    assert len(evidence["carried_slots"]) == 1 and evidence["archived_fresh_slots"] == 12
    assert evidence["prior_attempt"]["attempt_id"] == str(attempts[0]["rewrite_attempt_id"])
    assert evidence["staged_attempt"]["attempt_id"] == str(attempts[1]["rewrite_attempt_id"])
    assert evidence["prior_prompt_version"] == "full-prose-auto-prompt-v2"
    assert evidence["staged_prompt_version"] == "full-prose-auto-prompt-v55"
    assert evidence["prior_review_id"] == str(prior_review)
    assert evidence["prior_source_revision_id"] == str(old_source)
    assert evidence["staged_source_revision_id"] == str(failed_job["source_revision_id"])
    assert revision["review_status"] == "UNREVIEWED"
    final = _state(repo, article)
    assert final["source"] == final["served_source"] == failed_job["source_revision_id"]
    assert final["canonical"] == final["served_canonical"] == revision_id and final["events"] == 2
    assert len(final["images"]) == 12 and all(image["status"] == "available" for image in final["images"])
    final_job = _job(repo, refreshed.job_id)
    assert final_job["checkpoint"][CHECKPOINT]["evidence"] == evidence
    assert final_job["retry_count"] == failed_job["retry_count"] == 1 and final_job["status"] == "completed"
    assert len(old_model.calls) == len(failed_model.calls) == 1 and connector.calls == connector_calls
    audit_request = dict(
        expected_job_id=refreshed.job_id, expected_source_revision_id=failed_job["source_revision_id"],
        expected_prior_source_revision_id=old_source, expected_prior_canonical_revision_id=baseline["canonical"],
    )
    assert audit_published_staged_media_reply(repo, article, **audit_request) == {
        "status": "verified", "archived_attempts": 2, "publication_events": 1,
        "archived_fresh_slots": 12, "new_model_dispatches": 0,
        "carried_slots": 1, "carried_introductions": 1, "figures": 12,
    }
    audit_request["expected_prior_source_revision_id"] = uuid4()
    with pytest.raises(ValueError, match="^STAGED_MEDIA_REPLY_RECOVERY_STALE$"):
        audit_published_staged_media_reply(repo, article, **audit_request)
    with pytest.raises(ValueError, match="^STAGED_MEDIA_REPLY_RECOVERY_STALE$"):
        recover_staged_media_reply(repo, article, **arguments)
    assert _state(repo, article) == final
