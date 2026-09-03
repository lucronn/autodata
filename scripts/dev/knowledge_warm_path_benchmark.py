"""Deterministic cold/fetched versus warm normalized-revision knowledge lookup.

The default CLI uses the embedded article fixture from ``universal_article_smoke``
and an in-memory resolver/connector.  It emits one JSON object suitable for
protected CI.  ``WARM_PATH_TARGET`` deliberately describes a report-only
measurement target: synthetic timings are useful for comparing the two paths,
but are not a production latency SLO.  The fixture's fetched article is also
projected into one procedure result so ordering and provenance are exercised
with more than one normalized record; this projection is not a second fetch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).parents[2]
WORKER_SRC = ROOT / "workers" / "ingestion-python" / "src"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from autodata_ingestion.article_intake import (  # noqa: E402
    VehicleArticleIntake,
    VehicleTarget,
    ingest_vehicle_article,
)
from autodata_ingestion.knowledge_fallback import (  # noqa: E402
    KnowledgeFallbackResult,
    ResolvedSource,
    query_vehicle_knowledge,
)
from universal_article_smoke import (  # noqa: E402
    DEFAULT_REVISION_ID,
    DEFAULT_SOURCE_URI,
    DEFAULT_TARGET,
    SAMPLE_ARTICLE_HTML,
    StaticHTTPSource,
)


DEFAULT_QUERY = "brake caliper"
NORMALIZED_REVISION_ID = DEFAULT_REVISION_ID
WARM_PATH_TARGET_NS: int | None = None
WARM_PATH_TARGET = {
    "name": "normalized_revision_lookup",
    "metric": "latency_ns",
    "unit": "ns",
    "max_latency_ns": WARM_PATH_TARGET_NS,
    "enforcement": "report_only",
    "measurement_hook": "on_measurement",
}

Clock = Callable[[], int]
MeasurementHook = Callable[["LookupMeasurement"], None]


@dataclass(frozen=True)
class LookupMeasurement:
    """Machine-readable observation for one lookup path."""

    phase: str
    status: str
    elapsed_ns: int
    result_count: int
    resolver_calls: int
    revision_id: str
    result_order: tuple[str, ...]
    provenance: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "latency_ns": self.elapsed_ns,
            "result_count": self.result_count,
            "resolver_calls": self.resolver_calls,
            "revision_id": self.revision_id,
            "result_order": list(self.result_order),
            "provenance": [dict(item) for item in self.provenance],
        }


@dataclass(frozen=True)
class NormalizedRevision:
    """The small immutable revision index used by the warm lookup."""

    revision_id: str
    vehicle_key: str
    source_uri: str
    source_version: str
    records: tuple[dict[str, Any], ...]


class WarmPathBenchmark:
    """Run one fetched lookup followed by a normalized-revision cache hit."""

    def __init__(
        self,
        target: VehicleTarget,
        query: str,
        *,
        source_resolver: Callable[..., Any] | Any,
        ingest: Callable[..., VehicleArticleIntake] = ingest_vehicle_article,
        keywords: tuple[str, ...] = (),
        kind: str = "all",
        limit: int = 10,
        revision_id: str = NORMALIZED_REVISION_ID,
        clock: Clock = time.perf_counter_ns,
        on_measurement: MeasurementHook | None = None,
    ) -> None:
        self.target = target
        self.query = query
        self.source_resolver = source_resolver
        self.ingest = ingest
        self.keywords = tuple(keywords)
        self.kind = kind
        self.limit = limit
        self.revision_id = revision_id
        self.clock = clock
        self.on_measurement = on_measurement
        self.resolver_calls_total = 0
        self._revision: NormalizedRevision | None = None
        self._last_source_uri = ""
        self._last_source_version = ""

    def lookup(self) -> tuple[KnowledgeFallbackResult, LookupMeasurement]:
        """Perform a cold fetch once, then search the stored revision."""

        phase = "warm_normalized_revision" if self._revision is not None else "cold_fetch"
        resolver_calls_before = self.resolver_calls_total
        start = self.clock()
        if self._revision is None:
            result = query_vehicle_knowledge(
                self.target,
                self.query,
                catalog=(),
                source_resolver=self._counted_resolver,
                keywords=self.keywords,
                kind=self.kind,
                ingest=self._capturing_ingest,
            )
            if result.status != "fetched":
                raise AssertionError(f"cold lookup was not marked fetched: {result.status}")
            if not result.source_uri or not self._last_source_version:
                raise AssertionError("fetched lookup did not expose source provenance")
            result = _project_fixture_procedure(result)
            self._revision = NormalizedRevision(
                revision_id=self.revision_id,
                vehicle_key=self.target.vehicle_key,
                source_uri=result.source_uri,
                source_version=self._last_source_version,
                records=tuple(
                    {
                        "vehicle_key": self.target.vehicle_key,
                        **deepcopy(record),
                    }
                    for record in result.results
                ),
            )
        else:
            revision = self._revision
            result = query_vehicle_knowledge(
                self.target,
                self.query,
                catalog={
                    "vehicle_key": revision.vehicle_key,
                    "results": deepcopy(revision.records),
                },
                source_resolver=self._counted_resolver,
                keywords=self.keywords,
                kind=self.kind,
                ingest=self.ingest,
            )
            if result.status != "cache_hit":
                raise AssertionError(f"warm lookup was not marked cache_hit: {result.status}")

        revision = self._revision
        assert revision is not None
        measurement = LookupMeasurement(
            phase=phase,
            status=result.status,
            elapsed_ns=max(0, self.clock() - start),
            result_count=len(result.results),
            resolver_calls=self.resolver_calls_total - resolver_calls_before,
            revision_id=revision.revision_id,
            result_order=tuple(
                f"{item['kind']}:{item['id']}" for item in result.results
            ),
            provenance=_provenance(
                result.results,
                source_uri=revision.source_uri,
                source_version=revision.source_version,
            ),
        )
        if self.on_measurement is not None:
            self.on_measurement(measurement)
        return result, measurement

    def run(self) -> dict[str, Any]:
        cold_result, cold_measurement = self.lookup()
        warm_result, warm_measurement = self.lookup()
        cold = cold_measurement.to_dict()
        warm = warm_measurement.to_dict()

        if cold["result_order"] != warm["result_order"]:
            raise AssertionError("cold and warm result ordering changed")
        if cold["provenance"] != warm["provenance"]:
            raise AssertionError("cold and warm provenance changed")
        if cold["result_count"] != warm["result_count"]:
            raise AssertionError("cold and warm result counts changed")
        if cold_result.status != "fetched" or warm_result.status != "cache_hit":
            raise AssertionError("lookup path status markers are inconsistent")

        return {
            "benchmark": "knowledge_warm_path",
            "status": "passed",
            "target": dict(WARM_PATH_TARGET),
            "vehicle_key": self.target.vehicle_key,
            "query": self.query,
            "revision_id": self.revision_id,
            "cold_fetch": cold,
            "warm_normalized_revision": warm,
            "resolver_calls_total": self.resolver_calls_total,
            "comparisons": {
                "cold_slower_than_warm": cold["latency_ns"] > warm["latency_ns"],
                "result_count_equal": cold["result_count"] == warm["result_count"],
                "stable_ordering": cold["result_order"] == warm["result_order"],
                "stable_provenance": cold["provenance"] == warm["provenance"],
            },
        }

    def _counted_resolver(self, *args: Any, **kwargs: Any) -> Any:
        self.resolver_calls_total += 1
        resolver = getattr(self.source_resolver, "resolve", None)
        if callable(resolver):
            return resolver(*args, **kwargs)
        return self.source_resolver(*args, **kwargs)

    def _capturing_ingest(self, source_uri: str, target: VehicleTarget, **options: Any) -> VehicleArticleIntake:
        intake = self.ingest(source_uri, target, **options)
        self._last_source_uri = source_uri
        connector = options.get("connector")
        source_version = getattr(connector, "source_version", None)
        if not source_version and intake.artifacts:
            source_version = intake.artifacts[0].source_version
        self._last_source_version = str(source_version or "unknown")
        return intake


def run_benchmark(
    *,
    query: str = DEFAULT_QUERY,
    clock: Clock = time.perf_counter_ns,
    on_measurement: MeasurementHook | None = None,
) -> dict[str, Any]:
    """Run the local embedded-fixture benchmark without external services."""

    source = StaticHTTPSource(
        SAMPLE_ARTICLE_HTML,
        source_uri=DEFAULT_SOURCE_URI,
    )

    def resolver(target: VehicleTarget, resolved_query: str, keywords: tuple[str, ...]) -> ResolvedSource:
        del target, resolved_query, keywords
        return ResolvedSource(
            source.source_uri,
            connector=source,
            source_version=source.source_version,
        )

    benchmark = WarmPathBenchmark(
        DEFAULT_TARGET,
        query,
        source_resolver=resolver,
        clock=clock,
        on_measurement=on_measurement,
    )
    return benchmark.run()


def _project_fixture_procedure(result: KnowledgeFallbackResult) -> KnowledgeFallbackResult:
    """Add a deterministic procedure view backed by the fetched article evidence."""

    article_result = next(
        (item for item in result.results if item.get("kind") == "article"),
        None,
    )
    if article_result is None:
        return result
    article = article_result.get("article", {})
    if not isinstance(article, Mapping):
        return result
    article_id = str(article_result.get("id", "")).strip()
    excerpt = str(article.get("body", "")).strip()
    if not article_id or not excerpt:
        return result
    procedure = {
        "kind": "procedure",
        "id": f"procedure:{article_id}",
        "score": article_result["score"],
        "procedure": {
            "procedure_id": f"procedure:{article_id}",
            "section": "procedures",
            "excerpt": excerpt,
            "matched_terms": ["brake", "caliper"],
        },
        "evidence": deepcopy(article_result.get("evidence", [])),
    }
    return replace(result, results=tuple(result.results) + (procedure,))


def validate_benchmark_report(report: Mapping[str, Any]) -> None:
    """Validate the stable fields emitted for protected CI consumption."""

    required = {
        "benchmark",
        "status",
        "target",
        "vehicle_key",
        "query",
        "revision_id",
        "cold_fetch",
        "warm_normalized_revision",
        "resolver_calls_total",
        "comparisons",
    }
    missing = sorted(required - report.keys())
    if missing:
        raise ValueError(f"benchmark report is missing fields: {', '.join(missing)}")
    if report["benchmark"] != "knowledge_warm_path" or report["status"] != "passed":
        raise ValueError("benchmark report has an invalid identity or status")
    target = report["target"]
    if not isinstance(target, Mapping) or target.get("measurement_hook") != "on_measurement":
        raise ValueError("benchmark report is missing its measurement hook target")
    cold = report["cold_fetch"]
    warm = report["warm_normalized_revision"]
    for label, measurement, expected_status in (
        ("cold_fetch", cold, "fetched"),
        ("warm_normalized_revision", warm, "cache_hit"),
    ):
        if not isinstance(measurement, Mapping):
            raise ValueError(f"{label} measurement must be an object")
        if measurement.get("status") != expected_status:
            raise ValueError(f"{label} status must be {expected_status}")
        if not isinstance(measurement.get("latency_ns"), int) or measurement["latency_ns"] < 0:
            raise ValueError(f"{label} latency_ns must be a non-negative integer")
        if not isinstance(measurement.get("result_count"), int) or measurement["result_count"] < 0:
            raise ValueError(f"{label} result_count must be a non-negative integer")
        if not isinstance(measurement.get("result_order"), list):
            raise ValueError(f"{label} result_order must be an array")
        if not isinstance(measurement.get("provenance"), list):
            raise ValueError(f"{label} provenance must be an array")
    if report["resolver_calls_total"] != 1:
        raise ValueError("benchmark must resolve exactly once")
    if cold["result_count"] != warm["result_count"]:
        raise ValueError("cold and warm result counts differ")
    if cold["result_order"] != warm["result_order"]:
        raise ValueError("cold and warm result order differs")
    if cold["provenance"] != warm["provenance"]:
        raise ValueError("cold and warm provenance differs")


def _provenance(
    results: tuple[dict[str, Any], ...],
    *,
    source_uri: str,
    source_version: str,
) -> tuple[dict[str, str], ...]:
    unique: dict[str, dict[str, str]] = {}
    for result in results:
        for evidence in result.get("evidence", []):
            if not isinstance(evidence, Mapping):
                continue
            evidence_id = str(evidence.get("evidence_id", "")).strip()
            if not evidence_id:
                continue
            unique.setdefault(
                evidence_id,
                {
                    "evidence_id": evidence_id,
                    "source_uri": str(evidence.get("source_uri") or source_uri),
                    "source_version": str(evidence.get("source_version") or source_version),
                },
            )
    return tuple(unique[key] for key in sorted(unique))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(query=args.query)
        validate_benchmark_report(report)
    except Exception as error:
        print(
            json.dumps(
                {
                    "benchmark": "knowledge_warm_path",
                    "status": "failed",
                    "error": str(error),
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
