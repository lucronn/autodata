"""Independent durable bank enumeration. Index browsing never reads article bodies."""

from uuid import UUID, uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import ArticleKey, scope_key
from .article_lifecycle_store import _upsert_descriptor, persist_resource
from .source_job_persistence import _result, lock_live_lease, fail_source_job, LeaseLost
from .source_connector_client import SourceCatalogAbsence, SourceConnectorError
from .source_article_capture import upload_envelope
from .vehicle_identity import _extract_engine_displacement, engine_variants_from_label

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


def refresh_catalog_jobs(repo, *, vehicle_id, vehicle_configuration_id, actor, reason, provider=None):
    """Refresh both suppliers by default, or one existing supplier scope."""
    if not actor.strip() or not reason.strip():
        raise ValueError("actor/reason required")
    if provider is not None and provider not in PROVIDERS:
        raise ValueError("unknown catalog provider")
    if provider is None:
        ensure_article_catalog_jobs(
            repo, vehicle_id=vehicle_id, vehicle_configuration_id=vehicle_configuration_id
        )
    results = []
    providers = [provider] if provider is not None else list(PROVIDERS)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        scopes = cur.execute(
            """SELECT * FROM catalog_article_provider_scopes
               WHERE scope_key=%s AND provider_slug=ANY(%s) ORDER BY provider_slug FOR UPDATE""",
            (scope_key(vehicle_id, vehicle_configuration_id), providers),
        ).fetchall()
        if provider is not None and not scopes:
            raise KeyError("catalog provider scope not found")
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


def retry_failed_catalog_provider(
    repo, *, vehicle_id, vehicle_configuration_id, provider, expected_job_id, actor, reason,
):
    """Queue the next catalog generation for one failed provider on a paid vehicle."""
    if provider not in PROVIDERS or not all(
        isinstance(value, str) and value.strip() and len(value) <= limit
        and all(32 <= ord(character) != 127 for character in value)
        for value, limit in ((actor, 256), (reason, 2048))
    ):
        raise ValueError("CATALOG_PROVIDER_RETRY_INVALID")
    try:
        vehicle_id, vehicle_configuration_id, expected_job_id = (
            UUID(str(value)) for value in (vehicle_id, vehicle_configuration_id, expected_job_id)
        )
    except ValueError:
        raise ValueError("CATALOG_PROVIDER_RETRY_INVALID") from None
    audit = {"prior_job_id": str(expected_job_id), "actor": actor, "reason": reason}
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        scope = cur.execute(
            """SELECT * FROM catalog_article_provider_scopes
               WHERE vehicle_id=%s AND vehicle_configuration_id=%s AND provider_slug=%s
                 AND scope_key=%s FOR UPDATE""",
            (vehicle_id, vehicle_configuration_id, provider, scope_key(vehicle_id, vehicle_configuration_id)),
        ).fetchone()
        if scope is None:
            raise ValueError("CATALOG_PROVIDER_RETRY_STALE")
        paid = cur.execute(
            """SELECT 1 FROM workshop_orders o
               JOIN vehicle_configurations c ON c.vehicle_configuration_id=o.configuration_id
               JOIN vehicle_identity_bases b USING(vehicle_identity_base_id)
               JOIN customer_accounts a ON a.customer_account_id=o.customer_account_id
                   AND a.personal_organization_id=o.organization_id
               JOIN entitlements e ON e.entitlement_id=o.entitlement_id AND e.commerce_order_id=o.order_id
                   AND e.customer_account_id=o.customer_account_id AND e.organization_id=o.organization_id
                   AND e.configuration_id=o.configuration_id AND e.region=o.region
                   AND e.dataset_request_id=o.dataset_request_id
               JOIN payment_events p ON p.payment_event_id=e.payment_event_id
               WHERE o.configuration_id=%s AND c.vehicle_id=%s AND o.region=b.region
                 AND o.status='paid' AND e.status='active' AND a.status='active'
                 AND p.fulfillment_status='fulfilled'
                 AND c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected'
               ORDER BY o.order_id LIMIT 1 FOR SHARE OF o,e,a,c,b,p""",
            (vehicle_configuration_id, vehicle_id),
        ).fetchone()
        if paid is None:
            raise ValueError("CATALOG_PROVIDER_RETRY_GRANT_REQUIRED")
        job = cur.execute(
            """SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s
                 AND job_kind='catalog_index' AND request_generation=%s
                 AND catalog_provider_scope_id=%s AND provider_slug=%s AND canonical_vehicle_id=%s""",
            (scope["current_job_id"], scope["generation"], scope["catalog_provider_scope_id"], provider, vehicle_id),
        ).fetchone()
        if job is None:
            raise ValueError("CATALOG_PROVIDER_RETRY_STALE")
        if job["checkpoint"].get("catalog_provider_retry") == audit:
            return _result(cur, None, job)
        if (
            job["source_fetch_job_id"] != expected_job_id
            or scope["status"] != "failed" or scope["error_code"] != "UPSTREAM_UNAVAILABLE"
            or job["status"] != "dead_letter" or job["error_code"] != "UPSTREAM_UNAVAILABLE"
            or job["retryable"] or job["retry_count"] < job["max_attempts"]
            or job["next_attempt_at"] is not None or job["lease_owner"] is not None
        ):
            raise ValueError("CATALOG_PROVIDER_RETRY_STALE")
        scope = cur.execute(
            """UPDATE catalog_article_provider_scopes
               SET generation=generation+1, retry_at=NULL
               WHERE catalog_provider_scope_id=%s RETURNING *""",
            (scope["catalog_provider_scope_id"],),
        ).fetchone()
        successor = _create_catalog_job(cur, scope, {"catalog_provider_retry": audit})
        return _result(cur, None, successor, True)


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
        "UPDATE source_fetch_jobs SET status='completed',phase='completed',lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,retryable=false,error_code=NULL,next_attempt_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
        (lease.job_id,),
    )


def _configuration_candidate_matches(cur, scope, configuration, candidate):
    label = candidate["label"]
    variants = engine_variants_from_label(label)
    variant = configuration["engine_variant"]
    displacement = configuration["engine_displacement_l"]
    if variant is None:
        return displacement is None or not variants
    if variants != (variant,) or (
        displacement is not None and _extract_engine_displacement(label) != float(displacement)
    ):
        return False

    # A requested region echoed by a resolver does not identify the source
    # vehicle's market. Require a same-reference catalog observation with
    # independent market evidence and honor a previously rejected exact mapping.
    region = configuration["region"]
    provider = scope["provider_slug"]
    ref = candidate["opaque_ref"]
    return cur.execute(
        """SELECT EXISTS (
            SELECT 1 FROM vehicle_identity_observations o
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(o.raw_observation->'provider_mappings')='array'
                    THEN o.raw_observation->'provider_mappings' ELSE '[]'::jsonb END
            ) AS mappings(mapping)
            WHERE o.vehicle_id=%s AND o.vehicle_configuration_id=%s
              AND o.resolution_status='matched' AND o.reviewer_state<>'rejected'
              AND o.canonical_observation->'engine_variant_market_verified'='true'::jsonb
              AND o.canonical_observation->>'engine_variant'=%s
              AND o.canonical_observation->>'region'=%s
              AND mapping->>'source_provider'=%s AND mapping->>'provider_id'=%s
              AND mapping->>'source_region'=%s
              AND nullif(btrim(mapping->>'source_uri'),'') IS NOT NULL
              AND nullif(btrim(mapping->>'source_version'),'') IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM vehicle_provider_mappings review
                WHERE review.vehicle_id=o.vehicle_id
                  AND review.vehicle_configuration_id=o.vehicle_configuration_id
                  AND review.provider IN (mapping->>'source_provider',mapping->>'provider')
                  AND review.entity_type='car' AND review.provider_id=mapping->>'provider_id'
                  AND review.mapping_status='rejected'
              )
        ) AS matched""",
        (scope["vehicle_id"], scope["vehicle_configuration_id"], variant, region, provider, ref, region),
    ).fetchone()["matched"]


def _retained_banktwo_catalog_refs(cur, scope, region):
    rows = cur.execute(
        """SELECT DISTINCT mapping->>'provider_id' AS ref
        FROM vehicle_identity_observations o
        JOIN source_snapshots snapshot USING(source_snapshot_id)
        CROSS JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof(o.raw_observation->'provider_mappings')='array'
                THEN o.raw_observation->'provider_mappings' ELSE '[]'::jsonb END
        ) AS mappings(mapping)
        WHERE o.vehicle_id=%s AND o.vehicle_configuration_id=%s
          AND o.resolution_status='matched' AND o.reviewer_state<>'rejected'
          AND o.extraction_evidence_id IS NOT NULL AND snapshot.takedown_status='active'
          AND o.canonical_observation->>'region'=%s
          AND mapping->>'provider'='autoapitwo' AND mapping->>'entity_type'='car'
          AND COALESCE(mapping->>'source_provider','banktwo')='banktwo'
          AND COALESCE(mapping->>'source_region',%s)=%s
          AND nullif(btrim(mapping->>'provider_id'),'') IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM vehicle_provider_mappings review
            WHERE review.vehicle_id=o.vehicle_id AND review.vehicle_configuration_id=o.vehicle_configuration_id
              AND review.provider IN ('autoapitwo','banktwo') AND review.entity_type='car'
              AND review.provider_id=mapping->>'provider_id' AND review.mapping_status='rejected'
          )""",
        (scope["vehicle_id"], scope["vehicle_configuration_id"], region, region, region),
    ).fetchall()
    return {row["ref"] for row in rows}


def _resolve_banktwo_catalog_configuration(repo, client, scope, selector, configuration):
    """Confirm a retained reference against the supplier's current selector catalog."""
    if configuration is None or configuration["trim"] or configuration["engine_variant"]:
        return None, None
    displacement = configuration["engine_displacement_l"]
    if displacement is None:
        return None, None
    region = configuration["region"]
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        retained = _retained_banktwo_catalog_refs(cur, scope, region)
    if not retained:
        return None, None

    query = {key: selector[key] for key in ("year", "make", "model")}
    try:
        catalog = client.catalog("configurations", query, timeout=6)
    except SourceConnectorError as error:
        if error.code != "NOT_FOUND":
            raise
        return None, None
    if isinstance(catalog, SourceCatalogAbsence) or not catalog.complete:
        return None, None

    matches = {}
    drivetrain = configuration["drivetrain"]
    model_suffix = selector["model"].strip().upper().rsplit(" ", 1)[-1]
    if not drivetrain and model_suffix in {"FWD", "RWD", "AWD", "2WD", "4WD"}:
        drivetrain = model_suffix
    for row in catalog.body["items"]:
        ref = row["opaque_ref"]
        if ref not in retained or row.get("year") != selector["year"]:
            continue
        if any((row.get(key) or "").casefold() != selector[key].casefold() for key in ("make", "model")):
            continue
        if (row.get("region") or "US").upper() != region:
            continue
        if drivetrain and (row.get("drivetrain") or model_suffix).casefold() != drivetrain.casefold():
            continue
        label = row.get("configuration") or row["label"]
        engine = row.get("engine") or label
        if (not engine_variants_from_label(label + " " + engine)
            and _extract_engine_displacement(label) == float(displacement)
            and _extract_engine_displacement(engine) in {None, float(displacement)}):
            matches[ref] = {"opaque_ref": ref, "label": label}
    if len(matches) > 1:
        raise SourceConnectorError("AMBIGUOUS")
    candidate = next(iter(matches.values()), None)
    return (candidate, catalog) if candidate is not None else (None, None)


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
        configuration = None
        configuration_unresolved = False
        if scope["vehicle_configuration_id"]:
            configuration = cur.execute(
                """SELECT c.trim,c.engine_displacement_l,c.engine_variant,b.drivetrain,b.region FROM vehicle_configurations c
                JOIN vehicle_identity_bases b USING(vehicle_identity_base_id)
                WHERE c.vehicle_configuration_id=%s""",
                (scope["vehicle_configuration_id"],),
            ).fetchone()
            selector["region"] = configuration["region"]
            label = " ".join(
                str(value).strip()
                for value in (
                    configuration["trim"],
                    (
                        f'{configuration["engine_displacement_l"]:.1f}L'
                        if configuration["engine_displacement_l"] is not None
                        else None
                    ),
                    configuration["engine_variant"],
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
            candidate = None
            catalog_evidence = None
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
                candidates = resolution.body["candidates"]
                ambiguous = len(candidates) > 1
                candidate = candidates[0] if len(candidates) == 1 else None
                if provider == "banktwo" and not candidates:
                    candidate, catalog_evidence = _resolve_banktwo_catalog_configuration(
                        repo, client, scope, selector, configuration
                    )
                resolution_resource = upload_envelope(
                    catalog_evidence or resolution, "vehicle_resolution", object_store
                )
                ref = candidate["opaque_ref"] if candidate is not None else None
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                scope = _lock_scope(cur, lease)
                if catalog_evidence is not None and ref not in _retained_banktwo_catalog_refs(
                    cur, scope, configuration["region"]
                ):
                    ref = None
                    configuration_unresolved = True
                if (
                    candidate is not None
                    and configuration is not None
                    and not _configuration_candidate_matches(cur, scope, configuration, candidate)
                ):
                    ref = None
                    configuration_unresolved = True
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
                if ref is None and not ambiguous and not configuration_unresolved:
                    _complete(cur, lease, scope, "NO_MATCHING_SOURCE_VEHICLE")
                    return
            if ambiguous:
                raise SourceConnectorError("AMBIGUOUS")
            if configuration_unresolved and ref is None:
                raise SourceConnectorError("UNRESOLVED_CONFIGURATION")
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
