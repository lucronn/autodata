#!/usr/bin/env python3
"""Ingest one AutoAPI source bundle per vehicle from a local source root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.autoapi_batch import (  # noqa: E402
    build_autoapi_batch_plan,
    collect_autoapi_selection_rows,
    execute_autoapi_batch,
    load_selector_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--selector-json", type=Path)
    parser.add_argument("--region", default="US")
    parser.add_argument("--source-version", default="autoapi-local-v1")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    selector_rows = load_selector_rows(args.selector_json) if args.selector_json else None
    if selector_rows is None:
        selector_rows = collect_autoapi_selection_rows(
            args.source_root,
            default_region=args.region,
            source_version=args.source_version,
        )
    plan = build_autoapi_batch_plan(
        args.source_root,
        selector_rows=selector_rows,
        default_region=args.region,
        source_version=args.source_version,
    )
    output = execute_autoapi_batch(
        plan,
        source_version=args.source_version,
        persist=args.persist,
        selector_rows=selector_rows,
    )
    output["plan"] = [
        {
            "vehicle_key": batch.vehicle_key,
            "source_directory": str(batch.source_directory) if batch.source_directory is not None else None,
            "configuration_count": len(batch.configurations),
        }
        for batch in plan
    ]
    print(json.dumps(output, sort_keys=True))
    if output["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
