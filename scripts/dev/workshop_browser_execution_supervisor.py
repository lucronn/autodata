"""Pure broker/supervisor/watchdog reduction and offline tooling.

Actions describe work for a future independently admitted broker. No action in
this module calls an OS process, Docker, socket, signal or provider adapter.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import stat
import sys

import workshop_browser_execution_contract as c
import workshop_browser_execution_evidence as evidence


ATTEMPT_NS = 7500 * 1000000000
PHASE_NS = {"reserved": 480, "preparing": 180, "services_starting": 120, "ready": 120,
            "api_running": 2100, "dto_running": 4560, "stopping": 120, "reaping": 120, "sealing": 120}
TRANSITIONS = {
    "preparing": (("reserved",), ("reserved",)),
    "services_starting": (("preparing",), ("preparation_complete", "runtime_binding_observed")),
    "ready": (("services_starting",), ("runner_started", "postgres_ready", "nats_ready", "s3_ready")),
    "api_running": (("ready",), ("api_producer_started",)),
    "stopping": (("api_running", "dto_running"), ("producer_exited",)),
    "reaping": (("stopping",), ("owned_stop_complete",)),
    "sealing": (("reaping",), ("all_children_reaped", "all_logs_flushed", "inventory_accounted")),
    "sealed_unreviewed": (("sealing",), ("seal_written",)),
}
FAILURE_EVENTS = {"broker_dead": "recovery_blocked", "broker_lock_lost": "recovery_blocked",
                  "session_lost": "interrupted", "reap_failed": "recovery_blocked",
                  "service_exit": "failed", "write_failed": "failed", "source_failed": "failed",
                  "signal": "interrupted"}
NONPASS = {"failed", "interrupted", "recovery_blocked"}
LIVE_MODES = {"execute", "probe-execute", "cleanup-live", "recover-live", "execute-runner", "broker-live", "watchdog-live"}


def initial_state(bindings: c.RuntimeBindings, now_ns: int, *, broker_process=None, lease_ns=1000000000) -> dict:
    c.validate_bindings(bindings)
    if type(now_ns) is not int or now_ns < 0 or type(lease_ns) is not int or lease_ns <= 0:
        raise ValueError("invalid monotonic clock or lease")
    if broker_process is not None and evidence.validate_value("Process", broker_process):
        raise ValueError("invalid broker process identity")
    inv = c.inventory()
    return dict(status="reserved", mode="offline_replay", attempt_id=bindings.attempt_id,
                candidate_sha=bindings.candidate_sha, supervisor_sha256=bindings.supervisor_sha256,
                start_ns=now_ns, now_ns=now_ns, deadline_ns=now_ns + ATTEMPT_NS,
                phase_deadline_ns=now_ns + PHASE_NS["reserved"] * 1000000000,
                epoch=1, holder="supervisor", broker_process=copy.deepcopy(broker_process), broker_alive=True,
                lock_held=True, lease_ns=lease_ns, lease_until_ns=now_ns + lease_ns,
                journal_sequence=0, fence_pending=None, pending=None, completed_actions=[],
                receipts={"reserved": "offline_reserved"}, resources={}, artifacts={}, residual_resource_keys=[],
                cases={"api": {row["id"]: "not_started" for row in inv["api_cases"]},
                       "dto": {row["id"]: "not_started" for row in inv["dto_cases"]}},
                blockers=list(sorted(set(c.graph_blockers(bindings, "api") + c.graph_blockers(bindings, "dto")))),
                failure_reasons=[], **{"pass": False}, new_case_credit=0)


def _fail(state, status, reason):
    # A cleanup acknowledgement never upgrades a previous failure to success.
    # A durable intent acknowledgement arriving after cancellation is only an
    # observation. It must never revive the cancelled external action.
    if state["pending"] is not None and state["pending"]["stage"] == "intent_wait":
        state["pending"]["stage"] = "cancelled"
    if state["status"] not in NONPASS:
        state["phase_deadline_ns"] = min(state["deadline_ns"], state["now_ns"] + 120000000000)
    if state["status"] != "recovery_blocked" or status == "recovery_blocked":
        state["status"] = status
    if reason not in state["failure_reasons"]:
        state["failure_reasons"].append(reason)
    state["pass"], state["new_case_credit"] = False, 0


def _action(state, kind, action_id, resource_key=None, **extra):
    return dict(kind=kind, action_id=action_id, resource_key=resource_key,
                journal_sequence=state["journal_sequence"], epoch=state["epoch"], holder=state["holder"],
                deadline_ns=min(state["phase_deadline_ns"], state["deadline_ns"]), **extra)


def _journal_action(state, name, action_id, resource_key=None):
    return _action(state, "append_fsync", action_id, resource_key,
                   record=dict(action=name, state=state["status"], epoch=state["epoch"], holder=state["holder"],
                               sequence=state["journal_sequence"] + 1, monotonic_ns=state["now_ns"]))


def _payload(event, required=(), optional=()):
    if not isinstance(event.payload, dict) or not set(required) <= set(event.payload) or set(event.payload) - set(required) - set(optional):
        raise ValueError("unknown/missing event payload field: " + event.kind)
    return event.payload


def _ticket_valid(state, ticket):
    if evidence.validate_value("FenceTicket", ticket):
        return False
    return (ticket["epoch"] == state["epoch"] and ticket["holder"] == state["holder"]
            and ticket["broker_process"] == state["broker_process"] and ticket["broker_process"] is not None
            and ticket["lease_until_ns"] == state["lease_until_ns"] and ticket["journal_sequence"] == state["journal_sequence"])


def _cleanup_actions(state):
    # Request read-only reconciliation first. No mutation without a fresh exact
    # ownership observation and separately persisted mutation intent.
    if not state["broker_alive"] or not state["lock_held"]:
        return ()
    return tuple(_action(state, "inspect", "cleanup-inspect:" + key, key) for key in sorted(state["resources"]))


def reduce(state: dict, event: c.Event) -> tuple[dict, tuple[dict, ...]]:
    if not isinstance(event, c.Event) or type(event.monotonic_ns) is not int or event.monotonic_ns < 0:
        raise ValueError("typed event with integer monotonic time required")
    next_state = copy.deepcopy(state)
    if event.monotonic_ns < state["now_ns"]:
        _fail(next_state, "failed", "backward_monotonic_clock")
        return next_state, ()
    next_state["now_ns"] = event.monotonic_ns
    if state["status"] == "sealed_unreviewed" and event.kind not in ("dto_requested", "tick", "request"):
        raise ValueError("sealed replay cannot be rewritten")
    if state["status"] == "sealed_unreviewed" and event.kind == "request":
        return next_state, ()
    if event.monotonic_ns >= min(state["deadline_ns"], state["phase_deadline_ns"]) and event.kind not in ("cleanup_finished", "broker_dead", "broker_lock_lost", "takeover", "fence_fsynced"):
        _fail(next_state, "interrupted", "absolute_deadline_reached")
        return next_state, _cleanup_actions(next_state)
    p = event.payload
    actions = ()
    if event.kind in FAILURE_EVENTS:
        p = _payload(event, ("reason",))
        if not isinstance(p["reason"], str) or not p["reason"]:
            raise ValueError("failure requires reason")
        _fail(next_state, FAILURE_EVENTS[event.kind], p["reason"])
        if event.kind.startswith("broker_"):
            next_state["broker_alive"] = False
            next_state["lock_held"] = False
        else:
            actions = _cleanup_actions(next_state)
    elif event.kind == "tick":
        _payload(event)
    elif event.kind == "heartbeat":
        p = _payload(event, ("ticket",))
        if (_ticket_valid(state, p["ticket"]) and state["holder"] == "supervisor" and event.monotonic_ns < state["lease_until_ns"]
                and state["broker_alive"] and state["lock_held"] and state["status"] not in NONPASS):
            next_state["lease_until_ns"] = min(state["deadline_ns"], event.monotonic_ns + state["lease_ns"])
        else:
            if "expired_or_stale_heartbeat" not in next_state["failure_reasons"]:
                next_state["failure_reasons"].append("expired_or_stale_heartbeat")
    elif event.kind == "takeover":
        p = _payload(event, ("expected_epoch",))
        if not state["broker_alive"] or not state["lock_held"]:
            _fail(next_state, "recovery_blocked", "broker_unavailable_no_client_fallback")
        elif (state["holder"] == "supervisor" and p["expected_epoch"] == state["epoch"]
              and event.monotonic_ns >= state["lease_until_ns"] and state["fence_pending"] is None):
            next_state["fence_pending"] = state["epoch"] + 1
            actions = (_journal_action(next_state, "fence_advance", "fence:" + str(state["epoch"] + 1)),)
    elif event.kind == "fence_fsynced":
        p = _payload(event, ("epoch", "sequence"))
        if p["epoch"] != state["fence_pending"] or p["sequence"] != state["journal_sequence"] + 1:
            _fail(next_state, "recovery_blocked", "fence_fsync_receipt_mismatch")
        else:
            next_state.update(epoch=p["epoch"], holder="watchdog_cleanup", fence_pending=None, journal_sequence=p["sequence"])
            next_state["lease_until_ns"] = min(state["deadline_ns"], event.monotonic_ns + 120000000000)
            if state["pending"]:
                _fail(next_state, "recovery_blocked", "inflight_completion_uncertain_reconcile_required")
                actions = (_action(next_state, "inspect", "reconcile:" + state["pending"]["action_id"], state["pending"]["resource_key"]),)
            else:
                _fail(next_state, "interrupted", "supervisor_lease_expired")
                actions = _cleanup_actions(next_state)
    elif event.kind == "request":
        p = _payload(event, ("ticket", "kind", "resource_key", "timeout_ns", "prerequisite_receipts", "command"))
        if p["kind"] not in ("create", "start", "stop", "signal", "remove", "reap", "inspect"):
            raise ValueError("unknown broker action kind")
        if type(p["timeout_ns"]) is not int or not 0 < p["timeout_ns"] <= 10000000000:
            raise ValueError("broker action bound invalid")
        if not _ticket_valid(state, p["ticket"]) or event.monotonic_ns >= state["lease_until_ns"]:
            actions = (_journal_action(next_state, "stale_action_rejected", p["ticket"].get("action_id", "invalid-ticket"), p["resource_key"]),)
        elif not state["broker_alive"] or not state["lock_held"]:
            _fail(next_state, "recovery_blocked", "broker_unavailable_no_client_fallback")
        elif p["ticket"]["action_id"] in state["completed_actions"]:
            pass
        elif state["pending"] is not None or state["fence_pending"] is not None:
            pass  # One live mutation, including its durability receipts, at a time.
        elif state["status"] in NONPASS and not (state["holder"] == "watchdog_cleanup" and p["kind"] in ("stop", "signal", "remove", "reap", "inspect")):
            pass
        elif any(name not in state["receipts"] for name in p["prerequisite_receipts"]):
            _fail(next_state, "recovery_blocked", "missing_prerequisite_receipt")
        elif p["kind"] in ("stop", "signal", "remove", "reap", "start") and p["resource_key"] not in state["resources"]:
            _fail(next_state, "recovery_blocked", "missing_complete_ownership_identity")
        else:
            if p["command"] is not None and evidence.validate_value("Command", p["command"]):
                raise ValueError("invalid bound command")
            pending = copy.deepcopy(p)
            pending.update(action_id=p["ticket"]["action_id"], stage="intent_wait",
                           deadline_ns=min(event.monotonic_ns + p["timeout_ns"], state["phase_deadline_ns"], state["deadline_ns"]))
            next_state["pending"] = pending
            actions = (_journal_action(next_state, "intent", pending["action_id"], p["resource_key"]),)
    elif event.kind == "intent_fsynced":
        p = _payload(event, ("action_id", "sequence", "parent_fsynced"))
        pending = state["pending"]
        if not state["broker_alive"] or not state["lock_held"]:
            _fail(next_state, "recovery_blocked", "broker_unavailable_before_mutation")
        elif (pending is None or pending["stage"] != "intent_wait" or pending["action_id"] != p["action_id"]
                or p["sequence"] != state["journal_sequence"] + 1 or p["parent_fsynced"] is not True):
            _fail(next_state, "recovery_blocked", "intent_fsync_receipt_mismatch")
        elif (pending["ticket"]["epoch"] != state["epoch"] or pending["ticket"]["holder"] != state["holder"]
              or pending["ticket"]["broker_process"] != state["broker_process"] or state["status"] == "recovery_blocked"
              or (state["status"] in NONPASS and (state["holder"] != "watchdog_cleanup"
                  or pending["kind"] not in ("stop", "signal", "remove", "reap", "inspect")))):
            _fail(next_state, "recovery_blocked", "revoked_intent_cannot_mutate")
        elif event.monotonic_ns >= min(pending["deadline_ns"], state["lease_until_ns"]) or state["fence_pending"] is not None:
            _fail(next_state, "recovery_blocked", "intent_expired_before_mutation")
        else:
            next_state["journal_sequence"] = p["sequence"]
            next_state["pending"]["stage"] = "executing"
            action = _action(next_state, pending["kind"], pending["action_id"], pending["resource_key"], command=pending["command"])
            action["deadline_ns"] = pending["deadline_ns"]
            actions = (action,)
    elif event.kind == "action_completed":
        p = _payload(event, ("action_id", "success", "observation"))
        pending = state["pending"]
        if pending is None or pending["stage"] != "executing" or pending["action_id"] != p["action_id"]:
            _fail(next_state, "recovery_blocked", "unknown_action_completion")
        elif (event.monotonic_ns >= pending["deadline_ns"] or not state["broker_alive"] or not state["lock_held"]
              or pending["ticket"]["epoch"] != state["epoch"]):
            _fail(next_state, "recovery_blocked", "late_or_revoked_action_requires_reconcile")
            if state["broker_alive"] and state["lock_held"]:
                actions = (_action(next_state, "inspect", "reconcile:" + p["action_id"], pending["resource_key"]),)
        elif p["success"] is not True:
            _fail(next_state, "failed", "adapter_action_failed")
        else:
            next_state["pending"].update(stage="observation_wait", observation=copy.deepcopy(p["observation"]))
            actions = (_journal_action(next_state, "created" if pending["kind"] == "create" else "observed", p["action_id"], pending["resource_key"]),)
    elif event.kind == "observation_fsynced":
        p = _payload(event, ("action_id", "sequence"))
        pending = state["pending"]
        if pending is None or pending["stage"] != "observation_wait" or pending["action_id"] != p["action_id"] or p["sequence"] != state["journal_sequence"] + 1:
            _fail(next_state, "recovery_blocked", "observation_fsync_receipt_mismatch")
        else:
            next_state["journal_sequence"] = p["sequence"]
            next_state["completed_actions"].append(p["action_id"])
            next_state["receipts"][p["action_id"]] = c.digest(pending["observation"])
            next_state["pending"] = None
    elif event.kind == "ownership_observed":
        p = _payload(event, ("expected", "observed"), ("identity_case",))
        if not evidence.ownership_matches(p["expected"], p["observed"]):
            _fail(next_state, "recovery_blocked", "ambiguous_resource_identity")
        else:
            next_state["resources"][p["expected"]["resource_key"]] = copy.deepcopy(p["observed"])
    elif event.kind == "crash":
        p = _payload(event, ("reason",))
        _fail(next_state, "recovery_blocked", p["reason"])
        if state["pending"]:
            actions = (_action(next_state, "inspect", "reconcile:" + state["pending"]["action_id"], state["pending"]["resource_key"]),)
    elif event.kind == "receipt":
        p = _payload(event, ("name", "sha256"))
        c.hex_value(p["sha256"], 64)
        if p["name"] in state["receipts"] and state["receipts"][p["name"]] != p["sha256"]:
            _fail(next_state, "recovery_blocked", "receipt_rewritten")
        else:
            next_state["receipts"][p["name"]] = p["sha256"]
    elif event.kind == "advance":
        p = _payload(event, ("target",))
        target = p["target"]
        if target not in TRANSITIONS:
            raise ValueError("unknown lifecycle state")
        sources, required = TRANSITIONS[target]
        if state["status"] not in sources or any(name not in state["receipts"] for name in required) or state["pending"]:
            _fail(next_state, "recovery_blocked", "forbidden_transition_or_missing_receipt")
        else:
            next_state["status"] = target
            if target in PHASE_NS:
                if target in ("reaping", "sealing"):
                    next_state["phase_deadline_ns"] = state["phase_deadline_ns"]
                else:
                    next_state["phase_deadline_ns"] = min(state["deadline_ns"], event.monotonic_ns + PHASE_NS[target] * 1000000000)
    elif event.kind == "dto_requested":
        _payload(event)
        # Static success-shaped API replay confers no timer/runtime admission.
        if "blocked_timer_dependency" not in next_state["blockers"]:
            next_state["blockers"].append("blocked_timer_dependency")
            next_state["blockers"].sort()
    elif event.kind == "cleanup_finished":
        p = _payload(event, ("residual_resource_keys",))
        next_state["residual_resource_keys"] = list(p["residual_resource_keys"])
        if p["residual_resource_keys"]:
            _fail(next_state, "recovery_blocked", "residual_owned_resources")
    elif event.kind == "artifact":
        p = _payload(event, ("path", "data"))
        c.relative_path(p["path"])
        if not isinstance(p["data"], bytes):
            raise ValueError("artifact event requires retained raw bytes")
        if p["path"] in state["artifacts"]:
            _fail(next_state, "failed", "artifact_overwrite_rejected")
        else:
            next_state["artifacts"][p["path"]] = dict(path=p["path"], state="produced", reason=None,
                                                     sha256=c.digest_bytes(p["data"]), bytes=len(p["data"]))
            if len(p["data"]) > 33554432:
                next_state["artifacts"][p["path"]].update(state="partial", reason="raw_stream_cap_exceeded_preserved_in_quarantine")
                _fail(next_state, "failed", "raw_stream_cap_exceeded")
    elif event.kind == "case_result":
        p = _payload(event, ("lane", "case_id", "result"))
        if p["lane"] not in next_state["cases"] or p["case_id"] not in next_state["cases"][p["lane"]] or p["result"] not in ("exited", "failed", "interrupted"):
            raise ValueError("case outside exact inventory/result vocabulary")
        if state["cases"][p["lane"]][p["case_id"]] != "not_started":
            _fail(next_state, "failed", "duplicate_case_result")
        else:
            next_state["cases"][p["lane"]][p["case_id"]] = p["result"]
            if p["result"] != "exited":
                _fail(next_state, "failed", "source_case_nonpass:" + p["case_id"])
    else:
        raise ValueError("unknown event kind: " + event.kind)
    next_state["pass"], next_state["new_case_credit"] = False, 0
    return next_state, actions


def watchdog(state: dict, now_ns: int) -> tuple[dict, ...]:
    if type(now_ns) is not int or now_ns < state["now_ns"]:
        raise ValueError("watchdog monotonic clock regressed")
    if not state["broker_alive"] or not state["lock_held"]:
        return (_action(state, "external_failure_receipt", "broker-unavailable", reason="recovery_blocked"),)
    if state["status"] == "sealed_unreviewed" or state["holder"] != "supervisor" or state["fence_pending"]:
        return ()
    if now_ns >= min(state["lease_until_ns"], state["phase_deadline_ns"], state["deadline_ns"]):
        return (_action(state, "takeover_request", "takeover:" + str(state["epoch"]), expected_epoch=state["epoch"]),)
    return ()


def missing_map(state: dict) -> list[dict]:
    expected = evidence.required_artifacts() - {"terminal.json", "seal.json"}
    expected.update(state["artifacts"])
    result = []
    for path in sorted(expected):
        result.append(copy.deepcopy(state["artifacts"].get(path, dict(path=path, state="not_started", reason="not produced in offline replay", sha256=None, bytes=0))))
    return result


def reconcile(journal: tuple[dict, ...], observed_resources: tuple[dict, ...]) -> dict:
    errors = list(evidence.validate_journal(journal))
    if observed_resources:
        # Journal intent alone cannot reconstruct a full immutable ownership
        # tuple. No recovery execution or guessed creation replay is supplied.
        errors.append("full_resource_intents_and_direct_identity_reconciliation_required")
    return dict(status="recovery_blocked" if errors or not journal else "sealed_unreviewed",
                reasons=errors or (["empty_journal"] if not journal else []), actions=[], **{"pass": False}, new_case_credit=0)


def _read_offline_bundle(root: Path) -> tuple[dict, list[str]]:
    """Bounded, read-only collection for the offline validator, with no links."""
    files, errors = {}, []
    pending = [root]
    entries, total = 0, 0
    if root.is_symlink() or not root.is_dir():
        return {}, ["attempt root must be an existing nonlinked directory"]
    while pending:
        directory = pending.pop()
        for entry in sorted(directory.iterdir()):
            entries += 1
            if entries > 10000:
                return files, errors + ["evidence entry limit exceeded"]
            name = entry.relative_to(root).as_posix()
            metadata = entry.lstat()
            if stat.S_ISDIR(metadata.st_mode):
                if evidence.known_artifact_directory(name):
                    pending.append(entry)
                else:
                    errors.append("unknown evidence directory: " + name)
            elif not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                errors.append("nonregular or linked evidence entry: " + name)
            elif not evidence.known_artifact(name):
                errors.append("unknown evidence artifact: " + name)
            elif metadata.st_size > 33554432 or total + metadata.st_size > 1073741824:
                errors.append("evidence byte limit exceeded: " + name)
            else:
                with entry.open("rb") as stream:
                    raw = stream.read(min(metadata.st_size + 1, 33554433))
                after = entry.lstat()
                identity = lambda observed: (observed.st_dev, observed.st_ino, observed.st_mode, observed.st_nlink, observed.st_size, observed.st_mtime_ns)
                if identity(metadata) != identity(after) or len(raw) != metadata.st_size:
                    errors.append("evidence changed while read: " + name)
                else:
                    files[name] = raw
                    total += len(raw)
    return files, errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in LIVE_MODES:
        raise c.LiveAdapterNotAdmitted("concrete process/Docker/network adapter not admitted")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("render", "validate", "replay"))
    parser.add_argument("--bindings")
    parser.add_argument("--lane", choices=("api", "dto"), default="api")
    parser.add_argument("--attempt-root")
    parser.add_argument("--events")
    parser.add_argument("--observations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if not args.bindings:
        raise ValueError("offline output protection requires --bindings")
    bindings = c.parse_bindings(Path(c.absolute_path(args.bindings)).read_bytes())
    protected = (bindings.source_root, bindings.tools_root, bindings.module_cache_root, bindings.browser_cache_root)
    if args.mode == "validate":
        protected += (c.absolute_path(args.attempt_root),)
    output = c.offline_output(args.output, protected)
    if args.mode == "render":
        result = dict(status="unadmitted", operations=[c.operation_dict(op) for op in c.compile_graph(bindings, args.lane)],
                      blockers=c.graph_blockers(bindings, args.lane), **{"pass": False}, new_case_credit=0)
    elif args.mode == "validate":
        root = Path(c.absolute_path(args.attempt_root))
        files, errors = _read_offline_bundle(root)
        if "seal.json" in files:
            errors.extend(evidence.validate_artifact("seal.json", files["seal.json"], {"files": files}))
        else:
            errors.append("seal.json missing; incomplete evidence bundle")
            errors.extend(evidence.validate_bundle(files))
        result = dict(status="unadmitted", errors=errors, **{"pass": False}, new_case_credit=0)
    else:
        events = c.strict_json(Path(c.absolute_path(args.events)).read_bytes())
        observations = c.strict_json(Path(c.absolute_path(args.observations)).read_bytes())
        result = initial_state(bindings, observations["start_ns"], broker_process=observations.get("broker_process"))
        for item in events:
            if set(item) != {"kind", "monotonic_ns", "payload"}:
                raise ValueError("unknown replay event fields")
            result, _ = reduce(result, c.Event(**item))
    with output.open("xb") as stream:
        stream.write(c.canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
