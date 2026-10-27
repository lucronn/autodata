#!/usr/bin/env python3
"""Traverse a running Banktwo Source Connector and ingest its catalog."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.bankone_batch import (  # noqa: E402
    BankoneBatch,
    execute_bankone_batch,
)
from autodata_ingestion.source_connector_client import (  # noqa: E402
    SourceConnectorClient,
    source_connector_token,
)


def fetch_banktwo_batches(
    connector: SourceConnectorClient,
    *,
    region: str = "US",
    source_version: str = "banktwo-http-v1",
) -> tuple[list[BankoneBatch], list[dict[str, object]], dict[str, object]]:
    """Traverse the Banktwo connector to assemble vehicle batches and selection rows."""
    batches: list[BankoneBatch] = []
    selection_rows: list[dict[str, object]] = []
    years: list[int] = []
    errors: list[dict[str, str]] = []

    try:
        years_page = connector.catalog("years")
        years = sorted({int(item["year"]) for item in years_page.body.get("items", []) if "year" in item})
    except Exception as exc:
        errors.append({"scope": "years", "error": str(exc)})

    for year in years:
        try:
            makes_page = connector.catalog("makes", selector={"year": year})
            makes = sorted({str(item["make"]) for item in makes_page.body.get("items", []) if "make" in item})
        except Exception as exc:
            errors.append({"scope": f"makes:{year}", "error": str(exc)})
            continue

        for make in makes:
            try:
                models_page = connector.catalog("models", selector={"year": year, "make": make})
                models = sorted({str(item["model"]) for item in models_page.body.get("items", []) if "model" in item})
            except Exception as exc:
                errors.append({"scope": f"models:{year}:{make}", "error": str(exc)})
                continue

            for model in models:
                try:
                    configs_page = connector.catalog(
                        "configurations",
                        selector={"year": year, "make": make, "model": model},
                    )
                    items = configs_page.body.get("items", [])
                    vehicle_key = f"{make.lower()}-{model.lower()}-{year}-{region.lower()}"
                    vehicle_obj = {"make": make, "model": model, "year": year, "region": region}
                    configs_list = []
                    for item in items:
                        configs_list.append(dict(item))
                        selection_rows.append({
                            "year": year,
                            "make": make,
                            "model": model,
                            "configuration": item.get("label", item.get("configuration", "")),
                            "region": region,
                            "source_version": source_version,
                            "source_locator": configs_page.source_locator,
                        })

                    batches.append(
                        BankoneBatch(
                            vehicle_key=vehicle_key,
                            vehicle=vehicle_obj,
                            source_directory=None,
                            configurations=tuple(configs_list),
                        )
                    )
                except Exception as exc:
                    errors.append({"scope": f"configs:{year}:{make}:{model}", "error": str(exc)})

    summary = {
        "years": years,
        "year_count": len(years),
        "vehicle_count": len(batches),
        "selector_row_count": len(selection_rows),
        "traversal_error_count": len(errors),
        "traversal_errors": errors,
    }
    return batches, selection_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("BANKTWO_BASE_URL", "https://banktwo.cars.tk"),
    )
    parser.add_argument(
        "--source-version",
        default=os.getenv("AUTODATA_BANKTWO_SOURCE_VERSION", "banktwo-http-v1"),
    )
    parser.add_argument("--region", default=os.getenv("AUTODATA_SOURCE_REGION", "US"))
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    connector = SourceConnectorClient(
        args.base_url,
        token=source_connector_token("banktwo"),
        provider="banktwo",
        timeout_seconds=args.timeout_seconds,
    )
    batches, selection_rows, catalog_summary = fetch_banktwo_batches(
        connector,
        region=args.region,
        source_version=args.source_version,
    )
    output = execute_bankone_batch(
        batches,
        source_version=args.source_version,
        persist=args.persist,
        adapter_name=connector.provider,
        selector_rows=selection_rows,
        selector_source_uri=f"{args.base_url.rstrip('/')}/v1/catalog/years",
    )
    output["catalog"] = catalog_summary
    if catalog_summary["traversal_error_count"]:
        output["status"] = "failed"
    elif not batches:
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
