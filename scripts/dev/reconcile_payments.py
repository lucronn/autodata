"""Continuously reconcile verified payment events whose fulfillment is pending."""

from __future__ import annotations

import os
import time

from autodata_ingestion.payment_reconciliation import reconcile_pending_payments


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


def run_once() -> list[dict[str, object]]:
    with db_connection() as connection:
        return reconcile_pending_payments(
            connection,
            int(os.getenv("AUTODATA_PAYMENT_RECONCILE_BATCH_SIZE", "50")),
        )


def main() -> None:
    interval = float(os.getenv("AUTODATA_PAYMENT_RECONCILE_POLL_SECONDS", "15"))
    if os.getenv("AUTODATA_PAYMENT_RECONCILE_ONCE") == "1":
        print(run_once(), flush=True)
        return
    while True:
        results = run_once()
        if results:
            print(results, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
