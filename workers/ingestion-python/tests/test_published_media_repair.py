from copy import deepcopy

import pytest

from autodata_ingestion.article_document import build_ordered_document
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE,
    SOURCE_BOUND_CORRECTION_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, digest_json,
)
from autodata_ingestion.bankone_first_draft_structure import extract_bankone_structure
from autodata_ingestion.procedure_rewrite import editable_slots, rewrite_ordered_document
from autodata_ingestion.procedure_rewrite_auto import render_auto
from autodata_ingestion.procedure_rewrite_fidelity import recast_conditional_color_note
from autodata_ingestion.procedure_rewrite_full import prose_slots, render_full
from autodata_ingestion.procedure_rewrite_recovery import (
    BANKONE_LINKED_RECOVERY_METHOD, recover_structured_bankone_first_draft,
)
from autodata_ingestion.procedure_rewrite_v2 import plan_v2, render_v2
from autodata_ingestion.published_media_repair import repair_published_media

from test_bankone_first_draft_recovery import linked_fixture

_CURRENT_PROMPT = "full-prose-auto-prompt-v6"
_HISTORICAL_PROMPT = "full-prose-auto-prompt-v2"


def _image(caption="Pump alignment marks", digest_char="a"):
    return {
        "kind": "image",
        "image_id": digest_char * 64,
        "storage_key": f"sources/{digest_char * 16}/{digest_char * 64}",
        "content_sha256": digest_char * 64,
        "media_type": "image/png",
        "alt": caption,
        "caption": caption,
        "evidence_ids": ["fixture-evidence"],
    }


def _document(blocks):
    return build_ordered_document({"article_id": "fixture", "evidence_ids": ["fixture-evidence"]}, blocks)


def _response(source, replacements, *, introduction="This procedure covers the pump and seal."):
    return {
        "introduction": introduction,
        "replacements": [
            {**slot, "action": "rewrite", "text": text, "reason": ""}
            for slot, text in zip(prose_slots(source), replacements, strict=True)
        ],
    }


def _fixture():
    begin = {"kind": "step", "number": 1, "text": "Remove the pump."}
    warning = {"kind": "warning", "text": "Do not reuse the seal."}
    table = {"kind": "table", "columns": ["Component", "Torque"], "rows": [["Cover", "40 Nm"]]}
    end = {"kind": "step", "number": 2, "text": "Install the cover."}
    image = _image()
    old = _document([begin, warning, table, end, image])
    repaired = _document([begin, image, warning, table, end])
    response = _response(old, ["Take the pump off.", "Fit the cover in place."])
    published = render_auto(old, response, prompt_version=_CURRENT_PROMPT)
    return old, published, repaired, response


@pytest.mark.parametrize("profile,prompt_version", [
    (AUTOMATIC_REWRITE_PROFILE, _CURRENT_PROMPT),
    (SOURCE_BOUND_REWRITE_PROFILE, "full-prose-auto-prompt-v55"),
])
def test_placement_repair_keeps_exact_published_prose_and_protected_fields(profile, prompt_version):
    old, _, repaired, response = _fixture()
    published = render_auto(old, response, prompt_version=prompt_version, profile_version=profile)
    before = deepcopy((old, published, repaired, response))

    result = repair_published_media(old, published, repaired, response=response, prompt_version=prompt_version,
                                    profile=profile)

    assert result == repair_published_media(old, published, repaired, response=response, prompt_version=prompt_version,
                                            profile=profile)
    introduction, first, figure, warning, table, second = result.document["blocks"]
    assert introduction["text"] == published["blocks"][0]["text"]
    assert introduction["evidence_ids"] == published["blocks"][0]["evidence_ids"]
    assert introduction["block_id"] != published["blocks"][0]["block_id"]
    assert first["text"] == published["blocks"][1]["text"]
    assert second["text"] == published["blocks"][4]["text"]
    assert (first["number"], second["number"]) == (1, 2)
    assert warning["text"] == "Do not reuse the seal."
    assert warning["label"] == "WARNING"
    assert table["rows"] == [["Cover", "40 Nm"]]
    assert table["columns"] == ["Component", "Torque"]
    assert all(block["evidence_ids"] == ["fixture-evidence"] for block in result.document["blocks"])
    assert figure["caption"] == "Pump alignment marks"
    assert figure["storage_key"] == repaired["blocks"][1]["storage_key"]
    assert result.projection["images"] == [figure]
    assert [row["path"] for row in result.remapped_response["replacements"]] == ["/blocks/0/text", "/blocks/4/text"]
    assert result.validation.passed
    assert result.validation.report["profile_version"] == profile
    assert result.provenance["original_published_document_hash"] == digest_json(published)
    assert result.provenance["repaired_published_document_hash"] == digest_json(result.document)
    assert result.provenance["original_response_hash"] == digest_json(response)
    assert result.provenance["remapped_response_hash"] == digest_json(result.remapped_response)
    assert (old, published, repaired, response) == before


def test_moves_figure_into_structured_item_and_keeps_distinct_repeated_slot_prose():
    items = ["Inspect the seal.", "Inspect the seal."]
    image = _image()
    old = _document([{"kind": "ordered_list", "items": items}, image])
    repaired = _document([{"kind": "ordered_list", "items": [
        {"text": items[0], "blocks": [image]},
        items[1],
    ]}])
    response = _response(old, ["Check the seal condition.", "Check the sealing surface."])
    published = render_auto(old, response, prompt_version=_CURRENT_PROMPT)

    result = repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)

    first, second = result.document["blocks"][1]["items"]
    assert first["text"] == "Check the seal condition."
    assert first["blocks"][0]["alt"] == "Pump alignment marks"
    assert second == "Check the sealing surface."
    assert [row["path"] for row in result.remapped_response["replacements"]] == [
        "/blocks/0/items/0/text", "/blocks/0/items/1",
    ]


def test_image_can_move_to_table_cell_without_changing_specification_or_prose():
    image = _image()
    caption = {"kind": "paragraph", "text": "Inspect the cover."}
    old = _document([caption, {"kind": "table", "rows": [["Cover", "40 Nm"]]}, image])
    repaired = _document([caption, {"kind": "table", "rows": [
        ["Cover", {"text": "40 Nm", "images": [image]}],
    ]}])
    response = _response(old, ["Check the cover condition."])
    published = render_auto(old, response, prompt_version=_CURRENT_PROMPT)

    result = repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)

    cover, torque = result.document["blocks"][2]["rows"][0]
    assert cover == "Cover"
    assert torque["text"] == "40 Nm"
    assert torque["images"][0]["content_sha256"] == image["content_sha256"]
    assert result.document["blocks"][1]["text"] == "Check the cover condition."


def test_historical_model_output_uses_original_prompt_rules():
    old, _, repaired, _ = _fixture()
    response = _response(old, ["Take the pump out.", "Fit the cover in place."])
    published = render_auto(old, response, prompt_version=_HISTORICAL_PROMPT)

    result = repair_published_media(old, published, repaired, response=response, prompt_version=_HISTORICAL_PROMPT)

    assert result.document["blocks"][1]["text"] == "Take the pump out."
    assert result.provenance["original_prompt_version"] == _HISTORICAL_PROMPT


@pytest.mark.parametrize("prompt_version", [
    "full-prose-auto-prompt-v11", "full-prose-auto-prompt-v12", "full-prose-auto-prompt-v13",
    "full-prose-auto-prompt-v14", "full-prose-auto-prompt-v15",
    "full-prose-auto-prompt-v16", "full-prose-auto-prompt-v17",
    "full-prose-auto-prompt-v18", "full-prose-auto-prompt-v19",
    "full-prose-auto-prompt-v20", "full-prose-auto-prompt-v21",
    "full-prose-auto-prompt-v22", "full-prose-auto-prompt-v23",
    "full-prose-auto-prompt-v24", "full-prose-auto-prompt-v25", "full-prose-auto-prompt-v26",
    "full-prose-auto-prompt-v27", "full-prose-auto-prompt-v28", "full-prose-auto-prompt-v29",
    "full-prose-auto-prompt-v30",
    "full-prose-auto-prompt-v31",
    "full-prose-auto-prompt-v32",
    "full-prose-auto-prompt-v33",
    "full-prose-auto-prompt-v34",
    "full-prose-auto-prompt-v35",
    "full-prose-auto-prompt-v36",
    "full-prose-auto-prompt-v37",
    "full-prose-auto-prompt-v38",
    "full-prose-auto-prompt-v39",
    "full-prose-auto-prompt-v40",
    "full-prose-auto-prompt-v41",
    "full-prose-auto-prompt-v42",
    "full-prose-auto-prompt-v43",
    "full-prose-auto-prompt-v44",
    "full-prose-auto-prompt-v45",
    "full-prose-auto-prompt-v46",
    "full-prose-auto-prompt-v47",
    "full-prose-auto-prompt-v48",
    "full-prose-auto-prompt-v49",
    "full-prose-auto-prompt-v50",
    "full-prose-auto-prompt-v51",
    "full-prose-auto-prompt-v52",
    "full-prose-auto-prompt-v53",
    "full-prose-auto-prompt-v54",
    "full-prose-auto-prompt-v55",
])
def test_repair_replays_cell_prose_with_original_prompt_version(prompt_version):
    text = "Remove the cover while the ignition is off."
    draft = "With the ignition off, take the cover off."
    instruction = _document([{"kind": "text", "text": text}])["blocks"][0]
    instruction["block_id"] = "nested-cell-instruction"
    old = _document([{"kind": "table", "rows": [["25 Nm"]]}, _image()])
    old["blocks"][0]["rows"][0][0] = {"text": "25 Nm", "blocks": [instruction]}
    repaired = deepcopy(old)
    figure = repaired["blocks"].pop()
    figure["source_order"] = 1
    cell = repaired["blocks"][0]["rows"][0][0]
    cell["blocks"][0]["source_order"] = 2
    cell["blocks"].insert(0, figure)
    payload = {"introduction": "This procedure describes component access.", "replacements": [
        {**prose_slots(old, include_cell_blocks=True)[0], "action": "rewrite", "text": draft, "reason": ""},
    ]}
    published = render_auto(old, payload, prompt_version=prompt_version)

    result = repair_published_media(old, published, repaired, response=payload, prompt_version=prompt_version)

    repaired_cell = result.document["blocks"][1]["rows"][0][0]
    assert repaired_cell["text"] == "25 Nm"
    assert repaired_cell["blocks"][0] == figure
    assert repaired_cell["blocks"][1]["text"] == draft
    assert result.remapped_response["replacements"][0]["path"] == "/blocks/0/rows/0/0/blocks/1/text"
    assert result.validation.passed
    assert result.provenance["original_prompt_version"] == prompt_version
    assert result.provenance["model_dispatch_count"] == 0


def test_reviewed_repair_preserves_approved_effective_response():
    old, _, repaired, _ = _fixture()
    corrected_response = _response(old, ["Take the pump off.", "Fit the cover in place."])
    corrected_response["introduction"] = "This procedure describes pump and cover service."
    published = render_full(old, corrected_response)

    result = repair_published_media(
        old, published, repaired, response=corrected_response, profile="full-prose-review-v1",
    )

    assert result.validation.passed
    assert result.validation.report["content_acceptance_required"]
    assert result.provenance["profile_version"] == "full-prose-review-v1"
    assert result.provenance["original_prompt_version"] is None
    assert result.document["blocks"][0]["text"] == corrected_response["introduction"]
    assert result.document["blocks"][4]["rows"][0][1] == "40 Nm"
    assert result.document["blocks"][-1]["text"] == "Fit the cover in place."


def test_reviewed_repair_rejects_original_response_after_correction():
    old, _, repaired, original = _fixture()
    corrected = deepcopy(original)
    corrected["introduction"] = "This procedure describes pump and cover service."
    published = render_full(old, corrected)
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH$"):
        repair_published_media(old, published, repaired, response=original, profile="full-prose-review-v1")


def _technical_sources():
    remove = {"kind": "step", "number": 1, "text": "Remove the pump."}
    warning = {"kind": "warning", "text": "Do not reuse the seal."}
    specification = {"kind": "step", "number": 2, "text": "Tighten the bolts to 40 Nm."}
    install = {"kind": "step", "number": 3, "text": "Install the cover."}
    image = _image()
    return (
        _document([remove, warning, specification, install, image]),
        _document([remove, warning, image, specification, install]),
    )


def _v1_reply(document):
    saved = {"Remove the pump.": "Take off the pump.", "Install the cover.": "Fit the cover."}
    return {
        "replacements": [{**slot, "text": saved[slot["text"]]} for slot in editable_slots(document)],
    }


def _v2_reply(document):
    return {"operations": [
        {key: operation[key] for key in ("block_id", "path", "operation_id")}
        for operation in plan_v2(document)["operations"]
    ]}


def test_technical_v1_keeps_original_saved_prose_under_exact_remapped_paths():
    old, repaired = _technical_sources()
    saved = _v1_reply(old)

    class SavedResponse:
        def complete_json(self, _prompt):
            return saved

    original = rewrite_ordered_document(
        old, client=SavedResponse(), context={}, profile_version="technical-prose-v1",
    )
    assert original.error_code is None
    result = repair_published_media(
        old, original.document, repaired, response=saved, profile="technical-prose-v1",
    )

    assert result.remapped_response == _v1_reply(repaired)
    assert set(result.remapped_response) == {"replacements"}
    assert all(set(row) == {"block_id", "path", "text"} for row in result.remapped_response["replacements"])
    assert [row["path"] for row in result.remapped_response["replacements"]] == ["/blocks/0/text", "/blocks/4/text"]
    first, warning, figure, specification, last = result.document["blocks"]
    assert (first["text"], warning["text"], specification["text"], last["text"]) == (
        "Take off the pump.", "Do not reuse the seal.", "Tighten the bolts to 40 Nm.", "Fit the cover.",
    )
    assert figure == repaired["blocks"][2]
    assert result.validation.report["validator_version"] == "technical-prose-validator-v1"
    assert result.provenance["model_calls"] == 0


def test_technical_v1_rejects_valid_but_different_words_from_the_bound_reply():
    old, repaired = _technical_sources()
    saved = _v1_reply(old)

    class SavedResponse:
        def complete_json(self, _prompt):
            return saved

    original = rewrite_ordered_document(old, client=SavedResponse(), context={})
    assert original.error_code is None
    different = deepcopy(saved)
    different["replacements"][0]["text"] = "Lift off the pump."
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH$"):
        repair_published_media(
            old, original.document, repaired, response=different, profile="technical-prose-v1",
        )


def test_technical_v2_rebinds_all_operation_ids_and_preserves_exact_rendered_text():
    old, repaired = _technical_sources()
    saved = _v2_reply(old)
    original = render_v2(old, saved)
    result = repair_published_media(
        old, original, repaired, response=saved, profile="technical-prose-v2",
    )

    assert result.remapped_response == _v2_reply(repaired)
    assert all(
        previous["operation_id"] != following["operation_id"]
        for previous, following in zip(saved["operations"], result.remapped_response["operations"], strict=True)
    )
    assert all(set(row) == {"block_id", "path", "operation_id"} for row in result.remapped_response["operations"])
    assert [block["text"] for block in result.document["blocks"] if "text" in block] == [
        "The pump is to be removed.", "Do not reuse the seal.",
        "The bolts are to be tightened to 40 Nm.", "The cover is to be installed.",
    ]
    assert result.document["blocks"][2] == repaired["blocks"][2]
    assert result.validation.report["validator_version"] == "technical-prose-validator-v2"
    assert result.provenance["model_calls"] == 0


@pytest.mark.parametrize("mutation", ["incomplete", "reordered", "prose", "new_source"])
def test_technical_v2_rejects_an_unbound_or_ambiguous_selector(mutation):
    old, repaired = _technical_sources()
    saved = _v2_reply(old)
    published = render_v2(old, saved)
    if mutation == "incomplete":
        saved["operations"].pop()
    elif mutation == "reordered":
        saved["operations"].reverse()
    elif mutation == "prose":
        saved["operations"][0]["text"] = "Remove the pump."
    else:
        saved = _v2_reply(repaired)
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH$"):
        repair_published_media(old, published, repaired, response=saved, profile="technical-prose-v2")


def test_other_rewrite_profiles_are_outside_the_repair_contract():
    old, published, repaired, response = _fixture()
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PROFILE_UNSUPPORTED$"):
        repair_published_media(old, published, repaired, response=response, profile="technical-prose-v3")


@pytest.mark.parametrize("mutation", ["text", "warning", "torque", "evidence", "order", "inserted"])
def test_repair_rejects_any_nonmedia_drift(mutation):
    old, published, repaired, response = _fixture()
    blocks = repaired["blocks"]
    if mutation == "text":
        blocks[0]["text"] = "Remove the bolt."
    elif mutation == "warning":
        blocks[2]["text"] = "Reuse the seal."
    elif mutation == "torque":
        blocks[3]["rows"][0][1] = "50 Nm"
    elif mutation == "evidence":
        blocks[2]["evidence_ids"] = ["different-source"]
    elif mutation == "order":
        blocks[2], blocks[3] = blocks[3], blocks[2]
        for index, block in enumerate(blocks, 1):
            block["source_order"] = index
    else:
        new = deepcopy(blocks[-1])
        new.update(block_id="extra", source_order=6, text="Inspect the flange.")
        blocks.append(new)
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_SOURCE_TEXT_DRIFT$"):
        repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)


@pytest.mark.parametrize("field,value", [
    ("caption", "Different illustration"),
    ("evidence_ids", ["other-evidence"]),
    ("storage_key", "sources/other"),
    ("content_sha256", "b" * 64),
])
def test_repair_rejects_changed_media_payload_or_attribution(field, value):
    old, published, repaired, response = _fixture()
    repaired["blocks"][1][field] = value
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_MEDIA_DRIFT$"):
        repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)


def test_repair_rejects_a_revision_without_a_media_placement_change():
    old, published, _, response = _fixture()
    unchanged_placement = deepcopy(old)
    unchanged_placement["blocks"][0]["block_id"] = "renumbered"
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_UNCHANGED$"):
        repair_published_media(old, published, unchanged_placement, response=response, prompt_version=_CURRENT_PROMPT)


@pytest.mark.parametrize("origin", ["canonical", "response", "missing_response"])
def test_repair_rejects_unbound_publication_and_response(origin):
    old, published, repaired, response = _fixture()
    if origin == "canonical":
        published["blocks"][1]["text"] = "Lift the pump off."
    elif origin == "response":
        response["replacements"][0]["text"] = "Lift the pump off."
    else:
        response = None
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH$"):
        repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)


def test_retained_technical_rows_and_reasons_survive_repositioning():
    image = _image()
    block = {"kind": "step", "text": "Tighten the cover bolts to 40 Nm."}
    old = _document([block, image])
    repaired = _document([image, block])
    response = {
        "introduction": "This procedure covers the cover bolts.",
        "replacements": [
            {**prose_slots(old)[0], "action": "retain", "reason": "Keep the exact specification."},
        ],
    }
    published = render_auto(old, response, prompt_version=_CURRENT_PROMPT)

    result = repair_published_media(old, published, repaired, response=response, prompt_version=_CURRENT_PROMPT)

    assert result.remapped_response["replacements"][0] == {
        **prose_slots(repaired)[0], "action": "retain", "reason": "Keep the exact specification.",
    }
    assert result.document["blocks"][-1]["text"] == block["text"]
    assert result.provenance["model_calls"] == result.provenance["model_dispatch_count"] == 0


@pytest.mark.parametrize(("prompt_version", "validator_version", "flow_unit"), [
    ("full-prose-auto-prompt-v56", "full-prose-auto-validator-v54", "cm³/min"),
    ("full-prose-auto-prompt-v57", "full-prose-auto-validator-v55", "L/min"),
    ("full-prose-auto-prompt-v58", "full-prose-auto-validator-v56", "fl oz/min"),
])
@pytest.mark.parametrize("ordinals", [False, True], ids=["media", "ordinals"])
def test_repair_replays_retained_compound_specification(prompt_version, validator_version, flow_unit, ordinals):
    opening = "Remove the pump."
    specification = f"Set the return line flow rate to a maximum of 14 {flow_unit}."
    image = _image()
    old = _document([{"kind": "ordered_list", "items": [opening, specification]}, image])
    if ordinals:
        repaired = _document([{"kind": "ordered_list", "start": 4, "items": [
            opening, {"text": specification, "number": 9},
        ]}, image])
    else:
        repaired = _document([{"kind": "ordered_list", "items": [
            opening, {"text": specification, "blocks": [image]},
        ]}])
    response = _response(old, ["Take the pump off.", specification])
    response["replacements"][1].update(action="retain", reason="Keep the exact flow limit.")
    published = render_auto(old, response, prompt_version=prompt_version)

    result = repair_published_media(
        old, published, repaired, response=response, prompt_version=prompt_version, ordinals=ordinals,
    )

    instructions = result.document["blocks"][1]
    assert instructions["items"][0] == "Take the pump off."
    retained = instructions["items"][1]
    assert retained["text"] == specification
    if ordinals:
        assert (instructions["start"], retained["number"]) == (4, 9)
    else:
        assert retained["blocks"][0]["storage_key"] == image["storage_key"]
    assert result.remapped_response["replacements"][1] == {
        **prose_slots(repaired)[1], "action": "retain", "reason": "Keep the exact flow limit.",
    }
    assert result.validation.passed
    assert result.validation.report["validator_version"] == validator_version
    assert result.provenance["original_prompt_version"] == prompt_version
    assert result.provenance["model_dispatch_count"] == 0


def _conditional_note_repair_fixture(prompt_version, *, ordinals=False):
    note = (
        "Note: During normal vehicle operation, OrchidVale™ Yellow ReadyMix Antifreeze/Coolant "
        "may change color from Yellow to Violet or light Blue. "
        "As long as the coolant is clear and clean, this observation alone does not require service."
    )
    opening = "Remove the pump."
    image = _image()
    old = _document([{"kind": "ordered_list", "items": [opening, note]}, image])
    if ordinals:
        repaired = _document([{"kind": "ordered_list", "start": 4, "items": [
            opening, {"text": note, "number": 9},
        ]}, image])
    else:
        repaired = _document([{"kind": "ordered_list", "items": [opening, {"text": note, "blocks": [image]}]}])
    response = _response(old, ["Take the pump off.", recast_conditional_color_note(note)])
    published = render_auto(
        old, response, prompt_version=prompt_version, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
        verified_color_notes=True,
    )
    return old, published, repaired, response


@pytest.mark.parametrize("prompt_version", (
    "full-prose-auto-prompt-v55", "full-prose-auto-prompt-v61", "full-prose-auto-prompt-v62",
))
@pytest.mark.parametrize("ordinals", [False, True], ids=["media", "ordinals"])
def test_repair_replays_verified_conditional_note_with_saved_prompt(prompt_version, ordinals):
    old, published, repaired, response = _conditional_note_repair_fixture(prompt_version, ordinals=ordinals)
    before = deepcopy((old, published, repaired, response))

    result = repair_published_media(
        old, published, repaired, response=response, profile=RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE,
        prompt_version=prompt_version, ordinals=ordinals,
    )

    steps = result.document["blocks"][1]
    assert steps["items"][0] == published["blocks"][1]["items"][0]
    note = steps["items"][1]
    assert note["text"] == published["blocks"][1]["items"][1]
    if ordinals:
        assert (steps["start"], note["number"]) == (4, 9)
    else:
        assert note["blocks"][0]["content_sha256"] == old["blocks"][-1]["content_sha256"]
    assert result.remapped_response["replacements"][1]["text"] == response["replacements"][1]["text"]
    assert result.validation.passed
    assert result.validation.report["profile_version"] == SOURCE_BOUND_CORRECTION_PROFILE
    assert result.validation.report["validator_version"] == "full-prose-color-note-replay-validator-v1"
    assert result.provenance["profile_version"] == RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE
    assert result.provenance["original_prompt_version"] == prompt_version
    assert result.provenance["model_dispatch_count"] == 0
    assert (old, published, repaired, response) == before


@pytest.mark.parametrize(("drift", "code"), (
    ("repaired_source", "PUBLISHED_MEDIA_REPAIR_SOURCE_TEXT_DRIFT"),
    ("published_and_reply", "PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH"),
))
def test_repair_rejects_conditional_note_warning_drift(drift, code):
    version = "full-prose-auto-prompt-v61"
    old, published, repaired, response = _conditional_note_repair_fixture(version)
    if drift == "repaired_source":
        note = repaired["blocks"][0]["items"][1]
        note["text"] = note["text"].replace("clear and clean", "clear or clean")
    else:
        changed = response["replacements"][1]["text"].replace("clear and clean", "clear or clean")
        response["replacements"][1]["text"] = published["blocks"][1]["items"][1] = changed

    with pytest.raises(ValueError, match=f"^{code}$"):
        repair_published_media(
            old, published, repaired, response=response, profile=RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE,
            prompt_version=version,
        )


def _bankone_media_fixture(prompt_version, *, placement):
    source, raw, html = linked_fixture()
    illustration = _document([_image()])["blocks"][0]
    illustration["source_order"] = len(source["blocks"]) + 1
    source["blocks"].append(illustration)
    proof = extract_bankone_structure(source, html, version=2)
    with pytest.raises(ValueError) as rejected:
        render_auto(source, raw, prompt_version=prompt_version)
    recovered = recover_structured_bankone_first_draft(
        source, {"guard_version": prompt_version, "response": raw, "error_code": str(rejected.value)},
        proof, method=BANKONE_LINKED_RECOVERY_METHOD,
    )
    assert recovered is not None
    repaired = deepcopy(source)
    media = repaired["blocks"].pop()
    if placement == "inline":
        media["source_order"] = 1
        item = repaired["blocks"][1]["items"]
        item[0] = {"text": item[0], "blocks": [media]}
    else:
        repaired["blocks"].insert(0, media)
    for index, block in enumerate(repaired["blocks"], start=1):
        block.update(source_order=index, block_id=f"repaired-{index}")
    return source, recovered.document, repaired, recovered.response, proof


@pytest.mark.parametrize("prompt_version", ("full-prose-auto-prompt-v55", "full-prose-auto-prompt-v62"))
@pytest.mark.parametrize("placement", ("inline", "block"))
def test_bankone_media_repair_rebinds_exact_structural_slots(prompt_version, placement):
    old, published, repaired, response, proof = _bankone_media_fixture(prompt_version, placement=placement)
    before = deepcopy((old, published, repaired, response, proof))
    result = repair_published_media(
        old, published, repaired, response=response, prompt_version=prompt_version, bankone_structure=proof,
    )

    linked_path = "/blocks/1/items/0/text" if placement == "inline" else "/blocks/2/items/0"
    assert result.remapped_response["replacements"][1]["path"] == linked_path
    assert result.remapped_response["replacements"][1]["text"] == response["replacements"][1]["text"]
    assert result.validation.passed
    assert result.provenance["original_bankone_structure_hash"] == digest_json(proof)
    assert result.provenance["original_prompt_version"] == prompt_version
    assert result.provenance["model_dispatch_count"] == 0
    path_pairs = zip(response["replacements"], prose_slots(repaired, include_cell_blocks=True), strict=True)
    remapped = {
        **proof,
        "source_hash": digest_json(repaired),
        "slots": {
            new["path"]: {**proof["slots"][old["path"]], "block_id": new["block_id"]}
            for old, new in path_pairs
            if old["path"] in proof["slots"]
        },
    }
    assert result.provenance["remapped_bankone_structure_hash"] == digest_json(remapped)
    assert result.projection["images"][0]["content_sha256"] == old["blocks"][-1]["content_sha256"]
    assert (old, published, repaired, response, proof) == before


def test_bankone_media_repair_rejects_a_retargeted_published_link():
    version = "full-prose-auto-prompt-v62"
    old, published, repaired, response, proof = _bankone_media_fixture(version, placement="block")
    wording = response["replacements"][1]["text"].replace("Fixture Filter Replacement", "Other Filter Replacement")
    response["replacements"][1]["text"] = published["blocks"][2]["items"][0] = wording
    assert render_auto(old, response, prompt_version=version) == published

    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH$"):
        repair_published_media(
            old, published, repaired, response=response, prompt_version=version, bankone_structure=proof,
        )


@pytest.mark.parametrize("prompt_version", [
    None, "full-prose-auto-prompt-v0", "full-prose-auto-prompt-v61", "full-prose-auto-prompt-v62",
    "full-prose-auto-prompt-v99",
])
def test_repair_rejects_unrecognized_original_prompt_version(prompt_version):
    old, published, repaired, response = _fixture()
    with pytest.raises(ValueError, match="^PUBLISHED_MEDIA_REPAIR_PROMPT_UNSUPPORTED$"):
        repair_published_media(old, published, repaired, response=response, prompt_version=prompt_version)


def test_available_figure_accepts_a_missing_historical_null_reason():
    old, _, repaired, response = _fixture()
    old["blocks"][-1].pop("unavailable_reason", None)
    repaired["blocks"][1]["unavailable_reason"] = None
    prompt = "full-prose-auto-prompt-v8"
    published = render_auto(old, response, prompt_version=prompt)
    result = repair_published_media(old, published, repaired, response=response, prompt_version=prompt)
    assert result.validation.passed
    assert result.document["blocks"][2]["unavailable_reason"] is None

    repaired["blocks"][1]["unavailable_reason"] = "a changed reason"
    with pytest.raises(ValueError, match="MEDIA_DRIFT"):
        repair_published_media(old, published, repaired, response=response, prompt_version=prompt)


def test_repair_replays_v59_equivalent_orientation_at_the_authored_figure_position():
    image = _image()
    original = "The painted mark on the inside guide face of the cover identifies the latch."
    rewrite = "Find the latch by the reference mark on the cover's interior guide face."
    before = _document([{"kind": "ordered_list", "items": [original]}, image])
    corrected = _document([{"kind": "ordered_list", "items": [{"text": original, "blocks": [image]}]}])
    response = _response(before, [rewrite])
    prompt = "full-prose-auto-prompt-v59"
    published = render_auto(before, response, prompt_version=prompt)

    result = repair_published_media(before, published, corrected, response=response, prompt_version=prompt)

    step = result.document["blocks"][1]["items"][0]
    assert step["text"] == rewrite
    assert step["blocks"][0]["storage_key"] == image["storage_key"]
    assert result.validation.passed
    assert result.validation.report["validator_version"] == "full-prose-auto-validator-v57"
    assert result.provenance["original_prompt_version"] == prompt
    assert result.provenance["model_dispatch_count"] == 0
