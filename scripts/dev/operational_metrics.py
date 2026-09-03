"""Render a provider-neutral Prometheus snapshot from the operational store.

This command intentionally has no vendor SDK dependency. It can be run as a
short-lived sidecar, a scheduled exporter, or from a local Compose shell. NATS
and worker queues are represented by their durable PostgreSQL job/outbox state;
that state is the recovery source of truth after a process restart.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | int
    labels: dict[str, str] | None = None
    kind: str = "gauge"
    family_name: str | None = None


CONFIDENCE_BUCKETS = (0.5, 0.7, 0.8, 0.9, 0.95, 1.0)


def confidence_histogram(values: Iterable[float | None]) -> list[tuple[float, int]]:
    """Return cumulative confidence counts for the standard quality buckets."""

    usable = sorted(float(value) for value in values if value is not None)
    return [(bucket, sum(value <= bucket for value in usable)) for bucket in CONFIDENCE_BUCKETS]


def render_metrics(metrics: Iterable[Metric]) -> str:
    """Render deterministic Prometheus text with stable label ordering."""

    rows: list[str] = []
    declared: set[str] = set()
    for metric in metrics:
        family_name = metric.family_name or metric.name
        if family_name not in declared:
            rows.append(f"# TYPE {family_name} {metric.kind}")
            declared.add(family_name)
        labels = ""
        if metric.labels:
            encoded = []
            for key, value in sorted(metric.labels.items()):
                escaped = str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
                encoded.append(f'{key}="{escaped}"')
            labels = "{" + ",".join(encoded) + "}"
        rows.append(f"{metric.name}{labels} {_number(metric.value)}")
    return "\n".join(rows) + ("\n" if rows else "")


def collect_metrics(connection: Any, now: datetime | None = None) -> list[Metric]:
    """Collect the required operational signals from PostgreSQL."""

    observed_at = now or datetime.now(UTC)
    metrics: list[Metric] = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT avg(GREATEST(EXTRACT(EPOCH FROM (
                latest.published_at - COALESCE(payment.occurred_at, request.created_at)
            )), 0))
            FROM dataset_requests request
            JOIN dataset_projections projection
              ON projection.dataset_request_id = request.dataset_request_id
            LEFT JOIN entitlements entitlement
              ON entitlement.dataset_request_id = request.dataset_request_id
            LEFT JOIN payment_events payment
              ON payment.payment_event_id = entitlement.payment_event_id
            JOIN LATERAL (
                SELECT published_at
                FROM dataset_revisions revision
                WHERE revision.dataset_projection_id = projection.dataset_projection_id
                  AND revision.published_at IS NOT NULL
                ORDER BY revision.revision_number ASC
                LIMIT 1
            ) latest ON true
            WHERE request.status IN ('viewable', 'enriching', 'complete')
            """
        )
        payment_to_viewable = cursor.fetchone()[0]
        if payment_to_viewable is not None:
            metrics.append(Metric("autodata_payment_to_viewable_seconds", float(payment_to_viewable)))

        cursor.execute(
            """
            SELECT lane, status, count(*)
            FROM dataset_requests
            GROUP BY lane, status
            ORDER BY lane, status
            """
        )
        metrics.extend(
            Metric(
                "autodata_lane_requests_total",
                count,
                {"lane": lane, "status": status},
            )
            for lane, status, count in cursor.fetchall()
        )

        cursor.execute(
            """
            SELECT section_name, status, count(*)
            FROM dataset_section_status
            GROUP BY section_name, status
            ORDER BY section_name, status
            """
        )
        metrics.extend(
            Metric(
                "autodata_deep_section_status_total",
                count,
                {"section": section_name, "status": status},
            )
            for section_name, status, count in cursor.fetchall()
        )

        cursor.execute(
            """
            SELECT lane, status, count(*),
                   COALESCE(EXTRACT(EPOCH FROM (%s - min(created_at))), 0)
            FROM ingestion_jobs
            WHERE status IN ('pending', 'processing')
            GROUP BY lane, status
            ORDER BY lane, status
            """,
            (observed_at,),
        )
        for lane, status, count, oldest_age in cursor.fetchall():
            labels = {"queue": "ingestion", "lane": lane, "status": status}
            metrics.append(Metric("autodata_queue_depth", count, labels))
            metrics.append(Metric("autodata_queue_oldest_age_seconds", float(oldest_age), labels))

        cursor.execute(
            """
            SELECT delivery_status, count(*),
                   COALESCE(EXTRACT(EPOCH FROM (%s - min(created_at))), 0)
            FROM publication_events
            WHERE delivery_status IN ('pending', 'failed')
            GROUP BY delivery_status
            ORDER BY delivery_status
            """,
            (observed_at,),
        )
        for status, count, oldest_age in cursor.fetchall():
            labels = {"queue": "publication_outbox", "status": status}
            metrics.append(Metric("autodata_queue_depth", count, labels))
            metrics.append(Metric("autodata_queue_oldest_age_seconds", float(oldest_age), labels))

        cursor.execute(
            """
            SELECT COALESCE(sum(GREATEST(attempt_count - 1, 0)), 0),
                   count(*) FILTER (WHERE status = 'dead_letter')
            FROM ingestion_jobs
            """
        )
        ingestion_retries, ingestion_dead_letters = cursor.fetchone()
        metrics.append(Metric("autodata_retry_count", ingestion_retries, {"queue": "ingestion"}))
        metrics.append(Metric("autodata_dead_letter_count", ingestion_dead_letters, {"queue": "ingestion"}))

        cursor.execute(
            """
            SELECT COALESCE(sum(delivery_attempts), 0),
                   count(*) FILTER (WHERE delivery_status = 'dead_letter')
            FROM publication_events
            """
        )
        publication_retries, publication_dead_letters = cursor.fetchone()
        metrics.append(Metric("autodata_retry_count", publication_retries, {"queue": "publication_outbox"}))
        metrics.append(Metric("autodata_dead_letter_count", publication_dead_letters, {"queue": "publication_outbox"}))

        cursor.execute("SELECT confidence FROM extraction_evidence WHERE confidence IS NOT NULL")
        confidence_values = [row[0] for row in cursor.fetchall()]
        for bucket, count in confidence_histogram(confidence_values):
            metrics.append(
                Metric(
                    "autodata_extraction_confidence_bucket",
                    count,
                    {"le": str(bucket)},
                    kind="histogram",
                    family_name="autodata_extraction_confidence",
                )
            )
        metrics.append(
            Metric(
                "autodata_extraction_confidence_bucket",
                len(confidence_values),
                {"le": "+Inf"},
                kind="histogram",
                family_name="autodata_extraction_confidence",
            )
        )
        metrics.append(
            Metric(
                "autodata_extraction_confidence_count",
                len(confidence_values),
                kind="histogram",
                family_name="autodata_extraction_confidence",
            )
        )
        metrics.append(
            Metric(
                "autodata_extraction_confidence_sum",
                sum(confidence_values),
                kind="histogram",
                family_name="autodata_extraction_confidence",
            )
        )

        cursor.execute(
            """
            SELECT 'feedback' AS kind, count(*),
                   COALESCE(EXTRACT(EPOCH FROM (%s - min(created_at))), 0)
            FROM feedback_items
            WHERE status IN ('open', 'in_review')
            UNION ALL
            SELECT 'evidence' AS kind, count(*),
                   COALESCE(EXTRACT(EPOCH FROM (%s - min(created_at))), 0)
            FROM extraction_evidence
            WHERE reviewer_state = 'pending'
            ORDER BY kind
            """,
            (observed_at, observed_at),
        )
        for kind, count, oldest_age in cursor.fetchall():
            metrics.append(Metric("autodata_human_review_backlog", count, {"kind": kind}))
            metrics.append(Metric("autodata_human_review_oldest_age_seconds", float(oldest_age), {"kind": kind}))

        cursor.execute(
            """
            SELECT count(*)
            FROM dataset_revisions
            WHERE published_at >= %s - interval '1 hour'
            """,
            (observed_at,),
        )
        metrics.append(Metric("autodata_revision_publication_rate_per_hour", cursor.fetchone()[0]))

        cursor.execute("SELECT EXTRACT(EPOCH FROM (%s - max(retrieved_at))) FROM source_snapshots", (observed_at,))
        source_lag = cursor.fetchone()[0]
        if source_lag is not None:
            metrics.append(Metric("autodata_source_watermark_age_seconds", float(source_lag)))

        cursor.execute(
            """
            SELECT avg(EXTRACT(EPOCH FROM (fulfilled_at - occurred_at))),
                   count(*) FILTER (WHERE fulfillment_status = 'pending'),
                   count(*) FILTER (WHERE fulfillment_status = 'failed')
            FROM payment_events
            """
        )
        fulfillment_lag, pending_fulfillment, failed_fulfillment = cursor.fetchone()
        if fulfillment_lag is not None:
            metrics.append(Metric("autodata_entitlement_fulfillment_lag_seconds", float(fulfillment_lag)))
        metrics.append(Metric("autodata_entitlement_fulfillment_pending", pending_fulfillment))
        metrics.append(Metric("autodata_entitlement_fulfillment_failures", failed_fulfillment))

        cursor.execute(
            """
            SELECT count(*) FILTER (WHERE event_type = 'dataset.revision.revoked'),
                   count(*) FILTER (WHERE event_type = 'dataset.revision.revoked'
                                    AND payload->>'reason' = 'source_takedown')
            FROM publication_events
            """
        )
        revocations, takedown_revocations = cursor.fetchone()
        metrics.append(Metric("autodata_entitlement_revocations_total", revocations))
        metrics.append(Metric("autodata_source_takedown_revocations_total", takedown_revocations))

        cursor.execute("SELECT count(*) FROM source_snapshots WHERE takedown_status = 'takedown'")
        metrics.append(Metric("autodata_source_takedowns_total", cursor.fetchone()[0]))

    return metrics


def _number(value: float | int) -> str:
    return str(value) if isinstance(value, int) else format(value, ".15g")


def _db_connection() -> Any:
    import psycopg

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    with _db_connection() as connection:
        print(render_metrics(collect_metrics(connection)), end="")


if __name__ == "__main__":
    main()
