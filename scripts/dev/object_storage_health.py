"""Ensure configured S3-compatible buckets exist and use versioning."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.object_storage import ensure_versioned_bucket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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

    client = Minio(
        os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
        access_key=os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin"),
        secret_key=os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password"),
        secure=False,
    )
    result = [ensure_versioned_bucket(client, bucket) for bucket in buckets]
    print(json.dumps({"status": "ready", "buckets": result}, sort_keys=True))


if __name__ == "__main__":
    main()
