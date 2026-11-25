"""Publish the authored order of retained Bankone HTML with its saved rewrite."""

from uuid import UUID

from psycopg.rows import dict_row

from .article_lifecycle_types import CapturedSource, SOURCE_BOUND_CORRECTION_PROFILE, digest_json, transformation_key
from .procedure_rewrite_sentence_correction import SENTENCE_RECOVERY_METHOD
from .published_media_publication import _normalize, _publication_evidence_for_revision, _publish, _RepairPlan, _result
from .retained_bankone_order_reply import BANKONE_ORDER_METHOD, repair_bankone_order
from .retained_procedure_repair import _HASH, _valid_audit
from .source_bankone_order_replay import (
    load_bankone_order_binding, preview_bankone_order_replay, validate_bankone_order_capture,
)
from .source_media_replay import _context, _source_replay_row
from .source_revision_reprojection import _require_no_active_normal_job


SCHEMA = "autodata:published-bankone-html-order:v1"
_INVALID = "BANKONE_ORDER_PUBLICATION_INVALID"
_STALE = "BANKONE_ORDER_PUBLICATION_STALE"


def _article(cur, article_id, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s" + suffix, (article_id,)).fetchone()


def _plan(cur, article, binding, captured, previous_revision_id, *, lock=False):
    validate_bankone_order_capture(binding, captured)
    previous = cur.execute("""
        SELECT model_metadata, transformation_key FROM canonical_article_revisions
        WHERE canonical_article_revision_id=%s AND canonical_article_id=%s AND source_revision_id=%s
    """, (previous_revision_id, binding.canonical_article_id, binding.source_revision_id)).fetchone()
    if (previous is None
            or previous["model_metadata"].get("transformation_method") != SENTENCE_RECOVERY_METHOD):
        raise ValueError(_INVALID)
    revision, review, decision, attempt, reply, prompt_version, authors = _publication_evidence_for_revision(
        cur, article, binding, previous_revision_id, fixture_mode=False, lock=lock,
        expected_profile=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    if review is not None or decision != "UNREVIEWED" or attempt is None:
        raise ValueError(_INVALID)
    owner = cur.execute("""
        SELECT source_fetch_job_id, request_generation FROM source_fetch_jobs
        WHERE transformation_key=%s AND status='completed'
    """, (previous["transformation_key"],)).fetchone()
    if owner is None:
        raise ValueError(_INVALID)

    normalized = _normalize(captured, binding.canonical_article_id)
    repair = repair_bankone_order(
        revision["normalized_source_document"], revision["canonical_document"], normalized,
        response=reply, prompt_version=prompt_version, profile=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    manifest = {
        "schema": SCHEMA,
        "article_id": str(binding.canonical_article_id),
        "source_revision_id": str(binding.source_revision_id),
        "source_observation_id": str(binding.source_observation_id),
        "canonical_revision_id": str(previous_revision_id),
        "current_job_id": str(owner["source_fetch_job_id"]),
        "request_generation": owner["request_generation"],
        "descriptor_snapshot_id": str(binding.context.descriptor_snapshot_id),
        "body_sha256": binding.body_sha256,
        "source_fingerprint": binding.source_fingerprint,
        "repaired_source_fingerprint": captured.source_fingerprint,
        "repaired_source_document_hash": digest_json(captured.source_document),
        "repaired_provenance_hash": digest_json(captured.resource_provenance),
        "repaired_projection_version": captured.projection_version,
        "normalization_version": revision["normalization_version"],
        "original_attempt_id": str(attempt["rewrite_attempt_id"]),
        "original_prompt_hash": attempt["prompt_hash"],
        "original_validation_hash": revision["validation_hash"],
        "repaired_validation_hash": digest_json(repair.validation.report),
        **repair.provenance,
    }
    return _RepairPlan(manifest, revision, normalized, repair, decision, authors), attempt


def _require_current(article, manifest):
    if (article is None or article["provider_slug"] != "bankone"
            or article["membership_status"] != "active" or article["takedown_status"] != "active"
            or str(article["current_source_revision_id"]) != manifest["source_revision_id"]
            or str(article["current_canonical_revision_id"]) != manifest["canonical_revision_id"]
            or str(article["current_job_id"]) != manifest["current_job_id"]
            or str(article["descriptor_source_snapshot_id"]) != manifest["descriptor_snapshot_id"]
            or article["request_generation"] != manifest["request_generation"]
            or article["target_normalization_version"] != manifest["normalization_version"]
            or article["target_rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE):
        raise ValueError(_STALE)


def preview_bankone_order_publication(repo, source_revision_id, *, object_store):
    """Return a digest-bound proposal with no stored-data changes."""
    binding, captured = preview_bankone_order_replay(repo, source_revision_id, object_store=object_store)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='8s'")
        article = _article(cur, binding.canonical_article_id)
        if article is None or article["current_source_revision_id"] != binding.source_revision_id:
            raise ValueError(_STALE)
        if binding != load_bankone_order_binding(cur, source_revision_id):
            raise ValueError(_STALE)
        plan, _ = _plan(cur, article, binding, captured, article["current_canonical_revision_id"])
        _require_current(article, plan.manifest)
        return plan.manifest


def _captured_revision(cur, source_id):
    row = _source_replay_row(cur, source_id)
    if row is None:
        raise ValueError(_INVALID)
    return CapturedSource(
        _context(row), row["source_fingerprint"], row["body_source_snapshot_id"],
        tuple(row["resource_provenance"]), row["resource_manifest"], row["resource_provenance"],
        row["source_document"], row["source_images"], row["source_body"], row["source_steps"],
        row["evidence_manifest"], row["projection_status"], row["captured_at"],
        projection_version=row["projection_version"],
    )


def _approval(job):
    approval = job["checkpoint"].get("media_repair")
    if (not isinstance(approval, dict) or set(approval) != {"manifest", "actor", "reason"}
            or not isinstance(approval["manifest"], dict) or approval["manifest"].get("schema") != SCHEMA
            or not _valid_audit(approval["actor"], approval["reason"])):
        raise ValueError(_INVALID)
    return approval


def resolve_bankone_order_publication(cur, job, article, candidate, *, lock=False):
    """Rebuild the repaired publication from its retained source and prior proof."""
    manifest = _approval(job)["manifest"]
    try:
        source_id = UUID(manifest["source_revision_id"])
        prior_id = UUID(manifest["canonical_revision_id"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError(_INVALID) from None
    if (candidate["canonical_article_id"] != article["canonical_article_id"]
            or source_id == candidate["source_revision_id"] or prior_id == candidate["canonical_article_revision_id"]
            or job["canonical_article_id"] != candidate["canonical_article_id"]
            or job["source_revision_id"] != candidate["source_revision_id"]
            or job["status"] != "completed" or job["source_version"] != BANKONE_ORDER_METHOD
            or job["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
            or candidate["status"] != "published" or candidate["review_status"] != "UNREVIEWED"
            or candidate["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE):
        raise ValueError(_INVALID)
    binding = load_bankone_order_binding(cur, source_id, lock=lock)
    if binding.canonical_article_id != article["canonical_article_id"]:
        raise ValueError(_INVALID)
    captured = _captured_revision(cur, candidate["source_revision_id"])
    plan, attempt = _plan(cur, article, binding, captured, prior_id, lock=lock)
    key = transformation_key(
        article["canonical_article_id"], captured.source_fingerprint, plan.previous["normalization_version"],
        SOURCE_BOUND_CORRECTION_PROFILE, projection_version=captured.projection_version,
    )
    if (manifest != plan.manifest or job["request_generation"] != manifest["request_generation"] + 1
            or job["transformation_key"] != key or candidate["transformation_key"] != key
            or job["normalization_version"] != manifest["normalization_version"]
            or candidate["normalization_version"] != manifest["normalization_version"]
            or candidate["normalized_source_document"] != plan.normalized
            or candidate["normalized_source_hash"] != digest_json(plan.normalized)
            or candidate["canonical_document"] != plan.repair.document
            or candidate["rewrite_result_hash"] != digest_json(plan.repair.document)
            or candidate["validation_report"] != plan.repair.validation.report
            or candidate["validation_hash"] != digest_json(plan.repair.validation.report)
            or plan.repair.projection != {"body": candidate["canonical_body"], "steps": candidate["canonical_steps"],
                                          "images": candidate["canonical_images"]}
            or candidate["model_metadata"] != {
                **plan.repair.provenance,
                "model": plan.previous["model_metadata"]["model"],
                "original_attempt_id": manifest["original_attempt_id"],
                "original_prompt_hash": manifest["original_prompt_hash"],
                "original_canonical_revision_id": manifest["canonical_revision_id"],
            }):
        raise ValueError(_INVALID)
    return plan.repair, attempt, plan.repair.provenance["original_prompt_version"]


def _already_published(cur, article, approval):
    candidate = cur.execute("""
        SELECT r.* FROM canonical_article_revisions r
        JOIN catalog_article_current visible ON visible.canonical_revision_id=r.canonical_article_revision_id
        WHERE r.canonical_article_revision_id=%s AND r.canonical_article_id=%s
          AND r.source_revision_id=%s AND r.status='published' AND visible.availability='available'
          AND visible.takedown_status='active'
    """, (article["current_canonical_revision_id"], article["canonical_article_id"],
          article["current_source_revision_id"])).fetchone()
    if candidate is None or candidate["model_metadata"].get("transformation_method") != BANKONE_ORDER_METHOD:
        return None
    job = cur.execute("SELECT * FROM source_fetch_jobs WHERE transformation_key=%s AND status='completed'",
                      (candidate["transformation_key"],)).fetchone()
    if job is None or _approval(job) != approval:
        raise ValueError(_STALE)
    resolve_bankone_order_publication(cur, job, article, candidate)
    return _result({**candidate, "source_fetch_job_id": job["source_fetch_job_id"]}, "already_published")


def publish_bankone_order(repo, *, expected, object_store, actor, reason, hooks=None):
    """Publish the exact preview with its prior publication and snapshot rights locked."""
    if (not isinstance(expected, dict) or expected.get("schema") != SCHEMA
            or type(expected.get("request_generation")) is not int or not _valid_audit(actor, reason)
            or not all(isinstance(expected.get(field), str) and _HASH.fullmatch(expected[field])
                       for field in ("body_sha256", "repaired_source_document_hash", "repaired_published_document_hash"))):
        raise ValueError(_INVALID)
    try:
        article_id, source_id, prior_id = (UUID(expected[name]) for name in
                                          ("article_id", "source_revision_id", "canonical_revision_id"))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError(_INVALID) from None
    approval = {"manifest": expected, "actor": actor, "reason": reason}
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='8s'")
        article = _article(cur, article_id)
        if article is None:
            raise ValueError(_STALE)
        repeated = _already_published(cur, article, approval)
        if repeated is not None:
            return repeated
        _require_current(article, expected)
    binding, captured = preview_bankone_order_replay(repo, source_id, object_store=object_store)

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        article = _article(cur, article_id, lock=True)
        if article is None:
            raise ValueError(_STALE)
        repeated = _already_published(cur, article, approval)
        if repeated is not None:
            return repeated
        _require_current(article, expected)
        _require_no_active_normal_job(cur, article_id)
        locked = load_bankone_order_binding(cur, source_id, lock=True)
        if binding != locked or locked.canonical_article_id != article_id:
            raise ValueError(_STALE)
        plan, _ = _plan(cur, article, locked, captured, prior_id, lock=True)
        if plan.manifest != expected:
            raise ValueError(_STALE)
        key = transformation_key(
            article_id, captured.source_fingerprint, plan.previous["normalization_version"],
            SOURCE_BOUND_CORRECTION_PROFILE, projection_version=captured.projection_version,
        )
        result = _publish(cur, article, captured, key, plan, approval, hooks=hooks)
        candidate = cur.execute("""
            SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s
        """, (UUID(result["canonical_revision_id"]),)).fetchone()
        job = cur.execute("SELECT * FROM source_fetch_jobs WHERE transformation_key=%s", (key,)).fetchone()
        current = _article(cur, article_id)
        if (candidate is None or job is None or current["current_canonical_revision_id"] != candidate["canonical_article_revision_id"]
                or current["current_source_revision_id"] != candidate["source_revision_id"]):
            raise ValueError(_INVALID)
        resolve_bankone_order_publication(cur, job, current, candidate)
        return result
