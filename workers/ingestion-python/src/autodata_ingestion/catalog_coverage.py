"""Independent durable bank enumeration. Index browsing never reads article bodies."""

from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import ArticleKey, scope_key
from .article_lifecycle_store import _upsert_descriptor, persist_resource
from .source_job_persistence import _result, lock_live_lease, fail_source_job, LeaseLost
from .source_connector_client import SourceConnectorError
from .source_article_capture import upload_envelope

PROVIDERS = ("bankone", "banktwo")


def ensure_article_catalog_jobs(repo, *, vehicle_id, vehicle_configuration_id):
    results = []
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Serializes first scope creation as well as repeat ensures.
        if (
            cur.execute(
                "SELECT vehicle_id FROM vehicles WHERE vehicle_id=%s FOR UPDATE",
                (vehicle_id,),
            ).fetchone()
            is None
        ):
            raise KeyError("vehicle not found")
        for provider in PROVIDERS:
            scope = cur.execute(
                """INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,vehicle_configuration_id,scope_key,provider_slug)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(scope_key,provider_slug) DO NOTHING RETURNING *""",
                (
                    uuid4(),
                    vehicle_id,
                    vehicle_configuration_id,
                    scope_key(vehicle_id, vehicle_configuration_id),
                    provider,
                ),
            ).fetchone()
            if scope is None:
                scope = cur.execute(
                    "SELECT * FROM catalog_article_provider_scopes WHERE scope_key=%s AND provider_slug=%s FOR UPDATE",
                    (scope_key(vehicle_id, vehicle_configuration_id), provider),
                ).fetchone()
            if scope["current_job_id"]:
                job = cur.execute(
                    "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                    (scope["current_job_id"],),
                ).fetchone()
                results.append(_result(cur, None, job))
                continue
            job = _create_catalog_job(cur, scope)
            results.append(_result(cur, None, job, True))
    return tuple(results)


def _create_catalog_job(cur, scope, checkpoint=None):
    job = cur.execute(
        """INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_version,connector_name,idempotency_key,status,job_kind,catalog_provider_scope_id,request_generation,checkpoint)
    VALUES (%s,%s,%s,%s,'lifecycle-v1',%s,%s,'pending','catalog_index',%s,%s,%s) RETURNING *""",
        (
            uuid4(),
            scope["provider_slug"],
            scope["vehicle_id"],
            scope["source_vehicle_ref"] or "",
            scope["provider_slug"],
            f'catalog:{scope["catalog_provider_scope_id"]}:{scope["generation"]}',
            scope["catalog_provider_scope_id"],
            scope["generation"],
            Jsonb(checkpoint or {}),
        ),
    ).fetchone()
    cur.execute(
        "UPDATE catalog_article_provider_scopes SET current_job_id=%s,status='pending',error_code=NULL,next_cursor=NULL,row_count=0,updated_at=clock_timestamp() WHERE catalog_provider_scope_id=%s",
        (job["source_fetch_job_id"], scope["catalog_provider_scope_id"]),
    )
    return job


def refresh_catalog_jobs(repo, *, vehicle_id, vehicle_configuration_id, actor, reason):
    if not actor.strip() or not reason.strip():
        raise ValueError("actor/reason required")
    ensure_article_catalog_jobs(
        repo, vehicle_id=vehicle_id, vehicle_configuration_id=vehicle_configuration_id
    )
    results = []
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        scopes = cur.execute(
            "SELECT * FROM catalog_article_provider_scopes WHERE scope_key=%s ORDER BY provider_slug FOR UPDATE",
            (scope_key(vehicle_id, vehicle_configuration_id),),
        ).fetchall()
        for scope in scopes:
            job = cur.execute(
                "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                (scope["current_job_id"],),
            ).fetchone()
            if job["status"] in ("pending", "processing", "failed"):
                results.append(_result(cur, None, job))
                continue
            scope = cur.execute(
                "UPDATE catalog_article_provider_scopes SET generation=generation+1 WHERE catalog_provider_scope_id=%s RETURNING *",
                (scope["catalog_provider_scope_id"],),
            ).fetchone()
            results.append(
                _result(
                    cur,
                    None,
                    _create_catalog_job(
                        cur, scope, {"refresh_actor": actor, "refresh_reason": reason}
                    ),
                    True,
                )
            )
    return tuple(results)


def _lock_scope(cur, lease):
    lock_live_lease(cur, lease)
    scope = cur.execute(
        "SELECT * FROM catalog_article_provider_scopes WHERE catalog_provider_scope_id=%s FOR UPDATE",
        (lease.catalog_provider_scope_id,),
    ).fetchone()
    if (
        scope is None
        or scope["generation"] != lease.generation
        or scope["current_job_id"] != lease.job_id
    ):
        raise LeaseLost("catalog generation changed")
    return scope


def _complete(cur, lease, scope, code=None):
    cur.execute(
        "UPDATE catalog_article_provider_scopes SET status='complete',completed_generation=generation,next_cursor=NULL,error_code=%s,updated_at=clock_timestamp() WHERE catalog_provider_scope_id=%s",
        (code, lease.catalog_provider_scope_id),
    )
    cur.execute(
        "UPDATE canonical_articles SET membership_status='retired',updated_at=clock_timestamp() WHERE scope_key=%s AND provider_slug=%s AND last_seen_catalog_generation<%s",
        (scope["scope_key"], scope["provider_slug"], scope["generation"]),
    )
    cur.execute(
        "UPDATE source_fetch_jobs SET status='completed',phase='completed',lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,retryable=false,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
        (lease.job_id,),
    )


def run_catalog_index_job(repo, lease, *, registry, object_store):
    if lease is None or lease.kind != "catalog_index":
        raise ValueError("catalog lease required")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        scope = _lock_scope(cur, lease)
        vehicle = cur.execute(
            "SELECT make,model,model_year,region FROM vehicles WHERE vehicle_id=%s",
            (scope["vehicle_id"],),
        ).fetchone()
        selector = {
            "year": vehicle["model_year"],
            "make": vehicle["make"],
            "model": vehicle["model"],
            "region": vehicle["region"],
        }
        configuration_unresolved = False
        if scope["vehicle_configuration_id"]:
            configuration = cur.execute(
                """SELECT c.trim,c.engine_displacement_l,b.drivetrain FROM vehicle_configurations c
                JOIN vehicle_identity_bases b USING(vehicle_identity_base_id)
                WHERE c.vehicle_configuration_id=%s""",
                (scope["vehicle_configuration_id"],),
            ).fetchone()
            label = " ".join(
                str(value).strip()
                for value in (
                    configuration["trim"],
                    (
                        f'{configuration["engine_displacement_l"]:.1f}L'
                        if configuration["engine_displacement_l"] is not None
                        else None
                    ),
                    configuration["drivetrain"],
                )
                if value not in (None, "")
            )
            if label:
                selector["configuration"] = label
            else:
                configuration_unresolved = True
        cur.execute(
            "UPDATE catalog_article_provider_scopes SET status='running',error_code=NULL,updated_at=clock_timestamp() WHERE catalog_provider_scope_id=%s",
            (lease.catalog_provider_scope_id,),
        )
        job = cur.execute(
            "SELECT checkpoint FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        ).fetchone()
        checkpoint = job["checkpoint"]
    provider = scope["provider_slug"]
    if provider not in registry:
        with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            _lock_scope(cur, lease)
            cur.execute(
                "UPDATE catalog_article_provider_scopes SET status='not_configured',error_code='NOT_CONFIGURED' WHERE catalog_provider_scope_id=%s",
                (lease.catalog_provider_scope_id,),
            )
        fail_source_job(repo, lease, code="NOT_CONFIGURED", retryable=False)
        return
    client = registry[provider]
    if client.provider != provider:
        raise ValueError("registry provider mismatch")
    try:
        ref = scope["source_vehicle_ref"]
        ambiguous = False
        if not ref:
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                mappings = cur.execute(
                    "SELECT provider_id,source_snapshot_id FROM vehicle_provider_mappings WHERE vehicle_id=%s AND vehicle_configuration_id IS NOT DISTINCT FROM %s AND provider=%s AND entity_type='car' AND mapping_status='verified'",
                    (scope["vehicle_id"], scope["vehicle_configuration_id"], provider),
                ).fetchall()
            unique = {r["provider_id"] for r in mappings}
            if len(unique) > 1:
                raise SourceConnectorError("AMBIGUOUS")
            if len(unique) == 1:
                ref = next(iter(unique))
                resolution_snapshot = mappings[0]["source_snapshot_id"]
                resolution_resource = None
            else:
                if configuration_unresolved:
                    raise SourceConnectorError("UNRESOLVED_CONFIGURATION")
                resolution = client.resolve_vehicle(selector)
                resolution_resource = upload_envelope(
                    resolution, "vehicle_resolution", object_store
                )
                candidates = resolution.body["candidates"]
                ambiguous = len(candidates) > 1
                ref = candidates[0]["opaque_ref"] if len(candidates) == 1 else None
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                scope = _lock_scope(cur, lease)
                if resolution_resource:
                    resolution_snapshot = persist_resource(cur, resolution_resource)
                cur.execute(
                    "UPDATE catalog_article_provider_scopes SET source_vehicle_ref=%s,resolution_source_snapshot_id=%s WHERE catalog_provider_scope_id=%s",
                    (ref, resolution_snapshot, lease.catalog_provider_scope_id),
                )
                cur.execute(
                    "UPDATE source_fetch_jobs SET source_vehicle_ref=%s WHERE source_fetch_job_id=%s",
                    (ref or "", lease.job_id),
                )
                if ref is None and not ambiguous:
                    _complete(cur, lease, scope, "NO_MATCHING_SOURCE_VEHICLE")
                    return
            if ambiguous:
                raise SourceConnectorError("AMBIGUOUS")
        cursor = checkpoint.get("next_cursor")
        page_number = checkpoint.get("next_page_number", 0)
        seen_cursors = set(checkpoint.get("seen_cursors", []))
        for number in range(page_number, 1000):
            envelope = client.list_articles(ref, cursor)
            resource = upload_envelope(envelope, "article_index", object_store)
            repeated = not envelope.complete and (
                envelope.next_cursor == cursor or envelope.next_cursor in seen_cursors
            )
            conflict = False
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                scope = _lock_scope(cur, lease)
                snapshot = persist_resource(cur, resource)
                for index, raw in enumerate(envelope.body["articles"]):
                    key = ArticleKey(
                        provider,
                        scope["vehicle_id"],
                        scope["vehicle_configuration_id"],
                        ref,
                        raw["opaque_ref"],
                    )
                    previous = cur.execute(
                        "SELECT descriptor,last_seen_catalog_generation FROM canonical_articles WHERE provider_slug=%s AND scope_key=%s AND source_vehicle_ref=%s AND source_article_ref=%s",
                        (provider, scope["scope_key"], ref, raw["opaque_ref"]),
                    ).fetchone()
                    if (
                        previous
                        and previous["last_seen_catalog_generation"] == lease.generation
                    ):
                        old = {
                            k: v
                            for k, v in previous["descriptor"].items()
                            if k != "source_sort_order"
                        }
                        if old != raw:
                            conflict = True
                        continue
                    descriptor = {**raw, "source_sort_order": number * 1000 + index}
                    _upsert_descriptor(
                        conn, key, descriptor, snapshot, lease.generation
                    )
                cur.execute(
                    """INSERT INTO catalog_article_index_pages(catalog_provider_scope_id,generation,page_number,source_snapshot_id,request_id,provider_revision,cursor_in,cursor_out,complete)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        lease.catalog_provider_scope_id,
                        lease.generation,
                        number,
                        snapshot,
                        envelope.request_id,
                        envelope.source_revision,
                        cursor,
                        envelope.next_cursor,
                        envelope.complete,
                    ),
                )
                count = cur.execute(
                    "SELECT count(*) AS n FROM canonical_articles WHERE provider_slug=%s AND scope_key=%s AND last_seen_catalog_generation=%s",
                    (provider, scope["scope_key"], lease.generation),
                ).fetchone()["n"]
                cur.execute(
                    "UPDATE catalog_article_provider_scopes SET row_count=%s,next_cursor=%s,updated_at=clock_timestamp() WHERE catalog_provider_scope_id=%s",
                    (count, envelope.next_cursor, lease.catalog_provider_scope_id),
                )
                seen_cursors.add(cursor or "")
                cur.execute(
                    "UPDATE source_fetch_jobs SET checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
                    (
                        Jsonb(
                            {
                                "next_page_number": number + 1,
                                "next_cursor": envelope.next_cursor,
                                "seen_cursors": sorted(seen_cursors),
                            }
                        ),
                        lease.job_id,
                    ),
                )
                if envelope.complete and not conflict:
                    _complete(cur, lease, scope)
                    return
            if conflict:
                raise SourceConnectorError("CONFLICTING_DESCRIPTOR")
            if repeated:
                raise SourceConnectorError("REPEATED_CURSOR")
            cursor = envelope.next_cursor
        raise SourceConnectorError("PAGE_LIMIT")
    except SourceConnectorError as error:
        with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            scope = _lock_scope(cur, lease)
            status = (
                "needs_review"
                if error.code
                in ("AMBIGUOUS", "CONFLICTING_DESCRIPTOR", "UNRESOLVED_CONFIGURATION")
                else ("partial" if scope["row_count"] else "failed")
            )
            cur.execute(
                "UPDATE catalog_article_provider_scopes SET status=%s,error_code=%s,updated_at=clock_timestamp() WHERE catalog_provider_scope_id=%s",
                (status, error.code, lease.catalog_provider_scope_id),
            )
        fail_source_job(
            repo,
            lease,
            code=error.code,
            retryable=error.retryable,
            retry_after_seconds=error.retry_after_seconds,
        )


def read_catalog_coverage(repo, *, vehicle_id, vehicle_configuration_id):
    scope = scope_key(vehicle_id, vehicle_configuration_id)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT * FROM catalog_article_provider_scopes WHERE scope_key=%s", (scope,)
        ).fetchall()
        coverage = {r["provider_slug"]: r for r in rows}
        items = cur.execute(
            "SELECT * FROM canonical_articles WHERE scope_key=%s AND membership_status='active' AND takedown_status='active' ORDER BY provider_slug,source_sort_order,canonical_article_id",
            (scope,),
        ).fetchall()
        complete = all(
            p in coverage
            and coverage[p]["status"] == "complete"
            and coverage[p]["completed_generation"] == coverage[p]["generation"]
            for p in PROVIDERS
        )
        return {"items": items, "coverage": coverage, "complete": complete}
