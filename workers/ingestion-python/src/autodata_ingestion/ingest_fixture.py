"""Run the deterministic fast-lane fixture through storage and publication."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from autodata_contracts.fakes import FakePaymentProvider, FakePrimarySource, SourceSnapshot

from .normalization import NormalizedVehicle, normalize_source_snapshot
from .object_storage import ensure_versioned_bucket
from .source_adapters import SourceArtifact, SourceResource, adapt_source_resource


ORGANIZATION_ID = "41000000-0000-0000-0000-000000000001"
PRODUCT_KEY = "vehicle-core-fixture"


def build_viewable_content(normalized: NormalizedVehicle) -> dict[str, Any]:
    return {
        "vehicle_identity": {
            "vehicle_key": normalized.vehicle_key,
            "make": normalized.make,
            "model": normalized.model,
            "model_year": normalized.model_year,
            "region": normalized.region,
        },
        "source_metadata": {
            "source_snapshot_id": normalized.source_snapshot_id,
            "source_uri": normalized.source_uri,
            "source_version": normalized.source_version,
            "content_sha256": normalized.source_sha256,
        },
        "specifications": [
            {"name": specification.name, "value": specification.value, "unit": specification.unit}
            for specification in normalized.specifications
        ],
    }


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-ingest:{value}"))


def _timestamp() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _source_payload(snapshot: SourceSnapshot) -> bytes:
    return json.dumps(snapshot.content, sort_keys=True, separators=(",", ":")).encode()


def store_source_object(snapshot: SourceSnapshot) -> SourceArtifact:
    """Store the raw deterministic source artifact in S3-compatible storage."""

    from io import BytesIO

    from minio import Minio

    resource = SourceResource.from_bytes(
        source_uri=snapshot.source_uri,
        source_version=snapshot.source_version,
        payload=_source_payload(snapshot),
        media_type="application/json",
        locator=snapshot.object_key,
        metadata=snapshot.attribution,
    )
    artifact = adapt_source_resource(resource)
    client = Minio(
        os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
        access_key=os.environ["AUTODATA_S3_ACCESS_KEY"],
        secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
        secure=False,
    )
    bucket = os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")
    ensure_versioned_bucket(client, bucket)
    payload = _source_payload(snapshot)
    client.put_object(bucket, artifact.object_key, BytesIO(payload), len(payload), content_type="application/json")
    return artifact


def persist_fast_lane(
    normalized: NormalizedVehicle,
    snapshot: SourceSnapshot,
    organization_id: str = ORGANIZATION_ID,
    object_key: str | None = None,
) -> dict[str, str]:
    """Persist canonical records and one immutable viewable revision atomically."""

    import psycopg
    from psycopg.types.json import Jsonb

    db_address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    host, port_text = db_address.rsplit(":", 1)
    product_id = _stable_uuid(f"product:{PRODUCT_KEY}:1")
    payment_provider = FakePaymentProvider(
        signing_secret=os.environ["AUTODATA_FAKE_PAYMENT_SIGNING_SECRET"]
    )
    session = payment_provider.create_checkout_session(PRODUCT_KEY, organization_id)
    payment_event = payment_provider.record_payment_event(
        payment_provider.verify_webhook(session["headers"], session["body"])
    )
    entitlement = payment_provider.create_entitlement(payment_event)
    request_key = f"fast:{normalized.vehicle_key}:{normalized.source_version}:v1"
    correlation_id = _stable_uuid(f"correlation:{request_key}")
    now = _timestamp()
    content = build_viewable_content(normalized)
    request_id = _stable_uuid(f"request:{request_key}")
    projection_id = _stable_uuid(f"projection:{request_key}")
    revision_id = _stable_uuid(f"revision:{request_key}:1")
    vehicle_id = _stable_uuid(f"vehicle:{normalized.vehicle_key}")

    conninfo = {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dataset_products
                    (dataset_product_id, product_key, product_version, vehicle_selector,
                     minimum_sections, price_minor, currency)
                VALUES (%s, %s, 1, %s, %s, 0, 'USD')
                ON CONFLICT (product_key, product_version)
                DO UPDATE SET product_key = EXCLUDED.product_key
                RETURNING dataset_product_id
                """,
                (
                    product_id,
                    PRODUCT_KEY,
                    Jsonb(
                        {
                            "make": normalized.make,
                            "model": normalized.model,
                            "model_year": normalized.model_year,
                            "region": normalized.region,
                        }
                    ),
                    Jsonb(["vehicle_identity", "source_metadata", "specifications"]),
                ),
            )
            product_id = str(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO source_snapshots
                    (source_snapshot_id, adapter_name, source_uri, source_version,
                     content_sha256, object_key, license_metadata, retrieved_at)
                VALUES (%s, 'fake-primary-source', %s, %s, %s, %s, %s, %s)
                ON CONFLICT (content_sha256)
                DO UPDATE SET object_key = EXCLUDED.object_key
                RETURNING source_snapshot_id
                """,
                (
                    snapshot.source_snapshot_id,
                    snapshot.source_uri,
                    snapshot.source_version,
                    snapshot.content_sha256,
                    object_key or snapshot.object_key,
                    Jsonb(snapshot.attribution),
                    now,
                ),
            )
            source_snapshot_id = str(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO payment_events
                    (payment_event_id, provider_name, provider_event_id, event_type,
                     verified, payload, occurred_at, fulfillment_status,
                     fulfillment_attempts, fulfilled_at)
                VALUES (%s, 'fake', %s, %s, true, %s, %s, 'fulfilled', 1, %s)
                ON CONFLICT (provider_event_id)
                DO UPDATE SET provider_event_id = EXCLUDED.provider_event_id,
                              fulfillment_status = CASE
                                  WHEN payment_events.fulfillment_status = 'failed'
                                  THEN payment_events.fulfillment_status
                                  ELSE 'fulfilled'
                              END,
                              fulfillment_attempts = GREATEST(payment_events.fulfillment_attempts, 1),
                              fulfilled_at = COALESCE(payment_events.fulfilled_at, EXCLUDED.fulfilled_at)
                RETURNING payment_event_id
                """,
                (
                    payment_event.payment_event_id,
                    payment_event.provider_event_id,
                    payment_event.event_type,
                    Jsonb({"product_id": PRODUCT_KEY, "purchaser_id": organization_id}),
                    now,
                    now,
                ),
            )
            payment_event_id = str(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO dataset_requests
                    (dataset_request_id, dataset_product_id, vehicle_key, region, status,
                     lane, source_snapshot_id, correlation_id, idempotency_key,
                     processing_version, organization_id)
                VALUES (%s, %s, %s, %s, 'fast_lane_processing', 'fast', %s, %s, %s, 'fixture-v1', %s)
                ON CONFLICT (idempotency_key)
                DO UPDATE SET source_snapshot_id = EXCLUDED.source_snapshot_id
                RETURNING dataset_request_id
                """,
                (
                    request_id,
                    product_id,
                    normalized.vehicle_key,
                    normalized.region,
                    source_snapshot_id,
                    correlation_id,
                    request_key,
                    organization_id,
                ),
            )
            request_id = str(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO entitlements
                    (entitlement_id, organization_id, dataset_request_id, payment_event_id,
                     provider_event_id, status, granted_at)
                VALUES (%s, %s, %s, %s, %s, 'active', %s)
                ON CONFLICT (provider_event_id)
                DO UPDATE SET provider_event_id = EXCLUDED.provider_event_id
                RETURNING entitlement_id, status
                """,
                (
                    entitlement.entitlement_id,
                    organization_id,
                    request_id,
                    payment_event_id,
                    payment_event.provider_event_id,
                    now,
                ),
            )
            entitlement_id, entitlement_status = cursor.fetchone()
            entitlement_id = str(entitlement_id)
            if entitlement_status == "revoked":
                raise ValueError("entitlement is revoked; refusing fast-lane fulfillment")
            cursor.execute(
                """
                INSERT INTO dataset_projections
                    (dataset_projection_id, dataset_product_id, dataset_request_id, entitlement_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset_request_id)
                DO UPDATE SET dataset_request_id = EXCLUDED.dataset_request_id
                RETURNING dataset_projection_id
                """,
                (projection_id, product_id, request_id, entitlement_id),
            )
            projection_id = str(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO vehicles
                    (vehicle_id, vehicle_key, make, model, model_year, region,
                     source_snapshot_id, source_watermark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (vehicle_key)
                DO UPDATE SET source_snapshot_id = EXCLUDED.source_snapshot_id,
                              source_watermark = EXCLUDED.source_watermark,
                              updated_at = now()
                RETURNING vehicle_id
                """,
                (
                    vehicle_id,
                    normalized.vehicle_key,
                    normalized.make,
                    normalized.model,
                    normalized.model_year,
                    normalized.region,
                    source_snapshot_id,
                    normalized.source_version,
                ),
            )
            vehicle_id = str(cursor.fetchone()[0])
            for specification in normalized.specifications:
                cursor.execute(
                    """
                    INSERT INTO vehicle_specifications
                        (vehicle_id, name, value_json, unit, source_snapshot_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, name)
                    DO UPDATE SET value_json = EXCLUDED.value_json,
                                  unit = EXCLUDED.unit,
                                  source_snapshot_id = EXCLUDED.source_snapshot_id
                    """,
                    (
                        vehicle_id,
                        specification.name,
                        Jsonb(specification.value),
                        specification.unit,
                        source_snapshot_id,
                    ),
                )
            cursor.execute(
                """
                UPDATE dataset_requests
                SET status = 'viewable', vehicle_id = %s, updated_at = now()
                WHERE dataset_request_id = %s
                """,
                (vehicle_id, request_id),
            )
            cursor.execute(
                """
                INSERT INTO dataset_revisions
                    (dataset_revision_id, dataset_projection_id, revision_number,
                     availability, source_watermark, schema_version, changelog, content, published_at)
                VALUES (%s, %s, 1, 'viewable', %s, 1, %s, %s, %s)
                ON CONFLICT (dataset_projection_id, revision_number)
                DO NOTHING
                """,
                (
                    revision_id,
                    projection_id,
                    normalized.source_version,
                    Jsonb({"kind": "initial-fast-lane-publication", "source_sha256": normalized.source_sha256}),
                    Jsonb(content),
                    now,
                ),
            )
            for section_name in ("vehicle_identity", "source_metadata", "specifications"):
                cursor.execute(
                    """
                    INSERT INTO dataset_section_status
                        (dataset_projection_id, section_name, status,
                         last_published_revision_id, updated_at)
                    VALUES (%s, %s, 'viewable', %s, %s)
                    ON CONFLICT (dataset_projection_id, section_name)
                    DO UPDATE SET status = 'viewable',
                                  last_published_revision_id = EXCLUDED.last_published_revision_id,
                                  updated_at = EXCLUDED.updated_at
                    """,
                    (projection_id, section_name, revision_id, now),
                )
            cursor.execute(
                """
                INSERT INTO publication_events
                    (event_type, event_version, dataset_request_id, dataset_projection_id,
                     dataset_revision_id, correlation_id, idempotency_key, payload, published_at,
                     producer)
                VALUES ('dataset.viewable', 1, %s, %s, %s, %s, %s, %s, %s, 'ingestion-worker')
                ON CONFLICT (idempotency_key)
                DO NOTHING
                """,
                (
                    request_id,
                    projection_id,
                    revision_id,
                    correlation_id,
                    f"viewable:{request_id}:1",
                    Jsonb({"source_snapshot_id": source_snapshot_id, "source_watermark": normalized.source_version}),
                    now,
                ),
            )
        connection.commit()
    return {
        "dataset_request_id": request_id,
        "entitlement_id": entitlement_id,
        "projection_id": projection_id,
        "revision_id": revision_id,
        "vehicle_id": vehicle_id,
        "payment_event_id": payment_event_id,
        "source_snapshot_id": source_snapshot_id,
    }


async def publish_viewable_event(result: dict[str, str], normalized: NormalizedVehicle) -> None:
    import nats
    from nats.js.errors import BadRequestError

    connection = await nats.connect(os.getenv("AUTODATA_NATS_URL", "nats://nats:4222"))
    try:
        jetstream = connection.jetstream()
        try:
            await jetstream.add_stream(name="AUTODATA", subjects=["dataset.>"])
        except BadRequestError as error:
            if "stream name already in use" not in str(error).lower():
                raise
        event = {
            "event_id": _stable_uuid(f"event:{result['revision_id']}"),
            "event_type": "dataset.viewable",
            "event_version": 1,
            "occurred_at": _timestamp().isoformat(),
            "producer": "ingestion-worker",
            "request_id": result["dataset_request_id"],
            "projection_id": result["projection_id"],
            "revision_id": result["revision_id"],
            "correlation_id": _stable_uuid(f"correlation:{result['dataset_request_id']}"),
            "idempotency_key": f"viewable:{result['dataset_request_id']}:1",
            "payload": {
                "vehicle_key": normalized.vehicle_key,
                "source_snapshot_id": result["source_snapshot_id"],
                "source_watermark": normalized.source_version,
            },
        }
        await jetstream.publish("dataset.viewable", json.dumps(event, sort_keys=True).encode())
        await connection.flush()
    finally:
        await connection.close()

    import psycopg

    db_address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    host, port_text = db_address.rsplit(":", 1)
    with psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    ) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE publication_events
            SET delivery_status = 'published', delivered_at = now(), delivery_attempts = GREATEST(delivery_attempts, 1)
            WHERE idempotency_key = %s
            """,
            (f"viewable:{result['dataset_request_id']}:1",),
        )
        connection.commit()


def run_fixture() -> dict[str, Any]:
    source = FakePrimarySource()
    snapshot = source.fetch(
        os.getenv("AUTODATA_FIXTURE_MAKE", "Toyota"),
        os.getenv("AUTODATA_FIXTURE_MODEL", "Corolla"),
        int(os.getenv("AUTODATA_FIXTURE_YEAR", "2024")),
        os.getenv("AUTODATA_FIXTURE_REGION", "US"),
        os.getenv("AUTODATA_FIXTURE_VERSION", "fixture-v1"),
    )
    normalized = normalize_source_snapshot(snapshot)
    if os.getenv("AUTODATA_INGEST_DRY_RUN") == "1":
        return {"normalized": normalized.to_dict(), "dry_run": True}
    artifact = store_source_object(snapshot)
    result = persist_fast_lane(normalized, snapshot, object_key=artifact.object_key)
    asyncio.run(publish_viewable_event(result, normalized))
    return {"normalized": normalized.to_dict(), "published": result, "event_subject": "dataset.viewable"}


def main() -> None:
    print(json.dumps(run_fixture(), sort_keys=True))


if __name__ == "__main__":
    main()
