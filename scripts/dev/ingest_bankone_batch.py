#!/usr/bin/env python3
"""Ingest one Bankone source bundle per vehicle from a local source root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

from autodata_ingestion.bankone_batch import (  # noqa: E402
    BankBatch,
    BankoneBatch,
    build_bank_batch_plan,
    collect_bankone_selection_rows,
    execute_bank_batch,
    load_selector_rows,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--selector-json", type=Path)
    parser.add_argument("--region", default="US")
    parser.add_argument("--source-version", default="autoapi-local-v1")
    parser.add_argument("--limit", type=int, default=None, help="Maximum vehicle batches to ingest")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args(argv)

    selector_rows = load_selector_rows(args.selector_json) if args.selector_json else None
    if selector_rows is None:
        selector_rows = collect_bankone_selection_rows(
            args.source_root,
            default_region=args.region,
            source_version=args.source_version,
        )
    plan = build_bank_batch_plan(
        args.source_root,
        selector_rows=selector_rows,
        default_region=args.region,
        source_version=args.source_version,
    )
    if args.limit is not None and args.limit >= 0:
        plan = plan[: args.limit]
    output = execute_bank_batch(
        plan,
        source_version=args.source_version,
        persist=args.persist,
        selector_rows=selector_rows,
    )
    output["plan"] = [
        {
            "vehicle_key": batch.vehicle_key,
            "source_directory": str(batch.source_directory) if batch.source_directory is not None else None,
            "source_directories": [
                str(directory) for directory in batch.article_source_directories()
            ],
            "configuration_count": len(batch.configurations),
        }
        for batch in plan
    ]
    print(json.dumps(output, sort_keys=True))
    if output["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
