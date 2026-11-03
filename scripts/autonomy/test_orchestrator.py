import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner as r
import orchestrator as o
from test_runner import PROFILE, SHA

REPO_ROOT = Path(__file__).resolve().parents[2]


class EvidenceAggregationTests(unittest.TestCase):
    def test_summary_only_gate_cannot_receive_candidate_sha(self):
        reports = o.aggregate_gate_reports(
            "run", SHA, {"security": {"decision": "pass"}}
        )
        self.assertEqual(reports["security"]["decision"], "blocked")
        self.assertIsNone(reports["security"]["implementation_sha"])
        self.assertEqual(reports["source_provenance"]["decision"], "blocked")

    def test_coverage_reopens_files_and_nonempty_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = r._save_artifact(b"one", root, "one", "test-result", SHA, None)
            p = {"ratio": 0.5, "eligible_count": 2, "covered_count": 1}
            measured = o.calculate_coverage({"one", "two"}, [a], p, root)
            self.assertEqual(measured["evidence_completeness"], 0.5)
            self.assertEqual(measured["evidence"]["missing_ids"], ["two"])
            (root / a["ref"]).write_bytes(b"tampered")
            self.assertEqual(
                o.calculate_coverage({"one"}, [a], p, root)["evidence_completeness"], 0
            )
            self.assertTrue(
                o.calculate_coverage(set(), [a], p, root)["evidence"]["errors"]
            )
            self.assertTrue(
                o.calculate_coverage({"one"}, [a, a], p, root)["evidence"]["errors"]
            )

    def test_configuration_blocks_before_provider_or_output_creation(self):
        with tempfile.TemporaryDirectory() as d, patch(
            "orchestrator.run_agent"
        ) as provider:
            root = Path(d) / "run"
            with self.assertRaises(r.RunnerError):
                o.orchestrate_task(
                    REPO_ROOT, {"task_id": "legacy"}, "local-cli", root, 1
                )
            provider.assert_not_called()
            self.assertFalse(root.exists())

    def test_agent_usable_reads_runner_state_and_blocking_medium(self):
        self.assertFalse(
            o._agent_usable(
                {"response": {"decision": "pass"}, "decision": "blocked"}, False, SHA
            )
        )
        self.assertFalse(
            o._agent_usable(
                {
                    "decision": "pass",
                    "findings": [{"severity": "medium", "blocking": True}],
                },
                False,
                SHA,
            )
        )

    def test_bundle_rejects_fabricated_legacy_metrics_and_missing_required_slots(self):
        trusted = {
            "trusted_base_sha": SHA,
            "task": {
                "task_id": "t",
                "execution": PROFILE,
                "verification": {
                    "checks": [],
                    "required_agent_evidence": [],
                    "provenance": {
                        "check_id": "source-fixture",
                        "population_ref": "fixture/population.json",
                        "report_artifact_id": "source",
                    },
                },
            },
            "policy": json.loads(
                (REPO_ROOT / ".autodata-autonomy-policy.json").read_text()
            ),
            "artifacts": {},
            "population": {
                "population_id": "x",
                "scope": "synthetic-regression",
                "records": [],
            },
            "provenance_inputs": {},
        }
        with tempfile.TemporaryDirectory() as d:
            result = o.validate_evidence_bundle(
                {
                    "evidence_completeness": 1.0,
                    "fast_lane_provenance_coverage": 1.0,
                    "implementation_sha": SHA,
                },
                trusted,
                Path(d),
            )
            self.assertFalse(result["passed"])
            self.assertTrue(result["failures"])


class FullChainV2Tests(unittest.TestCase):
    def run_fixture(
        self, directory, fail_check=False, unavailable=False, malformed=False
    ):
        from test_runner import make_trusted_repository

        root = directory / "repo"
        root.mkdir()
        task, base = make_trusted_repository(root)
        trusted = r.load_trusted_inputs(root, base, task["task_ref"])
        original = r.bounded_process
        if fail_check:
            # Commit a failed command as a frozen requirement, never modify it after trust resolution.
            task["verification"]["checks"][0]["argv"] = [
                "python3",
                "-c",
                "raise SystemExit(7)",
            ]
            (root / task["task_ref"]).write_text(json.dumps(task))
            import subprocess

            subprocess.run(
                ["git", "add", "."], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "failed fixture requirement"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            base = r._run_git(root, ["rev-parse", "HEAD"]).strip()
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
        from test_app_server_adapter import fake_codex, boundary
        from unittest.mock import patch
        import app_server_adapter as adapter
        bindir=fake_codex(directory)
        output=directory/"bundle"
        mode="unavailable-security" if unavailable else "malformed" if malformed else "success"
        with patch.dict(os.environ, {"PATH":str(bindir)+os.pathsep+os.environ["PATH"], "CODEX_HOME":"/tmp/codex-disposable", "FAKE_CODEX_MODE":mode}), patch.object(adapter,"validate_boundary",side_effect=lambda path, cwd, env: boundary(cwd)):
            code,path=o.orchestrate_task(root,task,"local-cli",output,6)
        envelopes=[json.loads(p.read_text()) for p in sorted(output.glob("agents/*/task-envelope.json"))]
        return code,path,trusted,envelopes

    def test_real_checks_fake_provider_complete_bundle_and_replay_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, envelopes = self.run_fixture(Path(d))
            final = json.loads(path.read_text())
            self.assertEqual(code, 0, (path.parent / "decision.json").read_text())
            self.assertEqual(len(envelopes), 10)
            self.assertEqual(
                final["agent_runs"]["architect"]["provider_command"]["exit_code"], 0
            )
            self.assertTrue(
                any(
                    a["artifact_id"] == "architect:invocation"
                    for a in final["artifacts"]
                )
            )
            self.assertTrue(all(e["execution"] == PROFILE for e in envelopes))
            self.assertEqual(final["measurements"]["provenance"]["eligible_count"], 2)
            self.assertTrue(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )
            for mutate in (
                "metric",
                "count",
                "slots",
                "missing-gate",
                "stale",
                "blocking-medium",
            ):
                bad = copy.deepcopy(final)
                if mutate == "metric":
                    bad["fast_lane_provenance_coverage"] = 0.5
                elif mutate == "count":
                    bad["measurements"]["provenance"]["covered_count"] = 1
                elif mutate == "slots":
                    bad["measurements"]["evidence"]["required_ids"] = []
                elif mutate == "missing-gate":
                    del bad["agent_runs"]["security"]
                elif mutate == "stale":
                    bad["agent_runs"]["security"]["subject_sha"] = "b" * 40
                else:
                    bad["agent_runs"]["security"]["findings"] = [
                        {**r.finding("medium", "blocked"), "severity": "medium"}
                    ]
                self.assertFalse(
                    o.validate_evidence_bundle(bad, trusted, path.parent)["passed"],
                    mutate,
                )
            response_artifact = next(
                a for a in final["artifacts"] if a["artifact_id"] == "security:response"
            )
            response_path = path.parent / response_artifact["ref"]
            original_response = response_path.read_bytes()
            for nonpass in ("fail", "blocked", "needs_review", "not_applicable"):
                bad = copy.deepcopy(final)
                response = copy.deepcopy(bad["agent_runs"]["security"]["response"])
                response["decision"] = nonpass
                changed = json.dumps(response).encode()
                response_path.write_bytes(changed)
                bad["agent_runs"]["security"]["response"] = response
                digest = hashlib.sha256(changed).hexdigest()

                def refresh(value):
                    if isinstance(value, dict):
                        if value.get("artifact_id") == "security:response":
                            value["sha256"] = digest
                            value["size_bytes"] = len(changed)
                        for child in value.values():
                            refresh(child)
                    elif isinstance(value, list):
                        for child in value:
                            refresh(child)

                refresh(bad)
                try:
                    replay = o.validate_evidence_bundle(bad, trusted, path.parent)
                    self.assertFalse(replay["passed"], nonpass)
                    self.assertTrue(
                        any(
                            "provider decision" in error for error in replay["failures"]
                        ),
                        replay,
                    )
                finally:
                    response_path.write_bytes(original_response)
            artifact = final["artifacts"][0]
            (path.parent / artifact["ref"]).write_bytes(b"tampered")
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )

    def test_malformed_provider_record_retains_blocked_complete_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, _ = self.run_fixture(Path(d), malformed=True)
            self.assertEqual(code, 20)
            final = json.loads(path.read_text())
            self.assertTrue((path.parent / "decision.json").is_file())
            security = final["agent_runs"]["security"]
            self.assertEqual(security["agent_decision"], "blocked")
            self.assertIsNone(security["response"])
            self.assertEqual(security["commands_run"][0]["exit_code"], 0)
            raw = next(
                a for a in final["artifacts"] if a["artifact_id"] == "security:response"
            )
            self.assertIsNone(
                json.loads((path.parent / raw["ref"]).read_text())["findings"]
            )
            replay = o.validate_evidence_bundle(final, trusted, path.parent)
            self.assertFalse(replay["passed"])
            self.assertTrue(
                any("findings" in error for error in replay["failures"]), replay
            )

    def test_real_failed_check_cannot_be_overridden_by_fake_provider_pass(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, _ = self.run_fixture(Path(d), fail_check=True)
            self.assertEqual(code, 20)
            final = json.loads(path.read_text())
            self.assertEqual(final["commands_run"][0]["exit_code"], 7)
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )

    def test_unavailable_provider_keeps_successful_actual_command_records(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, _ = self.run_fixture(Path(d), unavailable=True)
            self.assertEqual(code, 20)
            final = json.loads(path.read_text())
            security = final["agent_runs"]["security"]
            self.assertEqual(security["commands_run"][0]["exit_code"], 0)
            self.assertEqual(security["agent_decision"], "blocked")
            validation = o.validate_evidence_bundle(final, trusted, path.parent)
            self.assertNotIn(
                "final findings differ from runner findings", validation["failures"]
            )
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )


if __name__ == "__main__":
    unittest.main()

class AppServerReplayTests(FullChainV2Tests):
    # Do not inherit the parent's tests a second time; only reuse its fixture helper.
    test_real_checks_fake_provider_complete_bundle_and_replay_tampering = None
    test_malformed_provider_record_retains_blocked_complete_bundle = None
    test_real_failed_check_cannot_be_overridden_by_fake_provider_pass = None
    test_unavailable_provider_keeps_successful_actual_command_records = None

    def test_self_consistent_hashes_cannot_hide_protocol_or_observation_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            code,path,trusted,_=self.run_fixture(Path(d))
            self.assertEqual(code,0)
            final=json.loads(path.read_text())
            by_id={x['artifact_id']:x for x in final['artifacts']}
            protocol_path=path.parent/by_id['architect:protocol']['ref']
            stdout_path=path.parent/by_id['architect:stdout']['ref']
            original_protocol=protocol_path.read_bytes();original_stdout=stdout_path.read_bytes()
            def refresh(value,aid,data):
                if isinstance(value,dict):
                    if value.get('artifact_id')==aid:
                        value['sha256']=hashlib.sha256(data).hexdigest();value['size_bytes']=len(data)
                    for child in value.values():refresh(child,aid,data)
                elif isinstance(value,list):
                    for child in value:refresh(child,aid,data)
            for mode in ['prompt-hash','candidate','version','client-override','catalog','resolved','foreign-turn','observed','sequence']:
                with self.subTest(mode=mode):
                    bad=copy.deepcopy(final);records=[json.loads(x) for x in original_protocol.splitlines()]
                    if mode=='prompt-hash':records[0]['context']['prompt_sha256']='0'*64
                    elif mode=='candidate':records[0]['context']['subject_sha']='f'*40
                    elif mode=='version':records[0]['cli_version']='codex-cli 0.162.0'
                    elif mode=='observed':bad['agent_runs']['architect']['observed_execution']['model']='other'
                    elif mode=='sequence':records[1]['seq']=2
                    else:
                        for rec in records[1:-1]:
                            frame=json.loads(rec['raw'])
                            if mode=='client-override' and frame.get('method')=='turn/start':frame['params']['effort']='high'
                            elif mode=='catalog' and frame.get('id')==2 and 'result' in frame:frame['result']['data'][0]['serviceTiers']=[]
                            elif mode=='resolved' and frame.get('id')==3 and 'result' in frame:frame['result']['model']='other'
                            elif mode=='foreign-turn' and frame.get('method')=='turn/completed':frame['params']['turn']['id']='foreign'
                            rec['raw']=json.dumps(frame)+'\n'
                    changed=('\n'.join(json.dumps(x) for x in records)+'\n').encode()
                    changed_stdout=''.join(x['raw'] for x in records[1:-1] if x['direction']=='server').encode()
                    protocol_path.write_bytes(changed);stdout_path.write_bytes(changed_stdout)
                    refresh(bad,'architect:protocol',changed);refresh(bad,'architect:stdout',changed_stdout)
                    try:
                        result=o.validate_evidence_bundle(bad,trusted,path.parent)
                        self.assertFalse(result['passed'],mode)
                        self.assertTrue(any('runtime evidence' in x or 'observed execution' in x for x in result['failures']),result)
                    finally:
                        protocol_path.write_bytes(original_protocol);stdout_path.write_bytes(original_stdout)
