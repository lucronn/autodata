"""Shared immutable lifecycle contracts and exact provider-scoped identities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, NAMESPACE_URL, uuid5
import hashlib
import json

NORMALIZATION_VERSION = "ordered-article-v1"
REWRITE_PROFILE_VERSION = "technical-prose-v1"


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
):
    return digest_json(
        {
            "canonical_article_id": str(canonical_article_id),
            "source_fingerprint": source_fingerprint,
            "normalization_version": normalization_version,
            "rewrite_profile_version": rewrite_profile_version,
        }
    )


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
