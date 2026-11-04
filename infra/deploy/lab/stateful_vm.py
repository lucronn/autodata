#!/usr/bin/python3
"""Fixed-path, fail-closed disposable offline KVM lab controller.

This module is intentionally independent of every production deployment helper.
Approval is a local administrator decision, never cloud/deployment authority.
"""
import contextlib
import ctypes
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

FILES = {"stateful_vm.py": 1048576, "stateful_probe.py": 262144,
         "compose.stateful.yaml": 65536, "postgres-seed.sql": 65536}
TOOLS = {"python": "/usr/bin/python3", "docker": "/usr/bin/docker",
         "docker_compose": "/usr/libexec/docker/cli-plugins/docker-compose",
         "findmnt": "/usr/bin/findmnt", "systemd_detect_virt": "/usr/bin/systemd-detect-virt"}
SEAWEED_REFERENCE = "ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d"
SEAWEED_ID = "sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5"
VERBS = ("install", "deliver", "start", "seed", "check", "stop", "recover")
AUTHORITY = ("application_verified", "cloud_staging_verified", "production_ready",
             "deployment_authorized", "cutover_authorized")
CHECKS = ("identity", "mounts", "cache", "profile", "secrets", "postgres", "nats",
          "s3", "negative_auth", "no_work", "children_reaped")
DATA = "/var/lib/autodata-lab"
RUNTIME = "/run/autodata-lab"
RELEASES = "/opt/autodata-lab/releases"
APPROVAL = "/etc/autodata-lab/approval.json"
BIN = "/opt/autodata-lab/bin/stateful_vm.py"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class LabError(Exception):
    def __init__(self, code="invalid", exit_code=2):
        super().__init__(code)
        self.code, self.exit_code = code, exit_code


def require(condition, code="invalid", exit_code=2):
    if not condition:
        raise LabError(code, exit_code)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def strict_json(data, limit=65536):
    require(isinstance(data, bytes) and len(data) <= limit)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(LabError()))
    except (ValueError, UnicodeError, RecursionError):
        raise LabError() from None
    require(type(value) is dict)
    return value


def uuid_text(value, version=None):
    try:
        parsed = uuid.UUID(value)
        return str(parsed) == value and (version is None or parsed.version == version)
    except (ValueError, TypeError, AttributeError):
        return False


def bridge_name(run):
    require(uuid_text(run, 4))
    return "adlab-" + run.replace("-", "")[:9]


def validate_approval(value, source_sha, run_id):
    keys = {"schema_version", "operation", "authorization_id", "run_id", "expires_at",
            "source_sha", "machine_id", "product_uuid", "boot_id", "data_uuid",
            "hypervisor_config_sha256", "helper_files", "images", "tools"}
    require(type(value) is dict and set(value) == keys)
    require(type(value["schema_version"]) is int and value["schema_version"] == 1)
    require(value["operation"] == "disposable-offline-stateful-vm")
    require(re.fullmatch("[0-9a-f]{40}", source_sha or "") is not None)
    require(uuid_text(run_id, 4) and value["run_id"] == run_id and value["source_sha"] == source_sha)
    require(uuid_text(value["authorization_id"], 4))
    for name in ("product_uuid", "boot_id", "data_uuid"):
        require(uuid_text(value[name]))
    require(type(value["machine_id"]) is str and re.fullmatch("[0-9a-f]{32}", value["machine_id"]) is not None)
    require(type(value["hypervisor_config_sha256"]) is str and HEX64.fullmatch(value["hypervisor_config_sha256"]))
    try:
        require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value["expires_at"]) is not None)
        expiry = dt.datetime.strptime(value["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        remaining = (expiry - dt.datetime.now(dt.timezone.utc)).total_seconds()
        require(0 < remaining <= 86400, "approval_expired", 3)
    except (TypeError, ValueError):
        raise LabError() from None
    inventory = value["helper_files"]
    require(type(inventory) is list and len(inventory) == 4)
    require([i.get("path") if type(i) is dict else None for i in inventory] ==
            ["infra/deploy/lab/" + n for n in sorted(FILES)])
    for item in inventory:
        name = item["path"].rsplit("/", 1)[1]
        require(set(item) == {"path", "bytes", "sha256"})
        require(type(item["bytes"]) is int and 0 < item["bytes"] <= FILES[name])
        require(type(item["sha256"]) is str and HEX64.fullmatch(item["sha256"]))
    require(type(value["images"]) is dict and set(value["images"]) == {"postgres", "nats", "minio", "probe"})
    for item in value["images"].values():
        require(type(item) is dict and set(item) == {"reference", "image_id", "platform"})
        require(type(item["reference"]) is str and re.fullmatch(r"[a-z0-9.:-]+/[a-z0-9/_.-]+@sha256:[0-9a-f]{64}", item["reference"]))
        require(type(item["image_id"]) is str and re.fullmatch("sha256:[0-9a-f]{64}", item["image_id"]))
        require(item["platform"] == "linux/amd64")
    require(value["images"]["minio"]["reference"] == SEAWEED_REFERENCE and value["images"]["minio"]["image_id"] == SEAWEED_ID)
    require(type(value["tools"]) is dict and set(value["tools"]) == set(TOOLS))
    for name, path in TOOLS.items():
        item = value["tools"][name]
        require(type(item) is dict and set(item) == {"path", "sha256"} and item["path"] == path)
        require(type(item["sha256"]) is str and HEX64.fullmatch(item["sha256"]))
    return value


def require_owner(info, uid=0, gid=0):
    require(info.st_uid == uid and info.st_gid == gid, "ownership")


def fingerprint(info):
    return tuple(getattr(info, n) for n in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


@contextlib.contextmanager
def open_dir(path, private=False):
    require(path.startswith("/") and all(p not in (".", "..") for p in path.split("/")))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in [p for p in path.split("/") if p]:
            info = os.fstat(fd)
            require_owner(info)
            require(not info.st_mode & 0o022, "parent_permissions")
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = new
        info = os.fstat(fd)
        require_owner(info)
        require(not info.st_mode & 0o022, "parent_permissions")
        if private:
            require(stat.S_IMODE(info.st_mode) == 0o700, "private_permissions")
        yield fd
    finally:
        os.close(fd)


def read_file(path, limit, mode=None, uid=0, gid=0):
    parent, name = path.rsplit("/", 1)
    with open_dir(parent) as directory:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        try:
            before = os.fstat(fd)
            require_owner(before, uid, gid)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit, "file_type")
            if mode is not None:
                require(stat.S_IMODE(before.st_mode) == mode, "file_permissions")
            chunks, count = [], 0
            while True:
                block = os.read(fd, min(65536, limit + 1 - count))
                if not block:
                    break
                chunks.append(block)
                count += len(block)
                require(count <= limit, "file_size")
            require(fingerprint(before) == fingerprint(os.fstat(fd)), "file_drift")
            require(fingerprint(before) == fingerprint(os.stat(name, dir_fd=directory, follow_symlinks=False)), "file_drift")
            return b"".join(chunks)
        finally:
            os.close(fd)


def write_all(fd, data):
    while data:
        written = os.write(fd, data)
        require(written > 0, "short_write", 4)
        data = data[written:]


def atomic_json(path, value):
    data = canonical(value) + b"\n"
    require(len(data) <= 65536, "state_size", 4)
    parent, name = path.rsplit("/", 1)
    with open_dir(parent, private=True) as directory:
        temp = ".pending-" + str(uuid.uuid4())
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
        try:
            write_all(fd, data)
            os.fsync(fd)
            os.close(fd)
            fd = None
            try:
                existing = os.stat(name, dir_fd=directory, follow_symlinks=False)
                require_owner(existing)
                require(stat.S_ISREG(existing.st_mode) and existing.st_nlink == 1 and stat.S_IMODE(existing.st_mode) == 0o600)
            except FileNotFoundError:
                pass
            os.rename(temp, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temp, dir_fd=directory)
            except FileNotFoundError:
                pass


def noreplace(directory, source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, source.encode(), directory, target.encode(), 1) != 0:
        err = ctypes.get_errno()
        raise OSError(err, "promotion failed")


def verify_bundle(path, bundle):
    with open_dir(path) as directory:
        require(stat.S_IMODE(os.fstat(directory).st_mode) == 0o500, "release_permissions")
        require(set(os.listdir(directory)) == set(bundle), "release_inventory")
    for name, data in bundle.items():
        require(read_file(path + "/" + name, FILES[name], 0o444) == data, "release_drift")


def install_bundle(parent, sha, authorization, bundle, recheck):
    final = parent + "/" + sha
    with open_dir(parent) as directory:
        try:
            os.stat(sha, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            verify_bundle(final, bundle)
            recheck()
            return False
        temp = ".install-" + authorization
        try:
            os.mkdir(temp, 0o700, dir_fd=directory)
        except FileExistsError:
            raise LabError("stale_install", 6) from None
        owned, promoted = [], False
        tfd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        pinned = os.fstat(tfd)
        try:
            for name in sorted(bundle):
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444, dir_fd=tfd)
                owned.append((name, os.fstat(fd).st_ino))
                try:
                    write_all(fd, bundle[name])
                    os.fchmod(fd, 0o444)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fchmod(tfd, 0o500)
            os.fsync(tfd)
            verify_bundle(parent + "/" + temp, bundle)
            recheck()
            noreplace(directory, temp, sha)
            promoted = True
            os.fsync(directory)
            return True
        except BaseException:
            if promoted:
                raise LabError("post_commit_failure", 6) from None
            try:
                current = os.stat(temp, dir_fd=directory, follow_symlinks=False)
                require((current.st_dev, current.st_ino) == (pinned.st_dev, pinned.st_ino), "cleanup_identity", 6)
                require(set(os.listdir(tfd)) == {n for n, _ in owned}, "cleanup_inventory", 6)
                os.fchmod(tfd, 0o700)
                for name, inode in owned:
                    require(os.stat(name, dir_fd=tfd, follow_symlinks=False).st_ino == inode, "cleanup_identity", 6)
                    os.unlink(name, dir_fd=tfd)
                os.rmdir(temp, dir_fd=directory)
                os.fsync(directory)
            except BaseException:
                raise LabError("cleanup_incomplete", 6) from None
            raise
        finally:
            os.close(tfd)


def pseudo_read(path, limit=65536):
    # proc/sysfs have synthetic size/link metadata. Never use this for disk inputs.
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        data = bytearray()
        while True:
            block = os.read(fd, min(4096, limit + 1 - len(data)))
            if not block:
                return bytes(data)
            data.extend(block)
            require(len(data) <= limit, "pseudo_size")
    finally:
        os.close(fd)


def run_tool(tool, args, deadline, timeout=15):
    """Execute the verified descriptor; bound output, process group and cleanup."""
    path = tool["path"]
    parent, name = path.rsplit("/", 1)
    with open_dir(parent) as directory:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    proc, selector, old_handlers = None, selectors.DefaultSelector(), {}
    try:
        before = os.fstat(fd)
        require_owner(before)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o022, "tool_permissions")
        data = bytearray()
        while True:
            block = os.read(fd, 65536)
            if not block:
                break
            data.extend(block)
            require(len(data) <= 134217728, "tool_size")
        require(digest(data) == tool["sha256"] and fingerprint(before) == fingerprint(os.fstat(fd)), "tool_drift")
        os.lseek(fd, 0, os.SEEK_SET)
        def cancelled(signum, _frame):
            raise LabError("cancelled", 6)
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, cancelled)
        end = min(deadline, time.monotonic() + timeout)
        require(end > time.monotonic(), "timeout", 5)
        proc = subprocess.Popen([path] + list(args), executable="/proc/self/fd/" + str(fd), pass_fds=(fd,),
                                cwd="/", env={"DOCKER_HOST": "unix:///var/run/docker.sock", "DOCKER_CONFIG": RUNTIME + "/docker-empty"},
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ)
        output = bytearray()
        while selector.get_map():
            require(time.monotonic() < end, "timeout", 5)
            for key, _ in selector.select(min(0.1, end - time.monotonic())):
                block = os.read(key.fd, 65536)
                if not block:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(block)
                    require(len(output) <= 65536, "child_output", 4)
        proc.wait(timeout=max(0.001, end - time.monotonic()))
        return proc.returncode, bytes(output)
    except subprocess.TimeoutExpired:
        raise LabError("timeout", 5) from None
    finally:
        # Retain cancellation ownership until the entire group and pipes are closed.
        for signum in old_handlers:
            signal.signal(signum, signal.SIG_IGN)
        try:
            if proc is not None:
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    try:
                        os.killpg(proc.pid, sig)
                    except ProcessLookupError:
                        break
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        continue
                require(proc.poll() is not None, "child_unreaped", 6)
                proc.stdout.close()
        finally:
            selector.close()
            os.close(fd)
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)


def empty_receipt(verb, sha, run):
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = dict(schema_version=1, operation=verb if verb in VERBS else "invalid", authorization_id=None,
                  run_id=run if uuid_text(run, 4) else None, source_sha=sha if re.fullmatch("[0-9a-f]{40}", sha or "") else None,
                  boot_id=None, started_at=now, finished_at=now, status="failed", failure_code="invalid",
                  approval_sha256=None, profile_sha256=None, image_ids={}, resource_ids={},
                  checks={k: None for k in CHECKS}, cleanup={"status": "not_needed"},
                  material_committed=False, stateful_started=False, fixture_seeded=False,
                  persistence_verified=False, recovery_verified=False)
    result.update({k: False for k in AUTHORITY})
    return result


def refuse_production():
    require(not any(os.path.lexists(p) for p in ("/etc/autodata", "/opt/autodata/current")), "production_object", 3)


def observe_machine(approval, deadline):
    refuse_production()
    for key, path in (("machine_id", "/etc/machine-id"), ("product_uuid", "/sys/class/dmi/id/product_uuid"),
                      ("boot_id", "/proc/sys/kernel/random/boot_id")):
        first = pseudo_read(path, 256).decode("ascii").strip().lower()
        require(first == approval[key] and pseudo_read(path, 256).decode("ascii").strip().lower() == first,
                "machine_identity", 3)
    code, output = run_tool(approval["tools"]["systemd_detect_virt"], [], deadline)
    require(code == 0 and output == b"kvm\n", "not_kvm", 3)
    routes = pseudo_read("/proc/net/route").decode("ascii").splitlines()
    for line in routes[1:]:
        parts = line.split()
        require(len(parts) >= 8 and parts[1] != "00000000", "default_route", 3)
    for line in pseudo_read("/proc/net/ipv6_route").decode("ascii").splitlines():
        parts = line.split()
        require(len(parts) >= 10 and not (parts[0] == "0" * 32 and parts[1] == "00"), "default_route", 3)


def observe_mounts(approval, deadline):
    observed = {}
    for target in (DATA, RUNTIME):
        code, output = run_tool(approval["tools"]["findmnt"],
                                ["--json", "--list", "--mountpoint", target, "--output", "TARGET,UUID,FSTYPE,OPTIONS"], deadline)
        require(code == 0, "mount_unavailable", 3)
        parsed = strict_json(output)
        require(set(parsed) == {"filesystems"} and type(parsed["filesystems"]) is list and len(parsed["filesystems"]) == 1,
                "missing_mount", 3)
        item = parsed["filesystems"][0]
        require(type(item) is dict and set(item) == {"target", "uuid", "fstype", "options"} and item["target"] == target,
                "mount_identity", 3)
        options = set(item["options"].split(","))
        require("rw" in options and "ro" not in options, "mount_readonly", 3)
        if target == DATA:
            require(item["uuid"] == approval["data_uuid"] and item["fstype"] in ("ext4", "xfs"), "data_mount", 3)
        else:
            require(item["fstype"] == "tmpfs" and {"nosuid", "nodev", "noexec"} <= options, "tmpfs_mount", 3)
        with open_dir(target, private=True) as fd:
            info = os.fstat(fd)
            observed[target] = [info.st_dev, info.st_ino, item["uuid"], item["fstype"]]
    return observed


def observe_interfaces(owned):
    names = set(os.listdir("/sys/class/net"))
    require(names <= ({"lo", "docker0"} | owned) and "lo" in names, "external_interface", 3)
    return names


def validate_inventory(containers, networks, resources):
    ids = set(resources.get("containers", {}).values())
    expected_network = resources.get("network")
    require(all(type(c) is dict and c.get("Id") in ids for c in containers), "unowned_container", 3)
    for network in networks:
        if network.get("Name") in ("bridge", "host", "none"):
            require(not network.get("Containers"), "attached_builtin_network", 3)
        else:
            require(network.get("Id") == expected_network and expected_network is not None, "unowned_network", 3)


def make_private(path):
    parent, name = path.rsplit("/", 1)
    with open_dir(parent, private=True) as fd:
        try:
            os.mkdir(name, 0o700, dir_fd=fd)
            os.fsync(fd)
        except FileExistsError:
            pass
    with open_dir(path, private=True):
        pass


@contextlib.contextmanager
def operation_lock():
    make_private(RUNTIME + "/state")
    with open_dir(RUNTIME + "/state", private=True) as directory:
        fd = os.open("operation.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        info = os.fstat(fd)
        require_owner(info)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600, "lock_identity", 3)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LabError("busy", 3) from None
        yield
    finally:
        os.close(fd)


class Controller:
    def __init__(self, approval, receipt):
        self.approval, self.receipt = approval, receipt
        self.deadline = time.monotonic() + 270
        self.total_output = 0
        self.mounts = None
        self.run = approval["run_id"]
        self.sha = approval["source_sha"]
        self.run_path = DATA + "/runs/" + self.run
        self.resources = {"containers": {}, "network": None}
        self.state = None

    def tool(self, name, args, timeout=15):
        code, output = run_tool(self.approval["tools"][name], args, self.deadline, timeout)
        self.total_output += len(output)
        require(self.total_output <= 1048576, "total_output", 4)
        return code, output

    def docker(self, args):
        return self.tool("docker", ["--host", "unix:///var/run/docker.sock", "--config", RUNTIME + "/docker-empty"] + args)

    def recheck(self):
        current = validate_approval(strict_json(read_file(APPROVAL, 65536, 0o600)), self.sha, self.run)
        require(current == self.approval, "approval_drift", 3)
        observe_machine(current, self.deadline)
        require(observe_mounts(current, self.deadline) == self.mounts, "mount_drift", 3)

    def inventory(self):
        result = []
        for kind in ("container", "network"):
            code, output = self.docker([kind, "ls", "--quiet", "--no-trunc"] if kind == "container" else [kind, "ls", "--quiet", "--no-trunc"])
            # container ls must include stopped resources, not just running ones.
            if kind == "container":
                code, output = self.docker(["container", "ls", "--all", "--quiet", "--no-trunc"])
            require(code == 0, "inventory_unavailable", 3)
            ids = output.decode("ascii").splitlines()
            require(len(ids) <= 64 and all(re.fullmatch("[0-9a-f]{64}", x) for x in ids), "inventory_format", 3)
            if ids:
                code, output = self.docker([kind, "inspect"] + ids)
                require(code == 0, "inventory_unavailable", 3)
                parsed = json.loads(output)
                require(type(parsed) is list and len(parsed) == len(ids), "inventory_format", 3)
            else:
                parsed = []
            result.append(parsed)
        validate_inventory(*result, self.resources)
        return result

    def prepare(self):
        with open_dir("/etc/autodata-lab", private=True), open_dir("/opt/autodata-lab", private=True), open_dir(RELEASES, private=True):
            pass
        observe_machine(self.approval, self.deadline)
        self.receipt["checks"]["identity"] = True
        self.mounts = observe_mounts(self.approval, self.deadline)
        self.receipt["checks"]["mounts"] = True
        inventory = {x["path"].rsplit("/", 1)[1]: x for x in self.approval["helper_files"]}
        require(digest(read_file(BIN, FILES["stateful_vm.py"], 0o444)) == inventory["stateful_vm.py"]["sha256"], "installed_helper_drift", 3)
        return inventory

    def load_state(self):
        try:
            self.state = strict_json(read_file(self.run_path + "/state.json", 65536, 0o600))
        except FileNotFoundError:
            self.state = None
            return
        require(self.state.get("binding") == self.binding(), "run_binding_drift", 6)
        resources = self.state.get("resources")
        require(type(resources) is dict and set(resources) == {"containers", "network"}, "state_invalid", 6)
        require(type(resources["containers"]) is dict and set(resources["containers"]) <= {"postgres", "nats", "minio"}, "state_invalid", 6)
        require(all(type(v) is str and re.fullmatch("[0-9a-f]{64}", v) for v in resources["containers"].values()), "state_invalid", 6)
        require(resources["network"] is None or (type(resources["network"]) is str and re.fullmatch("[0-9a-f]{64}", resources["network"])), "state_invalid", 6)
        self.resources = resources

    def binding(self):
        keys = ("source_sha", "run_id", "machine_id", "product_uuid", "data_uuid", "hypervisor_config_sha256", "helper_files", "images", "tools")
        return {k: self.approval[k] for k in keys}

    def save(self, phase):
        self.recheck()
        self.state.update(phase=phase, boot_id=self.approval["boot_id"], authorization_id=self.approval["authorization_id"], resources=self.resources)
        atomic_json(self.run_path + "/state.json", self.state)

    def cache(self):
        for name, pin in self.approval["images"].items():
            code, output = self.docker(["image", "inspect", pin["reference"]])
            require(code == 0, "image_unavailable", 3)
            images = json.loads(output)
            require(type(images) is list and len(images) == 1, "image_invalid", 3)
            image = images[0]
            require(image.get("Id") == pin["image_id"] and image.get("Os") == "linux" and image.get("Architecture") == "amd64" and pin["reference"] in image.get("RepoDigests", []), "image_drift", 3)
            self.receipt["image_ids"][name] = pin["image_id"]
        self.receipt["checks"]["cache"] = True

    def install(self, inventory):
        self.load_state()
        containers, networks = self.inventory()
        require(not containers and self.resources == {"containers": {}, "network": None}, "install_not_bare", 3)
        observe_interfaces(set())
        bundle = {}
        inbox = DATA + "/incoming/" + self.sha
        with open_dir(inbox, private=True) as fd:
            require(set(os.listdir(fd)) == set(FILES), "inbox_inventory")
        for name in sorted(FILES):
            data = read_file(inbox + "/" + name, FILES[name], 0o444)
            require(len(data) == inventory[name]["bytes"] and digest(data) == inventory[name]["sha256"], "inbox_drift")
            bundle[name] = data
        self.cache()
        self.recheck()
        make_private(DATA + "/runs")
        make_private(self.run_path)
        make_private(self.run_path + "/receipts")
        if self.state is None:
            self.state = {"binding": self.binding(), "resources": self.resources, "bundle_sha256": None, "delivery_boot_id": None, "seeded": False}
        self.save("install_pending")
        try:
            changed = install_bundle(RELEASES, self.sha, self.approval["authorization_id"], bundle, self.recheck)
            self.receipt["material_committed"] = changed
        except LabError as error:
            if error.code == "post_commit_failure":
                self.receipt["material_committed"] = True
            raise
        self.save("installed")

    def finish(self, verb):
        self.receipt["resource_ids"] = self.resources
        self.receipt["checks"]["children_reaped"] = True
        self.receipt["finished_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.recheck()
        atomic_json(self.run_path + "/receipts/" + self.approval["authorization_id"] + "-" + verb + ".json", self.receipt)


def install_cli(verb, source_sha, run_id):
    receipt = empty_receipt(verb, source_sha, run_id)
    try:
        require(verb in VERBS and receipt["source_sha"] is not None and uuid_text(run_id, 4))
        approval = validate_approval(strict_json(read_file(APPROVAL, 65536, 0o600)), source_sha, run_id)
        receipt.update(authorization_id=approval["authorization_id"], boot_id=approval["boot_id"], approval_sha256=digest(canonical(approval)))
        # FD3 is a closed delivery channel, never an alternate config/argv surface.
        try:
            os.fstat(3)
            inherited = True
        except OSError as error:
            require(error.errno == errno.EBADF)
            inherited = False
        require(verb == "deliver" or not inherited, "unexpected_fd3")
        controller = Controller(approval, receipt)
        inventory = controller.prepare()
        with operation_lock():
            controller.recheck()
            make_private(RUNTIME + "/docker-empty")
            with open_dir(RUNTIME + "/docker-empty", private=True) as fd:
                require(not os.listdir(fd), "docker_config_not_empty", 3)
            if verb == "install":
                controller.install(inventory)
            else:
                raise LabError("lifecycle_unavailable", 3)
            receipt.update(status="passed", failure_code=None)
            controller.finish(verb)
        return 0, receipt
    except FileNotFoundError:
        receipt["status"] = "failed"
        receipt["failure_code"] = "missing_prerequisite"
        return 3, receipt
    except LabError as error:
        receipt["failure_code"] = error.code
        receipt["status"] = "incomplete" if error.exit_code == 6 else "failed"
        if error.code == "post_commit_failure":
            receipt["material_committed"] = True
        return error.exit_code, receipt
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        receipt["status"] = "failed"
        receipt["failure_code"] = "operation_failed"
        return 4, receipt


if __name__ == "__main__":
    os.environ.clear()
    os.chdir("/")
    os.umask(0o077)
    if len(sys.argv) == 4:
        exit_code, result = install_cli(*sys.argv[1:])
    else:
        exit_code, result = 2, empty_receipt("invalid", "", "")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    raise SystemExit(exit_code)
