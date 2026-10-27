"""Ensure configured S3-compatible buckets exist and use versioning."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

import socket

from autodata_ingestion.object_storage import ensure_versioned_bucket


def resolve_s3_endpoint(endpoint: str | None = None) -> str:
    if endpoint:
        return endpoint
    configured = os.getenv("AUTODATA_S3_ENDPOINT") or os.getenv("AUTODATA_S3_ADDRESS")
    if configured:
        return configured
    try:
        with socket.create_connection(("127.0.0.1", 9000), timeout=0.2):
            return "127.0.0.1:9000"
    except OSError:
        pass
    return "minio:9000"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--bucket", action="append", dest="buckets")
    args = parser.parse_args()
    buckets = args.buckets or [
        bucket.strip()
        for bucket in os.getenv("AUTODATA_STORAGE_BUCKETS", os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")).split(",")
        if bucket.strip()
    ]
    if not buckets:
        raise SystemExit("at least one object-storage bucket is required")

    from minio import Minio

    endpoint = resolve_s3_endpoint(args.endpoint)
    client = Minio(
        endpoint,
        access_key=os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin"),
        secret_key=os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password"),
        secure=False,
    )
    result = [ensure_versioned_bucket(client, bucket) for bucket in buckets]
    print(json.dumps({"status": "ready", "buckets": result}, sort_keys=True))


if __name__ == "__main__":
    main()
