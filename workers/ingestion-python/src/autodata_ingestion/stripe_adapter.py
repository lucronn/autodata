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

        session = _stripe_dict(self._client.v1.checkout.sessions.create(dict(
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
        )))
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
            event = _stripe_dict(self._stripe.Webhook.construct_event(
                body,
                signature,
                self._webhook_secret,
                tolerance=300,
            ))
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


    def verify_merchant(self, expected_account: str) -> None:
        account = _stripe_dict(self._client.v1.accounts.retrieve_current())
        if account.get('id') != expected_account:
            raise ValueError('Stripe merchant configuration mismatch')

    def verify_price(self, price_id: str, livemode: bool) -> None:
        price = _stripe_dict(self._client.v1.prices.retrieve(price_id))
        if (price.get('id') != price_id or price.get('active') is not True or price.get('type') != 'one_time'
            or price.get('currency') != 'usd' or type(price.get('unit_amount')) is not int or price['unit_amount'] != 2000
            or type(price.get('livemode')) is not bool or price['livemode'] != livemode):
            raise ValueError('Stripe price configuration mismatch')

    def create_order_checkout(self, order: Mapping[str, Any]) -> dict[str, Any]:
        """Only server-stored order parameters enter the official SDK call."""
        first = order['first_create_attempt_at']
        stamp = int(first.timestamp()) if hasattr(first, 'timestamp') else int(first)
        metadata = {'order_id': str(order['order_id'])}
        return _stripe_dict(self._client.v1.checkout.sessions.create({
            'mode': 'payment', 'payment_method_types': ['card'],
            'line_items': [{'price': order['expected_price_id'], 'quantity': 1}],
            'success_url': self._success_url + '?order=' + str(order['order_id']),
            'cancel_url': self._cancel_url + '?order=' + str(order['order_id']),
            'expires_at': stamp + 3600, 'metadata': metadata,
            'payment_intent_data': {'capture_method': 'automatic', 'metadata': metadata},
        }, options={'idempotency_key': order['provider_idempotency_key']}))

    def retrieve_order_session(self, session_id: str) -> dict[str, Any]:
        return _stripe_dict(self._client.v1.checkout.sessions.retrieve(session_id,
            params={'expand': ['line_items.data.price', 'payment_intent']}))

    def expire_order_session(self, session_id: str) -> dict[str, Any]:
        return _stripe_dict(self._client.v1.checkout.sessions.expire(session_id))

    def retrieve_payment_intent(self, intent_id: str) -> dict[str, Any]:
        return _stripe_dict(self._client.v1.payment_intents.retrieve(intent_id))

    def cancel_payment_intent(self, intent_id: str) -> dict[str, Any]:
        return _stripe_dict(self._client.v1.payment_intents.cancel(intent_id))

    def verify_commerce_webhook(self, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        signature = _stripe_signature(headers)
        if not signature:
            raise ValueError('Stripe signature is required')
        try:
            event = _stripe_dict(self._stripe.Webhook.construct_event(body, signature, self._webhook_secret, tolerance=300))
        except Exception:
            raise ValueError('Stripe signature verification failed') from None
        event_id, event_type = event.get('id'), event.get('type')
        if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
            raise ValueError('Stripe event identity is missing')
        if event_type not in ('checkout.session.completed', 'checkout.session.expired',
                              'payment_intent.succeeded', 'charge.refunded', 'charge.dispute.closed'):
            return {'provider_name': 'stripe', 'provider_event_id': event_id, 'event_type': 'ignored'}
        obj = event.get('data', {}).get('object', {})
        if not isinstance(obj, Mapping) or type(event.get('livemode')) is not bool or type(event.get('created')) is not int:
            raise ValueError('Stripe event shape is invalid')
        metadata = obj.get('metadata', {})
        intent = obj.get('payment_intent')
        if isinstance(intent, Mapping):
            intent = intent.get('id')
        # Only immutable signed facts belong to the replay payload. Expanded
        # retrieval observations are never merged into this object.
        result = {'provider_name': 'stripe', 'provider_event_id': event_id,
                  'event_type': event_type, 'kind': 'workshop',
                  'occurred_at': event['created'], 'livemode': event['livemode'],
                  'order_id': metadata.get('order_id') if isinstance(metadata, Mapping) else None,
                  'object_id': obj.get('id'),
                  'checkout_session_id': obj.get('id') if event_type.startswith('checkout.session.') else None,
                  'payment_intent_id': obj.get('id') if event_type.startswith('payment_intent.') else intent}
        for key in ('amount', 'amount_total', 'amount_refunded', 'currency', 'refunded', 'status', 'payment_status'):
            value = obj.get(key)
            if isinstance(value, (str, int, bool)) or value is None:
                result[key] = value
        return result


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


def _stripe_dict(value: Any) -> dict[str, Any]:
    # Stripe16 resources are no longer dict subclasses; to_dict recursively
    # converts nested StripeObjects. Explicit injected mappings remain supported.
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError('Stripe response shape is invalid')
