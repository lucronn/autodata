from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion import procedure_images as pi  # noqa: E402


def test_localize_procedure_images_stores_local_keys_and_drops_provider_url(monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_fetch(urls, *, provider_id):  # noqa: ARG001
        return {url: b"\x89PNG\r\n\x1a\n" + url.encode() for url in urls}

    def fake_put(storage_key, payload, media_type):  # noqa: ARG001
        stored[storage_key] = payload

    monkeypatch.setattr(pi, "_fetch_urls", fake_fetch)
    monkeypatch.setattr(pi, "_put_object", fake_put)

    article = {
        "images": [
            {
                "image_id": "legacy",
                "url": "https://autoapitwo.vercel.app/fig/oil.png",
                "alt": "oil",
            }
        ],
        "steps": [
            {
                "action": "Remove pump",
                "images": [
                    {
                        "image_id": "legacy",
                        "url": "https://autoapitwo.vercel.app/fig/oil.png",
                    }
                ],
            }
        ],
    }
    localized = pi.localize_procedure_images(article, vehicle={"autoapitwo_vehicle_id": "41215"})
    image = localized["images"][0]
    assert image["storage_key"].startswith("procedure-images/")
    assert image["content_sha256"]
    assert "url" not in image or not str(image.get("url") or "").startswith("https://autoapitwo")
    assert localized["steps"][0]["images"][0]["storage_key"] == image["storage_key"]
    assert stored


def test_hydrate_article_image_urls_uses_artifact_refs_by_default(monkeypatch):
    png = b"\x89PNG\r\n\x1a\nhello"
    monkeypatch.setattr(pi, "_read_storage_bytes", lambda key: png if key else b"")
    article = {
        "images": [
            {
                "image_id": "abc",
                "storage_key": "procedure-images/abc",
                "media_type": "image/png",
                "url": "https://autoapitwo.vercel.app/fig/oil.png",
            }
        ],
        "steps": [
            {
                "images": [
                    {
                        "image_id": "abc",
                        "storage_key": "procedure-images/abc",
                        "media_type": "image/png",
                    }
                ]
            }
        ],
    }
    hydrated = pi.hydrate_article_image_urls(article)
    assert hydrated["images"][0]["url"] == "artifact://abc"
    assert "autoapitwo.vercel.app" not in hydrated["images"][0]["url"]
    assert hydrated["steps"][0]["images"][0]["url"] == "artifact://abc"
    embedded = pi.hydrate_article_image_urls(article, embed_data_uri=True)
    assert embedded["images"][0]["url"].startswith("data:image/png;base64,")


def test_hydrate_strips_provider_host_without_storage():
    article = {
        "images": [{"image_id": "x", "url": "https://autoapitwo.vercel.app/fig/x.png"}],
        "steps": [],
    }
    hydrated = pi.hydrate_article_image_urls(article)
    assert "url" not in hydrated["images"][0]


def test_localization_preserves_associations_originals_and_is_idempotent(monkeypatch):
    from copy import deepcopy
    url = 'https://images.example.org/figure.png'
    image = {'image_id': 'source-figure', 'url': url, 'source_url': url}
    article = {'images': [image], 'steps': [{'image_ids': ['source-figure'], 'images': [image]}],
               'source_original': {'images': [image]}}
    before = deepcopy(article)
    calls = []
    monkeypatch.setattr(pi, '_fetch_urls', lambda urls, **kw: calls.append(urls) or {url: b'\x89PNGfigure'})
    monkeypatch.setattr(pi, '_put_object', lambda *args: None)
    result = pi.localize_procedure_images(article)
    assert result['images'][0]['image_id'] == 'source-figure'
    assert 'source_url' not in result['images'][0]
    assert result['steps'][0]['images'][0]['image_id'] == 'source-figure'
    assert result['source_original'] == before['source_original']
    assert article == before
    assert pi.localize_procedure_images(result) == result
    assert calls == [[url]]


def test_storage_failure_is_local_and_does_not_abort_other_images(monkeypatch):
    urls = ['https://images.example.org/bad.png', 'https://images.example.org/good.png']
    monkeypatch.setattr(pi, '_fetch_urls', lambda urls, **kw: {url: url.encode() for url in urls})
    def put(key, payload, media_type):
        if b'bad.png' in payload:
            raise OSError('storage unavailable')
    monkeypatch.setattr(pi, '_put_object', put)
    result = pi.localize_procedure_images({'images': [{'url': url} for url in urls]})
    assert result['images'][0]['fetch_failed'] is True
    assert 'url' not in result['images'][0]
    assert result['images'][1]['storage_key']


def test_failed_fetch_never_serves_unknown_provider_host(monkeypatch):
    monkeypatch.setattr(pi, '_fetch_urls', lambda *args, **kwargs: {})
    image = {'url': 'https://new-provider.example/figure', 'source_url': 'https://new-provider.example/figure'}
    localized = pi.localize_procedure_images({'images': [image]})
    assert localized['images'][0] == {'fetch_failed': True}
    assert pi.resolve_local_image_url(image) == ''
    assert 'url' not in pi.hydrate_article_image_urls({'images': [image]})['images'][0]


def test_local_storage_read_failure_does_not_fall_back_to_remote(monkeypatch):
    monkeypatch.setattr(pi, '_read_storage_bytes', lambda key: b'')
    assert pi.resolve_local_image_url({'storage_key': 'procedure-images/a', 'url': 'https://cdn.example/a'}) == ''


def test_object_cache_reuses_existing_content_and_uploads_missing(monkeypatch):
    from types import ModuleType, SimpleNamespace
    import pytest

    class S3Error(Exception):
        def __init__(self, code):
            self.code = code

    objects = {}
    writes = []
    def stat(bucket, key):
        if key not in objects:
            raise S3Error('NoSuchKey')
    def put(bucket, key, stream, size, **kwargs):
        objects[key] = stream.read()
        writes.append(key)
    client = SimpleNamespace(stat_object=stat, put_object=put)
    module = ModuleType('minio')
    module.Minio = lambda *args, **kwargs: client
    errors = ModuleType('minio.error')
    errors.S3Error = S3Error
    monkeypatch.setitem(sys.modules, 'minio', module)
    monkeypatch.setitem(sys.modules, 'minio.error', errors)
    monkeypatch.setenv('AUTODATA_S3_ACCESS_KEY', 'test')
    monkeypatch.setenv('AUTODATA_S3_SECRET_KEY', 'test')
    monkeypatch.setattr(pi, 'ensure_versioned_bucket', lambda *args: None)
    first = pi._store_image_bytes('https://provider.example/a.png', b'\x89PNGsame')
    second = pi._store_image_bytes('https://provider.example/b.png', b'\x89PNGsame')
    assert first == second
    assert writes == [first['storage_key']]
    def denied(*args):
        raise S3Error('AccessDenied')
    client.stat_object = denied
    with pytest.raises(S3Error):
        pi._store_image_bytes('https://provider.example/c.png', b'\x89PNGother')
    assert len(writes) == 1


def test_fetch_failure_isolated_and_vehicle_context_forwarded(monkeypatch):
    from autodata_ingestion import autoapitwo_connector
    calls = []
    class Connector:
        def __init__(self, base_url):
            pass
        def read(self, url, **kwargs):
            calls.append((url, kwargs))
            if url == 'bad':
                raise OSError('offline')
            return b'\x89PNGfigure'
    monkeypatch.setattr(autoapitwo_connector, 'AutoAPITwoConnector', Connector)
    assert pi._fetch_urls(['bad', 'good'], provider_id='123') == {'good': b'\x89PNGfigure'}
    assert all(kwargs == {'car_id': '123', 'binary': True} for _, kwargs in calls)


def test_autodbone_signed_asset_is_fetched_from_its_configured_origin(monkeypatch):
    import urllib.request
    from autodata_ingestion import autoapitwo_connector

    url = "https://autodbone-curtt.vercel.app/v1/assets/reference/c2lnbmVk.c2lnbmF0dXJl"
    payload = b"\x89PNG\r\n\x1a\nfigure"
    requests = []

    class Response:
        status = 200
        headers = {"Content-Type": "image/png", "Content-Length": str(len(payload))}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def geturl(self): return url
        def read(self, size=-1):
            nonlocal payload
            if size < 0: size = len(payload)
            chunk, payload = payload[:size], payload[size:]
            return chunk

    class Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return Response()

    def forbidden_autodbtwo(*_args, **_kwargs):
        raise AssertionError("AutoDBone signed assets must not be sent to AutoDBtwo")

    monkeypatch.setenv("AUTODATA_AUTOAPI_BASE_URL", "https://autodbone-curtt.vercel.app")
    monkeypatch.setenv("AUTODATA_SOURCE_REQUEST_HEADERS_JSON", '{"X-Access-Test":"approved"}')
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: Opener())
    monkeypatch.setattr(autoapitwo_connector, "AutoAPITwoConnector", forbidden_autodbtwo)

    fetched = pi._fetch_urls([url], provider_id="")

    assert fetched == {url: b"\x89PNG\r\n\x1a\nfigure"}
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == url
    assert request.get_header("X-access-test") == "approved"
    assert timeout > 0


def test_autodbone_signed_asset_fetch_rejects_other_origins_and_paths(monkeypatch):
    from autodata_ingestion import autoapitwo_connector

    monkeypatch.setenv("AUTODATA_AUTOAPI_BASE_URL", "https://autodbone-curtt.vercel.app")
    monkeypatch.setattr(
        autoapitwo_connector,
        "AutoAPITwoConnector",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not proxy arbitrary URLs")),
    )
    arbitrary = [
        "https://attacker.example/v1/assets/reference/c2lnbmVk.c2lnbmF0dXJl",
        "https://autodbone-curtt.vercel.app/other/c2lnbmVk.c2lnbmF0dXJl",
        "https://autodbone-curtt.vercel.app/v1/assets/reference/a/../b.signature",
    ]
    assert pi._fetch_urls(arbitrary, provider_id="") == {}


def test_autodbone_signed_asset_fetch_rejects_non_image_responses(monkeypatch):
    import urllib.request

    url = "https://autodbone-curtt.vercel.app/v1/assets/reference/c2lnbmVk.c2lnbmF0dXJl"

    class Response:
        headers = {"Content-Type": "text/html"}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def geturl(self): return url
        def read(self, _size=-1): return b"not an image"

    class Opener:
        def open(self, _request, timeout):
            assert timeout > 0
            return Response()

    monkeypatch.setenv("AUTODATA_AUTOAPI_BASE_URL", "https://autodbone-curtt.vercel.app")
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: Opener())
    assert pi._fetch_urls([url], provider_id="") == {}
