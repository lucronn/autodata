"""Immutable source-price snapshots and non-blocking refresh decisions.

Prices in this module are catalog observations, not customer charges.  A
snapshot is copied from the source record, stamped with a freshness state, and
never modified in place.  Refresh callbacks are queue boundaries: they are
allowed to record durable work, but must not be used to replace the value that
is returned for the current request.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any


PRICE_FRESHNESS_WINDOW = timedelta(days=30)


def price_freshness(priced_at: datetime, now: datetime) -> str:
    """Return ``fresh`` for prices younger than 30 days, otherwise ``stale``.

    Both timestamps are interpreted as instants and normalized to UTC.  A
    naive timestamp is rejected because silently treating local wall-clock
    time as UTC could move a price across the exact 30-day boundary.
    """

    priced_at_utc = _utc_datetime(priced_at, "priced_at")
    now_utc = _utc_datetime(now, "now")
    return "fresh" if now_utc - priced_at_utc < PRICE_FRESHNESS_WINDOW else "stale"


def read_cached_price_or_queue_refresh(
    part: Mapping[str, Any],
    *,
    now: datetime,
    refresh: Callable[[Mapping[str, Any]], Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Return one source-price snapshot and queue refresh work when stale.

    The input is never mutated.  A refresh callback is invoked only for a
    stale snapshot and is expected to enqueue durable work, not fetch a source
    synchronously.  Callback failures are represented in the returned stale
    snapshot so the current response remains useful and the old pricing date
    is retained.
    """

    if not isinstance(part, Mapping):
        raise TypeError("price record must be a mapping")
    if not callable(refresh):
        raise TypeError("price refresh boundary must be callable")

    snapshot = _snapshot_from_part(part)
    freshness = price_freshness(snapshot["_priced_at_datetime"], now)
    priced_at = snapshot.pop("_priced_at_datetime")
    snapshot["priced_at"] = _timestamp_text(part["priced_at"], priced_at)
    snapshot["freshness"] = freshness
    snapshot["refresh_status"] = "current"
    snapshot["markup_applied"] = False

    if freshness == "fresh":
        return snapshot

    refresh_key = _refresh_idempotency_key(snapshot)
    snapshot["refresh_idempotency_key"] = refresh_key
    snapshot["refresh_request_id"] = refresh_key
    snapshot["refresh_attempt_number"] = 1
    try:
        queued = refresh(deepcopy(dict(part)))
    except Exception as error:  # noqa: BLE001 - refresh must not block stale reads
        snapshot.update(
            {
                "refresh_status": "failed",
                "retryable": _retryable_refresh_error(error),
                "refresh_failure": {
                    "error_type": type(error).__name__,
                    "message": str(error).strip() or type(error).__name__,
                },
            }
        )
        return snapshot

    queue_result = dict(queued) if isinstance(queued, Mapping) else {}
    returned_key = _first_text(
        queue_result,
        "refresh_idempotency_key",
        "refresh_request_id",
        "refresh_id",
    )
    if returned_key:
        snapshot["refresh_idempotency_key"] = returned_key
        snapshot["refresh_request_id"] = returned_key
    attempt_number = _positive_int(
        queue_result.get("refresh_attempt_number", queue_result.get("attempt_count"))
    )
    if attempt_number is not None:
        snapshot["refresh_attempt_number"] = attempt_number

    queue_status = str(queue_result.get("status", "queued")).strip().casefold()
    if queue_status in {"failed", "dead_letter", "dead-letter"}:
        snapshot["refresh_status"] = "failed"
        snapshot["retryable"] = bool(queue_result.get("retryable", queue_status != "dead_letter"))
        if queue_status != "failed":
            snapshot["dead_lettered"] = True
        failure = queue_result.get("failure", queue_result.get("error"))
        snapshot["refresh_failure"] = _failure_payload(failure, queue_status)
    else:
        snapshot["refresh_status"] = "queued"
    return snapshot


def _snapshot_from_part(part: Mapping[str, Any]) -> dict[str, Any]:
    canonical_part_id = _first_text(part, "canonical_part_id", "part_id", "canonical_id")
    source_part_number = _first_text(
        part,
        "source_part_number",
        "part_number",
        "partNumber",
        "sourcePartNumber",
    )
    source_snapshot_id = _first_text(
        part,
        "source_snapshot_id",
        "price_snapshot_id",
        "snapshot_id",
    )
    priced_at_value = part.get("priced_at")
    if not canonical_part_id:
        raise ValueError("price record requires canonical_part_id")
    if not source_part_number:
        raise ValueError("price record requires source_part_number")
    if not source_snapshot_id:
        raise ValueError("price record requires source_snapshot_id")
    if priced_at_value is None:
        raise ValueError("price record requires priced_at")

    amount = _amount(part)
    currency = _first_text(part, "currency", "source_currency")
    if currency is None or len(currency) != 3 or not currency.isalpha():
        raise ValueError("price record requires a three-letter currency")

    result: dict[str, Any] = {
        "canonical_part_id": canonical_part_id,
        "source_part_number": source_part_number,
        "amount": amount,
        "currency": currency.upper(),
        "source_snapshot_id": source_snapshot_id,
        "_priced_at_datetime": _parse_timestamp(priced_at_value),
    }
    for output_key, input_keys in (
        ("name", ("name", "description", "part_description", "partDescription")),
        ("quantity", ("quantity",)),
        ("source", ("source", "provider")),
        ("source_uri", ("source_uri", "sourceUri")),
    ):
        value = next((part[key] for key in input_keys if part.get(key) is not None), None)
        if value is not None:
            result[output_key] = deepcopy(value)
    return result


def _amount(part: Mapping[str, Any]) -> float:
    value: Any = part.get("amount")
    if value is None:
        value = part.get("price")
    if isinstance(value, Mapping):
        value = value.get("amount", value.get("value"))
    if value is None and part.get("price_minor") is not None:
        value = Decimal(str(part["price_minor"])) / Decimal(100)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError("price record requires a numeric amount") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError("price amount must be a finite non-negative number")
    return float(amount)


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _utc_datetime(value, "priced_at")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("priced_at must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("priced_at must be an ISO-8601 timestamp") from error
    return _utc_datetime(parsed, "priced_at")


def _timestamp_text(original: Any, parsed: datetime) -> str:
    if isinstance(original, str) and original.strip():
        return original.strip()
    return parsed.isoformat().replace("+00:00", "Z")


def _utc_datetime(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware UTC timestamp")
    return value.astimezone(UTC)


def _refresh_idempotency_key(snapshot: Mapping[str, Any]) -> str:
    identity = json.dumps(
        {
            key: snapshot[key]
            for key in (
                "canonical_part_id",
                "source_part_number",
                "source_snapshot_id",
                "priced_at",
            )
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "price-refresh:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _retryable_refresh_error(error: Exception) -> bool:
    return isinstance(error, (TimeoutError, ConnectionError, OSError))


def _failure_payload(value: Any, status: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    message = str(value).strip() if value is not None else status
    return {"error_type": "RefreshFailure", "message": message or status}


def _first_text(value: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        item = value.get(key)
        if item is not None and str(item).strip():
            return str(item).strip()
    return None


def _positive_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


__all__ = [
    "PRICE_FRESHNESS_WINDOW",
    "price_freshness",
    "read_cached_price_or_queue_refresh",
]
