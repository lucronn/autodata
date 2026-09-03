"""Inspect a NATS JetStream stream without mutating it."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Mapping
from typing import Any


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
    import nats

    connection = await nats.connect(url)
    try:
        info = await connection.jetstream().stream_info(stream)
        return normalize_stream_info(info)
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("AUTODATA_NATS_URL", "nats://nats:4222"))
    parser.add_argument("--stream", default=os.getenv("AUTODATA_NATS_STREAM", "AUTODATA"))
    args = parser.parse_args()
    result = asyncio.run(inspect_stream(args.url, args.stream))
    if result["name"] != args.stream:
        raise SystemExit(f"NATS stream name mismatch: expected {args.stream}")
    print(json.dumps({"status": "ready", **result}, sort_keys=True))


if __name__ == "__main__":
    main()
