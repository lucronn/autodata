"""Automatic mechanical publication checks; synthetic, not semantic proof."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite as rewrite
from autodata_ingestion.article_lifecycle_types import SOURCE_BOUND_REWRITE_PROFILE, digest_json
from test_procedure_rewrite_full import document, response, Draft

PROFILE = "full-prose-auto-v1"


def run(source, payload):
    return rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=PROFILE)


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
def test_oil_filter_preparation_recasts_two_sentences_and_preserves_the_retained_procedure(profile):
    from autodata_ingestion import procedure_rewrite_auto as auto

    condition = "If the adapter is loose, tighten it."
    amount = "Add up to 0.5 l of oil after installation."
    source = document("Oil filter service",
        "Remove the oil filter. Clean gasket seal area on oil filter mounting surface. "
        f"{condition} Lightly oil the gasket with clean engine oil and install the filter. {amount}")
    source["blocks"][0].update(type="heading", level=2)
    if profile == PROFILE:
        historical = auto._encode_prompt_with_technical_tokens(
            auto._auto_prompt_payload_v67(source, context={}), retain_standalone_notes=True)
    else:
        historical = auto._build_source_bound_prompt(
            source, preserve_notes=True, procedure_fidelity=True, allow_drain_subject=True,
            allow_rotation_removal=True, allow_optional_observation=True, allow_spaced_rotation=True,
            include_technical_tokens=True, retain_standalone_notes=True, recast_short_actions=True,
        )
    previous = json.loads(historical)
    assert previous["slots"][0]["required_action"] == "retain"
    assert auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(historical.encode()).hexdigest(), profile_version=profile,
    ) == previous["prompt_version"]
    current = json.loads(auto.build_auto_prompt(source, context={}, profile_version=profile))
    slot, = current["slots"]
    version = current["prompt_version"]
    assert version == auto._FILTER_PREPARATION_PROMPT_VERSION
    assert slot["required_action"] == "rewrite"
    expected = ("Remove the oil filter. Clean the part of the oil filter mounting surface that seals against the gasket. "
                f"{condition} Coat the gasket lightly with clean engine oil. Then install the filter. {amount}")
    assert slot["required_text"] == expected
    payload = response("unused", expected, introduction="This article covers oil filter service.")
    payload["replacements"].pop(0)
    result = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=profile)
    assert result.error_code is None
    assert result.document["blocks"][2]["text"] == expected
    assert auto.require_current_publication_checks(source, result.document, saved_prompt_version=version) is None

    altered = deepcopy(result.document)
    altered["blocks"][2]["text"] = expected.replace(amount, "Add up to 0.8 l of oil after installation.")
    with pytest.raises(ValueError, match="REWRITE_FILTER_PREPARATION_MUTATION"):
        auto.require_current_publication_checks(source, altered, saved_prompt_version=version)
    warning = deepcopy(source)
    warning["blocks"][0]["text"] = "Caution"
    warning_prompt = json.loads(auto.build_auto_prompt(warning, context={}, profile_version=profile))
    assert warning_prompt["slots"][0]["required_action"] == "retain"


def test_archived_oil_filter_repair_preserves_the_original_introduction_identity():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.retained_note_label_repair import _FILTER_PREPARATION

    source = document("Oil filter service",
        "Remove the oil filter. Clean gasket seal area on oil filter mounting surface. "
        "Lightly oil the gasket with clean engine oil and install the filter. Refit the cover.")
    source["blocks"][0].update(type="heading", level=2)
    archived = response("unused", source["blocks"][1]["text"], introduction="This article covers oil filter service.")
    archived["replacements"].pop(0)
    archived["replacements"][0].update(action="retain", reason="Keep the service sequence intact.")
    prior_version = auto._auto_prompt_payload_v67(source, context={})["prompt_version"]
    prior = auto.render_auto(source, archived, prompt_version=prior_version, profile_version=PROFILE)
    saved_reply = deepcopy(archived)
    successor, validation, revised, paths = _FILTER_PREPARATION.edit_reply(
        source, source, prior, archived, prompt_version=_FILTER_PREPARATION.successor_guard, profile_version=PROFILE,
    )
    assert validation.passed and paths == ["/blocks/1/text"] and archived == saved_reply
    assert successor["blocks"][:2] == prior["blocks"][:2]
    assert revised["replacements"][0]["action"] == "rewrite"
    assert successor["blocks"][2]["text"] == auto.recast_oil_filter_preparation(source["blocks"][1]["text"])

    mismatched = deepcopy(prior)
    mismatched["blocks"][2]["text"] = "Refit only the cover."
    with pytest.raises(ValueError, match="RETAINED_FILTER_PREPARATION_REPAIR_INVALID"):
        _FILTER_PREPARATION.edit_reply(
            source, source, mismatched, archived, prompt_version=_FILTER_PREPARATION.successor_guard,
            profile_version=PROFILE,
        )


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
@pytest.mark.parametrize("marker", ["Note:", "NOTE :"])
def test_standalone_authored_note_is_retained_without_exempting_prose(profile, marker):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(marker, "Inspect the cover for damage.")
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    if profile == PROFILE:
        previous = auto._build_auto_prompt_with_technical_tokens(source, context={})
    else:
        previous = auto._build_source_bound_prompt(
            source, preserve_notes=True, procedure_fidelity=True, allow_drain_subject=True,
            allow_rotation_removal=True, allow_optional_observation=True, allow_spaced_rotation=True,
            include_technical_tokens=True,
        )
    assert [entry["required_action"] for entry in json.loads(prompt)["slots"]] == ["retain", "rewrite"]
    assert prompt != previous
    for archived in (prompt, previous):
        assert auto._auto_prompt_version(
            source, context={}, profile_version=profile, prompt_hash=sha256(archived.encode()).hexdigest(),
        ) == auto._NOTE_LABEL_PROMPT_VERSION

    payload = response(marker, "Check the cover for damage.",
                       introduction="This article describes service checks for the cover.")
    payload["replacements"][0].update(action="retain", reason="Preserve the exact label.")
    result = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=profile)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == marker
    assert result.document["blocks"][2]["text"] == "Check the cover for damage."

    payload["replacements"][0].update(action="rewrite", text=f"{marker} Remove the cover.", reason="")
    result = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=profile)
    assert result.error_code == "REWRITE_NOTE_LABEL_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
def test_automatic_prompt_lists_each_required_technical_token_and_replays_previous_attempts(profile):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Remove the 2 clips from the lower cover and set the 2 clips aside.",
                      "A completely ordinary paragraph about an engine cover.")
    historical = (
        auto._build_auto_prompt_v65(source, context={}) if profile == PROFILE
        else auto._build_source_bound_prompt(
            source, preserve_notes=True, procedure_fidelity=True, allow_drain_subject=True,
            allow_rotation_removal=True, allow_optional_observation=True,
        )
    )
    current = auto.build_auto_prompt(source, context={}, profile_version=profile)
    payload = json.loads(current)
    assert payload["technical_tokens_by_path"] == {"/blocks/0/text": ["2 clips", "2 clips"]}
    assert "output key action" in payload["rules"][0]
    assert "technical_tokens_by_path" not in json.loads(historical)
    assert current != historical
    for raw in [current, historical]:
        assert auto._auto_prompt_version(
            source, context={}, prompt_hash=sha256(raw.encode()).hexdigest(), profile_version=profile,
        ) == payload["prompt_version"]

    omitted = response("Take the 2 clips off the lower cover and put them aside.",
                       "The engine cover is the subject of this paragraph.")
    result = rewrite.rewrite_ordered_document(source, client=Draft(omitted), context={}, profile_version=profile)
    assert result.error_code == "REWRITE_TECHNICAL_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
def test_automatic_rewrite_reapplies_authored_note_labels_without_replacing_prose(profile):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Note: Remove the cover.", "unused")
    source["blocks"][1].pop("text")
    source["blocks"][1].update(type="ordered_list", items=["NOTE :  Inspect the seal."])
    payload = response("Take the cover off.", "note: Check the seal.")
    payload["replacements"][1]["path"] = "/blocks/1/items/0"
    client = Draft(payload)
    result = rewrite.rewrite_ordered_document(source, client=client, context={}, profile_version=profile)
    assert client.calls == 1
    assert result.error_code is None
    assert result.raw_response == payload
    assert result.document["blocks"][1]["text"] == "Note: Take the cover off."
    assert result.document["blocks"][2]["items"] == ["NOTE :  Check the seal."]

    version = auto._auto_prompt_version(source, context={}, prompt_hash=result.prompt_hash, profile_version=profile)
    assert version == "full-prose-auto-prompt-v61"
    assert auto.validate_auto(
        source, result.document, response=payload, prompt_version=version, profile_version=profile,
    ).passed
    historical_prompt = (
        auto._build_auto_prompt_v60(source, context={}) if profile == PROFILE
        else auto._build_source_bound_prompt(source, preserve_notes=False)
    )
    archived_version = auto._auto_prompt_version(
        source, context={}, prompt_hash=sha256(historical_prompt.encode()).hexdigest(), profile_version=profile,
    )
    assert archived_version == "full-prose-auto-prompt-v55"
    archived_candidate = auto.render_auto(source, payload, prompt_version=archived_version, profile_version=profile)
    assert archived_candidate["blocks"][1]["text"] == "Take the cover off."
    assert auto.validate_auto(
        source, archived_candidate, response=payload, prompt_version=archived_version, profile_version=profile,
    ).passed


def test_note_draft_cannot_move_labels_or_count_label_only_edits_as_rewrites():
    source = document("Note: Remove the cover.", "Inspect the seal.")
    assert run(source, response("Remove the cover.", "Check the seal.")).error_code == "REWRITE_UNCHANGED"
    assert run(
        source, response("Take the cover off.", "Note: Check the seal."),
    ).error_code == "REWRITE_NOTE_LABEL_MUTATION"


@pytest.mark.parametrize("introduction", [
    "Overview. The acoustic insulation softens vibration from the ventilation system.",
    'The manual states: "The acoustic insulation softens vibration from the ventilation system."',
])
def test_new_introduction_rejects_copied_sentence_without_rejecting_archived_reply(introduction):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("The acoustic insulation softens vibration from the ventilation system.")
    payload = response("Vibration from the ventilation unit is damped by the acoustic insulation.",
                       introduction=introduction)
    version = "full-prose-auto-prompt-v55"
    candidate = auto.render_auto(source, payload, prompt_version=version)
    archived = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert archived.passed
    with pytest.raises(ValueError, match="^REWRITE_INTRODUCTION_COPIED$"):
        auto.require_distinct_generated_introduction(
            source, candidate, rewritten_paths=archived.report["changed_prose_slots"],
        )


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
@pytest.mark.parametrize(("original", "advisory", "required"), [
    (
        "Tighten the clamp on the existing bracket.",
        "The bracket's clamp should be tightened.",
        "The bracket's clamp must be tightened.",
    ),
    (
        "Install the protective cap over the port.",
        "You should install the port's protective cap.",
        "You must install the port's protective cap.",
    ),
])
def test_new_automatic_drafts_preserve_required_directives_and_replay_old_prompts(profile, original, advisory, required):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    version = "full-prose-auto-prompt-v55"
    weakening = response(advisory, introduction="This article describes service information.")
    archived = auto.render_auto(source, weakening, prompt_version=version, profile_version=profile)
    validation = auto.validate_auto(source, archived, response=weakening, prompt_version=version, profile_version=profile)
    assert validation.passed
    with pytest.raises(ValueError, match="^REWRITE_REQUIRED_ACTION_WEAKENED$"):
        auto.require_required_procedure_actions(source, archived, rewritten_paths=validation.report["changed_prose_slots"])

    failed = rewrite.rewrite_ordered_document(source, client=Draft(weakening), context={}, profile_version=profile)
    assert failed.error_code == "REWRITE_REQUIRED_ACTION_WEAKENED"
    assert failed.document == source and failed.raw_response == weakening
    accepted = rewrite.rewrite_ordered_document(
        source, client=Draft(response(required, introduction="This article describes service information.")),
        context={}, profile_version=profile,
    )
    assert accepted.error_code is None


@pytest.mark.parametrize(("original", "wording"), [
    ("You should install the protective cap.", "The protective cap should be installed."),
    ("Install the protective cap if desired.", "The protective cap should be installed if desired."),
    ("Install the protective cap. Inspect the seal.", "Fit the cap in place. You should inspect the seal."),
    ("Tighten the clamp.", "The clamp must be tightened."),
    ("Install the cap.", "The technician should check the cap."),
    ('Remove the frame. The screen says “You should remove the central cover.”',
     'The display reads “You should remove the central cover.” Take the frame off.'),
    ("Install the protective cap. The shop note recommends installing the neighboring cap.",
     "You should install the neighboring cap, as the workshop suggests. Fit the protective cap into place."),
])
def test_required_action_guard_is_bound_to_the_source_directive(original, wording):
    from autodata_ingestion import procedure_rewrite_auto as auto

    auto.require_required_procedure_actions(
        document(original), document("This covers service information.", wording), rewritten_paths=("/blocks/0/text",),
    )


@pytest.mark.parametrize(("original", "wording"), [
    ("Install the dust cap. Tighten the clamp.",
     "Fit the protective cap in place. The clamp should be tightened."),
    ("Install the protective cap.", "A separate note about setup. The protective cap should be installed."),
    ("Install the dust cap, then optionally tighten the retainer.",
     "The dust cap should be fitted first, followed by optional tightening of the retainer."),
    ("Note: Install the cap over the port.", "Note: The port's cap should carefully be installed."),
])
def test_required_action_guard_tracks_the_complete_rewritten_passage(original, wording):
    from autodata_ingestion import procedure_rewrite_auto as auto

    with pytest.raises(ValueError, match="^REWRITE_REQUIRED_ACTION_WEAKENED$"):
        auto.require_required_procedure_actions(
            document(original), document("This covers service information.", wording), rewritten_paths=("/blocks/0/text",),
        )


@pytest.mark.parametrize(("source_text", "introduction", "rewritten_paths"), [
    (
        "The panel shows “The system is ready for a check.”",
        "“The system is ready for a check.” is the display message.",
        ("/blocks/0/text",),
    ),
    ("Torque is 18 N·m at T-42.", "Torque is 18 N·m at T-42.", ("/blocks/0/text",)),
    (
        "The acoustic insulation softens vibration from the ventilation system.",
        "The acoustic insulation softens vibration from the ventilation system.",
        (),
    ),
])
def test_new_introduction_preserves_authored_quotations_technical_literals_and_retained_paths(
    source_text, introduction, rewritten_paths,
):
    from autodata_ingestion import procedure_rewrite_auto as auto

    auto.require_distinct_generated_introduction(
        document(source_text), {"blocks": [{"text": introduction}]}, rewritten_paths=rewritten_paths,
    )


def test_new_introduction_checks_prose_around_an_exact_authored_quotation():
    from autodata_ingestion import procedure_rewrite_auto as auto

    wording = "The panel shows “Ready” whenever the vehicle enters inspection mode."
    with pytest.raises(ValueError, match="^REWRITE_INTRODUCTION_COPIED$"):
        auto.require_distinct_generated_introduction(
            document(wording), {"blocks": [{"text": wording}]}, rewritten_paths=("/blocks/0/text",),
        )


@pytest.mark.parametrize(("source_text", "draft_text"), [
    (
        "The panel displays “Service mode available” during diagnostics.",
        "During the diagnostic check, “Service mode available” is shown on the instrument cluster.",
    ),
    (
        "The switch labeled 'Ventilation override' controls the fan.",
        "The fan is governed by the switch marked 'Ventilation override'.",
    ),
    (
        "The report calls this an “overnight check”. The screen displays “Ready for service”.",
        "The report describes a “nighttime review”. “Ready for service” appears on the screen.",
    ),
    (
        "The bulletin describes the mechanism as “ready for inspection”.",
        "The bulletin says the mechanism is “prepared for a review”.",
    ),
])
def test_new_display_quotation_check_allows_surrounding_and_unrelated_prose_edits(source_text, draft_text):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(source_text)
    candidate = document("This article describes the system.", draft_text)
    auto.require_preserved_display_quotations(source, candidate, rewritten_paths=("/blocks/0/text",))


@pytest.mark.parametrize("draft_text", [
    "The screen lists the operating state.",
    "The screen shows “Maintenance mode available”. The report calls it “Service mode available”.",
    "The switch marked “Service mode available” identifies the operating control.",
])
def test_new_display_quotation_check_rejects_missing_or_moved_authored_display_text(draft_text):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("The display reads “Service mode available” during the check.")
    candidate = document("This article describes the system.", draft_text)
    with pytest.raises(ValueError, match="^REWRITE_DISPLAY_QUOTATION_MUTATION$"):
        auto.require_preserved_display_quotations(source, candidate, rewritten_paths=("/blocks/0/text",))


def test_automatic_rewrite_has_own_identity_and_no_manual_acceptance():
    source = document("Remove the cover.", "Tighten the bolts to 25 Nm with tool T-42.")
    payload = response("Take the cover off.", source["blocks"][1]["text"])
    payload["replacements"][1].update(action="retain", reason="Keep the named bolts and tool with their torque.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.profile_version == PROFILE
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["passed"] and not report["content_acceptance_required"]
    assert report["publication_mode"] == "automatic"
    assert report["profile_version"] == PROFILE
    assert report["changed_prose_slots"] == ["/blocks/0/text"]
    assert report["retained_paths"] == ["/blocks/1/text"]
    reviewed = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version="full-prose-review-v1")
    assert reviewed.error_code is None
    assert result.document["blocks"][0]["block_id"] != reviewed.document["blocks"][0]["block_id"]
    assert rewrite.validate_article_rewrite(source, reviewed.document, profile_version="full-prose-review-v1").report["content_acceptance_required"]


def test_source_bound_prompt_omits_routing_facts_and_keeps_historical_hashes():
    from autodata_ingestion.procedure_rewrite_auto import _auto_prompt_version

    source = document("Remove the cover.")
    context = {"year": 2024, "configuration": "Test 2.0L AWD"}
    legacy = rewrite.build_rewrite_prompt(source, context=context, profile_version=PROFILE)
    current = rewrite.build_rewrite_prompt(source, context=context, profile_version=SOURCE_BOUND_REWRITE_PROFILE)
    payload = json.loads(current)
    assert json.loads(legacy)["context"] == context
    assert "context" not in payload and "2.0L" not in current and "2024" not in current
    assert payload["profile_version"] == SOURCE_BOUND_REWRITE_PROFILE
    assert payload["document"] == source
    assert payload["slots"] == json.loads(legacy)["slots"]
    assert current == rewrite.build_rewrite_prompt(source, context={"year": 2019},
                                                  profile_version=SOURCE_BOUND_REWRITE_PROFILE)
    assert _auto_prompt_version(source, context=context, prompt_hash=sha256(legacy.encode()).hexdigest()) == (
        json.loads(legacy)["prompt_version"]
    )
    assert _auto_prompt_version(source, context=context, prompt_hash=sha256(current.encode()).hexdigest(),
                                profile_version=SOURCE_BOUND_REWRITE_PROFILE) == payload["prompt_version"]
    assert _auto_prompt_version(source, context=context, prompt_hash=sha256(legacy.encode()).hexdigest(),
                                profile_version=SOURCE_BOUND_REWRITE_PROFILE) is None
    assert _auto_prompt_version(source, context=context, prompt_hash=sha256(current.encode()).hexdigest()) is None


@pytest.mark.parametrize("replacement,introduction,error", [
    ("Take the cover off.", "This procedure covers the 2.0L engine.", "REWRITE_TECHNICAL_MUTATION"),
    ("Remove the cover.", "This procedure describes component access.", "REWRITE_UNCHANGED"),
    ("Take the cover off.", "This procedure describes component access.", None),
])
def test_source_bound_profile_applies_the_existing_mechanical_checks(replacement, introduction, error):
    source = document("Remove the cover.")
    payload = response(replacement, introduction=introduction)
    result = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={"engine": "2.0L"},
                                              profile_version=SOURCE_BOUND_REWRITE_PROFILE)
    assert result.error_code == error
    assert result.profile_version == SOURCE_BOUND_REWRITE_PROFILE
    assert result.raw_response == payload
    if error:
        assert result.document == source
    else:
        validation = rewrite.validate_article_rewrite(source, result.document,
                                                      profile_version=SOURCE_BOUND_REWRITE_PROFILE)
        assert validation.passed
        assert validation.report["changed_prose_slots"] == ["/blocks/0/text"]
        assert not rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).passed


def test_failed_source_bound_draft_records_each_rejected_passage():
    source = document(
        "Remove the cover.", "Install the shield.",
        "Tighten the bolts to 25 Nm.", "Do not disconnect the harness.",
    )
    draft = response(
        "Remove the cover.", "Take off the shield.",
        "Tighten the bolts to 20 Nm.", "Do not disconnect the harness.",
    )
    draft["replacements"][3].update(action="retain", reason="Preserve the safety instruction.")
    prior = deepcopy(draft)
    client = Draft(draft)
    result = rewrite.rewrite_ordered_document(
        source, client=client, context={}, profile_version=SOURCE_BOUND_REWRITE_PROFILE,
    )
    assert client.calls == 1
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.document == source
    assert result.raw_response == draft == prior
    assert result.model_metadata["passage_errors"] == [
        {"path": "/blocks/0/text", "code": "REWRITE_UNCHANGED"},
        {"path": "/blocks/1/text", "code": "REWRITE_ACTION_MUTATION"},
        {"path": "/blocks/2/text", "code": "REWRITE_TECHNICAL_MUTATION"},
    ]


def test_source_bound_passage_errors_require_the_original_path_and_block_order():
    source = document("Remove the cover.", "Install the shield.")
    draft = response("Remove the cover.", "Take off the shield.")
    draft["replacements"].reverse()
    result = rewrite.rewrite_ordered_document(
        source, client=Draft(draft), context={}, profile_version=SOURCE_BOUND_REWRITE_PROFILE,
    )
    assert result.error_code == "REWRITE_SLOT_MISMATCH"
    assert "passage_errors" not in result.model_metadata


def _assembly_label_rewrite(replacement, *, label="REAR TIMING SENSOR ASSEMBLY"):
    source = document("unused")
    item = source["blocks"][0]
    del item["text"]
    item.update(type="ordered_list", items=[label])
    draft = response(replacement, introduction="This article presents component reference information.")
    draft["replacements"][0]["path"] = "/blocks/0/items/0"
    return source, draft


def test_automatic_rewrite_rewords_an_assembly_label_with_its_component_intact():
    source, draft = _assembly_label_rewrite("Assembly for the rear timing sensor.")
    result = run(source, draft)
    assert result.error_code is None
    assert result.document["blocks"][1]["items"] == ["Assembly for the rear timing sensor."]
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v60"


@pytest.mark.parametrize("replacement", [
    "Assembly for the front timing sensor.",
    "Assembly for the rear pressure sensor.",
    "Assembly for the rear timing switch.",
    "Assembly for the timing sensor.",
])
def test_automatic_rewrite_rejects_a_changed_assembly_component(replacement):
    source, draft = _assembly_label_rewrite(replacement)
    assert run(source, draft).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


def test_failed_source_bound_draft_locates_changed_assembly_component():
    source, draft = _assembly_label_rewrite("Assembly for the rear timing switch.")
    result = rewrite.rewrite_ordered_document(
        source, client=Draft(draft), context={}, profile_version=SOURCE_BOUND_REWRITE_PROFILE,
    )
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.model_metadata["passage_errors"] == [
        {"path": "/blocks/0/items/0", "code": "REWRITE_SPEC_SCOPE_MUTATION"},
    ]


def test_automatic_rewrite_replays_old_assembly_draft_before_current_publication_checks():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source, draft = _assembly_label_rewrite("Assembly for the rear timing switch.")
    saved = render_full(source, draft, profile_version=PROFILE)
    prompt = auto._build_auto_prompt_v59(source, context={})
    version = auto._auto_prompt_version(source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest())
    assert version == "full-prose-auto-prompt-v55"
    assert auto.validate_auto(source, saved, response=draft, prompt_version=version).passed
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, saved, saved_prompt_version=version)


@pytest.mark.parametrize(("label", "replacement"), [
    ("CLEAN THE FUEL PUMP ASSEMBLY", "Carry out cleaning of the fuel pump assembly."),
    ("CLEAN FUEL PUMP ASSEMBLY", "Carry out cleaning of the fuel pump assembly."),
    ("REBUILD FUEL PUMP ASSEMBLY", "Carry out the rebuild of the fuel pump assembly."),
    ("CALIBRATE THROTTLE ACTUATOR ASSEMBLY", "Carry out calibration of the throttle actuator assembly."),
    ("FLUSH COOLANT PUMP ASSEMBLY", "Carry out flushing of the coolant pump assembly."),
    ("ALIGN THROTTLE ACTUATOR ASSEMBLY", "Carry out alignment of the throttle actuator assembly."),
    ("PRIME FUEL PUMP ASSEMBLY", "Carry out priming of the fuel pump assembly."),
])
def test_automatic_rewrite_keeps_an_uppercase_assembly_instruction_editable(label, replacement):
    source, draft = _assembly_label_rewrite(replacement, label=label)
    assert run(source, draft).error_code is None


@pytest.mark.parametrize(("label", "replacement"), [
    ("STOP LAMP SWITCH ASSEMBLY", "Assembly for the stop lamp sensor."),
    ("START SWITCH ASSEMBLY", "Assembly for the start relay."),
    ("START INHIBITOR SWITCH ASSEMBLY", "Assembly for the start inhibitor relay."),
    ("SIDE IMPACT SENSOR ASSEMBLY", "Assembly for the front impact sensor."),
])
def test_automatic_rewrite_preserves_switch_and_restraint_component_names(label, replacement):
    source, draft = _assembly_label_rewrite(replacement, label=label)
    assert run(source, draft).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


def test_assembly_label_prompt_rechecks_new_technical_qualifiers_at_publication():
    from autodata_ingestion import procedure_rewrite_auto as auto

    source, draft = _assembly_label_rewrite("Assembly for the rear timing sensor.")
    paragraph = document("The reservoir contains 14 US gal of water.")["blocks"][0]
    paragraph.update(block_id="p1", source_order=2)
    source["blocks"].append(paragraph)
    draft["replacements"].append({
        "block_id": "p1", "path": "/blocks/1/text", "action": "rewrite",
        "text": "The reservoir holds 14 US gal of water per second.", "reason": "",
    })
    version = "full-prose-auto-prompt-v60"
    saved = auto.render_auto(source, draft, prompt_version=version)
    assert auto.validate_auto(source, saved, response=draft, prompt_version=version).passed
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, saved, saved_prompt_version=version)


@pytest.mark.parametrize("replacement", ["Remove the cover.", " REMOVE  THE COVER. ", "Remove the cover!"])
def test_automatic_profile_rejects_unchanged_ordinary_prose(replacement):
    source = document("Remove the cover.")
    payload = response(replacement)
    if replacement == source["blocks"][0]["text"]:
        payload["replacements"][0].update(action="retain", reason="Keep accurate source instructions")
    result = run(source, payload)
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.document == source


@pytest.mark.parametrize(("source_text", "replacement"), [
    (
        "After the cap comes off, gently slide the cable from the guide beside the outer bracket.",
        "Once the cap comes off, gently slide the cable from the guide beside the outer bracket.",
    ),
    (
        "Release the latch, slide the cable along the inner guide and lift it out by hand.",
        "Open the clip, slide the cable along the inner guide and lift it out manually.",
    ),
    ("Remove the cap.", "First, remove the cap."),
    ("Remove the cap.", "Remove the cap before proceeding."),
    ("Remove the cap before proceeding.", "Remove the cap."),
])
def test_automatic_profile_rejects_near_verbatim_ordinary_prose(source_text, replacement):
    source = document(source_text)
    result = run(source, response(replacement))
    assert result.error_code == "REWRITE_PROSE_TOO_SIMILAR"
    assert result.document == source


@pytest.mark.parametrize("warning", [
    "Never connect the battery while the connector is wet.",
    "Warning: Wear eye protection during this procedure.",
    "Inspect the cable, but do not connect the battery yet.",
    "The battery cannot be connected while the connector is wet.",
    "Inspect the cable before service. Do not reconnect the battery until the terminals are dry.",
])
def test_automatic_profile_retains_inline_safety_instruction(warning):
    source = document(warning, "Remove the cover.")
    payload = response("Reconnect the battery before drying the connector.", "Take the cover off.")
    assert run(source, payload).error_code == "REWRITE_SAFETY_MUTATION"
    payload["replacements"][0].update(action="retain", text=warning, reason="Exact safety wording")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == warning


def test_current_and_historical_validation_bind_their_own_prose_rules():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = document("Remove the cover.")
    payload = response("First, remove the cover.")
    candidate = render_full(source, payload, profile_version=PROFILE)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version="full-prose-auto-prompt-v2")
    assert historical.passed
    assert historical.report["validator_version"] == "full-prose-auto-validator-v1"
    for bound_response in (payload, None):
        current = auto.validate_auto(source, candidate, response=bound_response, prompt_version="full-prose-auto-prompt-v4")
        assert current.error_codes == ("REWRITE_PROSE_TOO_SIMILAR",)
        assert current.report["validator_version"] == "full-prose-auto-validator-v2"


def test_ordinary_text_cannot_be_reduced_to_its_specification():
    source = document("Tighten the bolts to 25 Nm.")
    result = run(source, response("25 Nm."))
    assert result.error_code == "REWRITE_PROSE_MISSING"
    assert result.document == source


def test_automatic_profile_rejects_new_inline_warning_or_prohibition():
    source = document("Remove the cover.")
    for payload in (
        response("Never take the cover off."),
        response("Take the cover off.", introduction="Do not take the cover off."),
    ):
        result = run(source, payload)
        assert result.error_code == "REWRITE_SAFETY_MUTATION"
        assert result.document == source


def test_distinct_prose_preserves_action_order_facts_and_source_blocks():
    source = document(
        "After removing the cover, inspect the cable to check whether the guide is secure.",
        "Use tool T-42 to tighten the cover bolts evenly to 25 Nm after seating the gasket.",
    )
    source["blocks"].extend([
        {"block_id": "warning", "source_order": 3, "type": "callout",
         "text": "Before work, isolate the battery.", "evidence_ids": ["safety-evidence"]},
        {"block_id": "image", "source_order": 4, "type": "image",
         "status": "unavailable", "unavailable_reason": "fixture", "evidence_ids": ["media-evidence"]},
    ])
    replacements = (
        "Take the cover off before checking that the cable guide is firmly attached.",
        source["blocks"][1]["text"],
    )
    payload = response(*replacements)
    payload["replacements"][1].update(action="retain", reason="Keep the gasket condition and the specified torque.")
    result = run(source, payload)
    assert result.error_code is None
    assert [block["source_order"] for block in result.document["blocks"]] == [1, 2, 3, 4, 5]
    for original, rendered, text in zip(source["blocks"][:2], result.document["blocks"][1:3], replacements):
        assert rendered == dict(original, source_order=original["source_order"] + 1, text=text)
    for original, rendered in zip(source["blocks"][2:], result.document["blocks"][3:]):
        assert rendered == dict(original, source_order=original["source_order"] + 1)


@pytest.mark.parametrize("source_text,draft,code", [
    ("Avoid reconnecting the battery while the connector is wet.",
     "Reconnect the battery before drying the connector.", "REWRITE_SAFETY_MUTATION"),
    ("The battery needs to stay disconnected until the connector is dry.",
     "Let the connector dry while the battery is attached.", "REWRITE_SAFETY_MUTATION"),
    ("Tighten the cover to 7 Nm only after the seal sits flush.",
     "Set the cover torque to 7 Nm.", "REWRITE_SAFETY_MUTATION"),
    ("Fit the connector cover unless the harness is damaged.",
     "Install the connector cover.", "REWRITE_SAFETY_MUTATION"),
    ("Disconnect the battery before handling the connector.",
     "Attach the battery ahead of connector service.", "REWRITE_ACTION_MUTATION"),
    ("Tighten the connector cover screws to 7 Nm.",
     "Loosen the connector cover screws until they reach 7 Nm.", "REWRITE_SPEC_SCOPE_MUTATION"),
    ("First disconnect the battery, then remove the connector cover.",
     "Take the connector cover off before detaching the battery.", "REWRITE_ACTION_MUTATION"),
    ("Remove the connector cover.",
     "Take the cover off the connector and start the engine.", "REWRITE_ACTION_MUTATION"),
    ("Check that the guide clips are attached.",
     "Inspect whether the guide clips hold firmly and start the engine.", "REWRITE_ACTION_MUTATION"),
])
def test_automatic_rewrite_rejects_changed_safety_conditions_and_recognizable_actions(source_text, draft, code):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == code
    assert result.document == source


def test_prerequisite_remains_verbatim_when_the_other_steps_are_rewritten():
    condition = "Fit the cover only after the seal sits flush."
    source = document(condition, "Inspect the cable.")
    payload = response(condition, "Check the cable for wear.")
    payload["replacements"][0].update(action="retain", reason="Preserve the seal prerequisite.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == condition
    assert result.document["blocks"][2]["text"] == "Check the cable for wear."


def test_automatic_rewrite_checks_actions_bound_to_each_slot():
    source = document("Remove the connector cover.", "Inspect the guide.")
    result = run(source, response("Check the guide visually.", "Take the cover off the connector."))
    assert result.error_code == "REWRITE_ACTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("First disconnect the battery, then remove the connector cover.",
     "Once power has been isolated at the battery, take the cover off the connector."),
    ("Tighten the connector cover screws evenly.",
     "For an even fit, tighten each screw on the connector cover."),
    ("Remove the latch cover and inspect the cable.",
     "Check the cable once the latch cover is removed."),
    ("Open the housing before disconnecting the battery.",
     "Detach the battery after opening the housing."),
])
def test_automatic_rewrite_accepts_recognizable_action_paraphrases(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("intro", [
    "Start the engine before removing the cover.",
    "This article covers cover access. Then, start the engine.",
    "You should start the engine first.",
    "The engine must be started before this procedure.",
])
def test_automatic_rewrite_rejects_an_imperative_introduction(intro):
    source = document("Remove the connector cover.")
    result = run(source, response("Take the cover off the connector.", introduction=intro))
    assert result.error_code == "REWRITE_INTRODUCTION_INSTRUCTION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Tighten the connector cover screws to 7 Nm.", "Set the torque of the battery mounting screws to 7 Nm."),
    ("Inflate the front left tire to 33 psi.", "Raise the spare tire pressure to 33 psi."),
    ("Tighten the cover screws to 25Nm.", "Tighten the mounting screws to 25Nm."),
    ("Warm the cover to 30–40 °C before testing the seal.",
     "Before testing the seal, warm the housing to 30–40 °C."),
    ("Cool the probe to -25 °C.", "Lower the axle temperature to -25 °C."),
    ("Set the front tire pressure to 30-40 psi.", "Use a range of 30-40 psi for the spare tire."),
    ("Read the gauge in kilopascals after it stabilizes.",
     "Once the needle settles, read the result in pounds per square inch."),
    ("Read the gauge in kilopascals after it stabilizes.",
     "Observe the needle after it settles."),
    ("Read the gauge in psi once it stabilizes.", "Read the needle once it settles."),
    ("Report the measurement using kilopascals.", "Report the measurement using megapascals."),
    ("Use kilopascals rather than pounds per square inch.",
     "Report pressures in pounds per square inch rather than kilopascals."),
])
def test_automatic_rewrite_preserves_full_specification_scope(source_text, draft):
    source = document(source_text, "Inspect the cover.")
    payload = response(draft, "Check the cover for wear.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source

    payload["replacements"][0].update(action="retain", text=source_text, reason="Keep the specification and its context.")
    model = Draft(payload)
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "retain"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == source_text
    assert result.document["blocks"][2]["text"] == "Check the cover for wear."


def test_automatic_rewrite_cannot_invent_a_unit_assignment():
    source = document("Read the indicated pressure after the needle settles.")
    result = run(source, response("Read the gauge in kilopascals once it settles."))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Inspect 2 guides for wear.", "Check the condition of the 2 guides."),
    ("Inspect the guide at step 2.", "At step 2, check the guide for wear."),
    ("In the tray, inspect the filter.", "Check the filter in the tray."),
    ("Spend a few minutes checking the guide.", "Take a moment to inspect the guide."),
    ("Read the odometer once the display settles.", "Once the display settles, note the odometer reading."),
    ("The sensor cable extends for miles along the track.", "The sensor cable follows the track for a long distance."),
    ("The service depot is in Watts.", "Watts is home to the service depot."),
])
def test_scoped_guard_leaves_bare_numbers_and_incidental_units_editable(source_text, draft):
    source = document(source_text)
    model = Draft(response(draft))
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "rewrite"
    assert result.error_code is None


def test_introduction_cannot_reassign_an_exact_source_specification():
    source = document("Tighten the connector cover screws to 7 Nm.", "Inspect the cover.")
    payload = response("Tighten the connector cover screws to 7 Nm.", "Check the cover for wear.",
                       introduction="The battery mounting screws require 7 Nm.")
    payload["replacements"][0].update(action="retain", reason="The scope is exact.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the left rear splash shield for access.",
     "Take off the splash shield from the right rear to gain access."),
    ("Inspect the left front harness connector.",
     "Check the harness connector at the left rear."),
    ("Disconnect the left sensor and remove the right cover.",
     "Detach the right sensor, then take off the left cover."),
    ("Remove the left-hand wheel-arch liner.",
     "Take off the liner from the wheel arch."),
    ("Open the LH engine bay access panel.",
     "Swing the RH access panel open in the engine bay."),
    ("Inspect the inboard pad and remove the outboard shim.",
     "Check the outboard pad, then take the inboard shim off."),
    ("Remove the left cover first, then remove the right cover.",
     "Take off the right cover before lifting off the left cover."),
    ("Inspect the upper guide and remove the lower bracket.",
     "Check the lower guide, then take off the upper bracket."),
])
def test_automatic_rewrite_rejects_changed_direction_for_each_recognized_action(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_DIRECTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the left rear splash shield for access.",
     "Take off the splash shield from the left rear to gain access."),
    ("Remove the left-hand wheel-arch liner.",
     "Take the liner off the LH wheel arch."),
    ("Inspect the left front harness connector.",
     "Check the front-left connector for the harness."),
    ("Inspect the cover for debris left behind by the gasket.",
     "Check the cover for any debris that remained by the gasket."),
    ("Inspect the rubber pad on the inside face of the door.",
     "Check the pad on the inner face of the door."),
    ("Remove the left cover first, then remove the right cover.",
     "Take off the right cover after lifting off the left cover."),
    ("Disconnect the right harness before removing the left sensor.",
     "Once the right harness is detached, take off the left sensor."),
    ("The guard is on the right side of the housing.",
     "The housing's right-hand side carries the guard."),
    ("Remove the lifting hook after the hoist has left the bay.",
     "Take off the lifting hook once the hoist has departed."),
    ("Lower the spare tire to the ground.", "Bring the spare tire down to the ground."),
])
def test_automatic_rewrite_accepts_equivalent_direction_and_ordinary_prose(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("source_text,draft", [
    ("If the seal is not flush, inspect the connector.",
     "Check the connector once the seal is flush."),
    ("Inspect the harness if no moisture is visible.",
     "Check the harness when moisture can be seen."),
    ("For vehicles without an auxiliary battery, inspect the starter connection.",
     "Check the starter connection on vehicles with an auxiliary battery."),
    ("Reconnection is forbidden while the connector is damp.",
     "Restore the electrical connection while the connector is still damp."),
    ("Remove the cover without lifting the cable guide.",
     "Take the cover off after lifting the cable guide."),
    ("Inspect only the connector shell for corrosion.",
     "Check the entire harness for corrosion."),
])
def test_automatic_rewrite_protects_negative_applicability_and_restrictions(source_text, draft):
    source = document(source_text, "Inspect the cover.")
    payload = response(draft, "Check the cover for wear.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SAFETY_MUTATION"
    assert result.document == source

    payload["replacements"][0].update(action="retain", text=source_text, reason="Keep the full restriction.")
    model = Draft(payload)
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "retain"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == source_text
    assert result.document["blocks"][2]["text"] == "Check the cover for wear."


@pytest.mark.parametrize("source_text,draft", [
    ("The connector cover is supplied without a gasket.",
     "The gasket and connector cover are supplied separately."),
    ("Only the connector shell is supplied with the kit.",
     "The kit contains the connector shell by itself."),
])
def test_automatic_rewrite_keeps_nonprocedural_negative_phrasing_editable(source_text, draft):
    model = Draft(response(draft))
    result = rewrite.rewrite_ordered_document(document(source_text), client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "rewrite"
    assert result.error_code is None


@pytest.mark.parametrize("draft", [
    ("Remove the cable shield.", "Remove the inlet cover."),
    ("Take off the cable shield.", "Lift off the inlet cover."),
    ("Take the cable shield off.", "Lift the inlet cover off."),
])
def test_automatic_rewrite_rejects_reciprocal_swaps_of_unambiguous_simple_targets(draft):
    source = document("Remove the inlet cover.", "Remove the cable shield.")
    result = run(source, response(*draft))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


def test_automatic_rewrite_rejects_swapping_brief_unarticled_targets():
    source = document("Remove inlet cover.", "Remove harness shield.")
    result = run(source, response("Take off the harness shield.", "Lift the inlet cover off."))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


_INSPECTION_TARGETS = ("Inspect the seal.", "Inspect the gasket.")
_FOCUSED_INSPECTION_TARGETS = ("Inspect the seal for wear.", "Inspect the gasket for cracks.")
_ONE_FOCUS_SWAP = ("Check the gasket for wear.", "Check the seal.")
_LEAKAGE_SWAP = ("Check the gasket for leakage.", "Check the seal for leakage.")


def _inspection_pair_source(originals, *, in_cell):
    source = document(*originals)
    if in_cell:
        instruction = source["blocks"][1]
        instruction["source_order"] = 1
        source["blocks"][1] = {
            "type": "table", "block_id": "inspection-cell", "source_order": 2,
            "rows": [[{"text": "Service addendum", "blocks": [instruction]}, "25 Nm"]],
            "evidence_ids": ["fixture-evidence"],
        }
    return source


def _inspection_pair_response(prompt, drafts):
    return {
        "introduction": "This procedure describes component inspection.",
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "reason": "", "text": draft}
            for slot, draft in zip(json.loads(prompt)["slots"], drafts)
        ],
    }


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("originals,drafts", [
    (_INSPECTION_TARGETS, _ONE_FOCUS_SWAP),
    (_INSPECTION_TARGETS, ("Check the gasket for signs of corrosion.", "Check the seal for damage.")),
    (_INSPECTION_TARGETS, _LEAKAGE_SWAP),
    (_INSPECTION_TARGETS, ("Check the gasket for cracking.", "Check the seal for cracking.")),
    (_INSPECTION_TARGETS, ("Check the gasket for indications of wear.", "Check the seal for indications of wear.")),
    (
        ("Inspect the seal for wear before service.", "Inspect the gasket for wear before service."),
        ("Check the gasket for wear before service.", "Check the seal for wear before service."),
    ),
    (
        _INSPECTION_TARGETS,
        (
            "Check the gasket for wear, then wipe the mating surface.",
            "Check the seal for wear, then wipe the mating surface.",
        ),
    ),
    (_FOCUSED_INSPECTION_TARGETS, ("Check the gasket for signs of cracks.", "Check the seal for signs of wear.")),
    (
        (*_INSPECTION_TARGETS, "Inspect the housing."),
        ("Check the gasket for wear.", "Check the housing.", "Check the seal for cracks."),
    ),
])
def test_automatic_rewrite_rejects_swapped_inspections_with_focus(in_cell, originals, drafts):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _inspection_pair_source(originals, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _inspection_pair_response(prompt, drafts)
    result = run(source, payload)
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_COMPONENT_SWAP",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("originals,drafts", [
    (_INSPECTION_TARGETS, ("Check the seal.", "Check the gasket.")),
    (_INSPECTION_TARGETS, ("Check the seal for wear.", "Check the gasket for signs of damage.")),
    (_INSPECTION_TARGETS, ("Check the seal for leakage.", "Check the gasket for indications of cracking.")),
    (
        ("Inspect the seal for wear before service.", "Inspect the gasket for wear before service."),
        ("Check the seal for wear before service.", "Check the gasket for wear before service."),
    ),
    (_FOCUSED_INSPECTION_TARGETS, ("Check the seal for signs of wear.", "Check the gasket for signs of cracks.")),
    (("Inspect the seal.", "Inspect the seal for wear."), ("Check the seal.", "Check the seal for signs of wear.")),
])
def test_automatic_rewrite_preserves_inspection_assignment_and_focus(in_cell, originals, drafts):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _inspection_pair_source(originals, in_cell=in_cell)
    payload = _inspection_pair_response(auto.build_auto_prompt(source, context={}), drafts)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "868c62588f30c36d358b9e39da9e5db52538674222500a7305d830244c5e3f4c",
     "038288b20a570506e3755e3d92fa0940c8edbd468d973aaa3c60c272d664b948",
     "31cb9a5d31b250628f575589f60a24f66049696e94cf8ba48608df1734e67961"),
    (True, "a4e8b701646a9e787e4f1c88cf660cc0c93f144399761a35902f3167de53e826",
     "e053df34c315ea6d23f95e369f0714f88a117e45c7a463ecfed898c4b236b1cc",
     "d9311d2a46e6955040f2a52fa1171d24aadeb9be2aed74deeb86e201cf9e0c34"),
])
def test_automatic_reopens_v46_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _inspection_pair_source(_INSPECTION_TARGETS, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v46(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v46"
    payload = _inspection_pair_response(prompt, _ONE_FOCUS_SWAP)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_COMPONENT_SWAP",)


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "8a53e68a3f332bcb269c7767b77efb5860a70199fe953dd99b27d779147b740a",
     "6fa1ecb58a8d660df5db6903ad513de3ef44eded84acf57493a2d3a5aa825d8d",
     "c00ca5210d361bcc27de1b681362b231418337e061fa7ff0588cc3462f22e8f0"),
    (True, "aba878bff2eb9ced8ae22335880b6474522a4596b913ca009609167f49bc48fa",
     "68306fbf85e0eea873673c32f27b8e932786d288e3872d17104db0d3f8f03a24",
     "b9209d4bf9e117e4ef121663cefc8e71a327cb465392331b876a5f2adc2aaf58"),
])
def test_automatic_reopens_v47_inspection_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _inspection_pair_source(_INSPECTION_TARGETS, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v47(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v47"
    payload = _inspection_pair_response(prompt, _LEAKAGE_SWAP)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_COMPONENT_SWAP",)


def test_extended_inspection_target_match_does_not_hide_a_previously_proven_swap():
    source = document(*_INSPECTION_TARGETS, "Inspect the seal for leakage.")
    result = run(source, response(*_ONE_FOCUS_SWAP, "Check the seal for leakage."))

    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


def test_automatic_rewrite_rejects_a_cycle_of_distinct_simple_targets():
    source = document("Remove the inlet cover.", "Remove the cable shield.", "Remove the pump guard.")
    result = run(source, response("Take off the cable shield.", "Take the pump guard off.",
                                  "Lift off the inlet cover."))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


@pytest.mark.parametrize("source_texts,draft", [
    (("Remove the inlet cover.", "Remove the inlet cover."),
     ("Take off the inlet cover.", "Take off the inlet cover.")),
    (("Remove the inlet cover.", "Remove the cable shield."),
     ("Take the cover off the inlet.", "Take off the wiring shield.")),
    (("Remove the inlet cover.", "Remove the cover from the inlet."),
     ("Take the cover off the inlet.", "Lift off the inlet cover.")),
    (("Remove the inlet cover.", "Remove the cable shield after the latch releases."),
     ("Take the inlet cover off.", "Once the latch releases, take the cable shield off.")),
    (("Inspect the pump casing.", "Check the pump casing."),
     ("Look over and inspect the casing of the pump.", "Visually inspect the casing of the pump.")),
    (("Remove the inlet cover.", "Remove the cable shield.", "Remove the inlet cover."),
     ("Take off the cable shield.", "Lift off the inlet cover.", "Take the inlet cover off.")),
])
def test_automatic_rewrite_keeps_repeat_operations_and_nonliteral_aliases_editable(source_texts, draft):
    result = run(document(*source_texts), response(*draft))
    assert result.error_code is None


@pytest.mark.parametrize("intro", [
    "This procedure applies to diesel models equipped with an auxiliary battery.",
    "No battery isolation is required for this service.",
    "This repair is safe to perform with the engine running.",
    "This procedure restores hydraulic pressure by bleeding the brake lines.",
    "This procedure describes access to the right rear pump cover.",
    "The pump cover procedure is guaranteed to fix the issue.",
])
def test_automatic_rewrite_rejects_unsupported_claims_in_introduction(intro):
    source = document("Remove the pump cover.")
    result = run(source, response("Take the cover off the pump.", introduction=intro))
    assert result.error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft,intro", [
    ("Remove the pump cover.", "Take the cover off the pump.",
     "This procedure covers access to the pump by removing its cover."),
    ("Remove the pump cover.", "Take the cover off the pump.", "This article covers pump cover removal."),
    ("Remove the right rear pump cover.", "Take the pump cover off from the right rear.",
     "This procedure describes access to the rear-right pump cover."),
    ("Inspect the brake lines.", "Check the brake lines for wear.",
     "This procedure covers a brake line inspection."),
    ("Inspect the brake lines.", "Check the brake lines for wear.",
     "This section describes checking the brake lines."),
    ("Remove the high-voltage battery cover.", "Take the cover off the high-voltage battery.",
     "This procedure describes gaining access to the high voltage battery."),
])
def test_automatic_rewrite_accepts_coherent_source_bound_introductions(source_text, draft, intro):
    result = run(document(source_text), response(draft, introduction=intro))
    assert result.error_code is None


def test_intro_component_can_be_grounded_in_protected_source_text():
    source = document("Remove the guide bracket.")
    source["blocks"].append({
        "block_id": "s0", "source_order": 2, "type": "callout", "label": "Caution",
        "text": "Protect the brake lines before removing the guide bracket.",
        "evidence_ids": ["fixture-evidence"],
    })
    payload = response("Take off the guide bracket.", introduction="This procedure describes access near the brake line.")
    assert run(source, payload).error_code is None


@pytest.mark.parametrize("source_text,draft", [
    pytest.param("Remove the inlet cover first, then remove the cable shield.",
                 "Take the cable shield off before lifting off the inlet cover.",
                 id="same-action-reversal-explicit-then"),
    pytest.param("Remove the inlet cover. Then remove the cable shield.",
                 "Take the cable shield off first. Lift off the inlet cover next.",
                 id="same-action-reversal-across-sentences"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Detach the inlet cover, then take off the pump lead.",
                 id="verbs-assigned-to-opposite-targets"),
    pytest.param("Inspect the guide bracket and remove the harness shield.",
                 "Check the harness shield, then take the guide bracket off.",
                 id="parallel-distinct-assignments-reversed-with-grammatical-order-unchanged"),
    pytest.param("Inspect the cover after removing the connector.",
                 "After taking off the cover, check the connector.",
                 id="conditional-mixup-retains-both-verb-and-object-words"),
])
def test_automatic_rewrite_rejects_proven_within_leaf_clause_mutation(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    (
        "Remove the inlet cover first, then remove the cable shield.",
        "Lift off the cable shield and take the inlet cover off.",
    ),
    (
        "Inspect the connector shell, then inspect the retaining clip.",
        "Check the connector shell for damage.",
    ),
    (
        "Inspect the connector and seal, then remove the cable shield.",
        "Check the shield before taking off the connector and seal.",
    ),
])
def test_within_leaf_guard_abstains_without_two_exact_bound_targets(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    assert auto._clause_assignment_changed(source_text, draft) is False


@pytest.mark.parametrize("source_text,draft", [
    pytest.param("Remove the inlet cover first, then remove the cable shield.",
                 "Take the cable shield off after lifting off the inlet cover.",
                 id="same-action-reversal-with-matching-valid-before-after-paraphrase"),
    pytest.param("Remove the inlet cover, reinstall the cover temporarily, then remove the inlet cover again.",
                 "Take off the inlet cover. Fit the cover temporarily, then lift off the inlet cover a second time.",
                 id="same-action-repeated-identical-object-remains-legitimate"),
    pytest.param("Inspect the connector. Inspect the connector again.",
                 "Check the connector, then inspect it a second time.",
                 id="same-action-repeat-across-simple-sentences"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Detach the lead from the pump before taking the cover off the inlet.",
                 id="distinct-different-verb-objects-paraphrased-by-noun-complement"),
    pytest.param("Inspect the connector shell and cover for visible wear.",
                 "Check the cover and connector shell for signs of wear.",
                 id="unordered-shared-verb-noun-phrase"),
    pytest.param("Disconnect the pump lead before removing the inlet cover.",
                 "Once the pump lead is detached, lift off the inlet cover.",
                 id="different-clauses-rendered-via-conditional-grammar"),
    pytest.param("Inspect the inlet cover and the cable shield.",
                 "Check the cable shield and the inlet cover.",
                 id="coordinated-shared-verb-objects-reordered"),
    pytest.param("Inspect the cover for rust and confirm the guide is attached.",
                 "Check the cover for corrosion and inspect the guide for secure attachment.",
                 id="one-directive-paraphrased-with-duplicate-synonym"),
    pytest.param("Inspect the cable shield and inspect the inlet cover.",
                 "Check the inlet cover and check the cable shield.",
                 id="bare-conjunction-does-not-state-an-order-for-inspection"),
    pytest.param("Inspect the cable shield; inspect the inlet cover.",
                 "Check the inlet cover. Also check the cable shield.",
                 id="semicolon-without-explicit-timing-leaves-prose-order-ambiguous"),
    pytest.param("Disconnect the pump lead before removing the inlet cover.",
                 "After detaching the pump lead, lift off the inlet cover.",
                 id="different-grammar-preserves-explicit-before-after-with-exact-targets"),
    pytest.param("Remove the inlet cover, then remove the inlet cover.",
                 "Take off the inlet cover before lifting off the inlet cover.",
                 id="same-action-on-one-component-intentionally-repeated"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Lift off the inlet cover and detach the pump lead.",
                 id="parallel-distinct-actions-with-the-same-assignment-in-opposite-syntax"),
])
def test_within_leaf_guard_keeps_repeat_parallel_and_qualified_controls(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    assert auto._clause_assignment_changed(source_text, draft) is False
    source = document(source_text)
    payload = response(draft)
    current = run(source, payload)
    try:
        auto.render_auto(source, payload, prompt_version="full-prose-auto-prompt-v7")
    except ValueError as error:
        # Recognized v7 limitations stay visible. The new check does not
        # reinterpret installer synonyms or parallel action grammar.
        assert current.error_code == str(error) == "REWRITE_ACTION_MUTATION"
    else:
        assert current.error_code is None


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover.", "Take the cover off if the seal is dry."),
    ("If the retaining clip is damaged, inspect the harness.", "Check the harness for signs of wear."),
    ("If the seal is dry, remove the cover.", "Take the cover off if the connector is dry."),
    ("Disconnect the battery.", "Detach the battery after the ignition is off."),
    ("Inspect the seal once the cover is cool.", "Check the seal for damage."),
    ("Install the seal.", "Fit the old seal into place."),
    ("Remove the seal.", "Take the new seal off."),
    ("Install a new seal.", "Fit the used seal into place."),
    ("Install a new seal.", "Fit the seal into place."),
    ("Remove the cover.", "Take the cover off with a pry bar."),
    ("On models equipped with a trailer package, inspect the connector.",
     "On trims equipped with a trailer package, check the connector."),
    ("Remove the seal.", "Take the seal off with a heat gun."),
    ("Remove the cover with a pry bar.", "Take the cover off with a screwdriver."),
    ("Remove the cover with a pry bar.", "Take the cover off."),
    ("Inspect the housing.", "If desired, check the housing for damage."),
    ("Inspect the connector.", "On models equipped with a trailer package, check the connector."),
    ("Inspect the seal for wear.", "Check the seal for corrosion."),
    ("Inspect the seal for wear.", "Check the seal."),
])
def test_automatic_rewrite_rejects_proven_new_missing_or_changed_task_qualifiers(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover.", "Take the cover off."),
    ("If the retaining clip is damaged, inspect the harness.", "Check the harness if the retaining clip is damaged."),
    ("If the seal is dry, remove the cover.", "When the seal has dried, take the cover off."),
    ("Inspect the seal once the cover is cool.", "After the cover is cool, check the seal."),
    ("Disconnect the battery once the ignition is off.", "After switching the ignition off, detach the battery."),
    ("Install a new seal.", "Fit a replacement seal into place."),
    ("Install the old gasket.", "Fit the original gasket into place."),
    ("Remove the old gasket.", "Take the original gasket off."),
    ("Remove the cover using a pry bar.", "With a pry bar, take the cover off."),
    ("Remove the cover when accessing the seal.", "Take the cover off to reach the seal."),
    ("Inspect the seal to determine if the lip is damaged.", "Check the seal for a damaged lip."),
    ("Inspect the seal for wear.", "Check the seal for signs of wear."),
    ("Inspect the seal.", "Check the seal for wear."),
    ("The filter housing is supplied with a heat gun.", "The heat gun comes together with the filter housing."),
    ("Before removing the cover, disconnect the battery.",
     "Detach the battery before taking off the cover."),
    ("If the latch vibrates, inspect the motor.", "Check the motor when the latch makes a rattling sound."),
])
def test_automatic_rewrite_preserves_equivalent_and_unresolved_qualifier_phrasing(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("source_text,draft,error", [
    ("Remove all fasteners except the captive bolt.",
     "Take off every fastener, including the captive bolt.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove the clips, other than the cable clip.",
     "Take off the cable clip as well as the other clips.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect all hinges excluding the latch hinge.",
     "Check all hinges except the center hinge.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove all fasteners except the captive bolt.",
     "Take off every fastener.", "REWRITE_QUALIFIER_MUTATION"),
    ("Except if the seal is dry, inspect the housing.",
     "Check the housing whenever needed.", "REWRITE_SAFETY_MUTATION"),
    ("Inspect the seal, then inspect the cover.",
     "Check the seal, or check the cover instead.", "REWRITE_CLAUSE_MUTATION"),
    ("Inspect either the seal or the cover.",
     "Check the seal and check the cover.", "REWRITE_CLAUSE_MUTATION"),
    ("Either inspect the seal or inspect the cover.",
     "Check the seal and check the cover.", "REWRITE_CLAUSE_MUTATION"),
    ("If the retaining clip is damaged and the seal is dry, inspect the harness.",
     "Check the harness if the retaining clip is damaged or the seal is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the retaining clip is damaged and the seal is dry, inspect the harness.",
     "Check the harness if the retaining clip is damaged.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry and cool, remove the cover.",
     "Take the cover off if the seal is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("When the seal is dry, remove the cover.",
     "Take the cover off if the seal is dry and cool.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry or cool, remove the cover.",
     "When the seal is cool and dry, take the cover off.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness if the seal is cool and the housing is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new oil seal.", "Fit the used oil seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new outer seal.", "Fit the used outer seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install an undamaged new seal.", "Fit a damaged new seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new rubber oil seal.", "Fit a used rubber oil seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove the old transmission seal.", "Take the new transmission seal off.", "REWRITE_QUALIFIER_MUTATION"),
])
def test_automatic_rewrite_v10_rejects_proven_scope_changes(source_text, draft, error):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == error
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove all fasteners except the captive bolt.",
     "Take off all fasteners other than the captive bolt."),
    ("Inspect either the seal or the cover.",
     "Either check the cover or check the seal instead."),
    ("Inspect the seal, then inspect the cover.",
     "After checking the seal, check the cover."),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness when the housing is cool and the seal is dry."),
    ("If the seal is dry and cool, remove the cover.",
     "Take the cover off when the seal is cool and dry."),
    ("If the retaining clip is damaged or the seal is dry, inspect the harness.",
     "Check the harness when the seal is dry or the retaining clip is damaged."),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness when the seal has dried and the housing has cooled."),
    ("Install a new rubber oil seal.", "Fit the replacement rubber oil seal into place."),
    ("Install a new outer seal.", "Fit the outer replacement seal into place."),
    ("Install an undamaged original oil seal.", "Fit the old undamaged oil seal into place."),
])
def test_automatic_rewrite_v10_preserves_equivalent_scope(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


def test_automatic_rewrite_v10_retains_conditional_exception_exactly():
    first = "Except if the seal is dry, inspect the housing."
    source = document(first, "Remove the cover.")
    payload = response(first, "Take the cover off.")
    payload["replacements"][0].update(action="retain", reason="Keep the source exception.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == first


def _scoped_prose_source(text, *, in_cell):
    source = document("Remove the retaining clip.", text)
    if in_cell:
        instruction = source["blocks"][1]
        instruction["source_order"] = 1
        source["blocks"][1] = {
            "type": "table", "block_id": "scope-cell", "source_order": 2,
            "rows": [[{"text": "Service addendum", "blocks": [instruction]}, "25 Nm"]],
            "evidence_ids": ["fixture-evidence"],
        }
    return source


def _scoped_prose_response(prompt, draft):
    return {
        "introduction": "This procedure describes component access.",
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "reason": "",
             "text": "Take the retaining clip off." if index == 0 else draft}
            for index, slot in enumerate(json.loads(prompt)["slots"])
        ],
    }


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover while the ignition is off.", "Take the cover off while the ignition is on."),
    ("Remove the cover while the ignition is off.", "Carefully take the cover off for access."),
    ("Remove the cover while the ignition is off.", "Take the panel off while the ignition is on."),
    ("Remove the cover while the ignition is off.", "With the ignition off, take the panel off."),
    ("Take the cover off with the ignition switched off.", "Remove the cover with the ignition switched on."),
    ("Remove the cover while the ignition is on.", "With the ignition off, take the cover off."),
    ("Install the gasket with the flange dry.", "Fit the gasket while the flange is wet."),
    ("With the flange dry, install the gasket.", "Fit the gasket into place."),
    ("Install the gasket.", "With the flange dry, fit the gasket."),
    ("Install the gasket.", "With the flange dry, carefully fit the gasket into place."),
    ("Install the seal while the pump is off.", "Fit the seal while the motor is off."),
    ("Install the seal while the pump is off.", "Fit the seal after the pump is off."),
])
def test_automatic_rewrite_v12_rejects_changed_simultaneous_conditions(in_cell, source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    validation = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert validation.error_codes == ("REWRITE_QUALIFIER_MUTATION",)
    assert validation.report["validator_version"] == "full-prose-auto-validator-v53"


_COMBINED_REPLACEMENT_SOURCE = (
    "Disconnect the battery, remove the shared drive belt, and inspect the mounting area before replacing both components."
)
_LATE_MOUNTING_INSPECTION = (
    "Detach the battery, take the shared drive belt off, and check the mounting area after replacing both components."
)
_COMBINED_REPLACEMENT_THEN_COMMA = (
    "Detach the battery. Then, take off the shared drive belt. "
    "Check the mounting area before replacing both components."
)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    _LATE_MOUNTING_INSPECTION,
    "Detach the battery, take the shared drive belt off, and check the mounting area before replacing one component.",
    "Detach the battery, take the shared drive belt off, and check the drive cover before replacing both components.",
    "Detach the battery, take the shared drive belt off, check the mounting area, and replace both components.",
    "Detach the starter lead, take the shared drive belt off, and check the mounting area before replacing both components.",
    "Detach the battery, take the timing belt off, and check the mounting area before replacing both components.",
    _COMBINED_REPLACEMENT_THEN_COMMA.replace("before replacing", "after replacing"),
])
def test_automatic_rewrite_rejects_changed_combined_replacement_preparation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_COMBINED_REPLACEMENT_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Detach the battery, take the shared drive belt off, and check the mounting area before replacing both components.",
    "Detach the battery. Take off the shared drive belt. Before replacing both components, check the mounting area.",
    "Detach the battery and take off the shared drive belt. Replace both components after checking the mounting area.",
    "Detach the battery first. Next, take off the shared drive belt. Check the mounting area before replacing the two components.",
    _COMBINED_REPLACEMENT_THEN_COMMA,
    "Detach the battery and then, take off the shared drive belt. Check the mounting area before replacing both components.",
    "Detach the battery. Take off the shared drive belt. Then, check the mounting area before replacing both components.",
])
def test_automatic_rewrite_accepts_equivalent_combined_replacement_preparation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_COMBINED_REPLACEMENT_SOURCE, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "2ed0353b16f41bf69a5346fc20792d271986133f9d8d7aad1107502a351f3916",
     "758dcc9dc517c12c5ba30600ee0220d244b22b0166a7f9632a7d8592eda4d396",
     "de7a9e1888f0dd75edfff3960b7e5cd03286a32e044a7f2514acf11a5552d9bc"),
    (True, "09630cc7520edeb3fff0c5e43f7c5a339c626efde52a4ef2e1d41d69df6b9038",
     "532f379b09963cb647287a6329e7617ba51f4d94ab5cefee2bc07c552d2ded4b",
     "89a23e9b6b4c9126ab1c77b7b0956d738d6a3705fb3181f99530efd196677138"),
])
def test_automatic_reopens_v45_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_COMBINED_REPLACEMENT_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v45(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v45"
    payload = _scoped_prose_response(prompt, _LATE_MOUNTING_INSPECTION)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell,prompt_hash,report_hash", [
    (False, "75777156970c5976105895006843d9317f1cf7c0fcde8bf3d666565268dba30a",
     "d8610155a720b2e7c6e6c100a84c43c054efbe4d5101a1ecd17d47b71ace619e"),
    (True, "821f9d94eaff766c4a175a06f0bbc12cf0fd06ca0b6a589b7f3f6d975f705fc6",
     "0e4acd6e50d8340d8938967b2445633753693135cec148e35b7631243c121fbc"),
])
def test_automatic_v47_keeps_original_then_comma_validation(in_cell, prompt_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_COMBINED_REPLACEMENT_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v47(source, context={"make": "Fixture"})
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    payload = _scoped_prose_response(prompt, _COMBINED_REPLACEMENT_THEN_COMMA)
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    for version in ("full-prose-auto-prompt-v46", "full-prose-auto-prompt-v47"):
        historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
        assert historical.error_codes == ("REWRITE_CLAUSE_MUTATION",)
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).passed


_MULTI_SENTENCE_CONNECTOR_SOURCE = (
    "Inspect the brake connector before service. Remove the retaining clip and replace the terminal if damaged."
)
_COPIED_FIRST_CONNECTOR_SENTENCE = (
    "Inspect the brake connector before service. Take the retaining clip off. If the terminal is damaged, replace it."
)
_UNCONDITIONAL_TERMINAL_DRAFT = (
    "Before servicing, check the brake connector. Take the retaining clip off and replace the terminal."
)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    _COPIED_FIRST_CONNECTOR_SENTENCE,
    "Before servicing, check the brake connector. Remove the retaining clip and replace the terminal if damaged.",
    "First, inspect the brake connector before service. Take the retaining clip off. If the terminal is damaged, replace it.",
    "Inspect the brake connector before service, then take the retaining clip off and replace the terminal if damaged.",
])
def test_automatic_rewrite_rejects_copied_sentences_in_editable_prose(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_MULTI_SENTENCE_CONNECTOR_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_PROSE_TOO_SIMILAR"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_PROSE_TOO_SIMILAR",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    _UNCONDITIONAL_TERMINAL_DRAFT,
    "Before servicing, check the brake connector. Take the retaining clip off and replace the connector if it is damaged.",
    "Before servicing, check the brake connector. Take the retaining clip off and replace the terminal if it is undamaged.",
    "Check the brake connector before servicing, then take off the retaining clip and replace the terminal if the clip is damaged.",
])
def test_automatic_rewrite_rejects_changed_embedded_terminal_condition(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_MULTI_SENTENCE_CONNECTOR_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_MULTI_SENTENCE_CONNECTOR_SOURCE,
     "Before servicing, check the brake connector. Take the retaining clip off. If the terminal is damaged, replace it."),
    (_MULTI_SENTENCE_CONNECTOR_SOURCE,
     "Check the brake connector before servicing, then take off the retaining clip and replace the terminal if it shows damage."),
    ("Open the housing. Inspect the bracket around the cable guide.",
     "Open the housing. Check the bracket surrounding the cable guide."),
])
def test_automatic_rewrite_accepts_rephrased_editable_prose(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,draft,error_code,prompt_hash,candidate_hash,report_hash", [
    (False, _COPIED_FIRST_CONNECTOR_SENTENCE, "REWRITE_PROSE_TOO_SIMILAR",
     "c9fcbb134c7d665060f62478c4d064972f6e9994968f712dca8633242fd3ce03",
     "82dd7158c35d82210ca539073bb6617d28777be7250803189732b61619757353",
     "dce78d34b60fd6d2cd7bf257626222a8f1fd7e405b94d068410a8180e212820d"),
    (True, _COPIED_FIRST_CONNECTOR_SENTENCE, "REWRITE_PROSE_TOO_SIMILAR",
     "6095203d1dc193cb2b0fcae03157466b9796bd118fbbbabd8f8f0c46cffdc553",
     "c92916b25af0a7ec6603451a844b957ff7e9d546f4823b8a8e3d468e467b3898",
     "819aaf61bb089824ae2925b847deee983a8a47680186410fa067e8a721a4b1c9"),
    (False, _UNCONDITIONAL_TERMINAL_DRAFT, "REWRITE_QUALIFIER_MUTATION",
     "c9fcbb134c7d665060f62478c4d064972f6e9994968f712dca8633242fd3ce03",
     "0367d85ee9368fb5296b656e5b4e3385317f81ff28939a2808278dba85c8a955",
     "abc83edaf1775384ac07bf617462641b62e0ec4ad9719d70ff395479aa6edea0"),
    (True, _UNCONDITIONAL_TERMINAL_DRAFT, "REWRITE_QUALIFIER_MUTATION",
     "6095203d1dc193cb2b0fcae03157466b9796bd118fbbbabd8f8f0c46cffdc553",
     "ebece0d645976ed01b98c039484d762b195e70c43d58300cea75ee033d44c441",
     "045e690311a4002b34b694e03685a4d3a2f60bd5df0969a5e9248d4c589548e2"),
])
def test_automatic_reopens_v44_with_original_validation_bytes(
    in_cell, draft, error_code, prompt_hash, candidate_hash, report_hash,
):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_MULTI_SENTENCE_CONNECTOR_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v44(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v44"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == (error_code,)


_OIL_PUMP_PREPARATION_SOURCE = "Remove the oil pan and clean the strainer before releasing the pump body."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Take the oil pan off and clean the strainer after releasing the pump body.",
    "Take the oil pan off before releasing the pump body.",
    "Take the oil pan off and clean the filter before releasing the pump body.",
    "Take the oil pan off and clean the strainer before releasing the valve body.",
    "Take off the oil pan or clean the strainer before releasing the pump body.",
    "Clean the strainer before releasing the pump body, then remove the oil pan.",
    "Before releasing the pump body, clean the strainer, then take off the oil pan.",
])
def test_automatic_rewrite_rejects_changed_oil_pump_preparation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_OIL_PUMP_PREPARATION_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Take the oil pan off, then clean the strainer before releasing the pump body.",
    "Take the oil pan off. Before releasing the pump body, clean the strainer.",
    "Take off the oil pan and clean the strainer ahead of releasing the pump body.",
    "Before releasing the pump body, take off the oil pan and clean the strainer.",
])
def test_automatic_rewrite_accepts_equivalent_oil_pump_preparation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_OIL_PUMP_PREPARATION_SOURCE, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "9579eff8379dabca185a10290266fb5866f592567c2f5032d811940bf70b4e28",
     "85596dbc73d91bb0fe763a3228f1b664397b011e1c4010ec4665431d059b2208",
     "c83c0fe946e41b33eb309426b6cee618d996ebd1b982528fa7ceb2046b57a938"),
    (True, "71ed1c0d718b7ba3e2bd92fd7f3016cb338fbd8f42cc012689c86cb40d2e854a",
     "23010145208416afe0a320bb7e7ab630f2984b433e906ad9ddf0a22a13d0be72",
     "e72b72bd5509eabcf21a241b441a19bc241ab87057e5f8ed8f009057a7a18e80"),
])
def test_automatic_reopens_v43_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_OIL_PUMP_PREPARATION_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v43(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v43"
    payload = _scoped_prose_response(prompt, "Take the oil pan off and clean the strainer after releasing the pump body.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


_DISCONNECT_BEFORE_SERVICE_SOURCE = "Disconnect the battery before service."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "After servicing, detach the battery.",
    "While servicing, detach the battery.",
    "Detach the battery.",
    "Before servicing, detach the alternator connector.",
])
def test_automatic_rewrite_rejects_changed_disconnect_before_service(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_DISCONNECT_BEFORE_SERVICE_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Before servicing, disconnect the battery.",
    "Prior to service, detach the battery.",
    "Carry out the service after disconnecting the battery.",
    "Disconnect the battery before carrying out the service.",
    "Before service, disconnect the battery from the electrical system.",
    "Disconnect the battery before performing any service.",
])
def test_automatic_rewrite_accepts_equivalent_disconnect_before_service(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_DISCONNECT_BEFORE_SERVICE_SOURCE, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "a5f2a45c94a3b822eadfa0a81ff83eab266322ddd96b0ca67491e1e78bf8571b",
     "50ee290af26eb2909e4abeb5f2a86d852e3d92ae1da5f9aa69cbb0226be81660",
     "3b8fb2eb2e09f4a451e84e9f6182e4c454c78c03935c373f2c18d7c7b3b32341"),
    (True, "dd121e32487ebdb8d7a84152411dde794b97eef49474da1f00b110608530b730",
     "172ffe5d7a12f161367ce4a1633080549d0c4bc0650710c7fa60d1e493b3c55c",
     "16f3a9bb687d9f167b4fdcdbf976438f1a2aa3ac6eb52b902794176ae66e25ec"),
])
def test_automatic_reopens_v42_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_DISCONNECT_BEFORE_SERVICE_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v42(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v42"
    payload = _scoped_prose_response(prompt, "After servicing, detach the battery.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


_MAXIMUM_PULL_FORCE_SOURCE = "Pull the wiring harness plug with a maximum force of 35 N."
_MINIMUM_PULL_FORCE_SOURCE = "Pull the wiring harness plug with a minimum force of 35 N."
_RETAINING_PIN_FORCE = "Press the retaining pin with a maximum force of 35 N."
_REVERSED_RETAINING_PIN_FORCE = "When pressing the retaining pin, apply at least 35 N."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_RETAINING_PIN_FORCE, _REVERSED_RETAINING_PIN_FORCE),
    (_RETAINING_PIN_FORCE, "When pressing the guide pin, apply at most 35 N."),
    (_RETAINING_PIN_FORCE, "When pressing the retaining pin, apply 35 N."),
    ("When seating the sleeve, apply no more than 1.2 kN.", "Apply at least 1.2 kN to seat the sleeve."),
    ("Retaining pin: ≤35 N.", "Guide pin: ≤35 N."),
    (
        "Use a maximum force of 35 newtons on the pin.",
        "Use a minimum force of 35 newtons on the pin.",
    ),
    ("Release the fixture above 35 N.", "Release the fixture below 35 N."),
    ("Release the fixture at 35 N or greater.", "Release the fixture at 35 N or less."),
    ("Limit the retaining pin to 35 N.", "Limit the guide pin to 35 N."),
    ("Retaining pin: 35 newtons.", "Guide pin: 35 newtons."),
    ("Retaining pin: 1.2 kN.", "Guide pin: 1.2 kN."),
    ("Press the retaining pin with 35 N.", "Push the guide pin using 35 N."),
    ("Push the latch with 35 N.", "Pull the latch using 35 N."),
    ("Pull the retaining clip at 35 N.", "At 35 N, push the retaining clip."),
    ("At 35 N, press the retaining pin.", "Use the guide pin with 35 N."),
    ("Press the retaining pin:35 N.", "Press the guide pin:35 N."),
    ("The retaining pin must be pressed with 35 N.", "The guide pin must be pulled with 35 N."),
    ("The insertion effort is 35 N.", "Removal effort is 35 N."),
    ("The insertion force stays below 35 N.", "The insertion force stays above 35 N."),
    ("The load remains below 35 N throughout travel.", "The load remains above 35 N throughout travel."),
    ("Keep the load on the terminal directly above 35 N.", "Keep the load on the terminal directly below 35 N."),
    (
        "The terminal directly below 35 N on the test board is the return terminal.",
        "On the test board, the return terminal sits directly below 35 N.",
    ),
    ("Connector 35 N maximum.", "Connector 35 N minimum."),
    ("Connector 30–35 N.", "Terminal 30–35 N."),
    (
        "The insertion effort at terminal 35 N is 35 N.",
        "Removal effort at terminal 35 N is 35 N.",
    ),
])
def test_automatic_rewrite_retains_unproved_measured_force(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.article_document import project_ordered_document
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert rejected.document == source
    cue = json.loads(prompt)
    assert cue["slots"][-1]["required_action"] == "retain"
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    assert auto.validate_auto(
        source, candidate, response=payload, prompt_version=cue["prompt_version"],
    ).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Retain the exact force specification.")
    retained = run(source, payload)
    assert retained.error_code is None
    body = project_ordered_document(retained.document)["body"]
    assert original in body and "Take the retaining clip off." in body
    assert auto.validate_auto(source, retained.document, response=payload).report["retained_paths"] == [
        cue["slots"][-1]["path"],
    ]


@pytest.mark.parametrize("draft", [
    "The maximum force on the clip is 35 N.",
    "This procedure describes the 35 N maximum.",
    "This procedure specifies an insertion effort of 35 N.",
])
def test_automatic_rewrite_rejects_force_claims_in_the_introduction(draft):
    source = document("Remove the retaining clip.", _RETAINING_PIN_FORCE)
    payload = response("Take the retaining clip off.", _RETAINING_PIN_FORCE, introduction=draft)
    payload["replacements"][-1].update(action="retain", reason="Retain the exact force specification.")

    assert run(source, payload).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


@pytest.mark.parametrize("draft", [
    "Use a force of at most 35 N to pull the wiring harness plug.",
    "The retaining pin must be pressed with 35 N.",
])
def test_automatic_rewrite_rejects_repurposing_a_terminal_label_as_measured_force(draft):
    source = document("The retaining guide fits terminal 35 N on the test board.")
    payload = response(draft)

    assert run(source, payload).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (
        "The retaining guide fits terminal 35 N on the test board.",
        "On the test board, terminal 35 N accepts the retaining guide.",
    ),
    (
        "The terminal directly below connector 35 N on the test board is the return terminal.",
        "On the test board, the return terminal sits directly below connector 35 N.",
    ),
    (
        "The electrical load uses connector 35 N on the test board.",
        "On the test board, connector 35 N serves the electrical load.",
    ),
    (
        "Hold the electrical connector labeled: 35 N.",
        "Hold the electrical connector designated: 35 N.",
    ),
])
def test_automatic_rewrite_keeps_non_force_terminal_label_editable(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)

    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    assert run(source, payload).error_code is None


@pytest.mark.parametrize("text", [
    "Apply 35 N·m to the actuator.",
    "Apply 35 kN·m to the actuator.",
    "Apply 35 kN m to the actuator.",
    "Apply 35 lbf ft to the actuator.",
    "Apply 35 newton metres to the actuator.",
    "The stress rating is 35 kN/mm².",
    "The expression uses 35 N².",
    "The expression uses 35 kN².",
])
def test_measured_force_excludes_compound_units(text):
    from autodata_ingestion.procedure_rewrite_auto import _measured_force_scope

    assert not _measured_force_scope(text)


@pytest.mark.parametrize("draft", [
    "Press the retaining pin with a maximum force of 36 N.",
    "Press the retaining pin with a maximum force of 35 kN.",
])
def test_automatic_rewrite_rejects_changed_force_literal(draft):
    source = document(_RETAINING_PIN_FORCE)

    assert run(source, response(draft)).error_code == "REWRITE_TECHNICAL_MUTATION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "598db5fd3f4a85a778ec97687254add18af72f2517706ccb33a760509d9be8ef",
     "1147b6b775305cc8be15f53bfbba88204b6e56eb9ebf77255663f788ab97b61e",
     "68585c0e749835ce5ffc08faa27bb342e638a36a1f13790a30b221fff4eff960"),
    (True, "8df9be87e33565e1d019aeaca5dc7668d3132f2c77fd3231a8c4b88f6e17dfe8",
     "eb0c48b39c9a89c04186a17149b999f44534d76e5f80144cce13c226bb3d14f6",
     "ab724350d12cd000b48ac8afb44d997ea3de17db9b305037cdb37b84dd63e75d"),
])
def test_automatic_reopens_v50_force_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_RETAINING_PIN_FORCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v50(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v50"
    payload = _scoped_prose_response(prompt, _REVERSED_RETAINING_PIN_FORCE)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_MAXIMUM_PULL_FORCE_SOURCE, _MINIMUM_PULL_FORCE_SOURCE),
    (_MAXIMUM_PULL_FORCE_SOURCE, "Pull the wiring harness plug using 35 N of force."),
    (_MAXIMUM_PULL_FORCE_SOURCE, "Use a force of no more than 35 N to pull the latch."),
    (_MAXIMUM_PULL_FORCE_SOURCE, "Use a force of no more than 35 N to push the wiring harness plug."),
    (_MINIMUM_PULL_FORCE_SOURCE, _MAXIMUM_PULL_FORCE_SOURCE),
])
def test_automatic_rewrite_rejects_changed_harness_pull_force_bound(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_MAXIMUM_PULL_FORCE_SOURCE, "Use a force of no more than 35 N to pull the wiring harness plug."),
    (_MAXIMUM_PULL_FORCE_SOURCE, "When pulling the wiring harness plug, limit the applied force to 35 N."),
    (_MAXIMUM_PULL_FORCE_SOURCE, "Apply no more than 35 N of force when pulling the wiring harness plug."),
    (_MAXIMUM_PULL_FORCE_SOURCE, "Use a force of at most 35 N to pull the plug on the wiring harness."),
    (_MINIMUM_PULL_FORCE_SOURCE, "Apply at least 35 N of force when pulling the wiring harness plug."),
])
def test_automatic_rewrite_accepts_equivalent_harness_pull_force_bound(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "25942f6bc2d8566fcf4fe45058b6989831913fed1bebaafb82b36a8a61fea5a9",
     "a7e7872e7501f8f73c386bd3c1d31117f20287e69c250567ada174da2a58e320",
     "a9436265b3db4a36ec72163adceba4c24a6b0485ae09c172b14d5b5a4c9acbad"),
    (True, "68c752ef5d29634f351d436b2222ae61444b0902feb8e48a9a2c10159ad1ffc8",
     "0a8e3a7c50a2cef84c86198cff89a9c5b51c87974d1bdeb9245f62329ec1fad3",
     "ca9840586248bb59f223c48d698f819a5ba9dfed891888529a8b1a10bf2fd470"),
])
def test_automatic_reopens_v41_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_MAXIMUM_PULL_FORCE_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v41(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v41"
    payload = _scoped_prose_response(prompt, _MINIMUM_PULL_FORCE_SOURCE)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


_EYE_PROTECTION_START_SOURCE = "Wear eye protection before starting the engine."
_EYE_PROTECTION_START_UNSPECIFIED = "Wear eye protection before starting."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_EYE_PROTECTION_START_SOURCE, "After the engine starts, put on eye protection."),
    (_EYE_PROTECTION_START_SOURCE, "Start the engine, then put on eye protection."),
    (_EYE_PROTECTION_START_SOURCE, "When the engine starts, put on eye protection."),
    (_EYE_PROTECTION_START_SOURCE, "Put on hearing protection before starting the engine."),
    (_EYE_PROTECTION_START_SOURCE, "Put on eye protection before starting the compressor."),
    (_EYE_PROTECTION_START_SOURCE, "Start the engine."),
    (_EYE_PROTECTION_START_UNSPECIFIED, "After starting, put on eye protection."),
])
def test_automatic_rewrite_rejects_changed_prestart_eye_protection(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_EYE_PROTECTION_START_SOURCE, "Before starting the engine, put on eye protection."),
    (_EYE_PROTECTION_START_SOURCE, "Start the engine after putting on eye protection."),
    (_EYE_PROTECTION_START_SOURCE, "Put on protective eyewear before you start the engine."),
    (_EYE_PROTECTION_START_SOURCE, "Put on eye protection ahead of starting the engine."),
    (_EYE_PROTECTION_START_SOURCE, "Before the engine starts, put on eye protection."),
    (_EYE_PROTECTION_START_UNSPECIFIED, "Before you start, put on eye protection."),
    (_EYE_PROTECTION_START_UNSPECIFIED, "Start after putting on eye protection."),
])
def test_automatic_rewrite_accepts_equivalent_prestart_eye_protection(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "55ed1289c05c54da241a1d344e7b150dff5be70488667899f89ab20b2363c945",
     "0a6b27159c958eb0698d307fefc4d835ec06c4f72be88d771bd7732734853660",
     "ff2e44b1250ed0c18b2b5b5a7724d74fc423ffb70aa744462d5a16d0e930dcab"),
    (True, "44488b906d92b3338587e3d26a3f4913c8cc90d2d9532b3c5fee72c4557372f8",
     "6f4aa23590dcfa7aafa38c8b88c08afbd55c516103d30f4caf2a891a5640e330",
     "14271d6ccfd9003647c36a37fe936c179af777b4828b128db96b76f180c59998"),
])
def test_automatic_reopens_v40_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_EYE_PROTECTION_START_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v40(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v40"
    payload = _scoped_prose_response(prompt, "After the engine starts, put on eye protection.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


_CONDITIONAL_TERMINAL_SOURCE = "Remove the retaining clip and replace the terminal if damaged."
_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE = "Remove the retaining clip and replace terminal C-17 if damaged."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off and replace the terminal."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off and replace terminal C-17."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off and replace terminal C-17 if undamaged."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off and replace terminal C-17 if the clip is damaged."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off if terminal C-17 is damaged, then replace it."),
])
def test_automatic_rewrite_rejects_changed_conditional_terminal_replacement(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_CONDITIONAL_TERMINAL_SOURCE, "Take off the retaining clip and replace the terminal if it is damaged."),
    (_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off. If the terminal is damaged, replace it."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take the retaining clip off. If terminal C-17 is damaged, replace it."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take off the retaining clip, then renew terminal C-17 if it is damaged."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take off the retaining clip, then replace terminal C-17 if it shows damage."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take off the retaining clip and replace terminal C-17 if damage is present."),
    (_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, "Take off the retaining clip, then renew the C-17 terminal if it is damaged."),
])
def test_automatic_rewrite_accepts_equivalent_conditional_terminal_replacement(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "4664eb79aa5af4d9529e2c69408dcb732993b60005a025a02954e5dad5addcd5",
     "567f00ab149b378f9d0b38d72049373e4235fba35620b8623830e6a463ec05ff",
     "92f25daa9f0dbdf876682c4b165f6545a3bd05cc8075a78deb8e8043a010047d"),
    (True, "13d0ac94b6f66b89586590f8255ba4cbddd784cfd7988c060dfa87868a3a6203",
     "39dbb7c4001692314f31bdea3cbf0c3b50a0b48ce109ee62856c7b6b80b936e9",
     "1520209bb92b128909e6910e0e52468006a655523fac9bb9f411079a0dfee976"),
])
def test_automatic_reopens_v39_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_IDENTIFIED_CONDITIONAL_TERMINAL_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v39(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v39"
    payload = _scoped_prose_response(prompt, "Take the retaining clip off and replace terminal C-17.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


_COMPOUND_TIGHTENING_SOURCE = "Tighten the cover bolts by hand in a crisscross pattern."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Use an impact wrench to tighten the cover bolts in a crisscross pattern.",
    "Hand-tighten the cover bolts in clockwise order.",
    "Hand-tighten the bracket bolts in an alternating diagonal sequence.",
    "Tighten the cover bolts in an alternating diagonal sequence.",
    "Hand-tighten the cover bolts.",
])
def test_automatic_rewrite_rejects_changed_compound_tightening_method(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_COMPOUND_TIGHTENING_SOURCE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Hand-tighten the cover bolts in an alternating diagonal sequence.",
    "By hand, tighten the cover bolts in a cross pattern.",
    "Use a cross pattern when tightening the cover bolts by hand.",
    "Tighten the cover bolts in an alternating diagonal sequence by hand.",
    "In a crisscross pattern, hand-tighten the cover bolts.",
])
def test_automatic_rewrite_accepts_equivalent_compound_tightening_method(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_COMPOUND_TIGHTENING_SOURCE, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "cf0354149bb21a7e5036300c2ac64fd5953217c980284a8f0486ef6e7d0cb99b",
     "bb00c23461cbf93652fb752346a80e4197fdab2f3b8071fd63dc8c6aea640a3c",
     "150f7b5a0ff1f8b8667f3e829d87ad3d6b21a3dd893e520301587f0e19391191"),
    (True, "174843a727b04ab71620789dd478f13c107254db6a9871d0317cbac4d04ee37d",
     "00cef092e3bbb5c360efcfde42ce39626c865dd6d60f8753c86a5287faf7d4c4",
     "d85768c12e7bd8fe7808a287915a060510a06ecc1b49c694e654915b316165eb"),
])
def test_automatic_reopens_v38_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_COMPOUND_TIGHTENING_SOURCE, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v38(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v38"
    payload = _scoped_prose_response(prompt, "Use an impact wrench to tighten the cover bolts in a crisscross pattern.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


_HAND_TIGHTENING_SOURCE = "Tighten the cover bolts by hand."
_CRISSCROSS_TIGHTENING_SOURCE = "Tighten the cover bolts in a crisscross pattern."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_HAND_TIGHTENING_SOURCE, "Use an impact wrench to tighten the cover bolts."),
    (_HAND_TIGHTENING_SOURCE, "Hand-tighten the bracket bolts."),
    (_HAND_TIGHTENING_SOURCE, "Tighten the cover bolts securely."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts in clockwise order."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Use a crisscross sequence when tightening the bracket bolts."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts evenly."),
])
def test_automatic_rewrite_rejects_changed_tightening_method(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_HAND_TIGHTENING_SOURCE, "Hand-tighten the cover bolts."),
    (_HAND_TIGHTENING_SOURCE, "By hand, tighten the cover bolts."),
    (_HAND_TIGHTENING_SOURCE, "Using your hands, tighten the cover bolts."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts in an alternating diagonal sequence."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Use a crisscross pattern when tightening the cover bolts."),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts in a cross pattern."),
])
def test_automatic_rewrite_accepts_equivalent_tightening_method(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("original,draft,in_cell,prompt_hash,candidate_hash,report_hash", [
    (_HAND_TIGHTENING_SOURCE, "Use an impact wrench to tighten the cover bolts.", False,
     "357240280de45fd8e1c82c941f46e903304cd24a3ae1d23c3f0c801b4d057a30",
     "0dd9c245fa9a6b3b68f767de16edda57a74d20bb32025fde77327c9dfc14b08e",
     "8a131cfb25f968b249aa79474b4f5c04c5c75d0292fcc56b6f0daa734ad5f347"),
    (_HAND_TIGHTENING_SOURCE, "Use an impact wrench to tighten the cover bolts.", True,
     "98aced19a2aa074fd0102f7d00bd3f3bc4882b7faaa0682eda8995fb98de3a83",
     "65ba4e32852f3f2689f841721a993e63aa6bda57bd2168b23c093482912bda34",
     "e6c7c132a81f9f35dbea05bf13fcfd3da8b003c57cee47d2a1c541f5cb673a25"),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts in clockwise order.", False,
     "d3ea2850b4f38012119c7f6337d32ff1b3bcd34a143cb3f7b01bf39479455d31",
     "a090c552429dac2620685163290507059d468a7c1ba5cecad41049655199730c",
     "dce0be1130d152ba200694143c6f30eaf8e469b31cc49467eeb44b9160d48d08"),
    (_CRISSCROSS_TIGHTENING_SOURCE, "Tighten the cover bolts in clockwise order.", True,
     "5a61357bbbf940f8b51eadadf11bad799f4fbc132f485ee744a6737e94e499e3",
     "808bc8bc2f8757149875e710795eab449544f87bec21f9723db847d3007f56ad",
     "8acdfd7a1618d954f92dcce2b24ce48fe35095f7a3521e2c2a8708981334b914"),
])
def test_automatic_reopens_v37_with_original_validation_bytes(
    original, draft, in_cell, prompt_hash, candidate_hash, report_hash,
):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v37(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v37"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


_BRAKE_LINE_INSPECTION = "Visually inspect brake lines and replace as required."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check the brake lines visually and replace them.",
    "Visually check the brake lines and change the fittings as needed.",
    "Check the brake lines visually and replace the fittings as needed.",
    "Check the brake lines by sight.",
    "Check the brake lines and replace them as needed.",
])
def test_automatic_rewrite_rejects_changed_conditional_brake_line_replacement(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_BRAKE_LINE_INSPECTION, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check the brake lines visually and replace them as needed.",
    "Give the brake lines a visual check, then replace any that require replacement.",
    "Check the brake lines by sight. Replace them if necessary.",
    "Look over the brake lines and replace them if inspection shows replacement is needed.",
])
def test_automatic_rewrite_accepts_equivalent_conditional_brake_line_replacement(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_BRAKE_LINE_INSPECTION, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "b93088aa7612afa9e0e1e13587b58ea2073e3370792ef1c98fd780d575af2fef",
     "f28090a31ee31fcb2695a7bb20e987663fb86d6c1a9ced2755f22a1d5db412bc",
     "775073a891af662476e643260203b53754c64e7d896c27b834c211714397ebcd"),
    (True, "4dfae22e45e6bc5e8a23a6be5c6c78b7e119c41507d6657260fc6462a6d07050",
     "8232cc69c3f8b6b75286a2b8e196e4f7266b03c80c582350c62dbafa9a898c28",
     "d1eb17799a9327650718bb033ffae491eb40651a1275ff764b73e21e671045f8"),
])
def test_automatic_reopens_v36_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_BRAKE_LINE_INSPECTION, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v36(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v36"
    payload = _scoped_prose_response(prompt, "Check the brake lines visually and replace them.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


_LINE_FITTING_PREPARATION = "Remove the damaged line and clean the fittings before installation."


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft,error", [
    ("Take the damaged line off before installation.", "REWRITE_CLAUSE_MUTATION"),
    ("Take off the damaged line and clean the bracket before installation.", "REWRITE_CLAUSE_MUTATION"),
    ("Take off the damaged line or clean the fittings before installation.", "REWRITE_CLAUSE_MUTATION"),
    ("Take off the damaged line and clean the fittings.", "REWRITE_ACTION_MUTATION"),
    ("Take the damaged line off before installation, then clean the fittings.", "REWRITE_CLAUSE_MUTATION"),
    ("Take off the nearby line and clean the fittings before installation.", "REWRITE_CLAUSE_MUTATION"),
    ("Before installation, take the damaged line off. Clean the fittings.", "REWRITE_CLAUSE_MUTATION"),
])
def test_automatic_rewrite_rejects_changed_line_fitting_preparation(in_cell, draft, error):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(_LINE_FITTING_PREPARATION, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == error
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == (error,)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Take the damaged line off, then clean the fittings before installation.",
    "Take the damaged line off. Before installation, clean the fittings.",
    "Take off the damaged line and clean the fittings before fitting the replacement.",
    "Before installation, clean the fittings and take off the damaged line.",
    "Before installation, take off the damaged line and clean the fittings.",
    "Take the damaged line off, and wipe the fittings clean before installation.",
])
def test_automatic_rewrite_accepts_equivalent_line_fitting_preparation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_LINE_FITTING_PREPARATION, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "6c10a891be0bf9be97038d907b58fd3a5f066a3a646710af34e053a73207a1e8",
     "9ea79ac55df7e35b08f3b2d0c21f2cdf52c7cccc2d9efcfff3e683842091a25b",
     "c20c5ed8b2bc18fa5205b709d325cb12d627186eb6ac3680e3db027b55c7473c"),
    (True, "e27a26a06d4337cc8d6dbf80b7e9f13ed893a15744b92770e0e29d474dce57cf",
     "8b7934ab613f2e64ae84b5735750adb6c0b79b78325bb04c07bfa5dc4cf86a1c",
     "6563da48aa2548a45f68500c79c66f36e019ec89ca0c0e41a89e1e71a7a707cb"),
])
def test_automatic_reopens_v35_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_LINE_FITTING_PREPARATION, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v35(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v35"
    payload = _scoped_prose_response(prompt, "Take the damaged line off before installation.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Fill the pump with fluid.",
    "Empty the reservoir.",
    "Clean the pump housing.",
])
def test_automatic_rewrite_rejects_changed_pump_drain(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Drain the pump.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_ACTION_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_ACTION_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Drain the pump.", "Empty the pump."),
    ("Drain the pump.", "Let the fluid drain out of the pump."),
    ("Drain the pump.", "Allow the fluid to drain from the pump."),
    ("Drain the pump.", "Drain the fluid from the pump."),
    ("Drain the oil pump.", "Empty out the oil pump."),
])
def test_automatic_rewrite_accepts_equivalent_pump_drain(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "d5b8136eec86fd141cbafb33e9213081967bae366941e3746dd9ff3102796768",
     "18c66b94621392c7e2a200daf5c8215183d6388742eb62e054481f30daaabe17",
     "15713f6ddcbbbab1908e4b6b2aef294d9b4cc0d0777b0e1fd44ddaa6055e1179"),
    (True, "841eb604b5ae38ee696618bf93472036982680afc80630c31f53456e04044a4b",
     "0d9a3ffe27eb9a8efc6e189a2ca0c405ad455c81f07f72d177b6159cb6e3b0c1",
     "a77d9eacac19b1279331623d89be53d64fb8561ca6b692887d76a7d4b411f869"),
])
def test_automatic_reopens_v34_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Drain the pump.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v34(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v34"
    payload = _scoped_prose_response(prompt, "Fill the pump with fluid.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_ACTION_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "After the flange has dried, fit the replacement gasket into place.",
    "After the flange has dried, fit the original gasket into place.",
    "Fit the replacement oil seal before the flange dries.",
    "Carefully fit the replacement oil seal into place.",
    "After the flange has dried, fit the replacement oil seal at the pump outlet.",
])
def test_automatic_rewrite_rejects_changed_dry_replacement_installation(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Install a new oil seal after the flange is dry.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Install a new oil seal after the flange is dry.",
     "After the flange has dried, fit the replacement oil seal into place."),
    ("Install a new oil seal after the flange is dry.",
     "Once the flange has dried, fit the new oil seal."),
    ("Install a new oil seal after the flange is dry.",
     "Fit the replacement oil seal once the flange has dried."),
    ("Install a new oil seal.", "Fit a replacement oil seal into place."),
])
def test_automatic_rewrite_accepts_equivalent_dry_replacement_installation(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "d4b9f0f33581f39ca0ec4277e035df153b2881c53dcd6f5aa6b5e17e147173d5",
     "f6646e01df55da8e7a08ecc4d8305bb60dcb10c7c327b34ca43c6a3a578bf40c",
     "9d2bb3ba11b9e66ce55cefc1c2799cf45d084979a93d25b5c35b4587dcfe4c23"),
    (True, "a71454b812ed340520053d9afe39bf96631ba5e4508db09fc1d6c9ae46b14a14",
     "caaba1fd89ede6d68f9f9c324f62a14f7d879202f261b8b0f19e88878f33dbfa",
     "3ce8c4bc1797a6ddcb54cd61f16c435e30020210d949bdc4ad77995dac9a8f86"),
])
def test_automatic_reopens_v33_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Install a new oil seal after the flange is dry.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v33(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v33"
    payload = _scoped_prose_response(prompt, "After the flange has dried, fit the replacement gasket into place.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check the guide marks before taking the pump off.",
    "Check the bracket alignment marks before pump removal.",
    "Check the marks before taking the pump off.",
    "Check the alignment marks before taking the bracket off.",
])
def test_automatic_rewrite_rejects_changed_alignment_mark_scope(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Inspect the alignment marks before removing the pump.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check the pump alignment marks before removal.",
    "Before lifting off the pump, check the alignment marks.",
    "Check the alignment marks before taking the pump off.",
    "Check the marks for pump alignment before removal.",
])
def test_automatic_rewrite_accepts_equivalent_alignment_mark_scope(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Inspect the alignment marks before removing the pump.", in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_rewrite_preserves_an_explicit_alignment_mark_owner():
    source = document("Inspect the drive alignment marks before removing the pump.")
    faithful = response("Check the marks for drive alignment before pump removal.")
    assert run(source, faithful).error_code is None
    substitute = response("Check the pump alignment marks before removal.")
    assert run(source, substitute).error_code == "REWRITE_CLAUSE_MUTATION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "dc04b9ce04f298bb7fb6fcd2bb7d1248abb0e34a12f35ff2f2fdab07f76cc9a1",
     "d950b8e795892b3cd560f20d453b9ae3fde50f86fe4153312059797b8c8360cf",
     "f5757a9d9243fe322cd3d9ae9fb44ae8f1f2f40f8d0dec5da6008952c49400da"),
    (True, "1a1b0afbe7d4fb36116c3d3c045611057d302d4e92d726029ca13b4bc39bfcdf",
     "69d1e55cd61eb7b5775edc95dfa97fc73608e6a334da672792684e2682a2e052",
     "fc7531f1ffed44e59b547e9905e4541fda1e41e8d1e0ea57c5de5c86316a4c0f"),
])
def test_automatic_reopens_v32_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Inspect the alignment marks before removing the pump.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v32(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v32"
    payload = _scoped_prose_response(prompt, "Check the guide marks before taking the pump off.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Take the retaining clip off, then pull the wiring harness plug gently."),
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Take the retaining clip off, then pull the wiring harness plug out."),
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Take the retaining clip off, then give the battery plug a firm pull."),
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Give the wiring harness plug a firm pull, then take the retaining clip off."),
    ("Pull wiring harness plug firmly.", "Give the wiring harness plug a gentle pull."),
])
def test_automatic_rewrite_rejects_changed_harness_pull_force(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Take the retaining clip off, then give the wiring harness plug a firm pull."),
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "Take the retaining clip off. Firmly pull the plug on the wiring harness."),
    ("Remove retaining clip. Pull wiring harness plug firmly.",
     "After removing the retaining clip, give the wiring harness plug a firm pull."),
    ("Pull wiring harness plug firmly.", "Give the wiring harness plug a firm pull."),
    ("Pull wiring harness plug gently.", "Give the wiring harness plug a gentle pull."),
])
def test_automatic_rewrite_accepts_equivalent_harness_pull(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "13e3048574aab70193fb794308d585dd2e68cf2ce2d9bf2fe983e1e3af8903ae",
     "e3ff9357d6bee44a65b4d2f9cd53a1c94233b9e574512ba86353827adddf0681",
     "61a59614cb67ae2434d0ad2e2d9b74c170114e8b7085eb86e90edd9ce70f20e3"),
    (True, "a6c7ca98a20efaa28be43689db72e3b662ee0f222204b8f8f41789fb1c546208",
     "a77f52df98ce22638ba0674c0f9e7ff69e05f9872465bccba75ef1051544a732",
     "0b0b2e0f38685aba54a40c891aa2fb626971f7a798a119d2a977c55477f6c693"),
])
def test_automatic_reopens_v31_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Remove retaining clip. Pull wiring harness plug firmly.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v31(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v31"
    payload = _scoped_prose_response(prompt, "Take the retaining clip off, then pull the wiring harness plug gently.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check the brake system for any sign of leakage.",
    "Bleed the brake system and inspect it for damage.",
    "Bleed the clutch system and inspect it for leaks.",
    "Bleed the brake system and inspect the clutch system for leaks.",
    "Bleed the brake system or check it for leakage.",
])
def test_automatic_rewrite_rejects_changed_brake_bleed_and_leak_check(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Bleed the brake system and check for leaks.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_CLAUSE_MUTATION"
    assert rejected.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Purge air from the brake system, then inspect it for leakage.",
    "After bleeding the brake system, inspect it for signs of leakage.",
    "Bleed the brakes and inspect the system for leaks.",
    "Bleed the brake system, then inspect the brake system for leaks.",
])
def test_automatic_rewrite_accepts_equivalent_brake_bleed_and_leak_check(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Bleed the brake system and check for leaks.", in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_brake_rewrite_retains_explicit_order():
    source = document("Bleed the brake system, then check it for leaks.")
    assert run(source, response("Bleed the brakes and inspect the system for signs of leakage.")).error_code == "REWRITE_CLAUSE_MUTATION"
    assert run(source, response("After bleeding the brake system, inspect it for signs of leakage.")).error_code is None


def test_automatic_rewrite_leaves_a_standalone_brake_leak_check_editable():
    source = document("Inspect the brake system for leaks.")
    assert run(source, response("Check for leaks in the brake system.")).error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "dcef3090483bdad80d5bd2ac5dccc28a3240daec584f49e5578ee4a96b2049d4",
     "91feaab39ba9d81180094065686f7bac89af27b40696d8ec1271949d738b2e3f",
     "998f8e11ce22b8a8d69f66c0c71e02ff383cc3b5dd281aa6c4274237540416d5"),
    (True, "b59420aabe14f527d5685ae376bd4bd9bb2c26d61d442e99f8111d017b25b00b",
     "0ba69bd1177d88ea0318350ba641ac3efe3f23a5a62980c891f4bc27e68827d3",
     "7043b1b684d76421dc14425576d8efffde0ddd4fee9278e0c07bfe40b51e6965"),
])
def test_automatic_reopens_v30_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Bleed the brake system and check for leaks.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v30(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v30"
    payload = _scoped_prose_response(prompt, "Check the brake system for any sign of leakage.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Lift the vehicle to gain access.",
    "Lift the vehicle and support the axle.",
    "Lift the vehicle and leave it unsupported.",
    "Support the vehicle on jack stands.",
    "Support the vehicle before lifting it.",
])
def test_automatic_rewrite_rejects_changed_vehicle_support(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Raise and support the vehicle.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_CLAUSE_MUTATION"
    assert rejected.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Lift the vehicle, then support it securely.",
    "Lift and securely support the vehicle.",
    "Securely support the vehicle once it has been lifted.",
    "After lifting the vehicle, support it securely.",
])
def test_automatic_rewrite_accepts_equivalent_vehicle_support(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Raise and support the vehicle.", in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_rewrite_preserves_authored_secure_support():
    source = document("Raise and securely support the vehicle.")
    assert run(source, response("Lift the vehicle, then support it.")).error_code == "REWRITE_CLAUSE_MUTATION"
    assert run(source, response("Lift the vehicle, then support it securely.")).error_code is None


def test_automatic_rewrite_leaves_ordinary_vehicle_lift_editable():
    source = document("Lift the vehicle to gain access.")
    assert run(source, response("Raise the vehicle so the area is accessible.")).error_code is None


def test_automatic_rewrite_rejects_vehicle_support_instruction_in_introduction():
    source = document("Remove the cover.")
    payload = response("Take the cover off.", introduction="Raise and support the vehicle.")
    assert run(source, payload).error_code == "REWRITE_INTRODUCTION_INSTRUCTION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "96d45341a6b4cafcf756eb61fcf90623030d3a1e34312875698a2e48911abc45",
     "c734c4db1426c2237cad610fe49d7c9b82b2f384a085b60ecdd8c2fede09ff09",
     "e68160482fb2a5e35b77bcafc383e9c002a83e53e164a834d914a211132db47c"),
    (True, "cc0cf951c498ca7a78ddf075a8853b9dc0306dac7df3525b4206481d64ae64d4",
     "54451250d41a08f16088a8cc3687877bf53ed2ea07f8a44077b3e68edc95036f",
     "9d908b3c1ac6746d372da278a69bf92a49f43b46aebbadc0394a2b6d70d584fd"),
])
def test_automatic_reopens_v29_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Raise and support the vehicle.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v29(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v29"
    payload = _scoped_prose_response(prompt, "Lift the vehicle to gain access.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Detach the positive battery terminal.",
    "Detach the plus terminal from the battery.",
    "Detach the battery terminal to isolate the battery.",
    "Detach the negative terminal from the starter.",
])
def test_automatic_rewrite_rejects_changed_battery_terminal_polarity(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Disconnect negative battery terminal.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert rejected.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Disconnect negative battery terminal.", "Detach the minus terminal from the battery."),
    ("Disconnect negative battery terminal.", "Detach the battery’s negative terminal."),
    ("Disconnect negative battery terminal.", "Disconnect the battery at its negative terminal."),
    ("Connect the positive battery terminal.", "Attach the plus terminal to the battery."),
    ("Inspect the negative battery terminal.", "Check the negative terminal on the battery."),
])
def test_automatic_rewrite_accepts_equivalent_battery_terminal_polarity(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_rewrite_rejects_added_battery_terminal_polarity():
    source = document("Disconnect the battery terminal.")
    assert run(source, response("Detach the minus terminal from the battery.")).error_code == "REWRITE_QUALIFIER_MUTATION"
    explicit = document("Connect the positive battery terminal.")
    assert run(explicit, response("Attach the plus terminal from the battery.")).error_code == "REWRITE_QUALIFIER_MUTATION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "3d2ac1aad9e4820079baaf806221efb35aeb4743e0d63d58d2c8074985c1861a",
     "cce1965eadbf1965766b47fc096d286251a2b1bb59087407b2f162dbd8cdb619",
     "fb67a1e2f48bac9053ea5afd333eff4244fd3072f65b77b5fe92812882115cad"),
    (True, "337073bcc7070dd2676eea4d176675297b5f0038bf210d4071a99964989e57a4",
     "5de988742f47e9e01cbe177152d406aea25f9e26e441b6bbbb826c545fa27798",
     "02ef8d736c4d0d4acd3b404d2f19f0a39aa2637f3c3ab49bbec9a71f7126d4e8"),
])
def test_automatic_reopens_v28_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Disconnect negative battery terminal.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v28(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v28"
    payload = _scoped_prose_response(prompt, "Detach the positive battery terminal.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Open the line before releasing pressure from the brake system.",
    "Pressurize the brake system before opening the line.",
    "Open the line after releasing pressure from the clutch system.",
    "Release pressure from the brake system and open the line.",
    "Open the line for access.",
])
def test_automatic_rewrite_rejects_changed_pressure_release_order(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Depressurize the brake system before opening the line.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_CLAUSE_MUTATION"
    assert rejected.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Open the line after relieving pressure in the brake system.",
    "Open the line once the pressure has been released from the brake system.",
    "Before opening the line, release pressure from the brake system.",
    "Depressurise the brake system, then open the line.",
])
def test_automatic_rewrite_accepts_equivalent_pressure_release_order(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Depressurize the brake system before opening the line.", in_cell=in_cell)
    payload = _scoped_prose_response(auto.build_auto_prompt(source, context={}), draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "8d7e99ceb6e6787ce84ef79f831b9ca6bbb6aae8e3d4109f563aa1d5c87c76e2",
     "c8ed12bd8f3d91d08175a2787dc13bbb57f37c9603f799585d15be1a894f8763",
     "56bd5f5bcd10b6263f2a5007f7a5d58b82854ac59995e03047b04e7f9adbb79b"),
    (True, "12a13387c97e4577a7b96329dc8fa74cc3a53d6ab97ce9faaa57ef289fba1647",
     "3db47e4f083b0936b6e96671ddf213fb0528f66c02644f0c526860dce233cadb",
     "07258d4cce58b334511f6acec1c7e6139bda3e156fccd68b59cecccb897f2144"),
])
def test_automatic_reopens_v27_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Depressurize the brake system before opening the line.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v27(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v27"
    payload = _scoped_prose_response(prompt, "Open the line before releasing pressure from the brake system.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Open the line while the brake system is depressurized.", "With the brake system pressurized, open the line."),
    ("Remove the line while the brake system is depressurized.", "With the clutch system depressurized, take the line off."),
    ("Remove the line while the brake system is depressurized.", "Take the line off for access."),
    ("Remove the line when the brake system is depressurized.", "When the brake system is pressurized, take the line off."),
    ("Remove the line after the brake system is depressurized.", "Take the line off before the brake system is depressurized."),
    ("Remove the line while the brake system is depressurized and the ignition is off.",
     "With the brake system pressurized and the ignition off, take the line off."),
])
def test_automatic_rewrite_rejects_changed_pressure_prerequisite(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert rejected.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Open the line while the brake system is depressurized.", "With the brake system depressurised, open the line."),
    ("Remove the line when the brake system is depressurized.", "Take the line off when the brake system is depressurized."),
    ("Remove the line after the brake system is depressurized.", "Once the brake system is depressurized, take the line off."),
    ("Remove the line while the brake system is depressurized and the ignition is off.",
     "With the ignition switched off and the brake system depressurized, take the line off."),
    ("Inspect the pressurized line.", "Check the pressurized line."),
])
def test_automatic_rewrite_accepts_equivalent_pressure_prerequisite(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_rewrite_rejects_unsupported_pressure_in_introduction():
    source = document("Remove the line.")
    payload = response(
        "Take the line off.", introduction="This procedure takes place when the brake system is pressurized.",
    )
    assert run(source, payload).error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "22be8c46a5acec598ec03335ff4f79aacda91a89e52f447cc13252d6f50e77c6",
     "adbd733c80a4d723e162814e967eb3bc84cc05148fb8e71f187b9c6e44020357",
     "927805a5a7134f42a3d5034a88448165cbe149816e96159246665d6178440415"),
    (True, "b968569b6fe1d55ca98107f2bbb8594647b2d709bacd28211de3f5c913469d64",
     "57aac72353dd65ceab6b30e661cc9febab08e56a4b25175aa1695ed7f0729813",
     "9e964836ee24bd47036d69d6adde1b309b3709f8cc73226cdfd67cfd4a044baa"),
])
def test_automatic_reopens_v26_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Remove the line while the brake system is depressurized.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v26(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v26"
    payload = _scoped_prose_response(prompt, "With the brake system pressurized, take the line off.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "With the ignition on and the flange wet, fit the seal into place.",
    "With the ignition off, fit the seal into place.",
    "With the ignition off or the flange dry, fit the seal into place.",
    "With the flange dry and the pump off, fit the seal into place.",
    "With the ignition off and the flange dry, fit the gasket into place.",
])
def test_automatic_rewrite_rejects_changed_conjunctive_simultaneous_conditions(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    original = "Install the seal while the ignition is off and the flange is dry."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "With the flange dry and the ignition switched off, fit the seal into place.",
    "Fit the seal while the flange is dry and the ignition is off.",
])
def test_automatic_rewrite_accepts_equivalent_conjunctive_simultaneous_conditions(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Install the seal while the ignition is off and the flange is dry.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


def test_automatic_rewrite_rejects_an_added_conjunctive_simultaneous_condition():
    source = document("Install the seal.")
    payload = response("With the ignition off and the flange dry, fit the seal into place.")
    assert run(source, payload).error_code == "REWRITE_QUALIFIER_MUTATION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "07eacf1eb8e108efcfc7fbef294b77cb0ba9bfc04ce10517922f1938bb246ff9",
     "3c9e136ac0139aed193d5a61627a891604fc67971b0646dc2e93e6a3b5dec7cc",
     "ce83b3833d2af5b9f9d70e29f05223051edc6d653d003c22b3371ec07421fb18"),
    (True, "1a19e18136e6446547ff149c16dca24212e4450f0cd9545d2da32f1a58e421a1",
     "4b2b844970fba654ca02f708d55f7f50264e7e264aa0c642800296abf3f92be7",
     "f2275c09f10963f30f61fed31f8e4637621be92e62a4f8d150ecc490ca437cbb"),
])
def test_automatic_reopens_v25_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Install the seal while the ignition is off and the flange is dry.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v25(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v25"
    payload = _scoped_prose_response(prompt, "With the ignition on and the flange wet, fit the seal into place.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover while the ignition is off.", "With the ignition off, take the cover off."),
    ("Remove the cover while the ignition is off.", "Take the cover off with the ignition switched off."),
    ("Remove the cover while the ignition is off.", "With the ignition off, take the cover off for access."),
    ("With the flange dry, install the gasket.", "Fit the gasket while the flange is dry."),
    ("Inspect the cover with a puller.", "Using a puller, check the cover."),
    ("While accessing the seal, remove the cover.", "Take the cover off to reach the seal."),
])
def test_automatic_rewrite_v12_preserves_same_state_and_existing_aliases(in_cell, source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    validation = auto.validate_auto(source, result.document, response=payload, prompt_version=version)
    assert validation.passed
    assert validation.report["validator_version"] == "full-prose-auto-validator-v53"


def test_automatic_rewrite_v12_rejects_added_condition_in_the_introduction():
    source = document("Remove the cover.")
    payload = response("Take the cover off.", introduction="The procedure is done while the ignition is on.")
    assert run(source, payload).error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "7f1b204ed2b850eb75bb6d2c82a2cea4026c249c99b7e06d06f53ce307ba2c00",
     "8b2cb315ab8f02c39758e44162e00a904dfb27ae5efb4c3e944faad181da84bb",
     "a6ab6beddcf7c98817929957f0561b9aae640cb7e9e86887c78806ab73c119ba"),
    (True, "036a9678db299ff592f8acc97d7b96159d9eba585364b47859edd383abebcdee",
     "df8b63713c517590e7a666fc3cff64d1518b76f0c65fd54eb5b37a498386d57c",
     "4f14669df13baeb023da1ae5a16d7362e655cf2b3f23f0582be05d2ff9bd1d7a"),
])
def test_automatic_reopens_v10_and_v11_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Remove the cover while the ignition is off.", in_cell=in_cell)
    context = {"make": "Fixture"}
    builder = auto._build_auto_prompt_v11 if in_cell else auto._build_auto_prompt_v10
    prompt = builder(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == ("full-prose-auto-prompt-v11" if in_cell else "full-prose-auto-prompt-v10")
    payload = _scoped_prose_response(prompt, "Take the cover off while the ignition is on.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("draft", [
    "Check connector C-17 for signs of wear.",
    "Check connector C-17.",
    "Carefully check connector C-17.",
    "Check sensor C-17 for signs of corrosion.",
    "Check connector C-17 for corrosion or wear.",
])
def test_automatic_rewrite_rejects_changed_identified_inspection(in_cell, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source("Inspect connector C-17 for corrosion.", in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft", [
    ("Inspect connector C-17 for corrosion.", "Check the C-17 connector for signs of corrosion."),
    ("Inspect hose AB.17 for leakage.", "Check the AB.17 hose for leaks."),
    ("Inspect mounting bracket RX/3 for cracks.", "Check mounting bracket RX/3 for signs of cracking."),
    ("Inspect connector C-17.", "Check the C-17 connector."),
    ("Inspect the seal near connector C-17.", "Check the seal around connector C-17."),
])
def test_automatic_rewrite_accepts_identified_inspection_aliases(in_cell, source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    checked = auto.validate_auto(source, result.document, response=payload, prompt_version=version)
    assert checked.passed
    assert checked.report["validator_version"] == "full-prose-auto-validator-v53"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "c8131c60f60d68377560caa64612b3a5d1267d518559cf332c9c04addc337459",
     "1abd0c319ed4425569839c40763f97ccb8082c34e0bc0de3737f205a602b6377",
     "1de8d473ba03155c620474ad6b54eaf0759c96dcd97d4be6c05446ae222ab8bf"),
    (True, "edde1cc2e0f05b13062ded040c66f5070325cb98f4f5327e992a6f3bcf0410ba",
     "98bf12c788ff3f03cbbb5c5e12fe87e2a815089d841fdbffccc41d551b6c4a76",
     "faa24491be45bb23791943138839dba48d6166b4f583a03d9613dcc31fe86c8a"),
])
def test_automatic_reopens_v12_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Inspect connector C-17 for corrosion.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v12(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v12"
    payload = _scoped_prose_response(prompt, "Check connector C-17 for signs of wear.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft,expected", [
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 connector for signs of corrosion.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 connector for corrosion and wear.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 connector for corrosion or cracking.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 sensor for signs of cracking and corrosion.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 connector for cracking, corrosion, and leaks.", "REWRITE_QUALIFIER_MUTATION"),
    ("Check hose AB.17 for wear, leakage, and cracks.",
     "Inspect the AB.17 hose for cracks and leaks.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect bracket RX/3 for either damage or cracking.",
     "Check the RX/3 bracket for cracks and signs of damage.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check the C-17 connector for both signs of cracking and evidence of corrosion.", None),
    ("Inspect connector C-17 for corrosion and cracks.",
     "Check for cracks and corrosion on connector C-17.", None),
    ("Check hose AB.17 for wear, leakage, and cracks.",
     "Inspect the AB.17 hose for cracks, signs of wear and leaks.", None),
    ("Inspect bracket RX/3 for either damage or cracking.",
     "Check the RX/3 bracket for cracks or signs of damage.", None),
    ("Inspect connector C-17 for corrosion and cracks in the housing.",
     "Check connector C-17 for cracks in the housing and corrosion.", None),
])
def test_identified_inspection_preserves_the_complete_defect_list(in_cell, source_text, draft, expected):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == expected
    if expected:
        assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ((expected,) if expected else ())


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "0c301fbcbad6a6e04c219551944c609fd68d78aba3f3310ff6a297d4bb9adf90",
     "38daa95963ca6e881330dfe0dce32d3756b18b6c9f882e4a279d5078917a105e",
     "6c54acffe9478bb211bcbce814f98d0fe63d170f7f7bf7560c82f5cb2c221a4d"),
    (True, "099c247a826abf8daef1b6abebc7e7d735a310024d0ee69bfaf24157ebbe1992",
     "96f1e5f72490a1a124cb4fc8d5081a7eb7129e95c1148038f6ced7cfa4ae694a",
     "2ec82f21aa0302fe823eff9a569f0177df586b0a7065e89ef6687f51115a0699"),
])
def test_automatic_reopens_v13_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Inspect connector C-17 for corrosion and cracks.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v13(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v13"
    payload = _scoped_prose_response(prompt, "Check the C-17 connector for signs of corrosion.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft,expected", [
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach either the battery cable or the pump connector.", "REWRITE_CLAUSE_MUTATION"),
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach the battery cable.", "REWRITE_CLAUSE_MUTATION"),
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach the battery cable or detach the battery cable.", "REWRITE_CLAUSE_MUTATION"),
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach the service plug and detach the battery cable.", "REWRITE_CLAUSE_MUTATION"),
    ("Either remove the fuse or disconnect the battery cable.",
     "Take the fuse off or detach the pump connector.", "REWRITE_CLAUSE_MUTATION"),
    ("Either disconnect the left battery cable or remove the rear cover.",
     "Take the front cover off or detach the left battery cable.", "REWRITE_CLAUSE_MUTATION"),
    ("Inspect either the battery cable or the service plug.",
     "Carefully check the service plug or check the pump connector.", "REWRITE_CLAUSE_MUTATION"),
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach either the service plug or the battery cable.", None),
    ("Either disconnect the battery cable or disconnect the service plug.",
     "Detach the service plug, or detach the battery cable instead.", None),
    ("Either remove the fuse or disconnect the battery cable.",
     "Detach the battery cable or take the fuse off.", None),
    ("Either disconnect the left battery cable or remove the rear cover.",
     "Take the rear cover off or detach the left battery cable.", None),
    ("Inspect the cover and inspect the shield.", "Check the shield and check the cover.", None),
    ("Inspect the seal, then inspect the cover.", "After checking the seal, check the cover.", None),
])
def test_automatic_rewrite_preserves_bound_alternative_actions(in_cell, source_text, draft, expected):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == expected
    if expected:
        assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ((expected,) if expected else ())
    assert checked.report["validator_version"] == "full-prose-auto-validator-v53"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "ac73f4c74810a4fddef64626e9c78faabc0bce4d46a11e86cbfb85be16ef4b93",
     "5603a7753afec6b47dcda10319f892a8c24b81c05b1f6ceb208b26901dfbed66",
     "45813533d9dc7670abd3d6d16dc9974b2744b975da861057ecc216e756258752"),
    (True, "9dae6d605cea9a7cb5cd0a3d36980f1c9e32e3f04510436639f84bb9fc4b45e0",
     "27a7d561ad50fe5326f51afe3ab18830bb994f17f8b73b87c39fa52f482b89b9",
     "113991d182f8648c51e4ff1084ec4459fc07f474ca7cbb10c424da0e86df0ca4"),
])
def test_automatic_reopens_v14_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(
        "Either disconnect the battery cable or disconnect the service plug.", in_cell=in_cell,
    )
    prompt = auto._build_auto_prompt_v14(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v14"
    payload = _scoped_prose_response(prompt, "Detach either the battery cable or the pump connector.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("source_text,draft,expected", [
    ("Disconnect the battery cable before removing the fuse.",
     "Detach the battery cable and take the fuse off.", "REWRITE_CLAUSE_MUTATION"),
    ("Disconnect the battery cable before removing the fuse.",
     "Detach the battery cable, and take the fuse off.", "REWRITE_CLAUSE_MUTATION"),
    ("After removing the retaining pin, remove the bracket.",
     "Lift off the bracket and take the retaining pin off.", "REWRITE_CLAUSE_MUTATION"),
    ("After removing the retaining pin, remove the bracket.",
     "Lift off the bracket. Take the retaining pin off.", "REWRITE_CLAUSE_MUTATION"),
    ("Remove the inlet cover, then remove the cable shield.",
     "Lift off the cable shield and take the inlet cover off.", "REWRITE_CLAUSE_MUTATION"),
    ("Disconnect the battery cable before removing the fuse.",
     "Take the fuse off after detaching the battery cable.", None),
    ("Disconnect the battery cable before removing the fuse.",
     "Before taking off the fuse, detach the battery cable.", None),
    ("Disconnect the battery cable before removing the fuse.",
     "Detach the battery cable first, and then take the fuse off.", None),
    ("Disconnect the battery cable before removing the fuse.",
     "First, detach the battery cable and next take the fuse off.", None),
    ("Disconnect the battery cable before removing the fuse.",
     "Detach the battery cable. Take the fuse off.", None),
    ("Remove the inlet cover, then remove the cable shield.",
     "Take the cable shield off after lifting off the inlet cover.", None),
    ("Inspect the cover and inspect the shield.", "Check the shield and check the cover.", None),
    ("Disconnect the pump lead before removing the inlet cover.",
     "Once the pump lead is detached, lift off the inlet cover.", None),
])
def test_automatic_rewrite_preserves_bound_instruction_order(in_cell, source_text, draft, expected):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == expected
    if expected:
        assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ((expected,) if expected else ())
    assert checked.report["validator_version"] == "full-prose-auto-validator-v53"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "f99d7df33e80fd28360aa4eedbc959327542ced9a01f2967d25eb8be7b261fd8",
     "38f5e916458c636e790710bc3c108ecf2ec8fb1417290eb13320ec341cfc78ea",
     "8f448c8e82d12176c344f5771dcd57ec04340b5b2b2a6b93c9de7c21cea11086"),
    (True, "7d9bfd547cbb74dc4a204fd2e0e3b22537318e508d71f4778fd64859d8566d2b",
     "c2b08c57f7527add84332d22584361f17c13c076ddb84804a813dff97b0c99e7",
     "3aff77e36862297cb40b43709d49c965cb606142a139d6c9ef94d646b69d1740"),
])
def test_automatic_reopens_v15_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Disconnect the battery cable before removing the fuse.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v15(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v15"
    payload = _scoped_prose_response(prompt, "Detach the battery cable and take the fuse off.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["N-m", "N–m", "N⋅m", "N·M", "nm", "ft-lbs", "ft/lbs", "lb. ft.", "lbs-ft", "lb ft", "in·lb"])
def test_automatic_rewrite_keeps_torque_assignments_across_unit_spellings(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    end = "" if unit.endswith(".") else "."
    source_text = f"Tighten the cover bolts to 18 {unit} and the bracket bolts to 25 {unit}{end}"
    draft = f"Torque the bracket bolts to 18 {unit} and the cover bolts to 25 {unit}{end}"
    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    changed = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, changed, response=payload, prompt_version="full-prose-auto-prompt-v52")
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=source_text, reason="Preserve the exact torque values.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("source_text,draft", [
    ("Tighten the cover bolts to a maximum of 18 N-m.", "Torque the cover bolts to a minimum of 18 N-m."),
    ("Tighten the cover bolts from 16 to 20 N-m.", "Torque the bracket bolts within 16 to 20 N-m."),
    ("Tighten the cover bolts to 16-20 N-m.", "Torque the bracket bolts to 16-20 N-m."),
    ("Tighten the cover bolts to 18 N⋅m.", "Torque the cover bolts to 18 N–m."),
])
def test_automatic_rewrite_keeps_torque_bounds_and_unit_typography(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("The coating is 18 nm thick.", "The film has a thickness of 18 nm."),
    ("Remove the 2 guide clips.", "Take off the 2 guide clips."),
    ("Inspect connector NM-17.", "Check connector NM-17 for wear."),
])
def test_automatic_rewrite_keeps_unrelated_text_editable_with_torque_aliases(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(source_text)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    result = run(source, response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "ba4de05aca3f82f9e85695d78ecdd8c20ae4af3154f656a0f25009d70ae0442a",
     "f55eedad6fe828e32e01b16dcdd4a4bc5ee9ee773d5bb42178601e9fc40e5885",
     "61abac00e2efd0b11ca10786a721c60e2c13695924d4eb932c7d41dbb1449b38"),
    (True, "651220a51111893440b219efe20efa9c8f0fbe85647e1db84b7c2eee4b0de5f9",
     "cf8f2e33f4653165d88b70ecf0057fe361ba4ee52a6181d37db648ee6eefae65",
     "c9b833dc07176c9a15c29072cb4904c0428b1d27e3ffa9ffc49c6494cc39b7cc"),
])
def test_automatic_reopens_v16_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source_text = "Tighten the cover bolts to 18 N-m and the bracket bolts to 25 N-m."
    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v16(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v16"
    payload = _scoped_prose_response(prompt, "Torque the bracket bolts to 18 N-m and the cover bolts to 25 N-m.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["milliseconds", "ms", "msec", "seconds", "sec", "s", "minutes", "min", "hours", "hrs", "h"])
def test_automatic_rewrite_keeps_measured_duration_assignments(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source_text = f"Hold the reset button for 5 {unit} and the mode button for 10 {unit}."
    draft = f"Press and hold the mode button for 5 {unit} and the reset button for 10 {unit}."
    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=source_text, reason="Preserve both timing assignments.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("source_text,draft", [
    ("Hold the reset button for a minimum of 5 seconds.", "Keep the reset button depressed for a maximum of 5 seconds."),
    ("Allow 5 minutes for the inlet circuit and 20 minutes for the outlet circuit to discharge.",
     "Give the outlet circuit 5 minutes and the inlet circuit 20 minutes to discharge."),
])
def test_automatic_rewrite_keeps_duration_limits_and_discharge_targets(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("The sensor conductance is 3 mS.", "The reading for conductance is 3 mS."),
    ("The cable length is 5 m.", "The cable measures 5 m in length."),
    ("Hold the reset button for the second chime.", "Keep the reset button pressed until the second chime."),
    ("Remove the 2 guide clips.", "Take off the 2 guide clips."),
    ("Inspect connector MS-17.", "Check connector MS-17 for wear."),
])
def test_automatic_rewrite_leaves_non_duration_prose_editable(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(source_text)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


def test_automatic_rewrite_keeps_measured_duration_out_of_introduction():
    duration = "Hold the reset button for 5 seconds."
    source = document("Remove the retaining clip.", duration)
    payload = response("Take the retaining clip off.", duration,
                       introduction="This procedure takes 5 seconds.")
    payload["replacements"][1].update(action="retain", reason="Preserve the exact duration.")
    assert run(source, payload).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "f41a3786f91b6df7ef546d30dcfcb112efa30908846caed92a79fd8a24d5dcc1",
     "840a258bd90a9d93a82f6f459dc4ed1573c08c905a3e53576d11cd8dcf7888e5",
     "ed289ce07e19aa7f0c6a4bf6e03645438d354d062a126306dc3276db8bce0e2a"),
    (True, "036d1832995b4b472c2c5b1940b4400fbf9b28efd67753ebb8631cf6c885d7d7",
     "b099fccd42d21f8d701a731e91a80620cc20cb221cf2b00dfb79807d9264d9f6",
     "43604b3da7c4e165fc10fefe1e00cc2db17dce911e8fbaad4faec16f09a9af8e"),
])
def test_automatic_reopens_v17_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Hold the reset button for 5 seconds and the mode button for 10 seconds."
    draft = "Press and hold the mode button for 5 seconds and the reset button for 10 seconds."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v17(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v17"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["VDC", "VAC", "Vdc", "V-DC", "V.D.C.", "mVDC", "ADC", "mA", "mV", "µA", "μA", "kV"])
def test_automatic_rewrite_keeps_labelled_voltage_and_current_values(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source_text = f"Apply 5 {unit} to the sensor signal pin and 12 {unit} to the supply pin."
    end = "" if unit.endswith(".") else "."
    draft = f"Feed the supply pin with 5 {unit} and the sensor signal pin with 12 {unit}{end}"
    source = _scoped_prose_source(source_text, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=source_text, reason="Preserve both electrical values.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("original,draft", [
    ("The sensor signal must be below 5 VDC.", "The signal from the sensor must be above 5 VDC."),
    ("The signal voltage is 5 VDC maximum.", "The sensor signal is rated at 5 VDC minimum."),
    ("Apply 5 V.D.C. to the sensor pin.", "Feed the sensor pin with 5 V.A.C."),
    ("Connect the 12 VDC supply to the motor and the 5 VDC supply to the controller.",
     "Attach the 12 VDC supply to the controller and the 5 VDC supply to the motor."),
    ("Apply at least 5 VDC nominal at the sensor signal pin.", "Feed the power pin at least 5 VDC nominal."),
])
def test_automatic_rewrite_keeps_electrical_limits_modes_and_supply_targets(original, draft):
    source = document(original)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("original,draft", [
    ("Install the 2 VDC modules.", "Fit the 2 VDC modules into place."),
    ("Install the 5 ADC channels.", "Fit the 5 ADC channels into place."),
    ("Inspect connector VDC-17.", "Check connector VDC-17 for wear."),
    ("The adapter has 12 A-series clips.", "There are 12 A-series clips on the adapter."),
])
def test_automatic_rewrite_keeps_component_names_and_counts_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "e5e0d3bec0b239270a47911a50a60a09728842a9d6acfb0d543f3fd5d948a48c",
     "cffb80b5c1d16f6ab9e31c8abcc3d227c4778f674e49a11570942bb902bc1833",
     "1200ef71b7bb1fb001a80ce1a18cc1833d4267c783105ef9f1f3b92242e639e7"),
    (True, "77bedb5982f8326b0b8f07dc7f3830d61a64df44bd6d87597d6f4c9450bed6a2",
     "5444000220eb78bef8c286d0bcbd9df850c9249318bf31e147359e9691c67b34",
     "6c9f8594187dbb8845e5e514014580935b474dabea7ac95a5eaaa703082397b7"),
])
def test_automatic_reopens_v18_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Apply 5 VDC to the sensor signal pin and 12 VDC to the supply pin."
    draft = "Feed the supply pin with 5 VDC and the sensor signal pin with 12 VDC."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v18(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v18"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["PSI", "psig", "PSIG", "psia", "PSIA", "KPA", "MPA", "BAR", "inHg", "mmHg", "Pa", "hPa", "lb/in2"])
def test_automatic_rewrite_keeps_pressure_assignments(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    original = f"Set the inlet pressure to 18 {unit} and the outlet pressure to 25 {unit}."
    draft = f"Adjust the outlet pressure to 18 {unit} and the inlet pressure to 25 {unit}."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Preserve the pressure assignments.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("original,draft", [
    ("The fuel rail pressure is 45 PSIG maximum.", "The fuel rail pressure is rated at 45 PSIG minimum."),
    ("The low-pressure port reads 30 p.s.i. under load.", "Under load, the high-pressure port reads 30 p.s.i."),
    ("Run the inlet at 18 PSI.", "Maintain the outlet at 18 PSI."),
])
def test_automatic_rewrite_keeps_pressure_targets_and_limits(original, draft):
    source = document(original)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("original,draft", [
    ("Inspect the 5 PSI-rated fittings.", "Check the 5 PSI-rated fittings for damage."),
    ("Inspect connector PSI-17.", "Check connector PSI-17 for wear."),
    ("Install the 3 BAR series clips.", "Fit the 3 BAR series clips into place."),
])
def test_automatic_rewrite_leaves_pressure_like_labels_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "5fd26efbf9c37b6424d581918e792c471928016fe660d0885b7a4dae8dde8cc4",
     "498ffd0203698fdf5999f5801680ee6a66fa7edcf94b13f596853b054ff4d552",
     "2adec5cb8e217a5d9d056b1e32e06e29c0b050537fa9adaf2e27dac6bf2b1af4"),
    (True, "2e08d1b7035813875d1dad1bff8d6b22986747d5356cd62bd1bb4cfb41dff773",
     "dc0e5c3b157e526ba066b06572fdcbda5753ee309df45b40d856e00b380ec0c0",
     "8d0c4f6c32a435800edd7e272fffd0b0e73eee6eb7cda74035bf67250967ea34"),
])
def test_automatic_reopens_v19_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Set the inlet pressure to 18 PSI and the outlet pressure to 25 PSI."
    draft = "Adjust the outlet pressure to 18 PSI and the inlet pressure to 25 PSI."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v19(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v19"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["deg C", "deg F", "deg.C", "deg. F", "degree C", "degrees F", "degree-C", "℃", "℉", "Celsius", "Fahrenheit"])
def test_automatic_rewrite_keeps_temperature_assignments(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    original = f"Set the intake sensor to 18 {unit} and the outlet sensor to 25 {unit}."
    draft = f"Use 18 {unit} as the outlet sensor setting and 25 {unit} as the intake sensor setting."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Preserve the temperature assignments.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("original,draft", [
    ("The seal temperature is 60 degrees F maximum.", "The seal temperature is rated at 60 degrees F minimum."),
    ("Heat the seal to 80 deg. C.", "Heat the seal holder to 80 deg. C."),
    ("The connector temperature is 60 ℃ maximum.", "The connector temperature is rated at 60 ℉ maximum."),
])
def test_automatic_rewrite_preserves_temperature_targets_limits_and_scale(original, draft):
    source = document(original)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("original,draft", [
    ("Install the 3 C grade inserts.", "Fit the 3 C grade inserts into place."),
    ("Inspect connector DEG-C17.", "Check connector DEG-C17 for wear."),
    ("Install the 2 temperature sensors.", "Fit the 2 temperature sensors into place."),
    ("The gauge shows 90 degrees on its display.", "A reading of 90 degrees appears on the gauge."),
])
def test_automatic_rewrite_leaves_unrelated_temperature_like_prose_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "a323b2c24bf68a8cbef547bf9969beab3efc1e59158987e7fef3141a73b77b6a",
     "0ae0b183aae3e90ec2d5272a36d2e6fc66c7147b92dfb89ac5083b33ebfc3d9f",
     "38e6287ec868950961fb0557ec463a053794e6095b51d86eaa36ecbcc2881b49"),
    (True, "ecef404339a0f06ac9a51870c228431f6764e376a61df1cd973db0e2d87c3a36",
     "17c0bc4d0261b09edc9d4866aa8428c8390d6bbb32fce9fee8ed879a38d70317",
     "16f03677f2774470b51b32491d63e9f8e97b4602ecbd8bea1ed067abf0d21046"),
])
def test_automatic_reopens_v20_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Set the intake sensor to 18 deg C and the outlet sensor to 25 deg C."
    draft = "Use 18 deg C as the outlet sensor setting and 25 deg C as the intake sensor setting."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v20(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v20"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("unit", ["mΩ", "kΩ", "MΩ", "µΩ", "μΩ", "kΩ", "kOhms", "k ohms", "kilo-ohms", "megohms", "milliohms", "micro-ohms"])
def test_automatic_rewrite_keeps_resistance_assignments(in_cell, unit):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    original = f"The heater winding is specified at 3 {unit} and the sensor winding at 8 {unit}."
    draft = f"Use 3 {unit} as the sensor winding target and 8 {unit} as the heater winding target."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    assert version == "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Preserve the resistance assignments.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@pytest.mark.parametrize("original,draft", [
    ("The heater winding resistance is 3–5 kΩ and the sensor winding resistance is 8–12 kΩ.",
     "Use 3–5 kΩ as the sensor winding range and 8–12 kΩ as the heater winding range."),
    ("The intake temperature sensor resistance is 2 to 4 kΩ.", "The outlet temperature sensor measures 2 to 4 kΩ."),
    ("The return circuit resistance is 50 mΩ maximum.", "The resistance of the return circuit is normally 50 mΩ minimum."),
])
def test_automatic_rewrite_keeps_resistance_ranges_targets_and_limits(original, draft):
    source = document(original)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("original,draft", [
    ("Inspect connector KOHM-17.", "Check connector KOHM-17 for wear."),
    ("Inspect the 3 M-series clips.", "Check the 3 M-series clips for damage."),
    ("The sensor conductance is 3 mS.", "The reading for conductance is 3 mS."),
    ("The harness uses an 80 kΩ-rated resistor.", "The 80 kΩ-rated resistor belongs in the harness."),
])
def test_automatic_rewrite_leaves_resistance_like_labels_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "c0a9c04ba0cca645ed8d7e87864664e22fc3de7fa60de7180ad24ff6ee2afb9f",
     "404ada334c63c8dfbd0d20b53737fcd29741ec45d273b02d0742e06a0be11b69",
     "511c4811c458418406aa25ff9a4f51e085b292e93e19ec8907f7f85bfa06cb0b"),
    (True, "a9f636e613df384d11b56525f25ff9c0816d6e93edf8e974f9326cc4f426d11d",
     "d521b0363a4905a7c5338b7cff95a034d81dcfae78754cde3014a3bea031ad62",
     "7e5d43171b10d009c50d5e1629f24afb7659df47135d88a070946343b68f9125"),
])
def test_automatic_reopens_v21_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "The heater winding resistance is 3 to 5 kOhms and the sensor winding resistance is 8 to 12 kOhms."
    draft = "Use 3 to 5 kOhms as the sensor winding range and 8 to 12 kOhms as the heater winding range."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v21(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v21"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Remove the inlet cover, then remove the cable shield.", "Take the inlet cover off."),
    ("Remove the inlet cover, then remove the cable shield.", "Lift off the cable shield."),
    ("Inspect the seal before inspecting the cover.", "Check the seal."),
    ("Inspect the seal before inspecting the cover.", "Check the cover."),
])
def test_automatic_rewrite_keeps_both_distinct_ordered_actions(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    version = json.loads(prompt)["prompt_version"]
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Remove the inlet cover, then remove the cable shield.", "Take the cable shield off after lifting off the inlet cover."),
    ("Remove the inlet cover, then remove the cable shield.", "After the inlet cover has been removed, take the cable shield off."),
    ("Remove the inlet cover, then remove the cable shield.", "Take the inlet cover off. Then lift off the cable shield."),
    ("Inspect the seal before inspecting the cover.", "Check the cover after checking the seal."),
    ("Inspect the seal before inspecting the cover.", "Check the seal for wear before inspecting the cover."),
    ("Remove the inlet cover.", "Take the inlet cover off."),
])
def test_automatic_rewrite_keeps_ordered_instruction_paraphrases_editable(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    parsed = json.loads(prompt)
    assert parsed["prompt_version"] == "full-prose-auto-prompt-v55"
    assert parsed["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]
    assert checked.report["retained_paths"] == []


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "527d5f6a1b5981f1e9e0fc2b8c211c8cf0048520e865121874842ac20958403d",
     "31ae44e01aa064fb444da3a7b2ba78b53c9d628d3f5f77ad4fcbd669eaa01e68",
     "c61340bbb5cf6b8a4fe113983dd5d01572daabca927ddf0514ae1f159e2601c7"),
    (True, "429313bd0027711bc30899a80379bdf4a4a40978fac3d713e4592cfcf2134176",
     "b3918a8e618f58ef58b8bd36256e4e5d4abc2329bdc027cfd54e82caa1191647",
     "0ca275fabe2e272c6d1f0470b837ff760b837e520be7879c2160a94f263c5cce"),
])
def test_automatic_reopens_v22_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Remove the inlet cover, then remove the cable shield."
    draft = "Take the inlet cover off."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v22(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v22"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_CLAUSE_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Keep your hands clear of the moving fan.", "Keep your hands close to the moving fan."),
    ("Keep your hands clear of the moving fan.", "Keep your hands away from the moving fan."),
    ("Keep the cable away from the pulley.", "Guide the cable toward the pulley."),
    ("Stay clear of the rotating shaft.", "Stand beside the rotating shaft."),
    ("Check the cable; keep the cable away from the pulley.", "Inspect the cable; place it next to the pulley."),
])
def test_automatic_rewrite_retains_explicit_clearance_warnings(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.article_document import project_ordered_document
    from autodata_ingestion.procedure_rewrite_full import _get, render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    parsed = json.loads(prompt)
    version = parsed["prompt_version"]
    slot = parsed["slots"][-1]
    assert version == "full-prose-auto-prompt-v55"
    assert slot["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SAFETY_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_SAFETY_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Preserve the source warning.")
    retained = run(source, payload)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=payload)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [slot["path"]]
    projected = project_ordered_document(retained.document)
    assert original in projected["body"]
    assert "Take the retaining clip off." in projected["body"]
    parent = slot["path"].removesuffix("/text")
    original_warning = _get(source, parent)
    retained_warning = _get({"blocks": retained.document["blocks"][1:]}, parent)
    assert retained_warning["text"] == original_warning["text"]
    assert retained_warning["evidence_ids"] == original_warning["evidence_ids"]


@pytest.mark.parametrize("original,draft", [
    ("Route the cable through the guide channel.", "Feed the cable along the guide channel."),
    ("The cable is routed away from the pulley.", "The cable follows a path apart from the pulley."),
    ("Keep the cover aligned with the guide.", "Maintain the cover's alignment with the guide."),
])
def test_automatic_rewrite_leaves_non_warning_placement_prose_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


def test_automatic_rewrite_cannot_add_a_clearance_warning_to_the_introduction():
    source = document("Remove the retaining clip.")
    payload = response("Take the retaining clip off.", introduction="Stay clear of the rotating shaft.")
    assert run(source, payload).error_code == "REWRITE_SAFETY_MUTATION"


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    ("Turn the adjuster 1.5 turns clockwise.", "Give the adjuster 1.5 turns counterclockwise."),
    ("Turn the adjuster 1.5 turns clockwise.", "Give the locknut 1.5 turns clockwise."),
    ("Rotate the camshaft 90 degrees clockwise.", "Move the crankshaft through 90 degrees counterclockwise."),
    ("Rotate the camshaft by a maximum of 90 degrees.", "Move the camshaft by at least 90 degrees."),
    ("Turn the adjuster 1/2 turn.", "Give the locknut 1/2 turn."),
    ("Rotate the cam 45 degrees clockwise.", "Turn the cam clockwise through 45 degrees."),
])
def test_automatic_rewrite_retains_measured_rotation_scope(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.article_document import project_ordered_document
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    parsed = json.loads(prompt)
    slot = parsed["slots"][-1]
    payload = _scoped_prose_response(prompt, draft)
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert rejected.document == source
    assert slot["required_action"] == "retain"
    unchecked = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, unchecked, response=payload, prompt_version=parsed["prompt_version"])
    assert checked.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Exact rotation specification.")
    result = run(source, payload)
    assert result.error_code is None
    projected = project_ordered_document(result.document)
    assert original in projected["body"]
    assert "Take the retaining clip off." in projected["body"]
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.report["retained_paths"] == [slot["path"]]
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]


_QUALITATIVE_ROTATION = "Rotate the adjuster clockwise until the guide slots align."
_QUALITATIVE_ROTATION_RESTATEMENT = "Bring the guide slots into alignment by turning the adjuster clockwise."
_REVERSED_QUALITATIVE_ROTATION = (
    "Bring the guide slots into alignment by turning the adjuster counterclockwise."
)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_QUALITATIVE_ROTATION, _REVERSED_QUALITATIVE_ROTATION),
    (_QUALITATIVE_ROTATION, "Bring the guide slots into alignment by turning the adjuster."),
    ("Rotate the adjuster until the guide slots align.", _QUALITATIVE_ROTATION_RESTATEMENT),
    (_QUALITATIVE_ROTATION, "Bring the guide slots into alignment by turning the locknut clockwise."),
    (
        "Turn the spindle anti-clockwise to align the marks.",
        "Align the marks by rotating the spindle clockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "Turn the spindle clockwise before rotating the adjuster counterclockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "Rotate the adjuster clockwise after turning the spindle counterclockwise.",
    ),
    (_QUALITATIVE_ROTATION, "Align the guide slots before turning the adjuster clockwise."),
    (_QUALITATIVE_ROTATION, "Bring the pressure slot into alignment by turning the adjuster clockwise."),
    (_QUALITATIVE_ROTATION, "Bring the guide slots into alignment by turning the adjuster clockwise if needed."),
    (
        _QUALITATIVE_ROTATION,
        "Bring the guide slots into alignment by turning the adjuster clockwise with steady hand pressure.",
    ),
    (
        "Turn the spindle counter-clockwise to align the marks.",
        "Align the cap by rotating the spindle anticlockwise.",
    ),
])
def test_automatic_rewrite_preserves_qualitative_rotation_direction(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)

    assert result.error_code == "REWRITE_DIRECTION_MUTATION"
    assert result.document == source
    unchecked = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    validation = auto.validate_auto(source, unchecked, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert validation.error_codes == ("REWRITE_DIRECTION_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_QUALITATIVE_ROTATION, _QUALITATIVE_ROTATION_RESTATEMENT),
    (
        _QUALITATIVE_ROTATION,
        "Bring the guide slots into alignment by turning the adjuster in a clockwise direction.",
    ),
    (
        "Turn the spindle counter-clockwise to align the marks.",
        "Align the marks by rotating the spindle anticlockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "Turn the spindle anticlockwise after rotating the adjuster clockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "Turn the adjuster clockwise. Then, rotate the spindle anticlockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "Before turning the spindle anticlockwise, rotate the adjuster clockwise.",
    ),
    (
        "Rotate the adjuster clockwise, then turn the spindle counterclockwise.",
        "After rotating the adjuster clockwise, turn the spindle anticlockwise.",
    ),
])
def test_automatic_rewrite_accepts_restructured_qualitative_rotation(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.article_document import project_ordered_document

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)

    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    assert result.error_code is None
    assert auto.validate_auto(source, result.document, response=payload).passed
    assert draft in project_ordered_document(result.document)["body"]


_ROTATE_REMOVE = "Rotate the retaining sleeve clockwise and remove the guide plate."
_ROTATE_REMOVE_REPHRASED = "Turn the retaining sleeve in a clockwise direction and take the guide plate off."


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
@pytest.mark.parametrize("direction", ["counter clockwise", "counter-clockwise", "anti clockwise"])
@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
def test_split_counterclockwise_binds_direction_and_both_components(profile, direction, in_cell):
    from autodata_ingestion import procedure_rewrite_auto as auto

    original = f"Rotate the counter shaft {direction} and remove the guide plate."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    version = json.loads(prompt)["prompt_version"]
    assert version == auto._SPACED_ROTATION_PROMPT_VERSION
    expected = "Turn the counter shaft counterclockwise, then take off the guide plate."
    assert json.loads(prompt)["slots"][-1]["required_text"] == expected
    candidate = _scoped_prose_response(prompt, expected)
    result = rewrite.rewrite_ordered_document(source, client=Draft(candidate), context={}, profile_version=profile)
    assert result.error_code is None
    auto.require_current_publication_checks(source, result.document, saved_prompt_version=version)
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest(),
                                     profile_version=profile) == version
    wrong = _scoped_prose_response(prompt, "Turn the counter shaft counter in a clockwise direction and take the guide plate off.")
    with pytest.raises(ValueError, match="REWRITE_ROTATION_DIRECTION_MUTATION"):
        auto.render_auto(source, wrong, prompt_version=version, profile_version=profile)


def test_split_direction_keeps_archived_reply_verifiable_and_blocks_republication():
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source("Rotate the retaining sleeve counter clockwise and remove the guide plate.", in_cell=False)
    old = auto._build_auto_prompt_v65_with_technical_tokens(source, context={})
    old_version = auto._ROTATION_REMOVAL_PROMPT_VERSION
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(old.encode()).hexdigest()) == old_version
    wording = "Turn the retaining sleeve counter in a clockwise direction and take the guide plate off."
    response = _scoped_prose_response(old, wording)
    historical = auto.render_auto(source, response, prompt_version=old_version)
    assert auto.validate_auto(source, historical, response=response, prompt_version=old_version).passed
    with pytest.raises(ValueError, match="REWRITE_ROTATION_DIRECTION_MUTATION"):
        auto.require_current_publication_checks(source, historical, saved_prompt_version=old_version)


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
def test_plain_rotation_and_removal_rewrites_use_a_separate_prompt_version(profile, in_cell):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_ROTATE_REMOVE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={}, profile_version=profile)
    version = json.loads(prompt)["prompt_version"]
    assert version == auto._ROTATION_REMOVAL_PROMPT_VERSION
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, _ROTATE_REMOVE_REPHRASED)
    result = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=profile)
    assert result.error_code is None

    report = auto.validate_auto(source, result.document, response=payload, prompt_version=version, profile_version=profile)
    assert report.passed
    assert report.report["validator_version"] == "full-prose-auto-validator-v62"
    auto.require_current_publication_checks(source, result.document, saved_prompt_version=version)
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest(),
                                     profile_version=profile) == version
    archived = (auto._build_source_bound_prompt(source, preserve_notes=True, procedure_fidelity=True,
                                                allow_drain_subject=True)
                if profile == SOURCE_BOUND_REWRITE_PROFILE else auto._build_auto_prompt_v63(source, context={}))
    archived_version = json.loads(archived)["prompt_version"]
    assert archived_version != version
    assert json.loads(archived)["slots"][-1]["required_action"] == "retain"
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(archived.encode()).hexdigest(),
                                     profile_version=profile) == archived_version
    assert not auto.validate_auto(source, result.document, response=payload, prompt_version=archived_version,
                                  profile_version=profile).passed


@pytest.mark.parametrize("replacement", [
    _ROTATE_REMOVE_REPHRASED.replace("clockwise", "counterclockwise"),
    _ROTATE_REMOVE_REPHRASED.replace("retaining sleeve", "guide plate"),
    _ROTATE_REMOVE_REPHRASED.replace("guide plate", "retaining sleeve"),
    _ROTATE_REMOVE_REPHRASED.replace(" and ", " or "),
    _ROTATE_REMOVE_REPHRASED.replace("take the", "optionally take the"),
    "Take the guide plate off and turn the retaining sleeve in a clockwise direction.",
    "Turn the retaining sleeve in a clockwise direction.",
])
def test_plain_rotation_and_removal_rejects_technical_mutations(replacement):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_ROTATE_REMOVE, in_cell=False)
    prompt = auto.build_auto_prompt(source, context={})
    rejected = run(source, _scoped_prose_response(prompt, replacement))
    assert rejected.error_code in {"REWRITE_DIRECTION_MUTATION", "REWRITE_ACTION_MUTATION"}
    assert rejected.document == source



@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("direction", ["counter-\nclockwise", "counter- clockwise", "counter–clockwise", "anti‑clockwise"])
def test_automatic_rewrite_preserves_wrapped_rotary_direction(in_cell, direction):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(
        f"Turn the adjuster {direction} until the guide slots align.", in_cell=in_cell,
    )
    prompt = auto.build_auto_prompt(source, context={})
    reversed_payload = _scoped_prose_response(prompt, _QUALITATIVE_ROTATION_RESTATEMENT)
    rejected = run(source, reversed_payload)
    assert rejected.error_code == "REWRITE_DIRECTION_MUTATION"
    assert rejected.document == source

    payload = _scoped_prose_response(prompt, _REVERSED_QUALITATIVE_ROTATION)
    faithful = run(source, payload)
    assert faithful.error_code is None
    assert auto.validate_auto(source, faithful.document, response=payload).passed


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (
        "Turn the pump’s shaft clockwise.",
        "Use a clockwise rotation on the spindle.",
    ),
    (
        "Turn the adjuster slowly clockwise.",
        "Use a clockwise rotation on the spindle.",
    ),
    (
        "Turn the adjuster clockwise or counterclockwise.",
        "Rotate the spindle in a clockwise or counterclockwise direction.",
    ),
    (
        "Turn the adjuster not clockwise.",
        "Use a clockwise rotation on the spindle.",
    ),
    (
        "Rotate the adjuster clockwise until the detent engages.",
        "Use a clockwise rotation on the spindle.",
    ),
    (
        "Rotate the adjuster clockwise with steady hand pressure.",
        "Turn the adjuster clockwise.",
    ),
    (
        "Using the knurled handle, rotate the adjuster clockwise.",
        "Turn the adjuster clockwise.",
    ),
    (
        "Rotate the adjuster clockwise and mark its position.",
        "Turn the adjuster clockwise.",
    ),
    (
        "Rotate the adjuster clockwise. Mark its position.",
        "Turn the adjuster clockwise.",
    ),
    (
        "Clean the keyed slot. Rotate the adjuster clockwise.",
        "Turn the adjuster clockwise.",
    ),
])
def test_automatic_rewrite_retains_unproven_rotary_scope(in_cell, original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.article_document import project_ordered_document

    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    rejected = run(source, payload)
    assert rejected.error_code == "REWRITE_DIRECTION_MUTATION"
    assert rejected.document == source

    payload["replacements"][-1].update(action="retain", text=original, reason="Keep the exact source rotation.")
    retained = run(source, payload)
    assert retained.error_code is None
    assert original in project_ordered_document(retained.document)["body"]


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
def test_automatic_rewrite_rejects_one_word_qualitative_rotation_copy(in_cell):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = _scoped_prose_source(_QUALITATIVE_ROTATION, in_cell=in_cell)
    payload = _scoped_prose_response(
        auto.build_auto_prompt(source, context={}),
        "Turn the adjuster clockwise until the guide slots align.",
    )
    result = run(source, payload)

    assert result.error_code == "REWRITE_PROSE_TOO_SIMILAR"
    assert result.document == source


def test_automatic_rewrite_rejects_qualitative_direction_in_generated_introduction():
    source = document("Rotate the adjuster until the guide slots align.")
    payload = response(
        "Bring the guide slots into alignment by turning the adjuster.",
        introduction="This procedure covers counterclockwise adjuster alignment.",
    )

    assert run(source, payload).error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "9756bce42468d20a935a38f9f75549dca9874f37ae763319145d960a368ce44b",
     "62ead7e34eadd8154ce0965ee6f67038ca30af527a0f9aa865c65a7661445d8e",
     "9003731a2872dfaf1a10e0cf6a00c45e359e6a46e25d5621dbda63da784c759f"),
    (True, "36ed51704a9c94dcf29fefbc94ed839c1028a969c9e037f8c96d65055e9cb77a",
     "cc40dad355690e8f56c3fb7d0057e9f8eaf0b3f80015571b467320548428739c",
     "c6770b9ba1c58b0151014a1edfc6f27008438ac5cc2186ea82107ac503e5ee39"),
])
def test_automatic_reopens_v49_rotation_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source(_QUALITATIVE_ROTATION, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v49(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v49"
    payload = _scoped_prose_response(prompt, _REVERSED_QUALITATIVE_ROTATION)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_DIRECTION_MUTATION",)


@pytest.mark.parametrize("original,draft", [
    ("The guide route has 2 turns before the outlet.", "There are 2 turns in the guide route ahead of the outlet."),
    ("The guide route has 2 turns before the outlet. Rotate the adjustment knob.",
     "There are 2 turns in the guide route ahead of the outlet. Twist the adjustment knob."),
])
def test_automatic_rewrite_leaves_counted_route_turns_editable(original, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document(original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    assert run(source, response(draft)).error_code is None


def test_automatic_rewrite_rejects_repurposing_a_route_turn_count_as_a_rotation():
    source = document("The guide route has 2 turns before the outlet.")
    assert run(source, response("The adjustment uses 2 turns of clockwise rotation.")).error_code == "REWRITE_SPEC_SCOPE_MUTATION"


def test_v24_leaves_rotation_degrees_editable_under_historical_temperature_guard():
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Rotate the cam 45 degrees clockwise.")
    prompt = json.loads(auto._build_auto_prompt_v24(source, context={}))
    assert prompt["slots"][0]["required_action"] == "rewrite"
    payload = response("Turn the cam clockwise through 45 degrees.")
    version = prompt["prompt_version"]
    candidate = auto.render_auto(source, payload, prompt_version=version)
    assert auto.validate_auto(source, candidate, response=payload, prompt_version=version).passed


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "01ff6e97df729ee957d51b5cdb1c5e676b86202ebf9542947d955d38b08d2af8",
     "5a09ffe33009cb15d02a7e20e78e7473805a33bbcebb163fd04dc79bc1c1a565",
     "55f1ee62b5f1d9678406d5f9c4e0ea80adba426db07faea730786e0db84e96bb"),
    (True, "28c466aeb7f2e3ce3ea7db484703d40f0ef74fc8510c259f2a163a43e9ec2434",
     "6db7e387707b5ceb52e9d7193ed769eff25fbcbe25f695ba78f33cfb600bf345",
     "7b53d3d89731483562919ba7112a92727dfa95606b83cb2d4de10dc1f9d936d4"),
])
def test_automatic_reopens_v24_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    source = _scoped_prose_source("Turn the adjuster 1.5 turns clockwise.", in_cell=in_cell)
    prompt = auto._build_auto_prompt_v24(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v24"
    payload = _scoped_prose_response(prompt, "Give the adjuster 1.5 turns counterclockwise.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "2a09e5ad3bef71e7919f98d3ba71cdd9aeb13927cb8c36459a238cc9fef75613",
     "56632b0b074612452a4e9060a1b613ba521ce761397b0cf40b2caa2ee8a13a57",
     "5979abae43790af45fccbdcb72e146e267c3d4ecfdeb024b5f5aa370348baa6f"),
    (True, "978004407e3ab904f53f61f64b0060ef9240194571014a65aed3e928ad93b7e0",
     "cf4de56f2848d63bb9570128ef44adace5e92db9c2e27f1ddcb0cba491e633b5",
     "1cbe96457d0dc12545dc52118f69382bae868371ccebd331cdc95498613bdd02"),
])
def test_automatic_reopens_v23_with_original_validation_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"make": "Fixture"}
    original = "Keep your hands clear of the moving fan."
    draft = "Keep your hands close to the moving fan."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v23(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v23"
    payload = _scoped_prose_response(prompt, draft)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SAFETY_MUTATION",)


def test_technical_only_retention_is_explicit_and_table_stays_exact():
    source = document("25 Nm", "Remove the cover.")
    source["blocks"].append({"block_id":"table", "source_order":3,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]})
    payload = response("25 Nm", "Take the cover off.")
    payload["replacements"][0].update(action="retain", reason="Exact technical specification")
    result = run(source, payload)
    assert result.error_code is None
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["retained_paths"] == ["/blocks/0/text"]
    assert result.document["blocks"][-1] == dict(source["blocks"][-1], source_order=4)


def test_auto_table_only_introduction_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = document()
    source["blocks"] = [{"block_id":"table","source_order":1,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]}]
    payload = response(introduction="The table lists the cover torque of 25 Nm.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    changed = deepcopy(payload); changed["introduction"] = "Cover torque is listed as 25 Nm."
    assert not validate_auto(source, result.document, response=changed).passed


@pytest.mark.parametrize("mutation", ["number", "order", "missing", "extra", "context"])
def test_automatic_profile_rejects_corrupt_or_incomplete_model_outputs(mutation):
    source = document("Tighten the bolts to 25 Nm.", "Remove the cover.")
    payload = response("The bolts require tightening to 25 Nm.", "Take the cover off.")
    if mutation == "number": payload["replacements"][0]["text"] = "The bolts require tightening to 30 Nm."
    if mutation == "order": payload["replacements"].reverse()
    if mutation == "missing": payload["replacements"].pop()
    if mutation == "extra": payload["replacements"].append(deepcopy(payload["replacements"][0]))
    if mutation == "context": payload["introduction"] = "Use this for the 2012 Audi A3."
    result = run(source, payload)
    assert result.error_code is not None and result.document == source


def test_prompt_asks_for_automatic_full_prose_without_human_review_obligations():
    prompt = json.loads(rewrite.build_rewrite_prompt(document("Remove the cover."), context={}, profile_version=PROFILE))
    assert prompt["profile_version"] == PROFILE
    assert "human" not in " ".join(prompt["rules"]).lower()
    assert "automatically" in " ".join(prompt["rules"]).lower()
    assert prompt["slots"][0]["text"] == "Remove the cover."


def test_current_prompt_declares_complete_response_rows_and_server_required_actions():
    source = document("Remove the cover.", "25 Nm", "Never start the motor.",
                      "Fit the cover only after the seal sits flush.",
                      "Except if the seal is dry, inspect the housing.")
    before = deepcopy(source)
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v55"
    assert prompt["response_shape"] == {"introduction": "string", "replacements": [
        {"block_id": "string", "path": "string", "action": "rewrite|retain", "text": "string", "reason": "string"}]}
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "rewrite_or_retain", "retain", "retain", "retain"]
    rules = " ".join(prompt["rules"])
    assert 'reason:""' in rules
    assert "exactly five keys" in rules
    assert "copying long phrases" in rules
    assert source == before


def test_historical_auto_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v1
    prompt = _build_auto_prompt_v1(document("Remove the cover."), context={})
    assert sha256(prompt.encode()).hexdigest() == "cc5ef47228dc07abee81956adabf0de870247950fc3f5867ce6ed8b110f62e51"
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v1"


def test_historical_v4_prompt_digest_and_validation_report_remain_stable():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _auto_prompt_version, _build_auto_prompt_v4, render_auto, validate_auto

    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt_hash = sha256(_build_auto_prompt_v4(source, context=context).encode()).hexdigest()
    assert prompt_hash == "00e8a399286299d7c8bb588c9c38f10a99895bb4e0f8a252d18c9f4338c21b2d"
    version = _auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v4"

    # The old validator accepted this changed operation and resulting report.
    payload = response("Fit the cover.")
    candidate = render_auto(source, payload, prompt_version=version)
    historical = validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v2"
    current = validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_ACTION_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"


def test_historical_v5_prompt_digest_and_validation_report_remain_stable():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from hashlib import sha256

    source = document("Remove the left-hand wheel-arch liner.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v5(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "096c23f47e4a38e3a48175b377e3f49cf1f5ca24204e59837e5f3a916365b3f9"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v5"

    payload = response("Take off the liner from the right-hand wheel arch.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v3"
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_DIRECTION_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"


def test_historical_v6_prompt_digest_and_validation_report_remain_stable():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from hashlib import sha256

    source = document("Remove the inlet cover.", "Remove the cable shield.")
    context = {"vehicle": "routing-only"}
    digest = sha256(auto._build_auto_prompt_v6(source, context=context).encode()).hexdigest()
    assert digest == "8cb4564ba563dc7fbd04a443abc67b71b2c50718ed5607d194a06227e86bf87d"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=digest)
    assert version == "full-prose-auto-prompt-v6"

    payload = response("Take off the cable shield.", "Lift off the inlet cover.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v4"
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_COMPONENT_SWAP",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"


def test_historical_v7_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Remove the inlet cover first, then remove the cable shield.")
    payload = response("Take the cable shield off before lifting off the inlet cover.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v7(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "d17f83f22c979878e4e5f11dc3f47e33c8c7affb0decc511047e323842432857"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v7"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    validation = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert validation.passed is True
    assert validation.report["content_acceptance_required"] is False
    assert validation.report["complete_rewrite"] is False
    assert digest_json(candidate) == "8597df2a50095d2a843c0b87b571d590831babc8416bee23977d08d166ceb487"
    assert digest_json(validation.report) == "96d1fb4a3d6efe7135794fd5ba9fdce64c4efbc2bd481b1dd48b773b16522d66"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.passed is False
    assert current.report["passed"] is False
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"
    assert current.error_codes == ("REWRITE_CLAUSE_MUTATION",)


def test_historical_v8_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Remove the cover.")
    payload = response("Take the cover off if the seal is dry.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v8(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "7214abba87a6086a1023c317b31d0586f19a6946b241aec7ca7e776b79037f3a"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v8"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    validation = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert validation.passed is True
    assert validation.report["content_acceptance_required"] is False
    assert validation.report["complete_rewrite"] is False
    assert digest_json(candidate) == "3da3ec07cb74b58eab8eea69bfd1cb6d46088a8790201cd2f8aeac5719116daf"
    assert digest_json(validation.report) == "574e67861f5c7c268db9fa436f22137cf587a41ab7676eb37ecd0e94e8e4403c"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.passed is False
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


def test_historical_v9_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Install a new oil seal.")
    payload = response("Fit the used oil seal into place.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v9(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "13cb6f8ddc88bed61bacf96da7839468447a6c6c2bf2c496289faac1b8289e38"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v9"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert historical.report["validator_version"] == "full-prose-auto-validator-v7"
    assert digest_json(candidate) == "79c64e1180988281853e16b91a4da5e124a5a6250cd92b40b96713a9345cd0f4"
    assert digest_json(historical.report) == "edfe4cdccc79773c6098aa4679e2cb57850601de0c4494ccc3dc4f1e67a2e268"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"


def test_auto_prompt_hash_accepts_only_exact_server_reconstructions():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _auto_prompt_version, _build_auto_prompt_v1, _build_auto_prompt_v2,
        _build_auto_prompt_v4, _build_auto_prompt_v5, _build_auto_prompt_v6, _build_auto_prompt_v7,
        _build_auto_prompt_v8, _build_auto_prompt_v9, _build_auto_prompt_v10,
        _build_auto_prompt_v11, _build_auto_prompt_v12, _build_auto_prompt_v13, _build_auto_prompt_v14, _build_auto_prompt_v15, _build_auto_prompt_v16, _build_auto_prompt_v17, _build_auto_prompt_v18, _build_auto_prompt_v19, _build_auto_prompt_v20, _build_auto_prompt_v21, _build_auto_prompt_v22, _build_auto_prompt_v23, _build_auto_prompt_v24, _build_auto_prompt_v25, _build_auto_prompt_v26, _build_auto_prompt_v27, _build_auto_prompt_v28, _build_auto_prompt_v29, _build_auto_prompt_v30, _build_auto_prompt_v31, _build_auto_prompt_v32, _build_auto_prompt_v33, _build_auto_prompt_v34, _build_auto_prompt_v35, _build_auto_prompt_v36, _build_auto_prompt_v37, _build_auto_prompt_v38, _build_auto_prompt_v39, _build_auto_prompt_v40, _build_auto_prompt_v41, _build_auto_prompt_v42, _build_auto_prompt_v43, _build_auto_prompt_v44, _build_auto_prompt_v45, _build_auto_prompt_v46, _build_auto_prompt_v47, _build_auto_prompt_v48, _build_auto_prompt_v49, _build_auto_prompt_v50, _build_auto_prompt_v51, build_auto_prompt,
    )
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompts = [builder(source, context=context) for builder in
               (_build_auto_prompt_v1, _build_auto_prompt_v2, _build_auto_prompt_v4, _build_auto_prompt_v5,
                _build_auto_prompt_v6, _build_auto_prompt_v7, _build_auto_prompt_v8, _build_auto_prompt_v24, _build_auto_prompt_v25, _build_auto_prompt_v26, _build_auto_prompt_v27, _build_auto_prompt_v28, _build_auto_prompt_v29, _build_auto_prompt_v30, _build_auto_prompt_v31, _build_auto_prompt_v32, _build_auto_prompt_v33, _build_auto_prompt_v34, _build_auto_prompt_v35, _build_auto_prompt_v36, _build_auto_prompt_v37, _build_auto_prompt_v38, _build_auto_prompt_v39, _build_auto_prompt_v40, _build_auto_prompt_v41, _build_auto_prompt_v42, _build_auto_prompt_v43, _build_auto_prompt_v44, _build_auto_prompt_v45, _build_auto_prompt_v46, _build_auto_prompt_v47, _build_auto_prompt_v48, _build_auto_prompt_v49, _build_auto_prompt_v50, _build_auto_prompt_v51, build_auto_prompt)]
    for prompt in prompts:
        digest = sha256(prompt.encode()).hexdigest()
        assert _auto_prompt_version(source, context=context, prompt_hash=digest) == json.loads(prompt)["prompt_version"]
        assert not _auto_prompt_version(document("Remove the panel."), context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    for mutation in ("rule", "required_action", "version"):
        changed = json.loads(prompts[-1])
        if mutation == "rule": changed["rules"].pop()
        if mutation == "required_action": del changed["slots"][0]["required_action"]
        if mutation == "version": changed["prompt_version"] = "full-prose-auto-prompt-v3"
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())
    assert not _auto_prompt_version(source, context=context, prompt_hash="0" * 64)


def test_prompt_v9_response_example_satisfies_strict_renderer():
    source = document("Remove the cover.", "25 Nm")
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    payload = {"introduction": "The procedure covers removal of the cover.", "replacements": []}
    for slot, text in zip(prompt["slots"], ["Take the cover off.", "25 Nm"]):
        row = {key: "" for key in prompt["response_shape"]["replacements"][0]}
        row.update(block_id=slot["block_id"], path=slot["path"], text=text,
                   action="rewrite" if slot["required_action"] == "rewrite" else "retain")
        if row["action"] == "retain": row["reason"] = "Exact technical specification"
        payload["replacements"].append(row)
    assert run(source, payload).error_code is None
    del payload["replacements"][0]["reason"]
    assert run(source, payload).error_code == "REWRITE_SLOT_MISMATCH"


def zero_slot_document():
    """Synthetic shape of the failed proof; no production text or references."""
    source = document()
    source["title"] = "Cover service references"
    kinds = ["callout"] * 35 + ["heading"] * 24 + ["link"] * 4
    source["blocks"] = [
        {"block_id": f"protected-{i}", "source_order": i + 1, "type": kind,
         "text": "Cover service references", "evidence_ids": ["fixture-evidence"]}
        for i, kind in enumerate(kinds)
    ]
    return source


def test_zero_slot_prompt_v3_requests_only_source_introduction_without_routing():
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    source = zero_slot_document()
    before = deepcopy(source)
    context = {"vehicle": "2099 RoutingModel CTX-99"}
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context=context, profile_version=PROFILE))
    assert len(source["blocks"]) == 63 and prose_slots(source) == []
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v3"
    assert prompt["replacement_count"] == 0 and prompt["slots"] == []
    assert prompt["response_shape"] == {"introduction": "string", "replacements": []}
    assert "context" not in prompt and "RoutingModel" not in json.dumps(prompt)
    rules = " ".join(prompt["rules"])
    assert '"replacements":[]' in rules
    assert "Do not invent replacement rows" in rules
    assert "document is the only source of facts" in rules
    assert "numeric, identifier or reference facts" in rules
    assert prompt["document"] == source == before


def test_zero_slot_output_preserves_all_protected_content_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = zero_slot_document()
    before = deepcopy(source)
    payload = response(introduction="The article provides cover service references.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    restored = deepcopy(result.document)
    restored["blocks"].pop(0)
    for block in restored["blocks"]:
        block["source_order"] -= 1
    assert digest_json(restored) == digest_json(source)
    assert source == before
    changed = deepcopy(payload)
    changed["introduction"] = "Cover service references are provided here."
    assert not validate_auto(source, result.document, response=changed).passed
    report = validate_auto(source, result.document, response=payload).report
    assert report["complete_rewrite"] is False


@pytest.mark.parametrize("mutation", ["fabricated_slot", "numeric", "identifier", "third_key"])
def test_zero_slot_output_still_rejects_fabricated_slots_and_unsupported_facts(mutation):
    source = zero_slot_document()
    payload = response(introduction="The article provides cover service references.")
    if mutation == "fabricated_slot":
        payload["replacements"] = response("Reword this protected heading.")["replacements"]
    elif mutation == "numeric":
        payload["introduction"] = "The cover requires 99 Nm."
    elif mutation == "identifier":
        payload["introduction"] = "Use tool UNSUPPORTED-99 for cover service."
    else:
        payload["replacement_count"] = 0
    result = run(source, payload)
    assert result.error_code == {
        "fabricated_slot": "REWRITE_SLOT_MISMATCH", "numeric": "REWRITE_TECHNICAL_MUTATION",
        "identifier": "REWRITE_TECHNICAL_MUTATION", "third_key": "REWRITE_RESPONSE_INVALID",
    }[mutation]
    assert result.document == source


def test_zero_slot_historical_prompt_reconstruction_and_current_routing_omission():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _build_auto_prompt_v1, _build_auto_prompt_v2, build_auto_prompt, _auto_prompt_version,
    )
    source = zero_slot_document()
    context = {"vehicle": "routing-only"}
    historical = [(_build_auto_prompt_v1, "ce519878922481405f40028c3af5ebf2ff742af5bab96126ea21650311d67ea0"),
                  (_build_auto_prompt_v2, "e1fb10033d5aec793c15dda664767656be5530d380972e76bf48a2bb5d2ee3f5")]
    for builder, expected in historical:
        digest = sha256(builder(source, context=context).encode()).hexdigest()
        assert digest == expected
        assert _auto_prompt_version(source, context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    current = build_auto_prompt(source, context=context)
    digest = sha256(current.encode()).hexdigest()
    assert current == build_auto_prompt(source, context={"vehicle": "other routing"})
    assert _auto_prompt_version(source, context={}, prompt_hash=digest)
    changed_source = deepcopy(source)
    changed_source["blocks"][0]["text"] = "Other protected content"
    assert not _auto_prompt_version(changed_source, context=context, prompt_hash=digest)
    for key, value in [("replacement_count", 1), ("prompt_version", "unrecognized"),
                       ("response_shape", {"introduction": "string", "replacements": [{}]})]:
        changed = json.loads(current)
        changed[key] = value
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())


def test_nonzero_slot_historical_v2_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v2
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt = _build_auto_prompt_v2(source, context=context)
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v2"
    assert sha256(prompt.encode()).hexdigest() == "d972668e5934f6f66dee2ead79ee6bd45e4ca3c98e4f8fb94128fa330cdd22b6"


@pytest.mark.parametrize("profile", [PROFILE, SOURCE_BOUND_REWRITE_PROFILE])
def test_server_zero_slot_candidate_is_exact_heading_and_preserves_source(profile):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); before = deepcopy(source)
    candidate, metadata = auto.build_source_preserving_candidate(source, profile_version=profile)
    heading = next(b['text'] for b in source['blocks'] if b['type'] == 'heading')
    assert candidate['blocks'][0]['text'] == heading
    restored = deepcopy(candidate); restored['blocks'].pop(0)
    for block in restored['blocks']: block['source_order'] -= 1
    assert restored == source == before
    assert metadata == {"transformation_method":"source-preserving-zero-slot-v1",
        "drafting_actor":"server", "model":"server-zero-slot-v1", "profile_version":profile,
        "model_calls":0, "model_dispatch_count":0, "complete_rewrite":False,
        "source_hash":digest_json(source), "output_hash":digest_json(candidate)}
    validation = auto.validate_source_preserving_candidate(source, candidate, metadata, profile_version=profile)
    assert validation.passed and validation.report['complete_rewrite'] is False
    assert validation.report['introduction_origin'] == 'source_heading'
    assert validation.report['model_dispatch_count'] == 0
    assert auto.build_source_preserving_candidate(source, profile_version=profile) == (candidate, metadata)


def test_server_zero_slot_skips_ambiguous_heading_without_editing_it():
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    first = next(i for i,b in enumerate(source['blocks']) if b['type']=='heading')
    source['blocks'][first]['text'] = 'Specification ½'
    candidate, metadata = auto.build_source_preserving_candidate(source)
    assert candidate['blocks'][0]['text'] == next(b['text'] for b in source['blocks'][first+1:] if b['type']=='heading')
    assert candidate['blocks'][first+1]['text'] == 'Specification ½'
    assert auto.validate_source_preserving_candidate(source, candidate, metadata).passed


@pytest.mark.parametrize('kind', ['no_heading', 'ambiguous', 'oversize', 'nonzero'])
def test_server_zero_slot_fails_closed_without_an_eligible_heading(kind):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    if kind == 'nonzero': source = document('Remove the cover.')
    else:
        for b in source['blocks']:
            if b['type'] == 'heading':
                if kind == 'no_heading': b.update(type='callout', label='note'); b.pop('level', None)
                else: b['text'] = 'Specification ½' if kind=='ambiguous' else 'A'*(1024*1024)
    with pytest.raises(ValueError): auto.build_source_preserving_candidate(source)


@pytest.mark.parametrize('mutation', ['candidate', 'source', 'method', 'extra', 'zero_boolean'])
def test_server_zero_slot_revalidation_rejects_tampered_candidate_or_provenance(mutation):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); candidate, metadata = auto.build_source_preserving_candidate(source)
    if mutation == 'candidate': candidate['blocks'][0]['text'] += ' Unsupported-99'
    elif mutation == 'source': source['blocks'][0]['text'] += ' changed'
    elif mutation == 'method': metadata['transformation_method'] = 'forged'
    elif mutation == 'extra': metadata['prompt_hash'] = '0'*64
    else: metadata['model_calls'] = False
    with pytest.raises(ValueError): auto.validate_source_preserving_candidate(source, candidate, metadata)



@pytest.mark.parametrize("wrapped_row", [False, True])
def test_auto_rewrites_nested_table_prose_and_preserves_saved_v10(wrapped_row):
    from hashlib import sha256

    from autodata_ingestion import procedure_rewrite_auto as auto

    context = {"vehicle": "routing-only"}
    source = document("Remove the pump.", "Inspect the seal.", "Never reuse the seal.")
    lead, inspection, warning = source["blocks"]
    inspection["source_order"], warning["source_order"] = 1, 2
    cell = {"text": "Service addendum", "blocks": [inspection, warning]}
    row = [cell, "25 Nm"]
    table = {
        "block_id": "table", "type": "table", "source_order": 2,
        "evidence_ids": ["source:linked"], "columns": ["Service instruction", "Torque"],
        "rows": [{"cells": row} if wrapped_row else row],
    }
    source["blocks"] = [lead, table]

    def draft(prompt):
        outputs = {"Remove the pump.": "Take off the pump.", "Inspect the seal.": "Check the seal."}
        return {
            "introduction": "This procedure covers pump removal.",
            "replacements": [
                {"block_id": slot["block_id"], "path": slot["path"],
                 "action": "retain" if slot["required_action"] == "retain" else "rewrite",
                 "text": outputs.get(slot["text"], slot["text"]),
                 "reason": "Preserve the original safety instruction." if slot["required_action"] == "retain" else ""}
                for slot in json.loads(prompt)["slots"]
            ],
        }

    historical_version = "full-prose-auto-prompt-v10"
    historical_prompt = auto._build_auto_prompt_v10(source, context=context)
    historical_draft = draft(historical_prompt)
    assert len(historical_draft["replacements"]) == 1
    assert auto._auto_prompt_version(
        source, context=context, prompt_hash=sha256(historical_prompt.encode()).hexdigest(),
    ) == historical_version
    historical = auto.render_auto(source, historical_draft, prompt_version=historical_version)
    assert auto.validate_auto(source, historical, response=historical_draft, prompt_version=historical_version).passed

    prompt = auto.build_auto_prompt(source, context=context)
    version = "full-prose-auto-prompt-v55"
    assert json.loads(prompt)["prompt_version"] == version
    assert auto._auto_prompt_version(source, context=context, prompt_hash=sha256(prompt.encode()).hexdigest()) == version
    paths = [slot["path"] for slot in json.loads(prompt)["slots"]]
    base = "/blocks/1/rows/0" + ("/cells" if wrapped_row else "") + "/0/blocks"
    assert paths == ["/blocks/0/text", base + "/0/text", base + "/1/text"]
    payload = draft(prompt)
    result = run(source, payload)
    assert result.error_code is None
    revised = result.document["blocks"][2]["rows"][0]
    revised = revised["cells"] if wrapped_row else revised
    assert revised == [
        {"text": "Service addendum", "blocks": [{**inspection, "text": "Check the seal."}, warning]},
        "25 Nm",
    ]
    checked = auto.validate_auto(source, result.document, response=payload, prompt_version=version)
    assert checked.passed
    assert checked.report["changed_prose_slots"] == paths[:2]
    assert checked.report["retained_paths"] == paths[2:]
    changed = deepcopy(result.document)
    changed_row = changed["blocks"][2]["rows"][0]
    (changed_row["cells"] if wrapped_row else changed_row)[1] = "35 Nm"
    assert "REWRITE_PROTECTED_MUTATION" in auto.validate_auto(source, changed, prompt_version=version).error_codes
