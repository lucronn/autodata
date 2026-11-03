"""Inline synthetic parser tests; these are never product acceptance evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_acceptance as assembler

BASE = '0e21f6dbdf5ad0402b8bef42d3e1f2566964b309'
TASK = 'docs/agents/tasks/2026-11-03-production-release/r6-release.json'
POLICY = '798e91b9854098a706ea4ab66a414492c044059a1c98edb9d2f1d003e3baad98'
GATES = ('deterministic_ci', 'contract_compatibility', 'schema_integrity',
         'source_provenance', 'data_quality', 'security', 'reliability', 'independent_review')


def available_committed_base():
    """CI checks out one commit; test the committed task reachable there."""
    result = subprocess.run(['/usr/bin/git', 'rev-parse', 'HEAD'],
                            cwd=assembler.REPO_ROOT,
                            env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent'},
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


TRUSTED_BASE = available_committed_base()


def committed_envelope():
    item = synthetic_envelope()
    item['trusted_base_sha'] = TRUSTED_BASE
    return item


def synthetic_envelope():
    return dict(contract='workshop-product-evidence-v1', schema_version=1,
                candidate_sha=BASE, trusted_base_sha=BASE, requested_tier='fixture',
                task_ref=TASK, policy_sha256=POLICY,
                bindings={key: 'proof' for key in ('source_manifest_artifact',
                    'migration_manifest_artifact', 'production_images_artifact', 'sdk_provenance_artifact')},
                artifacts=[dict(artifact_id='proof', kind='manifest', ref='proof.json',
                    sha256=hashlib.sha256(b'{}').hexdigest(), bytes=2, visibility='private')],
                slots=[], eight_reports=[dict(gate_id=gate, candidate_sha=BASE, scope='fixture',
                    verdict='pending', author_id=None, reviewer_id=None, artifact_ids=['proof'],
                    findings=[], reason_code='missing') for gate in GATES])


class EnvelopeTests(unittest.TestCase):
    def parse(self, value):
        return assembler.parse_envelope(json.dumps(value).encode())

    def test_synthetic_structural_input_is_not_verification(self):
        self.assertEqual(self.parse(synthetic_envelope())['candidate_sha'], BASE)

    def test_json_limits_duplicates_utf8_and_nonfinite_are_rejected(self):
        for raw in (b'{}' * (1024 * 1024 + 1), b'\xff', b'[]', b'{',
                    b'{"contract":1,"contract":2}',
                    b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":-Infinity}', b'{"x":1e999}', b'{"x":"\\ud800"}'):
            with self.subTest(raw=raw[:40]), self.assertRaises(assembler.ContractError):
                assembler.parse_envelope(raw)

    def test_envelope_independent_mutations_are_rejected(self):
        mutations = [('schema_version', True), ('schema_version', 2), ('candidate_sha', 'A'*40),
                     ('trusted_base_sha', 'x'), ('policy_sha256', '0'*63),
                     ('requested_tier', 'production'), ('contract', 'other'), ('task_ref', '../task'),
                     ('unknown', True), ('artifacts', {}), ('slots', None), ('bindings', [])]
        for key, value in mutations:
            item = synthetic_envelope(); item[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(assembler.ContractError):
                self.parse(item)

    def test_artifact_and_binding_mutations_are_rejected(self):
        for key, value in [('artifact_id', 'Proof'), ('kind', 'executable'), ('bytes', True),
                           ('bytes', -1), ('sha256', 'z'*64), ('visibility', 'secret'),
                           ('unknown', 1), ('ref', '/tmp/proof'), ('ref', 'a/../b'),
                           ('ref', 'a//b'), ('ref', 'a/./b'), ('ref', 'a\\b'),
                           ('ref', 'a\x00b'), ('ref', 'https://example.com/proof')]:
            item = synthetic_envelope(); item['artifacts'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(assembler.ContractError):
                self.parse(item)
        for mutate in ('duplicate_id', 'duplicate_ref', 'missing_binding', 'unknown_binding', 'unknown_ref'):
            item = synthetic_envelope()
            if mutate.startswith('duplicate'):
                other = copy.deepcopy(item['artifacts'][0])
                other['ref' if mutate == 'duplicate_id' else 'artifact_id'] = 'other'
                item['artifacts'].append(other)
            elif mutate == 'missing_binding': del item['bindings']['source_manifest_artifact']
            elif mutate == 'unknown_binding': item['bindings']['unknown'] = 'proof'
            else: item['bindings']['source_manifest_artifact'] = 'absent'
            with self.subTest(mutate=mutate), self.assertRaises(assembler.ContractError): self.parse(item)

    def test_two_mebibyte_boundary_is_inclusive(self):
        raw = json.dumps(synthetic_envelope()).encode()
        bounded = raw + b' ' * (2 * 1024 * 1024 - len(raw))
        self.assertEqual(assembler.parse_envelope(bounded)['candidate_sha'], BASE)
        with self.assertRaises(assembler.ContractError): assembler.parse_envelope(bounded + b' ')

    def test_utc_rfc3339_offsets_and_fraction_order_are_preserved(self):
        item = self.with_slot()
        item['slots'][0].update(started_at='2026-11-03T00:00:00.000000001+00:00',
                                finished_at='2026-11-03T00:00:00.000000002Z')
        self.assertEqual(self.parse(item)['slots'][0]['exit_code'], 0)
        item['slots'][0].update(started_at='2026-11-03T00:00:00.000000002Z',
                                finished_at='2026-11-03T00:00:00.000000001Z')
        with self.assertRaises(assembler.ContractError): self.parse(item)


    def test_reports_and_findings_reject_unknown_types_duplicates_and_aliases(self):
        for key, value in [('scope', 'production'), ('gate_id', 'other'), ('candidate_sha', '1'*40),
                           ('verdict', 'success'), ('reason_code', 'whatever'), ('author_id', ''),
                           ('reviewer_id', 1), ('artifact_ids', ['proof', 'proof']), ('extra', True)]:
            item = synthetic_envelope(); item['eight_reports'][0][key] = value
            with self.subTest(key=key), self.assertRaises(assembler.ContractError): self.parse(item)
        item = synthetic_envelope(); item['eight_reports'][1] = copy.deepcopy(item['eight_reports'][0])
        with self.assertRaises(assembler.ContractError): self.parse(item)
        for key, value in [('blocking', 1), ('severity', 'urgent'), ('status', 'closed'),
                           ('finding_id', 'BAD'), ('artifact_ids', ['absent']), ('extra', 1)]:
            finding = dict(finding_id='finding.one', blocking=True, severity='medium', status='open', artifact_ids=['proof'])
            finding[key] = value; item = synthetic_envelope(); item['eight_reports'][0]['findings'] = [finding]
            with self.subTest(key=key), self.assertRaises(assembler.ContractError): self.parse(item)

    def slot(self):
        return dict(slot_id='fixture.identity', kind='identity', scope='fixture', candidate_sha=BASE,
                    profile_sha256='0'*64, result_artifact='result', host_receipt_artifact='host',
                    raw_artifact_ids=['proof'], command=dict(argv=['never-execute'], sha256=hashlib.sha256(b'["never-execute"]').hexdigest()),
                    started_at='2026-11-03T00:00:00Z', finished_at='2026-11-03T00:00:01Z',
                    deadline_seconds=2, exit_code=0, timed_out=False)

    def with_slot(self):
        item = synthetic_envelope()
        for name, kind in [('result', 'collector_result'), ('host', 'host_receipt')]:
            artifact = copy.deepcopy(item['artifacts'][0]); artifact.update(artifact_id=name, kind=kind, ref=name+'.json')
            item['artifacts'].append(artifact)
        item['slots'] = [self.slot()]
        return item

    def test_slot_contract_and_failure_records_are_preserved(self):
        item = self.with_slot(); item['slots'][0]['exit_code'] = 1
        self.assertEqual(self.parse(item)['slots'][0]['exit_code'], 1)
        for key, value in [('slot_id', 'fixture.other'), ('scope', 'staging'), ('kind', 'other'),
                           ('exit_code', True), ('timed_out', 0), ('deadline_seconds', True),
                           ('deadline_seconds', 0), ('candidate_sha', '1'*40), ('profile_sha256', None),
                           ('result_artifact', 'proof'), ('raw_artifact_ids', ['proof', 'proof']),
                           ('started_at', '2026-11-03'), ('finished_at', '2026-11-02T00:00:00Z'),
                           ('unknown', 1), ('command', dict(argv=['never-execute'], sha256='0'*64))]:
            item = self.with_slot(); item['slots'][0][key] = value
            with self.subTest(key=key), self.assertRaises(assembler.ContractError): self.parse(item)
        item = self.with_slot(); item['slots'].append(copy.deepcopy(item['slots'][0]))
        with self.assertRaises(assembler.ContractError): self.parse(item)

    def test_wrong_primitives_at_each_nested_boundary_are_contract_errors(self):
        paths = [('bindings', 'source_manifest_artifact'), ('artifacts', 0, 'artifact_id'),
                 ('artifacts', 0, 'ref'), ('artifacts', 0, 'sha256'), ('artifacts', 0, 'kind'),
                 ('artifacts', 0, 'visibility'), ('eight_reports', 0, 'artifact_ids'),
                 ('eight_reports', 0, 'findings'), ('eight_reports', 0, 'gate_id')]
        for path in paths:
            for value in (None, True, 1, [], {}):
                if value == [] and path[-1] in ('artifact_ids', 'findings'):
                    continue
                item = synthetic_envelope(); target = item
                for part in path[:-1]: target = target[part]
                target[path[-1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(assembler.ContractError):
                    self.parse(item)

    def test_fixture_request_cannot_relabel_a_report_as_staging(self):
        item = synthetic_envelope(); item['eight_reports'][0]['scope'] = 'staging'
        with self.assertRaises(assembler.ContractError): self.parse(item)


    def test_duplicate_and_unknown_keys_at_each_nested_object_are_rejected(self):
        for path in [('bindings',), ('artifacts', 0), ('slots', 0), ('slots', 0, 'command'),
                     ('eight_reports', 0), ('eight_reports', 0, 'findings', 0)]:
            item = self.with_slot()
            item['eight_reports'][0]['findings'] = [dict(finding_id='one', severity='low', blocking=False,
                                                        status='open', artifact_ids=['proof'])]
            target = item
            for part in path: target = target[part]
            target['unknown'] = True
            with self.subTest(path=path), self.assertRaises(assembler.ContractError): self.parse(item)
        item = self.with_slot()
        raw = json.dumps(item).replace('"argv": ["never-execute"]',
                                       '"argv": ["never-execute"], "argv": ["never-execute"]')
        with self.assertRaises(assembler.ContractError): assembler.parse_envelope(raw.encode())


class TrustedBoundaryTests(unittest.TestCase):
    def test_actual_unpromoted_task_is_diagnostic_only(self):
        trust = assembler.load_trusted(TRUSTED_BASE, TASK, 'fixture')
        item = assembler.parse_envelope(json.dumps(committed_envelope()).encode())
        for mode, code, status in [('plan', 0, 'planned'), ('validate', 3, 'unavailable')]:
            result, exit_code = assembler.assemble(item, trust, mode)
            self.assertEqual((exit_code, result['status']), (code, status))
            self.assertEqual(result['derived_counts']['total'], 0)
            for flag in ('fixture_verified', 'product_candidate_verified', 'staging_verified', 'deployment_authorized', 'cutover_verified'):
                self.assertIs(result[flag], False)
            self.assertTrue(result['missing_slots'])

    def test_invocation_cannot_be_selected_by_manifest(self):
        trust = assembler.load_trusted(TRUSTED_BASE, TASK, 'fixture')
        for key, value in [('trusted_base_sha', '1'*40), ('task_ref', 'other/task.json'),
                           ('requested_tier', 'staging'), ('policy_sha256', '0'*64)]:
            item = committed_envelope(); item[key] = value
            with self.subTest(key=key), self.assertRaises(assembler.ContractError):
                assembler.assemble(assembler.parse_envelope(json.dumps(item).encode()), trust, 'plan')
        for base, task, tier in [('HEAD', TASK, 'fixture'), (TRUSTED_BASE, '../task', 'fixture'), (TRUSTED_BASE, TASK, 'production')]:
            with self.assertRaises(assembler.ContractError): assembler.load_trusted(base, task, tier)

    def test_committed_profile_unknown_keys_wrong_types_and_promotion_are_rejected(self):
        raw = assembler.git_read(TRUSTED_BASE, TASK)
        task = json.loads(raw)
        mutations = [('schema_version', True), ('contract', 'other'), ('assembler_ref', '../tool.py'),
                     ('assembler_sha256', 'bad'), ('evaluator_sha256', '0'*64),
                     ('policy_sha256', '0'*64), ('supervisor_profiles', {}),
                     ('bindings_profile', dict(enabled=0)), ('enabled_tiers', ['fixture']),
                     ('slot_profiles', []), ('report_profile', dict(enabled=False, gate_ids=[])),
                     ('ci_profile', dict(enabled=False, workflow_sha256='0'*64, dto_upload_required=True)),
                     ('unknown', True)]
        original_read = assembler.git_read
        for key, value in mutations:
            changed = copy.deepcopy(task); changed['product_evidence'][key] = value
            def read(base, ref):
                return json.dumps(changed).encode() if ref == TASK else original_read(base, ref)
            with self.subTest(key=key), patch.object(assembler, 'git_read', side_effect=read):
                with self.assertRaises(assembler.ContractError): assembler.load_trusted(TRUSTED_BASE, TASK, 'fixture')

    def test_fabricated_pass_claims_cannot_enable_any_tier(self):
        for tier in ('fixture', 'staging'):
            item = committed_envelope(); item['requested_tier'] = tier
            for report in item['eight_reports']:
                report.update(verdict='pass', author_id='invented.author', reviewer_id='invented.reviewer', reason_code=None)
            parsed = assembler.parse_envelope(json.dumps(item).encode())
            trusted = assembler.load_trusted(TRUSTED_BASE, TASK, tier)
            result, code = assembler.assemble(parsed, trusted, 'validate')
            self.assertEqual(code, 3)
            self.assertTrue(all(result[flag] is False for flag in ('fixture_verified', 'product_candidate_verified',
                'staging_verified', 'deployment_authorized', 'cutover_verified')))
            self.assertTrue(all(value == 0 for value in result['derived_counts'].values()))


    def test_cli_actual_planning_task_returns_unavailable_and_redacts_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'envelope.json'; path.write_text(json.dumps(committed_envelope()))
            command = [sys.executable, str(Path(__file__).with_name('release_acceptance.py')), 'validate',
                       '--manifest', str(path), '--evidence-root', directory,
                       '--trusted-base-sha', TRUSTED_BASE, '--task-ref', TASK, '--requested-tier', 'fixture']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'unavailable')
            path.write_text('{"SECRET_PRIVATE_TOKEN":NaN}')
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('SECRET_PRIVATE_TOKEN', run.stdout+run.stderr)


if __name__ == '__main__': unittest.main()
