"""Vehicle-matched repair-guide retrieval and consumer composition for Banktwo.

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

from .banktwo_connector import BanktwoConnector, SourceUnavailable
from .source_connector_client import source_connector_registry
from .vehicle_identity import canonicalize_vehicle_observation, stable_vehicle_identity_id


_COMPONENT_TERMS = {
    "oil_pump": "oil pump",
    "water_pump": "water pump",
    "timing_belt": "timing belt",
    "power_steering_pump": "power steering pump",
    "alternator": "alternator",
    "starter": "starter",
    "brakes": "brake",
}

_CONFIGURED_CONNECTOR: BanktwoConnector | None = None
_CONFIGURED_CONNECTOR_BASE: str | None = None
_CONFIGURED_CONNECTOR_LOCK = RLock()


def _configured_connector() -> BanktwoConnector:
    global _CONFIGURED_CONNECTOR, _CONFIGURED_CONNECTOR_BASE
    base_url = os.getenv("BANKTWO_BASE_URL", "https://banktwo.cars.tk")
    with _CONFIGURED_CONNECTOR_LOCK:
        if _CONFIGURED_CONNECTOR is None or _CONFIGURED_CONNECTOR_BASE != base_url:
            registry = source_connector_registry(include_defaults=True)
            _CONFIGURED_CONNECTOR = BanktwoConnector(source_client=registry["banktwo"])
            _CONFIGURED_CONNECTOR_BASE = base_url
        return _CONFIGURED_CONNECTOR


def _components(query: str) -> list[str]:
    from .job_plan import _components_from_query

    components = list(_components_from_query(query))
    specific_brake_components = {component for component in components if component.startswith("brake_")}
    if specific_brake_components:
        components = [component for component in components if component != "brakes"]
    return components


def _vehicle_candidate(raw: Mapping[str, Any], selector: Mapping[str, Any]) -> dict[str, Any] | None:
    source_ref = str(raw.get("opaque_ref") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not source_ref or not label:
        return None
    try:
        from .chat_intent import _parse_vehicle

        parsed = _parse_vehicle(label)
    except Exception:
        parsed = {}
    values = {
        key: parsed.get(key) if parsed.get(key) not in (None, "") else selector.get(key)
        for key in ("year", "make", "model", "region", "body_style", "trim", "drivetrain", "engine_displacement_l")
    }
    values["year"] = values.get("year", selector.get("year"))
    values["make"] = values.get("make") or selector.get("make")
    values["model"] = values.get("model") or selector.get("model")
    if values.get("year") is None or not values.get("make") or not values.get("model"):
        return None
    try:
        observation = canonicalize_vehicle_observation(values)
    except (TypeError, ValueError):
        return None
    canonical = observation.to_dict()
    label_parts = [str(canonical["year"]), str(canonical["make"]), str(canonical["model"])]
    for field in ("body_style", "drivetrain"):
        if canonical.get(field):
            label_parts.append(str(canonical[field]))
    if canonical.get("engine_displacement_l") is not None:
        label_parts.append(f'{canonical["engine_displacement_l"]:g}L')
    provider_mapping = {
        "provider": "autoapitwo", "entity_type": "vehicle", "provider_id": source_ref,
        "provider_label": label, "source_provider": "banktwo",
    }
    candidate = {
        "vehicle_id": stable_vehicle_identity_id(observation),
        "candidate_key": f"autoapitwo:source:{source_ref}",
        "autoapitwo_vehicle_id": source_ref,
        "source_vehicle_ref": source_ref,
        "year": canonical["year"], "make": canonical["make"], "model": canonical["model"],
        "region": canonical.get("region") or selector.get("region") or "US",
        "body_style": canonical.get("body_style"), "trim": canonical.get("trim"),
        "drivetrain": canonical.get("drivetrain"),
        "engine_displacement_l": canonical.get("engine_displacement_l"),
        "label": " ".join(label_parts),
        "provider_mappings": [provider_mapping],
        "provider_identity": {"provider": "banktwo", "opaque_ref": source_ref, "label": label,
                              "evidence": list(raw.get("evidence") or [])},
        "confidence": raw.get("confidence", 1.0),
    }
    return candidate


def vehicle_candidates_from_banktwo(
    message: str, *, connector: BanktwoConnector | None = None
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
        from .chat_intent import _parse_vehicle

        parsed = _parse_vehicle(search_text)
    except Exception:
        return []
    selector = {key: parsed.get(key) for key in ("year", "make", "model", "configuration", "region", "vin")
                if parsed.get(key) not in (None, "")}
    for config_key in ("trim", "body_style", "drivetrain", "engine"):
        if parsed.get(config_key) and not selector.get("configuration"):
            selector["configuration"] = str(parsed[config_key])
    if not {"year", "make", "model"}.issubset(selector):
        return []
    try:
        resolution = client.resolve_vehicle(selector)
        values = resolution.body.get("candidates", [])
    except SourceUnavailable:
        raise
    except Exception as error:
        raise SourceUnavailable() from error
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values, 1):
        if not isinstance(value, Mapping):
            continue
        candidate = _vehicle_candidate(value, selector)
        if candidate and candidate["candidate_key"] not in seen:
            candidates.append(candidate)
            seen.add(candidate["candidate_key"])
    return candidates


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


def retrieve_banktwo_articles(
    query: str,
    vehicle: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]] = (),
    *,
    connector: BanktwoConnector | None = None,
) -> list[dict[str, Any]]:
    """Retrieve bounded removal/installation/specification pages for one car."""

    provider_id = str(vehicle.get("source_vehicle_ref") or vehicle.get("autoapitwo_vehicle_id") or "").strip()
    if not provider_id:
        return []
    requested = _components(query)
    # Both pumps on the RAV4 share timing-belt access. Asking for it here lets
    # the completeness checker expose the prerequisite instead of hiding it.
    terms_components = list(dict.fromkeys(requested + (["timing_belt"] if {"oil_pump", "water_pump"} & set(requested) else [])))
    client = connector or _configured_connector()
    selected: dict[str, tuple[dict[str, Any], str, str, str]] = {}
    for component in terms_components:
        term = _COMPONENT_TERMS.get(component, component.replace("_", " "))
        try:
            results = client.search(provider_id, term)
        except SourceUnavailable:
            raise
        except Exception as error:
            raise SourceUnavailable() from error
        for result in results:
            if not isinstance(result, Mapping):
                continue
            title = str(result.get("title") or "").strip()
            category = str(result.get("category") or "").strip()
            display = " >> ".join(value for value in (category, title) if value)
            if not str(result.get("opaque_ref") or "").strip() or "service and repair" not in display.casefold():
                continue
            source_component = str(result.get("component") or "").replace("_", " ").strip().casefold()
            found_component = _result_component(f"{display} {source_component}", (component,))
            requested_component = _COMPONENT_TERMS.get(component, component.replace("_", " ")).casefold()
            if found_component is None and (
                source_component == requested_component
                or component == "timing_belt" and source_component == "timing"
            ):
                found_component = component
            actions = _actions(display)
            if found_component is None or not actions:
                continue
            action = actions[0]
            descriptor = dict(result)
            descriptor["title"] = title
            key = f"{found_component}:{result.get('opaque_ref')}"
            selected.setdefault(key, (descriptor, display, found_component, action))
            if len(selected) >= 16:
                break
    articles: list[dict[str, Any]] = []
    for descriptor, display, component, action in selected.values():
        try:
            article = client.article_by_descriptor(provider_id, descriptor)
        except SourceUnavailable as error:
            if error.code == "NOT_FOUND":
                continue
            raise
        except (ValueError, KeyError):
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
            image = {
                key: block[key]
                for key in ("url", "alt", "image_id", "evidence_ids", "asset_resource_ref",
                            "storage_key", "content_sha256", "source_sha256", "media_type")
                if block.get(key)
            }
            if image.get("url") or image.get("asset_resource_ref") or image.get("storage_key"):
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
            step["action"] = _clean_step_action(step["action"])
            if _is_summary_artifact(step):
                continue
            step["sequence"] = len(steps) + 1
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


__all__ = ["compose_illustrated_guide", "retrieve_banktwo_articles", "vehicle_candidates_from_banktwo"]
