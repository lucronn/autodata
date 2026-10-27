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

    def test_nats_url_resolution_and_silent_offline_handling(self):
        from nats_health import resolve_nats_url

        self.assertEqual(resolve_nats_url("nats://custom:4222"), "nats://custom:4222")

        nats_src = (ROOT / "scripts/dev/nats_health.py").read_text()
        self.assertIn("_silent_nats_error", nats_src)
        self.assertIn("error_cb=_silent_nats_error", nats_src)

        smoke_src = (ROOT / "scripts/dev/ingestion_smoke.py").read_text()
        self.assertIn("_silent_nats_error", smoke_src)
        self.assertIn("error_cb=_silent_nats_error", smoke_src)

        outbox_src = (ROOT / "workers/enrichment-python/src/autodata_enrichment/outbox.py").read_text()
        self.assertIn("_resolve_nats_url", outbox_src)
        self.assertIn("_silent_nats_error", outbox_src)
        self.assertIn("error_cb=_silent_nats_error", outbox_src)

    def test_reconcile_payments_cli_argument_parsing(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/reconcile_payments.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--once", result.stdout)
        self.assertIn("--batch-size", result.stdout)
        self.assertIn("--poll-seconds", result.stdout)

    def test_outbox_relay_cli_argument_parsing(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/outbox_relay.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--once", result.stdout)
        self.assertIn("--limit", result.stdout)
        self.assertIn("--max-attempts", result.stdout)
        self.assertIn("--poll-seconds", result.stdout)

    def test_persistence_modules_use_database_and_s3_resolvers(self):
        bundle_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/bundle_persistence.py").read_text()
        self.assertIn("_resolve_database_address", bundle_src)
        self.assertIn("_resolve_s3_endpoint", bundle_src)

        selection_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/vehicle_selection_persistence.py").read_text()
        self.assertIn("_resolve_database_address", selection_src)

        derived_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py").read_text()
        self.assertIn("_resolve_database_address", derived_src)

        bankone_jobs_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/bankone_job_persistence.py").read_text()
        self.assertIn("_resolve_database_address", bankone_jobs_src)

        proc_images_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/procedure_images.py").read_text()
        self.assertIn("_resolve_s3_endpoint", proc_images_src)

        catalog_sync_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/catalog_sync.py").read_text()
        self.assertIn("_resolve_database_address", catalog_sync_src)

        knowledge_catalog_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/knowledge_catalog.py").read_text()
        self.assertIn("_resolve_database_address", knowledge_catalog_src)

        catalog_service_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/catalog_service.py").read_text()
        self.assertIn("_resolve_database_address", catalog_service_src)

        chat_runtime_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/chat_durable_runtime.py").read_text()
        self.assertIn("_resolve_database_address", chat_runtime_src)

        fallback_runtime_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/knowledge_fallback_runtime.py").read_text()
        self.assertIn("_resolve_database_address", fallback_runtime_src)

        fixture_src = (ROOT / "workers/ingestion-python/src/autodata_ingestion/ingest_fixture.py").read_text()
        self.assertIn("_resolve_database_address", fixture_src)
        self.assertIn("_resolve_s3_endpoint", fixture_src)

    def test_normalize_source_directory_cli_limit(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/normalize_source_directory.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--limit", result.stdout)

    def test_ingest_bankone_batch_cli_limit_and_aliases(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/ingest_bankone_batch.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--limit", result.stdout)

    def test_replay_outbox_cli_argv(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/replay_outbox.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--event-id", result.stdout)
        self.assertIn("--job-id", result.stdout)

    def test_fake_integrations_smoke_cli_argv(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dev/fake_integrations_smoke.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--signing-secret", result.stdout)
        self.assertIn("--org-id", result.stdout)

    def test_developer_scripts_discover_worker_virtualenvs(self):
        scripts_to_check = [
            "normalize_source_directory.py",
            "reconcile_payments.py",
            "ingest_bankone_service.py",
            "ingest_banktwo_service.py",
            "deep_lane_smoke.py",
            "ingest_bankone_batch.py",
            "replay_outbox.py",
            "fake_integrations_smoke.py",
            "object_storage_health.py",
            "api_runtime_smoke.py",
            "backup_restore_smoke.py",
            "operational_metrics.py",
            "payment_reconciliation_smoke.py",
            "universal_article_smoke.py",
            "knowledge_warm_path_benchmark.py",
            "smoke_local_stack.py",
            "migrate.py",
            "migration_plan.py",
            "consumer_agent.py",
            "nats_health.py",
            "ingestion_smoke.py",
        ]
        for name in scripts_to_check:
            content = (ROOT / "scripts/dev" / name).read_text()
            self.assertIn("venv_site", content, f"missing venv_site discovery in {name}")

    def test_developer_scripts_support_cli_argv(self):
        import subprocess

        for script_name, expected_flag in [
            ("ingest_bankone_service.py", "--limit"),
            ("ingest_banktwo_service.py", "--limit"),
            ("deep_lane_smoke.py", "--processing-version"),
            ("smoke_local_stack.py", "--base-url"),
            ("normalize_source_directory.py", "--persist"),
            ("api_runtime_smoke.py", "--base-url"),
            ("backup_restore_smoke.py", "--compose-file"),
            ("operational_metrics.py", "--address"),
            ("payment_reconciliation_smoke.py", "--address"),
            ("migrate.py", "--address"),
            ("migration_plan.py", "--migrations-dir"),
            ("nats_health.py", "--stream"),
            ("object_storage_health.py", "--bucket"),
            ("ingestion_smoke.py", "--address"),
            ("ingestion_smoke.py", "--s3-endpoint"),
            ("ingestion_smoke.py", "--nats-url"),
            ("universal_article_smoke.py", "--live-url"),
            ("knowledge_warm_path_benchmark.py", "--query"),
        ]:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/dev" / script_name), "--help"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(expected_flag, result.stdout, f"missing {expected_flag} in {script_name}")


if __name__ == "__main__":
    unittest.main()
