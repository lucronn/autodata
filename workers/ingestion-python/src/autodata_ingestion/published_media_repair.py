"""Reapply a bound published rewrite to a verified figure placement correction."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from functools import partial

from .article_document import (
    has_only_list_ordinal_additions, has_only_table_span_additions, project_ordered_document,
)
from .article_lifecycle_types import ValidationResult, digest_json
from .procedure_rewrite import _set_path, editable_slots, validate_article_rewrite
from .procedure_rewrite_auto import PROFILE, _include_cell_blocks, render_auto, validate_auto
from .procedure_rewrite_full import PROFILE as REVIEW_PROFILE
from .procedure_rewrite_full import _source_valid, prose_slots, render_full, validate_full
from .procedure_rewrite_v2 import PROFILE as TECHNICAL_V2
from .procedure_rewrite_v2 import _selection, plan_v2, render_v2

TECHNICAL_V1 = "technical-prose-v1"
_SUPPORTED_PROMPTS = frozenset(f"full-prose-auto-prompt-v{version}" for version in range(1, 60))
_POSITION_KEYS = frozenset({"block_id", "source_order"})
_IMAGE_KEYS = _POSITION_KEYS | {"type"}
MEDIA_METHOD = "published-media-placement-v1"
ORDINAL_METHOD = "published-list-ordinals-v1"
TABLE_SPAN_METHOD = "published-table-spans-v1"


@dataclass(frozen=True)
class PublishedMediaRepair:
    document: dict
    projection: dict
    remapped_response: dict
    validation: ValidationResult
    provenance: dict


def _without_media(value):
    if isinstance(value, list):
        return [
            _without_media(child) for child in value
            if not isinstance(child, dict) or child.get("type") != "image"
        ]
    if not isinstance(value, dict):
        return value

    cleaned = {}
    for key, child in value.items():
        if key in _POSITION_KEYS or key == "images":
            continue
        protected = _without_media(child)
        if key == "blocks" and not protected and "text" in value:
            continue
        cleaned[key] = protected
    if cleaned.keys() == {"text"}:
        # List and table text may gain an object wrapper for a placed figure.
        return cleaned["text"]
    return cleaned


def _image_positions(document):
    def visit(value, path):
        if isinstance(value, list):
            for index, child in enumerate(value):
                yield from visit(child, (*path, index))
        elif isinstance(value, dict):
            if value.get("type") == "image":
                yield path, _image_hash(value)
                return
            for key, child in value.items():
                if key == "images":
                    if not isinstance(child, list) or any(not isinstance(image, dict) for image in child):
                        raise ValueError("PUBLISHED_MEDIA_REPAIR_DOCUMENT_INVALID")
                    for index, image in enumerate(child):
                        yield (*path, key, index), _image_hash(image)
                else:
                    yield from visit(child, (*path, key))

    return dict(visit(document, ()))


def _image_hash(image):
    identity = {key: value for key, value in image.items() if key not in _IMAGE_KEYS}
    if image.get("status") == "available" and image.get("unavailable_reason") is None:
        # Available figures use the same render when older projections omit this null.
        identity.pop("unavailable_reason", None)
    return digest_json(identity)


def _render_technical_v1(source, response):
    """Rebuild the v1 reply exactly as the original worker applied it."""
    if set(response) != {"replacements"} or not isinstance(response["replacements"], list):
        raise ValueError("REWRITE_RESPONSE_INVALID")
    slots = editable_slots(source, profile_version=TECHNICAL_V1)
    rows = response["replacements"]
    if len(rows) != len(slots):
        raise ValueError("REWRITE_SLOT_MISMATCH")
    candidate = deepcopy(source)
    for slot, row in zip(slots, rows, strict=True):
        if (
            not isinstance(row, dict) or set(row) != {"block_id", "path", "text"}
            or row["block_id"] != slot["block_id"] or row["path"] != slot["path"]
            or not isinstance(row["text"], str) or not row["text"].strip()
        ):
            raise ValueError("REWRITE_SLOT_MISMATCH")
        _set_path(candidate, slot["path"], row["text"])
    return candidate


def _validate_technical(source, candidate, *, response, profile, render):
    if digest_json(render(source, response)) != digest_json(candidate):
        raise ValueError("REWRITE_RESPONSE_MISMATCH")
    return validate_article_rewrite(source, candidate, profile_version=profile)


def _remap_replacements(old_source, repaired_source, response, slots):
    old_slots = slots(old_source)
    new_slots = slots(repaired_source)
    if [slot["text"] for slot in old_slots] != [slot["text"] for slot in new_slots]:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_SLOT_DRIFT")
    return {
        **response,
        "replacements": [
            {**replacement, "block_id": slot["block_id"], "path": slot["path"]}
            for replacement, slot in zip(response["replacements"], new_slots, strict=True)
        ],
    }


def _remap_v2_operations(old_source, repaired_source):
    old_plan = plan_v2(old_source)
    new_plan = plan_v2(repaired_source)
    if not old_plan["eligible"] or not new_plan["eligible"]:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_SLOT_DRIFT")

    positional_keys = {"block_id", "path", "source_hash", "operation_id"}

    def semantics(plan, field):
        return [
            {key: value for key, value in row.items() if key not in positional_keys}
            for row in plan[field]
        ]

    if any(semantics(old_plan, field) != semantics(new_plan, field) for field in ("operations", "classifications")):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_SLOT_DRIFT")
    # The v2 response selects the complete plan. Its operation IDs bind the
    # repaired source hash and cannot be carried over from the original reply.
    return _selection(new_plan)


def repair_published_media(
    old_source, published, repaired_source, *, response, prompt_version=None, profile=PROFILE,
    ordinals=False, table_spans=False,
) -> PublishedMediaRepair:
    """Restore figure placement, list numbering or table spans using the saved rewrite.

    The caller supplies a validated immutable publication, its authorized
    response, and a source reconstructed from verified retained bytes. Resolve
    the original automatic prompt version from its stored prompt hash. For a
    reviewed publication, supply its approved effective response. Reviewed
    and technical publications do not use an automatic prompt version.
    """
    if ordinals and table_spans:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_MODE_INVALID")
    if profile == PROFILE:
        if not isinstance(prompt_version, str) or prompt_version not in _SUPPORTED_PROMPTS:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_PROMPT_UNSUPPORTED")
        render = partial(render_auto, prompt_version=prompt_version)
        validate = partial(validate_auto, prompt_version=prompt_version)
        slots = partial(prose_slots, include_cell_blocks=_include_cell_blocks(prompt_version))
    elif profile in (REVIEW_PROFILE, TECHNICAL_V1, TECHNICAL_V2):
        if prompt_version is not None:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_PROMPT_UNSUPPORTED")
        if profile == REVIEW_PROFILE:
            render, validate = render_full, validate_full
            slots = prose_slots
        else:
            render = _render_technical_v1 if profile == TECHNICAL_V1 else render_v2
            validate = partial(_validate_technical, profile=profile, render=render)
            slots = partial(editable_slots, profile_version=TECHNICAL_V1)
    else:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PROFILE_UNSUPPORTED")
    if not all(_source_valid(doc) for doc in (old_source, published, repaired_source)):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_DOCUMENT_INVALID")
    if not isinstance(response, dict):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH")
    try:
        previous_validation = validate(old_source, published, response=response)
    except ValueError:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH") from None
    if not previous_validation.passed:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH")
    structure_only = None
    if table_spans:
        structure_only = has_only_table_span_additions
        method = TABLE_SPAN_METHOD
        if not structure_only(old_source, repaired_source):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_TABLE_DRIFT")
    elif ordinals:
        structure_only = has_only_list_ordinal_additions
        method = ORDINAL_METHOD
        if not structure_only(old_source, repaired_source):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_ORDINAL_DRIFT")
    else:
        method = MEDIA_METHOD
        if _without_media(old_source) != _without_media(repaired_source):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_SOURCE_TEXT_DRIFT")
        old_positions = _image_positions(old_source)
        repaired_positions = _image_positions(repaired_source)
        if Counter(old_positions.values()) != Counter(repaired_positions.values()):
            raise ValueError("PUBLISHED_MEDIA_REPAIR_MEDIA_DRIFT")
        if old_positions == repaired_positions:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_UNCHANGED")

    if profile == TECHNICAL_V2:
        new_response = _remap_v2_operations(old_source, repaired_source)
    else:
        new_response = _remap_replacements(old_source, repaired_source, response, slots)
    try:
        document = render(repaired_source, new_response)
        validation = validate(repaired_source, document, response=new_response)
    except ValueError:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REWRITE_INVALID") from None
    if not validation.passed:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REWRITE_INVALID")
    published_prose = _without_media(published)
    if structure_only is not None:
        if profile in (PROFILE, REVIEW_PROFILE):
            # The validated introduction's ID binds the entire source hash.
            # Compare its prose and evidence while allowing that ID to rebind.
            before_intro, *before_blocks = published["blocks"]
            after_intro, *after_blocks = document["blocks"]
            intact_intro = (
                {key: value for key, value in before_intro.items() if key != "block_id"}
                == {key: value for key, value in after_intro.items() if key != "block_id"}
            )
            preserved = intact_intro and structure_only(
                {**published, "blocks": before_blocks}, {**document, "blocks": after_blocks},
            )
        else:
            preserved = structure_only(published, document)
    else:
        preserved = published_prose == _without_media(document)
    if not preserved:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_TEXT_DRIFT")

    return PublishedMediaRepair(
        document=document,
        projection=project_ordered_document(document),
        remapped_response=new_response,
        validation=validation,
        provenance={
            "transformation_method": method,
            "profile_version": profile,
            "model_calls": 0,
            "model_dispatch_count": 0,
            "original_prompt_version": prompt_version,
            "original_normalized_source_hash": digest_json(old_source),
            "original_published_document_hash": digest_json(published),
            "original_response_hash": digest_json(response),
            "repaired_normalized_source_hash": digest_json(repaired_source),
            "repaired_published_document_hash": digest_json(document),
            "remapped_response_hash": digest_json(new_response),
            "preserved_nonmedia_hash": digest_json(published_prose),
        },
    )
