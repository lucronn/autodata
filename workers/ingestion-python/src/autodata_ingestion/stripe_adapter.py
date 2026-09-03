"""Stripe implementation of the provider-neutral payment adapter.

The Stripe SDK module and client are injected so local tests do not need Stripe
credentials or a network connection. Production composition supplies the
official Stripe client and the webhook signing secret through a secret-manager
interface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class StripePaymentProvider:
    """Create hosted Stripe Checkout sessions and normalize signed webhooks."""

    def __init__(
        self,
        *,
        stripe_module: Any,
        client: Any,
        webhook_secret: str,
        success_url: str,
        cancel_url: str,
        price_ids: Mapping[str, str] | None = None,
    ) -> None:
        if not webhook_secret.strip():
            raise ValueError("Stripe webhook secret is required")
        if not success_url.strip() or not cancel_url.strip():
            raise ValueError("Stripe checkout return URLs are required")
        self._stripe = stripe_module
        self._client = client
        self._webhook_secret = webhook_secret
        self._success_url = success_url
        self._cancel_url = cancel_url
        self._price_ids = dict(price_ids or {})

    def create_checkout_session(
        self,
        product_id: str,
        purchaser_id: str,
        dataset_request_id: str | None = None,
    ) -> dict[str, str]:
        product_id = product_id.strip()
        purchaser_id = purchaser_id.strip()
        if not product_id or not purchaser_id:
            raise ValueError("product ID and purchaser ID are required")

        metadata = {
            "product_id": product_id,
            "purchaser_id": purchaser_id,
        }
        if dataset_request_id and dataset_request_id.strip():
            metadata["dataset_request_id"] = dataset_request_id.strip()

        session = self._client.checkout.sessions.create(
            mode="payment",
            line_items=[
                {
                    "price": self._price_ids.get(product_id, product_id),
                    "quantity": 1,
                }
            ],
            success_url=self._success_url,
            cancel_url=self._cancel_url,
            metadata=metadata,
        )
        session_id = str(session.get("id", "")).strip()
        checkout_url = str(session.get("url", "")).strip()
        if not session_id or not checkout_url:
            raise ValueError("Stripe Checkout response omitted session identity or URL")
        return {
            "provider_name": "stripe",
            "session_id": session_id,
            "checkout_url": checkout_url,
        }

    def verify_webhook(
        self,
        headers: Mapping[str, str] | str,
        body: str | bytes,
    ) -> dict[str, str]:
        signature = _stripe_signature(headers)
        if not signature:
            raise ValueError("Stripe-Signature header is required")
        try:
            event = self._stripe.Webhook.construct_event(
                body,
                signature,
                self._webhook_secret,
            )
        except Exception as exc:  # Stripe SDK raises provider-specific exceptions.
            raise ValueError("Stripe webhook signature verification failed") from exc

        if event.get("type") != "checkout.session.completed":
            raise ValueError(f"unsupported Stripe event type: {event.get('type', '')}")
        event_id = str(event.get("id", "")).strip()
        session = event.get("data", {}).get("object", {})
        metadata = session.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("Stripe Checkout metadata is missing")
        product_id = str(metadata.get("product_id", "")).strip()
        purchaser_id = str(metadata.get("purchaser_id", "")).strip()
        if not event_id or not product_id or not purchaser_id:
            raise ValueError("Stripe webhook is missing payment or purchaser identity")

        normalized = {
            "provider_name": "stripe",
            "provider_event_id": event_id,
            "event_type": "checkout.completed",
            "product_id": product_id,
            "purchaser_id": purchaser_id,
        }
        dataset_request_id = str(metadata.get("dataset_request_id", "")).strip()
        if dataset_request_id:
            normalized["dataset_request_id"] = dataset_request_id
        return normalized


def _stripe_signature(headers: Mapping[str, str] | str) -> str:
    if isinstance(headers, str):
        prefix, separator, value = headers.partition(":")
        if prefix.strip().lower() == "stripe-signature" and separator:
            return value.strip()
        return ""
    for key, value in headers.items():
        if key.lower() == "stripe-signature":
            return str(value).strip()
    return ""
