import json
import os
import unittest
from unittest.mock import patch

from autodata_ingestion.mercury2 import (
    Mercury2Client,
    Mercury2SourceExtractor,
    Mercury2VehicleAdjudicator,
    PROCEDURE_COMPOSITION_SCHEMA,
)
from autodata_ingestion.source_adapters import SourceResource
from autodata_ingestion.vehicle_identity import canonicalize_vehicle_observation


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


class Mercury2Tests(unittest.TestCase):
    def test_procedure_schema_requires_provenance_and_structured_warnings(self):
        step_schema = PROCEDURE_COMPOSITION_SCHEMA["properties"]["steps"]["items"]
        warning_schema = PROCEDURE_COMPOSITION_SCHEMA["properties"]["warnings"]["items"]

        self.assertIn("operation_id", step_schema["required"])
        self.assertEqual(step_schema["additionalProperties"], False)
        self.assertEqual(warning_schema["additionalProperties"], False)
        self.assertEqual(
            warning_schema["required"],
            ["warning_id", "message", "source_article_ids", "evidence_ids", "requires_review"],
        )

    def test_source_extractor_returns_validated_typed_candidates(self):
        class FakeClient:
            def complete_json(self, prompt):
                self.prompt = prompt
                return {
                    "candidates": [
                        {
                            "kind": "article",
                            "key": "article:TSB-42:llm",
                            "locator": "body.records[0]",
                            "data": {
                                "id": "TSB-42",
                                "title": "Brake connector bulletin",
                                "body": "Inspect the brake connector.",
                            },
                        }
                    ]
                }

        resource = SourceResource.from_bytes(
            "provider://source/unknown.json",
            "source-v1",
            b'{"body":{"providerSpecificArticle":{"headline":"Brake connector bulletin"}}}',
            "application/json",
        )
        client = FakeClient()

        candidates = Mercury2SourceExtractor(client).extract(resource)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].kind, "article")
        self.assertEqual(candidates[0].data["id"], "TSB-42")
        self.assertIn("provider://source/unknown.json", client.prompt)

    def test_source_extractor_rejects_non_object_model_output(self):
        class FakeClient:
            def complete_json(self, prompt):
                return []

        resource = SourceResource.from_bytes(
            "provider://source/unknown.json",
            "source-v1",
            b"{}",
            "application/json",
        )

        with self.assertRaisesRegex(ValueError, "response must be a JSON object"):
            Mercury2SourceExtractor(FakeClient()).extract(resource)

    def test_source_extractor_rejects_non_string_candidate_kind(self):
        class FakeClient:
            def complete_json(self, prompt):
                return {"candidates": [{"kind": ["article"], "locator": "body", "data": {}}]}

        resource = SourceResource.from_bytes(
            "provider://source/unknown.json",
            "source-v1",
            b"{}",
            "application/json",
        )

        with self.assertRaisesRegex(ValueError, "unsupported kind"):
            Mercury2SourceExtractor(FakeClient()).extract(resource)

    def test_source_extractor_rejects_missing_kind_specific_fields(self):
        class FakeClient:
            def complete_json(self, prompt):
                return {"candidates": [{"kind": "document", "locator": "body", "data": {}}]}

        resource = SourceResource.from_bytes(
            "provider://source/unknown.json",
            "source-v1",
            b"{}",
            "application/json",
        )

        with self.assertRaisesRegex(ValueError, "document requires documentId"):
            Mercury2SourceExtractor(FakeClient()).extract(resource)

    def test_source_extractor_rejects_invalid_vehicle_identity_values(self):
        class FakeClient:
            def complete_json(self, prompt):
                return {
                    "candidates": [
                        {
                            "kind": "vehicle_identity",
                            "locator": "body.vehicle",
                            "data": {"year": "unknown", "make": "Chevrolet", "model": "Silverado 1500"},
                        }
                    ]
                }

        resource = SourceResource.from_bytes(
            "provider://source/unknown.json",
            "source-v1",
            b"{}",
            "application/json",
        )

        with self.assertRaisesRegex(ValueError, "invalid vehicle identity"):
            Mercury2SourceExtractor(FakeClient()).extract(resource)

    def test_client_reads_key_only_from_environment_and_parses_json(self):
        seen = {}

        def transport(request, timeout):
            seen["authorization"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        with patch.dict(os.environ, {"INCEPTION_API_KEY": "test-key", "INCEPTION_API_BASE_URL": "https://example.test/v1"}, clear=False):
            result = Mercury2Client.from_environment(transport=transport).complete_json("select")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(seen["authorization"], "Bearer test-key")

    def test_client_defaults_to_official_inception_api_base(self):
        seen = {}

        def transport(request, timeout):
            del timeout
            seen["url"] = request.full_url
            seen["payload"] = json.loads(request.data)
            return FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        with patch.dict(os.environ, {"INCEPTION_API_KEY": "test-key"}, clear=True):
            Mercury2Client.from_environment(transport=transport).complete_json("select")

        self.assertEqual(
            seen["url"],
            "https://api.inceptionlabs.ai/v1/chat/completions",
        )

        self.assertEqual(seen["payload"]["max_tokens"], 8192)
        self.assertEqual(seen["payload"]["model"], "mercury-2")

    def test_client_sends_environment_output_token_budget(self):
        seen = {}

        def transport(request, timeout):
            seen["payload"] = json.loads(request.data)
            return FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        with patch.dict(os.environ, {
            "INCEPTION_API_KEY": "test-key",
            "INCEPTION_MAX_TOKENS": "2048",
        }, clear=True):
            Mercury2Client.from_environment(transport=transport).complete_json("select")

        self.assertEqual(seen["payload"]["max_tokens"], 2048)

    def test_client_rejects_invalid_environment_output_token_budget_before_transport(self):
        def transport(request, timeout):
            self.fail("invalid token budget reached transport")

        for value in ("0", "32769", "abc"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "INCEPTION_API_KEY": "test-key",
                "INCEPTION_MAX_TOKENS": value,
            }, clear=True):
                with self.assertRaises(ValueError):
                    Mercury2Client.from_environment(transport=transport).complete_json("select")

    def test_adjudicator_accepts_only_a_supplied_high_confidence_candidate(self):
        def transport(_request, timeout):
            return FakeResponse({"selected_candidate_key": "chevrolet-silverado-1500-1999-us-drivetrain-2wd-engine-5-3l", "confidence": 0.99})

        client = Mercury2Client(api_key="test-key", base_url="https://example.test", transport=transport)
        observation = canonicalize_vehicle_observation({"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "engine": "5.3L"})
        result = Mercury2VehicleAdjudicator(client).adjudicate(
            observation,
            [
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "engine": "5.3L", "drivetrain": "2WD"},
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "engine": "5.3L", "drivetrain": "4WD"},
            ],
        )
        self.assertEqual(result.status, "matched")
        self.assertEqual(result.selected_candidate_key, "chevrolet-silverado-1500-1999-us-drivetrain-2wd-engine-5-3l")

    def test_invalid_model_output_stays_in_review(self):
        def invalid_transport(_request, timeout):
            return FakeResponse({"selected_candidate_key": "not-a-candidate", "confidence": 1.0})

        client = Mercury2Client(api_key="test-key", base_url="https://example.test", transport=invalid_transport)
        observation = canonicalize_vehicle_observation({"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US"})
        result = Mercury2VehicleAdjudicator(client).adjudicate(
            observation,
            [
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD"},
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "4WD"},
            ],
        )
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.reason, "mercury_invalid_candidate")

    def test_procedure_schema_is_exposed_for_constrained_composition(self):
        from autodata_ingestion.mercury2 import PROCEDURE_COMPOSITION_SCHEMA

        self.assertEqual(PROCEDURE_COMPOSITION_SCHEMA["type"], "object")
        self.assertIn("steps", PROCEDURE_COMPOSITION_SCHEMA["required"])
        self.assertEqual(
            PROCEDURE_COMPOSITION_SCHEMA["properties"]["steps"]["items"]["properties"]["category"]["enum"],
            ["required", "recommended"],
        )

    def test_procedure_prompt_carries_structured_evidence_context(self):
        from autodata_ingestion.mercury2 import compose_procedure_draft

        class FakeClient:
            def complete_json(self, prompt):
                self.prompt = prompt
                return {"title": "Service", "steps": [], "warnings": []}

        client = FakeClient()
        compose_procedure_draft(
            client,
            vehicle={"year": 1999, "make": "Chevrolet", "model": "Silverado 1500"},
            quote={"labor": {"operations": []}, "procedure": {"warnings": []}},
            articles=[{
                "article_id": "article-1",
                "evidence": [{
                    "evidence_id": "evidence-1",
                    "excerpt": "Use the specified tool.",
                    "locator": "body.steps[1]",
                    "source_uri": "https://source.test/article.html",
                    "source_watermark": "source-v2",
                }],
            }],
        )

        payload = json.loads(client.prompt)
        self.assertEqual(payload["articles"][0]["evidence"][0]["excerpt"], "Use the specified tool.")
        self.assertEqual(payload["articles"][0]["evidence"][0]["locator"], "body.steps[1]")
        self.assertEqual(payload["articles"][0]["evidence"][0]["source_uri"], "https://source.test/article.html")
        self.assertEqual(payload["articles"][0]["evidence"][0]["source_watermark"], "source-v2")


if __name__ == "__main__":
    unittest.main()


def test_mercury_rejects_oversized_actual_byte_stream():
    import io
    import pytest
    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self,*args): self.close()
    client=Mercury2Client(api_key="fixture",base_url="http://127.0.0.1",transport=lambda *a,**k:Response(b" "*(1024*1024+1)))
    with pytest.raises(ValueError,match="response exceeds"):
        client.complete_json("fixture")


def test_mercury_rejects_oversized_prompt_before_transport():
    import pytest
    def never(*a,**k): pytest.fail("oversized prompt sent")
    client=Mercury2Client(api_key="fixture",base_url="http://127.0.0.1",transport=never)
    with pytest.raises(ValueError,match="prompt exceeds"):
        client.complete_json("x"*(200*1024+1))
