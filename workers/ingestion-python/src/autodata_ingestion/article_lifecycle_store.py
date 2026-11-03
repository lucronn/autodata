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


def store_captured_source(repo, lease, captured):
    """Source revision, observation, pointer and transformation transition are atomic."""
    context = captured.context
    if (
        article_id(context.key) != lease.canonical_article_id
        or not captured.source_body.strip()
        or not captured.source_document.get("blocks")
    ):
        raise ValueError("captured article identity/body mismatch")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job = lock_live_lease(cur, lease)
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (lease.canonical_article_id,),
        ).fetchone()
        if (
            article["request_generation"] != job["request_generation"]
            or article["current_job_id"] != lease.job_id
        ):
            raise LeaseLost("article generation changed")
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
            """INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(canonical_article_id,source_fingerprint) DO NOTHING RETURNING source_revision_id""",
            (
                revision_id,
                lease.canonical_article_id,
                captured.source_fingerprint,
                body_snapshot,
                Jsonb(captured.resource_manifest),
                Jsonb(captured.source_document),
                Jsonb(captured.source_images),
                captured.source_body,
                Jsonb(captured.source_steps),
                captured.projection_status,
                Jsonb(captured.evidence_manifest),
                captured.captured_at,
            ),
        ).fetchone()
        if row is None:
            row = cur.execute(
                "SELECT source_revision_id FROM canonical_article_source_revisions WHERE canonical_article_id=%s AND source_fingerprint=%s",
                (lease.canonical_article_id, captured.source_fingerprint),
            ).fetchone()
        revision_id = row["source_revision_id"]
        provenance = deepcopy(captured.resource_provenance)
        for resource in provenance:
            if str(resource.get("source_snapshot_id")) in snapshots:
                resource["source_snapshot_id"] = str(
                    snapshots[str(resource["source_snapshot_id"])]
                )
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
        key = transformation_key(
            lease.canonical_article_id,
            captured.source_fingerprint,
            job["normalization_version"],
            job["rewrite_profile_version"],
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
        )
