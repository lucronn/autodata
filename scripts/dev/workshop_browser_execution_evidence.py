"""Strict static support evidence validation and injected durable-write protocol.

No filesystem/process/container adapter is supplied. MemoryEvidencePort models
the required order for offline tests; it is not proof of OS durability.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import re

import workshop_browser_execution_contract as c


def _same(a, b):
    return type(a) is type(b) and a == b


def _schema(value, schema, root, path, errors, context):
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        before = len(errors)
        _schema(value, root["$defs"][name], root, path, errors, context)
        if len(errors) == before:
            _semantic(name, value, path, errors, context)
        return
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            branch_errors = []
            _schema(value, branch, root, path, branch_errors, context)
            if not branch_errors:
                return
        errors.append(path + ": no valid union alternative")
        return
    if "const" in schema and not _same(value, schema["const"]):
        errors.append(path + ": invalid constant")
        return
    if "enum" in schema and not any(_same(value, v) for v in schema["enum"]):
        errors.append(path + ": unknown enum")
        return
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    if "type" in schema and type(value) is not types[schema["type"]]:
        errors.append(path + ": wrong type")
        return
    if type(value) is dict:
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(path + ": missing " + key)
        if len(value) > schema.get("maxProperties", len(value)):
            errors.append(path + ": too many properties")
        for key, member in value.items():
            if not isinstance(key, str):
                errors.append(path + ": non-string key")
                continue
            if "propertyNames" in schema:
                _schema(key, schema["propertyNames"], root, path + ".key", errors, context)
            if key in props:
                _schema(member, props[key], root, path + "." + key, errors, context)
            elif schema.get("additionalProperties") is False:
                errors.append(path + ": unknown " + key)
            elif isinstance(schema.get("additionalProperties"), dict):
                _schema(member, schema["additionalProperties"], root, path + "." + key, errors, context)
    elif type(value) is list:
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
            errors.append(path + ": invalid collection size")
        if "items" in schema:
            for i, member in enumerate(value):
                _schema(member, schema["items"], root, path + f"[{i}]", errors, context)
    elif type(value) is str:
        if "\0" in value or not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)):
            errors.append(path + ": invalid string size/content")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(path + ": invalid pattern")
    elif type(value) is int:
        if not schema.get("minimum", value) <= value <= schema.get("maximum", value):
            errors.append(path + ": integer outside bounds")


def _semantic(name, value, path, errors, context):
    def reject(reason):
        errors.append(path + ": " + reason)

    if name == "Process":
        if any(value[k] <= 0 for k in ("pid", "pgid", "start_ticks", "pid_namespace_inode")):
            reject("process creation identity must be positive")
    elif name == "Outcome":
        if value["signal"] is not None and value["exit_code"] is not None:
            reject("signal and exit code are exclusive")
        start, end = value["start_ns"], value["end_ns"]
        if end is not None and (start is None or end < start):
            reject("invalid observation time order")
        if value["state"] == "running" and (start is None or end is not None or value["signal"] is not None or value["exit_code"] is not None):
            reject("running outcome has terminal fields")
        if value["state"] == "exited" and (end is None or (value["signal"] is None) == (value["exit_code"] is None)):
            reject("exit result missing")
        if value["state"] in ("missing", "failed", "interrupted", "timeout", "not_started") and not value["reason"]:
            reject("nonpass outcome requires reason")
        if value["state"] == "not_started" and any(value[k] is not None for k in ("start_ns", "end_ns", "signal", "exit_code")):
            reject("not-started outcome contains invented execution")
    elif name == "Command":
        try:
            c.absolute_path(value["argv"][0])
            c.absolute_path(value["cwd"])
            c.absolute_path(value["stdout_path"])
            c.absolute_path(value["stderr_path"])
        except ValueError as exc:
            reject(str(exc))
        if value["binding_sha256"] != c.digest({k: v for k, v in value.items() if k != "binding_sha256"}):
            reject("command digest mismatch")
        if any("${" in a or a.startswith("@") for a in value["argv"]):
            reject("unresolved command binding")
        if value["argv"][0].rsplit("/", 1)[-1] in ("sh", "bash", "zsh", "dash"):
            reject("outer shell execution forbidden")
        expected = context.get("command_environments", {}).get(value["id"])
        if expected is not None and value["environment"] != expected:
            reject("complete environment mismatch")
    elif name in ("Missing", "File"):
        try:
            c.relative_path(value["path"])
        except ValueError as exc:
            reject(str(exc))
        if name == "Missing":
            if value["state"] != "produced" and not value["reason"]:
                reject("missing/partial artifact requires reason")
            if value["state"] == "produced" and value["sha256"] is None:
                reject("produced artifact lacks digest")
        elif value["kind"] == "regular" and value["sha256"] is None:
            reject("regular file lacks digest")
    elif name == "Resource":
        if value["status"] == "ambiguous" and not value["reason"]:
            reject("ambiguous resource requires reason")
        if value["status"] in ("verified", "stopped", "removed"):
            if value["inspect_sha256"] is None:
                reject("verified ownership lacks inspection")
            if value["kind"] in ("network", "container"):
                try:
                    c.hex_value(value["immutable_id"], 64)
                except ValueError:
                    reject("resource immutable identity missing")
            if value["kind"] == "process" and value["process"] is None:
                reject("process ownership identity missing")
            if value["kind"] in ("volume", "directory") and value["filesystem"] is None:
                reject("filesystem ownership identity missing")
        expected_labels = {"autodata.attempt": value["attempt_id"], "autodata.candidate": value["candidate_sha"],
                           "autodata.supervisor": value["supervisor_sha256"], "autodata.generation": value["generation"], "autodata.contract": "api21-dto120-v1"}
        if value["kind"] in ("container", "network", "volume") and value["labels"] != expected_labels:
            reject("resource labels differ from complete ownership tuple")
    elif name == "Worker":
        if value["observation"] != "direct" or value["process"] is None or value["exit"]["state"] != "exited":
            reject("worker creation and exit are unobservable/incomplete")
        if value["observation"] == "missing" and not value["reason"]:
            reject("missing worker requires reason")
    elif name == "Migration":
        if value["state"] != "applied" or value["applied_sha256"] != value["source_sha256"] or not value["command_id"]:
            reject("migration lacks direct applied checksum observation")
        expected = context.get("migration_source_sha256", {}).get(value["path"])
        if expected is None or expected != value["source_sha256"]:
            reject("migration candidate SQL pin missing/mismatched")
    elif name == "Binding":
        if value["state"] == "matched" and (value["expected_sha256"] is None or value["expected_sha256"] != value["observed_sha256"]):
            reject("matched binding lacks equal observed identity")
        elif value["state"] != "matched" and not value["reason"]:
            reject("unavailable binding needs reason")
    elif name == "Manifest":
        excluded = {"manifest.json", "terminal.json", "seal.json"}
        names = [v["path"] for v in value["files"]] + [v["path"] for v in value["missing"]]
        if len(names) != len(set(names)) or excluded.intersection(names):
            reject("manifest recursive or duplicate entry")
        if value["total_bytes"] != sum(v["bytes"] for v in value["files"]):
            reject("manifest byte total mismatch")
    elif name == "Terminal":
        names = [v["path"] for v in value["artifacts"]]
        if len(names) != len(set(names)) or {"terminal.json", "seal.json"}.intersection(names):
            reject("terminal recursive or duplicate entry")
        expected = context.get("expected_artifacts")
        if expected is not None and set(names) != set(expected) - {"terminal.json", "seal.json"}:
            reject("terminal incomplete/unknown missing map")
        if value["state"] in ("failed", "interrupted", "recovery_blocked") and not value["failure_reasons"]:
            reject("terminal nonpass has no failure reason")
    elif name == "Seal":
        if value["seal_sha256"] != c.digest({k: v for k, v in value.items() if k != "seal_sha256"}):
            reject("seal self hash mismatch")
        files = context.get("files", {})
        for artifact, field in (("manifest.json", "manifest_sha256"), ("terminal.json", "terminal_sha256"), ("journal.jsonl", "journal_sha256")):
            if artifact not in files or c.digest_bytes(files[artifact]) != value[field]:
                reject("seal raw byte binding missing/mismatch: " + artifact)
    elif name == "OperationSpec":
        members = tuple(value[k] is not None for k in ("command", "local_read", "readiness"))
        expected = {"command": (True, False, False), "local_read": (False, True, False), "readiness": (False, False, True), "observation_gate": (False, False, False)}
        if members != expected[value["kind"]] or (value["required_event"] is not None) != (value["kind"] == "observation_gate"):
            reject("operation discriminant mismatch")
    elif name == "Probe":
        if value["candidate_sha"] != c.CANDIDATE_SHA or value["candidate_tree"] != c.CANDIDATE_TREE:
            reject("probe source mismatch")
        if value["deadline_ns"] - value["start_ns"] > 180000000000 or value["deadline_ns"] < value["start_ns"]:
            reject("probe wall budget exceeded")
        operations = value["operations"]
        if [op["index"] for op in operations] != list(range(len(operations))):
            reject("probe indices reordered/duplicated")
        if value["terminal"] == "complete_unadmitted" and len(operations) != 13:
            reject("complete probe must contain exact thirteen operations")
        expected = context.get("preparation_operations")
        if expected is None:
            reject("independently rendered preparation plan missing")
        else:
            expected = [c.operation_dict(op) if isinstance(op, c.OperationSpec) else op for op in expected]
            if len(operations) != len(expected) or any(op["spec"] != wanted or op["index"] != wanted["index"] for op, wanted in zip(operations, expected)):
                reject("probe operation differs from frozen rendering")
        for op in operations:
            if op["spec"]["kind"] not in ("command", "local_read") or op["spec"]["timeout_ms"] > 10000:
                reject("preparation illegal action/budget")
        if value["terminal"] == "complete_unadmitted" and any(op["outcome"]["state"] != "exited" or op["outcome"]["exit_code"] != 0 for op in operations):
            reject("complete probe includes non-success outcome")
    elif name == "ProbeInput":
        try:
            c.disjoint_roots(tuple(value[k] for k in ("source_root", "tools_root", "module_cache_root", "browser_cache_root", "evidence_root", "docker_config_root")))
            for k in ("host_python", "host_go", "docker", "docker_socket"):
                c.absolute_path(value[k])
            for path_value in value["exported_runtime_manifest_paths"]:
                c.absolute_path(path_value)
            if not value["exported_runtime_manifest_paths"]:
                reject("exported runtime manifest required")
            if value["expected_environment_sha256"] != c.digest(c.environment("host", value["evidence_root"])):
                reject("host environment digest mismatch")
        except ValueError as exc:
            reject(str(exc))
        if value["candidate_sha"] != c.CANDIDATE_SHA or value["candidate_tree"] != c.CANDIDATE_TREE:
            reject("probe input source mismatch")
    elif name == "LocalReadResult":
        if value["before"] != value["after"]:
            reject("local source/cache metadata or content drift")
        if value["before_sha256"] != c.digest(value["before"]) or value["after_sha256"] != c.digest(value["after"]):
            reject("local manifest hash mismatch")
        if value["action"] == "capacity_v1":
            floors = c.specification()["preparation_parsers"]["capacity_floors"]
            for snapshot in (value["capacity_before"], value["capacity_after"]):
                if not snapshot:
                    reject("capacity snapshot missing")
                for row in snapshot:
                    if (row["affinity_cpus"] < floors["affinity_cpus"] or row["physical_memory_bytes"] < floors["physical_memory_bytes"]
                            or row["fd_soft_limit"] < floors["fd_soft_limit"] or row["available_disk_bytes"] < floors["evidence_available_bytes"]):
                        reject("capacity floor not met")
    elif name == "ReadinessResult":
        if value["observed_ns"] >= value["deadline_ns"]:
            reject("readiness at/after deadline")
        if value["ready"]:
            expected = context.get("readiness_steps", {}).get(value["operation_id"])
            if expected is None or [step["name"] for step in value["steps"]] != expected:
                reject("readiness exact steps missing")
            if any(step["outcome"]["state"] != "exited" or step["outcome"]["exit_code"] != 0 for step in value["steps"]):
                reject("readiness step failed")
            if value["case_id"] is not None and value["producer_process"] is None:
                reject("case readiness lacks producer creation identity")
        output = context.get("artifact_name")
        if any(step["raw_artifact_path"] == output for step in value["steps"]):
            reject("readiness result hashes itself")
    elif name == "Admission":
        # Receipt strings are never their own root of trust. The caller supplies
        # a separately committed gate context; this code does not admit that gate.
        trusted = context.get("trusted_admission")
        if not isinstance(trusted, dict) or trusted.get("status") != "synchronized" or not trusted.get("independently_pinned"):
            reject("no independently trusted admission gate")
            return
        try:
            c.hex_value(trusted["checkpoint_sha"], 40)
            if c.digest_bytes(context["raw_data"]) != trusted["admitted_receipt_sha256"]:
                reject("raw receipt pin mismatch")
            for key in ("trust_policy_sha256", "authorization_sha256", "candidate_sha", "supervisor_sha256", "probe_manifest_sha256", "binding_manifest_sha256"):
                if value[key] != trusted[key]:
                    reject("trusted admission binding mismatch: " + key)
            if value["reviewer"] not in trusted["reviewers"] or value["verdict"] != "admitted":
                reject("reviewer/verdict not admitted")
            expires = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00"))
            now = datetime.fromisoformat(context["now_utc"].replace("Z", "+00:00"))
            if expires.utcoffset() != timezone.utc.utcoffset(expires) or now.tzinfo is None or now >= expires:
                reject("admission expired/invalid UTC")
        except (KeyError, ValueError, TypeError):
            reject("admission context incomplete/invalid")


def validate_value(name: str, value, context: dict | None = None) -> tuple[str, ...]:
    root = c.specification()["support_schemas"]
    if name not in root["$defs"]:
        return ("unknown schema: " + name,)
    errors = []
    _schema(value, {"$ref": "#/$defs/" + name}, root, name, errors, context or {})
    return tuple(errors)


def validate_artifact(name: str, data: bytes, context: dict) -> tuple[str, ...]:
    root = c.specification()["support_schemas"]
    if name == "journal.jsonl":
        if len(data) > root["journal"]["max_total_bytes"]:
            return ("journal byte cap exceeded",)
        try:
            if data and not data.endswith(b"\n"):
                return ("torn journal record",)
            lines = data.splitlines(keepends=True)
            if any(len(line) > root["journal"]["max_record_bytes"] for line in lines):
                return ("journal record cap exceeded",)
            return validate_journal(tuple(c.strict_json(line) for line in lines))
        except (ValueError, UnicodeError):
            return ("invalid journal JSON",)
    contract = {**root["artifact_contracts"], **root["input_contracts"]}.get(name)
    if contract is None:
        return ("unknown artifact: " + name,)
    if len(data) > contract["max_bytes"]:
        return ("artifact byte cap exceeded",)
    try:
        value = c.strict_json(data)
        if data != c.canonical_json(value):
            return ("support artifact is not canonical JSON bytes",)
    except (ValueError, UnicodeError, RecursionError):
        return ("invalid JSON",)
    errors = []
    ctx = {**context, "raw_data": data, "artifact_name": name}
    _schema(value, contract["schema"], root, name, errors, ctx)
    if errors:
        return tuple(errors)
    if name == "migrations.json":
        cases = [case["id"] for case in c.inventory()["api_cases"]] if context.get("lane", "api") == "api" else []
        expected = [(case, version) for case in cases for version in range(1, 41)]
        if [(row["case_id"], row["version"]) for row in value] != expected:
            errors.append("migrations: exact forty applied versions per API case required")
        database_keys = {case: {r["database_resource_key"] for r in value if r["case_id"] == case} for case in cases}
        if any(len(keys) != 1 for keys in database_keys.values()) or len({next(iter(keys)) for keys in database_keys.values() if keys}) != len(cases):
            errors.append("migrations: unique owned per-case databases required")
    if name in ("service-readiness.json", "service-exits.json"):
        expected = [("api", role) for role in ("postgres", "nats", "s3", "runner")]
        if context.get("lane", "api") == "dto":
            expected = [("dto", "runner")]
        if [(row["generation"], row["kind"]) for row in value] != expected:
            errors.append("service rows do not match exact generation inventory")
    if name.endswith(("before.json", "after.json")):
        counterpart = context.get("counterpart")
        if counterpart is not None and counterpart != value:
            errors.append("immutable before/after manifests differ")
    return tuple(errors)


def journal_event(value: dict) -> dict:
    if "event_sha256" in value:
        raise ValueError("caller cannot supply event self hash")
    result = {**copy.deepcopy(value), "event_sha256": c.digest(value)}
    errors = validate_value("JournalEvent", result)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def validate_journal(journal: tuple[dict, ...]) -> tuple[str, ...]:
    errors = []
    previous = "0" * 64
    previous_ns = -1
    sealed = False
    attempt_id = None
    epoch = 1
    for index, event in enumerate(journal):
        structural = validate_value("JournalEvent", event)
        errors.extend(structural)
        if structural:
            continue
        if sealed:
            errors.append("journal append after seal_intent")
        if event["sequence"] != index or event["previous_sha256"] != previous:
            errors.append("journal chain/sequence mismatch")
        if event["event_sha256"] != c.digest({k: v for k, v in event.items() if k != "event_sha256"}):
            errors.append("journal event hash mismatch")
        if event["monotonic_ns"] < previous_ns or event["monotonic_ns"] > event["deadline_ns"]:
            errors.append("journal clock/deadline mismatch")
        if attempt_id is not None and event["attempt_id"] != attempt_id:
            errors.append("journal attempt changed")
        attempt_id = event["attempt_id"]
        if event["fence"]["journal_sequence"] != index:
            errors.append("fence sequence mismatch")
        if event["action"] == "fence_advance":
            if event["fence"]["epoch"] != epoch + 1 or event["fence"]["holder"] != "watchdog_cleanup":
                errors.append("invalid durable fence advance")
            epoch = event["fence"]["epoch"]
        elif event["action"] != "stale_action_rejected" and event["fence"]["epoch"] != epoch:
            errors.append("stale journal mutation epoch")
        if event["action"] == "seal_intent":
            if event["state"] != "sealing" or event["observation_sha256"] is not None:
                errors.append("seal intent must not bind later artifacts")
            sealed = True
        previous, previous_ns = c.digest_bytes(c.canonical_json(event)), event["monotonic_ns"]
    if len(journal) > 20000:
        errors.append("journal record count exceeded")
    return tuple(errors)


def append_journal(journal: tuple[dict, ...], value: dict) -> tuple[dict, ...]:
    result = (*journal, journal_event(value))
    errors = validate_journal(result)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def ownership_matches(expected: dict, observed: dict) -> bool:
    """Complete recorded ownership comparison, including PID start and volume metadata."""
    if validate_value("Resource", expected) or validate_value("Resource", observed):
        return False
    keys = ("resource_key", "generation", "kind", "attempt_id", "candidate_sha", "supervisor_sha256",
            "name", "immutable_id", "created_at", "labels", "process", "filesystem", "owner_resource_key")
    if any(expected[k] != observed[k] for k in keys):
        return False
    return expected["status"] in ("verified", "stopped") and observed["status"] in ("verified", "stopped")


class MemoryEvidencePort:
    """Offline fake; preserves every byte and exclusive writes, including torn writes."""
    def __init__(self, fail_at=None):
        self.files = {}
        self.calls = []
        self.fail_at = fail_at

    def append_fsync(self, name, data):
        self.calls.append(("append_fsync", name))
        self.files[name] = self.files.get(name, b"") + data
        if name == self.fail_at:
            raise OSError("fake fsync failure")

    def write_exclusive(self, name, data):
        self.calls.append(("write_exclusive", name))
        if name in self.files:
            raise ValueError("evidence already exists")
        self.files[name] = data
        if name == self.fail_at:
            raise OSError("fake write/fsync failure")

    def fsync_parent(self, name):
        self.calls.append(("fsync_parent", name))


def seal_evidence(port, journal: tuple[dict, ...], manifest: dict, terminal: dict, sealed_at: str) -> dict:
    errors = validate_journal(journal)
    if errors or not journal or journal[-1]["action"] != "seal_intent":
        raise ValueError("sealing requires intact frozen final journal")
    if validate_value("Manifest", manifest):
        raise ValueError("invalid manifest")
    journal_bytes = b"".join(c.canonical_json(event) for event in journal)
    # The broker must have durably appended the final event before this call.
    # The port exposes immutable original bytes for independent comparison.
    if getattr(port, "files", {}).get("journal.jsonl") != journal_bytes:
        raise ValueError("final journal not durably present")
    manifest_bytes = c.canonical_json(manifest)
    port.write_exclusive("manifest.json", manifest_bytes)
    port.fsync_parent("manifest.json")
    terminal = {**copy.deepcopy(terminal), "manifest_sha256": c.digest_bytes(manifest_bytes), "journal_sha256": c.digest_bytes(journal_bytes)}
    if validate_value("Terminal", terminal):
        raise ValueError("invalid terminal")
    terminal_bytes = c.canonical_json(terminal)
    port.write_exclusive("terminal.json", terminal_bytes)
    port.fsync_parent("terminal.json")
    seal = dict(attempt_id=manifest["attempt_id"], manifest_sha256=c.digest_bytes(manifest_bytes),
                terminal_sha256=c.digest_bytes(terminal_bytes), journal_sha256=c.digest_bytes(journal_bytes), sealed_at=sealed_at)
    seal["seal_sha256"] = c.digest(seal)
    port.write_exclusive("seal.json", c.canonical_json(seal))
    port.fsync_parent("seal.json")
    return seal
