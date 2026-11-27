"""Repair wording in a completed article publication using its archived reply."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
import re
from types import SimpleNamespace
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_document import project_ordered_document
from .article_lifecycle_types import (
    RETAINED_AUTHORED_PROCEDURE_REPAIR_PROFILE as AUTHORED_PROCEDURE_PROFILE,
    RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE as CONDITIONAL_PROFILE,
    RETAINED_NOTE_LABEL_REPAIR_PROFILE as PROFILE,
    RETAINED_OPTIONAL_OBSERVATION_REPAIR_PROFILE as OPTIONAL_OBSERVATION_PROFILE,
    RETAINED_PROCEDURE_CONDITION_REPAIR_PROFILE as PROCEDURE_CONDITION_PROFILE,
    RETAINED_ROTATION_REMOVAL_REPAIR_PROFILE as ROTATION_REMOVAL_PROFILE,
    RETAINED_SHORT_ACTION_REPAIR_PROFILE as SHORT_ACTION_PROFILE,
    RETAINED_SPACED_ROTATION_REPAIR_PROFILE as SPACED_ROTATION_PROFILE,
    SOURCE_BOUND_CORRECTION_PROFILE, ValidationResult,
    digest_json, transformation_key,
)
from .authored_procedure_scope import correct_authored_procedure_step
from .procedure_rewrite_auto import (
    _OPTIONAL_OBSERVATION_PROMPT_VERSION, _PROCEDURE_FIDELITY_PROMPT_VERSION, _ROTATION_REMOVAL_PROMPT_VERSION,
    _SHORT_ACTION_PROMPT_VERSION, _SPACED_ROTATION_PROMPT_VERSION, _auto_prompt_payload_v62, _procedure_condition,
    authored_note_prefix, failed_rewrite_passages, recast_authored_rotation_removal, recast_optional_observation,
    recast_short_procedure, recast_spaced_rotation_removal, render_auto, require_current_publication_checks, validate_auto,
)
from .procedure_rewrite_correction import ARCHIVED_FIRST_DRAFT_METHOD
from .procedure_rewrite_fidelity import recast_conditional_color_note
from .procedure_rewrite_full import _get, _set
from .procedure_rewrite_recovery import RECOVERY_METHOD
from .procedure_rewrite_sentence_correction import (
    SENTENCE_CORRECTION_METHOD, SENTENCE_INSTRUCTION_RECOVERY_METHOD, SENTENCE_TOOL_RECOVERY_METHOD,
)
from .retained_bankone_order_reply import BANKONE_ORDER_METHOD
from .retained_banktwo_notice_reply import BANKTWO_NOTICE_METHOD
from .retained_procedure_repair import _valid_audit
from .source_job_persistence import _lease_from_row, source_bound_rewrite_source_allowed
from .source_media_replay import _check_review_quarantine, _load_snapshots, _source_replay_row
from .source_revision_reprojection import _require_no_active_normal_job


METHOD = "retained-note-label-archived-reply-repair-v1"
CHECKPOINT = "retained_note_label_repair"
_INVALID = "RETAINED_NOTE_LABEL_REPAIR_INVALID"
_STALE = "RETAINED_NOTE_LABEL_REPAIR_STALE"
_UNAVAILABLE = "RETAINED_NOTE_LABEL_REPAIR_SOURCE_UNAVAILABLE"
CONDITIONAL_METHOD = "retained-conditional-note-archived-reply-repair-v1"
CONDITIONAL_CHECKPOINT = "retained_conditional_note_repair"
_CONDITIONAL_INVALID = "RETAINED_CONDITIONAL_NOTE_REPAIR_INVALID"
ROTATION_REMOVAL_METHOD = "retained-rotation-removal-archived-reply-repair-v1"
ROTATION_REMOVAL_CHECKPOINT = "retained_rotation_removal_repair"
_ROTATION_REMOVAL_INVALID = "RETAINED_ROTATION_REMOVAL_REPAIR_INVALID"
SPACED_ROTATION_METHOD = "retained-spaced-rotation-archived-reply-repair-v1"
SPACED_ROTATION_CHECKPOINT = "retained_spaced_rotation_repair"
_SPACED_ROTATION_INVALID = "RETAINED_SPACED_ROTATION_REPAIR_INVALID"
OPTIONAL_OBSERVATION_METHOD = "retained-optional-observation-archived-reply-repair-v1"
OPTIONAL_OBSERVATION_CHECKPOINT = "retained_optional_observation_repair"
_OPTIONAL_OBSERVATION_INVALID = "RETAINED_OPTIONAL_OBSERVATION_REPAIR_INVALID"
AUTHORED_PROCEDURE_METHOD = "retained-authored-procedure-archived-reply-repair-v1"
AUTHORED_PROCEDURE_CHECKPOINT = "retained_authored_procedure_repair"
_AUTHORED_PROCEDURE_INVALID = "RETAINED_AUTHORED_PROCEDURE_REPAIR_INVALID"
PROCEDURE_CONDITION_METHOD = "retained-procedure-condition-archived-reply-repair-v1"
PROCEDURE_CONDITION_CHECKPOINT = "retained_procedure_condition_repair"
_PROCEDURE_CONDITION_INVALID = "RETAINED_PROCEDURE_CONDITION_REPAIR_INVALID"
SHORT_ACTION_METHOD = "retained-short-action-archived-reply-repair-v1"
SHORT_ACTION_CHECKPOINT = "retained_short_action_repair"
_SHORT_ACTION_INVALID = "RETAINED_SHORT_ACTION_REPAIR_INVALID"
_CONDITION_RETENTION_REASON = "Preserve the exact authored equipment or timing condition."
_HASH = re.compile(r"[a-f0-9]{64}")


@dataclass(frozen=True)
class _Plan:
    source: dict
    document: dict
    validation: ValidationResult
    evidence: dict
    key: str
    attempt: dict
    reply: dict


def _restore_reply(source, retained, old_document, old_reply, *, prompt_version):
    reply = deepcopy(old_reply)
    changed = {}
    for row in reply["replacements"]:
        path = row["path"]
        original = _get(source, path)
        prefix = authored_note_prefix(original)
        if row["action"] != "rewrite" or prefix is None or authored_note_prefix(row["text"]) is not None:
            continue
        if _get(retained, path) != original:
            raise ValueError(_INVALID)
        changed[path] = row["text"]
        row["text"] = prefix + row["text"]
    if not changed:
        raise ValueError(_INVALID)
    document = render_auto(source, reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE)
    validation = validate_auto(
        source, document, response=reply, prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    reverted = deepcopy(document)
    leaves = {"blocks": reverted["blocks"][1:]}
    for path, text in changed.items():
        _set(leaves, path, text)
    if not validation.passed or reverted != old_document:
        raise ValueError(_INVALID)
    return document, validation, reply, sorted(changed)


def _recast_reply(source, retained, old_document, old_reply, *, prompt_version, recast, invalid,
                  verified_color_notes=False):
    reply = deepcopy(old_reply)
    old_leaves = {"blocks": old_document["blocks"][1:]}
    changed = {}
    for row in reply["replacements"]:
        if row["action"] != "retain":
            continue
        path = row["path"]
        original = _get(source, path)
        wording = recast(original)
        if wording is None:
            continue
        if original != row["text"] or original != _get(retained, path) or original != _get(old_leaves, path):
            raise ValueError(invalid)
        row.update(action="rewrite", text=wording, reason="")
        changed[path] = original
    if not changed:
        raise ValueError(invalid)

    options = dict(
        prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
        verified_color_notes=verified_color_notes,
    )
    document = render_auto(source, reply, **options)
    validation = validate_auto(source, document, response=reply, **options)
    reverted = deepcopy(document)
    for path, text in changed.items():
        _set({"blocks": reverted["blocks"][1:]}, path, text)
    if not validation.passed or reverted != old_document:
        raise ValueError(invalid)
    return document, validation, reply, sorted(changed)


def _restore_authored_procedure_reply(
    source, retained, old_document, old_reply, *, prompt_version, verified_color_notes=False,
    recast=correct_authored_procedure_step, invalid=_AUTHORED_PROCEDURE_INVALID,
):
    reply = deepcopy(old_reply)
    old_leaves = {"blocks": old_document["blocks"][1:]}
    changed = {}
    for row in reply["replacements"]:
        if row["action"] != "rewrite":
            continue
        path = row["path"]
        original = _get(source, path)
        published = row["text"]
        wording = recast(original, published)
        if wording is None:
            continue
        if original != _get(retained, path) or published != _get(old_leaves, path):
            raise ValueError(invalid)
        row["text"] = wording
        changed[path] = published
    if not changed:
        raise ValueError(invalid)
    return _validate_restored_reply(source, old_document, reply, changed, invalid,
                                    prompt_version=prompt_version, verified_color_notes=verified_color_notes)


def _validate_restored_reply(source, old_document, reply, changed, invalid, *, prompt_version,
                             verified_color_notes=False):
    options = dict(prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
                   verified_color_notes=verified_color_notes)
    document = render_auto(source, reply, **options)
    validation = validate_auto(source, document, response=reply, **options)
    reverted = deepcopy(document)
    for path, text in changed.items():
        _set({"blocks": reverted["blocks"][1:]}, path, text)
    if not validation.passed or reverted != old_document:
        raise ValueError(invalid)
    return document, validation, reply, sorted(changed)


def _restore_procedure_condition_reply(source, retained, old_document, old_reply, *, prompt_version):
    prompt = _auto_prompt_payload_v62(source, context={})
    if prompt["prompt_version"] != prompt_version:
        raise ValueError(_PROCEDURE_CONDITION_INVALID)
    failures = {finding["path"] for finding in failed_rewrite_passages(source, old_reply, prompt_version=prompt_version)
                if finding["code"] == "REWRITE_QUALIFIER_MUTATION"}
    eligible = {slot["path"] for slot in prompt["slots"]
                if slot["path"] in failures and slot["required_action"] == "retain"
                and _procedure_condition(slot["text"], fuel_prerequisites=True) is None}
    if not eligible:
        raise ValueError(_PROCEDURE_CONDITION_INVALID)
    reply = deepcopy(old_reply)
    old_leaves = {"blocks": old_document["blocks"][1:]}
    changed = {}
    for row in reply["replacements"]:
        path = row["path"]
        if path not in eligible:
            continue
        original = _get(source, path)
        if row["action"] != "rewrite" or original != _get(retained, path) or row["text"] != _get(old_leaves, path):
            raise ValueError(_PROCEDURE_CONDITION_INVALID)
        changed[path] = row["text"]
        row.update(action="retain", text=original, reason=_CONDITION_RETENTION_REASON)
    return _validate_restored_reply(source, old_document, reply, changed, _PROCEDURE_CONDITION_INVALID,
                                    prompt_version=prompt_version)


def _correct_spaced_rotation(original, published):
    replacement = recast_spaced_rotation_removal(original)
    if replacement and published == recast_authored_rotation_removal(original) and published != replacement:
        return replacement
    return None


def _correct_short_procedure(original, published):
    wording = recast_short_procedure(original)
    return wording if wording != published else None


@dataclass(frozen=True)
class _Repair:
    profile: str
    method: str
    checkpoint: str
    prior_methods: tuple[str, ...]
    invalid: str
    stale: str
    edit_reply: Callable
    successor_guard: str | None = None
    provider: str | None = "banktwo"
    prior_profiles: tuple[str, ...] = (SOURCE_BOUND_CORRECTION_PROFILE,)


_LABELS = _Repair(PROFILE, METHOD, CHECKPOINT, (RECOVERY_METHOD,), _INVALID, _STALE, _restore_reply)
_CONDITIONAL = _Repair(
    CONDITIONAL_PROFILE, CONDITIONAL_METHOD, CONDITIONAL_CHECKPOINT, (ARCHIVED_FIRST_DRAFT_METHOD,),
    _CONDITIONAL_INVALID, "RETAINED_CONDITIONAL_NOTE_REPAIR_STALE",
    partial(_recast_reply, recast=recast_conditional_color_note, invalid=_CONDITIONAL_INVALID, verified_color_notes=True),
)
_ROTATION_REMOVAL = _Repair(
    ROTATION_REMOVAL_PROFILE, ROTATION_REMOVAL_METHOD, ROTATION_REMOVAL_CHECKPOINT, (SENTENCE_CORRECTION_METHOD,),
    _ROTATION_REMOVAL_INVALID, "RETAINED_ROTATION_REMOVAL_REPAIR_STALE",
    partial(_recast_reply, recast=recast_authored_rotation_removal, invalid=_ROTATION_REMOVAL_INVALID),
    successor_guard=_ROTATION_REMOVAL_PROMPT_VERSION,
)
_SPACED_ROTATION = _Repair(
    SPACED_ROTATION_PROFILE, SPACED_ROTATION_METHOD, SPACED_ROTATION_CHECKPOINT, (ROTATION_REMOVAL_METHOD,),
    _SPACED_ROTATION_INVALID, "RETAINED_SPACED_ROTATION_REPAIR_STALE",
    partial(_restore_authored_procedure_reply, recast=_correct_spaced_rotation, invalid=_SPACED_ROTATION_INVALID),
    successor_guard=_SPACED_ROTATION_PROMPT_VERSION, prior_profiles=(ROTATION_REMOVAL_PROFILE,),
)
_OPTIONAL_OBSERVATION = _Repair(
    OPTIONAL_OBSERVATION_PROFILE, OPTIONAL_OBSERVATION_METHOD, OPTIONAL_OBSERVATION_CHECKPOINT, (BANKONE_ORDER_METHOD,),
    _OPTIONAL_OBSERVATION_INVALID, "RETAINED_OPTIONAL_OBSERVATION_REPAIR_STALE",
    partial(_recast_reply, recast=recast_optional_observation, invalid=_OPTIONAL_OBSERVATION_INVALID),
    successor_guard=_OPTIONAL_OBSERVATION_PROMPT_VERSION, provider="bankone",
)
_AUTHORED_PROCEDURE = _Repair(
    AUTHORED_PROCEDURE_PROFILE, AUTHORED_PROCEDURE_METHOD, AUTHORED_PROCEDURE_CHECKPOINT,
    (RECOVERY_METHOD, SENTENCE_INSTRUCTION_RECOVERY_METHOD, SENTENCE_TOOL_RECOVERY_METHOD, CONDITIONAL_METHOD),
    _AUTHORED_PROCEDURE_INVALID, "RETAINED_AUTHORED_PROCEDURE_REPAIR_STALE",
    _restore_authored_procedure_reply, provider=None,
    prior_profiles=(SOURCE_BOUND_CORRECTION_PROFILE, CONDITIONAL_PROFILE),
)
_PROCEDURE_CONDITION = _Repair(
    PROCEDURE_CONDITION_PROFILE, PROCEDURE_CONDITION_METHOD, PROCEDURE_CONDITION_CHECKPOINT, (AUTHORED_PROCEDURE_METHOD,),
    _PROCEDURE_CONDITION_INVALID, "RETAINED_PROCEDURE_CONDITION_REPAIR_STALE",
    _restore_procedure_condition_reply, successor_guard=_PROCEDURE_FIDELITY_PROMPT_VERSION,
    prior_profiles=(AUTHORED_PROCEDURE_PROFILE,),
)
_SHORT_ACTIONS = _Repair(
    SHORT_ACTION_PROFILE, SHORT_ACTION_METHOD, SHORT_ACTION_CHECKPOINT,
    (ARCHIVED_FIRST_DRAFT_METHOD, BANKTWO_NOTICE_METHOD, RECOVERY_METHOD, AUTHORED_PROCEDURE_METHOD, METHOD),
    _SHORT_ACTION_INVALID, "RETAINED_SHORT_ACTION_REPAIR_STALE",
    partial(_restore_authored_procedure_reply, recast=_correct_short_procedure, invalid=_SHORT_ACTION_INVALID),
    successor_guard=_SHORT_ACTION_PROMPT_VERSION,
    prior_profiles=(SOURCE_BOUND_CORRECTION_PROFILE, AUTHORED_PROCEDURE_PROFILE, PROFILE),
)


def _source_evidence(cur, article, source_id, descriptor_id, *, lock):
    source = _source_replay_row(cur, source_id)
    if (source is None or source["canonical_article_id"] != article["canonical_article_id"]
        or source["membership_status"] != "active" or source["takedown_status"] != "active"):
        raise ValueError(_UNAVAILABLE)
    try:
        resources = {}
        for entry, proof in zip(source["resource_manifest"], source["resource_provenance"], strict=True):
            if proof["provider"] != article["provider_slug"] or any(proof.get(key) != value for key, value in entry.items()):
                raise ValueError(_UNAVAILABLE)
            if not entry.get("sha256"):
                if entry != {key: value for key, value in proof.items() if key != "provider"} or not entry.get("failure_code"):
                    raise ValueError(_UNAVAILABLE)
                continue
            snapshot = UUID(proof["source_snapshot_id"])
            binding = (entry["sha256"], proof["object_key"], entry["media_type"])
            if resources.setdefault(snapshot, binding) != binding:
                raise ValueError(_UNAVAILABLE)
        if (source["resource_manifest"][0]["role"] != "body"
            or source["body_source_snapshot_id"] != UUID(source["resource_provenance"][0]["source_snapshot_id"])
            or source["body_source_snapshot_id"] not in resources):
            raise ValueError(_UNAVAILABLE)
        ids = set(resources) | {descriptor_id, source["descriptor_source_snapshot_id"], source["resolution_source_snapshot_id"]}
        snapshots = _load_snapshots(cur, ids, resource_ids=set(resources), lock=lock)
        for row in snapshots:
            if row.id in resources and (
                (row.digest, row.object_key, row.media_type) != resources[row.id]
                or (row.artifact_digest, row.artifact_key) != resources[row.id][:2]
            ):
                raise ValueError(_UNAVAILABLE)
        _check_review_quarantine(cur, ids, lock=lock)
        if lock and (
            article["descriptor_source_snapshot_id"] != descriptor_id
            or not source_bound_rewrite_source_allowed(cur, article, source_id)
        ):
            raise ValueError(_UNAVAILABLE)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        raise ValueError(_UNAVAILABLE) from None
    return source


def _rebuild(cur, article, prior_job, source_id, descriptor_id, prior_revision_id, old_hash, *, lock, repair=_LABELS):
    from .article_lifecycle_store import _require_source_bound_rewrite_rights
    from .published_media_publication import _publication_evidence_for_revision

    if (prior_job is None or prior_job["provider_slug"] != article["provider_slug"]
        or repair.provider is not None and article["provider_slug"] != repair.provider
        or prior_job["canonical_article_id"] != article["canonical_article_id"] or prior_job["source_revision_id"] != source_id
        or prior_job["job_kind"] != "article" or prior_job["rewrite_profile_version"] not in repair.prior_profiles
        or prior_job["status"] != "completed" or prior_job["phase"] != "completed" or prior_job["retryable"]
        or prior_job["lease_owner"] is not None or prior_job["lease_expires_at"] is not None):
        raise ValueError(repair.stale)
    prior = cur.execute("""SELECT transformation_key,rewrite_result_hash,model_metadata->>'transformation_method' AS method
        FROM canonical_article_revisions WHERE canonical_article_revision_id=%s AND canonical_article_id=%s
          AND source_revision_id=%s AND status='published'""", (prior_revision_id, article["canonical_article_id"], source_id)).fetchone()
    if (prior is None or prior["method"] not in repair.prior_methods or prior["transformation_key"] != prior_job["transformation_key"]
        or prior["rewrite_result_hash"] != old_hash):
        raise ValueError(repair.stale)
    bound_source = _source_evidence(cur, article, source_id, descriptor_id, lock=lock)
    if lock and repair in (_ROTATION_REMOVAL, _AUTHORED_PROCEDURE, _SPACED_ROTATION, _PROCEDURE_CONDITION, _SHORT_ACTIONS):
        _require_source_bound_rewrite_rights(cur, prior_job, article)
    prior_profile = prior_job["rewrite_profile_version"]
    prior, review, decision, attempt, archived_reply, version, _ = _publication_evidence_for_revision(
        cur, article, SimpleNamespace(source_revision_id=source_id), prior_revision_id,
        fixture_mode=False, lock=lock, expected_profile=prior_profile,
    )
    if review is not None or decision != "UNREVIEWED" or attempt is None:
        raise ValueError(repair.invalid)

    if repair is _OPTIONAL_OBSERVATION:
        if lock and not source_bound_rewrite_source_allowed(
            cur, article, source_id,
            predecessor_observation=(bound_source["source_observation_id"], bound_source["source_fetch_job_id"],
                                     bound_source["request_generation"]),
            require_current_observation_scope=True,
        ):
            raise ValueError(_UNAVAILABLE)
        # A successor without an exact link-binding copy could lose access to an embedded link.
        if cur.execute("""SELECT 1 FROM canonical_article_link_bindings
            WHERE canonical_article_revision_id=%s LIMIT 1""", (prior_revision_id,)).fetchone():
            raise ValueError(repair.invalid)
        archive = {"archived_order_evidence_hash": digest_json(prior["model_metadata"])}
    elif repair in (_AUTHORED_PROCEDURE, _SPACED_ROTATION, _PROCEDURE_CONDITION, _SHORT_ACTIONS):
        if cur.execute("""SELECT 1 FROM canonical_article_link_bindings WHERE canonical_article_revision_id=%s
            UNION ALL SELECT 1 FROM canonical_article_inline_link_bindings WHERE canonical_article_revision_id=%s LIMIT 1""",
            (prior_revision_id, prior_revision_id)).fetchone():
            raise ValueError(repair.invalid)
        archive = {"archived_publication_metadata_hash": digest_json(prior["model_metadata"])}
    else:
        archive = {"archived_correction_evidence_hash": digest_json(prior["model_metadata"]["correction_evidence"])}

    source = prior["normalized_source_document"]
    guard = repair.successor_guard or version
    options = {"verified_color_notes": prior_profile == CONDITIONAL_PROFILE} if repair is _AUTHORED_PROCEDURE else {}
    document, validation, reply, paths = repair.edit_reply(
        source, bound_source["source_document"], prior["canonical_document"], archived_reply, prompt_version=guard, **options,
    )
    if lock:
        checked = prior["canonical_document"] if repair is _CONDITIONAL else document
        require_current_publication_checks(source, checked, saved_prompt_version=guard)
    facts = {
        "source_revision_id": str(source_id),
        "source_observation_id": str(bound_source["source_observation_id"]),
        "source_fingerprint": bound_source["source_fingerprint"],
        "source_body_snapshot_id": str(bound_source["body_source_snapshot_id"]),
        "source_resource_manifest_hash": digest_json(bound_source["resource_manifest"]),
        "descriptor_snapshot_id": str(descriptor_id),
        "prior_job_id": str(prior_job["source_fetch_job_id"]),
        "prior_revision_id": str(prior_revision_id),
        "prior_document_hash": old_hash,
        **archive,
        "archived_attempt_id": str(attempt["rewrite_attempt_id"]),
        "archived_final_reply_hash": digest_json(archived_reply),
        "guard_version": guard,
        "restored_paths": paths,
        "repaired_reply_hash": digest_json(reply),
        "repaired_document_hash": digest_json(document),
    }
    if repair.successor_guard is not None:
        facts["archived_guard_version"] = version
    key = transformation_key(
        article["canonical_article_id"], bound_source["source_fingerprint"], prior["normalization_version"],
        repair.profile, projection_version=bound_source["projection_version"],
    )
    return _Plan(source, document, validation, facts, key, attempt, reply)


def resolve_retained_note_label_repair(cur, job, article, candidate, *, publishing=False):
    """Verify the immutable prior replay and the exact prefix-only successor."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_LABELS)


def resolve_retained_conditional_note_repair(cur, job, article, candidate, *, publishing=False):
    """Rebuild the exact successor from the retained source and archived reply."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_CONDITIONAL)


def resolve_retained_rotation_removal_repair(cur, job, article, candidate, *, publishing=False):
    """Replay the archived reply and validate the exact rotation and removal rewording."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_ROTATION_REMOVAL)


def resolve_retained_spaced_rotation_repair(cur, job, article, candidate, *, publishing=False):
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_SPACED_ROTATION)


def resolve_retained_optional_observation_repair(cur, job, article, candidate, *, publishing=False):
    """Rebuild the exact optional observation from the Bankone order publication."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_OPTIONAL_OBSERVATION)


def resolve_retained_authored_procedure_repair(cur, job, article, candidate, *, publishing=False):
    """Replay the scoped repair from the original source and previous reply."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_AUTHORED_PROCEDURE)


def resolve_retained_procedure_condition_repair(cur, job, article, candidate, *, publishing=False):
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_PROCEDURE_CONDITION)


def resolve_retained_short_action_repair(cur, job, article, candidate, *, publishing=False):
    """Rebuild the same two-action wording from the pinned archive."""
    return _resolve_repair(cur, job, article, candidate, publishing=publishing, repair=_SHORT_ACTIONS)


def _resolve_repair(cur, job, article, candidate, *, publishing, repair):
    audit = job["checkpoint"].get(repair.checkpoint)
    metadata = candidate["model_metadata"]
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or metadata.get(repair.checkpoint) != audit or metadata.get("transformation_method") != repair.method
        or metadata.get("profile_version") != repair.profile or not _valid_audit(audit["actor"], audit["reason"])
        or not isinstance(audit["evidence"], dict)
        or job["rewrite_profile_version"] != repair.profile or candidate["rewrite_profile_version"] != repair.profile
        or job["provider_slug"] != article["provider_slug"]
        or repair.provider is not None and job["provider_slug"] != repair.provider
        or job["source_version"] != repair.method
        or job["retry_count"] != 0 or job["max_attempts"] != 1
        or any(candidate[field] != job[field] for field in (
            "canonical_article_id", "source_revision_id", "normalization_version", "transformation_key",
        ))
        or cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s OR canonical_article_revision_id=%s LIMIT 1""",
            (job["source_fetch_job_id"], candidate["canonical_article_revision_id"])).fetchone()):
        raise ValueError(repair.invalid)
    evidence = audit["evidence"]
    try:
        prior_job_id, prior_revision_id, descriptor_id = (UUID(evidence[key]) for key in (
            "prior_job_id", "prior_revision_id", "descriptor_snapshot_id",
        ))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(repair.invalid) from None
    expected_visible_revision = None if repair is _SPACED_ROTATION else prior_revision_id
    if publishing and (
        article["current_canonical_revision_id"] != expected_visible_revision
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["descriptor_source_snapshot_id"] != descriptor_id
    ):
        raise ValueError(repair.stale)
    prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                            (prior_job_id,)).fetchone()
    plan = _rebuild(cur, article, prior_job, job["source_revision_id"], descriptor_id, prior_revision_id,
                    evidence.get("prior_document_hash"), lock=publishing, repair=repair)
    if (plan.evidence != evidence or job["request_generation"] != prior_job["request_generation"] + 1
        or plan.key != job["transformation_key"] or plan.attempt["model"] != metadata.get("model")
        or candidate["normalized_source_document"] != plan.source or candidate["canonical_document"] != plan.document):
        raise ValueError(repair.invalid)
    return plan


def repair_retained_note_labels(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish a pinned prefix repair and its outbox event in one transaction."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_LABELS,
    )


def repair_retained_conditional_note(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish one source-verified wording repair and its outbox event."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_CONDITIONAL,
    )


def repair_retained_rotation_removal(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish the pinned rewording and its outbox event in one transaction."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_ROTATION_REMOVAL,
    )


def repair_retained_spaced_rotation(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish the corrected direction after the ambiguous revision is held."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_SPACED_ROTATION,
    )


def repair_retained_optional_observation(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish the pinned observation rewording and its event in one transaction."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_OPTIONAL_OBSERVATION,
    )


def repair_retained_authored_procedure(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish verified instruction wording against the same stored source."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id,
        expected_published_revision_id=expected_published_revision_id, expected_published_hash=expected_published_hash,
        expected_repaired_hash=expected_repaired_hash, actor=actor, reason=reason, hooks=hooks, repair=_AUTHORED_PROCEDURE,
    )


def repair_retained_procedure_condition(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Republish the archived rewrite with its original procedure conditions."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id, expected_published_revision_id=expected_published_revision_id,
        expected_published_hash=expected_published_hash, expected_repaired_hash=expected_repaired_hash,
        actor=actor, reason=reason, hooks=hooks, repair=_PROCEDURE_CONDITION,
    )


def repair_retained_short_actions(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish a clearer rendition of the same ordered instructions and source."""
    return _repair_retained_note(
        repo, article_id, expected_job_id=expected_job_id, expected_source_revision_id=expected_source_revision_id,
        expected_descriptor_snapshot_id=expected_descriptor_snapshot_id, expected_published_revision_id=expected_published_revision_id,
        expected_published_hash=expected_published_hash, expected_repaired_hash=expected_repaired_hash,
        actor=actor, reason=reason, hooks=hooks, repair=_SHORT_ACTIONS,
    )


def _repair_retained_note(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks, repair,
):
    if (not _valid_audit(actor, reason) or not all(
        isinstance(value, str) and _HASH.fullmatch(value) for value in (expected_published_hash, expected_repaired_hash)
    )):
        raise ValueError(repair.invalid)
    article_id, prior_job_id, source_id, descriptor_id, prior_revision_id = map(UUID, map(str, (
        article_id, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
        expected_published_revision_id,
    )))
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                                (prior_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (article_id,)).fetchone()
        expected_visible_revision = None if repair is _SPACED_ROTATION else prior_revision_id
        if (prior_job is None or article is None or article["current_job_id"] != prior_job_id
            or article["current_source_revision_id"] != source_id or article["current_canonical_revision_id"] != expected_visible_revision
            or article["descriptor_source_snapshot_id"] != descriptor_id
            or article["request_generation"] != prior_job["request_generation"]
            or article["target_rewrite_profile_version"] != prior_job["rewrite_profile_version"]
            or article["target_normalization_version"] != prior_job["normalization_version"]):
            raise ValueError(repair.stale)
        _require_no_active_normal_job(cur, article_id)
        plan = _rebuild(
            cur, article, prior_job, source_id, descriptor_id, prior_revision_id, expected_published_hash,
            lock=True, repair=repair,
        )
        if plan.evidence["repaired_document_hash"] != expected_repaired_hash:
            raise ValueError(repair.stale)

        return _publish_archived_reply_repair(
            cur, article, plan, profile=repair.profile, method=repair.method, checkpoint=repair.checkpoint,
            actor=actor, reason=reason, hooks=hooks,
        )


def _publish_archived_reply_repair(cur, article, plan, *, profile, method, checkpoint, actor, reason, hooks):
    from .article_lifecycle_store import _publish_article_revision

    article_id = article["canonical_article_id"]
    source_id = article["current_source_revision_id"]
    provider = article["provider_slug"]
    audit = {"actor": actor, "reason": reason, "evidence": plan.evidence}
    generation = article["request_generation"] + 1
    normalization = article["target_normalization_version"]
    job_id, revision_id, worker_id = uuid4(), uuid4(), uuid4()
    job = cur.execute("""INSERT INTO source_fetch_jobs(
        source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,
        source_version,connector_name,idempotency_key,status,phase,job_kind,canonical_article_id,
        request_generation,normalization_version,rewrite_profile_version,source_revision_id,transformation_key,
        max_attempts,lease_owner,lease_token,lease_expires_at,heartbeat_at,checkpoint)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'processing','publishing','article',%s,%s,%s,%s,%s,%s,
        1,%s,1,clock_timestamp()+interval '90 seconds',clock_timestamp(),%s) RETURNING *""",
        (job_id, provider, article["vehicle_id"], article["source_vehicle_ref"], article["source_article_ref"],
         method, provider, f"article:{article_id}:{generation}", article_id, generation, normalization,
         profile, source_id, plan.key, worker_id, Jsonb({checkpoint: audit}))).fetchone()
    projection = project_ordered_document(plan.document)
    cur.execute("""INSERT INTO canonical_article_revisions(
        canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,
        normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,
        canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,
        rewrite_result_hash,model_metadata)
        VALUES (%s,%s,%s,%s,%s,%s,'validated',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (revision_id, article_id, source_id, plan.key, normalization, profile,
         Jsonb(plan.source), digest_json(plan.source), Jsonb(plan.document), projection["body"],
         Jsonb(projection["steps"]), Jsonb(projection["images"]), Jsonb(plan.validation.report),
         digest_json(plan.validation.report), plan.evidence["repaired_document_hash"],
         Jsonb({"transformation_method": method, "model": plan.attempt["model"],
                "profile_version": profile, checkpoint: audit})))
    cur.execute("""UPDATE canonical_articles SET current_job_id=%s,request_generation=%s,
        target_rewrite_profile_version=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
        (job_id, generation, profile, article_id))
    return _publish_article_revision(cur, _lease_from_row(job, worker_id), revision_id, hooks=hooks)
