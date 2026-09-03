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


if __name__ == "__main__":
    unittest.main()
