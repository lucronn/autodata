from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_media_replay as replay
from autodata_ingestion.article_lifecycle_store import _remap_snapshot_references
from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext, article_id
from autodata_ingestion.source_article_capture import capture_source_article, project_document
from autodata_ingestion.source_connector_client import SourceEnvelopeV1


class _Cursor:
    def __init__(self, row, snapshots):
        self.row = row
        self.snapshots = snapshots
        self.queries = []

    def execute(self, sql, parameters):
        self.queries.append((sql, parameters))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.snapshots

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def cursor(self, *, row_factory):
        return self

    def connect(self):
        return self


class _Objects:
    def __init__(self):
        self.data = {}
        self.reads = []
        self.writes = 0

    def put_object(self, key, data, media_type):
        self.data[key] = data
        self.writes += 1

    def get_object(self, key, *, max_bytes):
        self.reads.append((key, max_bytes))
        assert 0 < len(self.data[key]) <= max_bytes
        return self.data[key]


class _Connector:
    def __init__(self, provider, body, figure=None, *, bindings=None):
        self.provider = provider
        self.resources = {"body": self._resource(body, "text/html", bindings=bindings)}
        if figure is not None:
            self.resources["figure"] = self._resource(figure, "image/png")

    def _resource(self, payload, mime, *, bindings=None):
        fields = {"kind": "asset" if mime == "image/png" else "article",
                  "media_type": mime, "sha256": sha256(payload).hexdigest()}
        if bindings is not None:
            fields.update(asset_resource_refs=["figure"], asset_bindings=bindings)
        return SourceEnvelopeV1(
            str(uuid4()), self.provider, "test-revision", datetime.now(timezone.utc).isoformat(),
            "fixture:retained", fields, raw_resource=payload,
        )

    def read_resource(self, ref, *, timeout):
        assert timeout > 0
        return self.resources[ref]


def _fixture(provider, variant="connector", *, move_image=True, embedded=False):
    if variant == "pdf":
        import random

        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        picture = Image.frombytes("RGB", (96, 96), random.Random(7).randbytes(96 * 96 * 3))
        picture.save(buffer, format="PNG")
        buffer.seek(0)
        out = BytesIO()
        document = canvas.Canvas(out)
        document.drawString(72, 720, "Remove the pump.")
        document.drawImage(ImageReader(buffer), 72, 500)
        document.showPage()
        document.drawString(72, 720, "Install the replacement.")
        document.showPage()
        document.save()
        client = _Connector(provider, b"")
        client.resources["body"] = client._resource(out.getvalue(), "application/pdf")
    else:
        client = _html_fixture(provider, variant, embedded=embedded)
    return _retained_fixture(client, move_image=move_image)


def _html_fixture(provider, variant, *, embedded):

    buffer = BytesIO()
    Image.new("RGB", (24, 24), "green").save(buffer, format="PNG")
    png = buffer.getvalue()
    bindings = None
    if embedded:
        import base64

        url = base64.b64encode(png).decode()
        image = f'<img src="data:image/png;base64,{url}" alt="Pump alignment">'
    elif variant == "binding":
        image = '<img src="/fixture/alignment" alt="Pump alignment">'
        bindings = [{"source_url": "/fixture/alignment", "resource_ref": "figure"}]
    else:
        image = '<img data-resource-ref="figure" alt="Pump alignment">'
    raw = f"<p>Remove the pump.</p>{image}<p>Install the replacement.</p>".encode()
    return _Connector(provider, raw, None if embedded else png, bindings=bindings)


def _retained_fixture(client, *, move_image):
    provider = client.provider
    context = SourceArticleContext(
        ArticleKey(provider, uuid4(), uuid4(), "fixture-vehicle", "fixture-article"),
        {"year": 2024},
        {"title": "Pump", "resource_ref": "body"},
        uuid4(), uuid4(), (),
    )
    objects = _Objects()
    captured = capture_source_article(context, registry={provider: client}, object_store=objects)
    persisted_ids = {owner["source_snapshot_id"]: str(uuid4()) for owner in captured.resources}
    provenance = _remap_snapshot_references(captured.resource_provenance, persisted_ids)
    evidence = _remap_snapshot_references(captured.evidence_manifest, persisted_ids)
    document = deepcopy(captured.source_document)
    if move_image:
        blocks = document["blocks"]
        image = blocks.pop(1)
        blocks.append(image)
        for order, block in enumerate(blocks, start=1):
            block.update(source_order=order, block_id=f"{article_id(context.key)}:block:{order:04d}")
    _, _, images = project_document(document)
    row = {
        "canonical_article_id": article_id(context.key),
        "source_revision_id": uuid4(),
        "source_observation_id": uuid4(),
        "source_fingerprint": captured.source_fingerprint,
        "body_source_snapshot_id": replay._uuid(persisted_ids[str(captured.body_source_snapshot_id)]),
        "resource_manifest": captured.resource_manifest,
        "resource_provenance": provenance,
        "evidence_manifest": evidence,
        "source_document": document,
        "source_images": images,
        "captured_at": captured.captured_at,
        "projection_status": captured.projection_status,
        "projection_version": "source-projection-v2",
        "provider_slug": provider,
        "vehicle_id": context.key.vehicle_id,
        "vehicle_configuration_id": context.key.vehicle_configuration_id,
        "source_vehicle_ref": context.key.source_vehicle_ref,
        "source_article_ref": context.key.source_article_ref,
        "membership_status": "active",
        "takedown_status": "active",
        "body_provider_revision": provenance[0]["source_revision"],
        "captured_context": {"vehicle": context.vehicle, "descriptor": context.descriptor, "evidence_ids": []},
        "descriptor_source_snapshot_id": context.descriptor_snapshot_id,
        "resolution_source_snapshot_id": context.resolution_snapshot_id,
    }
    snapshots = [{
        "source_snapshot_id": replay._uuid(resource["source_snapshot_id"]),
        "content_sha256": resource["sha256"], "object_key": resource["object_key"],
        "takedown_status": "active", "artifact_digest": resource["sha256"],
        "artifact_key": resource["object_key"], "media_type": resource["media_type"],
    } for resource in provenance]
    for id_value in (context.descriptor_snapshot_id, context.resolution_snapshot_id):
        snapshots.append({
            "source_snapshot_id": id_value, "content_sha256": "d" * 64,
            "object_key": "descriptor/fixture", "takedown_status": "active",
            "artifact_digest": None, "artifact_key": None, "media_type": None,
        })
    return _Cursor(row, snapshots), objects


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("variant", ["connector", "binding", "embedded", "pdf"])
def test_retained_replay_keeps_verified_media_and_provenance(provider, variant):
    cursor, objects = _fixture(provider, variant, embedded=variant == "embedded")
    rows_before, snapshots_before, data_before = deepcopy((cursor.row, cursor.snapshots, objects.data))
    writes_before = objects.writes

    binding, result = replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    rebuilt = replay.reproject_media_source(cursor, cursor.row["source_revision_id"], object_store=objects)

    assert result == rebuilt
    assert [block["type"] for block in result.source_document["blocks"]] == [
        "paragraph", "image", "paragraph",
    ]
    assert result.source_fingerprint == rows_before["source_fingerprint"]
    assert result.resource_manifest == rows_before["resource_manifest"]
    assert result.resource_provenance == rows_before["resource_provenance"]
    assert result.evidence_manifest == rows_before["evidence_manifest"]
    assert result.captured_at == rows_before["captured_at"]
    assert result.projection_version == replay.MEDIA_REPLAY_PROJECTION_VERSION
    assert binding.source_observation_id == rows_before["source_observation_id"]
    assert binding.canonical_article_id == rows_before["canonical_article_id"]
    assert binding.body_sha256 == rows_before["resource_manifest"][0]["sha256"]
    assert replay.media_replay_document_hash(result) != binding.source_document_hash
    assert (cursor.row, cursor.snapshots, objects.data) == (rows_before, snapshots_before, data_before)
    assert objects.writes == writes_before


@pytest.mark.parametrize("status", ["expired", "takedown"])
@pytest.mark.parametrize("snapshot_index", [0, 1, 2, 3])
def test_withdrawn_snapshot_is_denied_before_object_reads(status, snapshot_index):
    cursor, objects = _fixture("bankone")
    cursor.snapshots[snapshot_index]["takedown_status"] = status
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_WITHDRAWN$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    assert not objects.reads


def test_apply_binding_shares_locks_for_all_observed_snapshot_ids():
    cursor, _ = _fixture("bankone")
    preview = replay.load_media_replay_binding(cursor, cursor.row["source_revision_id"])
    locked = replay.load_media_replay_binding(cursor, cursor.row["source_revision_id"], lock=True)
    query, (ids,) = cursor.queries[-1]
    assert "FOR SHARE OF s" in query
    assert ids == sorted(row["source_snapshot_id"] for row in cursor.snapshots)
    assert preview == locked


@pytest.mark.parametrize("field,value,code", [
    ("projection_version", "source-projection-v3", "UNSUPPORTED"),
    ("projection_status", "partial", "UNSUPPORTED"),
    ("membership_status", "retired", "WITHDRAWN"),
    ("takedown_status", "expired", "WITHDRAWN"),
    ("source_fingerprint", "a" * 64, "FINGERPRINT_MISMATCH"),
])
def test_unsupported_or_unbound_records_do_not_read_objects(field, value, code):
    cursor, objects = _fixture("banktwo")
    cursor.row[field] = value
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_" + code + "$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    assert not objects.reads


@pytest.mark.parametrize("target", ["provider", "snapshot", "artifact_mime", "evidence", "failure"])
def test_malformed_provenance_and_manifest_fail_before_object_reads(target):
    cursor, objects = _fixture("bankone")
    if target == "provider":
        cursor.row["resource_provenance"][1]["provider"] = "banktwo"
    elif target == "snapshot":
        cursor.row["resource_provenance"][1]["source_snapshot_id"] = str(uuid4())
    elif target == "artifact_mime":
        cursor.snapshots[1]["media_type"] = "image/gif"
    elif target == "evidence":
        cursor.row["evidence_manifest"][0]["evidence_id"] = "forged-evidence"
    else:
        cursor.row["resource_manifest"][1]["failure_code"] = "SOURCE_NOT_FOUND"
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_(BINDING_MISMATCH|UNSUPPORTED)$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    assert not objects.reads


def test_modified_and_missing_retained_objects_are_rejected():
    cursor, objects = _fixture("bankone")
    asset_key = cursor.row["resource_provenance"][1]["object_key"]
    objects.data[asset_key] += b"tampered"
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    del objects.data[asset_key]
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_OBJECT_UNAVAILABLE$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def test_replay_rejects_unchanged_projection():
    cursor, objects = _fixture("bankone", move_image=False)
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_UNCHANGED$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def test_replay_rejects_pending_read_at_deadline():
    cursor, objects = _fixture("bankone")
    release = Event()

    def wait_for_release(*_, **__):
        release.wait(2)
        raise AssertionError("still blocked")

    try:
        with patch.object(objects, "get_object", side_effect=wait_for_release):
            with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_DEADLINE$"):
                replay.preview_media_replay(
                    cursor, cursor.row["source_revision_id"], object_store=objects, deadline_seconds=0.05,
                )
    finally:
        release.set()


def test_replay_rejects_drift_in_protected_text():
    cursor, objects = _fixture("bankone")
    cursor.row["source_document"]["blocks"][0]["text"] = "Detach the seal."
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_TEXT_DRIFT$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def test_apply_revalidates_media_and_projections():
    cursor, objects = _fixture("banktwo")
    binding, captured = replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    wrong_images = [dict(captured.source_images[0], caption="changed")]
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_PROJECTION_DRIFT$"):
        replay.validate_media_replay_result(binding, replace(captured, source_images=wrong_images))
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_BINDING_MISMATCH$"):
        replay.validate_media_replay_result(binding, replace(captured, resources=()))
