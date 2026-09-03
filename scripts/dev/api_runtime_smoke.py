#!/usr/bin/env python3
"""Exercise the PostgreSQL-backed Go API through the live Compose network."""

from __future__ import annotations

import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = os.getenv("AUTODATA_API_URL", "http://127.0.0.1:8080").rstrip("/")
ORGANIZATION_ID = os.getenv(
    "AUTODATA_API_ORGANIZATION_ID",
    "41000000-0000-0000-0000-000000000001",
)
OTHER_ORGANIZATION_ID = "42000000-0000-0000-0000-000000000001"
PRODUCT_ID = os.getenv(
    "AUTODATA_API_PRODUCT_ID",
    str(uuid.uuid5(uuid.NAMESPACE_URL, "autodata-ingest:product:vehicle-core-fixture:1")),
)
VEHICLE_KEY = "toyota-corolla-2024-us"


def call_api(method: str, path: str, *, organization_id: str, body: dict | None = None, idempotency_key: str | None = None) -> tuple[int, dict]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer local:{organization_id}:dataset_viewer",
    }
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    request = Request(f"{API_URL}{path}", data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())
    except URLError as error:
        raise RuntimeError(f"API request failed: {error.reason}") from error


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    request_body = {
        "product_id": PRODUCT_ID,
        "vehicle_key": VEHICLE_KEY,
        "region": "US",
    }
    idempotency_key = "api-runtime-smoke-v1"
    first_status, first = call_api(
        "POST",
        "/dataset-requests",
        organization_id=ORGANIZATION_ID,
        body=request_body,
        idempotency_key=idempotency_key,
    )
    require(first_status == 202, f"first request status = {first_status}, want 202")
    request_id = first.get("dataset_request_id")
    require(isinstance(request_id, str) and request_id, "first response omitted dataset_request_id")
    require(first.get("status") == "fast_lane_processing", "first request is not processing")

    replay_status, replay = call_api(
        "POST",
        "/dataset-requests",
        organization_id=ORGANIZATION_ID,
        body=request_body,
        idempotency_key=idempotency_key,
    )
    require(replay_status == 200, f"replay status = {replay_status}, want 200")
    require(replay.get("dataset_request_id") == request_id, "replay created a different request")

    read_status, read = call_api(
        "GET",
        f"/dataset-requests/{request_id}",
        organization_id=ORGANIZATION_ID,
    )
    require(read_status == 200, f"request read status = {read_status}, want 200")
    sections = read.get("sections")
    require(isinstance(sections, list) and sections, "durable request read omitted sections")
    require(all(section.get("status") == "pending" for section in sections), "unexpected pre-projection section state")

    denied_status, denied = call_api(
        "GET",
        f"/dataset-requests/{request_id}",
        organization_id=OTHER_ORGANIZATION_ID,
    )
    require(denied_status == 403, f"cross-organization read status = {denied_status}, want 403")
    require(denied.get("error", {}).get("code") == "ENTITLEMENT_REQUIRED", "wrong cross-organization error")

    invalid_status, invalid = call_api(
        "POST",
        "/dataset-requests",
        organization_id=ORGANIZATION_ID,
        body={**request_body, "product_id": "not-a-uuid"},
        idempotency_key="invalid-product",
    )
    require(invalid_status == 422, f"invalid product status = {invalid_status}, want 422")
    require(invalid.get("error", {}).get("code") == "INVALID_REQUEST", "wrong invalid product error")

    print(json.dumps({
        "status": "ready",
        "dataset_request_id": request_id,
        "first_status": first_status,
        "replay_status": replay_status,
        "read_status": read_status,
        "section_count": len(sections),
        "cross_organization_status": denied_status,
        "invalid_product_status": invalid_status,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
