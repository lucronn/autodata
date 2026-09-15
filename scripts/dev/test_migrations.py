import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))

from migration_plan import (  # noqa: E402
    fixture_files,
    migration_files,
    validate_migration_set,
)


class MigrationPlanTests(unittest.TestCase):
    def test_migrations_are_numeric_and_ordered(self):
        paths = migration_files(ROOT / "db/migrations")

        self.assertEqual(
            [path.name for path in paths],
            [
                "001_extensions.sql",
                "002_platform_spine.sql",
                "003_canonical_vehicle.sql",
                "004_normalized_source_bundle.sql",
                "005_preserve_duplicate_article_ids.sql",
                "006_backfill_article_source_locators.sql",
                "007_link_evidence_to_revision.sql",
                "008_publication_outbox_delivery.sql",
                "009_feedback_evidence_link.sql",
                "010_evidence_review_metadata.sql",
                "011_feedback_review_metadata.sql",
                "012_payment_fulfillment_reconciliation.sql",
                "013_dataset_request_ownership.sql",
                "014_normalized_article_content.sql",
                "015_vehicle_identity_resolution.sql",
                "016_catalog_article_configuration.sql",
                "017_knowledge_catalog_evidence_index.sql",
                "018_source_review_items.sql",
                "019_article_content_provenance.sql",
                "020_autoapi_article_fetch_jobs.sql",
                "021_autoapi_article_fetch_job_retries.sql",
                "022_job_plan_derived_articles.sql",
                "023_catalog_article_images.sql",
                "024_catalog_article_operations.sql",
                "025_chat_quote_procedure.sql",
                "026_chat_quote_operation_categories.sql",
                "027_chat_runtime_durable_state.sql",
            ],
        )

    def test_dataset_request_ownership_is_backfilled_without_overwriting_existing_values(self):
        migration = (ROOT / "db/migrations/013_dataset_request_ownership.sql").read_text()

        self.assertIn(
            "ADD COLUMN IF NOT EXISTS organization_id uuid",
            migration,
        )
        self.assertIn(
            "request.organization_id IS NULL",
            migration,
        )
        self.assertIn(
            "dataset_requests_organization_idx",
            migration,
        )

    def test_schema_migrations_cover_platform_spine_and_vector(self):
        errors = validate_migration_set(ROOT / "db/migrations")

        self.assertEqual(errors, [])

    def test_foundation_fixture_is_separate_from_schema_migrations(self):
        self.assertEqual(
            [path.name for path in fixture_files(ROOT / "db/fixtures")],
            ["001_foundation.sql"],
        )

    def test_chat_quote_revision_publication_state_and_immutability_are_database_enforced(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn("CHECK ((status = 'published') = (published_at IS NOT NULL))", migration)
        self.assertIn("OLD.status = 'published' OR OLD.published_at IS NOT NULL", migration)
        self.assertIn("BEFORE UPDATE OR DELETE ON chat_quote_revisions", migration)

    def test_price_snapshots_are_immutable_and_refresh_failures_are_separate(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn("CREATE TABLE IF NOT EXISTS parts_price_snapshot_refreshes", migration)
        self.assertIn("parts_price_snapshot_id uuid NOT NULL REFERENCES parts_price_snapshots", migration)
        self.assertIn("refresh_status text NOT NULL", migration)
        self.assertIn("failure jsonb", migration)
        self.assertIn("BEFORE UPDATE OR DELETE ON parts_price_snapshots", migration)
        self.assertIn("stale values remain readable", migration)

    def test_visual_artifacts_require_and_preserve_source_artifact_linkage(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn("source_artifact_id uuid NOT NULL", migration)
        self.assertIn("REFERENCES source_artifacts(source_artifact_id, source_snapshot_id, object_key)", migration)
        self.assertIn("published_at timestamptz", migration)
        self.assertIn("BEFORE UPDATE OR DELETE ON chat_visual_artifacts", migration)
        self.assertIn("processor text NOT NULL", migration)
        self.assertIn("processor_version text NOT NULL", migration)

    def test_quote_arithmetic_and_overlap_bounds_are_database_enforced(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn(
            "CHECK (total_hours = required_hours + recommended_hours - overlap_hours_removed)",
            migration,
        )
        self.assertIn(
            "CHECK (overlap_hours_removed <= required_hours + recommended_hours)",
            migration,
        )

    def test_quote_persists_required_and_recommended_operation_collections(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        for collection in ("required_operations", "recommended_operations"):
            self.assertIn(
                f"{collection} jsonb NOT NULL DEFAULT '[]'::jsonb",
                migration,
            )
            self.assertIn(
                f"CHECK (jsonb_typeof({collection}) = 'array')",
                migration,
            )

    def test_quote_operation_categories_upgrade_existing_025_table(self):
        clean_install = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()
        upgrade = (ROOT / "db/migrations/026_chat_quote_operation_categories.sql").read_text()

        for collection in ("required_operations", "recommended_operations"):
            definition = f"{collection} jsonb NOT NULL DEFAULT '[]'::jsonb"
            self.assertIn(definition, clean_install)
            self.assertIn(
                f"CHECK (jsonb_typeof({collection}) = 'array')",
                clean_install,
            )
            self.assertRegex(
                upgrade,
                rf"ALTER TABLE chat_quote_revisions\s+"
                rf"ADD COLUMN IF NOT EXISTS {collection} jsonb NOT NULL DEFAULT '\[\]'::jsonb;",
            )
            self.assertIn(
                f"CONSTRAINT chat_quote_revisions_{collection}_array_check",
                upgrade,
            )
            self.assertIn(
                f"CHECK (jsonb_typeof({collection}) = 'array')",
                upgrade,
            )

        self.assertNotIn("CREATE TABLE IF NOT EXISTS chat_quote_revisions", upgrade)
        self.assertIn(
            "VALUES ('026_chat_quote_operation_categories')",
            upgrade,
        )

    def test_worker_events_persist_the_complete_event_envelope(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        for column in (
            "producer text NOT NULL",
            "request_id uuid NOT NULL",
            "projection_id uuid NOT NULL",
            "revision_id uuid",
            "correlation_id uuid NOT NULL",
            "idempotency_key text NOT NULL",
            "payload jsonb NOT NULL",
        ):
            self.assertIn(column, migration)
        self.assertIn("'stale'", migration)

    def test_reusable_derived_article_key_prevents_query_uniqueness_collisions(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn("CREATE TABLE IF NOT EXISTS chat_derived_article_keys", migration)
        self.assertIn("derived_article_identity text PRIMARY KEY", migration)
        self.assertIn("derived_article_id uuid NOT NULL REFERENCES derived_articles", migration)
        self.assertRegex(
            migration,
            r"derived_article_identity text NOT NULL\s+REFERENCES chat_derived_article_keys",
        )
        self.assertNotIn("derived_article_identity text NOT NULL UNIQUE", migration)

    def test_markup_is_structurally_prohibited(self):
        migration = (ROOT / "db/migrations/025_chat_quote_procedure.sql").read_text()

        self.assertIn("markup_applied boolean NOT NULL DEFAULT false CHECK (markup_applied = false)", migration)


if __name__ == "__main__":
    unittest.main()
