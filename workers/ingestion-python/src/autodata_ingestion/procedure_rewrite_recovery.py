"""Replay a failed correction and finish only recognized, equivalent edits."""

from copy import deepcopy
import re

from . import procedure_rewrite_auto as auto
from . import procedure_rewrite_full as full
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
FIRST_DRAFT_RECOVERY_METHOD = "source-bound-first-draft-recovery-v1"
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


def recover_first_draft(source, raw, *, prompt_version):
    """Recover verbatim echoes in one saved first draft through unchanged guards."""
    if (not full._source_valid(source) or not isinstance(raw, dict)
            or set(raw) != {"introduction", "replacements"}
            or not isinstance(raw["introduction"], str) or not isinstance(raw["replacements"], list)):
        return None
    slots = full.prose_slots(source, include_cell_blocks=auto._include_cell_blocks(prompt_version))
    if (prompt_version is None or not auto._uses_prose_guards(prompt_version, len(slots))
            or len(raw["replacements"]) != len(slots)):
        return None
    draft = deepcopy(raw)
    corrected_paths = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        if (not isinstance(row, dict) or set(row) != {"block_id", "path", "action", "text", "reason"}
                or not all(isinstance(value, str) for value in row.values())
                or row["block_id"] != slot["block_id"] or row["path"] != slot["path"]
                or row["action"] not in {"retain", "rewrite"} or not row["text"].strip()):
            return None
        if row["action"] == "rewrite" and row["text"] == slot["text"]:
            wording = _equivalent_wording(slot["text"])
            if wording is None:
                return None
            row.update(text=wording, reason="Distinct source-bound prose.")
            corrected_paths.append(slot["path"])
    if not corrected_paths:
        return None
    try:
        auto.render_auto(source, raw, prompt_version=prompt_version)
    except ValueError as error:
        if str(error) != "REWRITE_UNCHANGED":
            return None
    else:
        return None
    try:
        document = auto.render_auto(source, draft, prompt_version=prompt_version)
        validation = auto.validate_auto(source, document, response=draft, prompt_version=prompt_version)
        if not validation.passed:
            return None
        auto.require_current_publication_checks(source, document, saved_prompt_version=prompt_version)
    except ValueError:
        return None
    return CorrectionResult(draft, document, None, {
        "method": FIRST_DRAFT_RECOVERY_METHOD,
        "original_error_code": "REWRITE_UNCHANGED",
        "guard_version": prompt_version,
        "input_hash": digest_json(source),
        "raw_response_hash": digest_json(raw),
        "draft_hash": digest_json(draft),
        "output_hash": digest_json(document),
        "corrected_paths": corrected_paths,
    })


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
