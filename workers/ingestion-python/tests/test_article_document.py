from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.article_document import (
    NORMALIZATION_VERSION,
    build_ordered_document,
    segment_plain_article_text,
    validate_ordered_document,
)
from autodata_ingestion.procedure_normalize import normalize_procedure_article


def test_document_preserves_mixed_source_order_and_nested_table_images():
    article = {"article_id": "article-1", "evidence_ids": ["e-1"]}
    document = build_ordered_document(
        article,
        [
            {"kind": "text", "text": "REMOVAL"},
            {
                "kind": "table",
                "rows": [[
                    {"blocks": [{"kind": "image", "url": "https://source.test/tool.svg", "alt": "Tool"}]},
                    {"blocks": [{"kind": "text", "text": "8498 - Receiver"}]},
                ]],
            },
            {"kind": "text", "text": "Remove the seal."},
            {"kind": "image", "image_id": "figure-1", "alt": "Seal"},
        ],
    )

    assert [block["type"] for block in document["blocks"]] == ["heading", "table", "paragraph", "image"]
    assert [block["source_order"] for block in document["blocks"]] == [1, 2, 3, 4]
    assert document["blocks"][1]["rows"][0][0]["images"][0]["alt"] == "Tool"
    assert document["blocks"][3]["image_id"] == "figure-1"
    assert validate_ordered_document(document) == []


def test_document_validation_rejects_reordered_or_unresolved_blocks():
    document = {
        "schema_version": 1,
        "normalization_version": NORMALIZATION_VERSION,
        "blocks": [
            {"block_id": "b2", "source_order": 2, "type": "image", "status": "pending"},
        ],
    }

    errors = validate_ordered_document(document)
    assert "block 1 has invalid source_order" in errors
    assert "block 1 has no image status" in errors


def test_figure_captions_pull_article_images_into_document_blocks():
    article = {
        "article_id": "pdf-article",
        "body": "Service\n1. Use the funnel.\nFigure 1. Oil funnel VAS 6675.\nWarranty Informational only.",
        "images": [
            {
                "image_id": "pdf-page-2-abcdef123456",
                "url": "data:image/png;base64,aaaa",
                "alt": "Figure from page 2",
            }
        ],
    }
    document = build_ordered_document(article, segment_plain_article_text(article["body"]))
    types = [block["type"] for block in document["blocks"]]
    assert "image" in types
    image = next(block for block in document["blocks"] if block["type"] == "image")
    assert image["image_id"] == "pdf-page-2-abcdef123456"
    assert image["status"] == "available"


def test_collapsed_tsb_pdf_text_is_segmented_for_workshop_display():
    body = (
        "Technical Service Bulletin 00 Oil draining - cleanliness 00 14 59 2029737/2 "
        "February 20, 2014. Condition The process of draining oil through the drain plug "
        "is not always tidy. Technical Background When oil is drained through the drain "
        "plug, the oil might spill. Production Solution Not applicable. Service 1. When "
        "necessary, use flexible oil funnel VAS 6675. 2. Clean any oil residue off of "
        "components. Note: Capture any spilled oil. Figure 1. Oil funnel VAS 6675. "
        "Warranty This TSB is informational only. Required Parts and Tools VAS 6675 "
        "Flexible oil funnel 1 Additional Information Always check with your Parts "
        "Department."
    )

    segments = segment_plain_article_text(body)
    kinds = [segment["kind"] for segment in segments]
    assert "heading" in kinds
    assert "note" in kinds
    assert any(str(segment.get("text") or "").startswith("1.") for segment in segments)
    assert any(str(segment.get("text") or "").startswith("2.") for segment in segments)

    article = normalize_procedure_article(
        {
            "article_id": "autoapi:vehicle:article",
            "title": "00 Oil draining - cleanliness",
            "body": body,
            "steps": [
                {
                    "action": body,
                    "instructions": [body],
                    "components": ["service"],
                    "phase": "procedure",
                }
            ],
            "normalized_document": {
                "schema_version": 1,
                "normalization_version": NORMALIZATION_VERSION,
                "blocks": [
                    {
                        "block_id": "b1",
                        "source_order": 1,
                        "type": "paragraph",
                        "text": body,
                        "evidence_ids": [],
                    }
                ],
            },
            "content_status": "content_complete",
        }
    )
    block_types = [block["type"] for block in article["normalized_document"]["blocks"]]
    assert "heading" in block_types
    assert "step" in block_types
    assert "callout" in block_types
    assert block_types.count("paragraph") >= 1
    assert len(article["normalized_document"]["blocks"]) >= 6
