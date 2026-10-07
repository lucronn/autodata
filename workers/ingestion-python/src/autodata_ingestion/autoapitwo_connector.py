"""Read-only, vehicle-scoped access to AutoAPI Two repair content."""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
import re
from threading import RLock
import time
from urllib.parse import quote, urljoin, urlsplit, unquote
from urllib.request import build_opener, HTTPRedirectHandler, Request
from typing import Any, Mapping

from .autodbtwo_http_client import AutoDBtwoHTTPClient, AutoDBtwoRequestError


class SourceUnavailable(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceUnavailable("unexpected source redirect")


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


class AutoAPITwoConnector:
    def __init__(
        self,
        base_url="https://autoapitwo.vercel.app",
        *,
        opener=None,
        timeout=25,
        max_bytes=8_000_000,
        cache_entries=128,
        cache_ttl=300,
        retry_attempts=3,
        retry_delay=0.25,
        retry_after_cap=30.0,
        connector_url=None,
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("source base must be an HTTPS origin")
        if min(timeout, max_bytes, cache_entries, cache_ttl, retry_attempts) <= 0 or retry_delay < 0 or retry_after_cap < 0:
            raise ValueError("source limits must be positive")
        self.base = base_url.rstrip("/")
        configured_connector_url = connector_url or os.getenv("AUTODATA_AUTODBTWO_BASE_URL")
        self._remote_client = (
            AutoDBtwoHTTPClient(
                configured_connector_url or "http://127.0.0.1:3001",
                upstream_base_url=self.base,
                opener=opener,
                timeout=timeout,
                max_bytes=max_bytes,
            )
            if configured_connector_url or opener is None
            else None
        )
        self.opener = opener or build_opener(_NoRedirect()).open
        self.timeout, self.max_bytes = timeout, max_bytes
        self.cache_entries, self.cache_ttl = cache_entries, cache_ttl
        self.retry_attempts, self.retry_delay, self.retry_after_cap = retry_attempts, retry_delay, retry_after_cap
        self._cache = OrderedDict()
        # Serialize source reads to bound upstream load and coalesce identical misses.
        self._lock = RLock()
        self._retry_at = 0.0

    def safe_url(self, href, car_id=None):
        url = urljoin(self.base + "/", href)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != urlsplit(self.base).netloc or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("source link leaves the configured origin")
        path = unquote(parsed.path)
        if any(part in {".", ".."} for part in path.split("/")) or "\\" in path:
            raise ValueError("invalid source path")
        allowed = ("/api/v1/fleet/search/", "/api/v1/fleet/carids/", "/api/v1/content/carids/")
        if not path.startswith(allowed):
            raise ValueError("source endpoint is not an allowed content read")
        if car_id is not None:
            car_id = str(car_id)
            if not car_id.isdigit() or not path.startswith(f"/api/v1/content/carids/{car_id}/"):
                raise ValueError("source content vehicle mismatch")
        return url

    def read(self, href, *, car_id=None, binary=False):
        url = self.safe_url(href, car_id)
        key = (url, binary)
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                self._cache.move_to_end(key)
                return deepcopy(cached[1])
            if self._remote_client is not None:
                try:
                    response = self._remote_client.read(
                        url,
                        binary=binary,
                        car_id=str(car_id) if car_id is not None else None,
                    )
                    result = response.body if binary else json.loads(response.body)
                except (AutoDBtwoRequestError, json.JSONDecodeError) as error:
                    raise SourceUnavailable(str(error) or "AutoDBtwo source read failed") from error
                self._cache[key] = (time.monotonic() + self.cache_ttl, result)
                while len(self._cache) > self.cache_entries:
                    self._cache.popitem(last=False)
                return deepcopy(result)
            for attempt in range(self.retry_attempts):
                cooldown = self._retry_at - time.monotonic()
                if cooldown > 0:
                    time.sleep(cooldown)
                try:
                    from .api_auth import api_key_headers

                    headers = {"Accept": "image/*" if binary else "application/json", **api_key_headers("banktwo")}
                    with self.opener(Request(url, headers=headers), timeout=self.timeout) as response:
                        if hasattr(response, "geturl") and response.geturl() != url:
                            raise SourceUnavailable("unexpected source redirect")
                        raw = response.read(self.max_bytes + 1)
                        if len(raw) > self.max_bytes:
                            raise SourceUnavailable("source response exceeds size limit")
                        result = raw if binary else json.loads(raw)
                    break
                except SourceUnavailable:
                    raise
                except Exception as error:
                    status = getattr(error, "code", None)
                    if status not in {429, 502, 503, 504} or attempt + 1 >= self.retry_attempts:
                        raise SourceUnavailable("repair source read failed") from error
                    delay = self._retry_delay(error, attempt)
                    if status == 429:
                        self._retry_at = max(self._retry_at, time.monotonic() + delay)
                    if delay:
                        time.sleep(delay)
            else:
                raise SourceUnavailable("repair source read failed")
            self._cache[key] = (time.monotonic() + self.cache_ttl, result)
            while len(self._cache) > self.cache_entries:
                self._cache.popitem(last=False)
            return deepcopy(result)

    def _retry_delay(self, error, attempt):
        """Return a small capped delay without exposing provider details."""
        delay = self.retry_delay * (2**attempt)
        headers = getattr(error, "headers", {}) or {}
        retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
        if retry_after is not None:
            try:
                delay = max(0.0, float(retry_after))
            except (TypeError, ValueError):
                pass
        return min(self.retry_after_cap, delay)

    def search_vehicles(self, query):
        result = self.read('/api/v1/fleet/search/' + quote(str(query), safe=''))
        values = result.get('results', [])
        return values if isinstance(values, list) else []

    def fetch_article_catalog(self, car_id, *, max_index_reads=512, on_progress=None):
        """Read the AutoAPItwo article index without fetching article bodies.

        AutoAPItwo's component tree is useful for navigating a vehicle, but it
        is far too expensive for catalog hydration: older vehicles can expose
        thousands of component and information-type pages. Its search index
        returns the same article descriptors (title, category, and detail
        link) in one bounded request per alphanumeric query. The query set is
        deterministic and the results are deduplicated by detail link.

        Detail content is fetched only by :meth:`article` after a user selects
        one catalog row.
        """

        car_id = str(car_id).strip()
        if not car_id.isdigit():
            raise ValueError("AutoAPItwo car ID must be numeric")
        terms = tuple("abcdefghijklmnopqrstuvwxyz0123456789")
        if len(terms) > max_index_reads:
            raise ValueError("repair article catalog search exceeds its index read limit")
        articles = {}
        errors = []

        def search_term(term):
            # Each worker has its own read lock so the independent search
            # requests can run in a small, bounded pool. This is still only
            # the fixed index query set; no article body is fetched.
            client = AutoAPITwoConnector(
                self.base,
                opener=self.opener,
                timeout=self.timeout,
                max_bytes=self.max_bytes,
                cache_entries=self.cache_entries,
                cache_ttl=self.cache_ttl,
                retry_attempts=self.retry_attempts,
                retry_delay=self.retry_delay,
                retry_after_cap=self.retry_after_cap,
                connector_url=self._remote_client.base_url if self._remote_client else None,
            )
            return term, client.search(car_id, term)

        completed_reads = 0
        with ThreadPoolExecutor(max_workers=min(4, len(terms))) as pool:
            futures = {pool.submit(search_term, term): term for term in terms}
            for future in as_completed(futures):
                try:
                    _, results = future.result()
                except Exception as error:  # noqa: BLE001 - a partial index is not complete
                    errors.append(error)
                    completed_reads += 1
                    if on_progress is not None:
                        try:
                            on_progress({
                                "phase": "indexing",
                                "processed_units": completed_reads,
                                "total_units": len(terms),
                                "term": futures[future],
                                "outcome": "failed",
                                "detail": f'Article-index query "{futures[future]}" failed — {_source_failure_reason(error)}.',
                            })
                        except Exception:
                            pass
                    continue
                for result in results:
                    if not isinstance(result, Mapping):
                        continue
                    article_href = _self_href(result)
                    if not article_href:
                        continue
                    article_url = self.safe_url(article_href, car_id)
                    article_id = unquote(urlsplit(article_url).path.rstrip("/").rsplit("/", 1)[-1]).strip()
                    display = str(result.get("display") or "").strip()
                    title = str(result.get("title") or result.get("name") or "").strip()
                    if not title and display:
                        title = display.rsplit(">>", 1)[-1].strip()
                    if not article_id or not title:
                        continue
                    category = result.get("itypeCategory")
                    bucket = category.get("name") if isinstance(category, Mapping) else ""
                    articles.setdefault(
                        article_url,
                        {
                            "id": f"autoapitwo:{car_id}:{article_id}",
                            "title": title,
                            "bucket": str(bucket or "").strip(),
                            "href": article_url,
                            "provider": "autoapitwo",
                            "provider_vehicle_id": car_id,
                        },
                    )
                completed_reads += 1
                if on_progress is not None:
                    try:
                        on_progress({
                            "phase": "indexing",
                            "processed_units": completed_reads,
                            "total_units": len(terms),
                            "term": futures[future],
                            "outcome": "succeeded",
                            "result_count": len(results),
                            "detail": f'Article-index query "{futures[future]}" succeeded — {len(results)} article links returned.',
                        })
                    except Exception:
                        pass
        if errors:
            raise SourceUnavailable("repair article search index is incomplete") from errors[0]
        ordered_articles = tuple(
            sorted(
                articles.values(),
                key=lambda item: (
                    str(item.get("title") or "").casefold(),
                    str(item.get("bucket") or "").casefold(),
                    str(item.get("id") or ""),
                ),
            )
        )
        return {
            "articles": ordered_articles,
            "index_reads": len(terms),
            "component_reads": 0,
            "information_type_reads": 0,
            "search_terms": terms,
            "search_error_count": len(errors),
        }


    def search(self, car_id, term):
        result = self.read(f'/api/v1/content/carids/{car_id}/search/{quote(term, safe="")}', car_id=car_id)
        values = result.get('_embedded', {}).get('data', {}).get('results', [])
        return values if isinstance(values, list) else []

    def article(self, car_id, href, *, title=None):
        url = self.safe_url(href, car_id)
        result = self.read(url, car_id=car_id)
        if str(result.get('car', {}).get('id', '')) != str(car_id):
            raise SourceUnavailable('article vehicle does not match request')
        embedded = result.get('_embedded', {}).get('data', {})
        if not isinstance(embedded, Mapping):
            embedded = {}
        article = embedded.get('article', {})
        if not isinstance(article, Mapping):
            article = {}
        html = article.get('content')
        if isinstance(html, str) and html.strip():
            parser = ArticleParser()
            parser.feed(html)
            parser.flush()
            digest = sha256(html.encode()).hexdigest()
            article_id = f'autoapitwo:{car_id}:{result.get("id", digest)}'
            evidence_id = f'{article_id}:{digest}'
            image_blocks = []
            for index, block in enumerate(parser.blocks):
                _annotate_article_block(
                    block,
                    article_id=article_id,
                    evidence_id=evidence_id,
                    source_index=index,
                    car_id=car_id,
                    connector=self,
                    image_blocks=image_blocks,
                )
            component_links = []
            for link in dict.fromkeys(parser.links):
                # Provider article HTML includes document-local anchors for
                # tool tables and headings. They are presentation links, not
                # source resources, and must not be sent through safe_url.
                if not link or link.startswith('#'):
                    continue
                try:
                    component_links.append(self.safe_url(link, car_id))
                except ValueError:
                    # A malformed or external inline link must not make an
                    # otherwise readable repair article unavailable.
                    continue
            return {
                'article_id': article_id, 'title': title or result.get('title', ''),
                'provider': 'autoapitwo', 'provider_vehicle_id': str(car_id),
                'vehicle': result['car'], 'source_uri': url, 'source_watermark': digest,
                # Keep the provider's block boundaries so the reader can
                # render headings and paragraphs instead of one text wall.
                'raw_html': html, 'body': '\n\n'.join(_article_text_blocks(parser.blocks)),
                'blocks': parser.blocks, 'images': image_blocks,
                'component_links': component_links,
                'evidence_ids': [evidence_id],
                'evidence': [{'evidence_id': evidence_id, 'source_uri': url, 'content_hash': digest}],
            }
        labor_article = self._parts_and_labor_article(car_id, url, result, embedded, title=title)
        if labor_article is not None:
            return labor_article
        raise SourceUnavailable('repair article has no instructions')

    def _parts_and_labor_article(self, car_id, url, result, embedded, *, title=None):
        """Build a source article from Parts and Labor when procedure HTML is absent."""

        parts = embedded.get('partsAndLabor')
        if not isinstance(parts, Mapping):
            return None
        labors = parts.get('labors')
        if not isinstance(labors, Mapping):
            return None
        operations = labors.get('operations')
        if not isinstance(operations, list) or not operations:
            return None
        lines: list[str] = []
        labor_hours: list[float] = []
        for operation in operations:
            if not isinstance(operation, Mapping):
                continue
            op_name = str(operation.get('operation') or 'Replace').strip() or 'Replace'
            qualifiers = operation.get('qualifiers')
            if not isinstance(qualifiers, list) or not qualifiers:
                lines.append(f'{op_name}.')
                continue
            for qualifier in qualifiers:
                if not isinstance(qualifier, Mapping):
                    continue
                name = str(qualifier.get('name') or op_name).strip() or op_name
                labor = qualifier.get('labor') if isinstance(qualifier.get('labor'), Mapping) else {}
                note = str(labor.get('note') or '').strip()
                standard = labor.get('standardtime')
                try:
                    if standard is not None and str(standard).strip():
                        labor_hours.append(float(standard))
                except (TypeError, ValueError):
                    pass
                if note:
                    lines.append(f'{name}. {note}'.strip())
                else:
                    lines.append(f'{name}.')
                nested = qualifier.get('qualifiers')
                if isinstance(nested, list):
                    for child in nested:
                        if not isinstance(child, Mapping):
                            continue
                        child_name = str(child.get('name') or '').strip()
                        child_labor = child.get('labor') if isinstance(child.get('labor'), Mapping) else {}
                        child_note = str(child_labor.get('note') or '').strip()
                        if child_name and child_note:
                            lines.append(f'{child_name}. {child_note}'.strip())
                        elif child_name:
                            lines.append(f'{child_name}.')
        lines = [line for line in dict.fromkeys(lines) if line]
        if not lines:
            return None
        body = '\n'.join(lines)
        digest = sha256(body.encode()).hexdigest()
        article_id = f'autoapitwo:{car_id}:labor:{result.get("id", digest)}'
        evidence_id = f'{article_id}:{digest}'
        blocks = [
            {
                'kind': 'text',
                'text': line,
                'evidence_ids': [evidence_id],
                'block_id': f'{article_id}:block:{index}',
            }
            for index, line in enumerate(lines)
        ]
        payload = {
            'article_id': article_id,
            'title': title or result.get('title', '') or 'Parts and Labor',
            'provider': 'autoapitwo',
            'provider_vehicle_id': str(car_id),
            'vehicle': result.get('car') if isinstance(result.get('car'), Mapping) else {'id': str(car_id)},
            'source_uri': url,
            'source_watermark': digest,
            'raw_html': '',
            'body': body,
            'blocks': blocks,
            'images': [],
            'component_links': [],
            'evidence_ids': [evidence_id],
            'evidence': [{'evidence_id': evidence_id, 'source_uri': url, 'content_hash': digest}],
            'bucket': 'labor',
            'content_kind': 'parts_and_labor',
        }
        if labor_hours:
            payload['labor_hours'] = max(labor_hours)
            payload['duration_hours'] = max(labor_hours)
        return payload


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
    if "no matching" in text or "did not resolve" in text or "no vehicle" in text:
        return "returned no matching vehicle"
    if "incomplete" in text and "article" in text:
        return "article index was incomplete"
    if "source read failed" in text:
        return "source read failed"
    return "request failed"


def _annotate_article_block(
    block: Any,
    *,
    article_id: str,
    evidence_id: str,
    source_index: int,
    car_id: str,
    connector: AutoAPITwoConnector,
    image_blocks: list[dict[str, Any]],
    path: tuple[int, ...] = (),
) -> None:
    """Attach stable evidence and image identities without flattening tables."""

    if not isinstance(block, dict):
        return
    suffix = ".".join(str(value) for value in (source_index, *path))
    block["evidence_ids"] = [evidence_id]
    block["block_id"] = f"{article_id}:block:{suffix}"
    if block.get("kind") == "image":
        block["url"] = connector.safe_url(block.get("url"), car_id)
        block["image_id"] = sha256(block["url"].encode()).hexdigest()
        image_blocks.append(block)
        return
    if block.get("kind") != "table":
        return
    for row_index, row in enumerate(block.get("rows") or []):
        cells = row.get("blocks") if isinstance(row, dict) else row
        if not isinstance(cells, list):
            continue
        for cell_index, cell in enumerate(cells):
            if isinstance(cell, dict) and isinstance(cell.get("blocks"), list):
                for child_index, cell_block in enumerate(cell["blocks"]):
                    _annotate_article_block(
                        cell_block,
                        article_id=article_id,
                        evidence_id=evidence_id,
                        source_index=source_index,
                        car_id=car_id,
                        connector=connector,
                        image_blocks=image_blocks,
                        path=(row_index, cell_index, child_index),
                    )
            else:
                _annotate_article_block(
                    cell,
                    article_id=article_id,
                    evidence_id=evidence_id,
                    source_index=source_index,
                    car_id=car_id,
                    connector=connector,
                    image_blocks=image_blocks,
                    path=(row_index, cell_index),
                )


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


def _embedded_data(payload):
    embedded = payload.get("_embedded") if isinstance(payload, Mapping) else None
    data = embedded.get("data") if isinstance(embedded, Mapping) else None
    return data if isinstance(data, Mapping) else {}


def _embedded_items(value):
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _self_href(value):
    links = value.get("_links") if isinstance(value, Mapping) else None
    self_link = links.get("self") if isinstance(links, Mapping) else None
    href = self_link.get("href") if isinstance(self_link, Mapping) else None
    return str(href).strip() if href else ""
