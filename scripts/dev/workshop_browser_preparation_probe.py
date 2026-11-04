"""Compile the thirteen frozen preparation operations and parse retained bytes.

This is an offline compiler, not a preparation executor. No subprocess, Docker,
filesystem traversal or network adapter is implemented here.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import workshop_browser_execution_contract as c
import workshop_browser_execution_evidence as e


def _resolve(value, bindings):
    if isinstance(value, list):
        return [_resolve(item, bindings) for item in value]
    if isinstance(value, dict):
        return {k: _resolve(v, bindings) for k, v in value.items()}
    if not isinstance(value, str):
        return value
    if value.startswith("unix://@"):
        if value != "unix://@docker_socket":
            raise ValueError("undeclared socket substitution")
        return "unix://" + bindings["docker_socket"]
    if value.startswith("@evidence_root/"):
        suffix = value[len("@evidence_root/"):]
        c.relative_path(suffix)
        return bindings["evidence_root"] + "/" + suffix
    if value.startswith("@"):
        keys = value[1:].split(".")
        target = bindings
        for key in keys:
            if not isinstance(target, dict) or key not in target:
                raise ValueError("unbound typed preparation value: " + value)
            target = target[key]
        if not isinstance(target, str):
            raise ValueError("preparation binding must be string")
        return target
    if "@" in value or "${" in value:
        raise ValueError("unsupported interpolation")
    return value


def plan_preparation(bindings: dict) -> tuple[c.OperationSpec, ...]:
    errors = e.validate_value("ProbeInput", bindings)
    if errors:
        raise ValueError("; ".join(errors))
    result = []
    for row in c.specification()["preparation_schedule"]:
        command = None
        if row["kind"] == "command":
            template = row["command_template"]
            command = c.make_command(row["id"], "probe", _resolve(template["argv"], bindings),
                                     _resolve(template["cwd"], bindings), c.environment("host", bindings["evidence_root"]),
                                     template["timeout_ms"], _resolve(template["stdout_path"], bindings),
                                     _resolve(template["stderr_path"], bindings), row["depends_on"])
        result.append(c.OperationSpec(row["id"], row["index"], row["kind"], command,
                                      _resolve(row["local_read"], bindings), None, tuple(row["depends_on"]), None,
                                      row["timeout_ms"], _resolve(row["output_prefix"], bindings)))
    c.validate_operations(tuple(result))
    return tuple(result)


def validate_preparation_operations(operations, bindings) -> tuple[str, ...]:
    try:
        expected = plan_preparation(bindings)
        actual = [c.operation_dict(op) if isinstance(op, c.OperationSpec) else op for op in operations]
        if actual != [c.operation_dict(op) for op in expected]:
            return ("operation schedule differs from exact frozen rendering",)
        return ()
    except (ValueError, TypeError):
        return ("invalid preparation operation/input",)


def _nonempty(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value:
        raise ValueError("missing/malformed version string")
    return value


def parse_command_output(operation: c.OperationSpec, stdout: bytes, stderr: bytes, bindings: dict,
                         executable_sha256: str, outcome: dict, *, runtime_exports=None) -> dict:
    expected = plan_preparation(bindings)
    if operation.index not in range(7) or operation != expected[operation.index]:
        raise ValueError("not an exact frozen preparation command")
    if len(stdout) > 33554432 or len(stderr) > 33554432:
        raise ValueError("raw output cap exceeded; preserve bytes outside admission")
    c.hex_value(executable_sha256, 64)
    if e.validate_value("Outcome", outcome) or outcome["state"] != "exited" or outcome["exit_code"] != 0:
        raise ValueError("command did not exit successfully")
    parser = c.specification()["preparation_schedule"][operation.index]["parser"]
    fields = c.specification()["support_schemas"]["$defs"]["VersionResult"]["properties"]["values"]["required"]
    values = dict.fromkeys(fields)
    if parser == "go_version_line_v1":
        match = re.fullmatch(rb"go version (go[0-9]+\.[0-9]+(?:\.[0-9]+)?) ([A-Za-z0-9_]+)/([A-Za-z0-9_]+)\n", stdout)
        if match is None:
            raise ValueError("malformed exact Go version line")
        values.update(zip(("go_version", "go_os", "go_arch"), (part.decode("ascii") for part in match.groups())))
    else:
        if not stdout.endswith(b"\n") or stdout.count(b"\n") != 1:
            raise ValueError("version output must be one JSON object and LF")
        obj = c.strict_json(stdout)
        if not isinstance(obj, dict):
            raise ValueError("version object required")
        if parser == "python_version_json_v1":
            if set(obj) != {"version", "implementation", "executable"} or not isinstance(obj["version"], list) or len(obj["version"]) != 3 or any(type(v) is not int or v < 0 for v in obj["version"]):
                raise ValueError("malformed Python version fields")
            if obj["executable"] != bindings["host_python"]:
                raise ValueError("Python executable identity mismatch")
            values.update(python_version=obj["version"], python_implementation=_nonempty(obj["implementation"]), python_executable=obj["executable"])
        elif parser == "docker_version_json_v1":
            for peer, prefix in (("Client", "client"), ("Server", "server")):
                part = obj.get(peer)
                if not isinstance(part, dict) or not {"Version", "ApiVersion", "Os", "Arch"} <= set(part):
                    raise ValueError("Docker peer version missing")
                for source, target in (("Version", "docker_" + prefix + "_version"), ("ApiVersion", "docker_" + prefix + "_api_version"), ("Os", prefix + "_os"), ("Arch", prefix + "_arch")):
                    values[target] = _nonempty(part[source])
        else:
            role = c.IMAGE_ROLES[operation.index - 1]
            if not {"Id", "Architecture", "Os", "Config", "RootFS"} <= set(obj) or obj["Id"] != bindings["images"][role]:
                raise ValueError("image identity missing/mismatched")
            if not isinstance(obj["Config"], dict) or not isinstance(obj["RootFS"], dict) or not isinstance(obj["RootFS"].get("Layers"), list):
                raise ValueError("image Config/RootFS missing")
            for layer in obj["RootFS"]["Layers"]:
                if not isinstance(layer, str) or not layer.startswith("sha256:"):
                    raise ValueError("invalid immutable image layer")
                c.hex_value(layer[7:], 64)
            declared = (runtime_exports or {}).get(obj["Id"])
            config_hash, rootfs_hash = c.digest(obj["Config"]), c.digest(obj["RootFS"])
            if not isinstance(declared, dict) or declared.get("config_sha256") != config_hash or declared.get("rootfs_sha256") != rootfs_hash:
                raise ValueError("exported image config/rootfs binding missing/mismatched")
            image_env = obj["Config"].get("Env", [])
            if not isinstance(image_env, list) or any(not isinstance(item, str) or "=" not in item for item in image_env):
                raise ValueError("malformed image environment")
            pairs = [item.split("=", 1) for item in image_env]
            env = dict(pairs)
            allowed = {"PATH", "LANG", "LC_ALL", "TZ"}
            if len(env) != len(pairs) or set(env) - allowed or env != declared.get("environment"):
                raise ValueError("undeclared/credential-bearing image environment")
            values.update(image_id=obj["Id"], image_os=_nonempty(obj["Os"]), image_arch=_nonempty(obj["Architecture"]),
                          image_config_sha256=config_hash, image_rootfs_sha256=rootfs_hash)
    result = dict(operation_id=operation.id, parser=parser, values=values, executable_sha256=executable_sha256,
                  command_sha256=operation.command.binding_sha256, raw_stdout_sha256=c.digest_bytes(stdout),
                  raw_stderr_sha256=c.digest_bytes(stderr), outcome=outcome, reasons=[])
    if e.validate_value("VersionResult", result):
        raise ValueError("invalid normalized version result")
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("execute", "probe-execute"):
        raise c.LiveAdapterNotAdmitted("preparation live adapter not admitted")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("render",))
    parser.add_argument("--bindings", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    inp = c.strict_json(Path(c.absolute_path(args.bindings)).read_bytes())
    operations = plan_preparation(inp)
    output = Path(c.absolute_path(args.output))
    c.disjoint_roots((str(output.parent), inp["source_root"], inp["tools_root"], inp["module_cache_root"], inp["browser_cache_root"]))
    with output.open("xb") as stream:
        stream.write(c.canonical_json(dict(status="unadmitted", admitted=False, operations=[c.operation_dict(op) for op in operations])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
