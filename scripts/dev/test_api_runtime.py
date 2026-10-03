import json
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

    def test_catalog_image_storage_key_is_internal_only(self):
        store = self.read("apps/api-go/catalog_store.go")
        self.assertIn('StorageKey string `json:"-"`', store)
        media_test = self.read("apps/api-go/catalog_media_test.go")
        self.assertIn("private/source-object/key", media_test)
        self.assertIn("storage_key", media_test)

    def test_api_docker_build_copies_all_embedded_web_assets(self):
        dockerfile = self.read("apps/api-go/Dockerfile")

        self.assertIn("COPY apps/api-go/dashboard ./apps/api-go/dashboard", dockerfile)
        self.assertIn("COPY apps/api-go/workshop ./apps/api-go/workshop", dockerfile)
        self.assertIn(
            "COPY apps/api-go/openapi.json apps/api-go/openapi.yaml apps/api-go/swagger.html ./apps/api-go/",
            dockerfile,
        )
        self.assertIn("COPY apps/api-go/swagger-ui ./apps/api-go/swagger-ui", dockerfile)

    def test_openapi_documents_all_source_media_routes_without_storage_keys(self):
        spec = json.loads(self.read("apps/api-go/openapi.json"))
        router = self.read("apps/api-go/main.go")
        expected = {
            "/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source",
            "/v1/catalog/images/{token}",
            "/v1/catalog/images",
        }
        for route in expected:
            self.assertIn(route, spec["paths"])
            self.assertIn(f'"GET {route}"', router)
        image_properties = spec["components"]["schemas"]["Image"]["properties"]
        self.assertNotIn("storage_key", image_properties)
        source_responses = spec["paths"][
            "/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source"
        ]["get"]["responses"]["200"]["content"]
        self.assertIn("application/json", source_responses)
        self.assertIn("text/html", source_responses)
        self.assertIn("security", spec["paths"]["/v1/catalog/images/{token}"]["get"])
        openapi_yaml = self.read("apps/api-go/openapi.yaml")
        self.assertNotIn("storage_key", openapi_yaml)
        self.assertIn("image/*:", openapi_yaml)

    def test_protected_workflow_runs_api_runtime_smoke_after_migrations(self):
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        compose = "docker compose -f infra/compose/compose.yaml -f infra/compose/compose.ci.yaml"
        self.assertIn(
            f"{compose} up -d --wait api",
            workflow,
        )
        self.assertIn(f"{compose} run --rm api-runtime-smoke", workflow)
        self.assertLess(
            workflow.index(f"{compose} run migration-runner"),
            workflow.index(f"{compose} up -d --wait api"),
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
