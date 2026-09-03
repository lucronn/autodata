"""Deterministic smoke for universal article intake and knowledge lookup.

The default path is intentionally local: it uses an in-memory HTTP-shaped
source, the worker's provider-neutral article intake, and a small replay-safe
publisher.  A live knowledge URL is checked only when supplied explicitly via
``--live-url`` or ``AUTODATA_KNOWLEDGE_SMOKE_URL``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).parents[2]
WORKER_SRC = ROOT / "workers" / "ingestion-python" / "src"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from autodata_ingestion.article_intake import (  # noqa: E402
    VehicleArticleIntake,
    VehicleTarget,
    ingest_vehicle_article,
)
from autodata_ingestion.source_adapters import SourceResource  # noqa: E402


DEFAULT_TARGET = VehicleTarget("Cadillac", "Escalade ESV", 2019, "US")
DEFAULT_SOURCE_URI = "https://static.source.test/articles/tsb-42"
DEFAULT_SOURCE_VERSION = "fixture-v1"
DEFAULT_DATASET_ID = "70000000-0000-0000-0000-000000000042"
DEFAULT_REVISION_ID = "60000000-0000-0000-0000-000000000042"
FIXTURE_TIMESTAMP = "2026-09-03T00:00:00Z"

# This is a deliberately small, deterministic source-shaped payload.  It is
# not loaded from the repository's sample-data directory.
SAMPLE_ARTICLE_HTML = b"""
<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
      {
        "@type": "TechArticle",
        "headline": "Brake caliper replacement bulletin",
        "identifier": "TSB-42",
        "articleSection": "Service Bulletins",
        "datePublished": "2026-09-02",
        "articleBody": "Remove the wheel, replace the brake caliper, and torque the caliper guide pins.",
        "steps": ["Remove the wheel", "Torque the caliper guide pins"],
        "about": {"@type": "Vehicle", "name": "2019 Cadillac Escalade ESV"}
      }
    </script>
  </head>
  <body><article><h1>Brake caliper replacement bulletin</h1></article></body>
</html>
"""

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class StaticHTTPSource:
    """A deterministic connector with the same fetch shape as an HTTP source."""

    name = "static-http"

    def __init__(
        self,
        payload: bytes | str,
        *,
        source_uri: str = DEFAULT_SOURCE_URI,
        source_version: str = DEFAULT_SOURCE_VERSION,
    ) -> None:
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        self.source_uri = source_uri
        self.source_version = source_version
        self.requests: list[dict[str, Any]] = []

    def fetch(self, request: dict[str, Any]) -> list[SourceResource]:
        requested_uri = str(request.get("source_uri", self.source_uri))
        if requested_uri != self.source_uri:
            raise ValueError(f"static source received unexpected URI: {requested_uri}")
        self.requests.append({"source_uri": requested_uri})
        return [
            SourceResource.from_bytes(
                self.source_uri,
                self.source_version,
                self.payload,
                "text/html",
                locator=self.source_uri,
                metadata={"connector": self.name},
            )
        ]


@dataclass(frozen=True)
class ReplayRecord:
    status: str
    payload: dict[str, Any]


class ReplayStore:
    """In-memory publication boundary that makes duplicate delivery observable."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, dict[str, Any]]] = {}
        self.write_count = 0

    def publish(self, idempotency_key: str, payload: dict[str, Any]) -> ReplayRecord:
        key = str(idempotency_key).strip()
        if not key:
            raise ValueError("idempotency key is required")
        canonical = _canonical_json(payload)
        existing = self._records.get(key)
        if existing is not None:
            existing_canonical, existing_payload = existing
            if existing_canonical != canonical:
                raise ValueError(f"conflicting replay for idempotency key {key}")
            return ReplayRecord("replay", _copy_json(existing_payload))
        stored_payload = _copy_json(payload)
        self._records[key] = (canonical, stored_payload)
        self.write_count += 1
        return ReplayRecord("created", _copy_json(stored_payload))


@dataclass(frozen=True)
class LookupMetrics:
    query: str
    elapsed_ns: int
    result_count: int


def intake_fixture(source: StaticHTTPSource | None = None) -> VehicleArticleIntake:
    """Run the worker intake against the embedded static HTTP-shaped fixture."""

    connector = source or StaticHTTPSource(SAMPLE_ARTICLE_HTML)
    return ingest_vehicle_article(
        connector.source_uri,
        DEFAULT_TARGET,
        connector=connector,
    )


def intake_idempotency_key(intake: VehicleArticleIntake) -> str:
    """Return the stable replay identity for one normalized article."""

    if intake.status != "ready" or not intake.bundle.articles:
        raise ValueError("cannot create an idempotency key for an unsuccessful intake")
    article = intake.bundle.articles[0]
    return ":".join(
        (
            "article-intake",
            intake.target.vehicle_key,
            str(article["article_id"]),
            str(article["content_sha256"]),
        )
    )


def build_structured_catalog(intake: VehicleArticleIntake) -> dict[str, Any]:
    """Project an intake into the small structured catalog used by this smoke.

    The procedure record is intentionally sample-shaped and derived from the
    article's explicit body/steps.  This keeps the smoke independent of a live
    deep-lane processor while still exercising the article/procedure response
    contract used by keyword lookup.
    """

    if intake.status != "ready" or intake.bundle.vehicle is None:
        raise ValueError("cannot build a catalog from an unsuccessful intake")
    if not intake.bundle.articles:
        raise ValueError("cannot build a catalog without an article")

    source_artifact = intake.artifacts[0]
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence in intake.bundle.evidence:
        artifact = next(
            (
                candidate
                for candidate in intake.artifacts
                if candidate.content_sha256 == evidence["content_sha256"]
            ),
            source_artifact,
        )
        evidence_by_id[evidence["evidence_id"]] = {
            "evidence_id": evidence["evidence_id"],
            "locator": evidence["locator"],
            "artifact_key": artifact.object_key,
            "source_uri": evidence["source_uri"],
            "source_version": artifact.source_version,
            "extracted_text": evidence["extracted_text"],
            "confidence": evidence["confidence"],
        }

    article = dict(intake.bundle.articles[0])
    article_id = str(article["article_id"])
    procedure = {
        "procedure_id": f"procedure:{article_id}",
        "section": "procedures",
        "excerpt": str(article.get("body") or "").strip(),
        "evidence_id": article["evidence_id"],
        "matched_terms": [],
    }
    return {
        "dataset_id": DEFAULT_DATASET_ID,
        "revision_id": DEFAULT_REVISION_ID,
        "availability": "viewable",
        "source_watermark": source_artifact.source_version,
        "sections": [
            {
                "name": "vehicle_identity",
                "status": "viewable",
                "last_published_revision": DEFAULT_REVISION_ID,
                "updated_at": FIXTURE_TIMESTAMP,
            },
            {
                "name": "articles",
                "status": "viewable",
                "last_published_revision": DEFAULT_REVISION_ID,
                "updated_at": FIXTURE_TIMESTAMP,
            },
            {
                "name": "procedures",
                "status": "viewable",
                "last_published_revision": DEFAULT_REVISION_ID,
                "updated_at": FIXTURE_TIMESTAMP,
            },
        ],
        "vehicle_identity": dict(intake.bundle.vehicle),
        "articles": [article],
        "procedures": [procedure],
        "evidence": list(evidence_by_id.values()),
    }


def keyword_to_structured_json(
    catalog: dict[str, Any],
    query: str,
    *,
    kind: str = "all",
    limit: int = 10,
    clock: Callable[[], int] = time.perf_counter_ns,
    on_latency: Callable[[LookupMetrics], None] | None = None,
) -> dict[str, Any]:
    """Map a keyword query to deterministic, contract-shaped JSON results."""

    response, _ = measure_keyword_lookup(
        catalog,
        query,
        kind=kind,
        limit=limit,
        clock=clock,
        on_latency=on_latency,
    )
    return response


def measure_keyword_lookup(
    catalog: dict[str, Any],
    query: str,
    *,
    kind: str = "all",
    limit: int = 10,
    clock: Callable[[], int] = time.perf_counter_ns,
    on_latency: Callable[[LookupMetrics], None] | None = None,
) -> tuple[dict[str, Any], LookupMetrics]:
    """Map a keyword query to deterministic, contract-shaped JSON results."""

    if kind not in {"all", "article", "procedure"}:
        raise ValueError("kind must be all, article, or procedure")
    if limit < 1:
        raise ValueError("limit must be positive")
    start = clock()
    query_text = str(query).strip()
    query_tokens = _tokens(query_text)
    results: list[dict[str, Any]] = []
    evidence_by_id = {
        str(item["evidence_id"]): item for item in catalog.get("evidence", [])
    }
    if query_tokens:
        if kind in {"all", "article"}:
            for article in catalog.get("articles", []):
                score, _ = _match_score(query_tokens, article)
                if score:
                    results.append(
                        {
                            "kind": "article",
                            "id": str(article["article_id"]),
                            "score": score,
                            "article": _article_output(article),
                            "evidence": _evidence_output(article, evidence_by_id),
                        }
                    )
        if kind in {"all", "procedure"}:
            for procedure in catalog.get("procedures", []):
                score, matched = _match_score(query_tokens, procedure)
                if score:
                    procedure_output = dict(procedure)
                    procedure_output["matched_terms"] = matched
                    results.append(
                        {
                            "kind": "procedure",
                            "id": str(procedure["procedure_id"]),
                            "score": score,
                            "procedure": _procedure_output(procedure_output),
                            "evidence": _evidence_output(procedure, evidence_by_id),
                        }
                    )
    results.sort(key=lambda result: (-result["score"], result["kind"], result["id"]))
    response = {
        key: _copy_json(catalog[key])
        for key in (
            "dataset_id",
            "revision_id",
            "availability",
            "source_watermark",
            "sections",
            "vehicle_identity",
        )
        if key in catalog
    }
    response["results"] = results[:limit]
    validate_knowledge_response(response)
    return response, _finish_metrics(query_text, start, clock, len(response["results"]), on_latency)


def validate_knowledge_response(response: dict[str, Any]) -> None:
    """Validate the response fields needed by the article/procedure contract."""

    required = {
        "dataset_id",
        "revision_id",
        "availability",
        "source_watermark",
        "sections",
        "results",
    }
    missing = sorted(required - response.keys())
    if missing:
        raise ValueError(f"knowledge response is missing fields: {', '.join(missing)}")
    for field in ("dataset_id", "revision_id", "availability", "source_watermark"):
        if not isinstance(response[field], str) or not response[field].strip():
            raise ValueError(f"knowledge response field {field} must be a non-empty string")
    if not isinstance(response["sections"], list) or not isinstance(response["results"], list):
        raise ValueError("knowledge response sections and results must be arrays")
    for section in response["sections"]:
        _require_fields(section, ("name", "status", "last_published_revision", "updated_at"), "section")
    for result in response["results"]:
        _require_fields(result, ("kind", "id", "score", "evidence"), "result")
        if result["kind"] not in {"article", "procedure"}:
            raise ValueError(f"unsupported knowledge result kind: {result['kind']}")
        if not isinstance(result["score"], (int, float)) or result["score"] <= 0:
            raise ValueError("knowledge result score must be positive")
        if result["kind"] == "article":
            _require_fields(result.get("article", {}), ("article_id",), "article")
        else:
            _require_fields(
                result.get("procedure", {}),
                ("procedure_id", "section", "excerpt"),
                "procedure",
            )
        for evidence in result["evidence"]:
            _require_fields(evidence, ("evidence_id", "locator", "confidence"), "evidence")


def run_smoke(live_url: str | None = None, *, live_query: str = "brake caliper") -> dict[str, Any]:
    """Run local checks and optionally validate one explicitly configured URL."""

    source = StaticHTTPSource(SAMPLE_ARTICLE_HTML)
    intake = intake_fixture(source)
    catalog = build_structured_catalog(intake)
    response, metrics = measure_keyword_lookup(catalog, live_query)
    replay_store = ReplayStore()
    key = intake_idempotency_key(intake)
    first = replay_store.publish(key, response)
    replay = replay_store.publish(key, response)
    summary: dict[str, Any] = {
        "status": "passed",
        "vehicle_key": intake.bundle.vehicle["vehicle_key"],
        "article_id": intake.bundle.articles[0]["article_id"],
        "result_kinds": [result["kind"] for result in response["results"]],
        "replay": {
            "first": first.status,
            "second": replay.status,
            "writes": replay_store.write_count,
        },
        "lookup_latency_ns": metrics.elapsed_ns,
        "live": {"status": "skipped", "reason": "no live URL configured"},
    }
    if live_url:
        summary["live"] = _run_live_check(live_url, live_query)
    return summary


def _run_live_check(url: str, query: str) -> dict[str, Any]:
    parsed = urlsplit(url)
    query_values = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_values.setdefault("q", query)
    query_values.setdefault("limit", "10")
    target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query_values), parsed.fragment))
    request = Request(target, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=10) as response:
        status = int(getattr(response, "status", 200))
        payload = json.loads(response.read().decode("utf-8"))
    validate_knowledge_response(payload)
    return {"status": "passed", "http_status": status, "result_count": len(payload["results"])}


def _article_output(article: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _copy_json(article[key])
        for key in (
            "article_id",
            "article_key",
            "bucket",
            "title",
            "bulletin_number",
            "release_date",
            "body",
            "steps",
        )
        if key in article and article[key] is not None
    }


def _procedure_output(procedure: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _copy_json(procedure[key])
        for key in ("procedure_id", "section", "excerpt", "matched_terms")
        if key in procedure and procedure[key] is not None
    }


def _evidence_output(record: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ids = record.get("evidence_ids") or [record.get("evidence_id")]
    return [_copy_json(evidence_by_id[str(evidence_id)]) for evidence_id in ids if str(evidence_id) in evidence_by_id]


def _match_score(query_tokens: list[str], record: dict[str, Any]) -> tuple[float, list[str]]:
    text = " ".join(str(value) for value in record.values() if isinstance(value, (str, int, float, list)))
    record_tokens = set(_tokens(text))
    matched = [token for token in query_tokens if token in record_tokens]
    return len(matched) / len(query_tokens), matched


def _tokens(value: str) -> list[str]:
    return list(dict.fromkeys(_TOKEN_RE.findall(value.casefold())))


def _finish_metrics(
    query: str,
    start: int,
    clock: Callable[[], int],
    result_count: int,
    on_latency: Callable[[LookupMetrics], None] | None,
) -> LookupMetrics:
    metrics = LookupMetrics(query, max(0, clock() - start), result_count)
    if on_latency is not None:
        on_latency(metrics)
    return metrics


def _require_fields(value: Any, fields: tuple[str, ...], label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = [field for field in fields if field not in value]
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(missing)}")


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-url", default=os.getenv("AUTODATA_KNOWLEDGE_SMOKE_URL"))
    parser.add_argument("--query", default="brake caliper")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_smoke(args.live_url, live_query=args.query), sort_keys=True))
    except Exception as error:
        raise SystemExit(f"universal article smoke failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
