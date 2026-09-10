"""Vehicle-scoped multi-component labor and procedure planning.

The labor calculation is deliberately deterministic.  A model may later
rewrite the validated procedure through the adapter boundary, but it cannot
invent labor values, vehicle facts, or evidence references.
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, InvalidOperation
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
    "caliper": "brake_caliper",
    "rotor": "brake_rotor",
    "rotors": "brake_rotor",
    "pads": "brake_pads",
    "pad": "brake_pads",
    "waterpump": "water_pump",
    "water-pump": "water_pump",
    "water_pump": "water_pump",
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
    normalized = re.sub(r"[^a-z0-9_ -]", " ", query.casefold())
    found: list[str] = []
    for token in re.findall(r"[a-z0-9_-]+", normalized):
        component = _ALIASES.get(token)
        if component and component not in found:
            found.append(component)
    return found


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
        flattened.append(article)
    return flattened


def _article_components(article: Mapping[str, Any]) -> set[str]:
    values: list[Any] = [article.get("component"), article.get("component_key"), article.get("components"), article.get("title"), article.get("bucket")]
    text = " ".join(str(value) for value in values if value is not None).casefold()
    return {canonical for token, canonical in _ALIASES.items() if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text)}


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
            evidence = sorted({str(item) for item in raw.get("evidence_ids", _article_evidence_ids(article)) if str(item).strip()})
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


def _article_evidence_ids(article: Mapping[str, Any]) -> list[str]:
    evidence = article.get("evidence", [])
    if isinstance(evidence, Mapping):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    return [str(item.get("evidence_id")) for item in evidence if isinstance(item, Mapping) and item.get("evidence_id")]


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
    return parsed if parsed >= 0 else None


def _empty_labor() -> dict[str, Any]:
    return {"basis": "one_technician_standard_hours", "standalone_hours": 0.0, "overlap_hours": 0.0, "total_labor_hours": None, "confidence": 0.0, "assumptions": [], "operations": []}


def _empty_procedure(title: str) -> dict[str, Any]:
    return {"title": title, "steps": [], "warnings": [], "requires_review": True}


def _vehicle_slug(vehicle: Mapping[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "-".join(str(vehicle.get(key, "")) for key in ("year", "make", "model" )).casefold()).strip("-")


def _fingerprint(vehicle: Mapping[str, Any], components: list[str], source_ids: list[str], labor: Mapping[str, Any], procedure: Mapping[str, Any]) -> str:
    payload = repr((dict(vehicle), components, source_ids, labor, procedure)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = ["plan_job"]


def compose_procedure_with_llm(
    client: Any,
    query: str,
    vehicle: Mapping[str, Any],
    selected_articles: Iterable[Mapping[str, Any]],
    labor: Mapping[str, Any],
    deterministic_procedure: Mapping[str, Any],
) -> dict[str, Any]:
    """Ask Mercury-2 to consolidate only the already validated source steps."""

    article_payload = []
    allowed_article_ids: set[str] = set()
    allowed_evidence_ids: set[str] = set()
    for article in selected_articles:
        article_id = str(article.get("article_id", ""))
        allowed_article_ids.add(article_id)
        allowed_evidence_ids.update(_article_evidence_ids(article))
        article_payload.append({
            "article_id": article_id,
            "title": article.get("title"),
            "body": article.get("body"),
            "steps": article.get("steps", article.get("operations", [])),
            "evidence_ids": _article_evidence_ids(article),
        })
    prompt = (
        "Compose a vehicle repair procedure as JSON. Use only the supplied article steps and evidence. "
        "Do not invent torque values, tools, safety facts, durations, or vehicle facts. "
        "Return title, steps, warnings, and requires_review. Every step must include sequence, action, "
        "components, source_article_ids, evidence_ids, origin, and requires_review.\n\n"
        + json.dumps({"query": query, "vehicle": dict(vehicle), "labor": labor, "articles": article_payload}, sort_keys=True)
    )
    response = client.complete_json(prompt)
    if not isinstance(response, Mapping):
        raise ValueError("Mercury-2 procedure response must be an object")
    steps = response.get("steps")
    if not isinstance(steps, list) or not response.get("title"):
        raise ValueError("Mercury-2 procedure response requires title and steps")
    validated_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps, 1):
        if not isinstance(raw_step, Mapping):
            raise ValueError(f"Mercury-2 procedure step {index} must be an object")
        article_ids = [str(value) for value in raw_step.get("source_article_ids", [])]
        evidence_ids = [str(value) for value in raw_step.get("evidence_ids", [])]
        if not article_ids or not set(article_ids).issubset(allowed_article_ids):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid article references")
        if not evidence_ids or not set(evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError(f"Mercury-2 procedure step {index} has invalid evidence references")
        action = str(raw_step.get("action", "")).strip()
        components = [str(value) for value in raw_step.get("components", [])]
        if not action or not components:
            raise ValueError(f"Mercury-2 procedure step {index} is incomplete")
        validated_steps.append({
            "sequence": index,
            "action": action,
            "components": components,
            "source_article_ids": sorted(set(article_ids)),
            "evidence_ids": sorted(set(evidence_ids)),
            "origin": "llm_wording",
            "requires_review": bool(raw_step.get("requires_review", False)),
        })
    return {
        "title": str(response["title"]).strip(),
        "steps": validated_steps,
        "warnings": [str(value) for value in response.get("warnings", []) if str(value).strip()],
        "requires_review": bool(response.get("requires_review", False)),
        "generation": "mercury-2",
    }
