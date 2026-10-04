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
from threading import RLock
from typing import Any, Iterable, Mapping

from .autoapitwo_connector import AutoAPITwoConnector, SourceUnavailable
from .vehicle_identity import canonicalize_vehicle_observation, stable_vehicle_identity_id
from .vehicle_identity_provider import normalize_autoapitwo_candidate, resolve_autoapitwo_vehicle


_COMPONENT_TERMS = {
    "oil_pump": "oil pump",
    "water_pump": "water pump",
    "timing_belt": "timing belt",
    "power_steering_pump": "power steering pump",
    "alternator": "alternator",
    "starter": "starter",
    "brakes": "brake",
    "brake_pads": "brake pad",
    "brake_rotor": "brake rotor",
    "brake_caliper": "brake caliper",
}

_CONFIGURED_CONNECTOR: AutoAPITwoConnector | None = None
_CONFIGURED_CONNECTOR_BASE: str | None = None
_CONFIGURED_CONNECTOR_LOCK = RLock()


def _configured_connector() -> AutoAPITwoConnector:
    global _CONFIGURED_CONNECTOR, _CONFIGURED_CONNECTOR_BASE
    base_url = os.getenv("AUTODATA_AUTOAPITWO_BASE_URL", "https://autoapitwo.vercel.app")
    with _CONFIGURED_CONNECTOR_LOCK:
        if _CONFIGURED_CONNECTOR is None or _CONFIGURED_CONNECTOR_BASE != base_url:
            _CONFIGURED_CONNECTOR = AutoAPITwoConnector(base_url)
            _CONFIGURED_CONNECTOR_BASE = base_url
        return _CONFIGURED_CONNECTOR


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
    try:
        normalized = normalize_autoapitwo_candidate(raw)
    except (TypeError, ValueError):
        return None
    provider_id = normalized["provider_car_id"]
    observation = normalized["observation"]
    values = observation.to_dict()
    year = values["year"]
    make = values["make"]
    model = values["model"]
    candidate_key = normalized["candidate_key"]
    label_parts = [str(year), make, model]
    for field in ("body_style", "drivetrain"):
        if values.get(field):
            label_parts.append(str(values[field]))
    if values.get("engine_displacement_l") is not None:
        label_parts.append(f'{values["engine_displacement_l"]:g}L')
    return {
        "vehicle_id": stable_vehicle_identity_id(observation),
        "candidate_key": candidate_key,
        "autoapitwo_vehicle_id": provider_id,
        "year": year,
        "make": make,
        "model": model,
        "region": values.get("region") or "US",
        "body_style": values.get("body_style"),
        "drivetrain": values.get("drivetrain"),
        "engine_displacement_l": values.get("engine_displacement_l"),
        "label": " ".join(label_parts),
        "provider_mappings": normalized["provider_mappings"],
        "provider_identity": normalized,
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
    if candidates:
        try:
            requested = canonicalize_vehicle_observation(search_text)
            resolution = resolve_autoapitwo_vehicle(requested, values)
            if resolution.status == "matched" and resolution.selected is not None:
                selected_key = resolution.selected["candidate_key"]
                candidates = [candidate for candidate in candidates if candidate["candidate_key"] == selected_key]
        except (TypeError, ValueError):
            pass
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
    if actions:
        return actions
    # Provider titles often say "Replacement" instead of removal/installation.
    if re.search(r"\breplacement\b", terminal) or re.search(r"\breplace\b", terminal):
        return ["replace"]
    # Older vehicles often expose only Parts and Labor pages for a component.
    if "parts and labor" in terminal or "parts and labor" in normalized:
        return ["replace"]
    return []


def _is_procedure_result(display: str) -> bool:
    normalized = display.casefold()
    return "service and repair" in normalized or "parts and labor" in normalized


def _is_service_procedure(display: str) -> bool:
    return "service and repair" in display.casefold()


def _is_parts_and_labor(display: str) -> bool:
    return "parts and labor" in display.casefold()


def _result_component(display: str, requested: Iterable[str]) -> str | None:
    lowered = display.casefold()
    for component in requested:
        term = _COMPONENT_TERMS.get(component, component.replace("_", " "))
        aliases = {term, term.rstrip("s"), f"{term}s"}
        if component == "brake_rotor":
            aliases.update({"brake rotor", "brake rotors", "brake rotor/disc", "rotor/disc"})
        if component == "brake_pads":
            aliases.update({"brake pad", "brake pads"})
        if component.startswith("brake_") and "brake" not in lowered:
            continue
        if any(alias in lowered for alias in sorted(aliases, key=len, reverse=True)):
            return component
    return None


def _merge_procedure_pair(removal: Mapping[str, Any], installation: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize split removal/installation pages into one component procedure."""

    component = str(removal.get("component") or installation.get("component") or "service")
    term = _COMPONENT_TERMS.get(component, component.replace("_", " ")).title()
    removal_blocks = list(removal.get("blocks") or [])
    installation_blocks = list(installation.get("blocks") or [])
    if not removal_blocks and removal.get("body"):
        removal_blocks = [{"kind": "text", "text": removal.get("body")}]
    if not installation_blocks and installation.get("body"):
        installation_blocks = [{"kind": "text", "text": installation.get("body")}]
    blocks: list[dict[str, Any]] = []
    if removal_blocks:
        blocks.append({"kind": "text", "text": "REMOVAL"})
        blocks.extend(dict(block) for block in removal_blocks if isinstance(block, Mapping))
    if installation_blocks:
        blocks.append({"kind": "text", "text": "INSTALLATION"})
        blocks.extend(dict(block) for block in installation_blocks if isinstance(block, Mapping))
    body_parts = [str(removal.get("body") or "").strip(), str(installation.get("body") or "").strip()]
    body = "\n\n".join(part for part in body_parts if part)
    evidence_ids = list(
        dict.fromkeys(
            [
                *[str(value) for value in removal.get("evidence_ids", []) if str(value).strip()],
                *[str(value) for value in installation.get("evidence_ids", []) if str(value).strip()],
            ]
        )
    )
    images = []
    for source in (removal, installation):
        for image in source.get("images", []) or []:
            if isinstance(image, Mapping):
                images.append(dict(image))
    removal_id = str(removal.get("article_id") or "").strip()
    installation_id = str(installation.get("article_id") or "").strip()
    article_id = (
        f"merged:{removal_id}:{installation_id}"
        if removal_id and installation_id
        else removal_id or installation_id or f"merged:{component}"
    )
    return {
        **dict(removal),
        "article_id": article_id,
        "title": f"{term} Removal and Installation",
        "procedure_kind": "removal_and_installation",
        "component": component,
        "body": body,
        "blocks": blocks,
        "images": images,
        "evidence_ids": evidence_ids,
        "merged_from_article_ids": [value for value in (removal_id, installation_id) if value],
        "content_kind": "procedure",
    }


def _normalize_component_procedures(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one normalized procedure per component for multi-component composition.

    Prefer Service and Repair procedure pages. When the provider splits removal
    and installation, merge them into one component procedure. Parts and Labor
    is only retained when no procedure page exists for that component.
    """

    by_component: dict[str, list[dict[str, Any]]] = {}
    for article in articles:
        component = str(article.get("component") or "").strip() or "service"
        by_component.setdefault(component, []).append(article)

    normalized: list[dict[str, Any]] = []
    for component, group in by_component.items():
        service = [
            article
            for article in group
            if str(article.get("content_kind") or "") != "parts_and_labor"
            and not _is_parts_and_labor(str(article.get("source_title") or article.get("title") or ""))
        ]
        labor = [article for article in group if article not in service]
        candidates = service or labor
        if not candidates:
            continue
        combined = next(
            (
                article
                for article in candidates
                if str(article.get("procedure_kind")) == "removal_and_installation"
            ),
            None,
        )
        if combined is not None:
            article = dict(combined)
            article.setdefault("content_kind", "procedure")
            normalized.append(article)
            continue
        removal = next((article for article in candidates if str(article.get("procedure_kind")) == "removal"), None)
        installation = next(
            (article for article in candidates if str(article.get("procedure_kind")) == "installation"), None
        )
        if removal is not None and installation is not None:
            normalized.append(_merge_procedure_pair(removal, installation))
            continue
        best = max(candidates, key=lambda article: len(str(article.get("body") or "")))
        article = dict(best)
        if article.get("content_kind") != "parts_and_labor":
            article.setdefault("content_kind", "procedure")
        normalized.append(article)
    return normalized


def retrieve_autoapitwo_articles(
    query: str,
    vehicle: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]] = (),
    *,
    connector: AutoAPITwoConnector | None = None,
    only_components: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve bounded procedure pages and normalize to one article per component."""

    provider_id = str(vehicle.get("autoapitwo_vehicle_id") or "").strip()
    if not provider_id.isdigit():
        return []
    requested = _components(query)
    # Both pumps on the RAV4 share timing-belt access. Asking for it here lets
    # the completeness checker expose the prerequisite instead of hiding it.
    terms_components = list(dict.fromkeys(requested + (["timing_belt"] if {"oil_pump", "water_pump"} & set(requested) else [])))
    if only_components is not None:
        allowed = {str(component).strip() for component in only_components if str(component).strip()}
        terms_components = [component for component in terms_components if component in allowed]
    if not terms_components:
        return []
    client = connector or _configured_connector()
    selected: dict[str, tuple[str, str, str, str]] = {}
    for component in terms_components:
        term = _COMPONENT_TERMS.get(component, component.replace("_", " "))
        try:
            results = client.search(provider_id, term)
        except Exception:
            continue
        ranked = sorted(
            (result for result in results if isinstance(result, Mapping)),
            key=lambda result: (
                0 if _is_service_procedure(_display(result)) else 1,
                0 if not _is_parts_and_labor(_display(result)) else 1,
            ),
        )
        for result in ranked:
            display = _display(result)
            href = _href(result)
            if not href or not _is_procedure_result(display):
                continue
            found_component = _result_component(display, (component,))
            actions = _actions(display)
            if found_component is None or not actions:
                continue
            if _is_parts_and_labor(display) and any(
                key.startswith(f"{found_component}:") and not _is_parts_and_labor(value[1])
                for key, value in selected.items()
            ):
                continue
            action = actions[0]
            key = f"{found_component}:{href}"
            selected.setdefault(key, (href, display, found_component, action))
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
        if article.get("content_kind") != "parts_and_labor":
            article.setdefault("content_kind", "procedure")
        articles.append(article)
    return _normalize_component_procedures(articles)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_malformed_provider_label(label: str) -> bool:
    return bool(re.match(r"^(?:19|20)\d{2}\s+For\s+(?:A|An|The)\s+", label, re.IGNORECASE))


def _vehicle_applicability(vehicle: Mapping[str, Any]) -> str:
    """Return the most specific consumer-safe identity for the selected vehicle."""

    label = _text(vehicle.get("label"))
    if label and not _is_malformed_provider_label(label):
        return label

    parts = [
        _text(vehicle.get("year") or vehicle.get("model_year")),
        _text(vehicle.get("make")),
        _text(vehicle.get("model")),
    ]
    base = " ".join(part for part in parts if part)
    base_casefold = base.casefold()
    for value in (vehicle.get("body_style"), vehicle.get("drivetrain")):
        detail = _text(value)
        if detail and detail.casefold() not in base_casefold:
            parts.append(detail)
            base_casefold = f"{base_casefold} {detail.casefold()}"
    raw_engine = vehicle.get("engine")
    if isinstance(raw_engine, (int, float)) and not isinstance(raw_engine, bool):
        engine = f"{raw_engine:g}L"
    else:
        engine = _text(raw_engine or vehicle.get("engine_displacement_l"))
        if engine and re.fullmatch(r"\d+(?:\.\d+)?", engine):
            engine = f"{engine}L"
    if engine and engine.casefold() not in base_casefold:
        parts.append(engine)
    return " ".join(part for part in parts if part) or "Vehicle-specific procedure"


def _step_action(text: str, component: str, kind: str) -> str:
    clean = _text(text)
    if clean:
        return clean
    verb = "Remove" if kind == "removal" else "Install"
    return f"{verb} {_COMPONENT_TERMS.get(component, component.replace('_', ' '))}."


def _article_steps(article: Mapping[str, Any]) -> list[dict[str, Any]]:
    from .procedure_normalize import build_consumer_steps, normalize_procedure_article

    normalized = normalize_procedure_article(article)
    steps = normalized.get("steps")
    if isinstance(steps, list) and steps:
        return [dict(step) for step in steps if isinstance(step, Mapping)]
    return build_consumer_steps(normalized, normalized.get("blocks"))


def _clean_public_text(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"\b(?:source|article|document)\s+(?:says|states|indicates)\b[: ]*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _clean_step_action(value: Any) -> str:
    return re.sub(r"^\s*(?:step\s*)?\d+\s*[.):-]\s*", "", _clean_public_text(value), flags=re.IGNORECASE)


def _is_summary_artifact(step: Mapping[str, Any]) -> bool:
    """Reject provider summaries that were truncated before consumer projection."""

    if str(step.get("phase") or "").casefold() != "procedure":
        return False
    action = _text(step.get("action"))
    instructions = step.get("instructions")
    images = step.get("images")
    if instructions or images:
        return False
    if action.endswith("...") or len(action) > 180:
        return True
    return bool(re.search(r"\b(?:figs?\w*|refer\s+to|service\s+and\s+repair)\b", action, re.IGNORECASE))


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
    # Fixed component list order only. Within a component, keep removal before
    # installation when articles are split, but never globally regroup all
    # removals ahead of all installations across components.
    ordered_articles = sorted(
        all_articles,
        key=lambda article: (
            order.get(str(article.get("component")), 99),
            0 if str(article.get("procedure_kind")) in {"removal", "removal_and_installation"} else 1,
            str(article.get("article_id", "")),
        ),
    )
    steps: list[dict[str, Any]] = []
    evidence: set[str] = set()
    for article in ordered_articles:
        evidence.update(str(value) for value in article.get("evidence_ids", []) if str(value).strip())
        for step in _article_steps(article):
            step["action"] = _clean_step_action(step["action"])
            if _is_summary_artifact(step):
                continue
            step["sequence"] = len(steps) + 1
            steps.append(step)
    # Preserve source order within and across articles. Do not re-sort by phase;
    # that previously moved install-section "Remove ..." lines and inverted
    # multi-component dependency order (e.g. reinstalling a belt before a pump).
    for sequence, step in enumerate(steps, 1):
        step["sequence"] = sequence
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
        "applicability": _vehicle_applicability(vehicle),
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
