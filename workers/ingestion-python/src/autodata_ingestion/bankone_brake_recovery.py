"""Rephrase complete brake-service statements while keeping their conditions."""

import re


_NOUN = r"[a-z]+(?:-[a-z]+)*(?: [a-z]+(?:-[a-z]+)*){0,5}"
_MARKER = r"\([0-9]{1,4}\)"
_FLUID_LEVEL = (
    r"If the (?P<fluid>[a-z]+ fluid) level is {relation}midway between "
    r"the (?P<high>maximum(?:-[a-z]+)? point) and the (?P<low>minimum allowable level), "
)
_MIDPOINT = re.compile(
    _FLUID_LEVEL.format(relation="") + r"no (?P=fluid) needs to be removed before proceeding\.",
)
_ABOVE_MIDPOINT = re.compile(
    _FLUID_LEVEL.format(relation="higher than ")
    + r"remove (?P=fluid) to the midway point before proceeding\.",
)
_RECORD_LOCATION = re.compile(rf"Note: Note the location of the (?P<part>{_NOUN} sensor) for correct installation\.")
_PAIRED_PADS = re.compile(
    rf"(?P<verb>Remove|Install) the inner (?P<part>{_NOUN} pad) (?P<inner>{_MARKER}) "
    rf"and the outer (?P=part) (?P<outer>{_MARKER})\.",
)
_UPPER_AND_LOWER = re.compile(rf"Remove the upper and lower (?P<part>{_NOUN} springs) (?P<marker>{_MARKER})\.")
_AXLE_SET = re.compile(
    rf"Note: Always replace (?P<pads>{_NOUN} pads) in axle sets\. "
    rf"If installing new brake pads, install new (?P<springs>{_NOUN} springs)\.",
)
_PEDAL_TRAVEL = re.compile(
    r"With the engine OFF, gradually apply the brake pedal to approximately (?P<distance>[0-9]+/[0-9]+) "
    r"of its travel distance\.",
)
_BRAKE_APPLICABILITY = re.compile(
    r"This (?:procedure|process) (?P<modal>should|must) be (?:performed|followed) whenever "
    rf"the (?P<rotor>{_NOUN} rotor)s (?:have been|are) (?:refinished|resurfaced) or replaced, "
    rf"and/or whenever the (?P<pad>{_NOUN} pad)s (?:have been|are) replaced\."
)
_LOW_RESERVOIR_CHECK = (
    rf"If the (?P<fluid>{_NOUN} fluid) level is at or below the (?P<half>half-full) point "
    r"during routine fluid checks"
)
_FILL_LIMIT = r"may be topped-off up to the (?P<limit>maximum-fill level)\."
_RESERVOIR_INSPECTION = re.compile(
    _LOW_RESERVOIR_CHECK + rf", the (?P<system>{_NOUN} system) should be inspected "
    r"for wear and possible (?P=fluid) leaks\."
)
_RESERVOIR_FILL_AFTER_INSPECTION = re.compile(
    _LOW_RESERVOIR_CHECK + rf", and an inspection of the (?P<system>{_NOUN} system) "
    r"did not reveal wear or (?P=fluid) leaks, the (?P=fluid) " + _FILL_LIMIT
)
_RESERVOIR_FILL_AFTER_SERVICE = re.compile(
    rf"If (?P<system>{_NOUN} system) service was just completed, the (?P<fluid>{_NOUN} fluid) " + _FILL_LIMIT
)
_RESERVOIR_ABOVE_HALF = re.compile(
    rf"If the (?P<fluid>{_NOUN} fluid) level is above the (?P<half>half-full) point, "
    r"adding (?P=fluid) is not recommended under normal conditions\."
)
_RESERVOIR_CLEAN_BEFORE_OPENING = re.compile(
    rf"If (?P<fluid>{_NOUN} fluid) is to be added to the (?P<container>{_NOUN} reservoir), "
    r"clean the outside of the reservoir on and around the reservoir (?P<cap>cap) "
    r"prior to removing the (?P=cap) and (?P<seal>diaphragm)\."
)
_REFILL_AFTER_SERVICE_WORDING = (
    re.compile(rf"You may bring the (?P<fluid>{_NOUN} fluid) up to its (?P<limit>maximum-fill level) "
               rf"immediately after completing service on the (?P<system>{_NOUN} system)\."),
    re.compile(rf"Immediately after servicing the (?P<system>{_NOUN} system), you may top up "
               rf"the (?P<fluid>{_NOUN} fluid) to the (?P<limit>maximum-fill level)\."),
)
_CLEAN_BEFORE_OPENING_WORDING = re.compile(
    rf"To prepare the (?P<container>{_NOUN} reservoir) for added (?P<fluid>{_NOUN} fluid), "
    r"clean its outside at the (?P<cap>cap) and around it (?:prior to|before) removing the (?P=cap) and (?P<seal>diaphragm)\."
)


def reservoir_preparation_facts(text):
    """Recognize complete instructions that bind servicing or cleaning order."""
    for syntax in (_RESERVOIR_FILL_AFTER_SERVICE, *_REFILL_AFTER_SERVICE_WORDING):
        if match := syntax.fullmatch(text):
            return "refill_after_service", match["system"], match["fluid"], match["limit"]
    for syntax in (_RESERVOIR_CLEAN_BEFORE_OPENING, _CLEAN_BEFORE_OPENING_WORDING):
        if match := syntax.fullmatch(text):
            return "clean_before_opening", match["container"], match["fluid"], match["cap"], match["seal"]
    return None


def recast_brake_applicability(text):
    """Keep both service conditions and their original modality."""
    if match := _BRAKE_APPLICABILITY.fullmatch(text):
        modality = {"should": "recommended", "must": "required"}[match["modal"]]
        return (f"This procedure is {modality} after {match['rotor']} resurfacing or replacement, "
                f"after {match['pad']} replacement, or after both kinds of work.")
    return None


def recast_reservoir_filling(text):
    """Rephrase bounded fluid-level and reservoir preparation instructions."""
    if match := _RESERVOIR_INSPECTION.fullmatch(text):
        return (f"A routine fluid check showing a {match['fluid']} level of {match['half']} or less calls for "
                f"inspecting the {match['system']} for wear and possible fluid leaks.")
    if match := _RESERVOIR_FILL_AFTER_INSPECTION.fullmatch(text):
        return (f"During a routine fluid check, a level of {match['half']} or less permits topping up the {match['fluid']} "
                f"to the {match['limit']} once an inspection finds the {match['system']} free of wear and {match['fluid']} leaks.")
    if match := _RESERVOIR_FILL_AFTER_SERVICE.fullmatch(text):
        return (f"You may bring the {match['fluid']} up to its {match['limit']} immediately after completing service "
                f"on the {match['system']}.")
    if match := _RESERVOIR_ABOVE_HALF.fullmatch(text):
        return (f"Under normal conditions, topping up is discouraged when the {match['fluid']} stands higher "
                f"than {match['half']}.")
    if match := _RESERVOIR_CLEAN_BEFORE_OPENING.fullmatch(text):
        return (f"To prepare the {match['container']} for added {match['fluid']}, clean its outside at the "
                f"{match['cap']} and around it prior to removing the {match['cap']} and {match['seal']}.")
    return None


def recast_brake_passage(text, error):
    if error == "REWRITE_ACTION_MUTATION":
        if match := _MIDPOINT.fullmatch(text):
            fluid, high, low = match["fluid"], match["high"], match["low"]
            return (f"There is no need to remove {fluid} before proceeding when the {fluid} level is at the "
                    f"midpoint between the {high} and the {low}.")
        if match := _ABOVE_MIDPOINT.fullmatch(text):
            fluid, high, low = match["fluid"], match["high"], match["low"]
            return (f"When the {fluid} level is above the midpoint between the {high} and the {low}, "
                    f"remove {fluid} until it reaches that midpoint before proceeding.")
        if match := _RECORD_LOCATION.fullmatch(text):
            return f"Note: Record the location of the {match['part']} so it can be installed correctly."
    elif error == "REWRITE_DIRECTION_MUTATION":
        if match := _PAIRED_PADS.fullmatch(text):
            verb = {"Remove": "removed", "Install": "installed"}[match["verb"]]
            part = match["part"]
            return f"The inner {part} {match['inner']} and outer {part} {match['outer']} must be {verb}."
        if match := _UPPER_AND_LOWER.fullmatch(text):
            return f"The upper and lower {match['part']} {match['marker']} must be removed."
    elif error == "REWRITE_PROSE_TOO_SIMILAR" and (match := _AXLE_SET.fullmatch(text)):
        return (f"Note: {match['pads'].capitalize()} must always be replaced in axle sets. "
                f"Install new {match['springs']} whenever new brake pads are fitted.")
    elif error == "REWRITE_TECHNICAL_MUTATION" and (match := _PEDAL_TRAVEL.fullmatch(text)):
        return f"With the engine OFF, apply the brake pedal gradually through approximately {match['distance']} of its travel distance."
    return None
