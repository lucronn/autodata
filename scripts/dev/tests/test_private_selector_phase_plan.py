import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / "private_selector_phase_plan.py"
spec = importlib.util.spec_from_file_location("phase_plan", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def receipt(self):
        return {"pins": dict(m.PINS), "public_slot_released": False,
                "execution_authorized": False, "public_package_accounted": True,
                "public_install_accounted": True,
                "capacity": {"home_free": 6000000000, "docker_free": 1000000000,
                             "offloaded_free": 1000000000}}

    def test_exact_caps_and_floors_hold_execution(self):
        v = m.plan(self.receipt())
        self.assertEqual(v["private_home_cap"], 134217728)
        self.assertEqual(v["home_admission"], 5637144576)
        self.assertEqual(v["docker_admission"], 947912704)
        self.assertFalse(v["execution_authorized"])
        self.assertFalse(v["public_slot_released"])

    def test_future_public_phases_count_once(self):
        v = self.receipt(); v["public_install_accounted"] = False
        self.assertEqual(m.plan(v)["home_admission"], 5704253440)
        v["public_package_accounted"] = False
        self.assertEqual(m.plan(v)["home_admission"], 5838471168)

    def test_capacity_failure_is_not_execution_authority(self):
        for key in ("home_free", "docker_free", "offloaded_free"):
            v = self.receipt(); v["capacity"][key] = 0
            self.assertEqual(m.plan(v)["status"], "VALID_DRY_PLAN_CAPACITY_BLOCKED")
            self.assertFalse(m.plan(v)["execution_authorized"])

    def test_pin_release_and_execution_drift_refused(self):
        for key in ("execution_authorized", "public_slot_released"):
            v = self.receipt(); v[key] = True
            with self.assertRaises(ValueError): m.plan(v)
        v = self.receipt(); v["pins"]["image"] = "unexpected"
        with self.assertRaises(ValueError): m.plan(v)

    def test_boolean_capacity_and_ambiguous_accounting_refused(self):
        v = self.receipt(); v["capacity"]["home_free"] = True
        with self.assertRaises(ValueError): m.plan(v)
        v = self.receipt(); v["public_install_accounted"] = 1
        with self.assertRaises(ValueError): m.plan(v)

    def test_receipt_is_private_single_regular_file(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "r.json"; p.write_text(json.dumps(self.receipt())); p.chmod(0o600)
            self.assertEqual(m.load_receipt(p), self.receipt())
            q = Path(folder) / "link"; q.symlink_to(p)
            with self.assertRaises(OSError): m.load_receipt(q)
            p.chmod(0o644)
            with self.assertRaises(ValueError): m.load_receipt(p)
            p.chmod(0o600); p.write_bytes(b"x" * 65537)
            with self.assertRaises(ValueError): m.load_receipt(p)

    def test_cli_rejects_execution_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): m.main(["--execute", "--receipt", "missing"])

    def test_initial_probe_and_activation_are_separate_review_gates(self):
        v = m.plan(self.receipt())
        self.assertEqual(v["phase_order"][-1]["phase"], "initial_probe_separate")
        self.assertTrue(any("activator" in x for x in v["phase_order"][-2]["requires"]))
        self.assertTrue(any("START/FIN" in x for x in v["phase_order"][-1]["requires"]))


if __name__ == "__main__":
    unittest.main()
