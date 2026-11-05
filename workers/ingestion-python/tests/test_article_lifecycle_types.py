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
