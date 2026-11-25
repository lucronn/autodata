"""Exercise the source-only conditional coolant note recast."""

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import SOURCE_BOUND_CORRECTION_PROFILE
from autodata_ingestion.procedure_rewrite_fidelity import recast_conditional_color_note
from test_procedure_rewrite_full import document, response


_PRODUCT = "OrchidVale™ Yellow ReadyMix Antifreeze/Coolant"
_OBSERVATION = f"During normal vehicle operation, {_PRODUCT} may change color from Yellow to Violet or light Blue."
_CONDITION = "As long as the coolant is clear and clean, this observation alone does not require service."
_SOURCE = f"Note: {_OBSERVATION} {_CONDITION}"


@pytest.mark.parametrize("product", (
    _PRODUCT,
    "OrchidVale ® Yellow ReadyMix Antifreeze/Coolant",
    "OrchidVale Yellow ReadyMix Coolant",
))
@pytest.mark.parametrize("label,separator", (("Note: ", " "), ("  NOTE :\t", "\r\n  ")))
def test_source_recast_preserves_all_facts_and_authored_condition(product, label, separator):
    original = f"{label}{_OBSERVATION.replace(_PRODUCT, product)}{separator}{_CONDITION}"

    assert recast_conditional_color_note(original) == (
        f"{label}During normal vehicle operation, it is possible for {product} to change color "
        f"from Yellow to either Violet or light Blue.{separator}{_CONDITION}"
    )


@pytest.mark.parametrize("original", (
    _SOURCE.removeprefix("Note: "),
    _SOURCE.replace("normal vehicle operation", "heavy load"),
    _SOURCE.replace("may change color", "must change color"),
    _SOURCE.replace("may change color", "may change level"),
    _SOURCE.replace(" or light Blue", " and light Blue"),
    _SOURCE.replace("Violet or light Blue", "Violet"),
    _SOURCE.replace(" or light Blue", " or yellow"),
    _SOURCE.replace("Violet", "a striped shade"),
    _SOURCE.replace(_PRODUCT, f"only {_PRODUCT}"),
    _SOURCE.replace(_PRODUCT, f"other coolant and {_PRODUCT}"),
    _SOURCE.replace(_PRODUCT, f"other coolant/or {_PRODUCT}"),
    _SOURCE.replace("Antifreeze/Coolant", "Antifreeze"),
    _SOURCE.replace("As long as ", "If "),
    _SOURCE.replace(" and clean,", ","),
    _SOURCE.replace("clear and clean,", "clear and clean."),
    _SOURCE + " Read the label.",
))
def test_source_recast_refuses_unproved_grammar(original):
    assert recast_conditional_color_note(original) is None


def test_only_the_exact_recast_passes_archived_reply_validation():
    source = document(_SOURCE)
    wording = recast_conditional_color_note(_SOURCE)
    draft = response(wording)
    options = dict(
        prompt_version=auto._NOTE_LABEL_PROMPT_VERSION,
        profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
    )
    with pytest.raises(ValueError, match="^REWRITE_QUALIFIER_MUTATION$"):
        auto.render_auto(source, draft, **options)

    options["verified_color_notes"] = True
    candidate = auto.render_auto(source, draft, **options)
    assert auto.validate_auto(source, candidate, response=draft, **options).passed
    assert candidate["blocks"][1]["text"] == wording


@pytest.mark.parametrize(("old", "new"), (
    ("it is possible", "it is certain"),
    ("light Blue", "dark Blue"),
    ("Yellow to either Violet", "Violet to either Yellow"),
    ("Antifreeze/Coolant", "Antifreeze"),
    (" and clean", " or clean"),
    ("does not require", "requires"),
    (". As long as", ".  As long as"),
))
def test_archived_reply_validation_rejects_drift_in_either_sentence(old, new):
    source = document(_SOURCE)
    wording = recast_conditional_color_note(_SOURCE)
    draft = response(wording.replace(old, new))
    with pytest.raises(ValueError, match="^REWRITE_QUALIFIER_MUTATION$"):
        auto.render_auto(
            source, draft, prompt_version=auto._NOTE_LABEL_PROMPT_VERSION,
            profile_version=SOURCE_BOUND_CORRECTION_PROFILE, verified_color_notes=True,
        )
