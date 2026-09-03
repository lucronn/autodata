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
