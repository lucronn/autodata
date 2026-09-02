"""Deterministic local implementations of the source and payment boundaries."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Any


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-fake:{value}"))


@dataclass(frozen=True)
class SourceSnapshot:
    source_snapshot_id: str
    source_uri: str
    source_version: str
    content: dict[str, Any]
    content_sha256: str
    object_key: str
    attribution: dict[str, Any]
    takedown_status: str


class FakePrimarySource:
    """Return repeatable source captures for local fast-lane tests."""

    def fetch(
        self, make: str, model: str, year: int, region: str, version: str
    ) -> SourceSnapshot:
        vehicle_key = f"{make.lower()}-{model.lower()}-{year}-{region.lower()}"
        source_uri = f"fake://source/{vehicle_key}"
        takedown = version.startswith("takedown-")
        content = {
            "vehicle": {
                "make": make,
                "model": model,
                "year": year,
                "region": region,
            },
            "source_version": version,
            "minimum_sections": ["vehicle_identity", "source_metadata", "specifications"],
        }
        serialized = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        return SourceSnapshot(
            source_snapshot_id=_stable_uuid(f"{source_uri}:{version}"),
            source_uri=source_uri,
            source_version=version,
            content=content,
            content_sha256=hashlib.sha256(serialized).hexdigest(),
            object_key=f"fake/{vehicle_key}/{version}.json",
            attribution={
                "adapter": "fake-primary-source",
                "source_uri": source_uri,
                "terms": "local-only",
                "takedown_fixture": takedown,
            },
            takedown_status="takedown" if takedown else "active",
        )


@dataclass(frozen=True)
class FakePaymentEvent:
    payment_event_id: str
    provider_event_id: str
    provider_name: str
    event_type: str
    product_id: str
    purchaser_id: str


@dataclass(frozen=True)
class FakeEntitlement:
    entitlement_id: str
    organization_id: str
    provider_event_id: str
    product_id: str
    status: str
    revoke_reason: str | None = None


class FakePaymentProvider:
    """Reference fake for signed webhooks and idempotent entitlement behavior."""

    def __init__(self, signing_secret: str):
        self._signing_secret = signing_secret.encode()
        self.payment_events: dict[str, FakePaymentEvent] = {}
        self.entitlements: dict[str, FakeEntitlement] = {}

    def create_checkout_session(self, product_id: str, purchaser_id: str) -> dict[str, str]:
        provider_event_id = _stable_uuid(f"payment:{product_id}:{purchaser_id}")
        payload = {
            "provider_event_id": provider_event_id,
            "event_type": "checkout.completed",
            "product_id": product_id,
            "purchaser_id": purchaser_id,
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(self._signing_secret, body.encode(), hashlib.sha256).hexdigest()
        return {
            "session_id": _stable_uuid(f"session:{product_id}:{purchaser_id}"),
            "body": body,
            "headers": f"X-Fake-Signature: {signature}",
        }

    def verify_webhook(self, headers: str, body: str) -> dict[str, Any]:
        prefix, separator, signature = headers.partition(": ")
        expected = hmac.new(self._signing_secret, body.encode(), hashlib.sha256).hexdigest()
        if prefix != "X-Fake-Signature" or not separator or not hmac.compare_digest(signature, expected):
            raise ValueError("invalid fake payment webhook signature")
        return json.loads(body)

    def record_payment_event(self, event: dict[str, Any]) -> FakePaymentEvent:
        provider_event_id = event["provider_event_id"]
        existing = self.payment_events.get(provider_event_id)
        if existing:
            return existing
        payment_event = FakePaymentEvent(
            payment_event_id=_stable_uuid(f"payment-event:{provider_event_id}"),
            provider_event_id=provider_event_id,
            provider_name="fake",
            event_type=event["event_type"],
            product_id=event["product_id"],
            purchaser_id=event["purchaser_id"],
        )
        self.payment_events[provider_event_id] = payment_event
        return payment_event

    def create_entitlement(self, payment_event: FakePaymentEvent) -> FakeEntitlement:
        existing = self.entitlements.get(payment_event.provider_event_id)
        if existing:
            return existing
        entitlement = FakeEntitlement(
            entitlement_id=_stable_uuid(f"entitlement:{payment_event.provider_event_id}"),
            organization_id=payment_event.purchaser_id,
            provider_event_id=payment_event.provider_event_id,
            product_id=payment_event.product_id,
            status="active",
        )
        self.entitlements[payment_event.provider_event_id] = entitlement
        return entitlement

    def revoke_entitlement(self, entitlement_id: str, reason: str) -> FakeEntitlement:
        for provider_event_id, entitlement in self.entitlements.items():
            if entitlement.entitlement_id == entitlement_id:
                revoked = FakeEntitlement(
                    entitlement_id=entitlement.entitlement_id,
                    organization_id=entitlement.organization_id,
                    provider_event_id=entitlement.provider_event_id,
                    product_id=entitlement.product_id,
                    status="revoked",
                    revoke_reason=reason,
                )
                self.entitlements[provider_event_id] = revoked
                return revoked
        raise KeyError(f"unknown entitlement: {entitlement_id}")
