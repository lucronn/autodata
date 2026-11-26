"""Shared immutable lifecycle contracts and exact provider-scoped identities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, NAMESPACE_URL, uuid5
import hashlib
import json

NORMALIZATION_VERSION = "ordered-article-v1"
LEADING_DECIMAL_LAYOUT = "leading-decimal-text-v1"
REWRITE_PROFILE_VERSION = "technical-prose-v1"
AUTOMATIC_REWRITE_PROFILE = "full-prose-auto-v1"
SOURCE_BOUND_REWRITE_PROFILE = "full-prose-auto-v2"
SOURCE_BOUND_CORRECTION_PROFILE = "full-prose-auto-v3"
RETAINED_NOTE_LABEL_REPAIR_PROFILE = "full-prose-note-label-repair-v1"
RETAINED_OPTIONAL_OBSERVATION_REPAIR_PROFILE = "full-prose-optional-observation-repair-v1"
RETAINED_CONDITIONAL_NOTE_REPAIR_PROFILE = "full-prose-conditional-note-repair-v1"
RETAINED_ROTATION_REMOVAL_REPAIR_PROFILE = "full-prose-rotation-removal-repair-v1"
RETAINED_AUTHORED_PROCEDURE_REPAIR_PROFILE = "full-prose-authored-procedure-repair-v1"
RETAINED_REQUIRED_ACTION_REPAIR_PROFILE = "full-prose-required-action-repair-v1"
RETAINED_INTRODUCTION_REPAIR_PROFILE = "full-prose-introduction-repair-v1"
MAX_CORRECTION_CALLS = 12
MAX_LINKED_PDFS = 4
RETAINED_MEDIA_REPLAY_MAX_BYTES = 8 * 1024 * 1024
AUTOMATIC_REWRITE_PROFILES = (
    AUTOMATIC_REWRITE_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, SOURCE_BOUND_CORRECTION_PROFILE,
)
HTML_FIGURE_CAPTION_LAYOUT = "html-figure-caption-v1"
HTML_FLOW_FIGURE_CAPTION_LAYOUT = "html-flow-figure-caption-v1"
HTML_MULTILINE_FIGURE_CAPTION_LAYOUT = "html-multiline-figure-caption-v1"
HTML_TABLE_CAPTION_LAYOUT = "html-table-caption-v1"
HTML_MEDIA_TABLE_HEADER_LAYOUT = "html-media-table-header-v1"
HTML_NESTED_TABLE_LAYOUT = "html-nested-tables-v1"
HTML_NUMERIC_SUPERSCRIPT_LAYOUT = "html-numeric-superscript-v1"
HTML_DOCUMENT_LINK_LAYOUT = "html-document-link-labels-v1"
HTML_INLINE_ARTICLE_LINK_LAYOUT = "html-inline-article-links-v1"
HTML_SECTION_TITLE_LAYOUT = "html-section-titles-v1"
HTML_TABLE_SPAN_LAYOUT = "html-table-spans-v1"
HTML_BOUND_IMAGE_LAYOUT = "html-bound-image-v1"
BANKONE_HTML_FLOW_LAYOUT = "bankone-html-flow-v1"
MIXED_HTML_PDF_LAYOUT = "mixed-html-pdf-v1"
PDF_BLANK_PAGE_LAYOUT = "blank-pdf-pages-v1"
PDF_COMPACT_FIGURE_LAYOUT = "compact-pdf-figures-v1"
PDF_FAST_PNG_ENCODING = "png-level-3-v1"
PDF_LEGACY_FIGURE_LAYOUT = "legacy-pdf-figures-v1"
PDF_REPEAT_MARGIN_LAYOUT = "repeated-pdf-margins-v1"
PDF_SINGLE_LINE_FIGURE_LAYOUT = "single-line-pdf-figure-v1"
PDF_WORDLESS_FIGURE_LAYOUT = "wordless-pdf-figure-v1"
ORDERED_STEP_INSTRUCTIONS_LAYOUT = "ordered-step-instructions-v1"
ORDERED_STEP_IMAGE_ONLY_LAYOUT = "ordered-step-instructions-v2"
STRUCTURED_HEADING_IMAGE_LAYOUT = "structured-image-only-heading-v1"
STRUCTURED_TABLE_COLUMNS_LAYOUT = "structured-table-columns-v1"
STRUCTURED_TABLE_COLUMN_ORDER_LAYOUT = "structured-table-column-order-v1"
STRUCTURED_TABLE_CELL_ORDER_LAYOUT = "structured-table-cell-order-v1"
STRUCTURED_TABLE_NESTED_MEDIA_LAYOUT = "structured-table-nested-media-v1"
MISSING_TABLE_IMAGE_CAPTION_LAYOUT = "missing-table-image-captions-v1"
MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V2 = "missing-table-image-captions-v2"
MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V3 = "missing-table-image-captions-v3"
SOURCE_PROJECTION_VERSIONS = (
    "source-projection-v1",
    "source-projection-v2",
    "source-projection-v3",
    "source-projection-v4",
    "source-projection-v5",
    "source-projection-v6",
    "source-projection-v7",
    "source-projection-v8",
    "source-projection-v9",
    "source-projection-v10",
)


def validate_ref(value: str, limit: int = 2048) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("invalid opaque reference")


def digest_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ArticleKey:
    provider: str
    vehicle_id: UUID
    vehicle_configuration_id: UUID | None
    source_vehicle_ref: str
    source_article_ref: str

    def __post_init__(self):
        if (
            self.provider not in ("bankone", "banktwo")
            or not isinstance(self.vehicle_id, UUID)
            or (
                self.vehicle_configuration_id is not None
                and not isinstance(self.vehicle_configuration_id, UUID)
            )
        ):
            raise ValueError("invalid article scope")
        validate_ref(self.source_vehicle_ref, 1024)
        validate_ref(self.source_article_ref)

    @property
    def scope_key(self):
        return scope_key(self.vehicle_id, self.vehicle_configuration_id)


def scope_key(vehicle_id, configuration_id=None):
    return (
        f"configuration:{configuration_id}"
        if configuration_id
        else f"vehicle:{vehicle_id}"
    )


def identity_payload(key: ArticleKey) -> dict:
    return {
        "provider": key.provider,
        "vehicle_id": str(key.vehicle_id),
        "vehicle_configuration_id": (
            str(key.vehicle_configuration_id) if key.vehicle_configuration_id else None
        ),
        "source_vehicle_ref": key.source_vehicle_ref,
        "source_article_ref": key.source_article_ref,
    }


def identity_key(key: ArticleKey) -> str:
    return digest_json(identity_payload(key))


def article_id(key: ArticleKey) -> UUID:
    return uuid5(NAMESPACE_URL, "autodata:article:v1:" + identity_key(key))


def transformation_key(
    canonical_article_id,
    source_fingerprint,
    normalization_version,
    rewrite_profile_version,
    *,
    projection_version="source-projection-v1",
):
    if projection_version not in SOURCE_PROJECTION_VERSIONS:
        raise ValueError("unsupported source projection version")
    payload = {
        "canonical_article_id": str(canonical_article_id),
        "source_fingerprint": source_fingerprint,
        "normalization_version": normalization_version,
        "rewrite_profile_version": rewrite_profile_version,
    }
    # Historical v1 keys are persisted identities: preserve their exact payload.
    if projection_version != "source-projection-v1":
        payload.update(
            projection_version=projection_version,
            domain="autodata:article-transformation:" + projection_version.rsplit("-", 1)[1],
        )
    return digest_json(payload)


@dataclass(frozen=True)
class ResourceRef:
    provider: str
    opaque_ref: str

    def __post_init__(self):
        if self.provider not in ("bankone", "banktwo"):
            raise ValueError("invalid resource provider")
        validate_ref(self.opaque_ref)


@dataclass(frozen=True)
class SourceArticleContext:
    key: ArticleKey
    vehicle: dict
    descriptor: dict
    descriptor_snapshot_id: UUID
    resolution_snapshot_id: UUID
    evidence_ids: tuple[str, ...]
    legacy_published_pdf_roots: frozenset[str] = frozenset()
    legacy_published_pdf_margin_roots: frozenset[str] = frozenset()
    published_legacy_pdf_layout_roots: frozenset[str] = frozenset()
    legacy_published_pdf_compact_roots: frozenset[str] = frozenset()
    legacy_published_pdf_blank_roots: frozenset[str] = frozenset()
    legacy_published_html_figure_body: str | None = None
    legacy_published_html_flow_figure_body: str | None = None
    legacy_published_html_multiline_figure_body: str | None = None
    legacy_published_html_table_caption_body: str | None = None
    legacy_published_html_document_link_body: str | None = None
    legacy_published_html_section_title_body: str | None = None
    legacy_published_bankone_flow_body: str | None = None
    legacy_published_bankone_svg_refs: frozenset[str] = frozenset()
    has_stored_source: bool = False
    fast_linked_pdf_png_roots: frozenset[str] = frozenset()
    legacy_published_positioned_label_body: str | None = None
    legacy_published_inline_article_link_body: str | None = None


@dataclass(frozen=True)
class CapturedSource:
    context: SourceArticleContext
    source_fingerprint: str
    body_source_snapshot_id: UUID
    resources: tuple[dict, ...]
    resource_manifest: list[dict]
    resource_provenance: list[dict]
    source_document: dict
    source_images: list[dict]
    source_body: str
    source_steps: list[dict]
    evidence_manifest: list[dict]
    projection_status: str
    captured_at: datetime
    projection_version: str = "source-projection-v1"
    recovered_legacy_bankone_svg: bool = False
    image_only: bool = False
    service_schedule: str | None = None


@dataclass(frozen=True)
class JobLease:
    job_id: UUID
    worker_id: UUID
    token: int
    generation: int
    kind: str
    phase: str
    canonical_article_id: UUID | None
    catalog_provider_scope_id: UUID | None
    source_revision_id: UUID | None
    normalization_version: str
    rewrite_profile_version: str
    checkpoint: dict
    expires_at: datetime


@dataclass(frozen=True)
class EnsureResult:
    job_id: UUID
    canonical_article_id: UUID | None
    state: str
    source_revision_id: UUID | None
    retry_after_seconds: int | None
    published_revision_id: UUID | None
    created: bool


@dataclass(frozen=True)
class RewriteResult:
    document: dict
    changed_slots: tuple[str, ...]
    raw_response: dict
    input_hash: str
    output_hash: str
    prompt_hash: str
    model_metadata: dict
    profile_version: str
    error_code: str | None


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    error_codes: tuple[str, ...]
    report: dict


class Repository(Protocol):
    def connect(self): ...
