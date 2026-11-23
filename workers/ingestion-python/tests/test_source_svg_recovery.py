"""Recover media and table geometry from synthetic retained observations."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_svg_recovery as recovery
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_store import persist_resource, store_captured_source, upsert_article_descriptor
from autodata_ingestion.article_lifecycle_types import ArticleKey, HTML_TABLE_SPAN_LAYOUT, SourceArticleContext, digest_json
from autodata_ingestion.source_article_capture import capture_source_article, project_document
from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
from autodata_ingestion.source_job_persistence import claim_source_job, ensure_article_job, fail_source_job
from autodata_ingestion.source_table_replay import restore_table_spans
from autodata_ingestion.svg_rasterization import RASTERIZER_VERSION, SVGUnavailable
from lifecycle_support import fresh_database, seed_snapshot, seed_vehicle
from test_source_table_replay import BODY, Objects, source_state


_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4"/></svg>'
_LEGACY_MISSING = "source image reference is missing"


def _envelope(provider, payload, media_type, kind):
    return SourceEnvelopeV1(
        str(uuid4()), provider, "fixture-revision", datetime.now(UTC).isoformat(), "fixture:source",
        {"kind": kind, "media_type": media_type, "sha256": sha256(payload).hexdigest()}, raw_resource=payload,
    )


def _legacy(repo, *, provider="banktwo", body=BODY, other_failure=False, legacy_fallback=False, damage=None):
    key = ArticleKey(provider, seed_vehicle(repo), None, "fixture-vehicle", "fixture-art")
    refs = ["archived-figure", "missing-figure"] if other_failure else ["archived-figure"]
    descriptor = {"resource_ref": "body", "title": "Fastener checks", "asset_resource_refs": refs}
    descriptor_id = seed_snapshot(repo, b"fixture descriptor")
    resolution_id = seed_snapshot(repo, b"fixture resolution")
    profile = "technical-prose-v1"
    article = upsert_article_descriptor(repo, key, descriptor, descriptor_id, 0, rewrite_profile_version=profile)
    context = SourceArticleContext(key, {"year": 2020}, descriptor, descriptor_id, resolution_id, ("fixture-evidence",))

    class LegacyConnector:
        provider = key.provider

        def read_resource(self, ref, *, timeout):
            assert timeout > 0
            if ref == "archived-figure":
                raise SourceConnectorError("UNSUPPORTED_ASSET_MEDIA")
            if ref == "missing-figure":
                raise SourceConnectorError("SOURCE_NOT_FOUND", status=404)
            assert ref == "body"
            return _envelope(provider, body, "text/html", "article")

    objects = Objects()
    legacy = capture_source_article(context, registry={provider: LegacyConnector()}, object_store=objects)
    retained_figure = next(block for block in legacy.source_document["blocks"] if block.get("unavailable_reason")
                           == "UNSUPPORTED_ASSET_MEDIA")
    assert retained_figure["image_id"] == digest_json({"provider": provider, "ref": "archived-figure"})
    retained_figure["caption"] = "Alignment marks on the fastener cover"
    if legacy_fallback:
        for block in legacy.source_document["blocks"]:
            if block.get("status") == "unavailable":
                block["unavailable_reason"] = _LEGACY_MISSING
        legacy = replace(legacy, projection_version="source-projection-v2")
    if damage == "other_reason":
        retained_figure["unavailable_reason"] = "different failure"
    _, _, images = project_document(legacy.source_document)
    if damage == "duplicate_position":
        duplicate = deepcopy(retained_figure)
        blocks = legacy.source_document["blocks"]
        duplicate.update(source_order=len(blocks) + 1, block_id="fixture:duplicate")
        blocks.append(duplicate)
    elif damage == "unbound_position":
        retained_figure.update(image_id="f" * 64, asset_id="f" * 64)
    elif damage == "projection_drift":
        images[0]["caption"] = "Changed caption in flattened projection"
    legacy = replace(legacy, source_images=images)
    ensure = ensure_article_job(repo, article, normalization_version="ordered-article-v1", rewrite_profile_version=profile)
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=ensure.job_id)
    revision = store_captured_source(repo, lease, legacy)
    fail_source_job(repo, lease, code="FIXTURE_FINISHED", retryable=False)
    objects.seeding = False
    return article, revision, objects, {"archived-figure": _envelope(provider, _SVG, "image/svg+xml", "asset")}


@pytest.fixture
def raster(monkeypatch):
    out = BytesIO()
    Image.new("RGB", (4, 4), "green").save(out, format="PNG")
    png = out.getvalue()

    def render(payload, *, timeout):
        assert payload == _SVG and 0 < timeout <= 30
        return png

    monkeypatch.setattr(recovery, "rasterize_svg", render)
    return png


@pytest.mark.parametrize(("provider", "has_spans", "other_failure", "legacy_fallback"), [
    ("bankone", True, False, False),
    ("banktwo", False, True, False),
    ("banktwo", True, True, True),
])
def test_exact_figures_and_verified_table_spans_only(
    fresh_database, raster, provider, has_spans, other_failure, legacy_fallback,
):
    repo = fresh_database(through=42)
    body = BODY if has_spans else BODY.replace(b' colspan="2"', b"").replace(b' rowspan="2"', b"")
    article, revision, objects, assets = _legacy(
        repo, provider=provider, body=body, other_failure=other_failure, legacy_fallback=legacy_fallback,
    )
    prior_state, prior_objects = source_state(repo, article), deepcopy(objects.data)
    binding, captured, blobs = recovery.build_svg_recovery(repo, revision, object_store=objects, assets=assets)

    row = binding.row
    assert binding.source_revision_id == revision and binding.body_sha256 == sha256(body).hexdigest()
    assert captured.body_source_snapshot_id == row["body_source_snapshot_id"]
    assert captured.source_fingerprint != binding.source_fingerprint
    assert captured.projection_version == "source-projection-v5"
    assert captured.projection_status == ("partial" if other_failure else "readable")
    layout = HTML_TABLE_SPAN_LAYOUT if has_spans else None
    assert captured.resource_manifest[0].get("html_table_span_layout") == layout
    assert captured.resource_provenance[0].get("html_table_span_layout") == layout
    original, derivative = captured.resource_manifest[1:3]
    svg_sha, png_sha = sha256(_SVG).hexdigest(), sha256(raster).hexdigest()
    assert original == {"role": "asset_original", "opaque_ref": "archived-figure",
                        "sha256": svg_sha, "media_type": "image/svg+xml"}
    assert derivative == {"role": "asset", "opaque_ref": "archived-figure", "sha256": png_sha, "media_type": "image/png",
                          "derived_from_sha256": svg_sha, "derivation_version": RASTERIZER_VERSION}
    svg_key = f"sources/{svg_sha[:16]}/{svg_sha}"
    png_key = f"sources/{png_sha[:16]}/{png_sha}"
    assert blobs == {svg_key: (_SVG, "image/svg+xml"), png_key: (raster, "image/png")}
    assert [resource["object_key"] for resource in captured.resources[1:]] == [svg_key, png_key]
    for resource in captured.resource_provenance[1:3]:
        envelope = assets["archived-figure"]
        assert resource["fetched_at"] == envelope.fetched_at
        assert resource["request_id"] == envelope.request_id
        assert resource["source_revision"] == envelope.source_revision
        assert resource["locator"] == envelope.source_locator
    if other_failure:
        assert captured.resource_manifest[3:] == row["resource_manifest"][2:]
        assert captured.resource_provenance[3:] == row["resource_provenance"][2:]
        assert captured.resource_manifest[3]["failure_code"] == "SOURCE_NOT_FOUND"
        assert captured.source_images[-1] == row["source_images"][-1]
        if legacy_fallback:
            assert captured.source_images[-1]["unavailable_reason"] == _LEGACY_MISSING

    expected = restore_table_spans(row["source_document"], body) if has_spans else deepcopy(row["source_document"])
    placeholder_id = digest_json({"provider": provider, "ref": "archived-figure"})
    original_node = next(block for block in expected["blocks"] if block.get("image_id") == placeholder_id)
    assert original_node["unavailable_reason"] == (_LEGACY_MISSING if legacy_fallback else "UNSUPPORTED_ASSET_MEDIA")
    assert original_node["caption"] == "Alignment marks on the fastener cover"
    del original_node["unavailable_reason"]
    original_node.update(status="available", image_id=png_sha, content_sha256=png_sha, media_type="image/png",
                         asset_id=png_key, storage_key=png_key)
    assert captured.source_document == expected
    assert captured.source_images == project_document(expected)[2]
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert captured.source_body == row["source_body"] and captured.source_steps == row["source_steps"]
    assert captured.evidence_manifest == row["evidence_manifest"]
    assert source_state(repo, article) == prior_state and objects.data == prior_objects and objects.reads == 1
    with repo.connect() as conn:
        with pytest.raises(ValueError, match="BINDING_MISMATCH"):
            recovery.check_svg_recovery_rights(conn.cursor(), captured, require_existing=True)
        for resource in captured.resources[1:]:
            persist_resource(conn.cursor(), resource)
        recovery.check_svg_recovery_rights(conn.cursor(), captured, lock=True, require_existing=True)
        conn.execute("UPDATE source_snapshots SET takedown_status='expired' WHERE content_sha256=%s", (svg_sha,))
    with pytest.raises(ValueError, match="WITHDRAWN"):
        recovery.build_svg_recovery(repo, revision, object_store=objects, assets=assets)
    assert source_state(repo, article) == prior_state and objects.data == prior_objects


def test_unbound_inputs_body_and_unsafe_svg_are_refused(fresh_database, raster, monkeypatch):
    repo = fresh_database(through=42)
    article, revision, objects, assets = _legacy(repo)
    prior_state, prior_objects = source_state(repo, article), deepcopy(objects.data)
    envelope = assets["archived-figure"]
    for asset_map in ({}, {"unbound-figure": envelope}, {**assets, "extra-figure": envelope}):
        with pytest.raises(ValueError, match="BINDING_MISMATCH"):
            recovery.build_svg_recovery(repo, revision, object_store=objects, assets=asset_map)
    for invalid in (
        replace(envelope, raw_resource=_SVG + b" "),
        replace(envelope, provider="bankone"),
        replace(envelope, source_locator="fixture:source?token=synthetic"),
        replace(envelope, body={**envelope.body, "media_type": "image/png"}),
    ):
        with pytest.raises(ValueError, match="ASSET_INVALID"):
            recovery.build_svg_recovery(repo, revision, object_store=objects, assets={"archived-figure": invalid})
    assert objects.reads == 0

    [body_key] = objects.data
    objects.data[body_key] += b" "
    with pytest.raises(ValueError, match="BODY_MISMATCH"):
        recovery.build_svg_recovery(repo, revision, object_store=objects, assets=assets)
    objects.data[body_key] = prior_objects[body_key]

    def unsafe(*args, **kwargs):
        raise SVGUnavailable("SVG_UNSUPPORTED_FEATURE")

    monkeypatch.setattr(recovery, "rasterize_svg", unsafe)
    with pytest.raises(SVGUnavailable, match="SVG_UNSUPPORTED_FEATURE"):
        recovery.build_svg_recovery(repo, revision, object_store=objects, assets=assets)
    assert source_state(repo, article) == prior_state and objects.data == prior_objects


@pytest.mark.parametrize(("damage", "legacy_fallback"), [
    ("duplicate_position", False),
    ("unbound_position", False),
    ("projection_drift", False),
    ("unbound_position", True),
    ("other_reason", True),
])
def test_changed_legacy_figure_binding_is_refused(fresh_database, raster, damage, legacy_fallback):
    repo = fresh_database(through=42)
    _, revision, objects, assets = _legacy(repo, damage=damage, legacy_fallback=legacy_fallback)
    with pytest.raises(ValueError, match="BINDING_MISMATCH"):
        recovery.build_svg_recovery(repo, revision, object_store=objects, assets=assets)
