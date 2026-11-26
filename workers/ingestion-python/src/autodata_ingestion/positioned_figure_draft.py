"""Carry a saved draft across a verified diagram-label reprojection."""

import re

from . import procedure_rewrite_auto as auto, procedure_rewrite_full as full
from .article_lifecycle_types import digest_json
from .procedure_rewrite_recovery import (
    FIRST_DRAFT_POSITIONED_FIGURE_RECOVERY_METHOD as METHOD,
    NEUTRAL_INTRODUCTION,
    _validate_first_draft,
)


_SOURCE_MISMATCH = "FIRST_DRAFT_FIGURE_SOURCE_MISMATCH"
_DRAFT_MISMATCH = "FIRST_DRAFT_ARCHIVE_RECOVERY_MISMATCH"
_POSITION_FIELDS = {"block_id", "source_order", "figure_layout"}
_LABEL_FIELDS = {"block_id", "source_order", "evidence_ids", "type", "text"}
_PART = r"[a-z]+(?:-[a-z]+)*(?: [a-z]+(?:-[a-z]+)*){0,8}"
_INSTALL_AND_REFER = re.compile(
    rf"Install the (?P<first>{_PART}), and install the (?P<second>{_PART}); "
    r"refer to (?P<reference>the appropriate [A-Za-z0-9]+(?: [A-Za-z0-9]+){0,5} Service Manual)\.",
    re.I,
)


def _root_blocks(document):
    return {key: value for key, value in document.items() if key != "blocks"}


def _without_position(block):
    return {key: value for key, value in block.items() if key not in _POSITION_FIELDS}


def _projection_slots(previous, source):
    if (not full._source_valid(previous) or not full._source_valid(source)
            or _root_blocks(previous) != _root_blocks(source)):
        raise ValueError(_SOURCE_MISMATCH)
    before = iter(enumerate(previous["blocks"]))
    mapping = {}
    for index, block in enumerate(source["blocks"]):
        old_index, old = next(before, (None, {}))
        if (old_index is None or "figure_layout" in old or _without_position(old) != _without_position(block)):
            raise ValueError(_SOURCE_MISMATCH)
        mapping[index] = old_index
        if "figure_layout" not in block:
            continue
        if block["type"] != "image":
            raise ValueError(_SOURCE_MISMATCH)
        for label in block["figure_layout"]["labels"]:
            for text in label["lines"]:
                _, original = next(before, (None, {}))
                if (set(original) != _LABEL_FIELDS or original["type"] != "paragraph"
                        or original["text"] != text or not original["evidence_ids"]):
                    raise ValueError(_SOURCE_MISMATCH)
    if next(before, None) is not None or len(mapping) == len(previous["blocks"]):
        raise ValueError(_SOURCE_MISMATCH)
    return mapping


def _remap(previous, source, raw, prompt_version):
    mapping = _projection_slots(previous, source)
    flags = {"include_cell_blocks": auto._include_cell_blocks(prompt_version)}
    slots = full.prose_slots(previous, **flags)
    if len(slots) != len(raw["replacements"]):
        raise ValueError(_DRAFT_MISMATCH)
    originals = {}
    for slot, row in zip(slots, raw["replacements"], strict=True):
        if row["path"] != slot["path"] or row["block_id"] != slot["block_id"]:
            raise ValueError(_DRAFT_MISMATCH)
        originals[slot["path"]] = (slot, row)
    replacements = []
    for slot in full.prose_slots(source, **flags):
        _, collection, index, leaf = slot["path"].split("/", 3)
        previous_path = f"/{collection}/{mapping[int(index)]}/{leaf}"
        original, row = originals.get(previous_path, (None, None))
        if original is None or original["text"] != slot["text"]:
            raise ValueError(_SOURCE_MISMATCH)
        replacements.append({**row, "path": slot["path"], "block_id": slot["block_id"]})
    return replacements, len(slots) - len(replacements)


def _install_and_refer(text):
    if match := _INSTALL_AND_REFER.fullmatch(text):
        return (f"The {match['first']} must be installed. The {match['second']} must also be installed. "
                f"Refer to {match['reference']}.")
    return None


def recover_positioned_figure_draft(previous, source, attempt):
    prompt_version, raw = attempt["guard_version"], attempt["response"]
    original_error = attempt["error_code"]
    if original_error not in {"REWRITE_SPEC_SCOPE_MUTATION", "REWRITE_UNCHANGED"}:
        raise ValueError(_DRAFT_MISMATCH)
    try:
        auto.render_auto(previous, raw, prompt_version=prompt_version)
    except ValueError as error:
        if str(error) != original_error:
            raise ValueError(_DRAFT_MISMATCH) from None
    else:
        raise ValueError(_DRAFT_MISMATCH)
    try:
        auto.check_automatic_introduction(previous, raw["introduction"])
    except ValueError as error:
        if str(error) != "REWRITE_SPEC_SCOPE_MUTATION":
            raise ValueError(_DRAFT_MISMATCH) from None
    else:
        raise ValueError(_DRAFT_MISMATCH)

    replacements, removed = _remap(previous, source, raw, prompt_version)
    draft = {"introduction": NEUTRAL_INTRODUCTION, "replacements": replacements}
    failures = {item["path"]: item["code"] for item in auto.failed_rewrite_passages(
        source, draft, prompt_version=prompt_version,
    )}
    corrected = []
    for slot, row in zip(full.prose_slots(source, include_cell_blocks=auto._include_cell_blocks(prompt_version)),
                         replacements, strict=True):
        path = slot["path"]
        if failures.get(path) == "REWRITE_DIRECTION_MUTATION" and row["action"] == "rewrite":
            if wording := _install_and_refer(slot["text"]):
                row["text"] = wording
                corrected.append(path)
    result = _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version, method=METHOD, original_error=original_error,
    )
    if result is None:
        raise ValueError(_DRAFT_MISMATCH)
    result.evidence.update(previous_source_hash=digest_json(previous), removed_label_slots=removed)
    return result
