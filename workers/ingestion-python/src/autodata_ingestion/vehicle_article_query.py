"""Fast local article lookup with an injected source fallback."""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from typing import Any, Callable, Iterable, Mapping

from .vehicle_identity import canonicalize_vehicle_observation


ArticleFetcher = Callable[[Mapping[str, Any], str], Iterable[Mapping[str, Any]]]


def query_vehicle_articles(
    vehicle: Mapping[str, Any] | str,
    query: str,
    indexed_articles: MutableMapping[str, Iterable[Mapping[str, Any]]],
    *,
    fetcher: ArticleFetcher | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search a vehicle's normalized articles, fetching only on a cache miss."""

    if not str(query).strip():
        raise ValueError("article query must not be empty")
    if limit < 1 or limit > 50:
        raise ValueError("article query limit must be between 1 and 50")
    observation = canonicalize_vehicle_observation(vehicle)
    vehicle_key = _stable_vehicle_key(observation)
    candidates = list(indexed_articles.get(vehicle_key, ()))
    results = _rank_articles(candidates, query, limit)
    status = "found" if results else "not_found"
    if not results and fetcher is not None:
        fetched = list(fetcher(observation.to_dict(), query))
        if fetched:
            indexed_articles[vehicle_key] = tuple([*candidates, *fetched])
        results = _rank_articles(fetched, query, limit)
        status = "fetched" if results else "not_found"
    return {"status": status, "vehicle_id_key": vehicle_key, "results": results}


def _rank_articles(articles: Iterable[Mapping[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for article in articles:
        article_copy = dict(article)
        article_tokens = _tokens(_article_text(article_copy))
        overlap = query_tokens & article_tokens
        if not overlap:
            continue
        score = len(overlap) / len(query_tokens)
        ranked.append((score, str(article_copy.get("article_id", "")), article_copy | {"match_score": score}))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def _article_text(article: Mapping[str, Any]) -> str:
    return " ".join(
        str(article.get(field, ""))
        for field in ("article_id", "title", "bucket", "bulletin_number", "body", "content", "steps")
    )


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _stable_vehicle_key(observation: Any) -> str:
    parts = [_slug(observation.make), _slug(observation.model), str(observation.year)]
    if observation.region:
        parts.append(_slug(observation.region))
    return "-".join(parts)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


__all__ = ["query_vehicle_articles"]
