"""Exercise deterministic source and payment adapters from the Compose stack."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

from autodata_contracts.fakes import FakePaymentProvider, FakePrimarySource  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", "--api-url", dest="base_url", default=os.getenv("AUTODATA_API_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--signing-secret", default=os.getenv("AUTODATA_FAKE_PAYMENT_SIGNING_SECRET", "local-fixture-signing-key"))
    parser.add_argument("--org-id", default="fixture-org")
    parser.add_argument("--region", default="US")
    parser.add_argument("--source-version", default="fixture-v1")
    args = parser.parse_args(argv)

    source = FakePrimarySource()
    snapshot = source.fetch("Toyota", "Corolla", 2024, args.region, args.source_version)

    provider = FakePaymentProvider(signing_secret=args.signing_secret)
    session = provider.create_checkout_session("vehicle-core-fixture", args.org_id)
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
