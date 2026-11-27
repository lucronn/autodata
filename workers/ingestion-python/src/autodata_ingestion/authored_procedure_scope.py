"""Preserve authored location markers, procedure referrals and explicit checks."""

import re

from .procedure_rewrite_full import _get
from .service_procedure_scope import service_procedure_facts


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
_TIMING_MARK = re.compile(
    r"(?:(?P<guide>using (?:the|this) (?:illustration|diagram) as a guide), )?"
    r"mark the (?:(?:timing )?chain link|link in the timing chain) "
    r"(?:that (?:aligns|lines up) with|(?:that is )?(?:aligned|in line) with) "
    r"the timing mark (?:on|of) the "
    r"(?P<side>lh|rh|left(?:[ -]hand)?|right(?:[ -]hand)?) (?P<cam>intake|exhaust) vct assembly"
    r"(?P<shown>,? as (?:shown|illustrated))?\.?"
)
_LIN_WIRE = re.compile(r"the lin bus (?:is|uses|communicates (?:on|over)) (?:a single|one) wire\b")
_LIN_FAILURES = re.compile(
    r"\b(?:opens|open circuits), high resistance, shorts? to ground(?:/| or )power, "
    r"poor terminal drag, (?:(?:or|and) )?connectors (?:that are )?not fully seated\b"
)
_CHECK_FAILURES = r"(?:inspect|check) for (?:these (?:types? of )?|such |the (?:listed|above) )(?:faults|failures)"
_TERMINAL_PROBES = r"(?:the )?proper terminal test probes"
_LIN_PROBE_CHECK = re.compile(
    rf"(?:us(?:e|ing) {_TERMINAL_PROBES},? (?:to )?{_CHECK_FAILURES}"
    rf"|{_CHECK_FAILURES} (?:with|using) {_TERMINAL_PROBES})\.?"
)
_LIN_REFERENCE_CHECK = re.compile(
    r"test(?:ing)?(?:/| or )monitor(?:ing)? (?:the )?"
    r"(?:lin bus reference voltage|reference voltage (?:on|of) the lin bus)"
    r"(?:\. (?:the result|this))? can help (?:determine|identify) "
    r"(?:(?:what|which) type of |which |the type of )(?:failure|fault) to (?:inspect|check) for\.?"
)
_COOLANT_CONCENTRATION = re.compile(
    r"for (?:all |any )?other (?:target )?concentrations?, "
    r"(?:use|adjust the mixture with) (?P<coolant>[^,]+?)"
    r"(?: and/or distilled water (?:to|t) (?:get to|achieve) the desired concentration|, distilled water, or both)"
    r"\. (?:refer to|see) (?P<reference>[^.]+)\.?"
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


def _timing_mark_target(text):
    match = _TIMING_MARK.fullmatch(text)
    if match is None:
        return None
    side = "lh" if match["side"].startswith("l") else "rh"
    return side, match["cam"], bool(match["guide"] or match["shown"])


def _checks_lin_wiring(text):
    return (
        _LIN_WIRE.match(text) is not None
        and _LIN_FAILURES.search(text) is not None
        and _LIN_PROBE_CHECK.fullmatch(text.rsplit(". ", 1)[-1]) is not None
    )


def _coolant_concentration(text):
    match = _COOLANT_CONCENTRATION.fullmatch(text)
    return (match["coolant"], match["reference"]) if match else None


def require_authored_procedure_scope(source, document, *, rewritten_paths):
    """Check new publications without changing validation of historical replies."""
    candidate = {"blocks": document["blocks"][1:]}
    for path in rewritten_paths:
        original, wording = _get(source, path), _get(candidate, path)
        if correct_authored_procedure_step(original, wording) is not None:
            raise ValueError("REWRITE_CLAUSE_MUTATION")
        original, wording = _words(original), _words(wording)
        if (target := _timing_mark_target(original)) is not None and _timing_mark_target(wording) != target:
            raise ValueError("REWRITE_CLAUSE_MUTATION")
        if _checks_lin_wiring(original) and not _checks_lin_wiring(wording):
            raise ValueError("REWRITE_CLAUSE_MUTATION")
        if _LIN_REFERENCE_CHECK.fullmatch(original) and not _LIN_REFERENCE_CHECK.fullmatch(wording):
            raise ValueError("REWRITE_CLAUSE_MUTATION")
        if (mixture := _coolant_concentration(original)) is not None and _coolant_concentration(wording) != mixture:
            raise ValueError("REWRITE_CLAUSE_MUTATION")
        if (service := service_procedure_facts(original)) is not None and service_procedure_facts(wording) != service:
            raise ValueError("REWRITE_CLAUSE_MUTATION")
