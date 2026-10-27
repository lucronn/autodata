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


def test_document_figure_queue_does_not_duplicate_existing_image_blocks():
    article = {
        "article_id": "test-article",
        "evidence_ids": ["e-1"],
        "images": [
            {
                "image_id": "figure-seal",
                "url": "data:image/png;base64,aaaa",
                "alt": "Seal replacement",
            },
            {
                "image_id": "figure-unplaced",
                "url": "data:image/png;base64,bbbb",
                "alt": "Unplaced extra figure",
            },
        ],
    }
    document = build_ordered_document(
        article,
        [
            {"kind": "text", "text": "1. Remove the front wheel."},
            {"kind": "image", "image_id": "figure-seal", "alt": "Seal replacement"},
            {"kind": "text", "text": "2. Inspect the hub."},
        ],
    )

    image_blocks = [b for b in document["blocks"] if b["type"] == "image"]
    assert len(image_blocks) == 2
    assert [b["image_id"] for b in image_blocks] == ["figure-seal", "figure-unplaced"]
    assert [b["source_order"] for b in document["blocks"]] == [1, 2, 3, 4]
    assert validate_ordered_document(document) == []


def test_document_figure_queue_does_not_duplicate_table_images():
    article = {
        "article_id": "table-article",
        "evidence_ids": ["e-2"],
        "images": [
            {
                "image_id": "tool-in-table",
                "url": "data:image/png;base64,cccc",
                "alt": "Tool in table cell",
            }
        ],
    }
    document = build_ordered_document(
        article,
        [
            {"kind": "text", "text": "REQUIRED TOOLS"},
            {
                "kind": "table",
                "rows": [[
                    {"blocks": [{"kind": "image", "image_id": "tool-in-table", "alt": "Tool in table cell"}]},
                    {"blocks": [{"kind": "text", "text": "T10050 Tool"}]},
                ]],
            },
            {"kind": "text", "text": "Use the tool to lock timing."},
        ],
    )

    image_blocks = [b for b in document["blocks"] if b["type"] == "image"]
    assert len(image_blocks) == 0
    assert document["blocks"][1]["rows"][0][0]["images"][0]["image_id"] == "tool-in-table"
    assert [b["source_order"] for b in document["blocks"]] == [1, 2, 3]
    assert validate_ordered_document(document) == []


def test_table_cell_preserves_direct_images():
    article = {"article_id": "test-table-direct-img"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "table",
                "label": "Torque specifications",
                "rows": [
                    [
                        "Bolt A",
                        {
                            "text": "35 Nm",
                            "images": [
                                {
                                    "image_id": "img-torque-1",
                                    "storage_key": "s3://bucket/torque1.png",
                                    "alt": "Torque pattern",
                                }
                            ],
                        },
                    ]
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    cell = document["blocks"][0]["rows"][0][1]
    assert isinstance(cell, dict)
    assert cell["text"] == "35 Nm"
    assert len(cell["images"]) == 1
    assert cell["images"][0]["image_id"] == "img-torque-1"
    assert cell["images"][0]["storage_key"] == "s3://bucket/torque1.png"
    assert cell["images"][0]["status"] == "available"


def test_validate_ordered_document_checks_list_items():
    doc = {
        "schema_version": 1,
        "normalization_version": "ordered-article-v1",
        "blocks": [
            {
                "block_id": "art:block:0001",
                "source_order": 1,
                "type": "ordered_list",
                "items": "not a list",
            }
        ],
    }
    errors = validate_ordered_document(doc)
    assert "block 1 has no list items" in errors


def test_safe_link_sanitization():
    from autodata_ingestion.article_document import _safe_link

    assert _safe_link("javascript:alert(1)") == ""
    assert _safe_link("vbscript:msgbox(1)") == ""
    assert _safe_link("data:text/html,<script>alert(1)</script>") == ""
    assert _safe_link("#section-anchor") == ""
    assert _safe_link("/v1/catalog/articles/spec-1") == "/v1/catalog/articles/spec-1"
    assert _safe_link("https://example.com/spec") == "https://example.com/spec"


def test_image_block_preserves_asset_resource_ref_and_attributes():
    article = {"article_id": "test-art-asset-ref"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "image",
                "image_id": "fig-res-1",
                "asset_resource_ref": "banktwo/asset/123",
                "storage_key": "procedure-images/abcd",
                "url": "https://source.test/fig.png",
                "alt": "Component diagram",
            }
        ],
    )
    assert validate_ordered_document(document) == []
    block = document["blocks"][0]
    assert block["type"] == "image"
    assert block["status"] == "available"
    assert block["asset_resource_ref"] == "banktwo/asset/123"
    assert block["storage_key"] == "procedure-images/abcd"
    assert block["url"] == "https://source.test/fig.png"
    assert block["image_id"] == "fig-res-1"


def test_list_block_extracts_clean_text_from_dictionary_items():
    article = {"article_id": "test-list-dicts"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "list",
                "items": [
                    {"text": "Disconnect the negative battery cable."},
                    {"value": "Remove the alternator mounting bolts."},
                    {"label": "Inspect the drive belt."},
                    "Reinstall components in reverse order.",
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    block = document["blocks"][0]
    assert block["type"] == "unordered_list"
    assert block["items"] == [
        "Disconnect the negative battery cable.",
        "Remove the alternator mounting bolts.",
        "Inspect the drive belt.",
        "Reinstall components in reverse order.",
    ]


def test_callout_block_extracts_message_content_and_body():
    article = {"article_id": "test-callout-fields"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "warning",
                "message": "Disconnect the high voltage service plug before proceeding.",
            },
            {
                "kind": "caution",
                "content": "Do not reuse the cylinder head bolts.",
            },
            {
                "kind": "note",
                "body": "Apply clean engine oil to threads prior to torqueing.",
            },
        ],
    )
    assert validate_ordered_document(document) == []
    assert document["blocks"][0]["label"] == "WARNING"
    assert document["blocks"][0]["text"] == "Disconnect the high voltage service plug before proceeding."
    assert document["blocks"][1]["label"] == "CAUTION"
    assert document["blocks"][1]["text"] == "Do not reuse the cylinder head bolts."
    assert document["blocks"][2]["label"] == "NOTE"
    assert document["blocks"][2]["text"] == "Apply clean engine oil to threads prior to torqueing."


def test_list_block_extracts_clean_text_from_content_body_and_message():
    article = {"article_id": "test-list-expanded"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "ordered_list",
                "items": [
                    {"content": "Step 1: Drain cooling system."},
                    {"body": "Step 2: Disconnect upper radiator hose."},
                    {"message": "Step 3: Unbolt thermostat housing."},
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    block = document["blocks"][0]
    assert block["type"] == "ordered_list"
    assert block["items"] == [
        "Step 1: Drain cooling system.",
        "Step 2: Disconnect upper radiator hose.",
        "Step 3: Unbolt thermostat housing.",
    ]


def test_callout_block_preserves_images():
    article = {"article_id": "test-callout-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "warning",
                "text": "Wear protective gear during handling.",
                "images": [
                    {
                        "image_id": "warning-icon",
                        "storage_key": "procedure-images/warn1",
                        "url": "https://source.test/warn.png",
                    }
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    block = document["blocks"][0]
    assert block["type"] == "callout"
    assert block["text"] == "Wear protective gear during handling."
    assert "images" in block
    assert block["images"][0]["image_id"] == "warning-icon"
    assert block["images"][0]["storage_key"] == "procedure-images/warn1"
    assert block["images"][0]["status"] == "available"


def test_step_block_extracts_action_instruction_and_number():
    article = {"article_id": "test-step-normalization"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "step",
                "action": "Remove the oil drain plug.",
                "step_number": 1,
            },
            {
                "type": "step",
                "label": "Filter Replacement",
                "instruction": "Unscrew the oil filter canister.",
                "number": 2,
            },
            {
                "kind": "instruction",
                "instructions": ["Drain the oil pan.", "Inspect the crush washer."],
                "index": 3,
            },
        ],
    )
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    assert len(blocks) == 3
    assert blocks[0]["type"] == "step"
    assert blocks[0]["text"] == "Remove the oil drain plug."
    assert blocks[0]["number"] == 1

    assert blocks[1]["type"] == "step"
    assert blocks[1]["text"] == "Unscrew the oil filter canister."
    assert blocks[1]["number"] == 2
    assert blocks[1]["label"] == "Filter Replacement"

    assert blocks[2]["type"] == "step"
    assert blocks[2]["text"] == "Drain the oil pan. Inspect the crush washer."
    assert blocks[2]["number"] == 3


def test_step_block_preserves_images():
    article = {"article_id": "test-step-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "step",
                "text": "Disconnect the steering linkage.",
                "number": 4,
                "images": [
                    {
                        "image_id": "linkage-diagram",
                        "storage_key": "procedure-images/link1",
                    }
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    block = document["blocks"][0]
    assert block["type"] == "step"
    assert block["number"] == 4
    assert "images" in block
    assert block["images"][0]["image_id"] == "linkage-diagram"
    assert block["images"][0]["storage_key"] == "procedure-images/link1"
    assert block["images"][0]["status"] == "available"


def test_paragraph_block_extracts_content_and_body_and_preserves_images():
    article = {"article_id": "test-para-expanded"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "paragraph",
                "content": "Inspect brake pads for uneven wear patterns.",
                "images": [
                    {
                        "image_id": "pad-wear-spec",
                        "storage_key": "procedure-images/pad1",
                    }
                ],
            },
            {
                "type": "paragraph",
                "body": "Ensure caliper slide pins are free of corrosion.",
            },
            {
                "kind": "heading",
                "title": "Front Brake Service",
                "level": 3,
            },
        ],
    )
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    assert len(blocks) == 3
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["text"] == "Inspect brake pads for uneven wear patterns."
    assert "images" in blocks[0]
    assert blocks[0]["images"][0]["image_id"] == "pad-wear-spec"

    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["text"] == "Ensure caliper slide pins are free of corrosion."

    assert blocks[2]["type"] == "heading"
    assert blocks[2]["text"] == "Front Brake Service"
    assert blocks[2]["level"] == 3

