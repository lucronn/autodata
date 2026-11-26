"""Preserve a validated rewrite while correcting the retained source layout."""

from collections import defaultdict, deque

from .article_document import project_ordered_document
from .article_lifecycle_types import digest_json
from .bankone_first_draft_structure import validate_bankone_structure
from .procedure_rewrite_auto import (
    _include_cell_blocks,
    render_auto,
    require_current_publication_checks,
    require_distinct_generated_introduction,
    require_preserved_display_quotations,
    require_required_procedure_actions,
    validate_auto,
)
from .procedure_rewrite_full import prose_slots
from .published_media_repair import PublishedMediaRepair


BANKTWO_NOTICE_METHOD = "published-banktwo-list-notices-v1"
BANKONE_DEFINITION_METHOD = "published-bankone-definition-headings-v1"
BANKONE_LIST_BOUNDARY_METHOD = "published-bankone-list-boundaries-v1"
_INVALID = "PUBLISHED_BANKTWO_NOTICE_REWRITE_INVALID"


def repair_banktwo_notice_reply(previous, document, corrected, *, response, prompt_version, profile):
    return repair_layout_reply(previous, document, corrected, response=response, prompt_version=prompt_version,
                               profile=profile, method=BANKTWO_NOTICE_METHOD)


def _remap_bankone_list_reply(previous, corrected, response, *, bankone_structure, include_cells):
    validate_bankone_structure(previous, bankone_structure)
    saved = defaultdict(deque)
    destinations = defaultdict(list)
    current = prose_slots(corrected, include_cell_blocks=include_cells)
    for slot in current:
        destinations[slot["text"]].append(slot["path"])
    for slot, row in zip(prose_slots(previous, include_cell_blocks=include_cells), response["replacements"], strict=True):
        proof = {key: value for key, value in bankone_structure["slots"].get(slot["path"], {}).items()
                 if key != "block_id"}
        saved[slot["text"]].append((slot["path"], {key: row[key] for key in ("action", "text", "reason")}, proof))
    if saved.keys() != destinations.keys():
        raise ValueError(_INVALID)
    for text, matches in saved.items():
        paths = destinations[text]
        if len(matches) != len(paths):
            raise ValueError(_INVALID)
        # A repeated directive can have different saved wording. Its
        # instances may only carry that wording at their unchanged paths.
        if ([path for path, _, _ in matches] != paths
                and any((row, proof) != matches[0][1:] for _, row, proof in matches)):
            raise ValueError(_INVALID)
    replacements, proofs = [], {}
    for slot in current:
        _, row, proof = saved[slot["text"]].popleft()
        replacements.append({**row, "block_id": slot["block_id"], "path": slot["path"]})
        if proof:
            proofs[slot["path"]] = {**proof, "block_id": slot["block_id"]}
    remapped_proof = {**bankone_structure, "source_hash": digest_json(corrected), "slots": proofs}
    validate_bankone_structure(corrected, remapped_proof)
    return replacements, remapped_proof


def repair_layout_reply(previous, document, corrected, *, response, prompt_version, profile, method,
                        bankone_structure=None):
    """Rebind saved prose to unchanged source text at its new coordinates."""
    options = {"prompt_version": prompt_version, "profile_version": profile, "bankone_structure": bankone_structure}
    if (render_auto(previous, response, **options) != document
            or not validate_auto(previous, document, response=response, **options).passed):
        raise ValueError(_INVALID)

    include_cells = _include_cell_blocks(prompt_version)
    if method == BANKONE_LIST_BOUNDARY_METHOD:
        replacements, corrected_structure = _remap_bankone_list_reply(
            previous, corrected, response, bankone_structure=bankone_structure, include_cells=include_cells,
        )
        options["bankone_structure"] = corrected_structure
    else:
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
    changed = validation.report["changed_prose_slots"]
    require_current_publication_checks(corrected, candidate, saved_prompt_version=prompt_version,
                                       bankone_structure=options["bankone_structure"])
    require_distinct_generated_introduction(corrected, candidate, rewritten_paths=changed)
    if method == BANKONE_LIST_BOUNDARY_METHOD:
        require_preserved_display_quotations(corrected, candidate, rewritten_paths=changed)
        require_required_procedure_actions(corrected, candidate, rewritten_paths=changed)
    return PublishedMediaRepair(
        document=candidate,
        projection=project_ordered_document(candidate),
        remapped_response=reply,
        validation=validation,
        provenance={
            "transformation_method": method,
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
            **({"repaired_bankone_structure_hash": digest_json(options["bankone_structure"])}
               if method == BANKONE_LIST_BOUNDARY_METHOD else {}),
        },
    )
