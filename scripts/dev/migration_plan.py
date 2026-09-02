"""Inspect the ordered, reversible foundation migration set."""

from __future__ import annotations

import re
from pathlib import Path


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
