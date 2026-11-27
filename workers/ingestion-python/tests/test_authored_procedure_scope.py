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
    (
        "For all other concentrations, use Example Concentrated Coolant and/or distilled water to achieve the "
        "desired concentration. Refer to Cooling System Service.",
        "For other target concentrations, adjust the mixture with Example Concentrated Coolant, distilled water, "
        "or both. See Cooling System Service.",
        [
            ("other target concentrations", "all concentrations"),
            ("Concentrated", "Prediluted"),
            ("distilled water", "tap water"),
            (", or both", ""),
            ("Cooling System Service", "Coolant Disposal"),
        ],
    ),
    (
        "With a cold system, add the coolant mixture to the fill line on the radiator surge tank.",
        "With a cold system, add enough coolant mixture to bring the level in the radiator surge tank up to its fill line.",
        [("cold", "warm"), ("fill line", "top"), ("radiator surge tank", "radiator")],
    ),
    (
        "Remove the bolts and the upper RH secondary timing chain guide.",
        "Take out the bolts and remove the upper RH secondary timing chain guide.",
        [("upper RH", "lower RH"), ("Take out the bolts and remove", "Remove")],
    ),
    (
        "Install the upper RH secondary timing chain guide and the bolts.",
        "Fit the upper RH secondary timing chain guide and install its bolts.",
        [("secondary", "primary"), ("and install its bolts", "before removing its bolts")],
    ),
    (
        "Install the balancer shaft lower housing and oil pump as an assembly (8).",
        "Fit the assembly (8) that consists of the balancer shaft lower housing and oil pump.",
        [("assembly (8)", "assembly (9)"), ("the assembly (8) that consists of", "")],
    ),
    (
        "Slide the wedge of the EN-12345 balance shaft holding tool (8) to the balance shaft weights and tighten the "
        "EN-12345 balance shaft holding tool thumb screw (9) to hold the balance shafts in position.",
        "Move the wedge on the EN-12345 balance shaft holding tool (8) by sliding it to the balance shaft weights. "
        "To keep the balance shafts in position, tighten the EN-12345 balance shaft holding tool thumb screw (9).",
        [("(8)", "(9)"), ("EN-12345", "EN-45678"), ("tighten", "loosen")],
    ),
    (
        "Loosen the EN-12345 balance shaft holding tool thumb screw (9), then slide the wedge of the "
        "EN-12345 balance shaft holding tool (8) away from the balance shaft weights.",
        "Loosen the EN-12345 balance shaft holding tool thumb screw (9) first. Afterward, slide the "
        "EN-12345 balance shaft holding tool (8) wedge away from the balance shaft weights.",
        [("away from", "toward"), ("first. Afterward,", "last. First,")],
    ),
    (
        "For vehicles repaired under bumper-to-bumper coverage (Canada Base Warranty coverage), use the following "
        "labor operation. Reference the Applicable Warranties section of Investigate Vehicle History (IVH) "
        "for coverage information.",
        "Use the labor operation below when bumper-to-bumper coverage (Canada Base Warranty coverage) applies "
        "to the repair. For coverage information, see the Applicable Warranties section of Investigate Vehicle History (IVH).",
        [("when", "whether or not"), ("Applicable Warranties", "Service History")],
    ),
])
def test_publication_preserves_authored_procedure_details(source, rewrite, mutations):
    original = {"blocks": [{"items": [source]}]}
    candidate = {"blocks": [{"text": "Introduction"}, {"items": [rewrite]}]}
    paths = ["/blocks/0/items/0"]
    require_authored_procedure_scope(original, candidate, rewritten_paths=paths)
    for before, after in mutations:
        assert before in rewrite
        candidate["blocks"][1]["items"][0] = rewrite.replace(before, after, 1)
        with pytest.raises(ValueError, match="REWRITE_CLAUSE_MUTATION"):
            require_authored_procedure_scope(original, candidate, rewritten_paths=paths)
