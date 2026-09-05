import json
import os
import unittest
from unittest.mock import patch

from autodata_ingestion.mercury2 import Mercury2Client, Mercury2VehicleAdjudicator
from autodata_ingestion.vehicle_identity import canonicalize_vehicle_observation


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.payload


class Mercury2Tests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
