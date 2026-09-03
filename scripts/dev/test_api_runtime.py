import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class APIRuntimeContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing runtime file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_compose_declares_postgres_api_runtime_smoke(self):
        compose = self.read("infra/compose/compose.yaml")
        self.assertIn('AUTODATA_PROJECTION_STORE: "postgres"', compose)
        self.assertIn("api-runtime-smoke:", compose)
        self.assertIn("scripts/dev/api_runtime_smoke.py", compose)
        self.assertIn("api:\n        condition: service_healthy", compose)

    def test_protected_workflow_runs_api_runtime_smoke_after_migrations(self):
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        self.assertIn("docker compose -f infra/compose/compose.yaml up -d --wait api", workflow)
        self.assertIn("docker compose -f infra/compose/compose.yaml run --rm api-runtime-smoke", workflow)
        self.assertLess(
            workflow.index("docker compose -f infra/compose/compose.yaml run migration-runner"),
            workflow.index("docker compose -f infra/compose/compose.yaml up -d --wait api"),
        )

    def test_runtime_smoke_checks_replay_ownership_and_invalid_input(self):
        script = self.read("scripts/dev/api_runtime_smoke.py")
        for expected in (
            "Idempotency-Key",
            "fast_lane_processing",
            "dataset_request_id",
            "HTTPError",
            "ENTITLEMENT_REQUIRED",
            "invalid-product",
            "sections",
        ):
            self.assertIn(expected, script)

    def test_fast_lane_fixture_persists_request_owner(self):
        fixture = self.read("workers/ingestion-python/src/autodata_ingestion/ingest_fixture.py")
        self.assertIn("processing_version, organization_id", fixture)
        self.assertIn("request_key,\n                    organization_id", fixture)


if __name__ == "__main__":
    unittest.main()
