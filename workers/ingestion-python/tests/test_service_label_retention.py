"""Check that labeled service references retain their names in fresh drafts."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from test_procedure_rewrite_full import document


TOOL = "GX-8308 Fixture Alignment Gauge"
PARTS = ["Upper Fixture Guide Plate[2a]", "Lower Support"]
LABELS = {"/blocks/1/text", "/blocks/3/items/0", "/blocks/3/items/1"}
ACTION = "/blocks/6/text"


def service_source():
    source = document(
        "Special Tool", TOOL, "Fixture Covers and Components", "list", "figure", "table",
        "Remove the retaining clip.", "Do not energize the fixture.",
    )
    blocks = source["blocks"]
    for idx, fields in (
        (3, {"type": "unordered_list", "items": list(PARTS)}),
        (4, {"type": "image", "status": "unavailable", "unavailable_reason": "fixture"}),
        (5, {"type": "table", "rows": [["Mount surface", "Position"]]}),
    ):
        blocks[idx].pop("text")
        blocks[idx].update(fields)
    blocks[7]["type"] = "callout"
    return source


def previous_prompt(source, profile):
    if profile == auto.PROFILE:
        return auto._encode_automatic_prompt(source, context={}, retain_service_labels=False)
    return auto._build_source_bound_prompt(
        source, preserve_notes=True, procedure_fidelity=True, allow_drain_subject=True,
        allow_rotation_removal=True, allow_optional_observation=True, allow_spaced_rotation=True,
        include_technical_tokens=True, retain_standalone_notes=True, recast_short_actions=True,
        recast_filter_preparation=True,
    )


def service_reply(payload):
    words = {
        "/blocks/0/text": "Service equipment",
        "/blocks/2/text": "Names of the service parts",
        ACTION: "Take the retaining clip off.",
    }
    rows = []
    for slot in payload["slots"]:
        action = slot["required_action"]
        path = slot["path"]
        if path in LABELS:
            assert action == "retain"
        if path == ACTION:
            assert action == "rewrite"
        rows.append({
            "block_id": slot["block_id"], "path": path, "action": action,
            "text": slot["text"] if action == "retain" else (slot.get("required_text") or words[path]),
            "reason": "Keep the authored label" if action == "retain" else "",
        })
    return {"introduction": "This article describes service information.", "replacements": rows}


@pytest.mark.parametrize("profile", (auto.PROFILE, auto.SOURCE_BOUND_REWRITE_PROFILE))
def test_service_labels_bind_both_draft_and_publication(profile):
    source = service_source()
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    payload = json.loads(prompt)
    prior = previous_prompt(source, profile)
    assert payload["prompt_version"] == auto._SERVICE_LABEL_PROMPT_VERSION
    assert auto._authored_service_labels(source) == LABELS
    for raw in (prompt, prior):
        assert auto._auto_prompt_version(
            source, context={}, prompt_hash=sha256(raw.encode()).hexdigest(), profile_version=profile,
        ) == json.loads(raw)["prompt_version"]
    reply = service_reply(payload)
    version = payload["prompt_version"]
    candidate = auto.render_auto(source, reply, profile_version=profile, prompt_version=version)
    assert auto.validate_auto(
        source, candidate, response=reply, profile_version=profile, prompt_version=version,
    ).passed
    auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)
    assert candidate["blocks"][2]["text"] == TOOL
    assert candidate["blocks"][4]["items"] == PARTS
    assert candidate["blocks"][8]["text"] == source["blocks"][7]["text"]

    for path in LABELS:
        altered = deepcopy(reply)
        row = next(row for row in altered["replacements"] if row["path"] == path)
        row.update(action="rewrite", text=row["text"] + " Fixture", reason="")
        with pytest.raises(ValueError, match="^REWRITE_SERVICE_LABEL_MUTATION$"):
            auto.render_auto(source, altered, profile_version=profile, prompt_version=version)

    retained_action = deepcopy(reply)
    row = next(row for row in retained_action["replacements"] if row["path"] == ACTION)
    row.update(action="retain", text=source["blocks"][6]["text"], reason="Retained")
    with pytest.raises(ValueError, match="^REWRITE_UNCHANGED$"):
        auto.render_auto(source, retained_action, profile_version=profile, prompt_version=version)


def test_service_label_scope_requires_the_authored_context_and_nominal_entries():
    source = service_source()
    source["blocks"][1]["text"] = "GX-8308 Install the Fixture"
    source["blocks"][3]["items"][1] = "Remove Lower Support"
    assert auto._authored_service_labels(source) == set()
    assert auto.build_auto_prompt(source, context={}) == previous_prompt(source, auto.PROFILE)

    source = service_source()
    source["blocks"][0]["text"] = "Service Instructions"
    source["blocks"][4] = {
        "block_id": "missing-diagram", "source_order": 5, "type": "paragraph",
        "text": "The illustration is unavailable.", "evidence_ids": ["fixture-evidence"],
    }
    assert auto._authored_service_labels(source) == set()


def test_service_labels_compose_with_existing_single_use_directives():
    source = service_source()
    blocks = source["blocks"]
    blocks.extend([
        {"block_id": "single-use", "source_order": 9, "type": "paragraph",
         "text": "Single Use Fasteners and Components", "evidence_ids": ["fixture-evidence"]},
        {"block_id": "one-use-parts", "source_order": 10, "type": "unordered_list",
         "items": ["Fixture Mount Bolt[3x]"], "evidence_ids": ["fixture-evidence"]},
    ])
    fresh = json.loads(auto.build_auto_prompt(source, context={}))
    assert fresh["prompt_version"] == auto._SERVICE_LABEL_AND_SINGLE_USE_PROMPT_VERSION
    for slot in fresh["slots"]:
        if slot["path"] == "/blocks/8/text":
            assert slot["required_text"] == auto.SINGLE_USE_PARTS_TEXT
        if slot["path"] in LABELS | {"/blocks/9/items/0"}:
            assert slot["required_action"] == "retain"

    version = fresh["prompt_version"]
    reply = service_reply(fresh)
    candidate = auto.render_auto(source, reply, prompt_version=version)
    assert auto.validate_auto(source, candidate, response=reply, prompt_version=version).passed
    auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)
    assert candidate["blocks"][9]["text"] == auto.SINGLE_USE_PARTS_TEXT

    prior = previous_prompt(source, auto.PROFILE)
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(prior.encode()).hexdigest(),
    ) == auto.SINGLE_USE_PARTS_PROMPT_VERSION
    source_bound = json.loads(auto.build_auto_prompt(source, context={}, profile_version=auto.SOURCE_BOUND_REWRITE_PROFILE))
    assert source_bound["prompt_version"] == auto._SERVICE_LABEL_PROMPT_VERSION
    bound_prior = json.loads(previous_prompt(source, auto.SOURCE_BOUND_REWRITE_PROFILE))
    assert [slot for slot in source_bound["slots"] if slot["path"].startswith(("/blocks/8/", "/blocks/9/"))] == [
        slot for slot in bound_prior["slots"] if slot["path"].startswith(("/blocks/8/", "/blocks/9/"))
    ]
