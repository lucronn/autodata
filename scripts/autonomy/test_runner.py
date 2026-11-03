import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from runner import (
    RunnerError,
    build_provider_command,
    changed_paths,
    document_scope_violations,
    redact_text,
    run_agent,
    _make_guard_bin,
    validate_envelope,
)


class RunnerTests(unittest.TestCase):
    def _frozen_review_prompt(self):
        prompt = (Path(__file__).resolve().parents[2] / '.cursor/agents/autodata-review-agent.md').read_bytes()
        # Bind the complete prompt at gated base 5da393 without requiring its Git object in shallow CI.
        self.assertEqual(hashlib.sha256(prompt).hexdigest(),
                         'd43f9a584cd5e65b823b1ee401b744e5e4d9923b2e57cd9517cdd7832ade09ed')
        return prompt.decode('utf-8', errors='strict')

    def _environment_fixture(self, *, nested=False, source_output=False):
        from test_app_server_adapter import fake_codex, boundary
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);repo=parent/'repo';repo.mkdir()
            task,base=make_trusted_repository(repo)
            trusted=r.load_trusted_inputs(repo,base,task['task_ref'])
            bindir=fake_codex(parent);out=parent/'run';scratch=parent/'scratch';scratch.mkdir()
            ordinary=str(bindir)+os.pathsep+os.defpath
            inherited={'PATH':ordinary,'HOME':str(parent/'home'),'CODEX_HOME':'/tmp/codex-disposable',
                       'TMPDIR':str(scratch),'AUTODATA_TEST_PUBLIC':'retained',
                       'SYNTHETIC_API_KEY':'fixture-only','SYNTHETIC_TOKEN':'fixture-only',
                       'DATABASE_URL':'fixture-only','KUBECONFIG':'fixture-only','AWS_PROFILE':'fixture-only',
                       'GOOGLE_APPLICATION_CREDENTIALS':'fixture-only'}
            envelope={'run_id':'environment-check','task_id':task['task_id'],'repository':task['repository'],
                      'base_sha':base,'subject_sha':base,'trusted_base_sha':base,'task_ref':task['task_ref'],
                      'agent_name':'autodata-security-agent','task_contract':{k:task[k] for k in r.CONTRACT_FIELDS},
                      'allowed_paths':[],'deployment_target':'none','execution':task['execution'],
                      'evidence_label':'security','response_artifact_id':'security:response','gate':'security'}
            seen={};checks=r.execute_required_checks;provider=r.app_server.run_app_server
            def observe_checks(worktree,subject,assigned,output_root,environment):
                seen['checks']=dict(environment)
                if nested:
                    script='''import json,os,subprocess,sys
from pathlib import Path
import runner as r
from test_runner import make_trusted_repository
from test_app_server_adapter import fake_codex,boundary
root=Path(sys.argv[1]);root.mkdir();repo=root/'repo';repo.mkdir()
task,base=make_trusted_repository(repo);trusted=r.load_trusted_inputs(repo,base,task['task_ref'])
bindir=fake_codex(root);os.environ['PATH']=str(bindir)+os.pathsep+os.environ['PATH']
r.app_server.validate_boundary=lambda path,cwd,env:boundary(cwd)
envelope=json.loads(sys.argv[2]);envelope.update(base_sha=base,subject_sha=base,trusted_base_sha=base,task_contract={k:task[k] for k in r.CONTRACT_FIELDS})
out=root/'run';r.run_agent(repo,envelope,'local-cli',out,6,trusted=trusted)
manifest=json.loads((out/'run-manifest.json').read_text())
assert manifest['decision']=='pass',manifest['findings']
assert not (out/'worktree').exists(),'owned worktree cleanup failed'
assert len(subprocess.check_output(['git','worktree','list','--porcelain'],cwd=repo,text=True).split('worktree '))==2
guarded=r._safe_environment(out/'guard-bin',out/'isolated-gh-config')
for argv in (['git','worktree','remove','--force','unused'],['gh','repo','view']):
    result=subprocess.run(argv,cwd=repo,env=guarded,capture_output=True)
    assert result.returncode==126,result.stderr
print('nested owned cleanup and provider guards verified')
'''
                    result=subprocess.run([sys.executable,'-c',script,str(parent/'nested'),json.dumps(envelope)],
                        env={**environment,'PYTHONPATH':str(Path(__file__).parent)},cwd=parent,
                        capture_output=True,text=True,timeout=12)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn('nested owned cleanup and provider guards verified',result.stdout)
                return checks(worktree,subject,assigned,output_root,environment)
            marker='sk-'+('synthetic-source-pattern'*2)
            def observe_provider(**kwargs):
                seen['provider']=dict(kwargs['env'])
                result=provider(**kwargs)
                if source_output:
                    # Only synthetic bytes: model source dumping must still fail closed.
                    frame={'method':'item/agentMessage/delta','params':{'threadId':'thread-1','turnId':'turn-1','itemId':'comment','delta':marker}}
                    records=[json.loads(line) for line in result['protocol'].splitlines()]
                    index=next(i for i,rec in enumerate(records[1:-1],1) if rec['direction']=='server' and json.loads(rec['raw']).get('method')=='turn/completed')
                    records.insert(index,{'direction':'server','raw':json.dumps(frame)+'\n'})
                    for seq,rec in enumerate(records[1:-1],1):rec['seq']=seq
                    result['protocol']=b''.join((json.dumps(rec)+'\n').encode() for rec in records)
                    result['stdout']=''.join(rec['raw'] for rec in records[1:-1] if rec['direction']=='server').encode()
                    self.assertTrue(r.app_server.replay_capture(result['protocol'],stdout=result['stdout'],expected=kwargs['expected'])['completed'])
                return result
            with patch.dict(os.environ,inherited,clear=True),patch.object(r,'execute_required_checks',side_effect=observe_checks),patch.object(r.app_server,'run_app_server',side_effect=observe_provider),patch.object(r.app_server,'validate_boundary',side_effect=lambda path,cwd,env:boundary(cwd)):
                run_agent(repo,envelope,'local-cli',out,6,trusted=trusted)
                self.assertEqual(dict(os.environ),inherited)
            manifest=json.loads((out/'run-manifest.json').read_text())
            if source_output:
                self.assertEqual(manifest['decision'],'blocked')
                self.assertTrue(any(f['message']=='runtime transcript required redaction' for f in manifest['findings']))
                for artifact in manifest['artifacts']:
                    self.assertNotIn(marker.encode(),(out/artifact['ref']).read_bytes())
            else:self.assertEqual(manifest['decision'],'pass',manifest['findings'])
            return seen,inherited,str(out/'guard-bin'),str(out/'isolated-gh-config')

    def test_required_checks_receive_sanitized_unguarded_environment(self):
        seen,inherited,guard,config=self._environment_fixture()
        checks=seen['checks']
        self.assertEqual(checks['PATH'],inherited['PATH'])
        self.assertNotIn(guard,checks['PATH'].split(os.pathsep))
        for name in ('HOME','CODEX_HOME','TMPDIR','AUTODATA_TEST_PUBLIC'):
            self.assertEqual(checks[name],inherited[name])
            self.assertEqual(seen['provider'][name],inherited[name])
        for env in seen.values():
            self.assertEqual({k:env[k] for k in ('CI','GIT_TERMINAL_PROMPT','GIT_CONFIG_NOSYSTEM','GH_CONFIG_DIR','PYTHONDONTWRITEBYTECODE')},
                             {'CI':'true','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GH_CONFIG_DIR':config,'PYTHONDONTWRITEBYTECODE':'1'})
            for name in ('SYNTHETIC_API_KEY','SYNTHETIC_TOKEN','DATABASE_URL','KUBECONFIG','AWS_PROFILE','GOOGLE_APPLICATION_CREDENTIALS'):
                self.assertNotIn(name,env)
        self.assertIsNot(seen['checks'],seen['provider'])

    def test_provider_keeps_owned_command_guards(self):
        seen,inherited,guard,_=self._environment_fixture()
        self.assertEqual(seen['provider']['PATH'],guard+os.pathsep+inherited['PATH'])
        self.assertNotEqual(seen['provider']['PATH'],seen['checks']['PATH'])

    def test_nested_fixture_owns_its_git_guard_and_cleanup(self):
        self._environment_fixture(nested=True)

    def test_source_output_pattern_still_blocks_and_is_not_retained(self):
        self._environment_fixture(source_output=True)

    def test_runtime_fixture_assigned_verifier_prompt_scopes_local_decision(self):
        base=self._frozen_review_prompt()
        task=json.loads((Path(__file__).resolve().parents[2]/'docs/agents/tasks/2026-11-03-production-release/runtime-fixture.json').read_text())
        assigned=[c['check_id'] for c in task['verification']['checks'] if c['gate']=='independent_review']
        commands=[{'check_id':assigned[0],'status':'completed','exit_code':0}]
        artifacts=[{'artifact_id':assigned[0]+':command','kind':'command-result'}]
        prompt=r.build_agent_prompt(base,{'task_id':task['task_id']},commands,artifacts,{},role='verification',check_ids=assigned)
        self.assertTrue(prompt.startswith(base))
        for text in ('SYNTHETIC RUNTIME FIXTURE — LOCAL VERIFICATION ASSIGNMENT',
                     'For this turn, assess only the exact assigned check IDs',
                     'these instructions take precedence over',
                     'response decision','local to these assignments','not supplied in this fixture turn',
                     'all ten roles and eight gates','Return pass only if','concrete observed blocker',
                     'never fabricate unavailable evidence','exactly once','Do not run additional commands/checks',
                     'dump unrelated source/test files','credential-pattern examples','intentional synthetic test',
                     'strict redaction','exact raw replay'):
            self.assertIn(text,prompt)
        self.assertIn(json.dumps(assigned),prompt)
        self.assertIn(artifacts[0]['artifact_id'],prompt)
        self.assertNotIn('UPSTREAM GATE REPORTS:',prompt)

    def test_nonfixture_review_retains_full_review_duty(self):
        base=self._frozen_review_prompt()
        for task_id,role,ids in (('release-task','verification',['check']),('production-release-runtime-fixture','architecture',[]),('production-release-runtime-fixture','implementation',[])):
            prompt=r.build_agent_prompt(base,{'task_id':task_id},[],[],{},role=role,check_ids=ids)
            self.assertTrue(prompt.startswith(base))
            self.assertIn('Review the complete candidate diff, task contract, all gate reports, and evidence bundle.',prompt)
            self.assertNotIn('SYNTHETIC RUNTIME FIXTURE — LOCAL VERIFICATION ASSIGNMENT',prompt)

    def test_builder_without_pre_implementation_record_is_rejected_before_worktree(
        self,
    ):
        repo_root = Path(__file__).resolve().parents[2]
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        envelope = {
            "run_id": "run-preflight-test",
            "task_id": "issue-86",
            "base_sha": base_sha,
            "agent_name": "autodata-go-builder",
            "allowed_paths": ["apps/api-go/**"],
            "deployment_target": "none",
        }

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "run"
            with patch("runner._git_show", return_value="builder prompt"), patch(
                "runner._run_git", return_value=base_sha
            ), patch("runner._make_guard_bin", return_value=Path(directory)), patch(
                "runner.build_provider_command", return_value=["false"]
            ) as provider:
                with self.assertRaises(RunnerError):
                    run_agent(
                        repo_root, envelope, "local-cli", output_root, timeout_seconds=1
                    )

            provider.assert_not_called()
            self.assertFalse((output_root / "worktree").exists())

    def test_local_cli_command_is_noninteractive_and_workspace_scoped(self):
        command = build_provider_command(
            provider="local-cli",
            cwd=Path("/tmp/worktree"),
            output_file=Path("/tmp/last.json"),
            schema_file=Path("/tmp/schema.json"),
            execution=PROFILE,
        )

        self.assertEqual(command, [
            "codex", "app-server", "--stdio", "--strict-config", "-c", 'model="gpt-6.1-sol"',
            "-c", 'model_reasoning_effort="medium"', "-c", 'service_tier="fast"',
            "-c", "features.fast_mode=true"])

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            build_provider_command(
                provider="unknown",
                cwd=Path("/tmp/worktree"),
                output_file=Path("/tmp/last.json"),
                schema_file=Path("/tmp/schema.json"),
                execution=PROFILE,
            )

    def test_envelope_rejects_production_and_unregistered_agent(self):
        registry = {"agents": [{"name": "autodata-go-builder", "prompt": "agent.md"}]}
        policy = {
            "autonomy": {
                "production_deployment": False,
                "allowed_deployment_targets": ["dev"],
            }
        }

        errors = validate_envelope(
            {
                "run_id": "run-1",
                "task_id": "task-1",
                "base_sha": "a" * 40,
                "agent_name": "unregistered",
                "allowed_paths": ["apps/**"],
                "deployment_target": "production",
            },
            registry,
            policy,
            actual_base_sha="a" * 40,
        )

        self.assertIn("agent_name is not registered: unregistered", errors)
        self.assertIn("production deployment is disabled by policy", errors)

    def test_envelope_rejects_stale_base_and_empty_scope(self):
        registry = {"agents": [{"name": "autodata-go-builder", "prompt": "agent.md"}]}
        policy = {
            "autonomy": {
                "production_deployment": False,
                "allowed_deployment_targets": [],
            }
        }

        errors = validate_envelope(
            {
                "run_id": "run-1",
                "task_id": "task-1",
                "base_sha": "a" * 40,
                "agent_name": "autodata-go-builder",
                "allowed_paths": [],
                "deployment_target": "none",
            },
            registry,
            policy,
            actual_base_sha="b" * 40,
        )

        self.assertIn("base_sha does not match repository HEAD", errors)
        self.assertIn("allowed_paths must be a non-empty list of strings", errors)

    def test_changed_paths_includes_tracked_and_untracked_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            # A fake git executable is used so this unit test remains deterministic.
            git = root / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = diff ]; then printf 'apps/api/main.go\\0'; fi\n"
                "if [ \"$1\" = ls-files ]; then printf 'docs/new.md\\0'; fi\n",
                encoding="utf-8",
            )
            git.chmod(0o755)
            result = changed_paths(root, "a" * 40, git_executable=str(git))

        self.assertEqual(result, ["apps/api/main.go", "docs/new.md"])

    def test_document_scope_allows_canonical_docs_and_rejects_parallel_docs(self):
        policy = {
            "documentation": {
                "canonical_paths": ["docs/**"],
                "document_extensions": [".md", ".mdx"],
            }
        }

        violations = document_scope_violations(
            ["docs/architecture/contracts.md", "apps/api/README.md", "notes/design.md"],
            policy,
        )

        self.assertEqual(violations, ["apps/api/README.md", "notes/design.md"])

    def test_document_scope_fails_closed_when_policy_configuration_is_invalid(self):
        violations = document_scope_violations(
            ["apps/api/README.md", "apps/api/main.go"],
            {"documentation": {"canonical_paths": "docs/**"}},
        )

        self.assertEqual(violations, ["apps/api/README.md"])

    def test_redacts_common_secret_shapes(self):
        text = "token=sk-abc123 github_pat_abc123 AKIAIOSFODNN7EXAMPLE"

        redacted = redact_text(text)

        self.assertNotIn("sk-abc123", redacted)
        self.assertNotIn("github_pat_abc123", redacted)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", redacted)
        self.assertEqual(redacted.count("[REDACTED_SECRET]"), 3)

    def test_command_guard_blocks_subcommands_after_git_options(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = _make_guard_bin(Path(directory) / "bin")
            result = subprocess.run(
                [str(guard / "git"), "-C", directory, "push"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 126)
        self.assertIn("blocked by AutoData runner", result.stderr)


# v2 regressions use actual Git/files/processes; provider access is never required.
import os
import sys
import copy
import hashlib
import runner as r

PROFILE = {
    "model": "gpt-6.1-sol",
    "reasoning_effort": "medium",
    "service_tier": "fast",
    "features": {"fast_mode": True},
    "allow_fallback": False,
}
SHA = "a" * 40


class EvidenceSchemaTests(unittest.TestCase):
    def test_execution_profile_is_explicit_and_exact(self):
        self.assertEqual(r.validate_execution_profile(PROFILE), [])
        for value in (
            None,
            {},
            {**PROFILE, "allow_fallback": True},
            {**PROFILE, "extra": 1},
            {**PROFILE, "model": "other"},
            {**PROFILE, "features": {"fast_mode": False}},
        ):
            self.assertTrue(r.validate_execution_profile(value))
        argv = r.build_provider_command(
            "local-cli",
            Path("/tmp/w"),
            Path("/tmp/o"),
            Path("/tmp/s"),
            execution=PROFILE,
        )
        for argument in (
            'model="gpt-6.1-sol"',
            'model_reasoning_effort="medium"',
            'service_tier="fast"',
            "features.fast_mode=true",
            "--strict-config",
        ):
            self.assertIn(argument, argv)

    def test_response_rejects_legacy_identity_and_dangling_evidence(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        expected = {
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "role": "verification",
            "check_ids": ["check"],
            "artifact_ids": ["log"],
        }
        value = {
            "schema_version": 2,
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "decision": "pass",
            "summary": "checked",
            "task_contract": None,
            "findings": [],
            "assessments": [
                {
                    "check_id": "check",
                    "decision": "pass",
                    "evidence_ids": ["log"],
                    "explanation": "ok",
                }
            ],
            "evidence_ids": ["log"],
        }
        self.assertEqual(r.validate_agent_response(value, schema, expected), [])
        for bad in (
            {"decision": "pass", "summary": "ok", "task_contract": None},
            {**value, "subject_sha": "b" * 40},
            {**value, "schema_version": True},
            {**value, "extra": 1},
            {**value, "evidence_ids": ["unknown"]},
            {**value, "assessments": []},
            {**value, "evidence_ids": ["log", "log"]},
            {**value, "findings": [{"finding_id": "f"}]},
        ):
            self.assertTrue(r.validate_agent_response(bad, schema, expected), bad)

    def test_provider_schema_omits_rejected_unique_items_keyword(self):
        # The real provider rejected this keyword before executing any agent.
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        unsupported = []

        def visit(value, path=""):
            if isinstance(value, dict):
                if "uniqueItems" in value:
                    unsupported.append(path + "/uniqueItems")
                for key, child in value.items():
                    visit(child, path + "/" + key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, path + "/" + str(index))

        visit(schema)
        self.assertEqual(unsupported, [], "provider rejects uniqueItems")
        self.assertEqual(r.validate_schema_inventory(schema), [])

    def test_provider_schema_omits_unsupported_regex_lookaround(self):
        # The provider validates unused definitions too, before executing any agent.
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        unsupported = []

        def visit(value, path=""):
            if isinstance(value, dict):
                pattern = value.get("pattern")
                if isinstance(pattern, str) and any(
                    token in pattern for token in ("(?=", "(?!", "(?<=", "(?<!")
                ):
                    unsupported.append(path + "/pattern")
                for key, child in value.items():
                    visit(child, path + "/" + key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, path + "/" + str(index))

        visit(schema)
        self.assertEqual(unsupported, [], "provider rejects regex lookaround")
        self.assertEqual(r.validate_schema_inventory(schema), [])

    def test_runtime_rejects_duplicate_response_finding_and_assessment_evidence(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        expected = {
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "role": "verification",
            "check_ids": ["check"],
            "artifact_ids": ["log"],
        }
        observed = r.finding("finding", "observed")
        observed["evidence_ids"] = ["log"]
        response = {
            "schema_version": 2,
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "decision": "pass",
            "summary": "checked",
            "task_contract": None,
            "findings": [observed],
            "assessments": [
                {
                    "check_id": "check",
                    "decision": "pass",
                    "evidence_ids": ["log"],
                    "explanation": "checked report",
                }
            ],
            "evidence_ids": ["log"],
        }
        self.assertEqual(r.validate_agent_response(response, schema, expected), [])
        for path, error in (
            (["evidence_ids"], "unknown/duplicate evidence IDs"),
            (["findings", 0, "evidence_ids"], "invalid finding evidence IDs"),
            (["assessments", 0, "evidence_ids"], "invalid assessment"),
        ):
            with self.subTest(path=path):
                bad = copy.deepcopy(response)
                target = bad
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]].append("log")
                self.assertIn(error, r.validate_agent_response(bad, schema, expected))
        for key, error in (
            ("findings", "duplicate finding ID"),
            ("assessments", "assessments must match assigned checks exactly"),
        ):
            bad = copy.deepcopy(response)
            bad[key] *= 2
            self.assertIn(error, r.validate_agent_response(bad, schema, expected))

    def test_runtime_rejects_duplicate_command_output_ids(self):
        record = {
            "schema_version": 2,
            "check_id": "check",
            "subject_sha": SHA,
            "argv": ["python3", "-c", "pass"],
            "executable": "/usr/bin/python3",
            "cwd": ".",
            "started_at": "2026-11-03T00:00:00Z",
            "finished_at": "2026-11-03T00:00:01Z",
            "status": "completed",
            "exit_code": 0,
            "stdout_id": "check:stdout",
            "stderr_id": "check:stderr",
            "output_ids": ["report"],
        }
        self.assertEqual(r._command_errors(record), [])
        record["output_ids"].append("report")
        self.assertIn("invalid command output IDs", r._command_errors(record))

    def test_runtime_rejects_duplicate_provenance_eligible_and_covered_ids(self):
        report = {
            "schema_version": 2,
            "subject_sha": SHA,
            "population_id": "population",
            "scope": "synthetic-regression",
            "population_sha256": "b" * 64,
            "eligible_ids": ["fact"],
            "covered_ids": ["fact"],
            "uncovered": [],
            "records": [
                {
                    "fact_id": "fact",
                    "source_sha256": "c" * 64,
                    "extraction_sha256": "d" * 64,
                    "source_pointer": "/value",
                    "extraction_pointer": "/value",
                    "value_sha256": "e" * 64,
                }
            ],
        }
        self.assertEqual(r.validate_provenance_record(report), [])
        for key in ("eligible_ids", "covered_ids"):
            with self.subTest(key=key):
                bad = copy.deepcopy(report)
                bad[key].append("fact")
                self.assertIn(
                    "invalid provenance scope/IDs", r.validate_provenance_record(bad)
                )

    def test_runtime_rejects_duplicate_required_agent_evidence_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            task, _ = make_trusted_repository(Path(directory))
            verification = task["verification"]
            self.assertEqual(r.validate_verification(verification), [])
            # Preserve the required count so length alone cannot catch the duplicate.
            verification["required_agent_evidence"][-1] = verification[
                "required_agent_evidence"
            ][0]
            self.assertIn(
                "ten independent agent evidence IDs are required",
                r.validate_verification(verification),
            )

    def test_schema_inventory_matches_fixed_records(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        self.assertEqual(r.validate_schema_inventory(schema), [])
        altered = copy.deepcopy(schema)
        altered["$defs"]["Finding"]["properties"]["extra"] = {}
        self.assertTrue(r.validate_schema_inventory(altered))


# These forms must remain rejected after provider-side path patterns are removed.
UNSAFE_PATHS = (
    "",
    "/file",
    "../file",
    "dir/../file",
    "dir\\file",
    "dir\x00file",
    "dir//file",
    "./file",
    "dir/./file",
    "dir/.",
    "dir/",
)


class RuntimePathBoundaryTests(unittest.TestCase):
    def test_finding_response_rejects_unsafe_paths_and_allows_root(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        expected = {
            "run_id": "r", "task_id": "t", "agent_name": "a",
            "subject_sha": SHA, "role": "implementation",
            "check_ids": [], "artifact_ids": [],
        }
        response = {
            "schema_version": 2, "run_id": "r", "task_id": "t",
            "agent_name": "a", "subject_sha": SHA, "decision": "pass",
            "summary": "checked", "task_contract": None,
            "findings": [r.finding("observed", "checked")],
            "assessments": [], "evidence_ids": [],
        }
        for path in (".", "docs/valid file.md", "docs/évidence.md"):
            response["findings"][0]["path"] = path
            self.assertEqual(r.validate_agent_response(response, schema, expected), [])
        for path in UNSAFE_PATHS:
            with self.subTest(path=path):
                response["findings"][0]["path"] = path
                self.assertIn(
                    "invalid finding path",
                    r.validate_agent_response(response, schema, expected),
                )

    def test_artifact_records_reject_unsafe_refs_even_when_files_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dir").mkdir()
            for path in ("file", "dir/file", "dir\\file", "valid file", "évidence"):
                (root / path).write_bytes(b"evidence")
            record = {
                "artifact_id": "proof", "kind": "test-result", "ref": "file",
                "sha256": hashlib.sha256(b"evidence").hexdigest(),
                "size_bytes": 8, "subject_sha": SHA, "check_id": None,
            }
            for path in ("file", "dir/file", "valid file", "évidence"):
                record["ref"] = path
                self.assertEqual(r.validate_artifact(record, root, SHA), [])
            for path in (*UNSAFE_PATHS, ".", str(root / "file")):
                with self.subTest(path=path):
                    record["ref"] = path
                    self.assertIn(
                        "unsafe artifact path", r.validate_artifact(record, root, SHA)
                    )

    def test_command_records_reject_unsafe_cwd_and_allow_root(self):
        record = {
            "schema_version": 2, "check_id": "check", "subject_sha": SHA,
            "argv": ["python3", "-c", "pass"], "executable": "/usr/bin/python3",
            "cwd": ".", "started_at": "2026-11-03T00:00:00Z",
            "finished_at": "2026-11-03T00:00:01Z", "status": "completed",
            "exit_code": 0, "stdout_id": "check:stdout",
            "stderr_id": "check:stderr", "output_ids": [],
        }
        for path in (".", "scripts/autonomy", "valid directory"):
            record["cwd"] = path
            self.assertEqual(r._command_errors(record), [])
        for path in UNSAFE_PATHS:
            with self.subTest(path=path):
                record["cwd"] = path
                self.assertIn("invalid command argv/cwd", r._command_errors(record))

    def test_verification_rejects_unsafe_check_output_and_population_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            task, _ = make_trusted_repository(Path(directory))
            verification = task["verification"]
            output = next(
                check["outputs"][0]
                for check in verification["checks"] if check["outputs"]
            )
            for location, key, error, permits_root in (
                (
                    verification["checks"][0], "cwd",
                    "invalid check execution definition", True,
                ),
                (output, "relative_path", "invalid output definition", False),
                (
                    verification["provenance"], "population_ref",
                    "invalid provenance definition", False,
                ),
            ):
                original = location[key]
                valid_paths = ("valid/path", "valid file", "évidence")
                if permits_root:
                    valid_paths += (".",)
                for path in valid_paths:
                    location[key] = path
                    self.assertEqual(r.validate_verification(verification), [])
                for path in UNSAFE_PATHS + (() if permits_root else (".",)):
                    with self.subTest(field=key, path=path):
                        location[key] = path
                        self.assertIn(error, r.validate_verification(verification))
                location[key] = original


class EvidenceExecutionTests(unittest.TestCase):
    def test_artifact_rejects_unsafe_inputs_and_retains_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = root / "stage"
            stage.mkdir()
            dest = root / "dest"
            dest.mkdir()
            (stage / "x").write_bytes(b"valid\n")
            item = r.retain_artifact(stage, "x", dest, "x", "test-result", SHA, None)
            self.assertEqual(item["sha256"], hashlib.sha256(b"valid\n").hexdigest())
            self.assertEqual((dest / item["ref"]).read_bytes(), b"valid\n")
            (stage / "link").symlink_to(stage / "x")
            os.link(stage / "x", stage / "hard")
            os.mkfifo(stage / "fifo")
            for name in ("../x", "/x", "link", "hard", "fifo"):
                with self.assertRaises(r.RunnerError):
                    r.retain_artifact(
                        stage, name, dest, "bad", "test-result", SHA, None
                    )
            with self.assertRaises(r.RunnerError):
                r.retain_artifact(stage, "x", dest, "x", "test-result", SHA, None)

    def test_commands_capture_real_failure_unavailable_timeout_and_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "work"
            w.mkdir()
            checks = [
                {
                    "check_id": "failed",
                    "gate": "security",
                    "argv": [
                        "python3",
                        "-c",
                        'import sys;print("out");print("err",file=sys.stderr);sys.exit(7)',
                    ],
                    "cwd": ".",
                    "timeout_seconds": 2,
                    "expected_exit_code": 0,
                    "outputs": [],
                }
            ]
            commands, artifacts, findings = r.execute_required_checks(
                w, SHA, checks, root / "out", dict(os.environ)
            )
            self.assertEqual(commands[0]["exit_code"], 7)
            self.assertEqual(commands[0]["status"], "completed")
            self.assertTrue(any(f["blocking"] for f in findings))
            self.assertTrue(any(a["kind"] == "stderr" for a in artifacts))
            checks[0].update(
                check_id="timeout",
                argv=["python3", "-c", "import time;time.sleep(10)"],
                timeout_seconds=1,
            )
            commands, _, findings = r.execute_required_checks(
                w, SHA, checks, root / "timeout", dict(os.environ)
            )
            self.assertEqual(commands[0]["status"], "timed_out")
            self.assertIsNone(commands[0]["exit_code"])
            checks[0].update(check_id="missing", argv=["go", "version"])
            with patch("runner.shutil.which", return_value=None):
                commands, _, _ = r.execute_required_checks(
                    w, SHA, checks, root / "missing", dict(os.environ)
                )
            self.assertEqual(commands[0]["status"], "unavailable")

    def test_commands_reject_missing_undeclared_secret_and_malformed_output(self):
        for script in (
            "pass",
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/extra","w").write("x")',
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/result.json","w").write("invalid")',
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/result.json","w").write(\'{"token":"sk-secretvalue"}\')',
        ):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                check = {
                    "check_id": "c",
                    "gate": "security",
                    "argv": ["python3", "-c", script],
                    "cwd": ".",
                    "timeout_seconds": 2,
                    "expected_exit_code": 0,
                    "outputs": [
                        {
                            "artifact_id": "result",
                            "kind": "test-result",
                            "relative_path": "result.json",
                            "format": "json",
                        }
                    ],
                }
                _, _, findings = r.execute_required_checks(
                    root, SHA, [check], root / "out", dict(os.environ)
                )
                self.assertTrue(any(f["blocking"] for f in findings), script)

    def test_timeout_terminates_grandchild_and_output_exhaustion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            marker = root / "escaped"
            script = (
                'import subprocess,time;subprocess.Popen(["python3","-c",'
                + repr(
                    "import time;from pathlib import Path;time.sleep(3);Path("
                    + repr(str(marker))
                    + ').write_text("escaped")'
                )
                + "]);time.sleep(10)"
            )
            result = r.bounded_process(
                ["python3", "-c", script], root, dict(os.environ), 1
            )
            self.assertEqual(result["status"], "timed_out")
            result = r.bounded_process(
                ["python3", "-c", 'import sys;sys.stdout.write("x"*100000)'],
                root,
                dict(os.environ),
                2,
            )
            self.assertEqual(result["status"], "completed")
            self.assertFalse(marker.exists())
            with patch("runner.MAX_LOG", 1024):
                result = r.bounded_process(
                    ["python3", "-c", 'print("x"*100000)'], root, dict(os.environ), 2
                )
            self.assertTrue(result["output_budget_exhausted"])
            self.assertLessEqual(len(result["stdout"]), 1024)


class CandidateScopeTests(unittest.TestCase):
    def test_deleted_newline_path_and_dirty_after_commit_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=root, capture_output=True, text=True, check=True
                ).stdout.strip()

            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (root / "allowed").write_text("ok")
            (root / "outside\nname").write_text("x")
            git("add", ".")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            (root / "outside\nname").unlink()
            git("add", "-A")
            git("commit", "-m", "delete")
            head = git("rev-parse", "HEAD")
            trusted = {"policy": {"protected_paths": []}, "registry": {"agents": []}}
            result = r.inspect_candidate(
                root, base, head, "implementation", ["allowed"], trusted
            )
            self.assertIn("outside\nname", result["changed_paths"])
            self.assertTrue(
                any(f["finding_id"] == "runner.path-scope" for f in result["findings"])
            )
            (root / "allowed").write_text("dirty")
            result = r.inspect_candidate(
                root, base, head, "verification", ["**"], trusted
            )
            self.assertTrue(any(f["blocking"] for f in result["findings"]))

    def test_verifier_commit_and_protected_path_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=root, text=True, capture_output=True, check=True
                ).stdout.strip()

            git("init")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "x").write_text("a")
            git("add", ".")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            (root / ".autodata-agent-registry.json").write_text("{}")
            git("add", ".")
            git("commit", "-m", "protected")
            head = git("rev-parse", "HEAD")
            result = r.inspect_candidate(
                root,
                base,
                head,
                "verification",
                ["**"],
                {"subject_sha": base, "policy": {}, "registry": {}},
            )
            ids = {f["finding_id"] for f in result["findings"]}
            self.assertIn("runner.reviewer-commit", ids)
            self.assertIn("runner.protected-path", ids)


class ProvenanceMeasurementTests(unittest.TestCase):
    def test_real_fixture_and_independent_replay(self):
        fixture = Path(__file__).parent / "fixtures" / "provenance-v1"
        population = json.loads((fixture / "population.json").read_text())
        inputs = {
            n: (fixture / n).read_bytes() for n in ("source.json", "extraction.json")
        }
        with tempfile.TemporaryDirectory() as d:
            env = {
                **os.environ,
                "AUTODATA_EVIDENCE_ROOT": d,
                "AUTODATA_SUBJECT_SHA": SHA,
            }
            result = subprocess.run(
                [
                    sys.executable,
                    str(fixture.parent / "run_provenance_fixture.py"),
                    "--population",
                    str(fixture / "population.json"),
                ],
                env=env,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(d) / "provenance.json").read_text())
        measured = r.measure_provenance(population, inputs, report, SHA)
        self.assertEqual(
            (measured["eligible_count"], measured["covered_count"], measured["ratio"]),
            (2, 2, 1.0),
        )
        bad = copy.deepcopy(report)
        bad["records"][0]["source_pointer"] = "/missing"
        measured = r.measure_provenance(population, inputs, bad, SHA)
        self.assertEqual(measured["ratio"], 0.5)
        self.assertTrue(measured["findings"])
        for bad in (
            {**report, "eligible_ids": []},
            {**report, "subject_sha": "b" * 40},
            {**report, "ratio": 1.0},
            {**report, "covered_ids": ["foreign"]},
            {**report, "records": report["records"] * 2},
        ):
            self.assertTrue(
                r.measure_provenance(population, inputs, bad, SHA)["findings"]
            )
        empty = {**population, "records": []}
        self.assertIsNone(r.measure_provenance(empty, inputs, report, SHA)["ratio"])


def make_trusted_repository(root):
    """Real clean Git fixture carrying the current evaluator, never a production fake mode."""
    import shutil

    source = Path(__file__).resolve().parents[2]
    task = json.loads(
        (
            source / "docs/agents/tasks/2026-11-03-production-release/r0-evidence.json"
        ).read_text()
    )
    task.update(
        task_id="fixture-task",
        allowed_paths=["app.txt"],
        evidence_contract_version=2,
        task_ref="docs/agents/tasks/fixture.json",
    )
    checks = []
    for i, gate in enumerate(r.GATES):
        cid = (
            "source-fixture"
            if gate == "source_provenance"
            else "quality-fixture" if gate == "data_quality" else "check-" + str(i)
        )
        outputs = []
        argv = ["python3", "-c", 'print("real local check")']
        if gate in ("source_provenance", "data_quality"):
            argv = [
                "python3",
                "scripts/autonomy/fixtures/run_provenance_fixture.py",
                "--population",
                "scripts/autonomy/fixtures/provenance-v1/population.json",
            ]
            outputs = [
                {
                    "artifact_id": cid + ":proof",
                    "kind": "provenance-result",
                    "relative_path": "provenance.json",
                    "format": "json",
                }
            ]
        checks.append(
            {
                "check_id": cid,
                "gate": gate,
                "argv": argv,
                "cwd": ".",
                "timeout_seconds": 5,
                "expected_exit_code": 0,
                "outputs": outputs,
            }
        )
    task["verification"] = {
        "checks": checks,
        "provenance": {
            "check_id": "source-fixture",
            "population_ref": "scripts/autonomy/fixtures/provenance-v1/population.json",
            "report_artifact_id": "source-fixture:proof",
        },
        "required_agent_evidence": [
            x + ":response" for x in ("architect", "builder", *r.GATES)
        ],
    }
    paths = [
        ".autodata-agent-registry.json",
        ".autodata-autonomy-policy.json",
        "scripts/autonomy/runner.py",
        "scripts/autonomy/app_server_adapter.py",
        "scripts/autonomy/orchestrator.py",
        "scripts/autonomy/pre_implementation.py",
        "scripts/autonomy/validate_run.py",
        "scripts/autonomy/agent-output.schema.json",
        "scripts/autonomy/fixtures/run_provenance_fixture.py",
        task["pre_implementation"]["plan_ref"],
        *task["pre_implementation"]["repository_doc_refs"],
    ]
    registry = json.loads((source / ".autodata-agent-registry.json").read_text())
    paths += [a["prompt"] for a in registry["agents"]]
    paths += [
        "scripts/autonomy/fixtures/provenance-v1/" + name
        for name in ("population.json", "source.json", "extraction.json")
    ]
    for path in paths:
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / path, dest)
    (root / "docs/agents/tasks").mkdir(parents=True, exist_ok=True)
    (root / task["task_ref"]).write_text(json.dumps(task))
    (root / "app.txt").write_text("before")

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-m", "trusted fixture")
    return task, git("rev-parse", "HEAD")


class TrustBoundaryTests(unittest.TestCase):
    def test_load_uses_committed_inputs_and_external_overrides_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
            self.assertEqual(trusted["task"], task)
            (root / ".autodata-autonomy-policy.json").write_text("{}")
            self.assertNotEqual(
                r.load_trusted_inputs(root, base, task["task_ref"])["policy"], {}
            )
            self.assertTrue(
                r.validate_task_input({**task, "allowed_paths": ["**"]}, trusted)
            )
            self.assertTrue(
                r.validate_task_input({**task, "unknown": "override"}, trusted)
            )
            self.assertFalse(
                r.validate_task_input({**task, "run_id": "unique"}, trusted)
            )
            with self.assertRaises(r.RunnerError):
                r.load_trusted_inputs(root, base, "docs/agents/tasks/missing.json")
            with self.assertRaises(r.RunnerError):
                r.load_trusted_inputs(root, base, "../task.json")

    def test_planning_refs_are_loaded_safely_and_frozen_in_architect_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, base = make_trusted_repository(root)
            original = task["pre_implementation"]["plan_ref"]
            plan_text = (root / original).read_text()
            # Backslashes are legal Git filenames. Their committed existence must
            # not let the planning-record existence check replace _blob safety.
            unusual = "docs/superpowers/plans/real\\plan.md"
            valid = "docs/superpowers/plans/évidence plan.md"
            for path in (unusual, valid):
                (root / path).write_text(plan_text)
            r._run_git(root, ["add", "."])
            r._run_git(root, ["commit", "-m", "real unusual planning files"])

            def commit_ref(path):
                task["pre_implementation"]["plan_ref"] = path
                (root / task["task_ref"]).write_text(json.dumps(task))
                r._run_git(root, ["add", task["task_ref"]])
                r._run_git(root, ["commit", "-m", "planning reference fixture"])
                return r._run_git(root, ["rev-parse", "HEAD"]).strip()

            base = commit_ref(valid)
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
            self.assertEqual(trusted["artifacts"][valid], plan_text.encode())
            contract = {key: trusted["task"][key] for key in r.CONTRACT_FIELDS}
            expected = {
                "run_id": "r", "task_id": task["task_id"], "agent_name": "architect",
                "subject_sha": base, "role": "architecture", "task_contract": contract,
                "check_ids": [], "artifact_ids": [],
            }
            response = {
                "schema_version": 2, "run_id": "r", "task_id": task["task_id"],
                "agent_name": "architect", "subject_sha": base, "decision": "pass",
                "summary": "planned", "task_contract": copy.deepcopy(contract),
                "findings": [], "assessments": [], "evidence_ids": [],
            }
            self.assertEqual(
                r.validate_agent_response(response, trusted["schema"], expected), []
            )
            for path in (*UNSAFE_PATHS, ".", unusual):
                with self.subTest(architect_plan_ref=path):
                    response["task_contract"]["pre_implementation"]["plan_ref"] = path
                    self.assertIn(
                        "architect changed frozen task_contract",
                        r.validate_agent_response(response, trusted["schema"], expected),
                    )
            for path, error in (
                (unusual, "unsafe trusted input path"),
                ("./" + original, "unsafe trusted input path"),
                ("/" + original, "outside the configured plan paths"),
                ("docs/superpowers/plans/../plan.md", "outside the configured plan paths"),
                ("docs/superpowers/plans/nul\x00.md", "outside the configured plan paths"),
                (".", "outside the configured plan paths"),
            ):
                with self.subTest(committed_plan_ref=path):
                    base = commit_ref(path)
                    # The unusual filename and ./ alias both resolve to real
                    # committed blobs before the authoritative safe_ref boundary.
                    if error == "unsafe trusted input path":
                        self.assertEqual(
                            r._run_git(root, ["show", f"{base}:{path}"]), plan_text
                        )
                    with self.assertRaisesRegex(r.RunnerError, error):
                        r.load_trusted_inputs(root, base, task["task_ref"])

    def test_loaded_evaluator_cannot_self_certify_candidate_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "descendant"],
                cwd=root,
                capture_output=True,
                check=True,
            )
            # Pinning a different evaluator blob must be detected, not read as candidate authority.
            (root / "scripts/autonomy/runner.py").write_text("# alternate evaluator\n")
            subprocess.run(
                ["git", "add", "."], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "changed evaluator"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            candidate = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            with self.assertRaisesRegex(r.RunnerError, "loaded evaluator differs"):
                r.load_trusted_inputs(root, candidate, task["task_ref"])


class IntegrityEdgeTests(unittest.TestCase):
    def test_claimed_exec_session_config_does_not_certify_app_server(self):
        with self.assertRaises(r.app_server.ProtocolError):
            r.app_server.replay_capture(b'{"type":"session_config","model":"gpt-6.1-sol"}\n',stdout=b'',expected={})

    def test_candidate_keeps_canonical_documentation_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            (root / "outside.md").write_text("outside canonical docs")
            subprocess.run(
                ["git", "add", "outside.md"], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "outside docs"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            candidate = r._run_git(root, ["rev-parse", "HEAD"]).strip()
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
            result = r.inspect_candidate(
                root, base, candidate, "implementation", ["outside.md"], trusted
            )
            self.assertTrue(
                any(
                    f["finding_id"] == "runner.documentation-scope"
                    for f in result["findings"]
                )
            )

    def test_undeclared_directory_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            check = {
                "check_id": "dirs",
                "gate": "security",
                "argv": [
                    "python3",
                    "-c",
                    'import os;os.mkdir(os.environ["AUTODATA_EVIDENCE_ROOT"]+"/undeclared")',
                ],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            _, _, findings = r.execute_required_checks(
                root, SHA, [check], root / "out", dict(os.environ)
            )
            self.assertTrue(any(f["blocking"] for f in findings))

    def test_later_setup_failure_preserves_earlier_check_evidence(self):
        for failure in ("unsafe-cwd", "symlink-cwd", "staging-mkdir"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                work = root / "work"
                work.mkdir()
                output = root / "out"
                checks = [
                    {
                        "check_id": cid,
                        "gate": "security",
                        "argv": ["python3", "-c", 'print("retained")'],
                        "cwd": ".",
                        "timeout_seconds": 2,
                        "expected_exit_code": 0,
                        "outputs": [],
                    }
                    for cid in ("first", "second")
                ]
                if failure == "unsafe-cwd":
                    checks[1]["cwd"] = "../outside"
                elif failure == "symlink-cwd":
                    (work / "linked").symlink_to(root, target_is_directory=True)
                    checks[1]["cwd"] = "linked"
                else:
                    stage = output / "staging" / "second"
                    stage.mkdir(parents=True)
                commands, artifacts, findings = r.execute_required_checks(
                    work, SHA, checks, output, dict(os.environ)
                )
                self.assertEqual([c["check_id"] for c in commands], ["first"])
                self.assertEqual(commands[0]["exit_code"], 0)
                self.assertEqual(
                    {a["artifact_id"] for a in artifacts},
                    {"first:stdout", "first:stderr", "first:command"},
                )
                self.assertTrue(
                    all(not r.validate_artifact(a, output) for a in artifacts)
                )
                self.assertTrue(
                    any(
                        f["blocking"] and f["finding_id"] == "runner.second.setup"
                        for f in findings
                    ),
                    findings,
                )

    def test_cleanup_failure_keeps_command_and_artifact_records(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            work = root / "work"
            work.mkdir()
            check = {
                "check_id": "c",
                "gate": "security",
                "argv": ["python3", "-c", 'print("retained")'],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            with patch(
                "runner.shutil.rmtree", side_effect=OSError("fixture cleanup failure")
            ):
                commands, artifacts, findings = r.execute_required_checks(
                    work, SHA, [check], root / "out", dict(os.environ)
                )
            self.assertEqual(commands[0]["exit_code"], 0)
            self.assertEqual(len(artifacts), 3)
            self.assertTrue(any(f["finding_id"] == "runner.cleanup" for f in findings))

    def test_schema_profile_constants_cannot_drift(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        bad = copy.deepcopy(schema)
        bad["properties"] = {}
        self.assertTrue(r.validate_schema_inventory(bad))
        for name, field, value in [
            ("Execution", "model", "other"),
            ("Features", "fast_mode", False),
            ("CommandRecord", "schema_version", 1),
        ]:
            bad = copy.deepcopy(schema)
            bad["$defs"][name]["properties"][field]["const"] = value
            self.assertTrue(r.validate_schema_inventory(bad))

    def test_symlink_staging_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outside = root / "outside"
            outside.mkdir()
            (outside / "payload").write_text("payload")
            stage = root / "stage"
            stage.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(r.RunnerError):
                r.retain_artifact(
                    stage, "payload", root / "out", "p", "test-result", SHA, None
                )

    def test_response_malformed_primitives_return_errors(self):
        expected = {
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "role": "verification",
            "check_ids": [],
            "artifact_ids": [],
        }
        good = {
            "schema_version": 2,
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "decision": "pass",
            "summary": "ok",
            "task_contract": None,
            "findings": [],
            "assessments": [],
            "evidence_ids": [],
        }
        for key in good:
            for invalid in ({"nested": "invalid"}, True, 42):
                value = {**good, key: invalid}
                self.assertTrue(
                    r.validate_agent_response(value, {}, expected), (key, invalid)
                )

    def test_dirty_check_is_retained(self):
        # Full chain tests cover the process boundary; here the mutation is a real check.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
            root = Path(d)
            task, base = make_trusted_repository(root)
            check = {
                "check_id": "dirty",
                "gate": "security",
                "argv": ["python3", "-c", 'open("app.txt","w").write("dirty")'],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            _, _, findings = r.execute_required_checks(
                root, base, [check], Path(out), dict(os.environ)
            )
            self.assertTrue(
                any(f["finding_id"] == "runner.check-dirty-tree" for f in findings)
            )


if __name__ == "__main__":
    unittest.main()


class AppServerIntegrationTests(unittest.TestCase):
    def test_prompt_exposes_empty_architect_assignment_and_exact_gate_assignment(self):
        self.assertTrue(hasattr(r, "build_agent_prompt"), "explicit assignment prompt missing")
        from test_app_server_adapter import expected_context
        envelope={"agent_name":"autodata-architect","gate":None}
        prompt=r.build_agent_prompt("architect prompt", envelope, [], [], {}, role="architecture")
        self.assertEqual(json.JSONDecoder().raw_decode(prompt.split("ASSIGNED CHECK IDS:\n")[1])[0], [])
        self.assertIn('assessments must be exactly []',prompt)
        envelope["gate"]="security"
        prompt=r.build_agent_prompt("gate prompt", envelope, [], [], {}, role="verification", check_ids=["security-check"])
        self.assertEqual(json.JSONDecoder().raw_decode(prompt.split("ASSIGNED CHECK IDS:\n")[1])[0],["security-check"])

    def test_adapter_loaded_bytes_are_frozen_and_protected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task,base=make_trusted_repository(root)
            trusted=r.load_trusted_inputs(root,base,task["task_ref"])
            self.assertIn("scripts/autonomy/app_server_adapter.py",list(trusted["artifacts"]))
            changed=root/"scripts/autonomy/app_server_adapter.py"
            changed.write_text("# replaced adapter\n")
            subprocess.run(["git","add","."],cwd=root,check=True,capture_output=True)
            subprocess.run(["git","commit","-m","replace adapter"],cwd=root,check=True,capture_output=True)
            subject=r._run_git(root,["rev-parse","HEAD"]).strip()
            report=r.inspect_candidate(root,base,subject,"implementation",["scripts/autonomy/**"],trusted)
            self.assertTrue(any(x["finding_id"]=="runner.protected-path" for x in report["findings"]))

class CallerSignalTests(unittest.TestCase):
    def test_sigterm_after_real_turn_ids_preserves_interrupted_manifest_and_cleanup(self):
        import signal
        self._check_caller_signal(signal.SIGTERM)

    def test_sigint_after_real_turn_ids_preserves_interrupted_manifest_and_cleanup(self):
        import signal
        self._check_caller_signal(signal.SIGINT)

    def _check_caller_signal(self, signum):
        import inspect
        import signal
        import time
        self.assertIn('progress',inspect.signature(r.app_server.run_app_server).parameters,
                      'live protocol and caller signal support missing')
        from test_app_server_adapter import fake_codex
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'repo';repo.mkdir();task,base=make_trusted_repository(repo)
            bindir=fake_codex(root);output=root/'run'
            env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],
                 'CODEX_HOME':'/tmp/codex-disposable','FAKE_CODEX_MODE':'interrupt',
                 'PYTHONPATH':str(Path(__file__).parent),'PYTHONDONTWRITEBYTECODE':'1'}
            script=root/'caller.py'
            script.write_text('''import json,sys
from pathlib import Path
import runner as r
from test_app_server_adapter import boundary
repo=Path(sys.argv[1]);output=Path(sys.argv[2]);base=sys.argv[3]
task=json.loads((repo/'docs/agents/tasks/fixture.json').read_text())
trusted=r.load_trusted_inputs(repo,base,task['task_ref'])
r.app_server.validate_boundary=lambda path,cwd,env:boundary(cwd)
envelope={'run_id':'signal-architect','task_id':task['task_id'],'repository':task['repository'],'base_sha':base,'subject_sha':base,'trusted_base_sha':base,'task_ref':task['task_ref'],'agent_name':'autodata-architect','task_contract':{k:task[k] for k in r.CONTRACT_FIELDS},'allowed_paths':[],'deployment_target':'none','execution':task['execution'],'evidence_label':'architect','response_artifact_id':'architect:response','gate':None}
r.run_agent(repo,envelope,'local-cli',output,12,trusted=trusted)
''')
            caller=subprocess.Popen([sys.executable,str(script),str(repo),str(output),base],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                deadline=time.monotonic()+5;seen=False
                while time.monotonic()<deadline and caller.poll() is None:
                    progress=output/'provider-protocol-progress.jsonl'
                    if progress.exists():
                        for line in progress.read_text().splitlines():
                            try:
                                rec=json.loads(line);frame=json.loads(rec.get('raw','{}'))
                            except ValueError:continue
                            if rec.get('direction')=='server' and frame.get('method')=='turn/started':seen=True
                    if seen:break
                    time.sleep(.02)
                if not seen and caller.poll() is not None:
                    out,err=caller.communicate(timeout=1)
                    diagnostic=(output/'run-manifest.json').read_text() if (output/'run-manifest.json').exists() else ''
                    self.fail('no real turn identity observed: '+repr((out,err))+diagnostic)
                self.assertTrue(seen,'no real turn identity observed')
                caller.send_signal(signum)
                stdout,stderr=caller.communicate(timeout=4)
                self.assertEqual(caller.returncode,0,(stdout,stderr))
                manifest=json.loads((output/'run-manifest.json').read_text())
                self.assertEqual(manifest['agent_decision'],'blocked')
                self.assertEqual(manifest['provider_command']['status'],'unavailable')
                self.assertEqual(r._command_errors(manifest['provider_command']),[])
                self.assertEqual(manifest['provider_runtime_validation'],'blocked')
                self.assertFalse((output/'worktree').exists())
                protocol=next(x for x in manifest['artifacts'] if x['artifact_id']=='architect:protocol')
                records=[json.loads(x) for x in (output/protocol['ref']).read_text().splitlines()]
                self.assertEqual(records[-1]['status'],'interrupted')
                with self.assertRaises(ProcessLookupError):os.kill(records[0]['process_id'],0)
                self.assertTrue(any(x.get('direction')=='client' and json.loads(x['raw']).get('method')=='turn/interrupt' for x in records))
            finally:
                if caller.poll() is None:os.killpg(caller.pid,signal.SIGKILL)
                caller.communicate(timeout=3)
