from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.procedure_normalize import (
    article_is_content_complete,
    normalize_procedure_article,
)


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
        "blocks": [
            {"kind": "text", "text": "7L DIESEL"},
            {"kind": "text", "text": "REMOVAL"},
            {"kind": "ordered_list", "start": 1, "items": [
                "Disconnect the negative battery cable.",
                "Remove the oil pan bolts in sequence.",
                "Lift out the oil pump assembly.",
            ]},
        ],
        "source_original": {"retained": True},
    })

    assert [step["action"] for step in normalized["steps"]] == [
        "Disconnect the negative battery cable.",
        "Remove the oil pan bolts in sequence.",
        "Lift out the oil pump assembly.",
    ]
    assert normalized["content_status"] == "content_complete"


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
