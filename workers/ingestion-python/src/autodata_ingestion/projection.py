"""Deterministic purchaser-facing content and fast-lane readiness checks."""

from __future__ import annotations

from typing import Any, Iterable

from .source_adapters import SourceArtifact
from .source_bundle import SourceBundle


def build_viewable_content(
    bundle: SourceBundle,
    artifacts: Iterable[SourceArtifact],
) -> dict[str, Any]:
    """Build projection content without dropping evidence or source identity."""

    if bundle.vehicle is None:
        raise ValueError("cannot build a projection without vehicle identity")
    artifact_records = [
        {
            "source_uri": artifact.source_uri,
            "source_version": artifact.source_version,
            "media_type": artifact.media_type,
            "content_sha256": artifact.content_sha256,
            "locator": artifact.metadata.get("locator") or artifact.source_uri,
            "kind": artifact.kind,
        }
        for artifact in sorted(artifacts, key=lambda item: (item.source_uri, item.content_sha256))
    ]
    content: dict[str, Any] = {
        "vehicle_identity": dict(bundle.vehicle),
        "source_metadata": {
            "source_watermarks": sorted({artifact["source_version"] for artifact in artifact_records}),
            "artifacts": artifact_records,
        },
    }
    if bundle.specifications:
        content["specifications"] = list(bundle.specifications)
    for section_name in ("models", "powertrains", "parts", "articles", "documents", "diagrams"):
        records = list(getattr(bundle, section_name))
        if records:
            content[section_name] = records
    return content


def viewable_sections(bundle: SourceBundle, artifacts: Iterable[SourceArtifact]) -> set[str]:
    """Return sections with enough normalized content to expose safely."""

    sections: set[str] = set()
    if bundle.vehicle is not None:
        sections.add("vehicle_identity")
    if list(artifacts):
        sections.add("source_metadata")
    if bundle.specifications:
        sections.add("specifications")
    for section_name in ("models", "powertrains", "parts", "articles", "documents", "diagrams"):
        if getattr(bundle, section_name):
            sections.add(section_name)
    return sections


def required_sections_ready(available: set[str], required: Iterable[str]) -> bool:
    """Check a product's minimum-section contract without guessing missing facts."""

    required_set = {str(section).strip() for section in required if str(section).strip()}
    return required_set.issubset(available)
