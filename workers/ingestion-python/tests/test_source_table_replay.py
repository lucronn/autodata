"""Retained HTML replay with synthetic storage and exact published-anchor checks."""

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from autodata_ingestion.article_document import build_ordered_document
from autodata_ingestion.article_lifecycle_store import (
    store_captured_source, upsert_article_descriptor,
)
from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext, digest_json
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
from autodata_ingestion.source_job_persistence import claim_source_job, ensure_article_job, fail_source_job
from autodata_ingestion.source_revision_reprojection import apply_table_reprojection
from autodata_ingestion.source_table_replay import preview_table_replay, restore_table_spans
from lifecycle_support import apply_migration, fresh_database, seed_snapshot, seed_vehicle
from test_source_revision_reprojection import reprojection_cli


TABLE = b"""<table><thead><tr><th colspan="2">Fastener location</th><th>Torque</th></tr></thead>
<tbody><tr><th rowspan="2">Cover</th><td>Upper</td><td>25 Nm</td></tr>
<tr><td>Lower</td><td>12 Nm</td></tr></tbody></table>"""
BODY = b"<p>Measure the fasteners before installation.</p>" + TABLE + b"<p>Review the completed work.</p>"


def legacy_doc(payload=BODY):
    legacy = ArticleParser()
    legacy.feed(payload.decode())
    legacy.close()
    return build_ordered_document({"evidence_ids": ["fixture"]}, legacy.blocks)


def test_restore_spans_keeps_the_document_except_for_verified_cells():
    document = legacy_doc()
    expected = deepcopy(document)
    rows = expected["blocks"][1]["rows"]
    rows[0][0] = {"text": "Fastener location", "colspan": 2}
    rows[1][0] = {"text": "Cover", "rowspan": 2}
    assert restore_table_spans(document, BODY) == expected
    assert document == legacy_doc()


@pytest.mark.parametrize("damage", ("changed_value", "reordered_cells", "extra_table", "absent_spans", "ambiguous"))
def test_restore_spans_refuses_any_unbound_cell_or_table(damage):
    document, body = legacy_doc(), BODY
    if damage == "changed_value":
        document["blocks"][1]["rows"][1][-1] = "30 Nm"
    elif damage == "reordered_cells":
        document["blocks"][1]["rows"][1].reverse()
    elif damage == "extra_table":
        body += TABLE
    elif damage == "absent_spans":
        body = body.replace(b' colspan="2"', b"").replace(b' rowspan="2"', b"")
    else:
        body += TABLE.replace(b' colspan="2"', b"")
        document = legacy_doc(body)
    with pytest.raises(ValueError, match=r"SOURCE_TABLE_REPLAY_(?:CELL_DRIFT|TABLE_DRIFT|UNCHANGED|AMBIGUOUS_TABLE)"):
        restore_table_spans(document, body)


class Objects:
    def __init__(self):
        self.data = {}
        self.reads = 0
        self.seeding = True

    def put_object(self, key, payload, _media_type):
        assert self.seeding
        self.data[key] = payload

    def get_object(self, key, *, max_bytes):
        self.reads += 1
        assert len(self.data[key]) <= max_bytes
        return self.data[key]


def seed_legacy(repo, *, partial):
    key = ArticleKey("bankone", seed_vehicle(repo), None, "fixture-vehicle", "fixture-article")
    descriptor = {"resource_ref": "body", "title": "Synthetic table"}
    if partial:
        descriptor["asset_resource_refs"] = ["missing-figure"]
    descriptor_id = seed_snapshot(repo, b"fixture descriptor")
    resolution_id = seed_snapshot(repo, b"fixture resolution")
    owner = upsert_article_descriptor(repo, key, descriptor, descriptor_id, 0,
        rewrite_profile_version="technical-prose-v1")
    context = SourceArticleContext(key, {"year": 2020, "make": "Example", "model": "Car"},
        descriptor, descriptor_id, resolution_id, ("fixture-evidence",))
    envelope = SourceEnvelopeV1(
        str(uuid4()), key.provider, "fixture-revision", datetime.now(UTC).isoformat(), "fixture:table",
        {"kind": "article", "media_type": "text/html", "sha256": sha256(BODY).hexdigest()}, raw_resource=BODY,
    )

    class Connector:
        provider = key.provider

        def read_resource(self, ref, *, timeout):
            assert timeout > 0
            if partial and ref == "missing-figure":
                raise SourceConnectorError("SOURCE_NOT_FOUND", status=404)
            assert ref == "body"
            return envelope

    objects = Objects()
    captured = capture_source_article(context, registry={key.provider: Connector()}, object_store=objects)
    assert captured.projection_status == ("partial" if partial else "readable")
    ensure = ensure_article_job(repo, owner, normalization_version="ordered-article-v1",
                                rewrite_profile_version="technical-prose-v1")
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=ensure.job_id)
    source_revision = store_captured_source(repo, lease, captured)
    fail_source_job(repo, lease, code="FIXTURE_FINISHED", retryable=False)
    objects.seeding = False
    return owner, source_revision, objects


def source_state(repo, owner):
    with repo.connect() as conn:
        return conn.execute("""SELECT current_source_revision_id,current_canonical_revision_id,request_generation,
            (SELECT count(*) FROM canonical_article_source_revisions WHERE canonical_article_id=%s) AS revision_count
            FROM canonical_articles WHERE canonical_article_id=%s""", (owner, owner)).fetchone()


@pytest.mark.parametrize("partial", (False, True))
def test_disposable_replay_preview_schema_gate_and_exact_atomic_apply(fresh_database, partial, reprojection_cli, capsys):
    repo = fresh_database(through=42)
    owner, source_revision, objects = seed_legacy(repo, partial=partial)
    prior = source_state(repo, owner)
    binding, capture = preview_table_replay(repo, source_revision, object_store=objects)
    assert objects.reads == 1 and source_state(repo, owner) == prior
    row = binding.row
    assert row["current_canonical_revision_id"] is None
    cli = ["--retained-table-spans", "--article-id", str(owner), "--source-revision-id", str(source_revision)]
    assert reprojection_cli.main([*cli, "--dry-run"], repo=repo, object_store=objects) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["status"] == "preview" and preview["requires_canonical_repair"] is False
    assert preview["source_observation_id"] == str(row["source_observation_id"])
    assert preview["document_sha256"] == digest_json(capture.source_document)
    assert source_state(repo, owner) == prior
    assert capture.source_document == restore_table_spans(row["source_document"], BODY)
    assert capture.resource_manifest[1:] == row["resource_manifest"][1:]
    assert capture.resource_provenance[1:] == row["resource_provenance"][1:]
    assert capture.source_images == row["source_images"]
    assert capture.source_steps == row["source_steps"] and capture.source_body == row["source_body"]
    assert capture.evidence_manifest == row["evidence_manifest"]
    assert capture.projection_status == row["projection_status"]
    assert capture.source_fingerprint != row["source_fingerprint"]
    key = row["resource_provenance"][0]["object_key"]
    objects.data[key] = BODY + b" "
    with pytest.raises(ValueError, match="BODY_MISMATCH"):
        preview_table_replay(repo, source_revision, object_store=objects)
    objects.data[key] = BODY
    with repo.connect() as conn:
        conn.execute("UPDATE source_snapshots SET takedown_status='expired' WHERE source_snapshot_id=%s",
                     (row["body_source_snapshot_id"],))
    reads = objects.reads
    with pytest.raises(ValueError, match="WITHDRAWN"):
        preview_table_replay(repo, source_revision, object_store=objects)
    assert objects.reads == reads
    with repo.connect() as conn:
        conn.execute("UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=%s",
                     (row["body_source_snapshot_id"],))
    args = {
        "object_store": objects,
        "expected_observation_id": row["source_observation_id"],
        "expected_fingerprint": row["source_fingerprint"],
        "expected_body_sha256": row["resource_manifest"][0]["sha256"],
        "expected_document_sha256": digest_json(capture.source_document),
        "actor": "fixture",
        "reason": "restore source table spans",
    }
    with pytest.raises(ValueError, match="SCHEMA_REQUIRED"):
        apply_table_reprojection(repo, owner, source_revision, **args)
    assert source_state(repo, owner) == prior
    for migration in (43, 44, 45):
        apply_migration(repo, migration)
    with pytest.raises(ValueError, match="PREVIEW_BINDING_MISMATCH"):
        apply_table_reprojection(repo, owner, source_revision,
            **{**args, "expected_document_sha256": "0" * 64})
    assert source_state(repo, owner) == prior
    result = apply_table_reprojection(repo, owner, source_revision, **args)
    assert result["status"] == "applied"
    state = source_state(repo, owner)
    assert str(state["current_source_revision_id"]) == result["source_revision_id"]
    assert state["current_canonical_revision_id"] is None
    assert state["revision_count"] == prior["revision_count"] + 1
    assert apply_table_reprojection(repo, owner, source_revision, **args)["status"] == "already_applied"
    assert source_state(repo, owner) == state
    with repo.connect() as conn:
        original = conn.execute("SELECT source_document FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                (source_revision,)).fetchone()
        view = conn.execute("SELECT content_origin,document FROM catalog_article_current WHERE canonical_article_id=%s",
                            (owner,)).fetchone()
        assert original["source_document"] == row["source_document"]
        assert view == {"content_origin": "source", "document": capture.source_document}
