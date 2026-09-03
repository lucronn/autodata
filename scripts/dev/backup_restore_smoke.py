"""Verify a PostgreSQL custom-format backup by restoring it into an isolated DB."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]


def temporary_database_name(process_id: int) -> str:
    """Return a generated identifier safe for the local restore test."""

    if process_id < 0:
        raise ValueError("process ID must be non-negative")
    return f"autodata_restore_check_{process_id}"


def run_compose(
    compose_file: str,
    arguments: list[str],
    input_data: bytes | None = None,
) -> bytes:
    completed = subprocess.run(
        ["docker", "compose", "-f", compose_file, *arguments],
        check=False,
        capture_output=True,
        input=input_data,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Docker Compose command failed: {arguments[0]}")
    return completed.stdout


def main() -> None:
    if shutil.which("docker") is None:
        raise SystemExit("backup/restore verification must run on a host with Docker Compose")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compose-file",
        default=str(ROOT / "infra/compose/compose.yaml"),
    )
    parser.add_argument("--database", default=os.getenv("AUTODATA_POSTGRES_DB", "autodata"))
    parser.add_argument("--user", default=os.getenv("AUTODATA_POSTGRES_USER", "autodata"))
    args = parser.parse_args()

    restore_database = temporary_database_name(os.getpid())
    created = False
    try:
        backup = run_compose(
            args.compose_file,
            ["exec", "-T", "postgres", "pg_dump", "-Fc", "-U", args.user, "-d", args.database],
        )
        if not backup:
            raise RuntimeError("PostgreSQL backup was empty")
        run_compose(
            args.compose_file,
            ["exec", "-T", "postgres", "createdb", "-U", args.user, restore_database],
        )
        created = True
        run_compose(
            args.compose_file,
            [
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "-U",
                args.user,
                "-d",
                restore_database,
            ],
            input_data=backup,
        )
        ledger = run_compose(
            args.compose_file,
            [
                "exec",
                "-T",
                "postgres",
                "psql",
                "-At",
                "-U",
                args.user,
                "-d",
                restore_database,
                "-c",
                "SELECT count(*) FROM schema_migrations",
            ],
        ).decode().strip()
        if not ledger.isdigit() or int(ledger) == 0:
            raise RuntimeError("restored database has no schema migration records")
        print(json.dumps({"status": "verified", "schema_migrations": int(ledger)}))
    finally:
        if created:
            run_compose(
                args.compose_file,
                ["exec", "-T", "postgres", "dropdb", "-U", args.user, restore_database],
            )


if __name__ == "__main__":
    main()
