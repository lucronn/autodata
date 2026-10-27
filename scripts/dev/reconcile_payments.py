"""Continuously reconcile verified payment events whose fulfillment is pending."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.payment_reconciliation import reconcile_pending_payments


import socket


def resolve_database_address(address: str | None = None) -> str:
    if address:
        return address
    configured = os.getenv("AUTODATA_DB_ADDRESS")
    if configured:
        return configured
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.2):
            return "127.0.0.1:5432"
    except OSError:
        pass
    return "postgres:5432"


def db_connection():
    import psycopg

    host, port_text = resolve_database_address().rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
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
