"""Source-bound whole-clause v2 regressions; fixtures are synthetic, not acceptance."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from autodata_ingestion import procedure_rewrite as rewrite

PROFILE = "technical-prose-v2"


def document(*texts):
    return {"schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": [
        {"block_id": f"p{i}", "source_order": i + 1, "type": "paragraph", "text": text,
         "evidence_ids": ["fixture-evidence"]} for i, text in enumerate(texts)]}


class Selector:
    _model = "fixture"
    calls = 0

    def complete_json(self, prompt):
        self.calls += 1
        return {"operations": [{key: row[key] for key in ("block_id", "path", "operation_id")}
                               for row in json.loads(prompt)["plan"]["operations"]]}


def test_v2_whole_clause_routing_is_explicit_and_v1_stays_immutable():
    source = document("Tighten the bolts to 25 Nm.")
    model = Selector()
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert result.error_code is None
    assert model.calls == 1
    assert result.document["blocks"][0]["text"] == "The bolts are to be tightened to 25 Nm."
    assert rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).passed
    assert not rewrite.validate_article_rewrite(source, result.document, profile_version="technical-prose-v1").passed


@pytest.mark.parametrize("verb,past", [("Remove", "removed"), ("Install", "installed"),
    ("Disconnect", "disconnected"), ("Connect", "connected"), ("Loosen", "loosened"),
    ("Tighten", "tightened"), ("Replace", "replaced"), ("Inspect", "inspected"),
    ("Clean", "cleaned"), ("Lubricate", "lubricated")])
def test_all_reviewed_directives_are_complete_clauses(verb, past):
    from autodata_ingestion.procedure_rewrite_v2 import plan_v2, render_v2, validate_v2
    source = document(f"{verb} the cover.")
    plan = plan_v2(source)
    assert plan["eligible"]
    op = plan["operations"][0]
    assert source["blocks"][0]["text"][op["source_span"][0]:op["source_span"][1]] == f"{verb} the cover."
    response = Selector().complete_json(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    candidate = render_v2(source, response)
    assert candidate["blocks"][0]["text"] == f"The cover is to be {past}."
    report = validate_v2(source, candidate).report
    assert report["changed_clauses"] == 1 and report["complete_rewrite"]
    assert report["unsupported_paths"] == []


@pytest.mark.parametrize("torque", ["25 Nm", "-2.5–+3.0 N·m", "+25 N m", "10–20 lb-ft", "8 lb-in"])
def test_torque_span_is_byte_identical(torque):
    result = rewrite.rewrite_ordered_document(document(f"Tighten the bolts to {torque}."),
        client=Selector(), context={}, profile_version=PROFILE)
    assert result.error_code is None
    assert result.document["blocks"][0]["text"] == f"The bolts are to be tightened to {torque}."


@pytest.mark.parametrize("text", ["Remove the cover and disconnect the cable.",
    "Remove the cover to inspect the pump.", "Remove the cover with the bolts.",
    "Remove it.", "Remove the special widget.", "Remove the cover. Install the pump.",
    "Remove the cover\n", "Remove the ‘cover’.", "The cover provides access.",
    "Tighten the bolts to 25 N.m.", "Tighten the bolts to 25Nm.",
    "Tighten the bolts to 25 Nm with a wrench.", "Inspect the connector for damage.",
    "Remove the cover using tool T-42."])
def test_unsupported_ordinary_prose_falls_back_without_model(text):
    from autodata_ingestion.procedure_rewrite_v2 import plan_v2
    source = document("Install the pump.", text)
    model = Selector()
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_UNSUPPORTED_PROSE"
    assert result.document == source and model.calls == 0
    plan = plan_v2(source)
    assert not plan["eligible"] and plan["unsupported_paths"] == ["/blocks/1/text"]
    assert not rewrite.validate_article_rewrite(source, source, profile_version=PROFILE).report["complete_rewrite"]


def test_retained_safety_nested_lists_tables_and_images_are_immutable():
    source = document("Remove the cover.", "Do not disconnect the cable.", "If equipped, remove the pump.")
    source["blocks"].extend([
        {"block_id":"w", "source_order":4,"type":"callout", "text":"Warning: Disconnect the cable.", "evidence_ids":["e"]},
        {"block_id":"t", "source_order":5,"type":"table", "rows":[["25 Nm", "Remove the cover."]], "evidence_ids":["e"]},
        {"block_id":"i", "source_order":6,"type":"image", "status":"unavailable", "unavailable_reason":"missing", "evidence_ids":["e"]},
        {"block_id":"l", "source_order":7,"type":"ordered_list", "items":[{"text":"Install the pump.", "blocks":[
            {"block_id":"n", "source_order":1,"type":"unordered_list", "items":["Clean the cover."], "evidence_ids":["e"]}]}], "evidence_ids":["e"]}])
    result = rewrite.rewrite_ordered_document(source, client=Selector(), context={}, profile_version=PROFILE)
    assert result.error_code is None
    assert result.document["blocks"][1:6] == source["blocks"][1:6]
    assert result.document["blocks"][6]["items"][0]["blocks"][0]["items"] == ["The cover is to be cleaned."]
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["changed_clauses"] == 3 and report["retained_protected_clauses"] == 2
    assert report["source_protected_hash"] == report["target_protected_hash"]


@pytest.mark.parametrize("mode", ["missing", "duplicate", "reorder", "extra_text", "extra_top", "foreign_source", "foreign_path", "foreign_block"])
def test_model_can_only_select_exact_bound_operations(mode):
    source = document("Remove the cover.", "Install the pump.")
    class Bad(Selector):
        def complete_json(self, prompt):
            response = super().complete_json(prompt)
            rows = response["operations"]
            if mode == "missing": rows.pop()
            elif mode == "duplicate": rows[1] = deepcopy(rows[0])
            elif mode == "reorder": rows.reverse()
            elif mode == "extra_text": rows[0]["text"] = "New wording"
            elif mode == "extra_top": response["profile"] = PROFILE
            elif mode == "foreign_path": rows[0]["path"] = "/blocks/1/text"
            elif mode == "foreign_block": rows[0]["block_id"] = "other"
            else: rows[0]["operation_id"] = "op-unbound"
            return response
    result = rewrite.rewrite_ordered_document(source, client=Bad(), context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_OPERATION_MISMATCH" and result.document == source


@pytest.mark.parametrize("mode", ["number", "unit", "part", "negation", "order", "evidence", "extra", "unchanged"])
def test_validation_independently_reconstructs_every_document_member(mode):
    source = document("Tighten the bolts to 25 Nm.", "Remove the cover.")
    candidate = rewrite.rewrite_ordered_document(source, client=Selector(), context={}, profile_version=PROFILE).document
    if mode == "number": candidate["blocks"][0]["text"] = "The bolts are to be tightened to 250 Nm."
    elif mode == "unit": candidate["blocks"][0]["text"] = "The bolts are to be tightened to 25 lb-ft."
    elif mode == "part": candidate["blocks"][1]["text"] = "The pump is to be removed."
    elif mode == "negation": candidate["blocks"][1]["text"] = "The cover is not to be removed."
    elif mode == "order": candidate["blocks"].reverse()
    elif mode == "evidence": candidate["blocks"][0]["evidence_ids"] = ["forged"]
    elif mode == "extra": candidate["metadata"] = "unbound"
    else: candidate = deepcopy(source)
    assert not rewrite.validate_article_rewrite(source, candidate, profile_version=PROFILE).passed


def test_operation_id_binds_source_hash_and_exact_unicode_offsets():
    from autodata_ingestion.procedure_rewrite_v2 import plan_v2, render_v2
    source = document("Tighten the bolts to 2 N·m.")
    other = deepcopy(source); other["blocks"][0]["evidence_ids"] = ["other"]
    response = Selector().complete_json(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert plan_v2(source)["operations"][0]["operation_id"] != plan_v2(other)["operations"][0]["operation_id"]
    with pytest.raises(ValueError, match="REWRITE_OPERATION_MISMATCH"):
        render_v2(other, response)


def test_unknown_profile_and_limits_never_call_model():
    model = Selector()
    source = document("Remove the cover.")
    assert rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version="technical-prose-v99").error_code == "REWRITE_PROFILE_UNSUPPORTED"
    source["metadata"] = "x" * (201*1024)
    assert rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE).error_code == "REWRITE_INPUT_LIMIT"
    assert model.calls == 0


def test_frozen_development_corpus_hashes_eligibility_and_protected_context():
    from autodata_ingestion.article_lifecycle_types import digest_json
    corpus = json.loads((Path(__file__).parent / "fixtures/article_rewrite_v2.json").read_text())
    assert corpus["authentic_documents"] == 0  # Never promote synthetic data to acceptance.
    for row in corpus["documents"]:
        source = row["document"]
        assert digest_json(source) == row["source_hash"]
        result = rewrite.rewrite_ordered_document(source, client=Selector(), context={}, profile_version=PROFILE)
        if row["expected_v2_eligible"]:
            assert result.error_code is None, row["identity"]
            assert result.document["blocks"][-3:] == source["blocks"][-3:]
            assert rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).passed
        else:
            assert result.error_code == "REWRITE_UNSUPPORTED_PROSE", row["identity"]
            assert result.document == source


@pytest.mark.parametrize("text", ["Remove the cover. Note: Do not start the engine.",
    "Note: Do not start the engine. Remove the cover.",
    "Do not start the engine; remove the cover.",
    "Do not start the engine and remove the cover.",
    "If equipped, remove the cover\nInstall the pump."])
def test_mixed_safety_and_ordinary_clauses_never_earn_complete_rewrite(text):
    source = document("Inspect the pump.", text)
    model = Selector()
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_UNSUPPORTED_PROSE"
    assert result.document == source and model.calls == 0
    report = rewrite.validate_article_rewrite(source, source, profile_version=PROFILE).report
    assert not report["complete_rewrite"] and report["unsupported_paths"] == ["/blocks/1/text"]


@pytest.mark.parametrize("payload", [None, [], "{}", {"operations": None}, {"operations": []}])
def test_invalid_selector_shape_retains_source(payload):
    class Bad(Selector):
        def complete_json(self, prompt): return payload
    source = document("Inspect the pump.")
    result = rewrite.rewrite_ordered_document(source, client=Bad(), context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_OPERATION_MISMATCH" and result.document == source


def test_safety_only_document_is_not_a_complete_rewrite():
    source = document("Do not start the engine.", "If equipped, remove the pump.")
    model = Selector()
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_NOT_APPLICABLE" and result.document == source and model.calls == 0
    assert not rewrite.validate_article_rewrite(source, source, profile_version=PROFILE).report["complete_rewrite"]


def test_v2_oversized_response_falls_back_before_render():
    class Oversized(Selector):
        def complete_json(self, prompt): return {"operations": [], "text": "x" * (1024*1024)}
    source = document("Inspect the pump.")
    result = rewrite.rewrite_ordered_document(source, client=Oversized(), context={}, profile_version=PROFILE)
    assert result.error_code == "REWRITE_RESPONSE_LIMIT" and result.document == source


def test_validation_reports_whole_document_classification_counts_even_on_fallback():
    source = document("Inspect the pump.", "Do not start the engine.", "The cover provides access.")
    report = rewrite.validate_article_rewrite(source, source, profile_version=PROFILE).report
    assert report.get("prose_clauses") == 3
    assert report.get("eligible_clauses") == 1
    assert report.get("unsupported_clauses") == 1
    assert report["retained_protected_clauses"] == 1 and report["changed_clauses"] == 0
    assert not report["complete_rewrite"]
