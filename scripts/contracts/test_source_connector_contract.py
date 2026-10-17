import base64
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).parents[2]
CONTRACT = ROOT / "packages/contracts/source-connector/v1/openapi.yaml"
FIXTURES = CONTRACT.parent / "fixtures"


def validate_named(document, name, instance):
    document_id = "https://cars.tk/contracts/source-connector/v1/openapi-schema.json"
    registry = Registry().with_resource(
        document_id, Resource.from_contents(document, default_specification=DRAFT202012)
    )
    Draft202012Validator(
        {"$ref": f"{document_id}#/components/schemas/{name}"}, registry=registry
    ).validate(instance)


class SourceConnectorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = yaml.safe_load(CONTRACT.read_text())

    def test_required_paths_and_operations_are_versioned(self):
        paths = self.document["paths"]
        self.assertTrue(all(path.startswith("/v1/") or path in {"/healthz", "/readyz"} for path in paths))
        self.assertEqual(paths["/v1/capabilities"]["get"]["operationId"], "capabilities")
        self.assertEqual(paths["/v1/vehicle-resolutions"]["post"]["operationId"], "resolveVehicle")
        self.assertEqual(paths["/v1/resources/{opaqueRef}"]["get"]["operationId"], "readResource")
        resource_response = paths["/v1/resources/{opaqueRef}"]["get"]["responses"]["200"]
        for name in ("X-Request-Id", "X-Provider", "X-Source-Revision", "X-Fetched-At", "X-Source-Locator", "X-Source-Sha256", "X-Source-Media-Type"):
            header = resource_response["headers"][name]
            if "$ref" in header:
                header = self.document["components"]["headers"][header["$ref"].rsplit("/", 1)[-1]]
            self.assertTrue(header.get("required"), name)
        json_schema = resource_response["content"]["application/json"]["schema"]
        self.assertEqual(len(json_schema["oneOf"]), 2)

    def test_fixtures_validate_and_cover_pagination_and_ambiguity(self):
        catalog = json.loads((FIXTURES / "catalog-page.json").read_text())
        complete_catalog = json.loads((FIXTURES / "catalog-complete.json").read_text())
        resolution = json.loads((FIXTURES / "vehicle-resolution.json").read_text())
        articles = json.loads((FIXTURES / "articles.json").read_text())
        text_resource = json.loads((FIXTURES / "text-resource.json").read_text())
        binary_resource = json.loads((FIXTURES / "binary-resource.json").read_text())
        error = json.loads((FIXTURES / "error.json").read_text())
        validate_named(self.document, "CatalogResponse", catalog)
        validate_named(self.document, "CatalogResponse", complete_catalog)
        validate_named(self.document, "VehicleResolutionResponse", resolution)
        validate_named(self.document, "ArticleListResponse", articles)
        validate_named(self.document, "TextResource", text_resource)
        validate_named(self.document, "BinaryResource", binary_resource)
        self.assertEqual(
            text_resource["sha256"],
            hashlib.sha256(text_resource["content"].encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            binary_resource["sha256"],
            hashlib.sha256(base64.b64decode(binary_resource["content_base64"])).hexdigest(),
        )
        validate_named(self.document, "ErrorResponse", error)
        self.assertFalse(catalog["complete"])
        self.assertIn("region", complete_catalog["items"][0])
        self.assertEqual(len(resolution["candidates"]), 2)
        self.assertEqual(error["error"]["code"], "AMBIGUOUS")

    def test_capabilities_fixture_has_no_unknown_envelope_fields(self):
        capabilities = {
            "request_id": "00000000-0000-4000-8000-000000000008",
            "provider": "bankone",
            "source_revision": "fixture",
            "fetched_at": "2026-10-08T12:00:00Z",
            "capabilities": ["catalog", "resource_read"],
        }
        validate_named(self.document, "CapabilitiesResponse", capabilities)

    def test_resource_hashes_are_content_hashes_and_secrets_are_absent(self):
        content = b"redacted source article"
        digest = hashlib.sha256(content).hexdigest()
        resource = {
            "request_id": "00000000-0000-4000-8000-000000000004",
            "provider": "bankone",
            "source_revision": "fixture",
            "fetched_at": "2026-10-08T12:00:00Z",
            "kind": "asset",
            "media_type": "application/octet-stream",
            "content_base64": base64.b64encode(content).decode(),
            "sha256": digest,
        }
        validate_named(self.document, "BinaryResource", resource)
        encoded = json.dumps(resource).lower()
        self.assertNotRegex(encoded, re.compile(r"(cookie|authorization|password|secret|token|database|db_id)"))
        self.assertEqual(hashlib.sha256(base64.b64decode(resource["content_base64"])).hexdigest(), resource["sha256"])

    def test_schema_rejects_missing_required_fields_and_unknown_secret_fields(self):
        with self.assertRaises(Exception):
            validate_named(self.document, "CatalogResponse", {"provider": "bankone"})
        bad = json.loads((FIXTURES / "catalog-page.json").read_text())
        bad["authorization"] = "redacted"
        with self.assertRaises(Exception):
            validate_named(self.document, "CatalogResponse", bad)
        error = json.loads((FIXTURES / "error.json").read_text())
        for key in (
            "Authorization",
            "access_token",
            "database_id",
            "dbId",
            "connection_string",
            "password_hash",
            "nested",
        ):
            bad_error = json.loads(json.dumps(error))
            bad_error["error"]["details"] = {key: "redacted"}
            with self.assertRaises(Exception, msg=key):
                validate_named(self.document, "ErrorResponse", bad_error)

    def test_page_cursor_and_completeness_are_disjoint(self):
        base = {
            "request_id": "00000000-0000-4000-8000-000000000009",
            "provider": "bankone",
            "source_revision": "fixture",
            "fetched_at": "2026-10-08T12:00:00Z",
            "scope": "years",
            "items": [],
        }
        validate_named(self.document, "CatalogResponse", {**base, "complete": True})
        validate_named(
            self.document,
            "CatalogResponse",
            {**base, "complete": False, "next_cursor": "next"},
        )
        for page_fields in (
            {"complete": True, "next_cursor": "next"},
            {"complete": False},
            {"complete": False, "next_cursor": ""},
        ):
            with self.assertRaises(Exception, msg=str(page_fields)):
                validate_named(self.document, "CatalogResponse", {**base, **page_fields})


if __name__ == "__main__":
    unittest.main()
