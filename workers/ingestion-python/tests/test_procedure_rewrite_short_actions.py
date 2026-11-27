"""Preserve exact actions when rewording short compound steps."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from test_procedure_rewrite_full import document, response


RUN = "Start the engine and allow it to run until the fixture indicator goes off."
REMOVE = "Remove the bolts and the fluid pump screen and return tube."
RUN_REWRITE = "Start the engine. Keep it running until the fixture indicator turns off."
REMOVE_REWRITE = "Remove the bolts. Remove the fluid pump screen and return tube as well."


@pytest.mark.parametrize("wording", (
    "Run the engine until the fixture indicator goes off.",
    "Start the pump and allow it to run until the fixture indicator goes off.",
    "Start the engine and let it run until the fixture indicator comes on.",
    RUN[:-1] + ", unless the valve is closed.",
    REMOVE.replace(" and the ", " or the "),
    REMOVE[:-1] + " without moving the panel.",
))
def test_recast_leaves_unclassified_steps_to_existing_rules(wording):
    assert auto.recast_short_procedure(wording) is None


@pytest.mark.parametrize("profile", (auto.PROFILE, auto.SOURCE_BOUND_REWRITE_PROFILE))
def test_fresh_prompt_binds_both_actions_and_recognizes_the_previous_hash(profile):
    source = document(RUN, REMOVE)
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    payload = json.loads(prompt)
    version = payload["prompt_version"]
    assert version == auto._SHORT_ACTION_PROMPT_VERSION
    assert [slot["required_text"] for slot in payload["slots"]] == [RUN_REWRITE, REMOVE_REWRITE]
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest(), profile_version=profile,
    ) == version
    if profile == auto.PROFILE:
        previous = auto._encode_prompt_with_technical_tokens(
            auto._auto_prompt_payload_v66(source, context={}), retain_standalone_notes=True,
        )
    else:
        previous = auto._build_source_bound_prompt(
            source, preserve_notes=True, procedure_fidelity=True, allow_drain_subject=True,
            allow_rotation_removal=True, allow_optional_observation=True, allow_spaced_rotation=True,
            include_technical_tokens=True, retain_standalone_notes=True,
        )
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(previous.encode()).hexdigest(), profile_version=profile,
    ) == json.loads(previous)["prompt_version"]
    draft = response(RUN_REWRITE, REMOVE_REWRITE, introduction="This article describes service procedures.")
    rewritten = auto.render_auto(source, draft, prompt_version=version, profile_version=profile)
    assert auto.validate_auto(
        source, rewritten, response=draft, prompt_version=version, profile_version=profile,
    ).passed
    auto.require_current_publication_checks(source, rewritten, saved_prompt_version=version)

    for index, text in (
        (0, "Keep the engine running until the fixture indicator turns off."),
        (0, RUN_REWRITE.replace("turns off", "turns on")),
        (1, "Remove the fluid pump screen and return tube."),
        (1, REMOVE_REWRITE.replace("return tube", "feed tube")),
    ):
        checked = deepcopy(rewritten)
        checked["blocks"][index + 1]["text"] = text
        with pytest.raises(ValueError, match="^REWRITE_SHORT_PROCEDURE_MUTATION$"):
            auto.require_current_publication_checks(source, checked, saved_prompt_version=version)
