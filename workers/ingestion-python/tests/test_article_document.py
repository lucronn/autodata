from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.article_document import (
    NORMALIZATION_VERSION,
    build_ordered_document,
    document_from_steps,
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


def test_document_figure_queue_does_not_duplicate_block_images():
    article = {
        "article_id": "test-block-img-dedup",
        "images": [
            {
                "image_id": "step-fig-1",
                "storage_key": "procedure-images/step1",
                "alt": "Step 1 Figure",
            },
            {
                "image_id": "para-fig-2",
                "storage_key": "procedure-images/para2",
                "alt": "Paragraph Figure",
            },
            {
                "image_id": "standalone-fig-3",
                "storage_key": "procedure-images/standalone3",
                "alt": "Unattached PDF Figure",
            },
        ],
    }
    document = build_ordered_document(
        article,
        [
            {
                "kind": "step",
                "action": "Loosen caliper bolts.",
                "number": 1,
                "images": [
                    {
                        "image_id": "step-fig-1",
                        "storage_key": "procedure-images/step1",
                    }
                ],
            },
            {
                "kind": "paragraph",
                "text": "Apply anti-seize compound to guide pins.",
                "images": [
                    {
                        "image_id": "para-fig-2",
                        "storage_key": "procedure-images/para2",
                    }
                ],
            },
        ],
    )
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    # Blocks should be: step, paragraph, and the unattached standalone-fig-3 image block.
    # step-fig-1 and para-fig-2 should NOT be re-added as standalone image blocks.
    assert len(blocks) == 3
    assert blocks[0]["type"] == "step"
    assert blocks[0]["images"][0]["image_id"] == "step-fig-1"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["images"][0]["image_id"] == "para-fig-2"
    assert blocks[2]["type"] == "image"
    assert blocks[2]["image_id"] == "standalone-fig-3"


def test_numbered_paragraph_preserves_attached_images():
    article = {"article_id": "test-numbered-para-img"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "paragraph",
                "text": "1. Disconnect negative battery terminal.",
                "images": [
                    {
                        "image_id": "batt-term-fig",
                        "storage_key": "procedure-images/battery",
                        "alt": "Battery terminal",
                    }
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    step_block = document["blocks"][0]
    assert step_block["type"] == "step"
    assert step_block["number"] == 1
    assert step_block["text"] == "Disconnect negative battery terminal."
    assert "images" in step_block
    assert step_block["images"][0]["image_id"] == "batt-term-fig"
    assert step_block["images"][0]["status"] == "available"


def test_step_block_handles_mapping_instructions():
    article = {"article_id": "test-step-mapping-inst"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "step",
                "instructions": [
                    {"instruction": "Remove retaining clip."},
                    {"text": "Pull wiring harness plug firmly."},
                ],
                "number": 2,
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    step_block = document["blocks"][0]
    assert step_block["type"] == "step"
    assert step_block["number"] == 2
    assert step_block["text"] == "Remove retaining clip. Pull wiring harness plug firmly."


def test_document_from_steps_handles_mapping_instructions():
    from autodata_ingestion.article_document import document_from_steps

    article = {
        "article_id": "test-legacy-steps-mapping",
        "steps": [
            {
                "heading": "Remove intake manifold",
                "number": 1,
                "instructions": [
                    {"action": "Unbolt throttle body bolts."},
                    {"text": "Disconnect vacuum line."},
                    "Inspect gasket for damage.",
                ],
            }
        ],
    }
    document = document_from_steps(article)
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    assert len(blocks) == 4
    assert blocks[0]["type"] == "step"
    assert blocks[0]["number"] == 1
    assert blocks[0]["text"] == "Remove intake manifold"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["text"] == "Unbolt throttle body bolts."
    assert blocks[2]["type"] == "paragraph"
    assert blocks[2]["text"] == "Disconnect vacuum line."
    assert blocks[3]["type"] == "paragraph"
    assert blocks[3]["text"] == "Inspect gasket for damage."


def test_blocks_from_steps_handles_mapping_instructions():
    from autodata_ingestion.article_document import _blocks_from_steps

    steps = [
        {
            "action": "Loosen bracket",
            "instructions": [
                {"instruction": "Use 10mm socket."},
                {"value": "Turn counter-clockwise."},
            ],
            "evidence_ids": ["ev-1"],
        }
    ]
    blocks = _blocks_from_steps(steps)
    assert blocks is not None
    assert len(blocks) == 3
    assert blocks[0]["text"] == "Loosen bracket"
    assert blocks[1]["text"] == "Use 10mm socket."
    assert blocks[2]["text"] == "Turn counter-clockwise."


def test_list_block_preserves_attached_images():
    article = {"article_id": "test-list-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "unordered_list",
                "items": ["Torx T20", "Flathead screwdriver"],
                "images": [
                    {
                        "image_id": "tool-set-fig",
                        "storage_key": "procedure-images/tools",
                        "alt": "Required hand tools",
                    }
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    list_block = document["blocks"][0]
    assert list_block["type"] == "unordered_list"
    assert list_block["items"] == ["Torx T20", "Flathead screwdriver"]
    assert "images" in list_block
    assert list_block["images"][0]["image_id"] == "tool-set-fig"
    assert list_block["images"][0]["status"] == "available"


def test_list_item_images_prescan_deduplication():
    article = {
        "article_id": "test-list-item-img-dedup",
        "images": [
            {
                "image_id": "item-fig-1",
                "storage_key": "procedure-images/fuse-box",
                "alt": "Fuse box diagram",
            },
            {
                "image_id": "trailing-fig-2",
                "storage_key": "procedure-images/wiring-schematic",
                "alt": "Wiring schematic",
            },
        ],
    }
    document = build_ordered_document(
        article,
        [
            {
                "kind": "ordered_list",
                "items": [
                    {
                        "text": "Check 15A horn fuse.",
                        "images": [
                            {
                                "image_id": "item-fig-1",
                                "storage_key": "procedure-images/fuse-box",
                            }
                        ],
                    },
                    "Check relay socket pins.",
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    # item-fig-1 was pre-scanned and not inserted as a trailing figure.
    # trailing-fig-2 was not in the blocks, so it gets appended by figure_queue.
    assert len(blocks) == 2
    assert blocks[0]["type"] == "ordered_list"
    assert blocks[0]["items"] == ["Check 15A horn fuse.", "Check relay socket pins."]
    assert blocks[1]["type"] == "image"
    assert blocks[1]["image_id"] == "trailing-fig-2"


def test_table_block_direct_images_and_title_heading_label():
    article = {"article_id": "test-table-images-and-title"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "table",
                "title": "Fastener Torque Specifications",
                "columns": ["Component", "Torque"],
                "rows": [
                    ["Caliper bracket bolts", "115 Nm"],
                    ["Guide pin bolts", "38 Nm"],
                ],
                "images": [
                    {
                        "image_id": "torque-spec-fig",
                        "storage_key": "procedure-images/torque-spec",
                        "alt": "Torque chart diagram",
                    }
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    tbl = document["blocks"][0]
    assert tbl["type"] == "table"
    assert tbl["label"] == "Fastener Torque Specifications"
    assert tbl["columns"] == ["Component", "Torque"]
    assert tbl["rows"] == [["Caliper bracket bolts", "115 Nm"], ["Guide pin bolts", "38 Nm"]]
    assert "images" in tbl
    assert tbl["images"][0]["image_id"] == "torque-spec-fig"
    assert tbl["images"][0]["status"] == "available"


def test_table_cell_content_body_label_normalization():
    article = {"article_id": "test-table-cell-content-body"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "table",
                "heading": "Diagnostic Readings",
                "rows": [
                    {
                        "cells": [
                            {"content": "Sensor A voltage"},
                            {"body": "4.95 V"},
                            {"label": "Pass"},
                        ]
                    },
                    {
                        "cells": [
                            {
                                "blocks": [
                                    {"kind": "text", "content": "Sensor B resistance"},
                                    {"kind": "text", "body": "(cold)"},
                                ]
                            },
                            {"content": "1.2 kOhm"},
                            {"label": "Pass"},
                        ]
                    },
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    tbl = document["blocks"][0]
    assert tbl["type"] == "table"
    assert tbl["label"] == "Diagnostic Readings"
    assert tbl["rows"][0] == ["Sensor A voltage", "4.95 V", "Pass"]
    assert tbl["rows"][1] == ["Sensor B resistance (cold)", "1.2 kOhm", "Pass"]


def test_callout_block_custom_title_and_items_composite_text():
    article = {"article_id": "test-callout-title-items"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "warning",
                "title": "HIGH VOLTAGE SYSTEM",
                "items": [
                    {"content": "Disconnect 12V auxiliary battery first."},
                    {"body": "Remove high-voltage service disconnect plug."},
                    "Wait 5 minutes for capacitor discharge.",
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    callout = document["blocks"][0]
    assert callout["type"] == "callout"
    assert callout["label"] == "HIGH VOLTAGE SYSTEM"
    assert (
        callout["text"]
        == "Disconnect 12V auxiliary battery first. Remove high-voltage service disconnect plug. Wait 5 minutes for capacitor discharge."
    )


def test_document_from_steps_title_name_text_fallback():
    article = {
        "article_id": "test-steps-title-name-text",
        "steps": [
            {
                "number": 1,
                "title": "Inspect high-pressure fuel pump",
                "instructions": ["Check for visible leaks around the flange."],
            },
            {
                "number": 2,
                "name": "Verify fuel rail pressure",
                "instructions": ["Monitor live scan data at 2500 RPM."],
            },
            {
                "number": 3,
                "text": "Clear diagnostic trouble codes upon completion.",
            },
        ],
    }
    document = document_from_steps(article)
    assert validate_ordered_document(document) == []
    blocks = document["blocks"]
    assert len(blocks) == 5
    assert blocks[0]["type"] == "step"
    assert blocks[0]["number"] == 1
    assert blocks[0]["text"] == "Inspect high-pressure fuel pump"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["text"] == "Check for visible leaks around the flange."
    assert blocks[2]["type"] == "step"
    assert blocks[2]["number"] == 2
    assert blocks[2]["text"] == "Verify fuel rail pressure"
    assert blocks[3]["type"] == "paragraph"
    assert blocks[3]["text"] == "Monitor live scan data at 2500 RPM."
    assert blocks[4]["type"] == "step"
    assert blocks[4]["number"] == 3
    assert blocks[4]["text"] == "Clear diagnostic trouble codes upon completion."


def test_blocks_from_steps_heading_title_text_fallback():
    from autodata_ingestion.article_document import _blocks_from_steps

    steps = [
        {
            "heading": "Disconnect negative battery cable",
            "evidence_ids": ["ev-1"],
            "instructions": ["Use a 10mm socket."],
        },
        {
            "title": "Remove drive belt",
            "evidence_ids": ["ev-2"],
        },
        {
            "text": "Inspect belt for cracking or glazing.",
            "evidence_ids": ["ev-3"],
        },
    ]
    raw_blocks = _blocks_from_steps(steps)
    assert raw_blocks is not None
    assert len(raw_blocks) == 4
    assert raw_blocks[0] == {
        "kind": "text",
        "text": "Disconnect negative battery cable",
        "evidence_ids": ["ev-1"],
    }
    assert raw_blocks[1] == {
        "kind": "text",
        "text": "Use a 10mm socket.",
        "evidence_ids": ["ev-1"],
    }
    assert raw_blocks[2] == {
        "kind": "text",
        "text": "Remove drive belt",
        "evidence_ids": ["ev-2"],
    }
    assert raw_blocks[3] == {
        "kind": "text",
        "text": "Inspect belt for cracking or glazing.",
        "evidence_ids": ["ev-3"],
    }


def test_image_identities_includes_asset_resource_ref_and_deduplicates():
    from autodata_ingestion.article_document import _image_identities

    image = {"asset_resource_ref": "urn:asset:brake-rotor-01"}
    identities = _image_identities(image)
    assert "urn:asset:brake-rotor-01" in identities

    article = {
        "article_id": "test-asset-ref-dedup",
        "images": [
            {
                "image_id": "img-01",
                "asset_resource_ref": "urn:asset:brake-rotor-01",
                "storage_key": "procedure-images/brake1",
            }
        ],
    }
    document = build_ordered_document(
        article,
        [
            {
                "kind": "image",
                "asset_resource_ref": "urn:asset:brake-rotor-01",
                "url": "https://source.test/brake.png",
            }
        ],
    )
    assert validate_ordered_document(document) == []
    # Should only produce 1 image block, not duplicate via figure_queue
    image_blocks = [b for b in document["blocks"] if b["type"] == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["asset_resource_ref"] == "urn:asset:brake-rotor-01"


def test_image_block_caption_fallback_to_description_and_legend():
    article = {"article_id": "test-img-desc-legend"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "image",
                "url": "https://source.test/diagram.png",
                "description": "Wiring schematic for ambient lighting module",
                "content_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            },
            {
                "kind": "image",
                "url": "https://source.test/fuse-box.png",
                "legend": "Engine compartment fuse block layout",
            },
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 2
    b1 = document["blocks"][0]
    assert b1["type"] == "image"
    assert b1["caption"] == "Wiring schematic for ambient lighting module"
    assert b1["alt"] == "Wiring schematic for ambient lighting module"
    assert b1["content_sha256"] == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    b2 = document["blocks"][1]
    assert b2["type"] == "image"
    assert b2["caption"] == "Engine compartment fuse block layout"
    assert b2["alt"] == "Engine compartment fuse block layout"


def test_list_block_preserves_label_title_heading_and_collects_item_images():
    article = {"article_id": "test-list-label-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "unordered_list",
                "title": "Special Tools Required",
                "items": [
                    {
                        "text": "Universal pulley holder",
                        "images": [
                            {
                                "image_id": "tool-holder-01",
                                "storage_key": "procedure-images/tool1",
                            }
                        ],
                    },
                    "19mm deep socket",
                ],
            },
            {
                "kind": "ordered_list",
                "heading": "Torque Specifications",
                "items": [
                    "Cylinder head bolts: 45 Nm + 90 degrees",
                    "Camshaft caps: 12 Nm",
                ],
            },
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 2
    l1 = document["blocks"][0]
    assert l1["type"] == "unordered_list"
    assert l1["label"] == "Special Tools Required"
    assert l1["items"] == ["Universal pulley holder", "19mm deep socket"]
    assert "images" in l1
    assert l1["images"][0]["image_id"] == "tool-holder-01"
    assert l1["images"][0]["storage_key"] == "procedure-images/tool1"

    l2 = document["blocks"][1]
    assert l2["type"] == "ordered_list"
    assert l2["label"] == "Torque Specifications"
    assert l2["items"] == [
        "Cylinder head bolts: 45 Nm + 90 degrees",
        "Camshaft caps: 12 Nm",
    ]


def test_link_block_title_name_and_url_target_fallbacks():
    article = {"article_id": "test-link-fallbacks"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "link",
                "title": "Related Service Bulletin TSB-101",
                "url": "https://service.auto.test/tsb-101",
            },
            {
                "kind": "anchor",
                "name": "Diagnostic Flowchart PDF",
                "target": "https://service.auto.test/diagram.pdf",
            },
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 2
    link1 = document["blocks"][0]
    assert link1["type"] == "link"
    assert link1["text"] == "Related Service Bulletin TSB-101"
    assert link1["href"] == "https://service.auto.test/tsb-101"

    link2 = document["blocks"][1]
    assert link2["type"] == "link"
    assert link2["text"] == "Diagnostic Flowchart PDF"
    assert link2["href"] == "https://service.auto.test/diagram.pdf"


def test_image_identities_includes_uri_and_path_and_deduplicates():
    from autodata_ingestion.article_document import _image_identities

    img1 = {"uri": "file:///var/data/images/alternator.png"}
    img2 = {"path": "images/caliper.svg"}
    assert "file:///var/data/images/alternator.png" in _image_identities(img1)
    assert "images/caliper.svg" in _image_identities(img2)

    article = {
        "article_id": "test-uri-path-dedup",
        "images": [
            {
                "image_id": "img-uri-01",
                "uri": "file:///var/data/images/alternator.png",
                "storage_key": "procedure-images/alt1",
            }
        ],
    }
    document = build_ordered_document(
        article,
        [
            {
                "kind": "image",
                "uri": "file:///var/data/images/alternator.png",
                "url": "https://source.test/alt.png",
            }
        ],
    )
    assert validate_ordered_document(document) == []
    image_blocks = [b for b in document["blocks"] if b["type"] == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["uri"] == "file:///var/data/images/alternator.png"


def test_normalize_cell_image_caption_fallback_to_title():
    from autodata_ingestion.article_document import _normalize_cell_image

    normalized = _normalize_cell_image({
        "url": "https://source.test/cell-fig.png",
        "title": "Front Suspension Geometry Schematic",
    })
    assert normalized["caption"] == "Front Suspension Geometry Schematic"
    assert normalized["alt"] == "Front Suspension Geometry Schematic"


def test_callout_block_aggregates_item_images_and_deduplicates():
    article = {"article_id": "test-callout-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "warning",
                "title": "High Voltage Safety Precaution",
                "items": [
                    {
                        "text": "Disconnect 12V auxiliary battery before servicing hybrid fuse.",
                        "images": [
                            {
                                "image_id": "hybrid-fuse-01",
                                "storage_key": "procedure-images/hybrid-fuse",
                            }
                        ],
                    },
                    {
                        "text": "Wear Class 0 insulated gloves.",
                        "images": [
                            {
                                "image_id": "hybrid-fuse-01",
                                "storage_key": "procedure-images/hybrid-fuse",
                            },
                            {
                                "image_id": "gloves-02",
                                "storage_key": "procedure-images/gloves",
                            },
                        ],
                    },
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    callout = document["blocks"][0]
    assert callout["type"] == "callout"
    assert callout["label"] == "High Voltage Safety Precaution"
    assert "Disconnect 12V auxiliary battery" in callout["text"]
    assert "images" in callout
    # 2 unique images, deduplicated from 3 item-level image entries
    assert len(callout["images"]) == 2
    assert callout["images"][0]["image_id"] == "hybrid-fuse-01"
    assert callout["images"][1]["image_id"] == "gloves-02"


def test_step_block_aggregates_instruction_images_and_deduplicates():
    article = {"article_id": "test-step-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "step",
                "number": 4,
                "label": "Remove Timing Belt Cover",
                "instructions": [
                    {
                        "action": "Unbolt upper timing belt cover fasteners.",
                        "images": [
                            {
                                "image_id": "timing-cover-bolts",
                                "storage_key": "procedure-images/timing-bolts",
                            }
                        ],
                    },
                    {
                        "instruction": "Detach wiring harness bracket.",
                        "images": [
                            {
                                "image_id": "timing-cover-bolts",
                                "storage_key": "procedure-images/timing-bolts",
                            },
                            {
                                "image_id": "bracket-clip",
                                "storage_key": "procedure-images/bracket-clip",
                            },
                        ],
                    },
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    step = document["blocks"][0]
    assert step["type"] == "step"
    assert step["number"] == 4
    assert step["label"] == "Remove Timing Belt Cover"
    assert "Unbolt upper timing belt cover fasteners." in step["text"]
    assert "images" in step
    # 2 unique images, deduplicated from 3 instruction image entries
    assert len(step["images"]) == 2
    assert step["images"][0]["image_id"] == "timing-cover-bolts"
    assert step["images"][1]["image_id"] == "bracket-clip"


def test_table_block_aggregates_row_images_and_deduplicates():
    article = {"article_id": "test-table-row-images"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "table",
                "label": "Torque Specifications",
                "columns": ["Component", "Torque"],
                "images": [
                    {
                        "image_id": "torque-chart-img",
                        "storage_key": "procedure-images/torque-chart",
                        "caption": "Torque Chart",
                    }
                ],
                "rows": [
                    {
                        "cells": ["Caliper Guide Pins", "28 Nm"],
                        "images": [
                            {
                                "image_id": "torque-chart-img",
                                "storage_key": "procedure-images/torque-chart",
                            },
                            {
                                "image_id": "caliper-pin-img",
                                "storage_key": "procedure-images/caliper-pin",
                                "title": "Guide Pin Location",
                            },
                        ],
                    },
                    {
                        "cells": ["Mounting Bracket", "85 Nm"],
                        "images": [
                            {
                                "image_id": "bracket-bolt-img",
                                "url": "https://source.test/bracket.jpg",
                            }
                        ],
                    },
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    table = document["blocks"][0]
    assert table["type"] == "table"
    assert table["label"] == "Torque Specifications"
    assert "images" in table
    # 3 unique images (torque-chart deduplicated, caliper-pin, bracket-bolt)
    assert len(table["images"]) == 3
    assert table["images"][0]["image_id"] == "torque-chart-img"
    assert table["images"][1]["image_id"] == "caliper-pin-img"
    assert table["images"][1]["caption"] == "Guide Pin Location"
    assert table["images"][2]["image_id"] == "bracket-bolt-img"


def test_paragraph_block_deduplicates_attached_images():
    article = {"article_id": "test-paragraph-image-dedup"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "text",
                "text": "Inspect the brake caliper slide pins for corrosion or sticking.",
                "images": [
                    {
                        "image_id": "slide-pins-img",
                        "storage_key": "procedure-images/pins",
                    },
                    {
                        "image_id": "slide-pins-img",
                        "storage_key": "procedure-images/pins",
                    },
                    {
                        "image_id": "grease-tube-img",
                        "storage_key": "procedure-images/silicone-grease",
                    },
                ],
            }
        ],
    )
    assert validate_ordered_document(document) == []
    assert len(document["blocks"]) == 1
    para = document["blocks"][0]
    assert para["type"] == "paragraph"
    assert "images" in para
    assert len(para["images"]) == 2
    assert para["images"][0]["image_id"] == "slide-pins-img"
    assert para["images"][1]["image_id"] == "grease-tube-img"


def test_evidence_ids_extracts_singular_evidence_id():
    from autodata_ingestion.article_document import _evidence_ids

    # Block-level singular evidence_id
    assert _evidence_ids({"evidence_id": "ev-single-1"}, {}) == ["ev-single-1"]
    # Article-level singular evidence_id
    assert _evidence_ids({}, {"evidence_id": "ev-article-single"}) == ["ev-article-single"]
    # Block-level plural overrides article
    assert _evidence_ids({"evidence_ids": ["ev-a", "ev-b"]}, {"evidence_id": "ev-article"}) == ["ev-a", "ev-b"]


def test_image_block_caption_fallback_to_title():
    article = {"article_id": "test-image-caption-title"}
    document = build_ordered_document(
        article,
        [
            {
                "kind": "image",
                "image_id": "caliper-diagram",
                "storage_key": "procedure-images/caliper",
                "title": "Front Brake Caliper Exploded View",
            }
        ],
    )
    assert validate_ordered_document(document) == []
    img = document["blocks"][0]
    assert img["type"] == "image"
    assert img["caption"] == "Front Brake Caliper Exploded View"
    assert img["alt"] == "Front Brake Caliper Exploded View"
