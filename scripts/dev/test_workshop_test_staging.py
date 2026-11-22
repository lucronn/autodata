import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import sys
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
import io

import workshop_test_staging as staging


# Keep the synthetic manifest independent of the host's staging mount.
STAGING_FIXTURE_ROOT = Path(tempfile.gettempdir()).resolve() / staging.PROJECT


def render_fixture(p, root=STAGING_FIXTURE_ROOT):
    with patch.object(staging, "RUNTIME_ROOT", STAGING_FIXTURE_ROOT):
        return staging.render(p, root)


def profile():
    return {"origin": "https://workshop-test.example.org", "tester_uids": ["registered-test-uid"],
            "firebase": {"project_id": "fixture-project", "api_key": "public-firebase-key", "app_id": "1:123:web:a123", "auth_domain": "fixture-project.firebaseapp.com"},
            "stripe": {"account_id": "acct_fixture", "price_id": "price_fixture"},
            "source_sha": "a" * 40, "binary_sha256": "b" * 64,
            "runtime_image_id": "sha256:" + "c" * 64, "enabled": False}


class StagingTest(unittest.TestCase):
    def reconciler_env(self):
        p = profile(); p["enabled"] = True
        env = render_fixture(p)["services"]["payment-reconciler"]["environment"].copy()
        env.update({k: "private-isolated" for k in staging.COMMON})
        env.update({"AUTODATA_STRIPE_SECRET_KEY": "sk_test_private", "AUTODATA_STRIPE_WEBHOOK_SECRET": "whsec_private", "INCEPTION_API_KEY": "must-not-inherit", "GOOGLE_APPLICATION_CREDENTIALS": "/owner-adc"})
        return env

    def test_reconciler_only_exists_for_explicit_test_enablement(self):
        self.assertNotIn("payment-reconciler", render_fixture(profile())["services"])
        p = profile(); p["enabled"] = True
        c = render_fixture(p); self.assertEqual(len(c["services"]), 7)
        s = c["services"]["payment-reconciler"]
        self.assertEqual(s["environment"]["AUTODATA_COMMERCE_MODE"], "stripe_test")
        self.assertEqual(s["environment"]["AUTODATA_POSTGRES_DB"], "workshop_stripe_staging")
        self.assertEqual(s["command"], ["/usr/local/bin/python", "-I", "/src/scripts/dev/workshop_test_staging.py", "exec", "--role", "reconciler", "--private", "/run/staging/private.json"])
        self.assertEqual(s["depends_on"], {"ingestion-http": {"condition": "service_healthy"}})
        self.assertEqual(s["networks"], ["internal", "egress"])
        self.assertEqual(s["restart"], "no"); self.assertEqual(s["mem_limit"], "384m"); self.assertEqual(s["cpus"], 0.5)
        self.assertNotIn("ports", s); self.assertNotIn("healthcheck", s)
        self.assertEqual(s["stop_grace_period"], "10s"); self.assertTrue(s["init"])
        self.assertEqual(len(s["volumes"]), 2)
        self.assertTrue(s["volumes"][1]["source"].endswith("/private/reconciler.json"))
        for v in s["volumes"]: self.assertTrue(v["read_only"]); self.assertFalse(v["bind"]["create_host_path"])
        for key in staging.INHERITED_CLEAR:
            if key not in {"AUTODATA_STRIPE_ACCOUNT_ID", "AUTODATA_STRIPE_PRICE_ID"}: self.assertEqual(s["environment"][key], "")

    def test_reconciler_role_refuses_disabled_and_has_no_identity_provider_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp).resolve() / "private.json"
            data = {k: "private-isolated" for k in staging.COMMON}
            data.update({"AUTODATA_STRIPE_SECRET_KEY": "sk_test_private", "AUTODATA_STRIPE_WEBHOOK_SECRET": "whsec_private"})
            p.write_text(json.dumps(data)); p.chmod(0o600)
            self.assertEqual(staging.private_material(p, "reconciler", True), data)
            with self.assertRaises(ValueError): staging.private_material(p, "reconciler", False)
            data["GOOGLE_APPLICATION_CREDENTIALS"] = "/old-admin"
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError): staging.private_material(p, "reconciler", True)

    def test_reconciler_invokes_bounded_existing_runner_without_logging_results(self):
        clock = [0.0]; calls = []
        def run(argv, **kw):
            calls.append((argv, kw)); clock[0] += 1
            return SimpleNamespace(returncode=0, stdout="private payment result")
        def sleep(seconds): clock[0] += seconds
        output = io.StringIO()
        with redirect_stdout(output):
            status = staging.bounded_reconcile(env=self.reconciler_env(), run=run, monotonic=lambda: clock[0], sleep=sleep)
        self.assertEqual(status, 0); self.assertEqual(len(calls), 10); self.assertLessEqual(clock[0], 600)
        for argv, kw in calls:
            self.assertEqual(argv[1:], [str(Path(staging.__file__).with_name("reconcile_payments.py")), "--once", "--batch-size", "10"])
            self.assertLessEqual(kw["timeout"], 45); self.assertEqual(kw["stdout"], subprocess.DEVNULL); self.assertEqual(kw["stderr"], subprocess.DEVNULL)
            self.assertNotIn("INCEPTION_API_KEY", kw["env"]); self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", kw["env"])
        self.assertNotIn("private", output.getvalue())

    def test_reconciler_refuses_live_production_and_shared_db_before_launch(self):
        for key, value in [("AUTODATA_COMMERCE_MODE", "disabled"), ("AUTODATA_COMMERCE_MODE", "stripe_live"), ("AUTODATA_ENV", "production"), ("AUTODATA_PUBLIC_ORIGIN", "https://autodata.cars.tk"), ("AUTODATA_DB_ADDRESS", "production:5432"), ("AUTODATA_POSTGRES_DB", "autodata"), ("AUTODATA_STRIPE_SECRET_KEY", "sk_live_FORBIDDEN")]:
            env = self.reconciler_env(); env[key] = value
            with self.subTest(key=key, value=value), patch.object(subprocess, "run") as child, self.assertRaises(ValueError):
                staging.bounded_reconcile(env=env, run=child)
            child.assert_not_called()

    def test_reconciler_timeout_failure_and_deadline_stop(self):
        for result in [SimpleNamespace(returncode=1), subprocess.TimeoutExpired(["runner"], 45)]:
            child = unittest.mock.Mock(side_effect=result if isinstance(result, Exception) else None, return_value=result)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(staging.bounded_reconcile(env=self.reconciler_env(), run=child, monotonic=lambda: 0, sleep=lambda _: self.fail("failure must not poll")), 2)
            self.assertEqual(child.call_count, 1)
        clock = [0.0]; child = unittest.mock.Mock(return_value=SimpleNamespace(returncode=0))
        def stop_after_sleep(_): clock[0] = 600
        with redirect_stdout(io.StringIO()):
            self.assertEqual(staging.bounded_reconcile(env=self.reconciler_env(), run=child, monotonic=lambda: clock[0], sleep=stop_after_sleep), 0)
        self.assertEqual(child.call_count, 1)

    def test_isolated_disabled_defaults_and_secret_absence(self):
        p = profile()
        p["stripe"] = None
        c = render_fixture(p)
        self.assertEqual(c["name"], staging.PROJECT)
        self.assertTrue(c["networks"]["internal"]["internal"])
        for name, s in c["services"].items():
            self.assertEqual(s["restart"], "no")
            self.assertNotIn("build", s)
            self.assertTrue(s["image"].startswith("sha256:"))
            for v in s["volumes"]:
                self.assertTrue(v["source"].startswith(str(STAGING_FIXTURE_ROOT) + "/"))
                self.assertFalse(v["bind"]["create_host_path"])
            if name in {"api", "ingestion-http"}:
                self.assertEqual(s["image"], p["runtime_image_id"])
                self.assertEqual(s["pull_policy"], "never")
                self.assertEqual(s["depends_on"]["migration-runner"], {"condition": "service_completed_successfully"})
                self.assertEqual(s["environment"]["AUTODATA_COMMERCE_MODE"], "disabled")
                for key in staging.INHERITED_CLEAR | set().union(*staging.ROLE_KEYS.values()):
                    if name != "api" or key not in staging.PUBLIC_KEYS["api"]:
                        self.assertEqual(s["environment"][key], "")
            else:
                self.assertEqual(s["networks"], ["internal"])
                self.assertNotIn("ports", s)
        api = c["services"]["api"]
        self.assertEqual(api["ports"], [{"target": 8080, "published": "3043", "host_ip": "127.0.0.1", "protocol": "tcp"}])
        self.assertEqual(api["depends_on"]["ingestion-http"], {"condition": "service_healthy"})
        self.assertEqual(c["services"]["migration-runner"]["depends_on"], {"postgres": {"condition": "service_healthy"}})
        self.assertEqual(c["services"]["postgres"]["healthcheck"]["test"],
                         ["CMD", "pg_isready", "-h", "127.0.0.1", "-U", staging.DATABASE, "-d", staging.DATABASE])
        self.assertEqual(json.loads(api["environment"]["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"]), p["tester_uids"])
        self.assertFalse(json.loads(c["services"]["ingestion-http"]["environment"]["AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"])["enabled"])

    def test_test_enablement_is_equal_and_notices_are_same_origin(self):
        p = profile(); p["enabled"] = True
        c = render_fixture(p)
        for role in ["api", "ingestion-http"]:
            self.assertEqual(c["services"][role]["environment"]["AUTODATA_COMMERCE_MODE"], "stripe_test")
        n = json.loads(c["services"]["ingestion-http"]["environment"]["AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"])
        self.assertTrue(n["enabled"])
        for key in ["terms", "privacy", "refund", "contact"]:
            self.assertEqual(n[key+"_url"], p["origin"] + "/workshop/test-notices/" + key)
        p["tester_uids"] = ["$AMBIENT_VARIABLE"]
        self.assertIn("$$AMBIENT_VARIABLE", render_fixture(p)["services"]["api"]["environment"]["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"])
        p["stripe"] = None
        with self.assertRaises(ValueError):
            render_fixture(p)

    def test_origin_tester_and_shared_root_denials(self):
        for origin in ["https://cars.tk", "https://autodata.cars.tk", "https://autodata.curtis.click", "http://localhost:3013", "https://127.0.0.1", "https://example.org/path", "https://example.org:443", "https://user@example.org", "https://example.org.", " https://example.org", "https://lab-.example.org", "https://" + "a" * 64 + ".org"]:
            p = profile(); p["origin"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError): render_fixture(p)
        for ids in [[], ["same", "same"], [""], ["bad\nuid"], ["bad\u0085uid"], ["\ud800"], [1], ["u"]*101,
                    [f"{i:02d}" + "🚗" * 126 for i in range(100)]]:
            p = profile(); p["tester_uids"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError): render_fixture(p)
        with self.assertRaises(ValueError): render_fixture(profile(), Path("/home/corp/autodata/production"))

    def test_runtime_image_and_firebase_key_validation(self):
        p = profile()
        for image in ["worker:latest", "sha256:abc", "sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4"]:
            with self.subTest(image=image), self.assertRaises(ValueError):
                render_fixture({**p, "runtime_image_id": image})
        p["firebase"]["api_key"] += " "
        with self.assertRaises(ValueError):
            render_fixture(p)

    def test_manifest_rejects_symlinked_storage_and_private_binds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / "staging"
            root.mkdir()
            shared = base / "shared"
            shared.mkdir()
            for name in ["pgdata", "nats-data", "s3-data", "s3-work", "private"]:
                alias = root / name
                alias.symlink_to(shared, target_is_directory=True)
                with self.subTest(name=name), patch.object(staging, "RUNTIME_ROOT", root), self.assertRaises(ValueError):
                    staging.render(profile(), root)
                alias.unlink()

    def test_private_material_denials_do_not_expose_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp).resolve() / "private.json"
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
        env = {**{k: "inherited-sensitive" for k in staging.INHERITED_CLEAR},
               **render_fixture(profile())["services"]["api"]["environment"],
               "INCEPTION_API_KEY": "inherited-model-key", "UNKNOWN_VENDOR_CREDENTIAL": "unrecognized", "STRIPE_API_KEY": "sk_live_inherited", "LD_PRELOAD": "/untrusted/library.so"}
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["launcher", "exec", "--role", "api", "--private", "/private.json"]), patch.object(staging, "private_material", return_value={"AUTODATA_IMAGE_URL_KEY": "private-current"}), patch.object(os, "execvpe") as execute:
            self.assertEqual(staging.main(), 0)
            child_env = execute.call_args.args[2]
            self.assertFalse(set(child_env) & (staging.INHERITED_CLEAR - staging.PUBLIC_KEYS["api"]))
            self.assertNotIn("AUTODATA_STRIPE_ACCOUNT_ID", child_env)
            self.assertNotIn("AUTODATA_STRIPE_PRICE_ID", child_env)
            for key in ["INCEPTION_API_KEY", "UNKNOWN_VENDOR_CREDENTIAL", "STRIPE_API_KEY", "LD_PRELOAD"]:
                self.assertNotIn(key, child_env)
            self.assertEqual(child_env["AUTODATA_IMAGE_URL_KEY"], "private-current")

    def test_launchers_refuse_external_store_and_disabled_api_without_tester_config(self):
        for role, service in [("api", "api"), ("ingestion", "ingestion-http")]:
            env = render_fixture(profile())["services"][service]["environment"]
            unsafe_values = {"AUTODATA_DB_ADDRESS": "shared-db:5432", "AUTODATA_S3_ENDPOINT": "shared-s3:9000", "AUTODATA_NATS_ADDRESS": "shared-nats:4222"}
            if role == "api":
                unsafe_values.update({"AUTODATA_WORKSHOP_TESTER_UIDS_JSON": "", "AUTODATA_INGESTION_URL": "https://shared-ingestion.example.org"})
            for key, value in unsafe_values.items():
                argv = ["launcher", "exec", "--role", role, "--private", "/private.json"]
                with self.subTest(role=role, key=key), patch.dict(os.environ, {**env, key: value}, clear=True), patch.object(sys, "argv", argv), patch.object(staging, "private_material") as read_private, patch.object(os, "execvpe") as execute, redirect_stderr(io.StringIO()):
                    self.assertEqual(staging.main(), 2)
                    read_private.assert_not_called()
                    execute.assert_not_called()

    def test_actual_source_bytes_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"; repo.mkdir()
            source = root / "source"; source.mkdir()
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
        env = {**{k: "inherited-sensitive" for k in staging.INHERITED_CLEAR | set().union(*staging.ROLE_KEYS.values())},
               **render_fixture(profile())["services"]["ingestion-http"]["environment"]}
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["launcher", "exec", "--role", "ingestion", "--private", "/private.json"]), patch.object(staging, "private_material", return_value={k: "private-isolated" for k in staging.COMMON}), patch.object(os, "execvpe") as execute:
            self.assertEqual(staging.main(), 0)
            child_env = execute.call_args.args[2]
            self.assertFalse(any("STRIPE" in k or "FIREBASE" in k or k.startswith("GOOGLE_") for k in child_env))
            self.assertEqual(set(child_env) & set().union(*staging.ROLE_KEYS.values()), staging.COMMON)


if __name__ == "__main__": unittest.main()
