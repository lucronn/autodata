import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.directory_connector import DirectorySourceConnector  # noqa: E402


class DirectorySourceConnectorTests(unittest.TestCase):
    def test_fetch_returns_deterministic_content_addressed_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.json").write_bytes(b'{"value":2}')
            (root / "nested").mkdir()
            (root / "nested" / "a.csv").write_bytes(b"id,value\n1,one\n")

            connector = DirectorySourceConnector(root, "drop-v1")
            first = list(connector.fetch({}))
            second = list(connector.fetch({}))

        self.assertEqual([resource.source_uri for resource in first], ["file://nested/a.csv", "file://z.json"])
        self.assertEqual(
            [(resource.source_uri, resource.source_version, resource.content_sha256) for resource in first],
            [(resource.source_uri, resource.source_version, resource.content_sha256) for resource in second],
        )
        self.assertEqual([resource.media_type for resource in first], ["text/csv", "application/json"])
        self.assertEqual(first[0].locator, "nested/a.csv")

    def test_fetch_rejects_a_missing_or_non_directory_path(self):
        with self.assertRaisesRegex(ValueError, "source directory"):
            DirectorySourceConnector(Path("/path/that/does/not/exist"), "drop-v1").fetch({})


if __name__ == "__main__":
    unittest.main()
