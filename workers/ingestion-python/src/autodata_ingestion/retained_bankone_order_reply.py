"""Carry validated Bank One wording onto an authenticated HTML layout replay."""

from collections import Counter

from .article_document import project_ordered_document
from .article_lifecycle_types import SOURCE_BOUND_CORRECTION_PROFILE, digest_json
from .procedure_rewrite_auto import (
    _NOTE_LABEL_PROMPT_VERSION,
    _include_cell_blocks,
    render_auto,
    require_current_publication_checks,
    require_distinct_generated_introduction,
    require_preserved_display_quotations,
    require_required_procedure_actions,
    validate_auto,
)
from .procedure_rewrite_full import _source_valid, prose_slots
from .published_media_repair import PublishedMediaRepair, _SUPPORTED_PROMPTS, _image_hash


BANKONE_ORDER_METHOD = "published-bankone-html-order-v1"
_PROMPTS = _SUPPORTED_PROMPTS | {_NOTE_LABEL_PROMPT_VERSION}
_PROTECTED_BLOCKS = frozenset({"callout", "table", "link"})
_POSITION_KEYS = frozenset({"block_id", "source_order"})
_SOURCE_DRIFT = "PUBLISHED_BANKONE_ORDER_SOURCE_DRIFT"
_SLOT_DRIFT = "PUBLISHED_BANKONE_ORDER_SLOT_DRIFT"
_PUBLICATION_MISMATCH = "PUBLISHED_BANKONE_ORDER_PUBLISHED_BINDING_MISMATCH"


def _protected_contents(value):
    if isinstance(value, dict):
        return {
            key: _protected_contents(child)
            for key, child in value.items()
            if key not in _POSITION_KEYS
        }
    if isinstance(value, list):
        return [_protected_contents(child) for child in value]
    return value


def _protected_blocks(value):
    if isinstance(value, list):
        for child in value:
            yield from _protected_blocks(child)
    elif isinstance(value, dict):
        if value.get("type") in _PROTECTED_BLOCKS:
            yield _protected_contents(value)
        else:
            for child in value.values():
                yield from _protected_blocks(child)


def _ordered_figure_hashes(projection):
    # The authenticated HTML parser supplies alt text. Asset identity, captions,
    # evidence and render availability must still be exact.
    return [
        _image_hash({key: value for key, value in image.items() if key != "alt"})
        for image in projection["images"]
    ]


def _require_same_source_content(before, after):
    old = project_ordered_document(before)
    new = project_ordered_document(after)
    old_lines = old["body"].splitlines()
    new_lines = new["body"].splitlines()
    if (old_lines == new_lines or Counter(old_lines) != Counter(new_lines)
            or _ordered_figure_hashes(old) != _ordered_figure_hashes(new)
            or list(_protected_blocks(before["blocks"])) != list(_protected_blocks(after["blocks"]))):
        raise ValueError(_SOURCE_DRIFT)


def _remap_archived_reply(before, after, response, *, prompt_version):
    include_cells = _include_cell_blocks(prompt_version)
    old_slots = prose_slots(before, include_cell_blocks=include_cells)
    new_slots = prose_slots(after, include_cell_blocks=include_cells)
    old_counts = Counter(slot["text"] for slot in old_slots)
    new_counts = Counter(slot["text"] for slot in new_slots)
    old_headings = Counter(block["text"] for block in before["blocks"] if block["type"] == "heading")
    new_headings = Counter(block["text"] for block in after["blocks"] if block["type"] == "heading")
    first_old, first_new = before["blocks"][0], after["blocks"][0]
    promoted = first_old.get("text")
    if (first_old["type"] != "paragraph" or first_new["type"] != "heading"
            or first_new["text"] != promoted or first_new["evidence_ids"] != first_old["evidence_ids"]
            or new_headings != old_headings + Counter({promoted: 1})
            or old_counts - new_counts != Counter({promoted: 1})
            or new_counts - old_counts or not new_counts[promoted]):
        raise ValueError(_SLOT_DRIFT)

    archived = {}
    for slot, row in zip(old_slots, response["replacements"], strict=True):
        effective = {key: row[key] for key in ("action", "text", "reason")}
        if archived.setdefault(slot["text"], effective) != effective:
            raise ValueError(_SLOT_DRIFT)

    return {
        "introduction": response["introduction"],
        "replacements": [
            {**archived[slot["text"]], "block_id": slot["block_id"], "path": slot["path"]}
            for slot in new_slots
        ],
    }


def repair_bankone_order(old_source, published, repaired_source, *, response, prompt_version, profile):
    """Reapply the saved correction to a checksum-bound Bank One source replay."""
    if (profile != SOURCE_BOUND_CORRECTION_PROFILE
            or not isinstance(prompt_version, str) or prompt_version not in _PROMPTS):
        raise ValueError("PUBLISHED_BANKONE_ORDER_PROFILE_UNSUPPORTED")
    if not all(_source_valid(document) for document in (old_source, published, repaired_source)):
        raise ValueError("PUBLISHED_BANKONE_ORDER_DOCUMENT_INVALID")

    validation_options = {"prompt_version": prompt_version, "profile_version": profile}
    try:
        original = render_auto(old_source, response, **validation_options)
        original_validation = validate_auto(old_source, published, response=response, **validation_options)
    except ValueError:
        raise ValueError(_PUBLICATION_MISMATCH) from None
    if original != published or not original_validation.passed:
        raise ValueError(_PUBLICATION_MISMATCH)

    _require_same_source_content(old_source, repaired_source)
    remapped = _remap_archived_reply(old_source, repaired_source, response, prompt_version=prompt_version)
    document = render_auto(repaired_source, remapped, **validation_options)
    validation = validate_auto(repaired_source, document, response=remapped, **validation_options)
    if not validation.passed or published["blocks"][0]["text"] != document["blocks"][0]["text"]:
        raise ValueError("PUBLISHED_BANKONE_ORDER_REWRITE_INVALID")
    require_current_publication_checks(repaired_source, document, saved_prompt_version=prompt_version)
    changed = validation.report["changed_prose_slots"]
    require_distinct_generated_introduction(repaired_source, document, rewritten_paths=changed)
    require_preserved_display_quotations(repaired_source, document, rewritten_paths=changed)
    require_required_procedure_actions(repaired_source, document, rewritten_paths=changed)

    return PublishedMediaRepair(
        document=document,
        projection=project_ordered_document(document),
        remapped_response=remapped,
        validation=validation,
        provenance={
            "transformation_method": BANKONE_ORDER_METHOD,
            "profile_version": profile,
            "model_calls": 0,
            "model_dispatch_count": 0,
            "original_prompt_version": prompt_version,
            "original_normalized_source_hash": digest_json(old_source),
            "original_published_document_hash": digest_json(published),
            "original_response_hash": digest_json(response),
            "repaired_normalized_source_hash": digest_json(repaired_source),
            "repaired_published_document_hash": digest_json(document),
            "remapped_response_hash": digest_json(remapped),
        },
    )
