"""Protect the preview API boot dependency without touching the live unit."""

from configparser import ConfigParser
from pathlib import Path
import unittest


DROP_IN = (
    Path(__file__).resolve().parents[2]
    / "infra/deploy/preview/autodata-api-docker-dependency.conf"
)


class PreviewAPIDockerDependencyTest(unittest.TestCase):
    def load_drop_in(self) -> ConfigParser:
        self.assertTrue(DROP_IN.is_file(), f"missing preview API drop-in: {DROP_IN}")
        unit = ConfigParser(interpolation=None)
        unit.read(DROP_IN, encoding="utf-8")
        return unit

    def test_api_pulls_docker_into_boot_transaction(self) -> None:
        unit = self.load_drop_in()
        self.assertIn("docker.service", unit.get("Unit", "Requires").split())
        self.assertIn("docker.service", unit.get("Unit", "After").split())

    def test_drop_in_does_not_override_api_or_payment_configuration(self) -> None:
        unit = self.load_drop_in()
        self.assertEqual(["Unit"], unit.sections())


if __name__ == "__main__":
    unittest.main()
