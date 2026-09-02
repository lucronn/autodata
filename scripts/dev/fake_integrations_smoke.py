"""Exercise deterministic source and payment adapters from the Compose stack."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))

from autodata_contracts.fakes import FakePaymentProvider, FakePrimarySource  # noqa: E402


def main() -> None:
    source = FakePrimarySource()
    snapshot = source.fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")

    provider = FakePaymentProvider(
        signing_secret=os.getenv("AUTODATA_FAKE_PAYMENT_SIGNING_SECRET", "local-fixture-signing-key")
    )
    session = provider.create_checkout_session("vehicle-core-fixture", "fixture-org")
    event = provider.record_payment_event(
        provider.verify_webhook(session["headers"], session["body"])
    )
    duplicate_event = provider.record_payment_event(
        provider.verify_webhook(session["headers"], session["body"])
    )
    entitlement = provider.create_entitlement(event)
    duplicate_entitlement = provider.create_entitlement(duplicate_event)
    if event != duplicate_event or entitlement != duplicate_entitlement:
        raise SystemExit("fake payment replay was not idempotent")

    print(
        json.dumps(
            {
                "source_snapshot_id": snapshot.source_snapshot_id,
                "source_sha256": snapshot.content_sha256,
                "source_takedown_status": snapshot.takedown_status,
                "payment_event_id": event.payment_event_id,
                "entitlement_id": entitlement.entitlement_id,
                "payment_event_count": len(provider.payment_events),
                "entitlement_count": len(provider.entitlements),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
