"""Transactional identity/source store; all connections belong to their caller."""

from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from uuid import UUID, uuid4
from .article_document import has_ordered_list_numbering, has_structured_list_items
from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, AUTOMATIC_REWRITE_PROFILES, MAX_CORRECTION_CALLS, MAX_LINKED_PDFS,
    SOURCE_BOUND_CORRECTION_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, SOURCE_PROJECTION_VERSIONS,
    digest_json, transformation_key,
)
from .source_job_persistence import (
    REQUIRE_POSITIONED_SVG_REFRESH, STAGED_MEDIA_REFRESH, LeaseLost, lock_live_lease,
    staged_media_refresh_binding, transform_source_matches,
)

from psycopg.errors import DataError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import ArticleKey, article_id, identity_key


def upsert_article_descriptor(
    repo, key: ArticleKey, descriptor: dict, descriptor_snapshot_id, generation: int,
    *, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE
):
    with repo.connect() as conn:
        return _upsert_descriptor(
            conn, key, descriptor, descriptor_snapshot_id, generation, rewrite_profile_version=rewrite_profile_version
        )


def _upsert_descriptor(conn, key, descriptor, snapshot, generation, *, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE):
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            """INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,vehicle_configuration_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id,title,kind,component,source_sort_order,last_seen_catalog_generation,target_rewrite_profile_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                rewrite_profile_version,
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


def store_source_body_preview(
    repo, lease, context, resource, document, *, linked_document=None, linked_resources=()
):
    """Bind the parsed body to a live article generation without publishing it."""
    body_ref = context.descriptor.get("resource_ref") or context.descriptor.get("body_resource_ref")
    if (article_id(context.key) != lease.canonical_article_id or resource["provider"] != context.key.provider
            or resource["role"] != "body" or resource["opaque_ref"] != body_ref):
        raise ValueError("source body preview identity mismatch")
    if (bool(linked_resources) != (linked_document is not None) or len(linked_resources) > MAX_LINKED_PDFS
            or any(
                child["provider"] != context.key.provider or child["role"] != "document_asset"
                or child["media_type"] != "application/pdf" or child["opaque_ref"] == body_ref
                for child in linked_resources
            )):
        raise ValueError("linked source preview identity mismatch")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job = lock_live_lease(cur, lease)
        article = cur.execute("""
            SELECT current_job_id,request_generation,current_source_revision_id,descriptor_source_snapshot_id,
                   membership_status,takedown_status
            FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE
            """, (lease.canonical_article_id,)).fetchone()
        if (article is None or article["current_job_id"] != lease.job_id
                or job["canonical_article_id"] != lease.canonical_article_id
                or article["request_generation"] != job["request_generation"]
                or job["request_generation"] != lease.generation):
            raise LeaseLost("article generation changed during body preview")
        if (job["phase"] != "fetching_source" or job["source_revision_id"] is not None
                or article["current_source_revision_id"] is not None
                or article["membership_status"] != "active" or article["takedown_status"] != "active"
                or article["descriptor_source_snapshot_id"] != context.descriptor_snapshot_id):
            return
        snapshot = persist_resource(cur, resource)
        preview = {
            "snapshot_id": str(snapshot),
            "descriptor_snapshot_id": str(context.descriptor_snapshot_id),
        }
        if document is not None:
            preview["document"] = document
        if linked_document is not None:
            preview["linked_preview"] = {
                "document": linked_document,
                "snapshot_ids": list(dict.fromkeys(str(persist_resource(cur, child)) for child in linked_resources)),
            }
        cur.execute("""
            UPDATE source_fetch_jobs SET checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s
            """, (Jsonb({"source_body_preview": preview}), lease.job_id))


def store_captured_source(repo, lease, captured):
    """Source revision, observation, pointer and transformation transition are atomic."""
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        return _store_captured_source(cur, lease, captured)


def _store_captured_source(cur, lease, captured):
    """Use the caller's transaction, including exact source-only job creation."""
    if captured.projection_version not in SOURCE_PROJECTION_VERSIONS:
        raise ValueError("unsupported source projection version")
    context = captured.context
    if (
        article_id(context.key) != lease.canonical_article_id
        or not captured.source_body.strip()
        or not captured.source_document.get("blocks")
    ):
        raise ValueError("captured article identity/body mismatch")
    job = lock_live_lease(cur, lease)
    source_only = job["checkpoint"].get("source_only_reprojection") is True
    article_query = """
        SELECT a.*, s.projection_version AS current_projection_version,
                    s.source_fingerprint AS current_source_fingerprint
        FROM canonical_articles a
        LEFT JOIN canonical_article_source_revisions s ON s.source_revision_id=a.current_source_revision_id
        WHERE a.canonical_article_id=%s
    """
    article_params = (lease.canonical_article_id,)

    structural_versions = (
        "source-projection-v5", "source-projection-v6", "source-projection-v7", "source-projection-v8",
        "source-projection-v9", "source-projection-v10",
    )
    new_structure = captured.projection_version in structural_versions
    live_capture = not source_only and (captured.projection_version == "source-projection-v2" or new_structure)
    numbered_lists = live_capture and not new_structure and has_ordered_list_numbering(captured.source_document)
    structured_lists = live_capture and not new_structure and (numbered_lists or has_structured_list_items(captured.source_document))

    def effective_projection(article):
        if not live_capture:
            return captured.projection_version
        current = article["current_projection_version"]
        published_same_bytes = (
            article["current_canonical_revision_id"] is not None
            and article["current_source_fingerprint"] == captured.source_fingerprint
        )
        # A new projection never replaces a same-byte publication in place.
        if published_same_bytes and (new_structure or structured_lists):
            return current
        if current in structural_versions:
            if new_structure:
                return max(current, captured.projection_version, key=SOURCE_PROJECTION_VERSIONS.index)
            return current
        if new_structure:
            return captured.projection_version
        if numbered_lists or current == "source-projection-v4":
            return "source-projection-v4"
        if structured_lists or current == "source-projection-v3":
            return "source-projection-v3"
        return captured.projection_version

    # A full review owner may be adopted below. Lock it before the article,
    # matching review/publication's job -> article order even during refresh.
    review_owner = None
    review_projection = None
    if job["rewrite_profile_version"] == "full-prose-review-v1" and not source_only:
        before_lock = cur.execute(article_query, article_params).fetchone()
        review_projection = effective_projection(before_lock)
        review_key = transformation_key(
            lease.canonical_article_id, captured.source_fingerprint,
            job["normalization_version"], job["rewrite_profile_version"],
            projection_version=review_projection,
        )
        review_owner = cur.execute(
            "SELECT * FROM source_fetch_jobs WHERE transformation_key=%s FOR UPDATE", (review_key,)
        ).fetchone()
    article = cur.execute(article_query + " FOR UPDATE OF a", article_params).fetchone()
    if (
        article["request_generation"] != job["request_generation"]
        or article["current_job_id"] != lease.job_id
    ):
        raise LeaseLost("article generation changed")
    if REQUIRE_POSITIONED_SVG_REFRESH in job["checkpoint"] and (
        not captured.recovered_legacy_bankone_svg
        or job["checkpoint"][REQUIRE_POSITIONED_SVG_REFRESH] != {
            "source_revision_id": str(article["current_source_revision_id"]),
            "canonical_revision_id": str(article["current_canonical_revision_id"]),
        }
    ):
        raise ValueError("LEGACY_SVG_REFRESH_BINDING_INVALID")
    current_version = article["current_projection_version"]
    projection = effective_projection(article)
    if review_projection is not None and review_projection != projection:
        raise LeaseLost("article source projection changed")
    if current_version and SOURCE_PROJECTION_VERSIONS.index(projection) < SOURCE_PROJECTION_VERSIONS.index(current_version):
        raise ValueError("source projection downgrade is not supported")
    if captured.projection_version != projection:
        captured = replace(captured, projection_version=projection)
    observed = cur.execute(
        "SELECT source_revision_id FROM canonical_article_source_observations WHERE source_fetch_job_id=%s",
        (lease.job_id,),
    ).fetchone()
    if observed:
        return observed["source_revision_id"]
    revision_id = _persist_article_capture(
        cur, lease.canonical_article_id, lease.job_id, job["request_generation"], captured,
        verify_existing=source_only and projection == "source-projection-v3",
    )
    if source_only:
        cur.execute("""UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=NULL,
            status='needs_review',phase='completed',error_code='SOURCE_ONLY_REPROJECTION',retryable=false,
            next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,
            checkpoint=checkpoint-'source_body_preview',
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
    staged = captured.recovered_legacy_bankone_svg and not published
    if staged:
        binding = {STAGED_MEDIA_REFRESH: staged_media_refresh_binding(article, revision_id)}
        staged_job = {**job, "source_revision_id": revision_id, "checkpoint": {**job["checkpoint"], **binding}}
        _require_staged_media_refresh_rights(cur, staged_job, article)
    else:
        binding = {}
    if owner and owner["source_fetch_job_id"] != lease.job_id:
        terminal = owner["status"] in ("needs_review", "dead_letter") or bool(
            rejected
        )
        if not published and not terminal:
            raise LeaseLost("transformation already has an owner")
        checkpoint = {
            **binding,
            "reused_terminal_result": terminal,
            "reused_transformation_job_id": str(owner["source_fetch_job_id"]),
        }
        if published:
            checkpoint["reused_published_revision_id"] = str(current_canonical)
        cur.execute(
            """UPDATE source_fetch_jobs SET source_revision_id=%s,phase='completed',status='completed',checkpoint=(checkpoint-'source_body_preview')||%s,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,retryable=false,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (revision_id, Jsonb(checkpoint), lease.job_id),
        )
        if terminal:
            if not staged:
                current_job = owner["source_fetch_job_id"]
            if (review_owner is not None and owner["status"] == "needs_review"
                and job["rewrite_profile_version"] == "full-prose-review-v1"
                and owner["source_revision_id"] == revision_id
                and owner["normalization_version"] == job["normalization_version"]
                and owner["rewrite_profile_version"] == job["rewrite_profile_version"]
                and (not staged or owner["checkpoint"].get(STAGED_MEDIA_REFRESH) == binding[STAGED_MEDIA_REFRESH])):
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
                    current_job = owner["source_fetch_job_id"]
                    cur.execute("""UPDATE source_fetch_jobs SET request_generation=%s,
                        checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
                        (adopted_generation,Jsonb({"content_review":review_checkpoint,
                            "review_owner_adoption":{"previous_generation":owner["request_generation"],
                                "inspection_job_id":str(lease.job_id),"inspection_generation":job["request_generation"]}}),current_job))
                    cur.execute("UPDATE canonical_articles SET request_generation=%s WHERE canonical_article_id=%s",
                        (adopted_generation,lease.canonical_article_id))
    else:
        cur.execute(
            """UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s,phase='normalizing',
                checkpoint=(checkpoint-'source_body_preview')||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (revision_id, key, Jsonb(binding), lease.job_id),
        )
    if staged:
        if current_job != lease.job_id:
            cur.execute("""UPDATE canonical_articles SET current_job_id=%s,updated_at=clock_timestamp()
                WHERE canonical_article_id=%s""", (current_job, lease.canonical_article_id))
        return revision_id
    cur.execute(
        """UPDATE canonical_articles SET current_source_revision_id=%s,current_canonical_revision_id=%s,current_job_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
        (revision_id, current_canonical, current_job, lease.canonical_article_id),
    )
    return revision_id


def _persist_article_capture(cur, canonical_article_id, job_id, generation, captured, *, verify_existing=False):
    """Append immutable source and observation inside an article owner's transaction."""
    context = captured.context
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
            canonical_article_id,
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
            """SELECT source_revision_id, source_document FROM canonical_article_source_revisions
            WHERE canonical_article_id=%s AND source_fingerprint=%s AND projection_version=%s""",
            (canonical_article_id, captured.source_fingerprint, captured.projection_version),
        ).fetchone()
        if verify_existing and row["source_document"] != captured.source_document:
            raise ValueError("SOURCE_MEDIA_REPLAY_PROJECTION_CONFLICT")
    revision_id = row["source_revision_id"]
    provenance = _remap_snapshot_references(captured.resource_provenance, snapshots)
    body_resource = next(r for r in captured.resources if r["role"] == "body")
    cur.execute(
        """INSERT INTO canonical_article_source_observations(source_observation_id,canonical_article_id,source_revision_id,source_fetch_job_id,request_generation,body_provider_revision,resource_provenance,captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            uuid4(),
            canonical_article_id,
            revision_id,
            job_id,
            generation,
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
            """SELECT descriptor_source_snapshot_id,resolution_source_snapshot_id,captured_context
            FROM canonical_article_source_observations WHERE source_revision_id=%s
            ORDER BY captured_at,source_observation_id LIMIT 1""",
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
        or not transform_source_matches(article, job)
        or article["target_normalization_version"] != job["normalization_version"]
        or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
        or job["rewrite_profile_version"] != lease.rewrite_profile_version):
        raise LeaseLost("transformation generation/source changed")
    return job, article


def _require_staged_media_refresh_rights(cur, job, article):
    from .source_job_persistence import source_bound_rewrite_source_allowed
    from .source_media_replay import _check_review_quarantine, _load_snapshots

    unavailable = "STAGED_MEDIA_REFRESH_SOURCE_UNAVAILABLE"
    if (not transform_source_matches(article, job)
            or not source_bound_rewrite_source_allowed(cur, article, article["current_source_revision_id"])):
        raise ValueError(unavailable)
    row = cur.execute("""SELECT candidate.body_source_snapshot_id,candidate.resource_manifest,
               prior.resource_manifest AS prior_manifest, prior_observation.resource_provenance AS prior_provenance,
               prior_observation.descriptor_source_snapshot_id AS prior_descriptor,
               prior_observation.resolution_source_snapshot_id AS prior_resolution,
               observation.resource_provenance,observation.descriptor_source_snapshot_id,observation.resolution_source_snapshot_id
        FROM canonical_article_source_revisions candidate
        JOIN canonical_article_source_observations observation
          ON observation.source_revision_id=candidate.source_revision_id
          AND observation.canonical_article_id=candidate.canonical_article_id
        JOIN canonical_article_source_revisions prior
          ON prior.source_revision_id=%s AND prior.canonical_article_id=candidate.canonical_article_id
        JOIN LATERAL (
            SELECT resource_provenance,descriptor_source_snapshot_id,resolution_source_snapshot_id
            FROM canonical_article_source_observations o
            WHERE o.source_revision_id=prior.source_revision_id AND o.canonical_article_id=prior.canonical_article_id
            ORDER BY captured_at,source_observation_id LIMIT 1
        ) prior_observation ON true
        JOIN catalog_article_current served ON served.canonical_article_id=candidate.canonical_article_id
        WHERE candidate.source_revision_id=%s AND candidate.canonical_article_id=%s
          AND candidate.body_source_snapshot_id=prior.body_source_snapshot_id
          AND observation.source_fetch_job_id=%s AND observation.request_generation<=%s
          AND observation.descriptor_source_snapshot_id=%s
          AND served.canonical_revision_id=%s""",
        (article["current_source_revision_id"], job["source_revision_id"], article["canonical_article_id"],
         job["source_fetch_job_id"], job["request_generation"], article["descriptor_source_snapshot_id"],
         article["current_canonical_revision_id"])).fetchone()
    if row is None:
        raise ValueError(unavailable)
    try:
        resources = {}
        for manifest, provenance in ((row["resource_manifest"], row["resource_provenance"]),
                                     (row["prior_manifest"], row["prior_provenance"])):
            for entry, proof in zip(manifest, provenance, strict=True):
                checksum = entry.get("sha256")
                if checksum:
                    snapshot = UUID(proof["source_snapshot_id"])
                    if checksum != proof["sha256"] or resources.setdefault(snapshot, checksum) != checksum:
                        raise ValueError(unavailable)
        if row["body_source_snapshot_id"] not in resources:
            raise ValueError(unavailable)
        ids = set(resources) | {row[field] for field in (
            "descriptor_source_snapshot_id", "resolution_source_snapshot_id", "prior_descriptor", "prior_resolution",
        )}
        # Rights on either projection must stay held through a publication.
        snapshots = _load_snapshots(cur, ids, resource_ids=set(resources), lock=True)
        if any(snapshot.digest != resources[snapshot.id] for snapshot in snapshots if snapshot.id in resources):
            raise ValueError(unavailable)
        _check_review_quarantine(cur, ids, lock=True)
        if not source_bound_rewrite_source_allowed(cur, article, article["current_source_revision_id"]):
            raise ValueError(unavailable)
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(unavailable) from None


def _require_source_bound_rewrite_rights(cur, job, article):
    if STAGED_MEDIA_REFRESH in job["checkpoint"]:
        _require_staged_media_refresh_rights(cur, job, article)
        if "source_bound_rewrite" not in job["checkpoint"] and job["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE:
            return
    profile = job["rewrite_profile_version"]
    marker_version = {SOURCE_BOUND_REWRITE_PROFILE: 1, SOURCE_BOUND_CORRECTION_PROFILE: 2}.get(profile)
    predecessor_observation = None
    if "source_bound_rewrite" in job["checkpoint"] or profile == SOURCE_BOUND_CORRECTION_PROFILE:
        marker = job["checkpoint"].get("source_bound_rewrite")
        if (marker_version is None or not isinstance(marker, dict)
            or type(marker.get("version")) is not int or marker["version"] != marker_version
            or not job["source_revision_id"] or marker.get("source_revision_id") != str(job["source_revision_id"])):
            raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID")
        if "prior_source_observation_id" in marker:
            generation = marker.get("prior_generation")
            if marker_version != 1 or type(generation) is not int or generation + 1 != job["request_generation"]:
                raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID")
            try:
                predecessor_observation = (
                    UUID(marker["prior_source_observation_id"]), UUID(marker["prior_job_id"]), generation,
                )
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID") from None
        if marker_version == 2 and ("correction_method" in marker or "first_draft_observation_id" in marker):
            from .procedure_rewrite_sentence_correction import SENTENCE_CORRECTION_METHOD
            if marker.get("correction_method") != SENTENCE_CORRECTION_METHOD:
                raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID")
            try:
                prior_id = UUID(marker["prior_job_id"])
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID") from None
            if "first_draft_observation_id" in marker:
                generation = marker.get("prior_generation")
                if type(generation) is not int or generation + 1 != job["request_generation"]:
                    raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID")
                try:
                    predecessor_observation = (UUID(marker["first_draft_observation_id"]), prior_id, generation)
                except (AttributeError, TypeError, ValueError):
                    raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID") from None
            else:
                prior = cur.execute("""SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s
                    AND canonical_article_id=%s AND source_revision_id=%s AND rewrite_profile_version=%s""",
                    (prior_id, job["canonical_article_id"], job["source_revision_id"], SOURCE_BOUND_REWRITE_PROFILE),
                ).fetchone()
                if prior is None:
                    raise ValueError("SOURCE_BOUND_REWRITE_BINDING_INVALID")
                # A v2 draft can be tied to a specific source-only observation.
                _require_source_bound_rewrite_rights(cur, prior, article)
                return
    if marker_version is not None:
        from .source_job_persistence import source_bound_rewrite_source_allowed
        if not source_bound_rewrite_source_allowed(
            cur, article, job["source_revision_id"], predecessor_observation=predecessor_observation,
        ):
            raise ValueError("SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE")


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
    if lease.rewrite_profile_version == SOURCE_BOUND_CORRECTION_PROFILE:
        raise ValueError("SOURCE_BOUND_CORRECTION_DISPATCH_REQUIRED")
    prompt=build_rewrite_prompt(document,context=context,profile_version=lease.rewrite_profile_version)
    if len(prompt.encode())>200*1024: raise ValueError("REWRITE_INPUT_LIMIT")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job,article=_lock_transform(cur,lease)
        _require_source_bound_rewrite_rights(cur, job, article)
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
        job,article=_lock_transform(cur,lease)
        if job["rewrite_profile_version"] == SOURCE_BOUND_CORRECTION_PROFILE:
            raise ValueError("SOURCE_BOUND_CORRECTION_DISPATCH_REQUIRED")
        _require_source_bound_rewrite_rights(cur, job, article)
        recovery=job["checkpoint"].get("bankone_exact_recovery")
        if "bankone_exact_recovery" in job["checkpoint"]:
            if (not isinstance(recovery,dict) or recovery.get("version")!=1
                or type(recovery.get("lease_token")) is not int or recovery["lease_token"]!=lease.token
                or recovery.get("state")!="prepared"
                or type(recovery.get("max_additional_dispatches")) is not int or recovery["max_additional_dispatches"]!=1
                or type(recovery.get("dispatches_consumed")) is not int or recovery["dispatches_consumed"]!=0):
                raise ValueError("RECOVERY_DISPATCH_BLOCKED")
        changed=cur.execute("""UPDATE canonical_article_rewrite_attempts SET status='dispatched',dispatched_at=clock_timestamp()
            WHERE rewrite_attempt_id=%s AND source_fetch_job_id=%s AND lease_token=%s AND profile_version=%s
              AND status='prepared' RETURNING rewrite_attempt_id""",
            (attempt,lease.job_id,lease.token,job["rewrite_profile_version"])).fetchone()
        if changed is None: raise ValueError("attempt cannot dispatch again")
        if recovery is not None:
            consumed={**recovery,"state":"dispatched","dispatches_consumed":1}
            cur.execute("UPDATE source_fetch_jobs SET checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",
                (Jsonb({"bankone_exact_recovery":consumed}),lease.job_id))


_CORRECTION_EVIDENCE_INVALID = "REWRITE_CORRECTION_EVIDENCE_INVALID"
_CORRECTION_SERVER = "server-source-bound-correction"


def _bound_correction_draft(cur, job, document):
    from .procedure_rewrite_auto import _NOTE_LABEL_PROMPT_VERSION
    from .source_job_persistence import source_bound_correction_prior_attempt

    checkpoint = job["checkpoint"]
    binding = checkpoint.get("source_bound_rewrite")
    if (job["job_kind"] != "article" or job["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
        or job["max_attempts"] != 1 or job["retry_count"] != 1
        or not isinstance(binding, dict) or type(binding.get("version")) is not int or binding["version"] != 2
        or not job["source_revision_id"] or binding.get("source_revision_id") != str(job["source_revision_id"])
        or type(binding.get("prior_generation")) is not int
        or binding["prior_generation"] + 1 != job["request_generation"]
        or type(binding.get("model_call_budget")) is not int
        or not 1 <= binding["model_call_budget"] <= MAX_CORRECTION_CALLS
        or checkpoint.get("normalized_document") != document
        or checkpoint.get("normalized_hash") != digest_json(document)):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    first_draft = "first_draft_observation_id" in binding
    if "correction_method" in binding or first_draft:
        from .procedure_rewrite_sentence_correction import MAX_SENTENCE_CORRECTION_CALLS, SENTENCE_CORRECTION_METHOD
        if (binding.get("correction_method") != SENTENCE_CORRECTION_METHOD
            or binding["model_call_budget"] > MAX_SENTENCE_CORRECTION_CALLS):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    try:
        prior_id = UUID(binding["prior_job_id"])
    except (TypeError, ValueError, KeyError, AttributeError):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID) from None
    # The scheduler locks the prior job before the article. Its terminal row is
    # read without a new lock here while the current job and article are fenced.
    prior = cur.execute(
        "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,),
    ).fetchone()
    if (prior is None or prior["request_generation"] > binding["prior_generation"]
        or (first_draft and prior["request_generation"] != binding["prior_generation"])
        or any(prior[field] != job[field] for field in (
            "canonical_article_id", "canonical_vehicle_id", "source_vehicle_ref",
            "source_article_ref", "provider_slug", "source_revision_id", "normalization_version",
        )) or prior["checkpoint"].get("normalized_document") != document):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    source = cur.execute("""SELECT source_fingerprint,projection_version
        FROM canonical_article_source_revisions WHERE source_revision_id=%s AND canonical_article_id=%s""",
        (job["source_revision_id"], job["canonical_article_id"])).fetchone()
    if source is None:
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    key_inputs = (job["canonical_article_id"], source["source_fingerprint"], job["normalization_version"])
    for owner in (prior, job):
        if owner["transformation_key"] != transformation_key(
            *key_inputs, owner["rewrite_profile_version"], projection_version=source["projection_version"],
        ):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    attempt = source_bound_correction_prior_attempt(cur, prior, first_draft=first_draft)
    if (binding.get("prior_attempt_id") != str(attempt["rewrite_attempt_id"])
        or binding.get("prior_response_hash") != attempt["response_hash"]
        or (first_draft and binding["first_draft_observation_id"] != str(attempt["observation_id"]))):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    return {**binding, "preserve_notes": attempt["guard_version"] == _NOTE_LABEL_PROMPT_VERSION}, attempt["response"]


def _validate_correction_rounds(rounds, *, limit, model, token, input_hash, revision):
    if len(rounds) > limit or not isinstance(model, str) or not model.strip():
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    for number, attempt in enumerate(rounds, 1):
        if (attempt["lease_token"] != token or attempt["attempt_number"] != number
            or attempt["profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
            or attempt["provider"] != "inception" or attempt["model"] != model
            or attempt["input_hash"] != input_hash
            or attempt["status"] != "succeeded" or attempt["error_code"] is not None
            or attempt["dispatched_at"] is None or attempt["completed_at"] is None
            or attempt["dispatched_at"] > attempt["completed_at"]
            or attempt["canonical_article_revision_id"] != (revision if number == len(rounds) else None)):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)


def _correction_round_bindings(rounds):
    return [
        {"attempt_id": str(row["rewrite_attempt_id"]), "prompt_hash": row["prompt_hash"],
         "response_hash": row["response_hash"]}
        for row in rounds
    ]


def resolve_source_bound_correction(cur, job, candidate):
    """Rebuild a correction and bind every provider round to its publication."""
    from .article_document import project_ordered_document
    from .procedure_rewrite_correction import (
        _CORRECTION_METHOD, correction_recovery_for_method, replay_retained_correction,
    )

    source = candidate["normalized_source_document"]
    binding, previous = _bound_correction_draft(cur, job, source)
    metadata = candidate["model_metadata"]
    evidence = metadata.get("correction_evidence")
    method = metadata.get("transformation_method")
    scheduled_method = binding.get("correction_method", _CORRECTION_METHOD)
    token = metadata.get("model_lease_token")
    revision = candidate["canonical_article_revision_id"]
    if (candidate["normalized_source_hash"] != digest_json(source)
        or any(candidate[field] != job[field] for field in (
            "canonical_article_id", "source_revision_id", "normalization_version",
            "rewrite_profile_version", "transformation_key",
        ))
        or metadata.get("profile_version") != SOURCE_BOUND_CORRECTION_PROFILE
        or not isinstance(evidence, dict) or type(token) is not int or not 1 <= token <= job["lease_token"]):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    rounds = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
        WHERE source_fetch_job_id=%s ORDER BY attempt_number,lease_token""", (job["source_fetch_job_id"],)).fetchall()
    if rounds:
        if metadata.get("provider") != "inception":
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        _validate_correction_rounds(
            rounds, limit=binding["model_call_budget"], model=metadata.get("model"), token=token,
            input_hash=candidate["normalized_source_hash"], revision=revision,
        )
    elif metadata.get("provider") != "server" or metadata.get("model") != _CORRECTION_SERVER:
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    if method == scheduled_method:
        result = replay_retained_correction(
            source, previous, model_call_budget=binding["model_call_budget"], evidence=evidence, attempts=rounds,
            method=scheduled_method, preserve_notes=binding["preserve_notes"],
        )
    else:
        recovery_method, recover = correction_recovery_for_method(scheduled_method)
        recovery = metadata.get("correction_recovery")
        if (method != recovery_method
            or not rounds or not isinstance(recovery, dict)
            or recovery != job["checkpoint"].get("correction_recovery")
            or recovery.get("attempts") != _correction_round_bindings(rounds)):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        result = recover(
            source, previous, model_call_budget=binding["model_call_budget"], attempts=rounds,
            preserve_notes=binding["preserve_notes"],
        )
        if (not recovery.get("terminal_error")
            or result.evidence.get("original_error_code") != recovery["terminal_error"]):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    if (result.error_code is not None or result.document is None
        or result.evidence != evidence
        or result.document != candidate["canonical_document"]
        or digest_json(result.document) != candidate["rewrite_result_hash"]
        or project_ordered_document(result.document) != {
            "body": candidate["canonical_body"], "steps": candidate["canonical_steps"],
            "images": candidate["canonical_images"],
        }):
        raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    return result


def _stage_correction_candidate(cur, job, document, result, *, model, token, attempts, recovery=None):
    from .article_document import project_ordered_document

    if result.error_code is not None or result.document is None:
        raise ValueError(result.error_code or _CORRECTION_EVIDENCE_INVALID)
    projection = project_ordered_document(result.document)
    revision = uuid4()
    metadata = {
        "transformation_method": result.evidence["method"], "profile_version": SOURCE_BOUND_CORRECTION_PROFILE,
        "provider": "inception" if attempts else "server", "model": model if attempts else _CORRECTION_SERVER,
        "model_lease_token": token, "correction_evidence": result.evidence,
    }
    if recovery is not None:
        metadata["correction_recovery"] = recovery
    candidate = cur.execute("""INSERT INTO canonical_article_revisions
        (canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,
         normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,
         canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,
         rewrite_result_hash,model_metadata)
        VALUES (%s,%s,%s,%s,%s,%s,'building',%s,%s,%s,%s,%s,%s,'{}',%s,%s,%s) RETURNING *""",
        (revision, job["canonical_article_id"], job["source_revision_id"], job["transformation_key"],
         job["normalization_version"], job["rewrite_profile_version"], Jsonb(document), digest_json(document),
         Jsonb(result.document), projection["body"], Jsonb(projection["steps"]), Jsonb(projection["images"]),
         digest_json({}), digest_json(result.document), Jsonb(metadata))).fetchone()
    if attempts:
        linked = cur.execute("""UPDATE canonical_article_rewrite_attempts SET canonical_article_revision_id=%s
            WHERE rewrite_attempt_id=%s AND source_fetch_job_id=%s AND lease_token=%s AND status='succeeded'
              AND canonical_article_revision_id IS NULL RETURNING rewrite_attempt_id""",
            (revision, attempts[-1]["rewrite_attempt_id"], job["source_fetch_job_id"], token)).fetchone()
        if linked is None:
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
    validation = automatic_candidate_validation(cur, job, candidate, require_current=True)
    validation_hash = digest_json(validation.report)
    cur.execute("""UPDATE canonical_article_revisions
        SET status='validated',validation_report=%s,validation_hash=%s WHERE canonical_article_revision_id=%s""",
        (Jsonb(validation.report), validation_hash, revision))
    return revision, validation_hash


def recover_source_bound_correction(repo, article_id, *, expected_job_id, expected_source_revision_id, actor, reason):
    """Stage a validated correction from the exact current terminal job's archived replies."""
    from .procedure_rewrite_correction import _CORRECTION_METHOD, correction_recovery_for_method

    article_id, expected_job_id, expected_source_revision_id = (
        UUID(str(value)) for value in (article_id, expected_job_id, expected_source_revision_id)
    )
    if not all(
        isinstance(value, str) and value.strip() and len(value) <= limit
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
        for value, limit in ((actor, 256), (reason, 2048))
    ):
        raise ValueError("SOURCE_BOUND_CORRECTION_RECOVERY_AUDIT_INVALID")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE",
                          (expected_job_id,)).fetchone()
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (article_id,)).fetchone()
        if (job is None or article is None or job["canonical_article_id"] != article_id
            or article["current_job_id"] != expected_job_id
            or article["current_source_revision_id"] != expected_source_revision_id
            or job["source_revision_id"] != expected_source_revision_id
            or article["request_generation"] != job["request_generation"]
            or article["target_normalization_version"] != job["normalization_version"]
            or article["target_rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
            or job["rewrite_profile_version"] != SOURCE_BOUND_CORRECTION_PROFILE
            or any(job[job_field] != article[article_field] for job_field, article_field in (
                ("canonical_vehicle_id", "vehicle_id"), ("provider_slug", "provider_slug"),
                ("source_vehicle_ref", "source_vehicle_ref"), ("source_article_ref", "source_article_ref"),
            ))
            or job["status"] != "dead_letter" or job["phase"] != "rewriting" or job["retryable"]
            or not job["error_code"] or job["lease_owner"] is not None or job["next_attempt_at"] is not None
            or article["current_canonical_revision_id"] is not None
            or job["checkpoint"].get("candidate_revision_id") is not None
            or "correction_recovery" in job["checkpoint"] or "new_article_rollout" in job["checkpoint"]):
            raise ValueError("SOURCE_BOUND_CORRECTION_RECOVERY_STALE")
        _require_source_bound_rewrite_rights(cur, job, article)
        document = job["checkpoint"].get("normalized_document")
        binding, previous = _bound_correction_draft(cur, job, document)
        recovery_method, recover = correction_recovery_for_method(binding.get("correction_method", _CORRECTION_METHOD))
        if cur.execute("SELECT 1 FROM canonical_article_revisions WHERE transformation_key=%s",
                       (job["transformation_key"],)).fetchone():
            raise ValueError("SOURCE_BOUND_CORRECTION_RECOVERY_STALE")
        rounds = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s ORDER BY attempt_number,lease_token FOR UPDATE""",
            (expected_job_id,)).fetchall()
        if not rounds:
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        model, token = rounds[0]["model"], job["lease_token"]
        _validate_correction_rounds(
            rounds, limit=binding["model_call_budget"], model=model, token=token,
            input_hash=job["checkpoint"]["normalized_hash"], revision=None,
        )
        result = recover(
            document, previous, model_call_budget=binding["model_call_budget"], attempts=rounds,
            preserve_notes=binding["preserve_notes"],
        )
        if (result.evidence.get("method") != recovery_method
            or result.evidence.get("original_error_code") != job["error_code"]):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        _require_source_bound_rewrite_rights(cur, job, article)
        recovery = {
            "actor": actor, "reason": reason, "terminal_error": job["error_code"],
            "attempts": _correction_round_bindings(rounds),
        }
        job["checkpoint"] = {**job["checkpoint"], "correction_recovery": recovery}
        revision, validation_hash = _stage_correction_candidate(
            cur, job, document, result, model=model, token=token, attempts=rounds, recovery=recovery,
        )
        cur.execute("""UPDATE source_fetch_jobs SET status='pending',phase='publishing',error_code=NULL,
            checkpoint=(checkpoint-'rewrite_error_code')||%s,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s""",
            (Jsonb({"candidate_revision_id": str(revision), "validation_hash": validation_hash,
                    "correction_recovery": recovery}), expected_job_id))
        return revision


def run_source_bound_correction(repo, lease, document, *, model_client, hooks=None):
    """Durably dispatch and validate a corrective chain inside one lease."""
    from .procedure_rewrite_correction import _CORRECTION_METHOD, correction_for_method

    input_hash = digest_json(document)
    model = getattr(model_client, "_model", "mercury-2")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("MODEL_CONFIGURATION_INVALID")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job, article = _lock_transform(cur, lease)
        _require_source_bound_rewrite_rights(cur, job, article)
        binding, previous = _bound_correction_draft(cur, job, document)
    attempts = []

    def fence(cur):
        job, article = _lock_transform(cur, lease)
        _require_source_bound_rewrite_rights(cur, job, article)
        if (job["phase"] != "rewriting" or job["checkpoint"].get("candidate_revision_id") is not None
            or _bound_correction_draft(cur, job, document) != (binding, previous)):
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        rows = cur.execute("""SELECT rewrite_attempt_id,prompt_hash,response_hash,status
            FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s ORDER BY attempt_number,lease_token""",
            (lease.job_id,)).fetchall()
        if rows != attempts:
            raise LeaseLost("correction dispatch state changed")
        return job

    def complete_json(prompt):
        number = len(attempts) + 1
        if number > binding["model_call_budget"]:
            raise ValueError("REWRITE_CORRECTION_BUDGET_INVALID")
        attempt = uuid4()
        prompt_hash = sha256(prompt.encode()).hexdigest()
        with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            fence(cur)
            cur.execute("""INSERT INTO canonical_article_rewrite_attempts
                (rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,
                 profile_version,prompt_hash,input_hash,status,dispatched_at)
                VALUES (%s,%s,%s,%s,'inception',%s,%s,%s,%s,'dispatched',clock_timestamp())""",
                (attempt, lease.job_id, lease.token, number, model, SOURCE_BOUND_CORRECTION_PROFILE,
                 prompt_hash, input_hash))
        if hooks is not None:
            hooks("after_model_dispatch")
        reply = model_client.complete_json(prompt)
        if not isinstance(reply, dict):
            raise ValueError("REWRITE_CORRECTION_RESPONSE_INVALID")
        try:
            encoded = json.dumps(reply, ensure_ascii=False, allow_nan=False).encode()
        except (TypeError, ValueError):
            raise ValueError("REWRITE_CORRECTION_RESPONSE_INVALID") from None
        # JSONB cannot store NUL. Ignore pairs that encode literal backslashes.
        if b"\\u0000" in encoded.replace(b"\\\\", b""):
            raise ValueError("REWRITE_CORRECTION_RESPONSE_INVALID")
        if len(encoded) > 1048576:
            raise ValueError("REWRITE_CORRECTION_RESPONSE_LIMIT")
        response_hash = digest_json(reply)
        # A visibility change during IO can block the next dispatch and
        # publication. Keep the response for the request already delivered.
        try:
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                _lock_transform(cur, lease)
                saved = cur.execute("""UPDATE canonical_article_rewrite_attempts
                    SET status='succeeded',response=incoming.response,response_hash=%s,completed_at=clock_timestamp()
                    FROM (SELECT %s::jsonb AS response) incoming
                    WHERE rewrite_attempt_id=%s AND source_fetch_job_id=%s AND lease_token=%s
                      AND status='dispatched' AND prompt_hash=%s
                      AND canonical_article_rewrite_attempts.response IS NULL
                      AND octet_length(incoming.response::text)<=1048576
                    RETURNING rewrite_attempt_id,prompt_hash,response_hash,status""",
                    (response_hash, Jsonb(reply), attempt, lease.job_id, lease.token, prompt_hash)).fetchone()
                if saved is None:
                    owner = cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
                        WHERE rewrite_attempt_id=%s AND source_fetch_job_id=%s AND lease_token=%s
                          AND status='dispatched' AND prompt_hash=%s AND response IS NULL""",
                        (attempt, lease.job_id, lease.token, prompt_hash)).fetchone()
                    if owner is not None:
                        raise ValueError("REWRITE_CORRECTION_RESPONSE_LIMIT")
                    raise LeaseLost("correction response owner changed")
        except DataError:
            raise ValueError("REWRITE_CORRECTION_RESPONSE_INVALID") from None
        attempts.append(saved)
        return reply

    result = correction_for_method(binding.get("correction_method", _CORRECTION_METHOD))(
        document, previous, complete_json=complete_json, model_call_budget=binding["model_call_budget"],
        preserve_notes=binding["preserve_notes"],
    )
    if result.error_code is not None or result.document is None:
        raise ValueError(result.error_code or _CORRECTION_EVIDENCE_INVALID)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job = fence(cur)
        revision, validation_hash = _stage_correction_candidate(
            cur, job, document, result, model=model, token=lease.token, attempts=attempts,
        )
        cur.execute("UPDATE source_fetch_jobs SET phase='publishing',checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",
            (Jsonb({"candidate_revision_id": str(revision), "rewrite_error_code": None,
                    "validation_hash": validation_hash}), lease.job_id))
    return revision


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
        or not transform_source_matches(article, job)
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


def resolve_first_draft_recovery(candidate, attempt, *, prompt_version):
    """Replay a recovered v1 candidate from its original, unchanged provider reply."""
    from .procedure_rewrite_recovery import FIRST_DRAFT_RECOVERY_METHODS, recover_first_draft

    source = candidate["normalized_source_document"]
    metadata = candidate["model_metadata"]
    method = metadata.get("transformation_method")
    if (method not in FIRST_DRAFT_RECOVERY_METHODS
        or candidate["rewrite_profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or prompt_version is None or attempt is None
        or attempt["profile_version"] != AUTOMATIC_REWRITE_PROFILE
        or attempt["canonical_article_revision_id"] != candidate["canonical_article_revision_id"]
        or attempt["status"] != "succeeded" or attempt["error_code"] is not None
        or attempt["provider"] != "inception" or metadata.get("provider") != attempt["provider"]
        or attempt["model"] != metadata.get("model")
        or attempt["dispatched_at"] is None or attempt["completed_at"] is None
        or attempt["dispatched_at"] > attempt["completed_at"]
        or not isinstance(attempt["response"], dict)
        or attempt["response_hash"] != digest_json(attempt["response"])
        or attempt["input_hash"] != candidate["normalized_source_hash"]
        or attempt["prompt_hash"] != metadata.get("prompt_hash")):
        raise ValueError("FIRST_DRAFT_RECOVERY_BINDING_INVALID")
    recovered = recover_first_draft(source, attempt["response"], prompt_version=prompt_version, method=method)
    if (recovered is None or recovered.error_code is not None
        or recovered.evidence != metadata.get("first_draft_recovery")
        or recovered.document != candidate["canonical_document"]
        or digest_json(recovered.document) != candidate["rewrite_result_hash"]):
        raise ValueError("FIRST_DRAFT_RECOVERY_BINDING_INVALID")
    return recovered


def automatic_candidate_validation(cur, job, candidate, *, require_current=False):
    """Rebuild automatic source, prompt and output from immutable saved evidence."""
    from .article_lifecycle_types import digest_json
    from .procedure_rewrite_auto import _auto_prompt_version, require_current_publication_checks, validate_auto
    from .procedure_normalize import normalize_procedure_article
    if candidate is None:
        raise ValueError("automatic candidate binding missing")
    profile = job["rewrite_profile_version"]
    if profile not in AUTOMATIC_REWRITE_PROFILES or candidate["rewrite_profile_version"] != profile:
        raise ValueError("automatic candidate profile binding mismatch")
    source = candidate["normalized_source_document"]
    captured = cur.execute("""SELECT s.*,o.captured_context FROM canonical_article_source_revisions s
        JOIN LATERAL (SELECT captured_context FROM canonical_article_source_observations
        WHERE source_revision_id=s.source_revision_id ORDER BY captured_at,source_observation_id LIMIT 1) o ON true
        WHERE s.source_revision_id=%s AND s.canonical_article_id=%s""",
        (job["source_revision_id"],job["canonical_article_id"])).fetchone()
    if captured is None:
        raise ValueError("automatic source binding missing")
    context = captured["captured_context"]
    normalized = normalize_procedure_article({"normalized_document":captured["source_document"],
        "blocks":captured["source_document"]["blocks"],"images":captured["source_images"],
        "body":captured["source_body"],"steps":captured["source_steps"],
        "evidence_ids":context["evidence_ids"],"title":context["descriptor"].get("title"),
        "article_id":str(job["canonical_article_id"])}, resource_manifest=captured["resource_manifest"])["normalized_document"]
    if profile == SOURCE_BOUND_CORRECTION_PROFILE:
        if normalized != source:
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        correction = resolve_source_bound_correction(cur, job, candidate)
        validation = validate_auto(
            source, correction.document, response=correction.response,
            prompt_version=correction.evidence["guard_version"], profile_version=profile,
        )
        if not validation.passed:
            raise ValueError(_CORRECTION_EVIDENCE_INVALID)
        return validation
    from .procedure_rewrite_auto import SOURCE_PRESERVING_METHOD, validate_source_preserving_candidate
    if candidate["model_metadata"].get("transformation_method") == SOURCE_PRESERVING_METHOD:
        if (normalized != source or candidate["normalized_source_hash"] != digest_json(source)
            or job["checkpoint"].get("normalized_document") != source
            or job["checkpoint"].get("normalized_hash") != digest_json(source)
            or candidate["source_revision_id"] != job["source_revision_id"]
            or candidate["canonical_article_id"] != job["canonical_article_id"]
            or candidate["transformation_key"] != job["transformation_key"]
            or candidate["normalization_version"] != job["normalization_version"]
            or cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts x
                JOIN source_fetch_jobs t ON t.source_fetch_job_id=x.source_fetch_job_id
                WHERE x.source_fetch_job_id=%s OR x.canonical_article_revision_id=%s
                   OR t.transformation_key=%s LIMIT 1""",
                (job["source_fetch_job_id"],candidate["canonical_article_revision_id"],job["transformation_key"])).fetchone()):
            raise ValueError("source preserving saved evidence binding mismatch")
        return validate_source_preserving_candidate(
            source, candidate["canonical_document"], candidate["model_metadata"], profile_version=profile,
        )
    attempt = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
        WHERE canonical_article_revision_id=%s AND status='succeeded'""",
        (candidate["canonical_article_revision_id"],)).fetchone()
    if (normalized != source or candidate["normalized_source_hash"] != digest_json(source)
        or job["checkpoint"].get("normalized_document") != source
        or job["checkpoint"].get("normalized_hash") != digest_json(source)
        or candidate["source_revision_id"] != job["source_revision_id"]
        or candidate["canonical_article_id"] != job["canonical_article_id"]
        or candidate["transformation_key"] != job["transformation_key"]
        or candidate["normalization_version"] != job["normalization_version"]
        or attempt is None or attempt["source_fetch_job_id"] != job["source_fetch_job_id"]
        or attempt["profile_version"] != profile or not isinstance(attempt["response"],dict)
        or attempt["response_hash"] != digest_json(attempt["response"])
        or attempt["input_hash"] != digest_json(source)
        or attempt["prompt_hash"] != candidate["model_metadata"].get("prompt_hash")
        or attempt["model"] != candidate["model_metadata"].get("model")
        or candidate["model_metadata"].get("profile_version") != profile):
        raise ValueError("automatic saved evidence binding mismatch")
    prompt_version = _auto_prompt_version(
        source, context=context["vehicle"], prompt_hash=attempt["prompt_hash"], profile_version=profile,
    )
    if prompt_version is None:
        raise ValueError("automatic saved prompt binding mismatch")
    from .procedure_rewrite_recovery import FIRST_DRAFT_RECOVERY_METHODS

    response = attempt["response"]
    if candidate["model_metadata"].get("transformation_method") in FIRST_DRAFT_RECOVERY_METHODS:
        response = resolve_first_draft_recovery(candidate, attempt, prompt_version=prompt_version).response
    validation = validate_auto(
        source, candidate["canonical_document"], response=response, prompt_version=prompt_version,
        profile_version=profile,
    )
    if not validation.passed:
        raise ValueError("automatic rewrite operation binding mismatch")
    if require_current:
        require_current_publication_checks(
            source, candidate["canonical_document"], saved_prompt_version=prompt_version,
        )
    return validation


def validate_saved_candidate(repo,lease,candidate):
    profile = lease.rewrite_profile_version
    if profile not in AUTOMATIC_REWRITE_PROFILES and profile != "full-prose-review-v1":
        from .procedure_rewrite import validate_article_rewrite
        return validate_article_rewrite(candidate["normalized_source_document"],candidate["canonical_document"],profile_version=profile)
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_ = _lock_transform(cur,lease)
        return automatic_candidate_validation(cur,job,candidate) if profile in AUTOMATIC_REWRITE_PROFILES else full_candidate_validation(cur,job,candidate)


class RewriteStorageError(ValueError):
    """A fixed storage stage, never a projection or renderer exception message."""

    def __init__(self, stage):
        self.code = {
            "storage_projection": "REWRITE_STORAGE_PROJECTION_INVALID",
            "storage_binding": "REWRITE_STORAGE_BINDING_INVALID",
            "storage_limit": "REWRITE_RESPONSE_LIMIT",
        }[stage]
        self.diagnostics = {"stage": stage}
        super().__init__(self.code)


def store_source_preserving_candidate(repo,lease):
    """Persist an independently reconstructed server candidate; never manufacture an attempt."""
    from .article_lifecycle_types import digest_json
    from .article_document import project_ordered_document
    from .procedure_rewrite_auto import build_source_preserving_candidate
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,article=_lock_transform(cur,lease)
        _require_source_bound_rewrite_rights(cur, job, article)
        profile = job["rewrite_profile_version"]
        if (profile not in AUTOMATIC_REWRITE_PROFILES or profile == SOURCE_BOUND_CORRECTION_PROFILE
            or job["checkpoint"].get("rewrite_error_code")):
            raise ValueError("SOURCE_PRESERVING_BINDING_INVALID")
        source=job["checkpoint"]["normalized_document"]
        document,metadata=build_source_preserving_candidate(source, profile_version=profile)
        projection=project_ordered_document(document)
        revision=uuid4()
        candidate=cur.execute("""INSERT INTO canonical_article_revisions
            (canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,
             normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,
             canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,
             rewrite_result_hash,model_metadata)
            VALUES (%s,%s,%s,%s,%s,%s,'building',%s,%s,%s,%s,%s,%s,'{}',%s,%s,%s) RETURNING *""",
            (revision,job["canonical_article_id"],job["source_revision_id"],job["transformation_key"],
             job["normalization_version"],job["rewrite_profile_version"],Jsonb(source),digest_json(source),
             Jsonb(document),projection["body"],Jsonb(projection["steps"]),Jsonb(projection["images"]),digest_json({}),
             digest_json(document),Jsonb(metadata))).fetchone()
        # Locks, durable source normalization and zero-attempt checks precede commit.
        validation=automatic_candidate_validation(cur,job,candidate)
        if not validation.passed:raise ValueError("SOURCE_PRESERVING_BINDING_INVALID")
        cur.execute("UPDATE source_fetch_jobs SET phase='validating',checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",
            (Jsonb({"candidate_revision_id":str(revision),"rewrite_error_code":None}),lease.job_id))


def store_rewrite_result(repo,lease,result):
    try:
        return _store_rewrite_result(repo,lease,result)
    except RewriteStorageError:
        raise
    except ValueError:
        pass
    raise RewriteStorageError("storage_binding") from None


def _store_rewrite_result(repo,lease,result):
    from .article_lifecycle_types import digest_json
    from .article_document import project_ordered_document
    from .procedure_rewrite_recovery import (
        FIRST_DRAFT_RECOVERABLE_ERRORS, FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
        REQUIRED_ACTION_WEAKENED, recover_first_draft,
    )
    from hashlib import sha256
    import json
    projection = None
    try:
        projection=project_ordered_document(result.document)
    except ValueError:
        pass
    if projection is None:
        raise RewriteStorageError("storage_projection")
    # PostgreSQL jsonb includes separator whitespace. Enforce that storage bound
    # before attempting a transaction as well as the external wire bound.
    raw=json.dumps(result.raw_response,ensure_ascii=False)
    if len(raw.encode())>1048576: raise RewriteStorageError("storage_limit")
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job,_=_lock_transform(cur,lease)
        if job["rewrite_profile_version"] == SOURCE_BOUND_CORRECTION_PROFILE:
            raise ValueError("SOURCE_BOUND_CORRECTION_DISPATCH_REQUIRED")
        attempt=cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s AND lease_token=%s AND status='dispatched' FOR UPDATE",(lease.job_id,lease.token)).fetchone()
        if attempt is None: raise ValueError("no dispatched rewrite attempt")
        if (attempt["input_hash"]!=result.input_hash or attempt["prompt_hash"]!=result.prompt_hash
            or result.profile_version!=job["rewrite_profile_version"]
            or attempt["profile_version"]!=job["rewrite_profile_version"]
            or result.model_metadata.get("model")!=attempt["model"]
            or result.model_metadata.get("profile_version")!=attempt["profile_version"]
            or result.model_metadata.get("prompt_hash")!=attempt["prompt_hash"]
            or result.output_hash!=digest_json(result.document)):
            raise ValueError("rewrite input/output binding mismatch")
        recovered = None
        prompt_version = None
        if result.profile_version == AUTOMATIC_REWRITE_PROFILE and result.error_code in FIRST_DRAFT_RECOVERABLE_ERRORS:
            from .procedure_rewrite_auto import _auto_prompt_version

            source = job["checkpoint"]["normalized_document"]
            if (result.document != source or result.input_hash != digest_json(source)
                or job["checkpoint"].get("normalized_hash") != result.input_hash
                or attempt["dispatched_at"] is None or attempt["response"] is not None
                or attempt["provider"] != "inception" or result.model_metadata.get("provider") != attempt["provider"]):
                raise ValueError("FIRST_DRAFT_RECOVERY_BINDING_INVALID")
            captured = cur.execute("""SELECT captured_context->'vehicle' AS vehicle
                FROM canonical_article_source_observations WHERE source_revision_id=%s AND canonical_article_id=%s
                ORDER BY captured_at,source_observation_id LIMIT 1""",
                (job["source_revision_id"],job["canonical_article_id"])).fetchone()
            if captured is not None and isinstance(captured["vehicle"], dict):
                prompt_version = _auto_prompt_version(
                    source, context=captured["vehicle"], prompt_hash=attempt["prompt_hash"],
                    profile_version=AUTOMATIC_REWRITE_PROFILE,
                )
            if prompt_version is not None:
                method = (FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD
                          if result.error_code == REQUIRED_ACTION_WEAKENED else None)
                recovered = recover_first_draft(source, result.raw_response, prompt_version=prompt_version, method=method)
            if recovered is not None and (recovered.document is None or recovered.error_code is not None
                    or recovered.evidence.get("original_error_code") != result.error_code):
                raise ValueError("FIRST_DRAFT_RECOVERY_BINDING_INVALID")
        if result.profile_version == "full-prose-review-v1" and not result.error_code:
            from .procedure_rewrite_full import render_full, validate_full
            source = job["checkpoint"]["normalized_document"]
            full_validation = validate_full(source,result.document,response=result.raw_response)
            if digest_json(render_full(source,result.raw_response)) != digest_json(result.document) or not full_validation.passed:
                raise ValueError("rewrite operation binding mismatch")
        if result.profile_version in AUTOMATIC_REWRITE_PROFILES and (recovered is not None or not result.error_code):
            from .procedure_rewrite_auto import _NOTE_LABEL_PROMPT_VERSION, render_auto, validate_auto
            source = job["checkpoint"]["normalized_document"]
            response = recovered.response if recovered is not None else result.raw_response
            document = recovered.document if recovered is not None else result.document
            output_hash = digest_json(document) if recovered is not None else result.output_hash
            guard_version = prompt_version if recovered is not None else None
            if result.model_metadata.get("prompt_version") == _NOTE_LABEL_PROMPT_VERSION:
                guard_version = _NOTE_LABEL_PROMPT_VERSION
            rendered = render_auto(source, response, prompt_version=guard_version, profile_version=result.profile_version)
            validation = validate_auto(
                source, document, response=response, prompt_version=guard_version, profile_version=result.profile_version,
            )
            if digest_json(rendered) != output_hash or not validation.passed:
                raise ValueError("automatic rewrite operation binding mismatch")
            if recovered is not None:
                result = replace(
                    result, document=document, output_hash=output_hash, error_code=None,
                    changed_slots=tuple(validation.report["changed_slots"]),
                    model_metadata={**result.model_metadata, "transformation_method": recovered.evidence["method"],
                                    "first_draft_recovery": recovered.evidence},
                )
                projection = project_ordered_document(document)
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
        profile = job["rewrite_profile_version"]
        if profile in AUTOMATIC_REWRITE_PROFILES:
            expected = automatic_candidate_validation(cur, job, candidate)
        elif profile == "full-prose-review-v1":
            expected = full_candidate_validation(cur, job, candidate)
        else:
            expected = validate_article_rewrite(
                candidate["normalized_source_document"], candidate["canonical_document"], profile_version=profile,
            )
        if (expected != validation or (profile in (*AUTOMATIC_REWRITE_PROFILES, "technical-prose-v2", "full-prose-review-v1")
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


def publish_article_revision(repo, lease, revision_id, *, hooks=None):
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        return _publish_article_revision(cur, lease, revision_id, hooks=hooks)


def _publish_article_revision(cur, lease, revision_id, *, hooks=None):
    from .article_lifecycle_types import digest_json
    from .article_document import project_ordered_document
    from .procedure_rewrite import validate_article_rewrite
    from .retained_note_label_repair import METHOD as NOTE_LABEL_REPAIR_METHOD, resolve_retained_note_label_repair
    from .retained_procedure_repair import METHOD as RETAINED_PROCEDURE_REPAIR_METHOD, resolve_retained_procedure_repair
    from .retained_required_action_repair import METHOD as REQUIRED_ACTION_METHOD, resolve_retained_required_action_repair
    from .staged_media_reply_recovery import METHOD, verify_staged_media_reply_recovery
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
    _require_source_bound_rewrite_rights(cur, job, article)
    row=cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s FOR UPDATE",(revision_id,)).fetchone()
    if row is None: raise ValueError("missing candidate")
    projection=project_ordered_document(row["canonical_document"])
    profile = job["rewrite_profile_version"]
    method = row["model_metadata"].get("transformation_method")
    archived_reply_recovery = method in (
        METHOD, RETAINED_PROCEDURE_REPAIR_METHOD, NOTE_LABEL_REPAIR_METHOD, REQUIRED_ACTION_METHOD,
    )
    if method == METHOD:
        validation = verify_staged_media_reply_recovery(cur, job, article, row)
    elif method == RETAINED_PROCEDURE_REPAIR_METHOD:
        validation = resolve_retained_procedure_repair(cur, job, article, row, publishing=True).validation
    elif method == NOTE_LABEL_REPAIR_METHOD:
        validation = resolve_retained_note_label_repair(cur, job, article, row, publishing=True).validation
    elif method == REQUIRED_ACTION_METHOD:
        validation = resolve_retained_required_action_repair(cur, job, article, row, publishing=True).validation
    elif profile in AUTOMATIC_REWRITE_PROFILES:
        validation = automatic_candidate_validation(cur, job, row, require_current=True)
    elif profile == "full-prose-review-v1":
        validation = full_candidate_validation(cur, job, row)
    else:
        validation = validate_article_rewrite(
            row["normalized_source_document"], row["canonical_document"], profile_version=profile,
        )
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
    from .procedure_rewrite_auto import (
        SOURCE_PRESERVING_METHOD, require_distinct_generated_introduction,
        require_preserved_display_quotations, require_required_procedure_actions,
    )
    server_candidate=(profile in AUTOMATIC_REWRITE_PROFILES
        and row["model_metadata"].get("transformation_method") == SOURCE_PRESERVING_METHOD)
    # The v3 validator independently reconstructed the full correction
    # from every raw round, including verifying the terminal attempt link.
    if not server_candidate and not archived_reply_recovery and profile != SOURCE_BOUND_CORRECTION_PROFILE:
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
    if profile in AUTOMATIC_REWRITE_PROFILES or method in (NOTE_LABEL_REPAIR_METHOD, REQUIRED_ACTION_METHOD):
        source, document = row["normalized_source_document"], row["canonical_document"]
        rewritten_paths = validation.report["changed_prose_slots"]
        require_distinct_generated_introduction(source, document, rewritten_paths=rewritten_paths)
        require_preserved_display_quotations(source, document, rewritten_paths=rewritten_paths)
        require_required_procedure_actions(source, document, rewritten_paths=rewritten_paths)
    cur.execute("UPDATE canonical_article_revisions SET status='published',published_at=clock_timestamp() WHERE canonical_article_revision_id=%s",(revision_id,))
    if hooks is not None:hooks("inside_publication")
    cur.execute("""UPDATE canonical_articles SET current_source_revision_id=%s,
        current_canonical_revision_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s""",
        (job["source_revision_id"], revision_id, lease.canonical_article_id))
    cur.execute("UPDATE source_fetch_jobs SET status='completed',phase='completed',retryable=false,error_code=NULL,next_attempt_at=NULL,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",(lease.job_id,))
    cur.execute("""INSERT INTO publication_events(publication_event_id,event_type,event_version,canonical_article_id,canonical_article_revision_id,correlation_id,idempotency_key,payload,producer)
        VALUES (%s,'catalog.article.published',1,%s,%s,%s,%s,%s,'ingestion-worker') ON CONFLICT(idempotency_key) DO NOTHING""",
        (uuid4(),lease.canonical_article_id,revision_id,job["correlation_id"],"catalog.article.published:"+job["transformation_key"],Jsonb({"source_revision_id":str(job["source_revision_id"]),"review_status":"APPROVED" if job["rewrite_profile_version"] == "full-prose-review-v1" else "UNREVIEWED"})))
    return revision_id


def record_rewrite_failure(repo,lease,*,code,ambiguous=False,failure=None):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        _lock_transform(cur,lease)
        cur.execute("""UPDATE canonical_article_rewrite_attempts SET status=%s,error_code=%s,completed_at=clock_timestamp()
            WHERE source_fetch_job_id=%s AND lease_token=%s AND status IN ('prepared','dispatched') RETURNING rewrite_attempt_id""",
            ("ambiguous" if ambiguous else "failed",code,lease.job_id,lease.token))
        attempt=cur.fetchone()
        if failure is not None and attempt is not None:
            from .mercury2 import MercuryResponseError, _safe_response_diagnostics
            if isinstance(failure,MercuryResponseError):
                diagnostics=_safe_response_diagnostics(failure.diagnostics)
            elif isinstance(failure,RewriteStorageError):
                diagnostics={"stage":failure.diagnostics["stage"]}
            else:
                raise TypeError("typed rewrite failure required")
            cur.execute("UPDATE source_fetch_jobs SET checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",
                (Jsonb({"rewrite_failure":{"code":failure.code,"diagnostics":diagnostics,
                    "attempt_id":str(attempt["rewrite_attempt_id"])}}),lease.job_id))
