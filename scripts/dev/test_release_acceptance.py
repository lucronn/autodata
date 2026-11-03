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
                        paid_case_identities=DEFAULT, dto_case_identities=DEFAULT) as mocks:
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


if __name__ == '__main__': unittest.main()
