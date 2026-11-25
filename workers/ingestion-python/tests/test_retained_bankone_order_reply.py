from copy import deepcopy

import pytest

from autodata_ingestion.article_document import build_ordered_document
from autodata_ingestion.article_lifecycle_types import SOURCE_BOUND_CORRECTION_PROFILE, digest_json
from autodata_ingestion.procedure_rewrite_auto import render_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.retained_bankone_order_reply import BANKONE_ORDER_METHOD, repair_bankone_order


_PROFILE = SOURCE_BOUND_CORRECTION_PROFILE
_PROMPT = "full-prose-auto-prompt-v55"
_TITLE = "Seal Service"


def _image(caption, digest):
    return {
        "kind": "image",
        "image_id": digest * 64,
        "storage_key": f"sources/{digest * 16}/{digest * 64}",
        "content_sha256": digest * 64,
        "media_type": "image/png",
        "alt": caption,
        "caption": caption,
        "evidence_ids": ["fixture-evidence"],
    }


def _document(blocks):
    return build_ordered_document({"article_id": "fixture", "evidence_ids": ["fixture-evidence"]}, blocks)


def _fixture():
    title = {"kind": "paragraph", "text": _TITLE}
    promoted = {"kind": "heading", "level": 1, "text": _TITLE}
    removal = {"kind": "paragraph", "text": "Remove the pump."}
    installation = {"kind": "paragraph", "text": "Install the cover."}
    warning = {"kind": "warning", "text": "Do not reuse the seal."}
    table = {"kind": "table", "columns": ["Component", "Torque"], "rows": [["Cover", "40 Nm"]]}
    first = _image("Pump alignment marks", "a")
    last = _image("Seal overview", "b")
    old = _document([title, removal, warning, table, first, title, installation, last])
    repaired = _document([
        promoted, installation, warning, table, {**first, "alt": "Marks on the pump"},
        {"kind": "unordered_list", "items": [_TITLE, removal["text"]]}, last,
    ])
    response = {
        "introduction": "This procedure covers the pump and seal.",
        "replacements": [
            {**slot, "action": "rewrite", "text": text, "reason": ""}
            for slot, text in zip(
                prose_slots(old, include_cell_blocks=True),
                ("Servicing the seal", "Take the pump off.", "Servicing the seal", "Fit the cover in place."),
                strict=True,
            )
        ],
    }
    return old, _publish(old, response), repaired, response


def _publish(source, reply):
    return render_auto(source, reply, prompt_version=_PROMPT, profile_version=_PROFILE)


def _repair(old, published, repaired, response):
    return repair_bankone_order(old, published, repaired, response=response, prompt_version=_PROMPT, profile=_PROFILE)


def test_reorders_saved_effective_reply_and_preserves_protected_source_structure():
    old, published, repaired, response = fixture = _fixture()
    before = deepcopy(fixture)

    result = _repair(*fixture)

    assert result == _repair(*fixture)
    assert result.validation.passed
    intro, heading, installation, warning, table, first, procedures, last = result.document["blocks"]
    assert intro["text"] == published["blocks"][0]["text"]
    assert intro["evidence_ids"] == published["blocks"][0]["evidence_ids"]
    assert heading["type"] == "heading" and heading["text"] == _TITLE
    assert installation["text"] == "Fit the cover in place."
    assert warning["type"] == "callout" and warning["label"] == "WARNING"
    assert warning["text"] == "Do not reuse the seal."
    assert table["rows"] == [["Cover", "40 Nm"]]
    assert first["caption"] == "Pump alignment marks" and first["alt"] == "Marks on the pump"
    assert procedures["items"] == ["Servicing the seal", "Take the pump off."]
    assert result.projection["images"] == [first, last]
    assert result.provenance["transformation_method"] == BANKONE_ORDER_METHOD
    assert result.provenance["original_response_hash"] == digest_json(response)
    assert result.provenance["remapped_response_hash"] == digest_json(result.remapped_response)
    assert result.provenance["repaired_published_document_hash"] == digest_json(result.document)
    assert fixture == before


def test_requires_exact_saved_publication_and_row_binding():
    old, published, repaired, response = _fixture()
    response["replacements"][0]["path"] = "/blocks/5/text"
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_PUBLISHED_BINDING_MISMATCH$"):
        _repair(old, published, repaired, response)


def test_rejects_ambiguous_effective_wording_for_a_repeated_source_slot():
    old, _, repaired, response = _fixture()
    response["replacements"][2]["text"] = "Work on the seal"
    published = _publish(old, response)
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_SLOT_DRIFT$"):
        _repair(old, published, repaired, response)


@pytest.mark.parametrize(("block_index", "changes"), [
    (1, {"text": "Install a new cover."}),
    (2, {"type": "paragraph"}),
    (3, {"columns": ["Torque", "Component"], "rows": [["40 Nm", "Cover"]]}),
    (4, {"content_sha256": "c" * 64, "storage_key": f"sources/{'c' * 16}/{'c' * 64}"}),
])
def test_rejects_source_prose_warning_table_or_figure_drift(block_index, changes):
    old, published, repaired, response = _fixture()
    repaired["blocks"][block_index].update(changes)
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_SOURCE_DRIFT$"):
        _repair(old, published, repaired, response)


def test_requires_authored_order_change():
    old, published, _, response = _fixture()
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_SOURCE_DRIFT$"):
        _repair(old, published, old, response)


def test_rejects_rearranged_type_without_exact_authored_heading_proof():
    old, published, repaired, response = _fixture()
    repaired["blocks"][0]["type"] = "paragraph"
    del repaired["blocks"][0]["level"]
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_SLOT_DRIFT$"):
        _repair(old, published, repaired, response)


def test_rejects_newly_editable_prose_even_when_exact_text_is_unchanged():
    old, published, repaired, response = _fixture()
    items = repaired["blocks"][5]["items"]
    repaired["blocks"][5]["items"] = ["\n".join(items)]
    with pytest.raises(ValueError, match="^PUBLISHED_BANKONE_ORDER_SLOT_DRIFT$"):
        _repair(old, published, repaired, response)
