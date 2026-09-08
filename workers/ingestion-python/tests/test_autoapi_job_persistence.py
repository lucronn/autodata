import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.autoapi_batch import AutoAPIBatch  # noqa: E402
from autodata_ingestion.autoapi_job_persistence import (  # noqa: E402
    claim_autoapi_article_fetch_job,
    persist_autoapi_article_fetch_jobs,
    record_autoapi_article_fetch_failure,
)


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class SequencedCursor(RecordingCursor):
    def __init__(self, rows):
        super().__init__()
        self.rows = list(rows)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class RecordingConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True


class AutoAPIJobPersistenceTests(unittest.TestCase):
    def test_persists_pending_and_reviewable_article_fetch_jobs_idempotently(self):
        cursor = RecordingCursor()
        connection = RecordingConnection(cursor)
        batches = [
            AutoAPIBatch(
                vehicle_key="ford-f-150-2020-us",
                vehicle={"year": 2020, "make": "Ford", "model": "F-150", "region": "US"},
                source_directory=None,
                configurations=(),
            ),
            AutoAPIBatch(
                vehicle_key="cadillac-escalade-esv-2019-us",
                vehicle={
                    "year": 2019,
                    "make": "Cadillac",
                    "model": "Escalade ESV",
                    "region": "US",
                },
                source_directory=Path("catalog/cadillac-escalade-esv"),
                configurations=(),
            ),
        ]
        results = [
            {
                "vehicle_key": "ford-f-150-2020-us",
                "status": "pending_source",
                "error": "source bundle has not arrived",
            },
            {
                "vehicle_key": "cadillac-escalade-esv-2019-us",
                "status": "needs_review",
                "articles": 6016,
                "quarantined": 671,
            },
        ]
        selector_persistence = {
            "source_snapshot_id": "selector-snapshot-1",
            "observations": [
                {"vehicle_key": "ford-f-150-2020-us", "vehicle_id": "vehicle-ford"},
                {"vehicle_key": "cadillac-escalade-esv-2019-us", "vehicle_id": "vehicle-cadillac"},
            ],
        }

        fake_json = types.ModuleType("psycopg.types.json")
        fake_json.Jsonb = lambda value: value
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: connection
        with patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        ):
            with patch.dict("os.environ", {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
                result = persist_autoapi_article_fetch_jobs(
                    batches,
                    results,
                    selector_persistence=selector_persistence,
                    source_version="autoapi-selector-v1",
                )

        self.assertEqual(result["status"], "persisted")
        self.assertEqual(result["job_count"], 2)
        self.assertEqual(
            [job["status"] for job in result["jobs"]],
            ["pending", "needs_review"],
        )
        insert_calls = [
            (query, params)
            for query, params in cursor.calls
            if "INSERT INTO autoapi_article_fetch_jobs" in query
        ]
        self.assertEqual(len(insert_calls), 2)
        self.assertEqual(insert_calls[0][1][1], "vehicle-ford")
        self.assertEqual(insert_calls[0][1][6], "autoapi-selector-v1")
        self.assertTrue(connection.committed)

    def test_claim_increments_attempt_and_exhausted_failure_dead_letters(self):
        claim_cursor = SequencedCursor([("job-1", "pending", 0, {}, None)])
        claim_connection = RecordingConnection(claim_cursor)
        failure_cursor = SequencedCursor([("job-1", "processing", 3, {}, None)])
        failure_connection = RecordingConnection(failure_cursor)
        connections = iter([claim_connection, failure_connection])
        fake_json = types.ModuleType("psycopg.types.json")
        fake_json.Jsonb = lambda value: value
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: next(connections)
        with patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        ):
            with patch.dict("os.environ", {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
                claimed = claim_autoapi_article_fetch_job("autoapi-job-1", max_attempts=3)
                dead_lettered = record_autoapi_article_fetch_failure(
                    "autoapi-job-1", "source unavailable", max_attempts=3
                )

        self.assertEqual(claimed["status"], "processing")
        self.assertEqual(claimed["attempt_count"], 1)
        self.assertEqual(dead_lettered["status"], "dead_letter")
        self.assertTrue(claim_connection.committed)
        self.assertTrue(failure_connection.committed)
        self.assertTrue(any("status = 'processing'" in query for query, _ in claim_cursor.calls))
        self.assertTrue(any("status = %s" in query for query, _ in failure_cursor.calls))


if __name__ == "__main__":
    unittest.main()
