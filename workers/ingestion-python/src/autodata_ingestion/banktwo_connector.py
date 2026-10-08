"""Read-only, vehicle-scoped access to Banktwo repair content."""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import re
import os
from typing import Any, Mapping

from .source_connector_client import (
    SourceConnectorClient,
    SourceConnectorError,
    SourceEnvelopeV1,
    source_connector_registry,
)


class ArticleParser(HTMLParser):
    """Keep ordered paragraphs, figures and component links without executable HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.links = []
        self._text = []
        self._skip = 0
        self._image_link = 0
        self._list_kind = None
        self._list_items = []
        self._list_item_open = False
        self._list_item_parts = []
        self._list_start = 1
        self._list_continuation_pending = False
        self._table_rows = None
        self._table_row = None
        self._table_cell = None

    @property
    def _in_table(self):
        return self._table_rows is not None

    def flush(self):
        value = re.sub(r"\s+", " ", "".join(self._text)).strip()
        self._text = []
        if value:
            if self._table_cell is not None:
                self._table_cell.append({"kind": "text", "text": value})
            elif self._list_kind and self._list_item_open:
                self._list_item_parts.append(value)
            else:
                self.blocks.append({"kind": "text", "text": value})
                self._list_start = 1
                self._list_continuation_pending = False

    def _finish_list_item(self):
        if not self._list_kind or not self._list_item_open:
            return
        self.flush()
        value = re.sub(r"\s+", " ", " ".join(self._list_item_parts)).strip()
        if value:
            self._list_items.append(value)
        self._list_item_parts = []
        self._list_item_open = False

    def _flush_list(self):
        if not self._list_kind:
            return
        self._finish_list_item()
        if self._list_items:
            block = {"kind": self._list_kind, "items": list(self._list_items)}
            if self._list_kind == "ordered_list":
                block["start"] = self._list_start
            self.blocks.append(block)
            self._list_start += len(self._list_items)
            self._list_continuation_pending = True
        self._list_items = []

    def _flush_cell(self):
        self.flush()
        if self._table_cell is not None and self._table_row is not None:
            self._table_row.append({"blocks": self._table_cell})
        self._table_cell = None

    def _flush_row(self):
        self._flush_cell()
        if self._table_row is not None and self._table_rows is not None:
            if self._table_row:
                self._table_rows.append(self._table_row)
        self._table_row = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self._skip += 1
        if self._skip:
            return
        if self._list_continuation_pending and tag not in {"ol", "ul", "li", "a", "img"}:
            self._list_start = 1
            self._list_continuation_pending = False
        if tag == "table":
            self.flush()
            self._list_start = 1
            self._list_continuation_pending = False
            self._table_rows = []
            self._table_row = None
            self._table_cell = None
            return
        if self._in_table:
            if tag == "tr":
                self._flush_row()
                self._table_row = []
                return
            if tag in {"td", "th"}:
                self._flush_cell()
                if self._table_row is None:
                    self._table_row = []
                self._table_cell = []
                return
            if tag == "br":
                self.flush()
                return
        if tag in {"ol", "ul"} and not self._in_table:
            self.flush()
            if self._list_kind:
                self._flush_list()
            self._list_kind = "ordered_list" if tag == "ol" else "unordered_list"
            self._list_items = []
            self._list_item_open = False
            self._list_item_parts = []
            if not self._list_continuation_pending:
                self._list_start = 1
            self._list_continuation_pending = False
            return
        if tag == "li" and self._list_kind and not self._in_table:
            self._finish_list_item()
            self._list_item_open = True
            return
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.flush()
        if tag == "a":
            if attrs.get("class") == "image":
                self._image_link += 1
            elif attrs.get("href"):
                self.links.append(attrs["href"])
        if tag == "img" and attrs.get("src"):
            self.flush()
            image = {"kind": "image", "url": attrs["src"], "alt": attrs.get("alt", ""), "name": attrs.get("img_name", "")}
            if self._table_cell is not None:
                self._table_cell.append(image)
            elif self._list_kind:
                self._finish_list_item()
                self._flush_list()
                self.blocks.append(image)
            else:
                self.blocks.append(image)

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        if tag == "table" and self._in_table:
            self._flush_row()
            rows = self._table_rows or []
            self._table_rows = None
            self._table_row = None
            self._table_cell = None
            if rows:
                self.blocks.append({"kind": "table", "rows": rows})
            return
        if self._in_table:
            if tag in {"td", "th"}:
                self._flush_cell()
                return
            if tag == "tr":
                self._flush_row()
                return
            if tag in {"br", "div", "p"}:
                self.flush()
                return
        if tag == "li" and self._list_kind and not self._in_table:
            self._finish_list_item()
            return
        if tag in {"ol", "ul"} and self._list_kind and not self._in_table:
            self._flush_list()
            self._list_kind = None
            self._list_item_open = False
            self._list_item_parts = []
            return
        if tag == "a":
            self._image_link = 0
        if tag in {"p", "div", "li", "tr"}:
            self.flush()

    def handle_data(self, data):
        if not self._skip and not self._image_link:
            self._text.append(data)


class SourceUnavailable(RuntimeError):
    def __init__(self, message: str = "repair source is unavailable", *, code: str = "UPSTREAM_UNAVAILABLE"):
        self.code = code
        super().__init__(message)


class BanktwoConnector:
    """Compatibility facade for Banktwo's provider-neutral Source Connector v1."""

    def __init__(self, base_url: str | None = None, *, source_client: SourceConnectorClient | None = None,
                 opener: Any = None, timeout: float = 25, max_bytes: int = 8_000_000,
                 cache_entries: int = 128, cache_ttl: int = 300, retry_attempts: int = 3,
                 retry_delay: float = 0.25, retry_after_cap: float = 30.0):
        del cache_entries, cache_ttl, retry_attempts, retry_delay, retry_after_cap
        if source_client is not None:
            self.client = source_client
        elif opener is None and base_url is None:
            self.client = source_connector_registry(include_defaults=True)["banktwo"]
        else:
            configured = os.getenv("BANKTWO_BASE_URL", "https://banktwo.cars.tk")
            self.client = SourceConnectorClient(
                base_url or configured,
                token=os.getenv("BANKTWO_API_TOKEN") or None,
                timeout=timeout,
                max_bytes=max_bytes,
                provider="banktwo",
                opener=opener,
            )

    def resolve_vehicle(self, selector: Mapping[str, Any]) -> SourceEnvelopeV1:
        return self._call(self.client.resolve_vehicle, selector)

    def list_articles(self, source_vehicle_ref: str, cursor: str | None = None) -> SourceEnvelopeV1:
        return self._call(self.client.list_articles, source_vehicle_ref, cursor)

    def search_articles(self, source_vehicle_ref: str, query: str, cursor: str | None = None) -> SourceEnvelopeV1:
        return self._call(self.client.search_articles, source_vehicle_ref, query, cursor)

    def read_resource(self, resource_ref: str) -> SourceEnvelopeV1:
        return self._call(self.client.read_resource, resource_ref)

    def _call(self, operation: Any, *args: Any) -> SourceEnvelopeV1:
        try:
            return operation(*args)
        except SourceConnectorError as error:
            raise SourceUnavailable(code=error.code) from None

    def fetch_article_catalog(self, source_vehicle_ref: str, *, max_index_reads: int = 512, on_progress=None):
        """Compatibility wrapper that lists v1 article descriptors in source order."""
        rows: list[dict[str, Any]] = []
        cursor = None
        reads = 0
        while True:
            if reads >= max_index_reads:
                raise SourceUnavailable("article catalog exceeds its page limit", code="INVALID_UPSTREAM_RESPONSE")
            envelope = self.list_articles(source_vehicle_ref, cursor)
            reads += 1
            page = envelope.body["articles"]
            rows.extend(dict(row) for row in page)
            if on_progress is not None:
                try:
                    on_progress({"phase": "indexing", "processed_units": reads,
                                 "total_units": reads if envelope.complete else None,
                                 "outcome": "succeeded", "result_count": len(page)})
                except Exception:
                    pass
            if envelope.complete:
                break
            cursor = envelope.next_cursor
        return {"articles": tuple(rows), "index_reads": reads,
                "component_reads": 0, "information_type_reads": 0}

    @staticmethod
    def descriptor_for_legacy_article_id(
        legacy_article_id: str,
        descriptors: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> Mapping[str, Any]:
        """Resolve an old persisted ``autoapitwo:<vehicle>:<article>`` ID.

        Source Connector v1 makes refs opaque and does not promise equality
        with Banktwo's historical IDs. Compatibility therefore uses only an
        exact suffix match and fails closed when it is absent or ambiguous.
        """
        parts = str(legacy_article_id or "").split(":", 2)
        if (len(parts) != 3 or parts[0] != "autoapitwo"
                or not parts[1].isdigit() or not parts[2]):
            raise SourceUnavailable(code="NOT_FOUND")
        matches = [
            descriptor for descriptor in descriptors
            if isinstance(descriptor, Mapping)
            and str(descriptor.get("opaque_ref") or "") == parts[2]
        ]
        if len(matches) != 1:
            raise SourceUnavailable(code="NOT_FOUND")
        return matches[0]

    def article_by_legacy_id(
        self,
        source_vehicle_ref: str,
        legacy_article_id: str,
        descriptors: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        """Read a v1 resource while retaining the supplied persisted ID."""
        descriptor = self.descriptor_for_legacy_article_id(legacy_article_id, descriptors)
        return self.article_by_descriptor(
            source_vehicle_ref, descriptor, article_id=legacy_article_id
        )

    def article_by_descriptor(
        self,
        source_vehicle_ref: str,
        descriptor: Mapping[str, Any],
        *,
        article_id: str | None = None,
    ) -> dict[str, Any]:
        resource_ref = str(descriptor.get("resource_ref") or descriptor.get("opaque_ref") or "").strip()
        if not resource_ref:
            raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
        envelope = self.read_resource(resource_ref)
        resource = envelope.to_source_resource()
        if resource.metadata.get("kind") not in {"article", "text"}:
            raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
        html = resource.payload.decode("utf-8")
        article_id = article_id or f"autoapitwo:{source_vehicle_ref}:{descriptor.get('opaque_ref', resource_ref)}"
        digest = sha256(resource.payload).hexdigest()
        evidence_id = f"{article_id}:{digest}"
        parser = ArticleParser()
        parser.feed(html)
        parser.flush()
        asset_refs = []
        for value in (descriptor.get("asset_resource_refs"), envelope.body.get("asset_resource_refs")):
            if isinstance(value, list):
                asset_refs.extend(str(item) for item in value if isinstance(item, str))
        asset_refs = list(dict.fromkeys(asset_refs))
        image_blocks: list[dict[str, Any]] = []
        next_asset = iter(asset_refs)

        def annotate(block: Any, index: tuple[int, ...]) -> None:
            if not isinstance(block, dict):
                return
            suffix = ".".join(str(part) for part in index)
            block["evidence_ids"] = [evidence_id]
            block["block_id"] = f"{article_id}:block:{suffix}"
            if block.get("kind") == "image":
                block.pop("url", None)
                try:
                    ref = next(next_asset)
                except StopIteration:
                    block["status"] = "unavailable"
                    block["unavailable_reason"] = "source asset reference was not provided"
                else:
                    block["asset_resource_ref"] = ref
                    block["image_id"] = sha256(ref.encode()).hexdigest()
                    image_blocks.append(block)
                return
            if block.get("kind") == "table":
                for row_index, row in enumerate(block.get("rows") or []):
                    cells = row.get("blocks") if isinstance(row, dict) else row
                    if isinstance(cells, list):
                        for cell_index, cell in enumerate(cells):
                            nested = cell.get("blocks") if isinstance(cell, dict) else None
                            if isinstance(nested, list):
                                for child_index, child in enumerate(nested):
                                    annotate(child, (*index, row_index, cell_index, child_index))
                            elif isinstance(cell, dict):
                                annotate(cell, (*index, row_index, cell_index))

        for block_index, block in enumerate(parser.blocks):
            annotate(block, (block_index,))
        article = {
            "article_id": article_id,
            "title": str(descriptor.get("title") or ""),
            "provider": "autoapitwo",
            "provider_vehicle_id": source_vehicle_ref,
            "source_uri": resource.locator,
            "source_resource_ref": resource_ref,
            "source_asset_refs": asset_refs,
            "source_watermark": digest,
            "raw_html": html,
            "body": "\n\n".join(_article_text_blocks(parser.blocks)),
            "blocks": parser.blocks,
            "images": image_blocks,
            "component_links": [],
            "evidence_ids": [evidence_id],
            "evidence": [{"evidence_id": evidence_id, "source_uri": resource.locator, "content_hash": digest}],
            "source_request_id": resource.metadata.get("request_id"),
            "source_revision": resource.source_version,
            "source_provider": "banktwo",
            "source_sha256": digest,
            "bucket": str(descriptor.get("category") or ""),
        }
        labor_ref = str(descriptor.get("labor_resource_ref") or "").strip()
        if labor_ref:
            labor_envelope = self.read_resource(labor_ref)
            labor_resource = labor_envelope.to_source_resource()
            labor_text = labor_resource.payload.decode("utf-8")
            article.update({
                "labor_body": labor_text,
                "labor_resource_ref": labor_ref,
                "labor_source_uri": labor_resource.locator,
                "labor_source_sha256": sha256(labor_resource.payload).hexdigest(),
                "labor_source_revision": labor_resource.source_version,
                "labor_source_request_id": labor_resource.metadata.get("request_id"),
                "labor_source_provider": "banktwo",
            })
        return article

    def search(self, source_vehicle_ref: str, term: str) -> list[dict[str, Any]]:
        envelope = self.search_articles(source_vehicle_ref, term)
        rows = [dict(row) for row in envelope.body["articles"]]
        cursor = envelope.next_cursor
        seen: set[str] = set()
        while not envelope.complete:
            if not cursor or cursor in seen or len(seen) >= 512:
                raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
            seen.add(cursor)
            envelope = self.search_articles(source_vehicle_ref, term, cursor)
            rows.extend(dict(row) for row in envelope.body["articles"])
            cursor = envelope.next_cursor
        return rows

    def article(self, source_vehicle_ref: str, descriptor: Mapping[str, Any], *, title: str | None = None):
        value = dict(descriptor)
        if title and not value.get("title"):
            value["title"] = title
        return self.article_by_descriptor(source_vehicle_ref, value)


def _source_failure_reason(error: BaseException) -> str:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain and len(chain) < 8:
        chain.append(current)
        current = current.__cause__ or current.__context__
    status = next(
        (
            int(getattr(item, attribute))
            for item in chain
            for attribute in ("code", "status", "status_code")
            if str(getattr(item, attribute, "")).isdigit()
        ),
        None,
    )
    text = " ".join(str(getattr(item, "reason", "") or item).casefold() for item in chain)
    if "no matching" in text or "did not resolve" in text or "no vehicle" in text:
        return "returned no matching vehicle"
    codes = {str(getattr(item, "code", "")).upper() for item in chain}
    if "RATE_LIMITED" in codes:
        return "rate limited"
    if "UNAUTHORIZED" in codes:
        return "authentication expired or unauthorized"
    if "UPSTREAM_UNAVAILABLE" in codes:
        return "source server unavailable"
    if "AMBIGUOUS" in codes:
        return "vehicle resolution is ambiguous"
    if "NOT_FOUND" in codes:
        return "returned no matching vehicle"
    if status == 429 or "rate limit" in text or "too many requests" in text:
        return "rate limited"
    if status == 401 or "expired" in text or "authentication" in text or "unauthorized" in text:
        return "authentication expired or unauthorized"
    if status == 403 or "forbidden" in text:
        return "forbidden"
    if status in {408, 504} or "timed out" in text or "timeout" in text:
        return "server timed out"
    if status is not None and status >= 500:
        return f"source server unavailable (HTTP {status})"
    if "incomplete" in text and "article" in text:
        return "article index was incomplete"
    if "source read failed" in text:
        return "source read failed"
    return "request failed"


def _article_text_blocks(blocks: Any):
    """Yield readable text from top-level and table-cell source blocks."""

    for block in blocks or []:
        if not isinstance(block, Mapping):
            continue
        if block.get("kind") == "text" and str(block.get("text") or "").strip():
            yield str(block["text"]).strip()
        elif block.get("kind") == "table":
            for row in block.get("rows") or []:
                cells = row.get("blocks") if isinstance(row, Mapping) else row
                if not isinstance(cells, list):
                    continue
                for cell in cells:
                    cell_blocks = cell.get("blocks") if isinstance(cell, Mapping) else None
                    if not isinstance(cell_blocks, list):
                        cell_blocks = [cell]
                    for cell_block in cell_blocks:
                        if not isinstance(cell_block, Mapping) or cell_block.get("kind") != "text":
                            continue
                        text = str(cell_block.get("text") or "").strip()
                        if text:
                            yield text
