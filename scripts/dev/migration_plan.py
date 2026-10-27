"""Inspect the ordered, reversible foundation migration set."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))


REQUIRED_TABLES = (
    "dataset_products",
    "dataset_requests",
    "dataset_projections",
    "dataset_revisions",
    "dataset_section_status",
    "entitlements",
    "source_snapshots",
    "ingestion_jobs",
    "extraction_runs",
    "extraction_evidence",
    "publication_events",
    "feedback_items",
    "payment_events",
)


def migration_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))


def fixture_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))


def validate_migration_set(directory: Path) -> list[str]:
    paths = migration_files(directory)
    if not paths:
        return ["no numbered migration files found"]

    errors: list[str] = []
    versions = [path.name[:3] for path in paths]
    if versions != sorted(set(versions)):
        errors.append("migration versions must be unique and ordered")

    sql = "\n".join(path.read_text() for path in paths)
    if "CREATE EXTENSION IF NOT EXISTS vector" not in sql:
        errors.append("pgvector extension is not enabled")
    for table in REQUIRED_TABLES:
        if not re.search(rf"CREATE TABLE IF NOT EXISTS {table}\b", sql):
            errors.append(f"missing platform table: {table}")
    if "prevent_published_revision_mutation" not in sql:
        errors.append("published revision immutability trigger is not defined")
    return errors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspect and validate ordered migration set")
    parser.add_argument(
        "--migrations-dir",
        default=None,
        help="Path to migrations directory (defaults to db/migrations)",
    )
    args = parser.parse_args(argv)
    target_dir = Path(args.migrations_dir) if args.migrations_dir else ROOT / "db/migrations"
    errors = validate_migration_set(target_dir)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
    paths = migration_files(target_dir)
    print(f"validated {len(paths)} migrations in {target_dir}")


if __name__ == "__main__":
    main()
