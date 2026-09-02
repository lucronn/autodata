"""Verify the deterministic fast-lane fixture across database, object storage, and NATS."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from typing import Any


FIXTURE_MAKE = "Toyota"
FIXTURE_MODEL = "Corolla"
FIXTURE_YEAR = 2024
FIXTURE_REGION = "US"
FIXTURE_VERSION = "fixture-v1"
FIXTURE_VEHICLE_KEY = "toyota-corolla-2024-us"
FIXTURE_REQUEST_KEY = f"fast:{FIXTURE_VEHICLE_KEY}:{FIXTURE_VERSION}:v1"


def summarize_source_object(
    payload: bytes,
    expected_vehicle: str,
    expected_vehicle_key: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError(
            f"source object hash mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"source object is not valid JSON: {error}") from error
    vehicle = document.get("vehicle")
    if not isinstance(vehicle, dict):
        raise ValueError("source object is missing vehicle identity")
    actual_vehicle = f'{vehicle.get("make")} {vehicle.get("model")} {vehicle.get("year")}'
    if actual_vehicle != expected_vehicle:
        raise ValueError(f"source object identity mismatch: expected {expected_vehicle}, got {actual_vehicle}")
    actual_key = "-".join(
        (str(vehicle.get("make", "")), str(vehicle.get("model", "")), str(vehicle.get("year", "")), str(vehicle.get("region", "")).lower())
    ).lower()
    if actual_key != expected_vehicle_key:
        raise ValueError(f"source object vehicle key mismatch: expected {expected_vehicle_key}, got {actual_key}")
    return {
        "object_bytes": len(payload),
        "object_sha256": actual_sha256,
        "object_vehicle": actual_vehicle,
    }


def summarize_viewable_event(event: dict[str, Any], expected_revision_id: str) -> dict[str, Any]:
    if event.get("event_type") != "dataset.viewable":
        raise ValueError(f"NATS event is not dataset.viewable: {event.get('event_type')}")
    if event.get("event_version") != 1:
        raise ValueError(f"NATS event version is not 1: {event.get('event_version')}")
    if event.get("revision_id") != expected_revision_id:
        raise ValueError(
            f"NATS revision mismatch: expected {expected_revision_id}, got {event.get('revision_id')}"
        )
    if not str(event.get("idempotency_key", "")).startswith("viewable:"):
        raise ValueError("NATS event is missing a viewable idempotency key")
    return {
        "event_type": event["event_type"],
        "event_version": event["event_version"],
        "revision_id": event["revision_id"],
        "subject": "dataset.viewable",
    }


def _db_connection():
    import psycopg

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    )


def _read_database() -> dict[str, Any]:
    from autodata_contracts.fakes import FakePaymentProvider

    provider = FakePaymentProvider(os.environ["AUTODATA_FAKE_PAYMENT_SIGNING_SECRET"])
    session = provider.create_checkout_session("vehicle-core-fixture", "41000000-0000-0000-0000-000000000001")
    payment = provider.verify_webhook(session["headers"], session["body"])
    provider_event_id = payment["provider_event_id"]
    with _db_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT dr.dataset_request_id, dr.status, e.status, dp.dataset_projection_id,
                   dvr.dataset_revision_id, dvr.availability, dvr.revision_number,
                   dvr.source_watermark, ss.object_key, ss.content_sha256,
                   v.vehicle_key, count(dss.section_name)
            FROM dataset_requests dr
            JOIN entitlements e ON e.dataset_request_id = dr.dataset_request_id
            JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
            JOIN dataset_revisions dvr ON dvr.dataset_projection_id = dp.dataset_projection_id
            JOIN source_snapshots ss ON ss.source_snapshot_id = dr.source_snapshot_id
            JOIN vehicles v ON v.vehicle_id = dr.vehicle_id
            LEFT JOIN dataset_section_status dss ON dss.dataset_projection_id = dp.dataset_projection_id
            WHERE dr.idempotency_key = %s
            GROUP BY dr.dataset_request_id, dr.status, e.status, dp.dataset_projection_id,
                     dvr.dataset_revision_id, dvr.availability, dvr.revision_number,
                     dvr.source_watermark, ss.object_key, ss.content_sha256, v.vehicle_key
            """,
            (FIXTURE_REQUEST_KEY,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"database has no dataset request for idempotency key {FIXTURE_REQUEST_KEY}")
        (
            request_id,
            request_status,
            entitlement_status,
            projection_id,
            revision_id,
            availability,
            revision_number,
            source_watermark,
            object_key,
            content_sha256,
            vehicle_key,
            section_count,
        ) = row
        cursor.execute(
            "SELECT count(*) FROM payment_events WHERE provider_event_id = %s",
            (provider_event_id,),
        )
        payment_event_count = cursor.fetchone()[0]
    if request_status != "viewable":
        raise ValueError(f"dataset request is not viewable: {request_status}")
    if entitlement_status != "active":
        raise ValueError(f"fixture entitlement is not active: {entitlement_status}")
    if availability != "viewable" or revision_number != 1:
        raise ValueError(f"fixture revision is not the first viewable revision: {availability}/{revision_number}")
    if vehicle_key != FIXTURE_VEHICLE_KEY:
        raise ValueError(f"normalized vehicle key mismatch: {vehicle_key}")
    if section_count != 3:
        raise ValueError(f"minimum viewable section count is not 3: {section_count}")
    if payment_event_count != 1:
        raise ValueError(f"expected exactly one persisted payment event, got {payment_event_count}")
    return {
        "dataset_request_id": str(request_id),
        "projection_id": str(projection_id),
        "revision_id": str(revision_id),
        "source_watermark": source_watermark,
        "object_key": object_key,
        "content_sha256": content_sha256,
    }


def _read_object(database: dict[str, Any]) -> dict[str, Any]:
    from minio import Minio

    client = Minio(
        os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
        access_key=os.environ["AUTODATA_S3_ACCESS_KEY"],
        secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
        secure=False,
    )
    try:
        response = client.get_object(os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources"), database["object_key"])
        payload = response.read()
        response.close()
    except Exception as error:
        raise RuntimeError(f"cannot inspect source object {database['object_key']}: {error}") from error
    return summarize_source_object(payload, "Toyota Corolla 2024", FIXTURE_VEHICLE_KEY, database["content_sha256"])


async def _read_event(database: dict[str, Any]) -> dict[str, Any]:
    import nats

    connection = await nats.connect(os.getenv("AUTODATA_NATS_URL", "nats://nats:4222"))
    durable = f"smoke-{uuid.uuid4().hex[:12]}"
    try:
        jetstream = connection.jetstream()
        await jetstream.stream_info("AUTODATA")
        subscription = await jetstream.pull_subscribe("dataset.viewable", durable=durable)
        for _ in range(10):
            try:
                messages = await subscription.fetch(1, timeout=1)
            except asyncio.TimeoutError:
                break
            message = messages[0]
            event = json.loads(message.data)
            await message.ack()
            if event.get("revision_id") == database["revision_id"]:
                return summarize_viewable_event(event, database["revision_id"])
        raise ValueError(f"NATS stream has no dataset.viewable event for revision {database['revision_id']}")
    except Exception as error:
        if isinstance(error, ValueError):
            raise
        raise RuntimeError(f"cannot inspect NATS JetStream AUTODATA: {error}") from error
    finally:
        try:
            await connection.jetstream().delete_consumer("AUTODATA", durable)
        except Exception:
            pass
        await connection.close()


def main() -> None:
    try:
        database = _read_database()
        object_summary = _read_object(database)
        event_summary = asyncio.run(_read_event(database))
    except Exception as error:
        raise SystemExit(f"ingestion smoke failed: {error}") from error
    print(json.dumps({"database": database, "object": object_summary, "event": event_summary}, sort_keys=True))


if __name__ == "__main__":
    main()
