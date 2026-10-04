from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.procedure_normalize import (
    article_is_content_complete,
    is_meaningful_procedure_text,
    normalize_procedure_article,
)
from autodata_ingestion.article_document import build_ordered_document


def test_rebuilds_empty_ordered_document_from_legacy_steps_in_place_order():
    article = {
        "article_id": "autoapitwo:50582:210189",
        "content_status": "content_complete",
        "body": "Disconnect the connector. Remove the assembly.",
        "source_original": {"immutable": True},
        "steps": [
            {
                "number": 1,
                "heading": "Disconnect the connector.",
                "instructions": ["Unplug the harness."],
                "images": [],
            },
            {
                "number": 2,
                "heading": "Remove the assembly.",
                "instructions": ["Remove the two fasteners."],
                "images": [{"image_id": "figure-1", "alt": "Fastener location"}],
            },
        ],
        "normalized_document": {
            "schema_version": 1,
            "normalization_version": "ordered-article-v1",
            "blocks": [],
        },
    }

    normalized = normalize_procedure_article(article)

    blocks = normalized["normalized_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["step", "paragraph", "step", "paragraph", "image"]
    assert [block["source_order"] for block in blocks] == [1, 2, 3, 4, 5]
    assert (blocks[0]["number"], blocks[0]["text"]) == (1, "Disconnect the connector.")
    assert (blocks[2]["number"], blocks[2]["text"]) == (2, "Remove the assembly.")
    assert blocks[4]["image_id"] == "figure-1"
    assert normalized["source_original"] == article["source_original"]
    assert article["normalized_document"]["blocks"] == []


def test_expands_provider_ordered_list_items_into_separate_ordered_procedure_steps():
    normalized = normalize_procedure_article({
        "article_id": "autoapitwo:example:oil-pump",
        "title": "Engine Oil Pump - Removal",
        "component": "oil_pump",
        "procedure_kind": "removal",
        "evidence_ids": ["e-oil-pump"],
        "blocks": [
            {"kind": "text", "text": "7L DIESEL", "evidence_ids": ["e-oil-pump"]},
            {"kind": "text", "text": "REMOVAL", "evidence_ids": ["e-oil-pump"]},
            {"kind": "ordered_list", "start": 1, "items": [
                "Disconnect the negative battery cable.",
                "Remove the oil pan bolts in sequence.",
                "Lift out the oil pump assembly.",
            ], "evidence_ids": ["e-oil-pump"]},
        ],
        "source_original": {"retained": True},
    })

    assert [step["action"] for step in normalized["steps"]] == [
        "Disconnect the negative battery cable.",
        "Remove the oil pan bolts in sequence.",
        "Lift out the oil pump assembly.",
    ]
    assert normalized["content_status"] == "content_complete"


def test_missing_block_evidence_keeps_article_incomplete_and_preserves_order():
    normalized = normalize_procedure_article({
        "article_id": "autoapitwo:example:mixed",
        "title": "Oil Pump - Removal",
        "component": "oil_pump",
        "procedure_kind": "removal",
        "evidence_ids": ["e-source"],
        "blocks": [
            {"kind": "text", "text": "Remove the oil pump.", "evidence_ids": ["e-source"]},
            {"kind": "table", "rows": [["Tool", "8498"]], "evidence_ids": []},
            {"kind": "callout", "text": "Wear eye protection.", "evidence_ids": ["e-source"]},
            {"kind": "image", "url": "https://source.test/pump.svg", "evidence_ids": ["e-source"]},
        ],
    })

    assert normalized["content_status"] == "list_only"
    assert [block["source_order"] for block in normalized["normalized_document"]["blocks"]] == [1, 2, 3, 4]
    assert normalized["normalized_document"]["blocks"][1]["evidence_ids"] == []


def test_unknown_retained_block_and_unresolved_evidence_cannot_be_complete():
    normalized = normalize_procedure_article({
        "article_id": "autoapitwo:example:unknown",
        "title": "Starter - Removal",
        "component": "starter",
        "procedure_kind": "removal",
        "evidence_ids": ["e-source"],
        "blocks": [
            {"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-not-from-article"]},
            {"kind": "widget", "text": "Review this source row.", "evidence_ids": ["e-source"]},
        ],
    })

    assert normalized["content_status"] == "list_only"
    assert [block["source_order"] for block in normalized["normalized_document"]["blocks"]] == [1, 2]


def test_block_evidence_without_article_evidence_cannot_be_complete():
    normalized = normalize_procedure_article({
        "article_id": "autoapitwo:example:unresolved",
        "title": "Starter - Removal",
        "component": "starter",
        "procedure_kind": "removal",
        "blocks": [
            {"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-not-resolvable"]},
        ],
    })

    assert normalized["content_status"] == "list_only"


def test_prior_complete_status_and_source_original_do_not_bypass_unresolved_evidence():
    article = {
        "article_id": "autoapitwo:example:legacy",
        "content_status": "content_complete",
        "source_original": {"immutable": True},
        "steps": [{"action": "Remove the starter.", "instructions": []}],
        "normalized_document": build_ordered_document(
            {"article_id": "autoapitwo:example:legacy"},
            [{"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-block"]}],
        ),
    }

    assert article_is_content_complete(article) is False


def test_normalized_document_ids_do_not_self_certify_projection_reads():
    document = build_ordered_document(
        {"article_id": "autoapitwo:example:projected", "evidence_id": "e-source"},
        [{"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-source"]}],
    )
    projected_article = {
        "article_id": "autoapitwo:example:projected",
        "content_status": "content_complete",
        "source_original": {"immutable": True},
        "steps": [{"action": "Remove the starter.", "instructions": []}],
        "normalized_document": document,
    }

    assert document["evidence_ids"] == ["e-source"]
    assert article_is_content_complete(projected_article) is False


def test_complete_mixed_document_requires_evidence_and_matching_source_snapshot():
    article = {
        "article_id": "autoapitwo:example:complete",
        "title": "Starter - Removal",
        "component": "starter",
        "procedure_kind": "removal",
        "source_snapshot_id": "snapshot-1",
        "evidence": [{"evidence_id": "e-source", "source_snapshot_id": "snapshot-1"}],
        "evidence_ids": ["e-source"],
        "blocks": [
            {"kind": "heading", "text": "REMOVAL", "evidence_ids": ["e-source"]},
            {"kind": "table", "rows": [["Tool", "8498"]], "evidence_ids": ["e-source"]},
            {"kind": "callout", "text": "Wear eye protection.", "evidence_ids": ["e-source"]},
            {"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-source"]},
            {"kind": "image", "url": "https://source.test/starter.svg", "evidence_ids": ["e-source"]},
        ],
    }

    normalized = normalize_procedure_article(article)

    assert normalized["content_status"] == "content_complete"
    assert article_is_content_complete(normalized) is True


def test_stale_content_complete_label_does_not_make_metadata_only_steps_usable():
    for label in (
        "7L DIESEL",
        "7L",
        "5.7 L",
        "The oil pump is located inside the oil pan.",
    ):
        article = {
            "content_status": "content_complete",
            "title": "Generator - Removal",
            "component": "alternator",
            "body": label,
            "steps": [{"action": label, "instructions": []}],
        }

        assert article_is_content_complete(article) is False


def test_accepts_common_conditional_and_purpose_prefixed_repair_instructions():
    assert is_meaningful_procedure_text("Remove the oil pump assembly.")
    assert is_meaningful_procedure_text("If equipped, disconnect the sensor connector.")
    assert is_meaningful_procedure_text("To access the pump, remove the oil pan.")
    assert is_meaningful_procedure_text("Before installation, clean the mounting surface.")
