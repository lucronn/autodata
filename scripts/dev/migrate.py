"""Wait for the local database and establish the migration-runner boundary."""

from __future__ import annotations

import os
import socket
import time


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


def main() -> None:
    address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    timeout_seconds = int(os.getenv("AUTODATA_MIGRATION_WAIT_SECONDS", "60"))
    wait_for_database(address, timeout_seconds)
    print("migration runner reached the database; schema migrations are supplied by the schema slice")


if __name__ == "__main__":
    main()
