"""Restore a parked Banktwo source's notice order before its first rewrite."""

from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_lifecycle_store import _persist_article_capture
from .article_lifecycle_types import digest_json, transformation_key
from .retained_banktwo_notice_publication import _normalize
from .retained_procedure_repair import _valid_audit
from .rollout_model_lane import (
    _parked_rollout_candidates,
    _parked_rollout_source_allowed,
    _rollout_model_args,
)
from .source_banktwo_notice_replay import load_banktwo_notice_binding, preview_banktwo_notice_replay
from .source_job_persistence import RETAINED_NOTICE_REPROJECTION, RETAINED_NOTICE_SUPERSEDED


_STALE = "PARKED_BANKTWO_NOTICE_REPROJECTION_STALE"


def _installed(cur, prior, audit):
    successor = cur.execute(
        """SELECT j.source_fetch_job_id,j.source_revision_id,s.source_fingerprint,s.source_document
           FROM source_fetch_jobs j
           JOIN canonical_article_source_revisions s ON s.source_revision_id=j.source_revision_id
           JOIN canonical_article_source_observations o ON o.source_fetch_job_id=j.source_fetch_job_id
               AND o.source_revision_id=s.source_revision_id AND o.request_generation=j.request_generation
           WHERE j.canonical_article_id=%s AND j.request_generation=1
             AND j.source_fetch_job_id::text=%s AND j.checkpoint->%s=%s""",
        (prior["canonical_article_id"], prior["checkpoint"].get("notice_successor_job_id"),
         RETAINED_NOTICE_REPROJECTION, Jsonb(audit)),
    ).fetchone()
    if (prior["source_revision_id"] != UUID(audit["source_revision_id"]) or successor is None
            or successor["source_fingerprint"] != audit["fingerprint"]
            or digest_json(successor["source_document"]) != audit["document_sha256"]):
        raise ValueError(_STALE)
    return {
        "status": "already_applied", "job_id": str(successor["source_fetch_job_id"]),
        "source_revision_id": str(successor["source_revision_id"]),
    }


def reproject_parked_banktwo_notices(
    repo, snapshot, *, object_store, expected_job_id, expected_source_revision_id, expected_observation_id,
    expected_fingerprint, expected_document_sha256, actor, reason,
):
    """Append a verified source and transfer the original unspent reservation."""
    if not _valid_audit(actor, reason):
        raise ValueError("PARKED_BANKTWO_NOTICE_REPROJECTION_AUDIT_INVALID")
    job_id, source_id, observation_id = (
        UUID(str(value)) for value in (expected_job_id, expected_source_revision_id, expected_observation_id)
    )
    audit = {
        "job_id": str(job_id), "source_revision_id": str(source_id), "source_observation_id": str(observation_id),
        "fingerprint": expected_fingerprint, "document_sha256": expected_document_sha256,
        "actor": actor, "reason": reason,
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET LOCAL statement_timeout='5s'")
        # Own the prior job before reading its stored objects. Lock the article
        # only once the replay has finished and the new document is ready.
        prior = cur.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE", (job_id,),
        ).fetchone()
        if (prior is None or prior["job_kind"] != "article" or prior["provider_slug"] != "banktwo"
                or prior["source_revision_id"] != source_id or prior["request_generation"] != 0):
            raise ValueError(_STALE)
        if prior["error_code"] == RETAINED_NOTICE_SUPERSEDED:
            return _installed(cur, prior, audit)
        args = _rollout_model_args(snapshot)
        if args is None or prior["status"] != "failed" or prior["error_code"] != "MODEL_NOT_CONFIGURED":
            raise ValueError(_STALE)
        binding, captured = preview_banktwo_notice_replay(repo, source_id, object_store=object_store)
        if (binding.source_observation_id != observation_id
                or binding.canonical_article_id != prior["canonical_article_id"]
                or captured.source_fingerprint != expected_fingerprint
                or digest_json(captured.source_document) != expected_document_sha256):
            raise ValueError(_STALE)
        normalized = _normalize(captured, binding.canonical_article_id)
        rows = _parked_rollout_candidates(cur, args, job_id=job_id)
        if (not rows or rows[0]["source_observation_id"] != observation_id
                or not _parked_rollout_source_allowed(cur, rows[0])
                or load_banktwo_notice_binding(cur, source_id, lock=True) != binding):
            raise ValueError(_STALE)
        revision_exists = cur.execute("""SELECT 1 FROM canonical_article_source_revisions
              WHERE canonical_article_id=%s AND source_fingerprint=%s AND projection_version=%s""",
              (binding.canonical_article_id, captured.source_fingerprint, captured.projection_version)).fetchone()
        if revision_exists:
            raise ValueError(_STALE)

        successor_id = uuid4()
        cur.execute(
            """UPDATE source_fetch_jobs SET status='needs_review',phase='completed',retryable=false,error_code=%s,
                       checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (RETAINED_NOTICE_SUPERSEDED, Jsonb({"notice_successor_job_id": str(successor_id)}), job_id),
        )
        key = transformation_key(
            binding.canonical_article_id, captured.source_fingerprint, prior["normalization_version"],
            prior["rewrite_profile_version"], projection_version=captured.projection_version,
        )
        checkpoint = {
            "new_article_rollout": prior["checkpoint"]["new_article_rollout"],
            "awaiting_model_configuration": True,
            "normalized_document": normalized,
            "normalized_hash": digest_json(normalized),
            RETAINED_NOTICE_REPROJECTION: audit,
        }
        cur.execute(
            """INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,
                       source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,
                       job_kind,canonical_article_id,request_generation,phase,normalization_version,
                       rewrite_profile_version,max_attempts,retry_count,lease_token,error_code,retryable,checkpoint)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'failed','article',%s,1,'rewriting',%s,%s,
                       1,1,1,'MODEL_NOT_CONFIGURED',true,%s)""",
            (successor_id, prior["provider_slug"], prior["canonical_vehicle_id"], prior["source_vehicle_ref"],
             prior["source_article_ref"], prior["source_version"], prior["connector_name"],
             f"retained-notice:{job_id}", binding.canonical_article_id, prior["normalization_version"],
             prior["rewrite_profile_version"], Jsonb(checkpoint)),
        )
        revision = _persist_article_capture(cur, binding.canonical_article_id, successor_id, 1, captured,
                                            verify_existing=True)
        cur.execute("UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s WHERE source_fetch_job_id=%s",
                    (revision, key, successor_id))
        cur.execute("""UPDATE canonical_articles SET current_job_id=%s,current_source_revision_id=%s,
                           request_generation=1,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
                    (successor_id, revision, binding.canonical_article_id))
        successor = _parked_rollout_candidates(cur, args, job_id=successor_id)
        if not successor or not _parked_rollout_source_allowed(cur, successor[0]):
            raise ValueError(_STALE)
        return {"status": "applied", "job_id": str(successor_id), "source_revision_id": str(revision)}
