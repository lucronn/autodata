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


_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="green"/></svg>'


class _Cursor:
    def __init__(self, row, snapshots):
        self.row = row
        self.snapshots = snapshots
        self.reviews = []
        self.queries = []

    def execute(self, sql, parameters):
        self.queries.append((sql, parameters))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        sql, (ids,) = self.queries[-1]
        if "FROM source_review_items" in sql:
            return [
                review for review in self.reviews
                if review["item_kind"] == "quarantine" and set(review["source_snapshot_ids"]).intersection(ids)
            ]
        if "FROM source_artifacts" in sql:
            return [{
                "source_snapshot_id": row["source_snapshot_id"],
                "content_sha256": row["artifact_digest"],
                "object_key": row["artifact_key"],
                "media_type": row["media_type"],
                "extraction_status": row["extraction_status"],
            } for row in self.snapshots if row["source_snapshot_id"] in ids]
        return [row for row in self.snapshots if row["source_snapshot_id"] in ids]

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
        fields = {"kind": "asset" if mime.startswith("image/") else "article",
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
        "extraction_status": "candidate_ready",
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


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("svg", [False, True])
def test_replay_and_published_repair_move_detached_figure_into_existing_item(provider, svg):
    from autodata_ingestion.procedure_rewrite_auto import render_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.published_media_repair import repair_published_media

    buffer = BytesIO()
    Image.new("RGB", (24, 24), "green").save(buffer, format="PNG")
    raw = (
        b'<ol><li>Remove the pump.<img data-resource-ref="figure"></li>'
        b'<li>Install the cover.</li></ol>'
    )
    client = _Connector(provider, raw, buffer.getvalue())
    if svg:
        client.resources["figure"] = client._resource(_SVG, "image/svg+xml")
    cursor, objects = _retained_fixture(client, move_image=False)
    old_document = cursor.row["source_document"]
    [old_list] = old_document["blocks"]
    first, second = old_list["items"]
    [figure] = first["blocks"]
    old_list["items"] = [first["text"], second]
    figure.update(block_id=old_list["block_id"].removesuffix("0001") + "0002", source_order=2)
    old_document["blocks"].append(figure)
    _, _, cursor.row["source_images"] = project_document(old_document)
    before = deepcopy((cursor.row, objects.data, objects.writes))
    prompt_version = "full-prose-auto-prompt-v7"
    response = {
        "introduction": "This procedure covers pump and cover service.",
        "replacements": [
            {**slot, "action": "rewrite", "reason": "", "text": text}
            for slot, text in zip(
                prose_slots(old_document), ["Take the pump off.", "Fit the cover in place."], strict=True,
            )
        ],
    }
    published = render_auto(old_document, response, prompt_version=prompt_version)

    binding, captured = replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    repaired = repair_published_media(
        old_document, published, captured.source_document, response=response, prompt_version=prompt_version,
    )

    first_after, second_after = repaired.document["blocks"][1]["items"]
    assert first_after["text"] == "Take the pump off."
    assert second_after == "Fit the cover in place."
    [placed] = first_after["blocks"]
    assert placed["content_sha256"] == figure["content_sha256"]
    assert placed["evidence_ids"] == figure["evidence_ids"]
    assert repaired.validation.passed
    assert captured.source_fingerprint == binding.source_fingerprint
    assert (cursor.row, objects.data, objects.writes) == before

    old_list["items"].reverse()
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_TEXT_DRIFT$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


@pytest.mark.parametrize("kind,field", [("ordered_list", "items"), ("table", "rows"), ("table", "columns")])
def test_block_inventory_keeps_empty_protected_containers(kind, field):
    base = {"blocks": [{"type": kind}]}
    with_empty = {"blocks": [{"type": kind, field: []}]}
    assert replay._block_inventory(base, "text/html") != replay._block_inventory(with_empty, "text/html")


def test_block_inventory_keeps_intentional_empty_item_blocks():
    flat = {"blocks": [{"type": "ordered_list", "items": ["Remove the pump."]}]}
    empty = {"blocks": [{"type": "ordered_list", "items": [{"text": "Remove the pump.", "blocks": []}]}]}
    assert replay._block_inventory(flat, "text/html") != replay._block_inventory(empty, "text/html")


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
    snapshot_query, (snapshot_ids,) = cursor.queries[-3]
    artifact_query, (artifact_ids,) = cursor.queries[-2]
    review_query, (review_ids,) = cursor.queries[-1]
    assert "FOR SHARE OF s" in snapshot_query
    assert snapshot_ids == sorted(row["source_snapshot_id"] for row in cursor.snapshots)
    assert "FOR SHARE OF a" in artifact_query
    assert artifact_ids == sorted(row["source_snapshot_id"] for row in cursor.snapshots[:2])
    assert "FOR SHARE OF q" in review_query
    assert review_ids == sorted(map(str, {*artifact_ids, cursor.row["descriptor_source_snapshot_id"]}))
    assert preview == locked


@pytest.mark.parametrize("index", [0, 1])
def test_quarantined_resource_is_denied_before_read_and_at_apply(index):
    cursor, objects = _fixture("bankone")
    cursor.snapshots[index]["extraction_status"] = "quarantined"
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_QUARANTINED$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_QUARANTINED$"):
        replay.load_media_replay_binding(cursor, cursor.row["source_revision_id"], lock=True)
    assert not objects.reads


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


@pytest.mark.parametrize("deadline", [0, 31, float("nan"), float("inf"), True, "5"])
def test_replay_rejects_invalid_deadline_without_work(deadline):
    cursor, objects = _fixture("bankone")
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_DEADLINE_INVALID$"):
        replay.preview_media_replay(
            cursor, cursor.row["source_revision_id"], object_store=objects, deadline_seconds=deadline,
        )
    assert not cursor.queries and not objects.reads


def test_replay_rejects_reordered_html_text():
    cursor, objects = _fixture("bankone")
    blocks = cursor.row["source_document"]["blocks"]
    blocks[0]["text"], blocks[1]["text"] = blocks[1]["text"], blocks[0]["text"]
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_TEXT_DRIFT$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def _retained_numbered_list(provider, *, reversed_list=False):
    start = b'<ol reversed start="4">' if reversed_list else b'<ol start="4">'
    cursor, objects = _retained_fixture(_Connector(provider, start + (
        b'<li>Remove the pump.</li><li value="9">Inspect the cover.</li>'
        b'<li>Install the cover.</li></ol>'
    )), move_image=False)
    block, = cursor.row["source_document"]["blocks"]
    block.pop("start")
    block["items"][1] = block["items"][1]["text"]
    return cursor, objects


@pytest.mark.parametrize(("provider", "version"), [
    ("bankone", "source-projection-v2"),
    ("banktwo", "source-projection-v3"),
])
def test_retained_numbered_list_replays_without_image_or_writes(provider, version):
    cursor, objects = _retained_numbered_list(provider)
    cursor.row["projection_version"] = version
    before = deepcopy(cursor.row)
    writes = objects.writes
    with pytest.raises(ValueError, match="SOURCE_MEDIA_REPLAY_UNSUPPORTED"):
        replay.preview_media_replay(cursor, before["source_revision_id"], object_store=objects)
    binding, captured = replay.preview_media_replay(
        cursor, before["source_revision_id"], object_store=objects, ordinals=True,
    )
    assert captured.projection_version == "source-projection-v4"
    assert [step["number"] for step in captured.source_steps] == [4, 9, 10]
    assert binding.source_fingerprint == captured.source_fingerprint == before["source_fingerprint"]
    assert captured.source_images == []
    assert len(objects.reads) == 1 and objects.writes == writes and cursor.row == before


@pytest.mark.parametrize("mutation", ["text", "order", "existing_ordinal", "warning", "step_number"])
def test_retained_numbered_list_refuses_other_changes(mutation):
    cursor, objects = _retained_numbered_list("banktwo")
    block, = cursor.row["source_document"]["blocks"]
    if mutation == "text":
        block["items"][0] = "Remove the fuel pump."
    elif mutation == "order":
        block["items"][0], block["items"][1] = block["items"][1], block["items"][0]
    elif mutation == "existing_ordinal":
        block["items"][1] = {"text": block["items"][1], "number": 8}
    elif mutation == "warning":
        block["items"][0] = {"text": block["items"][0], "blocks": [{
            "type": "callout", "label": "Warning", "text": "Depressurize the line first.",
        }]}
    elif mutation == "step_number":
        block["items"][0] = {"text": block["items"][0], "blocks": [{
            "type": "step", "number": 2, "text": "Isolate the system.",
        }]}
    with pytest.raises(ValueError, match="SOURCE_MEDIA_REPLAY_ORDINAL_DRIFT"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects, ordinals=True)


def test_retained_numbered_list_refuses_reversed_markup():
    cursor, objects = _retained_numbered_list("banktwo", reversed_list=True)
    with pytest.raises(ValueError, match="SOURCE_MEDIA_REPLAY_UNSUPPORTED"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects, ordinals=True)


def _retained_svg(provider="bankone", *, ordinals=False):
    bindings = None
    if provider == "banktwo":
        image = b'<img src="/fixture/alignment" alt="Pump alignment">'
        bindings = [{"source_url": "/fixture/alignment", "resource_ref": "figure"}]
    else:
        image = b'<img data-resource-ref="figure" alt="Pump alignment">'
    if ordinals:
        raw = (
            b'<ol start="4"><li>Remove the pump.' + image
            + b'</li><li value="9">Install the cover.</li></ol>'
        )
    else:
        raw = b"<p>Remove the pump.</p>" + image + b"<p>Install the cover.</p>"
    client = _Connector(provider, raw, bindings=bindings)
    client.resources["figure"] = client._resource(_SVG, "image/svg+xml")
    cursor, objects = _retained_fixture(client, move_image=not ordinals)
    if ordinals:
        [block] = cursor.row["source_document"]["blocks"]
        block.pop("start")
        block["items"][1] = block["items"][1]["text"]
        cursor.row["projection_version"] = "source-projection-v3"
    return cursor, objects


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("ordinals", [False, True])
def test_retained_svg_requires_exact_png_rendition_and_preserves_figure(provider, ordinals):
    cursor, objects = _retained_svg(provider, ordinals=ordinals)
    before = deepcopy((cursor.row, cursor.snapshots, objects.data, objects.writes))
    body, original, derivative = cursor.row["resource_provenance"]
    assert original["role"] == "asset_original"
    assert derivative["derived_from_sha256"] == original["sha256"]
    assert derivative["derivation_version"] == replay.RASTERIZER_VERSION
    assert objects.data[original["object_key"]] == _SVG
    with Image.open(BytesIO(objects.data[derivative["object_key"]])) as png:
        assert png.format == "PNG" and png.getpixel((12, 12))[:3] == (0, 128, 0)

    binding, captured = replay.preview_media_replay(
        cursor, cursor.row["source_revision_id"], object_store=objects, ordinals=ordinals,
    )

    assert [key for key, _ in objects.reads] == [
        resource["object_key"] for resource in (body, original, derivative)
    ]
    assert captured.resource_manifest == before[0]["resource_manifest"]
    assert captured.resource_provenance == before[0]["resource_provenance"]
    assert captured.source_fingerprint == binding.source_fingerprint
    [image] = captured.source_images
    assert image["content_sha256"] == derivative["sha256"]
    assert image["media_type"] == "image/png"
    if ordinals:
        assert captured.projection_version == "source-projection-v4"
        assert [step["number"] for step in captured.source_steps] == [4, 9]
        assert captured.source_images == before[0]["source_images"]
    else:
        assert captured.projection_version == "source-projection-v3"
        assert [block["type"] for block in captured.source_document["blocks"]] == [
            "paragraph", "image", "paragraph",
        ]
    assert (cursor.row, cursor.snapshots, objects.data, objects.writes) == before


@pytest.mark.parametrize(("mutation", "code"), [
    ("orphan_original", "UNSUPPORTED"),
    ("orphan_derivative", "UNSUPPORTED"),
    ("wrong_version", "UNSUPPORTED"),
    ("wrong_digest", "BINDING_MISMATCH"),
    ("wrong_ref", "BINDING_MISMATCH"),
    ("wrong_request", "BINDING_MISMATCH"),
])
def test_retained_svg_rejects_unbound_derivative_before_object_reads(mutation, code):
    cursor, objects = _retained_svg()
    manifest = cursor.row["resource_manifest"]
    provenance = cursor.row["resource_provenance"]
    if mutation == "orphan_original":
        manifest.pop()
        provenance.pop()
    elif mutation == "orphan_derivative":
        manifest.pop(1)
        provenance.pop(1)
    elif mutation == "wrong_version":
        manifest[2]["derivation_version"] = provenance[2]["derivation_version"] = "unknown-rasterizer"
    elif mutation == "wrong_digest":
        manifest[2]["derived_from_sha256"] = provenance[2]["derived_from_sha256"] = "f" * 64
    elif mutation == "wrong_ref":
        manifest[2]["opaque_ref"] = provenance[2]["opaque_ref"] = "another-figure"
    else:
        provenance[2]["request_id"] = str(uuid4())
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_" + code + "$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    assert not objects.reads


@pytest.mark.parametrize("resource_index", [1, 2])
def test_retained_svg_rejects_tampered_object(resource_index):
    cursor, objects = _retained_svg()
    key = cursor.row["resource_provenance"][resource_index]["object_key"]
    objects.data[key] += b"tampered"
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def test_retained_svg_rejects_changed_rasterizer_output():
    cursor, objects = _retained_svg()
    buffer = BytesIO()
    Image.new("RGB", (24, 24), "red").save(buffer, format="PNG")
    writes = objects.writes
    with patch(
        "autodata_ingestion.source_article_capture.rasterize_svg", return_value=buffer.getvalue(),
    ) as rasterize:
        # Ordinary capture treats the rejected sink write as a failed derivative.
        with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_BINDING_MISMATCH$"):
            replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    assert rasterize.call_args.args == (_SVG,)
    assert objects.writes == writes


@pytest.mark.parametrize(("snapshot_index", "field", "status", "code"), [
    (1, "takedown_status", "takedown", "WITHDRAWN"),
    (2, "extraction_status", "quarantined", "QUARANTINED"),
    (1, "review", "rejected", "QUARANTINED"),
    (2, "review", "pending", "QUARANTINED"),
])
def test_retained_svg_checks_rights_for_both_objects_before_read_and_at_apply(snapshot_index, field, status, code):
    cursor, objects = _retained_svg()
    snapshot = cursor.snapshots[snapshot_index]
    if field == "review":
        cursor.reviews.append({
            "item_kind": "quarantine", "status": status,
            "source_snapshot_ids": [str(snapshot["source_snapshot_id"])],
        })
    else:
        snapshot[field] = status
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_" + code + "$"):
        replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_" + code + "$"):
        replay.load_media_replay_binding(cursor, cursor.row["source_revision_id"], lock=True)
    assert not objects.reads


def test_review_quarantine_uses_retained_article_scope_and_approval():
    cursor, objects = _fixture("bankone")
    cursor.reviews.extend([
        {"item_kind": "quarantine", "status": "approved",
         "source_snapshot_ids": [str(cursor.row["descriptor_source_snapshot_id"])]},
        {"item_kind": "conflict", "status": "pending",
         "source_snapshot_ids": [cursor.row["resource_provenance"][0]["source_snapshot_id"]]},
        {"item_kind": "quarantine", "status": "pending", "source_snapshot_ids": [str(uuid4())]},
    ])
    replay.preview_media_replay(cursor, cursor.row["source_revision_id"], object_store=objects)
    cursor.reviews[0]["status"] = "pending"
    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_QUARANTINED$"):
        replay.load_media_replay_binding(cursor, cursor.row["source_revision_id"], lock=True)
