"""Deterministic process boundary for the deep-lane worker."""

from __future__ import annotations

import json
import os
import time

from .publisher import DeepSectionJob, publish_deep_section


def run_once() -> dict[str, str]:
    """Run one explicitly configured deep job or return the worker heartbeat."""

    if os.getenv("AUTODATA_VIEWABLE_CONSUMER_ENABLED") == "1":
        return run_viewable_once()
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


def run_viewable_once() -> dict[str, str]:
    """Consume one viewable event and fan it out to independent deep jobs."""

    import asyncio

    from .fanout import deep_sections_from_event
    from .publisher import schedule_deep_sections
    from .viewable_consumer import consume_once

    def handle(envelope):
        sections = deep_sections_from_event(envelope)
        result = schedule_deep_sections(
            str(envelope["projection_id"]),
            sections,
            os.getenv("AUTODATA_DEEP_PROCESSING_VERSION", "deep-v1"),
        )
        return {"worker": "enrichment", "lane": "deep", **result}

    result = asyncio.run(
        consume_once(
            handle,
            fetch_timeout=float(os.getenv("AUTODATA_VIEWABLE_CONSUMER_FETCH_TIMEOUT_SECONDS", "1")),
            max_deliveries=int(os.getenv("AUTODATA_VIEWABLE_CONSUMER_MAX_DELIVERIES", "3")),
        )
    )
    return {"worker": "enrichment", "lane": "deep", **{key: str(value) for key, value in result.items()}}


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
