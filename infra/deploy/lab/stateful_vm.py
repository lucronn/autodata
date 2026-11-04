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
SECRET_KEYS = ("postgres_password", "nats_writer_password", "nats_reader_password", "s3_writer_access", "s3_writer_secret", "s3_reader_access", "s3_reader_secret")


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


def render_profile(approval, run_id):
    require(run_id == approval["run_id"] and uuid_text(run_id, 4))
    path = RELEASES + "/" + approval["source_sha"] + "/compose.stateful.yaml"
    template = strict_json(read_file(path, 65536, 0o444))
    labels = {"autodata.lab": "stateful-v1", "autodata.run": run_id, "autodata.source": approval["source_sha"]}
    replacements = {"@PROJECT@": "autodata-lab-" + run_id.replace("-", ""), "@RUN@": run_id,
                    "@BRIDGE@": bridge_name(run_id), "@DATA@": DATA + "/runs/" + run_id + "/data",
                    "@SECRETS@": RUNTIME + "/delivery/" + run_id, "@RELEASE@": RELEASES + "/" + approval["source_sha"], "@LABELS@": labels}
    replacements.update({"@" + name.upper() + "_IMAGE@": pin["reference"] for name, pin in approval["images"].items()})
    def substitute(value):
        if isinstance(value, str):
            if value in replacements:
                return replacements[value]
            for token, replacement in replacements.items():
                if token in value:
                    require(isinstance(replacement, str))
                    value = value.replace(token, replacement)
            require("@" not in value or "@sha256:" in value, "template_token")
            return value
        if isinstance(value, list):
            return [substitute(v) for v in value]
        if isinstance(value, dict):
            return {k: substitute(v) for k, v in value.items()}
        return value
    return substitute(template)


def validate_bundle(value, run):
    require(type(value) is dict and set(value) == set(SECRET_KEYS) | {"schema_version", "run_id"}, "delivery_schema")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["run_id"] == run, "delivery_identity")
    require(all(type(value[k]) is str and HEX64.fullmatch(value[k]) for k in SECRET_KEYS), "delivery_secret")
    require(len({value[k] for k in SECRET_KEYS}) == len(SECRET_KEYS), "delivery_distinct")
    return value


def read_pipe_frame(fd):
    end, data = time.monotonic() + 15, bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while True:
            remaining = end - time.monotonic()
            require(remaining > 0, "delivery_timeout", 5)
            require(selector.select(remaining), "delivery_timeout", 5)
            block = os.read(fd, min(4096, 16385 - len(data)))
            if not block:
                break
            data.extend(block)
            require(len(data) <= 16384, "delivery_size")
    require(data.endswith(b"\n") and data.count(b"\n") == 1, "delivery_frame")
    return bytes(data)


def read_delivery(run):
    info = os.fstat(3)
    require(stat.S_ISFIFO(info.st_mode) and fcntl.fcntl(3, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY, "delivery_pipe")
    return validate_bundle(strict_json(read_pipe_frame(3), 16384), run)


def delivery_material(bundle):
    password = bundle["postgres_password"]
    invalid = ("1" if password[0] != "1" else "2") + password[1:]
    nats = {"listen": "0.0.0.0:4222", "jetstream": {"store_dir": "/data/jetstream"},
            "authorization": {"users": [
                {"user": "writer", "password": bundle["nats_writer_password"], "permissions": {"publish": ["lab.probe", "$JS.API.>"], "subscribe": ["_INBOX.>"]}},
                {"user": "reader", "password": bundle["nats_reader_password"], "permissions": {"publish": ["$JS.API.INFO"], "subscribe": ["_INBOX.>"]}}]}}
    s3 = {"identities": [{"name": "writer", "credentials": [{"accessKey": bundle["s3_writer_access"], "secretKey": bundle["s3_writer_secret"]}], "actions": ["Read:lab-stateful", "Write:lab-stateful", "List:lab-stateful"]},
                         {"name": "reader", "credentials": [{"accessKey": bundle["s3_reader_access"], "secretKey": bundle["s3_reader_secret"]}], "actions": ["Read:lab-stateful"]}]}
    probe = {k: v for k, v in bundle.items() if k != "postgres_password"}
    prefix = "127.0.0.1:5432:workshop_lab:lab_admin:"
    return {"postgres": (999, {"POSTGRES_PASSWORD": (password + "\n").encode(), "valid.pgpass": (prefix + password + "\n").encode(), "invalid.pgpass": (prefix + invalid + "\n").encode()}),
            "nats": (1000, {"nats.conf": canonical(nats) + b"\n"}), "minio": (1000, {"s3.json": canonical(s3) + b"\n"}),
            "probe": (1000, {"probe.json": canonical(probe) + b"\n"})}


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
def open_dir(path, private=False, leaf_uid=0, leaf_gid=0):
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
        require_owner(info, leaf_uid, leaf_gid)
        require(not info.st_mode & 0o022, "parent_permissions")
        if private:
            require(stat.S_IMODE(info.st_mode) == 0o700, "private_permissions")
        yield fd
    finally:
        os.close(fd)


def read_file(path, limit, mode=None, uid=0, gid=0):
    parent, name = path.rsplit("/", 1)
    with open_dir(parent, leaf_uid=uid, leaf_gid=gid) as directory:
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


def run_tool(tool, args, deadline, timeout=15, negative_pg=False):
    """Execute the verified descriptor; bound output, process group and cleanup."""
    if negative_pg:
        prefix = ["--host", "unix:///var/run/docker.sock", "--config", RUNTIME + "/docker-empty"]
        require(tool["path"] == TOOLS["docker"] and args[:4] == prefix and len(args) > 15, "diagnostic_command")
        # Reconstruct the complete fixed command; no generic stderr capture API.
        candidate = next((x for x in args[4:] if type(x) is str and re.fullmatch("[0-9a-f]{64}", x)), None)
        require(candidate is not None and args[4:] == pg_args(candidate, "negative"), "diagnostic_command")
    path = tool["path"]
    parent, name = path.rsplit("/", 1)
    with open_dir(parent) as directory:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    proc, selector, old_handlers = None, selectors.DefaultSelector(), {}
    diagnostic = bytearray()
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
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE if negative_pg else subprocess.DEVNULL, start_new_session=True)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ)
        if negative_pg:
            os.set_blocking(proc.stderr.fileno(), False)
            selector.register(proc.stderr, selectors.EVENT_READ)
        output = bytearray()
        while selector.get_map():
            require(time.monotonic() < end, "timeout", 5)
            for key, _ in selector.select(min(0.1, end - time.monotonic())):
                is_diagnostic = negative_pg and key.fileobj is proc.stderr
                block = os.read(key.fd, min(4096, 8193 - len(diagnostic)) if is_diagnostic else 65536)
                if not block:
                    selector.unregister(key.fileobj)
                else:
                    if is_diagnostic:
                        diagnostic.extend(block)
                        require(len(diagnostic) <= 8192, "pg_diagnostic_limit", 4)
                    else:
                        output.extend(block)
                        require(len(output) <= 65536, "child_output", 4)
        proc.wait(timeout=max(0.001, end - time.monotonic()))
        if negative_pg:
            count = len(diagnostic)
            return proc.returncode, bytes(output), classify_pg_diagnostic(diagnostic, proc.returncode, output), count
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
                if proc.stderr is not None:
                    proc.stderr.close()
        finally:
            for i in range(len(diagnostic)):
                diagnostic[i] = 0
            diagnostic.clear()
            selector.close()
            os.close(fd)
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)


def classify_pg_diagnostic(buffer, code, stdout):
    expected = (b'psql: error: connection to server at "127.0.0.1", port 5432 failed: FATAL:  password authentication failed for user "lab_admin"\n'
                b'password retrieved from file "/run/lab/invalid.pgpass"\n')
    try:
        require(len(buffer) <= 8192, "pg_diagnostic_limit", 4)
        return code == 2 and not stdout and buffer == expected
    finally:
        for i in range(len(buffer)):
            buffer[i] = 0
        buffer.clear()


def pg_args(container, kind, run=None):
    require(type(container) is str and re.fullmatch("[0-9a-f]{64}", container), "pg_identity", 6)
    require(kind in ("positive", "negative", "locale", "version", "hba", "seed", "check"))
    args = ["exec", "--user", "999:999"]
    for value in ("LC_ALL=C", "PGSSLMODE=disable", "PGGSSENCMODE=disable", "PGPASSFILE=/run/lab/" + ("invalid" if kind == "negative" else "valid") + ".pgpass"):
        args += ["--env", value]
    args += [container, "psql", "-X", "-w", "--host=127.0.0.1", "--port=5432", "--username=lab_admin", "--dbname=workshop_lab", "--set=ON_ERROR_STOP=1", "--tuples-only", "--no-align"]
    if kind in ("seed", "check"):
        require(uuid_text(run, 4))
        args += ["--quiet", "--set=mode=" + kind, "--set=run_id=" + run, "--file=/lab/postgres-seed.sql"]
    else:
        queries = {"positive": "SELECT 1", "negative": "SELECT 1", "locale": "SHOW lc_messages", "version": "SHOW server_version_num",
                   "hba": "SELECT count(*) > 0 AND bool_and(auth_method = 'scram-sha-256' AND error IS NULL) FROM pg_hba_file_rules WHERE type IN ('host','hostssl','hostnossl')"}
        args += ["--command=" + queries[kind]]
    return args


PROBE_CHECKS = ("nats_connected", "nats_fixture", "nats_writer_denied", "nats_reader_denied", "s3_connected", "s3_fixture", "s3_reader_denied", "s3_anonymous_denied", "fixture_unchanged")
PROBE_MEASUREMENTS = ("nats_message_count", "s3_object_bytes", "nats_payload_sha256", "s3_payload_sha256")


def validate_probe_result(data, mode, run):
    value = strict_json(data, 32768)
    require(set(value) == {"schema_version", "mode", "run_id", "status", "checks", "measurements"}, "probe_schema", 4)
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["mode"] == mode and value["run_id"] == run and value["status"] == "passed", "probe_identity", 4)
    checks, measurements = value["checks"], value["measurements"]
    require(type(checks) is dict and set(checks) == set(PROBE_CHECKS) and all(v is None or type(v) is bool for v in checks.values()), "probe_checks", 4)
    required = {"nats_connected", "s3_connected"}
    if mode != "ready":
        required |= {"nats_fixture", "s3_fixture", "fixture_unchanged"}
    if mode == "deny":
        required |= {"nats_writer_denied", "nats_reader_denied", "s3_reader_denied", "s3_anonymous_denied"}
    require(all(checks[k] is True if k in required else checks[k] is None for k in PROBE_CHECKS), "probe_checks", 4)
    require(type(measurements) is dict and set(measurements) == set(PROBE_MEASUREMENTS), "probe_measurements", 4)
    if mode == "ready":
        require(all(v is None for v in measurements.values()), "probe_measurements", 4)
    else:
        payload = ("autodata-lab-v1:" + run).encode()
        require(type(measurements["nats_message_count"]) is int and measurements["nats_message_count"] == 1 and
                type(measurements["s3_object_bytes"]) is int and measurements["s3_object_bytes"] == len(payload) and
                measurements["nats_payload_sha256"] == digest(payload) and measurements["s3_payload_sha256"] == digest(payload), "probe_measurements", 4)
    return value


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
        self.hard_deadline = time.monotonic() + 300
        self.deadline = self.hard_deadline - 30
        self.total_output = 0
        self.mounts = None
        self.run = approval["run_id"]
        self.sha = approval["source_sha"]
        self.run_path = DATA + "/runs/" + self.run
        self.resources = {"containers": {}, "network": None}
        self.state = None
        self.images = {}
        self.profile = None

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

    def raw_inventory(self):
        result = []
        for kind in ("container", "network"):
            code, output = self.docker([kind, "ls"] + (["--all"] if kind == "container" else []) + ["--quiet", "--no-trunc"])
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
        return result

    def inventory(self):
        result = self.raw_inventory()
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
        for tool in self.approval["tools"].values():
            data = read_file(tool["path"], 134217728)
            require(digest(data) == tool["sha256"], "tool_drift", 3)
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
            self.images[name] = image
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

    def release(self):
        bundle = {}
        for item in self.approval["helper_files"]:
            name = item["path"].rsplit("/", 1)[1]
            data = read_file(RELEASES + "/" + self.sha + "/" + name, FILES[name], 0o444)
            require(len(data) == item["bytes"] and digest(data) == item["sha256"], "release_drift", 6)
            bundle[name] = data
        verify_bundle(RELEASES + "/" + self.sha, bundle)
        self.profile = render_profile(self.approval, self.run)
        profile_hash = digest(canonical(self.profile))
        self.receipt["profile_sha256"] = profile_hash
        require(self.state is not None, "run_missing", 3)
        previous = self.state.get("profile_sha256")
        require(previous is None or previous == profile_hash, "profile_drift", 6)
        path = self.run_path + "/compose.json"
        if previous is None:
            self.recheck()
            atomic_json(path, self.profile)
            self.state["profile_sha256"] = profile_hash
            self.save("profile_committed")
        else:
            require(strict_json(read_file(path, 65536, 0o600)) == self.profile, "profile_drift", 6)

    def compose(self, args):
        return self.tool("docker_compose", ["--project-name", self.profile["name"], "--file", self.run_path + "/compose.json"] + args)

    def validate_graph(self):
        code, output = self.compose(["config", "--format", "json"])
        require(code == 0, "compose_invalid", 4)
        observed = strict_json(output)
        require(observed.get("name") == self.profile["name"] and set(observed.get("services", {})) == set(self.profile["services"]), "compose_graph", 4)
        require(set(observed.get("networks", {})) == {"lab"} and not observed.get("volumes") and not observed.get("secrets") and not observed.get("configs"), "compose_graph", 4)
        network = observed["networks"]["lab"]
        expected_network = self.profile["networks"]["lab"]
        for key in ("internal", "enable_ipv6", "driver", "labels", "driver_opts", "ipam"):
            require(network.get(key) == expected_network[key], "compose_network", 4)
        require(not network.get("external"), "compose_network", 4)
        for name, expected in self.profile["services"].items():
            actual = observed["services"][name]
            require(not set(actual) - (set(expected) | {"name"}), "compose_service_fields", 4)
            for key in set(expected) - {"volumes"}:
                require(actual.get(key) == expected[key], "compose_service", 4)
            def mounts(value):
                return sorted((m.get("type"), m.get("source"), m.get("target"), m.get("read_only", False), m.get("bind", {}).get("create_host_path", False)) for m in value)
            require(mounts(actual.get("volumes", [])) == mounts(expected["volumes"]), "compose_mounts", 4)
        self.receipt["checks"]["profile"] = True

    def deliver(self):
        bundle = read_delivery(self.run)
        bundle_hash = digest(canonical(bundle))
        require(self.state.get("bundle_sha256") in (None, bundle_hash), "bundle_changed", 6)
        self.state["bundle_sha256"] = bundle_hash
        self.state["delivery_boot_id"] = None
        self.save("delivery_pending")
        self.recheck()
        make_private(RUNTIME + "/delivery")
        base = RUNTIME + "/delivery/" + self.run
        make_private(base)
        material = delivery_material(bundle)
        # Each service directory is an atomic tmpfs transaction. Partial delivery
        # has no current-boot completion record and can never start services.
        with open_dir(base, private=True) as parent:
            require(set(os.listdir(parent)) <= set(material), "delivery_inventory", 6)
            for name, (uid, contents) in material.items():
                self.recheck()
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    temp = ".delivery-" + self.approval["authorization_id"] + "-" + name
                    os.mkdir(temp, 0o700, dir_fd=parent)
                    stage = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    try:
                        for filename, data in contents.items():
                            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=stage)
                            try:
                                write_all(fd, data)
                                os.fchown(fd, uid, uid)
                                os.fchmod(fd, 0o400)
                                os.fsync(fd)
                            finally:
                                os.close(fd)
                        os.fchown(stage, uid, uid)
                        os.fchmod(stage, 0o500)
                        os.fsync(stage)
                        self.recheck()
                        noreplace(parent, temp, name)
                        os.fsync(parent)
                    finally:
                        os.close(stage)
                self.verify_service_delivery(base, name, uid, contents)
        self.state["delivery_boot_id"] = self.approval["boot_id"]
        self.save("delivered")
        self.receipt["checks"]["secrets"] = True

    def verify_service_delivery(self, base, name, uid, contents=None):
        with open_dir(base + "/" + name, leaf_uid=uid, leaf_gid=uid) as fd:
            require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o500, "delivery_permissions", 6)
            expected = {"postgres": {"POSTGRES_PASSWORD", "valid.pgpass", "invalid.pgpass"}, "nats": {"nats.conf"}, "minio": {"s3.json"}, "probe": {"probe.json"}}[name]
            require(set(os.listdir(fd)) == expected, "delivery_inventory", 6)
        for filename in expected:
            data = read_file(base + "/" + name + "/" + filename, 16384, 0o400, uid, uid)
            if contents is not None:
                require(data == contents[filename], "delivery_drift", 6)

    def require_delivery(self):
        require(self.state.get("bundle_sha256") and self.state.get("delivery_boot_id") == self.approval["boot_id"], "redelivery_required", 3)
        base = RUNTIME + "/delivery/" + self.run
        for name, uid in (("postgres", 999), ("nats", 1000), ("minio", 1000), ("probe", 1000)):
            self.verify_service_delivery(base, name, uid)
        # Reconstitute the complete synthetic bundle in memory to bind every
        # current tmpfs credential byte to the persistent hash, never the receipt.
        probe = strict_json(read_file(base + "/probe/probe.json", 16384, 0o400, 1000, 1000))
        password = read_file(base + "/postgres/POSTGRES_PASSWORD", 128, 0o400, 999, 999).decode("ascii")
        require(password.endswith("\n"), "delivery_drift", 6)
        bundle = validate_bundle(dict(probe, postgres_password=password[:-1]), self.run)
        require(digest(canonical(bundle)) == self.state["bundle_sha256"], "delivery_drift", 6)
        for name, (uid, contents) in delivery_material(bundle).items():
            self.verify_service_delivery(base, name, uid, contents)
        self.receipt["checks"]["secrets"] = True

    def data_directories(self):
        self.recheck()
        make_private(self.run_path + "/data")
        with open_dir(self.run_path + "/data", private=True) as parent:
            require(set(os.listdir(parent)) <= {"postgres", "nats", "seaweedfs"}, "data_inventory", 6)
            for name, uid in (("postgres", 999), ("nats", 1000), ("seaweedfs", 1000)):
                try:
                    os.mkdir(name, 0o700, dir_fd=parent)
                except FileExistsError:
                    # Existing service data is never recursively repaired.
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    require(self.state.get("data_inodes", {}).get(name) == [info.st_dev, info.st_ino], "unowned_data", 6)
                else:
                    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    try:
                        require(not os.listdir(fd), "data_not_empty", 6)
                        os.fchown(fd, uid, uid)
                        os.fsync(fd)
                        info = os.fstat(fd)
                        self.state.setdefault("data_inodes", {})[name] = [info.st_dev, info.st_ino]
                    finally:
                        os.close(fd)
                    os.fsync(parent)
                    self.save("data_created")
                with open_dir(self.run_path + "/data/" + name, leaf_uid=uid, leaf_gid=uid) as fd:
                    require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o700, "data_permissions", 6)

    def inspect_container(self, item, service, command=None, probe=False):
        expected = self.profile["services"][service]
        config, host = item.get("Config", {}), item.get("HostConfig", {})
        require(item.get("Image") == self.approval["images"][service]["image_id"], "container_image", 6)
        require(config.get("User") == expected["user"] and config.get("Cmd") == (command or expected["command"]), "container_command", 6)
        image_config = self.images[service].get("Config", {})
        require((config.get("Entrypoint") or []) == (image_config.get("Entrypoint") or []), "container_entrypoint", 6)
        image_env = dict(v.split("=", 1) for v in image_config.get("Env", []))
        image_env.update(expected.get("environment", {}))
        require(sorted(config.get("Env") or []) == sorted(k + "=" + v for k, v in image_env.items()), "container_environment", 6)
        labels = config.get("Labels", {})
        require(all(labels.get(k) == v for k, v in expected["labels"].items()) and labels.get("com.docker.compose.project") == self.profile["name"] and labels.get("com.docker.compose.service") == service, "container_labels", 6)
        require(all(k.startswith("com.docker.compose.") or k in expected["labels"] or image_config.get("Labels", {}).get(k) == v for k, v in labels.items()), "container_labels", 6)
        require(host.get("ReadonlyRootfs") is True and host.get("Privileged") is False and host.get("CapDrop") == ["ALL"] and not host.get("CapAdd") and
                host.get("SecurityOpt") == ["no-new-privileges:true"] and host.get("PidsLimit") == 128 and host.get("LogConfig", {}).get("Type") == "none" and
                host.get("RestartPolicy", {}).get("Name") in ("", "no") and not host.get("Init") and not host.get("Devices") and not host.get("PortBindings") and not host.get("ExtraHosts") and not host.get("Dns") and not host.get("PublishAllPorts"), "container_security", 6)
        require(host.get("NetworkMode") == self.profile["name"] + "_lab", "container_network", 6)
        require(host.get("Tmpfs", {}) == dict(t.split(":", 1) for t in expected["tmpfs"]), "container_tmpfs", 6)
        actual_mounts = sorted((m.get("Type"), m.get("Source"), m.get("Destination"), m.get("RW")) for m in item.get("Mounts", []))
        expected_mounts = sorted((m["type"], m["source"], m["target"], not m.get("read_only", False)) for m in expected["volumes"])
        require(actual_mounts == expected_mounts, "container_mounts", 6)
        networks = item.get("NetworkSettings", {}).get("Networks", {})
        require(set(networks) == {self.profile["name"] + "_lab"}, "container_network", 6)
        network = next(iter(networks.values()))
        address = expected["networks"]["lab"]["ipv4_address"]
        require(network.get("IPAMConfig", {}).get("IPv4Address") == address, "container_address", 6)
        running = item.get("State", {}).get("Running")
        require(network.get("IPAddress") in ((address,) if running else ("", address)) and network.get("NetworkID") in ((self.resources["network"],) if running else ("", self.resources["network"])), "container_network", 6)
        require(not config.get("Tty") and not config.get("OpenStdin"), "container_tty", 6)
        require(not any(v for v in (item.get("NetworkSettings", {}).get("Ports") or {}).values()), "published_port", 6)

    def inspect_network(self, network):
        expected = self.profile["networks"]["lab"]
        require(network.get("Name") == self.profile["name"] + "_lab" and network.get("Driver") == "bridge" and network.get("Internal") is True and network.get("EnableIPv6") is False,
                "network_security", 6)
        require(network.get("Options", {}).get("com.docker.network.bridge.name") == bridge_name(self.run), "network_bridge", 6)
        require(all(network.get("Labels", {}).get(k) == v for k, v in expected["labels"].items()) and network.get("Labels", {}).get("com.docker.compose.project") == self.profile["name"] and network.get("Labels", {}).get("com.docker.compose.network") == "lab", "network_labels", 6)
        ipam = network.get("IPAM", {}).get("Config", [])
        require(len(ipam) == 1 and ipam[0].get("Subnet") == "172.31.250.0/24" and ipam[0].get("Gateway") in (None, "", "172.31.250.1") and not ipam[0].get("IPRange") and not ipam[0].get("AuxiliaryAddresses"), "network_subnet", 6)

    def security_readback(self, stopped=False, ephemeral=None):
        containers, networks = self.raw_inventory()
        resources = dict(self.resources, containers=dict(self.resources["containers"]))
        if ephemeral is not None:
            resources["containers"]["probe"] = ephemeral["Id"]
        validate_inventory(containers, networks, resources)
        own_networks = [n for n in networks if n.get("Id") == self.resources["network"]]
        require(len(own_networks) == 1, "network_missing", 6)
        self.inspect_network(own_networks[0])
        allowed_interfaces = {bridge_name(self.run)}
        by_id = {c["Id"]: c for c in containers}
        for service, cid in self.resources["containers"].items():
            require(cid in by_id, "container_missing", 6)
            item = by_id[cid]
            self.inspect_container(item, service)
            state = item.get("State", {})
            if stopped:
                require(state.get("Running") is False and state.get("Status") in ("exited", "dead", "created"), "stop_unproven", 6)
            elif state.get("Running"):
                pid = state.get("Pid")
                require(type(pid) is int and pid > 1, "container_pid", 6)
                # Kernel proc-root/sysfs mount exposes that inspected netns's
                # peer indices. Cross-bind both ends; labels cannot authorize a veth.
                prefix = "/proc/" + str(pid) + "/root/sys/class/net/eth0/"
                peer_index = int(pseudo_read(prefix + "iflink", 32))
                inside_index = int(pseudo_read(prefix + "ifindex", 32))
                candidates = []
                for interface in os.listdir("/sys/class/net"):
                    if interface.startswith("veth") and int(pseudo_read("/sys/class/net/" + interface + "/ifindex", 32)) == peer_index:
                        require(int(pseudo_read("/sys/class/net/" + interface + "/iflink", 32)) == inside_index, "veth_identity", 6)
                        candidates.append(interface)
                require(len(candidates) == 1, "veth_identity", 6)
                allowed_interfaces.update(candidates)
        require(set(own_networks[0].get("Containers", {})) <= set(resources["containers"].values()), "unowned_endpoint", 6)
        observe_interfaces(allowed_interfaces)
        return containers

    def pg(self, kind):
        cid = self.resources["containers"].get("postgres")
        code, output = self.docker(pg_args(cid, kind, self.run))
        expected = {"positive": b"1\n", "locale": b"C\n", "hba": b"t\n", "seed": b"t\n", "check": b"t\n"}
        if kind == "version":
            require(code == 0 and re.fullmatch(b"17[0-9]{4}\n", output), "postgres_version", 4)
        else:
            require(code == 0 and output == expected[kind], "postgres_failed", 4)
        self.receipt["checks"]["postgres"] = True

    def pg_negative(self):
        self.recheck()
        self.security_readback()
        cid = self.resources["containers"].get("postgres")
        linked = (cid, self.approval["boot_id"], self.sha, self.receipt["profile_sha256"])
        code, output = self.docker(pg_args(cid, "positive"))
        require(code == 0 and output == b"1\n", "pg_positive_required", 4)
        self.recheck()
        require(linked == (self.resources["containers"].get("postgres"), self.approval["boot_id"], self.sha, self.receipt["profile_sha256"]), "pg_binding_drift", 6)
        prefix = ["--host", "unix:///var/run/docker.sock", "--config", RUNTIME + "/docker-empty"]
        code, output, denied, count = run_tool(self.approval["tools"]["docker"], prefix + pg_args(cid, "negative"), self.deadline, negative_pg=True)
        self.total_output += len(output) + count
        require(self.total_output <= 1048576 and code == 2 and not output and denied is True, "pg_auth_not_proven", 4)
        self.recheck()
        self.security_readback()
        require(linked == (self.resources["containers"].get("postgres"), self.approval["boot_id"], self.sha, self.receipt["profile_sha256"]), "pg_binding_drift", 6)
        self.receipt["checks"]["negative_auth"] = True

    def pending(self, kind, names):
        containers, networks = self.inventory()
        occupied = {c.get("Name", "").lstrip("/") for c in containers} | {n.get("Name") for n in networks}
        self.state["pending"] = {"kind": kind, "names_absent": sorted(set(names) - occupied), "started_at": time.time(), "profile_sha256": self.receipt["profile_sha256"]}
        self.save(kind + "_pending")

    def reconcile(self):
        pending = self.state.get("pending")
        if not pending:
            self.inventory()
            return
        require(pending.get("profile_sha256") == self.receipt["profile_sha256"], "pending_profile", 6)
        containers, networks = self.raw_inventory()
        def fresh(item, name):
            require(name in pending.get("names_absent", []), "unowned_resource", 6)
            created = dt.datetime.fromisoformat(item["Created"].replace("Z", "+00:00")).timestamp()
            require(pending["started_at"] <= created <= time.time(), "creation_interval", 6)
        for network in networks:
            if network.get("Name") == self.profile["name"] + "_lab" and self.resources["network"] is None:
                fresh(network, network["Name"])
                self.inspect_network(network)
                self.resources["network"] = network["Id"]
        for item in containers:
            name = item.get("Name", "").lstrip("/")
            for service in ("postgres", "nats", "minio"):
                if name == self.profile["name"] + "-" + service + "-1" and service not in self.resources["containers"]:
                    fresh(item, name)
                    self.inspect_container(item, service)
                    self.resources["containers"][service] = item["Id"]
            if pending.get("kind") == "probe" and name == pending.get("probe_name"):
                fresh(item, name)
                self.inspect_container(item, "probe", pending["command"], True)
                self.state["probe_id"] = item["Id"]
        known = dict(self.resources, containers=dict(self.resources["containers"]))
        if self.state.get("probe_id"):
            known["containers"]["probe"] = self.state["probe_id"]
        validate_inventory(containers, networks, known)
        self.save("reconciled")

    def probe(self, mode):
        require(mode in ("ready", "seed", "check", "deny"))
        name = self.profile["name"] + "-probe-" + mode + "-" + self.approval["authorization_id"]
        command = ["python", "-I", "/lab/stateful_probe.py", mode, self.run]
        self.pending("probe", [name])
        self.state["pending"].update(probe_name=name, command=command)
        self.save("probe_pending")
        code, output = self.compose(["run", "--interactive=false", "--no-TTY", "--no-deps", "--pull", "never", "--name", name, "probe"] + command)
        self.reconcile()
        cid = self.state.get("probe_id")
        require(cid is not None, "probe_identity_unknown", 6)
        inspect_code, inspect_output = self.docker(["container", "inspect", cid])
        require(inspect_code == 0, "probe_cleanup_unknown", 6)
        items = json.loads(inspect_output)
        require(len(items) == 1, "probe_cleanup_unknown", 6)
        self.inspect_container(items[0], "probe", command, True)
        require(items[0].get("State", {}).get("Running") is False and items[0]["State"].get("ExitCode") == code, "probe_not_stopped", 6)
        self.recheck()
        remove_code, _ = self.docker(["container", "rm", "--force", cid])
        require(remove_code == 0, "probe_cleanup_failed", 6)
        self.state.pop("probe_id", None)
        self.state.pop("pending", None)
        self.save("probe_removed")
        require(code == 0, "probe_failed", 4)
        result = validate_probe_result(output, mode, self.run)
        self.receipt["checks"].update(nats=result["checks"]["nats_connected"], s3=result["checks"]["s3_connected"])
        return result

    def start(self):
        self.require_delivery()
        self.cache()
        self.validate_graph()
        self.reconcile()
        if self.resources["network"] is None:
            observe_interfaces(set())
        else:
            self.security_readback()
        self.data_directories()
        names = [self.profile["name"] + "-" + s + "-1" for s in ("postgres", "nats", "minio")]
        names.append(self.profile["name"] + "_lab")
        self.pending("up", names)
        self.recheck()
        code, _ = self.compose(["up", "--detach", "--pull", "never", "--no-build", "postgres", "nats", "minio"])
        self.reconcile()
        require(code == 0 and set(self.resources["containers"]) == {"postgres", "nats", "minio"} and self.resources["network"], "start_failed", 6)
        self.state.pop("pending", None)
        self.save("start_observed")
        startup_end = min(self.deadline, time.monotonic() + 120)
        while True:
            self.security_readback()
            try:
                for kind in ("positive", "version", "locale", "hba"):
                    self.pg(kind)
                self.probe("ready")
                break
            except LabError as error:
                if error.exit_code != 4 or time.monotonic() + 1 >= startup_end:
                    raise
                # No reset of the startup aggregate or helper deadline.
                time.sleep(min(1, startup_end - time.monotonic()))
        self.save("started")
        self.receipt["stateful_started"] = True

    def seed(self):
        self.require_delivery()
        self.security_readback()
        self.save("seed_pending")
        self.pg("seed")
        self.probe("seed")
        self.state["seeded"] = True
        self.save("seeded")
        self.receipt["fixture_seeded"] = True

    def check(self):
        self.require_delivery()
        require(self.state.get("seeded") is True, "fixture_missing", 6)
        self.security_readback()
        self.pg("check")
        self.probe("check")
        self.pg_negative()
        self.probe("deny")
        self.pg("check")
        self.receipt["checks"].update(no_work=True, negative_auth=True)
        self.receipt["persistence_verified"] = True
        self.save("checked")

    def stop(self):
        self.security_readback()
        self.save("stop_pending")
        self.recheck()
        code, _ = self.compose(["stop", "--timeout", "10", "postgres", "nats", "minio"])
        require(code == 0, "stop_failed", 6)
        self.security_readback(stopped=True)
        self.save("stopped")
        self.receipt["cleanup"] = {"status": "stopped"}

    def recover(self):
        require(self.state.get("seeded") is True, "recovery_fixture_missing", 6)
        try:
            self.start()
            self.check()
        except LabError:
            raise LabError("recovery_incomplete", 6) from None
        self.save("recovered")
        self.receipt["recovery_verified"] = True

    def failed_operation(self):
        """Reconcile daemon state after CLI death; absence of proof stays incomplete."""
        self.deadline = self.hard_deadline
        self.receipt["status"] = "incomplete"
        self.receipt["cleanup"] = {"status": "unknown"}
        try:
            if self.state is None or self.profile is None:
                return
            self.reconcile()
            if self.state.get("probe_id"):
                # A running/uncertain one-off is retained, never force-removed.
                self.save("probe_requires_inspection")
                return
            if self.resources["containers"]:
                self.stop()
            else:
                self.receipt["cleanup"] = {"status": "no_containers"}
            self.save("operation_failed")
            self.finish(self.receipt["operation"])
        except (LabError, OSError, ValueError, KeyError, TypeError):
            # No raw output/exception can cross this boundary.
            self.receipt["cleanup"] = {"status": "incomplete"}

    def finish(self, verb):
        self.receipt["resource_ids"] = self.resources
        require(self.receipt["checks"]["children_reaped"] is not False, "child_unreaped", 6)
        self.receipt["checks"]["children_reaped"] = True
        self.receipt["finished_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.recheck()
        atomic_json(self.run_path + "/receipts/" + self.approval["authorization_id"] + "-" + verb + ".json", self.receipt)


def install_cli(verb, source_sha, run_id):
    receipt = empty_receipt(verb, source_sha, run_id)
    controller = None
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
                controller.load_state()
                require(controller.state is not None, "run_missing", 3)
                controller.release()
                controller.cache()
                # Recollect pending owned resources before any lifecycle action.
                controller.reconcile()
                if verb == "deliver":
                    controller.deliver()
                else:
                    getattr(controller, verb)()
            receipt.update(status="passed", failure_code=None)
            controller.finish(verb)
        return 0, receipt
    except FileNotFoundError:
        receipt["status"] = "failed"
        receipt["failure_code"] = "missing_prerequisite"
        if controller is not None and controller.state is not None:
            controller.failed_operation()
        return (6 if receipt["cleanup"]["status"] in ("unknown", "incomplete") else 3), receipt
    except LabError as error:
        receipt["failure_code"] = error.code
        receipt["status"] = "incomplete" if error.exit_code == 6 else "failed"
        if error.code == "post_commit_failure":
            receipt["material_committed"] = True
        if error.code == "child_unreaped":
            receipt["checks"]["children_reaped"] = False
        if controller is not None and controller.state is not None:
            controller.failed_operation()
        return (6 if receipt["cleanup"]["status"] in ("unknown", "incomplete") else error.exit_code), receipt
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        receipt["status"] = "failed"
        receipt["failure_code"] = "operation_failed"
        if controller is not None and controller.state is not None:
            controller.failed_operation()
        return (6 if receipt["cleanup"]["status"] in ("unknown", "incomplete") else 4), receipt


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
