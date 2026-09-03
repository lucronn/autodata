"""Exercise delayed payment fulfillment and replay-safe reconciliation locally."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_contracts.fakes import FakePaymentProvider  # noqa: E402
from autodata_ingestion.payment_reconciliation import (  # noqa: E402
    reconcile_payment_event,
    reconcile_pending_payments,
    revoke_entitlement,
)


REQUEST_ID = "91000000-0000-0000-0000-000000000004"
ORGANIZATION_ID = "91000000-0000-0000-0000-000000000005"
CORRELATION_ID = "91000000-0000-0000-0000-000000000006"
IDEMPOTENCY_KEY = "payment-reconciliation-smoke-004"


def db_connection():
    import psycopg

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    )


def cleanup(connection, provider_event_id: str) -> None:
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM publication_events WHERE dataset_request_id = %s",
                (REQUEST_ID,),
            )
            cursor.execute(
                """
                DELETE FROM dataset_section_status
                WHERE dataset_projection_id IN (
                    SELECT dataset_projection_id
                    FROM dataset_projections
                    WHERE dataset_request_id = %s
                )
                """,
                (REQUEST_ID,),
            )
            cursor.execute(
                """
                DELETE FROM dataset_revisions
                WHERE dataset_projection_id IN (
                    SELECT dataset_projection_id
                    FROM dataset_projections
                    WHERE dataset_request_id = %s
                )
                """,
                (REQUEST_ID,),
            )
            cursor.execute(
                "DELETE FROM dataset_projections WHERE dataset_request_id = %s",
                (REQUEST_ID,),
            )
            cursor.execute(
                "DELETE FROM entitlements WHERE dataset_request_id = %s",
                (REQUEST_ID,),
            )
            cursor.execute(
                "DELETE FROM dataset_requests WHERE dataset_request_id = %s",
                (REQUEST_ID,),
            )
            cursor.execute(
                "DELETE FROM payment_events WHERE provider_event_id = %s",
                (provider_event_id,),
            )


def main() -> None:
    provider = FakePaymentProvider(os.getenv("AUTODATA_FAKE_PAYMENT_SIGNING_SECRET", "local-fixture-signing-key"))
    session = provider.create_checkout_session(
        "vehicle-core-fixture",
        ORGANIZATION_ID,
        dataset_request_id=REQUEST_ID,
    )
    event = provider.verify_webhook(session["headers"], session["body"])
    provider_event_id = event["provider_event_id"]

    with db_connection() as connection:
        cleanup(connection, provider_event_id)
        pending = reconcile_payment_event(connection, event)
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dataset_requests
                        (dataset_request_id, dataset_product_id, vehicle_key, region,
                         status, lane, correlation_id, idempotency_key, processing_version)
                    SELECT %s, dataset_product_id, 'payment-smoke-vehicle', 'US',
                           'purchased', 'fast', %s, %s, 'payment-smoke-v1'
                    FROM dataset_products
                    WHERE product_key = 'vehicle-core-fixture' AND product_version = 1
                    """,
                    (REQUEST_ID, CORRELATION_ID, IDEMPOTENCY_KEY),
                )
        fulfilled_results = reconcile_pending_payments(connection)
        fulfilled = next(
            result for result in fulfilled_results
            if result.get("payment_event_id") == pending["payment_event_id"]
        )
        replay = reconcile_payment_event(connection, event)
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    -- The ingestion smoke owns the published-revision immutability check.
                    -- This disposable revision stays unpublished so the fixture can remove it after verification.
                    INSERT INTO dataset_revisions
                        (dataset_projection_id, revision_number, availability,
                         source_watermark, schema_version, changelog, content)
                    VALUES (%s, 1, 'viewable', 'payment-smoke-source-v1', 1,
                            '{"kind":"payment-reconciliation-smoke"}'::jsonb,
                            '{"vehicle_key":"payment-smoke-vehicle"}'::jsonb)
                    ON CONFLICT (dataset_projection_id, revision_number) DO NOTHING
                    """,
                    (fulfilled["dataset_projection_id"],),
                )
        revoked = revoke_entitlement(connection, fulfilled["entitlement_id"], "refund")
        revoked_replay = revoke_entitlement(
            connection,
            fulfilled["entitlement_id"],
            "a-different-reason-is-ignored",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pe.fulfillment_status, pe.fulfillment_attempts,
                       dr.status, e.status, count(DISTINCT dvr.dataset_revision_id),
                       count(DISTINCT dp.dataset_projection_id),
                       count(DISTINCT pe2.publication_event_id)
                FROM payment_events pe
                JOIN dataset_requests dr ON dr.dataset_request_id::text = %s
                LEFT JOIN entitlements e ON e.dataset_request_id = dr.dataset_request_id
                LEFT JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
                LEFT JOIN dataset_revisions dvr ON dvr.dataset_projection_id = dp.dataset_projection_id
                LEFT JOIN publication_events pe2
                    ON pe2.dataset_projection_id = dp.dataset_projection_id
                   AND pe2.event_type = 'dataset.revision.revoked'
                WHERE pe.provider_event_id = %s
                GROUP BY pe.fulfillment_status, pe.fulfillment_attempts, dr.status, e.status
                """,
                (REQUEST_ID, provider_event_id),
            )
            status = cursor.fetchone()
        cleanup(connection, provider_event_id)

    if pending["status"] != "pending":
        raise SystemExit(f"delayed payment was not held pending: {pending}")
    if fulfilled["status"] != "fulfilled" or replay["status"] != "fulfilled":
        raise SystemExit(f"payment reconciliation did not fulfill/replay: {fulfilled}/{replay}")
    if (
        revoked["status"] != "revoked"
        or revoked_replay["status"] != "revoked"
        or revoked_replay["publication_event_id"] != revoked["publication_event_id"]
        or revoked_replay["reason"] != "refund"
    ):
        raise SystemExit(f"entitlement revocation was not idempotent: {revoked}/{revoked_replay}")
    if status != ("fulfilled", 3, "revoked", "revoked", 1, 1, 1):
        raise SystemExit(f"unexpected durable reconciliation state: {status}")
    print(
        json.dumps(
            {
                "pending": pending,
                "fulfilled": fulfilled,
                "replay": replay,
                "revoked": revoked,
                "revoked_replay": revoked_replay,
                "durable_state": status,
            }
        )
    )


if __name__ == "__main__":
    main()
