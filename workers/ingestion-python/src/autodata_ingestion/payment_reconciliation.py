"""Durable, provider-neutral reconciliation for verified payment events."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class PaymentEventConflict(ValueError):
    """The same provider event ID was received with different trusted data."""


class EntitlementNotFound(ValueError):
    """The entitlement cannot be located in the projection boundary."""


@dataclass(frozen=True)
class PaymentIntent:
    provider_name: str
    provider_event_id: str
    event_type: str
    product_id: str
    purchaser_id: str
    dataset_request_id: str | None
    payload: dict[str, Any]

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "PaymentIntent":
        required = ("provider_event_id", "event_type", "product_id", "purchaser_id")
        missing = [name for name in required if not str(event.get(name, "")).strip()]
        if missing:
            raise ValueError(f"payment event is missing required fields: {', '.join(missing)}")
        event_type = str(event["event_type"]).strip()
        if event_type != "checkout.completed":
            raise ValueError(f"unsupported payment event type: {event_type}")
        dataset_request_id = str(event.get("dataset_request_id", "")).strip() or None
        return cls(
            provider_name=str(event.get("provider_name", "fake")).strip() or "fake",
            provider_event_id=str(event["provider_event_id"]).strip(),
            event_type=event_type,
            product_id=str(event["product_id"]).strip(),
            purchaser_id=str(event["purchaser_id"]).strip(),
            dataset_request_id=dataset_request_id,
            payload=dict(event),
        )

    @property
    def payment_event_id(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-payment:{self.provider_name}:{self.provider_event_id}"))


def canonical_payment_payload(payload: dict[str, Any]) -> str:
    """Return a deterministic representation suitable for replay comparison."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def revoke_entitlement(connection: Any, entitlement_id: str, reason: str) -> dict[str, Any]:
    """Revoke access and enqueue one auditable revision-revoked event."""

    entitlement_id = str(entitlement_id).strip()
    reason = str(reason).strip()
    if not entitlement_id or not reason or len(reason) > 1000:
        raise ValueError("entitlement ID and an auditable reason are required")
    from psycopg.types.json import Jsonb

    now = datetime.now(UTC)
    idempotency_key = f"revocation:{entitlement_id}"
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.entitlement_id::text, e.status, e.revoke_reason,
                       dr.dataset_request_id::text, dp.dataset_projection_id::text,
                       dr.correlation_id::text
                FROM entitlements e
                JOIN dataset_requests dr ON dr.dataset_request_id = e.dataset_request_id
                JOIN dataset_projections dp ON dp.entitlement_id = e.entitlement_id
                WHERE e.entitlement_id::text = %s
                FOR UPDATE
                """,
                (entitlement_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise EntitlementNotFound(f"entitlement {entitlement_id} was not found")
            stored_entitlement_id, stored_status, stored_reason, request_id, projection_id, correlation_id = row
            if stored_status != "revoked":
                cursor.execute(
                    """
                    UPDATE entitlements
                    SET status = 'revoked', revoked_at = now(), revoke_reason = %s
                    WHERE entitlement_id = %s
                    """,
                    (reason, stored_entitlement_id),
                )
                cursor.execute(
                    """
                    UPDATE dataset_requests
                    SET status = 'revoked', updated_at = now()
                    WHERE dataset_request_id = %s AND status <> 'revoked'
                    """,
                    (request_id,),
                )
                stored_reason = reason

            cursor.execute(
                """
                SELECT dataset_revision_id::text
                FROM dataset_revisions
                WHERE dataset_projection_id = %s
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (projection_id,),
            )
            revision_row = cursor.fetchone()
            revision_id = revision_row[0] if revision_row is not None else None
            payload = Jsonb(
                {
                    "entitlement_id": stored_entitlement_id,
                    "reason": stored_reason or reason,
                    "request_id": request_id,
                    "projection_id": projection_id,
                }
            )
            cursor.execute(
                """
                INSERT INTO publication_events
                    (event_type, event_version, dataset_request_id,
                     dataset_projection_id, dataset_revision_id, correlation_id,
                     idempotency_key, payload, published_at, producer)
                VALUES ('dataset.revision.revoked', 1, %s, %s, %s, %s, %s, %s, %s, 'payment-reconciler')
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    request_id,
                    projection_id,
                    revision_id,
                    correlation_id,
                    idempotency_key,
                    payload,
                    now,
                ),
            )
            cursor.execute(
                """
                SELECT publication_event_id::text
                FROM publication_events
                WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            )
            publication_event_id = cursor.fetchone()[0]
            return {
                "status": "revoked",
                "entitlement_id": stored_entitlement_id,
                "dataset_request_id": request_id,
                "dataset_projection_id": projection_id,
                "dataset_revision_id": revision_id,
                "publication_event_id": publication_event_id,
                "reason": stored_reason or reason,
            }


def reconcile_payment_event(connection: Any, event: dict[str, Any]) -> dict[str, Any]:
    """Record and fulfill one verified checkout event atomically.

    A payment can be recorded before its dataset request exists. In that case
    the event remains pending and a later reconciliation call can finish the
    entitlement and projection without replaying provider side effects.
    """

    intent = PaymentIntent.from_event(event)
    from psycopg.types.json import Jsonb

    now = datetime.now(UTC)
    payload_json = canonical_payment_payload(intent.payload)
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payment_events
                    (payment_event_id, provider_name, provider_event_id, event_type,
                     verified, payload, occurred_at, fulfillment_status)
                VALUES (%s, %s, %s, %s, true, %s, %s, 'pending')
                ON CONFLICT (provider_event_id) DO NOTHING
                """,
                (
                    intent.payment_event_id,
                    intent.provider_name,
                    intent.provider_event_id,
                    intent.event_type,
                    Jsonb(intent.payload),
                    now,
                ),
            )
            cursor.execute(
                """
                SELECT payment_event_id::text, payload, fulfillment_status,
                       fulfillment_attempts
                FROM payment_events
                WHERE provider_event_id = %s
                FOR UPDATE
                """,
                (intent.provider_event_id,),
            )
            stored_id, stored_payload, stored_status, attempts = cursor.fetchone()
            if canonical_payment_payload(stored_payload) != payload_json:
                raise PaymentEventConflict(
                    f"provider event {intent.provider_event_id} was replayed with different payload"
                )
            attempts += 1
            cursor.execute(
                """
                UPDATE payment_events
                SET fulfillment_attempts = %s, last_fulfillment_error = NULL
                WHERE payment_event_id = %s
                """,
                (attempts, stored_id),
            )

            if intent.dataset_request_id is None:
                return _mark_pending(cursor, stored_id, attempts, "dataset request reference is delayed")

            cursor.execute(
                """
                SELECT dr.dataset_request_id::text, dp.dataset_product_id::text,
                       dp.product_key, dr.status
                FROM dataset_requests dr
                JOIN dataset_products dp ON dp.dataset_product_id = dr.dataset_product_id
                WHERE dr.dataset_request_id::text = %s
                FOR UPDATE
                """,
                (intent.dataset_request_id,),
            )
            request = cursor.fetchone()
            if request is None:
                return _mark_pending(cursor, stored_id, attempts, "dataset request is not available yet")
            request_id, product_id, product_key, request_status = request
            if product_key != intent.product_id:
                return _mark_failed(
                    cursor,
                    stored_id,
                    attempts,
                    f"payment product {intent.product_id} does not match dataset product {product_key}",
                )
            if request_status == "revoked":
                return _mark_failed(cursor, stored_id, attempts, "dataset request is revoked")

            cursor.execute(
                """
                SELECT entitlement_id::text, status, provider_event_id
                FROM entitlements
                WHERE dataset_request_id = %s AND organization_id::text = %s
                FOR UPDATE
                """,
                (request_id, intent.purchaser_id),
            )
            entitlement = cursor.fetchone()
            if entitlement is not None:
                entitlement_id, entitlement_status, entitlement_provider_id = entitlement
                if entitlement_provider_id != intent.provider_event_id:
                    return _mark_failed(
                        cursor,
                        stored_id,
                        attempts,
                        "dataset request already has a different payment entitlement",
                    )
                if entitlement_status == "revoked":
                    return _mark_failed(cursor, stored_id, attempts, "entitlement is revoked")
            else:
                entitlement_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-entitlement:{intent.provider_event_id}"))
                cursor.execute(
                    """
                    INSERT INTO entitlements
                        (entitlement_id, organization_id, dataset_request_id,
                         payment_event_id, provider_event_id, status, granted_at)
                    VALUES (%s, %s, %s, %s, %s, 'active', %s)
                    ON CONFLICT (provider_event_id) DO NOTHING
                    """,
                    (
                        entitlement_id,
                        intent.purchaser_id,
                        request_id,
                        stored_id,
                        intent.provider_event_id,
                        now,
                    ),
                )
                cursor.execute(
                    """
                    SELECT entitlement_id::text, status
                    FROM entitlements
                    WHERE provider_event_id = %s
                    FOR UPDATE
                    """,
                    (intent.provider_event_id,),
                )
                entitlement_id, entitlement_status = cursor.fetchone()
                if entitlement_status == "revoked":
                    return _mark_failed(cursor, stored_id, attempts, "entitlement is revoked")

            cursor.execute(
                """
                INSERT INTO dataset_projections
                    (dataset_projection_id, dataset_product_id, dataset_request_id, entitlement_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset_request_id) DO NOTHING
                """,
                (
                    str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-projection:{request_id}")),
                    product_id,
                    request_id,
                    entitlement_id,
                ),
            )
            cursor.execute(
                """
                SELECT dataset_projection_id::text
                FROM dataset_projections
                WHERE dataset_request_id = %s
                """,
                (request_id,),
            )
            projection_id = cursor.fetchone()[0]
            cursor.execute(
                """
                UPDATE dataset_requests
                SET status = CASE WHEN status = 'purchased' THEN 'fast_lane_processing' ELSE status END,
                    updated_at = now()
                WHERE dataset_request_id = %s
                """,
                (request_id,),
            )
            cursor.execute(
                """
                UPDATE payment_events
                SET fulfillment_status = 'fulfilled', fulfilled_at = now(),
                    last_fulfillment_error = NULL
                WHERE payment_event_id = %s
                """,
                (stored_id,),
            )
            return {
                "status": "fulfilled",
                "payment_event_id": stored_id,
                "entitlement_id": entitlement_id,
                "dataset_request_id": request_id,
                "dataset_projection_id": projection_id,
                "fulfillment_attempts": attempts,
            }


def reconcile_pending_payments(connection: Any, limit: int = 50) -> list[dict[str, Any]]:
    """Retry pending verified checkout events in recorded order."""

    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload
                FROM payment_events
                WHERE verified = true AND fulfillment_status = 'pending'
                ORDER BY recorded_at, payment_event_id
                LIMIT %s
                """,
                (limit,),
            )
            events = [dict(row[0]) for row in cursor.fetchall()]
    return [reconcile_payment_event(connection, event) for event in events]


def _mark_pending(cursor: Any, payment_event_id: str, attempts: int, reason: str) -> dict[str, Any]:
    cursor.execute(
        """
        UPDATE payment_events
        SET fulfillment_status = 'pending', last_fulfillment_error = %s
        WHERE payment_event_id = %s
        """,
        (reason, payment_event_id),
    )
    return {
        "status": "pending",
        "payment_event_id": payment_event_id,
        "fulfillment_attempts": attempts,
        "reason": reason,
    }


def _mark_failed(cursor: Any, payment_event_id: str, attempts: int, reason: str) -> dict[str, Any]:
    cursor.execute(
        """
        UPDATE payment_events
        SET fulfillment_status = 'failed', last_fulfillment_error = %s
        WHERE payment_event_id = %s
        """,
        (reason, payment_event_id),
    )
    return {
        "status": "failed",
        "payment_event_id": payment_event_id,
        "fulfillment_attempts": attempts,
        "reason": reason,
    }
