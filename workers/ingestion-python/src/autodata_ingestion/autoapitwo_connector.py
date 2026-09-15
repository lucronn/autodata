"""Read-only, vehicle-scoped access to AutoAPI Two repair content."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from threading import RLock
import time
from urllib.parse import quote, urljoin, urlsplit, unquote
from urllib.request import build_opener, HTTPRedirectHandler, Request


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

    def flush(self):
        value = re.sub(r"\s+", " ", "".join(self._text)).strip()
        self._text = []
        if value:
            self.blocks.append({"kind": "text", "text": value})

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self._skip += 1
        if self._skip:
            return
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.flush()
        if tag == "td":
            self._text.append(" | ")
        if tag == "a":
            if attrs.get("class") == "image":
                self._image_link += 1
            elif attrs.get("href"):
                self.links.append(attrs["href"])
        if tag == "img" and attrs.get("src"):
            self.flush()
            self.blocks.append({"kind": "image", "url": attrs["src"], "alt": attrs.get("alt", ""), "name": attrs.get("img_name", "")})

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
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
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("source base must be an HTTPS origin")
        if min(timeout, max_bytes, cache_entries, cache_ttl, retry_attempts) <= 0 or retry_delay < 0 or retry_after_cap < 0:
            raise ValueError("source limits must be positive")
        self.base = base_url.rstrip("/")
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
            for attempt in range(self.retry_attempts):
                cooldown = self._retry_at - time.monotonic()
                if cooldown > 0:
                    time.sleep(cooldown)
                try:
                    with self.opener(Request(url, headers={"Accept": "image/*" if binary else "application/json"}), timeout=self.timeout) as response:
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

    def search(self, car_id, term):
        result = self.read(f'/api/v1/content/carids/{car_id}/search/{quote(term, safe="")}', car_id=car_id)
        values = result.get('_embedded', {}).get('data', {}).get('results', [])
        return values if isinstance(values, list) else []

    def article(self, car_id, href, *, title=None):
        url = self.safe_url(href, car_id)
        result = self.read(url, car_id=car_id)
        if str(result.get('car', {}).get('id', '')) != str(car_id):
            raise SourceUnavailable('article vehicle does not match request')
        article = result.get('_embedded', {}).get('data', {}).get('article', {})
        html = article.get('content')
        if not isinstance(html, str) or not html.strip():
            raise SourceUnavailable('repair article has no instructions')
        parser = ArticleParser()
        parser.feed(html)
        parser.flush()
        digest = sha256(html.encode()).hexdigest()
        article_id = f'autoapitwo:{car_id}:{result.get("id", digest)}'
        evidence_id = f'{article_id}:{digest}'
        for index, block in enumerate(parser.blocks):
            block['evidence_ids'] = [evidence_id]
            block['block_id'] = f'{article_id}:block:{index}'
            if block['kind'] == 'image':
                block['url'] = self.safe_url(block['url'], car_id)
                block['image_id'] = sha256(block['url'].encode()).hexdigest()
        return {
            'article_id': article_id, 'title': title or result.get('title', ''),
            'provider': 'autoapitwo', 'provider_vehicle_id': str(car_id),
            'vehicle': result['car'], 'source_uri': url, 'source_watermark': digest,
            'raw_html': html, 'body': '\n'.join(b['text'] for b in parser.blocks if b['kind'] == 'text'),
            'blocks': parser.blocks, 'images': [b for b in parser.blocks if b['kind'] == 'image'],
            'component_links': list(dict.fromkeys(self.safe_url(link, car_id) for link in parser.links)),
            'evidence_ids': [evidence_id],
            'evidence': [{'evidence_id': evidence_id, 'source_uri': url, 'content_hash': digest}],
        }
