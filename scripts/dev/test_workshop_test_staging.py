import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import sys

import workshop_test_staging as staging


def profile():
    return {"origin": "https://workshop-test.example.org", "tester_uids": ["registered-test-uid"],
            "firebase": {"project_id": "fixture-project", "api_key": "public-firebase-key", "app_id": "1:123:web:a123", "auth_domain": "fixture-project.firebaseapp.com"},
            "stripe": {"account_id": "acct_fixture", "price_id": "price_fixture"},
            "source_sha": "a" * 40, "binary_sha256": "b" * 64, "enabled": False}


class StagingTest(unittest.TestCase):
    def test_isolated_disabled_defaults_and_secret_absence(self):
        c = staging.render(profile())
        self.assertEqual(c["name"], staging.PROJECT)
        self.assertTrue(c["networks"]["internal"]["internal"])
        for name, s in c["services"].items():
            self.assertEqual(s["restart"], "no")
            self.assertNotIn("build", s)
            self.assertTrue(s["image"].startswith("sha256:"))
            for v in s["volumes"]:
                self.assertTrue(v["source"].startswith(str(staging.RUNTIME_ROOT) + "/"))
                self.assertFalse(v["bind"]["create_host_path"])
            if name in {"api", "ingestion-http"}:
                self.assertEqual(s["environment"]["AUTODATA_COMMERCE_MODE"], "disabled")
                for key in staging.INHERITED_CLEAR | set().union(*staging.ROLE_KEYS.values()):
                    if name != "api" or key not in staging.PUBLIC_KEYS["api"]:
                        self.assertEqual(s["environment"][key], "")
            else:
                self.assertEqual(s["networks"], ["internal"])
                self.assertNotIn("ports", s)
        p = c["services"]["api"]["ports"]
        self.assertEqual(p, [{"target": 8080, "published": "3043", "host_ip": "127.0.0.1", "protocol": "tcp"}])
        self.assertFalse(json.loads(c["services"]["ingestion-http"]["environment"]["AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"])["enabled"])

    def test_test_enablement_is_equal_and_notices_are_same_origin(self):
        p = profile(); p["enabled"] = True
        c = staging.render(p)
        for role in ["api", "ingestion-http"]:
            self.assertEqual(c["services"][role]["environment"]["AUTODATA_COMMERCE_MODE"], "stripe_test")
        n = json.loads(c["services"]["ingestion-http"]["environment"]["AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"])
        self.assertTrue(n["enabled"])
        for key in ["terms", "privacy", "refund", "contact"]:
            self.assertEqual(n[key+"_url"], p["origin"] + "/workshop/test-notices/" + key)
        p["tester_uids"] = ["$AMBIENT_VARIABLE"]
        self.assertIn("$$AMBIENT_VARIABLE", staging.render(p)["services"]["api"]["environment"]["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"])

    def test_origin_tester_and_shared_root_denials(self):
        for origin in ["https://cars.tk", "https://autodata.cars.tk", "https://autodata.curtis.click", "http://localhost:3013", "https://example.org/path", "https://example.org:443", "https://user@example.org", "https://example.org."]:
            p = profile(); p["origin"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError): staging.render(p)
        for ids in [[], ["same", "same"], [""], ["bad\nuid"], [1], ["u"]*101]:
            p = profile(); p["tester_uids"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError): staging.render(p)
        with self.assertRaises(ValueError): staging.render(profile(), Path("/home/corp/autodata/production"))

    def test_private_material_denials_do_not_expose_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "private.json"
            valid = {k: "private-test-value" for k in staging.COMMON}
            valid.update({"AUTODATA_STRIPE_SECRET_KEY": "sk_test_private", "AUTODATA_STRIPE_WEBHOOK_SECRET": "whsec_private"})
            def write(d, mode=0o600): p.write_text(json.dumps(d)); p.chmod(mode)
            write(valid)
            self.assertEqual(staging.private_material(p, "ingestion", True), valid)
            with self.assertRaises(ValueError): staging.private_material(p, "ingestion", False)
            variants = [{**valid, "AUTODATA_STRIPE_SECRET_KEY": "sk_live_PRIVATE"}, {**valid, "AUTODATA_ENV": "production"}, {k:v for k,v in valid.items() if k != "AUTODATA_STRIPE_WEBHOOK_SECRET"}]
            for value in variants:
                write(value)
                with self.assertRaisesRegex(ValueError, "^invalid isolated TEST staging input$"): staging.private_material(p, "ingestion", True)
            write(valid, 0o644)
            with self.assertRaises(ValueError): staging.private_material(p, "ingestion", True)
            write(valid); link=Path(tmp)/"link.json";link.symlink_to(p)
            with self.assertRaises(ValueError): staging.private_material(link, "ingestion", True)
            p.write_text('{"secret":"PRIVATE",')
            with self.assertRaisesRegex(ValueError, "^invalid isolated TEST staging input$"): staging.private_material(p, "ingestion", True)

    def test_launcher_removes_inherited_provider_credentials(self):
        env = {**{k: "inherited-sensitive" for k in staging.INHERITED_CLEAR}, "AUTODATA_ENV": "staging", "AUTODATA_COMMERCE_MODE": "disabled", "AUTODATA_PUBLIC_ORIGIN": "https://test.example.org", "INCEPTION_API_KEY": "inherited-model-key", "UNKNOWN_VENDOR_CREDENTIAL": "unrecognized", "STRIPE_API_KEY": "sk_live_inherited", "LD_PRELOAD": "/untrusted/library.so"}
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["launcher", "exec", "--role", "api", "--private", "/private.json"]), patch.object(staging, "private_material", return_value={"AUTODATA_IMAGE_URL_KEY": "private-current"}), patch.object(os, "execvpe") as execute:
            self.assertEqual(staging.main(), 0)
            child_env = execute.call_args.args[2]
            self.assertFalse(set(child_env) & (staging.INHERITED_CLEAR - staging.PUBLIC_KEYS["api"]))
            self.assertNotIn("AUTODATA_STRIPE_ACCOUNT_ID", child_env)
            self.assertNotIn("AUTODATA_STRIPE_PRICE_ID", child_env)
            for key in ["INCEPTION_API_KEY", "UNKNOWN_VENDOR_CREDENTIAL", "STRIPE_API_KEY", "LD_PRELOAD"]:
                self.assertNotIn(key, child_env)
            self.assertEqual(child_env["AUTODATA_IMAGE_URL_KEY"], "private-current")

    def test_actual_source_bytes_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"; repo.mkdir()
            source = Path(tmp) / "source"; source.mkdir()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git("init", "-q")
            (repo / "example").write_text("expected bytes")
            git("add", "example")
            git("-c", "user.name=Staging Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
            sha = git("rev-parse", "HEAD")
            (source / "example").write_text("expected bytes")
            with patch.object(staging, "__file__", str(repo / "scripts/dev/launcher.py")):
                staging.verify_source(source, sha)
                (source / "example").write_text("changed bytes")
                with self.assertRaises(ValueError): staging.verify_source(source, sha)

    def test_disabled_ingestion_child_has_no_stripe_or_firebase_credentials(self):
        env = {**{k: "inherited-sensitive" for k in staging.INHERITED_CLEAR | set().union(*staging.ROLE_KEYS.values())}, "AUTODATA_ENV": "staging", "AUTODATA_COMMERCE_MODE": "disabled", "AUTODATA_PUBLIC_ORIGIN": "https://test.example.org"}
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["launcher", "exec", "--role", "ingestion", "--private", "/private.json"]), patch.object(staging, "private_material", return_value={k: "private-isolated" for k in staging.COMMON}), patch.object(os, "execvpe") as execute:
            self.assertEqual(staging.main(), 0)
            child_env = execute.call_args.args[2]
            self.assertFalse(any("STRIPE" in k or "FIREBASE" in k or k.startswith("GOOGLE_") for k in child_env))
            self.assertEqual(set(child_env) & set().union(*staging.ROLE_KEYS.values()), staging.COMMON)


if __name__ == "__main__": unittest.main()
