"""Reword complete recurring cooling clauses without changing their facts."""

import re

from . import procedure_rewrite_auto as auto, procedure_rewrite_full as full


_WORD = r"[a-z]+(?:-[a-z]+)*"
_PHRASE = rf"{_WORD}(?: {_WORD}){{0,11}}"
_COUNT = r"[1-9][0-9]{0,3}"
_FLAGS = re.IGNORECASE | re.ASCII

_RATIO_BOUND = re.compile(
    rf"(?P<bound>Maximum|Minimum) (?P<subject>{_PHRASE}) is "
    rf"(?P<ratio>[0-9]+/[0-9]+) for (?P<scope>{_PHRASE})\.",
    _FLAGS,
)
_CLOSE = re.compile(rf"Close the (?P<part>{_PHRASE})\.", _FLAGS)
_INSTALL_TO_STOP = re.compile(
    rf"Install the (?P<part>{_PHRASE}) until "
    rf"(?P<endpoint>it (?:contacts|touches) the (?:{_WORD} ){{0,5}}stop)\.",
    _FLAGS,
)
_START_AND_IDLE = re.compile(
    rf"Start the (?P<part>{_PHRASE}) and let it idle until the "
    rf"(?P<primary>{_PHRASE}) reaches (?P<threshold>{_PHRASE}) and the "
    rf"(?P<secondary>{_PHRASE}) is fully open\. "
    rf"A (?P<state>fully open (?P<verified>{_PHRASE})) is verified by the "
    rf"(?P<indicator>{_PHRASE}) cycling on at least once\.",
    _FLAGS,
)
_REPEAT_TO_REMOVE = re.compile(
    rf"Repeat (?P<counted>Steps (?P<first>{_COUNT}) through (?P<last>{_COUNT}) "
    rf"a total of {_COUNT} times) to remove (?P<contents>{_PHRASE})\.",
    _FLAGS,
)
_SECTION_LABEL = re.compile(
    rf"Filling and Bleeding (?P<scope>(?:with|without|using) (?:a|an|the) {_PHRASE})",
    _FLAGS,
)
# Object names in the active-to-passive and split-command forms must not
# contain an extra direction, exception, or prerequisite clause.
_CLAUSE_WORDS = frozenset(
    ("after and before because except if instead never not only or otherwise "
     "unless until using when while with without").split()
)


def _object_name(text: str) -> bool:
    return _CLAUSE_WORDS.isdisjoint(text.casefold().split())


def _recast_directive(source: str) -> str | None:
    if (closure := _CLOSE.fullmatch(source)) and _object_name(closure["part"]):
        return f"The {closure['part']} must be closed."

    if (installation := _INSTALL_TO_STOP.fullmatch(source)) and _object_name(installation["part"]):
        return f"Install the {installation['part']}. Continue until {installation['endpoint']}."

    if start := _START_AND_IDLE.fullmatch(source):
        # The observation must verify the same open state used to end idling.
        if start["secondary"].casefold() != start["verified"].casefold() or not all(
            _object_name(start[key]) for key in ("part", "primary", "threshold", "secondary", "indicator")
        ):
            return None
        return (
            f"Start the {start['part']}. Keep it idling until both conditions are met: "
            f"the {start['primary']} has reached {start['threshold']}, and the {start['secondary']} "
            f"is fully open. The {start['indicator']} cycling on at least once verifies a {start['state']}."
        )

    if repeated := _REPEAT_TO_REMOVE.fullmatch(source):
        # The range, count and their protected adjacent words move together.
        if int(repeated["first"]) <= int(repeated["last"]) and _object_name(repeated["contents"]):
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
