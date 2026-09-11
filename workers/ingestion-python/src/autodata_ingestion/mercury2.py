"""Mercury-2 advisory boundary for ambiguous vehicle identity decisions.

The deterministic identity matcher remains authoritative. Mercury-2 may only
choose among candidates already supplied by that matcher, and every response
is schema-checked before it can affect a review state.
"""

from __future__ import annotations

import json
import hashlib
import os
from typing import Any, Callable, Mapping, Protocol
from urllib.request import Request, urlopen

from .source_adapters import NormalizationCandidate, SourceResource
from .vehicle_identity import (
    CanonicalVehicleObservation,
    VehicleMatchCandidate,
    VehicleReviewState,
    canonicalize_vehicle_observation,
    review_vehicle_candidates,
)


_SOURCE_CANDIDATE_KINDS = frozenset(
    {
        "vehicle_identity",
        "specification",
        "model",
        "part",
        "article",
        "document",
        "document_text",
        "diagram_text",
        "image_text",
    }
)
DEFAULT_INCEPTION_API_BASE_URL = "https://api.inceptionlabs.ai/v1"


# The application still validates every field after the model responds.  This
# schema is deliberately small: Mercury-2 may word and order already sourced
# operations, but it cannot add vehicle facts, components, or evidence.
PROCEDURE_COMPOSITION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "steps", "warnings"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "operation_id",
                    "action",
                    "components",
                    "category",
                    "source_article_ids",
                    "evidence_ids",
                ],
                "properties": {
                    "operation_id": {"type": "string", "minLength": 1},
                    "action": {"type": "string", "minLength": 1},
                    "components": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "category": {"type": "string", "enum": ["required", "recommended"]},
                    "source_article_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "requires_review": {"type": "boolean"},
                },
            },
        },
        "warnings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "warning_id",
                    "message",
                    "source_article_ids",
                    "evidence_ids",
                    "requires_review",
                ],
                "properties": {
                    "warning_id": {"type": "string", "minLength": 1},
                    "message": {"type": "string", "minLength": 1},
                    "source_article_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "requires_review": {"type": "boolean"},
                },
            },
        },
        "requires_review": {"type": "boolean"},
        "excluded_operation_ids": {"type": "array", "items": {"type": "string"}},
    },
}


class JsonTransport(Protocol):
    def __call__(self, request: Request, timeout: float) -> Any:
        ...


class Mercury2Client:
    """Small OpenAI-compatible JSON client with environment-only secrets."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "mercury-2",
        timeout_seconds: float = 20.0,
        transport: JsonTransport = urlopen,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Mercury-2 API key is required")
        if not base_url.strip():
            raise ValueError("Mercury-2 base URL is required")
        if timeout_seconds <= 0:
            raise ValueError("Mercury-2 timeout must be positive")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model.strip() or "mercury-2"
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_environment(cls, *, transport: JsonTransport = urlopen) -> "Mercury2Client":
        """Build a client without reading credentials from repository files."""

        api_key = os.getenv("INCEPTION_API_KEY", "")
        base_url = os.getenv("INCEPTION_API_BASE_URL", DEFAULT_INCEPTION_API_BASE_URL)
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=os.getenv("INCEPTION_MODEL", "mercury-2"),
            timeout_seconds=float(os.getenv("INCEPTION_API_TIMEOUT_SECONDS", "20")),
            transport=transport,
        )

    def complete_json(self, prompt: str) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("Mercury-2 prompt must not be empty")
        request = Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(
                {
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "Return only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                }
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with self._transport(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read())
        content = _response_content(payload)
        result = json.loads(content) if isinstance(content, str) else content
        if not isinstance(result, dict):
            raise ValueError("Mercury-2 response must be a JSON object")
        return result


def compose_procedure_draft(
    client: Any,
    *,
    vehicle: Mapping[str, Any],
    quote: Mapping[str, Any],
    articles: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Request wording for a procedure from already validated inputs.

    The prompt contains only canonical vehicle identity, the application-owned
    quote, and normalized source articles.  The caller remains responsible for
    validating all references and for deciding whether a draft is publishable.
    """

    if not isinstance(vehicle, Mapping):
        raise ValueError("Mercury-2 procedure vehicle must be an object")
    if not isinstance(quote, Mapping):
        raise ValueError("Mercury-2 procedure quote must be an object")
    if not isinstance(articles, list):
        raise ValueError("Mercury-2 procedure articles must be an array")
    prompt = json.dumps(
        {
            "task": (
                "Compose only a faithful procedure from the supplied normalized articles and quote. "
                "Do not invent steps, components, vehicle facts, values, tools, or evidence. "
                "Every step must retain its source article IDs, evidence IDs, and required/recommended category."
            ),
            "vehicle": dict(vehicle),
            "quote": dict(quote),
            "articles": [dict(article) for article in articles],
            "schema": PROCEDURE_COMPOSITION_SCHEMA,
            "output": {
                "title": "string",
                "steps": [],
                "warnings": [],
                "requires_review": True,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    response = client.complete_json(prompt)
    if not isinstance(response, Mapping):
        raise ValueError("Mercury-2 procedure response must be an object")
    return dict(response)


class Mercury2SourceExtractor:
    """Advisory extractor for typed candidates from an unrecognized resource.

    Mercury-2 proposes candidates only. The shared source-bundle normalizer
    still validates their fields, attaches source evidence, and decides
    whether anything is publishable. Candidate keys are derived locally so a
    model's arbitrary key choice cannot break replay idempotency.
    """

    def __init__(
        self,
        client: Mercury2Client,
        *,
        max_input_bytes: int = 200_000,
        max_candidates: int = 500,
    ) -> None:
        if max_input_bytes < 1:
            raise ValueError("Mercury-2 extraction input limit must be positive")
        if max_candidates < 1:
            raise ValueError("Mercury-2 extraction candidate limit must be positive")
        self._client = client
        self._max_input_bytes = max_input_bytes
        self._max_candidates = max_candidates

    def extract(self, resource: SourceResource) -> tuple[NormalizationCandidate, ...]:
        if len(resource.payload) > self._max_input_bytes:
            raise ValueError("Mercury-2 extraction input exceeds the configured limit")
        try:
            document: Any = json.loads(resource.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            document = resource.payload.decode("utf-8", errors="replace")
        response = self._client.complete_json(_build_source_extraction_prompt(resource, document))
        if not isinstance(response, Mapping):
            raise ValueError("Mercury-2 extraction response must be a JSON object")
        raw_candidates = response.get("candidates")
        if not isinstance(raw_candidates, list):
            raise ValueError("Mercury-2 extraction response candidates must be an array")
        if len(raw_candidates) > self._max_candidates:
            raise ValueError("Mercury-2 extraction returned too many candidates")
        candidates: list[NormalizationCandidate] = []
        for index, raw_candidate in enumerate(raw_candidates):
            if not isinstance(raw_candidate, Mapping):
                raise ValueError(f"Mercury-2 candidate {index} must be an object")
            kind = raw_candidate.get("kind")
            locator = raw_candidate.get("locator")
            data = raw_candidate.get("data")
            if not isinstance(kind, str) or kind not in _SOURCE_CANDIDATE_KINDS:
                raise ValueError(f"Mercury-2 candidate {index} has an unsupported kind")
            if not isinstance(locator, str) or not locator.strip():
                raise ValueError(f"Mercury-2 candidate {index} requires a locator")
            if not isinstance(data, dict):
                raise ValueError(f"Mercury-2 candidate {index} data must be an object")
            missing = _missing_required_fields(str(kind), data)
            if missing:
                raise ValueError(
                    f"Mercury-2 candidate {index} {kind} requires {', '.join(missing)}"
                )
            if kind == "vehicle_identity":
                try:
                    canonicalize_vehicle_observation(data)
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Mercury-2 candidate {index} has an invalid vehicle identity"
                    ) from error
            canonical = json.dumps(
                {"data": data, "kind": kind, "locator": locator.strip()},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            stable_key = hashlib.sha256(canonical).hexdigest()[:24]
            candidates.append(
                NormalizationCandidate(
                    str(kind),
                    f"mercury2:{kind}:{stable_key}",
                    dict(data),
                    locator.strip(),
                )
            )
        return tuple(candidates)


def configured_source_extractor() -> tuple[Mercury2SourceExtractor | None, str | None]:
    """Build the opt-in source extractor from secret-managed environment state."""

    if os.getenv("AUTODATA_MERCURY2_EXTRACTION_ENABLED") != "1":
        return None, None
    try:
        client = Mercury2Client.from_environment()
        return (
            Mercury2SourceExtractor(
                client,
                max_input_bytes=_positive_int_env(
                    "AUTODATA_MERCURY2_EXTRACTION_MAX_INPUT_BYTES", 200_000
                ),
                max_candidates=_positive_int_env(
                    "AUTODATA_MERCURY2_EXTRACTION_MAX_CANDIDATES", 500
                ),
            ),
            None,
        )
    except (TypeError, ValueError) as error:
        return None, str(error)


class Mercury2VehicleAdjudicator:
    """Use Mercury-2 only to resolve deterministic ambiguity."""

    def __init__(self, client: Mercury2Client, *, min_confidence: float = 0.95) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("Mercury-2 minimum confidence must be between 0 and 1")
        self._client = client
        self._min_confidence = min_confidence

    def adjudicate(
        self,
        observation: CanonicalVehicleObservation,
        candidates: list[Mapping[str, Any] | str],
    ) -> VehicleReviewState:
        deterministic = review_vehicle_candidates(observation, candidates)
        if deterministic.status != "ambiguous":
            return deterministic
        response = self._client.complete_json(_build_prompt(observation, deterministic.candidates))
        selected = response.get("selected_candidate_key")
        confidence = response.get("confidence")
        allowed = {candidate.candidate_key for candidate in deterministic.candidates}
        if not isinstance(selected, str) or selected not in allowed:
            return _needs_review(deterministic, "mercury_invalid_candidate")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            return _needs_review(deterministic, "mercury_invalid_confidence")
        if confidence < self._min_confidence:
            return _needs_review(deterministic, "mercury_confidence_below_threshold")
        return VehicleReviewState(
            status="matched",
            ambiguous=False,
            selected_candidate_key=selected,
            reason="mercury_adjudicated",
            candidates=deterministic.candidates,
        )


def _build_prompt(observation: CanonicalVehicleObservation, candidates: tuple[VehicleMatchCandidate, ...]) -> str:
    return json.dumps(
        {
            "task": "Choose exactly one candidate for this vehicle identity observation, or explain why review is required.",
            "observation": observation.to_dict(),
            "candidates": [candidate.to_dict() for candidate in candidates],
            "output": {"selected_candidate_key": "string", "confidence": 0.0},
        },
        sort_keys=True,
    )


def _positive_int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _missing_required_fields(kind: str, data: Mapping[str, Any]) -> tuple[str, ...]:
    required_by_kind = {
        "vehicle_identity": ("year", "make", "model"),
        "specification": ("name",),
        "model": ("id", "model"),
        "part": ("partNumber", "partDescription"),
        "article": ("id", "title"),
        "document": ("documentId",),
        "document_text": ("text",),
        "diagram_text": ("text",),
        "image_text": ("text",),
    }
    return tuple(
        field
        for field in required_by_kind.get(kind, ())
        if field not in data or data[field] in (None, "")
    )


def _build_source_extraction_prompt(resource: SourceResource, document: Any) -> str:
    return json.dumps(
        {
            "task": "Extract only explicit, source-supported typed candidates. Do not infer missing facts.",
            "source": {
                "source_uri": resource.source_uri,
                "media_type": resource.media_type,
                "document": document,
            },
            "allowed_candidate_kinds": sorted(_SOURCE_CANDIDATE_KINDS),
            "candidate_schema": {
                "kind": "one allowed kind",
                "locator": "JSON path or source locator",
                "data": "object containing only explicit source fields",
            },
            "output": {"candidates": []},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _needs_review(state: VehicleReviewState, reason: str) -> VehicleReviewState:
    return VehicleReviewState(
        status="needs_review",
        ambiguous=True,
        selected_candidate_key=None,
        reason=reason,
        candidates=state.candidates,
    )


def _response_content(payload: Any) -> Any:
    if isinstance(payload, dict) and "choices" in payload:
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            raise ValueError("Mercury-2 response choices are missing")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError("Mercury-2 response content is missing")
        return message["content"]
    return payload


__all__ = [
    "Mercury2Client",
    "Mercury2SourceExtractor",
    "Mercury2VehicleAdjudicator",
    "PROCEDURE_COMPOSITION_SCHEMA",
    "compose_procedure_draft",
    "configured_source_extractor",
]
