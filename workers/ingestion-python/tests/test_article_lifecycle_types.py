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
