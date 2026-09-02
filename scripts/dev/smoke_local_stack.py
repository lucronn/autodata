"""Probe the local API health and readiness contract."""

from __future__ import annotations

import argparse
import json
import urllib.request


def get_json(url: str) -> tuple[int, dict[str, object]]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    health_status, health = get_json(f"{args.base_url}/healthz")
    readiness_status, readiness = get_json(f"{args.base_url}/readyz")
    if health_status != 200 or health.get("status") != "ok":
        raise SystemExit(f"health probe failed: {health_status} {health}")
    if readiness_status != 200:
        raise SystemExit(f"readiness probe failed: {readiness_status} {readiness}")
    print(json.dumps({"health": health, "readiness": readiness}, sort_keys=True))


if __name__ == "__main__":
    main()
