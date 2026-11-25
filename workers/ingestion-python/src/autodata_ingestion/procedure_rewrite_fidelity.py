"""Bind recognized procedure actions and conditions to the facts they govern."""

import re


_WORD = r"[a-z]+(?:-[a-z]+)*"
_PHRASE = rf"{_WORD}(?: {_WORD}){{0,11}}"
_COUNT = r"[1-9][0-9]{0,3}"
_FLAGS = re.IGNORECASE | re.ASCII
_CLAUSE_WORDS = frozenset(
    ("after and before because except if instead never not only or otherwise "
     "unless until using when while with without").split()
)


def _object_name(text: str) -> bool:
    return _CLAUSE_WORDS.isdisjoint(text.casefold().split())


_CONTACT = rf"(?P<endpoint>it (?:contacts|touches) the (?P<stop>(?:{_WORD} ){{0,5}}stop))"
_INSTALL_TO_STOP = re.compile(rf"Install the (?P<part>{_PHRASE}) until {_CONTACT}\.", _FLAGS)
_REFIT_TO_STOP = re.compile(
    rf"(?:Install|Fit|Seat) the (?P<part>{_PHRASE})(?:\. Continue)? until {_CONTACT}\.", _FLAGS,
)
_THERMAL_STATE = rf"the (?P<primary>{_PHRASE}) (?:reaches|has reached) (?P<threshold>{_PHRASE})"
_OPEN_STATE = rf"the (?P<secondary>{_PHRASE}) is fully open"
_OPEN_VERIFICATION = (
    rf"A (?P<state>fully open (?P<verified>{_PHRASE})) is verified by the "
    rf"(?P<indicator>{_PHRASE}) cycling on at least once\."
)
_START_AND_IDLE = re.compile(
    rf"Start the (?P<part>{_PHRASE}) and let it idle until the "
    rf"(?P<primary>{_PHRASE}) reaches (?P<threshold>{_PHRASE}) and {_OPEN_STATE}\. {_OPEN_VERIFICATION}",
    _FLAGS,
)
_IDLING = re.compile(
    rf"(?:Start|Switch on|Turn on) the (?P<part>{_PHRASE})\. Keep it idling until "
    rf"(?P<conditions>[^.!?\n]+)\. (?P<verification>[^.!?\n]+\.)",
    _FLAGS,
)
_THERMAL_PREDICATE = re.compile(_THERMAL_STATE, _FLAGS)
_OPEN_PREDICATE = re.compile(_OPEN_STATE, _FLAGS)
_VERIFY_STATE = re.compile(
    rf"(?:{_OPEN_VERIFICATION}|"
    rf"The (?P<active_indicator>{_PHRASE}) cycling on at least once verifies "
    rf"a fully open (?P<active_verified>{_PHRASE})\.)",
    _FLAGS,
)
_COUNTED_STEPS = rf"(?P<counted>Steps (?P<first>{_COUNT}) through (?P<last>{_COUNT}) a total of (?P<count>{_COUNT}) times)"
_REPEAT_TO_REMOVE = re.compile(rf"Repeat {_COUNTED_STEPS} to remove (?P<contents>{_PHRASE})\.", _FLAGS)
_REMOVE_BY_REPEAT = re.compile(rf"Remove (?P<contents>{_PHRASE}) by repeating {_COUNTED_STEPS}\.", _FLAGS)

_FLUID_ACTION = re.compile(
    rf"(?P<action>Drain|Empty(?: out)?|Fill) the (?P<target>{_PHRASE})\.", _FLAGS,
)
_FLUID_PASSIVE = re.compile(
    rf"The (?P<target>{_PHRASE}) must be (?P<action>drained|emptied|filled)\.", _FLAGS,
)
_DRAIN_FLUID = re.compile(
    rf"(?:Drain the fluid|Let the fluid drain|Allow the fluid to drain) (?:from|out of) the "
    rf"(?P<target>{_PHRASE})\.",
    _FLAGS,
)
_FLUID_TARGET_BOUNDARIES = frozenset("by completely from fully gradually into out to".split())
_FLUID_ACTIONS = {
    "drain": "drain", "drained": "drain", "empty": "drain", "empty out": "drain", "emptied": "drain",
    "fill": "fill", "filled": "fill",
}


def _contact_instruction(text):
    match = _INSTALL_TO_STOP.fullmatch(text)
    return match if match and _object_name(match["part"]) else None


def _idle_instruction(text):
    match = _START_AND_IDLE.fullmatch(text)
    if match and (match["secondary"].casefold() == match["verified"].casefold()
                  and all(_object_name(match[key]) for key in ("part", "primary", "threshold", "secondary", "indicator"))):
        return match
    return None


def _repeat_instruction(text, pattern=_REPEAT_TO_REMOVE):
    match = pattern.fullmatch(text)
    if match and int(match["first"]) <= int(match["last"]) and _object_name(match["contents"]):
        return match
    return None


def _fluid_facts(text):
    explicit_drain = _DRAIN_FLUID.fullmatch(text)
    match = explicit_drain or _FLUID_ACTION.fullmatch(text) or _FLUID_PASSIVE.fullmatch(text)
    if match:
        target = match["target"]
        if _object_name(target) and _FLUID_TARGET_BOUNDARIES.isdisjoint(target.split()):
            return "fluid", "drain" if explicit_drain else _FLUID_ACTIONS[match["action"]], target
    return None


def _idle_facts(text):
    if source := _idle_instruction(text):
        return ("idle", *(source[key] for key in ("part", "primary", "threshold", "secondary", "indicator")))
    if not (draft := _IDLING.fullmatch(text)):
        return None
    conditions = draft["conditions"].removeprefix("both conditions are met: ")
    endpoints = re.split(r",? and ", conditions, maxsplit=1)
    if len(endpoints) != 2:
        return None
    thermal = _THERMAL_PREDICATE.fullmatch(endpoints[0]) or _THERMAL_PREDICATE.fullmatch(endpoints[1])
    valve = _OPEN_PREDICATE.fullmatch(endpoints[1]) or _OPEN_PREDICATE.fullmatch(endpoints[0])
    verification = _VERIFY_STATE.fullmatch(draft["verification"])
    if thermal and valve and verification:
        # Both predicates control the end of idling. The minimum recurrence
        # verifies the same open state through the original indicator.
        verified = verification["verified"] or verification["active_verified"]
        if verified == valve["secondary"]:
            return ("idle", draft["part"], thermal["primary"], thermal["threshold"], verified,
                    verification["indicator"] or verification["active_indicator"])
    return None


def procedure_facts(text: str) -> tuple[str, ...] | None:
    """Return comparable facts for a complete recognized instruction."""
    text = " ".join(text.casefold().split())
    if text and text[-1].isalpha():
        text += "."
    if facts := _fluid_facts(text):
        return facts
    if contact := _REFIT_TO_STOP.fullmatch(text):
        if _object_name(contact["part"]) and _object_name(contact["stop"]):
            return "contact", contact["part"], contact["stop"]
    if repeat := _repeat_instruction(text) or _repeat_instruction(text, _REMOVE_BY_REPEAT):
        return ("repeat", *(repeat[key] for key in ("first", "last", "count", "contents")))
    return _idle_facts(text)


_COOLANT_PRODUCT_WORD = r"[a-z][a-z0-9®™/-]{0,31}"
_COOLANT_PRODUCT = rf"{_COOLANT_PRODUCT_WORD}(?: (?:{_COOLANT_PRODUCT_WORD}|[®™])){{0,7}}(?: |/)coolant"
_HUE = (
    r"(?:(?:bright|dark|deep|light|pale) )?"
    r"(?:amber|black|blue|brown|clear|gray|green|grey|orange|pink|purple|red|violet|white|yellow)"
)
_CONDITIONAL_COLOR_NOTE = re.compile(
    rf"(?P<label>[ \t]*Note[ \t]*:[ \t]*)During normal vehicle operation, "
    rf"(?P<product>{_COOLANT_PRODUCT}) may change color from (?P<start>{_HUE}) "
    rf"to (?P<first_end>{_HUE}) or (?P<second_end>{_HUE})\."
    rf"(?P<suffix>[ \t\r\n]+As long as [^,.!?\r\n]+ and [^,.!?\r\n]+, [^.!?\r\n]+\.[ \t]*)",
    _FLAGS,
)
_COLOR_NOTE_PRODUCT_OPERATORS = _CLAUSE_WORDS | {
    "all", "any", "both", "can", "could", "either", "may", "must", "no", "shall", "should", "some", "will", "would",
}


def recast_conditional_color_note(text: str) -> str | None:
    """Reword a bound coolant color observation while preserving its conditional sentence."""
    match = _CONDITIONAL_COLOR_NOTE.fullmatch(text)
    if match is None:
        return None

    product_words = re.split(r"[ /-]+", match["product"].casefold())
    hues = {match[key].casefold() for key in ("start", "first_end", "second_end")}
    if not _COLOR_NOTE_PRODUCT_OPERATORS.isdisjoint(product_words) or len(hues) != 3:
        return None

    return (
        f"{match['label']}During normal vehicle operation, it is possible for {match['product']} "
        f"to change color from {match['start']} to either {match['first_end']} or {match['second_end']}."
        f"{match['suffix']}"
    )
