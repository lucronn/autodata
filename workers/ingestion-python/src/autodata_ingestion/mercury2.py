"""Mercury-2 advisory boundary for ambiguous vehicle identity decisions.

The deterministic identity matcher remains authoritative. Mercury-2 may only
choose among candidates already supplied by that matcher, and every response
is schema-checked before it can affect a review state.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping, Protocol
from urllib.request import Request, urlopen

from .vehicle_identity import (
    CanonicalVehicleObservation,
    VehicleMatchCandidate,
    VehicleReviewState,
    review_vehicle_candidates,
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


__all__ = ["Mercury2Client", "Mercury2VehicleAdjudicator"]
