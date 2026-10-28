"""Inspect a NATS JetStream stream without mutating it."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))


def resolve_nats_url(url: str | None = None) -> str:
    if url:
        raw = url.strip()
        if "://" not in raw:
            return f"nats://{raw}"
        return raw
    configured = os.getenv("AUTODATA_NATS_URL")
    if configured:
        return configured
    try:
        with socket.create_connection(("127.0.0.1", 4222), timeout=0.2):
            return "nats://127.0.0.1:4222"
    except OSError:
        pass
    try:
        socket.getaddrinfo("nats", 4222)
        return "nats://nats:4222"
    except OSError:
        pass
    return "nats://127.0.0.1:4222"


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def normalize_stream_info(info: Any) -> dict[str, Any]:
    """Reduce SDK-specific stream objects to safe, stable health fields."""

    config = _field(info, "config", {})
    state = _field(info, "state", {})
    return {
        "name": str(_field(config, "name", "")),
        "subjects": [str(subject) for subject in (_field(config, "subjects", []) or [])],
        "retention": str(_field(config, "retention", "")),
        "messages": int(_field(state, "messages", 0) or 0),
        "bytes": int(_field(state, "bytes", 0) or 0),
        "first_seq": int(_field(state, "first_seq", 0) or 0),
        "last_seq": int(_field(state, "last_seq", 0) or 0),
    }


async def inspect_stream(url: str, stream: str) -> dict[str, Any]:
    try:
        import nats
    except ImportError:
        return {
            "name": stream,
            "status": "skipped (nats-py not installed)",
        }

    async def _silent_nats_error(error: Exception) -> None:
        pass

    try:
        connection = await nats.connect(
            url,
            connect_timeout=1,
            max_reconnect_attempts=1,
            allow_reconnect=False,
            error_cb=_silent_nats_error,
        )
    except Exception as error:
        return {
            "name": stream,
            "status": f"skipped (broker unreachable: {error})",
        }
    try:
        info = await connection.jetstream().stream_info(stream)
        return {"status": "ready", **normalize_stream_info(info)}
    finally:
        await connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        "--nats-url",
        "--address",
        "--nats-address",
        dest="url",
        default=None,
    )
    parser.add_argument("--stream", default=os.getenv("AUTODATA_NATS_STREAM", "AUTODATA"))
    args = parser.parse_args(argv)
    url = resolve_nats_url(args.url)
    result = asyncio.run(inspect_stream(url, args.stream))
    if result["name"] != args.stream:
        raise SystemExit(f"NATS stream name mismatch: expected {args.stream}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
