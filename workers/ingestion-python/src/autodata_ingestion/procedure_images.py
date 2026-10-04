"""Fetch provider procedure figures into AutoData object storage."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import urllib.request
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request

from .object_storage import ensure_versioned_bucket

PROVIDER_IMAGE_HOST_MARKERS = (
    "autoapitwo.vercel.app",
    "alldata.com",
    "autodbone-curtt.vercel.app",
)
_ASSET_REFERENCE_PATH = re.compile(
    r"^/v1/assets/reference/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"
)
_MAX_SOURCE_IMAGE_BYTES = 8 * 1024 * 1024


class _RejectRedirect(HTTPRedirectHandler):
    """Signed source references must not forward credentials to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def localize_procedure_images(
    article: Mapping[str, Any],
    *,
    vehicle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Download figure URLs into MinIO and rewrite image records to local refs.

    Provider URLs are removed from served image records. Originals remain in
    ``source_original`` when the caller stashes them before localization.
    """

    out = dict(article)
    vehicle = vehicle or {}
    provider_id = str(vehicle.get("autoapitwo_vehicle_id") or "").strip()
    images = _collect_image_records(out)
    if not images:
        return out

    unique_urls = list(
        dict.fromkeys(
            str(image.get("url") or "").strip()
            for image in images
            if str(image.get("url") or "").strip()
            and not str(image.get("storage_key") or "").strip()
            and not str(image.get("url") or "").startswith("data:image/")
        )
    )
    fetched = _fetch_urls(unique_urls, provider_id=provider_id) if unique_urls else {}
    stored: dict[str, dict[str, Any]] = {}
    for url, payload in fetched.items():
        if not payload:
            continue
        try:
            stored[url] = _store_image_bytes(url, payload)
        except Exception:  # noqa: BLE001 - one failed figure must not abort ingestion
            continue

    def rewrite_image(image: Mapping[str, Any]) -> dict[str, Any]:
        record = dict(image)
        record.pop("source_url", None)
        url = str(record.get("url") or "").strip()
        if url and not str(record.get("image_id") or "").strip():
            # article_document derives image-block identities from the exact
            # source URL when the provider supplies no ID. Reuse that identity
            # on the materialized article image so both records join reliably.
            record["image_id"] = sha256(url.encode()).hexdigest()
        if str(record.get("storage_key") or "").strip():
            record.pop("url", None)
            record.pop("fetch_failed", None)
            return record
        local = stored.get(url)
        if local is None and url.startswith("data:image/"):
            return record
        if local is None:
            record.pop("url", None)
            record["fetch_failed"] = True
            return record
        image_id = record.get("image_id")
        record.update(local)
        if image_id:
            record["image_id"] = image_id
        # The object-store key is authoritative. The API mints the opaque
        # same-origin URL at projection time, so ingestion never persists a
        # provider-bearing or source-bearing public URL.
        record.pop("url", None)
        record.pop("fetch_failed", None)
        return record

    if isinstance(out.get("images"), list):
        out["images"] = [
            rewrite_image(image) for image in out["images"] if isinstance(image, Mapping)
        ]
    steps = out.get("steps")
    if isinstance(steps, list):
        rewritten_steps: list[Any] = []
        for step in steps:
            if not isinstance(step, Mapping):
                rewritten_steps.append(step)
                continue
            step_out = dict(step)
            step_images = step_out.get("images")
            if isinstance(step_images, list):
                step_out["images"] = [
                    rewrite_image(image)
                    for image in step_images
                    if isinstance(image, Mapping)
                ]
            rewritten_steps.append(step_out)
        out["steps"] = rewritten_steps
    _rewrite_document_images(out, _collect_image_records(out))
    return out


def resolve_local_image_url(image: Mapping[str, Any]) -> str:
    """Return a displayable URL for a localized image record."""

    url = str(image.get("url") or "").strip()
    if url.startswith("data:image/"):
        return url
    storage_key = str(image.get("storage_key") or "").strip()
    if storage_key and not url.startswith("data:image/"):
        payload = _read_storage_bytes(storage_key)
        if payload:
            media_type = str(image.get("media_type") or "image/png")
            encoded = base64.b64encode(payload).decode("ascii")
            return f"data:{media_type};base64,{encoded}"
    return ""


def hydrate_article_image_urls(
    article: Mapping[str, Any],
    *,
    embed_data_uri: bool = False,
) -> dict[str, Any]:
    """Attach display URLs for guide/markdown without provider CDN hosts.

    By default, chat answers keep ``artifact://{image_id}`` refs plus
    ``storage_key`` so JSON stays small. Pass ``embed_data_uri=True`` only for
    offline PDF/HTML preparation that already loads image bytes separately.
    """

    out = dict(article)

    def hydrate(image: Mapping[str, Any]) -> dict[str, Any]:
        record = dict(image)
        record.pop("source_url", None)
        if not str(record.get("url") or "").startswith("data:image/"):
            record.pop("url", None)
        storage_key = str(record.get("storage_key") or "").strip()
        image_id = str(record.get("image_id") or "").strip()
        if embed_data_uri and storage_key:
            display = resolve_local_image_url(record)
            if display:
                record["url"] = display
                return record
        if storage_key and image_id:
            record["url"] = f"artifact://{image_id}"
        elif _is_provider_host(str(record.get("url") or "")):
            record.pop("url", None)
        return record

    if isinstance(out.get("images"), list):
        out["images"] = [
            hydrate(image) for image in out["images"] if isinstance(image, Mapping)
        ]
    steps = out.get("steps")
    if isinstance(steps, list):
        hydrated_steps: list[Any] = []
        for step in steps:
            if not isinstance(step, Mapping):
                hydrated_steps.append(step)
                continue
            step_out = dict(step)
            if isinstance(step_out.get("images"), list):
                step_out["images"] = [
                    hydrate(image)
                    for image in step_out["images"]
                    if isinstance(image, Mapping)
                ]
            hydrated_steps.append(step_out)
        out["steps"] = hydrated_steps
    return out


def _collect_image_records(article: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(article.get("images"), list):
        records.extend(
            dict(image) for image in article["images"] if isinstance(image, Mapping)
        )
    steps = article.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            images = step.get("images")
            if isinstance(images, list):
                records.extend(dict(image) for image in images if isinstance(image, Mapping))
    return records


def _rewrite_document_images(article: dict[str, Any], original_images: list[dict[str, Any]]) -> None:
    """Copy localized asset identities into ordered document image blocks."""

    document = article.get("normalized_document")
    if not isinstance(document, Mapping):
        return
    by_ref: dict[str, dict[str, Any]] = {}
    for image in original_images:
        for key in (image.get("image_id"), image.get("asset_id"), image.get("url"), image.get("storage_key")):
            if key:
                by_ref[str(key)] = image
        source_url = str(image.get("url") or "").strip()
        if source_url:
            by_ref.setdefault(sha256(source_url.encode()).hexdigest(), image)

    def rewrite(block: Any) -> None:
        if not isinstance(block, dict):
            return
        if block.get("type") == "image":
            reference = str(block.get("image_id") or block.get("asset_id") or "")
            image = by_ref.get(reference)
            if image is None:
                block["status"] = "unavailable"
                block["unavailable_reason"] = "image was not materialized during ingest"
            elif image.get("storage_key") or str(image.get("url") or "").startswith("data:image/"):
                block["asset_id"] = image.get("storage_key") or image.get("image_id") or reference
                block["image_id"] = image.get("image_id") or block.get("image_id") or reference
                block["status"] = "available"
                block.pop("unavailable_reason", None)
            else:
                block["status"] = "unavailable"
                block["unavailable_reason"] = "image could not be materialized"
            return
        if block.get("type") == "table":
            for row in block.get("rows") or []:
                cells = row if isinstance(row, list) else row.get("cells", []) if isinstance(row, Mapping) else []
                for cell in cells:
                    if isinstance(cell, Mapping):
                        for image in cell.get("images") or []:
                            if isinstance(image, dict):
                                reference = str(image.get("image_id") or image.get("asset_id") or "")
                                localized = by_ref.get(reference)
                                if localized and localized.get("storage_key"):
                                    image["asset_id"] = localized["storage_key"]
                                    image["image_id"] = localized.get("image_id") or reference
                                    image["status"] = "available"
                                else:
                                    image["status"] = "unavailable"
                                    image["unavailable_reason"] = "image could not be materialized"
        for child in block.get("blocks") or []:
            rewrite(child)

    for block in document.get("blocks") or []:
        rewrite(block)


def _fetch_urls(urls: list[str], *, provider_id: str) -> dict[str, bytes]:
    from .autoapitwo_connector import AutoAPITwoConnector

    connector_base_url = os.getenv(
        "AUTODATA_AUTOAPITWO_BASE_URL", "https://autoapitwo.vercel.app"
    )

    def fetch_one(url: str) -> tuple[str, bytes]:
        try:
            if _is_autodbone_asset_reference(url):
                return url, _fetch_autodbone_asset(url)
            connector = AutoAPITwoConnector(connector_base_url)
            payload = connector.read(url, car_id=provider_id or None, binary=True)
            return url, bytes(payload or b"")
        except Exception:  # noqa: BLE001 - leave image marked failed
            return url, b""

    results: dict[str, bytes] = {}
    if not urls:
        return results
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as pool:
        for url, payload in pool.map(fetch_one, urls):
            if payload:
                results[url] = payload
    return results


def _is_autodbone_asset_reference(url: str) -> bool:
    configured = os.getenv(
        "AUTODATA_AUTOAPI_BASE_URL", "https://autodbone-curtt.vercel.app"
    ).strip()
    try:
        source = urlsplit(configured)
        candidate = urlsplit(url)
        return (
            source.scheme == "https"
            and bool(source.netloc)
            and not source.username
            and not source.password
            and candidate.scheme == source.scheme
            and candidate.netloc.casefold() == source.netloc.casefold()
            and not candidate.username
            and not candidate.password
            and not candidate.query
            and not candidate.fragment
            and bool(_ASSET_REFERENCE_PATH.fullmatch(candidate.path))
        )
    except ValueError:
        return False


def _fetch_autodbone_asset(url: str) -> bytes:
    """Fetch a signed AutoDBone image from its configured origin only."""
    if not _is_autodbone_asset_reference(url):
        return b""
    headers: dict[str, str] = {"Accept": "image/*"}
    raw_headers = os.getenv("AUTODATA_SOURCE_REQUEST_HEADERS_JSON", "").strip()
    if raw_headers:
        try:
            decoded = json.loads(raw_headers)
        except (TypeError, ValueError):
            return b""
        if not isinstance(decoded, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key.strip()
            or any(char in key + value for char in "\r\n")
            for key, value in decoded.items()
        ):
            return b""
        headers.update(decoded)
    limit = int(
        os.getenv("AUTODATA_AUTOAPI_IMAGE_MAX_BYTES", str(_MAX_SOURCE_IMAGE_BYTES))
    )
    if limit <= 0 or limit > _MAX_SOURCE_IMAGE_BYTES:
        limit = _MAX_SOURCE_IMAGE_BYTES
    request = Request(url, headers=headers)
    opener = urllib.request.build_opener(_RejectRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            if response.geturl() != url:
                return b""
            content_type = (
                str(response.headers.get("Content-Type", ""))
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if not content_type.startswith("image/"):
                return b""
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > limit:
                return b""
            payload = response.read(limit + 1)
            return payload if 0 < len(payload) <= limit else b""
    except (HTTPError, OSError, ValueError, TimeoutError):
        return b""


def _store_image_bytes(source_url: str, payload: bytes) -> dict[str, Any]:
    digest = sha256(payload).hexdigest()
    media_type = _guess_media_type(source_url, payload)
    storage_key = f"procedure-images/{digest}"
    _put_object(storage_key, payload, media_type)
    return {
        "image_id": digest,
        "storage_key": storage_key,
        "content_sha256": digest,
        "media_type": media_type,
    }


def _put_object(storage_key: str, payload: bytes, media_type: str) -> None:
    from minio import Minio
    from minio.error import S3Error

    client = Minio(
        os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
        access_key=os.environ["AUTODATA_S3_ACCESS_KEY"],
        secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
        secure=False,
    )
    bucket = os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")
    ensure_versioned_bucket(client, bucket)
    try:
        client.stat_object(bucket, storage_key)
        return
    except S3Error as exc:
        if exc.code not in {"NoSuchKey", "NoSuchObject"}:
            raise
    client.put_object(
        bucket,
        storage_key,
        BytesIO(payload),
        len(payload),
        content_type=media_type,
    )


def _read_storage_bytes(storage_key: str) -> bytes:
    try:
        from minio import Minio
    except ImportError:
        return b""
    try:
        client = Minio(
            os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
            access_key=os.environ["AUTODATA_S3_ACCESS_KEY"],
            secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
            secure=False,
        )
        bucket = os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")
        response = client.get_object(bucket, storage_key)
        try:
            return bytes(response.read())
        finally:
            response.close()
            response.release_conn()
    except Exception:  # noqa: BLE001
        return b""


def _guess_media_type(url: str, payload: bytes) -> str:
    if payload.startswith(b"\x89PNG"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    path = urlsplit(url).path
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "image/png"


def _is_provider_host(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold()
    except ValueError:
        return False
    return any(
        host == marker or host.endswith("." + marker)
        for marker in PROVIDER_IMAGE_HOST_MARKERS
    )


__all__ = [
    "PROVIDER_IMAGE_HOST_MARKERS",
    "hydrate_article_image_urls",
    "localize_procedure_images",
    "resolve_local_image_url",
]
