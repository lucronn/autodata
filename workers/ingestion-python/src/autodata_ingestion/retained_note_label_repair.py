"""Restore leading Note labels in one exact, completed Banktwo v3 publication."""

from copy import deepcopy
from dataclasses import dataclass
import re
from types import SimpleNamespace
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_document import project_ordered_document
from .article_lifecycle_types import (
    RETAINED_NOTE_LABEL_REPAIR_PROFILE as PROFILE, SOURCE_BOUND_CORRECTION_PROFILE, ValidationResult,
    digest_json, transformation_key,
)
from .procedure_rewrite_auto import authored_note_prefix, render_auto, require_current_publication_checks, validate_auto
from .procedure_rewrite_full import _get, _set
from .procedure_rewrite_recovery import RECOVERY_METHOD
from .retained_procedure_repair import _valid_audit
from .source_job_persistence import _lease_from_row, source_bound_rewrite_source_allowed
from .source_media_replay import _check_review_quarantine, _load_snapshots, _source_replay_row
from .source_revision_reprojection import _require_no_active_normal_job


METHOD = "retained-note-label-archived-reply-repair-v1"
CHECKPOINT = "retained_note_label_repair"
_INVALID = "RETAINED_NOTE_LABEL_REPAIR_INVALID"
_STALE = "RETAINED_NOTE_LABEL_REPAIR_STALE"
_UNAVAILABLE = "RETAINED_NOTE_LABEL_REPAIR_SOURCE_UNAVAILABLE"
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


def _source_evidence(cur, article, source_id, descriptor_id, *, lock):
    source = _source_replay_row(cur, source_id)
    if (source is None or source["canonical_article_id"] != article["canonical_article_id"]
        or source["membership_status"] != "active" or source["takedown_status"] != "active"):
        raise ValueError(_UNAVAILABLE)
    try:
        resources = {}
        for entry, proof in zip(source["resource_manifest"], source["resource_provenance"], strict=True):
            if proof["provider"] != "banktwo" or any(proof.get(key) != value for key, value in entry.items()):
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


def _rebuild(cur, article, prior_job, source_id, descriptor_id, prior_revision_id, old_hash, *, lock):
    from .published_media_publication import _publication_evidence_for_revision

    if (prior_job is None or article["provider_slug"] != "banktwo" or prior_job["provider_slug"] != "banktwo"
        or prior_job["canonical_article_id"] != article["canonical_article_id"] or prior_job["source_revision_id"] != source_id
        or prior_job["job_kind"] != "article" or prior_job["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
        or prior_job["status"] != "completed" or prior_job["phase"] != "completed" or prior_job["retryable"]
        or prior_job["lease_owner"] is not None or prior_job["lease_expires_at"] is not None):
        raise ValueError(_STALE)
    prior = cur.execute("""SELECT transformation_key,rewrite_result_hash,model_metadata->>'transformation_method' AS method
        FROM canonical_article_revisions WHERE canonical_article_revision_id=%s AND canonical_article_id=%s
          AND source_revision_id=%s AND status='published'""", (prior_revision_id, article["canonical_article_id"], source_id)).fetchone()
    if (prior is None or prior["method"] != RECOVERY_METHOD or prior["transformation_key"] != prior_job["transformation_key"]
        or prior["rewrite_result_hash"] != old_hash):
        raise ValueError(_STALE)
    bound_source = _source_evidence(cur, article, source_id, descriptor_id, lock=lock)
    prior, review, decision, attempt, archived_reply, version, _ = _publication_evidence_for_revision(
        cur, article, SimpleNamespace(source_revision_id=source_id), prior_revision_id,
        fixture_mode=False, lock=lock, expected_profile=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    if review is not None or decision != "UNREVIEWED" or attempt is None:
        raise ValueError(_INVALID)

    source = prior["normalized_source_document"]
    document, validation, reply, paths = _restore_reply(
        source, bound_source["source_document"], prior["canonical_document"], archived_reply, prompt_version=version,
    )
    if lock:
        require_current_publication_checks(source, document, saved_prompt_version=version)
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
        "archived_correction_evidence_hash": digest_json(prior["model_metadata"]["correction_evidence"]),
        "archived_attempt_id": str(attempt["rewrite_attempt_id"]),
        "archived_final_reply_hash": digest_json(archived_reply),
        "guard_version": version,
        "restored_paths": paths,
        "repaired_reply_hash": digest_json(reply),
        "repaired_document_hash": digest_json(document),
    }
    key = transformation_key(
        article["canonical_article_id"], bound_source["source_fingerprint"], prior["normalization_version"],
        PROFILE, projection_version=bound_source["projection_version"],
    )
    return _Plan(source, document, validation, facts, key, attempt, reply)


def resolve_retained_note_label_repair(cur, job, article, candidate, *, publishing=False):
    """Verify the immutable prior replay and the exact prefix-only successor."""
    audit = job["checkpoint"].get(CHECKPOINT)
    metadata = candidate["model_metadata"]
    if (not isinstance(audit, dict) or set(audit) != {"actor", "reason", "evidence"}
        or metadata.get(CHECKPOINT) != audit or metadata.get("transformation_method") != METHOD
        or metadata.get("profile_version") != PROFILE or not _valid_audit(audit["actor"], audit["reason"])
        or not isinstance(audit["evidence"], dict)
        or job["rewrite_profile_version"] != PROFILE or candidate["rewrite_profile_version"] != PROFILE
        or job["provider_slug"] != "banktwo" or job["source_version"] != METHOD
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
    prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                            (prior_job_id,)).fetchone()
    plan = _rebuild(cur, article, prior_job, job["source_revision_id"], descriptor_id, prior_revision_id,
                    evidence.get("prior_document_hash"), lock=publishing)
    if (plan.evidence != evidence or job["request_generation"] != prior_job["request_generation"] + 1
        or plan.key != job["transformation_key"] or plan.attempt["model"] != metadata.get("model")
        or candidate["normalized_source_document"] != plan.source or candidate["canonical_document"] != plan.document):
        raise ValueError(_INVALID)
    return plan


def repair_retained_note_labels(
    repo, article_id, *, expected_job_id, expected_source_revision_id, expected_descriptor_snapshot_id,
    expected_published_revision_id, expected_published_hash, expected_repaired_hash, actor, reason, hooks=None,
):
    """Publish a pinned prefix repair and its outbox event in one transaction."""
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
            or article["target_rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
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


def _publish_archived_reply_repair(cur, article, plan, *, profile, method, checkpoint, actor, reason, hooks):
    from .article_lifecycle_store import _publish_article_revision

    article_id = article["canonical_article_id"]
    source_id = article["current_source_revision_id"]
    audit = {"actor": actor, "reason": reason, "evidence": plan.evidence}
    generation = article["request_generation"] + 1
    normalization = article["target_normalization_version"]
    job_id, revision_id, worker_id = uuid4(), uuid4(), uuid4()
    job = cur.execute("""INSERT INTO source_fetch_jobs(
        source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,
        source_version,connector_name,idempotency_key,status,phase,job_kind,canonical_article_id,
        request_generation,normalization_version,rewrite_profile_version,source_revision_id,transformation_key,
        max_attempts,lease_owner,lease_token,lease_expires_at,heartbeat_at,checkpoint)
        VALUES (%s,'banktwo',%s,%s,%s,%s,'banktwo',%s,'processing','publishing','article',%s,%s,%s,%s,%s,%s,
        1,%s,1,clock_timestamp()+interval '90 seconds',clock_timestamp(),%s) RETURNING *""",
        (job_id, article["vehicle_id"], article["source_vehicle_ref"], article["source_article_ref"],
         method, f"article:{article_id}:{generation}", article_id, generation, normalization,
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
