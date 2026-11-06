"""Transactional identity/source store; all connections belong to their caller."""

from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID, uuid4
from .article_lifecycle_types import transformation_key
from .source_job_persistence import lock_live_lease, LeaseLost

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import ArticleKey, article_id, identity_key


def upsert_article_descriptor(
    repo, key: ArticleKey, descriptor: dict, descriptor_snapshot_id, generation: int
):
    with repo.connect() as conn:
        return _upsert_descriptor(
            conn, key, descriptor, descriptor_snapshot_id, generation
        )


def _upsert_descriptor(conn, key, descriptor, snapshot, generation):
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,vehicle_configuration_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id,title,kind,component,source_sort_order,last_seen_catalog_generation)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(provider_slug,scope_key,source_vehicle_ref,source_article_ref) DO UPDATE SET
        descriptor=EXCLUDED.descriptor,descriptor_source_snapshot_id=EXCLUDED.descriptor_source_snapshot_id,title=EXCLUDED.title,kind=EXCLUDED.kind,component=EXCLUDED.component,source_sort_order=EXCLUDED.source_sort_order,last_seen_catalog_generation=EXCLUDED.last_seen_catalog_generation,membership_status='active',updated_at=clock_timestamp()
        WHERE canonical_articles.last_seen_catalog_generation<=EXCLUDED.last_seen_catalog_generation RETURNING canonical_article_id""",
            (
                article_id(key),
                key.provider,
                key.vehicle_id,
                key.vehicle_configuration_id,
                key.scope_key,
                key.source_vehicle_ref,
                key.source_article_ref,
                identity_key(key),
                Jsonb(descriptor),
                snapshot,
                descriptor.get("title"),
                descriptor.get("kind"),
                descriptor.get("component"),
                descriptor.get("source_sort_order"),
                generation,
            ),
        ).fetchone()
        if row:
            return row["canonical_article_id"]
        return article_id(key)


def load_article_state(repo, canonical_article_id):
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "SELECT * FROM catalog_article_current WHERE canonical_article_id=%s",
            (canonical_article_id,),
        ).fetchone()


def persist_resource(cur, resource):
    """Blob dedupe shares bytes only; ownership lives in observation provenance."""
    row = cur.execute(
        """INSERT INTO source_snapshots(source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,license_metadata,retrieved_at)
    VALUES (%s,%s,%s,%s,%s,%s,'{}',%s) ON CONFLICT(content_sha256) DO NOTHING RETURNING source_snapshot_id""",
        (
            UUID(str(resource["source_snapshot_id"])),
            resource["provider"],
            resource["locator"],
            resource["source_revision"],
            resource["sha256"],
            resource["object_key"],
            resource["fetched_at"],
        ),
    ).fetchone()
    if row is None:
        row = cur.execute(
            "SELECT source_snapshot_id FROM source_snapshots WHERE content_sha256=%s",
            (resource["sha256"],),
        ).fetchone()
    snapshot = row["source_snapshot_id"]
    cur.execute(
        """INSERT INTO source_artifacts(source_snapshot_id,artifact_kind,media_type,content_sha256,object_key,metadata,extraction_status)
    VALUES (%s,%s,%s,%s,%s,'{}','candidate_ready') ON CONFLICT(content_sha256) DO NOTHING""",
        (
            snapshot,
            (
                "document"
                if resource["media_type"].startswith("text/")
                or resource["media_type"] == "application/pdf"
                else "structured"
            ),
            resource["media_type"],
            resource["sha256"],
            resource["object_key"],
        ),
    )
    return snapshot


def _remap_snapshot_references(value, snapshots):
    """Copy JSON provenance using persisted blob IDs, preserving evidence IDs."""
    if isinstance(value, list):
        return [_remap_snapshot_references(item, snapshots) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    result = {}
    for key, item in value.items():
        if (key == "snapshot_id" or key.endswith("_snapshot_id")) and str(
            item
        ) in snapshots:
            result[key] = str(snapshots[str(item)])
        elif (key == "snapshot_ids" or key.endswith("_snapshot_ids")) and isinstance(
            item, list
        ):
            result[key] = [
                str(snapshots[str(ref)]) if str(ref) in snapshots else deepcopy(ref)
                for ref in item
            ]
        else:
            result[key] = _remap_snapshot_references(item, snapshots)
    return result


def store_captured_source(repo, lease, captured):
    """Source revision, observation, pointer and transformation transition are atomic."""
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        return _store_captured_source(cur, lease, captured)


def _store_captured_source(cur, lease, captured):
    """Use the caller's transaction, including exact source-only job creation."""
    if captured.projection_version not in ("source-projection-v1", "source-projection-v2"):
        raise ValueError("unsupported source projection version")
    context = captured.context
    if (
        article_id(context.key) != lease.canonical_article_id
        or not captured.source_body.strip()
        or not captured.source_document.get("blocks")
    ):
        raise ValueError("captured article identity/body mismatch")
    job = lock_live_lease(cur, lease)
    # A full review owner may be adopted below. Lock it before the article,
    # matching review/publication's job -> article order even during refresh.
    review_owner = None
    if job["rewrite_profile_version"] == "full-prose-review-v1" and not job["checkpoint"].get("source_only_reprojection"):
        review_key = transformation_key(lease.canonical_article_id,captured.source_fingerprint,
            job["normalization_version"],job["rewrite_profile_version"],projection_version=captured.projection_version)
        review_owner = cur.execute("SELECT * FROM source_fetch_jobs WHERE transformation_key=%s FOR UPDATE",(review_key,)).fetchone()
    article = cur.execute(
        "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
        (lease.canonical_article_id,),
    ).fetchone()
    if (
        article["request_generation"] != job["request_generation"]
        or article["current_job_id"] != lease.job_id
    ):
        raise LeaseLost("article generation changed")
    if captured.projection_version == "source-projection-v1" and article["current_source_revision_id"]:
        current = cur.execute("SELECT projection_version FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                              (article["current_source_revision_id"],)).fetchone()
        if current["projection_version"] == "source-projection-v2":
            raise ValueError("source projection downgrade is not supported")
    observed = cur.execute(
        "SELECT source_revision_id FROM canonical_article_source_observations WHERE source_fetch_job_id=%s",
        (lease.job_id,),
    ).fetchone()
    if observed:
        return observed["source_revision_id"]
    snapshots = {}
    for resource in captured.resources:
        snapshots[str(resource["source_snapshot_id"])] = persist_resource(
            cur, resource
        )
    body_snapshot = snapshots[str(captured.body_source_snapshot_id)]
    revision_id = uuid4()
    row = cur.execute(
        """INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at,projection_version)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(canonical_article_id,source_fingerprint,projection_version) DO NOTHING RETURNING source_revision_id""",
        (
            revision_id,
            lease.canonical_article_id,
            captured.source_fingerprint,
            body_snapshot,
            Jsonb(
                _remap_snapshot_references(captured.resource_manifest, snapshots)
            ),
            Jsonb(captured.source_document),
            Jsonb(captured.source_images),
            captured.source_body,
            Jsonb(captured.source_steps),
            captured.projection_status,
            Jsonb(
                _remap_snapshot_references(captured.evidence_manifest, snapshots)
            ),
            captured.captured_at,
            captured.projection_version,
        ),
    ).fetchone()
    if row is None:
        row = cur.execute(
            "SELECT source_revision_id FROM canonical_article_source_revisions WHERE canonical_article_id=%s AND source_fingerprint=%s AND projection_version=%s",
            (lease.canonical_article_id, captured.source_fingerprint, captured.projection_version),
        ).fetchone()
    revision_id = row["source_revision_id"]
    provenance = _remap_snapshot_references(captured.resource_provenance, snapshots)
    body_resource = next(r for r in captured.resources if r["role"] == "body")
    cur.execute(
        """INSERT INTO canonical_article_source_observations(source_observation_id,canonical_article_id,source_revision_id,source_fetch_job_id,request_generation,body_provider_revision,resource_provenance,captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            uuid4(),
            lease.canonical_article_id,
            revision_id,
            lease.job_id,
            job["request_generation"],
            next(
                (
                    r.get("source_revision")
                    for r in provenance
                    if r.get("role") == "body"
                ),
                body_resource["source_revision"],
            ),
            Jsonb(provenance),
            Jsonb(
                {
                    "vehicle": context.vehicle,
                    "descriptor": context.descriptor,
                    "evidence_ids": list(context.evidence_ids),
                }
            ),
            context.resolution_snapshot_id,
            context.descriptor_snapshot_id,
            captured.captured_at,
        ),
    )
    if job["checkpoint"].get("source_only_reprojection") is True:
        cur.execute("""UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=NULL,
            status='needs_review',phase='completed',error_code='SOURCE_ONLY_REPROJECTION',retryable=false,
            next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,
            updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""", (revision_id, lease.job_id))
        cur.execute("""UPDATE canonical_articles SET current_source_revision_id=%s,current_canonical_revision_id=NULL,
            current_job_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
            (revision_id, lease.job_id, lease.canonical_article_id))
        return revision_id
    key = transformation_key(
        lease.canonical_article_id,
        captured.source_fingerprint,
        job["normalization_version"],
        job["rewrite_profile_version"],
        projection_version=captured.projection_version,
    )
    owner = cur.execute(
        "SELECT * FROM source_fetch_jobs WHERE transformation_key=%s", (key,)
    ).fetchone()
    published = cur.execute(
        "SELECT canonical_article_revision_id FROM canonical_article_revisions WHERE transformation_key=%s AND status='published'",
        (key,),
    ).fetchone()
    rejected = cur.execute(
        "SELECT canonical_article_revision_id FROM canonical_article_revisions WHERE transformation_key=%s AND status='rejected'",
        (key,),
    ).fetchone()
    current_job = lease.job_id
    current_canonical = (
        published["canonical_article_revision_id"] if published else None
    )
    if owner and owner["source_fetch_job_id"] != lease.job_id:
        terminal = owner["status"] in ("needs_review", "dead_letter") or bool(
            rejected
        )
        if not published and not terminal:
            raise LeaseLost("transformation already has an owner")
        checkpoint = {
            "reused_terminal_result": terminal,
            "reused_transformation_job_id": str(owner["source_fetch_job_id"]),
        }
        if published:
            checkpoint["reused_published_revision_id"] = str(current_canonical)
        cur.execute(
            """UPDATE source_fetch_jobs SET source_revision_id=%s,phase='completed',status='completed',checkpoint=checkpoint||%s,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,retryable=false,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (revision_id, Jsonb(checkpoint), lease.job_id),
        )
        if terminal:
            current_job = owner["source_fetch_job_id"]
            if (review_owner is not None and owner["status"] == "needs_review"
                and job["rewrite_profile_version"] == "full-prose-review-v1"
                and owner["source_revision_id"] == revision_id
                and owner["normalization_version"] == job["normalization_version"]
                and owner["rewrite_profile_version"] == job["rewrite_profile_version"]):
                candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE",(key,)).fetchone()
                if candidate is not None and candidate["status"] == "validated":
                    from .article_lifecycle_types import digest_json
                    if not full_candidate_validation(cur,owner,candidate).passed:
                        raise ValueError("CONTENT_REVIEW_REQUIRED")
                    # Inspection already owns its unique generation. Allocate
                    # the next generation for the saved owner instead of moving
                    # the original attempt or weakening any generation fence.
                    adopted_generation = job["request_generation"] + 1
                    review_checkpoint = {"version":1,"state":"awaiting_review",
                        "candidate_revision_id":str(candidate["canonical_article_revision_id"]),
                        "candidate_hash":digest_json(candidate["canonical_document"])}
                    cur.execute("""UPDATE source_fetch_jobs SET request_generation=%s,
                        checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
                        (adopted_generation,Jsonb({"content_review":review_checkpoint,
                            "review_owner_adoption":{"previous_generation":owner["request_generation"],
                                "inspection_job_id":str(lease.job_id),"inspection_generation":job["request_generation"]}}),current_job))
                    cur.execute("UPDATE canonical_articles SET request_generation=%s WHERE canonical_article_id=%s",
                        (adopted_generation,lease.canonical_article_id))
    else:
        cur.execute(
            "UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s,phase='normalizing',updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
            (revision_id, key, lease.job_id),
        )
    cur.execute(
        """UPDATE canonical_articles SET current_source_revision_id=%s,current_canonical_revision_id=%s,current_job_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
        (revision_id, current_canonical, current_job, lease.canonical_article_id),
    )
    return revision_id


@dataclass(frozen=True)
class StoredSource:
    source_revision_id: UUID
    context: object
    source_document: dict
    source_images: list
    source_body: str
    source_steps: list
    source_fingerprint: str
    evidence_manifest: list
    body_source_snapshot_id: UUID
    resource_manifest: list
    projection_status: str
    captured_at: object
    projection_version: str

    @property
    def vehicle(self):
        return self.context.vehicle

    def as_article(self):
        return {
            "article_id": str(article_id(self.context.key)),
            "title": self.context.descriptor.get("title"),
            "normalized_document": deepcopy(self.source_document),
            "blocks": deepcopy(self.source_document["blocks"]),
            "images": deepcopy(self.source_images),
            "body": self.source_body,
            "steps": deepcopy(self.source_steps),
            "evidence_ids": list(self.context.evidence_ids),
        }


def load_source_revision(repo, source_revision_id):
    from .article_lifecycle_types import SourceArticleContext

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """SELECT s.*,a.provider_slug,a.vehicle_id,a.vehicle_configuration_id,a.source_vehicle_ref,a.source_article_ref,a.descriptor,a.descriptor_source_snapshot_id,v.make,v.model,v.model_year,v.region
        FROM canonical_article_source_revisions s JOIN canonical_articles a USING(canonical_article_id) JOIN vehicles v ON v.vehicle_id=a.vehicle_id WHERE source_revision_id=%s""",
            (source_revision_id,),
        ).fetchone()
        if row is None:
            raise KeyError("source revision not found")
        observation = cur.execute(
            "SELECT descriptor_source_snapshot_id,resolution_source_snapshot_id,captured_context FROM canonical_article_source_observations WHERE source_revision_id=%s ORDER BY captured_at LIMIT 1",
            (source_revision_id,),
        ).fetchone()
        key = ArticleKey(
            row["provider_slug"],
            row["vehicle_id"],
            row["vehicle_configuration_id"],
            row["source_vehicle_ref"],
            row["source_article_ref"],
        )
        if observation is None:
            raise ValueError("source revision has no immutable observation context")
        saved = observation["captured_context"]
        context = SourceArticleContext(
            key,
            saved["vehicle"],
            saved["descriptor"],
            observation["descriptor_source_snapshot_id"],
            observation["resolution_source_snapshot_id"],
            tuple(saved["evidence_ids"]),
        )
        return StoredSource(
            row["source_revision_id"],
            context,
            row["source_document"],
            row["source_images"],
            row["source_body"],
            row["source_steps"],
            row["source_fingerprint"],
            row["evidence_manifest"],
            row["body_source_snapshot_id"],
            row["resource_manifest"],
            row["projection_status"],
            row["captured_at"],
            row["projection_version"],
        )


# All transformation writes use job -> article lock order. No connection spans IO.
def _lock_transform(cur, lease):
    job = lock_live_lease(cur, lease)
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    if (article is None or article["current_job_id"] != lease.job_id
        or article["request_generation"] != job["request_generation"]
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["target_normalization_version"] != job["normalization_version"]
        or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]):
        raise LeaseLost("transformation generation/source changed")
    return job, article


def save_normalized_input(repo, lease, normalized):
    from .article_lifecycle_types import digest_json
    document = normalized["normalized_document"]
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job, _ = _lock_transform(cur, lease)
        existing = job["checkpoint"].get("normalized_document")
        if existing is not None and existing != document:
            raise ValueError("normalized input is immutable")
        cur.execute("UPDATE source_fetch_jobs SET phase='rewriting',checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",
                    (Jsonb({"normalized_document":document,"normalized_hash":digest_json(document)}),lease.job_id))


def prepare_rewrite_attempt(repo, lease, document, *, context, model):
    from .procedure_rewrite import build_rewrite_prompt
    from .article_lifecycle_types import digest_json
    from hashlib import sha256
    prompt=build_rewrite_prompt(document,context=context,profile_version=lease.rewrite_profile_version)
    if len(prompt.encode())>200*1024: raise ValueError("REWRITE_INPUT_LIMIT")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job,_=_lock_transform(cur,lease)
        if job["checkpoint"].get("normalized_hash")!=digest_json(document):
            raise ValueError("normalized input mismatch")
        attempt=cur.execute("""INSERT INTO canonical_article_rewrite_attempts
            (rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status)
            VALUES (%s,%s,%s,%s,'inception',%s,%s,%s,%s,'prepared')
            ON CONFLICT(source_fetch_job_id,lease_token,attempt_number) DO NOTHING RETURNING rewrite_attempt_id""",
            (uuid4(),lease.job_id,lease.token,job["retry_count"],model,lease.rewrite_profile_version,sha256(prompt.encode()).hexdigest(),digest_json(document))).fetchone()
        if attempt is None:
            attempt=cur.execute("SELECT rewrite_attempt_id FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s AND lease_token=%s AND attempt_number=%s",(lease.job_id,lease.token,job["retry_count"])).fetchone()
        return attempt["rewrite_attempt_id"]


def mark_rewrite_dispatched(repo,lease,attempt):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        _lock_transform(cur,lease)
        changed=cur.execute("""UPDATE canonical_article_rewrite_attempts SET status='dispatched',dispatched_at=clock_timestamp()
            WHERE rewrite_attempt_id=%s AND source_fetch_job_id=%s AND lease_token=%s AND status='prepared' RETURNING rewrite_attempt_id""",(attempt,lease.job_id,lease.token)).fetchone()
        if changed is None: raise ValueError("attempt cannot dispatch again")


def _bind_v2_operations(source, candidate, response):
    """Rebuild from the persisted selector response, under the caller's lock."""
    from .procedure_rewrite_v2 import render_v2
    from .article_lifecycle_types import digest_json
    try:
        expected = render_v2(source, response)
    except ValueError as error:
        raise ValueError("rewrite operation binding mismatch") from error
    if digest_json(candidate) != digest_json(expected):
        raise ValueError("rewrite operation binding mismatch")


def _latest_content_review(cur, candidate):
    return cur.execute("""SELECT * FROM canonical_article_reviews WHERE canonical_article_revision_id=%s
        ORDER BY reviewed_at DESC,canonical_article_review_id DESC LIMIT 1""",
        (candidate["canonical_article_revision_id"],)).fetchone()


def full_candidate_validation(cur, job, candidate):
    """Independently rebuild prompt, source, response and correction evidence."""
    from .article_content_review import resolve_full_evidence
    from .procedure_rewrite_full import validate_full
    from .article_document import project_ordered_document
    from .article_lifecycle_types import digest_json
    if candidate is None:
        raise ValueError("CONTENT_REVIEW_REQUIRED")
    attempt, original, response, correction = resolve_full_evidence(cur, job, candidate)
    source = candidate["normalized_source_document"]
    validation = validate_full(source,candidate["canonical_document"],response=response)
    if candidate["status"] == "validated":
        if (candidate["normalized_source_hash"] != digest_json(source)
            or candidate["rewrite_result_hash"] != digest_json(candidate["canonical_document"])
            or candidate["validation_report"] != validation.report
            or candidate["validation_hash"] != digest_json(validation.report)
            or project_ordered_document(candidate["canonical_document"]) != {"body":candidate["canonical_body"],"steps":candidate["canonical_steps"],"images":candidate["canonical_images"]}):
            raise ValueError("rewrite saved validation/projection binding mismatch")
    return validation


def _require_full_approval(cur, job, article, candidate):
    from .article_lifecycle_types import digest_json
    if (candidate is None or article is None or article["current_job_id"] != job["source_fetch_job_id"]
        or article["request_generation"] != job["request_generation"]
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["target_normalization_version"] != job["normalization_version"]
        or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
        or candidate["canonical_article_id"] != article["canonical_article_id"]
        or candidate["source_revision_id"] != job["source_revision_id"]
        or candidate["transformation_key"] != job["transformation_key"]
        or candidate["rewrite_profile_version"] != job["rewrite_profile_version"]
        or candidate["normalization_version"] != job["normalization_version"]
        or candidate["status"] != "validated"):
        raise ValueError("CONTENT_REVIEW_REQUIRED")
    latest = _latest_content_review(cur,candidate)
    checkpoint = job["checkpoint"].get("content_review",{})
    if (latest is None or latest["decision"] != "APPROVED" or checkpoint.get("version") != 1
        or type(checkpoint.get("version")) is not int or checkpoint.get("state") != "approved"
        or checkpoint.get("review_id") != str(latest["canonical_article_review_id"])
        or checkpoint.get("candidate_revision_id") != str(candidate["canonical_article_revision_id"])
        or checkpoint.get("candidate_hash") != digest_json(candidate["canonical_document"])):
        raise ValueError("CONTENT_REVIEW_REQUIRED")
    source = cur.execute("SELECT source_fingerprint FROM canonical_article_source_revisions WHERE source_revision_id=%s",(job["source_revision_id"],)).fetchone()
    if source is None:
        raise ValueError("CONTENT_REVIEW_REQUIRED")
    import os
    fixture = (os.environ.get("AUTODATA_LIFECYCLE_TEST") == "1"
        and cur.execute("SELECT current_database() AS name").fetchone()["name"].startswith("lifecycle_test_"))
    from .article_content_review import validate_review_reason, correction_authors
    reason = validate_review_reason(latest["reason"],job=job,article=article,candidate=candidate,review=latest,
        source_fingerprint=source["source_fingerprint"],allow_synthetic=fixture)
    validation = full_candidate_validation(cur,job,candidate)
    from .article_content_review import resolve_full_evidence
    attempt, _, _, _ = resolve_full_evidence(cur,job,candidate)
    correction = reason.get("correction")
    if (not validation.passed or set(reason["retention_reviews"]) != set(validation.report.get("retained_paths",[]))
        or latest["authorized_reviewer_id"] in {attempt["provider"],attempt["model"],candidate["model_metadata"].get("drafting_actor")}
        or (correction is not None and (correction["actor"] == latest["authorized_reviewer_id"]
            or ("failed_origin" in correction and latest["authorized_reviewer_id"] in correction_authors(cur,candidate))))):
        raise ValueError("CONTENT_REVIEW_BINDING_INVALID")
    return latest


def validate_saved_candidate(repo,lease,candidate):
    if lease.rewrite_profile_version != "full-prose-review-v1":
        from .procedure_rewrite import validate_article_rewrite
        return validate_article_rewrite(candidate["normalized_source_document"],candidate["canonical_document"],profile_version=lease.rewrite_profile_version)
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_ = _lock_transform(cur,lease)
        return full_candidate_validation(cur,job,candidate)


def store_rewrite_result(repo,lease,result):
    from .article_lifecycle_types import digest_json
    from .article_document import project_ordered_document
    from hashlib import sha256
    import json
    projection=project_ordered_document(result.document)
    # PostgreSQL jsonb includes separator whitespace. Enforce that storage bound
    # before attempting a transaction as well as the external wire bound.
    raw=json.dumps(result.raw_response,ensure_ascii=False)
    if len(raw.encode())>1048576: raise ValueError("REWRITE_RESPONSE_LIMIT")
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_=_lock_transform(cur,lease)
        attempt=cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s AND lease_token=%s AND status='dispatched' FOR UPDATE",(lease.job_id,lease.token)).fetchone()
        if attempt is None: raise ValueError("no dispatched rewrite attempt")
        if (attempt["input_hash"]!=result.input_hash or attempt["prompt_hash"]!=result.prompt_hash
            or result.profile_version!=job["rewrite_profile_version"]
            or result.model_metadata.get("model")!=attempt["model"]
            or result.model_metadata.get("profile_version")!=attempt["profile_version"]
            or result.model_metadata.get("prompt_hash")!=attempt["prompt_hash"]
            or result.output_hash!=digest_json(result.document)):
            raise ValueError("rewrite input/output binding mismatch")
        if result.profile_version == "full-prose-review-v1" and not result.error_code:
            from .procedure_rewrite_full import render_full, validate_full
            source = job["checkpoint"]["normalized_document"]
            full_validation = validate_full(source,result.document,response=result.raw_response)
            if digest_json(render_full(source,result.raw_response)) != digest_json(result.document) or not full_validation.passed:
                raise ValueError("rewrite operation binding mismatch")
        if result.profile_version == "technical-prose-v2" and not result.error_code:
            _bind_v2_operations(job["checkpoint"]["normalized_document"], result.document, result.raw_response)
        revision=uuid4()
        cur.execute("""INSERT INTO canonical_article_revisions
            (canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,status,
             normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata)
            VALUES (%s,%s,%s,%s,%s,%s,'building',%s,%s,%s,%s,%s,%s,'{}',%s,%s,%s)""",
            (revision,job["canonical_article_id"],job["source_revision_id"],job["transformation_key"],job["normalization_version"],job["rewrite_profile_version"],
             Jsonb(job["checkpoint"]["normalized_document"]),result.input_hash,Jsonb(result.document),projection["body"],Jsonb(projection["steps"]),Jsonb(projection["images"]),digest_json({}),result.output_hash,Jsonb(result.model_metadata)))
        cur.execute("""UPDATE canonical_article_rewrite_attempts SET canonical_article_revision_id=%s,status=%s,response=%s,response_hash=%s,error_code=%s,completed_at=clock_timestamp() WHERE rewrite_attempt_id=%s""",
            (revision,"failed" if result.error_code else "succeeded",Jsonb(result.raw_response),digest_json(result.raw_response),result.error_code,attempt["rewrite_attempt_id"]))
        cur.execute("UPDATE source_fetch_jobs SET phase='validating',checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",(Jsonb({"candidate_revision_id":str(revision),"rewrite_error_code":result.error_code}),lease.job_id))
        if result.profile_version == "full-prose-review-v1" and not result.error_code:
            # The saved response, mechanical validation and review wait are one
            # commit, so process loss on the final delivery cannot exhaust it.
            cur.execute("UPDATE canonical_article_revisions SET status='validated',validation_report=%s,validation_hash=%s WHERE canonical_article_revision_id=%s",
                (Jsonb(full_validation.report),digest_json(full_validation.report),revision))
            checkpoint = {"version":1,"state":"awaiting_review","candidate_revision_id":str(revision),"candidate_hash":result.output_hash}
            cur.execute("""UPDATE source_fetch_jobs SET status='needs_review',phase='publishing',error_code='CONTENT_REVIEW_REQUIRED',retryable=false,
                next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,
                checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s""",
                (Jsonb({"content_review":checkpoint,"validation_hash":digest_json(full_validation.report)}),lease.job_id))
        return revision


def load_candidate(repo,lease):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_=_lock_transform(cur,lease)
        return cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s",(job["transformation_key"],)).fetchone()


def store_validation(repo,lease,validation):
    from .article_lifecycle_types import digest_json
    from .procedure_rewrite import validate_article_rewrite
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_=_lock_transform(cur,lease)
        candidate=cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE",(job["transformation_key"],)).fetchone()
        if candidate is None: raise ValueError("missing candidate")
        expected=full_candidate_validation(cur,job,candidate) if job["rewrite_profile_version"] == "full-prose-review-v1" else validate_article_rewrite(candidate["normalized_source_document"],candidate["canonical_document"],profile_version=job["rewrite_profile_version"])
        if (expected != validation or (job["rewrite_profile_version"] in ("technical-prose-v2", "full-prose-review-v1")
            and (type(validation.passed) is not bool or digest_json(expected.report) != digest_json(validation.report)))):
            raise ValueError("validation report binding mismatch")
        if expected.passed and job["rewrite_profile_version"] == "technical-prose-v2":
            attempt=cur.execute("SELECT response FROM canonical_article_rewrite_attempts WHERE canonical_article_revision_id=%s AND status='succeeded'",(candidate["canonical_article_revision_id"],)).fetchone()
            if attempt is None: raise ValueError("rewrite operation binding mismatch")
            _bind_v2_operations(candidate["normalized_source_document"], candidate["canonical_document"], attempt["response"])
        if candidate["status"] in ("validated","rejected"):
            if candidate["validation_report"]!=validation.report: raise ValueError("validation is immutable")
            return
        cur.execute("UPDATE canonical_article_revisions SET status=%s,validation_report=%s,validation_hash=%s WHERE canonical_article_revision_id=%s",("validated" if validation.passed else "rejected",Jsonb(validation.report),digest_json(validation.report),candidate["canonical_article_revision_id"]))
        cur.execute("UPDATE source_fetch_jobs SET phase='publishing',checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",(Jsonb({"validation_hash":digest_json(validation.report)}),lease.job_id))
        if expected.passed and job["rewrite_profile_version"] == "full-prose-review-v1":
            checkpoint = {"version":1,"state":"awaiting_review","candidate_revision_id":str(candidate["canonical_article_revision_id"]),"candidate_hash":digest_json(candidate["canonical_document"])}
            cur.execute("""UPDATE source_fetch_jobs SET status='needs_review',error_code='CONTENT_REVIEW_REQUIRED',retryable=false,
                next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,
                checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s""",(Jsonb({"content_review":checkpoint}),lease.job_id))


def publish_article_revision(repo,lease,revision_id,*,hooks=None):
    from .article_lifecycle_types import digest_json
    from .article_document import project_ordered_document
    from .procedure_rewrite import validate_article_rewrite
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job=cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",(lease.job_id,)).fetchone()
        if job is None or job["lease_token"]!=lease.token: raise LeaseLost("publication owner changed")
        if job["status"]=="completed":
            published=cur.execute("""SELECT r.canonical_article_revision_id FROM canonical_article_revisions r
                JOIN canonical_articles a ON a.current_canonical_revision_id=r.canonical_article_revision_id
                WHERE r.canonical_article_revision_id=%s AND r.transformation_key=%s AND r.status='published'
                  AND a.current_job_id=%s AND a.current_source_revision_id=r.source_revision_id
                  AND a.request_generation=%s""",(revision_id,job["transformation_key"],lease.job_id,job["request_generation"])).fetchone()
            if published: return published["canonical_article_revision_id"]
            raise LeaseLost("completed publication no longer current")
        job,article=_lock_transform(cur,lease)
        row=cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s FOR UPDATE",(revision_id,)).fetchone()
        if row is None: raise ValueError("missing candidate")
        projection=project_ordered_document(row["canonical_document"])
        validation=full_candidate_validation(cur,job,row) if job["rewrite_profile_version"] == "full-prose-review-v1" else validate_article_rewrite(row["normalized_source_document"],row["canonical_document"],profile_version=job["rewrite_profile_version"])
        if (job["rewrite_profile_version"] == "technical-prose-v2"
            and digest_json(row["validation_report"]) != digest_json(validation.report)):
            raise ValueError("publication binding validation failed")
        if (row["status"]!="validated" or row["transformation_key"]!=job["transformation_key"]
            or row["source_revision_id"]!=job["source_revision_id"] or row["canonical_article_id"]!=job["canonical_article_id"]
            or row["normalization_version"]!=job["normalization_version"] or row["rewrite_profile_version"]!=job["rewrite_profile_version"]
            or row["normalized_source_hash"]!=digest_json(row["normalized_source_document"])
            or row["rewrite_result_hash"]!=digest_json(row["canonical_document"])
            or not validation.passed or row["validation_report"]!=validation.report
            or row["validation_hash"]!=digest_json(validation.report)
            or projection!={"body":row["canonical_body"],"steps":row["canonical_steps"],"images":row["canonical_images"]}):
            raise ValueError("publication binding validation failed")
        if job["rewrite_profile_version"] == "full-prose-review-v1":
            from .article_content_review import resolve_full_evidence
            attempt, _, _, _ = resolve_full_evidence(cur,job,row)
        else:
            attempt=cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE canonical_article_revision_id=%s AND status='succeeded'",(revision_id,)).fetchone()
        if (attempt is None or attempt["input_hash"]!=row["normalized_source_hash"]
            or attempt["response_hash"]!=digest_json(attempt["response"])
            or attempt["prompt_hash"]!=row["model_metadata"].get("prompt_hash")
            or attempt["model"]!=row["model_metadata"].get("model")
            or attempt["profile_version"]!=row["model_metadata"].get("profile_version")):
            raise ValueError("publication attempt binding failed")
        if job["rewrite_profile_version"] == "technical-prose-v2":
            _bind_v2_operations(row["normalized_source_document"], row["canonical_document"], attempt["response"])
        if job["rewrite_profile_version"] == "full-prose-review-v1":
            _require_full_approval(cur,job,article,row)
        cur.execute("UPDATE canonical_article_revisions SET status='published',published_at=clock_timestamp() WHERE canonical_article_revision_id=%s",(revision_id,))
        if hooks is not None:hooks("inside_publication")
        cur.execute("UPDATE canonical_articles SET current_canonical_revision_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s",(revision_id,lease.canonical_article_id))
        cur.execute("UPDATE source_fetch_jobs SET status='completed',phase='completed',retryable=false,error_code=NULL,next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",(lease.job_id,))
        cur.execute("""INSERT INTO publication_events(publication_event_id,event_type,event_version,canonical_article_id,canonical_article_revision_id,correlation_id,idempotency_key,payload,producer)
            VALUES (%s,'catalog.article.published',1,%s,%s,%s,%s,%s,'ingestion-worker') ON CONFLICT(idempotency_key) DO NOTHING""",
            (uuid4(),lease.canonical_article_id,revision_id,job["correlation_id"],"catalog.article.published:"+job["transformation_key"],Jsonb({"source_revision_id":str(job["source_revision_id"]),"review_status":"APPROVED" if job["rewrite_profile_version"] == "full-prose-review-v1" else "UNREVIEWED"})))
        return revision_id


def record_rewrite_failure(repo,lease,*,code,ambiguous=False):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        _lock_transform(cur,lease)
        cur.execute("""UPDATE canonical_article_rewrite_attempts SET status=%s,error_code=%s,completed_at=clock_timestamp()
            WHERE source_fetch_job_id=%s AND lease_token=%s AND status IN ('prepared','dispatched')""",
            ("ambiguous" if ambiguous else "failed",code,lease.job_id,lease.token))
