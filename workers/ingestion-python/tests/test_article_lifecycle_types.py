import dataclasses
from uuid import uuid4
import pytest


def test_identity_preserves_provider_and_exact_opaque_scope():
    from autodata_ingestion.article_lifecycle_types import (
        ArticleKey,
        article_id,
        identity_payload,
        ResourceRef,
    )

    key = ArticleKey("bankone", uuid4(), None, " pref:Vehicle/1 ", "some/Ref")
    assert identity_payload(key)["source_vehicle_ref"] == " pref:Vehicle/1 "
    assert article_id(key) != article_id(dataclasses.replace(key, provider="banktwo"))
    assert article_id(key) != article_id(
        dataclasses.replace(key, source_article_ref="some/ref")
    )
    assert ResourceRef("bankone", "same") != ResourceRef("banktwo", "same")
    with pytest.raises(ValueError):
        ArticleKey("bankone", key.vehicle_id, None, "v", "bad\x7f")


def test_explicit_v2_has_distinct_transformation_key_and_v1_remains_default():
    from autodata_ingestion.article_lifecycle_types import REWRITE_PROFILE_VERSION, transformation_key
    assert REWRITE_PROFILE_VERSION == "technical-prose-v1"
    article = uuid4()
    v1 = transformation_key(article, "same-source", "ordered-article-v1", REWRITE_PROFILE_VERSION)
    v2 = transformation_key(article, "same-source", "ordered-article-v1", "technical-prose-v2")
    assert v1 != v2


def test_projection_key_preserves_historical_digest_and_separates_v2():
    from uuid import UUID
    from autodata_ingestion.article_lifecycle_types import transformation_key

    args = (UUID('12345678-1234-5678-1234-567812345678'), 'a' * 64,
            'ordered-article-v1', 'technical-prose-v1')
    historical = '5e02c89f1549a79e2719e22c5798635b72b00d773923e824cf51ed2c2262a833'
    assert transformation_key(*args) == historical
    assert transformation_key(*args, projection_version='source-projection-v1') == historical
    assert transformation_key(*args, projection_version='source-projection-v2') == (
        '20d541e2bc559477341d9695042bd0bcebf7f734eb2e3670d04a7209518c6535'
    )
    with pytest.raises(ValueError, match='projection'):
        transformation_key(*args, projection_version='source-projection-v3')


def test_captured_source_retains_legacy_constructor_default_and_explicit_v2():
    from datetime import datetime, timezone
    from autodata_ingestion.article_lifecycle_types import CapturedSource

    # Legacy callers omit the appended metadata; raw identity and payload survive.
    captured = CapturedSource(None, 'a' * 64, uuid4(), (), [], [],
                              {'blocks': []}, [], 'body', [], [], 'readable',
                              datetime.now(timezone.utc))
    assert captured.projection_version == 'source-projection-v1'
    upgraded = dataclasses.replace(captured, projection_version='source-projection-v2')
    assert upgraded.projection_version == 'source-projection-v2'
    assert dataclasses.asdict(upgraded) | {'projection_version': 'source-projection-v1'} == dataclasses.asdict(captured)
