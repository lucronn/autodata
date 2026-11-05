"""Deterministic offline browser command language. This module has no live port.

Returned commands are descriptions, never permissions. Dynamic Docker identities
and source observations remain explicit barriers until supplied to pure binders.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, fields
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit


SPEC_PATH = Path(__file__).resolve().parents[2] / "docs/agents/specs/2026-11-05-workshop-browser-current-source-contract.json"
CANDIDATE_SHA = "6949eb1b1a5b93c9b2eb0579328e24c697f6f331"
CANDIDATE_TREE = "47ec54b1896c83a39b6637a6ce944d3620414f4e"
IMAGE_ROLES = ("runner", "postgres", "nats", "s3")


class LiveAdapterNotAdmitted(RuntimeError):
    """No concrete execution adapter is available at this gate."""


def strict_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("nonfinite JSON: " + value)

    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value) -> str:
    return digest_bytes(canonical_json(value))


# Reviewed literals from the admitted c374f77 checkpoint. These expectations
# never come from the caller's spec or a runtime source/filesystem observation.
_CURRENT_SPEC_SHA256 = '75f412ed9ff42366dc7382364e3de1e4c0b777b1ee43ef4fb2060153e4e544ad'
_FROZEN_SECTION_DIGESTS = {
    "source_manifest": "316a4d15269d55b5229b4873653998c34cea80d75c5bbdfee401c991b98db722",
    "source_pins": "8217874c03373499d3a7678cf88540d4d7b755caed5dd111635a83bcfcf096a6",
    "producer_source_input_sha256": "f87c7488e03d8b2bcc18818177b3a30b596f4833d56409df29d84887bd5f9520",
    "current_served_asset_manifest": "2d8f9d6e7f3ab3c75f5691f2d9adce80467dd2b17ccfce76e3cd1dbb6a95cb16",
    "api21_v2_inventory": "9e3c5fb3b3d0502867da5120bca9ba8d1ddbc916c78720b77fe9d9d69692d185",
    "api_process_command_schedule": "2b2496bb706e457b7d94ec6fe7d245c67805bfead4dbf627e4e112419c25078e",
    "dto_timing_contract": "c3029bc08b5a40c323aab57ba1a65d1bc1d3dd4cd82f978839f713cb09a5cd52",
    "environments": "ad307ca5b1f87312b1c02c3d1c8874323e6859ab4eb30cadaf335dde9dc53bdb",
    "inventory": "0f197bd5aedecb2c0d996c5eeb0b5f34182d9614420833ab765e991695bbeead",
    "static_command_contract": "341e5d84be3a47e018d53219fafc5e10562eb918eda51514851bb4f8ec08f085",
    "timeout_binding_rules": "6116d2709bafadc89bf5d21753ec1d016e25716093c696fd5aef904314b61fc4"
}


def validate_source_contract(value: dict) -> None:
    """Validate the exact immutable current-source static contract, without I/O."""
    if not isinstance(value, dict):
        raise ValueError("current-source specification must be an object")
    if (value.get("candidate_sha") != CANDIDATE_SHA or
            value.get("candidate_tree") != CANDIDATE_TREE or
            value.get("source_candidate_sha") != CANDIDATE_SHA or
            value.get("source_candidate_tree") != CANDIDATE_TREE):
        raise ValueError("current-source specification identity mismatch")
    if value.get("frozen_section_digests") != _FROZEN_SECTION_DIGESTS:
        raise ValueError("current-source frozen digest map mismatch")
    for section, expected in _FROZEN_SECTION_DIGESTS.items():
        if section not in value or digest(value[section]) != expected:
            raise ValueError("current-source section mismatch: " + section)
    # Also freeze schemas, deadlines, authority barriers and root shape. A
    # self-consistent replacement map cannot certify altered static inputs.
    if digest(value) != _CURRENT_SPEC_SHA256:
        raise ValueError("current-source specification mismatch")


def specification() -> dict:
    # The canonical planning checkpoint carries literal schemas and inventories.
    # Return fresh data so callers cannot mutate the contract for other calls.
    value = strict_json(SPEC_PATH.read_bytes())
    validate_source_contract(value)
    return value


def inventory() -> dict:
    return specification()["inventory"]


def validate_inventory(value: dict) -> None:
    if value != inventory():
        raise ValueError("exact API21/DTO40x3 inventory mismatch")


def absolute_path(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or any(ch in value for ch in ("\0", "\n", "\r", ",", "$", "@", "\\")):
        raise ValueError("invalid absolute path")
    if str(PurePosixPath(value)) != value or any(p in (".", "..") for p in value.split("/")):
        raise ValueError("path must be normalized without traversal")
    return value


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\0" in value or "\\" in value:
        raise ValueError("invalid evidence path")
    if str(PurePosixPath(value)) != value or any(p in (".", "..") for p in value.split("/")):
        raise ValueError("evidence traversal")
    return value


def hex_value(value: str, length: int) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is None:
        raise ValueError("invalid hexadecimal identity")
    return value


def disjoint_roots(roots: tuple[str, ...]) -> None:
    for root in roots:
        absolute_path(root)
    for index, a in enumerate(roots):
        for b in roots[index + 1:]:
            if a == "/" or b == "/" or a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                raise ValueError("source/tools/cache/evidence roots overlap")


def offline_output(path: str, protected_roots: tuple[str, ...]) -> Path:
    """Check an offline CLI destination; no allocation or directory creation."""
    output = Path(absolute_path(path))
    disjoint_roots((str(output.parent), *protected_roots))
    for entry in (output, *output.parents):
        if entry.is_symlink():
            raise ValueError("offline output may not follow links")
    # Existing lexical roots may themselves have aliases. This observation is
    # only an offline write safeguard, never a runtime filesystem admission.
    disjoint_roots((str(output.parent.resolve()), *(str(Path(root).resolve()) for root in protected_roots)))
    return output


@dataclass(frozen=True)
class RuntimeBindings:
    candidate_sha: str
    candidate_tree: str
    supervisor_sha256: str
    attempt_id: str
    source_root: str
    tools_root: str
    attempt_root: str
    host_python: str
    docker: str
    images: dict[str, str]
    image_config_sha256: dict[str, str]
    image_rootfs_sha256: dict[str, str]
    runtime_admission_sha256: str | None
    docker_socket: str
    docker_config_root: str
    module_cache_root: str
    browser_cache_root: str
    control_root: str


@dataclass(frozen=True)
class CommandSpec:
    id: str
    role: str
    argv: tuple[str, ...]
    cwd: str
    environment: tuple[tuple[str, str], ...]
    timeout_ms: int
    stdout_path: str
    stderr_path: str
    depends_on: tuple[str, ...]
    binding_sha256: str


@dataclass(frozen=True)
class Event:
    kind: str
    monotonic_ns: int
    payload: dict


@dataclass(frozen=True)
class OperationSpec:
    id: str
    index: int
    kind: str
    command: CommandSpec | None
    local_read: dict | None
    readiness: dict | None
    depends_on: tuple[str, ...]
    required_event: str | None
    timeout_ms: int
    output_prefix: str


def validate_bindings(b: RuntimeBindings) -> None:
    if b.candidate_sha != CANDIDATE_SHA or b.candidate_tree != CANDIDATE_TREE:
        raise ValueError("candidate source identity mismatch")
    hex_value(b.supervisor_sha256, 64)
    hex_value(b.attempt_id, 32)
    if b.runtime_admission_sha256 is not None:
        hex_value(b.runtime_admission_sha256, 64)
    roots = tuple(getattr(b, k) for k in ("source_root", "tools_root", "attempt_root", "module_cache_root", "browser_cache_root", "control_root", "docker_config_root"))
    disjoint_roots(roots)
    for k in ("host_python", "docker", "docker_socket"):
        absolute_path(getattr(b, k))
    for values, image in ((b.images, True), (b.image_config_sha256, False), (b.image_rootfs_sha256, False)):
        if not isinstance(values, dict) or set(values) != set(IMAGE_ROLES):
            raise ValueError("exact four image bindings required")
        for value in values.values():
            if image:
                if not isinstance(value, str) or not value.startswith("sha256:"):
                    raise ValueError("immutable image ID required")
                value = value[7:]
            hex_value(value, 64)


def parse_bindings(value: dict | bytes) -> RuntimeBindings:
    if isinstance(value, bytes):
        value = strict_json(value)
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(RuntimeBindings)}:
        raise ValueError("unknown or missing runtime binding fields")
    result = RuntimeBindings(**copy.deepcopy(value))
    validate_bindings(result)
    return result


def environment(role: str, attempt_root: str) -> dict[str, str]:
    absolute_path(attempt_root)
    try:
        result = specification()["environments"][role]
    except KeyError as exc:
        raise ValueError("unknown environment") from exc
    result = {k: v.replace("${attempt_root}", attempt_root) for k, v in result.items()}
    if any("${" in v for v in result.values()):
        raise ValueError("unresolved static environment")
    return dict(sorted(result.items()))


def command_dict(command: CommandSpec, include_hash: bool = True) -> dict:
    result = asdict(command)
    result["argv"] = list(command.argv)
    result["depends_on"] = list(command.depends_on)
    result["environment"] = dict(command.environment)
    if not include_hash:
        del result["binding_sha256"]
    return result


def validate_environment(role: str, env: dict) -> None:
    if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) or "\0" in v for k, v in env.items()):
        raise ValueError("invalid complete command environment")
    if role in ("host", "probe", "cleanup"):
        home = env.get("HOME", "")
        suffix = "/scratch/host-home"
        if not home.endswith(suffix) or env != environment("host", home[:-len(suffix)]):
            raise ValueError("host environment differs from frozen replacement")
    else:
        choices = {"runner": ("runner",), "api": ("api_pytest",), "dto": ("dto_go", "dto_browser")}.get(role)
        if choices is None or not any(env == environment(choice, "/unused") for choice in choices):
            raise ValueError("command environment differs from frozen replacement")


def operation_dict(operation: OperationSpec) -> dict:
    result = asdict(operation)
    result["depends_on"] = list(operation.depends_on)
    result["command"] = command_dict(operation.command) if operation.command else None
    return result


def make_command(id: str, role: str, argv, cwd: str, env: dict, timeout_ms: int,
                 stdout_path: str, stderr_path: str, depends_on=()) -> CommandSpec:
    absolute_path(cwd)
    validate_environment(role, env)
    absolute_path(argv[0])
    for p in (stdout_path, stderr_path):
        absolute_path(p)
    if not argv or any(not isinstance(a, str) or not a or "\0" in a or a.startswith("@") for a in argv):
        raise ValueError("unresolved or malformed argv")
    if type(timeout_ms) is not int or not 0 < timeout_ms <= 5100000:
        raise ValueError("invalid command timeout")
    cmd = CommandSpec(id, role, tuple(argv), cwd, tuple(sorted(env.items())), timeout_ms,
                      stdout_path, stderr_path, tuple(depends_on), "")
    return CommandSpec(**{**asdict(cmd), "binding_sha256": digest(command_dict(cmd, False))})


def resource_name(b: RuntimeBindings, lane: str, role: str) -> str:
    if lane not in ("api", "dto") or role not in (*IMAGE_ROLES, "net", "pgdata", "natsdata", "s3data"):
        raise ValueError("unknown resource generation/role")
    return f"ad-b-{b.attempt_id}-{lane}-{role}"


def labels(b: RuntimeBindings, lane: str) -> list[str]:
    values = {"autodata.attempt": b.attempt_id, "autodata.candidate": b.candidate_sha,
              "autodata.contract": "api21-dto120-v1", "autodata.generation": lane,
              "autodata.supervisor": b.supervisor_sha256}
    return [part for k, v in sorted(values.items()) for part in ("--label", k + "=" + v)]


def resource_command(b: RuntimeBindings, lane: str, role: str, verb: str, *,
                     network_id: str | None = None, resource_id: str | None = None,
                     depends_on=()) -> CommandSpec:
    """Bind one frozen Docker template using exact observed IDs; no I/O."""
    validate_bindings(b)
    name = resource_name(b, lane, role)
    prefix = [b.docker, "--host", "unix://" + b.docker_socket, "--config", b.docker_config_root]
    timeout = 10000
    if role == "net":
        if verb == "create":
            suffix = ["network", "create", "--internal", "--driver", "bridge", *labels(b, lane), name]
        elif verb in ("inspect", "rm"):
            suffix = ["network", verb, hex_value(resource_id, 64)]
            timeout = 5000 if verb == "inspect" else 10000
        else:
            raise ValueError("invalid network verb")
    elif role in ("pgdata", "natsdata", "s3data"):
        if lane != "api" or verb not in ("create", "inspect", "rm"):
            raise ValueError("invalid volume operation")
        suffix = ["volume", verb, *(labels(b, lane) if verb == "create" else []), name]
        timeout = 5000 if verb == "inspect" else 10000
    elif role in IMAGE_ROLES:
        if lane == "dto" and role != "runner":
            raise ValueError("DTO has no service generation")
        if verb == "create":
            hex_value(network_id, 64)
            runner = role == "runner"
            suffix = ["create", "--name", name, "--pull", "never", "--network", network_id]
            if not runner:
                suffix += ["--network-alias", {"postgres": "postgres", "nats": "nats", "s3": "minio"}[role]]
            suffix += labels(b, lane) + ["--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", "2048" if runner else "256", "--memory",
                {"runner": "8589934592", "postgres": "2147483648", "nats": "536870912", "s3": "1073741824"}[role],
                "--cpus", "4" if runner else "2", "--tmpfs",
                "/tmp:rw,exec,nosuid,nodev,size=" + ("2147483648" if runner else "268435456")]
            base_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            if runner:
                mounts = [(b.source_root, "/workspace", True), (b.tools_root, "/tools", True),
                          (b.attempt_root + "/artifacts", "/artifacts", False), (b.control_root, "/control", True),
                          (b.module_cache_root, "/opt/go-module-cache", True), (b.browser_cache_root, "/opt/autodata-playwright", True)]
                for source, dest, readonly in mounts:
                    suffix += ["--mount", f"type=bind,src={source},dst={dest}" + (",readonly" if readonly else "")]
                suffix += ["--workdir", "/workspace"]
                env, entry = environment("runner", b.attempt_root), "/usr/local/bin/python3"
                args = ["-I", "/tools/scripts/dev/workshop_browser_execution_supervisor.py", "execute-runner", "--binding", "/control/runtime-binding.json", "--lane", lane]
            else:
                volume = {"postgres": "pgdata", "nats": "natsdata", "s3": "s3data"}[role]
                dest = "/var/lib/postgresql/data" if role == "postgres" else "/data"
                suffix += ["--mount", "type=volume,src=" + resource_name(b, lane, volume) + ",dst=" + dest]
                env = {"PATH": base_path}
                if role == "postgres":
                    suffix += ["--tmpfs", "/var/run/postgresql:rw,nosuid,nodev,size=16777216"]
                    env.update(POSTGRES_USER="lifecycle_test", POSTGRES_PASSWORD="lifecycle_test_only", POSTGRES_DB="lifecycle_fixture", LANG="C.UTF-8")
                entry, args = {"postgres": ("/usr/local/bin/docker-entrypoint.sh", ["postgres", "-c", "listen_addresses=*"]),
                               "nats": ("/nats-server", ["-js", "-sd", "/data"]),
                               "s3": ("/usr/bin/weed", ["mini", "-dir=/data", "-s3.port=9000"])}[role]
            suffix += [part for k, v in sorted(env.items()) for part in ("--env", k + "=" + v)]
            suffix += ["--entrypoint", entry, b.images[role], *args]
        else:
            identity = hex_value(resource_id, 64)
            templates = {"start": (["start", identity], 10000), "inspect": (["inspect", "--type", "container", identity], 5000),
                         "wait": (["wait", identity], 2100000 if lane == "api" else 5100000),
                         "logs": (["logs", "--timestamps", identity], 10000), "stop": (["stop", "--time", "2", identity], 5000),
                         "kill": (["kill", "--signal", "KILL", identity], 5000), "rm": (["rm", identity], 10000)}
            if verb not in templates:
                raise ValueError("invalid container verb")
            suffix, timeout = templates[verb]
    else:
        raise ValueError("unknown resource role")
    id = f"{lane}.{role}.{verb}"
    return make_command(id, "host", prefix + suffix, b.tools_root, environment("host", b.attempt_root), timeout,
                        b.attempt_root + "/artifacts/commands/" + id + ".stdout", b.attempt_root + "/artifacts/commands/" + id + ".stderr", depends_on)


def producer_command(b: RuntimeBindings, lane: str, *, origin: str | None = None, depends_on=()) -> CommandSpec:
    validate_bindings(b)
    if lane == "api":
        argv = ["/usr/local/bin/python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=/artifacts/workshop-browser-api.xml", "workers/ingestion-python/tests/test_workshop_browser_integration.py"]
        role, cwd, timeout, stem = "api_pytest", "/workspace", 2100000, "/artifacts/api/pytest"
    elif lane == "dto_go":
        argv = ["/usr/local/go/bin/go", "test", "-count=1", "-run", "^TestWorkshopBrowserFixtureHTTP$", "-timeout=5040s", "."]
        role, cwd, timeout, stem = "dto_go", "/workspace/apps/api-go", 5100000, "/artifacts/dto/go-fixture"
    elif lane == "dto":
        parsed = urlsplit(origin or "")
        if parsed.scheme != "https" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or not parsed.port or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("exact owned loopback HTTPS ready origin required")
        argv = ["/usr/local/bin/python3", "/workspace/scripts/dev/workshop_browser_smoke.py", "--base-url", origin, "--mode", "dto-fixture", "--browser", "all", "--candidate-sha", b.candidate_sha, "--output", "/artifacts/browser"]
        role, cwd, timeout, stem = "dto_browser", "/workspace", 5100000, "/artifacts/dto/browser"
    else:
        raise ValueError("unknown producer")
    stdout, stderr = (stem + ".log", stem + ".log") if lane == "dto_go" else (stem + ".stdout.log", stem + ".stderr.log")
    return make_command(lane + ".producer", "api" if lane == "api" else "dto", argv, cwd, environment(role, b.attempt_root), timeout,
                        stdout, stderr, depends_on)


def graph_blockers(bindings: RuntimeBindings, lane: str) -> tuple[str, ...]:
    validate_bindings(bindings)
    if lane not in ("api", "dto"):
        raise ValueError("unknown lane")
    result = {"live_adapter_not_admitted", "runtime_observations_missing", "source_observer_not_admitted",
              "filesystem_identity_not_observed", "go_path_resolution_not_observed", "runtime_admission_not_verified"}
    if bindings.runtime_admission_sha256 is None:
        result.add("runtime_admission_missing")
    if lane == "dto":
        result.update(("blocked_timer_dependency", "supervisor_dto_deadline_mismatch"))
    else:
        result.add("api_finite_success_proof_missing")
    return tuple(sorted(result))


def compile_graph(bindings: RuntimeBindings, lane: str) -> tuple[OperationSpec, ...]:
    """Compile ordered static operations; dynamic commands are observation gates.

    Gate IDs name the immutable template consumed by resource_command or
    producer_command after a future typed observation. No guessed IDs appear.
    """
    graph_blockers(bindings, lane)
    ops = []

    def add(id, *, command=None, readiness=None, event=None, deps=None, timeout=10000):
        dependencies = tuple(deps if deps is not None else ([ops[-1].id] if ops else []))
        kind = "command" if command else "readiness" if readiness else "observation_gate"
        ops.append(OperationSpec(id, len(ops), kind, command, None, readiness, dependencies,
                                 event if kind == "observation_gate" else None, timeout, "/artifacts/operations/" + id))

    add(lane + ".reserve", event="owned_directory_reserved_and_fsynced")
    if lane == "dto":
        add("dto.api-generation-sealed", event="api.cleaned_and_sealed")
    add(lane + ".net.create", command=resource_command(bindings, lane, "net", "create", depends_on=(ops[-1].id,)))
    add(lane + ".net.inspect", event="owned_network_inspected:exact_id_labels")
    if lane == "api":
        for volume in ("pgdata", "natsdata", "s3data"):
            add(lane + "." + volume + ".create", command=resource_command(bindings, lane, volume, "create", depends_on=(ops[-1].id,)))
            add(lane + "." + volume + ".inspect", event="owned_volume_inspected:" + volume)
        for role in ("postgres", "nats", "s3"):
            for verb in ("create", "start", "inspect"):
                add(f"api.{role}.{verb}", event=f"bound_command:api.{role}.{verb}:verified_identity")
        add("api.services.started", event="owned_services_started_and_inspected")
    for verb in ("create", "start", "inspect"):
        add(lane + ".runner." + verb, event=f"bound_command:{lane}.runner.{verb}:verified_identity")

    def ready(id, action, origin, case=None, deps=None):
        resource = "runner" if action == "fixture_ready_tls_assets" else {"pg_select_one": "postgres", "nats_info": "nats", "s3_roundtrip": "s3"}.get(action, "database")
        output_name = "fixture" if action == "fixture_ready_tls_assets" else resource
        output = "/artifacts/readiness/" + lane + "/" + ((case + "/") if case else "") + output_name + ".json"
        values = dict(action=action, origin=origin, resource_key=lane + "." + resource, case_id=case,
                      input_paths=[], output_path=output, request_timeout_ms=5000, phase_timeout_ms=120000,
                      poll_interval_ms=250, max_polls=480, expected_sha256=None)
        add(id, readiness=values, deps=deps, timeout=120000)

    if lane == "api":
        for role, action, origin in (("pg", "pg_select_one", "postgres:5432/lifecycle_fixture"), ("nats", "nats_info", "nats:4222"), ("s3", "s3_roundtrip", "http://minio:9000")):
            ready("api.service." + role, action, origin)
        add("api.producer.start", command=producer_command(bindings, "api", depends_on=(ops[-1].id,)), timeout=2100000)
        for case in inventory()["api_cases"]:
            id = case["id"]
            prefix = "api.case." + id
            add(prefix + ".database-created", event="source.database_created:" + id)
            add(prefix + ".migrations", event="source.migrations_applied:" + id)
            add(prefix + ".go-started", event="source.go_fixture_started:" + id)
            ready(prefix + ".fixture", "fixture_ready_tls_assets", None, id)
            add(prefix + ".browser-permission", event="source.barrier_acknowledged:" + id)
            add(prefix + ".browser-result", event="source.browser_result_and_cleanup:" + id)
    else:
        add("dto.timer-admission", event="separate_timer_gate_admitted")
        add("dto.go.start", command=producer_command(bindings, "dto_go", depends_on=(ops[-1].id,)), timeout=5100000)
        add("dto.go.started", event="dto.go.started:exact_process_identity")
        ready("dto.fixture.ready", "fixture_ready_tls_assets", None)
        add("dto.browser.start", event="bound_command:dto.producer:owned_ready_origin", timeout=5100000)
        add("dto.browser.result", event="exact_dto120_results_and_exits")
    for role in (("runner", "s3", "nats", "postgres") if lane == "api" else ("runner",)):
        for verb in ("wait", "logs", "stop", "kill", "rm"):
            add(f"{lane}.{role}.{verb}", event=f"conditional_bound_command:{lane}.{role}.{verb}:ownership_and_prior_outcome")
    if lane == "api":
        for volume in ("s3data", "natsdata", "pgdata"):
            add("api." + volume + ".rm", event="conditional_bound_command:api." + volume + ".rm:complete_volume_identity")
    add(lane + ".net.rm", event="conditional_bound_command:" + lane + ".net.rm:verified_identity")
    add(lane + ".seal", event="all_exits_reaped_logs_flushed_and_inventory_accounted", timeout=120000)
    validate_operations(tuple(ops))
    return tuple(ops)


def validate_operations(operations: tuple[OperationSpec, ...]) -> None:
    seen = set()
    for index, op in enumerate(operations):
        if op.id in seen or op.index != index or any(dep not in seen for dep in op.depends_on):
            raise ValueError("duplicate, reordered or cyclic operation")
        members = (op.command is not None, op.local_read is not None, op.readiness is not None)
        expected = {"command": (True, False, False), "local_read": (False, True, False), "readiness": (False, False, True), "observation_gate": (False, False, False)}
        if op.kind not in expected or members != expected[op.kind] or (op.required_event is not None) != (op.kind == "observation_gate"):
            raise ValueError("operation action discriminant mismatch")
        if op.command and tuple(op.command.depends_on) != tuple(op.depends_on):
            raise ValueError("command and operation dependencies differ")
        seen.add(op.id)
