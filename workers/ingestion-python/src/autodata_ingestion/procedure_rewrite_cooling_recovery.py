"""Reword complete recurring cooling clauses without changing their facts."""

import re

from . import procedure_rewrite_auto as auto, procedure_rewrite_full as full
from .procedure_rewrite_fidelity import (
    _FLAGS, _PHRASE, _contact_instruction, _idle_instruction, _object_name, _repeat_instruction,
)

_RATIO_BOUND = re.compile(
    rf"(?P<bound>Maximum|Minimum) (?P<subject>{_PHRASE}) is "
    rf"(?P<ratio>[0-9]+/[0-9]+) for (?P<scope>{_PHRASE})\.",
    _FLAGS,
)
_CLOSE = re.compile(rf"Close the (?P<part>{_PHRASE})\.", _FLAGS)
_SECTION_LABEL = re.compile(
    rf"Filling and Bleeding (?P<scope>(?:with|without|using) (?:a|an|the) {_PHRASE})",
    _FLAGS,
)


def _recast_directive(source: str) -> str | None:
    if (closure := _CLOSE.fullmatch(source)) and _object_name(closure["part"]):
        return f"The {closure['part']} must be closed."

    if installation := _contact_instruction(source):
        return f"Install the {installation['part']}. Continue until {installation['endpoint']}."

    if start := _idle_instruction(source):
        return (
            f"Start the {start['part']}. Keep it idling until both conditions are met: "
            f"the {start['primary']} has reached {start['threshold']}, and the {start['secondary']} "
            f"is fully open. The {start['indicator']} cycling on at least once verifies a {start['state']}."
        )

    if repeated := _repeat_instruction(source):
        return f"Remove {repeated['contents']} by repeating {repeated['counted']}."
    return None


def recast_cooling_passage(source: str, error_code: str) -> str | None:
    """Return a source-only rewording for an exact known cooling clause."""
    if error_code == "REWRITE_TECHNICAL_MUTATION" and (bound := _RATIO_BOUND.fullmatch(source)):
        subject = bound["subject"]
        if not _object_name(subject) or subject.casefold().split()[0] in {"a", "an", "the"}:
            return None
        # The token grammar includes the word "for" in the protected ratio.
        wording = f"The {subject} has a {bound['bound'].casefold()} of {bound['ratio']} for {bound['scope']}."
    elif error_code == "REWRITE_ACTION_MUTATION":
        wording = _recast_directive(source)
    elif error_code == "REWRITE_UNCHANGED" and (label := _SECTION_LABEL.fullmatch(source)):
        wording = f"How to fill and bleed {label['scope']}"
    else:
        return None

    if wording and full._technical_tokens(source) == full._technical_tokens(wording) and (
        auto._execution_order(source) == auto._execution_order(wording)
    ):
        return wording
    return None
