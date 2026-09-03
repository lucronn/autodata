import sys
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_dispatch import DeepRequest  # noqa: E402
from autodata_enrichment.search_processor import (  # noqa: E402
    build_search_index,
    process_search_request,
)


class SearchProcessorTests(unittest.TestCase):
    def test_builds_deterministic_index_from_approved_source_evidence(self):
        content, evidence = build_search_index(
            "search",
            "snapshot-1",
            [
                {
                    "evidence_id": "evidence-b",
                    "locator": "page:2",
                    "artifact_key": "sources/b.pdf",
                    "extracted_text": "brake specification",
                    "confidence": 0.91,
                    "reviewer_state": "approved",
                },
                {
                    "evidence_id": "evidence-a",
                    "locator": "page:1",
                    "artifact_key": "sources/a.pdf",
                    "extracted_text": "vehicle identity",
                    "confidence": 1.0,
                    "reviewer_state": "approved",
                },
            ],
        )

        self.assertEqual(content["index"], "approved-source-evidence")
        self.assertEqual(content["source_snapshot_id"], "snapshot-1")
        self.assertEqual(
            [record["evidence_id"] for record in content["records"]],
            ["evidence-a", "evidence-b"],
        )
        self.assertEqual(
            [record["locator"] for record in evidence], ["page:1", "page:2"]
        )
        self.assertEqual(evidence[0]["reviewer_state"], "approved")

    def test_rejects_unapproved_source_evidence(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            build_search_index(
                "search",
                "snapshot-1",
                [
                    {
                        "evidence_id": "evidence-pending",
                        "locator": "page:1",
                        "artifact_key": "sources/a.pdf",
                        "extracted_text": "unreviewed content",
                        "confidence": 0.5,
                        "reviewer_state": "pending",
                    }
                ],
            )

    def test_processes_only_evidence_for_the_requested_projection_snapshot(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, query, params):
                self.query = query
                self.params = params

            def fetchall(self):
                return [
                    (
                        "evidence-a",
                        "page:1",
                        "sources/a.pdf",
                        "vehicle identity",
                        1.0,
                        "approved",
                    )
                ]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                return self.cursor_instance

        connection = Connection()
        request = DeepRequest(
            event_id="event-1",
            request_id="request-1",
            projection_id="projection-1",
            correlation_id="correlation-1",
            idempotency_key="deep-1",
            section_name="search",
            source_snapshot_id="snapshot-1",
            processing_version="deep-v1",
        )

        with patch.dict(sys.modules, {"psycopg": type("Psycopg", (), {"connect": lambda **_kwargs: connection})}):
            with patch(
                "autodata_enrichment.search_processor._connection_kwargs",
                return_value={},
            ):
                with patch(
                    "autodata_enrichment.search_processor.publish_deep_section",
                    return_value={"status": "published"},
                ) as publish:
                    result = process_search_request(request)

        self.assertEqual(result, {"status": "published"})
        publish.assert_called_once()
        job = publish.call_args.args[0]
        self.assertEqual(job.section_name, "search")
        self.assertEqual(job.content["records"][0]["evidence_id"], "evidence-a")
        self.assertEqual(connection.cursor_instance.params, ("projection-1", "snapshot-1"))
        self.assertIn("reviewer_state = 'approved'", connection.cursor_instance.query)


if __name__ == "__main__":
    unittest.main()
