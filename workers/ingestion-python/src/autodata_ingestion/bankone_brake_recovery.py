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
