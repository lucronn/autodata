"""Wait for the local database and establish the migration-runner boundary."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path


def parse_address(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host or not port.isdigit():
        raise ValueError("database address must use host:port")
    return host, int(port)


def wait_for_database(address: str, timeout_seconds: int) -> None:
    host, port = parse_address(address)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"database did not become reachable at {address}")


def migration_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))


def psql_command() -> list[str]:
    user = os.getenv("AUTODATA_POSTGRES_USER", "autodata")
    database = os.getenv("AUTODATA_POSTGRES_DB", "autodata")
    if shutil.which("psql"):
        return ["psql", "-U", user, "-d", database]
    compose_file = os.getenv("AUTODATA_COMPOSE_FILE", "infra/compose/compose.yaml")
    return [
        "docker",
        "compose",
        "-f",
        compose_file,
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        user,
        "-d",
        database,
    ]


def apply_migrations(root: Path) -> list[str]:
    files = migration_files(root / "db/migrations")
    if not files:
        raise FileNotFoundError("no numbered migrations found")
    command = psql_command()
    completed: list[str] = []
    for migration in files:
        in_container = command[0] == "docker"
        migration_path = "/workspace/db/migrations/" + migration.name if in_container else str(migration)
        psql_args = [*command, "--set", "ON_ERROR_STOP=1", "--file", migration_path]
        input_sql = None
        if in_container:
            psql_args[-1] = "-"
            input_sql = migration.read_text()
        result = subprocess.run(
            psql_args,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            input=input_sql,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        completed.append(migration.name)
    return completed


def main() -> None:
    root = Path(__file__).parents[2]
    address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    timeout_seconds = int(os.getenv("AUTODATA_MIGRATION_WAIT_SECONDS", "60"))
    wait_for_database(address, timeout_seconds)
    completed = apply_migrations(root)
    print(f"applied migrations: {', '.join(completed)}")


if __name__ == "__main__":
    main()
