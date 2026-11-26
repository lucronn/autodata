import pytest

from autodata_ingestion.authored_procedure_scope import (
    correct_authored_procedure_step, require_authored_procedure_scope,
)


@pytest.mark.parametrize(("source", "drift", "expected"), [
    (
        "Sleeve(1)@Housing(2)»Remove", "Remove the sleeve (1) and housing (2).",
        "Remove the Sleeve (1) from the Housing (2).",
    ),
    (
        "Cable(3)@Support(4)»Install", "Fit both the cable (3) and support (4).",
        "Install the Cable (3) at the Support (4).",
    ),
    (
        "Sleeve (1) » Install — Sleeve Assembly Procedure", "Install the sleeve (1) and replace it.",
        "Install the component identified by (1) as described in Sleeve Assembly Procedure.",
    ),
    (
        "When sure the indicator is off, open the cover.", "Once the indicator is off, open the cover.",
        "Verify that the indicator is off. Then open the cover.",
    ),
    (
        "When sure the indicator is off, open the cover.", "Open the cover and confirm the indicator is off.",
        "Verify that the indicator is off. Then open the cover.",
    ),
])
def test_repair_and_guard_bind_the_source_step(source, drift, expected):
    assert correct_authored_procedure_step(source, drift) == expected
    assert correct_authored_procedure_step(source, expected) is None
    original = {"blocks": [{"items": [source]}]}
    document = {"blocks": [{"text": "Introduction"}, {"items": [drift]}]}
    with pytest.raises(ValueError, match="REWRITE_CLAUSE_MUTATION"):
        require_authored_procedure_scope(original, document, rewritten_paths=["/blocks/0/items/0"])
    document["blocks"][1]["items"][0] = expected
    require_authored_procedure_scope(original, document, rewritten_paths=["/blocks/0/items/0"])


@pytest.mark.parametrize(("source", "wording"), [
    ("Sleeve (1)@Housing (2) » Remove", "Take the sleeve [1] out of the housing [2]."),
    ("When sure the indicator is off, open the cover.", "Before opening the cover, confirm the indicator is off."),
    ("Cover » Close — Cover Inspection", "Follow Cover Inspection to close the cover."),
    ("When the indicator is off, open the cover.", "Open the cover once the indicator goes out."),
    ("Sleeve (1) and Housing (2) » Remove", "Take off the sleeve (1) and housing (2)."),
])
def test_equivalent_or_unscoped_wording_is_preserved(source, wording):
    assert correct_authored_procedure_step(source, wording) is None
