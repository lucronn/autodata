"""Host preparation: synthetic accepted inputs and recording commands only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent

def load(name):
    path = HERE / (name + '.py')
    if not path.exists(): raise AssertionError('missing host preparation entrypoint: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

class BundleTests(unittest.TestCase):
    def test_inventory_is_sorted_and_credential_free(self):
        builder = load('build_host_bundle')
        names = builder.source_inventory(HERE.parents[2])
        self.assertEqual(names, sorted(set(names)))
        self.assertIn('infra/compose/compose.production.yaml', names)
        self.assertIn('scripts/dev/migrate_sql.sh', names)
        self.assertIn('infra/deploy/gce/host-bootstrap-roles.sql', names)
        self.assertFalse(any('/test_' in name or name.endswith('host.json') for name in names))
        self.assertEqual(len([name for name in names if name.startswith('db/migrations/')]), 40)

    def test_wrong_source_and_dirty_tree_rejected_before_output(self):
        builder = load('build_host_bundle')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); subprocess.run(['git', 'init', '-q', root], check=True)
            (root / 'file').write_text('a')
            subprocess.run(['git', '-C', root, 'add', '.'], check=True)
            subprocess.run(['git', '-C', root, '-c', 'user.name=test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            sha = subprocess.check_output(['git', '-C', root, 'rev-parse', 'HEAD']).decode().strip()
            with self.assertRaises(ValueError): builder.build(root, 'a'*40, root/'output')
            (root/'file').write_text('changed')
            with self.assertRaises(ValueError): builder.build(root, sha, root/'output')
            self.assertFalse((root/'output').exists())

class ApprovalTests(unittest.TestCase):
    def test_bad_approval_fields_types_expiry_and_environment(self):
        p = load('host_provision')
        with self.assertRaises(ValueError): p.validate_approval({}, 'a'*40, 'provision')
        with self.assertRaises(ValueError): p.validate_approval({'schema_version':True}, 'a'*40, 'provision')
        with self.assertRaises(ValueError): p.validate_sha('../invalid')

    def test_bundle_rejects_traversal_link_hash_mode_and_unlisted_files(self):
        p = load('host_provision')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            item = root/'safe'; item.write_bytes(b'safe'); item.chmod(0o444)
            inventory = {'schema_version':1, 'source_sha':'a'*40, 'files':[{'path':'safe','bytes':4,'sha256':p.digest(b'safe'),'mode':292}]}
            # Inventory destinations must be the fixed bundle layout.
            for name in ('../outside','/absolute','safe'):
                inventory['files'][0]['path'] = name
                with self.assertRaises(ValueError): p.validate_inventory(root, inventory, 'a'*40)

    def test_bounded_executor_reaps_timeout_and_caps_output(self):
        p = load('host_provision')
        with self.assertRaises(Exception): p.command(['/usr/bin/python3','-c','import time; time.sleep(5)'],timeout=.05)
        with self.assertRaises(Exception): p.command(['/usr/bin/python3','-c','print("x"*20000)'],maximum=1024)
        self.assertEqual(p.command(['/usr/bin/python3','-c','print("ok")']), b'ok\n')

if __name__ == '__main__': unittest.main()

class JournalAndPolicyTests(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0,"root-owned temporary filesystem test")
    def test_package_failure_restores_prior_policy_exactly(self):
        p = load('host_provision')
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory)/'policy-rc.d'; policy.write_bytes(b'#!/bin/sh\nexit 0\n'); policy.chmod(0o751)
            class Files:
                def read(self,path,mode,pin=False): return Path(path).read_bytes()
            with patch.object(p,'POLICY',str(policy)):
                with self.assertRaises(RuntimeError):
                    with p.inhibit_starts(Files()):
                        self.assertEqual(policy.read_bytes(),b'#!/bin/sh\nexit 101\n')
                        raise RuntimeError('synthetic dpkg failure')
            self.assertEqual(policy.read_bytes(),b'#!/bin/sh\nexit 0\n')
            self.assertEqual(policy.stat().st_mode & 0o777,0o751)
            self.assertFalse(Path(str(policy)+'.autodata-saved').exists())

    def test_partial_journal_refuses_blind_retry_and_contains_no_output(self):
        p = load('host_provision')
        a = {'authorization_id':'synthetic','source_sha':'a'*40,'operation':'prepare-new-empty-staging-host',
            'bundle_inventory_sha256':'b'*64,'service_config_sha256':'c'*64}
        with tempfile.TemporaryDirectory() as directory, patch.object(p,'RECEIPTS',directory):
            journal = p.Journal(a); journal.stage('packages-installed')
            with self.assertRaises(ValueError): p.Journal(a)
            output = json.loads(Path(journal.path).read_bytes())
            self.assertEqual(output['status'],'incomplete')
            self.assertEqual(output['stages'],['packages-installed'])
            self.assertEqual(Path(journal.path).stat().st_mode & 0o777,0o600)

    @unittest.skipUnless(os.geteuid() == 0,"root-owned temporary filesystem test")
    def test_duplicate_json_and_symlink_hardlink_inputs_fail(self):
        p = load('host_provision')
        with self.assertRaises(ValueError): p.strict_json(b'{"x":1,"x":2}')
        with tempfile.TemporaryDirectory(dir='/root') as directory:
            root = Path(directory); root.chmod(0o700); original = root/'original'; original.write_bytes(b'data'); original.chmod(0o600)
            with p.Pins() as pins:
                self.assertEqual(pins.read(str(original)),b'data')
                original.write_bytes(b'evil')
                with self.assertRaises(ValueError): pins.recheck()
            link = root/'link'; link.symlink_to(original)
            with p.Pins() as pins:
                with self.assertRaises(OSError): pins.read(str(link))
            os.link(original,root/'hardlink')
            with p.Pins() as pins:
                with self.assertRaises(ValueError): pins.read(str(original))
