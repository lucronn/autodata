"""Deterministic process boundary for the deep-lane worker."""

from __future__ import annotations

import json
import os
import time

from .publisher import DeepSectionJob, publish_deep_section


def run_once() -> dict[str, str]:
    """Run one explicitly configured deep job or return the worker heartbeat."""

    projection_id = os.getenv("AUTODATA_DEEP_PROJECTION_ID")
    if not projection_id:
        return {"worker": "enrichment", "lane": "deep", "status": "idle"}
    section_name = os.getenv("AUTODATA_DEEP_SECTION", "diagnostics")
    content = json.loads(os.getenv("AUTODATA_DEEP_CONTENT", '{"fixture": true}'))
    evidence = tuple(json.loads(os.getenv("AUTODATA_DEEP_EVIDENCE", "[]")))
    result = publish_deep_section(
        DeepSectionJob(
            projection_id=projection_id,
            section_name=section_name,
            content=content,
            evidence=evidence,
            processing_version=os.getenv("AUTODATA_DEEP_PROCESSING_VERSION", "deep-v1"),
        )
    )
    return {"worker": "enrichment", "lane": "deep", **{key: str(value) for key, value in result.items()}}

    return {"worker": "enrichment", "lane": "deep", "status": "idle"}


def main() -> None:
    interval = float(os.getenv("AUTODATA_WORKER_HEARTBEAT_SECONDS", "30"))
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        print(json.dumps(run_once(), sort_keys=True))
        return
    while True:
        print(json.dumps(run_once(), sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
