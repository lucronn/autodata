"""Reapply a bound published rewrite to a verified figure placement correction."""

from collections import Counter
from dataclasses import dataclass
from functools import partial

from .article_document import project_ordered_document
from .article_lifecycle_types import ValidationResult, digest_json
from .procedure_rewrite_auto import PROFILE, render_auto, validate_auto
from .procedure_rewrite_full import PROFILE as REVIEW_PROFILE
from .procedure_rewrite_full import _source_valid, prose_slots, render_full, validate_full

_SUPPORTED_PROMPTS = frozenset(f"full-prose-auto-prompt-v{version}" for version in range(1, 8))
_POSITION_KEYS = frozenset({"block_id", "source_order"})
_IMAGE_KEYS = _POSITION_KEYS | {"type"}
_METHOD = "published-media-placement-v1"


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
    return digest_json({key: value for key, value in image.items() if key not in _IMAGE_KEYS})


def repair_published_media(
    old_source, published, repaired_source, *, response, prompt_version=None, profile=PROFILE,
) -> PublishedMediaRepair:
    """Reposition equivalent figures without generating or editing published prose.

    The caller supplies a validated immutable publication, its authorized
    response, and a source reconstructed from verified retained bytes. Resolve
    the original automatic prompt version from its stored prompt hash. For a
    reviewed publication, supply its approved effective response and omit the
    automatic prompt version.
    """
    if profile == PROFILE:
        if not isinstance(prompt_version, str) or prompt_version not in _SUPPORTED_PROMPTS:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_PROMPT_UNSUPPORTED")
        render = partial(render_auto, prompt_version=prompt_version)
        validate = partial(validate_auto, prompt_version=prompt_version)
    elif profile == REVIEW_PROFILE:
        if prompt_version is not None:
            raise ValueError("PUBLISHED_MEDIA_REPAIR_PROMPT_UNSUPPORTED")
        render, validate = render_full, validate_full
    else:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PROFILE_UNSUPPORTED")
    if not all(_source_valid(doc) for doc in (old_source, published, repaired_source)):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_DOCUMENT_INVALID")
    if (
        not isinstance(response, dict)
        or not validate(old_source, published, response=response).passed
    ):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_BINDING_MISMATCH")
    if _without_media(old_source) != _without_media(repaired_source):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_SOURCE_TEXT_DRIFT")

    old_positions = _image_positions(old_source)
    repaired_positions = _image_positions(repaired_source)
    if Counter(old_positions.values()) != Counter(repaired_positions.values()):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_MEDIA_DRIFT")
    if old_positions == repaired_positions:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_UNCHANGED")

    new_slots = prose_slots(repaired_source)
    old_slots = prose_slots(old_source)
    if [slot["text"] for slot in old_slots] != [slot["text"] for slot in new_slots]:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_SLOT_DRIFT")
    new_response = {
        "introduction": response["introduction"],
        "replacements": [
            {**replacement, "block_id": slot["block_id"], "path": slot["path"]}
            for replacement, slot in zip(response["replacements"], new_slots, strict=True)
        ],
    }
    try:
        document = render(repaired_source, new_response)
    except ValueError:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REWRITE_INVALID") from None
    validation = validate(repaired_source, document, response=new_response)
    if not validation.passed:
        raise ValueError("PUBLISHED_MEDIA_REPAIR_REWRITE_INVALID")
    published_prose = _without_media(published)
    if published_prose != _without_media(document):
        raise ValueError("PUBLISHED_MEDIA_REPAIR_PUBLISHED_TEXT_DRIFT")

    return PublishedMediaRepair(
        document=document,
        projection=project_ordered_document(document),
        remapped_response=new_response,
        validation=validation,
        provenance={
            "transformation_method": _METHOD,
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
