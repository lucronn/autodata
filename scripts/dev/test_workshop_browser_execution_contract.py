"""Offline contract tests: none of these tests starts a child or a service."""
import dataclasses
import json
import ast
from pathlib import Path

import pytest

import workshop_browser_execution_contract as c


def bindings():
    return c.RuntimeBindings(
        candidate_sha=c.CANDIDATE_SHA, candidate_tree=c.CANDIDATE_TREE,
        supervisor_sha256="a" * 64, attempt_id="b" * 32,
        source_root="/offline/source", tools_root="/offline/tools",
        attempt_root="/offline/evidence", host_python="/bin/python3", docker="/bin/docker",
        images={k: "sha256:" + "c" * 64 for k in c.IMAGE_ROLES},
        image_config_sha256={k: "d" * 64 for k in c.IMAGE_ROLES},
        image_rootfs_sha256={k: "e" * 64 for k in c.IMAGE_ROLES},
        runtime_admission_sha256=None, docker_socket="/offline/docker.sock",
        docker_config_root="/offline/config", module_cache_root="/offline/modules",
        browser_cache_root="/offline/browsers", control_root="/offline/control")


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_strict_json_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError):
        c.strict_json(raw)


@pytest.mark.parametrize("field,value", [
    ("source_root", "relative"), ("tools_root", "/offline/source/nested"),
    ("attempt_root", "/offline/source"), ("browser_cache_root", "/offline/a/../b"),
    ("module_cache_root", "/offline/a,b"), ("candidate_sha", "0" * 40),
    ("attempt_id", "B" * 32), ("docker_socket", "tcp://localhost"),
    ("images", {"runner": "runner:latest"}),
    ("source_root", "/"), ("docker", "/${UNRESOLVED_DOCKER}"),
    ("host_python", "/${UNRESOLVED_PYTHON}"),
])
def test_invalid_bindings_cannot_compile(field, value):
    with pytest.raises(ValueError):
        c.compile_graph(dataclasses.replace(bindings(), **{field: value}), "api")


def test_unknown_binding_and_lane_reject():
    data = dataclasses.asdict(bindings())
    with pytest.raises(ValueError):
        c.parse_bindings({**data, "HTTP_PROXY": "bad"})
    with pytest.raises(ValueError):
        c.compile_graph(bindings(), "paid")


def test_graph_is_deterministic_and_retains_inventory_and_barriers():
    graph = c.compile_graph(bindings(), "api")
    assert graph == c.compile_graph(bindings(), "api")
    ids = [op.id for op in graph]
    assert len(ids) == len(set(ids))
    assert [op.index for op in graph] == list(range(len(graph)))
    assert ids.index("api.runner.start") < ids.index("api.service.pg")
    assert ids.index("api.service.s3") < ids.index("api.producer.start")
    assert len([i for i in ids if i.endswith(".migrations")]) == 21
    for case in c.inventory()["api_cases"]:
        prefix = "api.case." + case["id"]
        assert ids.index("api.producer.start") < ids.index(prefix + ".migrations")
        assert ids.index(prefix + ".migrations") < ids.index(prefix + ".fixture")
        assert ids.index(prefix + ".fixture") < ids.index(prefix + ".browser-permission")
    c.validate_operations(graph)


def test_dto_stays_blocked_and_has_go_before_tls_before_browser():
    b = dataclasses.replace(bindings(), runtime_admission_sha256="f" * 64)
    assert "blocked_timer_dependency" in c.graph_blockers(b, "dto")
    assert "live_adapter_not_admitted" in c.graph_blockers(b, "dto")
    ops = c.compile_graph(b, "dto")
    ids = [op.id for op in ops]
    assert ids.index("dto.api-generation-sealed") < ids.index("dto.net.create")
    assert ids.index("dto.go.start") < ids.index("dto.fixture.ready") < ids.index("dto.browser.start")
    assert not any("migrations" in i or "service.pg" in i for i in ids)
    commands = [op.command for op in ops if op.command]
    assert not any("AUTODATA_LIFECYCLE_TEST" in dict(cmd.environment) for cmd in commands)


def test_fixture_readiness_paths_match_frozen_schedule():
    for lane in ("api", "dto"):
        ops = c.compile_graph(bindings(), lane)
        fixture_ops = [op for op in ops if op.readiness and op.readiness["action"] == "fixture_ready_tls_assets"]
        for op in fixture_ops:
            case = op.readiness["case_id"]
            wanted = "/artifacts/readiness/" + lane + "/" + ((case + "/") if case else "") + "fixture.json"
            assert op.readiness["output_path"] == wanted


def test_concrete_command_constructor_requires_observed_ids_and_keeps_isolation():
    b = bindings()
    cmd = c.resource_command(b, "api", "runner", "create", network_id="1" * 64)
    assert cmd.argv[:5] == (b.docker, "--host", "unix://" + b.docker_socket, "--config", b.docker_config_root)
    assert "--pull" in cmd.argv and "never" in cmd.argv
    assert "--read-only" in cmd.argv and "no-new-privileges" in cmd.argv
    assert not set(cmd.argv) & {"--publish", "-p", "--privileged", "--force", "--restart"}
    assert b.docker_socket not in " ".join(cmd.argv[5:])
    assert dict(cmd.environment) == c.environment("host", b.attempt_root)
    assert cmd.binding_sha256 == c.digest(c.command_dict(cmd, include_hash=False))
    with pytest.raises(ValueError):
        c.resource_command(b, "api", "runner", "create", network_id="guessed-name")


@pytest.mark.parametrize("role", ["postgres", "nats", "s3", "runner"])
def test_service_commands_use_exact_image_and_reset_environment(role):
    cmd = c.resource_command(bindings(), "api", role, "create", network_id="1" * 64)
    assert "sha256:" + "c" * 64 in cmd.argv
    assert "--entrypoint" in cmd.argv
    env = [cmd.argv[i + 1] for i, v in enumerate(cmd.argv[:-1]) if v == "--env"]
    assert env == sorted(env)


def test_canonical_bytes_and_inventory_equality():
    assert c.canonical_json({"z": "é", "a": 1}) == b'{"a":1,"z":"\\u00e9"}\n'
    inv = c.inventory()
    c.validate_inventory(inv)
    inv["dto_cases"] = inv["dto_cases"][:-1]
    with pytest.raises(ValueError):
        c.validate_inventory(inv)


@pytest.mark.parametrize("extra", ["HTTP_PROXY", "INCEPTION_API_KEY", "DOCKER_HOST", "GOOGLE_APPLICATION_CREDENTIALS"])
def test_commands_reject_ambient_environment_keys(extra):
    b = bindings()
    env = c.environment("host", b.attempt_root)
    with pytest.raises(ValueError):
        c.make_command("offline", "host", [b.docker, "version"], b.tools_root, {**env, extra: "bad"},
                       10000, b.attempt_root + "/out", b.attempt_root + "/err")


def test_runner_does_not_add_undeclared_alias_and_full_docker_verbs_are_closed():
    b = bindings()
    assert "--network-alias" not in c.resource_command(b, "api", "runner", "create", network_id="1" * 64).argv
    for verb, suffix in (("start", ["start", "2" * 64]), ("inspect", ["inspect", "--type", "container", "2" * 64]),
                         ("stop", ["stop", "--time", "2", "2" * 64]), ("kill", ["kill", "--signal", "KILL", "2" * 64]),
                         ("logs", ["logs", "--timestamps", "2" * 64]), ("rm", ["rm", "2" * 64])):
        assert c.resource_command(b, "api", "runner", verb, resource_id="2" * 64).argv[5:] == tuple(suffix)
    for verb in ("exec", "prune", "restart", "pull", "build"):
        with pytest.raises(ValueError):
            c.resource_command(b, "api", "runner", verb, resource_id="2" * 64)


def test_modules_import_no_process_or_network_clients():
    for filename in ("workshop_browser_execution_contract.py", "workshop_browser_execution_evidence.py",
                     "workshop_browser_execution_supervisor.py", "workshop_browser_preparation_probe.py"):
        tree = ast.parse(Path(c.__file__).with_name(filename).read_text())
        imports = {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        imports.update(alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        assert not imports & {"subprocess", "socket", "docker", "requests", "http", "signal", "multiprocessing", "ctypes"}
