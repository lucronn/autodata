"""Guard AutoData's direct, independently configurable bank connector origins."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/compose/compose.yaml"
K8S = ROOT / "infra/k8s/base.yaml"
DEFAULT_ORIGINS = {
    "BANKONE_BASE_URL": "https://bankone.cars.tk",
    "BANKTWO_BASE_URL": "https://banktwo.cars.tk",
}
REQUIRED_COMPOSE_ENV = {
    "AUTODATA_POSTGRES_PASSWORD": "compose-test-postgres",
    "AUTODATA_MINIO_ROOT_USER": "compose-test-minio",
    "AUTODATA_MINIO_ROOT_PASSWORD": "compose-test-minio-password",
}


class BankTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("docker") is None:
            raise unittest.SkipTest("Docker Compose is required for topology config tests")

    def compose_config(self, overrides: dict[str, str] | None = None) -> dict:
        environment = os.environ.copy()
        environment.update(REQUIRED_COMPOSE_ENV)
        environment.update(DEFAULT_ORIGINS)
        environment.update(overrides or {})
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE), "config", "--format", "json"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_origins_default_to_independent_bank_domains(self):
        config = self.compose_config()
        for service_name in ("ingestion-worker", "ingestion-http"):
            environment = config["services"][service_name]["environment"]
            self.assertEqual(environment["BANKONE_BASE_URL"], DEFAULT_ORIGINS["BANKONE_BASE_URL"])
            self.assertEqual(environment["BANKTWO_BASE_URL"], DEFAULT_ORIGINS["BANKTWO_BASE_URL"])

    def test_each_origin_can_be_overridden_without_changing_the_other(self):
        overrides = {
            "BANKONE_BASE_URL": "http://bankone.test:4101",
            "BANKTWO_BASE_URL": "http://banktwo.test:4202",
        }
        for variable, override in overrides.items():
            with self.subTest(variable=variable):
                config = self.compose_config({variable: override})
                for service_name in ("ingestion-worker", "ingestion-http"):
                    environment = config["services"][service_name]["environment"]
                    self.assertEqual(environment[variable], override)
                    other = set(overrides) - {variable}
                    for other_variable in other:
                        self.assertEqual(environment[other_variable], DEFAULT_ORIGINS[other_variable])

    def test_compose_has_no_bank_runtime_or_build_coupling(self):
        config = self.compose_config()
        services = config["services"]
        self.assertFalse(
            [name for name in services if "bankone" in name.lower() or "banktwo" in name.lower()]
        )
        for name, service in services.items():
            self.assertNotRegex(name, r"(?i)bank(one|two)")
            self.assertNotRegex(str(service.get("image", "")), r"(?i)bank(one|two)")
            self.assertNotRegex(str(service.get("build", "")), r"(?i)bank(one|two)")
            self.assertNotRegex(str(service.get("depends_on", {})), r"(?i)bank(one|two)")
            self.assertNotRegex(str(service.get("volumes", [])), r"(?i)bank(one|two)")
            self.assertNotRegex(str(service.get("networks", {})), r"(?i)bank(one|two)")
        self.assertNotRegex(COMPOSE.read_text(), r"(?i)BANK(ONE|TWO)_(?:API_TOKEN|POSTGRES|S3|MINIO)")

    def test_bank_repositories_are_not_git_submodules(self):
        gitmodules = ROOT / ".gitmodules"
        if gitmodules.exists():
            self.assertNotRegex(gitmodules.read_text(), r"(?i)bank(one|two)")
        index = subprocess.run(
            ["git", "ls-files", "--stage"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        bank_gitlinks = [
            line for line in index.splitlines()
            if line.startswith("160000 ") and re.search(r"(?i)bank(one|two)", line)
        ]
        self.assertEqual(bank_gitlinks, [])

    def test_kubernetes_config_has_independent_direct_origins_and_no_bank_workload(self):
        text = K8S.read_text()
        self.assertIn("BANKONE_BASE_URL: https://bankone.cars.tk", text)
        self.assertIn("BANKTWO_BASE_URL: https://banktwo.cars.tk", text)
        self.assertNotRegex(text, r"(?im)^\s*image:.*bank(one|two)")
        self.assertNotRegex(text, r"(?i)bank(one|two)-(?:api|service|deployment|worker)")
        self.assertNotRegex(text, r"(?i)BANK(ONE|TWO)_(?:API_TOKEN|POSTGRES|S3|MINIO)")

    def test_env_example_uses_client_names_and_contains_no_credentials(self):
        example = (ROOT / ".env.example").read_text()
        self.assertIn("BANKONE_BASE_URL=https://bankone.cars.tk", example)
        self.assertIn("BANKTWO_BASE_URL=https://banktwo.cars.tk", example)
        self.assertNotRegex(example, r"(?i)(?:TOKEN|PASSWORD|SECRET|CREDENTIAL)")

    def test_compose_does_not_inject_retired_autoapi_origins(self):
        self.assertNotRegex(COMPOSE.read_text(), r"(?i)AUTODATA_AUTOAPI(?:TWO)?_BASE_URL|autoapi(?:two|-sigma)\.vercel\.app")


if __name__ == "__main__":
    unittest.main()
