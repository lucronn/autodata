"""Malformed static evidence and in-memory durable write protocol tests."""
import copy
import json

import pytest

import workshop_browser_execution_contract as c
import workshop_browser_execution_evidence as e


def outcome(state="exited"):
    return dict(state=state, start_ns=1, end_ns=2, exit_code=0, signal=None,
                reason=None, stdout_sha256="1" * 64, stderr_sha256="2" * 64)


def process():
    return dict(pid=10, pgid=10, start_ticks=100, boot_id="boot", pid_namespace_inode=3,
                executable_sha256="1" * 64, container_id="2" * 64)


def manifest():
    return dict(attempt_id="a" * 32, sealed=True, files=[], total_bytes=0, missing=[], terminal_sha256=None)


def seal_documents(port, state="sealed_unreviewed"):
    support = set(c.specification()["support_schemas"]["artifact_contracts"])
    files = [dict(path=name, kind="regular", mode=384, uid=1, gid=1, device=1, inode=i + 1,
                  bytes=len(data), sha256=c.digest_bytes(data), classification="created", reason=None)
             for i, (name, data) in enumerate(port.files.items())]
    missing = [dict(path=name, state="not_started", reason="not produced", sha256=None, bytes=0)
               for name in sorted(support - set(port.files) - {"manifest.json", "terminal.json", "seal.json"})]
    m = {**manifest(), "files": files, "total_bytes": sum(row["bytes"] for row in files), "missing": missing}
    produced = [dict(path=name, state="produced", reason=None, sha256=c.digest_bytes(data), bytes=len(data))
                for name, data in port.files.items()]
    m_bytes = c.canonical_json(m)
    produced.append(dict(path="manifest.json", state="produced", reason=None, sha256=c.digest_bytes(m_bytes), bytes=len(m_bytes)))
    t = dict(attempt_id="a" * 32, candidate_sha=c.CANDIDATE_SHA, supervisor_sha256="1" * 64,
             state=state, **{"pass": False}, new_case_credit=0, manifest_sha256=None, journal_sha256="0" * 64,
             artifacts=produced + missing, failure_reasons=[] if state == "sealed_unreviewed" else ["source failed"], residual_resource_keys=[])
    return m, t


@pytest.mark.parametrize("value", ["f" * 64, 0, False])
def test_manifest_backreference_is_literal_null(value):
    obj = {**manifest(), "terminal_sha256": value}
    assert e.validate_artifact("manifest.json", c.canonical_json(obj), {})


def test_manifest_valid_and_unknown_keys_duplicate_nan_reject():
    assert e.validate_artifact("manifest.json", c.canonical_json(manifest()), {}) == ()
    for raw in [b'{"attempt_id":"x","attempt_id":"y"}', b'{"x":NaN}', c.canonical_json({**manifest(), "extra": 1})]:
        assert e.validate_artifact("manifest.json", raw, {})


@pytest.mark.parametrize("mutation", ["pid", "pgid", "start_ticks"])
def test_process_zero_identity_rejects(mutation):
    p = process()
    p[mutation] = 0
    assert e.validate_value("Process", p)


def test_outcome_exit_is_exclusive_and_deadlines_are_integer():
    assert e.validate_value("Outcome", outcome()) == ()
    assert e.validate_value("Outcome", {**outcome(), "signal": 9})
    assert e.validate_value("Outcome", {**outcome(), "end_ns": True})
    assert e.validate_value("Outcome", {**outcome(), "end_ns": 0})
    assert e.validate_value("Outcome", {**outcome("running"), "end_ns": 2})


def event(sequence=0, previous="0" * 64, action="intent", state="reserved"):
    return dict(sequence=sequence, previous_sha256=previous, attempt_id="a" * 32,
                utc="2026-11-04T00:00:00Z", monotonic_ns=sequence + 1, deadline_ns=100,
                state=state, action=action, resource_key=None, command_id=None,
                observation_sha256=None, reason=None,
                fence=dict(epoch=1, holder="supervisor", broker_process=process(),
                           lease_until_ns=100, action_id="action" + str(sequence), journal_sequence=sequence))


def test_journal_hash_chain_detects_reorder_and_freezes_final_event():
    first = e.journal_event(event())
    last = e.journal_event(event(1, c.digest_bytes(c.canonical_json(first)), "seal_intent", "sealing"))
    assert e.validate_journal((first, last)) == ()
    assert e.validate_journal((last, first))
    changed = copy.deepcopy(first)
    changed["state"] = "failed"
    assert e.validate_journal((changed, last))
    with pytest.raises(ValueError):
        e.append_journal((first, last), event(2, c.digest_bytes(c.canonical_json(last))))


def test_terminal_may_not_include_itself_and_paths_cannot_escape():
    t = dict(attempt_id="a" * 32, candidate_sha=c.CANDIDATE_SHA, supervisor_sha256="1" * 64,
             state="failed", **{"pass": False}, new_case_credit=0, manifest_sha256=None,
             journal_sha256="2" * 64, artifacts=[], failure_reasons=["source failed"], residual_resource_keys=[])
    assert e.validate_artifact("terminal.json", c.canonical_json(t), {}) == ()
    for path in ["terminal.json", "seal.json", "../escape", "/etc/passwd"]:
        row = dict(path=path, state="absent", reason="absent", sha256=None, bytes=0)
        assert e.validate_artifact("terminal.json", c.canonical_json({**t, "artifacts": [row]}), {})


def test_seal_write_order_and_raw_digest_vectors():
    port = e.MemoryEvidencePort()
    last = e.journal_event(event(action="seal_intent", state="sealing"))
    journal = (last,)
    port.append_fsync("journal.jsonl", c.canonical_json(last))
    m, terminal = seal_documents(port)
    seal = e.seal_evidence(port, journal, m, terminal, "2026-11-04T00:00:01Z")
    assert list(port.files) == ["journal.jsonl", "manifest.json", "terminal.json", "seal.json"]
    assert seal["manifest_sha256"] == c.digest_bytes(port.files["manifest.json"])
    assert seal["terminal_sha256"] == c.digest_bytes(port.files["terminal.json"])
    assert seal["seal_sha256"] == c.digest({k: v for k, v in seal.items() if k != "seal_sha256"})
    assert port.calls[-1] == ("fsync_parent", "seal.json")
    assert e.validate_artifact("seal.json", port.files["seal.json"], {"files": port.files}) == ()
    with pytest.raises(ValueError):
        e.seal_evidence(port, journal, m, terminal, "later")


def test_failed_fsync_never_creates_successor_artifacts():
    port = e.MemoryEvidencePort(fail_at="manifest.json")
    journal = (e.journal_event(event(action="seal_intent", state="sealing")),)
    port.append_fsync("journal.jsonl", c.canonical_json(journal[0]))
    m, terminal = seal_documents(port)
    with pytest.raises(OSError):
        e.seal_evidence(port, journal, m, terminal, "now")
    assert "terminal.json" not in port.files and "seal.json" not in port.files


def test_journal_rejects_noncanonical_raw_bytes():
    item = e.journal_event(event())
    assert e.validate_artifact("journal.jsonl", (json.dumps(item) + "\n").encode(), {})


def test_sealing_rejects_omitted_failed_log_and_mismatched_identity():
    last = e.journal_event(event(action="seal_intent", state="sealing"))
    for extra_log, terminal_change in ((True, {}), (False, {"attempt_id": "other"}), (False, {"candidate_sha": "0" * 40})):
        port = e.MemoryEvidencePort()
        port.append_fsync("journal.jsonl", c.canonical_json(last))
        m, terminal = seal_documents(port, "failed")
        if extra_log:
            port.write_exclusive("api/pytest.stderr.log", b"failure retained\n")
        with pytest.raises(ValueError):
            e.seal_evidence(port, (last,), m, {**terminal, **terminal_change}, "now")
        assert "seal.json" not in port.files


def test_sealing_rejects_laundered_terminal_file_hash():
    port = e.MemoryEvidencePort()
    last = e.journal_event(event(action="seal_intent", state="sealing"))
    port.append_fsync("journal.jsonl", c.canonical_json(last))
    m, terminal = seal_documents(port)
    terminal["artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        e.seal_evidence(port, (last,), m, terminal, "now")


def migration_rows():
    return [dict(case_id=case["id"], database_resource_key="db:" + case["id"], path=f"migrations/{version:03}.sql",
                 version=version, source_sha256="1" * 64, applied_sha256="1" * 64,
                 state="applied", command_id="source-migration:" + case["id"], reason=None)
            for case in c.inventory()["api_cases"] for version in range(1, 41)]


@pytest.mark.parametrize("mutation", ["39", "41", "duplicate", "checksum", "database", "unknown_case"])
def test_exact_per_case_migrations_cannot_be_reduced_to_one_global_receipt(mutation):
    rows = migration_rows()
    context = dict(lane="api", migration_source_sha256={row["path"]: row["source_sha256"] for row in rows})
    assert e.validate_artifact("migrations.json", c.canonical_json(rows), context) == ()
    if mutation == "39":
        del rows[0]
    elif mutation == "41":
        rows.insert(40, {**rows[39], "version": 41})
    elif mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "checksum":
        rows[0]["applied_sha256"] = "0" * 64
    elif mutation == "database":
        rows[40]["database_resource_key"] = rows[0]["database_resource_key"]
    else:
        rows[0]["case_id"] = "unknown"
    assert e.validate_artifact("migrations.json", c.canonical_json(rows), context)
    assert e.validate_artifact("migrations.json", c.canonical_json(rows), {**context, "lane": "dto"})


def test_worker_integer_exit_lists_cannot_replace_creation_identity():
    worker = dict(case_id="case", worker_ordinal=0, spawn_command_id="spawn", process=process(),
                  log_path="case/worker.log", log_sha256="1" * 64, exit=outcome(), observation="direct", reason=None)
    assert e.validate_value("Worker", worker) == ()
    assert e.validate_value("Worker", {**worker, "process": None})
    assert e.validate_value("Worker", {**worker, "exit": {**outcome(), "state": "running", "end_ns": None, "exit_code": None}})
    assert e.validate_artifact("workers.json", b"[0,0]\n", {})


@pytest.mark.parametrize("field", ["pid", "start_ticks", "labels", "filesystem", "created_at", "inspect_sha256"])
def test_complete_ownership_changes_never_match(field):
    proc = process()
    obj = dict(resource_key="api.runner", generation="api", kind="container", attempt_id="a" * 32,
               candidate_sha=c.CANDIDATE_SHA, supervisor_sha256="1" * 64, name="owned", immutable_id="2" * 64,
               created_at="2026-11-04T00:00:00Z", labels={"autodata.attempt": "a" * 32, "autodata.candidate": c.CANDIDATE_SHA,
               "autodata.supervisor": "1" * 64, "autodata.generation": "api", "autodata.contract": "api21-dto120-v1"},
               inspect_sha256="3" * 64, process=proc, filesystem=None, owner_resource_key=None, status="verified", reason=None)
    assert e.ownership_matches(obj, copy.deepcopy(obj))
    changed = copy.deepcopy(obj)
    if field in ("pid", "start_ticks"):
        changed["process"][field] += 1
    elif field == "labels":
        changed["labels"]["autodata.attempt"] = "b" * 32
    elif field == "filesystem":
        changed["filesystem"] = {}
    else:
        changed[field] = "changed"
    assert not e.ownership_matches(obj, changed)


def test_immutable_before_after_and_raw_stream_caps_are_not_truncation_permissions():
    assert e.validate_artifact("source.after.json", b"[]\n", {"counterpart": [{"different": True}]})
    assert e.validate_artifact("seal.json", b"x" * 65537, {})
