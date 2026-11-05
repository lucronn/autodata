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

class ProvisionOrderingTests(unittest.TestCase):
    def test_mount_and_actual_guard_precede_docker_and_failure_stops(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        p = load('host_provision')
        for guard_ok in (True,False):
            with self.subTest(guard_ok=guard_ok):
                events = []
                class Files:
                    def read(self,*args,**kwargs): return b'approved template'
                    def directory(self,*args,**kwargs): pass
                class Journal:
                    def __init__(self,a): self.value = {'status':'incomplete'}
                    def stage(self,name): events.append(('stage',name))
                    def success(self): self.value['status']='passed'
                class Runtime:
                    def validate_mount_observations(self,*args): events.append(('validated','mount'))
                    def validate_guard_tables(self,*args):
                        events.append(('validated','guard'))
                        if not guard_ok: raise ValueError('synthetic missing guard')
                op = p.Provision(Files(),{'packages':[],'data_filesystem_uuid':'a','data_device_major_minor':'8:16'}, {},[])
                def run(argv,*args,**kwargs):
                    events.append(('command',argv))
                    if 'findmnt' in argv[0]: return b'{"filesystems":[{"target":"/var/lib/autodata","uuid":"a","fstype":"ext4","options":"rw,nodev,nosuid","maj:min":"8:16"}]}'
                    if 'nft' in argv[0]: return b'{}'
                    if 'version' in argv: return b'1'
                    return b''
                # Package verification includes a pinned Compose plugin version.
                op.a['packages'] = [{'name':'docker-compose-plugin','version':'1','filename':'plugin.deb','architecture':'amd64'}]
                def verified_run(argv,*args,**kwargs):
                    if 'dpkg-query' in argv[0]: return b'docker-compose-plugin\t1\tamd64\tinstalled'
                    return run(argv,*args,**kwargs)
                original_stat = os.stat
                def binaries(path,*args,**kwargs):
                    if str(path) in ('/usr/bin/docker','/usr/sbin/nft','/usr/bin/findmnt','/usr/sbin/mkfs.ext4','/usr/bin/python3'):
                        return SimpleNamespace(st_mode=0o100755,st_uid=0)
                    return original_stat(path,*args,**kwargs)
                with patch.object(op,'observe'),patch.object(op,'device',return_value='/dev/accepted'),patch.object(op,'run',side_effect=verified_run),patch.object(p.os.path,'exists',return_value=False),patch.object(p,'inhibit_starts',return_value=nullcontext()),patch.object(p,'Journal',Journal),patch.object(p,'make_directory',side_effect=lambda path,*args: events.append(('directory',path))),patch.object(p,'write_new'),patch.object(p,'initialize_data_directories',side_effect=lambda *args: events.append(('directory',p.DATA+'/postgres'))),patch.object(p,'pristine_docker',side_effect=lambda *args,**kwargs: events.append(('validated','docker-empty'))),patch.object(p,'tighten_mount_root'),patch.object(p,'load_module',return_value=Runtime()),patch.object(p.os,'stat',side_effect=binaries):
                    if guard_ok: self.assertEqual(op.apply()['status'],'passed')
                    else:
                        with self.assertRaises(ValueError): op.apply()
                start = ('command',['/usr/bin/systemctl','start','docker.service'])
                if guard_ok:
                    self.assertLess(events.index(('validated','mount')),events.index(('directory',p.DATA+'/postgres')))
                    self.assertLess(events.index(('validated','guard')),events.index(start))
                    self.assertLess(events.index(('validated','docker-empty')),events.index(start))
                else: self.assertNotIn(start,events)
                formatting = [argv for kind,argv in events if kind == 'command' and 'mkfs.ext4' in argv[0]]
                self.assertEqual(formatting,[['/usr/sbin/mkfs.ext4','-U','a','/dev/accepted']])

class MaterializedBundleTests(unittest.TestCase):
    def test_complete_clean_bundle_is_deterministic_and_renderer_uses_installed_layout(self):
        import shutil
        from test_host_runtime import ContractTests
        builder = load('build_host_bundle'); provision = load('host_provision')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'source'; root.mkdir()
            source = HERE.parents[2]
            for name in builder.source_inventory(source):
                target = root/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source/name,target)
            subprocess.run(['git','init','-q',root],check=True)
            subprocess.run(['git','-C',root,'add','.'],check=True)
            subprocess.run(['git','-C',root,'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
            sha = subprocess.check_output(['git','-C',root,'rev-parse','HEAD']).decode().strip()
            first = Path(directory)/'first'; second = Path(directory)/'second'
            expected = builder.build(root,sha,first); actual = builder.build(root,sha,second)
            self.assertEqual(expected,actual)
            self.assertEqual((first/'inventory.json').read_bytes(),(second/'inventory.json').read_bytes())
            provision.validate_inventory(first,expected,sha)
            spec = importlib.util.spec_from_file_location('installed_runtime_test',first/'opt/autodata/bin/runtime-check.py')
            runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
            fixture = ContractTests(); fixture.setUp()
            try:
                rendered = runtime.render_bundle(fixture.manifest,fixture.config)
                self.assertEqual(set(rendered),{'compose.production.yaml','Caddyfile','nats.conf.template','seaweedfs-s3.json.template'})
                self.assertNotIn('${',rendered['compose.production.yaml'])
            finally: fixture.doCleanups()
            with self.assertRaises(FileExistsError): builder.build(root,sha,first)
            # Owner inventory acceptance cannot authorize paths outside the fixed layout.
            expected['files'][0]['path'] = '../outside'
            with self.assertRaises(ValueError): provision.validate_inventory(first,expected,sha)

class ReviewDeviceAndDaemonTests(unittest.TestCase):
    def test_uuid_collision_is_rejected_before_formatting(self):
        p = load('host_provision')
        op = p.Provision(None,{'data_filesystem_uuid':'12345678-1234-4234-8234-123456789abc'},None,[])
        calls = []
        def scan(argv,**kwargs): calls.append(argv); return b'/dev/other\n'
        with patch.object(op,'run',side_effect=scan),patch.object(p.os.path,'lexists',return_value=False):
            with self.assertRaises(ValueError): op.uuid_unused()
        self.assertFalse(any('mkfs.ext4' in arg for argv in calls for arg in argv))
        self.assertIn('--cache-file',calls[0]); self.assertIn('/dev/null',calls[0])
        with patch.object(op,'run',return_value=b''),patch.object(p.os.path,'lexists',return_value=False): op.uuid_unused()

    def test_mount_same_uuid_on_wrong_device_is_rejected(self):
        p = load('host_provision')
        a = {'data_filesystem_uuid':'12345678-1234-4234-8234-123456789abc','data_device_major_minor':'8:16'}
        op = p.Provision(None,a,None,[])
        for device in ('8:0','8:16'):
            data = json.dumps({'filesystems':[{'target':p.DATA,'uuid':a['data_filesystem_uuid'],'fstype':'ext4','options':'rw,nodev,nosuid','maj:min':device}]}).encode()
            with patch.object(op,'run',return_value=data):
                if device == '8:16': op.verify_data_mount()
                else:
                    with self.assertRaises(ValueError): op.verify_data_mount()

    @unittest.skipUnless(os.geteuid() == 0,'root-owned temporary filesystem test')
    def test_persisted_docker_containers_and_containerd_state_are_rejected(self):
        p = load('host_provision')
        with tempfile.TemporaryDirectory(dir='/root') as directory:
            root = Path(directory); docker = root/'docker'; containerd = root/'containerd'
            docker.mkdir(); containerd.mkdir()
            with patch.object(p,'DOCKER_STATE_DIRS',(str(docker),str(containerd))),patch.object(p,'DOCKER_CONFIGURATION_DIRS',()),patch.object(p,'DOCKER_UNIT_OVERRIDES',()):
                with p.Pins() as pins: p.pristine_docker(pins)
                container = docker/'containers'; container.mkdir(); (container/'restartable').write_text('synthetic stopped container')
                with p.Pins() as pins:
                    with self.assertRaises(ValueError): p.pristine_docker(pins)
                (container/'restartable').unlink(); container.rmdir(); (containerd/'metadata.db').write_text('synthetic metadata')
                with p.Pins() as pins:
                    with self.assertRaises(ValueError): p.pristine_docker(pins)

    def test_mismatched_mount_descriptor_never_chmods(self):
        from types import SimpleNamespace
        p = load('host_provision')
        with patch.object(p.os,'open',return_value=123),patch.object(p.os,'close'),patch.object(p.os,'fstat',return_value=SimpleNamespace(st_uid=0,st_gid=0,st_mode=0o40755,st_dev=os.makedev(8,0))),patch.object(p.os,'fchmod') as chmod:
            with self.assertRaises(ValueError): p.tighten_mount_root('8:16')
            chmod.assert_not_called()

class BoundDataDirectoryTests(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0,'root-owned temporary filesystem test')
    def test_directory_creation_stays_on_the_pinned_accepted_filesystem(self):
        p = load('host_provision')
        with tempfile.TemporaryDirectory(dir='/root') as directory,patch.object(p,'DATA',directory):
            value = os.stat(directory); accepted = str(os.major(value.st_dev))+':'+str(os.minor(value.st_dev))
            with p.Pins() as pins:
                with self.assertRaises(ValueError): p.initialize_data_directories(pins,'999:999')
                self.assertEqual(os.listdir(directory),[])
                p.initialize_data_directories(pins,accepted)
            for name,uid in (('postgres',999),('caddy',0),('nats',1000),('seaweedfs',1000),('operations',0)):
                actual = os.stat(Path(directory)/name)
                self.assertEqual((actual.st_uid,actual.st_gid,actual.st_mode & 0o777,actual.st_dev),(uid,uid,0o700,value.st_dev))
