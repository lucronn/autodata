import json
import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(ROOT / "scripts/contracts"))

from autodata_contracts import contracts  # noqa: E402
from generate import (  # noqa: E402
    is_backward_compatible_addition,
    load_contract,
    render_go,
    render_python,
    write_generated,
)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_contract(ROOT / "packages/contracts/contract.json")

    def test_canonical_source_declares_dataset_read_required_fields(self):
        self.assertEqual(
            self.source["dataset_read"]["required"],
            ["dataset_id", "revision_id", "availability", "source_watermark", "sections"],
        )

    def test_python_binding_matches_canonical_enums_and_subjects(self):
        self.assertEqual(contracts.SCHEMA_VERSION, self.source["schema_version"])
        self.assertEqual(
            contracts.DATASET_AVAILABILITY_VALUES,
            tuple(self.source["dataset_availability"]),
        )
        self.assertEqual(contracts.EVENT_SUBJECTS, tuple(self.source["event_subjects"]))
        self.assertEqual(
            contracts.ENTITLEMENT_STATUS_VALUES,
            tuple(self.source["entitlement"]["properties"]["status"]["enum"]),
        )
        self.assertEqual(
            contracts.FEEDBACK_CATEGORY_VALUES,
            tuple(self.source["feedback"]["properties"]["category"]["enum"]),
        )
        self.assertEqual(
            contracts.ERROR_CODE_VALUES,
            tuple(self.source["error"]["properties"]["code"]["enum"]),
        )

    def test_generated_bindings_match_canonical_source(self):
        self.assertEqual(
            render_go(self.source),
            (ROOT / "packages/contracts/go/contracts.go").read_text(),
        )

    def test_python_binding_exposes_request_access_evidence_feedback_and_error_types(self):
        for type_name in ("DatasetRequest", "Entitlement", "Evidence", "Feedback", "Error"):
            self.assertTrue(hasattr(contracts, type_name), type_name)
        self.assertEqual(
            render_python(self.source),
            (ROOT / "packages/contracts/python/autodata_contracts/contracts.py").read_text(),
        )

    def test_optional_property_is_backward_compatible_but_required_property_is_not(self):
        old = {"required": ["dataset_id"], "properties": {"dataset_id": {}}}
        optional_addition = {
            "required": ["dataset_id"],
            "properties": {"dataset_id": {}, "warnings": {"type": "array"}},
        }
        required_addition = {
            "required": ["dataset_id", "warnings"],
            "properties": {"dataset_id": {}, "warnings": {"type": "array"}},
        }
        self.assertTrue(is_backward_compatible_addition(old, optional_addition))
        self.assertFalse(is_backward_compatible_addition(old, required_addition))

    def test_contract_source_is_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as fixture:
            json.dump(self.source, fixture)
            fixture.flush()
            self.assertEqual(load_contract(Path(fixture.name)), self.source)

    def test_generated_output_is_replaced_as_one_complete_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "generated.py"
            write_generated(output, "complete contract")
            self.assertEqual(output.read_text(), "complete contract")


if __name__ == "__main__":
    unittest.main()
