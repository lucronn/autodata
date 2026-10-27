"""Replay one dead-lettered ingestion job or publication outbox event."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))


def replay_target(event_id: str | None, job_id: str | None) -> tuple[str, str]:
    event_id = (event_id or "").strip()
    job_id = (job_id or "").strip()
    if bool(event_id) == bool(job_id):
        raise ValueError("provide exactly one of --event-id or --job-id")
    return ("event", event_id) if event_id else ("job", job_id)


def resolve_database_address(address: str | None = None) -> str:
    if address:
        return address
    configured = os.getenv("AUTODATA_DB_ADDRESS")
    if configured:
        return configured
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.2):
            return "127.0.0.1:5432"
    except OSError:
        pass
    return "postgres:5432"


def _db_connection(address: str | None = None) -> Any:
    import psycopg

    host, port_text = resolve_database_address(address).rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
    )


def replay_dead_letter(connection: Any, kind: str, identifier: str) -> dict[str, Any]:
    with connection.transaction():
        with connection.cursor() as cursor:
            if kind == "event":
                cursor.execute(
                    """
                    UPDATE publication_events
                    SET delivery_status = 'pending',
                        delivery_attempts = 0,
                        last_delivery_error = jsonb_build_object(
                            'replayed_at', now(),
                            'prior_delivery_attempts', delivery_attempts,
                            'prior_error', last_delivery_error
                        )
                    WHERE publication_event_id::text = %s
                      AND delivery_status = 'dead_letter'
                    RETURNING publication_event_id::text, idempotency_key
                    """,
                    (identifier,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("publication event was not found in dead_letter state")
                return {"kind": kind, "id": row[0], "idempotency_key": row[1], "status": "pending"}

            if kind == "job":
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = 'pending',
                        attempt_count = 0,
                        last_error = jsonb_build_object(
                            'replayed_at', now(),
                            'prior_attempt_count', attempt_count,
                            'prior_error', last_error
                        ),
                        updated_at = now()
                    WHERE ingestion_job_id::text = %s
                      AND status = 'dead_letter'
                    RETURNING ingestion_job_id::text, idempotency_key
                    """,
                    (identifier,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("ingestion job was not found in dead_letter state")
                return {"kind": kind, "id": row[0], "idempotency_key": row[1], "status": "pending"}

            raise ValueError(f"unsupported replay target: {kind}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--address",
        "--database-url",
        dest="address",
        default=None,
        help="PostgreSQL host:port address override",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--event-id")
    group.add_argument("--job-id")
    args = parser.parse_args(argv)
    kind, identifier = replay_target(args.event_id, args.job_id)
    with _db_connection(args.address) as connection:
        print(json.dumps(replay_dead_letter(connection, kind, identifier), sort_keys=True))


if __name__ == "__main__":
    main()
