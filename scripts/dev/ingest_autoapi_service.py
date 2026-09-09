#!/usr/bin/env python3
"""Traverse a running AutoAPI connector and ingest its complete catalog."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.autoapi_batch import execute_autoapi_batch  # noqa: E402
from autodata_ingestion.autoapi_connector import AutoAPIConnector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("AUTODATA_AUTOAPI_BASE_URL", "http://127.0.0.1:3000"),
    )
    parser.add_argument(
        "--content-source",
        default=os.getenv("AUTODATA_AUTOAPI_CONTENT_SOURCE", "GeneralMotors"),
    )
    parser.add_argument(
        "--source-version",
        default=os.getenv("AUTODATA_AUTOAPI_SOURCE_VERSION", "autoapi-http-v1"),
    )
    parser.add_argument("--region", default=os.getenv("AUTODATA_SOURCE_REGION", "US"))
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--vehicle-concurrency",
        type=int,
        default=int(os.getenv("AUTODATA_AUTOAPI_VEHICLE_CONCURRENCY", "4")),
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=int(os.getenv("AUTODATA_AUTOAPI_RETRY_ATTEMPTS", "3")),
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=float(os.getenv("AUTODATA_AUTOAPI_RETRY_BACKOFF_SECONDS", "0.25")),
    )
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    connector = AutoAPIConnector(
        args.base_url,
        content_source=args.content_source,
        default_region=args.region,
        source_version=args.source_version,
        timeout_seconds=args.timeout_seconds,
        vehicle_max_concurrency=args.vehicle_concurrency,
        retry_attempts=args.retry_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    catalog = connector.fetch_catalog()
    plan = catalog.to_batches()
    output = execute_autoapi_batch(
        plan,
        source_version=args.source_version,
        persist=args.persist,
        adapter_name=connector.name,
        selector_rows=catalog.selection_rows,
        selector_source_uri=f"{args.base_url.rstrip('/')}/v1/api/years",
    )
    output["catalog"] = {
        "years": list(catalog.years),
        "year_count": len(catalog.years),
        "vehicle_count": len(catalog.vehicles),
        "selector_row_count": len(catalog.selection_rows),
        "traversal_error_count": len(catalog.errors),
        "traversal_errors": [dict(error) for error in catalog.errors],
        "article_list_count": sum(len(vehicle.article_ids) for vehicle in catalog.vehicles),
    }
    if catalog.errors:
        output["status"] = "failed"
    elif not catalog.vehicles:
        output["status"] = "failed"
        output["catalog"]["empty_catalog"] = True
    print(json.dumps(output, sort_keys=True))
    if (
        output["status"] == "failed"
        or output["catalog"]["traversal_error_count"]
        or output["catalog"].get("empty_catalog", False)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
