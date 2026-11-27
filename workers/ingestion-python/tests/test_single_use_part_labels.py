"""Preserve the identity, quantity and scope of authored single-use part labels."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from test_procedure_rewrite_full import document


HEADING = "Single Use Fasteners and Components"
LABELS = ["Fixture Mount Bolt[3x]", "Return Line Filter"]


def source_with_parts(items=LABELS, heading=HEADING):
    source = document(heading, "unused")
    listing = source["blocks"][1]
    listing.pop("text")
    listing.update(type="unordered_list", items=list(items))
    return source


def test_prompt_and_guards_bind_single_use_parts_and_keep_the_previous_prompt_hash():
    source = source_with_parts()
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    version = prompt["prompt_version"]
    assert version == auto.SINGLE_USE_PARTS_PROMPT_VERSION
    assert [(slot["required_action"], slot.get("required_text")) for slot in prompt["slots"]] == [
        ("rewrite", auto.SINGLE_USE_PARTS_TEXT), ("retain", None), ("retain", None),
    ]
    previous = auto._encode_prompt_with_technical_tokens(
        auto._auto_prompt_payload_v67(source, context={}), retain_standalone_notes=True,
    )
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(previous.encode()).hexdigest(),
    ) == json.loads(previous)["prompt_version"]
    rows = []
    for slot in prompt["slots"]:
        action = slot["required_action"]
        rows.append({"block_id": slot["block_id"], "path": slot["path"], "action": action,
                     "text": slot.get("required_text", slot["text"]),
                     "reason": "Exact component label." if action == "retain" else ""})
    draft = {"introduction": "This article describes service information.", "replacements": rows}
    candidate = auto.render_auto(source, draft, prompt_version=version)
    assert auto.validate_auto(source, candidate, response=draft, prompt_version=version).passed
    auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)
    assert candidate["blocks"][2]["items"] == LABELS

    for path, text in (
        ("/blocks/1/text", "Reuse the listed items."),
        ("/blocks/2/items/0", "Fixture Mount Bolt[2x]"),
        ("/blocks/2/items/1", "Supply Line Filter"),
    ):
        changed = deepcopy(candidate)
        auto.full._set(changed, path, text)
        with pytest.raises(ValueError, match="^REWRITE_SINGLE_USE_PARTS_MUTATION$"):
            auto.require_current_publication_checks(source, changed, saved_prompt_version=version)


@pytest.mark.parametrize(("heading", "items"), (
    ("Service Procedure", LABELS),
    (HEADING, [LABELS[0], "Remove Return Line Filter"]),
    (HEADING, [LABELS[0], "Use Alternate Filter"]),
    (HEADING, [LABELS[0], "Torque Bolt"]),
    (HEADING, [LABELS[0], "Return Line Filter if equipped"]),
))
def test_only_a_standalone_list_of_component_labels_receives_retention(heading, items):
    source = source_with_parts(items, heading=heading)
    assert auto.single_use_part_slots(source) == (set(), set())
    assert json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"] != auto.SINGLE_USE_PARTS_PROMPT_VERSION
