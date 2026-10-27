"""Continuously reconcile verified payment events whose fulfillment is pending."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

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


def db_connection(address: str | None = None):
    import psycopg

    host, port_text = resolve_database_address(address).rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
    )


def run_once(batch_size: int | None = None, address: str | None = None) -> list[dict[str, object]]:
    size = batch_size if batch_size is not None else int(os.getenv("AUTODATA_PAYMENT_RECONCILE_BATCH_SIZE", "50"))
    with db_connection(address) as connection:
        return reconcile_pending_payments(
            connection,
            size,
        )


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--address",
        "--database-url",
        default=None,
        help="PostgreSQL host:port address override",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=(os.getenv("AUTODATA_PAYMENT_RECONCILE_ONCE") == "1"),
        help="Run reconciliation once and exit",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("AUTODATA_PAYMENT_RECONCILE_BATCH_SIZE", "50")),
        help="Batch size of pending payments to reconcile",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("AUTODATA_PAYMENT_RECONCILE_POLL_SECONDS", "15")),
        help="Polling interval in seconds",
    )
    args = parser.parse_args(argv)

    if args.once:
        print(run_once(batch_size=args.batch_size, address=args.address), flush=True)
        return
    while True:
        results = run_once(batch_size=args.batch_size, address=args.address)
        if results:
            print(results, flush=True)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
