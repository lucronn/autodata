"""Restore mandatory wording in a pinned Banktwo archived publication."""

from copy import deepcopy
import re
from types import SimpleNamespace
from uuid import UUID

from psycopg.rows import dict_row

from .article_lifecycle_types import (
    RETAINED_REQUIRED_ACTION_REPAIR_METHOD as METHOD,
    RETAINED_REQUIRED_ACTION_REPAIR_PROFILE as PROFILE,
    SOURCE_BOUND_CORRECTION_PROFILE, digest_json, transformation_key,
)
from .procedure_rewrite_auto import (
    _AUTHORED_QUOTATION, _INLINE_WARNING, _action_matches, _execution_order, render_auto,
    require_current_publication_checks, validate_auto,
)
from .procedure_rewrite_full import _get, _set, _technical_tokens
from .retained_note_label_repair import (
    CHECKPOINT as NOTE_CHECKPOINT, METHOD as NOTE_METHOD, PROFILE as NOTE_PROFILE,
    _HASH, _Plan, _publish_archived_reply_repair, _source_evidence,
)
from .retained_procedure_repair import _valid_audit
from .source_revision_reprojection import _require_no_active_normal_job


CHECKPOINT = "retained_required_action_repair"
_INVALID = "RETAINED_REQUIRED_ACTION_REPAIR_INVALID"
_STALE = "RETAINED_REQUIRED_ACTION_REPAIR_STALE"
_DIRECTIVE = re.compile(r"^\s*(?:install|tighten)\b", re.I)
_OPTIONAL = re.compile(r"\b(?:optionally|if desired|as desired|at your discretion)\b", re.I)
_ADVISORY = re.compile(r"\bshould(?=[ \t]+(?:be[ \t]+)?(?:install(?:ed)?|tighten(?:ed)?)\b)", re.I)


def _restore_required_actions(source, retained, old_document, old_reply, *, prompt_version):
    reply = deepcopy(old_reply)
    old_leaves = {"blocks": old_document["blocks"][1:]}
    changed = {}
    for row in reply["replacements"]:
        path = row["path"]
        original = _get(source, path)
        if row["action"] != "rewrite" or not _DIRECTIVE.match(original) or _OPTIONAL.search(original):
            continue
        wording = row["text"]
        matches = list(_ADVISORY.finditer(wording))
        if len(matches) != 1 or _AUTHORED_QUOTATION.search(wording):
            continue
        action = next(iter(_action_matches(original)), None)
        rewritten = next(iter(_action_matches(wording)), None)
        modal = matches[0]
        if (action is None or rewritten is None or action.lastgroup != rewritten.lastgroup
            or modal.start() >= rewritten.start()):
            continue
        if (wording != _get(old_leaves, path) or original != _get(retained, path)
            or _INLINE_WARNING.search(original)
            or _execution_order(original) != _execution_order(wording)
            or _technical_tokens(original) != _technical_tokens(wording)):
            raise ValueError(_INVALID)
        replacement = "Must" if modal[0][0].isupper() else "must"
        row["text"] = wording[:modal.start()] + replacement + wording[modal.end():]
        changed[path] = wording
    if not changed:
        raise ValueError(_INVALID)

    document = render_auto(source, reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE)
    validation = validate_auto(
        source, document, response=reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    reverted = deepcopy(document)
    leaves = {"blocks": reverted["blocks"][1:]}
    for path, wording in changed.items():
        _set(leaves, path, wording)
    if not validation.passed or reverted != old_document:
        raise ValueError(_INVALID)
    return document, validation, reply, sorted(changed)


def _rebuild(cur, article, prior_job, source_id, descriptor_id, prior_revision_id, old_hash, *, lock):
    from .published_media_publication import _publication_evidence_for_revision

    article_id = article["canonical_article_id"]
    if (prior_job is None or article["provider_slug"] != "banktwo" or prior_job["provider_slug"] != "banktwo"
        or prior_job["canonical_article_id"] != article_id or prior_job["source_revision_id"] != source_id
        or prior_job["job_kind"] != "article" or prior_job["rewrite_profile_version"] != NOTE_PROFILE
        or prior_job["source_version"] != NOTE_METHOD or prior_job["status"] != "completed"
        or prior_job["phase"] != "completed" or prior_job["retryable"]
        or prior_job["lease_owner"] is not None or prior_job["lease_expires_at"] is not None):
        raise ValueError(_STALE)
    bound_source = _source_evidence(cur, article, source_id, descriptor_id, lock=lock)
    prior, review, decision, attempt, reply, version, _ = _publication_evidence_for_revision(
        cur, article, SimpleNamespace(source_revision_id=source_id), prior_revision_id,
        fixture_mode=False, lock=lock, expected_profile=NOTE_PROFILE,
    )
    note_audit = prior["model_metadata"][NOTE_CHECKPOINT]
    if (prior["transformation_key"] != prior_job["transformation_key"] or prior["rewrite_result_hash"] != old_hash
        or note_audit["evidence"]["descriptor_snapshot_id"] != str(descriptor_id)):
        raise ValueError(_STALE)
    if review is not None or decision != "UNREVIEWED" or attempt is None:
        raise ValueError(_INVALID)

    source = prior["normalized_source_document"]
    document, validation, repaired_reply, paths = _restore_required_actions(
        source, bound_source["source_document"], prior["canonical_document"], reply, prompt_version=version,
    )
    if lock:
        require_current_publication_checks(source, document, saved_prompt_version=version)
    evidence = {
        "source_revision_id": str(source_id),
        "source_observation_id": str(bound_source["source_observation_id"]),
        "source_fingerprint": bound_source["source_fingerprint"],
        "source_resource_manifest_hash": digest_json(bound_source["resource_manifest"]),
        "descriptor_snapshot_id": str(descriptor_id),
        "prior_job_id": str(prior_job["source_fetch_job_id"]),
        "prior_revision_id": str(prior_revision_id),
        "prior_document_hash": old_hash,
        "prior_note_repair_audit_hash": digest_json(note_audit),
        "archived_attempt_id": str(attempt["rewrite_attempt_id"]),
        "archived_final_reply_hash": digest_json(reply),
        "guard_version": version,
        "restored_paths": paths,
        "repaired_reply_hash": digest_json(repaired_reply),
        "repaired_document_hash": digest_json(document),
    }
    key = transformation_key(
        article_id, bound_source["source_fingerprint"], prior["normalization_version"],
        PROFILE, projection_version=bound_source["projection_version"],
    )
    return _Plan(source, document, validation, evidence, key, attempt, repaired_reply)


def resolve_retained_required_action_repair(cur, job, article, candidate, *, publishing=False):
    """Reconstruct exactly the saved successor from the original archive."""
    audit = job["checkpoint"].get(CHECKPOINT)
    metadata = candidate["model_metadata"]
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or not _valid_audit(audit["actor"], audit["reason"]) or not isinstance(audit["evidence"], dict)
        or metadata.get(CHECKPOINT) != audit or metadata.get("transformation_method") != METHOD
        or metadata.get("profile_version") != PROFILE or job["rewrite_profile_version"] != PROFILE
        or candidate["rewrite_profile_version"] != PROFILE or job["provider_slug"] != "banktwo"
        or job["job_kind"] != "article" or job["source_version"] != METHOD
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
        prior_job_id, prior_revision_id, descriptor_id = (UUID(evidence[key]) for key in (
            "prior_job_id", "prior_revision_id", "descriptor_snapshot_id",
        ))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INVALID) from None
    if publishing and (
        article["current_canonical_revision_id"] != prior_revision_id
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["descriptor_source_snapshot_id"] != descriptor_id
    ):
        raise ValueError(_STALE)
    prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_job_id,)).fetchone()
    plan = _rebuild(cur, article, prior_job, job["source_revision_id"], descriptor_id, prior_revision_id,
                    evidence.get("prior_document_hash"), lock=publishing)
    if (plan.evidence != evidence or job["request_generation"] != prior_job["request_generation"] + 1
        or plan.key != job["transformation_key"] or plan.attempt["model"] != metadata.get("model")
        or candidate["normalized_source_document"] != plan.source or candidate["canonical_document"] != plan.document):
        raise ValueError(_INVALID)
    return plan


def repair_retained_required_actions(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish one pinned wording repair using only stored source and reply evidence."""
    if (not _valid_audit(actor, reason) or not all(
        isinstance(value, str) and _HASH.fullmatch(value) for value in (expected_published_hash, expected_repaired_hash)
    )):
        raise ValueError(_INVALID)
    article_id, prior_job_id, source_id, descriptor_id, prior_revision_id = map(UUID, map(str, (
        article_id, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
        expected_published_revision_id,
    )))
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                                (prior_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (article_id,)).fetchone()
        if (prior_job is None or article is None or article["current_job_id"] != prior_job_id
            or article["current_source_revision_id"] != source_id or article["current_canonical_revision_id"] != prior_revision_id
            or article["descriptor_source_snapshot_id"] != descriptor_id
            or article["request_generation"] != prior_job["request_generation"]
            or article["target_rewrite_profile_version"] != NOTE_PROFILE
            or article["target_normalization_version"] != prior_job["normalization_version"]):
            raise ValueError(_STALE)
        _require_no_active_normal_job(cur, article_id)
        plan = _rebuild(cur, article, prior_job, source_id, descriptor_id, prior_revision_id, expected_published_hash, lock=True)
        if plan.evidence["repaired_document_hash"] != expected_repaired_hash:
            raise ValueError(_STALE)
        return _publish_archived_reply_repair(
            cur, article, plan, profile=PROFILE, method=METHOD, checkpoint=CHECKPOINT,
            actor=actor, reason=reason, hooks=hooks,
        )
