"""Fetch provider procedure figures into AutoData object storage."""

from __future__ import annotations

import base64
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from typing import Any, Mapping
from urllib.parse import urlsplit

from .object_storage import ensure_versioned_bucket


PROVIDER_IMAGE_HOST_MARKERS = (
    "banktwo.cars.tk",
    "alldata.com",
)


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
    del vehicle
    images = _collect_image_records(out)
    if not images:
        return out

    unique_asset_refs = list(
        dict.fromkeys(
            str(image.get("asset_resource_ref") or "").strip()
            for image in images
            if str(image.get("asset_resource_ref") or "").strip()
            and not str(image.get("storage_key") or "").strip()
        )
    )
    fetched = _fetch_asset_resources(unique_asset_refs) if unique_asset_refs else {}
    stored: dict[str, dict[str, Any]] = {}
    for resource_ref, resource in fetched.items():
        payload = resource["payload"]
        if not payload:
            continue
        try:
            stored[resource_ref] = _store_image_bytes(
                resource_ref,
                payload,
                media_type=resource["media_type"],
                source_metadata=resource["metadata"],
            )
        except Exception:  # noqa: BLE001 - one failed figure must not abort ingestion
            continue

    def rewrite_image(image: Mapping[str, Any]) -> dict[str, Any]:
        record = dict(image)
        record.pop("source_url", None)
        url = str(record.get("url") or "").strip()
        if url.startswith("data:image/"):
            localized = _localize_data_uri_image(record, url)
            if localized is None:
                record["fetch_failed"] = True
                return record
            return localized
        record.pop("url", None)
        if str(record.get("storage_key") or "").strip():
            record["url"] = f"artifact://{record.get('image_id')}" if record.get("image_id") else ""
            record.pop("fetch_failed", None)
            return record
        resource_ref = str(record.get("asset_resource_ref") or "").strip()
        local = stored.get(resource_ref)
        if local is None:
            record["fetch_failed"] = True
            return record
        image_id = record.get("image_id")
        record.update(local)
        if image_id:
            record["image_id"] = image_id
        record["url"] = f"artifact://{record.get('image_id')}" if record.get("image_id") else ""
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
        for key in (
            image.get("image_id"),
            image.get("id"),
            image.get("storage_key"),
            image.get("artifact_key"),
            image.get("asset_id"),
            image.get("content_sha256"),
            image.get("url"),
            image.get("src"),
            image.get("href"),
            image.get("asset_resource_ref"),
        ):
            if key and str(key).strip():
                by_ref[str(key).strip()] = image

    def _lookup(obj: Mapping[str, Any]) -> dict[str, Any] | None:
        for key in (
            obj.get("image_id"),
            obj.get("id"),
            obj.get("asset_id"),
            obj.get("storage_key"),
            obj.get("artifact_key"),
            obj.get("asset_resource_ref"),
            obj.get("url"),
            obj.get("content_sha256"),
        ):
            if key and str(key).strip() in by_ref:
                return by_ref[str(key).strip()]
        return None

    def rewrite(block: Any) -> None:
        if not isinstance(block, dict):
            return
        bkind = str(block.get("type") or block.get("kind") or "").casefold()
        if bkind == "image":
            image = _lookup(block)
            reference = str(block.get("image_id") or block.get("asset_id") or "")
            if image is None:
                if block.get("storage_key") or str(block.get("url") or "").startswith("data:image/"):
                    block["status"] = "available"
                    block.pop("unavailable_reason", None)
                else:
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
        if bkind in {"table", "grid"}:
            for row in block.get("rows") or []:
                cells = row if isinstance(row, list) else row.get("cells", []) if isinstance(row, Mapping) else []
                for cell in cells:
                    if isinstance(cell, Mapping):
                        for image in cell.get("images") or []:
                            if isinstance(image, dict):
                                localized = _lookup(image)
                                reference = str(image.get("image_id") or image.get("asset_id") or "")
                                if localized and (localized.get("storage_key") or str(localized.get("url") or "").startswith("data:image/")):
                                    image["asset_id"] = localized.get("storage_key") or localized.get("image_id") or reference
                                    image["image_id"] = localized.get("image_id") or image.get("image_id") or reference
                                    image["status"] = "available"
                                    image.pop("unavailable_reason", None)
                                elif image.get("storage_key") or str(image.get("url") or "").startswith("data:image/"):
                                    image["status"] = "available"
                                    image.pop("unavailable_reason", None)
                                else:
                                    image["status"] = "unavailable"
                                    image["unavailable_reason"] = "image could not be materialized"
                        for child in cell.get("blocks") or []:
                            rewrite(child)
        for child in block.get("blocks") or []:
            rewrite(child)

    for block in document.get("blocks") or []:
        rewrite(block)


def _fetch_asset_resources(resource_refs: list[str]) -> dict[str, dict[str, Any]]:
    def fetch_one(resource_ref: str) -> tuple[str, dict[str, Any] | None]:
        try:
            return resource_ref, _read_asset_resource(resource_ref)
        except Exception:  # noqa: BLE001 - leave image marked failed
            return resource_ref, None

    results: dict[str, dict[str, Any]] = {}
    if not resource_refs:
        return results
    with ThreadPoolExecutor(max_workers=min(4, len(resource_refs))) as pool:
        for resource_ref, value in pool.map(fetch_one, resource_refs):
            if value and value["payload"]:
                results[resource_ref] = value
    return results


def _read_asset_resource(resource_ref: str) -> dict[str, Any]:
    from .source_connector_client import source_connector_registry

    connector = source_connector_registry(include_defaults=True)["banktwo"]
    envelope = connector.read_resource(resource_ref)
    resource = envelope.to_source_resource()
    if resource.metadata.get("kind") not in {"asset", "binary"} or not resource.media_type.startswith("image/"):
        raise ValueError("source resource is not an image asset")
    return {
        "payload": resource.payload,
        "media_type": resource.media_type,
        "metadata": {
            **dict(resource.metadata),
            "source_revision": resource.source_version,
            "source_uri": resource.locator,
        },
    }


def _localize_data_uri_image(record: Mapping[str, Any], url: str) -> dict[str, Any] | None:
    """Persist an inline data-URI figure into procedure image object storage."""

    try:
        header, encoded = url.split(",", 1)
    except ValueError:
        return None
    if ";base64" not in header.casefold():
        return None
    media_type = header[5:].split(";", 1)[0].strip() or "image/png"
    if not media_type.startswith("image/"):
        return None
    try:
        payload = base64.b64decode(encoded, validate=False)
    except Exception:
        return None
    if not payload:
        return None
    digest = sha256(payload).hexdigest()
    storage_key = f"procedure-images/{digest}"
    try:
        _put_object(storage_key, payload, media_type)
    except Exception:
        return None
    image_id = str(record.get("image_id") or digest).strip() or digest
    localized = dict(record)
    localized.update(
        {
            "image_id": image_id,
            "storage_key": storage_key,
            "content_sha256": digest,
            "media_type": media_type,
            "url": f"artifact://{image_id}",
        }
    )
    localized.pop("fetch_failed", None)
    return localized


def _store_image_bytes(
    source_ref: str,
    payload: bytes,
    *,
    media_type: str,
    source_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    digest = sha256(payload).hexdigest()
    declared_digest = str(source_metadata.get("source_sha256") or "")
    if digest != declared_digest:
        raise ValueError("source asset hash did not match its envelope")
    storage_key = f"procedure-images/{digest}"
    _put_object(storage_key, payload, media_type)
    return {
        "image_id": digest,
        "storage_key": storage_key,
        "content_sha256": digest,
        "media_type": media_type,
        "source_sha256": declared_digest,
        "source_asset_ref": source_ref,
        "source_request_id": source_metadata.get("request_id"),
        "source_revision": source_metadata.get("source_revision"),
        "source_uri": source_metadata.get("source_uri"),
    }


def _put_object(storage_key: str, payload: bytes, media_type: str) -> None:
    from minio import Minio
    from minio.error import S3Error
    from autodata_ingestion.bundle_persistence import _resolve_s3_endpoint

    client = Minio(
        _resolve_s3_endpoint(),
        access_key=os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin"),
        secret_key=os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password"),
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
        from autodata_ingestion.bundle_persistence import _resolve_s3_endpoint
    except ImportError:
        return b""
    try:
        client = Minio(
            _resolve_s3_endpoint(),
            access_key=os.getenv("AUTODATA_S3_ACCESS_KEY", "localadmin"),
            secret_key=os.getenv("AUTODATA_S3_SECRET_KEY", "local-dev-password"),
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
    host = urlsplit(url).netloc.casefold()
    return any(marker in host for marker in PROVIDER_IMAGE_HOST_MARKERS)


__all__ = [
    "PROVIDER_IMAGE_HOST_MARKERS",
    "hydrate_article_image_urls",
    "localize_procedure_images",
    "resolve_local_image_url",
]
