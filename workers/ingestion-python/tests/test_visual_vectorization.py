import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.visual_vectorization import (  # noqa: E402
    DeterministicLocalVectorizer,
    ObjectStorageSourceDiagramVectorizer,
    vectorize_source_diagram,
)


class FakeObjectStorage:
    def __init__(self):
        self.objects = {}

    def put_object(self, bucket, key, stream, length, content_type=None):
        self.objects[(bucket, key)] = {
            "bytes": stream.read(length),
            "content_type": content_type,
        }


def test_deterministic_local_vectorizer_returns_repeatable_renderable_unreviewed_svg():
    vectorizer = DeterministicLocalVectorizer()

    image_bytes = b"\x89PNG\r\n\x1a\nsource diagram bytes"
    first = vectorizer.redraw(image_bytes, source_uri="https://source.test/brakes.png")
    second = vectorizer.redraw(image_bytes, source_uri="https://source.test/brakes.png")

    assert first == second
    assert first["media_type"] == "image/svg+xml"
    assert first["renderable"] is True
    assert first["review_state"] == "pending"
    assert first["label"] == "AI-enhanced / UNREVIEWED"
    assert first["source_artifact_id"].startswith("visual-source:")
    assert first["derived_artifact_id"].startswith("visual-derived:")
    assert first["svg"].startswith("<svg")
    assert "https://source.test/brakes.png" in first["svg"]


def test_text_only_vector_request_is_rejected_without_source_visual_bytes():
    with pytest.raises(ValueError, match="source visual"):
        vectorize_source_diagram(
            {"text": "A brake line runs from the master cylinder to the caliper."},
            vectorizer=DeterministicLocalVectorizer(),
        )


def test_non_image_source_bytes_are_rejected_even_when_uri_looks_like_an_image():
    with pytest.raises(ValueError, match="image"):
        DeterministicLocalVectorizer().redraw(
            b"this is text pretending to be a PNG",
            source_uri="https://source.test/brakes.png",
        )


def test_object_storage_adapter_writes_original_and_derived_objects():
    storage = FakeObjectStorage()
    adapter = ObjectStorageSourceDiagramVectorizer(
        storage,
        DeterministicLocalVectorizer(),
        bucket="autodata-visuals",
    )

    result = adapter.redraw(b"\x89PNG\r\n\x1a\nbytes", source_uri="https://source.test/brakes.png")

    assert result["source_object_key"].startswith("source/")
    assert result["derived_object_key"].startswith("derived/")
    assert result["review_state"] == "pending"
    assert result["source_artifact_id"].startswith("visual-source:")
    assert result["derived_artifact_id"].startswith("visual-derived:")
    assert ("autodata-visuals", result["source_object_key"]) in storage.objects
    assert ("autodata-visuals", result["derived_object_key"]) in storage.objects
    assert storage.objects[("autodata-visuals", result["derived_object_key"])]["content_type"] == "image/svg+xml"
