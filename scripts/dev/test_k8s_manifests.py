import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "infra/k8s/base.yaml"


class KubernetesManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = [document for document in MANIFEST.read_text().split("\n---\n") if document.strip()]
        cls.by_key = {}
        for document in cls.documents:
            kind = next(line.split(":", 1)[1].strip() for line in document.splitlines() if line.startswith("kind:"))
            name = next(line.split(":", 1)[1].strip() for line in document.splitlines() if line.startswith("  name:"))
            cls.by_key[(kind, name)] = document

    def test_provider_neutral_baseline_contains_runtime_topology(self):
        expected = {
            ("ConfigMap", "autodata-config"),
            ("Service", "autodata-api"),
            ("Deployment", "autodata-api"),
            ("Deployment", "autodata-ingestion-worker"),
            ("Deployment", "autodata-enrichment-worker"),
            ("Deployment", "autodata-payment-reconciler"),
            ("Job", "autodata-migrations"),
            ("PodDisruptionBudget", "autodata-api"),
        }
        self.assertTrue(expected.issubset(self.by_key))

    def test_api_has_rolling_update_probes_resources_and_external_secrets(self):
        deployment = self.by_key[("Deployment", "autodata-api")]
        self.assertIn("  replicas: 2", deployment)
        self.assertIn("    type: RollingUpdate", deployment)
        self.assertIn("        - name: api", deployment)
        self.assertIn("              path: /readyz", deployment)
        self.assertIn("              path: /healthz", deployment)
        self.assertIn("            requests:", deployment)
        self.assertIn("            limits:", deployment)
        self.assertIn("                name: autodata-runtime-secrets", deployment)

    def test_workers_are_independently_scalable_and_migration_is_one_shot(self):
        for name in (
            "autodata-ingestion-worker",
            "autodata-enrichment-worker",
            "autodata-payment-reconciler",
        ):
            deployment = self.by_key[("Deployment", name)]
            self.assertIn("  replicas: 1", deployment)
            self.assertIn("          resources:", deployment)
            self.assertIn("                name: autodata-runtime-secrets", deployment)

        migration = self.by_key[("Job", "autodata-migrations")]
        self.assertIn("  backoffLimit: 0", migration)
        self.assertRegex(migration, r"      restartPolicy: (Never|OnFailure)")


if __name__ == "__main__":
    unittest.main()
