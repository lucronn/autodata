"""Vehicle-scoped multi-component labor and procedure planning.

The labor calculation is deliberately deterministic.  A model may later
rewrite the validated procedure through the adapter boundary, but it cannot
invent labor values, vehicle facts, or evidence references.
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
from typing import Any, Iterable, Mapping


_ALIASES = {
    "alt": "alternator",
    "alternator": "alternator",
    "starter": "starter",
    "battery": "battery",
    "brake": "brakes",
    "brakes": "brakes",
    "brake line": "brake_line",
    "brake bleeding": "brake_bleeding",
    "brake bleed": "brake_bleeding",
    "bleed brakes": "brake_bleeding",
    "brake inspection": "brake_inspection",
    "brake system inspection": "brake_inspection",
    "inspection": "inspection",
    "caliper": "brake_caliper",
    "rotor": "brake_rotor",
    "rotors": "brake_rotor",
    "pads": "brake_pads",
    "pad": "brake_pads",
    "waterpump": "water_pump",
    "water pump": "water_pump",
    "oil pump": "oil_pump",
    "timing belt": "timing_belt",
    "power steering pump": "power_steering_pump",
}


def plan_job(
    query: str,
    vehicle: Mapping[str, Any],
    *,
    catalog: Iterable[Mapping[str, Any]],
    source_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable job-plan response from normalized article records."""

    if not str(query).strip():
        raise ValueError("job query must not be empty")
    if not isinstance(vehicle, Mapping) or not vehicle.get("make") or not vehicle.get("model"):
        raise ValueError("job vehicle must include make and model")
    components = _components_from_query(query)
    if not components:
        return {
            "status": "needs_review",
            "vehicle": dict(vehicle),
            "requested_components": [],
            "review_reasons": ["no_component_detected"],
            "labor": _empty_labor(),
            "procedure": _empty_procedure("No component detected"),
            "images": [],
            "source": dict(source_info or {"mode": "normalized_cache"}),
        }

    articles = _flatten_articles(catalog)
    selected: OrderedDict[str, dict[str, Any]] = OrderedDict()
    review_reasons: list[str] = []
    for component in components:
        candidates = [
            article for article in articles
            if component in _article_components(article)
        ]
        candidates.sort(key=lambda item: (-_article_score(item, component), str(item.get("article_id", ""))))
        if not candidates:
            review_reasons.append(f"missing_article:{component}")
            continue
        selected[component] = candidates[0]

    labor, labor_reasons = _calculate_labor(selected)
    review_reasons.extend(labor_reasons)
    procedure = _compose_procedure(selected, labor["operations"])
    images = _collect_images(selected.values())
    status = "ready" if not review_reasons else "needs_review"
    source_ids = [str(article.get("article_id")) for article in selected.values()]
    evidence_ids = sorted({
        str(evidence_id)
        for article in selected.values()
        for evidence_id in _article_evidence_ids(article)
    })
    derived_fingerprint = _fingerprint(vehicle, components, source_ids, labor, procedure)
    return {
        "status": status,
        "vehicle": dict(vehicle),
        "requested_components": components,
        "selected_articles": source_ids,
        "review_reasons": sorted(set(review_reasons)),
        "labor": labor,
        "procedure": {**procedure, "requires_review": bool(review_reasons)},
        "images": images,
        "source": dict(source_info or {"mode": "normalized_cache"}),
        "derived_article": {
            "article_id": f"combined:{_vehicle_slug(vehicle)}:{'+'.join(components)}:v1",
            "revision_id": f"revision:{derived_fingerprint[:24]}",
            "title": procedure["title"],
            "status": status,
            "fingerprint": derived_fingerprint,
            "source_article_ids": source_ids,
            "evidence_ids": evidence_ids,
        },
    }


def _components_from_query(query: str) -> list[str]:
    return _component_matches(query)


def _flatten_articles(catalog: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for record in catalog:
        if not isinstance(record, Mapping):
            continue
        raw = record.get("article", record)
        if not isinstance(raw, Mapping):
            continue
        article = dict(raw)
        article.setdefault("evidence", record.get("evidence", []))
        if not article.get("article_id") and record.get("id"):
            article["article_id"] = record["id"]
        for key in (
            "supporting_for",
            "supports",
            "required_for",
            "recommended_for",
            "support_category",
            "operation_category",
            "vehicle_identity",
            "source_watermark",
            "source_version",
            "watermark",
            "evidence_ids",
            "evidence_id",
            "components",
            "component_keys",
            "covered_components",
            "visuals",
            "source_visuals",
        ):
            if key not in article and key in record:
                article[key] = record[key]
        flattened.append(article)
    return flattened


def _article_components(article: Mapping[str, Any]) -> set[str]:
    components: set[str] = set()
    for key in (
        "component",
        "component_key",
        "components",
        "component_keys",
        "covered_components",
    ):
        for value in _component_values(article.get(key)):
            components.update(_component_matches(value))
    for operation in _article_operations(article):
        for value in _component_values(operation.get("components")):
            components.update(_component_matches(value))
        components.update(_component_matches(operation.get("component")))
    for key in ("title", "bucket"):
        components.update(_component_matches(article.get(key, "")))
    return components


def _component_matches(value: Any) -> list[str]:
    """Match natural component phrases after punctuation/spacing normalization."""

    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("component", "component_key", "name", "value", "title"):
            values.extend(_component_matches(value.get(key)))
        return list(dict.fromkeys(values))
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_component_matches(item))
        return list(dict.fromkeys(values))

    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    matches: list[tuple[int, int, int, str]] = []
    for alias, canonical in _ALIASES.items():
        phrase = re.sub(r"[^a-z0-9]+", " ", alias.casefold()).strip()
        if not phrase:
            continue
        match = re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized)
        if match is not None:
            matches.append((match.start(), -len(phrase), match.end(), canonical))
    found: list[str] = []
    occupied: list[tuple[int, int]] = []
    for start, _negative_length, end, canonical in sorted(matches):
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied):
            continue
        if canonical not in found:
            found.append(canonical)
            occupied.append((start, end))
    return found


def _component_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for nested in value for item in _component_values(nested)]
    if isinstance(value, Mapping):
        return [
            nested
            for key in ("component", "component_key", "name", "value", "title")
            for nested in _component_values(value.get(key))
        ]
    return [value]


def _article_score(article: Mapping[str, Any], component: str) -> int:
    score = 0
    if str(article.get("component", "")).casefold() == component:
        score += 100
    if component in _article_components(article):
        score += 25
    if article.get("operations") or article.get("labor_operations"):
        score += 10
    if _article_evidence_ids(article):
        score += 5
    article_id = str(article.get("article_id", "")).casefold()
    bucket = str(article.get("bucket", "")).casefold()
    if article_id.startswith("p:"):
        score += 20
    if article_id.startswith("l:") or bucket == "labor":
        score -= 40
    return score


def _calculate_labor(selected: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    merged: OrderedDict[str, dict[str, Any]] = OrderedDict()
    standalone = Decimal("0")
    reasons: list[str] = []
    for component, article in selected.items():
        operations = article.get("operations", article.get("labor_operations", []))
        if not isinstance(operations, list) or not operations:
            operations = [{"operation_id": f"replace-{component}", "action": f"Replace {component}", "duration_hours": article.get("labor_hours")}]
        for index, raw in enumerate(operations):
            if not isinstance(raw, Mapping):
                raw = {"action": str(raw)}
            action = str(raw.get("action") or raw.get("name") or f"Perform {component} work").strip()
            operation_id = _stable_operation_id(raw, action, component, index)
            duration = _decimal_hours(raw.get("duration_hours", raw.get("hours", raw.get("labor_hours"))))
            if duration is None:
                reasons.append(f"unknown_duration:{operation_id}")
            else:
                standalone += duration
            evidence = _operation_evidence_ids(raw, article)
            current = merged.get(operation_id)
            if current is None:
                merged[operation_id] = {"operation_id": operation_id, "action": action, "duration_hours": float(duration) if duration is not None else None, "components": [component], "evidence_ids": evidence, "origin": "source_operation"}
            else:
                if current["duration_hours"] is not None and duration is not None and current["duration_hours"] != float(duration):
                    reasons.append(f"conflicting_duration:{operation_id}")
                current["components"] = sorted(set(current["components"]) | {component})
                current["evidence_ids"] = sorted(set(current["evidence_ids"]) | set(evidence))
    union = sum((Decimal(str(value["duration_hours"])) for value in merged.values() if value["duration_hours"] is not None), Decimal("0"))
    overlap = standalone - union
    return {
        "basis": "one_technician_standard_hours",
        "standalone_hours": float(standalone),
        "overlap_hours": float(overlap),
        "total_labor_hours": float(union) if not any(item.startswith("unknown_duration:") for item in reasons) else None,
        "confidence": 1.0 if not reasons else 0.0,
        "assumptions": ["operations with the same stable operation_id are shared and counted once"],
        "operations": list(merged.values()),
    }, reasons


def _compose_procedure(selected: Mapping[str, Mapping[str, Any]], operations: list[Mapping[str, Any]]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for sequence, operation in enumerate(operations, 1):
        steps.append({
            "sequence": sequence,
            "action": operation["action"],
            "components": list(operation["components"]),
            "source_article_ids": sorted(str(article.get("article_id")) for component, article in selected.items() if component in operation["components"]),
            "evidence_ids": list(operation["evidence_ids"]),
            "origin": "shared_source_step" if len(operation["components"]) > 1 else "source_step",
            "requires_review": False,
        })
    return {"title": " and ".join(f"{component.replace('_', ' ')} service" for component in selected), "steps": steps, "warnings": []}


def _collect_images(articles: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    seen: set[str] = set()
    for article in articles:
        article_id = str(article.get("article_id", ""))
        values = article.get("images", article.get("image_urls", article.get("diagrams", [])))
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                item = {"url": value} if isinstance(value, str) else dict(value) if isinstance(value, Mapping) else {}
                url = str(item.get("url") or item.get("source_uri") or item.get("uri") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                images.append({"url": url, "alt": str(item.get("alt") or item.get("title") or article.get("title") or "Source diagram"), "article_id": article_id, **({"evidence_id": str(item["evidence_id"])} if item.get("evidence_id") else {})})
    for article in articles:
        article_id = str(article.get("article_id", ""))
        for evidence in article.get("evidence", []) if isinstance(article.get("evidence", []), list) else []:
            if not isinstance(evidence, Mapping):
                continue
            media_type = str(evidence.get("media_type", "")).casefold()
            source_uri = str(evidence.get("source_uri", "")).strip()
            artifact_key = str(evidence.get("artifact_key", "")).strip()
            is_image = media_type.startswith("image/") or bool(re.search(r"\.(?:bmp|gif|jpe?g|png|svg|tiff?|webp)(?:$|[?#])", source_uri.casefold()))
            if not is_image or not (source_uri or artifact_key):
                continue
            identity = source_uri or artifact_key
            if identity in seen:
                continue
            seen.add(identity)
            item = {"url": source_uri, "artifact_key": artifact_key, "alt": str(evidence.get("alt") or article.get("title") or "Source image"), "article_id": article_id}
            if evidence.get("evidence_id"):
                item["evidence_id"] = str(evidence["evidence_id"])
            images.append({key: value for key, value in item.items() if value})
    return images


def _vectorize_selected_visuals(
    selected_records: Iterable[Mapping[str, Any]],
    *,
    vectorizer: Any | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Redraw only source-backed images and return linked immutable refs."""

    from .visual_vectorization import DeterministicLocalVectorizer, vectorize_source_diagram

    active_vectorizer = vectorizer
    artifacts: list[dict[str, Any]] = []
    review_reasons: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for record in selected_records:
        article = record["article"]
        article_id = str(article.get("article_id", "")).strip()
        for visual in _article_visuals(article):
            source_bytes = visual.get("source_bytes", visual.get("bytes", visual.get("content")))
            if isinstance(source_bytes, bytearray):
                source_bytes = bytes(source_bytes)
            source_uri = str(
                visual.get("source_uri") or visual.get("uri") or visual.get("url") or ""
            ).strip()
            if source_bytes is None:
                continue
            if not isinstance(source_bytes, bytes) or not source_bytes:
                review_reasons.add("visual_source_bytes_missing")
                continue
            if not source_uri:
                review_reasons.add("visual_source_uri_missing")
                continue
            identity = (hashlib.sha256(source_bytes).hexdigest(), source_uri)
            if identity in seen:
                continue
            seen.add(identity)
            if active_vectorizer is None:
                active_vectorizer = DeterministicLocalVectorizer()
            try:
                raw_artifact = vectorize_source_diagram(
                    {"source_bytes": source_bytes, "source_uri": source_uri},
                    vectorizer=active_vectorizer,
                )
            except Exception:
                review_reasons.add("visual_vectorization_failed")
                continue
            artifact = dict(raw_artifact)
            source_sha256 = str(
                artifact.get("source_sha256") or hashlib.sha256(source_bytes).hexdigest()
            )
            derived_bytes = artifact.get("derived_bytes")
            if isinstance(derived_bytes, str):
                derived_bytes = derived_bytes.encode("utf-8")
            derived_sha256 = str(artifact.get("derived_sha256") or "")
            if not derived_sha256 and isinstance(derived_bytes, bytes):
                derived_sha256 = hashlib.sha256(derived_bytes).hexdigest()
            source_artifact_id = str(
                artifact.get("source_artifact_id") or f"visual-source:{source_sha256}"
            )
            derived_artifact_id = str(
                artifact.get("derived_artifact_id")
                or f"visual-derived:{derived_sha256 or source_sha256}"
            )
            source_key = str(
                artifact.get("source_artifact_key") or artifact.get("source_object_key") or ""
            ).strip()
            derived_key = str(
                artifact.get("derived_artifact_key") or artifact.get("derived_object_key") or ""
            ).strip()
            evidence_ids = sorted(
                set(_string_ids(visual.get("evidence_ids")))
                | set(_string_ids(visual.get("evidence_id")))
                | set(_article_evidence_ids(article))
            )
            source_ref = {
                "artifact_id": source_artifact_id,
                "object_key": source_key,
                "uri": source_uri,
                "article_id": article_id,
                "evidence_ids": evidence_ids,
            }
            source_ref = {key: value for key, value in source_ref.items() if value not in (None, "")}
            derived_ref = {
                "artifact_id": derived_artifact_id,
                "source_artifact_id": source_artifact_id,
                "object_key": derived_key,
                "media_type": str(artifact.get("media_type") or "image/svg+xml"),
                "review_state": "pending",
                "label": "AI-enhanced / UNREVIEWED",
            }
            derived_ref = {key: value for key, value in derived_ref.items() if value not in (None, "")}
            artifact.update(
                {
                    "source_artifact_id": source_artifact_id,
                    "derived_artifact_id": derived_artifact_id,
                    "source_artifact_key": source_key,
                    "derived_artifact_key": derived_key,
                    "source_object_key": source_key,
                    "derived_object_key": derived_key,
                    "source_uri": source_uri,
                    "source_article_ids": [article_id] if article_id else [],
                    "evidence_ids": evidence_ids,
                    "review_state": "pending",
                    "label": "AI-enhanced / UNREVIEWED",
                    "requires_review": True,
                    "source_ref": source_ref,
                    "derived_ref": derived_ref,
                }
            )
            # Binary payloads remain in the storage/vectorizer boundary; the
            # quote and persistence contracts carry references and metadata.
            artifact.pop("derived_bytes", None)
            artifacts.append(artifact)
            review_reasons.add("visual_requires_review")
    return artifacts, sorted(review_reasons)


def _article_visuals(article: Mapping[str, Any]) -> list[dict[str, Any]]:
    values: list[Any] = []
    for key in ("source_visual", "source_visuals", "visuals", "images", "diagrams"):
        value = article.get(key, [])
        if isinstance(value, Mapping):
            values.append(value)
        elif isinstance(value, list):
            values.extend(value)
    if article.get("source_bytes") is not None or article.get("source_uri"):
        values.append(article)
    return [dict(value) for value in values if isinstance(value, Mapping)]


def _article_evidence_ids(article: Mapping[str, Any]) -> list[str]:
    evidence_ids = set(_string_ids(article.get("evidence_ids")))
    evidence_ids.update(_string_ids(article.get("evidence_id")))
    evidence = article.get("evidence", [])
    if isinstance(evidence, Mapping):
        evidence = [evidence]
    if isinstance(evidence, (str, int)):
        evidence = [evidence]
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, Mapping):
                evidence_ids.update(_string_ids(item.get("evidence_ids")))
                evidence_ids.update(_string_ids(item.get("evidence_id") or item.get("id")))
            else:
                evidence_ids.update(_string_ids(item))
    return sorted(evidence_ids)


def _string_ids(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, Mapping):
        return _string_ids(value.get("evidence_ids") or value.get("evidence_id") or value.get("id"))
    if isinstance(value, (list, tuple, set)):
        return [item for nested in value for item in _string_ids(nested)]
    value = str(value).strip()
    return [value] if value else []


def _operation_evidence_ids(raw: Mapping[str, Any], article: Mapping[str, Any]) -> list[str]:
    if "evidence_ids" in raw or "evidence_id" in raw:
        return sorted(
            set(_string_ids(raw.get("evidence_ids")))
            | set(_string_ids(raw.get("evidence_id")))
        )
    return _article_evidence_ids(article)


def _stable_operation_id(raw: Mapping[str, Any], action: str, component: str, index: int) -> str:
    explicit = str(raw.get("operation_id") or raw.get("key") or "").strip()
    if explicit:
        return explicit
    return re.sub(r"[^a-z0-9]+", "-", action.casefold()).strip("-") or f"{component}-operation-{index}"


def _decimal_hours(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _empty_labor() -> dict[str, Any]:
    return {"basis": "one_technician_standard_hours", "standalone_hours": 0.0, "overlap_hours": 0.0, "total_labor_hours": None, "confidence": 0.0, "assumptions": [], "operations": []}


def _empty_procedure(title: str) -> dict[str, Any]:
    return {"title": title, "steps": [], "warnings": [], "requires_review": True}


def _vehicle_slug(vehicle: Mapping[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "-".join(str(vehicle.get(key, "")) for key in ("year", "make", "model" )).casefold()).strip("-")


def _fingerprint(vehicle: Mapping[str, Any], components: list[str], source_ids: list[str], labor: Mapping[str, Any], procedure: Mapping[str, Any]) -> str:
    payload = repr((dict(vehicle), components, source_ids, labor, procedure)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_quote_and_procedure(
    query: str,
    vehicle: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
    *,
    mercury_client: Any | None = None,
    vectorizer: Any | None = None,
) -> dict[str, Any]:
    """Build a deterministic quote and an evidence-linked procedure.

    ``articles`` is expected to contain normalized records.  The model is
    optional and can only rewrite the already validated procedure; vehicle
    selection, support classification, labor arithmetic, pricing arithmetic,
    and publication identity remain application-owned.
    """

    if not str(query).strip():
        raise ValueError("job query must not be empty")
    if not isinstance(vehicle, Mapping) or not vehicle.get("make") or not vehicle.get("model"):
        raise ValueError("job vehicle must include make and model")
    normalized_articles = _flatten_articles(articles)
    requested_components = _components_from_query(query)
    if not requested_components:
        empty_quote = {
            "required_hours": 0.0,
            "recommended_hours": 0.0,
            "total_hours": None,
            "overlap_hours_removed": 0.0,
            "required_operations": [],
            "recommended_operations": [],
            "overlap_operations": [],
            "parts": [],
            "evidence": [],
            "currency": "USD",
            "vehicle": dict(vehicle),
            "labor": _detailed_empty_labor(),
            "parts_summary": _empty_parts_quote(),
            "source_article_ids": [],
            "evidence_ids": [],
            "source_watermarks": [],
            "requested_components": [],
            "required_supporting_components": [],
            "recommended_supporting_components": [],
        }
        empty_quote["quote_identity"] = _json_fingerprint(empty_quote)
        return {
            "status": "needs_review",
            "vehicle": dict(vehicle),
            "canonical_vehicle": dict(vehicle),
            "requested_components": [],
            "required_supporting_components": [],
            "recommended_supporting_components": [],
            "selected_articles": [],
            "review_reasons": ["no_component_detected"],
            "labor": empty_quote["labor"],
            "quote": empty_quote,
            "procedure": _empty_composed_procedure("No component detected"),
            "parts": empty_quote["parts_summary"],
            "images": [],
            "visual_artifacts": [],
            "source_watermarks": [],
            "quote_identity": empty_quote["quote_identity"],
            "procedure_revision": "procedure:none",
        }

    selected_records, selected_by_component, selection_reasons = _select_quote_articles(
        requested_components, normalized_articles
    )
    labor, labor_reasons = _calculate_categorized_labor(selected_records)
    parts = _collect_parts_quote(selected_records)
    source_article_ids = [
        str(record["article"].get("article_id"))
        for record in selected_records
        if str(record["article"].get("article_id", "")).strip()
    ]
    evidence_ids = sorted(
        {
            evidence_id
            for record in selected_records
            for evidence_id in _article_evidence_ids(record["article"])
        }
        | {
            evidence_id
            for operation in labor["operations"]
            for evidence_id in operation.get("evidence_ids", [])
        }
    )
    watermarks = _source_watermarks(selected_records)
    required_supporting = sorted(
        record["component"]
        for record in selected_records
        if not record["requested"] and record["category"] == "required"
    )
    recommended_supporting = sorted(
        record["component"]
        for record in selected_records
        if not record["requested"] and record["category"] == "recommended"
    )
    parts_review_reasons = list(parts.get("review_reasons", []))
    public_parts = {key: value for key, value in parts.items() if key != "review_reasons"}
    source_images = _collect_images(record["article"] for record in selected_records)
    visual_artifacts, visual_review_reasons = _vectorize_selected_visuals(
        selected_records, vectorizer=vectorizer
    )
    source_visual_refs = [artifact["source_ref"] for artifact in visual_artifacts]
    derived_visual_refs = [artifact["derived_ref"] for artifact in visual_artifacts]
    quote = {
        "vehicle": dict(vehicle),
        "required_hours": labor["required_hours"],
        "recommended_hours": labor["recommended_hours"],
        "total_hours": labor["total_hours"],
        "overlap_hours_removed": labor["overlap_hours_removed"],
        "required_operations": labor["required_operations"],
        "recommended_operations": labor["recommended_operations"],
        "overlap_operations": labor["overlap_operations"],
        "parts": public_parts["items"],
        "evidence": [{"evidence_id": evidence_id} for evidence_id in evidence_ids],
        "currency": public_parts["currency"],
        # Compatibility and audit fields are derived from the same canonical
        # values; they do not create a second arithmetic implementation.
        "labor": labor,
        "parts_summary": public_parts,
        "source_article_ids": source_article_ids,
        "evidence_ids": evidence_ids,
        "source_watermarks": watermarks,
        "requested_components": requested_components,
        "required_supporting_components": required_supporting,
        "recommended_supporting_components": recommended_supporting,
        "visual_artifacts": visual_artifacts,
        "source_visual_refs": source_visual_refs,
        "derived_visual_refs": derived_visual_refs,
    }
    quote["quote_identity"] = _json_fingerprint(quote)

    deterministic_procedure = _compose_composed_procedure(
        selected_records,
        labor["operations"],
        title=_quote_title(requested_components, required_supporting, recommended_supporting),
    )
    composition_failed = False
    if mercury_client is None:
        procedure = compose_procedure_revision(
            {**quote, "procedure": deterministic_procedure},
            [record["article"] for record in selected_records],
        )
    else:
        try:
            procedure = compose_procedure_revision(
                {**quote, "procedure": deterministic_procedure},
                [record["article"] for record in selected_records],
                mercury_client=mercury_client,
            )
        except Exception:
            # A model/provider failure must not discard the deterministic quote
            # and source-bound procedure already calculated by the application.
            procedure = compose_procedure_revision(
                {**quote, "procedure": deterministic_procedure},
                [record["article"] for record in selected_records],
            )
            composition_failed = True
    review_reasons = sorted(set(selection_reasons + labor_reasons))
    review_reasons.extend(parts_review_reasons)
    review_reasons.extend(visual_review_reasons)
    if composition_failed:
        review_reasons.append("procedure_composition_failed")
    if procedure.get("requires_review"):
        review_reasons.append("procedure_requires_review")
    # unknown_price_ids is diagnostic input, not part of the public quote
    # contract.
    parts = public_parts
    status = "ready" if not review_reasons else "needs_review"
    procedure_revision = str(procedure.get("revision_id") or "")
    derived_id = _quote_derived_article_id(
        vehicle,
        requested_components,
        required_supporting,
        recommended_supporting,
    )
    fingerprint = _json_fingerprint(
        {
            "vehicle": dict(vehicle),
            "requested_components": requested_components,
            "required_supporting_components": required_supporting,
            "recommended_supporting_components": recommended_supporting,
            "source_watermarks": watermarks,
            "quote_identity": quote["quote_identity"],
            "procedure_revision": procedure_revision,
            "procedure": procedure,
            "visual_artifacts": visual_artifacts,
        }
    )
    result = {
        "status": status,
        "vehicle": dict(vehicle),
        "canonical_vehicle": dict(vehicle),
        "requested_components": requested_components,
        "required_supporting_components": required_supporting,
        "recommended_supporting_components": recommended_supporting,
        "selected_articles": source_article_ids,
        "review_reasons": sorted(set(review_reasons)),
        "labor": labor,
        "quote": quote,
        "procedure": procedure,
        "parts": parts,
        "images": source_images,
        "visual_artifacts": visual_artifacts,
        "source_visual_refs": source_visual_refs,
        "derived_visual_refs": derived_visual_refs,
        "source_watermarks": watermarks,
        "quote_identity": quote["quote_identity"],
        "procedure_revision": procedure_revision,
        "derived_article": {
            "article_id": derived_id,
            "revision_id": f"revision:{fingerprint[:24]}",
            "title": procedure["title"],
            "status": status,
            "fingerprint": fingerprint,
            "source_article_ids": source_article_ids,
            "evidence_ids": evidence_ids,
            "canonical_vehicle": dict(vehicle),
            "required_operations": labor["required_operations"],
            "recommended_operations": labor["recommended_operations"],
            "source_watermarks": watermarks,
            "quote_identity": quote["quote_identity"],
            "procedure_revision": procedure_revision,
            "visual_artifacts": visual_artifacts,
        },
    }
    # Keep the source selection available to the procedure validator without
    # leaking an internal record into the returned contract.
    del selected_by_component
    return result


def compose_procedure_revision(
    quote: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
    *,
    mercury_client: Any | None = None,
) -> dict[str, Any]:
    """Compose one immutable, reusable procedure revision from a quote."""

    if not isinstance(quote, Mapping):
        raise ValueError("quote must be an object")
    vehicle = quote.get("vehicle") or quote.get("canonical_vehicle")
    if not isinstance(vehicle, Mapping) or not vehicle.get("make") or not vehicle.get("model"):
        raise ValueError("quote must include canonical vehicle identity")
    normalized_articles = _flatten_articles(articles)
    source_ids = {
        str(value)
        for value in quote.get("source_article_ids", quote.get("selected_articles", []))
        if str(value).strip()
    }
    selected_articles = [
        article
        for article in normalized_articles
        if not source_ids or str(article.get("article_id", "")) in source_ids
    ]
    if source_ids and {str(article.get("article_id", "")) for article in selected_articles} != source_ids:
        raise ValueError("quote references an unavailable source article")
    records = _records_for_quote(quote, selected_articles)
    labor = quote.get("labor")
    if not isinstance(labor, Mapping):
        nested_quote = quote.get("quote")
        labor = nested_quote.get("labor", {}) if isinstance(nested_quote, Mapping) else {}
    if not isinstance(labor, Mapping):
        labor = {}
    if not labor:
        labor = {
            "required_hours": quote.get("required_hours", 0.0),
            "recommended_hours": quote.get("recommended_hours", 0.0),
            "total_hours": quote.get("total_hours"),
            "overlap_hours_removed": quote.get("overlap_hours_removed", 0.0),
            "overlap_operations": quote.get("overlap_operations", []),
            "required_operations": quote.get("required_operations", []),
            "recommended_operations": quote.get("recommended_operations", []),
        }
        labor["operations"] = [
            operation
            for operation in [
                *labor["required_operations"],
                *labor["recommended_operations"],
            ]
            if isinstance(operation, Mapping)
        ]
    operations = labor.get("operations", [])
    if not isinstance(operations, list):
        operations = []
    title = str(
        (quote.get("procedure") or {}).get("title")
        if isinstance(quote.get("procedure"), Mapping)
        else ""
    ).strip() or _quote_title(
        [str(value) for value in quote.get("requested_components", [])],
        [str(value) for value in quote.get("required_supporting_components", [])],
        [str(value) for value in quote.get("recommended_supporting_components", [])],
    )
    deterministic = _compose_composed_procedure(records, operations, title=title)
    if mercury_client is not None:
        # The legacy helper is kept as the compatibility entry point used by
        # worker.py.  It now delegates to the same strict validator.
        procedure = compose_procedure_with_llm(
            mercury_client,
            "",
            vehicle,
            selected_articles,
            labor,
            deterministic,
            quote_context={**dict(quote), "procedure": deterministic},
        )
    else:
        procedure = deterministic
    revision_fingerprint = _json_fingerprint(
        {
            "vehicle": dict(vehicle),
            "quote_identity": quote.get("quote_identity"),
            "source_watermarks": quote.get("source_watermarks", []),
            "source_article_ids": sorted(source_ids),
            "procedure": procedure,
        }
    )
    return {
        **procedure,
        "revision_id": f"procedure-revision:{revision_fingerprint[:24]}",
        "procedure_revision": f"procedure-v{revision_fingerprint[:12]}",
        "source_article_ids": sorted(source_ids),
        "source_watermarks": sorted(
            str(value) for value in quote.get("source_watermarks", []) if str(value).strip()
        ),
    }


def _select_quote_articles(
    requested_components: list[str], articles: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    selected_by_component: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    selected_ids: set[str] = set()
    selected_records_by_id: dict[str, dict[str, Any]] = {}
    for component in requested_components:
        candidates = [article for article in articles if component in _article_components(article)]
        candidates.sort(
            key=lambda item: (-_article_score(item, component), str(item.get("article_id", "")))
        )
        if not candidates:
            reasons.append(f"missing_article:{component}")
            continue
        article = candidates[0]
        article_id = str(article.get("article_id", "")).strip()
        existing = selected_records_by_id.get(article_id) if article_id else None
        if existing is not None:
            existing["components"] = sorted(set(existing["components"]) | {component})
            selected_by_component[component] = existing
            continue
        record = {
            "article": article,
            "component": component,
            "components": [component],
            "category": "required",
            "requested": True,
        }
        selected.append(record)
        selected_by_component[component] = record
        if article_id:
            selected_ids.add(article_id)
            selected_records_by_id[article_id] = record

    for article in articles:
        article_id = str(article.get("article_id", ""))
        if article_id in selected_ids:
            continue
        component = _article_primary_component(article)
        if not component:
            continue
        category = next(
            (
                _support_category(article, requested)
                for requested in requested_components
                if _support_category(article, requested) is not None
            ),
            None,
        )
        if category is None:
            continue
        support_components = sorted(_article_components(article))
        if not support_components:
            support_components = [component]
        selected.append(
            {
                "article": article,
                "component": component,
                "components": support_components,
                "category": category,
                "requested": False,
            }
        )
        if article_id:
            selected_ids.add(article_id)
    return selected, selected_by_component, reasons


def _records_for_quote(quote: Mapping[str, Any], articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requested = {str(value) for value in quote.get("requested_components", [])}
    required = {str(value) for value in quote.get("required_supporting_components", [])}
    recommended = {str(value) for value in quote.get("recommended_supporting_components", [])}
    records: list[dict[str, Any]] = []
    for article in articles:
        article_components = _article_components(article)
        selected_components = article_components & (requested | required | recommended)
        if selected_components:
            components = sorted(selected_components)
        else:
            primary = _article_primary_component(article) or str(article.get("component", ""))
            components = [primary] if primary else []
        component = components[0] if components else ""
        category = "required" if article_components & (requested | required) else "recommended"
        records.append(
            {
                "article": article,
                "component": component,
                "components": components,
                "category": category,
                "requested": bool(article_components & requested),
            }
        )
    return records


def _record_components(record: Mapping[str, Any]) -> list[str]:
    values = record.get("components")
    matches = set(_component_matches(values))
    if not matches:
        matches.update(_component_matches(record.get("component", "")))
    return sorted(matches)


def _calculate_categorized_labor(
    selected_records: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    merged: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
    standalone = Decimal("0")
    required_hours = Decimal("0")
    recommended_hours = Decimal("0")
    reasons: list[str] = []
    for record in selected_records:
        article = record["article"]
        record_components = _record_components(record)
        component = record_components[0] if record_components else str(record.get("component", ""))
        default_category = str(record.get("category") or "required")
        operations = article.get("operations", article.get("labor_operations", []))
        if not isinstance(operations, list) or not operations:
            operations = [
                {
                    "operation_id": f"replace-{component}",
                    "action": f"Replace {component.replace('_', ' ')}",
                    "duration_hours": article.get("labor_hours"),
                }
            ]
        for index, raw_value in enumerate(operations):
            raw = raw_value if isinstance(raw_value, Mapping) else {"action": str(raw_value)}
            action = str(
                raw.get("action") or raw.get("name") or f"Perform {component} work"
            ).strip()
            operation_id = _stable_operation_id(raw, action, component, index)
            scope = _shared_work_scope(raw, operation_id, component, index)
            identity = (operation_id, scope)
            operation_components = sorted(
                set(_component_matches(raw.get("components")))
                or set(record_components)
                or {component}
            )
            duration = _decimal_hours(
                raw.get("duration_hours", raw.get("hours", raw.get("labor_hours")))
            )
            category = _operation_category(raw, default_category)
            if duration is None:
                reasons.append(f"unknown_duration:{operation_id}")
            else:
                standalone += duration
                if category == "required":
                    required_hours += duration
                else:
                    recommended_hours += duration
            evidence = sorted(
                set(_operation_evidence_ids(raw, article))
            )
            current = merged.get(identity)
            if current is None:
                current = {
                    "operation_id": operation_id,
                    "action": action,
                    "duration_hours": float(duration) if duration is not None else None,
                    "raw_hours": float(duration) if duration is not None else None,
                    "components": operation_components,
                    "category": category,
                    "categories": [category],
                    "shared_work_scope": scope,
                    "source_article_ids": [str(article.get("article_id", ""))],
                    "evidence_ids": evidence,
                    "origin": "source_operation",
                    "contributions": [
                        {
                            "components": operation_components,
                            "category": category,
                            "duration_hours": float(duration) if duration is not None else None,
                            "source_article_id": str(article.get("article_id", "")),
                        }
                    ],
                }
                merged[identity] = current
            else:
                if (
                    current["duration_hours"] is not None
                    and duration is not None
                    and current["duration_hours"] != float(duration)
                ):
                    reasons.append(f"conflicting_duration:{operation_id}")
                if _normalize_text(current["action"]) != _normalize_text(action):
                    reasons.append(f"conflicting_action:{operation_id}")
                current["components"] = sorted(set(current["components"]) | set(operation_components))
                current["categories"] = sorted(set(current["categories"]) | {category})
                current["category"] = (
                    "required" if "required" in current["categories"] else "recommended"
                )
                current["source_article_ids"] = sorted(
                    set(current["source_article_ids"]) | {str(article.get("article_id", ""))}
                )
                current["evidence_ids"] = sorted(set(current["evidence_ids"]) | set(evidence))
                if current["raw_hours"] is not None and duration is not None:
                    current["raw_hours"] = float(Decimal(str(current["raw_hours"])) + duration)
                current["contributions"].append(
                    {
                        "components": operation_components,
                        "category": category,
                        "duration_hours": float(duration) if duration is not None else None,
                        "source_article_id": str(article.get("article_id", "")),
                    }
                )
    unique_hours = sum(
        (
            Decimal(str(operation["duration_hours"]))
            for operation in merged.values()
            if operation["duration_hours"] is not None
        ),
        Decimal("0"),
    )
    overlap_hours = max(Decimal("0"), standalone - unique_hours)
    overlap_operations: list[dict[str, Any]] = []
    for operation in merged.values():
        contributions = operation["contributions"]
        components = sorted(
            {
                component
                for item in contributions
                for component in item.get("components", [])
            }
        )
        components = sorted(set(components) | set(operation["components"]))
        if len(components) < 2:
            continue
        raw_hours = sum(
            (Decimal(str(item["duration_hours"])) for item in contributions if item["duration_hours"] is not None),
            Decimal("0"),
        )
        counted_hours = Decimal(str(operation["duration_hours"])) if operation["duration_hours"] is not None else None
        if counted_hours is None:
            continue
        deducted_hours = raw_hours - counted_hours
        if deducted_hours <= 0:
            continue
        overlap_operations.append(
            {
                "operation_id": operation["operation_id"],
                "shared_work_scope": operation["shared_work_scope"],
                "counted_once_for": components,
                "raw_hours": float(raw_hours),
                "counted_hours": float(counted_hours),
                "deducted_hours": float(deducted_hours),
            }
        )
    for operation in merged.values():
        operation.pop("contributions", None)
    operations = list(merged.values())
    required_operations = [
        operation for operation in operations if operation["category"] == "required"
    ]
    recommended_operations = [
        operation for operation in operations if operation["category"] == "recommended"
    ]
    has_invalid = bool(reasons)
    counted_required = sum(
        (
            Decimal(str(operation["duration_hours"]))
            for operation in required_operations
            if operation["duration_hours"] is not None
        ),
        Decimal("0"),
    )
    counted_recommended = sum(
        (
            Decimal(str(operation["duration_hours"]))
            for operation in recommended_operations
            if operation["duration_hours"] is not None
        ),
        Decimal("0"),
    )
    category_subtotals = {
        "required": {
            "raw_hours": float(required_hours),
            "counted_hours": float(counted_required),
            "overlap_hours_removed": float(max(Decimal("0"), required_hours - counted_required)),
        },
        "recommended": {
            "raw_hours": float(recommended_hours),
            "counted_hours": float(counted_recommended),
            "overlap_hours_removed": float(max(Decimal("0"), recommended_hours - counted_recommended)),
        },
    }
    labor = {
        "basis": "one_technician_standard_hours",
        "standalone_hours": float(standalone),
        "overlap_hours": float(overlap_hours),
        "total_labor_hours": None if has_invalid else float(unique_hours),
        "required_hours": float(required_hours),
        "recommended_hours": float(recommended_hours),
        "total_hours": None if has_invalid else float(unique_hours),
        "overlap_hours_removed": float(overlap_hours),
        "overlap_operations": overlap_operations,
        "required_operations": required_operations,
        "recommended_operations": recommended_operations,
        "category_subtotals": category_subtotals,
        "category_hours_after_overlap": {
            "required": float(counted_required),
            "recommended": float(counted_recommended),
        },
        "confidence": 0.0 if has_invalid else 1.0,
        "assumptions": [
            "required and recommended subtotals include their source operations",
            "operations with the same stable operation_id and shared work scope are counted once",
        ],
        "operations": operations,
    }
    return labor, sorted(set(reasons))


def _shared_work_scope(raw: Mapping[str, Any], operation_id: str, component: str, index: int) -> str:
    for key in (
        "shared_work_scope",
        "work_scope",
        "shared_scope",
        "overlap_group",
        "dedupe_key",
        "shared_operation_id",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            return value
    if raw.get("shared") is False:
        return f"{component}:{operation_id}:{index}"
    return operation_id


def _operation_category(raw: Mapping[str, Any], default: str) -> str:
    if raw.get("recommended") is True:
        return "recommended"
    if raw.get("required") is True:
        return "required"
    value = raw.get(
        "category",
        raw.get("operation_category", raw.get("labor_category", raw.get("support_category", default))),
    )
    normalized = str(value or default).strip().casefold().replace("_", " ").replace("-", " ")
    if normalized in {"recommended", "recommendation", "optional", "advisory"}:
        return "recommended"
    return "required"


def _article_primary_component(article: Mapping[str, Any]) -> str:
    direct = article.get("component") or article.get("component_key")
    if direct:
        matches = _component_matches(direct)
        if matches:
            return matches[0]
        normalized = re.sub(r"[^a-z0-9]+", "_", str(direct).casefold()).strip("_")
        if normalized:
            return normalized
    matches = _component_matches(article.get("title", ""))
    if matches:
        return matches[0]
    article_components = sorted(_article_components(article))
    return article_components[0] if article_components else ""


def _support_targets(article: Mapping[str, Any], key: str) -> set[str]:
    value = article.get(key, [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return set()
    targets: set[str] = set()
    for item in value:
        targets.update(_component_matches(item))
        normalized = re.sub(r"[^a-z0-9]+", "_", str(item).casefold()).strip("_")
        if normalized:
            targets.add(normalized)
    return targets


def _support_category(article: Mapping[str, Any], requested_component: str) -> str | None:
    if requested_component in _support_targets(article, "required_for"):
        return "required"
    if requested_component in _support_targets(article, "recommended_for"):
        return "recommended"
    supporting_targets = set()
    for key in ("supporting_for", "supports", "support_for", "related_components"):
        supporting_targets.update(_support_targets(article, key))
    if requested_component not in supporting_targets:
        return None
    if article.get("recommended") is True:
        return "recommended"
    if article.get("required") is True:
        return "required"
    value = article.get(
        "support_category",
        article.get("operation_category", article.get("category", "required")),
    )
    normalized = str(value).casefold().replace("_", " ").replace("-", " ")
    return "recommended" if normalized in {"recommended", "optional", "advisory"} else "required"


def _detailed_empty_labor() -> dict[str, Any]:
    return {
        "basis": "one_technician_standard_hours",
        "standalone_hours": 0.0,
        "overlap_hours": 0.0,
        "total_labor_hours": None,
        "required_hours": 0.0,
        "recommended_hours": 0.0,
        "total_hours": None,
        "overlap_hours_removed": 0.0,
        "overlap_operations": [],
        "required_operations": [],
        "recommended_operations": [],
        "confidence": 0.0,
        "assumptions": [],
        "operations": [],
    }


def _empty_parts_quote() -> dict[str, Any]:
    return {
        "items": [],
        "subtotal": 0.0,
        "currency": "USD",
        "price_basis": "source_catalog_only",
        "markup_applied": False,
    }


def _collect_parts_quote(selected_records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    parts: OrderedDict[str, dict[str, Any]] = OrderedDict()
    review_reasons: set[str] = set()
    for record in selected_records:
        article = record["article"]
        article_id = str(article.get("article_id", ""))
        values: list[Any] = []
        for key in ("parts", "part", "part_prices", "parts_prices", "price_snapshots"):
            value = article.get(key, [])
            if isinstance(value, (str, Mapping)):
                value = [value]
            if isinstance(value, list):
                values.extend(value)
        for raw_value in values:
            raw = raw_value if isinstance(raw_value, Mapping) else {"name": str(raw_value)}
            source_number = str(
                raw.get("source_part_number")
                or raw.get("part_number")
                or raw.get("partNumber")
                or ""
            ).strip()
            name = str(raw.get("name") or raw.get("part_name") or raw.get("partDescription") or source_number).strip()
            part_id = str(
                raw.get("canonical_part_id")
                or raw.get("part_id")
                or raw.get("id")
                or source_number
                or re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
            ).strip()
            if not part_id:
                continue
            amount_value = _first_present(
                raw, ("amount", "price", "unit_price", "source_price")
            )
            amount = _decimal_amount(amount_value[1]) if amount_value[0] else None
            if not amount_value[0]:
                review_reasons.add(f"unknown_part_price:{part_id}")
            elif amount is None:
                review_reasons.add(f"invalid_part_price:{part_id}")
            quantity_value = raw.get("quantity", 1)
            quantity = _decimal_amount(quantity_value)
            quantity_invalid = quantity is None
            if quantity is None:
                review_reasons.add(f"invalid_part_quantity:{part_id}")
                quantity = Decimal("1")
            currency = str(raw.get("currency") or article.get("currency") or "USD").upper()
            evidence = sorted(
                set(_operation_evidence_ids(raw, article))
            )
            existing = parts.get(part_id)
            if existing is None:
                item = {
                    "part_id": part_id,
                    "source_part_number": source_number or part_id,
                    "name": name or part_id,
                    "quantity": _number_from_decimal(quantity),
                    "amount": float(amount) if amount is not None else None,
                    "currency": currency,
                    "priced_at": raw.get("priced_at"),
                    "source_snapshot_id": raw.get("source_snapshot_id"),
                    "source_uri": raw.get("source_uri") or raw.get("source"),
                    "freshness": raw.get("freshness", "unknown"),
                    "refresh_status": raw.get("refresh_status", "current"),
                    "markup_applied": False,
                    "source_article_ids": [article_id],
                    "evidence_ids": evidence,
                    "requires_review": (not amount_value[0]) or amount is None or quantity_invalid,
                }
                parts[part_id] = {
                    key: value
                    for key, value in item.items()
                    if value not in (None, [], "")
                }
            else:
                existing_amount = _decimal_amount(existing.get("amount"))
                if existing_amount is not None and amount is not None and existing_amount != amount:
                    existing["amount"] = None
                    existing["price_conflict"] = True
                    existing["requires_review"] = True
                    review_reasons.add(f"conflicting_part_price:{part_id}")
                if str(existing.get("currency", "USD")) != currency:
                    existing["currency_conflict"] = True
                    existing["requires_review"] = True
                    review_reasons.add(f"conflicting_part_currency:{part_id}")
                existing["quantity"] = _number_from_decimal(
                    Decimal(str(existing.get("quantity", 1))) + quantity
                )
                existing["source_article_ids"] = sorted(
                    set(existing.get("source_article_ids", [])) | {article_id}
                )
                existing["evidence_ids"] = sorted(
                    set(existing.get("evidence_ids", [])) | set(evidence)
                )
                if amount is None and amount_value[0]:
                    existing["requires_review"] = True
                    review_reasons.add(f"invalid_part_price:{part_id}")
    subtotal = Decimal("0")
    currencies: set[str] = set()
    for item in parts.values():
        currencies.add(str(item.get("currency", "USD")))
        if item.get("amount") is not None and not item.get("price_conflict"):
            subtotal += Decimal(str(item["amount"])) * Decimal(str(item.get("quantity", 1)))
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "items": list(parts.values()),
        "subtotal": float(subtotal),
        "currency": sorted(currencies)[0] if len(currencies) == 1 else "MULTI",
        "price_basis": "source_catalog_only",
        "markup_applied": False,
        "review_reasons": sorted(review_reasons),
    }


def _decimal_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _first_present(raw: Mapping[str, Any], keys: Iterable[str]) -> tuple[bool, Any]:
    for key in keys:
        if key in raw:
            return True, raw[key]
    return False, None


def _number_from_decimal(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _compose_composed_procedure(
    selected_records: Iterable[Mapping[str, Any]],
    operations: Iterable[Mapping[str, Any]],
    *,
    title: str,
) -> dict[str, Any]:
    records = list(selected_records)
    article_by_id = {
        str(record["article"].get("article_id", "")): record for record in records
    }
    steps: list[dict[str, Any]] = []
    for sequence, operation in enumerate(operations, 1):
        article_ids = [
            str(value)
            for value in operation.get("source_article_ids", [])
            if str(value).strip()
        ]
        if not article_ids:
            article_ids = sorted(article_by_id)
        components = sorted(
            {
                str(value)
                for value in operation.get("components", [])
                if str(value).strip()
            }
        )
        step = {
            "sequence": sequence,
            "operation_id": str(operation.get("operation_id", "")),
            "action": str(operation.get("action", "")).strip(),
            "components": components,
            "category": str(operation.get("category", "required")),
            "source_article_ids": sorted(set(article_ids)),
            "evidence_ids": sorted(
                str(value) for value in operation.get("evidence_ids", []) if str(value).strip()
            ),
            "origin": "shared_source_step" if len(components) > 1 else "source_step",
            "requires_review": not bool(operation.get("evidence_ids")),
        }
        steps.append(step)
    warnings = _collect_safety_warnings(records)
    requires_review = any(step["requires_review"] for step in steps) or any(
        warning["requires_review"] for warning in warnings
    )
    return {
        "title": title or "Vehicle service procedure",
        "steps": steps,
        "warnings": warnings,
        "requires_review": requires_review,
        "review_state": "UNREVIEWED",
        "review_label": "UNREVIEWED — human review pending",
        "generation": "deterministic",
    }


def _collect_safety_warnings(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    warnings: OrderedDict[tuple[str, tuple[str, ...]], dict[str, Any]] = OrderedDict()
    for record in records:
        article = record["article"]
        article_id = str(article.get("article_id", ""))
        article_evidence = set(_article_evidence_ids(article))
        values: list[Any] = []
        for key in ("safety_warnings", "safety", "warnings"):
            value = article.get(key, [])
            if isinstance(value, (str, Mapping)):
                value = [value]
            if isinstance(value, list):
                values.extend(value)
        for raw in values:
            if isinstance(raw, Mapping):
                message = str(raw.get("message") or raw.get("warning") or raw.get("text") or "").strip()
                explicit_evidence = "evidence_ids" in raw or "evidence_id" in raw
                requested_evidence = (
                    set(_string_ids(raw.get("evidence_ids")))
                    | set(_string_ids(raw.get("evidence_id")))
                ) if explicit_evidence else article_evidence
                evidence_ids = sorted(requested_evidence & article_evidence)
                invalid_evidence = requested_evidence - article_evidence
                warning_id = str(raw.get("warning_id") or "").strip()
                source_ids = set(_string_ids(raw.get("source_article_ids")))
                invalid_source = source_ids and source_ids != {article_id}
                requires_review = bool(raw.get("requires_review", False)) or not evidence_ids or bool(invalid_evidence) or bool(invalid_source)
            else:
                message = str(raw).strip()
                evidence_ids = sorted(article_evidence)
                warning_id = ""
                requires_review = not bool(evidence_ids)
            if not message:
                continue
            warning_id = warning_id or _warning_id(article_id, message, evidence_ids)
            key = (message, tuple(evidence_ids))
            warnings.setdefault(
                key,
                {
                    "warning_id": warning_id,
                    "message": message,
                    "source_article_ids": [article_id],
                    "evidence_ids": evidence_ids,
                    "requires_review": requires_review,
                },
            )
            if article_id not in warnings[key]["source_article_ids"]:
                warnings[key]["source_article_ids"].append(article_id)
            warnings[key]["requires_review"] = warnings[key]["requires_review"] or requires_review
    return list(warnings.values())


def _warning_id(article_id: str, message: str, evidence_ids: Iterable[str]) -> str:
    return f"warning:{_json_fingerprint((article_id, message, sorted(evidence_ids)))[:24]}"


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _quote_title(requested: list[str], required: list[str], recommended: list[str]) -> str:
    components = list(requested)
    components.extend(required)
    components.extend(recommended)
    if not components:
        return "Vehicle service procedure"
    return " and ".join(f"{component.replace('_', ' ')} service" for component in components)


def _empty_composed_procedure(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "steps": [],
        "warnings": [],
        "requires_review": True,
        "review_state": "UNREVIEWED",
        "review_label": "UNREVIEWED — human review pending",
        "generation": "deterministic",
    }


def _source_watermarks(records: Iterable[Mapping[str, Any]]) -> list[str]:
    watermarks: set[str] = set()
    for record in records:
        article = record["article"]
        for key in ("source_watermark", "source_version", "watermark"):
            value = str(article.get(key, "")).strip()
            if value:
                watermarks.add(value)
        for evidence in article.get("evidence", []) if isinstance(article.get("evidence", []), list) else []:
            if isinstance(evidence, Mapping):
                value = str(evidence.get("source_watermark") or evidence.get("source_version") or "").strip()
                if value:
                    watermarks.add(value)
    return sorted(watermarks)


def _json_fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _quote_derived_article_id(
    vehicle: Mapping[str, Any], requested: list[str], required: list[str], recommended: list[str]
) -> str:
    vehicle_slug = _vehicle_slug(vehicle)
    operation_slug = "+".join(
        [*requested, *(f"required-{value}" for value in required), *(f"recommended-{value}" for value in recommended)]
    )
    identity = _json_fingerprint(
        {
            "vehicle": dict(vehicle),
            "requested": sorted(requested),
            "required": sorted(required),
            "recommended": sorted(recommended),
            "contract_version": 3,
        }
    )[:12]
    return f"combined:{vehicle_slug}:{operation_slug or 'service'}:v2:{identity}"


__all__ = [
    "build_quote_and_procedure",
    "compose_procedure_revision",
    "plan_job",
    "translate_job_query_with_llm",
]


def translate_job_query_with_llm(
    client: Any,
    query: str,
    vehicle: Mapping[str, Any],
) -> dict[str, Any]:
    """Translate natural language into safe component intents, not URLs.

    Mercury-2 may identify source terminology, but the connector remains the
    only code that constructs AutoAPI paths. This keeps model output bounded
    to an allowlisted component vocabulary and search terms.
    """

    allowed_components = sorted(set(_ALIASES.values()))
    prompt = (
        "Translate this vehicle repair request into JSON for a fixed AutoData connector. "
        "Return only components from the allowlist and source article search terms. "
        "Never return URLs, HTTP methods, credentials, or provider route paths. "
        'Use this shape exactly: {"components":["water_pump"],"source_queries":[]} . '
        f"Allowlist: {json.dumps(allowed_components)}\n"
        + json.dumps({"query": query, "vehicle": dict(vehicle)}, sort_keys=True)
    )
    response = client.complete_json(prompt)
    if not isinstance(response, Mapping):
        raise ValueError("Mercury-2 query translation response must be an object")
    raw_components = response.get("components")
    if isinstance(raw_components, str):
        raw_components = [raw_components]
    if not isinstance(raw_components, list):
        raise ValueError("Mercury-2 query translation components must be an array")
    components: list[str] = []
    for value in raw_components:
        component = str(value).strip()
        if component not in allowed_components:
            raise ValueError(f"Mercury-2 returned unsupported component: {component}")
        if component not in components:
            components.append(component)
    raw_queries = response.get("source_queries", [])
    if not isinstance(raw_queries, list):
        raise ValueError("Mercury-2 query translation source_queries must be an array")
    source_queries: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_queries):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Mercury-2 source query {index} must be an object")
        component = str(raw.get("component", "")).strip()
        terms = raw.get("article_terms", [])
        if component not in components or not isinstance(terms, list):
            raise ValueError(f"Mercury-2 source query {index} is invalid")
        clean_terms = [str(term).strip() for term in terms if str(term).strip()]
        if not clean_terms:
            raise ValueError(f"Mercury-2 source query {index} requires article_terms")
        source_queries.append({"component": component, "article_terms": clean_terms[:8]})
    return {
        "components": components,
        "source_queries": source_queries,
        "generation": "mercury-2",
    }


def compose_procedure_with_llm(
    client: Any,
    query: str,
    vehicle: Mapping[str, Any],
    selected_articles: Iterable[Mapping[str, Any]],
    labor: Mapping[str, Any],
    deterministic_procedure: Mapping[str, Any],
    quote_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask Mercury-2 to consolidate only the already validated source steps."""

    source_articles = [dict(article) for article in selected_articles]
    from .mercury2 import compose_procedure_draft

    article_payload: list[dict[str, Any]] = []
    allowed_article_ids: set[str] = set()
    allowed_evidence_ids: set[str] = set()
    allowed_components: set[str] = set()
    articles_by_id: dict[str, Mapping[str, Any]] = {}
    for article in source_articles:
        article_id = str(article.get("article_id", "")).strip()
        if not article_id:
            raise ValueError("Mercury-2 procedure source article requires article_id")
        allowed_article_ids.add(article_id)
        articles_by_id[article_id] = article
        article_components = _article_components(article)
        allowed_components.update(article_components)
        article_evidence_ids = _article_evidence_ids(article)
        allowed_evidence_ids.update(article_evidence_ids)
        operations = _article_operations(article)
        for operation in operations:
            allowed_components.update(_component_matches(operation.get("component")))
            allowed_components.update(_component_matches(operation.get("components")))
            allowed_evidence_ids.update(_operation_evidence_ids(operation, article))
        source_record = {
            "article": article,
            "component": _article_primary_component(article),
            "components": sorted(article_components),
            "category": "required",
            "requested": True,
        }
        article_payload.append(
            {
                "article_id": article_id,
                "title": article.get("title"),
                "body": article.get("body"),
                "components": sorted(article_components),
                "steps": article.get("steps", operations),
                "operations": operations,
                "evidence_ids": sorted(
                    set(article_evidence_ids)
                    | {
                        evidence_id
                        for operation in operations
                        for evidence_id in _operation_evidence_ids(operation, article)
                    }
                ),
                "safety_warnings": _collect_safety_warnings([source_record]),
            }
        )
    complete_quote = dict(quote_context or {})
    complete_quote.update(
        {
            "vehicle": dict(vehicle),
            "labor": dict(labor),
            "procedure": dict(deterministic_procedure),
        }
    )
    response = compose_procedure_draft(
        client,
        vehicle=vehicle,
        quote=complete_quote,
        articles=article_payload,
    )
    return _validate_llm_procedure(
        response,
        vehicle=vehicle,
        articles_by_id=articles_by_id,
        allowed_article_ids=allowed_article_ids,
        allowed_evidence_ids=allowed_evidence_ids,
        allowed_components=allowed_components,
        labor=labor,
        deterministic_procedure=deterministic_procedure,
    )


def _article_operations(article: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = article.get("operations", article.get("labor_operations", []))
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, Mapping)]


def _validate_llm_procedure(
    response: Mapping[str, Any],
    *,
    vehicle: Mapping[str, Any],
    articles_by_id: Mapping[str, Mapping[str, Any]],
    allowed_article_ids: set[str],
    allowed_evidence_ids: set[str],
    allowed_components: set[str],
    labor: Mapping[str, Any],
    deterministic_procedure: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        raise ValueError("Mercury-2 procedure response must be an object")
    if (
        not str(response.get("title", "")).strip()
        or not isinstance(response.get("steps"), list)
        or not isinstance(response.get("warnings"), list)
    ):
        raise ValueError("Mercury-2 procedure response requires title, steps, and warnings")
    top_level_allowed = {"title", "steps", "warnings", "requires_review", "excluded_operation_ids"}
    unexpected = set(response) - top_level_allowed
    if unexpected:
        raise ValueError(f"Mercury-2 procedure response has unsupported fields: {sorted(unexpected)}")

    raw_excluded = response.get("excluded_operation_ids", [])
    if not isinstance(raw_excluded, list):
        raise ValueError("Mercury-2 excluded_operation_ids must be an array")
    if any(not isinstance(value, str) or not value.strip() for value in raw_excluded):
        raise ValueError("Mercury-2 excluded_operation_ids must contain non-empty strings")
    excluded_operation_ids = {value.strip() for value in raw_excluded}
    if "requires_review" in response and not isinstance(response["requires_review"], bool):
        raise ValueError("Mercury-2 procedure requires_review must be a boolean")
    operation_provenance = _operation_provenance(labor, articles_by_id)
    known_operation_ids = set(operation_provenance)
    if not excluded_operation_ids.issubset(known_operation_ids):
        raise ValueError("Mercury-2 procedure excludes an unsupported labor operation")

    validated_steps: list[dict[str, Any]] = []
    represented_operation_ids: set[str] = set()
    for index, raw_step in enumerate(response["steps"], 1):
        if not isinstance(raw_step, Mapping):
            raise ValueError(f"Mercury-2 procedure step {index} must be an object")
        step_allowed = {
            "operation_id",
            "action",
            "components",
            "category",
            "source_article_ids",
            "evidence_ids",
            "requires_review",
        }
        unexpected_step = set(raw_step) - step_allowed
        if unexpected_step:
            raise ValueError(
                f"Mercury-2 procedure step {index} has unsupported fields: {sorted(unexpected_step)}"
            )
        if not isinstance(raw_step.get("operation_id"), str):
            raise ValueError(f"Mercury-2 procedure step {index} requires operation provenance")
        operation_id = raw_step["operation_id"].strip()
        if not operation_id:
            raise ValueError(f"Mercury-2 procedure step {index} requires operation provenance")
        if operation_id not in operation_provenance:
            raise ValueError(f"Mercury-2 procedure step {index} references an unsupported operation")
        if operation_id in represented_operation_ids:
            raise ValueError(f"Mercury-2 procedure step {index} repeats an operation")
        expected = operation_provenance[operation_id]
        article_ids = _string_list(raw_step.get("source_article_ids"), "source article references", index)
        evidence_ids = _string_list(raw_step.get("evidence_ids"), "evidence references", index)
        if not article_ids:
            raise ValueError(f"Mercury-2 procedure step {index} has no article provenance")
        if not evidence_ids:
            raise ValueError(f"Mercury-2 procedure step {index} has no evidence provenance")
        if set(article_ids) != set(expected["source_article_ids"]):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid article provenance")
        if not set(article_ids).issubset(allowed_article_ids):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid article references")
        if set(evidence_ids) != set(expected["evidence_ids"]):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid evidence provenance")
        if not set(evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid evidence references")
        if not isinstance(raw_step.get("action"), str):
            raise ValueError(f"Mercury-2 procedure step {index} requires an action")
        action = raw_step["action"].strip()
        components = [
            value.strip() for value in raw_step.get("components", [])
        ] if isinstance(raw_step.get("components"), list) and all(
            isinstance(value, str) and value.strip() for value in raw_step.get("components", [])
        ) else []
        if not action or not components:
            raise ValueError(f"Mercury-2 procedure step {index} is incomplete")
        unsupported_components = set(components) - allowed_components
        if unsupported_components:
            raise ValueError(
                f"Mercury-2 procedure step {index} has unsupported components: {sorted(unsupported_components)}"
            )
        for article_id in article_ids:
            article_vehicle = articles_by_id[article_id].get("vehicle") or articles_by_id[article_id].get("vehicle_identity")
            if isinstance(article_vehicle, Mapping) and not _vehicle_scopes_match(vehicle, article_vehicle):
                raise ValueError(f"Mercury-2 procedure step {index} has a vehicle scope mismatch")
        raw_category = raw_step.get("category")
        if not isinstance(raw_category, str):
            raise ValueError(f"Mercury-2 procedure step {index} requires category provenance")
        category = raw_category.strip().casefold()
        if category not in {"required", "recommended"}:
            raise ValueError(f"Mercury-2 procedure step {index} has an unsupported category")
        if category != expected["category"]:
            raise ValueError(f"Mercury-2 procedure step {index} has invalid category provenance")
        if _normalize_text(action) != _normalize_text(expected["action"]):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid action provenance")
        if set(components) != set(expected["components"]):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid component provenance")
        if "requires_review" in raw_step and not isinstance(raw_step["requires_review"], bool):
            raise ValueError(f"Mercury-2 procedure step {index} requires a boolean review flag")
        represented_operation_ids.add(operation_id)
        step = {
            "sequence": index,
            "action": action,
            "components": sorted(set(components)),
            "category": expected["category"],
            "source_article_ids": sorted(set(article_ids)),
            "evidence_ids": sorted(set(evidence_ids)),
            "origin": "llm_wording",
            "requires_review": bool(raw_step.get("requires_review", False)),
        }
        step["operation_id"] = operation_id
        validated_steps.append(step)

    missing_operation_ids = known_operation_ids - represented_operation_ids - excluded_operation_ids
    if missing_operation_ids:
        raise ValueError(
            f"Mercury-2 procedure omits labor operations: {sorted(missing_operation_ids)}"
        )
    expected_warnings = {
        str(warning.get("warning_id")): warning
        for warning in deterministic_procedure.get("warnings", [])
        if isinstance(warning, Mapping) and str(warning.get("warning_id", "")).strip()
    }
    warnings = _validate_llm_warnings(
        response["warnings"],
        expected_warnings,
        allowed_article_ids,
        allowed_evidence_ids,
    )
    requires_review = bool(response.get("requires_review", False)) or bool(excluded_operation_ids) or any(
        step["requires_review"] for step in validated_steps
    ) or any(warning["requires_review"] for warning in warnings)
    return {
        "title": str(response["title"]).strip(),
        "steps": validated_steps,
        "warnings": warnings,
        "requires_review": requires_review,
        "review_state": "UNREVIEWED",
        "review_label": "UNREVIEWED — human review pending",
        "generation": "mercury-2",
        "excluded_operation_ids": sorted(excluded_operation_ids),
    }


def _string_list(value: Any, label: str, index: int) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Mercury-2 procedure step {index} requires {label} array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Mercury-2 procedure step {index} requires non-empty string {label}")
    return [item.strip() for item in value]


def _operation_provenance(
    labor: Mapping[str, Any], articles_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    operations = labor.get("operations", [])
    if not isinstance(operations, list):
        operations = []
    provenance: dict[str, dict[str, Any]] = {}
    for raw_operation in operations:
        if not isinstance(raw_operation, Mapping):
            continue
        operation_id = str(raw_operation.get("operation_id", "")).strip()
        if not operation_id:
            continue
        source_article_ids = set(_string_ids(raw_operation.get("source_article_ids")))
        evidence_ids = set(_string_ids(raw_operation.get("evidence_ids")))
        normalized_components = set(_component_matches(raw_operation.get("components")))
        category = str(raw_operation.get("category", "required")).strip().casefold()
        action = str(raw_operation.get("action", "")).strip()
        for article_id, article in articles_by_id.items():
            for index, source_operation in enumerate(_article_operations(article)):
                source_action = str(
                    source_operation.get("action") or source_operation.get("name") or ""
                ).strip()
                source_id = _stable_operation_id(
                    source_operation,
                    source_action,
                    _article_primary_component(article),
                    index,
                )
                if source_id != operation_id:
                    continue
                source_article_ids.add(article_id)
                evidence_ids.update(_operation_evidence_ids(source_operation, article))
                if not action:
                    action = source_action
                source_components = _component_matches(source_operation.get("components"))
                normalized_components.update(source_components or _article_components(article))
        if not normalized_components:
            for article_id in source_article_ids:
                if article_id in articles_by_id:
                    normalized_components.update(_article_components(articles_by_id[article_id]))
        if not action:
            action = operation_id.replace("-", " ")
        provenance[operation_id] = {
            "operation_id": operation_id,
            "action": action,
            "components": sorted(normalized_components),
            "category": category if category in {"required", "recommended"} else "required",
            "source_article_ids": sorted(source_article_ids),
            "evidence_ids": sorted(evidence_ids),
        }
    return provenance


def _validate_llm_warnings(
    raw_warnings: Any,
    expected_warnings: Mapping[str, Mapping[str, Any]],
    allowed_article_ids: set[str],
    allowed_evidence_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_warnings, list):
        raise ValueError("Mercury-2 procedure warnings must be an array")
    warnings: list[dict[str, Any]] = []
    represented_warning_ids: set[str] = set()
    for index, raw_warning in enumerate(raw_warnings, 1):
        if not isinstance(raw_warning, Mapping):
            raise ValueError(f"Mercury-2 warning {index} must be a structured object")
        unexpected = set(raw_warning) - {
            "warning_id",
            "message",
            "source_article_ids",
            "evidence_ids",
            "requires_review",
        }
        if unexpected:
            raise ValueError(f"Mercury-2 warning {index} has unsupported fields: {sorted(unexpected)}")
        warning_id = str(raw_warning.get("warning_id", "")).strip()
        expected = expected_warnings.get(warning_id)
        if expected is None:
            raise ValueError(f"Mercury-2 warning {index} has unsupported provenance")
        if not isinstance(raw_warning.get("warning_id"), str) or not isinstance(raw_warning.get("message"), str):
            raise ValueError(f"Mercury-2 warning {index} requires string identity and message")
        message = raw_warning["message"].strip()
        article_ids = _string_list(raw_warning.get("source_article_ids"), "warning article references", index)
        evidence_ids = _string_list(raw_warning.get("evidence_ids"), "warning evidence references", index)
        if set(article_ids) != set(expected.get("source_article_ids", [])):
            raise ValueError(f"Mercury-2 warning {index} has invalid article provenance")
        if set(evidence_ids) != set(expected.get("evidence_ids", [])):
            raise ValueError(f"Mercury-2 warning {index} has invalid evidence provenance")
        if not set(article_ids).issubset(allowed_article_ids):
            raise ValueError(f"Mercury-2 warning {index} has invalid article references")
        if not set(evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError(f"Mercury-2 warning {index} has invalid evidence references")
        if _normalize_text(message) != _normalize_text(expected.get("message", "")):
            raise ValueError(f"Mercury-2 warning {index} has invalid message provenance")
        if warning_id in represented_warning_ids:
            raise ValueError(f"Mercury-2 warning {index} repeats a warning")
        if not isinstance(raw_warning.get("requires_review"), bool):
            raise ValueError(f"Mercury-2 warning {index} requires a boolean review flag")
        requires_review = raw_warning["requires_review"] or not bool(evidence_ids)
        if expected.get("requires_review") and not requires_review:
            raise ValueError(f"Mercury-2 warning {index} cannot clear a source review requirement")
        if not message:
            raise ValueError(f"Mercury-2 warning {index} is incomplete")
        represented_warning_ids.add(warning_id)
        warnings.append(
            {
                "warning_id": warning_id,
                "message": message,
                "source_article_ids": sorted(set(article_ids)),
                "evidence_ids": sorted(set(evidence_ids)),
                "requires_review": requires_review,
            }
        )
    missing_warning_ids = set(expected_warnings) - represented_warning_ids
    if missing_warning_ids:
        raise ValueError(f"Mercury-2 procedure omits safety warnings: {sorted(missing_warning_ids)}")
    return warnings


def _vehicle_scopes_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for keys in (("vehicle_id",), ("year", "model_year"), ("make",), ("model",), ("region",)):
        left_value = next((left.get(key) for key in keys if left.get(key) is not None), None)
        right_value = next((right.get(key) for key in keys if right.get(key) is not None), None)
        if left_value is not None and right_value is not None and str(left_value).casefold() != str(right_value).casefold():
            return False
    return True
