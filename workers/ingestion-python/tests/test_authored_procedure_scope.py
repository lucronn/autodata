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


@pytest.mark.parametrize(("source", "rewrite", "mutations"), [
    (
        "Mark the timing chain link aligned with the timing mark on the left-hand exhaust VCT assembly, as shown.",
        "Using this diagram as a guide, mark the link in the timing chain that lines up with the timing mark of the LH exhaust VCT assembly.",
        [
            ("lines up with", "sits next to"),
            ("LH exhaust", "RH exhaust"),
            ("LH exhaust", "LH intake"),
            ("Using this diagram as a guide, mark", "Mark"),
        ],
    ),
    (
        "The LIN bus uses one wire. Typical circuit problems include open circuits, high resistance, shorts to "
        "ground or power, poor terminal drag, or connectors that are not fully seated. Check for the listed faults "
        "using proper terminal test probes.",
        "The LIN bus communicates over a single wire. Inspect these potential connection and circuit faults. "
        "Examples include opens, high resistance, shorts to ground/power, poor terminal drag, and connectors "
        "not fully seated. Use the proper terminal test probes to check for these failures.",
        [
            ("a single wire", "two wires"),
            ("ground/power", "power"),
            ("not fully seated", "fully seated"),
            ("Use the proper terminal test probes to check", "Check"),
        ],
    ),
    (
        "Test or monitor the LIN bus reference voltage. This can help identify the type of fault to check for.",
        "Testing or monitoring the reference voltage on the LIN bus can help determine which fault to inspect for.",
        [
            ("reference voltage", "battery voltage"),
            ("or monitoring", ""),
        ],
    ),
])
def test_publication_preserves_specific_diagnostic_facts(source, rewrite, mutations):
    original = {"blocks": [{"items": [source]}]}
    candidate = {"blocks": [{"text": "Introduction"}, {"items": [rewrite]}]}
    paths = ["/blocks/0/items/0"]
    require_authored_procedure_scope(original, candidate, rewritten_paths=paths)
    for before, after in mutations:
        assert before in rewrite
        candidate["blocks"][1]["items"][0] = rewrite.replace(before, after, 1)
        with pytest.raises(ValueError, match="REWRITE_CLAUSE_MUTATION"):
            require_authored_procedure_scope(original, candidate, rewritten_paths=paths)
