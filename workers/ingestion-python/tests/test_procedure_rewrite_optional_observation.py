"""Validate exact observation recasts without changing their protected restriction."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite as rewrite
from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import _get, _set, render_full
from test_procedure_rewrite_full import Draft, document, response


FIRST = "The fixture flag drops in standby mode."
RESTRICTION = "Operating the fixture during inspection is not permitted."
PREFIX = f"{FIRST} {RESTRICTION} "
OBSERVATION = "This can be seen by the test gauge on the monitor panel."
RECAST = "You can see this behavior using the test gauge on the monitor panel."
SOURCE = PREFIX + OBSERVATION
EXPECTED = PREFIX + RECAST
ROTATION = "Rotate the fixture sleeve clockwise and remove the guard plate."
ROTATION_RECAST = "Turn the fixture sleeve in a clockwise direction and take the guard plate off."
VERSION = "full-prose-auto-prompt-v65"
ERROR = "REWRITE_OPTIONAL_OBSERVATION_MUTATION"


def test_recast_keeps_both_leading_sentences_and_instrument_location_exact():
    assert auto.recast_optional_observation(SOURCE) == EXPECTED


@pytest.mark.parametrize("source", (
    FIRST + " " + OBSERVATION,
    "Inspect the flag. " + SOURCE,
    SOURCE.replace(RESTRICTION, "Operating the fixture during inspection is permitted."),
    SOURCE.replace("This can be seen", "This must be seen"),
    SOURCE.replace("test gauge", "gauge"),
    SOURCE.replace("test gauge", "main test gauge"),
    SOURCE.replace("test gauge", "-- -"),
    SOURCE.replace("monitor panel", "panel"),
    SOURCE.replace("monitor panel", "upper monitor panel"),
    SOURCE.replace(". Operating", "\nOperating").replace(". This", "\nThis"),
    SOURCE + " Record the reading.",
))
def test_recast_refuses_other_restrictions_or_observation_shapes(source):
    assert auto.recast_optional_observation(source) is None


@pytest.mark.parametrize("profile", (auto.PROFILE, auto.SOURCE_BOUND_REWRITE_PROFILE))
@pytest.mark.parametrize("nested", (False, True), ids=("paragraph", "table-cell"))
def test_current_prompts_require_exact_recast_and_keep_media_order(profile, nested):
    source = document(SOURCE)
    if nested:
        source["blocks"] = [{
            "block_id": "observations", "source_order": 1, "type": "table",
            "rows": [[{"text": "Fixture status", "blocks": source["blocks"]}, "Fixture control"]],
            "evidence_ids": ["test-table"],
        }]
    source["blocks"].append({
        "block_id": "illustration", "source_order": 2, "type": "image", "status": "available",
        "storage_key": "fixture/observation.png", "content_sha256": "a" * 64,
        "caption": "Monitor panel", "evidence_ids": ["test-illustration"],
    })
    unchanged = deepcopy(source)
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    payload = json.loads(prompt)
    assert payload["prompt_version"] == auto._OPTIONAL_OBSERVATION_PROMPT_VERSION == VERSION
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest(), profile_version=profile,
    ) == VERSION
    [slot] = [slot for slot in payload["slots"] if slot["text"] == SOURCE]
    assert slot["required_action"] == "rewrite"
    assert slot["required_text"] == EXPECTED
    draft = response(EXPECTED, introduction="This article describes fixture flag behavior.")
    draft["replacements"][0].update(block_id=slot["block_id"], path=slot["path"])

    result = rewrite.rewrite_ordered_document(source, client=Draft(draft), context={}, profile_version=profile)
    assert result.error_code is None
    assert result.model_metadata["prompt_version"] == VERSION
    assert source == unchanged
    candidate = {"blocks": result.document["blocks"][1:]}
    assert _get(candidate, slot["path"]) == EXPECTED
    expected = deepcopy(source)
    _set(expected, slot["path"], EXPECTED)
    for block in expected["blocks"]:
        block["source_order"] += 1
    assert candidate["blocks"] == expected["blocks"]
    assert auto.validate_auto(source, result.document, response=draft, prompt_version=VERSION, profile_version=profile).passed
    auto.require_current_publication_checks(source, result.document, saved_prompt_version=VERSION)


def test_v65_keeps_the_v64_rotation_binding_in_the_same_document():
    source = document(SOURCE, ROTATION)
    draft = response(EXPECTED, ROTATION_RECAST, introduction="This article describes the fixture.")
    result = rewrite.rewrite_ordered_document(source, client=Draft(draft), context={}, profile_version=auto.PROFILE)
    assert result.error_code is None
    assert result.model_metadata["prompt_version"] == VERSION
    auto.require_current_publication_checks(source, result.document, saved_prompt_version=VERSION)

    result.document["blocks"][2]["text"] = ROTATION_RECAST.replace("clockwise", "counterclockwise")
    with pytest.raises(ValueError, match="^REWRITE_"):
        auto.require_current_publication_checks(source, result.document, saved_prompt_version=VERSION)


@pytest.mark.parametrize("wording", (
    EXPECTED.replace("drops", "rises"),
    EXPECTED.replace(". Operating", ".  Operating"),
    EXPECTED.replace("not permitted", "permitted"),
    EXPECTED.replace("You can see", "You must see"),
    EXPECTED.replace("test gauge", "check gauge"),
    EXPECTED.replace("monitor panel", "status panel"),
    EXPECTED.replace(" on the monitor panel", ""),
    EXPECTED + " The gauge also monitors pressure.",
    SOURCE,
))
def test_render_validation_and_publication_reject_changed_or_missing_recast(wording):
    source = document(SOURCE)
    draft = response(wording, introduction="This article describes fixture flag behavior.")
    with pytest.raises(ValueError, match=r"^REWRITE_"):
        auto.render_auto(source, draft, prompt_version=VERSION)

    candidate = auto.render_auto(
        source, response(EXPECTED, introduction=draft["introduction"]), prompt_version=VERSION,
    )
    candidate["blocks"][1]["text"] = wording
    checked = auto.validate_auto(source, candidate, prompt_version=VERSION)
    assert not checked.passed
    with pytest.raises(ValueError, match=f"^{ERROR}$"):
        auto.require_current_publication_checks(source, candidate, saved_prompt_version=VERSION)


@pytest.mark.parametrize(("builder", "version", "other_source", "other_recast", "checksums"), (
    ("_build_auto_prompt_v55", "full-prose-auto-prompt-v55",
     "Remove the fixture cover.", "Take the fixture cover off.", (
         "a7644e1ce3f72163cb3f88ad7161313a889c9da86f2fa51fac0ce52631d52952",
         "b87ed52b07e86aa27101b1a81dab51f790353524f5225a178ae22e5a78721e57",
         "647a094cf9866daca7eff9670ebaef300e3886cbbba55062321866d63f8e11b2",
     )),
    ("_build_auto_prompt_v64", "full-prose-auto-prompt-v64", ROTATION, ROTATION_RECAST, (
         "007ad0991a2df5c3a3d279322499d6ac158ad02322f935b777287bbe9d66d8c2",
         "d72c95c2b42270b8c47e39f2d4e5d1b6f60c9276c969fce6d7f5377f999e86d2",
         "a877ee7d86feee9264a3c422f9f845be53c94c2594276d1cb85a73fa3ffa56d9",
     )),
))
def test_historical_prompt_retains_restriction_and_rejects_the_new_wording(
    builder, version, other_source, other_recast, checksums,
):
    source = document(SOURCE, other_source)
    prompt = getattr(auto, builder)(source, context={})
    payload = json.loads(prompt)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert payload["prompt_version"] == version
    assert auto._auto_prompt_version(source, context={}, prompt_hash=prompt_hash) == version
    observation, _ = payload["slots"]
    assert observation["text"] == SOURCE
    assert observation["required_action"] == "retain"
    assert "required_text" not in observation
    archived = response(SOURCE, other_recast, introduction="This article describes the fixture.")
    archived["replacements"][0].update(action="retain", reason="Keep the protected restriction.")
    saved = auto.render_auto(source, archived, prompt_version=version)
    validation = auto.validate_auto(source, saved, response=archived, prompt_version=version)
    assert validation.passed
    # Record the archived prompt, document, and report before introducing v65.
    assert (prompt_hash, digest_json(saved), digest_json(validation.report)) == checksums
    assert saved["blocks"][1]["text"] == SOURCE

    changed = response(EXPECTED, other_recast, introduction=archived["introduction"])
    candidate = render_full(source, changed, profile_version=auto.PROFILE, include_cell_blocks=True)
    checked = auto.validate_auto(source, candidate, response=changed, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SAFETY_MUTATION",)
    with pytest.raises(ValueError, match="^REWRITE_SAFETY_MUTATION$"):
        auto.render_auto(source, changed, prompt_version=version)
