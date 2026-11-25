"""Test procedure-fact binding through normal automatic rewrite entry points."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite as rewrite
from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from autodata_ingestion.procedure_rewrite_recovery import FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD, recover_first_draft

from test_procedure_rewrite_auto import _scoped_prose_response, _scoped_prose_source
from test_procedure_rewrite_full import Draft, document, response


_DRAIN = "Drain the fixture reservoir."
_LET_DRAIN = "Let the fixture reservoir drain."
_CONTACT = "Install the fixture cap until it contacts the positive stop."
_REPEAT = "Repeat Steps 2 through 4 a total of 3 times to remove residue from the chamber."
_START = (
    "Start the drive motor and let it idle until the chamber temperature reaches operating temperature "
    "and the bypass valve is fully open. A fully open bypass valve is verified by the status lamp "
    "cycling on at least once."
)
_IDLE_CONDITIONS = (
    "the chamber temperature has reached operating temperature, and the bypass valve is fully open."
)
_IDLE = (
    "Start the drive motor. Keep it idling until both conditions are met: " + _IDLE_CONDITIONS
    + " The status lamp cycling on at least once verifies a fully open bypass valve."
)
_ACTION = "REWRITE_ACTION_MUTATION"
_QUALIFIER = "REWRITE_QUALIFIER_MUTATION"


def _draft(layout, original, wording, *, profile):
    if layout == "table":
        source = _scoped_prose_source(original, in_cell=True)
    elif layout == "note":
        source = document("Note: " + original)
    else:
        source = document(original)
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    raw = _scoped_prose_response(prompt, wording) if layout == "table" else response(wording)
    return source, prompt, raw


@pytest.mark.parametrize("layout", ("paragraph", "table", "note"))
@pytest.mark.parametrize("original,wording,error", [
    (_DRAIN, "Fill the fixture reservoir.", _ACTION),
    (_DRAIN, "The fixture reservoir must be filled.", _ACTION),
    (_DRAIN, "Empty the catch reservoir.", _ACTION),
    (_DRAIN, "Let the catch reservoir drain.", _ACTION),
    (_DRAIN, "Let the fixture reservoir fill.", _ACTION),
    (_DRAIN, "Let the fixture reservoir drain completely.", _ACTION),
    (_LET_DRAIN, "Fill the fixture reservoir.", _ACTION),
    ("Fill the fixture reservoir.", "Drain the fixture reservoir.", _ACTION),
    (_CONTACT, "Fit the fixture cap to the positive stop.", _QUALIFIER),
    (_CONTACT, "Install the fixture cap. Continue until it approaches the positive stop.", _QUALIFIER),
    (_CONTACT, "Install the fixture cap. Continue until it contacts the witness mark.", _ACTION),
    (_CONTACT, "Install the fixture cap. Continue until it contacts the secondary stop.", _QUALIFIER),
    (_REPEAT, "Skip Steps 2 through 4 a total of 3 times to remove residue from the chamber.", _ACTION),
    (_REPEAT, "Remove residue from the chamber by skipping Steps 2 through 4 a total of 3 times.", _ACTION),
    (_REPEAT, "Repeat Steps 2 through 4 a number of times. Remove residue from the chamber 3 times.", _ACTION),
    (_START, _IDLE.replace("both conditions are met:", "either condition is met:")
                  .replace(", and the bypass", ", or the bypass"), _QUALIFIER),
    (_START, _IDLE.replace(f"both conditions are met: {_IDLE_CONDITIONS}",
                          "the chamber temperature has reached operating temperature."), _QUALIFIER),
    (_START, _IDLE.replace("operating temperature", "standby temperature"), _QUALIFIER),
    (_START, _IDLE.replace("verifies a fully open bypass valve", "verifies a fully open drain valve"), _QUALIFIER),
    (_START, _IDLE.replace(" at least once", ""), _QUALIFIER),
    (_START, _IDLE.replace("at least once", "exactly once"), _QUALIFIER),
    (_START, _IDLE.replace("at least once", "at least twice"), _QUALIFIER),
])
def test_current_guard_rejects_shifted_procedure_facts(layout, original, wording, error):
    profile = auto.SOURCE_BOUND_REWRITE_PROFILE
    source, prompt, raw = _draft(layout, original, wording, profile=profile)
    version = json.loads(prompt)["prompt_version"]
    assert version == ("full-prose-auto-prompt-v63" if original in (_DRAIN, _LET_DRAIN) else "full-prose-auto-prompt-v62")
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest(), profile_version=profile,
    ) == version

    with pytest.raises(ValueError, match=f"^{error}$"):
        auto.render_auto(source, raw, prompt_version=version, profile_version=profile)

    result = rewrite.rewrite_ordered_document(source, client=Draft(raw), context={}, profile_version=profile)
    assert result.error_code == error
    assert result.document == source
    assert result.model_metadata["prompt_version"] == version
    failed_path = raw["replacements"][-1]["path"]
    assert result.model_metadata["passage_errors"] == [{"path": failed_path, "code": error}]

    # Materialize the structurally valid draft before applying automatic prose checks.
    candidate = render_full(source, auto._restore_authored_note_labels(source, raw), profile_version=profile,
                            include_cell_blocks=True)
    checked = auto.validate_auto(source, candidate, response=raw, prompt_version=version, profile_version=profile)
    assert checked.error_codes == (error,)
    with pytest.raises(ValueError, match=f"^{error}$"):
        auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)


@pytest.mark.parametrize("layout", ("paragraph", "table", "note"))
@pytest.mark.parametrize("profile", (auto.PROFILE, auto.SOURCE_BOUND_REWRITE_PROFILE))
@pytest.mark.parametrize("original,wording", [
    (_DRAIN, "Empty the fixture reservoir."),
    (_DRAIN, "The fixture reservoir must be drained."),
    (_DRAIN, "Allow the fluid to drain from the fixture reservoir."),
    (_DRAIN, _LET_DRAIN),
    (_LET_DRAIN, _DRAIN),
    (_DRAIN.removesuffix("."), "Drain the fluid from the fixture reservoir."),
    ("Fill the fixture reservoir.", "The fixture reservoir must be filled."),
    (_CONTACT, "Fit the fixture cap. Continue until it touches the positive stop."),
    (_REPEAT, "Remove residue from the chamber by repeating Steps 2 through 4 a total of 3 times."),
    (_START, _IDLE),
    (_START, _IDLE.replace(_IDLE_CONDITIONS, (
        "the bypass valve is fully open, and the chamber temperature has reached operating temperature."
    ))),
])
def test_current_guard_preserves_distinct_equivalent_prose(layout, profile, original, wording):
    source, prompt, raw = _draft(layout, original, wording, profile=profile)
    version = json.loads(prompt)["prompt_version"]
    drain = original in (_DRAIN, _DRAIN.removesuffix("."), _LET_DRAIN)
    assert version == ("full-prose-auto-prompt-v63" if drain else "full-prose-auto-prompt-v62")
    result = rewrite.rewrite_ordered_document(source, client=Draft(raw), context={}, profile_version=profile)
    assert result.error_code is None
    assert result.model_metadata["prompt_version"] == version
    checked = auto.validate_auto(source, result.document, response=raw, prompt_version=version, profile_version=profile)
    assert checked.passed
    assert checked.report["validator_version"] == (
        "full-prose-auto-validator-v61" if drain else "full-prose-auto-validator-v60"
    )
    auto.require_current_publication_checks(source, result.document, saved_prompt_version=version)
    if layout == "note":
        assert result.document["blocks"][-1]["text"] == "Note: " + wording


@pytest.mark.parametrize("introduction", (
    _LET_DRAIN, "Let the fixture reservoir fill.", "Let the catch reservoir drain.",
    "This article covers reservoir service. Then drain the fixture reservoir.",
    "This article covers reservoir service: let the other reservoir drain.",
    "The fixture reservoir must be drained.",
    "The fixture reservoir must be filled slowly.",
    "The fixture reservoir must be filled, then proceed with service.",
    "The fixture reservoir must be drained before inspection.",
    "The fixture reservoir needs to be drained into a separate container.",
))
def test_drain_subject_prompt_rejects_fluid_instructions_in_introduction(introduction):
    source = document(_DRAIN)
    raw = response(_LET_DRAIN, introduction=introduction)
    version = json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"]
    assert version == "full-prose-auto-prompt-v63"
    with pytest.raises(ValueError, match="^REWRITE_INTRODUCTION_INSTRUCTION$"):
        auto.render_auto(source, raw, prompt_version=version)
    candidate = render_full(source, raw)
    with pytest.raises(ValueError, match="^REWRITE_INTRODUCTION_INSTRUCTION$"):
        auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)


def test_drain_subject_prompt_keeps_existing_contact_guard_in_the_same_article():
    source = document(_DRAIN, _CONTACT, "Note: Remove the cover.")
    version = json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"]
    assert version == "full-prose-auto-prompt-v63"
    raw = response(_LET_DRAIN, "Fit the fixture cap. Continue until it touches the positive stop.",
                   "Take the cover off.")
    candidate = auto.render_auto(source, raw, prompt_version=version)
    assert candidate["blocks"][-1]["text"] == "Note: Take the cover off."
    assert auto.validate_auto(source, candidate, response=raw, prompt_version=version).passed
    raw["replacements"][1]["text"] = "Fit the fixture cap to the positive stop."
    with pytest.raises(ValueError, match="^REWRITE_QUALIFIER_MUTATION$"):
        auto.render_auto(source, raw, prompt_version=version)


@pytest.mark.parametrize("introduction", (
    "This article describes service on reservoirs that need to be drained.",
    "The reservoirs that need to be drained are covered in this procedure.",
))
def test_drain_subject_prompt_allows_a_descriptive_introduction(introduction):
    source = document(_DRAIN)
    candidate = auto.render_auto(source, response(_LET_DRAIN, introduction=introduction),
                                 prompt_version="full-prose-auto-prompt-v63")
    assert candidate["blocks"][0]["text"] == introduction


@pytest.mark.parametrize("profile,version,prompt_hash,document_hash,report_hash", [
    (auto.PROFILE, "v55",
     "7b8ef709d78828bdb4587d960998a0d93ed826e779f0f7854a41be483d477183",
     "d2e6d984a392a0c2e32abd5166f392b779b5adaa4d8983b60e214c55241e356b",
     "2f23778fafa41a858c4397b8c6dc8b2d8dae9671cbc5f940d24d057d95852fe2"),
    (auto.PROFILE, "v61",
     "8473257303870f39524619fcbadafa856a4ca221e2bdb460f6a708cf69d97fce",
     "4597716d6d796331143a092b65b7aa4b3c22f8d7abaa75172efa85b124d8455e",
     "19bab078040afad4788fc856358d8e25164352a1f630f3c048ffbd1272dc1c3c"),
    (auto.PROFILE, "v62",
     "4351d062beabd0045f6fd29995cd09082498fe0f8a20cb6464c43f133ac3ab68",
     "a6a21507f983b7ad6d829b8b14047043be9a852cc555d20413c5efb2ea54be1d",
     "99b6fb6b23756306cd8f35821baf6195a1b2f79ab0257f4bfae39a9701f7d60e"),
    (auto.SOURCE_BOUND_REWRITE_PROFILE, "v55",
     "627c8214aeaf21d8572194d9effd488a773f9f25ef993eb96f20587e6f085052",
     "280e74816eeffa042f817bf847f0f74e467f335d26ae4f1bc8b067f00e003838",
     "b8650eab8700b374b30ee768eab2c4fc3de2ed1f8649a55b68a97df20b318b19"),
    (auto.SOURCE_BOUND_REWRITE_PROFILE, "v61",
     "a708600e80a7996f3fb9ab54c8af058a508dd0c1acaf6bf6aa7eaca05dd4b0eb",
     "3fc81dc7c38a63ea77a1066a366321fb7b6da25f77011b53408b245cfe1ff854",
     "bbb26535f4a0a9cdd46903e331554f4bec9ccf7af022bdbbeddce868d2fe4376"),
    (auto.SOURCE_BOUND_REWRITE_PROFILE, "v62",
     "32d636a88a0b14730f09f8431bf3b9f7d655c1158b2fca74a0379479a217e5ae",
     "78775d05a214c03ae2910680a3238580452644441ba3b4a504a9e8952a4b422b",
     "fea89db2ed5aea0b4f2ce31c36b81d13c8e7a5eee82dca9e07b63b54f0f11ef9"),
])
def test_archived_prompt_and_validation_bytes_replay(profile, version, prompt_hash, document_hash, report_hash):
    with_note = version in ("v61", "v62")
    source = document(_DRAIN, "Note: Remove the cover.") if with_note else document(_DRAIN)
    wording = "Empty the fixture reservoir." if version == "v62" else "Fill the fixture reservoir."
    raw = response(wording, "Take the cover off.") if with_note else response(wording)
    saved_version = auto._auto_prompt_version(source, context={}, prompt_hash=prompt_hash, profile_version=profile)
    assert saved_version == f"full-prose-auto-prompt-{version}"
    version = saved_version
    candidate = auto.render_auto(source, raw, prompt_version=version, profile_version=profile)
    checked = auto.validate_auto(source, candidate, response=raw, prompt_version=version, profile_version=profile)
    assert checked.passed
    assert digest_json(candidate) == document_hash
    assert digest_json(checked.report) == report_hash
    auto.require_current_publication_checks(source, candidate, saved_prompt_version=version)


def test_drain_as_a_component_name_keeps_the_existing_prompt():
    source = document("Remove the drain plug.")
    result = rewrite.rewrite_ordered_document(
        source, client=Draft(response("Take the drain plug off.")), context={}, profile_version=auto.PROFILE,
    )
    assert result.error_code is None
    assert auto._auto_prompt_version(source, context={}, prompt_hash=result.prompt_hash) == "full-prose-auto-prompt-v55"


def test_cooling_recovery_repairs_a_newly_detected_contact_mutation():
    source = document(_CONTACT)
    raw = response("Install the fixture cap. Continue until it approaches the positive stop.")
    version = json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"]
    recovered = recover_first_draft(source, raw, prompt_version=version)
    assert recovered.error_code is None
    assert recovered.evidence["method"] == FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD
    assert recovered.evidence["original_error_code"] == _QUALIFIER
    assert recovered.document["blocks"][1]["text"] == "Install the fixture cap. Continue until it contacts the positive stop."
