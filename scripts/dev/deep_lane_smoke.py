"""Publish one deterministic deep-lane section against the local Compose database."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/enrichment-python/src"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

from autodata_enrichment.publisher import (  # noqa: E402
    DeepSectionJob,
    publish_deep_section,
    schedule_deep_sections,
)

DEFAULT_EVIDENCE: list[dict[str, Any]] = [
    {
        "evidence_id": "ev-smoke-001",
        "locator": "doc:section-1",
        "extracted_text": "Diagnostics verification evidence",
        "confidence": 0.99,
        "reviewer_state": "approved",
    }
]


def resolve_database_address(address: str | None = None) -> str:
    if address:
        return address
    configured = os.getenv("AUTODATA_DB_ADDRESS")
    if configured:
        return configured
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.2):
            return "127.0.0.1:5432"
    except OSError:
        pass
    return "postgres:5432"


def resolve_viewable_projection_id(
    projection_id: str | None = None,
    address: str | None = None,
) -> str:
    if projection_id:
        return projection_id
    configured = os.getenv("AUTODATA_DEEP_PROJECTION_ID")
    if configured:
        return configured
    import psycopg

    host, port_text = resolve_database_address(address).rsplit(":", 1)
    try:
        with psycopg.connect(
            host=host,
            port=int(port_text),
            dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
            user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
            password=os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
            connect_timeout=2,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT dp.dataset_projection_id::text
                FROM dataset_projections dp
                JOIN dataset_requests dr ON dr.dataset_request_id = dp.dataset_request_id
                WHERE dr.status IN ('viewable', 'enriching', 'needs_review', 'complete')
                ORDER BY dp.created_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                return str(row[0])
    except Exception:
        pass
    raise ValueError("no viewable dataset projection found in database; run fast-lane fixture first")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--address",
        "--database-url",
        default=None,
        help="PostgreSQL host:port address override",
    )
    parser.add_argument("--projection-id", default=None)
    parser.add_argument("--section", default=os.getenv("AUTODATA_DEEP_SECTION", "diagnostics"))
    parser.add_argument(
        "--schedule-sections",
        default=os.getenv("AUTODATA_DEEP_SCHEDULE_SECTIONS", ""),
    )
    parser.add_argument(
        "--processing-version",
        default=os.getenv("AUTODATA_DEEP_PROCESSING_VERSION", "deep-v1"),
    )
    parser.add_argument("--content", default=None)
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    if args.address:
        os.environ["AUTODATA_DB_ADDRESS"] = args.address
    projection_id = resolve_viewable_projection_id(args.projection_id, address=args.address)
    sections = tuple(
        item.strip()
        for item in args.schedule_sections.split(",")
        if item.strip()
    )
    if sections:
        print(
            json.dumps(
                schedule_deep_sections(
                    projection_id, sections, processing_version=args.processing_version
                ),
                sort_keys=True,
            )
        )
        return

    raw_evidence = args.evidence or os.getenv("AUTODATA_DEEP_EVIDENCE")
    if raw_evidence:
        evidence = tuple(json.loads(raw_evidence))
    else:
        evidence = tuple(DEFAULT_EVIDENCE)

    raw_content = args.content or os.getenv("AUTODATA_DEEP_CONTENT")
    if raw_content:
        content = json.loads(raw_content)
    else:
        content = {"fixture": True, "diagnostics_ok": True}

    result = publish_deep_section(
        DeepSectionJob(
            projection_id=projection_id,
            section_name=args.section,
            content=content,
            evidence=evidence,
            processing_version=args.processing_version,
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
