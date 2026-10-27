"""Probe the local API health and readiness contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))


def default_base_url() -> str:
    url = os.getenv("AUTODATA_API_BASE_URL") or os.getenv("AUTODATA_API_URL")
    if url:
        return url.rstrip("/")
    addr = os.getenv("AUTODATA_API_ADDR")
    if addr:
        port = addr.strip().rsplit(":", 1)[-1]
        if port:
            return f"http://127.0.0.1:{port}"
    return "http://127.0.0.1:8080"


def get_json(url: str) -> tuple[int, dict[str, object]]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, json.load(response)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args(argv)
    base_url = args.base_url or default_base_url()
    try:
        health_status, health = get_json(f"{base_url}/healthz")
    except Exception:
        if args.base_url is None and base_url == "http://127.0.0.1:8080":
            try:
                candidate = "http://127.0.0.1:18080"
                health_status, health = get_json(f"{candidate}/healthz")
                base_url = candidate
            except Exception:
                raise
        else:
            raise
    readiness_status, readiness = get_json(f"{base_url}/readyz")
    if health_status != 200 or health.get("status") != "ok":
        raise SystemExit(f"health probe failed: {health_status} {health}")
    if readiness_status != 200:
        raise SystemExit(f"readiness probe failed: {readiness_status} {readiness}")
    print(json.dumps({"health": health, "readiness": readiness}, sort_keys=True))


if __name__ == "__main__":
    main()
