"""Publish one deterministic deep-lane section against the local Compose database."""

from __future__ import annotations

import json
import os
import sys

from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/enrichment-python/src"))

from autodata_enrichment.publisher import (  # noqa: E402
    DeepSectionJob,
    publish_deep_section,
    schedule_deep_sections,
)


def main() -> None:
    projection_id = os.environ.get("AUTODATA_DEEP_PROJECTION_ID")
    if not projection_id:
        raise SystemExit("AUTODATA_DEEP_PROJECTION_ID is required")
    sections = tuple(
        item.strip()
        for item in os.getenv("AUTODATA_DEEP_SCHEDULE_SECTIONS", "").split(",")
        if item.strip()
    )
    if sections:
        print(json.dumps(schedule_deep_sections(projection_id, sections), sort_keys=True))
        return
    evidence = tuple(json.loads(os.getenv("AUTODATA_DEEP_EVIDENCE", "[]")))
    result = publish_deep_section(
        DeepSectionJob(
            projection_id=projection_id,
            section_name=os.getenv("AUTODATA_DEEP_SECTION", "diagnostics"),
            content=json.loads(os.getenv("AUTODATA_DEEP_CONTENT", '{"fixture": true}')),
            evidence=evidence,
            processing_version=os.getenv("AUTODATA_DEEP_PROCESSING_VERSION", "deep-v1"),
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
