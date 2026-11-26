"""Preserve a validated Banktwo rewrite while fixing the source notice layout."""

from .article_document import project_ordered_document
from .article_lifecycle_types import digest_json
from .procedure_rewrite_auto import (
    _include_cell_blocks,
    render_auto,
    require_current_publication_checks,
    require_distinct_generated_introduction,
    validate_auto,
)
from .procedure_rewrite_full import prose_slots
from .published_media_repair import PublishedMediaRepair


BANKTWO_NOTICE_METHOD = "published-banktwo-list-notices-v1"
_INVALID = "PUBLISHED_BANKTWO_NOTICE_REWRITE_INVALID"


def repair_banktwo_notice_reply(previous, document, corrected, *, response, prompt_version, profile):
    """Rebind saved prose to unchanged source text at its new coordinates."""
    options = {"prompt_version": prompt_version, "profile_version": profile}
    if (render_auto(previous, response, **options) != document
            or not validate_auto(previous, document, response=response, **options).passed):
        raise ValueError(_INVALID)

    include_cells = _include_cell_blocks(prompt_version)
    saved_prose = {}
    for slot, item in zip(prose_slots(previous, include_cell_blocks=include_cells), response["replacements"], strict=True):
        saved = {key: item[key] for key in ("action", "text", "reason")}
        if saved_prose.setdefault(slot["text"], saved) != saved:
            raise ValueError(_INVALID)

    replacements = []
    for slot in prose_slots(corrected, include_cell_blocks=include_cells):
        saved = saved_prose.get(slot["text"])
        if saved is None:
            raise ValueError(_INVALID)
        replacements.append({**saved, "block_id": slot["block_id"], "path": slot["path"]})

    reply = {"introduction": response["introduction"], "replacements": replacements}
    candidate = render_auto(corrected, reply, **options)
    validation = validate_auto(corrected, candidate, response=reply, **options)
    if not validation.passed or candidate["blocks"][0]["text"] != document["blocks"][0]["text"]:
        raise ValueError(_INVALID)
    require_current_publication_checks(corrected, candidate, saved_prompt_version=prompt_version)
    require_distinct_generated_introduction(corrected, candidate, rewritten_paths=validation.report["changed_prose_slots"])
    return PublishedMediaRepair(
        document=candidate,
        projection=project_ordered_document(candidate),
        remapped_response=reply,
        validation=validation,
        provenance={
            "transformation_method": BANKTWO_NOTICE_METHOD,
            "profile_version": profile,
            "model_calls": 0,
            "model_dispatch_count": 0,
            "original_prompt_version": prompt_version,
            "original_normalized_source_hash": digest_json(previous),
            "original_published_document_hash": digest_json(document),
            "original_response_hash": digest_json(response),
            "repaired_normalized_source_hash": digest_json(corrected),
            "repaired_published_document_hash": digest_json(candidate),
            "remapped_response_hash": digest_json(reply),
        },
    )
