from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from autodata_ingestion import source_bankone_order_replay as replay
from autodata_ingestion.article_lifecycle_types import BANKONE_HTML_FLOW_LAYOUT, HTML_TABLE_SPAN_LAYOUT
from autodata_ingestion.source_article_capture import WORKSHOP_CAPTURE_OPTIONS, project_document
from test_source_media_replay import _Connector, _retained_fixture


_BODY = b"""
<p>Service notes.</p>
<ul><li>Inspect the cover.</li><p>Keep the seal in place.</p><li>Fit the bracket.</li></ul>
<mtr-image id="71" alt="Bracket location"></mtr-image>
<table><thead><tr><th colspan="2">Fastener location</th><th>Torque</th></tr></thead>
<tbody><tr><th rowspan="2">Cover</th><td>Upper</td><td>25 Nm</td></tr>
<tr><td>Lower</td><td>12 Nm</td></tr></tbody></table>
<p>Review the completed work.</p>
<mtr-image id="72" alt="Cover fasteners"></mtr-image>
"""


@pytest.fixture
def retained_bankone(monkeypatch):
    connector = _Connector("bankone", _BODY)
    raster = {}
    locators = {}
    for number in (71, 72):
        ref = f"graphic-{number}"
        locator = "bankone:asset:" + sha256(f'{{"kind":"graphic","id":"{number}"}}'.encode()).hexdigest()[:24]
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{number}" height="1"/>'.encode()
        stream = BytesIO()
        Image.new("RGB", (number, 1), "green").save(stream, format="PNG")
        raster[svg] = stream.getvalue()
        locators[locator] = ref
        connector.resources[ref] = replace(
            connector._resource(svg, "image/svg+xml"), source_locator=locator,
        )
    refs = list(locators.values())
    body = connector.resources["body"]
    connector.resources["body"] = replace(
        body, body={**body.body, "asset_resource_refs": refs},
    )
    monkeypatch.setattr("autodata_ingestion.source_article_capture.rasterize_svg",
                        lambda svg, *, timeout: raster[svg])
    cursor, objects = _retained_fixture(
        connector, move_image=False, descriptor={"asset_resource_refs": refs}, evidence_ids=("fixture",),
        capture_options={**WORKSHOP_CAPTURE_OPTIONS, "keep_bankone_html_flow": False},
    )
    cursor.row.update(
        projection_version="source-projection-v5", current_canonical_revision_id=uuid4(),
    )

    def allowed(_, article, source_revision_id):
        return article["source_revision_id"] == source_revision_id

    monkeypatch.setattr(replay, "source_bound_rewrite_source_allowed", allowed)
    return cursor, objects, locators


def _preview(cursor, objects):
    return replay.preview_bankone_order_replay(cursor, cursor.row["source_revision_id"], object_store=objects)


def test_retained_replay_restores_the_authored_flow_and_exact_figures(retained_bankone):
    cursor, objects, locators = retained_bankone
    before = deepcopy((cursor.row, cursor.snapshots, objects.data, objects.writes))

    binding, captured = _preview(cursor, objects)

    assert (cursor.row, cursor.snapshots, objects.data, objects.writes) == before
    assert [key for key, _ in objects.reads] == [
        resource["object_key"] for resource in binding.resource_provenance
    ]
    assert binding.resource_manifest[0]["html_table_span_layout"] == HTML_TABLE_SPAN_LAYOUT
    assert captured.resource_manifest[0] == {
        **binding.resource_manifest[0],
        "bankone_graphic_position_bindings": locators,
        "bankone_html_flow_layout": BANKONE_HTML_FLOW_LAYOUT,
    }
    assert captured.body_source_snapshot_id == binding.body_source_snapshot_id
    assert captured.evidence_manifest == list(binding.evidence_manifest)
    assert [row["source_snapshot_id"] for row in captured.resource_provenance] == [
        row["source_snapshot_id"] for row in binding.resource_provenance
    ]
    assert binding.source_body.index("Keep the seal in place.") < binding.source_body.index("Inspect the cover.")
    assert captured.source_body.index("Inspect the cover.") < captured.source_body.index("Keep the seal in place.")
    assert [image["alt"] for image in captured.source_images] == ["Bracket location", "Cover fasteners"]
    assert captured.source_images[0]["source_order"] < binding.source_images[0]["source_order"]
    assert [image["content_sha256"] for image in captured.source_images] == [
        image["content_sha256"] for image in binding.source_images
    ]


def test_denied_snapshot_stops_before_object_reads(retained_bankone):
    cursor, objects, _ = retained_bankone
    cursor.snapshots[2]["takedown_status"] = "withdrawn"

    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_WITHDRAWN$"):
        _preview(cursor, objects)

    assert not objects.reads


def test_replay_rejects_tampered_retained_bytes(retained_bankone):
    cursor, objects, _ = retained_bankone
    png = cursor.row["resource_provenance"][2]
    objects.data[png["object_key"]] += b"modified"

    with pytest.raises(ValueError, match="^SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH$"):
        _preview(cursor, objects)


@pytest.mark.parametrize("mutation", ["procedure", "figure_order"])
def test_revalidation_rejects_drift_in_an_apparently_readable_successor(retained_bankone, mutation):
    cursor, objects, _ = retained_bankone
    binding, captured = _preview(cursor, objects)
    document = deepcopy(captured.source_document)
    if mutation == "procedure":
        target = next(block for block in document["blocks"] if block.get("text") == "Keep the seal in place.")
        target["text"] = "Discard the seal."
    else:
        first, second = [block for block in document["blocks"] if block["type"] == "image"]
        for field in ("asset_id", "image_id", "content_sha256", "storage_key", "alt"):
            first[field], second[field] = second[field], first[field]
    body, steps, images = project_document(document)

    with pytest.raises(ValueError, match="^SOURCE_BANKONE_ORDER_REPLAY_FLOW_DRIFT$"):
        replay.validate_bankone_order_capture(
            binding, replace(captured, source_document=document, source_body=body, source_steps=steps, source_images=images),
        )
