"""Repair a narrowly classified historical procedure from its exact archived reply."""

from copy import deepcopy
from dataclasses import dataclass
import json
import re
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_document import project_ordered_document
from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, ValidationResult, digest_json, transformation_key,
)
from .procedure_rewrite_auto import (
    _CLOSE_TO, _INLINE_WARNING, _include_cell_blocks, _require_changes, build_auto_prompt,
    render_auto, require_current_publication_checks, validate_auto,
)
from .procedure_rewrite_full import prose_slots
from .source_job_persistence import _lease_from_row, source_bound_rewrite_source_allowed
from .source_revision_reprojection import _require_no_active_normal_job
from .source_table_replay import load_table_replay_binding


METHOD = "retained-procedure-archived-reply-repair-v1"
CHECKPOINT = "retained_procedure_repair"
_INVALID = "RETAINED_PROCEDURE_REPAIR_INVALID"
_STALE = "RETAINED_PROCEDURE_REPAIR_STALE"
_SPEC_ERROR = "REWRITE_SPEC_SCOPE_MUTATION"
_DIRECTION_ERROR = "REWRITE_DIRECTION_MUTATION"
_WARNING_ERROR = "REWRITE_SAFETY_MUTATION"
_NEAR = re.compile(r"\bnear(?:[ \t]+to)?\b", re.IGNORECASE)
_HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RecoveredProcedure:
    response: dict
    document: dict
    validation: ValidationResult
    evidence: dict
    attempt: dict
    prompt_version: str


def _restore_proximity(original, draft):
    near = list(_NEAR.finditer(original))
    close = list(_CLOSE_TO.finditer(draft))
    if len(near) != 1 or len(close) != 1:
        raise ValueError(_INVALID)
    for text, relation in ((original, near[0]), (draft, close[0])):
        target = text[relation.end():].strip()
        if not target or any(mark in target.rstrip(".") for mark in ".,;:!?\n"):
            raise ValueError(_INVALID)
    return draft[:close[0].start()] + original[near[0].start():]


def _correct_reply(source, prior_document, original, prompt_version):
    try:
        _require_changes(source, prior_document, prompt_version=prompt_version, introduction_only=True)
    except ValueError as error:
        if str(error) != _SPEC_ERROR:
            raise ValueError(_INVALID) from None
    else:
        raise ValueError(_INVALID)

    failures = {}
    include_cells = _include_cell_blocks(prompt_version)
    _require_changes(source, prior_document, prompt_version=prompt_version,
                     include_cell_blocks=include_cells, slot_errors=failures)
    paths = {code: path for path, code in failures.items()}
    if len(failures) != 2 or set(paths) != {_DIRECTION_ERROR, _WARNING_ERROR}:
        raise ValueError(_INVALID)
    slots = {slot["path"]: slot["text"] for slot in prose_slots(
        source, include_cell_blocks=include_cells,
    )}
    direction_path, warning_path = paths[_DIRECTION_ERROR], paths[_WARNING_ERROR]
    if warning_path not in slots or direction_path not in slots or not _INLINE_WARNING.search(slots[warning_path]):
        raise ValueError(_INVALID)
    reply = deepcopy(original)
    reply["introduction"] = "This article describes service information."
    for replacement in reply["replacements"]:
        path = replacement["path"]
        if path == direction_path:
            replacement["text"] = _restore_proximity(slots[path], replacement["text"])
        elif path == warning_path:
            replacement.update(action="retain", text=slots[path], reason="Exact safety wording retained.")

    document = render_auto(source, reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_REWRITE_PROFILE)
    validation = validate_auto(
        source, document, response=reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_REWRITE_PROFILE,
    )
    if not validation.passed:
        raise ValueError(_INVALID)
    return reply, document, validation, [{"path": path, "code": code} for path, code in sorted(failures.items())]


def _valid_audit(actor, reason):
    return all(isinstance(value, str) and value.strip() and len(value) <= limit
               and not any(ord(character) < 32 or ord(character) == 127 for character in value)
               for value, limit in ((actor, 256), (reason, 2048)))


def _rebuild(cur, article, binding, prior_revision_id, *, old_hash, prompt_version=None, lock=False):
    from .published_media_publication import _publication_evidence_for_revision

    if (binding.canonical_article_id != article["canonical_article_id"]
        or article["provider_slug"] != "bankone" or len(binding.row["resource_manifest"]) != 1
        or (lock and article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id)):
        raise ValueError(_STALE)
    prior, review, decision, attempt, original, old_version, _ = _publication_evidence_for_revision(
        cur, article, binding, prior_revision_id, fixture_mode=False, lock=lock,
        expected_profile=AUTOMATIC_REWRITE_PROFILE,
    )
    if (prior["rewrite_result_hash"] != old_hash or prior["model_metadata"].get("transformation_method") is not None
        or review is not None or decision != "UNREVIEWED" or attempt is None or attempt["provider"] != "inception"
        or attempt["dispatched_at"] is None or attempt["completed_at"] is None
        or attempt["dispatched_at"] > attempt["completed_at"]
        or attempt["error_code"] is not None or attempt["response"] != original):
        raise ValueError(_INVALID)
    attempts = cur.execute(
        """SELECT * FROM canonical_article_rewrite_attempts
        WHERE source_fetch_job_id=%s ORDER BY attempt_number,lease_token""" + (" FOR SHARE" if lock else ""),
        (attempt["source_fetch_job_id"],),
    ).fetchall()
    if attempts != [attempt]:
        raise ValueError(_INVALID)

    source = prior["normalized_source_document"]
    if prompt_version is None:
        prompt = json.loads(build_auto_prompt(source, context={}, profile_version=SOURCE_BOUND_REWRITE_PROFILE))
        prompt_version = prompt["prompt_version"]
    reply, document, validation, failures = _correct_reply(source, prior["canonical_document"], original, prompt_version)
    evidence = {
        "prior_job_id": str(attempt["source_fetch_job_id"]),
        "prior_canonical_revision_id": str(prior_revision_id),
        "prior_canonical_hash": old_hash,
        "source_revision_id": str(binding.source_revision_id),
        "source_observation_id": str(binding.source_observation_id),
        "source_fingerprint": binding.source_fingerprint,
        "archived_attempt_id": str(attempt["rewrite_attempt_id"]),
        "archived_prompt_version": old_version,
        "archived_input_hash": attempt["input_hash"],
        "archived_prompt_hash": attempt["prompt_hash"],
        "archived_response_hash": attempt["response_hash"],
        "guard_version": prompt_version,
        "changed_slots": failures,
        "repaired_response_hash": digest_json(reply),
        "repaired_document_hash": digest_json(document),
        "new_model_dispatches": 0,
    }
    return RecoveredProcedure(reply, document, validation, evidence, attempt, prompt_version)


def resolve_retained_procedure_repair(cur, job, article, candidate, *, publishing=False):
    """Replay the historical input and derived candidate without a new model attempt."""
    audit = job["checkpoint"].get(CHECKPOINT)
    metadata = candidate["model_metadata"]
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or audit != metadata.get(CHECKPOINT) or metadata.get("transformation_method") != METHOD
        or not _valid_audit(audit["actor"], audit["reason"]) or not isinstance(audit["evidence"], dict)
        or job["rewrite_profile_version"] != SOURCE_BOUND_REWRITE_PROFILE
        or candidate["rewrite_profile_version"] != SOURCE_BOUND_REWRITE_PROFILE
        or metadata.get("profile_version") != SOURCE_BOUND_REWRITE_PROFILE
        or candidate["transformation_key"] != job["transformation_key"]
        or candidate["source_revision_id"] != job["source_revision_id"]
        or candidate["canonical_article_id"] != job["canonical_article_id"]
        or candidate["normalization_version"] != job["normalization_version"]
        or job["retry_count"] != 0 or job["max_attempts"] != 1
        or cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s OR canonical_article_revision_id=%s LIMIT 1""",
            (job["source_fetch_job_id"], candidate["canonical_article_revision_id"])).fetchone()):
        raise ValueError(_INVALID)
    evidence = audit["evidence"]
    try:
        prior_id = UUID(evidence["prior_canonical_revision_id"])
        prior_job_id = UUID(evidence["prior_job_id"])
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INVALID) from None
    if publishing and (article["current_canonical_revision_id"] != prior_id
        or not source_bound_rewrite_source_allowed(cur, article, job["source_revision_id"])):
        raise ValueError(_STALE)
    binding = load_table_replay_binding(cur, job["source_revision_id"], lock=publishing)
    recovered = _rebuild(
        cur, article, binding, prior_id, old_hash=evidence.get("prior_canonical_hash"),
        prompt_version=evidence.get("guard_version"), lock=publishing,
    )
    prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                            (prior_job_id,)).fetchone()
    if (recovered.evidence != evidence or prior_job is None
        or job["request_generation"] != prior_job["request_generation"] + 1
        or metadata.get("model") != recovered.attempt["model"]
        or candidate["normalized_source_hash"] != evidence["archived_input_hash"]
        or candidate["rewrite_result_hash"] != evidence["repaired_document_hash"]
        or candidate["canonical_document"] != recovered.document):
        raise ValueError(_INVALID)
    if publishing:
        require_current_publication_checks(
            candidate["normalized_source_document"], recovered.document, saved_prompt_version=recovered.prompt_version,
        )
    return recovered


def repair_retained_procedure(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_published_revision_id,
    expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish one audited recovery in the normal atomic publication transaction."""
    from .article_lifecycle_store import _publish_article_revision

    if (not _valid_audit(actor, reason) or not all(
        isinstance(value, str) and _HASH.fullmatch(value) for value in (expected_published_hash, expected_repaired_hash)
    )):
        raise ValueError(_INVALID)
    article_id, prior_job_id, source_id, prior_id = map(UUID, map(str, (
        article_id, expected_job_id, expected_source_revision_id, expected_published_revision_id,
    )))
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                                (prior_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (article_id,)).fetchone()
        if (article is None or prior_job is None or article["current_job_id"] != prior_job_id
            or article["current_source_revision_id"] != source_id or article["current_canonical_revision_id"] != prior_id
            or article["target_rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
            or article["request_generation"] != prior_job["request_generation"]
            or prior_job["canonical_article_id"] != article_id or prior_job["source_revision_id"] != source_id
            or prior_job["job_kind"] != "article" or prior_job["status"] != "completed"
            or prior_job["phase"] != "completed" or prior_job["retryable"] or prior_job["lease_owner"] is not None
            or not source_bound_rewrite_source_allowed(cur, article, source_id)):
            raise ValueError(_STALE)
        _require_no_active_normal_job(cur, article_id)
        binding = load_table_replay_binding(cur, source_id, lock=True)
        repaired = _rebuild(cur, article, binding, prior_id, old_hash=expected_published_hash, lock=True)
        if (repaired.evidence["prior_job_id"] != str(prior_job_id)
            or repaired.evidence["repaired_document_hash"] != expected_repaired_hash):
            raise ValueError(_STALE)
        normalization = article["target_normalization_version"]
        key = transformation_key(article_id, binding.source_fingerprint, normalization, SOURCE_BOUND_REWRITE_PROFILE,
                                 projection_version=binding.row["projection_version"])
        source = prior_job["checkpoint"]["normalized_document"]
        require_current_publication_checks(source, repaired.document, saved_prompt_version=repaired.prompt_version)
        audit = {"actor": actor, "reason": reason, "evidence": repaired.evidence}
        job_id, revision_id, worker_id = uuid4(), uuid4(), uuid4()
        generation = article["request_generation"] + 1
        job = cur.execute("""INSERT INTO source_fetch_jobs(
            source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,
            source_version,connector_name,idempotency_key,status,phase,job_kind,canonical_article_id,
            request_generation,normalization_version,rewrite_profile_version,source_revision_id,transformation_key,
            max_attempts,lease_owner,lease_token,lease_expires_at,heartbeat_at,checkpoint)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'processing','publishing','article',%s,%s,%s,%s,%s,%s,
            1,%s,1,clock_timestamp()+interval '90 seconds',clock_timestamp(),%s) RETURNING *""",
            (job_id, article["provider_slug"], article["vehicle_id"], article["source_vehicle_ref"],
             article["source_article_ref"], METHOD, article["provider_slug"], f"article:{article_id}:{generation}",
             article_id, generation, normalization, SOURCE_BOUND_REWRITE_PROFILE, source_id, key, worker_id,
             Jsonb({CHECKPOINT: audit}))).fetchone()
        projection = project_ordered_document(repaired.document)
        cur.execute("""INSERT INTO canonical_article_revisions(
            canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,
            normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,
            canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,
            rewrite_result_hash,model_metadata)
            VALUES (%s,%s,%s,%s,%s,%s,'validated',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (revision_id, article_id, source_id, key, normalization, SOURCE_BOUND_REWRITE_PROFILE,
             Jsonb(source), repaired.evidence["archived_input_hash"], Jsonb(repaired.document), projection["body"],
             Jsonb(projection["steps"]), Jsonb(projection["images"]), Jsonb(repaired.validation.report),
             digest_json(repaired.validation.report), expected_repaired_hash,
             Jsonb({"transformation_method": METHOD, "model": repaired.attempt["model"],
                    "profile_version": SOURCE_BOUND_REWRITE_PROFILE, CHECKPOINT: audit})))
        cur.execute("""UPDATE canonical_articles SET current_job_id=%s,request_generation=%s,
            target_rewrite_profile_version=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
            (job_id, generation, SOURCE_BOUND_REWRITE_PROFILE, article_id))
        return _publish_article_revision(cur, _lease_from_row(job, worker_id), revision_id, hooks=hooks)
