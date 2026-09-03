"""Evidence-preserving source index for the first deep-lane search processor."""

from __future__ import annotations

from typing import Any, Iterable

from .publisher import DeepSectionJob, _connection_kwargs, publish_deep_section


class SearchProcessorError(RuntimeError):
    """The search index cannot be built from the available approved evidence."""


def build_search_index(
    section_name: str,
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Build retrieval content without converting source text into domain facts.

    The input rows are expected to come from approved ``extraction_evidence``
    records. The returned content is an auditable index of those records; the
    deep publisher is responsible for assigning the new revision's evidence
    identifiers and embedding vectors.
    """

    if str(section_name).strip().casefold() != "search":
        raise ValueError("the built-in source index processor only handles search")
    normalized_snapshot_id = str(source_snapshot_id).strip()
    if not normalized_snapshot_id:
        raise ValueError("source snapshot id is required")

    evidence: list[dict[str, Any]] = []
    for row in rows:
        if row.get("reviewer_state") != "approved":
            raise ValueError("search indexing requires approved source evidence")
        required = ("evidence_id", "locator", "artifact_key", "extracted_text", "confidence")
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"source evidence is missing: {', '.join(missing)}")
        evidence.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "locator": str(row["locator"]),
                "artifact_key": str(row["artifact_key"]),
                "extracted_text": str(row["extracted_text"]),
                "confidence": float(row["confidence"]),
                "reviewer_state": "approved",
            }
        )

    evidence.sort(key=lambda item: (item["locator"], item["evidence_id"]))
    content = {
        "index": "approved-source-evidence",
        "source_snapshot_id": normalized_snapshot_id,
        "records": [
            {
                "evidence_id": item["evidence_id"],
                "locator": item["locator"],
                "artifact_key": item["artifact_key"],
                "extracted_text": item["extracted_text"],
                "confidence": item["confidence"],
            }
            for item in evidence
        ],
    }
    return content, tuple(evidence)


def process_search_request(request: Any) -> dict[str, Any]:
    """Publish an evidence-backed search section for one deep request.

    Search is deliberately the first built-in processor because it can provide
    useful retrieval coverage while preserving source text and provenance. It
    does not infer or write canonical vehicle facts.
    """

    rows = load_approved_source_evidence(request)

    try:
        content, evidence = build_search_index(
            request.section_name,
            request.source_snapshot_id,
            rows,
        )
    except ValueError as error:
        raise SearchProcessorError(str(error)) from error
    if not evidence:
        raise SearchProcessorError("no approved source evidence is available for search indexing")
    return publish_deep_section(
        DeepSectionJob(
            projection_id=request.projection_id,
            section_name=request.section_name,
            content=content,
            evidence=evidence,
            processing_version=request.processing_version,
        )
    )


def register_builtin_processors() -> None:
    """Register processors shipped by this worker image."""

    from .deep_dispatch import register_section_processor
    from .diagnostics_processor import process_diagnostics_request
    from .quality_processor import process_quality_request

    register_section_processor("diagnostics", process_diagnostics_request)
    register_section_processor("search", process_search_request)
    register_section_processor("quality", process_quality_request)


def load_approved_source_evidence(request: Any) -> list[dict[str, Any]]:
    """Load evidence scoped to the projection and source snapshot in a request."""

    import psycopg

    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ee.extraction_evidence_id::text, ee.locator,
                       ee.artifact_key, ee.extracted_text, ee.confidence,
                       ee.reviewer_state
                FROM dataset_projections dp
                JOIN dataset_requests dr ON dr.dataset_request_id = dp.dataset_request_id
                JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
                JOIN extraction_evidence ee ON ee.source_snapshot_id = dr.source_snapshot_id
                WHERE dp.dataset_projection_id = %s
                  AND dr.source_snapshot_id = %s
                  AND dr.status <> 'revoked'
                  AND e.status <> 'revoked'
                  AND ee.reviewer_state = 'approved'
                ORDER BY ee.locator, ee.extraction_evidence_id
                """,
                (request.projection_id, request.source_snapshot_id),
            )
            return [
                {
                    "evidence_id": row[0],
                    "locator": row[1],
                    "artifact_key": row[2],
                    "extracted_text": row[3],
                    "confidence": row[4],
                    "reviewer_state": row[5],
                }
                for row in cursor.fetchall()
            ]
