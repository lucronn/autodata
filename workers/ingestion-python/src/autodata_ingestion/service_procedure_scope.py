"""Recognize service instructions whose conditions and component bindings must survive rewriting."""

import re


_GUIDE = r"(?:lower|upper) (?:lh|rh) (?:primary|secondary) timing chain guide"
_TOOL = r"en-\d+ balance shaft holding tool"
_WEDGE = rf"{_TOOL} \(\d+\)"
_SCREW = rf"{_TOOL} thumb screw \(\d+\)"
_COVERAGE = r"bumper-to-bumper coverage \(canada base warranty coverage\)"
_WARRANTY_REFERENCE = r"applicable warranties section of investigate vehicle history \(ivh\)"
_SERIAL_DATA = r"serial data communication"
_LIN_MODULE = r"the master control module (?:will set|sets)"
_LIN_CODE = r"a no communication code"
_LIN_LOST_DEVICE = r"the (?:non-communicating lin device|lin device that lost communication)"
_OIL_PAN_BOLT = r"the oil pan-to-bell housing bolt"
_STARTER_POSITION = r"(?:below|under) the starter motor"
_PAN_SIDE_NOTE = (
    r"note: (?:lh rear (?:is )?shown[,;] rh (?:is )?similar"
    r"|the (?:illustration|figure) shows the lh rear\. the rh side is similar)\. "
)
_SHOWN_PRY_PADS = r"the (?:(?:illustrated|shown) pry pads|pry pads shown)"
_WHEEL_PILOT_HOLE = r"wheel hub pilot hole \(\d+\)"
_WHEEL_HUB_FLANGE = r"wheel bearing/hub flange"
_PILOT_LUBRICANT = r"a small amount of lubricant"

_SERVICE_STEPS = (
    ("cold coolant fill", re.compile(
        r"with a cold system, add (?:the coolant mixture to the fill line on the radiator surge tank"
        r"|to the fill line on the radiator surge tank the coolant mixture"
        r"|enough coolant mixture to bring the level in the radiator surge tank up to its fill line)\.?"
    )),
    ("remove timing guide", re.compile(
        rf"(?:remove the bolts and the (?P<guide>{_GUIDE})"
        rf"|take out the bolts and remove the (?P<recast_guide>{_GUIDE})"
        rf"|the bolts and the (?P<passive_guide>{_GUIDE}) are to be removed)\.?"
    )),
    ("install timing guide", re.compile(
        rf"(?:install the (?P<guide>{_GUIDE}) and (?:the|its) bolts"
        rf"|fit the (?P<recast_guide>{_GUIDE}) and install its bolts)\.?"
    )),
    ("install oil pump assembly", re.compile(
        r"(?:install the balancer shaft lower housing and oil pump as an assembly \(\d+\)"
        r"|fit the balancer shaft lower housing and oil pump together as an assembly \(\d+\)"
        r"|fit the assembly \(\d+\) that consists of the balancer shaft lower housing and oil pump)\.?"
    )),
    ("secure balance shafts", re.compile(
        rf"(?:slide the wedge of the {_WEDGE} (?:to|onto) the balance shaft weights(?: and|, then) tighten the {_SCREW}"
        r" to (?:hold|secure) the balance shafts in position"
        rf"|move the wedge on the {_WEDGE} by sliding it to the balance shaft weights\. "
        rf"to keep the balance shafts in position, tighten the {_SCREW})\.?"
    )),
    ("loosen balance shaft holding tool", re.compile(
        rf"loosen the {_SCREW}(?:, then slide the wedge of the {_WEDGE} away from the balance shaft weights"
        rf"| first\. then move the wedge of the {_WEDGE} by sliding it away from the balance shaft weights"
        rf"| first\. afterward, slide the {_WEDGE} wedge away from the balance shaft weights)\.?"
    )),
    ("warranty labor operation", re.compile(
        rf"(?:for vehicles repaired under (?:the )?{_COVERAGE}, "
        rf"(?:use the following labor operation\. reference the {_WARRANTY_REFERENCE} for coverage information"
        rf"|apply the labor operation shown below\. consult the {_WARRANTY_REFERENCE} to confirm coverage)"
        rf"|use the labor operation below when {_COVERAGE} applies to the repair\. "
        rf"for coverage information, see the {_WARRANTY_REFERENCE})\.?"
    )),
    ("set code for non-communicating LIN device", re.compile(
        rf"(?:if {_SERIAL_DATA} is lost between any (?:of the )?lin devices on the (?:lin bus(?: network)?|network), "
        rf"{_LIN_MODULE} {_LIN_CODE} (?:against|for) {_LIN_LOST_DEVICE}"
        rf"|a loss of {_SERIAL_DATA} between any (?:lin )?devices on the lin bus triggers {_LIN_CODE}\. "
        rf"{_LIN_MODULE} that code for {_LIN_LOST_DEVICE})\.?"
    )),
    ("remove bolt below starter", re.compile(
        rf"(?:remove {_OIL_PAN_BOLT} (?:located )?{_STARTER_POSITION}"
        rf"|{_STARTER_POSITION}, remove {_OIL_PAN_BOLT})\.?"
    )),
    ("remove oil pan at illustrated pads", re.compile(
        rf"{_PAN_SIDE_NOTE}(?:using a pry tool on {_SHOWN_PRY_PADS}, remove the oil pan"
        rf"|use a pry tool (?:on|at) {_SHOWN_PRY_PADS} to remove the oil pan"
        rf"|remove the oil pan by applying a pry tool (?:on|at) {_SHOWN_PRY_PADS})\.?"
    )),
    ("lubricate pilot hole at flange contact", re.compile(
        rf"(?:apply {_PILOT_LUBRICANT} to the inner diameter of the {_WHEEL_PILOT_HOLE} "
        rf"where it contacts (?:the with )?the {_WHEEL_HUB_FLANGE}"
        rf"|use {_PILOT_LUBRICANT} on the inner diameter of the {_WHEEL_PILOT_HOLE}, "
        rf"at the contact surface with the {_WHEEL_HUB_FLANGE}"
        rf"|where the {_WHEEL_HUB_FLANGE} meets the {_WHEEL_PILOT_HOLE}, "
        rf"apply {_PILOT_LUBRICANT} to the hole's inner diameter)\.?"
    )),
)


def service_procedure_facts(text):
    normalized = " ".join(text.casefold().split())
    normalized = re.sub(r"\[(en-\d+)\]", r"\1", normalized)
    normalized = re.sub(r"\[(\d+)\]", r"(\1)", normalized)
    for operation, pattern in _SERVICE_STEPS:
        match = pattern.fullmatch(normalized)
        if match:
            guide = next((value for value in match.groupdict().values() if value is not None), None)
            return operation, guide, tuple(re.findall(r"en-\d+|\(\d+\)", normalized))
    return None
