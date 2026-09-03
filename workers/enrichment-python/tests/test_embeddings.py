import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.embeddings import (  # noqa: E402
    DETERMINISTIC_EMBEDDING_DIMENSION,
    DeterministicEmbeddingProvider,
    format_pgvector,
)


class EmbeddingTests(unittest.TestCase):
    def test_deterministic_provider_returns_a_stable_unit_vector(self):
        provider = DeterministicEmbeddingProvider()

        first = provider.embed("P0300 misfire diagnostic procedure")
        second = provider.embed("P0300 misfire diagnostic procedure")

        self.assertEqual(len(first), DETERMINISTIC_EMBEDDING_DIMENSION)
        self.assertEqual(first, second)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0, places=6)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in first))

    def test_different_evidence_texts_do_not_share_the_same_vector(self):
        provider = DeterministicEmbeddingProvider()

        self.assertNotEqual(provider.embed("brake fluid DOT 4"), provider.embed("engine oil 0W-20"))

    def test_pgvector_serialization_is_dimension_checked_and_stable(self):
        provider = DeterministicEmbeddingProvider()
        vector = provider.embed("connector pinout")

        encoded = format_pgvector(vector)

        self.assertTrue(encoded.startswith("[") and encoded.endswith("]"))
        self.assertEqual(encoded.count(","), DETERMINISTIC_EMBEDDING_DIMENSION - 1)
        with self.assertRaises(ValueError):
            format_pgvector((0.1, 0.2))


if __name__ == "__main__":
    unittest.main()
