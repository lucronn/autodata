import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra" / "compose" / "compose.yaml"
LOCAL_MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z"
CI_SEAWEED_IMAGE = (
    "ghcr.io/chrislusf/seaweedfs@sha256:"
    "4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d"
)
CI_COMPOSE = ROOT / "infra" / "compose" / "compose.ci.yaml"


class ComposeImageContractTests(unittest.TestCase):
    def test_local_minio_default_and_override_remain_unchanged(self):
        compose = COMPOSE.read_text()

        self.assertIn(
            f"image: ${{AUTODATA_MINIO_IMAGE:-{LOCAL_MINIO_IMAGE}}}",
            compose,
        )
        self.assertIn("AUTODATA_MINIO_IMAGE", compose)
        self.assertNotIn("AUTODATA_MINIO_IMAGE:-minio/minio:latest", compose)

    def test_ci_uses_public_digest_pinned_s3_image_and_isolated_storage(self):
        compose = CI_COMPOSE.read_text()

        self.assertIn(f"image: {CI_SEAWEED_IMAGE}", compose)
        self.assertIn('"-s3.port=9000"', compose)
        self.assertIn("AWS_ACCESS_KEY_ID:", compose)
        self.assertIn("AWS_SECRET_ACCESS_KEY:", compose)
        self.assertIn("S3_BUCKET: autodata-sources", compose)
        self.assertIn("seaweedfs-ci-data:/data", compose)
        self.assertIn("!reset []", compose)
        self.assertIn("127.0.0.1:9333/cluster/status", compose)

    def test_chat_runtime_is_not_active_by_default(self):
        compose = COMPOSE.read_text()

        self.assertIn("AUTODATA_CHAT_WORKER_ENABLED: ${AUTODATA_CHAT_WORKER_ENABLED:-0}", compose)
        self.assertNotIn("AUTODATA_CHAT_RUNTIME_BACKEND:", compose)


if __name__ == "__main__":
    unittest.main()
