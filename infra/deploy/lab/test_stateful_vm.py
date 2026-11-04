"""Offline contract tests. External identity/tool observations are intercepted."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
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


if __name__ == "__main__":
    unittest.main()
