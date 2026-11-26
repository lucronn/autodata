"""Preserve authored location markers, procedure referrals and explicit checks."""

import re

from .procedure_rewrite_full import _get


_ACTION = re.compile(r"(remove|install|open|close)(?:\s*—\s*(\S.*))?", re.I)
_LOCATED_PART = re.compile(r"(.+?)\s*\((\d+)\)\s*@\s*(.+?)\s*\((\d+)\)")
_NUMBERED_PART = re.compile(r"(.+?)\s*(\(\d+\))")
_VERIFY_FIRST = re.compile(
    r"(?:when|once)\s+(?:you are\s+)?(?:sure|certain)\s+(?:that\s+)?([^,]+),\s*(\S.*)", re.I,
)
_TEMPORAL_CLAUSE = re.compile(r"(?:when|once|after)\s+([^,]+),\s*(\S.*)", re.I)
_VERIFICATION = re.compile(
    r"^(?:before\s+[^,]+,\s*)?(?:(?:first|when|once|after)\b[ ,]+)?(?:you\s+(?:are|have)\s+)?"
    r"(?:make\s+)?(?:sure|certain|verify|verified|verifying|confirm|confirmed|confirming|ensure|ensuring|check|checking)\b",
    re.I,
)


def _words(text):
    return " ".join(text.casefold().split())


def _callout(number):
    return rf"\s*(?:\({number}\)|\[{number}\])"


def _keeps_location(wording, part, part_number, location, location_number):
    relation = r"\s*(?:@\s*|(?:at|in|on|to|from|into|onto|off(?: of)?|out of)\s+(?:the\s+)?)"
    return re.search(
        re.escape(_words(part)) + _callout(part_number) + relation
        + re.escape(_words(location)) + _callout(location_number),
        _words(wording),
    ) is not None


def correct_authored_procedure_step(original, wording):
    """Return a recast only for a supported source instruction that lost scope."""
    verify = _VERIFY_FIRST.fullmatch(original.strip())
    if verify and not _VERIFICATION.match(wording.strip()):
        rewritten_clause = _TEMPORAL_CLAUSE.fullmatch(wording.strip())
        condition, instruction = (rewritten_clause or verify).groups()
        return f"Verify that {condition.strip()}. Then {instruction}"

    component, separator, operation = original.partition("»")
    action = _ACTION.fullmatch(operation.strip()) if separator else None
    if action is None:
        return None
    verb, reference = action.groups()
    location = _LOCATED_PART.fullmatch(component.strip())
    location_lost = location and not _keeps_location(wording, *location.groups())
    reference_lost = reference and _words(reference) not in _words(wording)
    if not (location_lost or reference_lost):
        return None

    if location:
        part, part_number, position, position_number = location.groups()
        preposition = "from" if verb.casefold() == "remove" else "at"
        target = f"{part} ({part_number}) {preposition} the {position} ({position_number})"
    else:
        target = component.strip()
        numbered = _NUMBERED_PART.fullmatch(target)
        if reference and numbered and _words(reference).startswith(_words(numbered[1]) + " "):
            target = f"component identified by {numbered[2]}"
    follow = " as described in " + reference.rstrip(".") if reference else ""
    return f"{verb.capitalize()} the {target}{follow}."


def require_authored_procedure_scope(source, document, *, rewritten_paths):
    """Check new publications without changing validation of historical replies."""
    candidate = {"blocks": document["blocks"][1:]}
    for path in rewritten_paths:
        if correct_authored_procedure_step(_get(source, path), _get(candidate, path)) is not None:
            raise ValueError("REWRITE_CLAUSE_MUTATION")
