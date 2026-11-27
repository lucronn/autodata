"""Replay two exact archived drafts for a failed, positioned Bank One refresh."""

from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_document import project_ordered_document
from .article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, digest_json
from .procedure_normalize import normalize_procedure_article
from .procedure_rewrite_auto import (
    _auto_prompt_version, _include_cell_blocks, check_automatic_introduction, failed_rewrite_passages,
    render_auto, require_current_publication_checks, validate_auto,
)
from .procedure_rewrite_full import prose_slots
from .source_job_persistence import (
    REQUIRE_POSITIONED_SVG_REFRESH, STAGED_MEDIA_REFRESH, _lease_from_row, transform_source_matches,
)


METHOD = "staged-media-archived-reply-recovery-v1"
CHECKPOINT = "staged_media_reply_recovery"
_ORIGINAL_ERROR = "REWRITE_TECHNICAL_MUTATION"
_INVALID = "STAGED_MEDIA_REPLY_RECOVERY_INVALID"
_STALE = "STAGED_MEDIA_REPLY_RECOVERY_STALE"


def _combine(old_source, old_reply, old_version, fresh_source, failed_reply, fresh_version):
    old_slots = prose_slots(old_source, include_cell_blocks=_include_cell_blocks(old_version))
    fresh_slots = prose_slots(fresh_source, include_cell_blocks=_include_cell_blocks(fresh_version))
    old_rows = old_reply["replacements"]
    heading = fresh_source["blocks"][0]
    restored_heading = (
        len(old_slots) == len(fresh_slots) + 1 and heading["type"] == "heading"
        and old_source["blocks"][0]["type"] == "paragraph" and old_slots[0]["path"] == "/blocks/0/text"
        and old_slots[0]["text"] == heading["text"]
    )
    if restored_heading:
        old_slots, old_rows = old_slots[1:], old_rows[1:]
    if not fresh_slots or [slot["text"] for slot in old_slots] != [slot["text"] for slot in fresh_slots]:
        raise ValueError("STAGED_MEDIA_REPLY_RECOVERY_SLOT_DRIFT")
    if (set(failed_reply) != {"introduction", "replacements"}
        or not isinstance(failed_reply["replacements"], list)
        or len(failed_reply["replacements"]) != len(fresh_slots)):
        raise ValueError(_INVALID)
    fresh_rows = failed_reply["replacements"]
    for row, slot in zip(fresh_rows, fresh_slots, strict=True):
        if not isinstance(row, dict) or row.get("path") != slot["path"] or row.get("block_id") != slot["block_id"]:
            raise ValueError(_INVALID)
    failed_paths = {item["path"] for item in failed_rewrite_passages(fresh_source, failed_reply)}
    carried = []
    replacements = []
    for previous, old_slot, fresh, new_slot in zip(old_rows, old_slots, fresh_rows, fresh_slots, strict=True):
        if new_slot["path"] in failed_paths:
            replacements.append({**previous, "block_id": new_slot["block_id"], "path": new_slot["path"]})
            carried.append({"prior_path": old_slot["path"], "replacement_path": new_slot["path"]})
        else:
            replacements.append(fresh)
    introduction = failed_reply["introduction"]
    try:
        check_automatic_introduction(fresh_source, introduction)
    except ValueError:
        introduction = old_reply["introduction"]
        check_automatic_introduction(fresh_source, introduction)
        carried_introduction = True
    else:
        carried_introduction = False
    if not carried and not carried_introduction:
        raise ValueError(_INVALID)
    combined = {"introduction": introduction, "replacements": replacements}
    document = render_auto(fresh_source, combined, prompt_version=fresh_version)
    validation = validate_auto(fresh_source, document, response=combined, prompt_version=fresh_version)
    if not validation.passed:
        raise ValueError(_INVALID)
    require_current_publication_checks(fresh_source, document, saved_prompt_version=fresh_version)
    return document, validation, {
        "restored_source_heading": restored_heading,
        "carried_introduction": carried_introduction,
        "carried_slots": carried,
        "archived_fresh_slots": len(fresh_slots) - len(carried),
        "effective_reply_hash": digest_json(combined),
        "canonical_document_hash": digest_json(document),
    }


def _attempt_binding(attempt):
    return {
        "job_id": str(attempt["source_fetch_job_id"]), "attempt_id": str(attempt["rewrite_attempt_id"]),
        "input_hash": attempt["input_hash"], "prompt_hash": attempt["prompt_hash"],
        "response_hash": attempt["response_hash"], "status": attempt["status"],
        "error_code": attempt["error_code"],
    }


def _rebuild(cur, job, article, candidate, *, prior_source, prior_canonical, lock):
    from .published_media_publication import _publication_evidence_for_revision
    from .source_table_replay import load_table_replay_binding

    if (not prior_source or not prior_canonical or job["source_revision_id"] == prior_source
        or article["provider_slug"] != job["provider_slug"] or job["provider_slug"] != "bankone"
        or job["checkpoint"].get(STAGED_MEDIA_REFRESH) != {
            "version": 1, "source_revision_id": str(job["source_revision_id"]),
            "prior_source_revision_id": str(prior_source), "prior_canonical_revision_id": str(prior_canonical),
        }
        or job["checkpoint"].get(REQUIRE_POSITIONED_SVG_REFRESH) != {
            "source_revision_id": str(prior_source), "canonical_revision_id": str(prior_canonical),
        }
        or job["job_kind"] != "article"
        or job["rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or article["target_rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or job["normalization_version"] != article["target_normalization_version"]
        or job["canonical_article_id"] != article["canonical_article_id"]
        or article["current_job_id"] != job["source_fetch_job_id"]
        or article["request_generation"] != job["request_generation"]
        or candidate is None
        or job["checkpoint"].get("candidate_revision_id") != str(candidate["canonical_article_revision_id"])
        or candidate["transformation_key"] != job["transformation_key"]
        or candidate["source_revision_id"] != job["source_revision_id"]
        or candidate["canonical_article_id"] != job["canonical_article_id"]
        or candidate["normalization_version"] != job["normalization_version"]
        or candidate["rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or candidate["review_status"] != "UNREVIEWED"
        or cur.execute("SELECT 1 FROM canonical_article_reviews WHERE canonical_article_revision_id=%s",
                       (candidate["canonical_article_revision_id"],)).fetchone()):
        raise ValueError(_STALE)
    prior_binding = load_table_replay_binding(cur, prior_source)
    prior, review, _, old, old_reply, old_version, _ = _publication_evidence_for_revision(
        cur, article, prior_binding, prior_canonical, fixture_mode=False, lock=lock,
    )
    if old is None or not isinstance(old_reply, dict):
        raise ValueError(_INVALID)
    if lock and cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s FOR SHARE",
                            (old["rewrite_attempt_id"],)).fetchone() != old:
        raise ValueError(_STALE)
    fresh = cur.execute("""SELECT source.*,obs.source_observation_id,obs.captured_context
        FROM canonical_article_source_revisions source
        JOIN canonical_article_source_observations obs USING(source_revision_id,canonical_article_id)
        WHERE source.source_revision_id=%s AND source.canonical_article_id=%s
        AND obs.source_fetch_job_id=%s AND obs.request_generation=%s""",
        (job["source_revision_id"], job["canonical_article_id"], job["source_fetch_job_id"], job["request_generation"]),
    ).fetchone()
    if (fresh is None or fresh["projection_status"] != "readable"
        or fresh["body_source_snapshot_id"] != prior_binding.row["body_source_snapshot_id"]):
        raise ValueError(_STALE)
    context = fresh["captured_context"]
    fresh_source = normalize_procedure_article(
        {"article_id": str(job["canonical_article_id"]), "title": context["descriptor"].get("title"),
         "normalized_document": fresh["source_document"], "blocks": fresh["source_document"]["blocks"],
         "images": fresh["source_images"], "body": fresh["source_body"], "steps": fresh["source_steps"],
         "evidence_ids": context["evidence_ids"]},
        resource_manifest=fresh["resource_manifest"],
    )["normalized_document"]
    source_hash = digest_json(fresh_source)
    if (candidate["normalized_source_document"] != fresh_source or candidate["normalized_source_hash"] != source_hash
        or job["checkpoint"].get("normalized_document") != fresh_source
        or job["checkpoint"].get("normalized_hash") != source_hash):
        raise ValueError(_INVALID)
    attempts = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
        WHERE source_fetch_job_id=%s ORDER BY attempt_number,lease_token""" + (" FOR SHARE" if lock else ""),
        (job["source_fetch_job_id"],)).fetchall()
    if len(attempts) != 1:
        raise ValueError(_INVALID)
    [failed] = attempts
    metadata = candidate["model_metadata"]
    if (failed["canonical_article_revision_id"] != candidate["canonical_article_revision_id"]
        or failed["status"] != "failed" or failed["error_code"] != _ORIGINAL_ERROR
        or failed["dispatched_at"] is None or failed["completed_at"] is None
        or failed["dispatched_at"] > failed["completed_at"]
        or failed["attempt_number"] != job["retry_count"]
        or failed["profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or failed["provider"] != "inception"
        or failed["input_hash"] != source_hash
        or not isinstance(failed["response"], dict)
        or failed["response_hash"] != digest_json(failed["response"])
        or any(failed[key] != metadata.get(key) for key in ("model", "provider", "profile_version", "prompt_hash"))):
        raise ValueError(_INVALID)
    fresh_version = _auto_prompt_version(
        fresh_source, context=context["vehicle"], prompt_hash=failed["prompt_hash"], profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    if fresh_version is None:
        raise ValueError(_INVALID)
    try:
        render_auto(fresh_source, failed["response"], prompt_version=fresh_version)
    except ValueError as exc:
        if str(exc) != failed["error_code"]:
            raise ValueError(_INVALID) from None
    else:
        raise ValueError(_INVALID)
    document, validation, carried = _combine(
        prior["normalized_source_document"], old_reply, old_version, fresh_source, failed["response"], fresh_version,
    )
    return document, validation, {
        "method": METHOD, "new_model_dispatches": 0, "request_generation": job["request_generation"],
        "prior_source_revision_id": str(prior_source), "prior_canonical_revision_id": str(prior_canonical),
        "prior_observation_id": str(prior_binding.source_observation_id),
        "prior_review_id": str(review["canonical_article_review_id"]) if review else None,
        "prior_effective_reply_hash": digest_json(old_reply), "prior_attempt": _attempt_binding(old),
        "prior_prompt_version": old_version,
        "staged_source_revision_id": str(job["source_revision_id"]),
        "staged_observation_id": str(fresh["source_observation_id"]), "staged_attempt": _attempt_binding(failed),
        "staged_attempt_lease_token": failed["lease_token"], "staged_prompt_version": fresh_version,
        "body_source_snapshot_id": str(fresh["body_source_snapshot_id"]), **carried,
    }


def _valid_audit(actor, reason):
    return all(isinstance(value, str) and value.strip() and len(value) <= limit
               and not any(ord(character) < 32 or ord(character) == 127 for character in value)
               for value, limit in ((actor, 256), (reason, 2048)))


def _verify_replay(cur, job, article, candidate, *, prior_source, prior_canonical, lock):
    audit = job["checkpoint"].get(CHECKPOINT)
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or candidate["model_metadata"].get("transformation_method") != METHOD
        or not _valid_audit(audit["actor"], audit["reason"])):
        raise ValueError(_INVALID)
    document, validation, evidence = _rebuild(
        cur, job, article, candidate, prior_source=prior_source, prior_canonical=prior_canonical, lock=lock,
    )
    if (evidence != audit["evidence"] or evidence != candidate["model_metadata"].get(CHECKPOINT)
        or job["lease_token"] != evidence["staged_attempt_lease_token"] + 1
        or candidate["canonical_document"] != document):
        raise ValueError(_INVALID)
    return validation, evidence


def verify_staged_media_reply_recovery(cur, job, article, candidate):
    """Independently rebuild the operator's update inside normal publication."""
    validation, _ = _verify_replay(
        cur, job, article, candidate, prior_source=article["current_source_revision_id"],
        prior_canonical=article["current_canonical_revision_id"], lock=True,
    )
    return validation


def resolve_published_staged_media_evidence(cur, job, article, candidate, *, lock):
    """Authenticate a committed staged recovery before a geometry-only repair."""
    refresh = job["checkpoint"].get(STAGED_MEDIA_REFRESH)
    if (not isinstance(refresh, dict) or job["status"] != "completed" or candidate["status"] != "published"
            or article["current_canonical_revision_id"] != candidate["canonical_article_revision_id"]
            or article["current_source_revision_id"] != candidate["source_revision_id"]):
        raise ValueError(_STALE)
    validation, evidence = _verify_replay(
        cur, job, article, candidate, prior_source=UUID(refresh["prior_source_revision_id"]),
        prior_canonical=UUID(refresh["prior_canonical_revision_id"]), lock=lock,
    )
    attempts = [cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s",
                            (evidence[key]["attempt_id"],)).fetchone()
                for key in ("prior_attempt", "staged_attempt")]
    if any(attempt is None for attempt in attempts):
        raise ValueError(_INVALID)
    authors = {attempt[key] for attempt in attempts for key in ("model", "provider")}
    authors.add(job["checkpoint"][CHECKPOINT]["actor"])
    return validation, attempts[-1], evidence["staged_prompt_version"], authors


def recover_staged_media_reply(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_published_revision_id, actor, reason,
    hooks=None,
):
    """Adopt the exact failed owner's placeholder and publish without external calls."""
    from .article_lifecycle_store import _publish_article_revision, _require_staged_media_refresh_rights

    if not _valid_audit(actor, reason):
        raise ValueError(_INVALID)
    article_id, expected_job_id, expected_source_revision_id, expected_published_revision_id = (
        UUID(str(value)) for value in (article_id, expected_job_id, expected_source_revision_id, expected_published_revision_id)
    )
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                          (expected_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (article_id,)).fetchone()
        if (job is None or article is None or job["canonical_article_id"] != article_id
            or job["source_revision_id"] != expected_source_revision_id
            or article["current_canonical_revision_id"] != expected_published_revision_id
            or job["status"] != "dead_letter" or job["phase"] != "validating"
            or job["retryable"] or job["lease_owner"] is not None or job["lease_expires_at"] is not None
            or job["error_code"] != _ORIGINAL_ERROR or job["checkpoint"].get("rewrite_error_code") != _ORIGINAL_ERROR
            or STAGED_MEDIA_REFRESH not in job["checkpoint"] or not transform_source_matches(article, job)
            or CHECKPOINT in job["checkpoint"]
            or not job["transformation_key"]):
            raise ValueError(_STALE)
        _require_staged_media_refresh_rights(cur, job, article)
        candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE",
                                (job["transformation_key"],)).fetchone()
        if (candidate is None or candidate["status"] != "building" or candidate["published_at"] is not None
            or candidate["validation_report"] != {} or candidate["validation_hash"] != digest_json({})
            or candidate["canonical_document"] != candidate["normalized_source_document"]
            or candidate["rewrite_result_hash"] != candidate["normalized_source_hash"]
            or project_ordered_document(candidate["canonical_document"]) != {
                "body": candidate["canonical_body"], "steps": candidate["canonical_steps"], "images": candidate["canonical_images"],
            }):
            raise ValueError(_STALE)
        document, validation, evidence = _rebuild(
            cur, job, article, candidate, prior_source=article["current_source_revision_id"],
            prior_canonical=article["current_canonical_revision_id"], lock=True,
        )
        if evidence["staged_attempt_lease_token"] != job["lease_token"]:
            raise ValueError(_STALE)
        revision_id = candidate["canonical_article_revision_id"]
        projection = project_ordered_document(document)
        validation_hash = digest_json(validation.report)
        metadata = {**candidate["model_metadata"], "transformation_method": METHOD, CHECKPOINT: evidence}
        cur.execute("""UPDATE canonical_article_revisions SET status='validated',canonical_document=%s,
            canonical_body=%s,canonical_steps=%s,canonical_images=%s,rewrite_result_hash=%s,validation_report=%s,
            validation_hash=%s,model_metadata=%s WHERE canonical_article_revision_id=%s""",
            (Jsonb(document), projection["body"], Jsonb(projection["steps"]), Jsonb(projection["images"]),
             digest_json(document), Jsonb(validation.report), validation_hash, Jsonb(metadata), revision_id))
        worker_id = uuid4()
        job = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='publishing',error_code=NULL,
            lease_owner=%s,lease_token=lease_token+1,lease_expires_at=clock_timestamp()+interval '90 seconds',
            heartbeat_at=clock_timestamp(),updated_at=clock_timestamp(),
            checkpoint=(checkpoint-'rewrite_error_code')||%s WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, Jsonb({"validation_hash": validation_hash, CHECKPOINT: {
                "actor": actor, "reason": reason, "evidence": evidence,
            }}), expected_job_id)).fetchone()
        return _publish_article_revision(cur, _lease_from_row(job, worker_id), revision_id, hooks=hooks)


def audit_published_staged_media_reply(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_prior_source_revision_id,
    expected_prior_canonical_revision_id,
):
    """Rebuild one committed exact repair in a read-only snapshot and report counts."""
    from .source_job_persistence import source_bound_rewrite_source_allowed

    article_id, job_id, source_id, prior_source_id, prior_canonical_id = (
        UUID(str(value)) for value in (
            article_id, expected_job_id, expected_source_revision_id, expected_prior_source_revision_id,
            expected_prior_canonical_revision_id,
        )
    )
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()
        article = cur.execute("""SELECT a.* FROM canonical_articles a
            JOIN catalog_article_current visible USING(canonical_article_id)
            WHERE a.canonical_article_id=%s AND a.current_job_id=%s AND a.current_source_revision_id=%s
            AND visible.content_origin='canonical' AND visible.takedown_status='active'
            AND visible.source_revision_id=a.current_source_revision_id
            AND visible.canonical_revision_id=a.current_canonical_revision_id""",
            (article_id, job_id, source_id)).fetchone()
        if (job is None or article is None or job["source_revision_id"] != source_id
            or job["status"] != "completed" or job["phase"] != "completed" or job["error_code"] is not None
            or job["lease_owner"] is not None or job["lease_expires_at"] is not None
            or not source_bound_rewrite_source_allowed(cur, article, source_id)):
            raise ValueError(_STALE)
        revision_id = article["current_canonical_revision_id"]
        candidate = cur.execute("""SELECT * FROM canonical_article_revisions
            WHERE canonical_article_revision_id=%s AND status='published'""", (revision_id,)).fetchone()
        if candidate is None:
            raise ValueError(_STALE)
        validation, evidence = _verify_replay(
            cur, job, article, candidate, prior_source=prior_source_id, prior_canonical=prior_canonical_id, lock=False,
        )
        if (candidate["rewrite_result_hash"] != evidence["canonical_document_hash"]
            or candidate["validation_report"] != validation.report
            or candidate["validation_hash"] != digest_json(validation.report)
            or job["checkpoint"].get("validation_hash") != candidate["validation_hash"]
            or project_ordered_document(candidate["canonical_document"]) != {
                "body": candidate["canonical_body"], "steps": candidate["canonical_steps"], "images": candidate["canonical_images"],
            }):
            raise ValueError(_INVALID)
        events = cur.execute("""SELECT idempotency_key,payload FROM publication_events
            WHERE event_type='catalog.article.published' AND canonical_article_id=%s AND canonical_article_revision_id=%s""",
            (article_id, revision_id)).fetchall()
        if events != [{
            "idempotency_key": "catalog.article.published:" + job["transformation_key"],
            "payload": {"source_revision_id": str(source_id), "review_status": "UNREVIEWED"},
        }]:
            raise ValueError(_INVALID)
        return {
            "status": "verified", "archived_attempts": 2, "publication_events": len(events),
            "archived_fresh_slots": evidence["archived_fresh_slots"], "new_model_dispatches": 0,
            "carried_slots": len(evidence["carried_slots"]),
            "carried_introductions": int(evidence["carried_introduction"]),
            "figures": len(candidate["canonical_images"]),
        }
