"""Bounded provider-bound capture; immutable public projection from actual bytes."""

from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import time
import base64
from uuid import NAMESPACE_URL, uuid5
from .article_lifecycle_types import (
    CapturedSource,
    ResourceRef,
    article_id,
    digest_json,
)
from .source_adapters import adapt_bound_article
from .source_connector_client import SourceConnectorError
from .article_document import build_ordered_document


def snapshot_id(digest):
    return uuid5(NAMESPACE_URL, "autodata:source-blob:v1:" + digest)


def upload_resource(envelope, opaque_ref, role, object_store):
    """Object store implements put_object(key, bytes, media_type); success is required."""
    resource = envelope.to_source_resource()
    digest = resource.content_sha256
    key = "sources/" + digest[:16] + "/" + digest
    object_store.put_object(key, resource.payload, resource.media_type)
    return {
        "provider": envelope.provider,
        "opaque_ref": opaque_ref,
        "role": role,
        "media_type": resource.media_type,
        "sha256": digest,
        "object_key": key,
        "source_snapshot_id": str(snapshot_id(digest)),
        "source_revision": envelope.source_revision,
        "request_id": envelope.request_id,
        "fetched_at": envelope.fetched_at,
        "locator": envelope.source_locator or envelope.resource_uri,
        **({"asset_bindings": deepcopy(resource.metadata["asset_bindings"])}
           if "asset_bindings" in resource.metadata else {}),
    }


def upload_envelope(envelope, role, object_store):
    """Persist exact index/resolution bytes, never a reconstructed JSON envelope."""

    if envelope.raw_envelope is None:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    raw = envelope.raw_envelope
    digest = sha256(raw).hexdigest()
    key = "sources/" + digest[:16] + "/" + digest
    object_store.put_object(key, raw, "application/json")
    return {
        "provider": envelope.provider,
        "opaque_ref": role,
        "role": role,
        "media_type": "application/json",
        "sha256": digest,
        "object_key": key,
        "source_snapshot_id": str(snapshot_id(digest)),
        "source_revision": envelope.source_revision,
        "request_id": envelope.request_id,
        "fetched_at": envelope.fetched_at,
        "locator": envelope.source_locator or "connector:" + role,
    }


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in list(value.values()):
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _image_nodes(value, *, image_container=False):
    """Include kind-less figures in the ordered document's nested images arrays."""
    if isinstance(value, dict):
        if (
            image_container
            or str(value.get("type") or value.get("kind") or "").casefold() == "image"
        ):
            yield value
        for key, child in list(value.items()):
            yield from _image_nodes(child, image_container=key == "images")
    elif isinstance(value, list):
        for child in value:
            yield from _image_nodes(child, image_container=image_container)


def project_document(document):
    """Compatibility fields derived only from the authoritative ordered document."""
    texts = []
    steps = []
    images = [deepcopy(node) for node in _image_nodes(document.get("blocks", []))]

    def visit(value, *, strings=False):
        if isinstance(value, str):
            if strings:
                texts.append(value)
        elif isinstance(value, list):
            for child in value:
                visit(child, strings=strings)
        elif isinstance(value, dict):
            node = value
            if isinstance(node.get("text"), str):
                texts.append(node["text"])
            if node.get("type") == "step" and isinstance(node.get("text"), str):
                steps.append(
                    {
                        "number": node.get("number", len(steps) + 1),
                        "text": node["text"],
                        "evidence_ids": node.get("evidence_ids", []),
                    }
                )
            if node.get("type") == "ordered_list":
                for item in node.get("items", []):
                    if isinstance(item, str):
                        steps.append(
                            {
                                "number": len(steps) + 1,
                                "text": item,
                                "evidence_ids": node.get("evidence_ids", []),
                            }
                        )
            for key, child in node.items():
                if key not in ("text", "images") and isinstance(child, (dict, list)):
                    visit(child, strings=key in ("columns", "rows", "items"))

    visit(document.get("blocks", []))
    return "\n".join(texts), steps, images


def capture_source_article(context, *, registry, object_store, deadline_seconds=30.0):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("capture deadline must be within 30 seconds")
    provider = context.key.provider
    if provider not in registry:
        raise SourceConnectorError("NOT_CONFIGURED")
    client = registry[provider]
    if client.provider != provider:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    deadline = time.monotonic() + deadline_seconds
    cache = {}

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise SourceConnectorError("UPSTREAM_UNAVAILABLE", retryable=True)
        return seconds

    def read(ref):
        bound = ResourceRef(provider, ref)
        if bound not in cache:
            cache[bound] = client.read_resource(ref, timeout=remaining())
        return cache[bound]

    class BoundedObjects:
        """Bound caller latency, not an adapter's already-running network request.

        Runtime adapters must configure their own socket timeouts. On timeout the
        only possible late effect is a content-addressed blob upload; no worker
        thread can commit lifecycle observations or publish an article.
        """

        def put_object(self, *args):
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                pool.submit(object_store.put_object, *args).result(timeout=timeout)
            except TimeoutError:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
            except Exception:
                # SDK and transport exceptions have no shared OSError base.
                raise SourceConnectorError(
                    "ASSET_STORAGE_UNAVAILABLE", retryable=True
                ) from None
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

    bounded_objects = BoundedObjects()

    body_ref = context.descriptor.get("resource_ref") or context.descriptor.get(
        "body_resource_ref"
    )
    if not body_ref:
        raise SourceConnectorError("SOURCE_NOT_FOUND")
    body_pool = ThreadPoolExecutor(max_workers=1)
    try:
        body = body_pool.submit(read, body_ref).result(timeout=remaining())
    except TimeoutError:
        raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
    except SourceConnectorError as error:
        if error.status == 404:
            raise SourceConnectorError("SOURCE_NOT_FOUND") from None
        raise
    finally:
        body_pool.shutdown(wait=False, cancel_futures=True)
    parser_pool = ThreadPoolExecutor(max_workers=1)
    try:
        parsing = parser_pool.submit(
            adapt_bound_article, body.to_source_resource(), context
        )
        article = parsing.result(timeout=remaining())
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        code = (
            "WRONG_APPLICABILITY"
            if "applicability" in str(error)
            else "INVALID_ARTICLE_BODY"
        )
        raise SourceConnectorError(code) from None
    except TimeoutError:
        raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
    finally:
        parser_pool.shutdown(wait=False, cancel_futures=True)
    blocks = deepcopy(article["blocks"])
    for node in _image_nodes(blocks):
        node["kind"] = node["type"] = "image"
    refs = (
        list(context.descriptor.get("asset_resource_refs") or [])
        + list(body.body.get("asset_resource_refs") or [])
        + list(article.get("asset_resource_refs") or [])
    )
    for node in _walk(blocks):
        if (node.get("kind") or node.get("type")) == "image" and node.get(
            "asset_resource_ref"
        ):
            refs.append(node["asset_resource_ref"])
    # Stable dedupe retains the first source position; opaque refs are never normalized.
    refs = list(dict.fromkeys(refs))
    for node in _walk(blocks):
        if (
            (node.get("kind") or node.get("type")) == "image"
            and not node.get("asset_resource_ref")
            and node.get("url") in refs
        ):
            node["asset_resource_ref"] = node["url"]
    labor_ref = context.descriptor.get("labor_resource_ref")
    optional = [(ref, "asset") for ref in refs]
    if labor_ref and labor_ref not in refs and labor_ref != body_ref:
        optional.append((labor_ref, "labor"))
    resources = [upload_resource(body, body_ref, "body", bounded_objects)]
    manifest = [
        {k: resources[0][k] for k in ("role", "opaque_ref", "sha256", "media_type")}
    ]
    provenance = [deepcopy(resources[0])]
    failures = {}
    localized = {}

    # All requests share one deadline; no more than four can run concurrently.
    def fetch(pair):
        ref, role = pair
        try:
            envelope = read(ref)
            resource = upload_resource(envelope, ref, role, bounded_objects)
            if role == "asset" and (
                not resource["media_type"].startswith("image/")
                or resource["media_type"] == "image/svg+xml"
            ):
                return ref, role, None, "UNSUPPORTED_ASSET_MEDIA"
            return ref, role, resource, None
        except SourceConnectorError as error:
            return (
                ref,
                role,
                None,
                "SOURCE_NOT_FOUND" if error.status == 404 else error.code,
            )

    pool = ThreadPoolExecutor(max_workers=4)
    futures = [pool.submit(fetch, pair) for pair in optional]
    done, _ = wait(futures, timeout=max(0, deadline - time.monotonic()))
    for pair, future in zip(optional, futures):
        ref, role = pair
        if future not in done:
            future.cancel()
            resource = None
            failure = "CAPTURE_DEADLINE"
        else:
            _, _, resource, failure = future.result()
        if resource:
            resources.append(resource)
            provenance.append(deepcopy(resource))
            manifest.append(
                {k: resource[k] for k in ("role", "opaque_ref", "sha256", "media_type")}
            )
            if role == "asset":
                localized[ref] = resource
        else:
            failures[ref] = failure
            entry = {"role": role, "opaque_ref": ref, "failure_code": failure}
            manifest.append(entry)
            provenance.append({"provider": provider, **entry})
    pool.shutdown(wait=False, cancel_futures=True)
    # Embedded figures are derived only from verified body bytes and never fetched by URL.
    for node in _walk(blocks):
        uri = node.get("url", "")
        if (node.get("kind") or node.get("type")) == "image" and uri.startswith(
            "data:image/"
        ):
            try:
                header, encoded = uri.split(",", 1)
                media = header[5:].split(";", 1)[0]
                if ";base64" not in header or media == "image/svg+xml":
                    raise ValueError("unsupported embedded figure")
                payload = base64.b64decode(encoded, validate=True)
                digest = sha256(payload).hexdigest()
                key = "sources/" + digest[:16] + "/" + digest
                bounded_objects.put_object(key, payload, media)
                ref = "embedded:" + resources[0]["sha256"] + ":" + digest
                local = {
                    "provider": provider,
                    "opaque_ref": ref,
                    "role": "embedded_asset",
                    "media_type": media,
                    "sha256": digest,
                    "object_key": key,
                    "source_snapshot_id": str(snapshot_id(digest)),
                    "source_revision": body.source_revision,
                    "request_id": body.request_id,
                    "fetched_at": body.fetched_at,
                    "locator": resources[0]["locator"],
                }
                localized[ref] = local
                resources.append(local)
                provenance.append(deepcopy(local))
                manifest.append(
                    {
                        k: local[k]
                        for k in ("role", "opaque_ref", "sha256", "media_type")
                    }
                )
                node["asset_resource_ref"] = ref
            except (ValueError, TypeError):
                node["reason"] = "INVALID_EMBEDDED_IMAGE"
            except SourceConnectorError as error:
                node["reason"] = error.code
    positioned = set()
    image_records = {}
    for node in _walk(blocks):
        # No executable/provider URLs or upstream-supplied source_original enter the projection.
        for key in (
            "source_original",
            "source_url",
            "href",
            "url",
            "src",
            "locator",
            "uri",
            "path",
            "storage_key",
            "artifact_key",
            "object_key",
            "asset_id",
            "content_sha256",
            "source_snapshot_id",
        ):
            node.pop(key, None)
        if (node.get("kind") or node.get("type")) == "image":
            ref = node.pop("asset_resource_ref", None)
            positioned.add(ref)
            local = localized.get(ref)
            node.update(
                {
                    "image_id": (
                        local["sha256"]
                        if local
                        else digest_json(
                            {
                                "provider": provider,
                                "ref": ref,
                                "position": len(positioned),
                            }
                        )
                    ),
                    "status": "available" if local else "unavailable",
                    "evidence_ids": list(context.evidence_ids),
                }
            )
            if local:
                node.update(
                    {
                        "storage_key": local["object_key"],
                        "content_sha256": local["sha256"],
                        "media_type": local["media_type"],
                    }
                )
            else:
                node.update(
                    {
                        "fetch_failed": True,
                        "reason": failures.get(
                            ref, node.get("reason", "UNBOUND_SOURCE_IMAGE")
                        ),
                    }
                )
            image_records[node["image_id"]] = deepcopy(node)
    for ref in refs:
        if ref not in positioned:
            local = localized.get(ref)
            blocks.append(
                {
                    "kind": "image",
                    "image_id": (
                        local["sha256"]
                        if local
                        else digest_json({"provider": provider, "ref": ref})
                    ),
                    "storage_key": local["object_key"] if local else None,
                    "content_sha256": local["sha256"] if local else None,
                    "media_type": local["media_type"] if local else None,
                    "fetch_failed": not bool(local),
                    "reason": failures.get(ref),
                    "evidence_ids": list(context.evidence_ids),
                }
            )
    evidence_ids = list(context.evidence_ids) or [
        "source:" + resources[0]["source_snapshot_id"]
    ]
    doc = build_ordered_document(
        {"article_id": str(article_id(context.key)), "evidence_ids": evidence_ids},
        blocks,
    )
    for node in _image_nodes(doc["blocks"]):
        node["evidence_ids"] = list(evidence_ids)
        local = image_records.get(node.get("image_id"))
        if local:
            for name in ("status", "media_type", "content_sha256", "storage_key"):
                if name in local:
                    node[name] = local[name]
            node["unavailable_reason"] = (
                local.get("reason") if local["status"] == "unavailable" else None
            )
    body_text, steps, images = project_document(doc)
    if (
        not body_text.strip()
        or body_text.strip() == str(context.descriptor.get("title", "")).strip()
    ):
        raise SourceConnectorError("INVALID_ARTICLE_BODY")
    fingerprint = digest_json(
        {
            "provider": provider,
            "body_ref": body_ref,
            "body_sha256": resources[0]["sha256"],
            "body_media_type": resources[0]["media_type"],
            "resource_manifest": manifest,
            **({"asset_bindings": sorted(body.body["asset_bindings"], key=lambda item: item["source_url"])}
               if body.body.get("asset_bindings") else {}),
        }
    )
    return CapturedSource(
        context,
        fingerprint,
        snapshot_id(resources[0]["sha256"]),
        tuple(resources),
        manifest,
        provenance,
        doc,
        images,
        body_text,
        steps,
        [
            {
                "evidence_id": e,
                "body_source_snapshot_id": resources[0]["source_snapshot_id"],
            }
            for e in evidence_ids
        ],
        (
            "partial"
            if failures or any(i.get("status") == "unavailable" for i in images)
            else "readable"
        ),
        datetime.now(timezone.utc),
        projection_version="source-projection-v2",
    )
