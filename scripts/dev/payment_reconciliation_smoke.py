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
)


REQUEST_ID = "91000000-0000-0000-0000-000000000001"
ORGANIZATION_ID = "91000000-0000-0000-0000-000000000002"
CORRELATION_ID = "91000000-0000-0000-0000-000000000003"
IDEMPOTENCY_KEY = "payment-reconciliation-smoke-001"


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
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pe.fulfillment_status, pe.fulfillment_attempts,
                       dr.status, count(DISTINCT e.entitlement_id),
                       count(DISTINCT dp.dataset_projection_id)
                FROM payment_events pe
                JOIN dataset_requests dr ON dr.dataset_request_id::text = %s
                LEFT JOIN entitlements e ON e.dataset_request_id = dr.dataset_request_id
                LEFT JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
                WHERE pe.provider_event_id = %s
                GROUP BY pe.fulfillment_status, pe.fulfillment_attempts, dr.status
                """,
                (REQUEST_ID, provider_event_id),
            )
            status = cursor.fetchone()
        cleanup(connection, provider_event_id)

    if pending["status"] != "pending":
        raise SystemExit(f"delayed payment was not held pending: {pending}")
    if fulfilled["status"] != "fulfilled" or replay["status"] != "fulfilled":
        raise SystemExit(f"payment reconciliation did not fulfill/replay: {fulfilled}/{replay}")
    if status != ("fulfilled", 3, "fast_lane_processing", 1, 1):
        raise SystemExit(f"unexpected durable reconciliation state: {status}")
    print(json.dumps({"pending": pending, "fulfilled": fulfilled, "replay": replay, "durable_state": status}))


if __name__ == "__main__":
    main()
