"""Durable generic source jobs. PostgreSQL time/locks are lifecycle authority."""

from hashlib import sha256
import re
from uuid import UUID, uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, AUTOMATIC_REWRITE_PROFILES, MAX_CORRECTION_CALLS,
    NORMALIZATION_VERSION, RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE, RETAINED_NOTE_LABEL_REPAIR_PROFILE,
    RETAINED_REQUIRED_ACTION_REPAIR_PROFILE, RETAINED_ROTATION_REMOVAL_REPAIR_PROFILE,
    SOURCE_BOUND_CORRECTION_PROFILE, SOURCE_BOUND_REWRITE_PROFILE,
    EnsureResult, JobLease, digest_json, transformation_key,
)


class LeaseLost(RuntimeError):
    pass


class ProfileRefreshRequired(ValueError):
    code = "PROFILE_REFRESH_REQUIRED"


ACTIVE = ("pending", "processing", "failed")
ARTICLE_JOB_CHANNEL = "autodata_article_job"
_OPERATOR_REWRITE_PROFILES = (
    SOURCE_BOUND_CORRECTION_PROFILE, RETAINED_NOTE_LABEL_REPAIR_PROFILE, RETAINED_REQUIRED_ACTION_REPAIR_PROFILE,
    RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE, RETAINED_ROTATION_REMOVAL_REPAIR_PROFILE,
)
STAGED_MEDIA_REFRESH = "staged_media_refresh"
REQUIRE_POSITIONED_SVG_REFRESH = "require_positioned_svg_refresh"


def staged_media_refresh_binding(article, source_revision_id):
    return {
        "version": 1,
        "source_revision_id": str(source_revision_id),
        "prior_source_revision_id": str(article["current_source_revision_id"]),
        "prior_canonical_revision_id": str(article["current_canonical_revision_id"]),
    }


def transform_source_matches(article, job):
    """Match a job to the served source or to its exact staged replacement."""
    if article is None:
        return False
    candidate = job["source_revision_id"]
    if STAGED_MEDIA_REFRESH not in job["checkpoint"]:
        return article["current_source_revision_id"] == candidate
    return bool(
        article["provider_slug"] == job["provider_slug"] == "bankone"
        and article["current_source_revision_id"]
        and article["current_canonical_revision_id"]
        and candidate and candidate != article["current_source_revision_id"]
        and job["checkpoint"][STAGED_MEDIA_REFRESH] == staged_media_refresh_binding(article, candidate)
    )


def _cursor(conn):
    return conn.cursor(row_factory=dict_row)


def _result(cur, article, job, created=False):
    delay = (
        cur.execute(
            "SELECT CASE WHEN %s::timestamptz IS NOT NULL THEN GREATEST(0,ceil(extract(epoch FROM %s::timestamptz-clock_timestamp()))::int) END AS delay",
            (job["next_attempt_at"], job["next_attempt_at"]),
        ).fetchone()["delay"]
        if job["status"] == "failed" and job["retryable"]
        else None
    )
    state = job["status"]
    published = None
    if article:
        view = cur.execute(
            "SELECT canonical_revision_id,processing_error_code FROM catalog_article_current WHERE canonical_article_id=%s",
            (article["canonical_article_id"],),
        ).fetchone()
        if view:
            published = view["canonical_revision_id"]
            if view["processing_error_code"] == "CANONICAL_REVIEW_REJECTED":
                state = "needs_review"
    return EnsureResult(
        job["source_fetch_job_id"],
        article["canonical_article_id"] if article else None,
        state,
        job["source_revision_id"],
        delay,
        published,
        created,
    )


def _ensure_locked(cur, article, *, force_new=False):
    if article["current_job_id"] and not force_new:
        job = cur.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (article["current_job_id"],),
        ).fetchone()
        # The authoritative pointer may be to an older terminal transformation.
        if job:
            return _result(cur, article, job)
    if article["target_rewrite_profile_version"] in _OPERATOR_REWRITE_PROFILES:
        raise ProfileRefreshRequired()
    job_id = uuid4()
    job = cur.execute(
        """INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,request_generation,normalization_version,rewrite_profile_version)
    VALUES (%s,%s,%s,%s,%s,'lifecycle-v1',%s,%s,'pending','article',%s,%s,%s,%s) RETURNING *""",
        (
            job_id,
            article["provider_slug"],
            article["vehicle_id"],
            article["source_vehicle_ref"],
            article["source_article_ref"],
            article["provider_slug"],
            f'article:{article["canonical_article_id"]}:{article["request_generation"]}',
            article["canonical_article_id"],
            article["request_generation"],
            article["target_normalization_version"],
            article["target_rewrite_profile_version"],
        ),
    ).fetchone()
    cur.execute(
        "UPDATE canonical_articles SET current_job_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s",
        (job_id, article["canonical_article_id"]),
    )
    # PostgreSQL delivers this empty wake-up only after the job commits.
    cur.execute("SELECT pg_notify(%s, '')", (ARTICLE_JOB_CHANNEL,))
    return _result(cur, article, job, True)


def ensure_article_job(
    repo, canonical_article_id, *, normalization_version, rewrite_profile_version
):
    with repo.connect() as conn, _cursor(conn) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise KeyError("canonical article not found")
        if (normalization_version, rewrite_profile_version) != (
            article["target_normalization_version"],
            article["target_rewrite_profile_version"],
        ):
            raise ProfileRefreshRequired()
        return _ensure_locked(cur, article)


def refresh_article_job(
    repo,
    canonical_article_id,
    *,
    actor,
    reason,
    normalization_version=None,
    rewrite_profile_version=None,
    expected_source_revision_id=None,
    expected_published_revision_id=None,
):
    if not actor.strip() or not reason.strip():
        raise ValueError("refresh actor and reason required")
    if rewrite_profile_version in _OPERATOR_REWRITE_PROFILES:
        raise ProfileRefreshRequired()
    if expected_published_revision_id is not None and (
        expected_source_revision_id is None or normalization_version is not None or rewrite_profile_version is not None
    ):
        raise ValueError("LEGACY_SVG_REFRESH_BINDING_INVALID")
    with repo.connect() as conn, _cursor(conn) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise KeyError("canonical article not found")
        checkpoint = {"refresh_actor": actor, "refresh_reason": reason}
        if expected_published_revision_id is not None:
            if (article["provider_slug"] != "bankone"
                or str(article["current_source_revision_id"]) != str(expected_source_revision_id)
                or str(article["current_canonical_revision_id"]) != str(expected_published_revision_id)
                or not source_bound_rewrite_source_allowed(cur, article, article["current_source_revision_id"])):
                raise ValueError("LEGACY_SVG_REFRESH_BINDING_INVALID")
            checkpoint[REQUIRE_POSITIONED_SVG_REFRESH] = {
                "source_revision_id": str(expected_source_revision_id),
                "canonical_revision_id": str(expected_published_revision_id),
            }
        elif expected_source_revision_id is not None:
            if str(article["current_source_revision_id"]) != str(expected_source_revision_id):
                raise ValueError("AUTOMATIC_SOURCE_CHANGED")
            if article["current_canonical_revision_id"] is not None:
                raise ValueError("AUTOMATIC_ALREADY_PUBLISHED")
        if article["current_job_id"]:
            job = cur.execute(
                "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                (article["current_job_id"],),
            ).fetchone()
            if job["status"] in ACTIVE:
                if expected_published_revision_id is not None and (
                    job["checkpoint"].get(REQUIRE_POSITIONED_SVG_REFRESH)
                    != checkpoint[REQUIRE_POSITIONED_SVG_REFRESH]
                ):
                    raise ValueError("LEGACY_SVG_REFRESH_BUSY")
                return _result(cur, article, job)
        if rewrite_profile_version is None and article["target_rewrite_profile_version"] in _OPERATOR_REWRITE_PROFILES:
            raise ProfileRefreshRequired()
        article = cur.execute(
            """UPDATE canonical_articles SET request_generation=request_generation+1,
        target_normalization_version=COALESCE(%s,target_normalization_version),target_rewrite_profile_version=COALESCE(%s,target_rewrite_profile_version)
        WHERE canonical_article_id=%s RETURNING *""",
            (normalization_version, rewrite_profile_version, canonical_article_id),
        ).fetchone()
        result = _ensure_locked(cur, article, force_new=True)
        cur.execute(
            "UPDATE source_fetch_jobs SET checkpoint=%s WHERE source_fetch_job_id=%s",
            (Jsonb(checkpoint), result.job_id),
        )
        return result


def source_bound_rewrite_source_allowed(
    cur, article, source_revision_id, *, predecessor_observation=None, require_current_observation_scope=False,
    allow_unscoped=False,
):
    """Check exact-scope source visibility while the caller owns the article lock."""
    if (article["current_source_revision_id"] != source_revision_id
        or article["provider_slug"] not in ("bankone", "banktwo")
        or (article["vehicle_configuration_id"] is None and not allow_unscoped)
        or article["membership_status"] != "active" or article["takedown_status"] != "active"):
        return False
    allowed = cur.execute("""
        SELECT 1 FROM catalog_article_current v
        JOIN canonical_article_source_revisions s USING(source_revision_id,canonical_article_id)
        JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=%s
        JOIN LATERAL (
            SELECT descriptor_source_snapshot_id,resolution_source_snapshot_id
            FROM canonical_article_source_observations o
            WHERE o.source_revision_id=s.source_revision_id AND o.canonical_article_id=s.canonical_article_id
            ORDER BY o.captured_at,o.source_observation_id LIMIT 1
        ) authored ON true
        JOIN source_snapshots retained_descriptor ON retained_descriptor.source_snapshot_id=authored.descriptor_source_snapshot_id
        JOIN source_snapshots retained_resolution ON retained_resolution.source_snapshot_id=authored.resolution_source_snapshot_id
        LEFT JOIN vehicle_configurations c ON c.vehicle_configuration_id=v.vehicle_configuration_id
        LEFT JOIN vehicle_identity_bases b ON b.vehicle_identity_base_id=c.vehicle_identity_base_id
        WHERE v.canonical_article_id=%s AND s.source_revision_id=%s
          AND descriptor.takedown_status='active' AND v.takedown_status='active'
          AND retained_descriptor.takedown_status='active' AND retained_resolution.takedown_status='active'
          AND ((v.vehicle_configuration_id IS NULL AND %s)
               OR (c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected'))
          AND v.availability='available'
          AND CASE WHEN jsonb_typeof(s.source_document->'blocks')='array'
                   THEN jsonb_array_length(s.source_document->'blocks')>0 ELSE false END
          AND NOT EXISTS (
              SELECT 1 FROM source_artifacts a
              WHERE a.extraction_status='quarantined'
              AND (a.source_snapshot_id=s.body_source_snapshot_id OR EXISTS (
                  SELECT 1 FROM jsonb_array_elements(s.resource_manifest) resource
                  JOIN source_snapshots asset ON asset.content_sha256::text=resource->>'sha256'
                  WHERE a.source_snapshot_id=asset.source_snapshot_id
              ))
          )
          AND NOT EXISTS (
              SELECT 1 FROM source_review_items q WHERE q.item_kind='quarantine' AND q.status<>'approved'
              AND (q.source_snapshot_ids ?| ARRAY[descriptor.source_snapshot_id::text,
                       authored.descriptor_source_snapshot_id::text, authored.resolution_source_snapshot_id::text,
                       s.body_source_snapshot_id::text]
                   OR EXISTS (
                       SELECT 1 FROM jsonb_array_elements(s.resource_manifest) resource
                       JOIN source_snapshots asset ON asset.content_sha256::text=resource->>'sha256'
                       WHERE q.source_snapshot_ids ? asset.source_snapshot_id::text
                   ))
          )
        """, (article["descriptor_source_snapshot_id"], article["canonical_article_id"], source_revision_id,
              allow_unscoped)).fetchone() is not None
    if not allowed or predecessor_observation is None:
        return allowed and not require_current_observation_scope
    observation_id, job_id, generation = predecessor_observation
    return cur.execute("""
        SELECT 1 FROM canonical_article_source_observations o
        JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=o.descriptor_source_snapshot_id
        JOIN source_snapshots resolution ON resolution.source_snapshot_id=o.resolution_source_snapshot_id
        WHERE o.source_observation_id=%s AND o.source_fetch_job_id=%s AND o.request_generation=%s
          AND o.canonical_article_id=%s AND o.source_revision_id=%s
          AND descriptor.takedown_status='active' AND resolution.takedown_status='active'
          AND (NOT %s OR EXISTS (
              SELECT 1 FROM canonical_articles a
              JOIN vehicles v ON v.vehicle_id=a.vehicle_id
              LEFT JOIN vehicle_configurations c ON c.vehicle_configuration_id=a.vehicle_configuration_id
                                                AND c.vehicle_id=a.vehicle_id
              LEFT JOIN vehicle_identity_bases b ON b.vehicle_identity_base_id=c.vehicle_identity_base_id
                                                 AND b.vehicle_id=a.vehicle_id
              JOIN catalog_article_provider_scopes p ON p.scope_key=a.scope_key
                                                    AND p.provider_slug=a.provider_slug
                                                    AND p.source_vehicle_ref=a.source_vehicle_ref
              WHERE a.canonical_article_id=o.canonical_article_id
                AND a.descriptor_source_snapshot_id=o.descriptor_source_snapshot_id
                AND p.resolution_source_snapshot_id=o.resolution_source_snapshot_id
                AND (CASE WHEN a.vehicle_configuration_id IS NULL THEN v.region ELSE b.region END)
                    =o.captured_context->'vehicle'->>'region'
          ))
          AND NOT EXISTS (
              SELECT 1 FROM source_review_items q WHERE q.item_kind='quarantine' AND q.status<>'approved'
              AND q.source_snapshot_ids ?| ARRAY[descriptor.source_snapshot_id::text,resolution.source_snapshot_id::text]
          )
        """, (observation_id, job_id, generation, article["canonical_article_id"], source_revision_id,
              require_current_observation_scope)).fetchone() is not None


def schedule_source_bound_rewrite(
    repo, canonical_article_id, *, expected_job_id, expected_source_revision_id, actor, reason,
):
    """Queue one new-profile rewrite of an exact, unchanged, unpublished source."""
    return _schedule_source_bound_job(
        repo, canonical_article_id, expected_job_id=expected_job_id,
        expected_source_revision_id=expected_source_revision_id, actor=actor, reason=reason,
        prior_profile=AUTOMATIC_REWRITE_PROFILE, next_profile=SOURCE_BOUND_REWRITE_PROFILE,
    )


def source_bound_correction_prior_attempt(cur, prior_job, *, first_draft=False):
    """Rebuild immutable draft evidence independently of today's catalog pointers."""
    rejected = "SOURCE_BOUND_CORRECTION_PRIOR_DRAFT_INVALID"
    profile = AUTOMATIC_REWRITE_PROFILE if first_draft else SOURCE_BOUND_REWRITE_PROFILE
    if (prior_job is None or prior_job["job_kind"] != "article"
        or prior_job["rewrite_profile_version"] != profile
        or prior_job["status"] != "dead_letter" or prior_job["phase"] != "validating"
        or prior_job["retryable"] or prior_job["lease_owner"] is not None
        or not prior_job["source_revision_id"] or not prior_job["transformation_key"]):
        raise ValueError(rejected)
    checkpoint = prior_job["checkpoint"]
    source = checkpoint.get("normalized_document")
    if (not isinstance(source, dict) or not isinstance(source.get("blocks"), list)
        or not source["blocks"] or not checkpoint.get("rewrite_error_code")
        or prior_job["error_code"] != checkpoint["rewrite_error_code"]
        or checkpoint.get("normalized_hash") != digest_json(source)):
        raise ValueError(rejected)
    observed = None
    context = {}
    if first_draft:
        if prior_job["retry_count"] != 1 or cur.execute("""
            SELECT count(*) AS total FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s
            """, (prior_job["source_fetch_job_id"],)).fetchone()["total"] != 1:
            raise ValueError(rejected)
        observed = cur.execute("""
            SELECT o.source_observation_id,o.captured_context->'vehicle' AS vehicle,o.captured_at
            FROM canonical_article_source_observations o
            WHERE o.source_fetch_job_id=%s AND o.canonical_article_id=%s AND o.source_revision_id=%s
              AND o.request_generation=%s
            """, (prior_job["source_fetch_job_id"], prior_job["canonical_article_id"], prior_job["source_revision_id"],
                  prior_job["request_generation"])).fetchone()
        if (observed is None or not isinstance(observed["vehicle"], dict)
            or observed["captured_at"] < prior_job["created_at"]):
            raise ValueError(rejected)
        context = observed["vehicle"]
    attempts = cur.execute("""SELECT r.* FROM canonical_article_rewrite_attempts r
        JOIN canonical_article_revisions c
          ON c.canonical_article_revision_id=r.canonical_article_revision_id
        WHERE r.source_fetch_job_id=%s AND r.lease_token=%s
          AND r.attempt_number=%s AND r.status='failed' AND r.profile_version=%s
          AND r.dispatched_at IS NOT NULL AND r.completed_at IS NOT NULL
          AND r.error_code=%s AND r.input_hash=%s
          AND c.canonical_article_id=%s AND c.source_revision_id=%s AND c.transformation_key=%s
          AND c.rewrite_profile_version=%s AND c.normalization_version=%s AND c.status='building'
          AND c.canonical_article_revision_id::text=%s
          AND c.normalized_source_hash=r.input_hash AND c.normalized_source_document=%s
          AND c.canonical_document=c.normalized_source_document AND c.rewrite_result_hash=r.input_hash
          AND r.provider='inception'
          AND c.model_metadata->>'provider'=r.provider AND c.model_metadata->>'model'=r.model
          AND c.model_metadata->>'profile_version'=r.profile_version
          AND c.model_metadata->>'prompt_hash'=r.prompt_hash
        """, (prior_job["source_fetch_job_id"], prior_job["lease_token"], prior_job["retry_count"],
              profile, prior_job["error_code"], checkpoint["normalized_hash"],
              prior_job["canonical_article_id"], prior_job["source_revision_id"], prior_job["transformation_key"],
              profile, prior_job["normalization_version"], checkpoint.get("candidate_revision_id"),
              Jsonb(source))).fetchall()
    if len(attempts) != 1:
        raise ValueError(rejected)
    attempt = attempts[0]
    response = attempt["response"]
    if (not isinstance(response, dict) or set(response) != {"introduction", "replacements"}
        or not isinstance(response["replacements"], list) or not response["replacements"]
        or attempt["response_hash"] != digest_json(response)):
        raise ValueError(rejected)
    from .procedure_rewrite_auto import _auto_prompt_version
    guard_version = _auto_prompt_version(source, context=context, prompt_hash=attempt["prompt_hash"],
                                         profile_version=profile)
    if guard_version is None:
        raise ValueError(rejected)
    if first_draft:
        from .procedure_rewrite_auto import _keeps_authored_note_labels
        from .procedure_rewrite_correction import _initial_draft

        if (not isinstance(response["introduction"], str) or not response["introduction"].strip()
            or not observed["captured_at"] <= attempt["dispatched_at"] <= attempt["completed_at"]):
            raise ValueError(rejected)
        try:
            _initial_draft(source, response, preserve_notes=_keeps_authored_note_labels(guard_version))
        except ValueError:
            raise ValueError(rejected) from None
        return {**attempt, "guard_version": guard_version, "observation_id": observed["source_observation_id"]}
    return {**attempt, "guard_version": guard_version}


def schedule_source_bound_correction(
    repo, canonical_article_id, *, expected_job_id, expected_source_revision_id, actor, reason, model_call_budget,
    by_sentence=False, first_draft=False,
):
    """Queue an explicit correction of an unchanged source and its bound failed draft."""
    from .procedure_rewrite_sentence_correction import MAX_SENTENCE_CORRECTION_CALLS
    limit = MAX_SENTENCE_CORRECTION_CALLS if by_sentence else MAX_CORRECTION_CALLS
    if (type(by_sentence) is not bool or type(first_draft) is not bool or (first_draft and not by_sentence)
        or type(model_call_budget) is not int
        or not 1 <= model_call_budget <= limit):
        raise ValueError("SOURCE_BOUND_CORRECTION_BUDGET_INVALID")
    return _schedule_source_bound_job(
        repo, canonical_article_id, expected_job_id=expected_job_id,
        expected_source_revision_id=expected_source_revision_id, actor=actor, reason=reason,
        prior_profile=AUTOMATIC_REWRITE_PROFILE if first_draft else SOURCE_BOUND_REWRITE_PROFILE,
        next_profile=SOURCE_BOUND_CORRECTION_PROFILE,
        model_call_budget=model_call_budget, by_sentence=by_sentence,
    )


def bankone_archive_body_binding(cur, source_id, observation_id, *, lock=False):
    from .source_media_replay import _check_review_quarantine, _key, _load_snapshots

    mismatch = "FIRST_DRAFT_ARCHIVE_STRUCTURE_MISMATCH"
    row = cur.execute("""
        SELECT s.body_source_snapshot_id, s.resource_manifest, o.resource_provenance,
               o.descriptor_source_snapshot_id, o.resolution_source_snapshot_id
        FROM canonical_article_source_revisions s
        JOIN canonical_article_source_observations o USING (source_revision_id, canonical_article_id)
        JOIN canonical_articles a USING (canonical_article_id)
        WHERE s.source_revision_id=%s AND o.source_observation_id=%s
          AND a.provider_slug='bankone' AND a.membership_status='active' AND a.takedown_status='active'
    """, (source_id, observation_id)).fetchone()
    if row is None:
        raise ValueError(mismatch)
    try:
        [resource] = [item for item in row["resource_provenance"] if item["role"] == "body"]
        [manifest] = [item for item in row["resource_manifest"] if item["role"] == "body"]
        snapshot_id = row["body_source_snapshot_id"]
        resource_ids = {UUID(item["source_snapshot_id"]) for item in row["resource_provenance"]}
        if (resource["provider"] != "bankone" or resource["media_type"] != "text/html"
            or UUID(resource["source_snapshot_id"]) != snapshot_id
            or any(manifest[field] != resource[field] for field in ("sha256", "media_type", "opaque_ref"))):
            raise ValueError(mismatch)
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(mismatch) from None
    ids = resource_ids | {row["descriptor_source_snapshot_id"], row["resolution_source_snapshot_id"]}
    snapshots = _load_snapshots(cur, ids, resource_ids=resource_ids, lock=lock)
    _check_review_quarantine(cur, ids, lock=lock)
    [body] = [snapshot for snapshot in snapshots if snapshot.id == snapshot_id]
    if (body.digest != resource["sha256"] or body.artifact_digest != body.digest
        or body.object_key != resource["object_key"] or body.artifact_key != body.object_key
        or body.object_key != _key(body.digest) or body.media_type != "text/html"):
        raise ValueError(mismatch)
    return body


def bankone_first_draft_body_binding(cur, job, dispatched_at, *, require_current=False, lock=False):
    """Bind an automatic draft to the body captured by its own job."""
    mismatch = "FIRST_DRAFT_RECOVERY_BINDING_INVALID"
    if job["provider_slug"] != "bankone" or STAGED_MEDIA_REFRESH in job["checkpoint"]:
        raise ValueError(mismatch)
    observation = cur.execute("""
        SELECT source_observation_id,captured_at FROM canonical_article_source_observations
        WHERE source_fetch_job_id=%s AND canonical_article_id=%s AND source_revision_id=%s AND request_generation=%s
        """, (job["source_fetch_job_id"], job["canonical_article_id"], job["source_revision_id"],
              job["request_generation"])).fetchone()
    if (observation is None or dispatched_at is None
        or not job["created_at"] <= observation["captured_at"] <= dispatched_at):
        raise ValueError(mismatch)
    observation_id = observation["source_observation_id"]
    model_observation = job["checkpoint"].get("rollout_model_observation_id")
    if model_observation is not None and model_observation != str(observation_id):
        raise ValueError(mismatch)
    if require_current:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (job["canonical_article_id"],)).fetchone()
        if (article is None or article["current_job_id"] != job["source_fetch_job_id"]
            or article["request_generation"] != job["request_generation"]
            or not source_bound_rewrite_source_allowed(
                cur, article, job["source_revision_id"], require_current_observation_scope=True,
                predecessor_observation=(observation_id, job["source_fetch_job_id"], job["request_generation"]),
                allow_unscoped=model_observation is not None,
            )):
            raise ValueError(mismatch)
    return observation_id, bankone_archive_body_binding(
        cur, job["source_revision_id"], observation_id, lock=lock,
    )


def load_bankone_structure(read_retained_object, binding, source, observation_id, *, structure_version):
    """Read a bound object outside the database transaction."""
    from .bankone_first_draft_structure import extract_bankone_structure
    from .source_media_replay import _MAX_OBJECT_BYTES

    try:
        body = read_retained_object(binding.object_key, max_bytes=_MAX_OBJECT_BYTES)
    except Exception:
        raise ValueError("FIRST_DRAFT_ARCHIVE_BODY_UNAVAILABLE") from None
    if (not isinstance(body, bytes) or not 0 < len(body) <= _MAX_OBJECT_BYTES
        or sha256(body).hexdigest() != binding.digest):
        raise ValueError("FIRST_DRAFT_ARCHIVE_STRUCTURE_MISMATCH")
    return {"observation_id": str(observation_id), "body_sha256": binding.digest,
            "proof": extract_bankone_structure(source, body, version=structure_version)}


def read_bankone_archive_structure(repo, canonical_id, prior_id, source_id, *, object_store, structure_version=1):
    """Extract exact authored slots from the retained, rights-checked HTML body."""
    canonical_id, prior_id, source_id = (UUID(str(value)) for value in (canonical_id, prior_id, source_id))
    with repo.connect() as conn, _cursor(conn) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (canonical_id,)).fetchone()
        if (article is None or prior is None or prior["canonical_article_id"] != canonical_id
            or prior["source_revision_id"] != source_id):
            raise ValueError("FIRST_DRAFT_ARCHIVE_STRUCTURE_MISMATCH")
        attempt = source_bound_correction_prior_attempt(cur, prior, first_draft=True)
        observation_id = attempt["observation_id"]
        if not source_bound_rewrite_source_allowed(
            cur, article, source_id, predecessor_observation=(observation_id, prior_id, prior["request_generation"]),
            require_current_observation_scope=article["current_job_id"] == prior_id,
        ):
            raise ValueError("SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE")
        binding = bankone_archive_body_binding(cur, source_id, observation_id)
        source = prior["checkpoint"]["normalized_document"]
    return load_bankone_structure(
        getattr(object_store, "get_object", None), binding, source, observation_id, structure_version=structure_version,
    )


def publish_source_bound_first_draft(
    repo, canonical_article_id, *, expected_job_id, expected_source_revision_id, recovery_method,
    expected_recovery_hash, actor, reason, hooks=None, object_store=None,
):
    """Publish a checked first-draft recovery from its saved response in one transaction."""
    from .procedure_rewrite_recovery import ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS, BANKONE_ARCHIVE_STRUCTURE_VERSIONS

    if (recovery_method not in ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS
        or not isinstance(expected_recovery_hash, str)
        or not re.fullmatch(r"[a-f0-9]{64}", expected_recovery_hash)):
        raise ValueError("FIRST_DRAFT_ARCHIVE_RECOVERY_MISMATCH")
    archive = {"method": recovery_method, "output_hash": expected_recovery_hash}
    if structure_version := BANKONE_ARCHIVE_STRUCTURE_VERSIONS.get(recovery_method):
        if object_store is None:
            raise ValueError("FIRST_DRAFT_ARCHIVE_BODY_UNAVAILABLE")
        archive["bankone_structure"] = read_bankone_archive_structure(
            repo, canonical_article_id, expected_job_id, expected_source_revision_id, object_store=object_store,
            structure_version=structure_version,
        )
    return _schedule_source_bound_job(
        repo, canonical_article_id, expected_job_id=expected_job_id,
        expected_source_revision_id=expected_source_revision_id, actor=actor, reason=reason,
        prior_profile=AUTOMATIC_REWRITE_PROFILE, next_profile=SOURCE_BOUND_CORRECTION_PROFILE,
        model_call_budget=0, archived_recovery=archive,
        hooks=hooks,
    )


def _schedule_source_bound_job(
    repo, canonical_article_id, *, expected_job_id, expected_source_revision_id, actor, reason,
    prior_profile, next_profile, model_call_budget=None, by_sentence=False, archived_recovery=None, hooks=None,
):
    canonical_article_id, expected_job_id, expected_source_revision_id = (
        UUID(str(value)) for value in (canonical_article_id, expected_job_id, expected_source_revision_id)
    )
    if not all(
        isinstance(value, str) and value.strip() and len(value) <= limit
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
        for value, limit in ((actor, 256), (reason, 2048))
    ):
        raise ValueError("SOURCE_BOUND_REWRITE_AUDIT_INVALID")
    first_draft = model_call_budget is not None and prior_profile == AUTOMATIC_REWRITE_PROFILE
    binding = {
        "version": 1, "prior_job_id": str(expected_job_id),
        "source_revision_id": str(expected_source_revision_id), "actor": actor, "reason": reason,
    }
    with repo.connect() as conn, _cursor(conn) as cur:
        # Lifecycle writers lock the job before the article.
        prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                            (expected_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (canonical_article_id,)).fetchone()
        if (prior is None or article is None or prior["canonical_article_id"] != canonical_article_id
            or prior["job_kind"] != "article" or prior["provider_slug"] != article["provider_slug"]
            or prior["canonical_vehicle_id"] != article["vehicle_id"]
            or prior["source_vehicle_ref"] != article["source_vehicle_ref"]
            or prior["source_article_ref"] != article["source_article_ref"]
            or prior["source_revision_id"] != expected_source_revision_id
            or prior["normalization_version"] != NORMALIZATION_VERSION
            or article["target_normalization_version"] != NORMALIZATION_VERSION
            or prior["rewrite_profile_version"] != prior_profile
            or prior["status"] not in ("completed", "dead_letter", "needs_review") or prior["retryable"]
            or prior["lease_owner"] is not None):
            raise ValueError("SOURCE_BOUND_REWRITE_PRIOR_JOB_CHANGED")
        source_only = ("source_only_reprojection" in prior["checkpoint"]
                       or prior["error_code"] == "SOURCE_ONLY_REPROJECTION")
        predecessor_observation = None
        if source_only:
            # A source-only job owns an observation but never a transformation.
            if (prior_profile != AUTOMATIC_REWRITE_PROFILE or next_profile != SOURCE_BOUND_REWRITE_PROFILE
                or prior["checkpoint"].get("source_only_reprojection") is not True
                or prior["status"] != "needs_review" or prior["phase"] != "completed"
                or prior["error_code"] != "SOURCE_ONLY_REPROJECTION"
                or prior["transformation_key"] is not None or prior["next_attempt_at"] is not None):
                raise ValueError("SOURCE_BOUND_REWRITE_PRIOR_JOB_CHANGED")
            observation = cur.execute("""
                SELECT o.source_observation_id FROM canonical_article_source_observations o
                WHERE o.source_fetch_job_id=%s AND o.canonical_article_id=%s AND o.source_revision_id=%s
                  AND o.request_generation=%s
                  AND NOT EXISTS (
                      SELECT 1 FROM canonical_article_rewrite_attempts r WHERE r.source_fetch_job_id=o.source_fetch_job_id
                  )
                """, (expected_job_id, canonical_article_id, expected_source_revision_id,
                      prior["request_generation"])).fetchone()
            if observation is None:
                raise ValueError("SOURCE_BOUND_REWRITE_PRIOR_JOB_CHANGED")
            observation_id = observation["source_observation_id"]
            binding["prior_source_observation_id"] = str(observation_id)
            predecessor_observation = (observation_id, expected_job_id, prior["request_generation"])
        if not source_bound_rewrite_source_allowed(
            cur, article, expected_source_revision_id, predecessor_observation=predecessor_observation,
        ):
            raise ValueError("SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE")
        source = cur.execute("""
            SELECT source_fingerprint,projection_version FROM canonical_article_source_revisions
            WHERE source_revision_id=%s AND canonical_article_id=%s
            """, (expected_source_revision_id, canonical_article_id)).fetchone()
        key_inputs = (canonical_article_id, source["source_fingerprint"], NORMALIZATION_VERSION)
        projection = source["projection_version"]
        if not source_only and prior["transformation_key"] != transformation_key(
            *key_inputs, prior_profile, projection_version=projection,
        ):
            raise ValueError("SOURCE_BOUND_REWRITE_PRIOR_JOB_CHANGED")
        if model_call_budget is not None:
            if by_sentence:
                from .article_lifecycle_store import _require_source_bound_rewrite_rights
                from .procedure_rewrite_sentence_correction import SENTENCE_CORRECTION_METHOD
                _require_source_bound_rewrite_rights(cur, prior, article)
                binding["correction_method"] = SENTENCE_CORRECTION_METHOD
            if archived_recovery is not None:
                from .procedure_rewrite_correction import ARCHIVED_FIRST_DRAFT_METHOD

                binding["correction_method"] = ARCHIVED_FIRST_DRAFT_METHOD
                binding["archived_recovery"] = archived_recovery
            attempt = source_bound_correction_prior_attempt(cur, prior, first_draft=first_draft)
            binding.update(
                version=2, prior_attempt_id=str(attempt["rewrite_attempt_id"]),
                prior_response_hash=attempt["response_hash"], model_call_budget=model_call_budget,
            )
            if first_draft:
                observation_id = attempt["observation_id"]
                predecessor_observation = (observation_id, expected_job_id, prior["request_generation"])
                binding["first_draft_observation_id"] = str(observation_id)
        key = transformation_key(*key_inputs, next_profile, projection_version=projection)
        generation = article["request_generation"]
        rejoining = article["target_rewrite_profile_version"] == next_profile
        # Rejoining a saved job still requires access to its source. Only a
        # new admission requires the observed catalog scope to be current.
        if first_draft and not source_bound_rewrite_source_allowed(
            cur, article, expected_source_revision_id, predecessor_observation=predecessor_observation,
            require_current_observation_scope=not rejoining,
        ):
            raise ValueError("SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE")
        if rejoining:
            # No lock on the current rewrite job while holding the article row.
            current = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                                  (article["current_job_id"],)).fetchone()
            if (current and current["transformation_key"] == key
                and current["canonical_article_id"] == canonical_article_id
                and current["normalization_version"] == NORMALIZATION_VERSION
                and current["rewrite_profile_version"] == next_profile
                and current["source_revision_id"] == expected_source_revision_id
                and current["request_generation"] == generation
                and (archived_recovery is None or (
                    current["status"] == "completed" and article["current_canonical_revision_id"] is not None
                ))
                and current["checkpoint"].get("source_bound_rewrite") == {**binding, "prior_generation": generation - 1}):
                return _result(cur, article, current)
            raise ValueError("SOURCE_BOUND_REWRITE_ALREADY_SCHEDULED")
        if (article["target_rewrite_profile_version"] != prior_profile
            or article["current_job_id"] != expected_job_id or prior["request_generation"] > generation
            or ((source_only or first_draft) and prior["request_generation"] != generation)):
            raise ValueError("SOURCE_BOUND_REWRITE_CURRENT_JOB_CHANGED")
        if article["current_canonical_revision_id"] is not None or cur.execute("""
            SELECT 1 FROM canonical_article_revisions WHERE status='published'
              AND (transformation_key=%s OR (%s AND canonical_article_id=%s AND source_revision_id=%s))
            """, (prior["transformation_key"], source_only, canonical_article_id, expected_source_revision_id)).fetchone():
            raise ValueError("SOURCE_BOUND_REWRITE_ALREADY_PUBLISHED")
        if cur.execute("""
            SELECT 1 FROM source_fetch_jobs WHERE transformation_key=%s
            OR (canonical_article_id=%s AND job_kind='article' AND status=ANY(%s))
            """, (key, canonical_article_id, list(ACTIVE))).fetchone():
            raise ValueError("SOURCE_BOUND_REWRITE_ALREADY_SCHEDULED")
        checkpoint = {"source_bound_rewrite": {**binding, "prior_generation": generation}}
        generation += 1
        job = cur.execute("""
            INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,
                source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,
                request_generation,normalization_version,rewrite_profile_version,source_revision_id,
                transformation_key,phase,max_attempts,checkpoint)
            VALUES (%s,%s,%s,%s,%s,'lifecycle-v1',%s,%s,'pending','article',%s,%s,%s,%s,%s,%s,'normalizing',1,%s)
            RETURNING *
            """, (uuid4(), article["provider_slug"], article["vehicle_id"], article["source_vehicle_ref"],
                  article["source_article_ref"], article["provider_slug"], f"article:{canonical_article_id}:{generation}",
                  canonical_article_id, generation, NORMALIZATION_VERSION, next_profile,
                  expected_source_revision_id, key, Jsonb(checkpoint))).fetchone()
        cur.execute("""
            UPDATE canonical_articles SET current_job_id=%s,request_generation=%s,
                target_rewrite_profile_version=%s,updated_at=clock_timestamp()
            WHERE canonical_article_id=%s
            """, (job["source_fetch_job_id"], generation, next_profile, canonical_article_id))
        if archived_recovery is not None:
            from .article_lifecycle_store import _publish_source_bound_first_draft

            completed = _publish_source_bound_first_draft(
                cur, job, prior["checkpoint"]["normalized_document"], hooks=hooks,
            )
            return _result(cur, article, completed, True)
        cur.execute("SELECT pg_notify(%s, '')", (ARTICLE_JOB_CHANNEL,))
        return _result(cur, article, job, True)


def _mark_delivery_ambiguous(cur, job):
    # Only the locked row actually reclaimed/swept determines delivery ownership.
    # The transition and ambiguity accounting commit or roll back together.
    cur.execute("""UPDATE canonical_article_rewrite_attempts
        SET status='ambiguous',error_code='MODEL_DELIVERY_AMBIGUOUS',completed_at=clock_timestamp()
        WHERE source_fetch_job_id=%s AND lease_token=%s AND status='dispatched' AND response IS NULL""",
        (job["source_fetch_job_id"], job["lease_token"]))


_CORRECTION_JOB_BINDING_SQL = f"""(
    j.job_kind='article' AND j.rewrite_profile_version='{SOURCE_BOUND_CORRECTION_PROFILE}'
    AND j.max_attempts=1 AND j.source_revision_id IS NOT NULL AND j.transformation_key IS NOT NULL
    AND NOT (j.checkpoint ? 'new_article_rollout')
    AND j.checkpoint @> '{{"source_bound_rewrite":{{"version":2}}}}'::jsonb
    AND j.checkpoint->'source_bound_rewrite'->>'source_revision_id'=j.source_revision_id::text
    AND j.checkpoint->'source_bound_rewrite'->>'prior_job_id' IS NOT NULL
    AND j.checkpoint->'source_bound_rewrite'->>'prior_attempt_id' IS NOT NULL
    AND j.checkpoint->'source_bound_rewrite'->>'prior_response_hash' ~ '^[a-f0-9]{{64}}$'
    AND jsonb_typeof(j.checkpoint->'source_bound_rewrite'->'model_call_budget')='number'
)"""

_EXPLICIT_CORRECTION_SQL = f"""(
    j.rewrite_profile_version IS DISTINCT FROM '{SOURCE_BOUND_CORRECTION_PROFILE}'
    OR (%s::boolean AND {_CORRECTION_JOB_BINDING_SQL})
)"""

_SOURCE_BOUND_EXACT_JOB_SQL = f"""COALESCE((
    j.job_kind='article' AND j.max_attempts=1
    AND j.retry_count=1 AND j.source_revision_id IS NOT NULL
    AND j.checkpoint->'source_bound_rewrite'->>'source_revision_id'=j.source_revision_id::text
    AND ((j.rewrite_profile_version='{SOURCE_BOUND_REWRITE_PROFILE}'
          AND j.checkpoint @> '{{"source_bound_rewrite":{{"version":1}}}}'::jsonb)
         OR {_CORRECTION_JOB_BINDING_SQL})
), false)"""

_SOURCE_BOUND_CURRENT_OWNER_SQL = """a.canonical_article_id=j.canonical_article_id
    AND a.current_job_id=j.source_fetch_job_id AND a.request_generation=j.request_generation
    AND a.current_source_revision_id=j.source_revision_id
    AND a.target_rewrite_profile_version=j.rewrite_profile_version
    AND a.target_normalization_version=j.normalization_version"""


def _source_bound_no_delivery_sql(*, include_expired_prepared=False):
    expired_prepared = """OR (r.lease_token=j.lease_token AND r.status='prepared'
        AND r.error_code IS NULL AND r.completed_at IS NULL)""" if include_expired_prepared else ""
    return f"""NOT EXISTS (
        SELECT 1 FROM canonical_article_rewrite_attempts r
        WHERE r.source_fetch_job_id=j.source_fetch_job_id AND (
            r.profile_version=j.rewrite_profile_version AND r.attempt_number=1
            AND r.dispatched_at IS NULL AND r.response IS NULL AND r.response_hash IS NULL
            AND r.canonical_article_revision_id IS NULL
            AND ((r.lease_token<j.lease_token AND r.status='failed'
                  AND r.error_code='MODEL_NOT_DISPATCHED_LEASE_EXPIRED' AND r.completed_at IS NOT NULL)
                 {expired_prepared})
        ) IS NOT TRUE
    )"""


_MODEL_CONFIGURATION_NO_ATTEMPT_SQL = f"""(
    NOT EXISTS (
        SELECT 1 FROM canonical_article_rewrite_attempts r
        WHERE r.source_fetch_job_id=j.source_fetch_job_id
    )
    OR ({_SOURCE_BOUND_EXACT_JOB_SQL} AND {_source_bound_no_delivery_sql()})
)"""

_SOURCE_BOUND_NO_DELIVERY_EXPIRY_SQL = f"""{_SOURCE_BOUND_EXACT_JOB_SQL}
    AND j.phase IN ('normalizing','rewriting')
    AND j.checkpoint->>'candidate_revision_id' IS NULL
    AND j.checkpoint->>'rewrite_error_code' IS NULL
    AND {_source_bound_no_delivery_sql(include_expired_prepared=True)}"""


def _claim_source_bound_predispatch_resume(cur, worker_id, job_id):
    """Fence an expired exact-source job before its first model delivery."""
    job = cur.execute(f"""SELECT j.* FROM source_fetch_jobs j JOIN canonical_articles a
        ON {_SOURCE_BOUND_CURRENT_OWNER_SQL}
        WHERE (%s::uuid IS NULL OR j.source_fetch_job_id=%s)
          AND j.status='processing' AND j.lease_expires_at<clock_timestamp()
          AND {_EXPLICIT_CORRECTION_SQL}
          AND {_SOURCE_BOUND_NO_DELIVERY_EXPIRY_SQL}
        ORDER BY j.created_at,j.source_fetch_job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1""",
        (job_id, job_id, job_id is not None)).fetchone()
    if job is None:
        return None
    # A dispatch changes the attempt row under the job lock. Use a fresh read
    # after acquiring that lock to close a race with the initial selection.
    safe = cur.execute(f"""SELECT 1 FROM source_fetch_jobs j JOIN canonical_articles a
        ON {_SOURCE_BOUND_CURRENT_OWNER_SQL}
        WHERE j.source_fetch_job_id=%s AND {_source_bound_no_delivery_sql(include_expired_prepared=True)}
        FOR UPDATE OF a""", (job["source_fetch_job_id"],)).fetchone()
    if safe is None:
        return None
    cur.execute("""UPDATE canonical_article_rewrite_attempts
        SET status='failed',error_code='MODEL_NOT_DISPATCHED_LEASE_EXPIRED',completed_at=clock_timestamp()
        WHERE source_fetch_job_id=%s AND lease_token=%s AND status='prepared'""",
        (job["source_fetch_job_id"], job["lease_token"]))
    row = cur.execute("""UPDATE source_fetch_jobs SET lease_token=lease_token+1,
        lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',
        heartbeat_at=clock_timestamp(),updated_at=clock_timestamp()
        WHERE source_fetch_job_id=%s RETURNING *""", (worker_id, job["source_fetch_job_id"])).fetchone()
    return _lease_from_row(row, worker_id)


def _claim_review_resume(cur, worker_id, job_id=None):
    """Saved full drafts have a publication lease, never another model attempt."""
    from .article_lifecycle_store import _require_full_approval
    jobs = cur.execute("""SELECT * FROM source_fetch_jobs WHERE job_kind='article' AND NOT (checkpoint ? 'bankone_exact_recovery')
        AND rewrite_profile_version='full-prose-review-v1' AND (%s::uuid IS NULL OR source_fetch_job_id=%s)
        AND checkpoint->'content_review'->>'state'='approved'
        AND ((status='pending' AND COALESCE(next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp())
          OR (status='processing' AND lease_expires_at<clock_timestamp()))
        ORDER BY created_at,source_fetch_job_id FOR UPDATE SKIP LOCKED LIMIT 1""", (job_id,job_id)).fetchall()
    for job in jobs:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
        candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE", (job["transformation_key"],)).fetchone()
        try:
            _require_full_approval(cur, job, article, candidate)
        except ValueError:
            cur.execute("""UPDATE source_fetch_jobs SET status='needs_review',error_code='CONTENT_REVIEW_REQUIRED',retryable=false,
                lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,checkpoint=jsonb_set(checkpoint,'{content_review,state}','"awaiting_review"'::jsonb) WHERE source_fetch_job_id=%s""", (job["source_fetch_job_id"],))
            continue
        row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='publishing',lease_token=lease_token+1,
            lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
            error_code=NULL,next_attempt_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id,job["source_fetch_job_id"])).fetchone()
        return _lease_from_row(row,worker_id)
    return None


def _claim_automatic_resume(cur, worker_id, job_id=None):
    """Saved successful auto output consumes publication leases, not model attempts."""
    from .article_lifecycle_store import automatic_candidate_validation
    from .procedure_rewrite_correction import _CORRECTION_METHOD
    from .procedure_rewrite_sentence_correction import SENTENCE_CORRECTION_METHOD
    job = cur.execute(f"""SELECT j.* FROM source_fetch_jobs j
        JOIN canonical_article_revisions r ON r.transformation_key=j.transformation_key
        WHERE j.job_kind='article' AND NOT (j.checkpoint ? 'bankone_exact_recovery') AND j.rewrite_profile_version=ANY(%s) AND (%s::uuid IS NULL OR j.source_fetch_job_id=%s)
          AND {_EXPLICIT_CORRECTION_SQL}
          AND (EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts a WHERE a.canonical_article_revision_id=r.canonical_article_revision_id AND a.status='succeeded')
            OR r.model_metadata->>'transformation_method'='source-preserving-zero-slot-v1'
            OR (j.rewrite_profile_version='{SOURCE_BOUND_CORRECTION_PROFILE}'
                AND r.model_metadata->>'transformation_method' IN ('{_CORRECTION_METHOD}','{SENTENCE_CORRECTION_METHOD}')
                AND r.model_metadata->'correction_evidence'->'exchanges'='[]'::jsonb))
          AND r.status IN ('building','validated') AND j.checkpoint->>'rewrite_error_code' IS NULL
          AND j.checkpoint->>'candidate_revision_id'=r.canonical_article_revision_id::text
          AND ((j.status='pending' AND COALESCE(j.next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp())
            OR (j.status='processing' AND j.lease_expires_at<clock_timestamp()))
        ORDER BY j.created_at,j.source_fetch_job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1""",
        (list(AUTOMATIC_REWRITE_PROFILES), job_id, job_id, job_id is not None)).fetchone()
    if job is None:
        return None
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE", (job["transformation_key"],)).fetchone()
    try:
        if (article is None or article["current_job_id"] != job["source_fetch_job_id"]
            or article["request_generation"] != job["request_generation"]
            or not transform_source_matches(article, job)
            or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
            or article["target_normalization_version"] != job["normalization_version"]):
            raise ValueError("automatic publication owner changed")
        automatic_candidate_validation(cur,job,candidate)
    except ValueError:
        cur.execute("""UPDATE source_fetch_jobs SET status='dead_letter',error_code='AUTOMATIC_CANDIDATE_INVALID',retryable=false,
            lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s""", (job["source_fetch_job_id"],))
        return None
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='validating',lease_token=lease_token+1,
        lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        error_code=NULL,next_attempt_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s RETURNING *""",
        (worker_id,job["source_fetch_job_id"])).fetchone()
    return _lease_from_row(row,worker_id)


def park_automatic_for_model(repo, lease):
    """Release only an undispatched auto job after source/normalization commit."""
    from .article_lifecycle_store import _lock_transform
    with repo.connect() as conn, _cursor(conn) as cur:
        job, _ = _lock_transform(cur, lease)
        if (job["rewrite_profile_version"] not in AUTOMATIC_REWRITE_PROFILES
            or not job["source_revision_id"] or not job["checkpoint"].get("normalized_hash")
            or not cur.execute(f"""SELECT {_MODEL_CONFIGURATION_NO_ATTEMPT_SQL} AS no_attempt
                FROM source_fetch_jobs j WHERE j.source_fetch_job_id=%s""",
                (lease.job_id,)).fetchone()["no_attempt"]):
            raise ValueError("MODEL_CONFIGURATION_PARK_INVALID")
        cur.execute("""UPDATE source_fetch_jobs SET status='failed',error_code='MODEL_NOT_CONFIGURED',retryable=true,
            checkpoint=checkpoint||'{"awaiting_model_configuration":true}'::jsonb,next_attempt_at=NULL,
            lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s""", (lease.job_id,))


def _claim_model_configuration_resume(cur, worker_id, job_id):
    """Configuration waits dispatched nothing and consume no additional attempt."""
    job = cur.execute(f"""SELECT j.* FROM source_fetch_jobs j JOIN canonical_articles a
        ON a.canonical_article_id=j.canonical_article_id
        WHERE j.job_kind='article' AND NOT (j.checkpoint ? 'bankone_exact_recovery') AND j.rewrite_profile_version=ANY(%s)
          AND (%s::uuid IS NULL OR j.source_fetch_job_id=%s)
          AND NOT (j.checkpoint ? 'new_article_rollout')
          AND {_EXPLICIT_CORRECTION_SQL}
          AND j.status IN ('failed','dead_letter') AND j.error_code='MODEL_NOT_CONFIGURED'
          AND j.source_revision_id IS NOT NULL AND j.checkpoint ? 'normalized_document' AND j.checkpoint ? 'normalized_hash'
          AND a.current_job_id=j.source_fetch_job_id AND a.request_generation=j.request_generation
          AND (a.current_source_revision_id=j.source_revision_id OR (
            j.checkpoint ? '{STAGED_MEDIA_REFRESH}'
            AND j.checkpoint->'{STAGED_MEDIA_REFRESH}'->>'source_revision_id'=j.source_revision_id::text
            AND j.checkpoint->'{STAGED_MEDIA_REFRESH}'->>'prior_source_revision_id'=a.current_source_revision_id::text
            AND j.checkpoint->'{STAGED_MEDIA_REFRESH}'->>'prior_canonical_revision_id'=a.current_canonical_revision_id::text
          ))
          AND a.target_rewrite_profile_version=j.rewrite_profile_version AND a.target_normalization_version=j.normalization_version
          AND {_MODEL_CONFIGURATION_NO_ATTEMPT_SQL}
        ORDER BY j.created_at,j.source_fetch_job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1""",
        (list(AUTOMATIC_REWRITE_PROFILES), job_id, job_id, job_id is not None)).fetchone()
    if job is None:
        return None
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    if (article["current_job_id"] != job["source_fetch_job_id"] or article["request_generation"] != job["request_generation"]
        or not transform_source_matches(article, job)
        or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
        or article["target_normalization_version"] != job["normalization_version"]):
        return None
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='rewriting',lease_token=lease_token+1,
        lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        checkpoint=checkpoint-'awaiting_model_configuration',error_code=NULL,retryable=false,next_attempt_at=NULL,updated_at=clock_timestamp()
        WHERE source_fetch_job_id=%s RETURNING *""", (worker_id,job["source_fetch_job_id"])).fetchone()
    return _lease_from_row(row,worker_id)


class BankoneRecoveryBlocked(ValueError):
    """A stable, content-free reason the exceptional recovery was rejected."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


BANKONE_RECOVERY_JOB = "a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d"
BANKONE_RECOVERY_ARTICLE = "aad66f67-355c-5d92-ab21-b4894bca9069"
BANKONE_RECOVERY_SOURCE = "acd11534-199a-40f7-bf94-717b34895752"
BANKTWO_FROZEN_JOB = "64888ce4-429e-4e22-9892-48d1fb4b82eb"


def claim_exact_bankone_recovery(
    repo, *, worker_id, job_id, canonical_article_id, source_revision_id,
    rewrite_profile_version, expected_generation, normalization_version,
    expected_normalized_hash, expected_lease_token, expected_retry_count,
    recovery_id, actor, reason, implementation_sha,
):
    """Consume the sole frozen recovery authorization and return its live lease.

    No polling/ensure path calls this function. Repeating even an identical
    request blocks: a prepared recovery resumes only using the returned lease.
    The dispatch boundary must atomically consume its checkpoint allowance.
    """
    from .article_lifecycle_types import digest_json, transformation_key

    def require(condition, code):
        if not condition:
            raise BankoneRecoveryBlocked(code)

    require((str(job_id), str(canonical_article_id), str(source_revision_id),
             rewrite_profile_version, normalization_version) ==
            (BANKONE_RECOVERY_JOB, BANKONE_RECOVERY_ARTICLE, BANKONE_RECOVERY_SOURCE,
             "full-prose-auto-v1", "ordered-article-v1"), "RECOVERY_SCOPE_MISMATCH")
    require(all(isinstance(value, str) and value.strip() and len(value) <= limit
                and not any(ord(c) < 32 or ord(c) == 127 for c in value)
                for value, limit in ((recovery_id, 128), (actor, 128), (reason, 512))),
            "RECOVERY_AUDIT_INVALID")
    require(isinstance(implementation_sha, str) and
            re.fullmatch(r"[a-f0-9]{40}", implementation_sha) is not None,
            "RECOVERY_IMPLEMENTATION_INVALID")
    require(isinstance(expected_normalized_hash, str) and
            re.fullmatch(r"[a-f0-9]{64}", expected_normalized_hash) is not None and
            all(type(value) is int and value >= 0 for value in
                (expected_generation, expected_lease_token, expected_retry_count)),
            "RECOVERY_FENCE_INVALID")
    with repo.connect() as conn, _cursor(conn) as cur:
        # Lock both exact budgets before examining attempts. This also serializes
        # competing recovery requests and ordinary claims for either frozen job.
        banks = cur.execute("""SELECT * FROM source_fetch_jobs
            WHERE source_fetch_job_id IN (%s,%s)
            ORDER BY source_fetch_job_id FOR UPDATE""", (job_id, BANKTWO_FROZEN_JOB)).fetchall()
        require(len(banks) == 2, "RECOVERY_HISTORY_UNKNOWN")
        jobs = {str(row["source_fetch_job_id"]): row for row in banks}
        job = jobs[BANKONE_RECOVERY_JOB]
        banktwo = jobs[BANKTWO_FROZEN_JOB]
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (canonical_article_id,)).fetchone()
        require("bankone_exact_recovery" not in job["checkpoint"], "RECOVERY_ALREADY_CONSUMED")
        require(job["status"] == "dead_letter" and job["error_code"] == "REWRITE_RESPONSE_INVALID"
                and job["job_kind"] == "article" and job["provider_slug"] == "bankone"
                and job["phase"] == "rewriting" and not job["retryable"]
                and job["lease_owner"] is None and job["lease_expires_at"] is None
                and job["heartbeat_at"] is None, "RECOVERY_JOB_STATE_CHANGED")
        require(article is not None and str(job["canonical_article_id"]) == str(canonical_article_id)
                and article["current_job_id"] == job["source_fetch_job_id"]
                and article["provider_slug"] == "bankone" and article["membership_status"] == "active"
                and article["takedown_status"] == "active"
                and article["current_source_revision_id"] == job["source_revision_id"]
                and str(job["source_revision_id"]) == str(source_revision_id)
                and article["request_generation"] == job["request_generation"] == expected_generation
                and article["target_normalization_version"] == job["normalization_version"] == normalization_version
                and article["target_rewrite_profile_version"] == job["rewrite_profile_version"] == rewrite_profile_version,
                "RECOVERY_OWNER_CHANGED")
        require(job["lease_token"] == expected_lease_token and job["retry_count"] == expected_retry_count,
                "RECOVERY_LEASE_CHANGED")
        require(job["retry_count"] < job["max_attempts"], "RECOVERY_RETRY_BUDGET_EXHAUSTED")
        source = cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s FOR SHARE",
                             (source_revision_id,)).fetchone()
        document = job["checkpoint"].get("normalized_document")
        require(source is not None and source["canonical_article_id"] == article["canonical_article_id"]
                and isinstance(document, dict) and isinstance(document.get("blocks"), list)
                and bool(document["blocks"])
                and digest_json(document) == job["checkpoint"].get("normalized_hash") == expected_normalized_hash
                and job["transformation_key"] == transformation_key(canonical_article_id,
                    source["source_fingerprint"], normalization_version, rewrite_profile_version,
                    projection_version=source["projection_version"]), "RECOVERY_INPUT_CHANGED")
        require(article["current_canonical_revision_id"] is None
                and not job["checkpoint"].get("candidate_revision_id")
                and cur.execute("SELECT 1 FROM canonical_article_revisions WHERE canonical_article_id=%s LIMIT 1",
                                (canonical_article_id,)).fetchone() is None
                and cur.execute("SELECT 1 FROM publication_events WHERE canonical_article_id=%s LIMIT 1",
                                (canonical_article_id,)).fetchone() is None, "RECOVERY_CANDIDATE_EXISTS")
        attempts = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id IN (%s,%s) ORDER BY source_fetch_job_id,attempt_number FOR UPDATE""",
            (job_id, BANKTWO_FROZEN_JOB)).fetchall()
        prior = [row for row in attempts if str(row["source_fetch_job_id"]) == BANKONE_RECOVERY_JOB]
        other = [row for row in attempts if str(row["source_fetch_job_id"]) == BANKTWO_FROZEN_JOB]
        require(banktwo["provider_slug"] == "banktwo" and banktwo["job_kind"] == "article"
                and banktwo["status"] == "completed" and banktwo["lease_owner"] is None
                and len(prior) == 1 and bool(other) and len(prior) < 2 and len(attempts) < 4,
                "RECOVERY_DISPATCH_BUDGET_BLOCKED")
        require(all(row["status"] in ("failed", "succeeded", "ambiguous")
                    and row["dispatched_at"] is not None and row["completed_at"] is not None
                    and row["provider"] == "inception" and row["model"] == "mercury-3"
                    and row["profile_version"] == "full-prose-auto-v1"
                    and row["lease_token"] <= jobs[str(row["source_fetch_job_id"])]["lease_token"]
                    and row["attempt_number"] <= jobs[str(row["source_fetch_job_id"])]["retry_count"]
                    for row in attempts)
                and prior[0]["status"] == "failed" and prior[0]["error_code"] == "REWRITE_RESPONSE_INVALID"
                and prior[0]["input_hash"] == expected_normalized_hash
                and prior[0]["canonical_article_revision_id"] is None,
                "RECOVERY_HISTORY_UNKNOWN")
        marker = dict(version=1, recovery_id=recovery_id, actor=actor, reason=reason,
                      implementation_sha=implementation_sha, state="prepared",
                      max_additional_dispatches=1, dispatches_consumed=0,
                      lease_token=job["lease_token"]+1, prior_lease_token=job["lease_token"],
                      prior_retry_count=job["retry_count"], original_error_code=job["error_code"])
        row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='rewriting',
            retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
            lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
            next_attempt_at=NULL,retryable=false,error_code=NULL,
            checkpoint=checkpoint||%s,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, Jsonb({"bankone_exact_recovery": marker}), job_id)).fetchone()
        return _lease_from_row(row, worker_id)


def _finalize_expired_bankone_recovery(cur, job_id):
    """End only the frozen one-shot lease; never reacquire or return it."""
    job = cur.execute("""SELECT * FROM source_fetch_jobs
        WHERE source_fetch_job_id=%s AND canonical_article_id=%s AND source_revision_id=%s
          AND (%s::uuid IS NULL OR source_fetch_job_id=%s)
          AND checkpoint ? 'bankone_exact_recovery' AND status='processing'
          AND lease_expires_at<clock_timestamp()
        FOR UPDATE SKIP LOCKED""", (BANKONE_RECOVERY_JOB, BANKONE_RECOVERY_ARTICLE,
            BANKONE_RECOVERY_SOURCE, job_id, job_id)).fetchone()
    if job is None:
        return
    # Unknown delivery remains consumed. Change only this lease's unresolved
    # dispatched attempt; the original terminal attempt is immutable evidence.
    _mark_delivery_ambiguous(cur, job)
    ambiguous = cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
        WHERE source_fetch_job_id=%s AND lease_token=%s AND status='ambiguous'
          AND response IS NULL AND dispatched_at IS NOT NULL
        LIMIT 1""", (job["source_fetch_job_id"], job["lease_token"])).fetchone()
    # A consumed allowance proves dispatch, not unknown delivery: a saved
    # response remains known evidence even when the publication lease expires.
    code = "MODEL_DELIVERY_AMBIGUOUS" if ambiguous else "RECOVERY_LEASE_EXPIRED"
    cur.execute("""UPDATE source_fetch_jobs SET status='dead_letter',error_code=%s,retryable=false,
        lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,
        updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
        (code, job["source_fetch_job_id"]))


def claim_source_job(repo, *, worker_id, model_ready=True, job_id=None):
    claim_scope = (job_id, job_id, list(AUTOMATIC_REWRITE_PROFILES))
    with repo.connect() as conn, _cursor(conn) as cur:
        _finalize_expired_bankone_recovery(cur, job_id)
        resumed = _claim_automatic_resume(cur, worker_id, job_id)
        if resumed is not None:
            return resumed
        resumed = _claim_review_resume(cur, worker_id, job_id)
        if resumed is not None:
            return resumed
        if model_ready:
            resumed = _claim_model_configuration_resume(cur, worker_id, job_id)
            if resumed is not None:
                return resumed
        resumed = _claim_source_bound_predispatch_resume(cur, worker_id, job_id)
        if resumed is not None:
            return resumed
        cur.execute(
            f"""WITH exhausted AS (SELECT j.source_fetch_job_id FROM source_fetch_jobs j
        WHERE job_kind IN ('article','catalog_index') AND NOT (checkpoint ? 'bankone_exact_recovery') AND (%s::uuid IS NULL OR source_fetch_job_id=%s) AND NOT (rewrite_profile_version=ANY(%s) AND COALESCE(error_code,'')='MODEL_NOT_CONFIGURED') AND NOT (checkpoint @> '{{"source_only_reprojection":true}}'::jsonb) AND NOT (rewrite_profile_version='full-prose-review-v1' AND checkpoint ? 'content_review') AND status='processing' AND retry_count>=max_attempts AND lease_expires_at<clock_timestamp()
        AND {_EXPLICIT_CORRECTION_SQL}
        AND NOT ({_SOURCE_BOUND_NO_DELIVERY_EXPIRY_SQL}
            AND EXISTS (SELECT 1 FROM canonical_articles a WHERE {_SOURCE_BOUND_CURRENT_OWNER_SQL}))
        FOR UPDATE OF j SKIP LOCKED)
        UPDATE source_fetch_jobs j SET status='dead_letter',error_code='LEASE_ATTEMPTS_EXHAUSTED',retryable=false,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp()
        FROM exhausted e WHERE j.source_fetch_job_id=e.source_fetch_job_id
        RETURNING j.source_fetch_job_id,j.lease_token""", (*claim_scope, job_id is not None)
        )
        for exhausted in cur.fetchall():
            _mark_delivery_ambiguous(cur, exhausted)
        job = cur.execute(
            f"""SELECT j.* FROM source_fetch_jobs j
        WHERE job_kind IN ('article','catalog_index') AND NOT (checkpoint ? 'bankone_exact_recovery')
        AND (%s::uuid IS NULL OR source_fetch_job_id=%s)
        AND NOT (rewrite_profile_version=ANY(%s) AND COALESCE(error_code,'')='MODEL_NOT_CONFIGURED')
        AND (%s::uuid IS NOT NULL OR NOT (j.checkpoint ? 'new_article_rollout'))
        AND {_EXPLICIT_CORRECTION_SQL}
        AND NOT (checkpoint @> '{{"source_only_reprojection":true}}'::jsonb)
        AND NOT (rewrite_profile_version='full-prose-review-v1' AND checkpoint ? 'content_review') AND retry_count<max_attempts AND
        ((status IN ('pending','failed') AND COALESCE(next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp()) OR (status='processing' AND lease_expires_at<clock_timestamp()))
        ORDER BY created_at,source_fetch_job_id FOR UPDATE SKIP LOCKED LIMIT 1""", (*claim_scope, job_id, job_id is not None)
        ).fetchone()
        if job is None:
            return None
        if job["status"] == "processing":
            _mark_delivery_ambiguous(cur, job)
        row = cur.execute(
            """UPDATE source_fetch_jobs SET status='processing',retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
        lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),updated_at=clock_timestamp(),
        phase=CASE WHEN phase='queued' THEN 'fetching_source' ELSE phase END WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, job["source_fetch_job_id"]),
        ).fetchone()
        return _lease_from_row(row, worker_id)



def _lease_from_row(row, worker_id):
    return JobLease(
        row["source_fetch_job_id"],
        worker_id,
        row["lease_token"],
        row["request_generation"],
        row["job_kind"],
        row["phase"],
        row["canonical_article_id"],
        row["catalog_provider_scope_id"],
        row["source_revision_id"],
        row["normalization_version"],
        row["rewrite_profile_version"],
        row["checkpoint"],
        row["lease_expires_at"],
    )


def claim_source_only_job(cur, job_id, canonical_article_id, *, worker_id):
    """Claim only the specified offline job in its caller's transaction."""
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',
        retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
        lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        phase='fetching_source',updated_at=clock_timestamp()
        WHERE source_fetch_job_id=%s AND canonical_article_id=%s AND job_kind='article'
          AND status='pending' AND retry_count<max_attempts
          AND checkpoint @> '{"source_only_reprojection":true}'::jsonb
        RETURNING *""", (worker_id, job_id, canonical_article_id)).fetchone()
    if row is None:
        raise LeaseLost("source-only exact claim rejected")
    return _lease_from_row(row, worker_id)


def lock_live_lease(cur, lease):
    row = cur.execute(
        """SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s AND status='processing' AND lease_owner=%s AND lease_token=%s AND lease_expires_at>clock_timestamp() FOR UPDATE""",
        (lease.job_id, lease.worker_id, lease.token),
    ).fetchone()
    if row is None:
        raise LeaseLost("source job lease lost")
    return row


def heartbeat_source_job(repo, lease):
    with repo.connect() as conn, _cursor(conn) as cur:
        lock_live_lease(cur, lease)
        cur.execute(
            "UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp() WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        )
        return True


def advance_source_job(repo, lease, *, phase, checkpoint):
    with repo.connect() as conn, _cursor(conn) as cur:
        lock_live_lease(cur, lease)
        cur.execute(
            """UPDATE source_fetch_jobs SET phase=%s,checkpoint=checkpoint||%s,status=CASE WHEN %s='completed' THEN 'completed' ELSE status END,
        lease_owner=CASE WHEN %s='completed' THEN NULL ELSE lease_owner END,lease_expires_at=CASE WHEN %s='completed' THEN NULL ELSE lease_expires_at END,
        heartbeat_at=CASE WHEN %s='completed' THEN NULL ELSE heartbeat_at END,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (phase, Jsonb(checkpoint), phase, phase, phase, phase, lease.job_id),
        )


def fail_source_job(repo, lease, *, code, retryable, retry_after_seconds=None):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code):
        raise ValueError("redacted stable error code required")
    with repo.connect() as conn, _cursor(conn) as cur:
        row = lock_live_lease(cur, lease)
        retry = retryable and "bankone_exact_recovery" not in row["checkpoint"] and row["retry_count"] < row["max_attempts"]
        delay = (
            max(
                5 if row["retry_count"] == 1 else 30,
                min(900, max(1, int(retry_after_seconds or 1))),
            )
            if retry
            else None
        )
        status = "failed" if retry else ("dead_letter" if retryable or row["rewrite_profile_version"] in AUTOMATIC_REWRITE_PROFILES else "needs_review")
        cur.execute(
            """UPDATE source_fetch_jobs SET status=%s,error_code=%s,retryable=%s,next_attempt_at=CASE WHEN %s::int IS NULL THEN NULL ELSE statement_timestamp()+make_interval(secs=>%s) END,
        lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=statement_timestamp() WHERE source_fetch_job_id=%s""",
            (status, code, retry, delay, delay, lease.job_id),
        )
