"""Bounded offline body replay. Never creates connector registries or model clients."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import replace
from hashlib import sha256
import time
from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_store import load_source_revision, _remap_snapshot_references
from .article_lifecycle_types import article_id, digest_json
from .source_article_capture import capture_source_article
from .source_connector_client import SourceEnvelopeV1, _valid_article_link_bindings

MAX_BODY_BYTES = 1024 * 1024
SUPPORTED_VERSIONS = {"source-projection-v1", "source-projection-v2"}


def _load_binding(repo, source_id):
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        return _binding_cursor(cur, source_id)


def _binding_cursor(cur, source_id, *, lock=False):
    return cur.execute("""SELECT o.body_provider_revision,o.resource_provenance,
        b.source_snapshot_id AS snapshot_id,b.content_sha256,b.object_key
        FROM canonical_article_source_revisions s
        JOIN source_snapshots b ON b.source_snapshot_id=s.body_source_snapshot_id
        JOIN LATERAL (SELECT * FROM canonical_article_source_observations
            WHERE source_revision_id=s.source_revision_id ORDER BY captured_at,source_observation_id LIMIT 1) o ON true
        WHERE s.source_revision_id=%s""" + (" FOR SHARE OF b" if lock else ""), (source_id,)).fetchone()


def _body_binding(stored, binding):
    if stored.projection_version not in SUPPORTED_VERSIONS or binding is None:
        raise ValueError("SOURCE_REPLAY_UNSUPPORTED")
    descriptor = stored.context.descriptor
    if descriptor.get("asset_resource_refs") or descriptor.get("labor_resource_ref"):
        raise ValueError("SOURCE_REPLAY_BODY_ONLY_REQUIRED")
    manifest = stored.resource_manifest
    provenance = binding["resource_provenance"]
    if len(manifest) != 1 or len(provenance) != 1:
        raise ValueError("SOURCE_REPLAY_BODY_ONLY_REQUIRED")
    body, owner = manifest[0], provenance[0]
    fields = {"role", "opaque_ref", "sha256", "media_type"}
    if "article_link_bindings" in body:
        fields.add("article_link_bindings")
        if (stored.context.key.provider != "bankone" or body.get("media_type") != "text/html"
            or not _valid_article_link_bindings(body["article_link_bindings"])):
            raise ValueError("SOURCE_REPLAY_BINDING_MISMATCH")
    elif "article_link_bindings" in owner:
        raise ValueError("SOURCE_REPLAY_BINDING_MISMATCH")
    ref = descriptor.get("resource_ref") or descriptor.get("body_resource_ref")
    if (set(body) != fields or body.get("role") != "body" or body.get("opaque_ref") != ref
        or any(owner.get(k) != body[k] for k in fields)
        or owner.get("provider") != stored.context.key.provider
        or owner.get("failure_code") or owner.get("source_revision") != binding["body_provider_revision"]
        or str(owner.get("source_snapshot_id")) != str(stored.body_source_snapshot_id)
        or str(binding["snapshot_id"]) != str(stored.body_source_snapshot_id)
        or binding["content_sha256"] != body["sha256"]
        or not all(owner.get(k) for k in ("request_id", "source_revision", "fetched_at", "locator"))):
        raise ValueError("SOURCE_REPLAY_BINDING_MISMATCH")
    digest = body["sha256"]
    key = "sources/" + digest[:16] + "/" + digest
    if binding["object_key"] != key or owner.get("object_key") != key:
        raise ValueError("SOURCE_REPLAY_BINDING_MISMATCH")
    expected = digest_json({"provider": stored.context.key.provider, "body_ref": ref,
        "body_sha256": digest, "body_media_type": body["media_type"], "resource_manifest": manifest})
    if stored.source_fingerprint != expected:
        raise ValueError("SOURCE_REPLAY_FINGERPRINT_MISMATCH")
    return body, owner


def reproject_stored_source(repo, source_revision_id, *, object_store, deadline_seconds=30):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("SOURCE_REPLAY_DEADLINE_INVALID")
    deadline = time.monotonic() + deadline_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_reproject_stored_source, repo, source_revision_id,
                           object_store=object_store, deadline=deadline).result(timeout=deadline_seconds)
    except TimeoutError:
        raise ValueError("SOURCE_REPLAY_DEADLINE") from None
    finally:
        # A late read can only finish verification; it cannot persist anything.
        pool.shutdown(wait=False, cancel_futures=True)


def _reproject_stored_source(repo, source_revision_id, *, object_store, deadline):
    def remaining():
        budget = deadline - time.monotonic()
        if budget <= 0: raise ValueError("SOURCE_REPLAY_DEADLINE")
        return budget
    stored = load_source_revision(repo, source_revision_id)
    binding = _load_binding(repo, source_revision_id)
    body, owner = _body_binding(stored, binding)
    budget = remaining()
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        payload = pool.submit(object_store.get_object, binding["object_key"], max_bytes=MAX_BODY_BYTES).result(timeout=budget)
    except TimeoutError:
        raise ValueError("SOURCE_REPLAY_DEADLINE") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if len(payload) > MAX_BODY_BYTES or sha256(payload).hexdigest() != body["sha256"]:
        raise ValueError("SOURCE_REPLAY_BODY_MISMATCH")
    resource = {"kind": "article", "media_type": body["media_type"], "sha256": body["sha256"]}
    if "article_link_bindings" in body:
        resource["article_link_bindings"] = body["article_link_bindings"]
    envelope = SourceEnvelopeV1(owner["request_id"], owner["provider"], owner["source_revision"],
        owner["fetched_at"], owner["locator"], resource, raw_resource=payload)
    class OfflineClient:
        provider = stored.context.key.provider
        def read_resource(self, ref, *, timeout):
            if ref != body["opaque_ref"]:
                raise ValueError("SOURCE_REPLAY_BODY_ONLY_REQUIRED")
            return envelope
    class VerifyOnlySink:
        def put_object(self, key, raw, media):
            if key != binding["object_key"] or raw != payload or media != body["media_type"]:
                raise ValueError("SOURCE_REPLAY_BODY_ONLY_REQUIRED")
    captured = capture_source_article(stored.context, registry={stored.context.key.provider: OfflineClient()},
        object_store=VerifyOnlySink(), deadline_seconds=remaining())
    remaining()
    if captured.source_images or len(captured.resources) != 1:
        raise ValueError("SOURCE_REPLAY_BODY_ONLY_REQUIRED")
    # Snapshot IDs can predate deterministic blob IDs. Retain persisted identity.
    raw_id = str(captured.body_source_snapshot_id)
    def remap(value):
        return _remap_snapshot_references(value, {raw_id: stored.body_source_snapshot_id})
    captured = replace(captured, body_source_snapshot_id=stored.body_source_snapshot_id,
        resources=tuple(remap(r) for r in captured.resources),
        resource_provenance=remap(captured.resource_provenance), evidence_manifest=remap(captured.evidence_manifest),
        captured_at=stored.captured_at)
    if (captured.source_fingerprint != stored.source_fingerprint
        or captured.resource_manifest != stored.resource_manifest
        or captured.resource_provenance != binding["resource_provenance"]
        or captured.evidence_manifest != stored.evidence_manifest):
        raise ValueError("SOURCE_REPLAY_IDENTITY_DRIFT")
    return captured


def apply_source_reprojection(repo, canonical_article_id, expected_source_revision_id, captured, *, actor, reason):
    """Append one source-only correction with exact identity, job and pointer fences."""
    _validate_actor_reason(actor, reason)
    if captured.projection_version != "source-projection-v2" or article_id(captured.context.key) != canonical_article_id:
        raise ValueError("SOURCE_REPLAY_IDENTITY_MISMATCH")
    original = load_source_revision(repo, expected_source_revision_id)
    binding = _load_binding(repo, expected_source_revision_id)
    _body_binding(original, binding)
    if (captured.context != original.context or captured.source_fingerprint != original.source_fingerprint
        or captured.body_source_snapshot_id != original.body_source_snapshot_id
        or captured.resource_manifest != original.resource_manifest
        or captured.resource_provenance != binding["resource_provenance"]
        or captured.evidence_manifest != original.evidence_manifest
        or captured.captured_at != original.captured_at or captured.source_images
        or len(captured.resources) != 1 or captured.resources[0] != binding["resource_provenance"][0]):
        raise ValueError("SOURCE_REPLAY_PREVIEW_BINDING_MISMATCH")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (canonical_article_id,)).fetchone()
        if article is None: raise KeyError("SOURCE_REPLAY_ARTICLE_NOT_FOUND")
        locked_binding = _binding_cursor(cur, expected_source_revision_id, lock=True)
        _body_binding(original, locked_binding)
        if locked_binding != binding:
            raise ValueError("SOURCE_REPLAY_PREVIEW_BINDING_MISMATCH")
        current = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                              (article["current_job_id"],)).fetchone()
        marker = current["checkpoint"] if current else {}
        if (current and current["status"] == "needs_review" and current["error_code"] == "SOURCE_ONLY_REPROJECTION"
            and marker.get("source_only_reprojection") is True
            and marker.get("original_source_revision_id") == str(expected_source_revision_id)
            and marker.get("actor") == actor and marker.get("reason") == reason
            and marker.get("expected_fingerprint") == captured.source_fingerprint
            and marker.get("projection_document_hash") == digest_json(captured.source_document)
            and current["source_revision_id"] == article["current_source_revision_id"]
            and current["request_generation"] == article["request_generation"]):
            return {"status": "already_applied", "source_revision_id": str(current["source_revision_id"]),
                    "job_id": str(current["source_fetch_job_id"])}
        if article["current_source_revision_id"] != expected_source_revision_id:
            raise ValueError("SOURCE_REPLAY_CURRENT_SOURCE_CHANGED")
        _require_no_active_normal_job(cur, canonical_article_id)
        checkpoint = {"source_only_reprojection": True, "original_source_revision_id": str(expected_source_revision_id),
            "actor": actor, "reason": reason, "expected_fingerprint": captured.source_fingerprint,
            "projection_document_hash": digest_json(captured.source_document)}
        return _apply_source_only(cur, article, captured, checkpoint)


def _validate_actor_reason(actor, reason):
    if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError("SOURCE_REPLAY_ACTOR_REASON_REQUIRED")
    if len(actor) > 256 or len(reason) > 2048:
        raise ValueError("SOURCE_REPLAY_ACTOR_REASON_INVALID")


def _require_no_active_normal_job(cur, canonical_article_id):
    active = cur.execute("""SELECT source_fetch_job_id FROM source_fetch_jobs
        WHERE canonical_article_id=%s AND status IN ('pending','processing','failed')
          AND NOT (checkpoint @> '{"source_only_reprojection":true}'::jsonb) LIMIT 1""",
        (canonical_article_id,)).fetchone()
    if active: raise ValueError("SOURCE_REPLAY_ACTIVE_NORMAL_JOB")


def _apply_source_only(cur, article, captured, checkpoint):
    from .article_lifecycle_store import _store_captured_source
    from .source_job_persistence import claim_source_only_job

    canonical_article_id = article["canonical_article_id"]
    generation = article["request_generation"] + 1
    job_id = uuid4()
    cur.execute("""INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,
        source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,
        canonical_article_id,request_generation,normalization_version,rewrite_profile_version,checkpoint)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending','article',%s,%s,%s,%s,%s)""",
        (job_id, article["provider_slug"], article["vehicle_id"], article["source_vehicle_ref"],
         article["source_article_ref"],
         "source-only-reprojection-" + captured.projection_version.rsplit("-", 1)[1], article["provider_slug"], f"source-only:{canonical_article_id}:{generation}",
         canonical_article_id, generation, article["target_normalization_version"],
         article["target_rewrite_profile_version"], Jsonb(checkpoint)))
    cur.execute("UPDATE canonical_articles SET request_generation=%s,current_job_id=%s WHERE canonical_article_id=%s",
                (generation, job_id, canonical_article_id))
    lease = claim_source_only_job(cur, job_id, canonical_article_id, worker_id=uuid4())
    revision = _store_captured_source(cur, lease, captured)
    return {"status": "applied", "source_revision_id": str(revision), "job_id": str(job_id)}


def apply_media_reprojection(repo, canonical_article_id, expected_source_revision_id, *, object_store,
                             expected_observation_id, expected_fingerprint, expected_body_sha256,
                             expected_document_sha256, actor, reason):
    """Replay again and install a verified media correction on a source-only article."""
    from .source_media_replay import (
        MEDIA_REPLAY_PROJECTION_VERSION, load_media_replay_binding, media_replay_document_hash,
        preview_media_replay, validate_media_replay_result,
    )

    _validate_actor_reason(actor, reason)
    binding, captured = preview_media_replay(repo, expected_source_revision_id, object_store=object_store)
    if (binding.canonical_article_id != canonical_article_id
        or binding.source_observation_id != expected_observation_id
        or binding.source_fingerprint != expected_fingerprint
        or binding.body_sha256 != expected_body_sha256
        or media_replay_document_hash(captured) != expected_document_sha256):
        raise ValueError("SOURCE_MEDIA_REPLAY_PREVIEW_BINDING_MISMATCH")
    checkpoint = {
        "source_only_reprojection": True,
        "original_source_revision_id": str(expected_source_revision_id),
        "original_source_observation_id": str(expected_observation_id),
        "actor": actor,
        "reason": reason,
        "expected_fingerprint": expected_fingerprint,
        "expected_body_sha256": expected_body_sha256,
        "projection_document_hash": expected_document_sha256,
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise KeyError("SOURCE_REPLAY_ARTICLE_NOT_FOUND")
        locked_binding = load_media_replay_binding(cur, expected_source_revision_id, lock=True)
        if locked_binding != binding:
            raise ValueError("SOURCE_MEDIA_REPLAY_PREVIEW_BINDING_MISMATCH")
        validate_media_replay_result(locked_binding, captured)
        if article["current_canonical_revision_id"] is not None:
            raise ValueError("SOURCE_MEDIA_REPLAY_PUBLISHED_REVISION")
        current = cur.execute("""
            SELECT j.source_fetch_job_id, j.status, j.error_code, j.checkpoint, j.request_generation,
                   s.source_revision_id, s.source_document, s.projection_version
            FROM source_fetch_jobs j JOIN canonical_article_source_revisions s USING(source_revision_id)
            WHERE j.source_fetch_job_id=%s AND s.source_revision_id=%s
        """, (article["current_job_id"], article["current_source_revision_id"])).fetchone()
        if (current and current["status"] == "needs_review"
            and current["error_code"] == "SOURCE_ONLY_REPROJECTION"
            and current["checkpoint"] == checkpoint
            and current["request_generation"] == article["request_generation"]
            and current["projection_version"] == MEDIA_REPLAY_PROJECTION_VERSION
            and digest_json(current["source_document"]) == expected_document_sha256):
            return {"status": "already_applied", "source_revision_id": str(current["source_revision_id"]),
                    "job_id": str(current["source_fetch_job_id"])}
        if article["current_source_revision_id"] != expected_source_revision_id:
            raise ValueError("SOURCE_REPLAY_CURRENT_SOURCE_CHANGED")
        _require_no_active_normal_job(cur, canonical_article_id)
        return _apply_source_only(cur, article, captured, checkpoint)


def apply_table_reprojection(repo, canonical_article_id, expected_source_revision_id, *,
                             object_store, expected_observation_id, expected_fingerprint,
                             expected_body_sha256, expected_document_sha256, actor, reason):
    """Append a verified span-only source revision for a source-only article."""
    from .source_table_replay import TABLE_REPLAY_PROJECTION_VERSION, load_table_replay_binding, preview_table_replay

    _validate_actor_reason(actor, reason)
    binding, captured = preview_table_replay(repo, expected_source_revision_id, object_store=object_store)
    row = binding.row
    if (row["canonical_article_id"] != canonical_article_id
            or row["source_observation_id"] != expected_observation_id
            or row["source_fingerprint"] != expected_fingerprint
            or row["resource_manifest"][0]["sha256"] != expected_body_sha256
            or digest_json(captured.source_document) != expected_document_sha256):
        raise ValueError("SOURCE_TABLE_REPLAY_PREVIEW_BINDING_MISMATCH")
    checkpoint = {
        "source_only_reprojection": True,
        "table_span_reprojection": True,
        "original_source_revision_id": str(expected_source_revision_id),
        "original_source_observation_id": str(expected_observation_id),
        "actor": actor,
        "reason": reason,
        "expected_fingerprint": expected_fingerprint,
        "expected_body_sha256": expected_body_sha256,
        "projection_document_hash": expected_document_sha256,
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise ValueError("SOURCE_TABLE_REPLAY_ARTICLE_NOT_FOUND")
        if load_table_replay_binding(cur, expected_source_revision_id, lock=True) != binding:
            raise ValueError("SOURCE_TABLE_REPLAY_PREVIEW_BINDING_MISMATCH")
        current = cur.execute("""
            SELECT j.source_fetch_job_id,j.status,j.error_code,j.checkpoint,j.request_generation,
                   s.source_revision_id,s.source_fingerprint,s.source_document,s.projection_version
            FROM source_fetch_jobs j JOIN canonical_article_source_revisions s USING(source_revision_id)
            WHERE j.source_fetch_job_id=%s AND s.source_revision_id=%s
        """, (article["current_job_id"], article["current_source_revision_id"])).fetchone()
        if (current and article["current_canonical_revision_id"] is None
                and current["status"] == "needs_review" and current["error_code"] == "SOURCE_ONLY_REPROJECTION"
                and current["checkpoint"] == checkpoint and current["request_generation"] == article["request_generation"]
                and current["projection_version"] == TABLE_REPLAY_PROJECTION_VERSION
                and current["source_fingerprint"] == captured.source_fingerprint
                and digest_json(current["source_document"]) == expected_document_sha256):
            return {"status": "already_applied", "source_revision_id": str(current["source_revision_id"]),
                    "job_id": str(current["source_fetch_job_id"])}
        if article["current_source_revision_id"] != expected_source_revision_id:
            raise ValueError("SOURCE_TABLE_REPLAY_CURRENT_SOURCE_CHANGED")
        if article["current_canonical_revision_id"] is not None:
            raise ValueError("SOURCE_TABLE_REPLAY_CANONICAL_ANCHOR")
        if cur.execute("SELECT 1 FROM schema_migrations WHERE version='045_article_source_projection_v5'").fetchone() is None:
            raise ValueError("SOURCE_TABLE_REPLAY_SCHEMA_REQUIRED")
        _require_no_active_normal_job(cur, canonical_article_id)
        _verify_projection_conflict(
            cur, canonical_article_id, captured, error="SOURCE_TABLE_REPLAY_PROJECTION_CONFLICT",
        )
        return _apply_source_only(cur, article, captured, checkpoint)


def _verify_projection_conflict(cur, canonical_article_id, captured, *, error):
    expected = {
        "body_source_snapshot_id": captured.body_source_snapshot_id,
        "source_document": captured.source_document,
        "source_body": captured.source_body,
        "source_images": captured.source_images,
        "source_steps": captured.source_steps,
        "resource_manifest": captured.resource_manifest,
        "evidence_manifest": captured.evidence_manifest,
        "projection_status": captured.projection_status,
    }
    existing = cur.execute("""
        SELECT body_source_snapshot_id,source_document,source_body,source_images,source_steps,
               resource_manifest,evidence_manifest,projection_status
        FROM canonical_article_source_revisions
        WHERE canonical_article_id=%s AND source_fingerprint=%s AND projection_version=%s
    """, (canonical_article_id, captured.source_fingerprint, captured.projection_version)).fetchone()
    if existing is not None and existing != expected:
        raise ValueError(error)


def preview_svg_reprojection(repo, source_revision_id, *, object_store, svg_archive):
    """Verify private SVG inputs against their immutable capture again."""
    from .source_svg_archive import read_svg_archive
    from .source_svg_recovery import build_svg_recovery

    original, assets = read_svg_archive(repo, source_revision_id, svg_archive)
    binding, captured, blobs = build_svg_recovery(
        repo, source_revision_id, object_store=object_store, assets=assets,
    )
    if original != binding:
        raise ValueError("SOURCE_SVG_REPLAY_SOURCE_CHANGED")
    return binding, captured, blobs


def svg_reprojection_digests(captured):
    return {
        "corrected_source_fingerprint": captured.source_fingerprint,
        "document_sha256": digest_json(captured.source_document),
        "provenance_sha256": digest_json(captured.resource_provenance),
    }


def apply_svg_reprojection(repo, canonical_article_id, expected_source_revision_id, *,
                           object_store, svg_archive, expected_observation_id, expected_fingerprint,
                           expected_body_sha256, expected_document_sha256, expected_corrected_fingerprint,
                           expected_provenance_sha256, actor, reason):
    """Install the exact previewed SVG repair while the article is source-only."""
    from .source_svg_recovery import check_svg_recovery_rights
    from .source_table_replay import load_table_replay_binding

    _validate_actor_reason(actor, reason)
    binding, captured, blobs = preview_svg_reprojection(
        repo, expected_source_revision_id, object_store=object_store, svg_archive=svg_archive,
    )
    expected = {
        "corrected_source_fingerprint": expected_corrected_fingerprint,
        "document_sha256": expected_document_sha256,
        "provenance_sha256": expected_provenance_sha256,
    }
    if (binding.canonical_article_id != canonical_article_id
            or binding.source_observation_id != expected_observation_id
            or binding.source_fingerprint != expected_fingerprint
            or binding.body_sha256 != expected_body_sha256
            or svg_reprojection_digests(captured) != expected):
        raise ValueError("SOURCE_SVG_REPLAY_PREVIEW_BINDING_MISMATCH")
    checkpoint = {
        "source_only_reprojection": True,
        "svg_reprojection": True,
        "original_source_revision_id": str(expected_source_revision_id),
        "original_source_observation_id": str(expected_observation_id),
        "actor": actor,
        "reason": reason,
        "expected_fingerprint": expected_fingerprint,
        "expected_body_sha256": expected_body_sha256,
        **expected,
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise ValueError("SOURCE_SVG_REPLAY_ARTICLE_NOT_FOUND")
        if article["current_canonical_revision_id"] is not None:
            raise ValueError("SOURCE_SVG_REPLAY_CANONICAL_ANCHOR")
        if load_table_replay_binding(cur, expected_source_revision_id, lock=True) != binding:
            raise ValueError("SOURCE_SVG_REPLAY_PREVIEW_BINDING_MISMATCH")
        if cur.execute("SELECT 1 FROM schema_migrations WHERE version='045_article_source_projection_v5'").fetchone() is None:
            raise ValueError("SOURCE_SVG_REPLAY_SCHEMA_REQUIRED")
        current = cur.execute("""
            SELECT j.source_fetch_job_id,j.status,j.error_code,j.checkpoint,j.request_generation,
                   s.source_revision_id,s.source_fingerprint,s.projection_version
            FROM source_fetch_jobs j JOIN canonical_article_source_revisions s USING(source_revision_id)
            WHERE j.source_fetch_job_id=%s AND s.source_revision_id=%s
        """, (article["current_job_id"], article["current_source_revision_id"])).fetchone()
        if (current and current["status"] == "needs_review"
                and current["error_code"] == "SOURCE_ONLY_REPROJECTION"
                and current["checkpoint"] == checkpoint
                and current["request_generation"] == article["request_generation"]
                and current["projection_version"] == captured.projection_version
                and current["source_fingerprint"] == captured.source_fingerprint):
            _verify_projection_conflict(
                cur, canonical_article_id, captured, error="SOURCE_SVG_REPLAY_PROJECTION_CONFLICT",
            )
            _verify_stored_svg_reprojection(cur, current["source_revision_id"], current["source_fetch_job_id"], captured)
            return {"status": "already_applied", "source_revision_id": str(current["source_revision_id"]),
                    "job_id": str(current["source_fetch_job_id"])}
        if article["current_source_revision_id"] != expected_source_revision_id:
            raise ValueError("SOURCE_SVG_REPLAY_CURRENT_SOURCE_CHANGED")
        _require_no_active_normal_job(cur, canonical_article_id)
        _verify_projection_conflict(
            cur, canonical_article_id, captured, error="SOURCE_SVG_REPLAY_PROJECTION_CONFLICT",
        )
        check_svg_recovery_rights(cur, captured, lock=True)
        for object_key, (payload, media_type) in blobs.items():
            object_store.put_object(object_key, payload, media_type)
        result = _apply_source_only(cur, article, captured, checkpoint)
        _verify_stored_svg_reprojection(cur, result["source_revision_id"], result["job_id"], captured)
        return result


def _verify_stored_svg_reprojection(cur, source_revision_id, job_id, captured):
    from .source_svg_recovery import check_svg_recovery_rights

    check_svg_recovery_rights(cur, captured, lock=True, require_existing=True)
    # Stored observations may use the pre-existing snapshot UUID for identical bytes.
    resources = captured.resources
    snapshots = {
        row["content_sha256"]: row["source_snapshot_id"] for row in cur.execute(
            "SELECT content_sha256, source_snapshot_id FROM source_snapshots WHERE content_sha256 = ANY(%s)",
            (sorted({resource["sha256"] for resource in resources}),),
        ).fetchall()
    }
    if any(resource["sha256"] not in snapshots for resource in resources):
        raise ValueError("SOURCE_SVG_REPLAY_PROVENANCE_MISMATCH")
    expected = _remap_snapshot_references(captured.resource_provenance, {
        resource["source_snapshot_id"]: snapshots[resource["sha256"]] for resource in resources
    })
    stored = cur.execute("""
        SELECT resource_provenance FROM canonical_article_source_observations
        WHERE source_revision_id=%s AND source_fetch_job_id=%s
    """, (source_revision_id, job_id)).fetchone()
    if stored is None or stored["resource_provenance"] != expected:
        raise ValueError("SOURCE_SVG_REPLAY_PROVENANCE_MISMATCH")
