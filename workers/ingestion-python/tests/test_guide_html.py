from __future__ import annotations

from base64 import b64encode
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.guide_html import render_guide_html


PNG_BYTES = b"\x89PNG\r\n\x1a\nhtml-guide-fixture"


def complete_guide() -> dict:
    return {
        "title": "Pump <Replacement> Guide",
        "applicability": "1997 Toyota RAV4 <4WD>",
        "revision_id": "guide:revision-1",
        "source_watermark": "source-v1 <trusted>",
        "content_status": "complete",
        "pdf_ready": True,
        "review_state": "UNREVIEWED",
        "review_label": "UNREVIEWED — human review pending",
        "preparation": ["Wear <eye protection> before starting."],
        "warnings": [{"message": "Disconnect the battery before service."}],
        "evidence_ids": ["guide-evidence-1"],
        "steps": [
            {
                "sequence": 1,
                "action": "Remove the pump.",
                "instructions": ["Follow evidence <A>."],
                "evidence_ids": ["step-evidence-1"],
                "images": [
                    {
                        "media_type": "image/png",
                        "alt": "Pump removal view",
                        "image_bytes": PNG_BYTES,
                    }
                ],
            },
            {
                "sequence": 2,
                "action": "Install the pump.",
                "instructions": ["Tighten the bolts."],
                "evidence_ids": ["step-evidence-2"],
                "images": [],
            },
        ],
    }


def test_render_guide_html_is_deterministic_standalone_and_escapes_content():
    guide = complete_guide()

    first = render_guide_html(guide)
    second = render_guide_html(guide)

    assert isinstance(first, bytes)
    assert first == second
    document = first.decode("utf-8")
    assert document.startswith("<!doctype html>")
    assert "<style>" in document
    assert "https://" not in document
    assert "Pump &lt;Replacement&gt; Guide" in document
    assert "1997 Toyota RAV4 &lt;4WD&gt;" in document
    assert "Wear &lt;eye protection&gt;" in document
    assert "Follow evidence &lt;A&gt;." in document
    assert "source-v1 &lt;trusted&gt;" in document
    assert "guide:revision-1" in document
    assert "UNREVIEWED" in document
    assert "<ol" in document
    assert document.index("Remove the pump.") < document.index("Install the pump.")
    assert "guide-evidence-1" in document
    assert "step-evidence-1" in document


def test_render_guide_html_embeds_all_images_and_filters_generic_captions():
    guide = complete_guide()
    guide["steps"][0]["images"] = [
        {
            "media_type": "image/png",
            "alt": "Pump removal view",
            "image_bytes": PNG_BYTES,
        },
        {
            "media_type": "image/png",
            "alt": "image",
            "image_bytes": b"second-image",
        },
    ]

    document = render_guide_html(guide).decode("utf-8")

    assert f"data:image/png;base64,{b64encode(PNG_BYTES).decode('ascii')}" in document
    assert f"data:image/png;base64,{b64encode(b'second-image').decode('ascii')}" in document
    assert document.count("<figure") == 2
    assert "<figcaption>Pump removal view</figcaption>" in document
    assert "<figcaption>image</figcaption>" not in document


@pytest.mark.parametrize(
    "guide",
    [
        {"content_status": "partial", "pdf_ready": False},
        {
            **complete_guide(),
            "steps": [
                {
                    "action": "Install the pump.",
                    "images": [{"url": "https://example.test/pump.png"}],
                }
            ],
        },
    ],
)
def test_render_guide_html_rejects_incomplete_or_unprepared_guides(guide):
    with pytest.raises(ValueError, match="complete|prepared"):
        render_guide_html(guide)
