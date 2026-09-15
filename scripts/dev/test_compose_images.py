import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra" / "compose" / "compose.yaml"
MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z"


class ComposeImageContractTests(unittest.TestCase):
    def test_minio_uses_verified_release_default_and_keeps_override(self):
        compose = COMPOSE.read_text()

        self.assertIn(
            f"image: ${{AUTODATA_MINIO_IMAGE:-{MINIO_IMAGE}}}",
            compose,
        )
        self.assertIn("AUTODATA_MINIO_IMAGE", compose)
        self.assertNotIn("AUTODATA_MINIO_IMAGE:-minio/minio:latest", compose)


if __name__ == "__main__":
    unittest.main()
