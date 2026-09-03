import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.projection import (  # noqa: E402
    build_viewable_content,
    required_sections_ready,
    viewable_sections,
)
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


def bundle_with_parts():
    resources = [
        SourceResource.from_bytes(
            "provider://vehicle/name",
            "source-v1",
            b'{"body":"2019 Cadillac Escalade ESV - 2WD"}',
            "application/json",
        ),
        SourceResource.from_bytes(
            "provider://vehicle/parts",
            "source-v1",
            b'{"body":[{"partNumber":"p1","partDescription":"Filter","price":"$1.00"}]}',
            "application/json",
        ),
    ]
    artifacts = [adapt_source_resource(resource) for resource in resources]
    return normalize_source_bundle(artifacts, "US"), artifacts


class ProjectionTests(unittest.TestCase):
    def test_viewable_content_is_deterministic_and_evidence_linked(self):
        bundle, artifacts = bundle_with_parts()

        content = build_viewable_content(bundle, artifacts)

        self.assertEqual(content["vehicle_identity"]["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(content["source_metadata"]["artifacts"][0]["source_uri"], "provider://vehicle/name")
        self.assertEqual(content["parts"][0]["evidence_id"], bundle.parts[0]["evidence_id"])
        self.assertEqual(content, build_viewable_content(bundle, artifacts))

    def test_viewable_sections_require_explicit_core_facts(self):
        bundle, artifacts = bundle_with_parts()

        sections = viewable_sections(bundle, artifacts)

        self.assertEqual(sections, {"vehicle_identity", "source_metadata", "parts"})
        self.assertTrue(required_sections_ready(sections, ("vehicle_identity", "source_metadata")))
        self.assertFalse(required_sections_ready(sections, ("vehicle_identity", "specifications")))

    def test_specifications_are_projected_when_the_source_provides_them(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/specifications",
            "source-v1",
            b'{"body":{"make":"Cadillac","model":"Escalade ESV","year":2019,"specifications":{"engine":{"value":"6.2L","unit":"L"}}}}',
            "application/json",
        )
        artifact = adapt_source_resource(resource)
        bundle = normalize_source_bundle([artifact], "US")

        content = build_viewable_content(bundle, [artifact])

        self.assertEqual(content["specifications"][0]["name"], "engine")
        self.assertIn("specifications", viewable_sections(bundle, [artifact]))

    def test_content_rejects_a_bundle_without_vehicle_identity(self):
        bundle, artifacts = bundle_with_parts()
        bundle = bundle.__class__(
            status=bundle.status,
            vehicle=None,
            specifications=bundle.specifications,
            models=bundle.models,
            powertrains=bundle.powertrains,
            parts=bundle.parts,
            articles=bundle.articles,
            documents=bundle.documents,
            diagrams=bundle.diagrams,
            evidence=bundle.evidence,
            quarantined=bundle.quarantined,
            conflicts=bundle.conflicts,
        )

        with self.assertRaisesRegex(ValueError, "vehicle identity"):
            build_viewable_content(bundle, artifacts)


if __name__ == "__main__":
    unittest.main()
