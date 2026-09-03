"""At-least-once delivery of PostgreSQL publication events to NATS JetStream."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


EVENT_SUBJECTS = {
    "dataset.fast.requested",
    "dataset.viewable",
    "dataset.deep.requested",
    "dataset.section.published",
    "dataset.enrichment.failed",
    "dataset.review.requested",
    "dataset.revision.revoked",
}


@dataclass(frozen=True)
class OutboxEvent:
    publication_event_id: str
    event_type: str
    event_version: int
    request_id: str
    projection_id: str
    revision_id: str | None
    correlation_id: str
    idempotency_key: str
    payload: dict[str, Any]
    occurred_at: datetime
    producer: str
    delivery_attempts: int = 0


def event_subject(event: OutboxEvent) -> str:
    """Return the allow-listed versioned subject for a stored event type."""

    if event.event_type not in EVENT_SUBJECTS:
        raise ValueError(f"event type is not publishable on the dataset bus: {event.event_type}")
    return event.event_type


def delivery_status_after_failure(attempts: int, max_attempts: int) -> str:
    if attempts < 1 or max_attempts < 1:
        raise ValueError("delivery attempts and max attempts must be positive")
    return "dead_letter" if attempts >= max_attempts else "failed"


def build_event_envelope(event: OutboxEvent) -> dict[str, Any]:
    """Reconstruct the public event envelope from the immutable outbox row."""

    for field_name in (
        "publication_event_id",
        "event_type",
        "request_id",
        "projection_id",
        "correlation_id",
        "idempotency_key",
        "producer",
    ):
        if not getattr(event, field_name):
            raise ValueError(f"outbox event is missing required {field_name}")
    if not isinstance(event.payload, dict):
        raise ValueError("outbox event payload must be an object")
    occurred_at = event.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return {
        "event_id": event.publication_event_id,
        "event_type": event.event_type,
        "event_version": event.event_version,
        "occurred_at": occurred_at.astimezone(UTC).isoformat(),
        "producer": event.producer,
        "request_id": event.request_id,
        "projection_id": event.projection_id,
        "revision_id": event.revision_id,
        "correlation_id": event.correlation_id,
        "idempotency_key": event.idempotency_key,
        "payload": event.payload,
    }


async def publish_event(event: OutboxEvent, jetstream: Any) -> Any:
    """Publish one event with a stable NATS de-duplication message ID."""

    subject = event_subject(event)
    payload = json.dumps(build_event_envelope(event), sort_keys=True).encode()
    return await jetstream.publish(
        subject,
        payload,
        headers={"Nats-Msg-Id": event.idempotency_key},
    )


async def relay_pending_events(limit: int = 10, max_attempts: int = 3) -> dict[str, Any]:
    """Claim, publish, and record a bounded batch of pending outbox events.

    PostgreSQL claiming and NATS publication are intentionally separate commits.
    A crash between them can cause a duplicate, so consumers must deduplicate by
    the envelope idempotency key and NATS receives the same key as its message ID.
    """

    if limit < 1:
        raise ValueError("relay limit must be positive")
    if max_attempts < 1:
        raise ValueError("max attempts must be positive")

    import nats

    connection = await nats.connect(os.getenv("AUTODATA_NATS_URL", "nats://nats:4222"))
    try:
        jetstream = connection.jetstream()
        await _ensure_stream(jetstream)
        published = 0
        failed = 0
        dead_lettered = 0
        while published + failed + dead_lettered < limit:
            event = _claim_next_event(max_attempts)
            if event is None:
                break
            try:
                await publish_event(event, jetstream)
            except Exception as error:  # noqa: BLE001 - boundary records all delivery errors
                status = _record_delivery_failure(event, str(error), max_attempts)
                if status == "dead_letter":
                    dead_lettered += 1
                else:
                    failed += 1
            else:
                _mark_delivered(event)
                published += 1
        await connection.flush()
        return {
            "status": "completed",
            "claimed": published + failed + dead_lettered,
            "published": published,
            "failed": failed,
            "dead_lettered": dead_lettered,
        }
    finally:
        await connection.close()


async def _ensure_stream(jetstream: Any) -> None:
    try:
        await jetstream.stream_info("AUTODATA")
    except Exception as error:  # noqa: BLE001 - only the server decides whether it exists
        if "stream name already in use" in str(error).lower():
            return
        await jetstream.add_stream(name="AUTODATA", subjects=["dataset.>"])


def _claim_next_event(max_attempts: int) -> OutboxEvent | None:
    import psycopg

    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT publication_event_id
                    FROM publication_events
                    WHERE delivery_status IN ('pending', 'failed')
                      AND delivery_attempts < %s
                    ORDER BY created_at, publication_event_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE publication_events pe
                SET delivery_status = 'failed',
                    delivery_attempts = pe.delivery_attempts + 1
                FROM candidate
                WHERE pe.publication_event_id = candidate.publication_event_id
                RETURNING pe.publication_event_id::text, pe.event_type,
                          pe.event_version, pe.dataset_request_id::text,
                          pe.dataset_projection_id::text, pe.dataset_revision_id::text,
                          pe.correlation_id::text, pe.idempotency_key, pe.payload,
                          pe.created_at, pe.producer, pe.delivery_attempts
                """,
                (max_attempts,),
            )
            row = cursor.fetchone()
        connection.commit()
    return _event_from_row(row) if row is not None else None


def _event_from_row(row: tuple[Any, ...]) -> OutboxEvent:
    payload = row[8] if isinstance(row[8], dict) else json.loads(row[8])
    return OutboxEvent(
        publication_event_id=str(row[0]),
        event_type=str(row[1]),
        event_version=int(row[2]),
        request_id=str(row[3]),
        projection_id=str(row[4]),
        revision_id=str(row[5]) if row[5] is not None else None,
        correlation_id=str(row[6]),
        idempotency_key=str(row[7]),
        payload=payload,
        occurred_at=row[9],
        producer=str(row[10]),
        delivery_attempts=int(row[11]),
    )


def _mark_delivered(event: OutboxEvent) -> None:
    import psycopg

    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE publication_events
                SET delivery_status = 'published', delivered_at = now(),
                    last_delivery_error = NULL
                WHERE publication_event_id = %s
                  AND delivery_attempts = %s
                """,
                (event.publication_event_id, event.delivery_attempts),
            )
        connection.commit()


def _record_delivery_failure(event: OutboxEvent, message: str, max_attempts: int) -> str:
    import psycopg
    from psycopg.types.json import Jsonb

    status = delivery_status_after_failure(event.delivery_attempts, max_attempts)
    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE publication_events
                SET delivery_status = %s,
                    last_delivery_error = %s
                WHERE publication_event_id = %s
                  AND delivery_attempts = %s
                """,
                (status, Jsonb({"message": message}), event.publication_event_id, event.delivery_attempts),
            )
        connection.commit()
    return status


def _connection_kwargs() -> dict[str, Any]:
    address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    host, separator, port = address.rpartition(":")
    if not separator:
        host, port = address, "5432"
    return {
        "host": host,
        "port": int(port),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }
