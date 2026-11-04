"""Frozen read-only preparation language; static outputs only."""
import copy

import pytest

import workshop_browser_execution_contract as c
import workshop_browser_execution_evidence as e
import workshop_browser_preparation_probe as p
from test_workshop_browser_execution_evidence import outcome


def probe_input():
    value = dict(version="browser-preparation-input-v1", candidate_sha=c.CANDIDATE_SHA,
                 candidate_tree=c.CANDIDATE_TREE, authorization_sha256="1" * 64, probe_source_sha256="2" * 64,
                 host_python="/host/python3", host_go="/host/go", docker="/host/docker",
                 docker_socket="/host/docker.sock", docker_config_root="/offline/config",
                 source_root="/offline/source", tools_root="/offline/tools", module_cache_root="/offline/modules",
                 browser_cache_root="/offline/browsers", evidence_root="/offline/evidence",
                 images={k: "sha256:" + "3" * 64 for k in c.IMAGE_ROLES},
                 exported_runtime_manifest_paths=["/offline/tools/runtime.json"],
                 limits=dict(wall_seconds=180, per_subprocess_seconds=10, max_operations=18, artifact_bytes=33554432, retry_count=0))
    value["expected_environment_sha256"] = c.digest(c.environment("host", value["evidence_root"]))
    return value


def test_exact_thirteen_operations_have_frozen_order_templates_outputs_and_no_live_actions():
    inp = probe_input()
    ops = p.plan_preparation(inp)
    schedule = c.specification()["preparation_schedule"]
    assert [op.id for op in ops] == [row["id"] for row in schedule]
    assert [op.index for op in ops] == list(range(13))
    assert [op.kind for op in ops] == ["command"] * 7 + ["local_read"] * 6
    for i, op in enumerate(ops):
        assert op.depends_on == ((ops[i - 1].id,) if i else ())
        assert op.timeout_ms == 10000
        assert op.output_prefix == inp["evidence_root"] + "/preparation/" + op.id
        if op.command:
            assert op.command.stdout_path == op.output_prefix + ".stdout"
            assert op.command.stderr_path == op.output_prefix + ".stderr"
            assert dict(op.command.environment) == c.environment("host", inp["evidence_root"])
            assert op.command.cwd == inp["tools_root"]
            assert not set(op.command.argv) & {"run", "exec", "start", "build", "pull", "install"}
        else:
            assert op.local_read["before_after"] is True
            assert op.local_read["symlink_policy"] == "reject"
    assert ops[0].command.argv == (inp["docker"], "--host", "unix://" + inp["docker_socket"], "--config", inp["docker_config_root"], "version", "--format", "{{json .}}")
    assert ops[6].command.argv == (inp["host_go"], "version")
    assert p.plan_preparation(copy.deepcopy(inp)) == ops


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(extra="secret"), lambda v: v["limits"].update(retry_count=1),
    lambda v: v["limits"].update(wall_seconds=181), lambda v: v["limits"].update(max_operations=19),
    lambda v: v.update(exported_runtime_manifest_paths=[]),
    lambda v: v["images"].update(runner="runner:latest"),
    lambda v: v.update(source_root="/offline/tools/source"),
    lambda v: v.update(expected_environment_sha256="0" * 64),
    lambda v: v.update(exported_runtime_manifest_paths=["/secret/export.json"]),
])
def test_invalid_probe_inputs_reject(mutate):
    inp = probe_input()
    mutate(inp)
    with pytest.raises(ValueError):
        p.plan_preparation(inp)


def test_go_parser_is_fullmatch_and_missing_fields_do_not_become_success():
    inp = probe_input()
    op = p.plan_preparation(inp)[6]
    result = p.parse_command_output(op, b"go version go1.24.3 linux/amd64\n", b"", inp, "4" * 64, outcome())
    assert result["values"]["go_version"] == "go1.24.3"
    assert result["values"]["image_id"] is None
    assert result["raw_stdout_sha256"] == c.digest_bytes(b"go version go1.24.3 linux/amd64\n")
    for raw in (b"go version go1x24 linux/amd64\n", b"go version go1.24 linux/amd64\nextra\n", b"", b"go version go1.24 linux/amd64"):
        with pytest.raises(ValueError):
            p.parse_command_output(op, raw, b"", inp, "4" * 64, outcome())


def test_python_parser_requires_exact_executable_and_fields():
    inp = probe_input()
    op = p.plan_preparation(inp)[5]
    raw = c.canonical_json(dict(version=[3, 14, 0], implementation="cpython", executable=inp["host_python"]))
    assert p.parse_command_output(op, raw, b"", inp, "4" * 64, outcome())["values"]["python_version"] == [3, 14, 0]
    for obj in (dict(version=[3, True, 0], implementation="cpython", executable=inp["host_python"]),
                dict(version=[3, 14, 0], implementation="cpython", executable="/other/python"),
                dict(version=[3, 14, 0], implementation="cpython", executable=inp["host_python"], extra="bad")):
        with pytest.raises(ValueError):
            p.parse_command_output(op, c.canonical_json(obj), b"", inp, "4" * 64, outcome())


def test_docker_version_parser_requires_both_peers_and_binds_only_produced_values():
    inp = probe_input()
    op = p.plan_preparation(inp)[0]
    version = dict(Version="28.0.0", ApiVersion="1.48", Os="linux", Arch="amd64")
    raw = c.canonical_json(dict(Client=version, Server=version))
    result = p.parse_command_output(op, raw, b"", inp, "4" * 64, outcome())
    assert result["values"]["docker_server_version"] == "28.0.0"
    assert result["values"]["python_version"] is None
    for obj in ({"Client": version}, {"Client": version, "Server": {}}, []):
        with pytest.raises(ValueError):
            p.parse_command_output(op, c.canonical_json(obj), b"", inp, "4" * 64, outcome())


def test_image_parser_needs_exported_byte_bindings_and_rejects_credentials():
    inp = probe_input()
    op = p.plan_preparation(inp)[1]
    obj = dict(Id=inp["images"]["runner"], Architecture="amd64", Os="linux", Config={"Env": ["PATH=/usr/bin:/bin"]}, RootFS={"Layers": ["sha256:" + "5" * 64]})
    exports = {obj["Id"]: dict(config_sha256=c.digest(obj["Config"]), rootfs_sha256=c.digest(obj["RootFS"]), environment={"PATH": "/usr/bin:/bin"})}
    result = p.parse_command_output(op, c.canonical_json(obj), b"", inp, "4" * 64, outcome(), runtime_exports=exports)
    assert result["values"]["image_config_sha256"] == c.digest(obj["Config"])
    with pytest.raises(ValueError):
        p.parse_command_output(op, c.canonical_json(obj), b"", inp, "4" * 64, outcome())
    bad = copy.deepcopy(obj)
    bad["Config"]["Env"].append("INCEPTION_API_KEY=secret")
    with pytest.raises(ValueError):
        p.parse_command_output(op, c.canonical_json(bad), b"", inp, "4" * 64, outcome(), runtime_exports=exports)


def test_operation_cannot_be_substituted_or_duplicate_even_with_valid_hash():
    inp = probe_input()
    ops = p.plan_preparation(inp)
    assert p.validate_preparation_operations(ops, inp) == ()
    assert p.validate_preparation_operations((ops[0],) * 13, inp)


def admission():
    return dict(probe_manifest_sha256="1" * 64, candidate_sha=c.CANDIDATE_SHA, supervisor_sha256="2" * 64,
                reviewer="reviewer", reviewed_at="2026-11-04T00:00:00Z", verdict="admitted",
                binding_manifest_sha256="3" * 64, reasons=[], mechanism="coordinator_pinned_receipt_sha256_v1",
                admission_id="independent-1", authorization_sha256="4" * 64, trust_policy_sha256="5" * 64,
                expires_at="2026-11-05T00:00:00Z")


def test_admission_needs_independent_complete_raw_pin_and_rejects_expiry_and_replay():
    obj = admission()
    raw = c.canonical_json(obj)
    assert e.validate_artifact("runtime-admission.json", raw, {})
    trusted = {k: obj[k] for k in ("probe_manifest_sha256", "candidate_sha", "supervisor_sha256", "binding_manifest_sha256", "authorization_sha256", "trust_policy_sha256")}
    trusted.update(status="synchronized", independently_pinned=True, checkpoint_sha="6" * 40,
                   admitted_receipt_sha256=c.digest_bytes(raw), reviewers=["reviewer"])
    context = dict(trusted_admission=trusted, now_utc="2026-11-04T01:00:00Z")
    assert e.validate_artifact("runtime-admission.json", raw, context) == ()
    assert e.validate_artifact("runtime-admission.json", raw, {**context, "now_utc": obj["expires_at"]})
    changed = c.canonical_json({**obj, "admission_id": "replayed-other-attempt"})
    assert e.validate_artifact("runtime-admission.json", changed, context)
    assert e.validate_artifact("runtime-admission.json", raw, {**context, "trusted_admission": {**trusted, "candidate_sha": "0" * 40}})


def test_execute_rejects_before_any_output_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("live mode did I/O")
    monkeypatch.setattr("builtins.open", forbidden)
    with pytest.raises(c.LiveAdapterNotAdmitted):
        p.main(["execute", "--bindings", "/missing", "--output", "/missing"])


def local_result(op):
    rows = [dict(path=root, kind="directory", mode=448, uid=1, gid=1, device=1, inode=i + 1,
                 bytes=0, sha256=None, classification="unchanged", reason=None)
            for i, root in enumerate(op.local_read["roots"])]
    capacity = [dict(root=root, available_disk_bytes=8589934592, affinity_cpus=4,
                     physical_memory_bytes=12884901888, fd_soft_limit=4096) for root in op.local_read["roots"]]
    return dict(operation_id=op.id, action=op.local_read["action"], before=rows, after=copy.deepcopy(rows),
                capacity_before=capacity if op.index == 12 else [], capacity_after=copy.deepcopy(capacity) if op.index == 12 else [],
                before_sha256=c.digest(rows), after_sha256=c.digest(rows), outcome=outcome(), effective_uid=1, reasons=[])


def test_local_result_requires_root_identity_and_all_capacity_floors_without_free_byte_equality():
    inp = probe_input()
    op = p.plan_preparation(inp)[12]
    result = local_result(op)
    roots = {row["path"]: row for row in result["before"]}
    assert p.validate_local_result(op, result, inp, roots) == ()
    result["capacity_after"][-1]["available_disk_bytes"] += 100
    assert p.validate_local_result(op, result, inp, roots) == ()
    for mutate in (lambda r: r["after"][0].update(inode=999),
                   lambda r: r["capacity_after"][-1].update(available_disk_bytes=1),
                   lambda r: r.update(before=[]), lambda r: r["before"][-1].update(mode=511)):
        changed = copy.deepcopy(result)
        mutate(changed)
        assert p.validate_local_result(op, changed, inp, roots)
    assert p.validate_local_result(op, result, inp, {})


def test_probe_complete_requires_exact_operations_and_literal_null_manifest():
    inp = probe_input()
    ops = p.plan_preparation(inp)
    rows = [dict(index=op.index, outcome={**outcome(), "start_ns": op.index * 3 + 1, "end_ns": op.index * 3 + 2}, bindings=[], before_manifest_sha256=None,
                 after_manifest_sha256=None, spec=c.operation_dict(op)) for op in ops]
    probe = dict(version="browser-preparation-v1", attempt_id="a" * 32, candidate_sha=c.CANDIDATE_SHA,
                 candidate_tree=c.CANDIDATE_TREE, probe_source_sha256="1" * 64, authorization_sha256="2" * 64,
                 start_utc="2026-11-04T00:00:00Z", end_utc="2026-11-04T00:00:01Z", start_ns=0,
                 end_ns=40, deadline_ns=180000000000, operations=rows, manifest_sha256=None,
                 terminal="complete_unadmitted", reasons=[], admitted=False)
    context = dict(preparation_operations=ops)
    assert e.validate_artifact("preparation-probe.json", c.canonical_json(probe), context) == ()
    for mutate in (lambda v: v.update(manifest_sha256="0" * 64), lambda v: v.update(admitted=True),
                   lambda v: v["operations"].pop(), lambda v: v["operations"][1].update(index=0),
                   lambda v: v["operations"][0]["spec"]["command"]["environment"].update(HTTP_PROXY="bad"),
                   lambda v: v.update(end_ns=180000000000)):
        changed = copy.deepcopy(probe)
        mutate(changed)
        assert e.validate_artifact("preparation-probe.json", c.canonical_json(changed), context)
