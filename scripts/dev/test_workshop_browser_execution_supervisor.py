"""Fake event replay, broker fencing and bounded lifecycle tests."""
import copy
import dataclasses

import pytest

import workshop_browser_execution_contract as c
import workshop_browser_execution_supervisor as s
from test_workshop_browser_execution_contract import bindings
from test_workshop_browser_execution_evidence import process


def state():
    return s.initial_state(bindings(), 100, broker_process=process(), lease_ns=1000)


def event(event_kind, now=101, **payload):
    return c.Event(event_kind, now, payload)


def ticket(st, action="act"):
    return dict(epoch=st["epoch"], holder=st["holder"], broker_process=st["broker_process"],
                lease_until_ns=st["lease_until_ns"], action_id=action, journal_sequence=st["journal_sequence"])


def request(st, action="act", now=101):
    return event("request", now, ticket=ticket(st, action), kind="create", resource_key="api.net", timeout_ns=50,
                 prerequisite_receipts=["reserved"], command=None)


def test_initial_state_and_unknown_events_are_strict_and_immutable():
    st = state()
    original = copy.deepcopy(st)
    with pytest.raises(ValueError):
        s.reduce(st, event("invented"))
    with pytest.raises(ValueError):
        s.reduce(st, event("heartbeat", ticket=ticket(st), extra=True))
    assert st == original
    assert st["pass"] is False and st["new_case_credit"] == 0


def test_request_requires_durable_intent_before_mutation_and_receipt_before_progress():
    st, actions = s.reduce(state(), request(state()))
    assert [a["kind"] for a in actions] == ["append_fsync"]
    assert st["pending"]["stage"] == "intent_wait"
    assert all(a.get("kind") != "create" for a in actions)
    st, actions = s.reduce(st, event("intent_fsynced", 102, action_id="act", sequence=1, parent_fsynced=True))
    assert [a["kind"] for a in actions] == ["create"]
    assert actions[0]["deadline_ns"] == 151
    assert actions[0]["journal_sequence"] == 1
    st, actions = s.reduce(st, event("action_completed", 103, action_id="act", success=True, observation={"id": "1" * 64}))
    assert st["pending"]["stage"] == "observation_wait"
    assert [a["kind"] for a in actions] == ["append_fsync"]
    st, actions = s.reduce(st, event("observation_fsynced", 104, action_id="act", sequence=2))
    assert st["pending"] is None and "act" in st["completed_actions"]
    replay, actions = s.reduce(st, request(st, now=105))
    assert not actions and replay["completed_actions"] == st["completed_actions"]


def test_fsync_failure_stops_before_create():
    st, _ = s.reduce(state(), request(state()))
    st, actions = s.reduce(st, event("write_failed", 102, reason="disk full"))
    assert st["status"] == "failed"
    assert all(a["kind"] != "create" for a in actions)


def test_missing_prerequisite_blocks_and_unknown_completion_never_retries():
    req = dataclasses.replace(request(state()), payload={**request(state()).payload, "prerequisite_receipts": ["not observed"]})
    st, actions = s.reduce(state(), req)
    assert st["status"] == "recovery_blocked" and not actions
    st, _ = s.reduce(state(), request(state()))
    st, actions = s.reduce(st, event("crash", 102, reason="lost during create"))
    assert st["status"] == "recovery_blocked"
    assert [a["kind"] for a in actions] == ["inspect"]


def test_watchdog_boundary_advances_epoch_durably_before_cleanup():
    st = state()
    assert s.watchdog(st, 1099) == ()
    actions = s.watchdog(st, 1100)
    assert actions[0]["kind"] == "takeover_request"
    st, actions = s.reduce(st, event("takeover", 1100, expected_epoch=1))
    assert st["epoch"] == 1
    assert actions[0]["kind"] == "append_fsync"
    st, actions = s.reduce(st, event("fence_fsynced", 1101, epoch=2, sequence=1))
    assert st["epoch"] == 2 and st["holder"] == "watchdog_cleanup"
    assert st["status"] == "interrupted"
    old = ticket(state())
    req = dataclasses.replace(request(st, now=1102), payload={**request(st, now=1102).payload, "ticket": old})
    st, actions = s.reduce(st, req)
    assert [a["kind"] for a in actions] == ["append_fsync"]
    assert actions[0]["record"]["action"] == "stale_action_rejected"
    assert not any(a["kind"] in ("create", "signal", "remove", "stop") for a in actions)


def test_heartbeat_at_expiry_cannot_revive_and_takeover_is_once():
    st, _ = s.reduce(state(), event("heartbeat", 1100, ticket=ticket(state())))
    assert st["lease_until_ns"] == 1100
    assert st["failure_reasons"]
    st, _ = s.reduce(st, event("takeover", 1100, expected_epoch=1))
    st2, actions = s.reduce(st, event("takeover", 1100, expected_epoch=1))
    assert not actions and st2 == st


def test_two_client_race_and_inflight_takeover_require_reconcile():
    st, _ = s.reduce(state(), request(state()))
    st, actions = s.reduce(st, request(st, "second", 102))
    assert not actions and st["pending"]["action_id"] == "act"
    st, actions = s.reduce(st, event("takeover", 1100, expected_epoch=1))
    st, actions = s.reduce(st, event("fence_fsynced", 1101, epoch=2, sequence=1))
    assert st["status"] == "recovery_blocked"
    assert all(a["kind"] not in ("create", "stop", "signal", "remove") for a in actions)


@pytest.mark.parametrize("kind", ["broker_dead", "broker_lock_lost", "session_lost", "reap_failed", "service_exit"])
def test_failure_events_stop_dispatch_without_laundering(kind):
    st, actions = s.reduce(state(), event(kind, reason=kind))
    assert st["status"] in ("failed", "interrupted", "recovery_blocked")
    assert st["pass"] is False and st["new_case_credit"] == 0
    original_reasons = list(st["failure_reasons"])
    st, _ = s.reduce(st, event("cleanup_finished", 102, residual_resource_keys=[]))
    assert st["failure_reasons"] == original_reasons
    assert st["status"] != "sealed_unreviewed"


@pytest.mark.parametrize("now", [99, 7500000000100])
def test_backward_clock_and_at_deadline_stop(now):
    st, actions = s.reduce(state(), event("tick", now))
    assert st["status"] in ("failed", "interrupted")
    assert all(a["kind"] != "create" for a in actions)


@pytest.mark.parametrize("mutation", ["pid_reused", "label_changed", "volume_mount_changed"])
def test_ambiguous_cleanup_emits_no_mutation(mutation):
    st, actions = s.reduce(state(), event("ownership_observed", expected={}, observed={}, identity_case=mutation))
    assert st["status"] == "recovery_blocked"
    assert all(a["kind"] not in ("signal", "remove", "stop") for a in actions)


def test_success_shaped_api_replay_is_unreviewed_and_dto_remains_blocked():
    st = state()
    now = 101
    for target, receipts in s.TRANSITIONS.items():
        if target == "sealed_unreviewed":
            break
        for receipt in receipts[1]:
            if receipt in st["receipts"]:
                continue
            st, _ = s.reduce(st, event("receipt", now, name=receipt, sha256="a" * 64))
            now += 1
        st, _ = s.reduce(st, event("advance", now, target=target))
        now += 1
        assert st["status"] == target
    st, _ = s.reduce(st, event("receipt", now, name="seal_written", sha256="b" * 64))
    st, _ = s.reduce(st, event("advance", now + 1, target="sealed_unreviewed"))
    assert st["status"] == "sealed_unreviewed" and not st["pass"]
    assert st["new_case_credit"] == 0
    st, _ = s.reduce(st, event("dto_requested", now + 2))
    assert "blocked_timer_dependency" in st["blockers"]
    assert st["cases"]["dto"] == {row["id"]: "not_started" for row in c.inventory()["dto_cases"]}


def test_forbidden_transition_and_missing_receipt_fail_closed():
    st, actions = s.reduce(state(), event("advance", target="api_running"))
    assert st["status"] == "recovery_blocked" and not actions
    st, _ = s.reduce(state(), event("advance", target="preparing"))
    st, _ = s.reduce(st, event("advance", 102, target="services_starting"))
    assert st["status"] == "recovery_blocked"


def test_failure_preserves_logs_missing_maps_and_previous_state():
    st = state()
    st, _ = s.reduce(st, event("artifact", path="api/pytest.stdout.log", data=b"raw failure\n"))
    previous = copy.deepcopy(st)
    next_state, _ = s.reduce(st, event("source_failed", 102, reason="case failed"))
    next_state, _ = s.reduce(next_state, event("cleanup_finished", 103, residual_resource_keys=[]))
    assert st == previous
    assert next_state["artifacts"]["api/pytest.stdout.log"]["sha256"] == c.digest_bytes(b"raw failure\n")
    assert next_state["status"] == "failed"
    assert any(row["state"] == "not_started" for row in s.missing_map(next_state))


def test_live_cli_rejects_before_opening_anything(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("live rejection attempted I/O")
    monkeypatch.setattr("builtins.open", forbidden)
    for mode in ("execute", "probe-execute", "cleanup-live", "recover-live", "execute-runner"):
        with pytest.raises(c.LiveAdapterNotAdmitted):
            s.main([mode, "--bindings", "/missing"])


def test_reconcile_never_retries_unknown_create():
    assert s.reconcile((), ({"name": "unowned"},))["status"] == "recovery_blocked"


@pytest.mark.parametrize("failure", ["broker_dead", "broker_lock_lost"])
def test_delayed_intent_ack_after_broker_failure_cannot_mutate(failure):
    st, _ = s.reduce(state(), request(state()))
    st, _ = s.reduce(st, event(failure, 102, reason="broker unavailable"))
    st, actions = s.reduce(st, event("intent_fsynced", 103, action_id="act", sequence=1, parent_fsynced=True))
    assert st["status"] == "recovery_blocked"
    assert not any(a["kind"] in ("create", "signal", "stop", "remove") for a in actions)


@pytest.mark.parametrize("failure", ["write_failed", "session_lost", "signal", "service_exit"])
def test_cancelled_supervisor_intent_cannot_dispatch_after_delayed_fsync(failure):
    st, _ = s.reduce(state(), request(state()))
    st, _ = s.reduce(st, event(failure, 102, reason="cancelled: " + failure))
    cancelled_reasons = list(st["failure_reasons"])
    st, actions = s.reduce(st, event("intent_fsynced", 103, action_id="act", sequence=1, parent_fsynced=True))
    assert st["status"] in s.NONPASS
    assert not any(a["kind"] in ("create", "start", "signal", "stop", "remove", "reap") for a in actions)
    assert st["failure_reasons"][:len(cancelled_reasons)] == cancelled_reasons
    assert st["pending"]["stage"] != "executing"


def test_delayed_intent_ack_after_fence_cannot_use_new_watchdog_lease():
    st, _ = s.reduce(state(), request(state()))
    st, _ = s.reduce(st, event("takeover", 1100, expected_epoch=1))
    st, _ = s.reduce(st, event("fence_fsynced", 1101, epoch=2, sequence=1))
    st, actions = s.reduce(st, event("intent_fsynced", 1102, action_id="act", sequence=2, parent_fsynced=True))
    assert not any(a["kind"] == "create" for a in actions)
    assert st["status"] == "recovery_blocked"


def test_action_completion_at_its_deadline_is_uncertain_and_never_claims_success():
    st, _ = s.reduce(state(), request(state()))
    st, _ = s.reduce(st, event("intent_fsynced", 102, action_id="act", sequence=1, parent_fsynced=True))
    st, actions = s.reduce(st, event("action_completed", 151, action_id="act", success=True, observation={"id": "1" * 64}))
    assert st["status"] == "recovery_blocked"
    assert "act" not in st["completed_actions"]
    assert all(a["kind"] not in ("create", "remove", "signal", "stop") for a in actions)


def test_cleanup_phases_share_one_deadline_and_never_reset_it():
    st = state()
    st.update(status="api_running", receipts={"producer_exited": "x", "owned_stop_complete": "y", "all_children_reaped": "z", "all_logs_flushed": "f", "inventory_accounted": "i"})
    st, _ = s.reduce(st, event("advance", 101, target="stopping"))
    deadline = st["phase_deadline_ns"]
    st, _ = s.reduce(st, event("advance", 102, target="reaping"))
    assert st["phase_deadline_ns"] == deadline
    st, _ = s.reduce(st, event("advance", 103, target="sealing"))
    assert st["phase_deadline_ns"] == deadline


def test_sealed_state_cannot_emit_new_mutation_or_be_changed_by_late_case():
    st = state()
    st["status"] = "sealed_unreviewed"
    unchanged, actions = s.reduce(st, request(st))
    assert not actions and unchanged["pending"] is None
    with pytest.raises(ValueError):
        s.reduce(st, event("case_result", lane="api", case_id=next(iter(st["cases"]["api"])), result="exited"))


def test_stop_reap_failures_cannot_clear_original_failure_and_artifact_caps_preserve_hash():
    st, _ = s.reduce(state(), event("source_failed", reason="original"))
    st, _ = s.reduce(st, event("reap_failed", 102, reason="unreaped child"))
    st, _ = s.reduce(st, event("cleanup_finished", 103, residual_resource_keys=["api.runner"]))
    assert st["failure_reasons"][0] == "original"
    assert st["status"] == "recovery_blocked"
    raw = b"x" * 33554433
    st, _ = s.reduce(state(), event("artifact", path="api/pytest.stdout.log", data=raw))
    assert st["artifacts"]["api/pytest.stdout.log"]["bytes"] == len(raw)
    assert st["artifacts"]["api/pytest.stdout.log"]["sha256"] == c.digest_bytes(raw)
    assert st["status"] == "failed"


def test_replay_cannot_write_to_candidate_or_cache_even_as_fresh_output(tmp_path):
    binding_path = tmp_path / "bindings.json"
    binding_path.write_bytes(c.canonical_json(dataclasses.asdict(bindings())))
    events = tmp_path / "events.json"
    events.write_bytes(b"[]\n")
    observations = tmp_path / "observations.json"
    observations.write_bytes(c.canonical_json(dict(start_ns=1)))
    for output in (bindings().source_root + "/new.json", bindings().module_cache_root + "/new.json"):
        with pytest.raises(ValueError):
            s.main(["replay", "--bindings", str(binding_path), "--events", str(events), "--observations", str(observations), "--output", output])


def test_offline_render_writes_fresh_external_file_and_rejects_symlink_parent(tmp_path):
    binding_path = tmp_path / "bindings.json"
    binding_path.write_bytes(c.canonical_json(dataclasses.asdict(bindings())))
    outdir = tmp_path / "out"
    outdir.mkdir()
    output = outdir / "render.json"
    assert s.main(["render", "--bindings", str(binding_path), "--output", str(output)]) == 0
    result = c.strict_json(output.read_bytes())
    assert result["status"] == "unadmitted" and result["pass"] is False
    with pytest.raises(FileExistsError):
        s.main(["render", "--bindings", str(binding_path), "--output", str(output)])
    linked = tmp_path / "linked"
    linked.symlink_to(outdir)
    with pytest.raises(ValueError):
        s.main(["render", "--bindings", str(binding_path), "--output", str(linked / "new.json")])
