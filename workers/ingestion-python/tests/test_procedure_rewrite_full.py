"""Synthetic mechanical-boundary regressions; these are not content acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion import procedure_rewrite as rewrite  # noqa: E402
from autodata_ingestion.article_document import validate_ordered_document  # noqa: E402
from autodata_ingestion.article_lifecycle_types import digest_json  # noqa: E402

PROFILE = "full-prose-review-v1"


def document(*texts):
    return {"schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": [
        {"block_id": f"p{i}", "source_order": i + 1, "type": "paragraph", "text": text,
         "evidence_ids": ["fixture-evidence"]} for i, text in enumerate(texts)]}


def response(*texts, introduction="This article describes access to the cover."):
    return {"introduction": introduction, "replacements": [
        {"block_id": f"p{i}", "path": f"/blocks/{i}/text", "action": "rewrite", "text": text, "reason": ""}
        for i, text in enumerate(texts)]}


class Draft:
    _model = "synthetic-fixture"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def complete_json(self, prompt):
        self.calls += 1
        self.prompt = json.loads(prompt)
        return deepcopy(self.payload)


def run(source, payload):
    return rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=PROFILE)


def test_introduction_prompt_limits_facts_to_document_not_vehicle_context():
    from autodata_ingestion.procedure_rewrite_full import build_full_prompt
    source = document("Tighten the bolts to 25 Nm using tool T-42.")
    context = {"vehicle": "2012 Audi A3", "engine": "CTX-99"}
    prompt = json.loads(build_full_prompt(source, context=context))
    assert prompt["prompt_version"] == "full-prose-prompt-v2"
    assert prompt["introduction_allowed_technical_tokens"] == ["25 Nm", "T-42", "ordered-article-v1", "p0"]
    assert prompt["context"] == context
    assert prompt["document"] == source
    rules = " ".join(prompt["rules"])
    assert "document is the only source of facts" in rules
    assert "Context is routing metadata, not source evidence" in rules
    assert "occur only in context" in rules
    assert "introduction_allowed_technical_tokens" in rules


def test_context_only_introduction_still_rejects_and_source_supported_intro_passes():
    from autodata_ingestion.procedure_rewrite_full import render_full
    source = document("Remove the cover.")
    payload = response("Take the cover off.", introduction="Access to the cover on the 2012 Audi A3.")
    with pytest.raises(ValueError, match="REWRITE_TECHNICAL_MUTATION"):
        render_full(source, payload)
    payload["introduction"] = "This article describes removing the cover."
    candidate = render_full(source, payload)
    assert rewrite.validate_article_rewrite(source, candidate, profile_version=PROFILE).passed


def test_introduction_token_payload_matches_all_document_strings_deterministically():
    from autodata_ingestion.procedure_rewrite_full import build_full_prompt
    source = document("Tighten to 25 Nm.", "Use tool T-42.")
    source["title"] = "Tool T-42"
    before = deepcopy(source)
    first = build_full_prompt(source, context={"vehicle": "CTX-99"})
    assert first == build_full_prompt(source, context={"vehicle": "CTX-99"})
    # Document metadata participates, duplicates collapse, and context stays excluded.
    assert json.loads(first)["introduction_allowed_technical_tokens"] == ["25 Nm", "T-42", "ordered-article-v1", "p0", "p1"]
    assert source == before


def test_full_rewrites_declarative_multisentence_conditional_prose_without_semantic_credit():
    source = document("The cover provides access. If equipped, disconnect the cable before removal.",
                      "Tighten the bolts to 25 Nm using tool T-42.")
    original = deepcopy(source)
    payload = response("Access is provided by the cover. Before removal, disconnect the cable if equipped.",
                       "Using tool T-42, tighten the bolts to 25 Nm.")
    # Technical tokens must remain in source-leaf order, even if the paraphrase reads well.
    bad = run(source, payload)
    assert bad.error_code == "REWRITE_TECHNICAL_MUTATION" and bad.document == source
    payload["replacements"][1]["text"] = "The bolts require tightening to 25 Nm with tool T-42."
    result = run(source, payload)
    assert result.error_code is None
    assert source == original
    assert result.document["blocks"][1]["text"].startswith("Access is provided")
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["structural_integrity_passed"] and report["content_acceptance_required"]
    assert report["complete_rewrite"] is False
    assert report["changed_slots"] == ["/introduction", "/blocks/0/text", "/blocks/1/text"]
    assert report["changed_prose_slots"] == ["/blocks/0/text", "/blocks/1/text"]
    assert report["source_protected_hash"] == report["target_protected_hash"]
    assert report["source_hash"] == digest_json(source)
    assert report["candidate_hash"] == digest_json(result.document)


def test_introduction_is_source_bound_server_owned_and_top_level_order_shifts_only():
    source = document("The cover provides access.")
    source["blocks"].append({"block_id":"list", "source_order":2,"type":"ordered_list",
        "items":[{"text":"Remove the cover.", "blocks":[{"block_id":"nested", "source_order":1,
          "type":"paragraph", "text":"The cable remains attached.", "evidence_ids":["nested-e"]}]}], "evidence_ids":["list-e"]})
    payload = response("Access is provided by the cover.")
    payload["replacements"].extend([
        {"block_id":"list","path":"/blocks/1/items/0/text","action":"rewrite","text":"Take the cover off.","reason":""},
        {"block_id":"nested","path":"/blocks/1/items/0/blocks/0/text","action":"rewrite","text":"Leave the cable attached.","reason":""}])
    result = run(source, payload)
    assert result.error_code is None
    blocks = result.document["blocks"]
    assert [b["source_order"] for b in blocks] == [1, 2, 3]
    assert blocks[2]["items"][0]["blocks"][0]["source_order"] == 1
    assert blocks[0] == {"type":"paragraph", "block_id":blocks[0]["block_id"], "source_order":1,
        "text":payload["introduction"], "evidence_ids":["fixture-evidence", "list-e", "nested-e"]}
    assert blocks[0]["block_id"] not in {"p0", "list", "nested"}
    assert run(source, payload).document == result.document
    other = deepcopy(source); other["blocks"][0]["evidence_ids"] = ["other"]
    assert run(other, payload).document["blocks"][0]["block_id"] != blocks[0]["block_id"]
    assert validate_ordered_document(result.document, strict=True) == []


def test_table_only_introduction_preserves_exact_technical_table():
    source = document()
    source["blocks"] = [{"block_id":"specs", "source_order":1,"type":"table",
        "columns":["Component", "Torque"], "rows":[["Cover", "25 Nm"]],"evidence_ids":["e-table"]}]
    payload = response(introduction="The table lists the cover torque of 25 Nm.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1] == {**source["blocks"][0], "source_order":2}
    assert rewrite.validate_article_rewrite(source,result.document,profile_version=PROFILE).report["changed_slots"] == ["/introduction"]
    payload["introduction"] = "The table lists the cover torque of 250 Nm."
    assert run(source, payload).error_code == "REWRITE_TECHNICAL_MUTATION"


def test_every_nested_string_and_object_list_leaf_is_accounted_for():
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    source = document("Cover access is provided.")
    source["blocks"].append({"block_id":"list","source_order":2,"type":"unordered_list", "evidence_ids":["e"],
        "items":["Remove the cover.", {"text":"Inspect the cable.", "blocks":[
          {"block_id":"inner","source_order":1,"type":"ordered_list","items":["Clean the cover."],"evidence_ids":["e"]}]}]})
    assert prose_slots(source) == [
        {"block_id":"p0","path":"/blocks/0/text","text":"Cover access is provided."},
        {"block_id":"list","path":"/blocks/1/items/0","text":"Remove the cover."},
        {"block_id":"list","path":"/blocks/1/items/1/text","text":"Inspect the cable."},
        {"block_id":"inner","path":"/blocks/1/items/1/blocks/0/items/0","text":"Clean the cover."}]
    assert rewrite.editable_slots(source,profile_version=PROFILE) == prose_slots(source)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "reorder", "extra", "foreign_path", "foreign_id", "structure", "top_structure", "blank", "case", "space", "retain_changed", "retain_blank", "action_bool", "path_int", "text_bool", "reason_int"])
def test_response_cannot_skip_forge_structure_or_claim_superficial_changes(mode):
    source = document("The cover provides access.", "Inspect the cable.")
    payload = response("Access is provided by the cover.", "Check the cable.")
    rows = payload["replacements"]
    if mode == "missing": rows.pop()
    elif mode == "duplicate": rows[1] = deepcopy(rows[0])
    elif mode == "reorder": rows.reverse()
    elif mode == "extra": rows.append(deepcopy(rows[0]))
    elif mode == "foreign_path": rows[0]["path"] = "/blocks/1/text"
    elif mode == "foreign_id": rows[0]["block_id"] = "foreign"
    elif mode == "structure": rows[0]["evidence_ids"] = ["forged"]
    elif mode == "top_structure": payload["blocks"] = []
    elif mode == "blank": rows[0]["text"] = " "
    elif mode == "case": rows[0]["text"] = source["blocks"][0]["text"].upper()
    elif mode == "space": rows[0]["text"] = "  The   cover provides access.\n"
    elif mode == "retain_changed": rows[0].update(action="retain", reason="Technical label")
    elif mode == "retain_blank": rows[0].update(action="retain", text=source["blocks"][0]["text"], reason=" ")
    elif mode == "action_bool": rows[0]["action"] = True
    elif mode == "path_int": rows[0]["path"] = 0
    elif mode == "text_bool": rows[0]["text"] = True
    else: rows[0]["reason"] = 1
    result = run(source, payload)
    assert result.error_code and result.document == source


def test_retentions_are_explicit_review_obligations_and_never_completeness_evidence():
    from autodata_ingestion.procedure_rewrite_full import render_full, validate_full
    source = document("T-42", "The cover provides access.")
    payload = response("T-42", "Access is provided by the cover.")
    payload["replacements"][0].update(action="retain", reason="Exact tool identifier label")
    candidate = render_full(source,payload)
    validation = validate_full(source,candidate,response=payload)
    assert validation.passed
    assert validation.report["retained_paths"] == ["/blocks/0/text"]
    assert validation.report["retention_reasons"] == {"/blocks/0/text":"Exact tool identifier label"}
    assert validation.report["content_acceptance_required"] and not validation.report["complete_rewrite"]
    # Machine cannot determine if a model's retention classification is honest.
    payload["replacements"][1].update(action="retain",text=source["blocks"][1]["text"],reason="Claimed label; requires human decision")
    validation = validate_full(source,render_full(source,payload),response=payload)
    assert validation.passed and len(validation.report["retained_paths"]) == 2
    assert not validation.report["complete_rewrite"]


@pytest.mark.parametrize("original,changed", [
    ("25 Nm", "250 Nm"), ("25 Nm", "25 lb-ft"), ("25Nm", "25nm"),
    ("-2.5–+3.0 N·m", "-2.5–+3.0 Nm"), ("≤ ٢٥ mm", "< ٢٥ mm"),
    ("1,234.50 psi", "1234.50 psi"), ("T-42", "T-43"),
    ("ABC123", "ABC124"), ("10–20 lb-ft", "20–10 lb-ft"),
    ("https://example.test/manual#cover", "https://example.test/manual#pump"),
    ("[manual](urn:manual:cover)", "[manual](urn:manual:pump)"),
])
def test_numeric_unit_identifier_and_reference_guards_require_verbatim_order(original,changed):
    source = document(f"Use {original} for the cover.")
    good = response(f"The cover requires {original} as specified.")
    assert run(source,good).error_code is None
    bad = response(f"The cover requires {changed} as specified.")
    assert run(source,bad).error_code == "REWRITE_TECHNICAL_MUTATION"


def test_numbers_cannot_move_between_leaves_or_enter_introduction_without_source_support():
    source = document("Tighten to 25 Nm.", "Use tool T-42.")
    payload = response("Use tool T-42.", "Tighten to 25 Nm.")
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_MUTATION"
    payload = response("Tightening requires 25 Nm.", "Tool T-42 is required.", introduction="Use tool T-43.")
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_MUTATION"


def test_ambiguous_numeric_notation_requires_literal_retention_and_review():
    source = document("Area is 25 mm².")
    payload = response("The area equals 25 mm².")
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_AMBIGUOUS"
    payload["replacements"][0].update(action="retain",text=source["blocks"][0]["text"],reason="Ambiguous superscript notation retained verbatim")
    assert run(source,payload).error_code is None


@pytest.mark.parametrize("mutation", ["table", "callout", "heading", "media", "evidence", "nested", "order", "extra", "id", "schema_bool", "schema_float", "order_bool", "intro_evidence", "intro_id", "intro_order"])
def test_independent_validation_rejects_protected_and_json_type_mutations(mutation):
    source = document("The cover provides access.")
    source["blocks"].extend([
      {"block_id":"table","type":"table","source_order":2,"rows":[["25 Nm"]],"evidence_ids":["e"]},
      {"block_id":"safety","type":"callout","source_order":3,"text":"Warning: Do not start the engine.","evidence_ids":["e"]},
      {"block_id":"heading","type":"heading","source_order":4,"text":"Removal","level":2,"evidence_ids":["e"]},
      {"block_id":"image","type":"image","source_order":5,"status":"unavailable","unavailable_reason":"not captured","evidence_ids":["e"]},
      {"block_id":"list","type":"ordered_list","source_order":6,"items":[{"text":"Cover label", "images":[]}],"evidence_ids":["e"]}])
    payload = response("Access is provided by the cover.")
    payload["replacements"].append({"block_id":"list","path":"/blocks/5/items/0/text","action":"retain","text":"Cover label","reason":"Exact component label"})
    candidate = run(source,payload).document
    assert candidate != source
    if mutation == "table": candidate["blocks"][2]["rows"][0][0] = "250 Nm"
    elif mutation == "callout": candidate["blocks"][3]["text"] = "Start the engine."
    elif mutation == "heading": candidate["blocks"][4]["text"] = "Installation"
    elif mutation == "media": candidate["blocks"][5]["unavailable_reason"] = "other"
    elif mutation == "evidence": candidate["blocks"][1]["evidence_ids"] = ["foreign"]
    elif mutation == "nested": candidate["blocks"][6]["items"][0]["images"] = [{"asset_id":"foreign"}]
    elif mutation == "order": candidate["blocks"][1:3] = reversed(candidate["blocks"][1:3])
    elif mutation == "extra": candidate["extra"] = "supplied structure"
    elif mutation == "id": candidate["blocks"][1]["block_id"] = "foreign"
    elif mutation == "schema_bool": candidate["schema_version"] = True
    elif mutation == "schema_float": candidate["schema_version"] = 1.0
    elif mutation == "order_bool": candidate["blocks"][1]["source_order"] = True
    elif mutation == "intro_evidence": candidate["blocks"][0]["evidence_ids"] = ["forged"]
    elif mutation == "intro_id": candidate["blocks"][0]["block_id"] = "forged"
    else: candidate["blocks"][0]["source_order"] = True
    assert not rewrite.validate_article_rewrite(source,candidate,profile_version=PROFILE).passed


def test_saved_response_is_recomputed_when_provided_for_independent_validation():
    from autodata_ingestion.procedure_rewrite_full import validate_full
    source = document("The cover provides access.")
    payload = response("Access is provided by the cover.")
    candidate = run(source,payload).document
    other = deepcopy(payload); other["replacements"][0]["text"] = "The cover permits access."
    assert not validate_full(source,candidate,response=other).passed


@pytest.mark.parametrize("payload", [None, [], "{}", {"introduction":True,"replacements":[]}, {"introduction":" ","replacements":[]}])
def test_invalid_response_shapes_never_produce_a_candidate(payload):
    source = document("The cover provides access.")
    result = run(source,payload)
    assert result.error_code and result.document == source


def test_explicit_profile_limits_and_invalid_source_do_not_dispatch():
    source = document("The cover provides access.")
    model = Draft(response("Access is provided by the cover."))
    invalid = deepcopy(source); invalid["blocks"][0]["evidence_ids"] = []
    assert rewrite.rewrite_ordered_document(invalid,client=model,context={},profile_version=PROFILE).error_code == "REWRITE_DOCUMENT_INVALID"
    huge = deepcopy(source); huge["metadata"] = "x" * (201*1024)
    assert rewrite.rewrite_ordered_document(huge,client=model,context={},profile_version=PROFILE).error_code == "REWRITE_INPUT_LIMIT"
    assert model.calls == 0
    oversized = Draft({"introduction":"x" * (1024*1024),"replacements":[]})
    result = rewrite.rewrite_ordered_document(source,client=oversized,context={},profile_version=PROFILE)
    assert result.error_code == "REWRITE_RESPONSE_LIMIT" and result.document == source
    assert rewrite.rewrite_ordered_document(source,client=None,context={},profile_version=PROFILE).error_code == "MODEL_NOT_CONFIGURED"
    assert rewrite.rewrite_ordered_document(source,client=model,context={}).error_code == "REWRITE_NOT_APPLICABLE"
    assert model.calls == 0


@pytest.mark.parametrize("original,changed", [
    ("25 quarts", "25 gallons"), ("20 mΩ", "20 kΩ"),
    ("T42/7", "T42 7"), ("25\u00a0Nm", "25 Nm"),
    ("1\u202f234.50 psi", "1 234.50 psi"),
])
def test_unfamiliar_units_identifiers_and_unicode_number_separators_stay_literal(original,changed):
    source = document(f"Use {original} for the cover.")
    payload = response(f"For the cover, use {changed} as specified.")
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_MUTATION"
    payload["replacements"][0]["text"] = f"For the cover, use {original} as specified."
    assert run(source,payload).error_code is None


@pytest.mark.parametrize("original,changed", [
    ("ABC/123", "XYZ/123"), ("123/ABC", "123/XYZ"),
    ("123-ABC/456", "123-XYZ/456"), ("123.ABC", "123.XYZ"),
    ("1KZ-TE", "1KZ-TD"), ("ABC/１２３", "XYZ/１２３"),
])
def test_complete_slash_and_leading_digit_identifiers_cannot_change(original,changed):
    source = document(f"Use tool {original} for the cover.")
    payload = response(f"For the cover, use tool {changed} as specified.")
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_MUTATION"
    payload["replacements"][0]["text"] = f"For the cover, use tool {original} as specified."
    assert run(source,payload).error_code is None
    payload["introduction"] = f"The article describes tool {changed} for cover access."
    assert run(source,payload).error_code == "REWRITE_TECHNICAL_MUTATION"


@pytest.mark.parametrize("field,value", [("type", []), ("type", {}), ("type", True),
    ("source_order", []), ("evidence_ids", True), ("evidence_ids", [{}]),
    ("block_id", []), ("text", {})])
@pytest.mark.parametrize("side", ["source", "candidate"])
def test_malformed_json_member_types_return_failed_validation_instead_of_raising(field,value,side):
    from autodata_ingestion.procedure_rewrite_full import render_full, validate_full
    source = document("The cover provides access.")
    payload = response("Access is provided by the cover.")
    candidate = render_full(source,payload)
    target = source if side == "source" else candidate
    target["blocks"][0][field] = value
    validation = validate_full(source,candidate,response=payload)
    assert not validation.passed
    assert "REWRITE_DOCUMENT_INVALID" in validation.error_codes
    assert not validation.report["structural_integrity_passed"]
    if side == "source":
        with pytest.raises(ValueError, match="REWRITE_DOCUMENT_INVALID"):
            render_full(source,payload)
        assert run(source,payload).error_code == "REWRITE_DOCUMENT_INVALID"


@pytest.mark.parametrize("original,changed", [
    ("T-42--ABC", "T-42--XYZ"), ("T-42//ABC", "T-42//XYZ"),
    ("T-42..ABC", "T-42..XYZ"), ("123--ABC/456", "123--XYZ/456"),
    ("ABC//123", "XYZ//123"), ("T-42-./ABC", "T-42-./XYZ"),
])
def test_repeated_separator_identifiers_preserve_every_letter_segment(original,changed):
    from autodata_ingestion.procedure_rewrite_full import render_full, validate_full
    source = document(f"Use tool {original} for the cover.")
    payload = response(f"For the cover, use tool {changed} as specified.")
    with pytest.raises(ValueError, match="REWRITE_TECHNICAL_MUTATION"):
        render_full(source,payload)
    payload["replacements"][0]["text"] = f"For the cover, use tool {original} as specified."
    candidate = render_full(source,payload)
    assert validate_full(source,candidate,response=payload).passed
    candidate["blocks"][1]["text"] = f"For the cover, use tool {changed} as specified."
    payload["replacements"][0]["text"] = candidate["blocks"][1]["text"]
    validation = validate_full(source,candidate,response=payload)
    assert not validation.passed and "REWRITE_TECHNICAL_MUTATION" in validation.error_codes


@pytest.mark.parametrize("table_only", [True, False])
def test_generated_introduction_is_a_stable_changed_content_slot_with_source_accounting(table_only):
    from autodata_ingestion.procedure_rewrite_full import render_full, validate_full
    if table_only:
        source = document()
        source["blocks"] = [{"block_id":"specs","source_order":1,"type":"table",
            "rows":[["Cover","25 Nm"]],"evidence_ids":["e-table"]}]
        payload = response(introduction="The table lists the cover torque of 25 Nm.")
        retained = []
    else:
        source = document("Exact cover label")
        payload = response("Exact cover label")
        payload["replacements"][0].update(action="retain",reason="Exact component label")
        retained = ["/blocks/0/text"]
    candidate = render_full(source,payload)
    for validation in (validate_full(source,candidate,response=payload),
                       validate_full(source,candidate)):
        assert validation.passed
        report = validation.report
        assert report["changed_slots"] == ["/introduction"]
        assert report["changed_prose_slots"] == []
        assert report["prose_slots"] == len(retained)
        assert report["retained_paths"] == retained
        assert report["content_acceptance_required"] and not report["complete_rewrite"]
    assert run(source,payload).changed_slots == ("/introduction",)
    corrupted = deepcopy(candidate)
    corrupted["blocks"][0]["block_id"] = "unbound-introduction"
    invalid = validate_full(source,corrupted,response=payload)
    assert not invalid.passed
    assert "/introduction" not in invalid.report["changed_slots"]


def test_known_legacy_and_current_prompt_hashes_only():
    from autodata_ingestion import procedure_rewrite_full as full
    source = document('Remove the cover.')
    context = {'vehicle': 'CTX-99'}
    # Golden bytes independently reconstructed from d123bbf and 02f863c.
    legacy = 'f6a6b43a53e6aea26b38a940fd2bad4a191ad3a1b8b92e358384c61613adf236'
    current = 'f58543a4405e730bcb68c1462a4aa435869a0a29325035c37d8f45fbb5cced93'
    assert full._matches_full_prompt_hash(source, context=context, prompt_hash=legacy)
    assert full._matches_full_prompt_hash(source, context=context, prompt_hash=current)
    assert not full._matches_full_prompt_hash(source, context=context, prompt_hash='0' * 64)
    assert not full._matches_full_prompt_hash(source, context={}, prompt_hash=legacy)
    from hashlib import sha256
    assert sha256(full.build_full_prompt(source, context=context).encode()).hexdigest() == current
