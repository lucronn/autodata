from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.procedure_normalize import normalize_procedure_article


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
