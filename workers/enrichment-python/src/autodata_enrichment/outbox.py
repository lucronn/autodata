"""At-least-once delivery of PostgreSQL publication events to NATS JetStream."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


EVENT_SUBJECTS = {
    "catalog.article.published",
    "dataset.fast.requested",
    "dataset.viewable",
    "dataset.deep.requested",
    "dataset.section.published",
    "dataset.enrichment.failed",
    "dataset.review.requested",
    "dataset.revision.revoked",
    "dataset.knowledge.fallback.requested",
}


@dataclass(frozen=True)
class OutboxEvent:
    publication_event_id: str
    event_type: str
    event_version: int
    request_id: str | None
    projection_id: str | None
    revision_id: str | None
    correlation_id: str
    idempotency_key: str
    payload: dict[str, Any]
    occurred_at: datetime
    producer: str
    delivery_attempts: int = 0
    canonical_article_id: str | None = None
    canonical_revision_id: str | None = None
    delivery_lease_owner: str | None = None
    delivery_lease_token: int = 0


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

    if event.event_type == "catalog.article.published":
        from dataclasses import asdict
        from uuid import UUID
        from autodata_contracts.contracts import CatalogArticlePublished, ARTICLE_REVIEW_STATUS_VALUES
        for identifier in (event.publication_event_id,event.correlation_id,event.canonical_article_id,event.canonical_revision_id,event.payload.get("source_revision_id")):
            UUID(str(identifier))
        if event.event_version != 1 or event.payload.get("review_status") not in ARTICLE_REVIEW_STATUS_VALUES:
            raise ValueError("invalid catalog publication envelope")
        if any((event.request_id,event.projection_id,event.revision_id)):
            raise ValueError("catalog event contains dataset identity")
        return asdict(CatalogArticlePublished(event.publication_event_id,event.event_type,event.event_version,
            event.occurred_at.astimezone(UTC).isoformat(),event.producer,event.correlation_id,event.idempotency_key,
            event.canonical_article_id,event.payload["source_revision_id"],event.canonical_revision_id,event.payload["review_status"]))
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


async def relay_pending_events(
    limit: int = 10,
    max_attempts: int = 3,
    *,
    address: str | None = None,
    nats_url: str | None = None,
) -> dict[str, Any]:
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

    resolved_nats_url = _resolve_nats_url(nats_url)

    async def _silent_nats_error(error: Exception) -> None:
        pass

    try:
        connection = await nats.connect(
            resolved_nats_url,
            connect_timeout=1,
            max_reconnect_attempts=1,
            allow_reconnect=False,
            error_cb=_silent_nats_error,
        )
    except Exception as error:
        return {
            "status": f"skipped (broker unreachable: {error})",
            "claimed": 0,
            "published": 0,
            "failed": 0,
            "dead_lettered": 0,
        }
    try:
        jetstream = connection.jetstream()
        await _ensure_stream(jetstream)
        published = 0
        failed = 0
        dead_lettered = 0
        while published + failed + dead_lettered < limit:
            event = _claim_next_event(max_attempts, address=address)
            if event is None:
                break
            try:
                await publish_event(event, jetstream)
            except Exception as error:  # noqa: BLE001 - boundary records all delivery errors
                status = _record_delivery_failure(event, str(error), max_attempts, address=address)
                if status == "dead_letter":
                    dead_lettered += 1
                else:
                    failed += 1
            else:
                _mark_delivered(event, address=address)
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
    from nats.js.errors import NotFoundError
    for name,subjects in (("AUTODATA",["dataset.>"]),("AUTODATA_CATALOG",["catalog.>"])):
        try:
            await jetstream.stream_info(name)
        except NotFoundError:
            await jetstream.add_stream(name=name,subjects=subjects)


def _claim_next_event(max_attempts: int, address: str | None = None) -> OutboxEvent | None:
    import psycopg
    from uuid import uuid4
    owner=uuid4()
    with psycopg.connect(**_connection_kwargs(address=address)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""WITH exhausted AS (SELECT publication_event_id FROM publication_events
                WHERE delivery_status='processing' AND delivery_lease_expires_at<clock_timestamp()
                  AND delivery_attempts>=%s FOR UPDATE SKIP LOCKED)
                UPDATE publication_events pe SET delivery_status='dead_letter',delivery_lease_owner=NULL,
                  delivery_lease_expires_at=NULL,last_delivery_error='{"code":"DELIVERY_ATTEMPTS_EXHAUSTED"}'
                FROM exhausted e WHERE pe.publication_event_id=e.publication_event_id""",(max_attempts,))
            cursor.execute("""WITH candidate AS (
                SELECT publication_event_id FROM publication_events WHERE delivery_attempts<%s AND
                  ((delivery_status IN ('pending','failed') AND COALESCE(next_delivery_at,'-infinity'::timestamptz)<=clock_timestamp())
                   OR (delivery_status='processing' AND delivery_lease_expires_at<clock_timestamp()))
                ORDER BY created_at,publication_event_id FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE publication_events pe SET delivery_status='processing',delivery_attempts=pe.delivery_attempts+1,
                  delivery_lease_owner=%s,delivery_lease_token=pe.delivery_lease_token+1,
                  delivery_lease_expires_at=clock_timestamp()+interval '90 seconds'
                FROM candidate WHERE pe.publication_event_id=candidate.publication_event_id
                RETURNING pe.publication_event_id::text,pe.event_type,pe.event_version,pe.dataset_request_id::text,
                  pe.dataset_projection_id::text,pe.dataset_revision_id::text,pe.correlation_id::text,
                  pe.idempotency_key,pe.payload,pe.created_at,pe.producer,pe.delivery_attempts,
                  pe.canonical_article_id::text,pe.canonical_article_revision_id::text,pe.delivery_lease_owner::text,pe.delivery_lease_token""",(max_attempts,owner))
            row=cursor.fetchone()
    return _event_from_row(row) if row is not None else None


def _event_from_row(row: tuple[Any, ...]) -> OutboxEvent:
    payload = row[8] if isinstance(row[8], dict) else json.loads(row[8])
    return OutboxEvent(
        publication_event_id=str(row[0]),
        event_type=str(row[1]),
        event_version=int(row[2]),
        request_id=str(row[3]) if row[3] is not None else None,
        projection_id=str(row[4]) if row[4] is not None else None,
        revision_id=str(row[5]) if row[5] is not None else None,
        correlation_id=str(row[6]),
        idempotency_key=str(row[7]),
        payload=payload,
        occurred_at=row[9],
        producer=str(row[10]),
        delivery_attempts=int(row[11]),
        canonical_article_id=row[12],canonical_revision_id=row[13],
        delivery_lease_owner=row[14],delivery_lease_token=row[15],
    )


class DeliveryLeaseLost(RuntimeError):
    pass


def _finish_delivery(event, *, status, error=None, address=None):
    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(**_connection_kwargs(address=address)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE publication_events SET delivery_status=%s,
                delivered_at=CASE WHEN %s='published' THEN clock_timestamp() ELSE NULL END,
                last_delivery_error=%s,delivery_lease_owner=NULL,delivery_lease_expires_at=NULL,
                next_delivery_at=CASE WHEN %s='failed' THEN clock_timestamp()+interval '5 seconds' ELSE NULL END
                WHERE publication_event_id=%s AND delivery_status='processing' AND delivery_lease_owner=%s
                  AND delivery_lease_token=%s AND delivery_lease_expires_at>clock_timestamp()
                RETURNING publication_event_id""",
                (status,status,Jsonb(error) if error else None,status,event.publication_event_id,event.delivery_lease_owner,event.delivery_lease_token))
            if cursor.fetchone() is None: raise DeliveryLeaseLost("outbox delivery lease lost")


def _mark_delivered(event: OutboxEvent, address: str | None = None) -> None:
    _finish_delivery(event,status="published",address=address)


def _record_delivery_failure(event: OutboxEvent, message: str, max_attempts: int, address: str | None = None) -> str:
    status=delivery_status_after_failure(event.delivery_attempts,max_attempts)
    _finish_delivery(event,status=status,error={"code":"BROKER_DELIVERY_FAILED"},address=address)
    return status


def _resolve_database_address(address: str | None = None) -> str:
    if address:
        return address
    configured = os.getenv("AUTODATA_DB_ADDRESS")
    if configured:
        return configured
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.2):
            return "127.0.0.1:5432"
    except OSError:
        pass
    return "postgres:5432"


def _resolve_nats_url(url: str | None = None) -> str:
    if url:
        return url
    configured = os.getenv("AUTODATA_NATS_URL")
    if configured:
        return configured
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 4222), timeout=0.2):
            return "nats://127.0.0.1:4222"
    except OSError:
        pass
    try:
        import socket
        socket.getaddrinfo("nats", 4222)
        return "nats://nats:4222"
    except OSError:
        pass
    return "nats://127.0.0.1:4222"


def _connection_kwargs(address: str | None = None) -> dict[str, Any]:
    resolved = _resolve_database_address(address)
    host, separator, port = resolved.rpartition(":")
    if not separator:
        host, port = resolved, "5432"
    return {
        "host": host,
        "port": int(port),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
    }
