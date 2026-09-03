"""Durable JetStream delivery for viewable-to-deep-lane fanout."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from .fanout import ViewableEventError, deep_sections_from_event


VIEWABLE_SUBJECT = "dataset.viewable"
VIEWABLE_DEAD_LETTER_SUBJECT = "dataset.deep.schedule.dead_letter"
DEFAULT_STREAM = "AUTODATA"
DEFAULT_DURABLE = "autodata-viewable-fanout"


async def consume_once(
    handler: Callable[[dict[str, Any]], Any],
    *,
    connect: Callable[[str], Awaitable[Any]] | None = None,
    url: str | None = None,
    stream: str | None = None,
    durable: str | None = None,
    subject: str = VIEWABLE_SUBJECT,
    dead_letter_subject: str = VIEWABLE_DEAD_LETTER_SUBJECT,
    fetch_timeout: float = 1,
    max_deliveries: int = 3,
) -> dict[str, Any]:
    """Process at most one viewable event with at-least-once delivery."""

    if fetch_timeout <= 0:
        raise ValueError("JetStream fetch timeout must be positive")
    if max_deliveries < 1:
        raise ValueError("maximum deliveries must be positive")
    stream = stream or os.getenv("AUTODATA_NATS_STREAM", DEFAULT_STREAM)
    durable = durable or os.getenv("AUTODATA_VIEWABLE_CONSUMER_DURABLE", DEFAULT_DURABLE)
    url = url or os.getenv("AUTODATA_NATS_URL", "nats://nats:4222")
    connector = connect or _connect
    connection = await connector(url)
    try:
        jetstream = connection.jetstream()
        await ensure_stream(jetstream, stream)
        subscription = await jetstream.pull_subscribe(subject, durable=durable, stream=stream)
        try:
            messages = await subscription.fetch(1, timeout=fetch_timeout)
        except asyncio.TimeoutError:
            return {"status": "idle", "received": 0}
        if not messages:
            return {"status": "idle", "received": 0}

        message = messages[0]
        envelope: dict[str, Any]
        try:
            envelope = _decode_envelope(message.data)
            deep_sections_from_event(envelope)
            handled = handler(envelope)
            if inspect.isawaitable(handled):
                await handled
        except Exception as error:  # noqa: BLE001 - delivery boundary classifies handler failures
            delivery_count = _delivery_count(message)
            if isinstance(error, ViewableEventError) or delivery_count >= max_deliveries:
                await _dead_letter(
                    jetstream,
                    dead_letter_subject,
                    envelope if "envelope" in locals() else {"raw_event": "invalid"},
                    error,
                    delivery_count,
                )
                await message.ack()
                return {
                    "status": "dead_lettered",
                    "received": 1,
                    "delivery_count": delivery_count,
                }
            delay = min(2 ** (delivery_count - 1), 30)
            await message.nak(delay=delay)
            return {
                "status": "retrying",
                "received": 1,
                "delivery_count": delivery_count,
                "retry_delay_seconds": delay,
            }
        await message.ack()
        return {"status": "completed", "received": 1, "delivery_count": _delivery_count(message)}
    finally:
        await connection.close()


async def ensure_stream(jetstream: Any, stream: str = DEFAULT_STREAM) -> None:
    try:
        await jetstream.stream_info(stream)
    except Exception as error:  # noqa: BLE001 - server-specific missing-stream errors vary
        if "already in use" in str(error).lower():
            return
        await jetstream.add_stream(name=stream, subjects=["dataset.>"])


def _decode_envelope(data: bytes) -> dict[str, Any]:
    try:
        envelope = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ViewableEventError("viewable message is not valid JSON") from error
    if not isinstance(envelope, dict):
        raise ViewableEventError("viewable message envelope must be an object")
    return envelope


def _delivery_count(message: Any) -> int:
    metadata = getattr(message, "metadata", None)
    try:
        return max(1, int(getattr(metadata, "num_delivered", 1)))
    except (TypeError, ValueError):
        return 1


async def _dead_letter(
    jetstream: Any,
    subject: str,
    envelope: dict[str, Any],
    error: Exception,
    delivery_count: int,
) -> None:
    key = str(envelope.get("idempotency_key") or envelope.get("event_id") or "unknown")
    payload = {
        "dead_lettered_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "delivery_count": delivery_count,
        "error_type": type(error).__name__,
        "original_event": envelope,
    }
    await jetstream.publish(
        subject,
        json.dumps(payload, sort_keys=True).encode(),
        headers={"Nats-Msg-Id": f"viewable-dead-letter:{key}:{delivery_count}"},
    )


async def _connect(url: str) -> Any:
    import nats

    return await nats.connect(url)
