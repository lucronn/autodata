"""Preview and atomically publish an approved retained article correction."""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_content_review import (
    _fixture_allowed,
    _source_evidence,
    _substantive,
    authorize_reviewer,
    correction_authors,
    resolve_full_evidence,
    validate_review_reason,
    write_private_export,
)
from .article_document import project_ordered_document
from .article_lifecycle_store import (
    _latest_content_review, _persist_article_capture, automatic_candidate_validation, resolve_first_draft_recovery,
    resolve_source_bound_correction,
)
from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILES, SOURCE_BOUND_CORRECTION_PROFILE, digest_json, transformation_key,
)
from .procedure_normalize import normalize_procedure_article
from .procedure_rewrite import build_rewrite_prompt, validate_article_rewrite
from .procedure_rewrite_auto import (
    SOURCE_PRESERVING_METHOD,
    _auto_prompt_version,
    build_source_preserving_candidate,
)
from .procedure_rewrite_full import PROFILE as REVIEW_PROFILE, validate_full
from .procedure_rewrite_recovery import ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS, BANKONE_ARCHIVE_STRUCTURE_VERSIONS
from .published_media_repair import (
    MEDIA_METHOD, ORDINAL_METHOD, SVG_RECOVERY_METHOD, TABLE_SPAN_METHOD, TECHNICAL_V1, TECHNICAL_V2,
    PublishedMediaRepair, repair_published_media,
)
from .source_media_replay import (
    load_media_replay_binding,
    media_replay_document_hash,
    preview_media_replay,
    validate_media_replay_result,
)
from .source_revision_reprojection import (
    _require_no_active_normal_job, preview_svg_reprojection,
)
from .source_table_replay import load_table_replay_binding, preview_table_replay

SCHEMA = "autodata:published-media-repair:v1"
ORDINAL_SCHEMA = "autodata:published-list-ordinals:v1"
TABLE_SPAN_SCHEMA = "autodata:published-table-spans:v1"
SVG_RECOVERY_SCHEMA = "autodata:published-svg-recovery:v1"


@dataclass(frozen=True)
class _RepairPlan:
    manifest: dict
    previous: dict
    normalized: dict
    repair: PublishedMediaRepair
    review_status: str
    drafting_identities: tuple[str, ...]
    retained_links: tuple[dict, ...] = ()


def _normalize(captured, canonical_article_id):
    return normalize_procedure_article({
        "article_id": str(canonical_article_id),
        "title": captured.context.descriptor.get("title"),
        "evidence_ids": list(captured.context.evidence_ids),
        "normalized_document": captured.source_document,
        "blocks": captured.source_document["blocks"],
        "images": captured.source_images,
        "body": captured.source_body,
        "steps": captured.source_steps,
    })["normalized_document"]


def _saved_attempt(cur, revision_id, job_id):
    return cur.execute("""
        SELECT * FROM canonical_article_rewrite_attempts
        WHERE canonical_article_revision_id=%s AND source_fetch_job_id=%s AND status='succeeded'
        """, (revision_id, job_id)).fetchone()


def _validate_technical_evidence(cur, job, row, attempt):
    profile = row["rewrite_profile_version"]
    source = row["normalized_source_document"]
    context = _source_evidence(cur, job, row)
    prompt_hash = sha256(build_rewrite_prompt(source, context=context, profile_version=profile).encode()).hexdigest()
    if (attempt is None or not isinstance(attempt["response"], dict)
        or attempt["profile_version"] != profile or job["rewrite_profile_version"] != profile
        or attempt["input_hash"] != row["normalized_source_hash"]
        or attempt["response_hash"] != digest_json(attempt["response"])
        or attempt["prompt_hash"] != prompt_hash or row["model_metadata"].get("prompt_hash") != prompt_hash
        or attempt["model"] != row["model_metadata"].get("model")
        or profile != row["model_metadata"].get("profile_version")):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_ATTEMPT_REQUIRED")
    return validate_article_rewrite(source, row["canonical_document"], profile_version=profile)


def _publication_evidence(cur, article, binding, *, fixture_mode, lock):
    return _publication_evidence_for_revision(
        cur, article, binding, article["current_canonical_revision_id"], fixture_mode=fixture_mode, lock=lock,
    )


def _publication_evidence_for_revision(cur, article, binding, revision_id, *, fixture_mode, lock, expected_profile=None):
    from .retained_bankone_order_reply import BANKONE_ORDER_METHOD
    from .retained_banktwo_notice_reply import BANKONE_DEFINITION_METHOD, BANKONE_LIST_BOUNDARY_METHOD, BANKTWO_NOTICE_METHOD
    from .retained_introduction_repair import (
        METHOD as INTRODUCTION_METHOD, PROFILE as INTRODUCTION_PROFILE, resolve_retained_introduction_repair,
    )
    from .retained_note_label_repair import (
        AUTHORED_PROCEDURE_METHOD, AUTHORED_PROCEDURE_PROFILE,
        CONDITIONAL_METHOD, CONDITIONAL_PROFILE, METHOD as NOTE_LABEL_REPAIR_METHOD, PROFILE as NOTE_LABEL_REPAIR_PROFILE,
        DIAGNOSTIC_WORDING_METHOD, DIAGNOSTIC_WORDING_PROFILE,
        OPTIONAL_OBSERVATION_METHOD, OPTIONAL_OBSERVATION_PROFILE, PROCEDURE_CONDITION_METHOD, PROCEDURE_CONDITION_PROFILE,
        ROTATION_REMOVAL_METHOD, ROTATION_REMOVAL_PROFILE,
        SERVICE_WORDING_METHOD, SERVICE_WORDING_PROFILE,
        SHORT_ACTION_METHOD, SHORT_ACTION_PROFILE,
        SPACED_ROTATION_METHOD, SPACED_ROTATION_PROFILE,
        resolve_retained_authored_procedure_repair, resolve_retained_conditional_note_repair, resolve_retained_note_label_repair,
        resolve_retained_diagnostic_wording_repair,
        resolve_retained_optional_observation_repair, resolve_retained_procedure_condition_repair,
        resolve_retained_rotation_removal_repair,
        resolve_retained_service_wording_repair,
        resolve_retained_short_action_repair,
        resolve_retained_spaced_rotation_repair,
    )
    from .retained_procedure_repair import METHOD as RETAINED_PROCEDURE_REPAIR_METHOD, resolve_retained_procedure_repair
    from .retained_required_action_repair import (
        METHOD as REQUIRED_ACTION_METHOD, PROFILE as REQUIRED_ACTION_PROFILE, resolve_retained_required_action_repair,
    )
    from .staged_media_reply_recovery import METHOD as STAGED_MEDIA_REPLY_RECOVERY_METHOD

    article_id = article["canonical_article_id"]
    row = cur.execute("""
        SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s
          AND canonical_article_id=%s AND source_revision_id=%s AND status='published'
        """ + (" FOR UPDATE" if lock else ""), (revision_id, article_id, binding.source_revision_id)).fetchone()
    if row is None:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_CURRENT_REVISION_REQUIRED")

    if row["model_metadata"].get("transformation_method") in (
        MEDIA_METHOD, ORDINAL_METHOD, TABLE_SPAN_METHOD, SVG_RECOVERY_METHOD, STAGED_MEDIA_REPLY_RECOVERY_METHOD,
    ):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PRIOR_REPAIR_UNSUPPORTED")

    profile = row["rewrite_profile_version"]
    method = row["model_metadata"].get("transformation_method")
    repaired = {
        NOTE_LABEL_REPAIR_PROFILE: (NOTE_LABEL_REPAIR_METHOD, resolve_retained_note_label_repair),
        REQUIRED_ACTION_PROFILE: (REQUIRED_ACTION_METHOD, resolve_retained_required_action_repair),
        CONDITIONAL_PROFILE: (CONDITIONAL_METHOD, resolve_retained_conditional_note_repair),
        ROTATION_REMOVAL_PROFILE: (ROTATION_REMOVAL_METHOD, resolve_retained_rotation_removal_repair),
        SPACED_ROTATION_PROFILE: (SPACED_ROTATION_METHOD, resolve_retained_spaced_rotation_repair),
        OPTIONAL_OBSERVATION_PROFILE: (OPTIONAL_OBSERVATION_METHOD, resolve_retained_optional_observation_repair),
        AUTHORED_PROCEDURE_PROFILE: (AUTHORED_PROCEDURE_METHOD, resolve_retained_authored_procedure_repair),
        PROCEDURE_CONDITION_PROFILE: (PROCEDURE_CONDITION_METHOD, resolve_retained_procedure_condition_repair),
        SHORT_ACTION_PROFILE: (SHORT_ACTION_METHOD, resolve_retained_short_action_repair),
        DIAGNOSTIC_WORDING_PROFILE: (DIAGNOSTIC_WORDING_METHOD, resolve_retained_diagnostic_wording_repair),
        SERVICE_WORDING_PROFILE: (SERVICE_WORDING_METHOD, resolve_retained_service_wording_repair),
        INTRODUCTION_PROFILE: (INTRODUCTION_METHOD, resolve_retained_introduction_repair),
    }
    if (profile not in (*AUTOMATIC_REWRITE_PROFILES, REVIEW_PROFILE, TECHNICAL_V1, TECHNICAL_V2, *repaired)
        or (profile in repaired and method not in (repaired[profile][0], BANKTWO_NOTICE_METHOD, BANKONE_DEFINITION_METHOD))
        or profile != (expected_profile or article["target_rewrite_profile_version"])
        or row["normalization_version"] != article["target_normalization_version"]):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PROFILE_UNSUPPORTED")
    job = cur.execute("""
        SELECT * FROM source_fetch_jobs WHERE transformation_key=%s
          AND canonical_article_id=%s AND source_revision_id=%s AND status='completed'
        """, (row["transformation_key"], article_id, binding.source_revision_id)).fetchone()
    if job is None:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_OWNER_MISSING")
    latest = _latest_content_review(cur, row)
    decision = latest["decision"] if latest else row["review_status"]
    if (decision == "REJECTED" or (decision == "APPROVED" and latest is None)
        or (profile == REVIEW_PROFILE and decision != "APPROVED")):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REVIEW_REQUIRED")
    source = row["normalized_source_document"]
    document = row["canonical_document"]
    if (digest_json(source) != row["normalized_source_hash"]
        or digest_json(document) != row["rewrite_result_hash"]
        or project_ordered_document(document) != {
            "body": row["canonical_body"], "steps": row["canonical_steps"], "images": row["canonical_images"],
        }):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH")

    prompt_version = None
    authors = set()
    if profile == REVIEW_PROFILE:
        attempt, _, response, correction = resolve_full_evidence(cur, job, row)
        validation = validate_full(source, document, response=response)
        reason = validate_review_reason(
            latest["reason"], job=job, article=article, candidate=row,
            source_fingerprint=binding.source_fingerprint, review=latest, allow_synthetic=fixture_mode,
        )
        authors.update(correction_authors(cur, row))
        if correction is not None:
            authors.add(correction["actor"])
        if set(reason["retention_reviews"]) != set(validation.report.get("retained_paths", [])):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_REVIEW_REQUIRED")
    elif row["model_metadata"].get("transformation_method") == BANKONE_ORDER_METHOD:
        from .retained_bankone_order_publication import resolve_bankone_order_publication

        repaired, attempt, prompt_version = resolve_bankone_order_publication(cur, job, article, row, lock=lock)
        validation, response = repaired.validation, repaired.remapped_response
    elif method == BANKTWO_NOTICE_METHOD:
        from .retained_banktwo_notice_publication import resolve_banktwo_notice_publication

        repaired, attempt, prompt_version = resolve_banktwo_notice_publication(cur, job, article, row, lock=lock)
        validation, response = repaired.validation, repaired.remapped_response
    elif method == BANKONE_DEFINITION_METHOD:
        from .retained_banktwo_notice_publication import resolve_bankone_definition_heading_publication

        repaired, attempt, prompt_version = resolve_bankone_definition_heading_publication(cur, job, article, row, lock=lock)
        validation, response = repaired.validation, repaired.remapped_response
    elif method == BANKONE_LIST_BOUNDARY_METHOD:
        from .retained_banktwo_notice_publication import resolve_bankone_list_boundary_publication

        repaired, attempt, prompt_version = resolve_bankone_list_boundary_publication(cur, job, article, row, lock=lock)
        validation, response = repaired.validation, repaired.remapped_response
    elif method == RETAINED_PROCEDURE_REPAIR_METHOD:
        recovered = resolve_retained_procedure_repair(cur, job, article, row)
        validation, attempt, response, prompt_version = (
            recovered.validation, recovered.attempt, recovered.response, recovered.prompt_version,
        )
    elif profile in repaired:
        _, resolve = repaired[profile]
        recovered = resolve(cur, job, article, row)
        validation, attempt, response, prompt_version = (
            recovered.validation, recovered.attempt, recovered.reply, recovered.evidence["guard_version"],
        )
    elif profile in AUTOMATIC_REWRITE_PROFILES:
        validation = automatic_candidate_validation(cur, job, row)
        attempt = _saved_attempt(cur, revision_id, job["source_fetch_job_id"])
        if profile == SOURCE_BOUND_CORRECTION_PROFILE:
            corrected = resolve_source_bound_correction(cur, job, row)
            if corrected.archived_attempt is not None:
                attempt = corrected.archived_attempt
            response = corrected.response
            prompt_version = corrected.evidence["guard_version"]
        elif row["model_metadata"].get("transformation_method") == SOURCE_PRESERVING_METHOD:
            # Automatic validation above has independently rebuilt the exact
            # source-heading introduction and proved there was no model attempt.
            attempt = None
            response = {"introduction": document["blocks"][0]["text"], "replacements": []}
            prompt_version = "full-prose-auto-prompt-v3"
        elif attempt is not None:
            prompt_version = _auto_prompt_version(
                source, context=binding.context.vehicle, prompt_hash=attempt["prompt_hash"],
                profile_version=profile,
            )
            response = attempt["response"]
            if row["model_metadata"].get("transformation_method") in ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS:
                response = resolve_first_draft_recovery(cur, job, row, attempt, prompt_version=prompt_version).response
        else:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_ATTEMPT_REQUIRED")
    else:
        attempt = _saved_attempt(cur, revision_id, job["source_fetch_job_id"])
        validation = _validate_technical_evidence(cur, job, row, attempt)
        response = attempt["response"]
    if (not validation.passed or validation.report != row["validation_report"]
        or digest_json(validation.report) != row["validation_hash"]):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_VALIDATION_MISMATCH")
    if attempt is not None:
        authors.update((attempt["provider"], attempt["model"]))
    authors.add(row["model_metadata"].get("drafting_actor"))
    authors.discard(None)
    if profile == REVIEW_PROFILE and latest["authorized_reviewer_id"] in authors:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REVIEW_REQUIRED")
    return row, latest, decision, attempt, response, prompt_version, tuple(sorted(authors))


def _plan(cur, article, binding, captured, *, fixture_mode, lock=False, ordinals=False,
          table_spans=False, svg_recovery=False):
    if article["current_source_revision_id"] != binding.source_revision_id:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_STALE")
    row, review, decision, attempt, response, prompt_version, authors = _publication_evidence(
        cur, article, binding, fixture_mode=fixture_mode, lock=lock,
    )
    normalized = captured.source_document if table_spans or svg_recovery else _normalize(captured, binding.canonical_article_id)
    metadata = row["model_metadata"]
    bankone_structure = (
        metadata["bankone_first_draft_structure"]["proof"]
        if metadata.get("transformation_method") in BANKONE_ARCHIVE_STRUCTURE_VERSIONS else None
    )
    repair = repair_published_media(
        row["normalized_source_document"], row["canonical_document"], normalized,
        response=response, prompt_version=prompt_version, profile=row["rewrite_profile_version"],
        ordinals=ordinals, table_spans=table_spans, svg_recovery=svg_recovery, bankone_structure=bankone_structure,
    )
    if row["model_metadata"].get("transformation_method") == SOURCE_PRESERVING_METHOD:
        preserving_document, _ = build_source_preserving_candidate(normalized, profile_version=row["rewrite_profile_version"])
        if digest_json(preserving_document) != digest_json(repair.document):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_SOURCE_HEADING_CHANGED")
    manifest = {
        "schema": (
            SVG_RECOVERY_SCHEMA if svg_recovery else TABLE_SPAN_SCHEMA if table_spans
            else ORDINAL_SCHEMA if ordinals else SCHEMA
        ),
        "article_id": str(binding.canonical_article_id),
        "source_revision_id": str(binding.source_revision_id),
        "source_observation_id": str(binding.source_observation_id),
        "canonical_revision_id": str(row["canonical_article_revision_id"]),
        "source_fingerprint": binding.source_fingerprint,
        "body_sha256": binding.body_sha256,
        "repaired_source_document_hash": media_replay_document_hash(captured),
        "repaired_projection_version": captured.projection_version,
        "current_job_id": str(article["current_job_id"]),
        "request_generation": article["request_generation"],
        "normalization_version": row["normalization_version"],
        "original_attempt_id": str(attempt["rewrite_attempt_id"]) if attempt else None,
        "original_prompt_hash": attempt["prompt_hash"] if attempt else None,
        "original_transformation_method": row["model_metadata"].get("transformation_method"),
        "original_review_id": str(review["canonical_article_review_id"]) if review else None,
        "original_review_status": decision,
        "original_validation_hash": row["validation_hash"],
        "repaired_validation_hash": digest_json(repair.validation.report),
        **repair.provenance,
    }
    if svg_recovery:
        manifest.update(
            recovered_source_fingerprint=captured.source_fingerprint,
            recovered_provenance_hash=digest_json(captured.resource_provenance),
        )
    return _RepairPlan(manifest, row, normalized, repair, decision, authors)


def _preview_repair_source(repo, source_revision_id, *, object_store, ordinals, table_spans, svg_archive):
    if sum((ordinals, table_spans, svg_archive is not None)) > 1:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_MODE_INVALID")
    if svg_archive is not None:
        return preview_svg_reprojection(
            repo, source_revision_id, object_store=object_store, svg_archive=svg_archive,
        )
    if table_spans:
        binding, captured = preview_table_replay(repo, source_revision_id, object_store=object_store)
    else:
        binding, captured = preview_media_replay(repo, source_revision_id, object_store=object_store, ordinals=ordinals)
    return binding, captured, {}


def preview_published_media_repair(repo, article_id, source_revision_id, *, object_store, destination,
                                   fixture_mode=False, ordinals=False, table_spans=False, svg_archive=None):
    """Export both documents and exact approval bindings to a private directory."""
    binding, captured, _ = _preview_repair_source(
        repo, source_revision_id, object_store=object_store, ordinals=ordinals,
        table_spans=table_spans, svg_archive=svg_archive,
    )
    if binding.canonical_article_id != article_id:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_ARTICLE_MISMATCH")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        _fixture_allowed(cur, fixture_mode)
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article_id,)).fetchone()
        if article is None:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_ARTICLE_MISMATCH")
        plan = _plan(cur, article, binding, captured, fixture_mode=fixture_mode,
                     ordinals=ordinals, table_spans=table_spans, svg_recovery=svg_archive is not None)
    write_private_export(destination, {
        "manifest": plan.manifest,
        "source": {"before": plan.previous["normalized_source_document"], "after": plan.normalized},
        "candidate": {"before": plan.previous["canonical_document"], "after": plan.repair.document},
    })
    return {"status": "preview", "article_id": str(article_id), "manifest_sha256": digest_json(plan.manifest)}


def _result(row, status):
    return {
        "status": status,
        "job_id": str(row["source_fetch_job_id"]),
        "source_revision_id": str(row["source_revision_id"]),
        "canonical_revision_id": str(row["canonical_article_revision_id"]),
    }


def _already_published(cur, article, key, expected, reviewer_id, rationale, *, allowlist, fixture_mode):
    current = cur.execute("""
        SELECT j.checkpoint, j.source_fetch_job_id, r.source_revision_id, r.canonical_article_revision_id,
               r.rewrite_result_hash, r.validation_hash
        FROM canonical_article_revisions r
        JOIN source_fetch_jobs j USING(transformation_key)
        JOIN catalog_article_current visible ON visible.canonical_revision_id=r.canonical_article_revision_id
        WHERE r.transformation_key=%s AND j.status='completed' AND r.status='published'
          AND r.canonical_article_revision_id=%s AND r.source_revision_id=%s
        """, (key, article["current_canonical_revision_id"], article["current_source_revision_id"])).fetchone()
    if current is None:
        return None
    approval = current["checkpoint"].get("media_repair", {})
    reviewer_kind = authorize_reviewer(allowlist, reviewer_id, drafting_identities=(), fixture_mode=fixture_mode)
    if (digest_json(approval) != digest_json({"manifest": expected, "reviewer": reviewer_id, "reviewer_kind": reviewer_kind, "rationale": rationale})
        or current["rewrite_result_hash"] != expected["repaired_published_document_hash"]
        or current["validation_hash"] != expected["repaired_validation_hash"]):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_STALE")
    return _result(current, "already_published")


def publish_retained_media_repair(repo, *, expected, object_store, reviewer_id, allowlist, rationale,
                                  fixture_mode=False, hooks=None, svg_archive=None):
    """Rebuild the reviewed correction under owner/source rights locks, then publish."""
    if (not isinstance(expected, dict)
        or expected.get("schema") not in (SCHEMA, ORDINAL_SCHEMA, TABLE_SPAN_SCHEMA, SVG_RECOVERY_SCHEMA)
        or type(expected.get("request_generation")) is not int or not _substantive(rationale)):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_APPROVAL_INVALID")
    article_id = UUID(expected["article_id"])
    source_revision_id = UUID(expected["source_revision_id"])
    ordinals = expected["schema"] == ORDINAL_SCHEMA
    table_spans = expected["schema"] == TABLE_SPAN_SCHEMA
    svg_recovery = expected["schema"] == SVG_RECOVERY_SCHEMA
    if svg_recovery != (svg_archive is not None):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_APPROVAL_INVALID")
    binding, captured, blobs = _preview_repair_source(
        repo, source_revision_id, object_store=object_store, ordinals=ordinals,
        table_spans=table_spans, svg_archive=svg_archive,
    )
    if binding.canonical_article_id != article_id:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_ARTICLE_MISMATCH")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        _fixture_allowed(cur, fixture_mode)
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (article_id,)).fetchone()
        if article is None:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_ARTICLE_MISMATCH")
        if table_spans or svg_recovery:
            locked = load_table_replay_binding(cur, source_revision_id, lock=True)
        else:
            locked = load_media_replay_binding(cur, source_revision_id, lock=True, ordinals=ordinals)
        if binding != locked:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_SOURCE_CHANGED")
        if not (table_spans or svg_recovery):
            validate_media_replay_result(locked, captured, ordinals=ordinals)
        key = transformation_key(
            article_id, captured.source_fingerprint if svg_recovery else locked.source_fingerprint,
            article["target_normalization_version"],
            article["target_rewrite_profile_version"], projection_version=captured.projection_version,
        )
        repeated = _already_published(
            cur, article, key, expected, reviewer_id, rationale, allowlist=allowlist, fixture_mode=fixture_mode,
        )
        if repeated is not None:
            return repeated
        if (table_spans or svg_recovery) and cur.execute(
            "SELECT 1 FROM schema_migrations WHERE version='045_article_source_projection_v5'"
        ).fetchone() is None:
            raise ValueError("SOURCE_TABLE_REPLAY_SCHEMA_REQUIRED")
        _require_no_active_normal_job(cur, article_id)
        plan = _plan(cur, article, locked, captured, fixture_mode=fixture_mode, lock=True,
                     ordinals=ordinals, table_spans=table_spans, svg_recovery=svg_recovery)
        if digest_json(plan.manifest) != digest_json(expected):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_STALE")
        reviewer_kind = authorize_reviewer(
            allowlist, reviewer_id, drafting_identities=plan.drafting_identities, fixture_mode=fixture_mode,
        )
        approval = {"manifest": expected, "reviewer": reviewer_id, "reviewer_kind": reviewer_kind, "rationale": rationale}
        if svg_recovery:
            from .source_svg_recovery import check_svg_recovery_rights

            check_svg_recovery_rights(cur, captured, lock=True)
            for object_key, (payload, media_type) in blobs.items():
                object_store.put_object(object_key, payload, media_type)
        return _publish(cur, article, captured, key, plan, approval, hooks=hooks)


def _publish(cur, article, captured, key, plan, approval, *, hooks):
    article_id = article["canonical_article_id"]
    generation = article["request_generation"] + 1
    job_id, revision_id = uuid4(), uuid4()
    method = plan.repair.provenance["transformation_method"]
    if cur.execute("""
        SELECT 1 FROM canonical_article_source_revisions
        WHERE canonical_article_id=%s AND source_fingerprint=%s AND projection_version=%s
        """, (article_id, captured.source_fingerprint, captured.projection_version)).fetchone():
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PROJECTION_CONFLICT")
    job = cur.execute("""
        INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,
            source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,
            status,phase,job_kind,canonical_article_id,request_generation,normalization_version,
            rewrite_profile_version,checkpoint)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'completed','completed','article',%s,%s,%s,%s,%s)
        RETURNING correlation_id
        """, (job_id, article["provider_slug"], article["vehicle_id"], article["source_vehicle_ref"],
              article["source_article_ref"], method, article["provider_slug"], "published-media:" + key,
              article_id, generation, plan.previous["normalization_version"], plan.previous["rewrite_profile_version"],
              Jsonb({"media_repair": approval}))).fetchone()
    source_id = _persist_article_capture(cur, article_id, job_id, generation, captured, verify_existing=True)
    if method == SVG_RECOVERY_METHOD:
        from .source_svg_recovery import check_svg_recovery_rights

        check_svg_recovery_rights(cur, captured, lock=True, require_existing=True)
    cur.execute("UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s WHERE source_fetch_job_id=%s",
                (source_id, key, job_id))
    repair = plan.repair
    metadata = {
        **repair.provenance,
        "model": plan.previous["model_metadata"]["model"],
        "original_attempt_id": plan.manifest["original_attempt_id"],
        "original_prompt_hash": plan.manifest["original_prompt_hash"],
        "original_canonical_revision_id": plan.manifest["canonical_revision_id"],
    }
    cur.execute("""
        INSERT INTO canonical_article_revisions(canonical_article_revision_id,canonical_article_id,source_revision_id,
            transformation_key,normalization_version,rewrite_profile_version,status,published_at,review_status,
            normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,
            canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata)
        VALUES (%s,%s,%s,%s,%s,%s,'published',clock_timestamp(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (revision_id, article_id, source_id, key, plan.previous["normalization_version"],
              plan.previous["rewrite_profile_version"], plan.review_status, Jsonb(plan.normalized),
              digest_json(plan.normalized), Jsonb(repair.document), repair.projection["body"],
              Jsonb(repair.projection["steps"]), Jsonb(repair.projection["images"]), Jsonb(repair.validation.report),
              digest_json(repair.validation.report), digest_json(repair.document), Jsonb(metadata)))
    for link in plan.retained_links:
        cur.execute("""
            INSERT INTO canonical_article_link_bindings(canonical_article_id,source_revision_id,
                canonical_article_revision_id,block_id,label_sha256,authored_id_sha256,target_ref_sha256,body_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (article_id, source_id, revision_id, link["block_id"], link["label_sha256"],
                  link["authored_id_sha256"], link["target_ref_sha256"], link["body_sha256"]))
    if plan.review_status == "APPROVED":
        reason = {"schema": plan.manifest["schema"], "approval": approval, "source_revision_id": str(source_id)}
        cur.execute("""
            INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,
                authorized_reviewer_id,decision,reason) VALUES (%s,%s,%s,'APPROVED',%s)
            """, (uuid4(), revision_id, approval["reviewer"], json.dumps(reason, sort_keys=True)))
    cur.execute("""
        UPDATE canonical_articles SET current_job_id=%s,request_generation=%s,current_source_revision_id=%s,
            current_canonical_revision_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s
        """, (job_id, generation, source_id, revision_id, article_id))
    cur.execute("""
        INSERT INTO publication_events(publication_event_id,event_type,event_version,canonical_article_id,
            canonical_article_revision_id,correlation_id,idempotency_key,payload,producer)
        VALUES (%s,'catalog.article.published',1,%s,%s,%s,%s,%s,'ingestion-worker')
        """, (uuid4(), article_id, revision_id, job["correlation_id"], "catalog.article.published:" + key,
              Jsonb({"source_revision_id": str(source_id), "review_status": plan.review_status})))
    if hooks is not None:
        hooks("inside_publication")
    return _result({"source_fetch_job_id": job_id, "source_revision_id": source_id,
                    "canonical_article_revision_id": revision_id}, "published")
