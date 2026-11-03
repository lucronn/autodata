"""Provider-neutral contract for hosted checkout and signed webhooks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class PaymentProvider(Protocol):
    """External payment adapter boundary used by the reconciliation service."""

    def create_checkout_session(
        self,
        product_id: str,
        purchaser_id: str,
        dataset_request_id: str | None = None,
    ) -> Mapping[str, str]: ...

    def verify_webhook(
        self,
        headers: Mapping[str, str] | str,
        body: str | bytes,
    ) -> Mapping[str, Any]: ...


class WorkshopPaymentProvider(Protocol):
    """Server-owned order authority; legacy checkout remains a separate seam."""
    def verify_merchant(self, expected_account: str) -> None: ...
    def verify_price(self, price_id: str, livemode: bool) -> None: ...
    def create_order_checkout(self, order: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def retrieve_order_session(self, session_id: str) -> Mapping[str, Any]: ...
    def expire_order_session(self, session_id: str) -> Mapping[str, Any]: ...
    def retrieve_payment_intent(self, intent_id: str) -> Mapping[str, Any]: ...
    def cancel_payment_intent(self, intent_id: str) -> Mapping[str, Any]: ...
    def verify_commerce_webhook(self, headers: Mapping[str,str], body: bytes) -> Mapping[str,Any]: ...
