import pytest

from autodata_ingestion.procedure_rewrite_recovery import _equivalent_wording


@pytest.mark.parametrize(("original", "expected"), [
    ("Remove the left-side access cover.", "The left-side access cover must be removed."),
    ("NOTE: The clip is removed for clarity. Remove the rear panel.",
     "NOTE: For clarity, the clip is removed. The rear panel must be removed."),
    ("Ensure that the drain plug (8) has been removed.", "Confirm the removal of the drain plug (8)."),
    ("Mounting Bracket(32)»Install", "Install Mounting Bracket(32)."),
    ("Install a new cartridge and tighten 1/2 to 2 full turn after the gasket makes contact with the "
     "seating surface on the cartridge holder.(42)",
     "Fit a new cartridge. After the seating surface on the cartridge holder comes into contact "
     "with the gasket, tighten 1/2 to 2 full turn.(42)"),
    ("Oil Filter", "Filter for the oil"),
])
def test_equivalent_wording_keeps_source_parts_conditions_and_references(original, expected):
    assert _equivalent_wording(original) == expected


@pytest.mark.parametrize("original", [
    "Remove the panel only when the vehicle is supported.",
    "Remove the upper cover and disconnect the fitting.",
    "Do not remove the left cover.",
    "NOTE: The clip is removed for service. Remove the rear panel.",
    "Install a new cartridge and tighten 5 N·m before the gasket makes contact with the "
    "seating surface on the cartridge holder.",
    "Mounting Bracket(32)»Install or inspect",
])
def test_equivalent_wording_leaves_unrecognized_passages_to_the_original_checks(original):
    assert _equivalent_wording(original) is None
