import dataclasses
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.fast_lane_persistence import (  # noqa: E402
    FastLanePersistenceError,
    FastLanePublication,
    publish_fast_lane_revision,
)
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


class RecordingCursor:
    """Small SQL-boundary fake; these tests assert decisions, not SQL execution."""

    def __init__(self, request_row, job_row=None, revision_id="revision-1"):
        self.request_row = request_row
        self.job_row = job_row
        self.revision_id = revision_id
        self.last_query = ""
        self.statements = []

    def execute(self, query, params=None):
        self.last_query = query
        self.statements.append((query, params))

    def fetchone(self):
        if "FROM dataset_requests" in self.last_query:
            return self.request_row
        if "FROM ingestion_jobs" in self.last_query:
            return self.job_row
        if "FROM dataset_revisions" in self.last_query:
            return (self.revision_id,)
        raise AssertionError(f"unexpected fetchone query: {self.last_query}")


def source_bundle():
    resource = SourceResource.from_bytes(
        "provider://vehicle/name",
        "source-v1",
        b'{"body":"2019 Cadillac Escalade ESV - 2WD"}',
        "application/json",
    )
    artifact = adapt_source_resource(resource)
    return normalize_source_bundle([artifact], "US"), [artifact]


def publication():
    return FastLanePublication(
        request_id="request-1",
        projection_id="projection-1",
        correlation_id="correlation-1",
        idempotency_key="fast-request-1",
        processing_version="fast-v1",
    )


def request_row(minimum_sections=("vehicle_identity", "source_metadata"), status="purchased"):
    return (
        status,
        "cadillac-escalade-esv-2019-us",
        "US",
        "projection-1",
        "active",
        list(minimum_sections),
    )


class FastLanePersistenceTests(unittest.TestCase):
    def test_approved_bundle_publishes_revision_and_all_available_sections(self):
        bundle, artifacts = source_bundle()
        approved_evidence = tuple(
            {**evidence, "reviewer_state": "approved"} for evidence in bundle.evidence
        )
        bundle = dataclasses.replace(bundle, evidence=approved_evidence)
        cursor = RecordingCursor(request_row())

        result = publish_fast_lane_revision(
            cursor,
            bundle,
            artifacts,
            {artifacts[0].content_sha256: "snapshot-1"},
            "vehicle-1",
            "snapshot-1",
            publication(),
            datetime(2026, 9, 3, tzinfo=UTC),
            lambda value: value,
        )

        self.assertEqual(result["status"], "viewable")
        self.assertTrue(result["published"])
        self.assertIn("revision-1", result["revision_id"])
        section_names = [
            params[1]
            for query, params in cursor.statements
            if "INSERT INTO dataset_section_status" in query
        ]
        self.assertEqual(section_names, ["source_metadata", "vehicle_identity"])
        self.assertTrue(any("INSERT INTO dataset_revisions" in query for query, _ in cursor.statements))
        self.assertTrue(any("INSERT INTO publication_events" in query for query, _ in cursor.statements))

    def test_pending_evidence_is_stored_as_review_without_viewable_publication(self):
        bundle, artifacts = source_bundle()
        cursor = RecordingCursor(request_row())

        result = publish_fast_lane_revision(
            cursor,
            bundle,
            artifacts,
            {artifacts[0].content_sha256: "snapshot-1"},
            "vehicle-1",
            "snapshot-1",
            publication(),
            datetime(2026, 9, 3, tzinfo=UTC),
            lambda value: value,
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["published"])
        self.assertEqual(len(result["review_evidence"]), 1)
        self.assertFalse(any("INSERT INTO dataset_revisions" in query for query, _ in cursor.statements))
        self.assertFalse(any("INSERT INTO publication_events" in query for query, _ in cursor.statements))

    def test_request_vehicle_mismatch_is_rejected_before_job_claim(self):
        bundle, artifacts = source_bundle()
        cursor = RecordingCursor(
            (
                "purchased",
                "different-vehicle",
                "US",
                "projection-1",
                "active",
                ["vehicle_identity"],
            )
        )

        with self.assertRaisesRegex(FastLanePersistenceError, "does not match"):
            publish_fast_lane_revision(
                cursor,
                bundle,
                artifacts,
                {artifacts[0].content_sha256: "snapshot-1"},
                "vehicle-1",
                "snapshot-1",
                publication(),
                datetime(2026, 9, 3, tzinfo=UTC),
                lambda value: value,
            )
        self.assertFalse(any("INSERT INTO ingestion_jobs" in query for query, _ in cursor.statements))

    def test_completed_idempotent_job_returns_original_result(self):
        cursor = RecordingCursor(
            request_row(),
            ("job-1", "completed", {"result": {"status": "viewable", "revision_id": "revision-1"}}),
        )
        bundle, artifacts = source_bundle()

        result = publish_fast_lane_revision(
            cursor,
            bundle,
            artifacts,
            {artifacts[0].content_sha256: "snapshot-1"},
            "vehicle-1",
            "snapshot-1",
            publication(),
            datetime(2026, 9, 3, tzinfo=UTC),
            lambda value: value,
        )

        self.assertEqual(result, {"status": "viewable", "revision_id": "revision-1"})
        self.assertFalse(any("INSERT INTO dataset_revisions" in query for query, _ in cursor.statements))


if __name__ == "__main__":
    unittest.main()
