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
    review_vehicle_candidates,
)


_SOURCE_CANDIDATE_KINDS = frozenset(
    {
        "vehicle_identity",
        "specification",
        "model",
        "powertrain",
        "part",
        "article",
        "document",
        "document_text",
        "diagram_text",
        "image_text",
    }
)


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
        base_url = os.getenv("INCEPTION_API_BASE_URL", "")
        if not base_url:
            raise ValueError("INCEPTION_API_BASE_URL is required for Mercury-2")
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


__all__ = ["Mercury2Client", "Mercury2SourceExtractor", "Mercury2VehicleAdjudicator"]
