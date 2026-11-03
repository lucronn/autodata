"""Inline synthetic parser tests; these are never product acceptance evidence."""
import copy
import hashlib
import io
import json
import os
import stat
import struct
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import DEFAULT, patch

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


class ArtifactStoreTests(unittest.TestCase):
    """Synthetic local transport tests; no raw producer profile is promoted."""
    def artifact(self, ref='proof.json', raw=b'{}', artifact_id='proof'):
        return dict(artifact_id=artifact_id, kind='manifest', ref=ref,
                    sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), visibility='private')

    def test_confined_file_reads_are_fresh_and_json_identity_is_data_only(self):
        raw = json.dumps(dict(candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE,
                              profile_sha256='1'*64, command=['never-execute'])).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'proof.json').write_bytes(raw)
            with assembler.ArtifactStore(root, [self.artifact(raw=raw)]) as store:
                self.assertEqual(store.read('proof'), raw)
                value = store.read_identity_json('proof', candidate_sha=BASE,
                    trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64)
                self.assertEqual(value['command'], ['never-execute'])
                self.assertEqual(store.read('proof'), raw)

    def test_symlink_leaf_directory_root_and_root_ancestor_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory); root = parent/'root'; root.mkdir()
            outside = parent/'outside'; outside.mkdir(); (outside/'proof.json').write_bytes(b'{}')
            (root/'proof.json').symlink_to(outside/'proof.json')
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(root, [self.artifact()])
            with self.assertRaises(assembler.ContractError):
                assembler.ArtifactStore(str(root)+'/../outside', [self.artifact()])
            (root/'proof.json').unlink(); (root/'child').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(root, [self.artifact('child/proof.json')])
            linked = parent/'linked'; linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(linked, [self.artifact()])
            (outside/'nested').mkdir(); (outside/'nested'/'proof.json').write_bytes(b'{}')
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(linked/'nested', [self.artifact()])

    def test_special_missing_extra_and_hardlinked_inventory_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'proof.json'
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(root, [self.artifact()])
            os.mkfifo(path)
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(root, [self.artifact()])
            path.unlink(); path.write_bytes(b'{}'); (root/'extra').write_bytes(b'private')
            with self.assertRaises(assembler.ContractError): assembler.ArtifactStore(root, [self.artifact()])
            (root/'extra').unlink(); os.link(path, root/'alias.json')
            with self.assertRaises(assembler.ContractError):
                assembler.ArtifactStore(root, [self.artifact(), self.artifact('alias.json', artifact_id='alias')])

    def test_duplicate_ids_refs_and_unsafe_refs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'proof.json').write_bytes(b'{}')
            for records in ([self.artifact(), self.artifact('other.json')],
                            [self.artifact(), self.artifact(artifact_id='other')],
                            [self.artifact('../proof.json')], [self.artifact('/proof.json')],
                            [self.artifact('child\\proof.json')], [self.artifact('a/./proof.json')]):
                with self.subTest(records=records), self.assertRaises(assembler.ContractError):
                    assembler.ArtifactStore(root, records)

    def test_size_hash_and_declared_limits_fail_before_unbounded_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'proof.json').write_bytes(b'{}')
            for artifact in (self.artifact(raw=b'x'), dict(self.artifact(), sha256='0'*64)):
                with self.subTest(artifact=artifact), self.assertRaises(assembler.ContractError):
                    with assembler.ArtifactStore(root, [artifact]) as store: store.read('proof')
            with patch.object(assembler.os, 'read', side_effect=AssertionError('must not read')):
                with self.assertRaises(assembler.ContractError):
                    assembler.ArtifactStore(root, [self.artifact()], max_file_bytes=1)
                (root/'second.json').write_bytes(b'{}')
                with self.assertRaises(assembler.ContractError):
                    assembler.ArtifactStore(root, [self.artifact(), self.artifact('second.json', artifact_id='second')],
                                            max_file_bytes=2, max_total_bytes=3)

    def test_inode_content_inventory_and_root_drift_fail_on_reread(self):
        for mutation in ('inode', 'content', 'extra', 'root'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory); root = parent/'root'; root.mkdir()
                path = root/'proof.json'; path.write_bytes(b'{}')
                with assembler.ArtifactStore(root, [self.artifact()]) as store:
                    self.assertEqual(store.read('proof'), b'{}')
                    if mutation == 'inode':
                        replacement = parent/'replacement'; replacement.write_bytes(b'{}'); replacement.replace(path)
                    elif mutation == 'content': path.write_bytes(b'[]')
                    elif mutation == 'extra': (root/'extra').write_bytes(b'private')
                    else:
                        root.rename(parent/'old'); root.mkdir(); (root/'proof.json').write_bytes(b'{}')
                    with self.assertRaises(assembler.ContractError): store.read('proof')

    def test_mutation_during_read_and_between_read_and_parse_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'proof.json'; path.write_bytes(b'{}')
            original_read = assembler.os.read
            with assembler.ArtifactStore(root, [self.artifact()]) as store:
                changed = False
                def read(fd, count):
                    nonlocal changed
                    result = original_read(fd, count)
                    if not changed:
                        changed = True; path.write_bytes(b'[]')
                    return result
                with patch.object(assembler.os, 'read', side_effect=read):
                    with self.assertRaises(assembler.ContractError): store.read('proof')
            path.write_bytes(b'{}')
            original_parse = assembler.strict_json
            with assembler.ArtifactStore(root, [self.artifact()]) as store:
                def parse(raw):
                    value = original_parse(raw); path.write_bytes(b'[]'); return value
                with patch.object(assembler, 'strict_json', side_effect=parse):
                    with self.assertRaises(assembler.ContractError):
                        store.read_identity_json('proof', candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE)

    def test_declared_raw_candidate_base_and_profile_ids_must_match(self):
        expected = dict(candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64)
        for field in expected:
            for wrong in ('2'*len(expected[field]), None, True, []):
                raw = json.dumps(dict(expected, **{field: wrong})).encode()
                with self.subTest(field=field, wrong=wrong), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); (root/'proof.json').write_bytes(raw)
                    with assembler.ArtifactStore(root, [self.artifact(raw=raw)]) as store:
                        with self.assertRaises(assembler.ContractError): store.read_identity_json('proof', **expected)

    def test_nested_regular_files_and_immutable_declaration_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'nested').mkdir(); (root/'nested'/'proof.json').write_bytes(b'{}')
            declaration = self.artifact('nested/proof.json')
            with assembler.ArtifactStore(root, [declaration]) as store:
                declaration.update(ref='../outside', bytes=100, sha256='0'*64)
                self.assertEqual(store.read('proof'), b'{}')
                value = store.read_identity_json('proof', candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE)
                self.assertEqual(value, {})  # Missing identities remain missing.
            (root/'empty-undeclared').mkdir()
            with self.assertRaises(assembler.ContractError):
                assembler.ArtifactStore(root, [self.artifact('nested/proof.json')])

    def test_nested_declared_identity_and_malformed_raw_json_are_rejected(self):
        for raw in (b'{"nested":[{"candidate_sha":"'+b'2'*40+b'"}]}',
                    b'{"candidate_sha":"'+BASE.encode()+b'","candidate_sha":"'+BASE.encode()+b'"}',
                    b'{"x":NaN}', b'\xff'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); (root/'proof.json').write_bytes(raw)
                with assembler.ArtifactStore(root, [self.artifact(raw=raw)]) as store:
                    with self.assertRaises(assembler.ContractError):
                        store.read_identity_json('proof', candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE)

    def test_read_permission_error_is_a_static_transport_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'proof.json').write_bytes(b'{}')
            with assembler.ArtifactStore(root, [self.artifact()]) as store:
                original_open = assembler.os.open
                def denied(path, flags, **kwargs):
                    if path == 'proof.json': raise PermissionError('PRIVATE_PATH')
                    return original_open(path, flags, **kwargs)
                with patch.object(assembler.os, 'open', side_effect=denied):
                    with self.assertRaisesRegex(assembler.ContractError, '^evidence_unavailable$'):
                        store.read('proof')

    def test_undeclared_reads_and_closed_store_fail_without_leaking_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'proof.json').write_bytes(b'{}')
            with assembler.ArtifactStore(root, [self.artifact()]) as store:
                with self.assertRaises(assembler.ContractError): store.read('not-declared')
            with self.assertRaises(assembler.ContractError): store.read('proof')


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


    def test_disabled_slot_profile_hash_must_match_committed_profile(self):
        item = EnvelopeTests().with_slot(); item['trusted_base_sha'] = TRUSTED_BASE
        trusted = assembler.load_trusted(TRUSTED_BASE, TASK, 'fixture')
        parsed = assembler.parse_envelope(json.dumps(item).encode())
        with self.assertRaises(assembler.ContractError): assembler.assemble(parsed, trusted, 'plan')
        item['slots'][0]['profile_sha256'] = hashlib.sha256(
            b'{"enabled":false,"expected_cases":5,"slot_id":"fixture.identity"}').hexdigest()
        result, code = assembler.assemble(assembler.parse_envelope(json.dumps(item).encode()), trusted, 'validate')
        self.assertEqual((code, result['status']), (3, 'unavailable'))

    def test_plan_performs_no_evidence_root_io_and_integrity_does_not_promote(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory); manifest = parent/'envelope.json'
            manifest.write_text(json.dumps(committed_envelope()))
            root = parent/'raw'
            command = [sys.executable, str(Path(__file__).with_name('release_acceptance.py')), 'plan',
                       '--manifest', str(manifest), '--evidence-root', str(root),
                       '--trusted-base-sha', TRUSTED_BASE, '--task-ref', TASK, '--requested-tier', 'fixture']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'planned')
            command[2] = 'validate'
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            root.mkdir(); (root/'proof.json').write_bytes(b'{}')
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 3)
            self.assertFalse(json.loads(run.stdout)['fixture_verified'])
            (root/'PRIVATE_EXTRA_FILE').write_bytes(b'SECRET_PRIVATE_CONTENT')
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('PRIVATE_EXTRA_FILE', run.stdout+run.stderr)
            self.assertNotIn('SECRET_PRIVATE_CONTENT', run.stdout+run.stderr)

    def test_cli_actual_planning_task_returns_unavailable_and_redacts_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'envelope.json'; path.write_text(json.dumps(committed_envelope()))
            root = Path(directory)/'raw'; root.mkdir(); (root/'proof.json').write_bytes(b'{}')
            command = [sys.executable, str(Path(__file__).with_name('release_acceptance.py')), 'validate',
                       '--manifest', str(path), '--evidence-root', str(root),
                       '--trusted-base-sha', TRUSTED_BASE, '--task-ref', TASK, '--requested-tier', 'fixture']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'unavailable')
            path.write_text('{"SECRET_PRIVATE_TOKEN":NaN}')
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('SECRET_PRIVATE_TOKEN', run.stdout+run.stderr)


class RawPrimitiveTests(unittest.TestCase):
    """Synthetic format tests; no producer profile or acceptance is enabled."""
    def test_raw_json_has_its_own_four_mebibyte_limit(self):
        raw = b'{"padding":"' + b'x' * (4 * 1024 * 1024 - 14) + b'"}'
        self.assertEqual(len(raw), 4 * 1024 * 1024)
        self.assertIn('padding', assembler.strict_raw_json(raw))
        with self.assertRaisesRegex(assembler.ContractError, '^manifest_size$'):
            assembler.strict_json(raw)
        with self.assertRaisesRegex(assembler.ContractError, '^raw_json_size$'):
            assembler.strict_raw_json(raw + b' ')
        for invalid in (b'{"x":1,"x":2}', b'{"n":{"x":1,"x":2}}', b'{"x":NaN}',
                        b'{"x":1e999}', b'{"x":"\\ud800"}', b'\xff', b'[]'):
            with self.subTest(raw=invalid), self.assertRaises(assembler.ContractError):
                assembler.strict_raw_json(invalid)

    def test_go_jsonl_requires_complete_bounded_object_records(self):
        raw = b'{"Action":"run"}\n{"Action":"pass"}\r\n'
        self.assertEqual([x['Action'] for x in assembler.strict_jsonl(raw)], ['run', 'pass'])
        for invalid in (b'', b'{}', b'{}\n\n', b'[]\n', b'{}\nnull\n',
                        b'{"x":1,"x":2}\n', b'{"x":Infinity}\n', b'\xff\n',
                        b'{}\n' * 65537, b' ' * (4 * 1024 * 1024 + 1)):
            with self.subTest(raw=invalid[:40]), self.assertRaises(assembler.ContractError):
                assembler.strict_jsonl(invalid)

    def test_junit_xml_is_utf8_bounded_and_forbids_dtd_entities_and_ambiguity(self):
        raw = b'<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite tests="1"><testcase name="one"/></testsuite></testsuites>'
        self.assertEqual(assembler.strict_junit_xml(raw).tag, 'testsuites')
        invalids = [b'', b'<testsuite', b'<testsuite tests="1" tests="2"/>', b'\xff',
                    b'<!DOCTYPE testsuite [<!ENTITY x "expanded">]><testsuite>&x;</testsuite>',
                    b'<!DOCTYPE testsuite SYSTEM "https://example.invalid/private"><testsuite/>',
                    b'<testsuite><!-- hidden --></testsuite>', b'<testsuite><?hidden x?></testsuite>',
                    b'<?xml version="1.0" encoding="latin1"?><testsuite/>',
                    b'<testsuite xmlns="urn:other"/>', b'<other/>',
                    b'<testsuite>' + b'<x>' * 65 + b'</x>' * 65 + b'</testsuite>',
                    b'<testsuite>' + b'<testcase/>' * 20001 + b'</testsuite>',
                    b' ' * (4 * 1024 * 1024 + 1)]
        for raw in invalids:
            with self.subTest(raw=raw[:80]), self.assertRaises(assembler.ContractError):
                assembler.strict_junit_xml(raw)

    def archive(self, entries=None, *, compression=zipfile.ZIP_DEFLATED):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=compression) as archive:
            for name, raw, mode in entries or [('browser/evidence.json', b'{}', stat.S_IFREG | 0o600),
                                              ('go-fixture.log', b'fixture', stat.S_IFREG | 0o600),
                                              ('ready.json', b'{}', stat.S_IFREG | 0o600)]:
                info = zipfile.ZipInfo(name); info.create_system = 3
                info.external_attr = mode << 16; info.compress_type = compression
                archive.writestr(info, raw)
        return stream.getvalue()

    def test_dto_zip_is_fixed_inventory_and_never_extracts(self):
        raw = self.archive()
        self.assertEqual(assembler.strict_dto_archive(raw), {
            'browser/evidence.json': b'{}', 'go-fixture.log': b'fixture', 'ready.json': b'{}'})
        entries = [('browser/evidence.json', b'{}', stat.S_IFREG | 0o600),
                   ('go-fixture.log', b'fixture', stat.S_IFREG | 0o600),
                   ('ready.json', b'{}', stat.S_IFREG | 0o600)]
        invalids = [b'not a zip', raw[:-3], raw + b'private trailing bytes', b'prefix' + raw,
                    self.archive(entries[:-1]), self.archive(entries + [('extra', b'x', stat.S_IFREG)]),
                    self.archive([('browser/evidence.json', b'x', stat.S_IFLNK | 0o777)] + entries[1:]),
                    self.archive([('../evidence.json', b'{}', stat.S_IFREG)] + entries[1:]),
                    self.archive([('browser\\evidence.json', b'{}', stat.S_IFREG)] + entries[1:]),
                    self.archive([('browser/evidence.json', b' ' * (4 * 1024 * 1024 + 1), stat.S_IFREG)] + entries[1:]),
                    self.archive(compression=zipfile.ZIP_BZIP2)]
        # Duplicate central names, despite a complete-looking final inventory.
        with self.assertWarns(UserWarning):
            invalids.append(self.archive(entries + [entries[0]]))
        # Mutate compressed bytes, local/central encryption flags and CRC independently.
        damaged = bytearray(raw); damaged[raw.index(b'browser/evidence.json') + len(b'browser/evidence.json')] ^= 0xff
        invalids.append(bytes(damaged))
        encrypted = bytearray(raw); central = raw.index(b'PK\x01\x02')
        struct.pack_into('<H', encrypted, 6, 1); struct.pack_into('<H', encrypted, central + 8, 1)
        invalids.append(bytes(encrypted))
        crc = bytearray(raw); struct.pack_into('<I', crc, central + 16, 0)
        invalids.append(bytes(crc))
        # Declared tiny output plus a large actual deflate stream must not hide expansion.
        bomb = bytearray(self.archive([('browser/evidence.json', b'x' * (4 * 1024 * 1024 + 1),
                                       stat.S_IFREG | 0o600)] + entries[1:]))
        central = bomb.index(b'PK\x01\x02')
        for offset in (22, central + 24): struct.pack_into('<I', bomb, offset, 1)
        for offset in (14, central + 16): struct.pack_into('<I', bomb, offset, zipfile.crc32(b'x'))
        invalids.append(bytes(bomb))
        version = bytearray(raw); struct.pack_into('<H', version, 4, 63)
        invalids.append(bytes(version))
        for raw in invalids:
            with self.subTest(raw=raw[:40]), self.assertRaises(assembler.ContractError):
                assembler.strict_dto_archive(raw)

    def test_zip_central_framing_disk_and_header_metadata_are_exact(self):
        raw = self.archive()
        directory_start = struct.unpack_from('<I', raw, len(raw)-6)[0]
        central_offsets = []
        cursor = directory_start
        for _ in range(3):
            central_offsets.append(cursor)
            name_bytes, extra_bytes, comment_bytes = struct.unpack_from('<3H', raw, cursor+28)
            cursor += 46+name_bytes+extra_bytes+comment_bytes
        self.assertEqual(cursor, len(raw)-22)
        # Reproduce every field on every member, including overclaims in the last record.
        for member, central in enumerate(central_offsets):
            local = struct.unpack_from('<I', raw, central+42)[0]
            mutations = [('central_extra_length', central+30, '<H', 1),
                         ('central_comment_length', central+32, '<H', 1),
                         ('member_disk_start', central+34, '<H', 1),
                         ('central_extract_reserved', central+7, '<B', 1),
                         ('local_extract_reserved', local+5, '<B', 1),
                         ('local_dos_time', local+10, '<H', 1),
                         ('central_dos_time', central+12, '<H', 1),
                         ('local_dos_date', local+12, '<H', 0x22),
                         ('central_dos_date', central+14, '<H', 0x22),
                         ('truncated_name_length', central+28, '<H', 1),
                         ('overclaimed_name_length', central+28, '<H', 65535)]
            for field, offset, format_code, value in mutations:
                altered = bytearray(raw); struct.pack_into(format_code, altered, offset, value)
                with self.subTest(member=member, field=field), self.assertRaises(assembler.ContractError):
                    assembler.strict_dto_archive(bytes(altered))
            for field, local_offset, central_offset, value in [
                    ('invalid_date', local+12, central+14, 0),
                    ('invalid_time', local+10, central+12, 65535)]:
                altered = bytearray(raw)
                for offset in (local_offset, central_offset): struct.pack_into('<H', altered, offset, value)
                with self.subTest(member=member, field=field), self.assertRaises(assembler.ContractError):
                    assembler.strict_dto_archive(bytes(altered))
        # Directory size must describe exactly the three record frames, without padding.
        altered = bytearray(raw[:-22] + b'x' + raw[-22:])
        size = struct.unpack_from('<I', altered, len(altered)-10)[0]
        struct.pack_into('<I', altered, len(altered)-10, size+1)
        with self.assertRaises(assembler.ContractError): assembler.strict_dto_archive(bytes(altered))
        # Keep both supported compression forms covered through the strict path.
        self.assertEqual(set(assembler.strict_dto_archive(self.archive(compression=zipfile.ZIP_STORED))),
                         {'browser/evidence.json', 'go-fixture.log', 'ready.json'})

    def test_junit_namespaced_attributes_are_rejected_at_every_element(self):
        for raw in (b'<testsuite xmlns:x="urn:other" x:tests="1"/>',
                    b'<testsuites xmlns:x="urn:other"><testsuite><testcase x:name="one"/></testsuite></testsuites>',
                    b'<testsuite xml:lang="en"/>'):
            with self.subTest(raw=raw), self.assertRaisesRegex(assembler.ContractError, '^xml_namespace$'):
                assembler.strict_junit_xml(raw)

    def test_raw_foundations_are_never_selected_by_the_disabled_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory); manifest = parent/'envelope.json'
            root = parent/'raw'; root.mkdir(); (root/'proof.json').write_bytes(b'{}')
            for tier in ('fixture', 'staging'):
                item = committed_envelope(); item['requested_tier'] = tier
                manifest.write_text(json.dumps(item))
                argv = ['plan', '--manifest', str(manifest), '--evidence-root', str(root),
                        '--trusted-base-sha', TRUSTED_BASE, '--task-ref', TASK, '--requested-tier', tier]
                with patch.multiple(assembler, strict_raw_json=DEFAULT, strict_jsonl=DEFAULT,
                        strict_junit_xml=DEFAULT, strict_dto_archive=DEFAULT,
                        paid_case_identities=DEFAULT, dto_case_identities=DEFAULT,
                        inspect_paid_common=DEFAULT, inspect_paid_pg_snapshots=DEFAULT,
                        inspect_paid_migration_receipts=DEFAULT) as mocks:
                    for mock in mocks.values(): mock.side_effect = AssertionError('raw dispatch forbidden')
                    with patch.object(assembler, 'ArtifactStore', side_effect=AssertionError('plan root I/O')):
                        with patch('builtins.print') as output:
                            self.assertEqual(assembler.main(argv), 0)
                    result = json.loads(output.call_args.args[0])
                    self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))
                    argv[0] = 'validate'
                    with patch('builtins.print') as output:
                        self.assertEqual(assembler.main(argv), 3)
                    result = json.loads(output.call_args.args[0])
                    self.assertEqual(result['status'], 'unavailable')
                    self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))
                    self.assertTrue(all(value == 0 for value in result['derived_counts'].values()))
                    for mock in mocks.values(): mock.assert_not_called()

    def test_fixed_paid_and_dto_identities_reject_count_substitution(self):
        paid = list(assembler.PAID_CASE_IDS)
        dto = [dict(browser=browser, scenario=scenario) for browser, scenario in assembler.DTO_CASE_IDS]
        self.assertEqual(len(assembler.paid_case_identities(paid)), 12)
        self.assertEqual(len(assembler.dto_case_identities(dto)), 120)
        for value in [paid[:-1], paid + paid[:1], ['unknown'] + paid[1:], [True] + paid[1:], {}]:
            with self.subTest(value=str(value)[:40]), self.assertRaises(assembler.ContractError):
                assembler.paid_case_identities(value)
        invalids = [dto[:-1], dto + dto[:1], [dict(browser='chromium', scenario='unknown')] + dto[1:],
                    [dict(browser='other', scenario=dto[0]['scenario'])] + dto[1:],
                    [dict(browser=True, scenario=dto[0]['scenario'])] + dto[1:],
                    [dict(dto[0], unknown=True)] + dto[1:], {}]
        for value in invalids:
            with self.subTest(value=str(value)[:60]), self.assertRaises(assembler.ContractError):
                assembler.dto_case_identities(value)

    def test_explicit_store_raw_reader_rechecks_reserved_identity_and_drift(self):
        value = dict(candidate_sha=BASE, trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64,
                     padding='x' * (2 * 1024 * 1024))
        raw = json.dumps(value).encode()
        artifact = dict(artifact_id='raw', kind='collector_result', ref='raw.json',
                        sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), visibility='private')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'raw.json'; path.write_bytes(raw)
            with assembler.ArtifactStore(directory, [artifact]) as store:
                result = store.read_raw_json('raw', candidate_sha=BASE,
                    trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64)
                self.assertEqual(result['candidate_sha'], BASE)
                with self.assertRaises(assembler.ContractError):
                    store.read_raw_json('raw', candidate_sha='2'*40,
                        trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64)
                original = assembler.strict_raw_json
                def changed_after_parse(data):
                    parsed = original(data); path.write_bytes(raw + b' '); return parsed
                with patch.object(assembler, 'strict_raw_json', side_effect=changed_after_parse):
                    with self.assertRaisesRegex(assembler.ContractError, '^artifact_size_mismatch$'):
                        store.read_raw_json('raw', candidate_sha=BASE,
                            trusted_base_sha=TRUSTED_BASE, profile_sha256='1'*64)


class PaidCommonTests(unittest.TestCase):
    """Synthetic paid receipts deliberately lack the deeper validation families."""
    def model(self):
        cases = []
        for root_index, name in enumerate(assembler.PAID_GO_ROOTS):
            for bank in ('bankone', 'banktwo'):
                case_id = name+'-'+bank
                phases = {phase: {} for phase in assembler.PAID_PHASES[root_index]}
                assertions = {key: True for key in assembler.PAID_CASE_ASSERTIONS[root_index]}
                measurement = dict(phase_snapshots=copy.deepcopy(phases), assertion_results=assertions,
                    held_model_receipt={} if root_index == 2 else None,
                    http_observations=[{}], identity_checks=1, reader_calls=0,
                    observed_views=[{} for _ in range(3 if root_index == 2 else 2)] if root_index in (2,3,4) else None)
                database = 'lifecycle_test_'+format(len(cases)+1, '032x')
                runtime = dict(schema_version=1, candidate_sha=BASE, provider=bank, go_test_name=name,
                    fixture_database=database, snapshots=copy.deepcopy(phases), final_snapshot={},
                    migrations={}, service_probes={}, worker_exits=[dict(kind='cli', terminated=True,
                        exit_code=-15, intentional_cleanup=True, alive_before_cleanup=True)
                        for _ in range(2 if root_index in (2,3,4) else 0)],
                    **{k:copy.deepcopy(v) for k,v in measurement.items() if k not in ('phase_snapshots','assertion_results')})
                result = dict(schema_version=1, candidate_sha=BASE, candidate_origin='coordinator-host-plain-clone',
                    provider=bank, go_test_name=name, fixture_database=database,
                    host_before_sha256=hashlib.sha256(b'{}').hexdigest(), input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
                    started_at='2026-11-03T00:00:00Z', finished_at='2026-11-03T00:00:01Z',
                    go_exit_code=0, timed_out=False, passed=True, failures=[],
                    phase_snapshots=copy.deepcopy(phases), assertion_results=dict(assertions,
                        **{key:True for key in assembler.PAID_MIGRATION_ASSERTIONS}))
                events = [dict(Time='2026-11-03T00:00:00Z', Action='start', Package=assembler.PAID_GO_PACKAGE),
                    dict(Time='2026-11-03T00:00:00Z', Action='run', Package=assembler.PAID_GO_PACKAGE, Test=name),
                    dict(Time='2026-11-03T00:00:01Z', Action='pass', Package=assembler.PAID_GO_PACKAGE, Test=name, Elapsed=0.1),
                    dict(Time='2026-11-03T00:00:01Z', Action='pass', Package=assembler.PAID_GO_PACKAGE, Elapsed=0.2)]
                cases.append(dict(case_id=case_id, name=name, bank=bank, result=result,
                    measurement=measurement, runtime=runtime, events=events,
                    command=dict(argv=['go','test','-json','-count=1','-timeout=90s','-run','^'+name+'$','.'], cwd='/workspace/apps/api-go')))
        return dict(cases=cases, flags={case_id:True for case_id in assembler.PAID_CASE_IDS})

    def junit(self, case_ids):
        children=''.join('<testcase classname="tests.test_paid_catalog_api_integration" name="test_required_paid_catalog_access['+case_id+']" time="0.5"/>' for case_id in case_ids)
        return ('<testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="'+str(len(case_ids))+'" time="1.0" timestamp="2026-11-03T00:00:00Z" hostname="fixture">'+children+'</testsuite></testsuites>').encode()

    def files(self, model):
        raw = {'host-before.json':b'{}', 'inputs.sha256.json':b'{}'}
        for ref in assembler.PAID_COLLECTOR_FILES: raw[ref] = b''
        raw['workshop-paid-access-tests.xml'] = self.junit(assembler.PAID_CASE_IDS)
        results={}
        for case in model['cases']:
            prefix='paid-access/'+case['bank']+'/'+case['name']+'/'
            for ref in assembler.PAID_CASE_FILES: raw[prefix+ref] = b'{}' if ref.endswith('.json') else b''
            raw[prefix+'case-tests.xml']=self.junit([case['case_id']])
            raw[prefix+'go-events.jsonl']=b''.join(json.dumps(event).encode()+b'\n' for event in case['events'])
            for ref,key in [('go-command.json','command'),('go-measurement.json','measurement'),('measured-runtime.json','runtime')]:
                raw[prefix+ref]=json.dumps(case[key]).encode()
            result=copy.deepcopy(case['result'])
            result['artifact_sha256']={ref:hashlib.sha256(raw[prefix+ref]).hexdigest() for ref in assembler.PAID_CASE_FILES}
            raw[prefix+'result.json']=json.dumps(result).encode();results[case['case_id']]=result
        collector=dict(schema_version=1, candidate_sha=BASE, candidate_origin='coordinator-host-plain-clone',
            host_before_sha256=hashlib.sha256(b'{}').hexdigest(),input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
            started_at='2026-11-03T00:00:00Z',finished_at='2026-11-03T00:00:02Z',passed=True,failures=[],
            pytest_exit_code=0,timed_out=False,pytest_test_count=12,case_results=results,
            assertion_results=model['flags'],runner_git_observation={},
            artifact_sha256={ref:hashlib.sha256(raw[ref]).hexdigest() for ref in assembler.PAID_COLLECTOR_FILES})
        raw['workshop-paid-access.json']=json.dumps(collector).encode()
        return raw

    def inspect(self, raw, **overrides):
        # The domain tests replace only transport; ArtifactStore itself is tested
        # separately, and one end-to-end test below exercises the real store.
        class SyntheticStore:
            def __init__(self):
                self.by_ref={ref:dict(artifact_id=ref) for ref in raw}
            def read(self, artifact_id): return raw[artifact_id]
            def read_raw_json(self, artifact_id, **_): return assembler.strict_raw_json(self.read(artifact_id))
            def recheck(self): pass
        invocation=dict(candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,profile_sha256='1'*64,
            input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),host_before_sha256=hashlib.sha256(b'{}').hexdigest(),profile_version='paid-selector-v2')
        invocation.update(overrides)
        return assembler.inspect_paid_common(SyntheticStore(), **invocation)

    def test_synthetic_common_outcomes_remain_incomplete_with_missing_families(self):
        result=self.inspect(self.files(self.model()))
        self.assertEqual(result['status'],'unavailable')
        self.assertFalse(result['complete'])
        self.assertEqual(result['observed_case_ids'],list(assembler.PAID_CASE_IDS))
        self.assertEqual(result['verified_case_ids'],[])
        self.assertEqual(set(result['missing_validation_families']),set(assembler.PAID_MISSING_FAMILIES))
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))
        self.assertIn('paid_source_pg_bindings',result['missing_validation_families'])
        self.assertIn('paid_http_media_rights',result['missing_validation_families'])

    def test_each_common_outcome_family_rejects_independent_contradictions(self):
        mutations=[
            ('child_failed',lambda m:m['cases'][0]['result'].update(go_exit_code=1)),
            ('bool_exit',lambda m:m['cases'][0]['result'].update(go_exit_code=False)),
            ('wrong_schema',lambda m:m['cases'][0]['result'].update(schema_version=True)),
            ('wrong_candidate',lambda m:m['cases'][0]['result'].update(candidate_sha='2'*40)),
            ('wrong_bank',lambda m:m['cases'][0]['result'].update(provider='banktwo')),
            ('duplicate_database',lambda m:(m['cases'][1]['result'].update(fixture_database=m['cases'][0]['result']['fixture_database']),m['cases'][1]['runtime'].update(fixture_database=m['cases'][0]['result']['fixture_database']))),
            ('phase_mismatch',lambda m:m['cases'][0]['runtime']['snapshots'].pop('before')),
            ('wrong_command',lambda m:m['cases'][0]['command']['argv'].append('-skip=all')),
            ('wrong_cwd',lambda m:m['cases'][0]['command'].update(cwd='/candidate')),
            ('child_assertion_false',lambda m:m['cases'][0]['measurement']['assertion_results'].update(public_selectors_metadata_only=False)),
            ('go_failed',lambda m:m['cases'][0]['events'][2].update(Action='fail')),
            ('go_foreign_root',lambda m:m['cases'][0]['events'][1].update(Test='Other')),
            ('go_foreign_package',lambda m:m['cases'][0]['events'][0].update(Package='foreign')),
            ('go_duplicate_run',lambda m:m['cases'][0]['events'].insert(2,copy.deepcopy(m['cases'][0]['events'][1]))),
            ('go_missing_package_pass',lambda m:m['cases'][0]['events'].pop()),
            ('go_unknown_field',lambda m:m['cases'][0]['events'][0].update(unknown=True)),
            ('go_bool_elapsed',lambda m:m['cases'][0]['events'][2].update(Elapsed=True)),
            ('go_huge_elapsed',lambda m:m['cases'][0]['events'][2].update(Elapsed=10**400)),
            ('go_timeout',lambda m:m['cases'][0]['events'][2].update(Elapsed=91)),
            ('case_timeout',lambda m:m['cases'][0]['result'].update(finished_at='2026-11-03T00:02:01Z')),
            ('worker_missing',lambda m:m['cases'][4]['runtime']['worker_exits'].pop()),
            ('worker_wrong_exit',lambda m:m['cases'][4]['runtime']['worker_exits'][0].update(exit_code=0)),
            ('worker_false_alive',lambda m:m['cases'][4]['runtime']['worker_exits'][0].update(alive_before_cleanup=False)),
            ('outer_flag_false',lambda m:m['flags'].update({assembler.PAID_CASE_IDS[0]:False})),
            ('missing_case',lambda m:m['cases'].pop())]
        for name,mutate in mutations:
            model=self.model();mutate(model)
            with self.subTest(name=name),self.assertRaises(assembler.ContractError):self.inspect(self.files(model))

    def test_raw_junit_hash_and_embedded_receipts_cannot_be_overridden_by_pass(self):
        for mutation in ('junit_failed','hash_mismatch','embedded_mismatch','missing_raw','unknown_collector','profile_version'):
            raw=self.files(self.model());collector=json.loads(raw['workshop-paid-access.json'])
            if mutation=='junit_failed':
                raw['workshop-paid-access-tests.xml']=raw['workshop-paid-access-tests.xml'].replace(b'<testcase ',b'<failure/><testcase ',1)
                collector['artifact_sha256']['workshop-paid-access-tests.xml']=hashlib.sha256(raw['workshop-paid-access-tests.xml']).hexdigest()
            elif mutation=='hash_mismatch':raw['paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/go-stderr.log']=b'changed'
            elif mutation=='embedded_mismatch':collector['case_results'][assembler.PAID_CASE_IDS[0]]['passed']=False
            elif mutation=='missing_raw':del raw['paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/go-command.json']
            elif mutation=='unknown_collector':collector['unknown']=True
            raw['workshop-paid-access.json']=json.dumps(collector).encode()
            with self.subTest(mutation=mutation),self.assertRaises(assembler.ContractError):
                self.inspect(raw,**({'profile_version':'paid-selector-v1'} if mutation=='profile_version' else {}))

    def test_paid_junit_rejects_aliased_ids_unknown_fields_and_hidden_outcomes(self):
        raw=self.junit(assembler.PAID_CASE_IDS)
        mutations=[raw.replace(b'tests="12"',b'tests="11"'),
            raw.replace(b'time="1.0"',b'time="NaN"'),
            raw.replace(b'tests.test_paid_catalog_api_integration',b'foreign',1),
            raw.replace(assembler.PAID_CASE_IDS[1].encode(),assembler.PAID_CASE_IDS[0].encode()),
            raw.replace(b'<testcase ',b'<skipped/><testcase ',1),
            raw.replace(b'<testcase ',b'<testcase unknown="true" ',1),
            raw.replace(b'<testcase ',b'hidden outcome<testcase ',1)]
        for altered in mutations:
            with self.subTest(raw=altered[:80]),self.assertRaises(assembler.ContractError):
                assembler._paid_junit(altered,assembler.PAID_CASE_IDS,1806)

    def test_go_elapsed_preserves_exact_json_number_bounds(self):
        case = self.model()['cases'][0]
        for event_index in (2, 3):
            def encoded(token):
                lines = [json.dumps(event).encode() for event in case['events']]
                original = str(case['events'][event_index]['Elapsed']).encode()
                lines[event_index] = lines[event_index].replace(b'"Elapsed": '+original,
                    b'"Elapsed": '+token)
                return b'\n'.join(lines)+b'\n'
            for token in (b'90', b'9e1', b'90.0000000000000000000000000000000000000000',
                          b'89.9999999999999999999999999999999999999999', b'0', b'1e-999'):
                with self.subTest(event=event_index, accepted=token):
                    assembler._paid_go_outcome(encoded(token), case['name'],
                        case['result']['started_at'], case['result']['finished_at'])
            for token in (b'90.0000000000000000000000000000000000000001',
                          b'-1e-999', b'true', b'"90"', b'null', b'NaN', b'Infinity', b'1e999'):
                with self.subTest(event=event_index, rejected=token), self.assertRaises(assembler.ContractError):
                    assembler._paid_go_outcome(encoded(token), case['name'],
                        case['result']['started_at'], case['result']['finished_at'])

    def test_case_deadlines_preserve_submicrosecond_precision(self):
        assembler._paid_duration('2026-11-03T00:00:00Z', '2026-11-03T00:02:00Z', 120)
        with self.assertRaises(assembler.ContractError):
            assembler._paid_duration('2026-11-03T00:00:00Z',
                '2026-11-03T00:02:00.0000000000000000000000000000000000000001Z',120)
        with self.assertRaises(assembler.ContractError):
            assembler._paid_duration('2026-11-03T00:00:00.0000000000000000000000000000000000000002Z',
                '2026-11-03T00:00:00.0000000000000000000000000000000000000001Z',120)

    def test_real_artifact_store_common_result_is_still_unavailable(self):
        raw=self.files(self.model())
        with tempfile.TemporaryDirectory() as directory:
            artifacts=[]
            for index,(ref,data) in enumerate(raw.items()):
                path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                artifacts.append(dict(artifact_id='raw-'+str(index),kind='raw',ref=ref,
                    sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),visibility='private'))
            with assembler.ArtifactStore(directory,artifacts) as store:
                result=assembler.inspect_paid_common(store,candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,
                    profile_sha256='1'*64,input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
                    host_before_sha256=hashlib.sha256(b'{}').hexdigest(),profile_version='paid-selector-v2')
            self.assertEqual(result['status'],'unavailable');self.assertEqual(result['verified_case_ids'],[])


class PaidPGSnapshotTests(unittest.TestCase):
    """PG binding fixtures keep source/media/migration payload semantics absent."""
    tables = ('schema_migrations', 'catalog_articles', 'canonical_articles',
        'canonical_article_source_revisions', 'canonical_article_source_observations',
        'canonical_article_revisions', 'canonical_article_reviews',
        'canonical_article_rewrite_attempts', 'source_fetch_jobs', 'publication_events',
        'source_snapshots', 'catalog_article_provider_scopes', 'catalog_article_index_pages',
        'canonical_article_aliases', 'customer_accounts', 'auth_sessions',
        'workshop_orders', 'workshop_checkout_requests')

    def model(self):
        model = PaidCommonTests().model()
        for case in model['cases']:
            article_id = '00000000-0000-0000-0000-000000000001'
            paid = dict(customer_accounts=[dict(customer_account_id='00000000-0000-0000-0000-00000000000'+str(i),
                personal_organization_id='00000000-0000-0000-0000-00000000001'+str(i),
                firebase_project_id='fixture-project', firebase_uid='paid-owner-'+str(i),
                created_at='2026-11-03T00:00:00Z', status='active') for i in (2,3)],
                auth_sessions=[dict(customer_account_id='00000000-0000-0000-0000-00000000000'+str(i),
                    session_token_hash='\\x'+str(i)*64, created_at='2026-11-03T00:00:00Z',
                    expires_at='2026-11-03T01:00:00Z', firebase_auth_time=1, revoked_at=None) for i in (2,3)],
                entitlements=[], workshop_orders=[], dataset_requests=[], dataset_projections=[])
            rows = {table:[] for table in self.tables}
            rows.update({key:copy.deepcopy(paid[key]) for key in ('customer_accounts','auth_sessions','workshop_orders')})
            rows['canonical_articles']=[dict(canonical_article_id=article_id, provider_slug=case['bank'])]
            snapshot = dict(article=dict(canonical_article_id=article_id, provider_slug=case['bank']),
                immutable_rows=rows, immutable_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
                paid_rows=paid, counts=dict(article_jobs=0, source_revisions=0, canonical_revisions=0,
                    published_revisions=0, publication_events=0, source_observations=0),
                ensure=dict(entered=0,completed=0,active=0), ensure_requests=[],
                selector_ensure=dict(entered=0,completed=0,active=0), selector_ensure_requests=[],
                model_calls=0, grant_calls=0, payment_calls=0,
                **{key:dict(bankone=0,banktwo=0) for key in ('provider_calls','source_calls','asset_calls')},
                provider_traces=dict(bankone=[],banktwo=[]),
                proxy=dict(request_received=0,upstream_completed=0,downstream_completed=0,
                    downstream_waiting=0,response_captured=False,errors=[]),workers=[])
            case['result']['phase_snapshots']={phase:dict(copy.deepcopy(snapshot),reader_calls=0,identity_checks=1)
                for phase in case['result']['phase_snapshots']}
            case['runtime']['final_snapshot']=copy.deepcopy(snapshot)
            case['runtime']['service_probes']=dict(postgres=dict(database=case['result']['fixture_database'],
                server_version_num=170011,user='lifecycle_test'),
                s3=dict(bucket='lifecycle-'+'1'*32,roundtrip_ok=True),
                nats=dict(jetstream_account_info_ok=True))
        return model

    def files(self, model):
        for case in model['cases']:
            case['runtime']['snapshots']=copy.deepcopy(case['result']['phase_snapshots'])
            case['measurement']['phase_snapshots']=copy.deepcopy(case['result']['phase_snapshots'])
        raw=PaidCommonTests().files(model)
        for case in model['cases']:
            ref='paid-access/'+case['bank']+'/'+case['name']+'/migration-replay-populated.rows.json'
            raw[ref]=json.dumps(case['runtime']['final_snapshot']['immutable_rows']).encode()
        self.reseal(raw)
        return raw

    def reseal(self, raw):
        collector=json.loads(raw['workshop-paid-access.json'])
        for case_id,result in collector['case_results'].items():
            prefix='paid-access/'+result['provider']+'/'+result['go_test_name']+'/'
            result['artifact_sha256']={ref:hashlib.sha256(raw[prefix+ref]).hexdigest() for ref in assembler.PAID_CASE_FILES}
            raw[prefix+'result.json']=json.dumps(result).encode()
        raw['workshop-paid-access.json']=json.dumps(collector).encode()

    def inspect(self, raw):
        class Store:
            by_ref={ref:dict(artifact_id=ref) for ref in raw}
            def read(self, artifact_id): return raw[artifact_id]
            def read_raw_json(self, artifact_id, **_): return assembler.strict_raw_json(raw[artifact_id])
            def recheck(self): pass
        self.assertTrue(callable(getattr(assembler,'inspect_paid_pg_snapshots',None)),
                        'explicit PG snapshot inspection is missing')
        return assembler.inspect_paid_pg_snapshots(Store(), candidate_sha=BASE,
            trusted_base_sha=TRUSTED_BASE,profile_sha256='1'*64,
            input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
            host_before_sha256=hashlib.sha256(b'{}').hexdigest(),profile_version='paid-selector-v2')

    def test_pg_snapshot_bindings_remain_incomplete(self):
        result=self.inspect(self.files(self.model()))
        self.assertEqual(result['status'],'unavailable'); self.assertIs(result['complete'],False)
        self.assertEqual(result['observed_pg_snapshot_count'],52)
        self.assertEqual(result['verified_case_ids'],[])
        self.assertTrue(set(assembler.PAID_MISSING_FAMILIES).issubset(result['missing_validation_families']))
        self.assertIn('paid_pg_row_semantics',result['missing_validation_families'])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_pg_phase_and_final_binding_contradictions_reject(self):
        mutations=[
            ('unknown_snapshot',lambda s:s.update(unknown=True)),
            ('bool_counter',lambda s:s.update(model_calls=True)),
            ('payment_work',lambda s:s.update(payment_calls=1)),
            ('active_work',lambda s:s['ensure'].update(entered=1,active=1)),
            ('counter_inventory',lambda s:s['provider_calls'].update(other=0)),
            ('trace_mismatch',lambda s:s['provider_calls'].update(bankone=1)),
            ('proxy_order',lambda s:s['proxy'].update(upstream_completed=1)),
            ('proxy_error',lambda s:s['proxy'].update(errors=['failed'])),
            ('proxy_bool',lambda s:s['proxy'].update(response_captured=0)),
            ('table_inventory',lambda s:s['immutable_rows'].update(other=[])),
            ('row_shape',lambda s:s['immutable_rows']['source_snapshots'].append([])),
            ('row_hash',lambda s:s.update(immutable_sha256='0'*64)),
            ('raw_count',lambda s:s['counts'].update(source_revisions=1)),
            ('bool_count',lambda s:s['counts'].update(source_revisions=False)),
            ('foreign_article',lambda s:s['article'].update(canonical_article_id='00000000-0000-0000-0000-000000000099')),
            ('wrong_provider',lambda s:s['article'].update(provider_slug='banktwo')),
            ('paid_inventory',lambda s:s['paid_rows'].update(other=[])),
            ('foreign_session',lambda s:s['paid_rows']['auth_sessions'][0].update(customer_account_id='00000000-0000-0000-0000-000000000099')),
            ('duplicate_account',lambda s:s['paid_rows']['customer_accounts'].append(copy.deepcopy(s['paid_rows']['customer_accounts'][0]))),
            ('worker_bool',lambda s:s['workers'].append(dict(kind='cli',alive=1,exit_code=None))),
        ]
        for final in (False,True):
            for name,mutate in mutations:
                model=self.model();case=model['cases'][0]
                snapshot=case['runtime']['final_snapshot'] if final else case['result']['phase_snapshots']['before']
                mutate(snapshot)
                with self.subTest(final=final,mutation=name),self.assertRaises(assembler.ContractError):
                    self.inspect(self.files(model))

    def test_real_artifact_store_pg_bindings_remain_unavailable(self):
        raw=self.files(self.model())
        with tempfile.TemporaryDirectory() as directory:
            artifacts=[]
            for index,(ref,data) in enumerate(raw.items()):
                path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                artifacts.append(dict(artifact_id='raw-'+str(index),kind='raw',ref=ref,
                    sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),visibility='private'))
            with assembler.ArtifactStore(directory,artifacts) as store:
                result=assembler.inspect_paid_pg_snapshots(store,candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,
                    profile_sha256='1'*64,input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
                    host_before_sha256=hashlib.sha256(b'{}').hexdigest(),profile_version='paid-selector-v2')
            self.assertEqual(result['status'],'unavailable');self.assertEqual(result['observed_pg_snapshot_count'],52)
            self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_pg_counts_derive_from_rows_and_producer_digest_encoding(self):
        snapshot=copy.deepcopy(self.model()['cases'][0]['runtime']['final_snapshot'])
        article_id=snapshot['article']['canonical_article_id']; rows=snapshot['immutable_rows']
        rows['catalog_articles']=[dict(title='Réparation')]
        rows['source_fetch_jobs']=[dict(canonical_article_id=article_id,job_kind='article'),
                                  dict(canonical_article_id=None,job_kind='catalog')]
        rows['canonical_article_source_revisions']=[dict(canonical_article_id=article_id)]
        rows['canonical_article_revisions']=[dict(canonical_article_id=article_id,status='published'),
                                            dict(canonical_article_id=article_id,status='draft')]
        rows['publication_events']=[dict(canonical_article_id=article_id)]
        rows['canonical_article_source_observations']=[dict(canonical_article_id=article_id)]
        snapshot['counts']=dict(article_jobs=1,source_revisions=1,canonical_revisions=2,
            published_revisions=1,publication_events=1,source_observations=1)
        snapshot['immutable_sha256']=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
        assembler._paid_pg_snapshot(snapshot,'bankone',final=True)
        for key in snapshot['counts']:
            altered=copy.deepcopy(snapshot);altered['counts'][key]+=1
            with self.subTest(count=key),self.assertRaises(assembler.ContractError):
                assembler._paid_pg_snapshot(altered,'bankone',final=True)
        altered=copy.deepcopy(snapshot)
        altered['immutable_sha256']=hashlib.sha256(assembler.canonical(rows)).hexdigest()
        with self.assertRaisesRegex(assembler.ContractError,'^paid_pg_row_hash$'):
            assembler._paid_pg_snapshot(altered,'bankone',final=True)
        for table in ('source_fetch_jobs','canonical_article_source_revisions','canonical_article_revisions'):
            altered=copy.deepcopy(snapshot)
            del altered['immutable_rows'][table][0]['canonical_article_id']
            altered['immutable_sha256']=hashlib.sha256(json.dumps(altered['immutable_rows'],sort_keys=True).encode()).hexdigest()
            with self.subTest(table=table),self.assertRaises(assembler.ContractError):
                assembler._paid_pg_snapshot(altered,'bankone',final=True)

    def owned_rows(self):
        paid=copy.deepcopy(self.model()['cases'][0]['runtime']['final_snapshot']['paid_rows'])
        owner=paid['customer_accounts'][0]
        order=dict(amount_minor=2000, checkout_session_id=None, checkout_url=None,
            configuration_id='00000000-0000-0000-0000-000000000020', created_at='2026-11-03T00:00:00Z',
            currency='USD',customer_account_id=owner['customer_account_id'],
            dataset_product_id='00000000-0000-0000-0000-000000000021',
            dataset_request_id='00000000-0000-0000-0000-000000000022',
            entitlement_id='00000000-0000-0000-0000-000000000023',expected_price_id='price_fixture',
            first_create_attempt_at='2026-11-03T00:00:00Z',last_reconciled_at=None,livemode=False,
            order_id='00000000-0000-0000-0000-000000000024',organization_id=owner['personal_organization_id'],
            paid_at='2026-11-03T00:00:00Z',payment_intent_id=None,preparation_attempts=0,
            preparation_index_job_ids=[],preparation_last_error_code=None,preparation_lease_expires_at=None,
            preparation_lease_owner=None,preparation_next_attempt_at='2026-11-03T00:00:00Z',
            preparation_state='pending',provider_expires_at=None,provider_idempotency_key='fixture:order',
            region='US',revocation_reason_code=None,revoked_at=None,status='paid',stripe_account_id='acct_fixture',
            terms_version='workshop-v1',updated_at='2026-11-03T00:00:00Z')
        grant=dict(commerce_order_id=order['order_id'],configuration_id=order['configuration_id'],
            customer_account_id=owner['customer_account_id'],dataset_request_id=order['dataset_request_id'],
            entitlement_id=order['entitlement_id'],granted_at='2026-11-03T00:00:00Z',
            organization_id=owner['personal_organization_id'],payment_event_id=None,provider_event_id='fixture:grant',
            region='US',revoke_reason=None,revoked_at=None,status='active')
        paid['workshop_orders']=[order];paid['entitlements']=[grant]
        return paid

    def test_paid_owner_order_scope_and_scalar_contradictions_reject(self):
        assembler._paid_pg_rows(self.owned_rows())
        mutations=[
            ('unknown_order',lambda p:p['workshop_orders'][0].update(other=1)),
            ('bool_amount',lambda p:p['workshop_orders'][0].update(amount_minor=True)),
            ('amount',lambda p:p['workshop_orders'][0].update(amount_minor=1999)),
            ('currency',lambda p:p['workshop_orders'][0].update(currency='CAD')),
            ('live',lambda p:p['workshop_orders'][0].update(livemode=True)),
            ('bool_live',lambda p:p['workshop_orders'][0].update(livemode=0)),
            ('stripe',lambda p:p['workshop_orders'][0].update(stripe_account_id='acct_other')),
            ('price',lambda p:p['workshop_orders'][0].update(expected_price_id='price_other')),
            ('unpaid',lambda p:p['workshop_orders'][0].update(status='pending')),
            ('scope_owner',lambda p:p['workshop_orders'][0].update(customer_account_id=p['customer_accounts'][1]['customer_account_id'])),
            ('scope_config',lambda p:p['workshop_orders'][0].update(configuration_id='00000000-0000-0000-0000-000000000099')),
            ('scope_region',lambda p:p['workshop_orders'][0].update(region='CA')),
            ('missing_order',lambda p:p['workshop_orders'].clear()),
            ('duplicate_order',lambda p:p['workshop_orders'].append(copy.deepcopy(p['workshop_orders'][0]))),
            ('duplicate_scope',lambda p:p['entitlements'].append(dict(p['entitlements'][0],entitlement_id='00000000-0000-0000-0000-000000000099'))),
            ('active_revoked',lambda p:p['entitlements'][0].update(revoked_at='2026-11-03T00:00:00Z')),
            ('status',lambda p:p['entitlements'][0].update(status='invented')),
            ('legacy_scope',lambda p:p['entitlements'][0].update(customer_account_id=None)),
            ('hash',lambda p:p['auth_sessions'][0].update(session_token_hash='plain-token')),
            ('bool_auth_time',lambda p:p['auth_sessions'][0].update(firebase_auth_time=True)),
            ('duplicate_token',lambda p:p['auth_sessions'][0].update(session_token_hash=p['auth_sessions'][1]['session_token_hash'])),
            ('session_time',lambda p:p['auth_sessions'][0].update(expires_at='2025-11-03T00:00:00Z')),
        ]
        for name,mutate in mutations:
            paid=self.owned_rows();mutate(paid)
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):
                assembler._paid_pg_rows(paid)

    def test_service_probes_and_populated_row_seam_reject(self):
        for name,mutate in [
            ('pg_database',lambda p:p['postgres'].update(database='lifecycle_test_'+'f'*32)),
            ('pg_version',lambda p:p['postgres'].update(server_version_num=True)),
            ('pg_major',lambda p:p['postgres'].update(server_version_num=180000)),
            ('pg_user',lambda p:p['postgres'].update(user='postgres')),
            ('s3',lambda p:p['s3'].update(roundtrip_ok=False)),
            ('s3_bucket',lambda p:p['s3'].update(bucket='../bucket')),
            ('nats',lambda p:p['nats'].update(jetstream_account_info_ok=1)),
            ('unknown_probe',lambda p:p.update(other={})),
            ('unknown_pg',lambda p:p['postgres'].update(other=1))]:
            model=self.model();mutate(model['cases'][0]['runtime']['service_probes'])
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):
                self.inspect(self.files(model))
        raw=self.files(self.model())
        prefix='paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/'
        rows=json.loads(raw[prefix+'migration-replay-populated.rows.json'])
        rows['schema_migrations'].append(dict(version='invented'))
        raw[prefix+'migration-replay-populated.rows.json']=json.dumps(rows).encode()
        self.reseal(raw)
        with self.assertRaises(assembler.ContractError):self.inspect(raw)


class PaidMigrationReceiptTests(unittest.TestCase):
    manifest = ['001_extensions.sql', '002_platform_spine.sql', '003_canonical_vehicle.sql', '004_normalized_source_bundle.sql', '005_preserve_duplicate_article_ids.sql', '006_backfill_article_source_locators.sql', '007_link_evidence_to_revision.sql', '008_publication_outbox_delivery.sql', '009_feedback_evidence_link.sql', '010_evidence_review_metadata.sql', '011_feedback_review_metadata.sql', '012_payment_fulfillment_reconciliation.sql', '013_dataset_request_ownership.sql', '014_normalized_article_content.sql', '015_vehicle_identity_resolution.sql', '016_catalog_article_configuration.sql', '017_knowledge_catalog_evidence_index.sql', '018_source_review_items.sql', '019_article_content_provenance.sql', '020_autoapi_article_fetch_jobs.sql', '021_autoapi_article_fetch_job_retries.sql', '022_job_plan_derived_articles.sql', '023_catalog_article_images.sql', '024_catalog_article_operations.sql', '025_chat_quote_procedure.sql', '026_chat_quote_operation_categories.sql', '027_chat_runtime_durable_state.sql', '028_vehicle_provider_mappings.sql', '029_vehicle_catalog_sync.sql', '030_vehicle_catalog_years.sql', '031_catalog_article_classification.sql', '032_catalog_article_source_original.sql', '033_catalog_scope_coverage.sql', '034_catalog_article_progress.sql', '035_ordered_article_document.sql', '036_source_fetch_jobs.sql', '037_article_source_lifecycle.sql', '038_article_transform_publication.sql', '039_production_identity_sessions.sql', '040_workshop_commerce.sql']
    driver = b'-- synthetic already-emitted driver; never executed\n'
    schema = b'-- synthetic opaque schema; DDL semantics deliberately unavailable\n'

    def files(self):
        pg=PaidPGSnapshotTests(); model=pg.model()
        ledger=[dict(version=name[:-4],applied_at='2026-11-03T00:00:00Z') for name in self.manifest]
        for case in model['cases']:
            for snap in [*case['result']['phase_snapshots'].values(),case['runtime']['final_snapshot']]:
                snap['immutable_rows']['schema_migrations']=copy.deepcopy(ledger)
                snap['immutable_sha256']=self.rows_hash(snap['immutable_rows'])
        raw=pg.files(model)
        for case in model['cases']:
            prefix='paid-access/'+case['bank']+'/'+case['name']+'/'
            measured=json.loads(raw[prefix+'measured-runtime.json'])
            fresh={table:[] for table in pg.tables};fresh['schema_migrations']=copy.deepcopy(ledger)
            populated=measured['final_snapshot']['immutable_rows']
            migrations=dict(manifest=self.manifest,driver_sha256=hashlib.sha256(self.driver).hexdigest(),driver_exit_code=0)
            raw[prefix+'migration-driver.sql']=self.driver
            for phase,stem,rows in [('fresh','fresh',fresh),('empty_replay','replay-empty',fresh),
                                    ('populated_replay','replay-populated',populated)]:
                command=dict(exit_code=0,timed_out=False,applied=self.manifest if phase=='fresh' else [],
                    skipped=[] if phase=='fresh' else self.manifest)
                hashes=dict(ledger=self.rows_hash(ledger),schema=hashlib.sha256(self.schema).hexdigest(),data=self.rows_hash(rows))
                migrations[phase]=dict(command,**{key+'_after_sha256':value for key,value in hashes.items()})
                if phase!='fresh':migrations[phase].update({key+'_before_sha256':value for key,value in hashes.items()})
                raw[prefix+'migration-'+stem+'.json']=json.dumps(command).encode()
                raw[prefix+'migration-'+stem+'.rows.json']=json.dumps(rows).encode()
                raw[prefix+'migration-'+stem+'.schema.sql']=self.schema
                marker='APPLIED' if phase=='fresh' else 'SKIPPED'
                raw[prefix+'migration-'+stem+'.stdout']=b''.join(('AUTODATA_'+marker+' '+name+'\n').encode() for name in self.manifest)
            raw[prefix+'populated-before.rows.json']=json.dumps(populated).encode()
            raw[prefix+'populated-before.schema.sql']=self.schema
            measured['migrations']=migrations
            raw[prefix+'measured-runtime.json']=json.dumps(measured).encode()
        pg.reseal(raw)
        return raw

    def rows_hash(self, rows):return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

    def inspect(self, raw, **overrides):
        class Store:
            by_ref={ref:dict(artifact_id=ref) for ref in raw}
            def read(self, artifact_id):return raw[artifact_id]
            def read_raw_json(self, artifact_id, **_):return assembler.strict_raw_json(raw[artifact_id])
            def recheck(self):pass
        self.assertTrue(callable(getattr(assembler,'inspect_paid_migration_receipts',None)),
                        'explicit migration receipt inspection is missing')
        args=dict(candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,profile_sha256='1'*64,
            input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),host_before_sha256=hashlib.sha256(b'{}').hexdigest(),
            profile_version='paid-selector-v2',expected_driver_sha256=hashlib.sha256(self.driver).hexdigest())
        args.update(overrides)
        return assembler.inspect_paid_migration_receipts(Store(),**args)

    def test_migration_receipts_stay_unavailable_without_sql_semantics_or_authority(self):
        result=self.inspect(self.files())
        self.assertEqual(result['observed_migration_phase_count'],36)
        self.assertEqual(result['status'],'unavailable');self.assertIs(result['complete'],False)
        self.assertEqual(result['verified_case_ids'],[])
        self.assertIn('paid_migration_replay',result['missing_validation_families'])
        self.assertIn('paid_migration_schema_semantics',result['missing_validation_families'])
        self.assertIn('paid_migration_driver_provenance',result['missing_validation_families'])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_migration_phase_and_driver_contradictions_reject(self):
        baseline=self.files();prefix='paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/'
        mutations=[('manifest_order',lambda m:m['manifest'].reverse()),
            ('driver_exit_bool',lambda m:m.update(driver_exit_code=False)),
            ('driver_exit',lambda m:m.update(driver_exit_code=1)),
            ('driver_digest',lambda m:m.update(driver_sha256='0'*64)),
            ('unknown',lambda m:m.update(other=True)),
            ('phase_unknown',lambda m:m['fresh'].update(other=True)),
            ('phase_exit_bool',lambda m:m['fresh'].update(exit_code=False)),
            ('timeout',lambda m:m['empty_replay'].update(timed_out=True)),
            ('vector',lambda m:m['fresh']['applied'].pop()),
            ('before_hash',lambda m:m['populated_replay'].update(data_before_sha256='0'*64)),
            ('after_hash',lambda m:m['fresh'].update(ledger_after_sha256='0'*64))]
        for name,mutate in mutations:
            raw=copy.deepcopy(baseline);measured=json.loads(raw[prefix+'measured-runtime.json'])
            mutate(measured['migrations']);raw[prefix+'measured-runtime.json']=json.dumps(measured).encode()
            PaidPGSnapshotTests().reseal(raw)
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(raw)
        with self.assertRaises(assembler.ContractError):self.inspect(baseline,expected_driver_sha256='0'*64)

    def test_raw_receipt_marker_dump_and_schema_contradictions_reject(self):
        baseline=self.files();prefix='paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/'
        mutations=[('driver',b'wrong driver'),('fresh.json',b'{"exit_code":false,"timed_out":false,"applied":[],"skipped":[]}'),
            ('fresh.stdout',b'AUTODATA_APPLIED unknown.sql\n'),
            ('replay-empty.stdout',b'AUTODATA_SKIPPED '+self.manifest[0].encode()+b' extra\n'),
            ('replay-populated.stdout',b'AUTODATA_UNKNOWN fixture\n'),
            ('replay-empty.stdout',baseline[prefix+'migration-replay-empty.stdout'].replace(b'\n',b'\v')),
            ('fresh.stdout',baseline[prefix+'migration-fresh.stdout'].rstrip(b'\n')),
            ('fresh.rows.json',b'{}'),('replay-empty.rows.json',b'{}'),
            ('replay-populated.schema.sql',b'changed schema'),('populated-before.rows.json',b'{}'),
            ('populated-before.schema.sql',b'changed schema')]
        for name,data in mutations:
            raw=copy.deepcopy(baseline)
            ref=prefix+('migration-driver.sql' if name=='driver' else name if name.startswith('populated-') else 'migration-'+name)
            raw[ref]=data;PaidPGSnapshotTests().reseal(raw)
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_matching_hashes_cannot_hide_nonempty_fresh_and_empty_replay(self):
        raw=self.files();prefix='paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/'
        measured=json.loads(raw[prefix+'measured-runtime.json'])
        for phase,stem in [('fresh','fresh'),('empty_replay','replay-empty')]:
            ref=prefix+'migration-'+stem+'.rows.json';rows=json.loads(raw[ref])
            rows['source_snapshots']=[dict(source_snapshot_id='invented fixture data')]
            raw[ref]=json.dumps(rows).encode()
            measured['migrations'][phase]['data_after_sha256']=self.rows_hash(rows)
            if phase!='fresh':measured['migrations'][phase]['data_before_sha256']=self.rows_hash(rows)
        raw[prefix+'measured-runtime.json']=json.dumps(measured).encode()
        PaidPGSnapshotTests().reseal(raw)
        with self.assertRaisesRegex(assembler.ContractError,'^paid_migration_nonempty_fresh$'):self.inspect(raw)

    def test_real_artifact_store_migration_receipts_are_still_unavailable(self):
        raw=self.files()
        with tempfile.TemporaryDirectory() as directory:
            artifacts=[]
            for index,(ref,data) in enumerate(raw.items()):
                path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                artifacts.append(dict(artifact_id='raw-'+str(index),kind='raw',ref=ref,
                    sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),visibility='private'))
            with assembler.ArtifactStore(directory,artifacts) as store:
                result=assembler.inspect_paid_migration_receipts(store,candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,
                    profile_sha256='1'*64,input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),
                    host_before_sha256=hashlib.sha256(b'{}').hexdigest(),profile_version='paid-selector-v2',
                    expected_driver_sha256=hashlib.sha256(self.driver).hexdigest())
            self.assertEqual(result['status'],'unavailable');self.assertEqual(result['observed_migration_phase_count'],36)
            self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_ledger_requires_exact_typed_001_040_inventory(self):
        self.assertTrue(callable(getattr(assembler,'_paid_migration_rows',None)))
        raw={table:[] for table in PaidPGSnapshotTests.tables}
        raw['schema_migrations']=[dict(version=name[:-4],applied_at='2026-11-03T00:00:00Z') for name in self.manifest]
        assembler._paid_migration_rows(raw)
        for name,mutate in [('duplicate',lambda r:r['schema_migrations'].__setitem__(1,copy.deepcopy(r['schema_migrations'][0]))),
            ('missing',lambda r:r['schema_migrations'].pop()),
            ('unknown_version',lambda r:r['schema_migrations'][0].update(version='001_wrong')),
            ('timestamp',lambda r:r['schema_migrations'][0].update(applied_at='yesterday')),
            ('timestamp_type',lambda r:r['schema_migrations'][0].update(applied_at=True)),
            ('unknown_column',lambda r:r['schema_migrations'][0].update(other=1)),
            ('table',lambda r:r.update(other=[]))]:
            altered=copy.deepcopy(raw);mutate(altered)
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):assembler._paid_migration_rows(altered)


if __name__ == '__main__': unittest.main()
