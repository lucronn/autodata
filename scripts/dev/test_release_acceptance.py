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
                        inspect_paid_migration_receipts=DEFAULT, inspect_paid_selector_work=DEFAULT,
                        inspect_paid_http_receipts=DEFAULT, inspect_paid_scope_receipts=DEFAULT,
                        inspect_dto_receipts=DEFAULT) as mocks:
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
    # Retained v2 producer digest of scripts/dev/migrate_sql.sh; no authority claim.
    runner_sha256 = '4970eab6f20be35c354547ed5acf73c991dae1a83433094715f051463790a8f3'
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
            migrations=dict(manifest=self.manifest,driver_sha256=hashlib.sha256(self.driver).hexdigest(),
                driver_exit_code=0,runner_sha256=self.runner_sha256)
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

    def test_runner_digest_requires_producer_shape_and_strict_hash_scalar(self):
        baseline=self.files();prefix='paid-access/bankone/'+assembler.PAID_GO_ROOTS[0]+'/'
        migrations=json.loads(baseline[prefix+'measured-runtime.json'])['migrations']
        self.assertEqual(set(migrations),{'manifest','driver_sha256','driver_exit_code',
            'runner_sha256','fresh','empty_replay','populated_replay'})
        self.assertEqual(migrations['runner_sha256'],self.runner_sha256)
        result=self.inspect(baseline)
        self.assertEqual(result['status'],'unavailable')
        self.assertIn('paid_migration_driver_provenance',result['missing_validation_families'])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))
        for value in (None,True,0,[],{},'',self.runner_sha256.upper(),self.runner_sha256[:-1],
                      self.runner_sha256+'0',' '+self.runner_sha256):
            raw=copy.deepcopy(baseline);measured=json.loads(raw[prefix+'measured-runtime.json'])
            measured['migrations']['runner_sha256']=value
            raw[prefix+'measured-runtime.json']=json.dumps(measured).encode()
            PaidPGSnapshotTests().reseal(raw)
            with self.subTest(value=value),self.assertRaisesRegex(assembler.ContractError,'^invalid_digest$'):
                self.inspect(raw)
        raw=copy.deepcopy(baseline);measured=json.loads(raw[prefix+'measured-runtime.json'])
        del measured['migrations']['runner_sha256']
        raw[prefix+'measured-runtime.json']=json.dumps(measured).encode();PaidPGSnapshotTests().reseal(raw)
        with self.assertRaisesRegex(assembler.ContractError,'^invalid_object_keys$'):self.inspect(raw)

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




class PaidSelectorWorkTests(unittest.TestCase):
    """Independent synthetic selector observations; no product receipt authority."""
    root = 'TestPostgresPaidCatalogGrantBeforeWork'
    phases = ('before', 'selectors', 'unpaid', 'expired', 'paid_cold', 'unavailable')
    routes = ('/v1/catalog/makes?year=2024',
              '/v1/catalog/models?year=2024&make=example',
              '/v1/catalog/configurations?year=2024&make=example&model=car')

    @classmethod
    def setUpClass(cls):
        cls.baseline = PaidMigrationReceiptTests().files()
        for bank in ('bankone', 'banktwo'):
            def populate(measured):
                requests = []
                for index, scope in enumerate(('makes', 'models', 'configurations')):
                    payload = dict(scope=scope, year=2024, region='US',
                                   idempotency_key='catalog-hydration:'+str(index+1)*24)
                    if scope != 'makes': payload['make'] = 'example'
                    if scope == 'configurations': payload['model'] = 'car'
                    requests.append(dict(completed=True, duration_seconds=0.5,
                        started_at='2026-11-03T00:00:00.1Z', finished_at='2026-11-03T00:00:00.2Z',
                        payload=payload, request_id='', scope=scope, status=200))
                for index, phase in enumerate(cls.phases):
                    snapshot = measured['snapshots'][phase]
                    snapshot.update(identity_checks=max(0,index-1), grant_calls=max(0,index-1))
                    if phase != 'before':
                        snapshot.update(selector_ensure=dict(entered=3,completed=3,active=0),
                            selector_ensure_requests=copy.deepcopy(requests),
                            provider_calls=dict(bankone=3,banktwo=3),
                            provider_traces=dict(bankone=list(cls.routes),banktwo=list(reversed(cls.routes))))
                final = copy.deepcopy(measured['snapshots']['unavailable'])
                del final['reader_calls']; del final['identity_checks']
                measured['final_snapshot'] = final
            cls.alter(cls.baseline, populate, bank=bank)

    @classmethod
    def alter(cls, raw, mutation, *, bank='bankone'):
        """Repair copy/hash seams so semantic mutations reach the new inspector."""
        prefix = 'paid-access/'+bank+'/'+cls.root+'/'
        measured = json.loads(raw[prefix+'measured-runtime.json']); mutation(measured)
        raw[prefix+'measured-runtime.json'] = json.dumps(measured).encode()
        measurement = json.loads(raw[prefix+'go-measurement.json'])
        measurement['phase_snapshots'] = copy.deepcopy(measured['snapshots'])
        raw[prefix+'go-measurement.json'] = json.dumps(measurement).encode()
        collector = json.loads(raw['workshop-paid-access.json'])
        collector['case_results'][cls.root+'-'+bank]['phase_snapshots'] = copy.deepcopy(measured['snapshots'])
        raw['workshop-paid-access.json'] = json.dumps(collector).encode()
        PaidPGSnapshotTests().reseal(raw)

    def invocation(self, **overrides):
        args = dict(candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,profile_sha256='1'*64,
            input_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),host_before_sha256=hashlib.sha256(b'{}').hexdigest(),
            expected_driver_sha256=hashlib.sha256(PaidMigrationReceiptTests.driver).hexdigest(),
            profile_version='paid-selector-v2')
        args.update(overrides)
        return args

    def inspect(self, raw, **overrides):
        class Store:
            by_ref = {ref:dict(artifact_id=ref) for ref in raw}
            def read(self, artifact_id): return raw[artifact_id]
            def read_raw_json(self, artifact_id, **_): return assembler.strict_raw_json(raw[artifact_id])
            def recheck(self): pass
        self.assertTrue(callable(getattr(assembler,'inspect_paid_selector_work',None)),
                        'explicit internal selector-work inspector is missing')
        return assembler.inspect_paid_selector_work(Store(), **self.invocation(**overrides))

    def real_store(self, raw, directory):
        artifacts=[]
        for index,(ref,data) in enumerate(raw.items()):
            path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            artifacts.append(dict(artifact_id='raw-'+str(index),kind='raw',ref=ref,
                sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),visibility='private'))
        return assembler.ArtifactStore(directory,artifacts)

    def assert_unavailable(self, result):
        self.assertEqual(result['status'],'unavailable'); self.assertIs(result['complete'],False)
        self.assertEqual(result['verified_case_ids'],[])
        self.assertEqual(result['observed_selector_case_ids'],[self.root+'-bankone',self.root+'-banktwo'])
        self.assertEqual(result['observed_selector_snapshot_count'],14)
        previous=PaidMigrationReceiptTests().inspect(self.baseline)
        self.assertEqual(result['missing_validation_families'],previous['missing_validation_families']+
            ['paid_selector_http_outcomes','paid_selector_request_provenance'])
        self.assertEqual(set(result)-set(previous),{'observed_selector_case_ids','observed_selector_snapshot_count'})
        for key in previous:
            if key!='missing_validation_families': self.assertEqual(result[key],previous[key])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_selector_receipts_add_only_incomplete_diagnostics(self):
        self.assert_unavailable(self.inspect(self.baseline))

    def test_closed_request_and_payload_fields_are_enforced_beyond_hash_consistency(self):
        mutations=[]
        receipt_fields=('completed','duration_seconds','finished_at','payload','request_id','scope','started_at','status')
        for key in receipt_fields:
            mutations.append(('missing-'+key,lambda req,k=key:req.pop(k)))
        mutations += [('extra',lambda req:req.update(extra=True)),
            ('not-completed',lambda req:req.update(completed=False)),
            ('bool-completed',lambda req:req.update(completed=1)),
            ('request-id',lambda req:req.update(request_id='unexpected'))]
        for key in ('scope','year','region','idempotency_key'):
            mutations.append(('missing-payload-'+key,lambda req,k=key:req['payload'].pop(k)))
        for key,value in [('year',True),('year',2025),('year','2024'),('region','CA'),('scope','models'),
                          ('idempotency_key','catalog-hydration:'+'A'*24),
                          ('idempotency_key','catalog-hydration:'+'1'*23),('idempotency_key','other:'+'1'*24),
                          ('vehicle_id','00000000-0000-0000-0000-000000000001')]:
            mutations.append(('payload-'+key+'-'+str(value),lambda req,k=key,v=value:req['payload'].update({k:v})))
        for value in (True,'200',None,201):
            mutations.append(('status-'+str(value),lambda req,v=value:req.update(status=v)))
        for value in (True,'0.5',None,-1,121):
            mutations.append(('duration-'+str(value),lambda req,v=value:req.update(duration_seconds=v)))
        for key,value in [('started_at','2026-11-03T00:00:00.3Z'),
            ('started_at','2026-11-02T23:59:59Z'),('finished_at','2026-11-03T00:00:02Z'),
            ('started_at','2026-11-03T01:00:00.1+01:00'),('finished_at',True)]:
            mutations.append((key+'-'+str(value),lambda req,k=key,v=value:req.update({k:v})))
        for name,mutation in mutations:
            raw=dict(self.baseline)
            self.alter(raw,lambda m:[mutation(s['selector_ensure_requests'][0])
                for s in [*m['snapshots'].values(),m['final_snapshot']] if s['selector_ensure_requests']])
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError): self.inspect(raw)
        for index,key,value in [(1,'make','wrong'),(2,'model','wrong'),(1,'make',None),(2,'model',None)]:
            raw=dict(self.baseline)
            self.alter(raw,lambda m:[s['selector_ensure_requests'][index]['payload'].update({key:value})
                for s in [*m['snapshots'].values(),m['final_snapshot']] if s['selector_ensure_requests']])
            with self.subTest(index=index,key=key,value=value),self.assertRaises(assembler.ContractError): self.inspect(raw)

    def test_request_inventory_and_later_copy_drift_cannot_hide_behind_pass_flags(self):
        mutations=[('missing',lambda m:m['snapshots']['selectors']['selector_ensure_requests'].pop()),
            ('extra',lambda m:m['snapshots']['selectors']['selector_ensure_requests'].append(copy.deepcopy(m['snapshots']['selectors']['selector_ensure_requests'][0]))),
            ('duplicate-scope',lambda m:m['snapshots']['selectors']['selector_ensure_requests'].__setitem__(1,copy.deepcopy(m['snapshots']['selectors']['selector_ensure_requests'][0]))),
            ('duplicate-key',lambda m:m['snapshots']['selectors']['selector_ensure_requests'][1]['payload'].update(idempotency_key='catalog-hydration:'+'1'*24)),
            ('later-order',lambda m:m['snapshots']['unpaid']['selector_ensure_requests'].reverse()),
            ('later-time',lambda m:m['snapshots']['unpaid']['selector_ensure_requests'][0].update(finished_at='2026-11-03T00:00:00.25Z')),
            ('final-copy',lambda m:m['final_snapshot']['selector_ensure_requests'][0].update(duration_seconds=0.6)),
            ('before-request',lambda m:m['snapshots']['before']['selector_ensure_requests'].append(copy.deepcopy(m['snapshots']['selectors']['selector_ensure_requests'][0])))]
        for name,mutation in mutations:
            raw=dict(self.baseline);self.alter(raw,mutation)
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError): self.inspect(raw)

    def test_exact_decimal_duration_boundaries_survive_binary_rounding(self):
        for token,valid in [('0',True),('120',True),('0.00000000000000000000000001',True),
            ('-0.00000000000000000000000000000000000001',False),('-1e-999',False),
            ('120.00000000000000000000000000000000000001',False),('NaN',False),('Infinity',False),('1e999',False)]:
            raw=dict(self.baseline)
            def mutate(m):
                for s in [*m['snapshots'].values(),m['final_snapshot']]:
                    for request in s['selector_ensure_requests']: request['duration_seconds']='NUMBER_TOKEN'
            self.alter(raw,mutate)
            raw={ref:data.replace(b'"NUMBER_TOKEN"',token.encode()) for ref,data in raw.items()}
            PaidPGSnapshotTests().reseal(raw)
            with self.subTest(token=token):
                if valid: self.assert_unavailable(self.inspect(raw))
                else:
                    code='^paid_selector_duration$' if token not in ('NaN','Infinity','1e999') else 'nonfinite_number'
                    with self.assertRaisesRegex(assembler.ContractError,code): self.inspect(raw)

    def test_exact_decimal_request_copy_changes_cannot_round_to_the_same_float(self):
        prefix='paid-access/bankone/'+self.root+'/'
        for ref in (prefix+'go-measurement.json',prefix+'result.json','workshop-paid-access.json'):
            raw=dict(self.baseline)
            raw[ref]=raw[ref].replace(b'"duration_seconds": 0.5',
                b'"duration_seconds": 0.50000000000000000000000000000001',1)
            if ref.endswith('go-measurement.json'): PaidPGSnapshotTests().reseal(raw)
            with self.subTest(ref=ref),self.assertRaisesRegex(assembler.ContractError,'^paid_selector_copy_drift$'):
                self.inspect(raw)

    def test_initial_concurrent_order_and_incidental_progress_counts_are_not_hardcoded(self):
        raw=dict(self.baseline)
        def reorder(m):
            for phase in self.phases[1:]:
                s=m['snapshots'][phase];s['selector_ensure_requests'].reverse()
                for bank in ('bankone','banktwo'):s['provider_traces'][bank].reverse()
            for phase,index in zip(self.phases[2:],(10,20,30,40)):
                m['snapshots'][phase].update(grant_calls=index,identity_checks=index+1)
            m['final_snapshot']['selector_ensure_requests'].reverse()
            for bank in ('bankone','banktwo'):m['final_snapshot']['provider_traces'][bank].reverse()
            m['final_snapshot']['grant_calls']=40
        self.alter(raw,reorder)
        self.assert_unavailable(self.inspect(raw))

    def test_metadata_and_later_work_must_stay_zero(self):
        # Check every phase plus the final snapshot for article/model work.
        for phase in self.phases+('final_snapshot',):
            for field in ('model_calls','payment_calls'):
                raw=dict(self.baseline)
                self.alter(raw,lambda m,p=phase,f=field:(m['final_snapshot'] if p=='final_snapshot' else m['snapshots'][p]).update({f:1}))
                with self.subTest(phase=phase,field=field),self.assertRaises(assembler.ContractError):self.inspect(raw)
        for field in ('source_calls','asset_calls'):
            for bank in ('bankone','banktwo'):
                raw=dict(self.baseline);self.alter(raw,lambda m:m['snapshots']['unpaid'][field].update({bank:1}))
                with self.subTest(field=field,bank=bank),self.assertRaises(assembler.ContractError):self.inspect(raw)
        for field in ('article_jobs','source_revisions','canonical_revisions','published_revisions','publication_events','source_observations'):
            raw=dict(self.baseline);self.alter(raw,lambda m:m['snapshots']['selectors']['counts'].update({field:1}))
            # PG-derived counters already reject this independent contradiction.
            with self.subTest(count=field),self.assertRaises(assembler.ContractError):self.inspect(raw)
        mutations=[('reader',lambda s:s.update(reader_calls=1)),
            ('ensure',lambda s:s.update(ensure=dict(entered=1,completed=1,active=0),ensure_requests=[{'scope':'article'}])),
            ('selector-count',lambda s:s.update(selector_ensure=dict(entered=2,completed=2,active=0),selector_ensure_requests=s['selector_ensure_requests'][:2])),
            ('proxy',lambda s:s['proxy'].update(request_received=1)),
            ('capture',lambda s:s['proxy'].update(response_captured=True)),
            ('errors',lambda s:s['proxy'].update(errors=['observed-error'])),
            ('workers',lambda s:s['workers'].append(dict(kind='cli',alive=True,exit_code=None)))]
        for name,mutate in mutations:
            raw=dict(self.baseline);self.alter(raw,lambda m:mutate(m['snapshots']['selectors']))
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_provider_trace_inventory_is_literal_and_stable(self):
        for value in ['',self.routes[0], 'https://example.invalid'+self.routes[1],
            self.routes[1]+'#fragment',self.routes[1]+'&extra=1',self.routes[1]+'&year=2024',
            '/v1/catalog/%6dodels?year=2024&make=example', '/v1/catalog/articles?year=2024']:
            raw=dict(self.baseline)
            self.alter(raw,lambda m:[s['provider_traces']['bankone'].__setitem__(1,value)
                for s in [*m['snapshots'].values(),m['final_snapshot']] if s['provider_traces']['bankone']])
            with self.subTest(route=value),self.assertRaises(assembler.ContractError):self.inspect(raw)
        for name,mutation in [('extra',lambda s:s['provider_traces']['bankone'].append(self.routes[0])),
            ('missing',lambda s:s['provider_traces']['bankone'].pop()),
            ('count',lambda s:s['provider_calls'].update(bankone=4)),
            ('later-order',lambda s:s['provider_traces']['banktwo'].reverse())]:
            raw=dict(self.baseline);self.alter(raw,lambda m:mutation(m['snapshots']['unpaid']))
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_monotone_identity_grant_progression_and_final_grant_binding(self):
        for field in ('grant_calls','identity_checks'):
            for phase in ('before','selectors','expired'):
                raw=dict(self.baseline)
                value=1 if phase in ('before','selectors') else 0
                self.alter(raw,lambda m:m['snapshots'][phase].update({field:value}))
                with self.subTest(field=field,phase=phase),self.assertRaises(assembler.ContractError):self.inspect(raw)
        raw=dict(self.baseline);self.alter(raw,lambda m:m['final_snapshot'].update(grant_calls=5))
        with self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_parent_hash_copy_and_identity_guards_are_not_bypassed(self):
        for name,override in [('candidate',dict(candidate_sha='2'*40)),('base',dict(trusted_base_sha='invalid')),
            ('profile',dict(profile_sha256='invalid')),('version',dict(profile_version='other'))]:
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(self.baseline,**override)
        prefix='paid-access/bankone/'+self.root+'/'
        for name in ('raw-hash','copy','missing','mixed-candidate','bank','nested-base','nested-profile'):
            raw=dict(self.baseline)
            if name=='raw-hash':raw[prefix+'measured-runtime.json']+=b' '
            elif name=='copy':
                m=json.loads(raw[prefix+'go-measurement.json']);m['phase_snapshots']['selectors']['grant_calls']=99
                raw[prefix+'go-measurement.json']=json.dumps(m).encode();PaidPGSnapshotTests().reseal(raw)
            elif name=='missing':del raw[prefix+'measured-runtime.json']
            else:
                key,value={'mixed-candidate':('candidate_sha','2'*40),'bank':('provider','banktwo'),
                    'nested-base':('trusted_base_sha','2'*40),'nested-profile':('profile_sha256','2'*64)}[name]
                self.alter(raw,lambda m:m.update({key:value}) if name in ('mixed-candidate','bank') else m['snapshots']['before']['article'].update({key:value}))
            with self.subTest(mutation=name),self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_real_confined_store_valid_and_semantic_mutation_remain_conservative(self):
        for valid in (True,False):
            raw=dict(self.baseline)
            if not valid:self.alter(raw,lambda m:m['snapshots']['selectors']['selector_ensure_requests'][0]['payload'].update(year=2025))
            with tempfile.TemporaryDirectory() as directory,self.real_store(raw,directory) as store:
                if valid:self.assert_unavailable(assembler.inspect_paid_selector_work(store,**self.invocation()))
                else:
                    with self.assertRaises(assembler.ContractError):assembler.inspect_paid_selector_work(store,**self.invocation())

    def test_real_confined_store_rejects_missing_symlink_and_post_read_mutation(self):
        prefix='paid-access/bankone/'+self.root+'/';ref=prefix+'measured-runtime.json'
        for mutation in ('missing','symlink','post-read'):
            with tempfile.TemporaryDirectory() as directory,self.real_store(self.baseline,directory) as store:
                path=Path(directory)/ref
                if mutation=='missing':path.unlink()
                elif mutation=='symlink':path.unlink();path.symlink_to(Path(directory)/'host-before.json')
                else:
                    original=store.read_raw_json
                    def changed(artifact_id,**kwargs):
                        value=original(artifact_id,**kwargs)
                        if artifact_id==store.by_ref[ref]['artifact_id']:path.write_bytes(path.read_bytes()+b' ')
                        return value
                    store.read_raw_json=changed
                with self.subTest(mutation=mutation),self.assertRaises(assembler.ContractError):
                    assembler.inspect_paid_selector_work(store,**self.invocation())


class PaidHTTPReceiptTests(unittest.TestCase):
    """Independent projected HTTP receipts, never raw wire or runtime evidence."""
    root = 'TestPostgresPaidCatalogGrantBeforeWork'
    phases = ('before', 'selectors', 'unpaid', 'expired', 'paid_cold', 'unavailable')
    configuration = '00000000-0000-0000-0000-000000000030'
    vehicle = '00000000-0000-0000-0000-000000000040'
    article_ids = ('00000000-0000-0000-0000-000000000001',
                   '00000000-0000-0000-0000-000000000002')
    media = '/v1/catalog/images/[sha256:e0b1bb59f4515880aab8a8b144d8f4e20236fcac5bbf55768f92fe3d17c02f01]'
    invocation = PaidSelectorWorkTests.invocation
    real_store = PaidSelectorWorkTests.real_store

    @classmethod
    def setUpClass(cls):
        PaidSelectorWorkTests.setUpClass()
        cls.baseline = dict(PaidSelectorWorkTests.baseline)
        for bank in ('bankone', 'banktwo'):
            def populate(m):
                articles = [dict(canonical_article_id=aid, provider_slug=provider,
                    vehicle_configuration_id=cls.configuration, vehicle_id=cls.vehicle, title='Pump',
                    current_source_revision_id=None, current_canonical_revision_id=None,
                    current_job_id=None) for aid,provider in zip(cls.article_ids,('bankone','banktwo'))]
                for snap in [*m['snapshots'].values(),m['final_snapshot']]:
                    snap['article'] = copy.deepcopy(articles[0 if bank=='bankone' else 1])
                    snap['immutable_rows']['canonical_articles'] = copy.deepcopy(articles)
                for phase,count in zip(cls.phases,(0,0,5,5,7,9)):
                    m['snapshots'][phase]['identity_checks'] = count
                m['identity_checks'] = 9
                m['http_observations'] = cls.observations(bank)
            cls.alter(cls.baseline, populate, bank=bank)

    @classmethod
    def observations(cls, bank):
        # Literal test schema, independent of production validators/builders.
        aid=cls.article_ids[0 if bank=='bankone' else 1]
        listing='/v1/catalog/vehicles/'+cls.configuration+'/articles'; detail=listing+'/'+aid
        paths=['/v1/catalog/years','/v1/catalog/years/2024/makes',
            '/v1/catalog/years/2024/makes/example/models',
            '/v1/catalog/years/2024/makes/example/models/car/configurations',
            listing,detail,detail+'/source',detail+'/prepare',cls.media,
            listing,detail,detail+'/source',detail+'/prepare',cls.media,listing,detail,detail,detail]
        bodies=[dict(items=[dict(year=2024)],version='v1'),
            dict(complete=False,hydrating=True,items=[dict(id='example',name='Example')],version='v1'),
            dict(complete=False,hydrating=True,items=[dict(id='car',name='Car')],version='v1')]
        configs=[dict(complete=True,id=cid,make='Example',model='Car',region=region,trim=trim,
            vehicle_id=cls.vehicle,year=2024) for cid,trim,region in
            [(cls.configuration,'Paid selected','US'),('00000000-0000-0000-0000-000000000031','Paid adjacent','US'),
             ('00000000-0000-0000-0000-000000000032','Paid other region','CA')]]
        bodies.append(dict(complete=False,hydrating=False,items=configs,version='v1'))
        error_specs=[('ENTITLEMENT_REQUIRED','Purchase access to this vehicle configuration.',{},False)]*4
        error_specs += [('CATALOG_NOT_FOUND','Catalog resource was not found.',{},False)]
        error_specs += [('UNAUTHENTICATED','Authentication is required.',dict(login_available=True),False)]*5
        for index,(code,message,details,retryable) in enumerate(error_specs):
            bodies.append(dict(error=dict(code=code,message=message,details=copy.deepcopy(details),
                retryable=retryable,request_id='00000000-0000-0000-0000-'+format(index+100,'012x'))))
        items=[dict(availability='unavailable',canonical_article_id=article,canonical_revision_id=None,
            complete=False,content_origin=None,content_status='list_only',id=article,images=[],processing=None,
            review_status='UNREVIEWED',source_revision_id=None,title='Pump',vehicle_id=cls.configuration,
            view_revision=None) for article in cls.article_ids]
        bodies.append(dict(complete=True,hydrating=False,items=items,version='v1',
            progress=dict(complete=True,percent=100,phase='indexing',processed=2,retryable=False,status='completed',total=2)))
        for index,(code,message,details) in enumerate([
            ('CATALOG_SOURCE_UNAVAILABLE','Article is temporarily unavailable.',dict(article_id=aid,retry_after_seconds=2)),
            ('CATALOG_UNAVAILABLE','Catalog is temporarily unavailable.',{}),
            ('AUTHENTICATION_UNAVAILABLE','Authentication is temporarily unavailable.',dict(login_available=True))]):
            bodies.append(dict(error=dict(code=code,message=message,details=details,retryable=True,
                request_id='00000000-0000-0000-0000-'+format(index+200,'012x'))))
        counts=[(0,0)]*4+[(0,1),(1,2),(2,3),(3,4),(4,5)]+[(5,5)]*5+[(5,6),(6,7),(7,8),(8,9)]
        rows=[]
        for i,(path,body,(before,after)) in enumerate(zip(paths,bodies,counts)):
            headers={'Content-Type':'application/json'}
            if i>=4:headers.update({'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
            if i==15:headers['Retry-After']='2'
            rows.append(dict(method='POST' if i in (7,12) else 'GET',path=path,
                owner_index=-1 if i<4 else 1 if 9<=i<=13 else 0,
                status=200 if i<4 or i==14 else 403 if i<8 else 404 if i==8 else 401 if i<14 else 503,
                headers=headers,body=body,body_sha256='a'*64,body_size=1,body_truncated=False,
                reader_before=0,reader_after=0,identity_before=before,identity_after=after))
        return rows

    @classmethod
    def alter(cls, raw, mutation, *, bank='bankone'):
        """Repair all semantic copies, PG row hashes, migration and result seams."""
        prefix='paid-access/'+bank+'/'+cls.root+'/'
        m=json.loads(raw[prefix+'measured-runtime.json']);mutation(m)
        for snap in [*m['snapshots'].values(),m['final_snapshot']]:
            snap['immutable_sha256']=PaidMigrationReceiptTests().rows_hash(snap['immutable_rows'])
        rows=m['final_snapshot']['immutable_rows']
        for name in ('migration-replay-populated.rows.json','populated-before.rows.json'):
            raw[prefix+name]=json.dumps(rows).encode()
        for side in ('before','after'):
            m['migrations']['populated_replay']['data_'+side+'_sha256']=PaidMigrationReceiptTests().rows_hash(rows)
        raw[prefix+'measured-runtime.json']=json.dumps(m).encode()
        measurement=json.loads(raw[prefix+'go-measurement.json'])
        measurement['phase_snapshots']=copy.deepcopy(m['snapshots'])
        for key in ('http_observations','identity_checks','reader_calls','held_model_receipt','observed_views'):
            measurement[key]=copy.deepcopy(m[key])
        raw[prefix+'go-measurement.json']=json.dumps(measurement).encode()
        collector=json.loads(raw['workshop-paid-access.json'])
        collector['case_results'][cls.root+'-'+bank]['phase_snapshots']=copy.deepcopy(m['snapshots'])
        raw['workshop-paid-access.json']=json.dumps(collector).encode()
        PaidPGSnapshotTests().reseal(raw)

    def inspect(self, raw, **overrides):
        class Store:
            by_ref={ref:dict(artifact_id=ref) for ref in raw}
            def read(self, artifact_id):return raw[artifact_id]
            def read_raw_json(self, artifact_id, **_):return assembler.strict_raw_json(raw[artifact_id])
            def recheck(self):pass
        self.assertTrue(callable(getattr(assembler,'inspect_paid_http_receipts',None)),
            'explicit internal HTTP receipt inspector is missing')
        return assembler.inspect_paid_http_receipts(Store(),**self.invocation(**overrides))

    def assert_unavailable(self, result, raw):
        previous=PaidSelectorWorkTests().inspect(raw)
        self.assertEqual(set(result)-set(previous),{'observed_http_case_ids','observed_http_observation_count'})
        for key,value in previous.items():
            self.assertEqual(result[key],value if key!='missing_validation_families' else value+
                ['paid_http_wire_body_provenance','paid_http_transport_authority'])
        self.assertEqual(result['observed_http_case_ids'],[self.root+'-bankone',self.root+'-banktwo'])
        self.assertEqual(result['observed_http_observation_count'],36)
        self.assertEqual(result['status'],'unavailable');self.assertIs(result['complete'],False)
        self.assertEqual(result['verified_case_ids'],[])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_projected_receipts_add_only_incomplete_diagnostics(self):
        self.assert_unavailable(self.inspect(self.baseline),self.baseline)

    def check_mutations(self, mutations, code):
        for name,mutation in mutations:
            raw=dict(self.baseline);self.alter(raw,mutation)
            with self.subTest(mutation=name),self.assertRaisesRegex(assembler.ContractError,'^'+code+'$'):
                self.inspect(raw)

    def test_observation_inventory_and_closed_fields(self):
        self.check_mutations([
            ('missing',lambda m:m['http_observations'].pop()),
            ('extra',lambda m:m['http_observations'].append(copy.deepcopy(m['http_observations'][0])))], 'paid_http_inventory')
        fields=tuple(self.observations('bankone')[0])
        self.check_mutations([(key,lambda m,k=key:m['http_observations'][0].pop(k)) for key in fields]+
            [('extra',lambda m:m['http_observations'][0].update(secret='x'))], 'paid_http_row')
        self.check_mutations([(str(v),lambda m,v=v:m['http_observations'].__setitem__(0,v))
            for v in (None,[],1)],'paid_http_shape')

    def test_declared_digest_size_and_primitive_types(self):
        mutations=[]
        for field in ('owner_index','status','body_size','reader_before','reader_after','identity_before','identity_after'):
            for v in (True,'1',None,0.5):
                mutations.append((field+str(v),lambda m,f=field,v=v:m['http_observations'][0].update({f:v})))
        for field,values in [('body_sha256',('A'*64,'','x'*64,None)),('body_size',(0,262145,-1)),
                             ('body_truncated',(True,0,None)),('method',(None,1)),('path',(None,1))]:
            for v in values:mutations.append((field+str(v),lambda m,f=field,v=v:m['http_observations'][0].update({f:v})))
        self.check_mutations(mutations,'paid_http_row')
        for size in (1,262144):
            raw=dict(self.baseline)
            self.alter(raw,lambda m:[r.update(body_size=size,body_sha256='f'*64,
                body=dict(reversed(list(r['body'].items())))) for r in m['http_observations']])
            self.assert_unavailable(self.inspect(raw),raw)
        for token in ('NaN','Infinity','1e999'):
            raw=dict(self.baseline);self.alter(raw,lambda m:m['http_observations'][0].update(body_size='TOKEN'))
            raw={ref:data.replace(b'"TOKEN"',token.encode()) for ref,data in raw.items()}
            PaidPGSnapshotTests().reseal(raw)
            with self.subTest(token=token),self.assertRaisesRegex(assembler.ContractError,'nonfinite_number'):
                self.inspect(raw)

    def test_every_route_owner_status_method_and_order_transition(self):
        mutations=[]
        for i in range(18):
            for field,value in [('method','DELETE'),('owner_index',2),('status',201)]:
                mutations.append((str(i)+field,lambda m,i=i,f=field,v=value:m['http_observations'][i].update({f:v})))
        route=self.observations('bankone')[5]['path']
        for value in ('https://example.invalid'+route,route.replace(self.configuration,self.vehicle),
            route.replace(self.article_ids[0],self.article_ids[1]),route.replace(self.configuration,'00000000-0000-0000-0000-000000000031'),
            route.replace('00000000','%300000000',1),route+'/',route+'?x=1',route+'#x',route.upper()):
            mutations.append((value,lambda m,v=value:m['http_observations'][5].update(path=v)))
        for value in (self.media.replace('e0b1','e0b2'),'/v1/catalog/images/invalid-token'):
            mutations.append((value,lambda m,v=value:m['http_observations'][8].update(path=v)))
        mutations += [('duplicate',lambda m:m['http_observations'].__setitem__(1,copy.deepcopy(m['http_observations'][0]))),
            ('reordered',lambda m:m['http_observations'].reverse())]
        self.check_mutations(mutations,'paid_http_route')

    def test_http_and_phase_counters_bind_without_implying_timing(self):
        mutations=[]
        for i in range(18):
            for field in ('reader_before','reader_after','identity_before','identity_after'):
                mutations.append((str(i)+field,lambda m,i=i,f=field:m['http_observations'][i].update({f:99})))
        for i in (0,):
            for field in ('reader_before','reader_after','identity_before','identity_after'):
                mutations.append((str(i)+field+'negative',lambda m,i=i,f=field:m['http_observations'][i].update({f:-1})))
        mutations += [('total',lambda m:m.update(identity_checks=10)),
            ('reader-total',lambda m:m.update(reader_calls=1)),('held',lambda m:m.update(held_model_receipt={})),
            ('phase',lambda m:m['snapshots']['expired'].update(identity_checks=6))]
        self.check_mutations(mutations,'paid_http_counter')

    def test_header_projection_is_closed_and_phase_specific(self):
        mutations=[]
        for i in range(18):
            headers=self.observations('bankone')[i]['headers']
            for key in headers:
                mutations.append((str(i)+key,lambda m,i=i,k=key:m['http_observations'][i]['headers'].pop(k)))
            for value in (None,[],{'content-type':'application/json'},dict(headers,Secret='x')):
                mutations.append((str(i)+str(value),lambda m,i=i,v=value:m['http_observations'][i].update(headers=v)))
            for key in headers:
                for value in (None,1,'wrong'):
                    mutations.append((str(i)+key+str(value),lambda m,i=i,k=key,v=value:m['http_observations'][i]['headers'].update({k:v})))
        for i in (16,17):mutations.append((str(i)+'retry',lambda m,i=i:m['http_observations'][i]['headers'].update({'Retry-After':'2'})))
        self.check_mutations(mutations,'paid_http_headers')

    def test_closed_nested_body_inventories(self):
        # Catch omission/extension at every distinct nested closed schema.
        locations=[(0,()),(0,('items',0)),(1,()),(1,('items',0)),(2,()),(2,('items',0)),
            (3,()),(3,('items',0)),(4,()),(4,('error',)),(4,('error','details')),(9,('error','details')),
            (14,()),(14,('progress',)),(14,('items',0)),(15,('error','details'))]
        mutations=[]
        def at(m,i,path):
            v=m['http_observations'][i]['body']
            for key in path:v=v[key]
            return v
        for i,path in locations:
            value=self.observations('bankone')[i]['body']
            for key in path:value=value[key]
            for key in value:
                mutations.append((str((i,path,key)),lambda m,i=i,p=path,k=key:at(m,i,p).pop(k)))
            mutations.append((str((i,path,'extra')),lambda m,i=i,p=path:at(m,i,p).update(secret='x')))
            if path:
                for replacement in (None,[]):
                    def replace(m,i=i,p=path,v=replacement):
                        parent=at(m,i,p[:-1]);parent[p[-1]]=copy.deepcopy(v)
                    mutations.append((str((i,path,replacement)),replace))
        for i in range(18):
            for value in (None,[],1):mutations.append((str(i)+str(value),lambda m,i=i,v=value:m['http_observations'][i].update(body=v)))
        self.check_mutations(mutations,'paid_http_body')

    def test_body_scalars_cardinality_and_error_semantics(self):
        mutations=[('year',lambda m:m['http_observations'][0]['body']['items'][0].update(year=True)),
            ('version',lambda m:m['http_observations'][0]['body'].update(version='v2')),
            ('extra-year',lambda m:m['http_observations'][0]['body']['items'].append(dict(year=2025))),
            ('progress',lambda m:m['http_observations'][14]['body']['progress'].update(percent=True)),
            ('progress-total',lambda m:m['http_observations'][14]['body']['progress'].update(total=3)),
            ('config-duplicate',lambda m:m['http_observations'][3]['body']['items'].__setitem__(1,copy.deepcopy(m['http_observations'][3]['body']['items'][0]))),
            ('config-extra',lambda m:m['http_observations'][3]['body']['items'].pop()),
            ('descriptor-duplicate',lambda m:m['http_observations'][14]['body']['items'].__setitem__(1,copy.deepcopy(m['http_observations'][14]['body']['items'][0]))),
            ('descriptor-extra',lambda m:m['http_observations'][14]['body']['items'].append(copy.deepcopy(m['http_observations'][14]['body']['items'][0])))]
        for i in (1,2):
            for field in ('id','name'):
                mutations.append((str(i)+field,lambda m,i=i,f=field:m['http_observations'][i]['body']['items'][0].update({f:'wrong'})))
        for i in (0,1,2):
            mutations.append((str(i)+'empty-items',lambda m,i=i:m['http_observations'][i]['body'].update(items=[])))
        for field,value in [('complete',1),('hydrating',0),('version','v2')]:
            mutations.append(('listing-'+field,lambda m,f=field,v=value:m['http_observations'][14]['body'].update({f:v})))
        for i in (1,2,3):
            for field,value in [('complete',0),('hydrating',0),('version','v2')]:
                mutations.append((str(i)+field,lambda m,i=i,f=field,v=value:m['http_observations'][i]['body'].update({f:v})))
        for i in (*range(4,14),15,16,17):
            for field,value in [('code','OTHER'),('message','wrong'),('retryable',1),('request_id',''),
                                ('request_id','A0000000-0000-0000-0000-000000000000'),('details',None)]:
                mutations.append((str(i)+field+str(value),lambda m,i=i,f=field,v=value:m['http_observations'][i]['body']['error'].update({f:v})))
        mutations += [('duplicate-request',lambda m:m['http_observations'][5]['body']['error'].update(request_id=m['http_observations'][4]['body']['error']['request_id'])),
            ('retry-type',lambda m:m['http_observations'][15]['body']['error']['details'].update(retry_after_seconds=True)),
            ('retry-value',lambda m:m['http_observations'][15]['body']['error']['details'].update(retry_after_seconds=3))]
        self.check_mutations(mutations,'paid_http_body')

    def test_config_descriptor_and_pg_bindings(self):
        mutations=[]
        for field,value in [('id',self.vehicle),('vehicle_id',self.configuration),('trim','Paid adjacent'),('region','CA'),('year',2025),('complete',1),('make','Other'),('model','Other')]:
            mutations.append(('config-'+field,lambda m,f=field,v=value:m['http_observations'][3]['body']['items'][0].update({f:v})))
        for field,value in [('id',self.article_ids[1]),('canonical_article_id',self.article_ids[1]),('vehicle_id',self.vehicle),
            ('title','Other'),('availability','ready'),('complete',True),('images',[{}]),('source_revision_id','x'),
            ('content_origin','source'),('processing',{}),('canonical_revision_id','x'),('review_status','APPROVED'),('content_status','ready'),('view_revision',1)]:
            mutations.append(('descriptor-'+field,lambda m,f=field,v=value:m['http_observations'][14]['body']['items'][0].update({f:v})))
        mutations += [('source-article',lambda m:m['http_observations'][15]['body']['error']['details'].update(article_id=self.article_ids[1])),
            ('selected-physical',lambda m:m['snapshots']['selectors']['article'].update(vehicle_id=self.configuration)),
            ('pg-title',lambda m:m['snapshots']['selectors']['immutable_rows']['canonical_articles'][0].update(title='Other')),
            ('pg-current',lambda m:m['snapshots']['selectors']['immutable_rows']['canonical_articles'][0].update(current_source_revision_id=self.article_ids[0])),
            ('pg-scope',lambda m:m['snapshots']['selectors']['immutable_rows']['canonical_articles'][1].update(vehicle_configuration_id=self.vehicle)),
            ('pg-provider',lambda m:m['snapshots']['selectors']['immutable_rows']['canonical_articles'][1].update(provider_slug='bankone'))]
        self.check_mutations(mutations,'paid_http_binding')
        raw=dict(self.baseline)
        self.alter(raw,lambda m:(m['http_observations'][3]['body']['items'].reverse(),m['http_observations'][14]['body']['items'].reverse()))
        self.assert_unavailable(self.inspect(raw),raw)

    def test_parent_identity_copy_and_hash_guards(self):
        for key,value in [('candidate_sha','2'*40),('trusted_base_sha','invalid'),('profile_sha256','invalid'),('profile_version','other')]:
            with self.subTest(key=key),self.assertRaises(assembler.ContractError):self.inspect(self.baseline,**{key:value})
        prefix='paid-access/bankone/'+self.root+'/'
        for name in ('hash','copy','missing','candidate','bank','base','profile','schema'):
            raw=dict(self.baseline)
            if name=='hash':raw[prefix+'measured-runtime.json']+=b' '
            elif name=='missing':del raw[prefix+'go-measurement.json']
            elif name=='copy':
                m=json.loads(raw[prefix+'go-measurement.json']);m['http_observations'][0]['status']=201
                raw[prefix+'go-measurement.json']=json.dumps(m).encode();PaidPGSnapshotTests().reseal(raw)
            else:
                key,value={'candidate':('candidate_sha','2'*40),'bank':('provider','banktwo'),
                    'base':('trusted_base_sha','2'*40),'profile':('profile_sha256','2'*64),'schema':('schema_version',2)}[name]
                self.alter(raw,lambda m:m.update({key:value}) if name in ('candidate','bank','schema') else m['snapshots']['selectors']['article'].update({key:value}))
            with self.subTest(name=name),self.assertRaises(assembler.ContractError):self.inspect(raw)

    def test_confined_store_major_semantic_groups_and_recheck(self):
        mutations=[(None,None),
            (lambda m:m['http_observations'].pop(),'paid_http_inventory'),
            (lambda m:m['http_observations'][0].update(body_size=0),'paid_http_row'),
            (lambda m:m['http_observations'][0].update(path='/wrong'),'paid_http_route'),
            (lambda m:m['http_observations'][0].update(reader_after=1),'paid_http_counter'),
            (lambda m:m['http_observations'][0]['headers'].update(Secret='x'),'paid_http_headers'),
            (lambda m:m['http_observations'][0]['body'].update(version='v2'),'paid_http_body'),
            (lambda m:m['http_observations'][14]['body']['items'][0].update(title='Other'),'paid_http_binding')]
        for mutation,code in mutations:
            raw=dict(self.baseline)
            if mutation:self.alter(raw,mutation)
            with tempfile.TemporaryDirectory() as directory,self.real_store(raw,directory) as store:
                if mutation:
                    with self.assertRaisesRegex(assembler.ContractError,'^'+code+'$'):
                        assembler.inspect_paid_http_receipts(store,**self.invocation())
                else:self.assert_unavailable(assembler.inspect_paid_http_receipts(store,**self.invocation()),raw)
        ref='paid-access/bankone/'+self.root+'/measured-runtime.json'
        for mutation in ('missing','symlink','post-read'):
            with tempfile.TemporaryDirectory() as directory,self.real_store(self.baseline,directory) as store:
                path=Path(directory)/ref
                if mutation=='missing':path.unlink()
                elif mutation=='symlink':path.unlink();path.symlink_to(Path(directory)/'host-before.json')
                else:
                    # Common and selector read this copy first. Change an already
                    # consumed file on the third read, in the new HTTP layer,
                    # after all inherited rechecks have completed.
                    original=store.read;reads=0
                    measurement_ref='paid-access/bankone/'+self.root+'/go-measurement.json'
                    def changed(artifact_id):
                        nonlocal reads
                        value=original(artifact_id)
                        if artifact_id==store.by_ref[measurement_ref]['artifact_id']:
                            reads+=1
                            if reads==3:path.write_bytes(path.read_bytes()+b' ')
                        return value
                    store.read=changed
                with self.subTest(mutation=mutation),self.assertRaises(assembler.ContractError):
                    assembler.inspect_paid_http_receipts(store,**self.invocation())


class DTOReceiptTests(unittest.TestCase):
    """Synthetic DTO consistency only; constants copied from the reviewed plan."""
    inputs = {'apps/api-go/workshop_browser_fixture_test.go': '7cf50daeb190686dc55c33c90056b87a62eece96640759b180f1282a0a1a6dd2',
 'scripts/dev/fixtures/workshop_customer/firebase_transport.js': '96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63',
 'scripts/dev/fixtures/workshop_customer/hostile_source.json': '076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1',
 'scripts/dev/fixtures/workshop_customer/scenarios.json': '83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9',
 'scripts/dev/fixtures/workshop_customer/stripe_checkout.html': '26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083',
 'scripts/dev/workshop_browser_smoke.py': '45299888e56a78679148f575ac071856f0a3c1941faf059cd586ff2980069de8'}
    assets = {'app.mjs': {'bytes': 37127,
             'sha256': 'bc1b0d5e1c1181c1ff2a833ab8dc8c9ab88bf84e38b00b018ffa5fc9206e5ab5'},
 'article-read.mjs': {'bytes': 2507,
                      'sha256': 'fefa9ba05d05e8a48f8135d07a53f92d7ef32bf848db075005981848cc8d8f08'},
 'auth.mjs': {'bytes': 7908,
              'sha256': 'ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2'},
 'catalog.mjs': {'bytes': 11688,
                 'sha256': 'cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52'},
 'commerce.mjs': {'bytes': 7321,
                  'sha256': 'be291187bdbd3ef7faeb9ace6c244eed8a0b28b0edc91f1e01881c7d32c9ae26'},
 'firebase-web.mjs': {'bytes': 112641,
                      'sha256': 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1'},
 'firebase-web.mjs.LEGAL.txt': {'bytes': 35536,
                                'sha256': '70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319'},
 'firebase-web.provenance.json': {'bytes': 2237,
                                  'sha256': '0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a'},
 'index.html': {'bytes': 10868,
                'sha256': '8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68'},
 'progress.mjs': {'bytes': 1076,
                  'sha256': 'dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48'},
 'styles.css': {'bytes': 20773,
                'sha256': 'c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c'}}
    scenarios = ('bankone-cascade',
 'banktwo-cascade',
 'dual-bank-coverage',
 'one-bank-unavailable',
 'pending-no-content',
 'source-to-canonical',
 'source-rewrite-failure',
 'review-required',
 'warm-reload',
 'selection-change-in-flight',
 'source-review-change-in-flight',
 'cancel-and-retry',
 'history-restore',
 'document-only',
 'missing-media',
 'withdrawal',
 'keyboard-print-mobile',
 'source-media-isolation',
 'auth-cookie-reload',
 'google-popup-exchange',
 'google-popup-blocked',
 'google-popup-cancelled',
 'google-stale-reauthentication',
 'firebase-memory-persistence',
 'signin-unavailable-local',
 'signin-malformed-config',
 'session-expired',
 'session-blocked',
 'auth-dependency-unavailable',
 'quote-exact-scope',
 'terms-config-unavailable',
 'checkout-double-click-retry',
 'checkout-processing-return',
 'checkout-untrusted-return',
 'checkout-expired',
 'already-owned-no-pay',
 'library-pagination-and-states',
 'paid-prepare-before-poll',
 'media-renew-coalesced',
 'logout-and-bfcache-clear')
    routes = [('GET',
  '/__/auth/handler',
  ['apiKey', 'appName', 'authType', 'eventId', 'providerId', 'redirectUrl', 'scopes', 'v']),
 ('GET', '/auth/config', []),
 ('GET', '/auth/session', []),
 ('GET', '/c/pay/fixture', []),
 ('GET', '/js/api.js', ['onload']),
 ('GET', '/v1/catalog/images/v2.expired-one', []),
 ('GET', '/v1/catalog/images/v2.expired-two', []),
 ('GET', '/v1/catalog/images/v2.renewed-one', []),
 ('GET', '/v1/catalog/images/v2.renewed-two', []),
 ('GET', '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles', []),
 ('GET',
  '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333',
  []),
 ('GET',
  '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/source',
  ['source_revision_id']),
 ('GET', '/v1/catalog/vehicles/22222222-2222-4222-8222-222222222222/articles', []),
 ('GET', '/v1/catalog/years', []),
 ('GET', '/v1/catalog/years/2024/makes', ['region']),
 ('GET', '/v1/catalog/years/2024/makes/fixture-make/models', ['region']),
 ('GET',
  '/v1/catalog/years/2024/makes/fixture-make/models/fixture-model/configurations',
  ['region']),
 ('GET', '/v1/projects', ['key']),
 ('GET', '/v1/workshop/library', ['cursor', 'limit']),
 ('GET', '/v1/workshop/orders/55555555-5555-4555-8555-555555555555', []),
 ('GET', '/v1/workshop/quote', ['configuration_id', 'region']),
 ('GET', '/workshop/', ['configuration', 'make', 'model', 'order', 'region', 'year']),
 ('GET', '/workshop/app.mjs', []),
 ('GET', '/workshop/article-read.mjs', []),
 ('GET', '/workshop/auth.mjs', []),
 ('GET', '/workshop/catalog.mjs', []),
 ('GET', '/workshop/commerce.mjs', []),
 ('GET', '/workshop/firebase-web.mjs', []),
 ('GET', '/workshop/fonts/InstrumentSans.ttf', []),
 ('GET', '/workshop/progress.mjs', []),
 ('GET', '/workshop/purchase-config.json', []),
 ('GET', '/workshop/styles.css', []),
 ('POST', '/auth/firebase/session', []),
 ('POST', '/auth/logout', []),
 ('POST', '/v1/accounts:lookup', ['key']),
 ('POST', '/v1/accounts:signInWithIdp', ['key']),
 ('POST',
  '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/prepare',
  []),
 ('POST', '/v1/token', ['key']),
 ('POST', '/v1/workshop/checkout-sessions', [])]
    missing = (
        'dto_scenario_assertion_provenance', 'dto_request_origin_and_response_provenance',
        'dto_source_execution_binding', 'dto_browser_installation_and_process_provenance',
        'dto_tls_capture_provenance', 'dto_sdk_build_provenance',
        'dto_supervisor_commands_and_cleanup', 'dto_host_and_input_provenance',
        'dto_authenticated_ci_archive_provenance', 'dto_supervisor_and_reviewer_authority')

    def model(self):
        sdk = 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1'
        evidence = dict(version='v1', mode='dto-fixture', candidate_sha=BASE,
            sdk_sha256=sdk, playwright_version='1.64.1',
            browser_versions={'chromium':'156.0.8078.4', 'firefox':'157.0', 'webkit':'27.2'},
            engine_revisions={'chromium':'1248', 'chromium-headless-shell':'1248',
                'firefox':'1555', 'webkit':'2370', 'ffmpeg':'1013', 'winldd':'1007', 'android':'1001'},
            input_sha256=copy.deepcopy(self.inputs),
            provenance=dict(certificate_sha256='a'*64, assets=copy.deepcopy(self.assets)),
            results=[dict(browser=engine, scenario=scenario, status='passed', elapsed_seconds=1.25,
                requests=[dict(method='GET', path='/workshop/', query={}),
                          dict(method='GET', path='/workshop/firebase-web.mjs', query={})],
                sdk_requests=1) for engine in ('chromium','firefox','webkit') for scenario in self.scenarios])
        ready = dict(version='v1',kind='dto-fixture',origin='https://127.0.0.1:12345',
                     certificate_sha256='a'*64,sdk_sha256=sdk)
        return dict(evidence=evidence, ready=ready, log=b'opaque synthetic fixture log')

    def archive(self, model=None, *, evidence_raw=None, ready_raw=None):
        model = self.model() if model is None else model
        return RawPrimitiveTests().archive([
            ('browser/evidence.json', evidence_raw if evidence_raw is not None else json.dumps(model['evidence']).encode(), stat.S_IFREG | 0o600),
            ('go-fixture.log',model['log'],stat.S_IFREG | 0o600),
            ('ready.json',ready_raw if ready_raw is not None else json.dumps(model['ready']).encode(), stat.S_IFREG | 0o600)])

    def invocation(self):
        return dict(candidate_sha=BASE,trusted_base_sha=TRUSTED_BASE,profile_sha256='b'*64)

    def inspect(self, model=None, *, raw=None, kind='raw', ref='dto-artifact.zip', **kwargs):
        raw = self.archive(model) if raw is None else raw
        declaration = dict(artifact_id='dto', kind=kind, ref=ref,
                          sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),visibility='private')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            with assembler.ArtifactStore(directory,[declaration]) as store:
                return assembler.inspect_dto_receipts(store,**(self.invocation() | kwargs))

    def reject(self, model, code=None):
        with self.assertRaises(assembler.ContractError) as caught:self.inspect(model)
        if code is not None:self.assertEqual(str(caught.exception),code)
        self.assertNotIn('SECRET_SENTINEL',str(caught.exception))

    def test_complete_tuple_inventory_is_observed_but_never_verified(self):
        result=self.inspect()
        self.assertEqual(set(result), {'status','complete','profile_version','candidate_sha',
            'trusted_base_sha','observed_case_ids','verified_case_ids','observed_request_count',
            'observed_asset_count','source_expectations_sha','missing_validation_families',
            'fixture_verified','product_candidate_verified','staging_verified',
            'deployment_authorized','cutover_verified'})
        self.assertEqual(result['status'],'unavailable');self.assertIs(result['complete'],False)
        self.assertEqual(result['profile_version'],'dto-fixture-v1')
        self.assertEqual(result['candidate_sha'],BASE);self.assertEqual(result['trusted_base_sha'],TRUSTED_BASE)
        self.assertEqual(result['observed_case_ids'],[dict(browser=e,scenario=s)
            for e in ('chromium','firefox','webkit') for s in self.scenarios])
        self.assertEqual(result['observed_request_count'],240);self.assertEqual(result['observed_asset_count'],11)
        self.assertEqual(result['source_expectations_sha'],'99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d')
        self.assertEqual(result['verified_case_ids'],[])
        self.assertEqual(result['missing_validation_families'],list(self.missing))
        for flag in ('fixture_verified','product_candidate_verified','staging_verified',
                     'deployment_authorized','cutover_verified'):self.assertIs(result[flag],False)

    def test_order_retries_optional_queries_and_opaque_copies_do_not_create_authority(self):
        model=self.model();model['evidence']['results'].reverse()
        row=model['evidence']['results'][0]
        row['requests']=[dict(method=m,path=p,query={k:['SECRET_SENTINEL'] for k in keys})
                         for m,p,keys in self.routes]
        row['sdk_requests']=1
        model['evidence']['results'][1].update(requests=[],sdk_requests=0)
        model['evidence']['results'][2]['requests'].append(dict(method='GET',path='/workshop/',query={}))
        model['evidence']['provenance']['certificate_sha256']='c'*64
        model['ready'].update(certificate_sha256='c'*64,origin='https://127.0.0.1:65535')
        model['log']=b'not an authenticated Go outcome\x00'
        result=self.inspect(model)
        self.assertEqual(result['observed_request_count'],len(self.routes)+237)
        self.assertEqual(result['missing_validation_families'],list(self.missing))
        self.assertNotIn('SECRET_SENTINEL',json.dumps(result))
        for port in (1,80,443):
            model['ready']['origin']=f'https://127.0.0.1:{port}';self.inspect(model)

    def test_closed_objects_reject_each_missing_and_extra_key(self):
        paths=[('evidence',),('ready',),('evidence','provenance'),
            ('evidence','provenance','assets','index.html'),('evidence','results',0),
            ('evidence','results',0,'requests',0)]
        for path in paths:
            original=self.model()
            target=original
            for key in path:target=target[key]
            for key in tuple(target)+('unknown',):
                model=copy.deepcopy(original);value=model
                for part in path:value=value[part]
                if key=='unknown':value[key]=True
                else:value.pop(key)
                with self.subTest(path=path,key=key):self.reject(model,'invalid_object_keys')

    def test_missing_duplicate_extra_or_substituted_tuples_fail(self):
        for kind in ('missing','extra','duplicate','scenario','engine','api','bool','rowtype'):
            model=self.model();rows=model['evidence']['results']
            if kind=='missing':rows.pop()
            elif kind=='extra':rows.append(copy.deepcopy(rows[0]))
            elif kind=='duplicate':rows[-1]=copy.deepcopy(rows[0])
            elif kind=='scenario':rows[0]['scenario']='unreviewed'
            elif kind=='engine':rows[0]['browser']='other'
            elif kind=='api':rows[0]['scenario']='google-exchange-checkout-library'
            elif kind=='bool':rows[0]['browser']=True
            else:rows[0]=[]
            with self.subTest(kind=kind):self.reject(model)
        for status in ('failed','unavailable','skipped','pending',True,None):
            model=self.model();model['evidence']['results'][0]['status']=status;self.reject(model)
        model=self.model();model['evidence']['results'][0]={'browser':'chromium','scenario':self.scenarios[0],
            'status':'unavailable','error':'launch failed'};self.reject(model)

    def test_source_input_asset_and_sdk_bindings_cannot_self_authenticate(self):
        for group in ('inputs','assets','browsers','revisions'):
            model=self.model();ev=model['evidence']
            base={'inputs':ev['input_sha256'],'assets':ev['provenance']['assets'],
                  'browsers':ev['browser_versions'],'revisions':ev['engine_revisions']}[group]
            for action in ('missing','extra','changed'):
                changed=copy.deepcopy(model);value={'inputs':changed['evidence']['input_sha256'],
                    'assets':changed['evidence']['provenance']['assets'],
                    'browsers':changed['evidence']['browser_versions'],
                    'revisions':changed['evidence']['engine_revisions']}[group]
                if action=='missing':value.pop(next(iter(value)))
                elif action=='extra':value['unreviewed']='0'*64
                else:value[next(iter(value))]='0'*64
                with self.subTest(group=group,action=action):self.reject(changed)
        for name in self.inputs:
            model=self.model();model['evidence']['input_sha256'][name]='0'*64
            self.reject(model,'dto_source_inputs')
        for name in self.assets:
            for field in ('sha256','bytes'):
                model=self.model();asset=model['evidence']['provenance']['assets'][name]
                asset[field]='0'*64 if field=='sha256' else asset[field]+1
                self.reject(model,'dto_source_assets')
        for bad in (True,False,'10868',None,-1):
            model=self.model();model['evidence']['provenance']['assets']['index.html']['bytes']=bad;self.reject(model)
        for container in ('evidence','ready'):
            model=self.model();model[container]['sdk_sha256']='0'*64;self.reject(model)
        model=self.model();model['evidence']['sdk_sha256']='0'*64;model['ready']['sdk_sha256']='0'*64
        model['evidence']['provenance']['assets']['firebase-web.mjs']['sha256']='0'*64;self.reject(model)

    def test_versions_readiness_identity_and_declared_artifact_are_closed(self):
        for key,bad in (('version','v2'),('mode','api-fixture'),('candidate_sha','0'*40),
                        ('playwright_version','1.64.0')):
            model=self.model();model['evidence'][key]=bad;self.reject(model)
        for key,bad in (('version','v2'),('kind','api-fixture'),('certificate_sha256','d'*64)):
            model=self.model();model['ready'][key]=bad;self.reject(model)
        for bad in ('https://localhost:80','http://127.0.0.1:80','https://127.0.0.1',
            'https://user@127.0.0.1:80','https://%31%32%37.0.0.1:80','https://127.0.0.1:0',
            'https://127.0.0.1:65536','https://127.0.0.1:080','https://127.0.0.1:+80',
            'https://127.0.0.1:80/','https://127.0.0.1:80?q=x','https://127.0.0.1:80#x',True,None):
            model=self.model();model['ready']['origin']=bad;self.reject(model)
        for bad in ('G'*64,'a'*63,True,None):
            model=self.model();model['evidence']['provenance']['certificate_sha256']=bad;self.reject(model)
        for key,bad in (('candidate_sha','x'),('trusted_base_sha','x'),('profile_sha256','x'),
                        ('profile_version','dto-fixture-v2')):
            with self.subTest(key=key),self.assertRaises(assembler.ContractError):self.inspect(**{key:bad})
        for kind,ref in (('manifest','dto-artifact.zip'),('raw','other.zip')):
            with self.assertRaises(assembler.ContractError):self.inspect(kind=kind,ref=ref)
        for key in ('candidate_sha','trusted_base_sha','profile_sha256'):
            model=self.model();model['evidence']['results'][0]['requests'][0]['query'][key]=['SECRET_SENTINEL']
            self.reject(model)

    def test_exact_decimal_duration_boundaries_and_nonfinite_values(self):
        for token in ('0','120','0.00000000000000000001','119.99999999999999999999'):
            model=self.model();raw=json.dumps(model['evidence']).replace('"elapsed_seconds": 1.25',
                '"elapsed_seconds": '+token,1).encode()
            self.inspect(raw=self.archive(model,evidence_raw=raw))
        for token in ('-1e-999','-0.00000000000000000001','120.00000000000000000001',
                      'NaN','Infinity','1e999','true','"1"','null'):
            model=self.model();raw=json.dumps(model['evidence']).replace('"elapsed_seconds": 1.25',
                '"elapsed_seconds": '+token,1).encode()
            with self.subTest(token=token),self.assertRaises(assembler.ContractError):
                self.inspect(raw=self.archive(model,evidence_raw=raw))

    def test_request_and_query_bounds_paths_primitives_and_sdk_derivation(self):
        for bad in (True,False,'1',None,-1,0,257):
            model=self.model();model['evidence']['results'][0]['sdk_requests']=bad;self.reject(model)
        for key,bad in (('method',True),('method','get'),('method','DELETE'),('path',True),
            ('path','https://cars.example/workshop/'),('path','/workshop/?x=1'),
            ('path','/workshop/#x'),('path','/%77orkshop/'),('path','/workshop/../workshop/'),
            ('query',[]),('query',{'unknown':['x']})):
            model=self.model();model['evidence']['results'][0]['requests'][0][key]=bad;self.reject(model)
        for bad in ([],['x']*9,'x',[True],[None],['x'*513],['é'*257],['a\nb'],['a\rb'],['a\x00b']):
            model=self.model();model['evidence']['results'][0]['requests'][0]=dict(
                method='GET',path='/v1/workshop/library',query={'limit':bad});self.reject(model)
        for bad in ({},True,None):
            model=self.model();model['evidence']['results'][0]['requests']=bad;self.reject(model)
        model=self.model();model['evidence']['results'][0].update(requests=[dict(method='GET',path='/workshop/',query={})]*257,sdk_requests=0)
        self.reject(model,'dto_request_limit')
        model=self.model()
        for index,row in enumerate(model['evidence']['results']):
            row.update(requests=[dict(method='GET',path='/workshop/',query={})]*(69 if index<33 else 68),sdk_requests=0)
        self.reject(model,'dto_request_limit')  # 33*69+87*68 = 8193, all rows below256.
        model['evidence']['results'][0]['requests'].pop()
        self.assertEqual(self.inspect(model)['observed_request_count'],8192)
        model=self.model();model['evidence']['results'][0].update(
            requests=[dict(method='GET',path='/workshop/',query={})]*256,sdk_requests=0)
        self.assertEqual(self.inspect(model)['observed_request_count'],494)
        model=self.model();row=model['evidence']['results'][0]
        row.update(requests=[dict(method='GET',path='/v1/workshop/library',query={'limit':['é'*256]*8})],sdk_requests=0)
        self.inspect(model)

    def test_strict_member_json_and_archive_corruption_are_not_bypassed(self):
        for raw in (b'{}',b'[]',b'\xff',b'{"candidate_sha":"x","candidate_sha":"y"}',
            b'{"x":"\\ud800"}',b'{"x":NaN}',b' '* (4*1024*1024+1),
            b'{"x":'+b'['*1100+b'0'+b']'*1100+b'}'):
            for member in ('evidence_raw','ready_raw'):
                with self.subTest(member=member),self.assertRaises(assembler.ContractError):
                    self.inspect(raw=self.archive(**{member:raw}))
        for raw in (b'not a zip',self.archive()[:-1],self.archive()+b'garbage',
            RawPrimitiveTests().archive([('browser/evidence.json',b'{}',stat.S_IFLNK | 0o777),
                ('go-fixture.log',b'x',stat.S_IFREG),('ready.json',b'{}',stat.S_IFREG)])):
            with self.assertRaises(assembler.ContractError):self.inspect(raw=raw)
        model=self.model();raw=json.dumps(model['evidence']).replace('"query": {}','"query": {"x":1,"x":2}',1).encode()
        with self.assertRaisesRegex(assembler.ContractError,'^duplicate_json_key$'):
            self.inspect(raw=self.archive(model,evidence_raw=raw))

    def test_confined_store_detects_missing_symlink_hash_and_post_read_drift(self):
        raw=self.archive();declaration=dict(artifact_id='dto',kind='raw',ref='dto-artifact.zip',
            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),visibility='private')
        for mutation in ('missing','symlink','ancestor','hash','post-read','extra'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)/'root';root.mkdir();path=root/'dto-artifact.zip';path.write_bytes(raw)
                record=dict(declaration)
                if mutation=='hash':record['sha256']='0'*64
                with assembler.ArtifactStore(root,[record]) as store:
                    if mutation=='missing':path.unlink()
                    elif mutation=='symlink':path.unlink();path.symlink_to(Path(directory)/'outside')
                    elif mutation=='ancestor':
                        root.rename(Path(directory)/'moved');root.symlink_to(Path(directory)/'moved',target_is_directory=True)
                    elif mutation=='extra':(root/'extra').write_bytes(b'x')
                    elif mutation=='post-read':
                        original=store.read
                        def changed(artifact_id):
                            value=original(artifact_id);path.write_bytes(raw+b' ');return value
                        store.read=changed
                    with self.subTest(mutation=mutation),self.assertRaises(assembler.ContractError):
                        assembler.inspect_dto_receipts(store,**self.invocation())



class PaidScopeReceiptTests(unittest.TestCase):
    """Closed producer projections, built independently from the new inspector."""
    root = 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation'
    configuration = PaidHTTPReceiptTests.configuration
    vehicle = PaidHTTPReceiptTests.vehicle
    invocation = PaidSelectorWorkTests.invocation
    real_store = PaidSelectorWorkTests.real_store
    alter = classmethod(PaidHTTPReceiptTests.alter.__func__)

    @staticmethod
    def uid(n): return '00000000-0000-0000-0000-'+format(n,'012x')

    @classmethod
    def setUpClass(cls):
        PaidHTTPReceiptTests.setUpClass()
        cls.baseline = dict(PaidHTTPReceiptTests.baseline)
        for bank in ('bankone','banktwo'):
            def populate(m):
                s=m['snapshots']['isolated'];paid=s['paid_rows']
                for i,a in enumerate(paid['customer_accounts']):a['firebase_uid']='paid-owner-'+('a' if i==0 else 'b')
                orders=[];requests=[];projections=[];entitlements=[]
                # Literal producer row schemas; do not import validator contracts.
                fields={
                    'o':'amount_minor checkout_session_id checkout_url configuration_id created_at currency customer_account_id dataset_product_id dataset_request_id entitlement_id expected_price_id first_create_attempt_at last_reconciled_at livemode order_id organization_id paid_at payment_intent_id preparation_attempts preparation_index_job_ids preparation_last_error_code preparation_lease_expires_at preparation_lease_owner preparation_next_attempt_at preparation_state provider_expires_at provider_idempotency_key region revocation_reason_code revoked_at status stripe_account_id terms_version updated_at',
                    'r':'correlation_id created_at dataset_product_id dataset_request_id idempotency_key lane organization_id processing_version region source_snapshot_id status updated_at vehicle_id vehicle_key',
                    'p':'created_at dataset_product_id dataset_projection_id dataset_request_id entitlement_id',
                    'e':'commerce_order_id configuration_id customer_account_id dataset_request_id entitlement_id granted_at organization_id payment_event_id provider_event_id region revoke_reason revoked_at status'}
                for i,a in enumerate(paid['customer_accounts']):
                    oid,rid,eid,pid=[cls.uid(100+i*10+j) for j in range(4)]
                    config=cls.uid(48+i); org=a['personal_organization_id'];account=a['customer_account_id']
                    o={k:'fixture' for k in fields['o'].split()};o.update(order_id=oid,configuration_id=config,
                        customer_account_id=account,organization_id=org,dataset_request_id=rid,entitlement_id=eid,
                        dataset_product_id=cls.uid(200),amount_minor=2000,currency='USD',livemode=False,status='paid',region='US',
                        stripe_account_id='acct_fixture',expected_price_id='price_fixture',preparation_attempts=0,preparation_index_job_ids=[])
                    r={k:'fixture' for k in fields['r'].split()};r.update(dataset_request_id=rid,correlation_id=oid,
                        organization_id=org,dataset_product_id=cls.uid(200),vehicle_key=config,region='US')
                    p={k:'fixture' for k in fields['p'].split()};p.update(dataset_projection_id=pid,dataset_request_id=rid,
                        entitlement_id=eid,dataset_product_id=cls.uid(200))
                    e={k:'fixture' for k in fields['e'].split()};e.update(entitlement_id=eid,dataset_request_id=rid,
                        organization_id=org,status='active',revoked_at=None,granted_at='2026-11-03T00:00:00Z',
                        customer_account_id=None if i==0 else account,configuration_id=None if i==0 else config,
                        commerce_order_id=None if i==0 else oid,region=None if i==0 else 'US',revoke_reason='fixture' if i==0 else None)
                    orders.append(o);requests.append(r);projections.append(p);entitlements.append(e)
                paid.update(workshop_orders=orders,dataset_requests=requests,dataset_projections=projections,entitlements=entitlements)
                canonical=[]
                for i,config in enumerate((cls.uid(48),cls.uid(49),cls.uid(50),None)):
                    for j,provider in enumerate(('bankone','banktwo')):
                        canonical.append(dict(canonical_article_id=cls.uid(300+i*2+j),provider_slug=provider,
                            vehicle_configuration_id=config,vehicle_id=cls.vehicle,title='Pump '+str(i*2+j),
                            current_source_revision_id=None,current_canonical_revision_id=None,current_job_id=None))
                s['article']=copy.deepcopy(canonical[0 if bank=='bankone' else 1])
                s['article']['producer_extra']='retained view field'
                s['immutable_rows']['canonical_articles']=canonical
                for table in ('customer_accounts','auth_sessions','workshop_orders'):s['immutable_rows'][table]=copy.deepcopy(paid[table])
                s.update(reader_calls=0,identity_checks=11,grant_calls=9)
                m['final_snapshot']=copy.deepcopy(s)
                del m['final_snapshot']['reader_calls'];del m['final_snapshot']['identity_checks']
                m.update(reader_calls=0,identity_checks=11,http_observations=cls.observations(bank))
            cls.alter(cls.baseline,populate,bank=bank)

    @classmethod
    def observations(cls,bank):
        c=cls.configuration;l='/v1/catalog/vehicles/'+c+'/articles';j=0 if bank=='bankone' else 1
        paths=[l,l,'/v1/catalog/vehicles/'+cls.vehicle+'/articles','/v1/catalog/vehicles/'+cls.uid(49)+'/articles',
            '/v1/catalog/vehicles/'+cls.uid(50)+'/articles',l+'?region=CA',l+'/'+cls.uid(302+j),l+'/'+cls.uid(306+j),l+'/legacy',l,l]
        items=[dict(availability='unavailable',canonical_article_id=cls.uid(300+k),canonical_revision_id=None,
            complete=False,content_origin=None,content_status='list_only',id=cls.uid(300+k),images=[],processing=None,
            review_status='UNREVIEWED',source_revision_id=None,title='Pump '+str(k),vehicle_id=c,view_revision=None) for k in range(2)]
        bodies=[dict(complete=True,hydrating=False,items=items,progress=dict(complete=True,percent=100,phase='indexing',
            processed=2,retryable=False,status='completed',total=2),version='v1')]
        for i in range(1,11):
            code,message=('ENTITLEMENT_REQUIRED','Purchase access to this vehicle configuration.') if i in (1,3,4,10) else (
                ('ENTITLEMENT_REVOKED','Access to this vehicle configuration was revoked.') if i==9 else
                ('CATALOG_NOT_FOUND','Catalog resource was not found.'))
            bodies.append(dict(error=dict(code=code,details={},message=message,request_id=cls.uid(400+i),retryable=False)))
        return [dict(method='GET',path=path,owner_index=1 if i==1 else 0,status=200 if i==0 else 403 if i in (1,3,4,9,10) else 404,
            headers={'Content-Type':'application/json','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'},
            body=bodies[i],body_sha256='a'*64,body_size=1,body_truncated=False,reader_before=0,reader_after=0,
            identity_before=i,identity_after=i+1) for i,path in enumerate(paths)]

    def inspect(self,raw,**overrides):
        class Store:
            by_ref={ref:dict(artifact_id=ref) for ref in raw}
            def read(self,artifact_id):return raw[artifact_id]
            def read_raw_json(self,artifact_id,**_):return assembler.strict_raw_json(raw[artifact_id])
            def recheck(self):pass
        self.assertTrue(callable(getattr(assembler,'inspect_paid_scope_receipts',None)), 'scope inspector is missing')
        return assembler.inspect_paid_scope_receipts(Store(),**self.invocation(**overrides))

    def assert_unavailable(self,result,raw):
        previous=PaidHTTPReceiptTests().inspect(raw)
        self.assertEqual(set(result)-set(previous),{'observed_scope_case_ids','observed_scope_http_observation_count','observed_scope_snapshot_count'})
        for key,value in previous.items():self.assertEqual(result[key],value if key!='missing_validation_families' else value+['paid_scope_temporal_entitlement_provenance'])
        self.assertEqual(result['observed_scope_case_ids'],[self.root+'-bankone',self.root+'-banktwo'])
        self.assertEqual(result['observed_scope_http_observation_count'],22);self.assertEqual(result['observed_scope_snapshot_count'],4)
        self.assertEqual(result['status'],'unavailable');self.assertIs(result['complete'],False);self.assertEqual(result['verified_case_ids'],[])
        self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_closed_receipts_add_only_unavailable_diagnostics(self):
        self.assert_unavailable(self.inspect(self.baseline),self.baseline)


    def check_mutations(self,mutations,code=None):
        for name,mutation in mutations:
            raw=dict(self.baseline);self.alter(raw,mutation)
            with self.subTest(mutation=name):
                if code:
                    with self.assertRaisesRegex(assembler.ContractError,'^'+code+'$'):self.inspect(raw)
                else:
                    with self.assertRaises(assembler.ContractError):self.inspect(raw)

    @staticmethod
    def terminal(m,mutation):
        for s in (m['snapshots']['isolated'],m['final_snapshot']):
            mutation(s)
            for table in ('customer_accounts','auth_sessions','workshop_orders'):
                s['immutable_rows'][table]=copy.deepcopy(s['paid_rows'][table])

    def test_every_route_owner_status_method_and_counter(self):
        mutations=[];counters=[]
        for i in range(11):
            for field,value in [('method','POST'),('owner_index',2),('status',201)]:
                mutations.append((str(i)+field,lambda m,i=i,f=field,v=value:m['http_observations'][i].update({f:v})))
            for field in ('reader_before','reader_after','identity_before','identity_after'):
                counters.append((str(i)+field,lambda m,i=i,f=field:m['http_observations'][i].update({f:99})))
        for i,row in enumerate(self.observations('bankone')):
            for path in (row['path']+'/',row['path']+'?extra=1',row['path']+'#x','https://example.invalid'+row['path'],
                row['path'].replace(self.configuration,self.vehicle)):
                if path!=row['path']:mutations.append((str(i)+path,lambda m,i=i,p=path:m['http_observations'][i].update(path=p)))
        for path in ('?region=%43A','?region=CA&x=1','?region=ca'):
            mutations.append((path,lambda m,p=path:m['http_observations'][5].update(path='/v1/catalog/vehicles/'+self.configuration+'/articles'+p)))
        mutations += [('reorder',lambda m:m['http_observations'].reverse()),('duplicate',lambda m:m['http_observations'].__setitem__(2,copy.deepcopy(m['http_observations'][1])))]
        self.check_mutations(mutations,'paid_scope_route');self.check_mutations(counters,'paid_scope_counter')
        self.check_mutations([('total',lambda m:m.update(identity_checks=12)),('reader',lambda m:m.update(reader_calls=1)),
            ('phase',lambda m:m['snapshots']['isolated'].update(identity_checks=12)),('held',lambda m:m.update(held_model_receipt={}))],'paid_scope_counter')

    def test_inventory_closed_row_and_strict_primitive_types(self):
        self.check_mutations([('missing',lambda m:m['http_observations'].pop()),('extra',lambda m:m['http_observations'].append(copy.deepcopy(m['http_observations'][0])))],'paid_scope_inventory')
        mutations=[]
        for key in self.observations('bankone')[0]:mutations.append((key,lambda m,k=key:m['http_observations'][0].pop(k)))
        mutations.append(('extra',lambda m:m['http_observations'][0].update(secret='SCOPE_SECRET_SENTINEL')))
        for key in ('owner_index','status','body_size','reader_before','reader_after','identity_before','identity_after'):
            for v in (True,'1',None,0.5):mutations.append((key+str(v),lambda m,k=key,v=v:m['http_observations'][0].update({k:v})))
        for key,values in [('body_size',(0,262145)),('body_sha256',('A'*64,'x'*64,None)),('body_truncated',(True,0,None)),('method',(None,1)),('path',(None,1))]:
            for value in values:mutations.append((key+str(value),lambda m,k=key,v=value:m['http_observations'][0].update({k:v})))
        self.check_mutations(mutations,'paid_scope_row')
        for size in (1,262144):
            raw=dict(self.baseline);self.alter(raw,lambda m:[r.update(body_size=size,body_sha256='f'*64) for r in m['http_observations']])
            self.assert_unavailable(self.inspect(raw),raw)

    def test_headers_and_every_closed_nested_schema(self):
        headers=[];bodies=[]
        def at(m,index,path):
            value=m['http_observations'][index]['body']
            for k in path:value=value[k]
            return value
        for i in range(11):
            for key in self.observations('bankone')[i]['headers']:
                headers.append((str(i)+key,lambda m,i=i,k=key:m['http_observations'][i]['headers'].pop(k)))
                for v in (None,1,'wrong'):headers.append((str(i)+key+str(v),lambda m,i=i,k=key,v=v:m['http_observations'][i]['headers'].update({k:v})))
            headers.append((str(i)+'extra',lambda m,i=i:m['http_observations'][i]['headers'].update(Secret='SCOPE_SECRET_SENTINEL')))
            for v in (None,[],1):bodies.append((str(i)+str(v),lambda m,i=i,v=v:m['http_observations'][i].update(body=v)))
        for index,path in [(0,()),(0,('progress',)),(0,('items',0)),(1,()),(1,('error',)),(1,('error','details'))]:
            value=self.observations('bankone')[index]['body']
            for k in path:value=value[k]
            for key in value:bodies.append((str((index,path,key)),lambda m,i=index,p=path,k=key:at(m,i,p).pop(k)))
            bodies.append((str((index,path,'extra')),lambda m,i=index,p=path:at(m,i,p).update(secret='SCOPE_SECRET_SENTINEL')))
        self.check_mutations(headers,'paid_scope_headers');self.check_mutations(bodies,'paid_scope_body')

    def test_error_progress_and_descriptor_values(self):
        bodies=[];bindings=[]
        for i in range(1,11):
            for key,value in [('code','WRONG'),('message','wrong'),('details',None),('retryable',1),('request_id','bad')]:
                bodies.append((str(i)+key,lambda m,i=i,k=key,v=value:m['http_observations'][i]['body']['error'].update({k:v})))
        bodies.append(('duplicate request',lambda m:m['http_observations'][2]['body']['error'].update(request_id=self.uid(401))))
        for key,value in [('complete',1),('hydrating',0),('version','v2')]:bodies.append((key,lambda m,k=key,v=value:m['http_observations'][0]['body'].update({k:v})))
        for key,value in [('complete',1),('percent',True),('phase','other'),('processed',3),('retryable',0),('status','other'),('total',3)]:
            bodies.append((key,lambda m,k=key,v=value:m['http_observations'][0]['body']['progress'].update({k:v})))
        for key,value in [('availability','ready'),('canonical_article_id',self.uid(302)),('canonical_revision_id',self.uid(1)),('complete',1),('content_origin','source'),('content_status','ready'),('id',self.uid(302)),('images',[{}]),('processing',{}),('review_status','APPROVED'),('source_revision_id',self.uid(1)),('title','Other'),('vehicle_id',self.vehicle),('view_revision',1)]:
            bindings.append((key,lambda m,k=key,v=value:m['http_observations'][0]['body']['items'][0].update({k:v})))
        bodies += [('missing descriptor',lambda m:m['http_observations'][0]['body']['items'].pop()),('extra descriptor',lambda m:m['http_observations'][0]['body']['items'].append({})),('duplicate descriptor',lambda m:m['http_observations'][0]['body']['items'].__setitem__(1,copy.deepcopy(m['http_observations'][0]['body']['items'][0])))]
        self.check_mutations(bodies,'paid_scope_body');self.check_mutations(bindings,'paid_scope_binding')

    def test_complete_chains_reject_repaired_cross_owner_and_dangling_joins(self):
        mutations=[]
        for table,keys in [
            ('workshop_orders',('dataset_request_id','entitlement_id','dataset_product_id','organization_id','configuration_id')),
            ('dataset_requests',('dataset_product_id','organization_id','correlation_id','vehicle_key')),
            ('dataset_projections',('dataset_request_id','entitlement_id','dataset_product_id')),
            ('entitlements',('dataset_request_id','organization_id'))]:
            for i in (0,1):
                for key in keys:
                    for v in (self.uid(999),None):
                        mutations.append((table+str(i)+key+str(v),lambda m,t=table,i=i,k=key,v=v:self.terminal(m,lambda s:s['paid_rows'][t][i].update({k:v}))))
        for table,key in [('workshop_orders','order_id'),('dataset_requests','dataset_request_id'),('dataset_projections','dataset_projection_id'),('entitlements','entitlement_id')]:
            for value in (None,'BAD',self.uid(100 if table=='workshop_orders' else 101 if table=='dataset_requests' else 103 if table=='dataset_projections' else 102)):
                mutations.append((table+str(value),lambda m,t=table,k=key,v=value:self.terminal(m,lambda s:s['paid_rows'][t][1].update({k:v}))))
            mutations += [(table+'missing',lambda m,t=table:self.terminal(m,lambda s:s['paid_rows'][t].pop())),
                (table+'duplicate',lambda m,t=table:self.terminal(m,lambda s:s['paid_rows'][t].append(copy.deepcopy(s['paid_rows'][t][0]))))]
        # Some malformed rows are intentionally rejected by inherited strict PG checks first.
        self.check_mutations(mutations)
        semantic=[]
        for table,keys in [('workshop_orders',('dataset_request_id','entitlement_id','dataset_product_id','organization_id')),
                ('dataset_requests',('dataset_product_id','organization_id','correlation_id','vehicle_key')),
                ('dataset_projections',('dataset_request_id','entitlement_id','dataset_product_id')),
                ('entitlements',('dataset_request_id','organization_id'))]:
            for i in (0,1):
                for key in keys:semantic.append((table+str(i)+key,lambda m,t=table,i=i,k=key:self.terminal(m,lambda s:s['paid_rows'][t][i].update({k:self.uid(999)}))))
        self.check_mutations(semantic,'paid_scope_binding')

    def test_terminal_owner_scopes_and_order_facts(self):
        mutations=[]
        for i in (0,1):
            for key,value in [('amount_minor',2001),('currency','EUR'),('livemode',True),('status','pending'),('region','CA')]:
                mutations.append((str(i)+key,lambda m,i=i,k=key,v=value:self.terminal(m,lambda s:s['paid_rows']['workshop_orders'][i].update({k:v}))))
            for key,value in [('firebase_uid','unknown'),('firebase_project_id','other'),('status','inactive')]:
                mutations.append((str(i)+key,lambda m,i=i,k=key,v=value:self.terminal(m,lambda s:s['paid_rows']['customer_accounts'][i].update({k:v}))))
        mutations += [('request region',lambda m:self.terminal(m,lambda s:s['paid_rows']['dataset_requests'][0].update(region='CA'))),
            ('legacy reason',lambda m:self.terminal(m,lambda s:s['paid_rows']['entitlements'][0].update(revoke_reason=None))),
            ('legacy revoked',lambda m:self.terminal(m,lambda s:s['paid_rows']['entitlements'][0].update(status='revoked'))),
            ('owner-b reason',lambda m:self.terminal(m,lambda s:s['paid_rows']['entitlements'][1].update(revoke_reason='fixture')))]
        self.check_mutations(mutations)
        def restore_legacy(s):
            o=s['paid_rows']['workshop_orders'][0];s['paid_rows']['entitlements'][0].update(customer_account_id=o['customer_account_id'],configuration_id=o['configuration_id'],region='US',commerce_order_id=o['order_id'])
        self.check_mutations([('rescoped legacy',lambda m:self.terminal(m,restore_legacy)),
            ('unscoped owner-b',lambda m:self.terminal(m,lambda s:s['paid_rows']['entitlements'][1].update(customer_account_id=None,configuration_id=None,region=None,commerce_order_id=None)))],'paid_scope_binding')

    def test_canonical_inventory_and_article_roles(self):
        mutations=[]
        for index in range(8):
            mutations.append(('missing'+str(index),lambda m,i=index:self.terminal(m,lambda s:s['immutable_rows']['canonical_articles'].pop(i))))
            mutations.append(('scope'+str(index),lambda m,i=index:self.terminal(m,lambda s:s['immutable_rows']['canonical_articles'][i].update(vehicle_configuration_id=self.uid(999)))))
        for key,value in [('vehicle_configuration_id',self.vehicle),('vehicle_id',self.configuration),('canonical_article_id',self.uid(301))]:
            mutations.append((key,lambda m,k=key,v=value:self.terminal(m,lambda s:s['article'].update({k:v}))))
        for key in ('current_source_revision_id','current_canonical_revision_id','current_job_id'):
            mutations.append((key,lambda m,k=key:self.terminal(m,lambda s:s['immutable_rows']['canonical_articles'][0].update({k:self.uid(999)}))))
        self.check_mutations(mutations)
        self.check_mutations([('other bank adjacent',lambda m:m['http_observations'][6].update(path='/v1/catalog/vehicles/'+self.configuration+'/articles/'+self.uid(303))),
            ('selected adjacent',lambda m:m['http_observations'][6].update(path='/v1/catalog/vehicles/'+self.configuration+'/articles/'+self.uid(300)))],'paid_scope_route')

    def test_no_work_even_when_all_terminal_copies_agree(self):
        mutations=[]
        def add(m,f):self.terminal(m,f)
        for group in ('source_calls','asset_calls'):
            mutations.append((group,lambda m,g=group:add(m,lambda s:s[g].update(bankone=1))))
        for field in ('model_calls','grant_calls'):
            mutations.append((field,lambda m,f=field:add(m,lambda s:s.update({f:1}))))
        mutations += [('provider',lambda m:add(m,lambda s:(s['provider_calls'].update(bankone=1),s['provider_traces'].update(bankone=['/work'])))),
            ('ensure',lambda m:add(m,lambda s:s.update(ensure=dict(entered=1,completed=1,active=0),ensure_requests=[dict(work=True)]))),
            ('selector',lambda m:add(m,lambda s:s.update(selector_ensure=dict(entered=1,completed=1,active=0),selector_ensure_requests=[dict(work=True)]))),
            ('worker',lambda m:add(m,lambda s:s['workers'].append(dict(kind='cli',alive=True,exit_code=None)))),
            ('proxy',lambda m:add(m,lambda s:s['proxy'].update(request_received=1))),
            ('captured',lambda m:add(m,lambda s:s['proxy'].update(response_captured=True))),
            ('final drift',lambda m:m['final_snapshot']['article'].update(producer_extra='changed'))]
        self.check_mutations(mutations,'paid_scope_work')
        self.check_mutations([('payment',lambda m:add(m,lambda s:s.update(payment_calls=1)))],'paid_pg_payment_work')

    def test_randomized_valid_uuid_titles_and_unordered_descriptors(self):
        raw=dict(self.baseline)
        for bank in ('bankone','banktwo'):
            self.alter(raw,lambda m:(m['http_observations'][0]['body']['items'].reverse(),self.terminal(m,lambda s:s['immutable_rows']['canonical_articles'].reverse())),bank=bank)
        # UUIDs are identities, not frozen historical constants. Replace every occurrence,
        # then repair hashes and populated replay seams through the fixture resealer.
        import uuid
        import re
        replacements={v:str(uuid.uuid4()) for data in raw.values() for v in re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',data.decode())}
        def randomize(m):
            data=json.dumps(m)
            for old,new in replacements.items():data=data.replace(old,new)
            updated=json.loads(data.replace('Pump ','Random title '))
            m.clear();m.update(updated)
        for bank in ('bankone','banktwo'):self.alter(raw,randomize,bank=bank)
        self.assert_unavailable(self.inspect(raw),raw)

    def test_parent_hash_copy_identity_and_confined_freshness_guards(self):
        prefix='paid-access/bankone/'+self.root+'/'
        for mutation in ('hash','copy','missing','identity'):
            raw=dict(self.baseline)
            if mutation=='hash':raw[prefix+'measured-runtime.json']+=b' '
            elif mutation=='missing':del raw[prefix+'go-measurement.json']
            elif mutation=='copy':
                value=json.loads(raw[prefix+'go-measurement.json']);value['identity_checks']=99
                raw[prefix+'go-measurement.json']=json.dumps(value).encode();PaidPGSnapshotTests().reseal(raw)
            else:self.alter(raw,lambda m:m['snapshots']['isolated']['article'].update(candidate_sha='2'*40))
            with self.subTest(mutation=mutation),self.assertRaises(assembler.ContractError):self.inspect(raw)
        for mutation in ('positive','missing','symlink','hash','post-read'):
            with tempfile.TemporaryDirectory() as directory,self.real_store(self.baseline,directory) as store:
                path=Path(directory)/prefix/'measured-runtime.json'
                if mutation=='missing':path.unlink()
                elif mutation=='symlink':path.unlink();path.symlink_to(Path(directory)/'host-before.json')
                elif mutation=='hash':path.write_bytes(path.read_bytes()+b' ')
                elif mutation=='post-read':
                    original=store.read;count=[0]
                    # Determine by ref without depending on ArtifactStore internals.
                    target=store.by_ref[prefix+'measured-runtime.json']['artifact_id']
                    def changed(artifact_id):
                        value=original(artifact_id)
                        if artifact_id==target:
                            count[0]+=1
                            if count[0]==5:path.write_bytes(value+b' ')
                        return value
                    store.read=changed
                with self.subTest(mutation=mutation):
                    if mutation=='positive':self.assert_unavailable(assembler.inspect_paid_scope_receipts(store,**self.invocation()),self.baseline)
                    else:
                        with self.assertRaises(assembler.ContractError):assembler.inspect_paid_scope_receipts(store,**self.invocation())


    def test_owner_one_cannot_be_replaced_by_owner_zero(self):
        self.check_mutations([('wrong owner',lambda m:m['http_observations'][1].update(owner_index=0))],'paid_scope_route')

    def test_all_zero_counts_and_secret_values_have_static_errors(self):
        def work(s):
            s['immutable_rows']['canonical_article_source_revisions'].append(dict(canonical_article_id=s['article']['canonical_article_id']))
            s['counts']['source_revisions']=1
        self.check_mutations([('source row and matching count',lambda m:self.terminal(m,work))],'paid_scope_work')
        sentinel='SCOPE_SECRET_SENTINEL'
        for mutation,code in [(lambda m:m['http_observations'][0]['body']['items'][0].update(title=sentinel),'paid_scope_binding'),
                (lambda m:m['http_observations'][0].update(path='/'+sentinel),'paid_scope_route')]:
            raw=dict(self.baseline);self.alter(raw,mutation)
            with self.assertRaises(assembler.ContractError) as caught:self.inspect(raw)
            self.assertEqual(str(caught.exception),code);self.assertNotIn(sentinel,str(caught.exception))

    def test_region_configuration_label_has_no_independent_region_row(self):
        prefix='paid-access/bankone/'+self.root+'/'
        snapshot=json.loads(self.baseline[prefix+'measured-runtime.json'])['snapshots']['isolated']
        self.assertNotIn('vehicle_configurations',snapshot['immutable_rows'])
        rows=[r for r in snapshot['immutable_rows']['canonical_articles'] if r['vehicle_configuration_id']==self.uid(50)]
        self.assertEqual(len(rows),2);self.assertTrue(all('region' not in row for row in rows))
        # Only the literal CA denial and request/order US facts are retained.
        self.assert_unavailable(self.inspect(self.baseline),self.baseline)


    def test_consistently_repaired_owner_and_chain_swaps_reach_scope_binding(self):
        def swap_owners(s):
            a,b=s['paid_rows']['customer_accounts'];a['firebase_uid'],b['firebase_uid']=b['firebase_uid'],a['firebase_uid']
        def swap_order_accounts(s):
            a,b=s['paid_rows']['workshop_orders'];a['customer_account_id'],b['customer_account_id']=b['customer_account_id'],a['customer_account_id']
            s['paid_rows']['entitlements'][1]['customer_account_id']=b['customer_account_id']
        def swap_configs(s):
            a,b=s['paid_rows']['workshop_orders'];a['configuration_id'],b['configuration_id']=b['configuration_id'],a['configuration_id']
            for i,o in enumerate((a,b)):s['paid_rows']['dataset_requests'][i]['vehicle_key']=o['configuration_id']
            s['paid_rows']['entitlements'][1]['configuration_id']=b['configuration_id']
        def swap_grants(s):
            a,b=s['paid_rows']['workshop_orders'];a['entitlement_id'],b['entitlement_id']=b['entitlement_id'],a['entitlement_id']
            for i,o in enumerate((a,b)):s['paid_rows']['dataset_projections'][i]['entitlement_id']=o['entitlement_id']
        def change_region(s):
            for t in ('workshop_orders','dataset_requests'):
                for row in s['paid_rows'][t]:row['region']='CA'
            s['paid_rows']['entitlements'][1]['region']='CA'
        def different_product(s):
            for table in ('workshop_orders','dataset_requests','dataset_projections'):s['paid_rows'][table][1]['dataset_product_id']=self.uid(999)
        def swap_organizations(s):
            a,b=s['paid_rows']['customer_accounts'];a['personal_organization_id'],b['personal_organization_id']=b['personal_organization_id'],a['personal_organization_id']
        self.check_mutations([(name,lambda m,f=f:self.terminal(m,f)) for name,f in
            [('owners',swap_owners),('accounts',swap_order_accounts),('configs',swap_configs),('grants',swap_grants),
             ('region',change_region),('product',different_product),('organizations',swap_organizations),
             ('owner-b revoked',lambda s:s['paid_rows']['entitlements'][1].update(status='revoked'))]],'paid_scope_binding')


    def test_canonical_unscoped_configuration_is_explicit_null(self):
        self.check_mutations([('missing scope '+str(i),lambda m,i=i:self.terminal(m,
            lambda s:s['immutable_rows']['canonical_articles'][i].pop('vehicle_configuration_id')))
            for i in range(8)],'paid_scope_binding')



class API21RawInspectorTests(unittest.TestCase):
    """Hand-authored source-shaped bytes, never a producer run or accepted capture."""
    candidate = 'b6279480dc57f81f11f93435ae5b3d10b5ae262f'
    cases = [{'case_id': 'test_browser_google_exchange_checkout_library_real_api[chromium]',
      'case_prefix': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/browser/chromium/test_browser_google_exchange_checkout_library_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'client_response_loss_same_key_one_checkout'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_google_exchange_checkout_library_real_api[chromium]',
      'ordinal': 1,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/child.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/result.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/ready.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/go-fixture.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/browser/evidence.json'],
      'root': 'test_browser_google_exchange_checkout_library_real_api'},
     {'case_id': 'test_browser_google_exchange_checkout_library_real_api[firefox]',
      'case_prefix': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/browser/firefox/test_browser_google_exchange_checkout_library_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'client_response_loss_same_key_one_checkout'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_google_exchange_checkout_library_real_api[firefox]',
      'ordinal': 2,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/child.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/result.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/ready.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/go-fixture.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/firefox-bankone/browser/evidence.json'],
      'root': 'test_browser_google_exchange_checkout_library_real_api'},
     {'case_id': 'test_browser_google_exchange_checkout_library_real_api[webkit]',
      'case_prefix': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/browser/webkit/test_browser_google_exchange_checkout_library_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'client_response_loss_same_key_one_checkout'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_google_exchange_checkout_library_real_api[webkit]',
      'ordinal': 3,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/child.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/result.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/ready.json',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/go-fixture.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_google_exchange_checkout_library_real_api/webkit-bankone/browser/evidence.json'],
      'root': 'test_browser_google_exchange_checkout_library_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[chromium-bankone]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/browser/chromium/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[chromium-bankone]',
      'ordinal': 4,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-bankone/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[chromium-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/browser/chromium/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[chromium-banktwo]',
      'ordinal': 5,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/chromium-banktwo/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[firefox-bankone]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/browser/firefox/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[firefox-bankone]',
      'ordinal': 6,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-bankone/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[firefox-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/browser/firefox/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[firefox-banktwo]',
      'ordinal': 7,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/firefox-banktwo/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[webkit-bankone]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/browser/webkit/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[webkit-bankone]',
      'ordinal': 8,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-bankone/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_owned_source_canonical_and_media_real_api[webkit-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/browser/webkit/test_browser_owned_source_canonical_and_media_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_owned_source_canonical_and_media_real_api[webkit-banktwo]',
      'ordinal': 9,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/child.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/result.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/ready.json',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_owned_source_canonical_and_media_real_api/webkit-banktwo/browser/evidence.json'],
      'root': 'test_browser_owned_source_canonical_and_media_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[chromium-bankone]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/browser/chromium/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[chromium-bankone]',
      'ordinal': 10,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-bankone/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[chromium-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/browser/chromium/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[chromium-banktwo]',
      'ordinal': 11,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/chromium-banktwo/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[firefox-bankone]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/browser/firefox/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[firefox-bankone]',
      'ordinal': 12,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-bankone/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[firefox-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/browser/firefox/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[firefox-banktwo]',
      'ordinal': 13,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/firefox-banktwo/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[webkit-bankone]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/browser/webkit/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[webkit-bankone]',
      'ordinal': 14,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-bankone/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_account_scope_and_revocation_real_api[webkit-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/browser/webkit/test_browser_account_scope_and_revocation_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'account_and_exact_scope_isolation',
                              'logout_bfcache_and_firebase_disable_deny'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_account_scope_and_revocation_real_api[webkit-banktwo]',
      'ordinal': 15,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/child.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/result.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/ready.json',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_account_scope_and_revocation_real_api/webkit-banktwo/browser/evidence.json'],
      'root': 'test_browser_account_scope_and_revocation_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[chromium-bankone]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/browser/chromium/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[chromium-bankone]',
      'ordinal': 16,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-bankone/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[chromium-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/browser/chromium/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'chromium',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[chromium-banktwo]',
      'ordinal': 17,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/chromium-banktwo/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[firefox-bankone]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/browser/firefox/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[firefox-bankone]',
      'ordinal': 18,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-bankone/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[firefox-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/browser/firefox/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'firefox',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[firefox-banktwo]',
      'ordinal': 19,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/firefox-banktwo/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[webkit-bankone]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/browser/webkit/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[webkit-bankone]',
      'ordinal': 20,
      'provider': 'bankone',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-bankone/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'},
     {'case_id': 'test_browser_signed_refund_blocks_old_links_real_api[webkit-banktwo]',
      'case_prefix': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/',
      'conditional_failure_ref': 'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/browser/webkit/test_browser_signed_refund_blocks_old_links_real_api-failure.png',
      'engine': 'webkit',
      'expected_assertions': ['official_sdk_cookie_and_pg_session',
                              'return_does_not_grant',
                              'signed_public_webhook_grants_once',
                              'permanent_owner_library_reload',
                              'permanent_owner_library_server_restart',
                              'paid_source_and_actual_s3_image',
                              'source_to_canonical_and_warm_reuse',
                              'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                              'signed_full_refund_denies_old_content_and_media'],
      'junit_classname': 'tests.test_workshop_browser_integration',
      'junit_name': 'test_browser_signed_refund_blocks_old_links_real_api[webkit-banktwo]',
      'ordinal': 21,
      'provider': 'banktwo',
      'required_refs': ['workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/child.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/result.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/ready.json',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/go-fixture.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/browser.stdout.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/browser.stderr.log',
                        'workshop-browser/test_browser_signed_refund_blocks_old_links_real_api/webkit-banktwo/browser/evidence.json'],
      'root': 'test_browser_signed_refund_blocks_old_links_real_api'}]
    inputs = {'apps/api-go/workshop_browser_fixture_test.go': '7520a24bcfa06fe64810c6c17625563d29a2387c6d0531a61713f50b2098bf33',
     'scripts/dev/fixtures/workshop_customer/firebase_transport.js': '96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63',
     'scripts/dev/fixtures/workshop_customer/hostile_source.json': '076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1',
     'scripts/dev/fixtures/workshop_customer/scenarios.json': '83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9',
     'scripts/dev/fixtures/workshop_customer/stripe_checkout.html': '26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083',
     'scripts/dev/workshop_browser_smoke.py': '95f95f25de9c1718901f1dc99580a89d5588a17dd43b8a3a013f8b459e6ba2bc'}
    assets = {'app.mjs': {'bytes': 37545, 'sha256': '4a3e16b3b407e738ed013f4b7ae416fe6c47eb1548d123e90b5b867df5c74788'},
     'article-read.mjs': {'bytes': 2579,
                          'sha256': '2957242037d4bc3ce7894ae2c7e4bae1636406d0256dd75b6150e78c1c4e5178'},
     'auth.mjs': {'bytes': 7908, 'sha256': 'ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2'},
     'catalog.mjs': {'bytes': 11688,
                     'sha256': 'cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52'},
     'commerce.mjs': {'bytes': 7369,
                      'sha256': 'e7f8e2fd45d6cd9f4ec2ef2f3a50d3f090f34e2562d4bbc58f9c23d06e8a1142'},
     'firebase-web.mjs': {'bytes': 112641,
                          'sha256': 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1'},
     'firebase-web.mjs.LEGAL.txt': {'bytes': 35536,
                                    'sha256': '70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319'},
     'firebase-web.provenance.json': {'bytes': 2237,
                                      'sha256': '0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a'},
     'index.html': {'bytes': 10868, 'sha256': '8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68'},
     'progress.mjs': {'bytes': 1076,
                      'sha256': 'dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48'},
     'styles.css': {'bytes': 20773, 'sha256': 'c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c'}}
    missing = ['actual_child_go_browser_exit_receipts',
     'parent_pytest_exit_and_command_receipts',
     'lost_response_pending_measurement_and_snapshot_raw',
     'checkout_idempotency_key_request_response_bytes_and_body_hashes',
     'signed_settlement_refund_http_bytes_and_authentic_delivery',
     'other_account_denial_http_status_and_response_bytes',
     'logout_disable_revocation_http_observations',
     'runtime_image_browser_cache_sdk_install_identity',
     'authenticated_capture_source_observer_and_containment',
     'global_worker_log_per_case_ownership_mapping',
     'finite_api_success_schedule',
     'junit_byte_preserving_capture_mapping',
     'all_final180_families_and_profile_promotion',
     'independent_authentic_raw_review']

    @staticmethod
    def uid(number):
        return '00000000-0000-0000-0000-'+str(number).zfill(12)

    def paid(self, *, isolation=False, revoked=False):
        u=self.uid; now='2026-11-04T00:00:00Z'
        account=dict(customer_account_id=u(10),personal_organization_id=u(11),
            firebase_project_id='fixture-project',firebase_uid='fixture-user',status='active',created_at=now)
        sessions=[dict(customer_account_id=u(10),session_token_hash='\\x'+'a'*64,created_at=now,
            expires_at='2026-11-05T00:00:00Z',firebase_auth_time=1,revoked_at=now if isolation else None)]
        accounts=[account]
        if isolation:
            accounts.append(dict(account,customer_account_id=u(12),personal_organization_id=u(13),firebase_uid='fixture-other'))
            sessions.extend([dict(sessions[0],customer_account_id=u(12),session_token_hash='\\x'+'b'*64,revoked_at=None),
                             dict(sessions[0],session_token_hash='\\x'+'c'*64)])
        order=dict(order_id=u(20),customer_account_id=u(10),organization_id=u(11),configuration_id=u(1),
            dataset_request_id=u(21),dataset_product_id=u(22),entitlement_id=u(23),amount_minor=2000,currency='USD',
            livemode=False,stripe_account_id='acct_fixture',expected_price_id='price_fixture',terms_version='workshop-v1',
            region='US',status='revoked' if revoked else 'paid',checkout_session_id='cs_test_'+'a'*32,
            checkout_url='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32,payment_intent_id='pi_fixture',
            provider_idempotency_key='fixture-key',created_at=now,updated_at=now,paid_at=now,
            first_create_attempt_at=now,last_reconciled_at=None,provider_expires_at=None,
            preparation_attempts=0,preparation_index_job_ids=[],preparation_state='pending',
            preparation_last_error_code=None,preparation_lease_expires_at=None,preparation_lease_owner=None,
            preparation_next_attempt_at=now,revoked_at=now if revoked else None,
            revocation_reason_code='full_refund' if revoked else None)
        grant=dict(entitlement_id=u(23),commerce_order_id=u(20),configuration_id=u(1),customer_account_id=u(10),
            dataset_request_id=u(21),organization_id=u(11),payment_event_id=u(24),provider_event_id='evt_fixture',
            region='US',status='revoked' if revoked else 'active',granted_at=now,
            revoked_at=now if revoked else None,revoke_reason='full_refund' if revoked else None)
        request=dict(dataset_request_id=u(21),dataset_product_id=u(22),organization_id=u(11),correlation_id=u(20),
            vehicle_key=u(1),vehicle_id=u(4),region='US',idempotency_key='workshop:'+u(20),lane='fast',
            processing_version='workshop-v1',source_snapshot_id=None,status='purchased',created_at=now,updated_at=now)
        projection=dict(dataset_projection_id=u(25),dataset_request_id=u(21),dataset_product_id=u(22),
            entitlement_id=u(23),created_at=now)
        return dict(customer_accounts=accounts,auth_sessions=sessions,workshop_orders=[order],entitlements=[grant],
            dataset_requests=[request],dataset_projections=[projection])

    def snapshot(self, bank, *, work=False, isolation=False, revoked=False):
        u=self.uid
        paid=self.paid(isolation=isolation,revoked=revoked)
        tables=('schema_migrations','catalog_articles','canonical_articles',
            'canonical_article_source_revisions','canonical_article_source_observations',
            'canonical_article_revisions','canonical_article_reviews','canonical_article_rewrite_attempts',
            'source_fetch_jobs','publication_events','source_snapshots','catalog_article_provider_scopes',
            'catalog_article_index_pages','canonical_article_aliases','customer_accounts','auth_sessions',
            'workshop_orders','workshop_checkout_requests')
        rows={table:[] for table in tables}
        article=dict(canonical_article_id=u(5),provider_slug=bank,vehicle_configuration_id=u(1),vehicle_id=u(4))
        rows['canonical_articles']=[article.copy()]
        for table in ('customer_accounts','auth_sessions','workshop_orders'):rows[table]=copy.deepcopy(paid[table])
        rows['workshop_checkout_requests']=[dict(order_id=u(20))]
        counts=dict(article_jobs=0,source_revisions=0,canonical_revisions=0,published_revisions=0,
            publication_events=0,source_observations=0)
        if work:
            rows['canonical_article_revisions']=[dict(canonical_article_id=u(5),status='published')]
            counts.update(canonical_revisions=1,published_revisions=1)
        zero=lambda:dict(bankone=0,banktwo=0)
        return dict(article=article,immutable_rows=rows,
            immutable_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
            paid_rows=paid,counts=counts,ensure=dict(entered=0,completed=0,active=0),ensure_requests=[],
            selector_ensure=dict(entered=0,completed=0,active=0),selector_ensure_requests=[],
            provider_calls=zero(),source_calls=zero(),asset_calls=zero(),provider_traces=dict(bankone=[],banktwo=[]),
            model_calls=int(work),payment_calls=1,grant_calls=1,
            proxy=dict(request_received=int(work),upstream_completed=int(work),downstream_completed=int(work),downstream_waiting=0,
                response_captured=work,errors=[]),
            workers=[dict(kind='cli',alive=True,exit_code=None) for _ in range(2)] if work else [])

    def measurement(self, *, isolation=False, revoked=False):
        return dict(auth_sessions=3 if isolation else 1,hashed_sessions=3 if isolation else 1,
            workshop_orders=1,workshop_checkout_requests=1,entitlements=1,dataset_requests=1,dataset_projections=1,
            payment_events=2 if revoked else 1,sdk_cert_calls=1,sdk_user_calls=2,sdk_unexpected=0,image_reads=2,
            orders=[dict(order_id=self.uid(20),state='revoked' if revoked else 'paid',owner=self.uid(10),
                configuration_id=self.uid(1),region='US')])

    def model(self):
        result=[]
        for index,case in enumerate(self.cases):
            google=case['root'].startswith('test_browser_google_')
            isolation=case['root'].startswith('test_browser_account_')
            refund=case['root'].startswith('test_browser_signed_')
            bank=case['provider'];engine=case['engine']
            ready=dict(version='v1',kind='api-fixture',origin='https://127.0.0.1:12345',
                certificate_sha256='a'*64,sdk_sha256=self.assets['firebase-web.mjs']['sha256'],
                scope=dict(configuration=self.uid(1),adjacent=self.uid(2),other_region=self.uid(3),
                    vehicle=self.uid(4),article=self.uid(5),unscoped=self.uid(6),provider=bank))
            final=self.snapshot(bank,work=not google,isolation=isolation,revoked=refund)
            before=self.measurement()
            row=dict(browser=engine,scenario=case['root'],status='passed',elapsed_seconds=70.5,
                provider=bank,assertions={key:True for key in case['expected_assertions']},
                requests=[dict(method='GET',path='/workshop/'),dict(method='POST',path='/auth/firebase/session'),
                    dict(method='GET',path='/v1/catalog/vehicles/{uuid}/articles/{uuid}'),
                    dict(method='GET',path='/v1/catalog/images/{capability}')],
                measurement=self.measurement(isolation=isolation,revoked=refund),
                restart=dict(runtime_before=dict(application_generation=0),runtime_after=dict(application_generation=1),
                    before=copy.deepcopy(before),after=copy.deepcopy(before)),warm={})
            if not google:
                warm=self.snapshot(bank,work=True)
                row['warm']=dict(before=warm,after=copy.deepcopy(warm),reader_before=0,reader_after=1)
            evidence=dict(version='v1',mode='api-fixture',candidate_sha=self.candidate,
                sdk_sha256=ready['sdk_sha256'],playwright_version='1.64.1',engine_revisions={engine:'synthetic-revision'},
                browser_versions={engine:'synthetic-version'},input_sha256=copy.deepcopy(self.inputs),
                provenance=dict(certificate_sha256='a'*64,assets=copy.deepcopy(self.assets)),results=[row])
            child=dict(version='v1',mode='api-fixture',candidate_sha=self.candidate,browser=engine,provider=bank,
                test=case['root'],fixture_database='lifecycle_'+str(index).zfill(32),passed=True,
                final_snapshot=final,worker_exits=[] if google else [dict(kind='cli',exit_code=-15,
                    terminated=True,intentional_cleanup=True,alive_before_cleanup=True) for _ in range(2)])
            result.append(dict(case=case,ready=ready,evidence=evidence,result=child))
        return result

    def files(self, model):
        raw={}
        for item in model:
            case=item['case'];prefix=case['case_prefix']
            raw.update({ref:b'SECRET_SENTINEL opaque support bytes' for ref in case['required_refs']})
            for filename,key in (('result.json','result'),('ready.json','ready'),('browser/evidence.json','evidence')):
                raw[prefix+filename]=json.dumps(item[key],allow_nan=False).encode()
        leaves=[]; failures=skipped=0
        for item in model:
            outcome=''
            if item['result']['passed'] is False:
                rows=item['evidence']['results']
                unavailable=rows and rows[0]['status']=='unavailable'
                skipped+=bool(unavailable);failures+=not unavailable
                outcome='<skipped message="SECRET_SENTINEL" />' if unavailable else '<failure message="SECRET_SENTINEL">private failure text</failure>'
            leaves.append('<testcase classname="tests.test_workshop_browser_integration" name="'+
                item['case']['case_id']+'" time="70.5">'+outcome+'</testcase>')
        raw['workshop-browser-api.xml']=('<testsuites name="pytest tests"><testsuite name="pytest" tests="'+str(len(model))+
            '" failures="'+str(failures)+'" errors="0" skipped="'+str(skipped)+
            '" time="1500.5" timestamp="2026-11-04T00:00:00Z" hostname="synthetic">'+
            ''.join(leaves)+'</testsuite></testsuites>').encode()
        return raw

    def invocation(self):
        return dict(candidate_sha=self.candidate,trusted_base_sha=TRUSTED_BASE,profile_sha256='b'*64)

    def store(self, raw, directory):
        declarations=[]
        for index,(ref,data) in enumerate(raw.items()):
            path=Path(directory)/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            declarations.append(dict(artifact_id='api-'+str(index),ref=ref,kind='junit' if ref.endswith('.xml') else 'raw',
                sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),visibility='private'))
        return assembler.ArtifactStore(directory,declarations)

    def inspect(self, model=None, *, raw=None, real=False, **kwargs):
        self.assertTrue(callable(getattr(assembler,'inspect_api21_receipts',None)), 'internal API21 inspector is missing')
        raw=self.files(self.model() if model is None else model) if raw is None else raw
        if real:
            with tempfile.TemporaryDirectory() as directory:
                with self.store(raw,directory) as store:return assembler.inspect_api21_receipts(store,**(self.invocation()|kwargs))
        class Store:
            by_ref={ref:dict(artifact_id=ref,kind='junit' if ref.endswith('.xml') else 'raw',visibility='private') for ref in raw}
            def read(self,ref):return raw[ref]
            def recheck(self):pass
        return assembler.inspect_api21_receipts(Store(),**(self.invocation()|kwargs))

    def reject(self, model=None, *, raw=None, **kwargs):
        with self.assertRaises(assembler.ContractError) as caught:self.inspect(model,raw=raw,**kwargs)
        self.assertNotIn('SECRET_SENTINEL',str(caught.exception))

    def test_complete_synthetic_inventory_observed_without_acceptance(self):
        result=self.inspect(real=True)
        self.assertEqual(result['observed_case_ids'],[case['case_id'] for case in self.cases])
        self.assertEqual(result['status'],'unavailable');self.assertIs(result['complete'],False)
        self.assertEqual(result['verified_case_ids'],[])
        self.assertEqual(result['accepted_case_credit'],0);self.assertEqual(result['accepted_new_case_credit'],0)
        self.assertEqual(result['missing_validation_families'],self.missing)
        self.assertEqual(result['diagnostics'],[])
        for flag in assembler.FLAGS:self.assertIs(result[flag],False)

    def test_closed_schemas_identity_source_support_and_authority(self):
        mutations=[
            lambda x:x['result'].update(candidate_sha='0'*40),
            lambda x:x['result'].update(go_exit_code=0),
            lambda x:x['result'].update(passed=1),
            lambda x:x['result'].update(fixture_database=''),
            lambda x:x['ready'].update(origin='https://localhost:1234/?token=SECRET_SENTINEL'),
            lambda x:x['ready']['scope'].update(provider='banktwo'),
            lambda x:x['ready']['scope'].update(adjacent=self.uid(1)),
            lambda x:x['evidence'].update(mode='dto-fixture'),
            lambda x:x['evidence'].update(playwright_version='1.64.0'),
            lambda x:x['evidence']['input_sha256'].update({'scripts/dev/workshop_browser_smoke.py':'0'*64}),
            lambda x:x['evidence']['provenance']['assets']['app.mjs'].update(bytes=1),
            lambda x:x['evidence']['provenance'].update(certificate_sha256='b'*64),
            lambda x:x['evidence']['engine_revisions'].update(leak=[]),
            lambda x:x['evidence']['results'][0]['assertions'].update(forged=True),
            lambda x:x['evidence']['results'][0]['requests'][0].update(query={'token':['SECRET_SENTINEL']}),
            lambda x:x['evidence']['results'][0]['requests'][0].update(path='/v1/catalog/images/v2.SECRET_SENTINEL'),
            lambda x:x['evidence']['results'][0].update(elapsed_seconds=True),
            lambda x:x['evidence']['results'][0].update(browser='firefox'),
            lambda x:x['result']['final_snapshot']['immutable_rows']['source_snapshots'].append(dict(accepted=True)),
            lambda x:x['result']['final_snapshot']['immutable_rows']['source_snapshots'].append(dict(candidate_tree='0'*40)),
            lambda x:x['result']['final_snapshot']['immutable_rows']['source_snapshots'].append(dict(profile_version='dto-fixture-v1')),
        ]
        for index,mutate in enumerate(mutations):
            model=self.model();mutate(model[0])
            with self.subTest(mutation=index):self.reject(model)
        for kwargs in (dict(candidate_sha='0'*40),dict(profile_version='other')):self.reject(**kwargs)
        raw=self.files(self.model())
        for ref in (next(iter(raw)),'workshop-browser-api.xml'):
            changed=raw.copy();changed.pop(ref)
            self.reject(raw=changed)
        changed=raw.copy();changed['workshop-browser-tests.xml']=changed.pop('workshop-browser-api.xml');self.reject(raw=changed)
        changed=raw.copy();changed['extra.log']=b'claimed exit0';self.reject(raw=changed)

    def test_semantic_measurement_restart_warm_scope_and_workers(self):
        mutations=[
            lambda x:x['evidence']['results'][0]['measurement'].update(hashed_sessions=0),
            lambda x:x['evidence']['results'][0]['measurement'].update(sdk_unexpected=1),
            lambda x:x['evidence']['results'][0]['measurement'].update(entitlements=True),
            lambda x:x['evidence']['results'][0]['measurement']['orders'][0].update(owner=self.uid(99)),
            lambda x:x['evidence']['results'][0]['restart']['runtime_after'].update(application_generation=3),
            lambda x:x['evidence']['results'][0]['restart']['after'].update(payment_events=4),
            lambda x:x['evidence']['results'][0]['warm'].update(reader_after=0),
            lambda x:x['evidence']['results'][0]['warm']['after'].update(model_calls=2),
            lambda x:x['result']['final_snapshot'].update(immutable_sha256='0'*64),
            lambda x:x['result']['final_snapshot']['paid_rows']['workshop_orders'][0].update(amount_minor=0),
            lambda x:x['result']['final_snapshot']['paid_rows']['entitlements'][0].update(customer_account_id=self.uid(99)),
            lambda x:x['result']['final_snapshot']['paid_rows']['dataset_projections'][0].update(entitlement_id=self.uid(99)),
            lambda x:x['result']['final_snapshot']['paid_rows']['dataset_requests'][0].update(region='CA'),
            lambda x:x['result']['final_snapshot']['paid_rows']['auth_sessions'][0].update(session_token_hash='SECRET_SENTINEL'),
            lambda x:x['result']['final_snapshot']['paid_rows']['workshop_orders'][0].update(status='revoked'),
            lambda x:x['result']['final_snapshot']['counts'].update(source_revisions=2),
            lambda x:x['result']['final_snapshot']['provider_calls'].update(bankone=1),
            lambda x:x['result']['final_snapshot']['proxy'].update(errors=['SECRET_SENTINEL']),
            lambda x:x['result']['final_snapshot']['ensure'].update(entered=1,active=1),
            lambda x:x['result']['final_snapshot']['workers'][0].update(alive=False),
            lambda x:x['result']['worker_exits'].pop(),
            lambda x:x['result']['worker_exits'][0].update(exit_code=True),
            lambda x:x['result']['worker_exits'][0].update(intentional_cleanup=False),
            lambda x:x['result']['worker_exits'][0].update(browser_exit_code=0),
        ]
        for index,mutate in enumerate(mutations):
            model=self.model();mutate(model[3])
            with self.subTest(mutation=index):self.reject(model)
        model=self.model();model[15]['result']['final_snapshot']['paid_rows']['entitlements'][0].update(revoked_at=None)
        self.reject(model)
        model=self.model();model[0]['result']['worker_exits']=[dict(kind='cli',exit_code=0,terminated=True,intentional_cleanup=True,alive_before_cleanup=True)]
        self.reject(model)

    def test_junit_order_counters_outcomes_and_hostile_json_xml(self):
        raw=self.files(self.model());junit=raw['workshop-browser-api.xml']
        for data in (junit.replace(b'tests="21"',b'tests="20"'),
            junit.replace(b'failures="0"',b'failures="1"'),
            junit.replace(b'tests.test_workshop_browser_integration',b'tests.test_workshop_dto_integration'),
            junit.replace(b'</testcase>',b'<skipped /></testcase>',1),
            junit.replace(self.cases[0]['case_id'].encode(),self.cases[1]['case_id'].encode(),1),
            b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'+junit,
            b'<testsuite>'+b'<x>'*65+b'</x>'*65+b'</testsuite>',b'<testsuites>'):
            changed=raw.copy();changed['workshop-browser-api.xml']=data;self.reject(raw=changed)
        model=self.model();model[0],model[1]=model[1],model[0];self.reject(model)
        ref=self.cases[0]['case_prefix']+'result.json'
        for data in (b'{"passed":false,"passed":true}',b'{',b'{"x":NaN}',b'{"x":1e999}',bytes([255]),
                     b'{"x":'+b'['*1100+b'0'+b']'*1100+b'}'):
            changed=raw.copy();changed[ref]=data;self.reject(raw=changed)

    def test_failed_unavailable_partial_preserve_private_bytes_and_safe_diagnostics(self):
        for status in ('failed','unavailable'):
            model=self.model();item=model[0];item['result']['passed']=False
            item['result'].pop('final_snapshot');item['result'].pop('worker_exits')
            row=dict(browser='chromium',scenario=item['case']['root'],status=status,error='SECRET_SENTINEL')
            if status=='failed':row['elapsed_seconds']=2
            item['evidence']['results']=[row]
            if status=='unavailable':item['evidence'].pop('browser_versions')
            raw=self.files(model);raw[item['case']['conditional_failure_ref']]=b'SECRET_SENTINEL png bytes'
            result=self.inspect(raw=raw,real=True)
            self.assertEqual(len(result['observed_case_ids']),20)
            self.assertEqual(result['diagnostics'],[dict(case_id=item['case']['case_id'],category='producer_'+status)])
            self.assertNotIn('SECRET_SENTINEL',json.dumps(result))
            self.assertEqual(result['verified_case_ids'],[])
        model=self.model();model[0]['result']['passed']=False
        model[0]['result'].pop('final_snapshot');model[0]['result'].pop('worker_exits')
        model[0]['evidence']['results']=[];model[0]['evidence'].pop('browser_versions')
        result=self.inspect(model)
        self.assertEqual(result['diagnostics'][0]['category'],'producer_partial')

    def test_inspector_has_no_process_network_producer_or_stdout_side_effects(self):
        model=self.model();output=io.StringIO()
        with patch('subprocess.run',side_effect=AssertionError('process forbidden')), \
             patch('subprocess.Popen',side_effect=AssertionError('process forbidden')), \
             patch('socket.socket',side_effect=AssertionError('network forbidden')), \
             patch('builtins.print',side_effect=AssertionError('output forbidden')):
            self.assertEqual(self.inspect(model)['accepted_case_credit'],0)
        self.assertNotIn('workshop_browser_smoke',sys.modules)

    def test_confined_transport_missing_hash_replacement_alias_and_limits(self):
        raw=self.files(self.model())
        for mode in ('hash','replace','symlink','hardlink','extra','public','kind'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                with self.store(raw,directory) as store:
                    ref=self.cases[0]['required_refs'][0];record=store.by_ref[ref];path=Path(directory)/ref
                    if mode=='hash':record['sha256']='0'*64
                    elif mode=='replace':path.write_bytes(b'X'*len(raw[ref]))
                    elif mode=='symlink':path.unlink();path.symlink_to('/etc/passwd')
                    elif mode=='hardlink':path.unlink();os.link(Path(directory)/self.cases[1]['required_refs'][0],path)
                    elif mode=='extra':(Path(directory)/'undeclared.log').write_bytes(b'x')
                    elif mode=='public':record['visibility']='public'
                    else:record['kind']='manifest'
                    with self.assertRaises(assembler.ContractError):assembler.inspect_api21_receipts(store,**self.invocation())
        self.assertEqual(assembler.MAX_ARTIFACT_BYTES,8*1024*1024)
        self.assertEqual(assembler.MAX_EVIDENCE_BYTES,64*1024*1024)

    @staticmethod
    def reseal(snapshot, *, copies=True):
        if copies:
            for table in ('customer_accounts','auth_sessions','workshop_orders'):
                snapshot['immutable_rows'][table]=copy.deepcopy(snapshot['paid_rows'][table])
        snapshot['immutable_sha256']=hashlib.sha256(json.dumps(snapshot['immutable_rows'],sort_keys=True,allow_nan=False).encode()).hexdigest()

    def test_semantic_mutations_reach_binding_checks_after_rehash(self):
        mutations=[
            ('api21_accounts',lambda s:s['paid_rows']['customer_accounts'][0].update(firebase_uid='intruder')),
            ('api21_paid_scope',lambda s:s['paid_rows']['workshop_orders'][0].update(configuration_id=self.uid(99))),
            ('api21_paid_scope',lambda s:s['paid_rows']['entitlements'][0].update(commerce_order_id=self.uid(99))),
            ('api21_paid_scope',lambda s:s['paid_rows']['dataset_requests'][0].update(organization_id=self.uid(99))),
            ('api21_paid_scope',lambda s:s['paid_rows']['dataset_projections'][0].update(dataset_product_id=self.uid(99))),
            ('api21_payment_binding',lambda s:s['paid_rows']['workshop_orders'][0].update(currency='CAD')),
            ('api21_payment_binding',lambda s:s['paid_rows']['workshop_orders'][0].update(livemode=True)),
            ('api21_payment_binding',lambda s:s['paid_rows']['workshop_orders'][0].update(stripe_account_id='wrong')),
            ('api21_revocation',lambda s:s['paid_rows']['workshop_orders'][0].update(revoked_at='2026-11-04T00:00:00Z')),
            ('api21_sessions',lambda s:s['paid_rows']['auth_sessions'][0].update(customer_account_id=self.uid(99))),
            ('api21_count_binding',lambda s:s['immutable_rows']['canonical_article_revisions'].append(dict(canonical_article_id=self.uid(5),status='published'))),
            ('api21_article_seam',lambda s:s['immutable_rows']['canonical_articles'][0].update(provider_slug='banktwo')),
            ('api21_resource_trace',lambda s:(s['provider_calls'].update(bankone=1),s['provider_traces']['bankone'].append('/fixture/resources/body'))),
        ]
        for position in ('final','warm_before','warm_after'):
            for code,mutate in mutations:
                model=self.model();item=model[3]
                snapshot=item['result']['final_snapshot'] if position=='final' else item['evidence']['results'][0]['warm'][position[5:]]
                mutate(snapshot);self.reseal(snapshot)
                with self.subTest(position=position,code=code),self.assertRaises(assembler.ContractError) as caught:self.inspect(model)
                self.assertEqual(str(caught.exception),code)
        model=self.model();s=model[3]['result']['final_snapshot']
        s['immutable_rows']['customer_accounts'][0]['status']='different';self.reseal(s,copies=False)
        with self.assertRaises(assembler.ContractError) as caught:self.inspect(model)
        self.assertEqual(str(caught.exception),'api21_paid_row_seam')

    def test_actual_source_route_templates_and_opaque_producer_hash_spacing(self):
        model=self.model()
        row=model[3]['evidence']['results'][0]
        row['requests']=[dict(method=method,path=path) for method,path in (
            ('GET','/auth/config'),('GET','/auth/session'),('POST','/auth/firebase/session'),('POST','/auth/logout'),
            ('GET','/workshop/fonts/InstrumentSans.ttf'),('GET','/workshop/purchase-config.json'),
            ('GET','/v1/catalog/years/2024/makes'),
            ('GET','/v1/catalog/years/2024/makes/example/models'),
            ('GET','/v1/catalog/years/2024/makes/example/models/car/configurations'),
            ('POST','/v1/catalog/vehicles/{uuid}/articles/{uuid}/prepare'),
            ('GET','/v1/catalog/vehicles/{uuid}/articles/{uuid}/source'))]
        snapshot=model[3]['result']['final_snapshot']
        snapshot['immutable_rows']['source_snapshots'].append(dict(opaque='é private SQL',amount=1.5))
        self.reseal(snapshot)
        self.assertEqual(self.inspect(model)['accepted_case_credit'],0)

    def test_nested_reserved_identities_and_redacted_exceptions_at_retained_positions(self):
        for index in (0,3,15):
            for key,value in (('trusted_base_sha','0'*40),('profile_sha256','0'*64),
                ('producer_sha','0'*40),('source_tree','0'*40),('verified_case_ids',['forged']),
                ('accepted_case_credit',1),('fixture_verified',True)):
                model=self.model();snapshot=model[index]['result']['final_snapshot']
                snapshot['immutable_rows']['source_snapshots'].append({key:value,'private':'SECRET_SENTINEL'})
                self.reseal(snapshot)
                with self.subTest(index=index,key=key),self.assertRaises(assembler.ContractError) as caught:self.inspect(model)
                self.assertIn(str(caught.exception),('api21_identity','api21_forged_authority'))
                self.assertNotIn('SECRET_SENTINEL',str(caught.exception))

    def test_cli_stays_exit_three_and_zero_after_internal_inspection(self):
        self.assertEqual(self.inspect()['verified_case_ids'],[])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'envelope.json';path.write_text(json.dumps(committed_envelope()))
            root=Path(directory)/'raw';root.mkdir();(root/'proof.json').write_bytes(b'{}')
            output=io.StringIO();errors=io.StringIO()
            with patch('sys.stdout',output),patch('sys.stderr',errors), \
                 patch.object(assembler,'inspect_api21_receipts',side_effect=AssertionError('CLI dispatch forbidden')):
                code=assembler.main(['validate','--manifest',str(path),'--evidence-root',str(root),
                    '--trusted-base-sha',TRUSTED_BASE,'--task-ref',TASK,'--requested-tier','fixture'])
            self.assertEqual(code,3)
            result=json.loads(output.getvalue());self.assertTrue(all(value==0 for value in result['derived_counts'].values()))
            self.assertTrue(all(result[flag] is False for flag in assembler.FLAGS))

    def test_source_early_failure_can_omit_only_ready_and_evidence(self):
        model=self.model();item=model[0];item['result']['passed']=False
        item['result'].pop('final_snapshot');item['result'].pop('worker_exits')
        item['evidence']['results']=[];item['evidence'].pop('browser_versions')
        raw=self.files(model);prefix=item['case']['case_prefix']
        for names in (('browser/evidence.json',),('ready.json','browser/evidence.json')):
            changed=raw.copy()
            for name in names:changed.pop(prefix+name)
            result=self.inspect(raw=changed,real=True)
            self.assertEqual(result['diagnostics'],[dict(case_id=item['case']['case_id'],category='producer_partial')])
            self.assertEqual(len(result['observed_case_ids']),20)
            self.assertEqual(result['accepted_case_credit'],0)
        changed=raw.copy();changed.pop(prefix+'child.log');self.reject(raw=changed)
        changed=self.files(self.model());changed.pop(prefix+'browser/evidence.json');self.reject(raw=changed)

    def test_large_finite_integer_duration_is_consistency_only(self):
        model=self.model();model[0]['evidence']['results'][0]['elapsed_seconds']=10**400
        self.assertEqual(self.inspect(model)['accepted_case_credit'],0)

    def test_refund_reason_and_model_proxy_conservation(self):
        for field,value in (('revocation_reason_code','chargeback_lost'),('revoked_at',None)):
            model=self.model();snapshot=model[15]['result']['final_snapshot']
            snapshot['paid_rows']['workshop_orders'][0][field]=value;self.reseal(snapshot)
            self.reject(model)
        model=self.model();model[15]['result']['final_snapshot']['paid_rows']['entitlements'][0]['revoke_reason']='other'
        self.reject(model)
        for position in ('final','before','after'):
            model=self.model();snapshot=model[3]['result']['final_snapshot'] if position=='final' else model[3]['evidence']['results'][0]['warm'][position]
            snapshot['proxy']['response_captured']=False
            with self.subTest(position=position):self.reject(model)
        model=self.model();model[3]['result']['final_snapshot']['model_calls']=2
        self.reject(model)

    def test_nonpass_validates_present_snapshots_cleanup_and_passed_row_internals(self):
        mutations=(
            lambda x:x['result'].update(final_snapshot='PRIVATE_SENTINEL'),
            lambda x:x['result'].update(worker_exits={'invalid':'PRIVATE_SENTINEL'}),
            lambda x:x['evidence']['results'][0].update(measurement='PRIVATE_SENTINEL'),
            lambda x:x['evidence']['results'][0].update(restart=[]),
            lambda x:x['evidence']['results'][0].update(warm=None),
        )
        for index,mutate in enumerate(mutations):
            model=self.model();model[3]['result']['passed']=False;mutate(model[3])
            with self.subTest(mutation=index):
                with self.assertRaises(assembler.ContractError) as caught:self.inspect(model,real=True)
                self.assertNotIn('PRIVATE_SENTINEL',str(caught.exception))
        for keep_final,keep_cleanup in ((True,True),(True,False),(False,False)):
            model=self.model();item=model[3];item['result']['passed']=False
            if not keep_final:item['result'].pop('final_snapshot')
            if not keep_cleanup:item['result'].pop('worker_exits')
            result=self.inspect(model,real=True)
            self.assertEqual(result['diagnostics'],[dict(case_id=item['case']['case_id'],category='producer_partial')])
            self.assertEqual(len(result['observed_case_ids']),20)
            self.assertEqual(result['accepted_case_credit'],0)

    def test_isolation_session_distribution_and_nullable_vehicle_fk(self):
        model=self.model();snapshot=model[9]['result']['final_snapshot']
        snapshot['paid_rows']['auth_sessions'][2]['customer_account_id']=self.uid(12)
        self.reseal(snapshot)
        with self.subTest(distribution='one-owner-two-other'):self.reject(model,real=True)
        for vehicle in ('not-a-uuid',self.uid(99)):
            model=self.model();model[3]['result']['final_snapshot']['paid_rows']['dataset_requests'][0]['vehicle_id']=vehicle
            with self.subTest(vehicle=vehicle):self.reject(model,real=True)
        model=self.model();model[3]['result']['final_snapshot']['paid_rows']['dataset_requests'][0]['vehicle_id']=None
        self.assertEqual(self.inspect(model,real=True)['accepted_case_credit'],0)

    def test_nonpass_retained_fields_follow_source_assignment_order(self):
        for status in ('failed','empty'):
            model=self.model();item=model[3];item['result']['passed']=False
            item['result'].pop('worker_exits')
            item['evidence']['results']=[] if status=='empty' else [dict(browser=item['case']['engine'],
                scenario=item['case']['root'],status='failed',elapsed_seconds=1,error='PRIVATE_SENTINEL')]
            if status=='empty':item['evidence'].pop('browser_versions')
            with self.subTest(status=status),self.assertRaises(assembler.ContractError):self.inspect(model,real=True)
        model=self.model();item=model[3];item['result']['passed']=False;item['result'].pop('final_snapshot')
        with self.assertRaises(assembler.ContractError):self.inspect(model,real=True)

    def test_closed_nonpass_browser_version_and_elapsed_branch_matrix(self):
        def branch(status,versions,elapsed):
            model=self.model();item=model[3];item['result']['passed']=False
            item['result'].pop('final_snapshot');item['result'].pop('worker_exits')
            if status=='empty':item['evidence']['results']=[]
            elif status!='passed':
                row=dict(browser=item['case']['engine'],scenario=item['case']['root'],status=status,error='PRIVATE_SENTINEL')
                if elapsed:row['elapsed_seconds']=1
                item['evidence']['results']=[row]
            if not versions:item['evidence'].pop('browser_versions')
            return model
        for status,versions,elapsed in (('unavailable',True,False),('empty',True,False),('unavailable',False,True)):
            with self.subTest(status=status,versions=versions,elapsed=elapsed),self.assertRaises(assembler.ContractError):
                self.inspect(branch(status,versions,elapsed),real=True)
        model=self.model();item=model[3];item['result']['passed']=False
        item['evidence'].pop('browser_versions')
        with self.assertRaises(assembler.ContractError):self.inspect(model,real=True)
        for status,versions,elapsed in (('passed',True,True),('failed',True,True),
            ('passed',False,True),('failed',False,True),('unavailable',False,False),('empty',False,False)):
            with self.subTest(positive=status):
                result=self.inspect(branch(status,versions,elapsed),real=True)
                self.assertEqual(len(result['observed_case_ids']),20)
                self.assertEqual(result['verified_case_ids'],[])
                self.assertEqual(result['accepted_case_credit'],0)
                self.assertEqual(result['diagnostics'][0]['category'],
                    'producer_partial' if status in ('passed','empty') else 'producer_'+status)


if __name__ == '__main__': unittest.main()
