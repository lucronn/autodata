import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


from autodata_ingestion.object_storage import ensure_versioned_bucket


class FakeBucketVersioning:
    def __init__(self, status):
        self.status = status


class FakeVersioningConfig:
    def __init__(self, status):
        self.status = status


class FakeObjectStorageClient:
    def __init__(self, status=None):
        self.status = status
        self.created = []
        self.versioning_updates = []

    def bucket_exists(self, bucket):
        return bool(self.status)

    def make_bucket(self, bucket):
        self.created.append(bucket)

    def get_bucket_versioning(self, bucket):
        return FakeBucketVersioning(self.status)

    def set_bucket_versioning(self, bucket, config):
        self.versioning_updates.append((bucket, config.status))
        self.status = config.status


class ObjectStorageTests(unittest.TestCase):
    def test_existing_bucket_is_upgraded_to_versioning(self):
        client = FakeObjectStorageClient(status=None)

        result = ensure_versioned_bucket(client, "autodata-sources", FakeVersioningConfig)

        self.assertEqual(result, {"bucket": "autodata-sources", "created": True, "versioning": "Enabled"})
        self.assertEqual(client.created, ["autodata-sources"])
        self.assertEqual(client.versioning_updates, [("autodata-sources", "Enabled")])

    def test_enabled_bucket_is_left_unchanged(self):
        client = FakeObjectStorageClient(status="Enabled")

        result = ensure_versioned_bucket(client, "autodata-sources", FakeVersioningConfig)

        self.assertEqual(result["created"], False)
        self.assertEqual(client.versioning_updates, [])


if __name__ == "__main__":
    unittest.main()
