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
from .source_connector_client import SourceEnvelopeV1

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
    envelope = SourceEnvelopeV1(owner["request_id"], owner["provider"], owner["source_revision"],
        owner["fetched_at"], owner["locator"], {"kind": "article", "media_type": body["media_type"],
        "sha256": body["sha256"]}, raw_resource=payload)
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
    from .article_lifecycle_store import _store_captured_source
    from .source_job_persistence import claim_source_only_job
    if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError("SOURCE_REPLAY_ACTOR_REASON_REQUIRED")
    if len(actor) > 256 or len(reason) > 2048:
        raise ValueError("SOURCE_REPLAY_ACTOR_REASON_INVALID")
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
        active = cur.execute("""SELECT source_fetch_job_id FROM source_fetch_jobs
            WHERE canonical_article_id=%s AND status IN ('pending','processing','failed')
              AND NOT (checkpoint @> '{"source_only_reprojection":true}'::jsonb) LIMIT 1""",
            (canonical_article_id,)).fetchone()
        if active: raise ValueError("SOURCE_REPLAY_ACTIVE_NORMAL_JOB")
        generation = article["request_generation"] + 1
        job_id = uuid4()
        checkpoint = {"source_only_reprojection": True, "original_source_revision_id": str(expected_source_revision_id),
            "actor": actor, "reason": reason, "expected_fingerprint": captured.source_fingerprint,
            "projection_document_hash": digest_json(captured.source_document)}
        cur.execute("""INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,
            source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,
            canonical_article_id,request_generation,normalization_version,rewrite_profile_version,checkpoint)
            VALUES (%s,%s,%s,%s,%s,'source-only-reprojection-v2',%s,%s,'pending','article',%s,%s,%s,%s,%s)""",
            (job_id, article["provider_slug"], article["vehicle_id"], article["source_vehicle_ref"],
             article["source_article_ref"], article["provider_slug"], f"source-only:{canonical_article_id}:{generation}",
             canonical_article_id, generation, article["target_normalization_version"],
             article["target_rewrite_profile_version"], Jsonb(checkpoint)))
        cur.execute("UPDATE canonical_articles SET request_generation=%s,current_job_id=%s WHERE canonical_article_id=%s",
                    (generation, job_id, canonical_article_id))
        lease = claim_source_only_job(cur, job_id, canonical_article_id, worker_id=uuid4())
        revision = _store_captured_source(cur, lease, captured)
        return {"status": "applied", "source_revision_id": str(revision), "job_id": str(job_id)}
