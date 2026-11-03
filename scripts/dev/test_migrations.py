import sys
import os
import shutil
import subprocess
import tempfile
import contextlib
import io
from unittest.mock import patch
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))

from migration_plan import (  # noqa: E402
    fixture_files,
    migration_files,
    validate_migration_set,
)
from migrate import apply_migrations, psql_command, resolve_database_address  # noqa: E402


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
                "028_vehicle_provider_mappings.sql",
                "029_vehicle_catalog_sync.sql",
                "030_vehicle_catalog_years.sql",
                "031_catalog_article_classification.sql",
                "032_catalog_article_source_original.sql",
                "033_catalog_scope_coverage.sql",
                "034_catalog_article_progress.sql",
                "035_ordered_article_document.sql",
                "036_source_fetch_jobs.sql",
                "037_article_source_lifecycle.sql",
                "038_article_transform_publication.sql",
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

    def test_psql_command_includes_host_and_port_when_address_provided(self):
        cmd = psql_command("127.0.0.1:5432")
        if cmd[0] == "psql":
            self.assertIn("-h", cmd)
            self.assertIn("127.0.0.1", cmd)
            self.assertIn("-p", cmd)
            self.assertIn("5432", cmd)

    def test_resolve_database_address_respects_explicit_and_environment(self):
        self.assertEqual(resolve_database_address("custom-host:5433"), "custom-host:5433")
        import os
        old = os.environ.get("AUTODATA_DB_ADDRESS")
        try:
            os.environ["AUTODATA_DB_ADDRESS"] = "env-host:5434"
            self.assertEqual(resolve_database_address(), "env-host:5434")
        finally:
            if old is not None:
                os.environ["AUTODATA_DB_ADDRESS"] = old
            else:
                os.environ.pop("AUTODATA_DB_ADDRESS", None)


class SharedDriverTests(unittest.TestCase):
    def emit(self, directory=None):
        command = ["sh", str(ROOT / "scripts/dev/migrate_sql.sh"), "--emit"]
        if directory is not None:
            command += ["--migrations-dir", str(directory)]
        return subprocess.run(command, capture_output=True, text=True)

    def test_emit_is_embedded_and_uses_one_session_lock(self):
        result = self.emit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("SELECT pg_advisory_lock(186,3738);"), 1)
        self.assertNotIn("\\i ", result.stdout)
        for path in migration_files(ROOT / "db/migrations"):
            self.assertIn(path.read_text(), result.stdout)
        self.assertIn("AUTODATA_APPLIED 033_catalog_scope_coverage.sql", result.stdout)

    def test_manifest_rejects_holes_unsafe_names_symlinks_and_wrong_stems(self):
        names = [p.name for p in migration_files(ROOT / "db/migrations")]
        cases = [names[1:3], names[:1]+names[2:3], names[:1]+["002_wrong.sql"],
                 names[:1]+["001_duplicate.sql"], names[:1]+["002_bad;name.sql"]]
        for manifest in cases:
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for name in manifest:
                    (directory / name).write_text("SELECT 1;\n")
                result = self.emit(directory)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / names[0]).symlink_to(ROOT / "db/migrations" / names[0])
            self.assertNotEqual(self.emit(directory).returncode, 0)

    def test_fixture_prefix_accepts_only_contiguous_canonical_prefix(self):
        with tempfile.TemporaryDirectory(prefix="migration space '") as tmp:
            directory = Path(tmp)
            first = migration_files(ROOT / "db/migrations")[0]
            shutil.copy(first, directory / first.name)
            result = self.emit(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            sentinel = directory / "shell-was-executed"
            body = "SELECT '$(touch " + str(sentinel) + ")';\n"
            (directory / first.name).write_text(body)
            literal = self.emit(directory)
            self.assertEqual(literal.returncode, 0, literal.stderr)
            self.assertIn(body, literal.stdout)
            self.assertFalse(sentinel.exists())
            (directory / first.name).write_text("SELECT 1; \\quit\n")
            self.assertNotEqual(self.emit(directory).returncode, 0)

    def test_default_refuses_truncated_manifest_before_sql_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts/dev").mkdir(parents=True)
            (root / "db/migrations").mkdir(parents=True)
            shutil.copy(ROOT / "scripts/dev/migrate_sql.sh", root / "scripts/dev")
            first = migration_files(ROOT / "db/migrations")[0]
            shutil.copy(first, root / "db/migrations")
            result = subprocess.run(["sh", str(root / "scripts/dev/migrate_sql.sh"), "--emit"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_default_invocation_executes_identical_emit_output_and_cleans_tempfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            capture = directory / "captured-driver.sql"
            fake = directory / "psql"
            fake.write_text("#!/bin/sh\n[ \"$1\" = -X ] || exit 91\n[ \"$2\" = --set ] || exit 92\n[ \"$3\" = ON_ERROR_STOP=1 ] || exit 93\n[ \"$4\" = --file ] || exit 94\ncp \"$5\" \"$CAPTURE_DRIVER\"\nprintf '%s' \"$5\" > \"$CAPTURE_PATH\"\n")
            fake.chmod(0o755)
            result = subprocess.run(["sh", str(ROOT / "scripts/dev/migrate_sql.sh")],
                env={**os.environ, "PATH":str(directory)+os.pathsep+os.environ["PATH"],
                     "CAPTURE_DRIVER":str(capture), "CAPTURE_PATH":str(directory/"path")},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(capture.read_text(), self.emit().stdout)
            self.assertFalse(Path((directory/"path").read_text()).exists())

    def test_fixed_transaction_contract_is_audited(self):
        import re
        for path in migration_files(ROOT / "db/migrations"):
            body = path.read_text()
            outer = re.findall(r"(?m)^(BEGIN|COMMIT);$", body)
            self.assertEqual(outer, ["BEGIN", "COMMIT"] if int(path.name[:3]) >= 36 else [])
            markers = re.findall(r"VALUES\s*\('([0-9]{3}_[a-z0-9_]+)'\)", body)
            self.assertEqual(markers, [] if path.name.startswith("033_") else [path.stem])

    def test_adapter_streams_one_driver_and_returns_only_actual_applications(self):
        emitted = subprocess.CompletedProcess([], 0, "driver SQL", "")
        applied = subprocess.CompletedProcess([], 0, "AUTODATA_SKIPPED 001_extensions.sql\nAUTODATA_APPLIED 002_platform_spine.sql\n", "notice")
        for command in (["psql"], ["docker", "compose", "exec", "-T", "postgres", "psql"]):
            with self.subTest(command=command), patch("migrate.psql_command", return_value=command), patch("migrate.subprocess.run", side_effect=[emitted, applied]) as run, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(apply_migrations(ROOT), ["002_platform_spine.sql"])
                self.assertEqual(run.call_count, 2)
                self.assertEqual(run.call_args.kwargs["input"], "driver SQL")
                self.assertEqual(run.call_args.args[0][-5:], ["-X", "--set", "ON_ERROR_STOP=1", "--file", "-"])

    def test_adapter_propagates_generator_and_psql_failure(self):
        for results in ([subprocess.CompletedProcess([], 1, "", "manifest rejected")],
                        [subprocess.CompletedProcess([], 0, "driver", ""), subprocess.CompletedProcess([], 3, "", "ledger rejected")]):
            with patch("migrate.subprocess.run", side_effect=results), contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(RuntimeError, "rejected"):
                apply_migrations(ROOT)


if __name__ == "__main__":
    unittest.main()
