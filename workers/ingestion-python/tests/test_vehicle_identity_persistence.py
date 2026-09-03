import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


class RecordingCursor:
    def __init__(self, select_results=None):
        self.calls = []
        self._returned_id = None
        self._select_results = list(select_results or [])

    def execute(self, query, params):
        self.calls.append((query, params))
        compact_query = " ".join(query.split()).lower()
        if compact_query.startswith("select "):
            self._returned_id = None
            return
        self._returned_id = params[0]

    def fetchone(self):
        if self._select_results:
            return (self._select_results.pop(0),)
        return (self._returned_id,)


class VehicleIdentityPersistenceTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("autodata_ingestion.vehicle_identity_persistence")
        self.assertIsNotNone(spec, "vehicle identity persistence module must exist")
        return importlib.import_module("autodata_ingestion.vehicle_identity_persistence")

    def test_migration_defines_forward_safe_identity_graph_with_provenance(self):
        migration = (ROOT / "db/migrations/015_vehicle_identity_resolution.sql").read_text()

        for table in (
            "vehicle_identity_bases",
            "vehicle_configurations",
            "vehicle_aliases",
            "vehicle_identity_observations",
            "catalog_article_vehicle_links",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", migration)
        for column in (
            "source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id)",
            "extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id)",
            "evidence_locator text NOT NULL",
            "evidence_confidence numeric(5, 4) NOT NULL CHECK",
            "reviewer_state text NOT NULL CHECK",
        ):
            self.assertIn(column, migration)
        self.assertIn("canonical_base_key text NOT NULL UNIQUE", migration)
        self.assertIn("configuration_key text NOT NULL UNIQUE", migration)
        self.assertIn("observation_key text NOT NULL UNIQUE", migration)
        self.assertIn("duplicate_catalog_article_id uuid NOT NULL UNIQUE", migration)
        self.assertNotIn("ALTER TABLE vehicles", migration)
        self.assertNotIn("DROP INDEX", migration)
        self.assertNotIn("DROP CONSTRAINT", migration)
        self.assertIn("INSERT INTO schema_migrations (version)", migration)
        self.assertIn("015_vehicle_identity_resolution", migration)

    def test_persist_observation_keeps_legacy_vehicle_identity_and_writes_graph_provenance(self):
        module = self._module()
        cursor = RecordingCursor()
        observation = module.canonicalize_vehicle_observation(
            {
                "year": "24",
                "make": " Chevy ",
                "model": " Silverado-1500 ",
                "trim": " ltz ",
                "body_style": " Crew-Cab ",
                "drivetrain": "4x2",
                "engine": "5.3LT",
                "market": "US",
            }
        )

        result = module.persist_vehicle_identity_resolution(
            cursor,
            observation,
            source_snapshot_id="snapshot-1",
            extraction_evidence_id="evidence-1",
            source_locator="json:vehicle",
            evidence_locator="json:vehicle.make",
            evidence_confidence=0.98,
            reviewer_state="approved",
            source_watermark="2026-09-03T12:00:00Z",
            jsonb=lambda value: value,
        )

        self.assertEqual(result.vehicle_key, "chevrolet-silverado-1500-2024-us")
        self.assertEqual(
            result.canonical_base_key,
            "chevrolet-silverado-1500-2024-us-body-crew-cab-drivetrain-2wd",
        )
        self.assertEqual(
            result.configuration_key,
            "chevrolet-silverado-1500-2024-us-body-crew-cab-drivetrain-2wd-trim-ltz-engine-5-3l",
        )
        self.assertGreaterEqual(len(cursor.calls), 6)
        vehicle_query, vehicle_params = cursor.calls[0]
        self.assertIn("ON CONFLICT (vehicle_key)", " ".join(vehicle_query.split()))
        self.assertEqual(vehicle_params[1], "chevrolet-silverado-1500-2024-us")
        self.assertEqual(vehicle_params[2:6], ("Chevrolet", "Silverado 1500", 2024, "US"))

        base_query, base_params = cursor.calls[1]
        compact_base_query = " ".join(base_query.split())
        self.assertIn("INSERT INTO vehicle_identity_bases", compact_base_query)
        self.assertIn("source_snapshot_id", compact_base_query)
        self.assertIn("extraction_evidence_id", compact_base_query)
        self.assertIn("reviewer_state", compact_base_query)
        self.assertEqual(base_params[1], result.canonical_base_key)
        self.assertEqual(base_params[2], result.vehicle_id)
        self.assertEqual(base_params[9:14], ("snapshot-1", "evidence-1", "json:vehicle", "json:vehicle.make", 0.98))
        self.assertEqual(base_params[14], "approved")

        observation_query, observation_params = cursor.calls[-1]
        compact_observation_query = " ".join(observation_query.split())
        self.assertIn("ON CONFLICT (observation_key)", compact_observation_query)
        self.assertEqual(observation_params[5], "snapshot-1")
        self.assertEqual(observation_params[6], "evidence-1")
        self.assertEqual(observation_params[13], "matched")

    def test_later_richer_observation_enriches_the_same_legacy_vehicle_row(self):
        module = self._module()
        coarse = module.canonicalize_vehicle_observation(
            {"year": 2024, "make": "Chevrolet", "model": "Silverado 1500", "region": "US"}
        )
        richer = module.canonicalize_vehicle_observation(
            {
                "year": 2024,
                "make": "Chevrolet",
                "model": "Silverado 1500",
                "region": "US",
                "body_style": "Crew Cab",
                "drivetrain": "2WD",
                "engine": "5.3L",
            }
        )
        first_cursor = RecordingCursor()
        second_cursor = RecordingCursor()

        first = module.persist_vehicle_identity_resolution(
            first_cursor,
            coarse,
            source_snapshot_id="snapshot-1",
            extraction_evidence_id="evidence-1",
            source_locator="json:vehicle[0]",
            evidence_locator="json:vehicle[0]",
            evidence_confidence=0.91,
            reviewer_state="approved",
            source_watermark="v1",
            jsonb=lambda value: value,
        )
        second = module.persist_vehicle_identity_resolution(
            second_cursor,
            richer,
            source_snapshot_id="snapshot-2",
            extraction_evidence_id="evidence-2",
            source_locator="json:vehicle[1]",
            evidence_locator="json:vehicle[1]",
            evidence_confidence=0.94,
            reviewer_state="approved",
            source_watermark="v2",
            jsonb=lambda value: value,
        )

        self.assertEqual(first.vehicle_key, "chevrolet-silverado-1500-2024-us")
        self.assertEqual(second.vehicle_key, "chevrolet-silverado-1500-2024-us")
        self.assertEqual(first.vehicle_id, second.vehicle_id)
        self.assertNotEqual(first.canonical_base_key, second.canonical_base_key)
        self.assertEqual(first_cursor.calls[0][1][1], second_cursor.calls[0][1][1])

    def test_article_duplicate_link_resolves_articles_by_source_scoped_replay_identity(self):
        module = self._module()
        cursor = RecordingCursor(select_results=["article-canonical", "article-duplicate"])

        link_id = module.persist_catalog_article_duplicate_link(
            cursor,
            canonical=module.CatalogArticleReplayIdentity(
                vehicle_id="vehicle-1",
                article_id="TSB-42",
                source_snapshot_id="snapshot-a",
                source_locator="json:articles[0]",
            ),
            duplicate=module.CatalogArticleReplayIdentity(
                vehicle_id="vehicle-1",
                article_id="TSB-42",
                source_snapshot_id="snapshot-b",
                source_locator="json:articles[3]",
            ),
            source_snapshot_id="snapshot-review",
            extraction_evidence_id="evidence-review",
            evidence_locator="review:duplicate",
            evidence_confidence=0.87,
            reviewer_state="approved",
        )

        select_queries = [" ".join(query.split()) for query, _ in cursor.calls[:2]]
        for query in select_queries:
            self.assertIn(
                "WHERE vehicle_id = %s AND article_id = %s AND source_snapshot_id = %s AND source_locator = %s",
                query,
            )
        insert_query, insert_params = cursor.calls[2]
        self.assertIn("ON CONFLICT (duplicate_catalog_article_id)", " ".join(insert_query.split()))
        self.assertEqual(insert_params[1:4], ("vehicle-1", "article-canonical", "article-duplicate"))
        self.assertEqual(insert_params[4:8], ("snapshot-review", "evidence-review", "review:duplicate", 0.87))
        self.assertEqual(link_id, insert_params[0])


if __name__ == "__main__":
    unittest.main()
