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
_LET_COMPONENT_DRAIN = re.compile(rf"Let the (?P<target>{_PHRASE}) drain\.", _FLAGS)
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


def _fluid_facts(text, *, allow_drain_subject):
    explicit_drain = _DRAIN_FLUID.fullmatch(text)
    if explicit_drain is None and allow_drain_subject:
        explicit_drain = _LET_COMPONENT_DRAIN.fullmatch(text)
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


def procedure_facts(text: str, *, allow_drain_subject: bool = True) -> tuple[str, ...] | None:
    """Return comparable facts for a complete recognized instruction."""
    text = " ".join(text.casefold().split())
    if text and text[-1].isalpha():
        text += "."
    if facts := _fluid_facts(text, allow_drain_subject=allow_drain_subject):
        return facts
    if contact := _REFIT_TO_STOP.fullmatch(text):
        if _object_name(contact["part"]) and _object_name(contact["stop"]):
            return "contact", contact["part"], contact["stop"]
    if repeat := _repeat_instruction(text) or _repeat_instruction(text, _REMOVE_BY_REPEAT):
        return ("repeat", *(repeat[key] for key in ("first", "last", "count", "contents")))
    return _idle_facts(text)


_SEAL = rf"the (?P<seal>(?:{_WORD} ){{0,7}}seal) (?P<marker>\([0-9]{{1,4}}\))"
_INSPECT_SEAL = re.compile(
    rf"(?:inspect|check|examine) {_SEAL}(?: and |\. (?:then )?)"
    r"(?:replace(?: it)? (?:as necessary|if (?:needed|necessary))|swap it out if needed)\."
)
_DISCARD_SPRINGS = re.compile(
    r"(?:if|when) (?:installing|fitting) new brake pads, (?:discard|dispose of) "
    rf"the (?P<springs>(?:{_WORD} ){{0,4}}springs)\."
)
_AXLE_PADS = rf"(?P<pads>(?:{_WORD} ){{0,4}}pads)"
_PAD_SPRINGS = rf"(?P<springs>(?:{_WORD} ){{0,4}}springs)"
_AXLE_REPLACEMENT = (
    re.compile(
        rf"note: always replace {_AXLE_PADS} in axle sets\. "
        rf"(?:if|when) (?:installing|fitting) new brake pads, install new {_PAD_SPRINGS}\."
    ),
    re.compile(
        rf"note: {_AXLE_PADS} must always be replaced in axle sets\. "
        rf"install new {_PAD_SPRINGS} whenever new brake pads are (?:fitted|installed)\."
    ),
)
_THREAD_REPLACEMENT = (
    re.compile(
        r"clean the threads (?:of the wheel studs|on each wheel stud)\. "
        r"(?:if the threads are damaged, replace the wheel stud|replace any stud with damage to its threads)\."
    ),
    re.compile(r"after cleaning the wheel stud threads, replace (?:a|each) stud only if its threads are damaged\."),
)
_NETWORK_DEVICE_CHECK = re.compile(
    r"(?:if there is more than one smart device|when multiple smart devices are present), "
    r"(?:such as|as in) the example below, (?:keep in mind that )?"
    r"each smart device (?:is sending out|outputs|provides) its own reference voltage\. "
    r"in (?:these|such) cases, (?:disconnect the other smart devices|the other smart devices will need to be disconnected) "
    r"(?:along with|and) the master controller before (?:checking|measuring) "
    r"the reference voltage from (?:the|that) smart device in question\."
)


def conditional_service_facts(text: str) -> tuple[str, ...] | None:
    """Bind replacement conditions, required parts and diagnostic isolation to complete passages."""
    if not isinstance(text, str):
        return None
    text = " ".join(text.casefold().split())
    if "seal (" in text and (seal := _INSPECT_SEAL.fullmatch(text)) and _object_name(seal["seal"]):
        return "inspect_seal", seal["seal"], seal["marker"]
    if "springs" in text:
        if (springs := _DISCARD_SPRINGS.fullmatch(text)) and _object_name(springs["springs"]):
            return "discard_springs", springs["springs"]
        for syntax in _AXLE_REPLACEMENT:
            if (axle := syntax.fullmatch(text)) and all(_object_name(axle[key]) for key in ("pads", "springs")):
                return "axle_set", axle["pads"], axle["springs"]
    if "wheel stud" in text and any(syntax.fullmatch(text) for syntax in _THREAD_REPLACEMENT):
        return ("damaged_stud_threads",)
    if "reference voltage" in text and _NETWORK_DEVICE_CHECK.fullmatch(text):
        return ("isolate_reference_voltage",)
    return None


def recast_conditional_service(text: str) -> str | None:
    facts = conditional_service_facts(text)
    if facts is None:
        return None
    kind, *parts = facts
    if kind == "inspect_seal":
        seal, marker = parts
        return f"Check the {seal} {marker} and swap it out if needed."
    if kind == "discard_springs":
        return f"When fitting new brake pads, dispose of the {parts[0]}."
    if kind == "damaged_stud_threads":
        return "Clean the threads on each wheel stud. Replace any stud with damage to its threads."
    if kind == "isolate_reference_voltage":
        device = "smart device"
        voltage = "reference voltage"
        return (f"When multiple {device}s are present, as in the example below, each {device} outputs its own {voltage}. "
                f"In such cases, disconnect the other {device}s along with the master controller before checking "
                f"the {voltage} from the {device} in question.")
    return None


_BRAKE_HALF_FULL = r"(?:the )?half[- ]full(?: point)?"
_BRAKE_FLUID_MIDPOINT = (
    r"(?:the )?(?:midpoint|midway(?: point)?) between the maximum-full point and the minimum allowable level"
)
_BRAKE_LEVEL_CONDITION = re.compile(
    r"\b(?:(?:if|when) the brake fluid (?:level is|stands)|showing a brake fluid level of|"
    r"during (?:a )?routine fluid check, a level of) "
    r"(?:(?P<prefix>at or below|at or above|no higher than|no lower than|higher than|lower than|above|below|at) )?"
    rf"(?P<reference>{_BRAKE_HALF_FULL}|{_BRAKE_FLUID_MIDPOINT})"
    r"(?: or (?P<suffix>less|more))?\b(?=[,.]|$| during (?:a )?routine fluid checks?\b| calls for\b| permits\b)"
)
_BRAKE_LEVEL_RELATIONS = {
    None: "equal", "at": "equal", "at or below": "at_or_below", "no higher than": "at_or_below", "less": "at_or_below",
    "at or above": "at_or_above", "no lower than": "at_or_above", "more": "at_or_above",
    "lower than": "below", "below": "below", "higher than": "above", "above": "above",
}
_ROUTINE_BRAKE_CHECK = re.compile(r"\broutine fluid checks?\b")
_NORMAL_BRAKE_CONDITIONS = re.compile(r"\bunder normal conditions\b")
_BEFORE_PROCEEDING = re.compile(r"\bbefore proceeding\b")
_CLEAN_BRAKE_INSPECTION = re.compile(
    r"\b(?:and an inspection of the brake system did not reveal wear or brake fluid leaks|"
    r"once an inspection finds the brake system free of wear and brake fluid leaks)\b"
)
_BRAKE_LEVEL_ACTIONS = tuple(
    (action, re.compile(syntax))
    for action, syntax in (
        ("inspect_for_wear_and_leaks", r"\b(?:the brake system should be inspected|calls for inspecting the brake system)"
         r" for wear and possible (?:brake )?fluid leaks\b"),
        ("allow_refill_to_maximum", r"\b(?:the brake fluid may be topped[- ]off up|permits topping up the brake fluid)"
         r" to the maximum-fill level\b"),
        ("discourage_refill", r"\b(?:adding brake fluid is not recommended|topping up is discouraged)\b"),
        ("no_drain_required", r"\b(?:no brake fluid needs to be removed|no need to remove brake fluid)\b"),
        ("drain_to_midpoint", r"\bremove brake fluid (?:to the midway point|until it reaches that midpoint)\b"),
    )
)


def brake_fluid_level_facts(text: str) -> tuple[str, str, str, bool, bool, bool, bool] | None:
    """Read the condition and qualifiers of a recognized brake-fluid instruction."""
    if not isinstance(text, str):
        return None
    text = " ".join(text.casefold().split())
    if "brake fluid" not in text:
        return None
    conditions = list(_BRAKE_LEVEL_CONDITION.finditer(text))
    actions = [action for action, syntax in _BRAKE_LEVEL_ACTIONS if syntax.search(text)]
    if len(conditions) != 1 or len(actions) != 1:
        return None
    condition, = conditions
    prefix, suffix = condition["prefix"], condition["suffix"]
    if prefix and suffix:
        return None
    reference = "half_full" if "half" in condition["reference"] else "midpoint_between_limits"
    return (
        actions[0], _BRAKE_LEVEL_RELATIONS[prefix or suffix], reference,
        bool(_ROUTINE_BRAKE_CHECK.search(text)), bool(_NORMAL_BRAKE_CONDITIONS.search(text)),
        bool(_CLEAN_BRAKE_INSPECTION.search(text)), bool(_BEFORE_PROCEEDING.search(text)),
    )


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
