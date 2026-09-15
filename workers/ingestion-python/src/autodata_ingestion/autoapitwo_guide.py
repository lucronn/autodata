"""Vehicle-matched repair-guide retrieval and consumer composition for AutoAPI Two.

This module keeps the provider boundary explicit: the source supplies the
repair facts and figures, while the application controls vehicle matching,
dependency coverage, ordering, completeness, and the public guide shape.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
import re
from typing import Any, Iterable, Mapping

from .autoapitwo_connector import AutoAPITwoConnector, SourceUnavailable


_COMPONENT_TERMS = {
    "oil_pump": "oil pump",
    "water_pump": "water pump",
    "timing_belt": "timing belt",
    "power_steering_pump": "power steering pump",
    "alternator": "alternator",
    "starter": "starter",
    "brakes": "brake",
}


def _configured_connector() -> AutoAPITwoConnector:
    return AutoAPITwoConnector(
        os.getenv("AUTODATA_AUTOAPITWO_BASE_URL", "https://autoapitwo.vercel.app")
    )


def _components(query: str) -> list[str]:
    from .job_plan import _components_from_query

    components = list(_components_from_query(query))
    specific_brake_components = {component for component in components if component.startswith("brake_")}
    if specific_brake_components:
        components = [component for component in components if component != "brakes"]
    return components


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")


def _number(value: Any) -> int | float | str | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    if match:
        return int(match.group(0))
    return None


def _engine_litres(value: Any) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*L", str(value or ""), re.IGNORECASE)
    return float(match.group(1)) if match else None


def _vehicle_candidate(raw: Mapping[str, Any], index: int) -> dict[str, Any] | None:
    provider_id = str(raw.get("id") or "").strip()
    if not provider_id.isdigit():
        return None
    description = str(raw.get("description") or "").strip()
    model_text = str(raw.get("model") or "").strip()
    model = re.split(r"\s+(?:(?:2|4)-Door|2WD|4WD)\b", model_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not model:
        return None
    body_match = re.search(r"\b(2|4)-Door\b", model_text, re.IGNORECASE)
    drive_match = re.search(r"\b(2WD|4WD)\b", model_text, re.IGNORECASE)
    make = re.sub(r"\s+Truck$", "", str(raw.get("make") or "").strip(), flags=re.IGNORECASE)
    year = _number(raw.get("year"))
    if year is None or not make:
        return None
    candidate_key = f"autoapitwo:{provider_id}"
    return {
        "vehicle_id": f"vehicle:{sha256(candidate_key.encode()).hexdigest()[:24]}",
        "candidate_key": candidate_key,
        "autoapitwo_vehicle_id": provider_id,
        "year": year,
        "make": make,
        "model": model,
        "region": "US",
        "body_style": body_match.group(1) + "-door" if body_match else None,
        "drivetrain": drive_match.group(1).upper() if drive_match else None,
        "engine_displacement_l": _engine_litres(raw.get("engine")),
        "label": description or f"{year} {make} {model}",
        "confidence": 1.0,
    }


def vehicle_candidates_from_autoapitwo(
    message: str, *, connector: AutoAPITwoConnector | None = None
) -> list[dict[str, Any]]:
    """Return exact provider variants without collapsing their IDs into AutoAPI IDs."""

    client = connector or _configured_connector()
    search_text = message
    try:
        from .chat_intent import _parse_vehicle

        observation = _parse_vehicle(message)
        fields = [observation.get(key) for key in ("year", "make", "model", "body_style", "drivetrain", "engine")]
        if all(value is not None for value in fields[:3]):
            search_text = " ".join(str(value) for value in fields if value)
    except Exception:
        pass
    try:
        values = client.search_vehicles(search_text)
    except Exception:
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values, 1):
        if not isinstance(value, Mapping):
            continue
        candidate = _vehicle_candidate(value, index)
        if candidate and candidate["candidate_key"] not in seen:
            candidates.append(candidate)
            seen.add(candidate["candidate_key"])
    return candidates


def _display(result: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(result.get("display") or result.get("title") or "")).strip()


def _href(result: Mapping[str, Any]) -> str:
    links = result.get("_links", {})
    if isinstance(links, Mapping):
        self_link = links.get("self", {})
        if isinstance(self_link, Mapping):
            return str(self_link.get("href") or "").strip()
    return str(result.get("href") or result.get("url") or "").strip()


def _action(display: str) -> str | None:
    actions = _actions(display)
    return actions[-1] if actions else None


def _actions(display: str) -> list[str]:
    normalized = display.casefold()
    terminal = normalized.rsplit(">>", 1)[-1]
    if re.search(r"\bremoval\s+and\s+replacement\b", terminal):
        return ["removal_and_installation"]
    terminal_matches = list(re.finditer(r"\b(removal|installation)\b", terminal))
    if terminal_matches:
        terminal_actions = list(dict.fromkeys(match.group(1) for match in terminal_matches))
        if len(terminal_actions) > 1:
            return ["removal_and_installation"]
        return terminal_actions
    if re.search(r"\bremoval\s+and\s+replacement\b", normalized):
        return ["removal_and_installation"]
    matches = list(re.finditer(r"\b(removal|installation)\b", normalized))
    actions = list(dict.fromkeys(match.group(1) for match in matches))
    if len(actions) > 1:
        return ["removal_and_installation"]
    return actions


def _result_component(display: str, requested: Iterable[str]) -> str | None:
    lowered = display.casefold()
    for component in requested:
        term = _COMPONENT_TERMS.get(component, component.replace("_", " "))
        if term in lowered:
            return component
    return None


def retrieve_autoapitwo_articles(
    query: str,
    vehicle: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]] = (),
    *,
    connector: AutoAPITwoConnector | None = None,
) -> list[dict[str, Any]]:
    """Retrieve bounded removal/installation/specification pages for one car."""

    provider_id = str(vehicle.get("autoapitwo_vehicle_id") or "").strip()
    if not provider_id.isdigit():
        return []
    requested = _components(query)
    # Both pumps on the RAV4 share timing-belt access. Asking for it here lets
    # the completeness checker expose the prerequisite instead of hiding it.
    terms_components = list(dict.fromkeys(requested + (["timing_belt"] if {"oil_pump", "water_pump"} & set(requested) else [])))
    client = connector or _configured_connector()
    selected: dict[str, tuple[str, str, str, str]] = {}
    for component in terms_components:
        term = _COMPONENT_TERMS.get(component, component.replace("_", " "))
        try:
            results = client.search(provider_id, term)
        except Exception:
            continue
        for result in results:
            if not isinstance(result, Mapping):
                continue
            display = _display(result)
            href = _href(result)
            if not href or "service and repair" not in display.casefold():
                continue
            found_component = _result_component(display, (component,))
            actions = _actions(display)
            if found_component is None or not actions:
                continue
            action = actions[0]
            key = f"{found_component}:{href}"
            selected.setdefault(key, (href, display, found_component, action))
            # Torque/specification pages are fetched from the same search but
            # are treated as supporting facts when they are returned inline.
            if len(selected) >= 16:
                break
    articles: list[dict[str, Any]] = []
    for href, display, component, action in selected.values():
        try:
            article = client.article(provider_id, href, title=display.rsplit(" >> ", 1)[-1])
        except (SourceUnavailable, ValueError, KeyError):
            continue
        article = dict(article)
        article.update({
            "component": component,
            "procedure_kind": action,
            "source_title": display,
        })
        articles.append(article)
    return articles


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _step_action(text: str, component: str, kind: str) -> str:
    clean = _text(text)
    if len(clean) > 180:
        clean = clean[:177].rstrip() + "..."
    if clean:
        return clean
    verb = "Remove" if kind == "removal" else "Install"
    return f"{verb} {_COMPONENT_TERMS.get(component, component.replace('_', ' '))}."


def _article_steps(article: Mapping[str, Any]) -> list[dict[str, Any]]:
    component = str(article.get("component") or "service")
    kind = str(article.get("procedure_kind") or "procedure")
    blocks = article.get("blocks")
    if not isinstance(blocks, list):
        blocks = [{"kind": "text", "text": article.get("body", "")}]
    pending_images: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    current_phase = "removal" if kind == "removal_and_installation" else kind
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        if block.get("kind") == "image":
            image = {key: block[key] for key in ("url", "alt", "image_id", "evidence_ids") if block.get(key)}
            if image.get("url"):
                pending_images.append(image)
            continue
        text = _text(block.get("text"))
        if not text:
            continue
        evidence_ids = [str(value) for value in block.get("evidence_ids", article.get("evidence_ids", [])) if str(value).strip()]
        # The provider separates each HTML line into a block. Keep numbered
        # source steps together so torque lines and lettered substeps remain
        # readable detail under one consumer-facing step.
        starts_step = bool(re.match(r"^\d+[.)]\s", text)) or not steps
        if starts_step:
            if kind == "removal_and_installation":
                verb = re.match(r"^\d+[.)]\s*(remove|install|replace)\b", text, re.IGNORECASE)
                if verb:
                    current_phase = "installation" if verb.group(1).casefold() in {"install", "replace"} else "removal"
            steps.append({
                "action": _step_action(text, component, kind),
                "instructions": [],
                "components": [component],
                "source_article_ids": [str(article.get("article_id"))],
                "evidence_ids": sorted(set(evidence_ids)),
                "images": pending_images,
                "phase": current_phase,
            })
            pending_images = []
        else:
            current = steps[-1]
            current["instructions"].append(text)
            current["evidence_ids"] = sorted(set(current.get("evidence_ids", [])) | set(evidence_ids))
    if pending_images and steps:
        steps[-1]["images"].extend(pending_images)
    return steps


def _clean_public_text(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"\b(?:source|article|document)\s+(?:says|states|indicates)\b[: ]*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _clean_step_action(value: Any) -> str:
    return re.sub(r"^\s*(?:step\s*)?\d+\s*[.):-]\s*", "", _clean_public_text(value), flags=re.IGNORECASE)


def compose_illustrated_guide(
    query: str,
    vehicle: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one ordered, source-bound consumer guide from retrieved pages."""

    requested = _components(query)
    all_articles = [dict(article) for article in articles if isinstance(article, Mapping)]
    required = list(dict.fromkeys(requested + (["timing_belt"] if {"oil_pump", "water_pump"} & set(requested) else [])))
    present: set[tuple[str, str]] = set()
    for article in all_articles:
        component = str(article.get("component"))
        kind = str(article.get("procedure_kind"))
        if kind == "removal_and_installation":
            present.update({(component, "removal"), (component, "installation")})
        else:
            present.add((component, kind))
    gaps: list[str] = []
    for component in required:
        if (component, "removal") not in present:
            gaps.append(f"missing_removal:{component}")
        if (component, "installation") not in present:
            gaps.append(f"missing_installation:{component}")
    order = {"timing_belt": 0, **{component: index + 1 for index, component in enumerate(requested)}}
    ordered_articles = sorted(
        all_articles,
        key=lambda article: (
            0 if str(article.get("procedure_kind")) in {"removal", "removal_and_installation"} else 1,
            order.get(str(article.get("component")), 99),
            str(article.get("article_id", "")),
        ),
    )
    steps: list[dict[str, Any]] = []
    evidence: set[str] = set()
    for article in ordered_articles:
        evidence.update(str(value) for value in article.get("evidence_ids", []) if str(value).strip())
        for step in _article_steps(article):
            step["sequence"] = len(steps) + 1
            step["action"] = _clean_step_action(step["action"])
            steps.append(step)
    images = [image for step in steps for image in step.get("images", [])]
    warnings: list[dict[str, Any]] = []
    for article in all_articles:
        values = article.get("warnings", article.get("safety_warnings", []))
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                message = _clean_public_text(value.get("message") if isinstance(value, Mapping) else value)
                if message:
                    warnings.append({"message": message, "evidence_ids": list(article.get("evidence_ids", []))})
    if not images:
        gaps.append("missing_required_figures")
    content_status = "complete" if not gaps and steps else "partial"
    public = {
        "title": " and ".join(_COMPONENT_TERMS.get(component, component.replace("_", " ")).title() for component in requested) + " Replacement Guide",
        "vehicle": dict(vehicle),
        "applicability": f"{vehicle.get('year', vehicle.get('model_year', ''))} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip(),
        "preparation": ["Work on a cool vehicle, support it securely, and keep replacement seals, fluids, and basic hand tools ready."],
        "steps": steps,
        "warnings": warnings,
        "images": images,
        "evidence_ids": sorted(evidence),
        "gaps": sorted(set(gaps)),
        "content_status": content_status,
        "pdf_ready": content_status == "complete",
        "review_state": "UNREVIEWED",
        "review_label": "UNREVIEWED — human review pending",
    }
    public["revision_id"] = "guide:" + sha256(json.dumps(public, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()[:24]
    return public


__all__ = ["compose_illustrated_guide", "retrieve_autoapitwo_articles", "vehicle_candidates_from_autoapitwo"]
