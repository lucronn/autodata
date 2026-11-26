"""Publish an introduction-only repair of a validated archived draft."""

from copy import deepcopy
from uuid import UUID

from psycopg.rows import dict_row

from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, RETAINED_INTRODUCTION_REPAIR_PROFILE as PROFILE, digest_json, transformation_key,
)
from .procedure_rewrite_auto import (
    _auto_prompt_version, render_auto, require_current_publication_checks,
    require_distinct_generated_introduction, validate_auto,
)
from .procedure_rewrite_recovery import NEUTRAL_INTRODUCTION
from .retained_note_label_repair import _HASH, _Plan, _publish_archived_reply_repair, _source_evidence
from .retained_procedure_repair import _valid_audit
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_revision_reprojection import _require_no_active_normal_job


METHOD = "retained-introduction-archived-reply-repair-v1"
CHECKPOINT = "retained_introduction_repair"
COPIED_INTRODUCTION = "REWRITE_INTRODUCTION_COPIED"
_INVALID = "RETAINED_INTRODUCTION_REPAIR_INVALID"
_STALE = "RETAINED_INTRODUCTION_REPAIR_STALE"


def _replace_copied_introduction(source, prior, reply, changed, *, version):
    try:
        require_distinct_generated_introduction(source, prior, rewritten_paths=changed)
    except ValueError as error:
        if str(error) != COPIED_INTRODUCTION:
            raise
    else:
        raise ValueError(_INVALID)

    repaired = deepcopy(reply)
    repaired["introduction"] = NEUTRAL_INTRODUCTION
    document = render_auto(source, repaired, prompt_version=version, profile_version=AUTOMATIC_REWRITE_PROFILE)
    if {**document, "blocks": document["blocks"][1:]} != {**prior, "blocks": prior["blocks"][1:]}:
        raise ValueError(_INVALID)
    validation = validate_auto(source, document, response=repaired, prompt_version=version,
                               profile_version=AUTOMATIC_REWRITE_PROFILE)
    if not validation.passed or validation.report["changed_prose_slots"] != changed:
        raise ValueError(_INVALID)
    require_current_publication_checks(source, document, saved_prompt_version=version)
    require_distinct_generated_introduction(source, document, rewritten_paths=changed)
    return document, validation, repaired


def _rebuild(cur, article, prior, source_id, descriptor_id, draft_id, *, lock):
    from .article_lifecycle_store import automatic_candidate_validation
    from .published_media_publication import _saved_attempt

    article_id = article["canonical_article_id"]
    if (prior is None or prior["job_kind"] != "article" or prior["canonical_article_id"] != article_id
        or prior["provider_slug"] != article["provider_slug"] or prior["canonical_vehicle_id"] != article["vehicle_id"]
        or prior["source_vehicle_ref"] != article["source_vehicle_ref"]
        or prior["source_article_ref"] != article["source_article_ref"] or prior["source_revision_id"] != source_id
        or prior["rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE or prior["retryable"]
        or prior["lease_owner"] is not None or prior["lease_expires_at"] is not None
        or (prior["status"], prior["phase"], prior["error_code"]) != ("dead_letter", "publishing", COPIED_INTRODUCTION)
        or prior["checkpoint"].get("candidate_revision_id") != str(draft_id)):
        raise ValueError(_STALE)
    draft = cur.execute("""SELECT * FROM canonical_article_revisions
        WHERE canonical_article_revision_id=%s AND canonical_article_id=%s AND source_revision_id=%s AND status='validated'
        """ + (" FOR UPDATE" if lock else ""), (draft_id, article_id, source_id)).fetchone()
    bound = _source_evidence(cur, article, source_id, descriptor_id, lock=lock)
    observation = (bound["source_observation_id"], bound["source_fetch_job_id"], bound["request_generation"])
    if (observation[1:] != (prior["source_fetch_job_id"], prior["request_generation"])
        or bound["descriptor_source_snapshot_id"] != descriptor_id
        or lock and not source_bound_rewrite_source_allowed(
            cur, article, source_id, predecessor_observation=observation, require_current_observation_scope=True,
        )):
        raise ValueError(_STALE)

    previous = automatic_candidate_validation(cur, prior, draft)
    if (not previous.passed or draft["validation_report"] != previous.report
        or draft["validation_hash"] != digest_json(previous.report)
        or prior["checkpoint"].get("validation_hash") != draft["validation_hash"]
        or draft["rewrite_result_hash"] != digest_json(draft["canonical_document"])):
        raise ValueError(_INVALID)
    attempt = _saved_attempt(cur, draft_id, prior["source_fetch_job_id"])
    if attempt is None:
        raise ValueError(_INVALID)
    source = draft["normalized_source_document"]
    version = _auto_prompt_version(source, context=bound["captured_context"]["vehicle"],
                                   prompt_hash=attempt["prompt_hash"], profile_version=AUTOMATIC_REWRITE_PROFILE)
    if version is None:
        raise ValueError(_INVALID)
    document, validation, reply = _replace_copied_introduction(
        source, draft["canonical_document"], attempt["response"], previous.report["changed_prose_slots"], version=version,
    )
    evidence = {
        "prior_job_id": str(prior["source_fetch_job_id"]), "prior_revision_id": str(draft_id),
        "prior_document_hash": draft["rewrite_result_hash"], "prior_validation_hash": draft["validation_hash"],
        "source_observation_id": str(observation[0]), "descriptor_snapshot_id": str(descriptor_id),
        "archived_attempt_id": str(attempt["rewrite_attempt_id"]), "archived_reply_hash": attempt["response_hash"],
        "guard_version": version, "repaired_reply_hash": digest_json(reply),
        "repaired_document_hash": digest_json(document),
    }
    key = transformation_key(article_id, bound["source_fingerprint"], draft["normalization_version"], PROFILE,
                             projection_version=bound["projection_version"])
    return _Plan(source, document, validation, evidence, key, attempt, reply)


def resolve_retained_introduction_repair(cur, job, article, candidate, *, publishing=False):
    """Replay the exact archived repair for publication and later media maintenance."""
    audit = job["checkpoint"].get(CHECKPOINT)
    metadata = candidate["model_metadata"]
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or not _valid_audit(audit["actor"], audit["reason"]) or not isinstance(audit["evidence"], dict)
        or metadata.get(CHECKPOINT) != audit or metadata.get("transformation_method") != METHOD
        or metadata.get("profile_version") != PROFILE or job["rewrite_profile_version"] != PROFILE
        or candidate["rewrite_profile_version"] != PROFILE or job["job_kind"] != "article"
        or job["provider_slug"] != article["provider_slug"] or job["source_version"] != METHOD
        or job["retry_count"] != 0 or job["max_attempts"] != 1
        or any(candidate[field] != job[field] for field in (
            "canonical_article_id", "source_revision_id", "normalization_version", "transformation_key",
        ))
        or cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s OR canonical_article_revision_id=%s LIMIT 1""",
            (job["source_fetch_job_id"], candidate["canonical_article_revision_id"])).fetchone()):
        raise ValueError(_INVALID)
    evidence = audit["evidence"]
    try:
        prior_id, draft_id, descriptor_id = (UUID(evidence[key]) for key in (
            "prior_job_id", "prior_revision_id", "descriptor_snapshot_id",
        ))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INVALID) from None
    if publishing and (article["current_canonical_revision_id"] is not None
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["descriptor_source_snapshot_id"] != descriptor_id):
        raise ValueError(_STALE)
    prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,)).fetchone()
    plan = _rebuild(cur, article, prior, job["source_revision_id"], descriptor_id, draft_id, lock=publishing)
    if (plan.evidence != evidence or job["request_generation"] != prior["request_generation"] + 1
        or plan.key != job["transformation_key"] or plan.attempt["model"] != metadata.get("model")
        or candidate["normalized_source_document"] != plan.source or candidate["canonical_document"] != plan.document):
        raise ValueError(_INVALID)
    return plan


def repair_retained_introduction(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_draft_revision_id,
    expected_reply_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Atomically publish a checked correction without a new capture or model call."""
    if not _valid_audit(actor, reason) or not all(
        isinstance(value, str) and _HASH.fullmatch(value) for value in (expected_reply_hash, expected_repaired_hash)
    ):
        raise ValueError(_INVALID)
    article_id, prior_id, source_id, draft_id = map(UUID, map(str, (
        article_id, expected_job_id, expected_source_revision_id, expected_draft_revision_id,
    )))
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE", (prior_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (article_id,)).fetchone()
        if (prior is None or article is None or article["current_job_id"] != prior_id
            or article["vehicle_configuration_id"] is None or article["current_source_revision_id"] != source_id
            or article["current_canonical_revision_id"] is not None
            or article["request_generation"] != prior["request_generation"]
            or article["target_rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
            or article["target_normalization_version"] != prior["normalization_version"]):
            raise ValueError(_STALE)
        _require_no_active_normal_job(cur, article_id)
        plan = _rebuild(cur, article, prior, source_id, article["descriptor_source_snapshot_id"], draft_id, lock=True)
        if (plan.evidence["archived_reply_hash"] != expected_reply_hash
            or plan.evidence["repaired_document_hash"] != expected_repaired_hash):
            raise ValueError(_STALE)
        return _publish_archived_reply_repair(
            cur, article, plan, profile=PROFILE, method=METHOD, checkpoint=CHECKPOINT,
            actor=actor, reason=reason, hooks=hooks,
        )
