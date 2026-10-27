import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))

from nats_health import normalize_stream_info
from replay_outbox import replay_target


class StorageMessagingOperationsTests(unittest.TestCase):
    def test_stream_info_is_reduced_to_safe_operational_fields(self):
        normalized = normalize_stream_info({
            "config": {
                "name": "AUTODATA",
                "subjects": ["dataset.>"],
                "retention": "limits",
            },
            "state": {"messages": 7, "bytes": 512, "first_seq": 10, "last_seq": 16},
        })

        self.assertEqual(normalized, {
            "name": "AUTODATA",
            "subjects": ["dataset.>"],
            "retention": "limits",
            "messages": 7,
            "bytes": 512,
            "first_seq": 10,
            "last_seq": 16,
        })

    def test_replay_requires_exactly_one_target(self):
        self.assertEqual(replay_target("event-1", None), ("event", "event-1"))
        self.assertEqual(replay_target(None, "job-1"), ("job", "job-1"))
        with self.assertRaises(ValueError):
            replay_target(None, None)
        with self.assertRaises(ValueError):
            replay_target("event-1", "job-1")

    def test_health_and_reconcile_scripts_use_safe_env_defaults(self):
        obj_health = (ROOT / "scripts/dev/object_storage_health.py").read_text()
        self.assertIn('os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin")', obj_health)
        self.assertIn('os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password")', obj_health)
        self.assertIn("workers/ingestion-python/src", obj_health)

        reconcile = (ROOT / "scripts/dev/reconcile_payments.py").read_text()
        self.assertIn('os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only")', reconcile)
        self.assertIn("resolve_database_address", reconcile)
        self.assertIn("workers/ingestion-python/src", reconcile)

        metrics = (ROOT / "scripts/dev/operational_metrics.py").read_text()
        self.assertIn('os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only")', metrics)
        self.assertIn("resolve_database_address", metrics)

        replay = (ROOT / "scripts/dev/replay_outbox.py").read_text()
        self.assertIn('os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only")', replay)
        self.assertIn("resolve_database_address", replay)

        backup = (ROOT / "scripts/dev/backup_restore_smoke.py").read_text()
        self.assertIn('os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only")', backup)
        self.assertIn('os.getenv("AUTODATA_MINIO_ROOT_USER", "localadmin")', backup)
        self.assertIn('os.getenv("AUTODATA_MINIO_ROOT_PASSWORD", "local-dev-password")', backup)

        deep = (ROOT / "scripts/dev/deep_lane_smoke.py").read_text()
        self.assertIn('os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only")', deep)
        self.assertIn("resolve_database_address", deep)
        self.assertIn("resolve_viewable_projection_id", deep)

        obj_health = (ROOT / "scripts/dev/object_storage_health.py").read_text()
        self.assertIn('os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin")', obj_health)
        self.assertIn('os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password")', obj_health)
        self.assertIn("resolve_s3_endpoint", obj_health)


if __name__ == "__main__":
    unittest.main()
