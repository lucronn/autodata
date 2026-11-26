"""Recast complete maintenance instructions while keeping their literal operands."""

import re

from .procedure_rewrite_recovery import _PART, _PART_WORD, _REFERENCE, _plain_label


_DOCUMENT_ID = re.compile(r"Document ID: ([0-9]{1,20})", re.I)
_CONFIRM_REMOVAL = re.compile(rf"(Note: )Ensure that the ({_PART}) has been removed\.", re.I)
_COUNTED_PART = re.compile(
    rf"(?P<part_label>(?P<part>{_PART}) ?{_REFERENCE})\s*»\s*"
    r"(?P<action>Remove|Install) (?P<quantity>\[[0-9]{1,4}\s*x\])", re.I,
)
_NUMBERED_ACTION = re.compile(
    rf"(Remove|Install) the ({_PART})\. ({_REFERENCE})( » (?:Remove|Install))?", re.I,
)
_DISCARD = re.compile(rf"Remove and discard the ({_PART})\. ({_REFERENCE})", re.I)
_OIL = rf"(?:{_PART_WORD} ){{0,4}}oil"
_LUBRICATE = re.compile(rf"Lubricate the ({_PART}) with ({_OIL})\.", re.I)
_REFERENCE_CATEGORIES = "Adhesives, Fluids, Lubricants, and Sealers"
_FLUID_REFERENCE = "Reference for fluids and lubricants, plus adhesives and sealers"
_PREFILL = re.compile(
    rf"Pre-fill the new ({_PART}) ({_REFERENCE}) with ({_OIL})\. {re.escape(_REFERENCE_CATEGORIES)}", re.I,
)
_START_AND_INSPECT = re.compile(rf"Start the ({_PART}) and inspect for leaks\.", re.I)
_PAST_ACTIONS = {"remove": "removed", "install": "installed"}


def recast_maintenance_passage(text):
    if match := _DOCUMENT_ID.fullmatch(text):
        return f"ID of this document: {match[1]}"
    if (match := _CONFIRM_REMOVAL.fullmatch(text)) and _plain_label(match[2]):
        return f"{match[1]}Confirm the removal of the {match[2]}."
    if (match := _COUNTED_PART.fullmatch(text)) and _plain_label(match["part"]):
        return f"{match['action'].capitalize()} {match['part_label']} {match['quantity']}"
    if (match := _NUMBERED_ACTION.fullmatch(text)) and _plain_label(match[2]):
        verb = match[1].casefold()
        suffix = match[4] or ""
        if not suffix or suffix.casefold().endswith(verb):
            return f"The {match[2]} must be {_PAST_ACTIONS[verb]}. {match[3]}{suffix}"
    if (match := _DISCARD.fullmatch(text)) and _plain_label(match[1]):
        return f"The {match[1]} must be removed and discarded. {match[2]}"
    if (match := _LUBRICATE.fullmatch(text)) and all(map(_plain_label, match.groups())):
        return f"The {match[1]} must be lubricated with {match[2]}."
    if (match := _PREFILL.fullmatch(text)) and _plain_label(match[1]) and _plain_label(match[3]):
        return f"With {match[3]}, pre-fill the new {match[1]} {match[2]}. {_FLUID_REFERENCE}."
    if text.casefold() == _REFERENCE_CATEGORIES.casefold():
        return _FLUID_REFERENCE
    if text.casefold() == "approximate fluid capacities":
        return "Estimated capacities for fluids"
    if (match := _START_AND_INSPECT.fullmatch(text)) and _plain_label(match[1]):
        return f"The {match[1]} must be started. Then inspect for leaks."
    return None
