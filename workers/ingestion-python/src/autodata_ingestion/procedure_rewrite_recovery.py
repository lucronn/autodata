"""Replay a failed correction and finish only recognized, equivalent edits."""

from copy import deepcopy
import re

from . import procedure_rewrite_auto as auto
from .article_lifecycle_types import digest_json
from .procedure_rewrite_correction import (
    CorrectionResult,
    _apply_variants,
    _initial_draft,
    _passage_errors,
    _validated_document,
    rebuild_retained_correction,
)

RECOVERY_METHOD = "source-bound-correction-recovery-v1"
_PART_WORD = r"[a-z]+(?:-[a-z]+)*"
_PART = rf"{_PART_WORD}(?: {_PART_WORD}){{0,9}}"
_REFERENCE = r"\([0-9]{1,4}\)"
_REMOVE = re.compile(rf"Remove the (?P<part>{_PART})\.", re.I)
_REMOVAL_NOTE = re.compile(
    rf"(?P<prefix>Note: )the (?P<part>{_PART_WORD}) is removed for clarity\. (?P<directive>Remove the {_PART}\.)",
    re.I,
)
_REMOVAL_CHECK = re.compile(rf"Ensure that the (?P<part>{_PART} {_REFERENCE}) has been removed\.", re.I)
_LABEL_DIRECTIVE = re.compile(rf"(?P<part>{_PART} ?{_REFERENCE})\s*»\s*(?P<verb>Remove|Install)", re.I)
_TIGHTEN_AFTER_CONTACT = re.compile(
    rf"Install a (?P<part>{_PART}) and tighten "
    rf"(?P<amount>[0-9]+/[0-9]+(?: to [0-9]+(?: full)?| of [0-9]+ full)? turn) after "
    rf"the gasket makes contact with the (?P<surface>{_PART}) on the (?P<owner>{_PART})"
    rf"(?P<suffix>\.(?: ?{_REFERENCE})?)",
    re.I,
)


def _removal_passive(text):
    match = _REMOVE.fullmatch(text)
    if (match is not None and auto._TARGET_DELIMITERS.isdisjoint(match["part"].casefold().split())
            and tuple(action.lastgroup for action in auto._action_matches(text)) == ("remove",)):
        return f"The {match['part']} must be removed."
    return None


def _equivalent_wording(text):
    text = text.strip()
    if wording := _removal_passive(text):
        return wording
    if (note := _REMOVAL_NOTE.fullmatch(text)) and (wording := _removal_passive(note["directive"])):
        return f"{note['prefix']}For clarity, the {note['part']} is removed. {wording}"
    if check := _REMOVAL_CHECK.fullmatch(text):
        return f"Confirm the removal of the {check['part']}."
    if label := _LABEL_DIRECTIVE.fullmatch(text):
        return f"{label['verb'].capitalize()} {label['part']}."
    if contact := _TIGHTEN_AFTER_CONTACT.fullmatch(text):
        return (f"Fit a {contact['part']}. After the {contact['surface']} on the {contact['owner']} comes "
                f"into contact with the gasket, tighten {contact['amount']}{contact['suffix']}")
    if text.casefold() == "oil filter":
        return "Filter for the oil"
    return None


def recover_retained_correction(source, previous, *, model_call_budget, attempts):
    """Verify the original transcript and reframe only unresolved passages."""
    original = rebuild_retained_correction(source, previous, model_call_budget=model_call_budget, attempts=attempts)
    version, slots, _ = _initial_draft(source, previous)
    draft = deepcopy(original.response)
    batch, alternatives = [], []
    for index in _passage_errors(source, slots, draft):
        if wording := _equivalent_wording(slots[index]["text"]):
            batch.append(index)
            alternatives.append([wording])
    if batch:
        _apply_variants(source, slots, draft, batch, alternatives)
    document, error_code = _validated_document(source, slots, draft, version)
    return CorrectionResult(draft, document, error_code, {
        **original.evidence,
        "method": RECOVERY_METHOD,
        "base_draft_hash": original.evidence["draft_hash"],
        "original_error_code": original.error_code,
        "draft_hash": digest_json(draft),
    })
