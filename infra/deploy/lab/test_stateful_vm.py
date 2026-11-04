"""Offline contract tests. External identity/tool observations are intercepted."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import contextlib
import unittest
from unittest.mock import patch


PATH = Path(__file__).with_name("stateful_vm.py")
SPEC = importlib.util.spec_from_file_location("stateful_vm", PATH)
vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vm)
SHA = "a" * 40
RUN = "12345678-1234-4234-8234-123456789abc"
AUTH = "87654321-1234-4234-8234-123456789abc"


def approval():
    return {"schema_version": 1, "operation": "disposable-offline-stateful-vm",
            "authorization_id": AUTH, "run_id": RUN, "source_sha": SHA,
            "expires_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "machine_id": "a" * 32, "product_uuid": AUTH, "boot_id": RUN,
            "data_uuid": AUTH, "hypervisor_config_sha256": "b" * 64,
            "helper_files": [{"path": "infra/deploy/lab/" + n, "bytes": 1, "sha256": "c" * 64}
                             for n in sorted(vm.FILES)],
            "images": {n: {"reference": "example.test/lab/" + n + "@sha256:" + "d" * 64,
                           "image_id": "sha256:" + "e" * 64, "platform": "linux/amd64"}
                       for n in ("postgres", "nats", "minio", "probe")},
            "tools": {n: {"path": p, "sha256": "f" * 64} for n, p in vm.TOOLS.items()}}


class ApprovalTests(unittest.TestCase):
    def good(self):
        a = approval()
        a["images"]["minio"] = dict(reference=vm.SEAWEED_REFERENCE, image_id=vm.SEAWEED_ID, platform="linux/amd64")
        return a

    def test_exact_approval_and_unknown_or_boolean_fields(self):
        a = self.good()
        self.assertEqual(vm.validate_approval(a, SHA, RUN), a)
        for change in ({"schema_version": True}, {"extra": 1}, {"run_id": AUTH}, {"source_sha": "A" * 40}):
            with self.subTest(change=change), self.assertRaises(vm.LabError):
                vm.validate_approval(dict(a, **change), SHA, RUN)

    def test_expired_or_too_long_approval(self):
        for hours in (-1, 25):
            a = self.good()
            a["expires_at"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
            with self.assertRaises(vm.LabError):
                vm.validate_approval(a, SHA, RUN)

    def test_duplicate_nonfinite_or_large_json_denied(self):
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b' ' * 65537):
            with self.subTest(data=data[:32]), self.assertRaises(vm.LabError):
                vm.strict_json(data)

    def test_missing_approval_no_child_or_write(self):
        with patch.object(vm, "read_file", side_effect=FileNotFoundError), patch.object(vm, "run_tool") as child, patch.object(vm, "atomic_json") as write:
            code, receipt = vm.install_cli("install", SHA, RUN)
        self.assertEqual(code, 3)
        self.assertFalse(receipt["material_committed"])
        child.assert_not_called()
        write.assert_not_called()

    def test_receipt_phase_flags_do_not_promote_product_or_cloud(self):
        code, receipt = vm.install_cli("arbitrary", SHA, RUN)
        self.assertEqual(code, 2)
        for key in vm.AUTHORITY:
            self.assertIs(receipt[key], False)

    def test_deterministic_bridge_is_fifteen_bytes(self):
        self.assertEqual(vm.bridge_name(RUN), "adlab-123456781")
        self.assertEqual(len(vm.bridge_name(RUN).encode("ascii")), 15)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        # Temp inode exercises run unprivileged; ownership is a separate boundary.
        self.owner = patch.object(vm, "require_owner")
        self.owner.start()
        self.addCleanup(self.owner.stop)

    def test_standard0755_parent_allowed_private0755_denied(self):
        self.root.chmod(0o755)
        with vm.open_dir(str(self.root)) as fd:
            self.assertGreaterEqual(fd, 0)
        with self.assertRaises(vm.LabError):
            with vm.open_dir(str(self.root), private=True):
                pass

    def test_symlink_hardlink_fifo_and_midread_drift_denied(self):
        f = self.root / "file"
        f.write_bytes(b"approved")
        f.chmod(0o600)
        link = self.root / "link"
        link.symlink_to(f)
        fifo = self.root / "fifo"
        os.mkfifo(fifo, 0o600)
        for p in (link, fifo):
            with self.assertRaises((vm.LabError, OSError)):
                vm.read_file(str(p), 100, 0o600)
        os.link(f, self.root / "hard")
        with self.assertRaises(vm.LabError):
            vm.read_file(str(f), 100, 0o600)
        (self.root / "hard").unlink()
        original = os.read
        def drift(fd, size):
            result = original(fd, size)
            f.write_bytes(b"changed!")
            return result
        with patch.object(os, "read", side_effect=drift), self.assertRaises(vm.LabError):
            vm.read_file(str(f), 100, 0o600)

    def test_atomic_json_has_exact_mode_and_no_temporary_file(self):
        vm.atomic_json(str(self.root / "state.json"), {"phase": "pending"})
        self.assertEqual(json.loads((self.root / "state.json").read_text()), {"phase": "pending"})
        self.assertEqual((self.root / "state.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["state.json"])

    def test_failed_fsync_close_or_receipt_never_passes(self):
        with patch.object(os, "fsync", side_effect=OSError), self.assertRaises(OSError):
            vm.atomic_json(str(self.root / "state.json"), {"phase": "pending"})
        self.assertFalse((self.root / "state.json").exists())

    def test_complete_install_idempotent(self):
        bundle = {n: b"x" for n in vm.FILES}
        final = str(self.root / SHA)
        self.assertTrue(vm.install_bundle(str(self.root), SHA, AUTH, bundle, lambda: None))
        self.assertFalse(vm.install_bundle(str(self.root), SHA, AUTH, bundle, lambda: None))
        self.assertEqual(sorted(p.name for p in Path(final).iterdir()), sorted(vm.FILES))
        self.assertEqual(Path(final).stat().st_mode & 0o777, 0o500)

    def test_no_replace_and_same_sha_byte_drift_denied(self):
        bundle = {n: b"x" for n in vm.FILES}
        vm.install_bundle(str(self.root), SHA, AUTH, bundle, lambda: None)
        altered = dict(bundle, **{"stateful_vm.py": b"y"})
        with self.assertRaises(vm.LabError):
            vm.install_bundle(str(self.root), SHA, AUTH, altered, lambda: None)
        self.assertEqual((self.root / SHA / "stateful_vm.py").read_bytes(), b"x")

    def test_partial_copy_cleanup_is_owned_and_bounded(self):
        bundle = {n: b"x" for n in vm.FILES}
        with patch.object(os, "write", side_effect=OSError), self.assertRaises(OSError):
            vm.install_bundle(str(self.root), SHA, AUTH, bundle, lambda: None)
        self.assertEqual(list(self.root.iterdir()), [])
        stale = self.root / (".install-" + AUTH)
        stale.mkdir()
        (stale / "unowned").write_text("retain")
        with self.assertRaises(vm.LabError):
            vm.install_bundle(str(self.root), SHA, AUTH, bundle, lambda: None)
        self.assertEqual((stale / "unowned").read_text(), "retain")


class IdentityTests(unittest.TestCase):
    def test_non_kvm_or_wrong_machine_boot_disk_denied(self):
        a = ApprovalTests().good()
        with patch.object(vm, "pseudo_read", return_value=b"wrong\n"), self.assertRaises(vm.LabError):
            vm.observe_machine(a, 99999999999)

    def test_production_path_or_external_interface_denied(self):
        with patch.object(vm.os.path, "lexists", return_value=True), self.assertRaises(vm.LabError):
            vm.refuse_production()
        with patch.object(vm.os, "listdir", return_value=["lo", "eth0"]), self.assertRaises(vm.LabError):
            vm.observe_interfaces(set())

    def test_unknown_unowned_docker_resource_denied(self):
        with self.assertRaises(vm.LabError):
            vm.validate_inventory([{"Id": "a" * 64}], [], {})

    def test_unmounted_no_boot_disk_creation(self):
        a = ApprovalTests().good()
        with patch.object(vm, "run_tool", return_value=(0, b'{"filesystems":[]}')), patch.object(vm.os, "mkdir") as mkdir:
            with self.assertRaises(vm.LabError):
                vm.observe_mounts(a, 99999999999)
        mkdir.assert_not_called()

    def test_operation_lock_shared_by_every_verb(self):
        # Actual flock, no host state: a second open description cannot acquire it.
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp, patch.object(vm, "require_owner"):
            Path(temp).chmod(0o700)
            Path(temp, "state").mkdir(mode=0o700)
            with patch.object(vm, "RUNTIME", temp), vm.operation_lock():
                with self.assertRaises(vm.LabError):
                    with vm.operation_lock():
                        pass


class DeliveryProfileTests(unittest.TestCase):
    def bundle(self):
        return dict(schema_version=1, run_id=RUN, **{key: format(i + 1, "064x") for i, key in enumerate(vm.SECRET_KEYS)})

    def test_pipe_single_frame_limit_and_secret_redaction(self):
        bundle = self.bundle()
        frame = json.dumps(bundle).encode() + b"\n"
        with patch.object(vm.os, "fstat", return_value=type("S", (), {"st_mode": 0o010000})()), patch.object(vm.fcntl, "fcntl", return_value=os.O_RDONLY), patch.object(vm, "read_pipe_frame", return_value=frame):
            self.assertEqual(vm.read_delivery(RUN), bundle)
        for invalid in (dict(bundle, extra="no"), dict(bundle, postgres_password="short"), dict(bundle, nats_writer_password=bundle["postgres_password"])):
            with self.assertRaises(vm.LabError):
                vm.validate_bundle(invalid, RUN)

    def test_profile_exact_graph_internal_network_no_ports_or_secret_env(self):
        with patch.object(vm, "read_file", return_value=Path(__file__).with_name("compose.stateful.yaml").read_bytes()):
            profile = vm.render_profile(ApprovalTests().good(), RUN)
        self.assertEqual(set(profile["services"]), {"postgres", "nats", "minio", "probe"})
        network = profile["networks"]["lab"]
        self.assertIs(network["internal"], True)
        self.assertEqual(network["driver_opts"]["com.docker.network.bridge.name"], "adlab-123456781")
        for service in profile["services"].values():
            self.assertNotIn("ports", service)
            self.assertEqual(service["pull_policy"], "never")
            self.assertTrue(service["read_only"])
            self.assertEqual(service["cap_drop"], ["ALL"])
            self.assertEqual(service["restart"], "no")
            self.assertTrue(all(not m["bind"]["create_host_path"] for m in service["volumes"]))
            self.assertFalse(any(k in vm.SECRET_KEYS for k in service.get("environment", {})))

    def test_postgres_check_sql_cannot_seed(self):
        sql = Path(__file__).with_name("postgres-seed.sql").read_text()
        self.assertIn("\\if :do_seed", sql)
        self.assertIn("ON CONFLICT DO NOTHING", sql)
        self.assertLess(sql.index("\\if :do_seed"), sql.index("CREATE TABLE"))
        self.assertLess(sql.index("\\endif"), sql.index("AS fixture_ok"))

    def test_deliver_exact_tmpfs_modes_and_only_hash_in_persistent_state(self):
        bundle = self.bundle()
        c = vm.Controller(ApprovalTests().good(), vm.empty_receipt("deliver", SHA, RUN))
        c.state = {"bundle_sha256": None, "delivery_boot_id": None}
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp:
            Path(temp).chmod(0o700)
            with patch.object(vm, "RUNTIME", temp), patch.object(vm, "require_owner"), patch.object(vm.os, "fchown") as chown, patch.object(vm, "read_delivery", return_value=bundle), patch.object(c, "save"), patch.object(c, "recheck"):
                c.deliver()
                c.require_delivery()
            base = Path(temp, "delivery", RUN)
            for name, (_, contents) in vm.delivery_material(bundle).items():
                self.assertEqual((base / name).stat().st_mode & 0o777, 0o500)
                for filename in contents:
                    self.assertEqual((base / name / filename).stat().st_mode & 0o777, 0o400)
            self.assertTrue(any(call.args[1:] == (999, 999) for call in chown.call_args_list))
            self.assertTrue(any(call.args[1:] == (1000, 1000) for call in chown.call_args_list))
        self.assertEqual(c.state["delivery_boot_id"], RUN)
        self.assertEqual(c.state["bundle_sha256"], vm.digest(vm.canonical(bundle)))
        self.assertFalse(any(value in json.dumps(c.state) for key, value in bundle.items() if key in vm.SECRET_KEYS))

    def test_partial_delivery_cannot_set_boot_completion(self):
        c = vm.Controller(ApprovalTests().good(), vm.empty_receipt("deliver", SHA, RUN))
        c.state = {"bundle_sha256": None, "delivery_boot_id": None}
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp, patch.object(vm, "RUNTIME", temp), patch.object(vm, "require_owner"), patch.object(vm, "read_delivery", return_value=self.bundle()), patch.object(c, "save"), patch.object(c, "recheck"), patch.object(vm, "write_all", side_effect=OSError), self.assertRaises(OSError):
            Path(temp).chmod(0o700)
            c.deliver()
        self.assertIsNone(c.state["delivery_boot_id"])


class PostgresDiagnosticTests(unittest.TestCase):
    DIAGNOSTIC = (b'psql: error: connection to server at "127.0.0.1", port 5432 failed: FATAL:  password authentication failed for user "lab_admin"\n'
                  b'password retrieved from file "/run/lab/invalid.pgpass"\n')

    def test_pg_negative_auth_exact_fixed_diagnostic_and_buffer_cleared(self):
        buffer = bytearray(self.DIAGNOSTIC)
        self.assertTrue(vm.classify_pg_diagnostic(buffer, 2, b""))
        self.assertEqual(buffer, bytearray())

    def test_pg_negative_auth_refusal_wrong_user_extra_text_or_exit_is_failure(self):
        for value, code, out in ((b"connection refused\n", 2, b""), (self.DIAGNOSTIC.replace(b"lab_admin", b"other"), 2, b""),
                                 (self.DIAGNOSTIC + b"extra\n", 2, b""), (self.DIAGNOSTIC.replace(b"FATAL:  ", b"FATAL: "), 2, b""),
                                 (self.DIAGNOSTIC, 1, b""), (self.DIAGNOSTIC, 2, b"1\n"), (b"secret-sentinel", 2, b"")):
            buffer = bytearray(value)
            self.assertFalse(vm.classify_pg_diagnostic(buffer, code, out))
            self.assertEqual(buffer, bytearray())

    def test_pg_negative_auth_8192_limit_and_8193_fail_closed(self):
        buffer = bytearray(b"x" * 8192)
        self.assertFalse(vm.classify_pg_diagnostic(buffer, 2, b""))
        self.assertEqual(buffer, bytearray())
        buffer = bytearray(b"x" * 8193)
        with self.assertRaises(vm.LabError) as error:
            vm.classify_pg_diagnostic(buffer, 2, b"")
        self.assertEqual(buffer, bytearray())
        self.assertNotIn("xxx", str(error.exception))

    def test_pg_locales_and_transport_flags_are_fixed(self):
        args = vm.pg_args("a" * 64, "negative")
        for token in ("LC_ALL=C", "PGSSLMODE=disable", "PGGSSENCMODE=disable", "PGPASSFILE=/run/lab/invalid.pgpass",
                      "--host=127.0.0.1", "--port=5432", "--username=lab_admin", "--dbname=workshop_lab", "-w", "-X", "--command=SELECT 1"):
            self.assertIn(token, args)
        with self.assertRaises(vm.LabError):
            vm.pg_args("a" * 64, "arbitrary SQL")

    def test_pg_negative_auth_positive_same_container_and_binding_required(self):
        c = vm.Controller(ApprovalTests().good(), vm.empty_receipt("check", SHA, RUN))
        c.resources["containers"]["postgres"] = "a" * 64
        with patch.object(c, "recheck"), patch.object(c, "security_readback"), patch.object(c, "docker", return_value=(2, b"")), patch.object(vm, "run_tool") as negative:
            with self.assertRaises(vm.LabError):
                c.pg_negative()
        negative.assert_not_called()
        with patch.object(c, "recheck"), patch.object(c, "security_readback"), patch.object(c, "docker", return_value=(0, b"1\n")), patch.object(vm, "run_tool", return_value=(2, b"", True, len(self.DIAGNOSTIC))):
            c.pg_negative()
        self.assertTrue(c.receipt["checks"]["negative_auth"])


class LifecycleTests(unittest.TestCase):
    def controller(self):
        c = vm.Controller(ApprovalTests().good(), vm.empty_receipt("check", SHA, RUN))
        c.state = {"binding": c.binding(), "resources": c.resources, "bundle_sha256": "b" * 64,
                   "delivery_boot_id": RUN, "phase": "started", "seeded": True}
        return c

    def test_all_probe_modes_disable_stdin_and_tty_in_exact_compose_argv(self):
        # Removing either flag would leave Compose's interactive/TTY defaults active.
        class Intercepted(Exception):
            pass
        project = "autodata-lab-12345678123442348234123456789abc"
        for mode in ("ready", "seed", "check", "deny"):
            with self.subTest(mode=mode):
                c = self.controller()
                c.profile = {"name": project}
                observed = []
                def intercept(tool, args, timeout=15):
                    observed.append((tool, args))
                    raise Intercepted
                with patch.object(c, "inventory", return_value=([], [])), patch.object(c, "save"), patch.object(c, "tool", side_effect=intercept), self.assertRaises(Intercepted):
                    c.probe(mode)
                self.assertEqual(observed, [("docker_compose", [
                    "--project-name", project, "--file",
                    "/var/lib/autodata-lab/runs/12345678-1234-4234-8234-123456789abc/compose.json",
                    "run", "--interactive=false", "--no-TTY", "--no-deps", "--pull", "never",
                    "--name", project + "-probe-" + mode + "-87654321-1234-4234-8234-123456789abc",
                    "probe", "python", "-I", "/lab/stateful_probe.py", mode,
                    "12345678-1234-4234-8234-123456789abc"] )])

    def test_probe_readback_rejects_stdin_and_tty_independently(self):
        c = self.controller()
        c.profile = {"name": "lab-project", "services": {"probe": {
            "user": "1000:1000", "command": ["python", "-I", "/lab/stateful_probe.py", "ready", RUN],
            "labels": {"autodata.run": RUN}, "tmpfs": [], "volumes": [],
            "networks": {"lab": {"ipv4_address": "172.31.250.50"}}}}}
        c.images = {"probe": {"Config": {}}}
        c.resources["network"] = "network-id"
        item = {"Image": "sha256:" + "e" * 64,
                "Config": {"User": "1000:1000", "Cmd": ["python", "-I", "/lab/stateful_probe.py", "ready", RUN],
                           "Labels": {"autodata.run": RUN, "com.docker.compose.project": "lab-project", "com.docker.compose.service": "probe"},
                           "OpenStdin": False, "Tty": False},
                "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"],
                               "SecurityOpt": ["no-new-privileges:true"], "PidsLimit": 128,
                               "LogConfig": {"Type": "none"}, "RestartPolicy": {"Name": "no"},
                               "NetworkMode": "lab-project_lab"},
                "State": {"Running": False}, "Mounts": [],
                "NetworkSettings": {"Ports": {}, "Networks": {"lab-project_lab": {
                    "IPAMConfig": {"IPv4Address": "172.31.250.50"}, "IPAddress": "", "NetworkID": ""}}}}
        c.inspect_container(item, "probe", probe=True)
        for field in ("OpenStdin", "Tty"):
            with self.subTest(field=field):
                changed = copy.deepcopy(item)
                changed["Config"][field] = True
                with self.assertRaises(vm.LabError) as caught:
                    c.inspect_container(changed, "probe", probe=True)
                self.assertEqual(caught.exception.code, "container_tty")

    def test_partial_delivery_cannot_start(self):
        c = self.controller()
        c.state["delivery_boot_id"] = None
        with patch.object(c, "compose") as command, self.assertRaises(vm.LabError):
            c.require_delivery()
        command.assert_not_called()

    def test_changed_bundle_fails_without_start(self):
        c = self.controller()
        with patch.object(vm, "read_delivery", return_value=DeliveryProfileTests().bundle()), patch.object(c, "save"), patch.object(c, "compose") as command, self.assertRaises(vm.LabError):
            c.deliver()
        command.assert_not_called()

    def test_recover_reuses_fixture_without_seed(self):
        c = self.controller()
        with patch.object(c, "start") as start, patch.object(c, "check") as check, patch.object(c, "seed") as seed, patch.object(c, "save"):
            c.recover()
        start.assert_called_once()
        check.assert_called_once()
        seed.assert_not_called()
        self.assertTrue(c.receipt["recovery_verified"])

    def test_drifted_or_corrupt_data_retained_incomplete(self):
        c = self.controller()
        with patch.object(c, "start"), patch.object(c, "check", side_effect=vm.LabError("fixture_failed", 4)), patch.object(c, "save"), self.assertRaises(vm.LabError) as caught:
            c.recover()
        self.assertEqual(caught.exception.exit_code, 6)
        self.assertFalse(c.receipt["recovery_verified"])

    def test_check_has_zero_write_commands(self):
        c = self.controller()
        calls = []
        with patch.object(c, "require_delivery"), patch.object(c, "security_readback"), patch.object(c, "pg_negative"), patch.object(c, "pg", side_effect=lambda mode: calls.append(mode)), patch.object(c, "probe", side_effect=lambda mode: calls.append(mode)), patch.object(c, "save"):
            c.check()
        self.assertEqual(calls, ["check", "check", "deny", "check"])
        self.assertTrue(c.receipt["checks"]["no_work"])

    def test_stop_preserves_data_and_unowned_resources(self):
        c = self.controller()
        commands = []
        with patch.object(c, "security_readback"), patch.object(c, "recheck"), patch.object(c, "save"), patch.object(c, "compose", side_effect=lambda args: (commands.append(args) or (0, b""))):
            c.stop()
        self.assertEqual(commands, [["stop", "--timeout", "10", "postgres", "nats", "minio"]])
        self.assertTrue(c.state["seeded"])

    def test_probe_result_requires_typed_closed_checks(self):
        result = dict(schema_version=1, mode="ready", run_id=RUN, status="passed",
                      checks={k: None for k in vm.PROBE_CHECKS}, measurements={k: None for k in vm.PROBE_MEASUREMENTS})
        with self.assertRaises(vm.LabError):
            vm.validate_probe_result(canonical_bytes(result), "ready", RUN)
        result["checks"].update(nats_connected=True, s3_connected=True)
        self.assertEqual(vm.validate_probe_result(canonical_bytes(result), "ready", RUN), result)
        result["checks"]["nats_connected"] = 1
        with self.assertRaises(vm.LabError):
            vm.validate_probe_result(canonical_bytes(result), "ready", RUN)

    def test_reboot_requires_new_boot_approval_and_redelivery(self):
        c = self.controller()
        c.approval["boot_id"] = AUTH
        with self.assertRaises(vm.LabError):
            c.require_delivery()
        c.state["delivery_boot_id"] = AUTH
        with patch.object(c, "verify_service_delivery"), patch.object(vm, "read_file", side_effect=FileNotFoundError), self.assertRaises(FileNotFoundError):
            c.require_delivery()

    def test_shortened_bridge_collision_cannot_be_adopted(self):
        c = self.controller()
        # Same shortened prefix, different full UUID and unknown exact ID.
        other = "12345678-1234-4234-8234-000000000000"
        self.assertEqual(vm.bridge_name(RUN), vm.bridge_name(other))
        with self.assertRaises(vm.LabError):
            vm.validate_inventory([], [{"Id": "f" * 64, "Name": "foreign", "Labels": {"autodata.run": other}}], c.resources)

    def test_pg_negative_auth_container_changed_during_positive_fails(self):
        c = self.controller()
        c.resources["containers"]["postgres"] = "a" * 64
        def changed(args):
            c.resources["containers"]["postgres"] = "b" * 64
            return 0, b"1\n"
        with patch.object(c, "recheck"), patch.object(c, "security_readback"), patch.object(c, "docker", side_effect=changed), patch.object(vm, "run_tool") as negative, self.assertRaises(vm.LabError):
            c.pg_negative()
        negative.assert_not_called()

    def test_failed_operation_keeps_unknown_probe_for_inspection(self):
        c = self.controller()
        c.profile = {"name": "fixed"}
        c.state["probe_id"] = "f" * 64
        with patch.object(c, "reconcile"), patch.object(c, "save"), patch.object(c, "stop") as stop:
            c.failed_operation()
        stop.assert_not_called()
        self.assertEqual(c.receipt["status"], "incomplete")
        self.assertEqual(c.receipt["cleanup"]["status"], "unknown")

    def test_successful_finish_does_not_override_unreaped_child(self):
        c = self.controller()
        c.receipt["status"] = "passed"
        c.receipt["checks"]["children_reaped"] = False
        with patch.object(c, "recheck"), patch.object(vm, "atomic_json"), self.assertRaises(vm.LabError):
            c.finish("check")


class CapturedChildTests(unittest.TestCase):
    """Intercept Popen; real pipe readiness/stream bounds, no process or Docker."""
    @contextlib.contextmanager
    def child(self, diagnostic, code=2):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp:
            Path(temp, "docker").write_bytes(b"reviewed binary")
            Path(temp, "docker").chmod(0o444)
            directory = os.open(temp, os.O_RDONLY | os.O_DIRECTORY)
            @contextlib.contextmanager
            def pinned_dir(*args, **kwargs):
                yield directory
            class Process:
                pid = 99999999
                returncode = code
                stderr = None
                def __init__(self, args, **kwargs):
                    self.kwargs = kwargs
                    r, w = os.pipe()
                    os.close(w)
                    self.stdout = os.fdopen(r, "rb", buffering=0)
                    if kwargs["stderr"] == vm.subprocess.PIPE:
                        r, w = os.pipe()
                        # Linux pipe capacity may be8KiB; stream through a thread.
                        import threading
                        def feed():
                            try:
                                vm.write_all(w, diagnostic)
                            except BrokenPipeError:
                                pass
                            finally:
                                os.close(w)
                        self.thread = threading.Thread(target=feed)
                        if len(diagnostic) <= 8192:
                            feed()
                        else:
                            self.thread.start()
                        self.stderr = os.fdopen(r, "rb", buffering=0)
                def wait(self, timeout=None):
                    return self.returncode
                def poll(self):
                    return self.returncode
            try:
                with patch.object(vm, "open_dir", side_effect=pinned_dir), patch.object(vm, "require_owner"), patch.object(vm.subprocess, "Popen", side_effect=Process) as popen, patch.object(vm.os, "killpg", side_effect=ProcessLookupError):
                    yield {"path": vm.TOOLS["docker"], "sha256": vm.digest(b"reviewed binary")}, popen
            finally:
                os.close(directory)

    def test_pg_capture_exact_and_oversize_never_returns_raw_stderr(self):
        args = ["--host", "unix:///var/run/docker.sock", "--config", vm.RUNTIME + "/docker-empty"] + vm.pg_args("a" * 64, "negative")
        for diagnostic, expected in ((PostgresDiagnosticTests.DIAGNOSTIC, True), (b"connection refused", False), (b"x" * 8192, False)):
            with self.child(diagnostic) as (tool, popen):
                result = vm.run_tool(tool, args, vm.time.monotonic() + 15, negative_pg=True)
                self.assertEqual(result, (2, b"", expected, len(diagnostic)))
                self.assertEqual(popen.call_args.kwargs["stderr"], vm.subprocess.PIPE)
        with self.child(b"x" * 8193) as (tool, _), self.assertRaises(vm.LabError) as caught:
            vm.run_tool(tool, args, vm.time.monotonic() + 15, negative_pg=True)
        self.assertEqual(caught.exception.code, "pg_diagnostic_limit")

    def test_non_pg_negative_children_stderr_discarded(self):
        with self.child(b"synthetic-secret") as (tool, popen):
            self.assertEqual(vm.run_tool(tool, ["image", "inspect", "fixed"], vm.time.monotonic() + 15), (2, b""))
        self.assertEqual(popen.call_args.kwargs["stderr"], vm.subprocess.DEVNULL)

    def test_pg_timeout_after_auth_prefix_clears_buffer_and_never_passes(self):
        args = ["--host", "unix:///var/run/docker.sock", "--config", vm.RUNTIME + "/docker-empty"] + vm.pg_args("a" * 64, "negative")
        buffers = []
        def capture(value=b""):
            buffer = bytearray(value)
            buffers.append(buffer)
            return buffer
        with self.child(PostgresDiagnosticTests.DIAGNOSTIC) as (tool, _), patch.object(vm, "bytearray", side_effect=capture, create=True), patch.object(vm.time, "monotonic", side_effect=[0, 0, 0, 0, 20]), self.assertRaises(vm.LabError) as caught:
            vm.run_tool(tool, args, 15, negative_pg=True)
        self.assertEqual(caught.exception.code, "timeout")
        self.assertTrue(not buffers[0])


def canonical_bytes(value):
    return json.dumps(value).encode()


if __name__ == "__main__":
    unittest.main()
