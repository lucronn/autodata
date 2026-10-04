from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.article_document import (
    NORMALIZATION_VERSION,
    build_ordered_document,
    validate_ordered_document,
)


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


def test_document_validation_requires_evidence_for_each_retained_block():
    document = build_ordered_document(
        {"article_id": "article-2", "evidence_ids": ["e-source"]},
        [
            {"kind": "text", "text": "Remove the seal.", "evidence_ids": ["e-source"]},
            {"kind": "callout", "label": "Warning", "text": "Wear eye protection.", "evidence_ids": []},
            {"kind": "image", "url": "https://source.test/seal.svg", "evidence_ids": ["e-source"]},
        ],
    )

    assert [block["source_order"] for block in document["blocks"]] == [1, 2, 3]
    assert document["blocks"][1]["evidence_ids"] == []
    assert "block 2 has no evidence_ids" in validate_ordered_document(document)


def test_document_builder_retains_unknown_rows_without_inventing_evidence():
    document = build_ordered_document(
        {"article_id": "article-3"},
        [
            {"kind": "widget", "text": "Unsupported source material"},
            {"kind": "heading", "text": ""},
            {"kind": "text", "text": "Remove the seal."},
        ],
    )

    assert len(document["blocks"]) == 3
    assert [block["source_order"] for block in document["blocks"]] == [1, 2, 3]
    assert [block["type"] for block in document["blocks"]] == ["unknown", "unknown", "paragraph"]
    assert all(block["evidence_ids"] == [] for block in document["blocks"])


def test_structural_break_does_not_require_content_evidence():
    document = build_ordered_document(
        {"article_id": "article-4", "evidence_ids": ["e-source"]},
        [
            {"kind": "text", "text": "Remove the seal.", "evidence_ids": ["e-source"]},
            {"kind": "break", "evidence_ids": []},
            {"kind": "text", "text": "Install the seal.", "evidence_ids": ["e-source"]},
        ],
    )

    assert validate_ordered_document(document) == []
