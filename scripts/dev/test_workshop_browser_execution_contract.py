"""Offline contract tests: none of these tests starts a child or a service."""
import copy
import hashlib
import re
import dataclasses
import json
import ast
from pathlib import Path

import pytest

import workshop_browser_execution_contract as c


def bindings():
    base = c.RuntimeBindings(
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
    return dataclasses.replace(base,
        candidate_sha="6949eb1b1a5b93c9b2eb0579328e24c697f6f331",
        candidate_tree="47ec54b1896c83a39b6637a6ce944d3620414f4e")


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


def test_dto_fixture_declares_the_source_merged_log_path():
    cmd = c.producer_command(bindings(), "dto_go")
    assert cmd.stdout_path == cmd.stderr_path == "/artifacts/dto/go-fixture.log"


def test_modules_import_no_process_or_network_clients():
    for filename in ("workshop_browser_execution_contract.py", "workshop_browser_execution_evidence.py",
                     "workshop_browser_execution_supervisor.py", "workshop_browser_preparation_probe.py"):
        tree = ast.parse(Path(c.__file__).with_name(filename).read_text())
        imports = {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        imports.update(alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        assert not imports & {"subprocess", "socket", "docker", "requests", "http", "signal", "multiprocessing", "ctypes"}


CURRENT_SPEC = Path(c.__file__).resolve().parents[2] / "docs/agents/specs/2026-11-05-workshop-browser-supervisor-deadlines.json"


def test_current_spec_is_fresh_and_validated():
    value = c.specification()
    assert value == json.loads(CURRENT_SPEC.read_bytes())
    assert c.validate_source_contract(value) is None
    value["inventory"]["api_cases"].clear()
    assert len(c.specification()["inventory"]["api_cases"]) == 21


@pytest.mark.parametrize("sha,tree", [
    ("4d82e413e04fb2401ac7bc28dc828375ac662180", "d9fb2a8f49beacd009374a76327d0736c1fc9b0a"),
    ("6949eb1b1a5b93c9b2eb0579328e24c697f6f331", "d9fb2a8f49beacd009374a76327d0736c1fc9b0a"),
    ("4d82e413e04fb2401ac7bc28dc828375ac662180", "47ec54b1896c83a39b6637a6ce944d3620414f4e"),
    ("c374f77af461f01d367a8b802c7d7bea886fe7ec", "47ec54b1896c83a39b6637a6ce944d3620414f4e"),
])
def test_old_mixed_and_tool_identities_reject_even_with_admission(sha, tree):
    with pytest.raises(ValueError):
        c.compile_graph(dataclasses.replace(bindings(), candidate_sha=sha,
            candidate_tree=tree, runtime_admission_sha256="f" * 64), "api")


# Each mutation changes one load-bearing value; a missing frozen-section check
# would allow that mutation through the public pure validator.
@pytest.mark.parametrize("path,replacement", [
    (("candidate_sha",), "4d82e413e04fb2401ac7bc28dc828375ac662180"),
    (("candidate_tree",), None),
    (("source_candidate_sha",), "0" * 40),
    (("source_binding", "candidate_tree"), "0" * 40),
    (("source_manifest", 0, "blob"), "0" * 40),
    (("source_manifest", 0, "bytes"), 1),
    (("source_pins", "scripts/dev/workshop_browser_smoke.py", "sha256"), "0" * 64),
    (("producer_source_input_sha256", "scripts/dev/workshop_browser_smoke.py"), "0" * 64),
    (("current_served_asset_manifest", "app.mjs", "blob"), "0" * 40),
    (("api21_v2_inventory", "ordered_cases", 0, "case_id"), "historical-case"),
    (("api21_v2_inventory", "ordered_cases", 0, "required_refs"), ["arbitrary"] * 9),
    (("api_process_command_schedule", "go", "argv", 6), "-timeout=4500s"),
    (("dto_timing_contract", "dto_fixture_seconds"), 4400),
    (("dto_timing_contract_sha256",), "0" * 64),
    (("environments", "api_pytest", "AUTODATA_API21_SOURCE_TREE"), "${TREE}"),
    (("environments", "api_pytest", "AUTODATA_R3_CANDIDATE_SHA"), "0" * 40),
    (("inventory", "dto_cases", 0, "engine"), "unknown"),
    (("inventory_sha256",), "0" * 64),
    (("static_command_contract", "api", "argv", 6), "--junitxml=/artifacts/api/junit.xml"),
    (("static_command_contract", "api", "cwd"), "/tmp"),
    (("timeout_binding_rules", "dto_resource_wait_ms"), 4560000),
    (("deadlines", "dto_go_test_seconds"), 4500),
    (("support_schemas", "$defs", "Command", "properties", "timeout_ms", "maximum"), 4560000),
])
def test_source_contract_rejects_single_value_mutations(path, replacement):
    value = copy.deepcopy(c.specification())
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        c.validate_source_contract(value)


@pytest.mark.parametrize("section", ["source_pins", "producer_source_input_sha256",
    "current_served_asset_manifest", "environments", "frozen_section_digests"])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_source_contract_rejects_missing_and_extra_map_keys(section, change):
    value = copy.deepcopy(c.specification())
    if change == "missing":
        value[section].pop(next(iter(value[section])))
    else:
        value[section]["unexpected"] = "untrusted"
    with pytest.raises(ValueError):
        c.validate_source_contract(value)


@pytest.mark.parametrize("replacement", [None, "", "0" * 40, "${TREE}"])
def test_api_source_tree_cannot_be_filled_from_ambient_environment(monkeypatch, replacement):
    monkeypatch.setenv("AUTODATA_API21_SOURCE_TREE", "47ec54b1896c83a39b6637a6ce944d3620414f4e")
    env = c.environment("api_pytest", "/unused")
    if replacement is None:
        del env["AUTODATA_API21_SOURCE_TREE"]
    else:
        env["AUTODATA_API21_SOURCE_TREE"] = replacement
    with pytest.raises(ValueError):
        c.validate_environment("api", env)


def test_exact_current_commands_and_dto_abort_bounds():
    b = bindings()
    api = c.producer_command(b, "api")
    assert api.argv == ("/usr/local/bin/python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "--junitxml=/artifacts/workshop-browser-api.xml",
        "workers/ingestion-python/tests/test_workshop_browser_integration.py")
    assert api.cwd == "/workspace" and api.timeout_ms == 2100000
    assert dict(api.environment)["AUTODATA_API21_SOURCE_TREE"] == "47ec54b1896c83a39b6637a6ce944d3620414f4e"
    go = c.producer_command(b, "dto_go")
    assert go.argv == ("/usr/local/go/bin/go", "test", "-count=1", "-run",
        "^TestWorkshopBrowserFixtureHTTP$", "-timeout=5040s", ".")
    assert go.cwd == "/workspace/apps/api-go" and go.timeout_ms == 5100000
    dto = c.producer_command(b, "dto", origin="https://127.0.0.1:12345")
    assert dto.argv == ("/usr/local/bin/python3", "/workspace/scripts/dev/workshop_browser_smoke.py",
        "--base-url", "https://127.0.0.1:12345", "--mode", "dto-fixture", "--browser", "all",
        "--candidate-sha", "6949eb1b1a5b93c9b2eb0579328e24c697f6f331", "--output", "/artifacts/browser")
    assert dto.cwd == "/workspace" and dto.timeout_ms == 5100000
    for lane, bound in (("api", 2100000), ("dto", 5100000)):
        assert c.resource_command(b, lane, "runner", "wait", resource_id="1" * 64).timeout_ms == bound
    ops = c.compile_graph(b, "dto")
    assert ops == c.compile_graph(b, "dto")
    assert {op.id: op.timeout_ms for op in ops if op.id in ("dto.go.start", "dto.browser.start")} == {
        "dto.go.start": 5100000, "dto.browser.start": 5100000}
    assert all(op.timeout_ms == 120000 for op in ops if op.readiness or op.id == "dto.seal")
    admitted = dataclasses.replace(b, runtime_admission_sha256="f" * 64)
    assert "blocked_timer_dependency" in c.graph_blockers(admitted, "dto")
    assert "supervisor_dto_deadline_mismatch" not in c.graph_blockers(admitted, "dto")
    assert {"api_finite_success_proof_missing", "source_observer_not_admitted",
        "runtime_admission_not_verified", "filesystem_identity_not_observed",
        "go_path_resolution_not_observed", "live_adapter_not_admitted"} <= set(c.graph_blockers(admitted, "api"))


@pytest.mark.parametrize("timeout,valid", [(1, True), (4560000, True), (5100000, True),
    (0, False), (-1, False), (True, False), ("5100000", False), (5100001, False)])
def test_command_timeout_current_boundary(timeout, valid):
    def command():
        return c.make_command("offline", "api", ["/bin/true"], "/workspace",
            c.environment("api_pytest", "/unused"), timeout, "/artifacts/out", "/artifacts/err")
    if valid:
        assert command().timeout_ms == timeout
    else:
        with pytest.raises(ValueError):
            command()


def test_source_timing_and_required_env_are_inspected_without_producer_import():
    root = Path(c.__file__).resolve().parents[2]
    timing_bytes = (root / "scripts/dev/fixtures/workshop_customer/timing.json").read_bytes()
    timing = json.loads(timing_bytes)
    tree = ast.parse((root / "scripts/dev/workshop_browser_smoke.py").read_text())
    declared = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "DTO_TIMING_V1" for t in n.targets))
    assert timing == declared == c.specification()["dto_timing_contract"]
    assert hashlib.sha256(timing_bytes).hexdigest() == c.specification()["dto_timing_contract_sha256"]
    assert {k: timing[k] for k in ("dto_fixture_seconds", "go_test_seconds", "ci_exercise_seconds",
        "producer_hard_seconds", "worker_hard_seconds")} == dict(dto_fixture_seconds=4800,
        go_test_seconds=5040, ci_exercise_seconds=5100, producer_hard_seconds=4440, worker_hard_seconds=4380)
    go = (root / "apps/api-go/workshop_browser_fixture_test.go").read_text()
    expected = go.split("expected := map[string]int{", 1)[1].split("}", 1)[0]
    assert dict((k, int(v)) for k, v in re.findall(r'"([^"]+)": ([0-9]+)', expected)) == {
        k: v for k, v in timing.items() if k != "version"}
    source = ast.parse((root / "workers/ingestion-python/tests/test_workshop_browser_integration.py").read_text())
    binding = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "_binding")
    env_keys = {n.slice.value for n in ast.walk(binding) if isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Attribute) and n.value.attr == "environ" and isinstance(n.slice, ast.Constant)}
    assert {"AUTODATA_R3_CANDIDATE_SHA", "AUTODATA_API21_SOURCE_TREE"} <= env_keys


def test_required_refs_and_identities_are_exact_not_just_counts():
    spec = c.specification()
    api = spec["api21_v2_inventory"]
    assert [case["case_id"] for case in api["ordered_cases"]] == [case["id"] for case in spec["inventory"]["api_cases"]]
    refs = [api["junit_ref"]] + [ref for case in api["ordered_cases"] for ref in case["required_refs"]]
    assert len(refs) == len(set(refs)) == 190
    assert sum(ref.endswith(("child-processes.json", "parent-process.json")) for ref in refs) == 42
    assert api["junit_original_producer_path"] == "/artifacts/workshop-browser-api.xml"
    assert len(spec["inventory"]["dto_cases"]) == 120
    assert spec["accepted_case_credit"] == spec["accepted_new_case_credit"] == 0
    assert spec["verified_case_ids"] == [] and not any(spec["authorities"].values())


def test_missing_or_malformed_current_spec_has_no_historical_fallback(monkeypatch, tmp_path):
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(c, "SPEC_PATH", missing)
    with pytest.raises(OSError):
        c.specification()
    missing.write_bytes(b'{"candidate_sha":1,"candidate_sha":2}')
    with pytest.raises(ValueError):
        c.specification()
    missing.write_text('{}')
    with pytest.raises(ValueError):
        c.specification()


def test_temporal_policy_is_exact_and_returns_fresh_copies():
    assert "temporal_policy" in c.specification()
    value=c.temporal_policy()
    assert [r["seconds"] for r in value["slots"]]==[480,180,480,360,2100,240,120,5100,240]
    assert (value["ordinary_seconds"],value["emergency_cancellation_seconds"],value["hard_seconds"])==(9300,120,9420)
    assert c.validate_temporal_policy(value) is None
    value["slots"][0]["seconds"]=1
    assert c.temporal_policy()["slots"][0]["seconds"]==480


@pytest.mark.parametrize("ordinary,hard", [(7380,7500),(7920,8040),(9060,9180),(9420,9540)])
def test_recomputed_policy_digests_cannot_admit_other_totals(ordinary,hard):
    changed=copy.deepcopy(c.specification())
    assert "temporal_policy" in changed
    changed['temporal_policy']['ordinary_seconds']=ordinary
    changed['temporal_policy']['hard_seconds']=hard
    changed['frozen_section_digests']['temporal_policy']=c.digest(changed['temporal_policy'])
    with pytest.raises(ValueError): c.validate_source_contract(changed)


@pytest.mark.parametrize("index",range(9))
@pytest.mark.parametrize("replacement", [True,"120",0,-1,121])
def test_each_temporal_slot_rejects_tampering_even_with_recomputed_digest(index,replacement):
    assert "temporal_policy" in c.specification()
    changed=c.specification(); changed['temporal_policy']['slots'][index]['seconds']=replacement
    changed['frozen_section_digests']['temporal_policy']=c.digest(changed['temporal_policy'])
    with pytest.raises(ValueError): c.validate_temporal_policy(changed['temporal_policy'])
    with pytest.raises(ValueError): c.validate_source_contract(changed)


@pytest.mark.parametrize("mutation", ["order","duplicate","reserve_zero","reserve_extra",
    "api_shared120","dto4560","dto_separate_readiness","browser_fresh5100"])
def test_temporal_structure_cannot_self_admit(mutation):
    assert "temporal_policy" in c.specification()
    changed=c.specification(); policy=changed['temporal_policy']
    if mutation=='order': policy['slots'][0],policy['slots'][1]=policy['slots'][1],policy['slots'][0]
    elif mutation=='duplicate': policy['slots'][1]['id']=policy['slots'][0]['id']
    elif mutation=='reserve_zero': policy['emergency_cancellation_seconds']=0
    elif mutation=='reserve_extra': policy['emergency_cancellation_seconds']=240
    elif mutation=='api_shared120': policy['api_readiness']['shared_seconds']=120
    elif mutation=='dto4560': policy['dto']['envelope_seconds']=4560
    elif mutation=='dto_separate_readiness': policy['dto']['readiness_nested']=False
    else: policy['dto']['browser_after_full_readiness_remaining_seconds']=5100
    changed['frozen_section_digests']['temporal_policy']=c.digest(policy)
    with pytest.raises(ValueError): c.validate_temporal_policy(policy)
    with pytest.raises(ValueError): c.validate_source_contract(changed)


@pytest.mark.parametrize('field',['ordinary_seconds','emergency_cancellation_seconds','hard_seconds','attempts','additional_retries'])
@pytest.mark.parametrize('replacement',[True,'120',0,-1])
def test_policy_scalar_types_and_composition_cannot_drift(field,replacement):
    policy=c.temporal_policy(); original=policy[field]
    if type(original) is type(replacement) and original==replacement:
        replacement=1
    policy[field]=replacement
    with pytest.raises(ValueError): c.validate_temporal_policy(policy)
