"""Isolated PostgreSQL fixture: never connects to an application database."""

from dataclasses import dataclass
from pathlib import Path
import os
import uuid
import hashlib
import pytest
import psycopg
from psycopg.rows import dict_row
from psycopg import sql

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Repository:
    database_name: str

    def connect(self):
        if os.environ.get(
            "AUTODATA_LIFECYCLE_TEST"
        ) != "1" or not self.database_name.startswith("lifecycle_test_"):
            raise RuntimeError("isolated lifecycle fixture required")
        return psycopg.connect(
            host="postgres",
            dbname=self.database_name,
            user="lifecycle_test",
            password="lifecycle_test_only",
            row_factory=dict_row,
        )


def apply_migration(repo, number):
    (path,) = (ROOT / "db/migrations").glob(f"{number:03d}_*.sql")
    with repo.connect() as conn:
        conn.autocommit = True
        conn.execute(path.read_text())


@pytest.fixture
def fresh_database():
    if os.environ.get("AUTODATA_LIFECYCLE_TEST") != "1":
        pytest.skip("requires isolated lifecycle Compose runner")
    names = []

    def fresh(through=None):
        name = "lifecycle_test_" + uuid.uuid4().hex
        with psycopg.connect(
            host="postgres",
            dbname="lifecycle_fixture",
            user="lifecycle_test",
            password="lifecycle_test_only",
            autocommit=True,
        ) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        names.append(name)
        repo = Repository(name)
        for path in sorted((ROOT / "db/migrations").glob("*.sql")):
            number = int(path.name.split("_")[0])
            if through is None or number <= through:
                apply_migration(repo, number)
        return repo

    yield fresh
    for name in names:
        with psycopg.connect(
            host="postgres",
            dbname="lifecycle_fixture",
            user="lifecycle_test",
            password="lifecycle_test_only",
            autocommit=True,
        ) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def seed_snapshot(repo, payload=b"fixture"):
    digest = hashlib.sha256(payload).hexdigest()
    with repo.connect() as conn:
        return conn.execute(
            """INSERT INTO source_snapshots(adapter_name, source_uri, source_version, content_sha256, object_key, license_metadata, retrieved_at)
        VALUES ('fixture','fixture://source','v1',%s,%s,'{}',now()) ON CONFLICT(content_sha256) DO UPDATE SET content_sha256=EXCLUDED.content_sha256 RETURNING source_snapshot_id""",
            (digest, "sources/" + digest),
        ).fetchone()["source_snapshot_id"]


def seed_vehicle(repo):
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        return conn.execute(
            "INSERT INTO vehicles(vehicle_key,make,model,model_year,region,source_snapshot_id,source_watermark) VALUES (%s,'Example','Car',2024,'US',%s,'v1') RETURNING vehicle_id",
            (uuid.uuid4().hex, snapshot),
        ).fetchone()["vehicle_id"]


def insert_descriptor(repo, key, **kwargs):
    from autodata_ingestion.article_lifecycle_store import upsert_article_descriptor

    return upsert_article_descriptor(
        repo,
        key,
        kwargs.get("descriptor", {"title": "Pump", "body_resource_ref": "body"}),
        seed_snapshot(repo),
        kwargs.get("generation", 0),
    )


def seed_legacy_jobs_and_read_invariants(repo):
    vehicle = seed_vehicle(repo)
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        for status in (
            "pending",
            "processing",
            "completed",
            "needs_review",
            "failed",
            "dead_letter",
        ):
            conn.execute(
                """INSERT INTO autoapi_article_fetch_jobs(vehicle_id,vehicle_key,source_location,selector_source_snapshot_id,source_snapshot_id,source_version,adapter_name,idempotency_key,status,attempt_count)
            VALUES (%s,'opaque:vehicle','fixture://legacy',%s,%s,'v1','autoapi',%s,%s,2)""",
                (vehicle, snapshot, snapshot, "legacy:" + status, status),
            )
        return conn.execute(
            "SELECT autoapi_article_fetch_job_id AS id,idempotency_key,vehicle_id,attempt_count AS retries,status,selector_source_snapshot_id,source_snapshot_id,source_location FROM autoapi_article_fetch_jobs ORDER BY idempotency_key"
        ).fetchall()


def read_imported_job_invariants(repo):
    with repo.connect() as conn:
        return conn.execute(
            "SELECT source_fetch_job_id AS id,idempotency_key,canonical_vehicle_id AS vehicle_id,retry_count AS retries,status,selector_source_snapshot_id,source_snapshot_id,source_locator AS source_location FROM source_fetch_jobs WHERE job_kind='legacy_batch' ORDER BY idempotency_key"
        ).fetchall()


def seed_configuration(repo, vehicle):
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        evidence = conn.execute(
            "INSERT INTO extraction_evidence(source_snapshot_id,locator,artifact_key,extracted_text,confidence,reviewer_state) VALUES (%s,'fixture','fixture','fixture',1,'approved') RETURNING extraction_evidence_id",
            (snapshot,),
        ).fetchone()["extraction_evidence_id"]
        base = conn.execute(
            "INSERT INTO vehicle_identity_bases(canonical_base_key,vehicle_id,make,model,model_year,region,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES (%s,%s,'Example','Car',2024,'US',%s,%s,'fixture','fixture',1,'approved') RETURNING vehicle_identity_base_id",
            (uuid.uuid4().hex, vehicle, snapshot, evidence),
        ).fetchone()["vehicle_identity_base_id"]
        return conn.execute(
            "INSERT INTO vehicle_configurations(configuration_key,vehicle_identity_base_id,vehicle_id,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES (%s,%s,%s,%s,%s,'fixture','fixture',1,'approved') RETURNING vehicle_configuration_id",
            (uuid.uuid4().hex, base, vehicle, snapshot, evidence),
        ).fetchone()["vehicle_configuration_id"]
