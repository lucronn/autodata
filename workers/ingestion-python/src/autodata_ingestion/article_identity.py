"""Canonical article identity helpers for ingestion."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


DEFAULT_NEAR_DUPLICATE_GATE = 0.95


@dataclass(frozen=True)
class CanonicalArticleIdentity:
    article_key: str
    source_uri: str | None
    title: str
    body: str
    normalized_text: str
    token_signature: tuple[str, ...]
    sequence_signature: str
    near_duplicate_of: str | None
    near_duplicate_score: float
    is_near_duplicate: bool

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["token_signature"] = list(self.token_signature)
        return output


def canonicalize_article_identity(
    article: Mapping[str, Any],
    *,
    existing_articles: Sequence[Mapping[str, Any]] = (),
    near_duplicate_gate: float = DEFAULT_NEAR_DUPLICATE_GATE,
) -> CanonicalArticleIdentity:
    title = _require_text(article.get("title"), "title")
    body = _require_text(article.get("body"), "body")
    source_uri = article.get("source_uri")
    if source_uri is not None:
        source_uri = str(source_uri)

    article_key = _exact_hash(title, body, source_uri)
    normalized_text = _normalize_text(f"{title} {body}")
    token_signature = tuple(re.findall(r"[a-z0-9]+", normalized_text))
    best_key = None
    best_score = 0.0
    for existing in existing_articles:
        existing_key = _exact_hash(
            _require_text(existing.get("title"), "title"),
            _require_text(existing.get("body"), "body"),
            str(existing.get("source_uri")) if existing.get("source_uri") is not None else None,
        )
        existing_normalized = _normalize_text(
            f"{_require_text(existing.get('title'), 'title')} {_require_text(existing.get('body'), 'body')}"
        )
        score = _similarity(normalized_text, token_signature, existing_normalized)
        if score > best_score or (score == best_score and best_key is not None and existing_key < best_key):
            best_key = existing_key
            best_score = score
        elif score == best_score and best_key is None:
            best_key = existing_key
    is_near_duplicate = best_score >= near_duplicate_gate and best_key is not None
    return CanonicalArticleIdentity(
        article_key=article_key,
        source_uri=source_uri,
        title=title,
        body=body,
        normalized_text=normalized_text,
        token_signature=token_signature,
        sequence_signature=normalized_text,
        near_duplicate_of=best_key if is_near_duplicate else None,
        near_duplicate_score=best_score,
        is_near_duplicate=is_near_duplicate,
    )


def _exact_hash(title: str, body: str, source_uri: str | None) -> str:
    payload = {"body": body, "source_uri": source_uri, "title": title}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _require_text(value: Any, field_name: str) -> str:
    text = str(value) if value is not None else ""
    if not text:
        raise ValueError(f"article {field_name} is required")
    return text


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.casefold())).strip()


def _similarity(
    normalized_text: str,
    token_signature: tuple[str, ...],
    other_normalized_text: str,
) -> float:
    other_tokens = tuple(re.findall(r"[a-z0-9]+", other_normalized_text))
    token_score = _token_similarity(token_signature, other_tokens)
    sequence_score = SequenceMatcher(None, normalized_text, other_normalized_text).ratio()
    return round((token_score + sequence_score) / 2, 6)


def _token_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left and not right:
        return 1.0
    overlap = sum((Counter(left) & Counter(right)).values())
    return overlap / max(len(left), len(right))


__all__ = [
    "CanonicalArticleIdentity",
    "DEFAULT_NEAR_DUPLICATE_GATE",
    "canonicalize_article_identity",
]
