"""Recover Bankone prose while keeping proven labels and choices intact."""

from copy import deepcopy
import re

from . import procedure_rewrite_auto as auto, procedure_rewrite_full as full
from .bankone_first_draft_structure import bankone_alternatives, validate_bankone_structure
from .procedure_rewrite_cooling_recovery import _object_name
from .procedure_rewrite_correction import _introduction


_STRUCTURE_INVALID = "REWRITE_BANKONE_STRUCTURE_INVALID"
_VARIANT_MUTATION = "REWRITE_VARIANT_SCOPE_MUTATION"
_DIGEST = re.compile(r"[a-f0-9]{64}")
_LABEL_ERRORS = {
    "note_label": frozenset({"REWRITE_UNCHANGED", "REWRITE_NOTE_LABEL_MUTATION"}),
    "tool_label": frozenset({"REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR"}),
}
_PROSE_ERRORS = frozenset({
    "REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR", "REWRITE_ACTION_MUTATION",
    "REWRITE_QUALIFIER_MUTATION", "REWRITE_TECHNICAL_MUTATION",
})
_NOUN = r"[A-Za-z][A-Za-z -]{1,119}?"
_CLAUSE = r"[^.!?;]{1,256}?"
_SHORT = re.compile(rf"(Drain|Remove|Install|Disconnect) the ({_NOUN})\.", re.I)
_PASSIVES = {"drain": "drained", "remove": "removed", "install": "installed", "disconnect": "disconnected"}
_USE_MIX = re.compile(rf"Use the ({_CLAUSE}) of ({_CLAUSE}) to fill the ({_CLAUSE}) during ({_CLAUSE})\.", re.I)
_FILL_AND_WAIT = re.compile(rf"Fill the ({_NOUN}) to the ({_NOUN}) and wait ({_CLAUSE})\.", re.I)
_ADJUST = re.compile(rf"Adjust the ({_NOUN}) level in the ({_NOUN}) to the ({_NOUN})\.", re.I)
_ADD_WITH = re.compile(rf"With a ({_NOUN}), add the ({_NOUN}) to the ({_NOUN})\.", re.I)
_OPTIONS = {"remove": "removal", "install": "installation"}


def _option_wrapper(alternatives) -> str:
    return f"follow the applicable {_OPTIONS[alternatives.verb]} option"


def _rewrite_alternatives(alternatives) -> str:
    return f"For {alternatives.target}, {_option_wrapper(alternatives)}: {alternatives.suffix}"


def check_bankone_passage(original: str, replacement: str, entry: dict) -> tuple[str, str] | None:
    """Verify protected text separately before comparing rewritten wrapper prose."""
    if not isinstance(entry, dict) or not isinstance(entry.get("block_id"), str) or not entry["block_id"]:
        raise ValueError(_STRUCTURE_INVALID)
    kind = entry.get("kind")
    if kind == "alternatives":
        alternatives = bankone_alternatives(original)
        hashes = entry.get("reference_hashes")
        if (set(entry) != {"block_id", "kind", "reference_hashes"} or alternatives is None
            or not isinstance(hashes, list) or len(hashes) != len(alternatives.options)
            or any(not isinstance(item, str) or not _DIGEST.fullmatch(item) for item in hashes)
            or len(set(hashes)) != len(hashes)):
            raise ValueError(_VARIANT_MUTATION)
        operator = alternatives.verb
        if replacement == original:
            return operator, operator
        if replacement != _rewrite_alternatives(alternatives):
            raise ValueError(_VARIANT_MUTATION)
        return operator, f"For, {_option_wrapper(alternatives)}"
    if set(entry) != {"block_id", "kind"}:
        raise ValueError(_STRUCTURE_INVALID)
    if kind == "note_label":
        if not original or auto.authored_note_prefix(original) != original or replacement != original:
            raise ValueError("REWRITE_NOTE_LABEL_MUTATION")
    elif kind == "tool_label":
        if not full._TOKENS.match(original) or replacement != original:
            raise ValueError("REWRITE_BANKONE_TOOL_LABEL_MUTATION")
    else:
        raise ValueError(_STRUCTURE_INVALID)
    return None


def _plain_wording(original: str):
    if match := _SHORT.fullmatch(original):
        verb, part = match.groups()
        if _object_name(part):
            yield f"The {part} must be {_PASSIVES[verb.casefold()]}."
    if match := _USE_MIX.fullmatch(original.strip()):
        mixture, components, assembly, interval = match.groups()
        yield f"During {interval}, fill the {assembly} with the {mixture}. The mixture consists of {components}."
        yield f"The {mixture} consists of {components}. Use it to fill the {assembly} during {interval}."
        yield (
            f"During {interval}, the {assembly} needs to be filled with the {mixture}. "
            f"The constituents of that mixture are {components}."
        )
    if match := _FILL_AND_WAIT.fullmatch(original):
        part, mark, delay = match.groups()
        if _object_name(part) and _object_name(mark):
            yield f"Fill the {part} until it reaches the {mark}. Then wait {delay}."
            yield f"Fill the {part} so it reaches the {mark}, then wait {delay}."
    if match := _ADJUST.fullmatch(original):
        material, part, mark = match.groups()
        if all(map(_object_name, (material, part, mark))):
            yield f"In the {part}, adjust the {material} level to the {mark}."
            yield f"Adjust the {part}'s {material} level to the {mark}."
    if match := _ADD_WITH.fullmatch(original):
        scope, material, destination = match.groups()
        if all(map(_object_name, (scope, material, destination))):
            yield f"With a {scope}, add to the {destination} the {material}."


def _aligned_reply(raw, slots):
    if (not isinstance(raw, dict) or set(raw) != {"introduction", "replacements"}
        or not isinstance(raw["introduction"], str) or not isinstance(raw["replacements"], list)
        or len(raw["replacements"]) != len(slots)):
        return False
    for slot, row in zip(slots, raw["replacements"], strict=True):
        if (not isinstance(row, dict) or set(row) != {"block_id", "path", "action", "text", "reason"}
            or not all(isinstance(item, str) for item in row.values())
            or row["block_id"] != slot["block_id"] or row["path"] != slot["path"]
            or row["action"] not in {"retain", "rewrite"} or not row["text"].strip()):
            return False
    return True


def _failure_paths(source, draft, *, prompt_version, structure=None):
    return {
        row["path"]: row["code"]
        for row in auto.failed_rewrite_passages(
            source, draft, prompt_version=prompt_version, bankone_structure=structure,
        )
    }


def recover_bankone_draft(source, raw, *, prompt_version, structure):
    """Recast only historically rejected passages of the proven source."""
    if not full._source_valid(source):
        return None
    slots = full.prose_slots(source, include_cell_blocks=auto._include_cell_blocks(prompt_version))
    if not _aligned_reply(raw, slots):
        return None
    try:
        validate_bankone_structure(source, structure)
    except ValueError:
        return None
    if not structure["slots"] or structure["slots"].keys() - {slot["path"] for slot in slots}:
        return None
    historical = _failure_paths(source, raw, prompt_version=prompt_version)
    if not historical:
        return None

    draft = deepcopy(raw)
    try:
        draft["introduction"] = _introduction(source, raw["introduction"])
    except ValueError:
        return None
    corrected = set()
    for slot, row in zip(slots, draft["replacements"], strict=True):
        path = slot["path"]
        entry = structure["slots"].get(path)
        if entry is None or path not in historical:
            continue
        original = slot["text"]
        kind = entry["kind"]
        if kind == "alternatives":
            if row["action"] != "rewrite" or historical[path] not in {"REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR"}:
                return None
            row["text"] = _rewrite_alternatives(bankone_alternatives(original))
        else:
            if historical[path] not in _LABEL_ERRORS[kind]:
                return None
            reason = (
                "Preserve the authored standalone note label exactly."
                if kind == "note_label" else "Preserve the complete authored tool label."
            )
            row.update(action="retain", text=original, reason=reason)
        corrected.add(path)

    current = _failure_paths(source, draft, prompt_version=prompt_version, structure=structure)
    for slot, row in zip(slots, draft["replacements"], strict=True):
        path = slot["path"]
        if (path in structure["slots"] or row["action"] != "rewrite" or path not in current
            or historical.get(path) not in _PROSE_ERRORS):
            continue
        original, saved_text = slot["text"], row["text"]
        for wording in _plain_wording(original):
            if (full._technical_tokens(original) != full._technical_tokens(wording)
                or auto._execution_order(original) != auto._execution_order(wording)):
                continue
            row["text"] = wording
            remaining = _failure_paths(source, draft, prompt_version=prompt_version, structure=structure)
            if path not in remaining and remaining.keys() <= current.keys():
                corrected.add(path)
                current = remaining
                break
            row["text"] = saved_text

    if current or not corrected:
        return None
    return draft, [slot["path"] for slot in slots if slot["path"] in corrected]
