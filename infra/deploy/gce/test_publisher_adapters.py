"""Offline authenticated-v3 boundary tests. No provider credentials or network."""
import hashlib
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

HERE = Path(__file__).resolve().parent


def load():
    path = HERE / 'publisher_adapters.py'
    if not path.exists(): return None
    spec = importlib.util.spec_from_file_location('publisher_adapters', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_fixture():
    return {'protocol_version': 3, 'environment': 'staging', 'repository': 'lucronn/autodata',
            'repository_id': '123456', 'repository_owner_id': '987654', 'run_id': '42', 'run_attempt': 2,
            'workflow_ref': 'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',
            'workflow_sha': 'd' * 40, 'source_sha': 'a' * 40, 'service_config_sha256': 'b' * 64,
            'protected_environment': 'workshop-staging-publish', 'activation_sha256': 'c' * 64,
            'toolchain_sha256': 'e' * 64, 'trust_policy_sha256': 'f' * 64}


def run_fixture(context):
    return {'id': int(context['run_id']), 'run_attempt': context['run_attempt'], 'event': 'workflow_dispatch',
            'head_branch': 'master', 'head_sha': context['workflow_sha'], 'path': '.github/workflows/release-workshop.yml',
            'status': 'completed', 'conclusion': 'success',
            'repository': {'id': int(context['repository_id']), 'full_name': context['repository'],
                           'owner': {'id': int(context['repository_owner_id'])}},
            'run_started_at': '2026-11-03T12:00:00Z', 'updated_at': '2026-11-03T12:05:00Z'}


class BoundaryTests(unittest.TestCase):
    def setUp(self): self.p = load()

    def needed(self):
        self.assertIsNotNone(self.p, 'authenticated adapter library is missing')
        return self.p

    def test_strict_wire_rejects_duplicates_depth_and_nonfinite(self):
        p = self.needed()
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[' * 33 + b'0' + b']' * 33):
            with self.subTest(data=data[:20]), self.assertRaises(p.AdapterError): p.strict_json(data)
        self.assertEqual(p.strict_json(b'{"x":true}'), {'x': True})

    def test_outer_envelope_returns_original_inner_and_denies_aliases(self):
        p = self.needed()
        inner = b'PK inner bytes'
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', compression=method) as archive: archive.writestr('release.zip', inner)
            data = out.getvalue()
            self.assertEqual(p.decode_actions_outer_zip(data, hashlib.sha256(inner).hexdigest(), len(inner)), inner)
            self.assertNotEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256(inner).hexdigest())
            for bad in (b'prefix' + data, data + b'trailer', data.replace(b'release.zip', b'release.zap')):
                with self.assertRaises(p.AdapterError): p.decode_actions_outer_zip(bad, hashlib.sha256(inner).hexdigest(), len(inner))

    def test_context_separates_workflow_source_and_attempt(self):
        p = self.needed()
        context = context_fixture()
        self.assertEqual(p.validate_context(context), context)
        run = run_fixture(context)
        p.validate_run(run, context, completed=True)
        for key, value in [('head_sha', context['source_sha']), ('run_attempt', True), ('event', 'push')]:
            with self.assertRaises(p.AdapterError): p.validate_run(dict(run, **{key: value}), context, completed=True)

    def test_url_policy_rejects_ambiguous_and_private_destinations(self):
        p = self.needed()
        for url in ('http://api.github.com/x', 'https://api.github.com:444/x', 'https://user@api.github.com/x',
                    'https://127.0.0.1/x', 'https://api.github.com/x#frag', 'https://api.github.com\\@evil.example/x'):
            with self.assertRaises(p.AdapterError): p.validate_url(url, {'api.github.com'})
        self.assertEqual(p.validate_url('https://api.github.com/x', {'api.github.com'}).hostname, 'api.github.com')

    def test_missing_owner_policy_fails_before_dependencies(self):
        p = self.needed()
        calls = []
        with self.assertRaises(p.AdapterError):
            p.build_authenticated_candidate({}, {}, context_fixture(), {}, dependencies=lambda: calls.append(1))
        self.assertEqual(calls, [])


if __name__ == '__main__': unittest.main()

class ExecutionTests(unittest.TestCase):
    def setUp(self): self.p = load()

    def test_process_bounds_and_private_output_reject_links(self):
        import os
        import time
        with self.p.private_workspace() as directory:
            path = self.p.private_write(directory, 'output.json', b'{}')
            self.assertEqual(self.p.private_read(directory, path.name, 10), b'{}')
            os.link(path, directory / 'alias')
            with self.assertRaises(self.p.AdapterError): self.p.private_read(directory, path.name, 10)
            code, out, err = self.p.bounded_process(['/usr/bin/python3', '-c', 'print("ok")'], cwd=directory,
                                                   deadline=time.monotonic() + 3)
            self.assertEqual((code, out, err), (0, b'ok\n', b''))
            with self.assertRaises(self.p.AdapterError):
                self.p.bounded_process(['/usr/bin/python3', '-c', 'print("x"*2000)'], cwd=directory,
                                       deadline=time.monotonic() + 3, maximum=100)
            with self.assertRaises(self.p.AdapterError):
                self.p.bounded_process(['/usr/bin/python3', '-c', 'import time; time.sleep(10)'], cwd=directory,
                                       deadline=time.monotonic() + .1)

    def test_build_argv_pins_migration_base_and_source_epoch(self):
        for role in ('api', 'ingestion', 'migration'):
            self.assertTrue(hasattr(self.p, 'build_argv'), 'fixed build argv missing')
            argv = self.p.build_argv(role, '/usr/bin/docker', '/work/source', 'staging.example/repo',
                                     context_fixture(), 123, 'docker.io/library/postgres@sha256:' + 'b' * 64,
                                     'workshop-42-2')
            self.assertIn('--platform=linux/amd64', argv)
            self.assertIn('SOURCE_DATE_EPOCH=123', argv)
            if role == 'migration':
                position = argv.index('--file')
                self.assertEqual(argv[position-2:position], ['--build-arg', 'POSTGRES_IMAGE=docker.io/library/postgres@sha256:' + 'b' * 64])
            self.assertIn('--provenance=mode=max', argv)
            self.assertIn('--sbom=true', argv)

    def test_registry_verifies_actual_index_manifest_and_config_chain(self):
        p = self.p
        self.assertTrue(hasattr(p, 'verify_registry_image'), 'registry verifier missing')
        config = p.canonical({'architecture': 'amd64', 'os': 'linux'})
        manifest = p.canonical({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                               'config': {'digest': 'sha256:' + p.digest(config), 'size': len(config)}, 'layers': []})
        objects = {'sha256:' + p.digest(config): config, 'sha256:' + p.digest(manifest): manifest}
        result = p.verify_registry_image('registry.example/repo/api@sha256:' + p.digest(manifest),
                                         lambda reference, kind, value: objects[value])
        self.assertEqual(result['image_id'], 'sha256:' + p.digest(config))
        bad = dict(objects); bad['sha256:' + p.digest(config)] = p.canonical({'architecture': 'arm64', 'os': 'linux'})
        with self.assertRaises(p.AdapterError):
            p.verify_registry_image('registry.example/repo/api@sha256:' + p.digest(manifest), lambda r,k,v: bad[v])

class PhaseTests(unittest.TestCase):
    def setUp(self):
        import test_host_runtime
        fixture = test_host_runtime.ContractTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.p = load(); self.config = fixture.config; self.manifest = fixture.manifest
        self.context = context_fixture(); self.context['service_config_sha256'] = self.p.rt.sha256(self.config)
        self.build_input = {key: self.manifest[key] for key in ('source_sha', 'platform', 'service_config_sha256',
                            'migrations', 'toolchain', 'secret_versions', 'rollback_source_sha')}
        self.build_input.update(protocol_version=3, source_epoch=123,
                                dependency_images={k: self.manifest['images'][k] for k in self.p.UPSTREAM},
                                rollback_manifest_sha256=None, toolchain_policy_sha256='e'*64, upstream_policy_sha256='1'*64)

    def test_candidate_projection_has_no_forecast_owned_images(self):
        self.assertTrue(hasattr(self.p, 'validate_build_input'), 'candidate projection missing')
        self.p.validate_build_input(self.build_input, self.config, self.context, rollback_manifest=None)
        for change in ({'owned_images': {}}, {'source_epoch': True}, {'upstream_policy_sha256': None}):
            with self.assertRaises(self.p.AdapterError):
                self.p.validate_build_input(dict(self.build_input, **change), self.config, self.context, rollback_manifest=None)

    def test_rollback_requires_separate_exact_previous_object(self):
        import copy
        self.assertTrue(hasattr(self.p, 'validate_build_input'), 'candidate projection missing')
        old = copy.deepcopy(self.manifest); old['source_sha'] = '9'*40; old['rollback_source_sha'] = '8'*40
        build_input = dict(self.build_input, rollback_source_sha=old['source_sha'], rollback_manifest_sha256=self.p.rt.sha256(old))
        self.p.validate_build_input(build_input, self.config, self.context, rollback_manifest=old)
        for rollback in (None, dict(old, platform='linux/arm64'), dict(old, source_sha='7'*40)):
            with self.assertRaises(self.p.AdapterError):
                self.p.validate_build_input(build_input, self.config, self.context, rollback_manifest=rollback)
        with self.assertRaises(self.p.AdapterError):
            self.p.validate_build_input(self.build_input, self.config, self.context, rollback_manifest=old)

    def test_upload_statement_requires_exact_verified_attempt_identity(self):
        self.assertTrue(hasattr(self.p, 'validate_upload_statement'), 'postupload signed binding missing')
        core = {'run_id': '42', 'run_attempt': 2, 'artifact_id': '91', 'artifact_digest': 'sha256:'+'b'*64,
                'artifact_bytes': 400, 'workflow_sha': 'd'*40}
        evidence = {'control_workflow_sha': 'd'*40, 'run_id': '42', 'run_attempt': 2,
                    'returned_artifact_id': '91', 'returned_digest': core['artifact_digest']}
        statement = {'_type': 'https://in-toto.io/Statement/v1', 'subject': [{'name': 'github-actions-artifact:91', 'digest': {'sha256':'b'*64}}],
                     'predicateType': 'https://autodata.invalid/attestations/workshop-upload/v3',
                     'predicate': {'binding_core':core, 'upload_evidence':evidence}}
        identity = {'run_invocation_uri': 'https://github.com/lucronn/autodata/actions/runs/42/attempts/1',
                    'workflow_sha':'d'*40, 'workflow_ref': self.context['workflow_ref']}
        with self.assertRaises(self.p.AdapterError): self.p.validate_upload_statement(statement, core, identity, self.context)
        identity['run_invocation_uri'] = identity['run_invocation_uri'][:-1] + '2'
        self.p.validate_upload_statement(statement, core, identity, self.context)
        wrong = dict(core, artifact_id='90')
        with self.assertRaises(self.p.AdapterError): self.p.validate_upload_statement(statement, wrong, identity, self.context)

class OrchestrationTests(PhaseTests):
    def policy(self):
        return dict({key: self.context[key] for key in ('activation_sha256','repository_id','repository_owner_id','workflow_sha','toolchain_sha256','trust_policy_sha256')},
                    tools={'docker':{'path':'/usr/bin/docker','sha256':'2'*64,'version':'local-test-fixture'}}, storage_origins=['storage.example'],
                    upstream_policy_sha256='1'*64, approval_keys={self.p.digest(b'TEST PUBLIC KEY'):'TEST PUBLIC KEY'}, approvers=['owner'],
                    registry=self.config['resources']['artifact_repository'], evidence_layout='https://evidence.example')

    def test_candidate_calls_each_build_once_and_returns_only_unaccepted(self):
        p = self.p
        class Dependencies:
            def __init__(this): this.calls=[]
            def prepare(this, *args): this.calls.append('prepare')
            def now(this):
                from datetime import datetime, timezone
                return datetime(2026,11,3,12,tzinfo=timezone.utc)
            def run(this, context, completed): return run_fixture(context) | {'status':'in_progress','conclusion':None}
            def checkout(this, source, epoch): this.calls.append(('checkout',source,epoch))
            def build(this, role, build_input, context):
                this.calls.append(('build',role))
                return {'reference': self.manifest['images'][role]['reference'], 'image_id':self.manifest['images'][role]['image_id'], 'platform':'linux/amd64'}
            def verify_image(this, image): this.calls.append(('verify',image['reference']))
            def create_image_evidence(this, role, image, build_input, context):
                return {key:self.manifest['images'][role][key] for key in ('provenance_uri','sbom_uri')}
            def sign_candidate(this, record, context): this.record=record; return self.config['resources']['artifact_repository']+'/candidate@sha256:'+p.digest(p.canonical(record))
            def cleanup(this): this.calls.append('cleanup')
        dependencies=Dependencies()
        result=p.build_authenticated_candidate(self.build_input,self.config,self.context,self.policy(),dependencies=dependencies)
        self.assertEqual(result['status'],'candidate_built_unaccepted')
        self.assertFalse(result['deployment_authorized'])
        self.assertEqual([call for call in dependencies.calls if type(call) is tuple and call[0]=='build'], [('build','api'),('build','ingestion'),('build','migration')])
        self.assertEqual(dependencies.calls[-1],'cleanup')
        self.assertNotIn('manifest_sha256', dependencies.record)

    def test_finalization_rejects_missing_signed_approval_before_any_call(self):
        p=self.p
        self.assertTrue(hasattr(p,'finalize_authenticated_publication'),'finalizer missing')
        context=self.context | {'manifest_sha256':p.rt.sha256(self.manifest), 'candidate_digest':self.policy()['registry']+'/candidate@sha256:'+'4'*64,
                                'candidate_run_id':'41','candidate_run_attempt':1}
        calls=[]
        with self.assertRaises(p.AdapterError):
            p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],{},context,self.policy(),dependencies=lambda:calls.append(1))
        self.assertEqual(calls,[])

class VerificationTests(unittest.TestCase):
    def setUp(self): self.p=load()

    def test_verification_and_host_have_no_default_authority(self):
        p=self.p
        for name in ('verify_authenticated_publication','run_fixed_iap_check'):
            self.assertTrue(hasattr(p,name), name+' missing')
            calls=[]
            with self.assertRaises(p.AdapterError):
                getattr(p,name)({}, {}, {}, context_fixture(), {}, dependencies=lambda:calls.append(1))
            self.assertEqual(calls,[])

    def test_fresh_upload_contract_rejects_mismatch_and_invented_evidence(self):
        p=self.p; context=context_fixture(); archive=b'inner bytes'; policy={'toolkit_lock_sha256':'a'*64,'runtime_service_origin':'https://runtime.example'}
        upload={'protocol_version':3,'artifact_id':'91','digest':'sha256:'+'b'*64,'digestMismatch':False,
                'runtime_service_origin':policy['runtime_service_origin'],'upload_request_sha256':p.digest(p.canonical(p.upload_request(archive,context))),
                'upload_started_at':'2026-11-03T12:00:00Z','upload_finished_at':'2026-11-03T12:00:01Z',
                'toolkit_lock_sha256':'a'*64,'control_workflow_sha':context['workflow_sha'],'run_id':'42','run_attempt':2}
        p.validate_upload_observation(upload,archive,context,policy)
        for change in ({'digestMismatch':True},{'digestMismatch':None},{'digestMismatch':0},{'run_attempt':1}, {'artifact_id':'latest'},{'upload_request_sha256':'c'*64}, {'toolkit_lock_sha256':None}, {'toolkit_lock_sha256':''}, {'toolkit_lock_sha256':True}, {'toolkit_lock_sha256':'A'*64}, {'runtime_service_origin':None}, {'runtime_service_origin':''}, {'runtime_service_origin':False}, {'runtime_service_origin':'https://runtime.example/'}, {'runtime_service_origin':'https://[::'}):
            with self.subTest(change=change),self.assertRaises(p.AdapterError): p.validate_upload_observation(upload|change,archive,context,policy)

    def test_redirect_keeps_bearer_off_storage_request_and_forbids_second_hop(self):
        p=self.p
        calls=[]
        class HTTP:
            def get(this,url,**kwargs):
                calls.append((url,kwargs))
                return (302,'https://storage.example/blob?signature=secret') if len(calls)==1 else (200,b'outer')
        self.assertEqual(p.download_actions_outer(HTTP(),'91','REST-TOKEN',['storage.example'],deadline=123),b'outer')
        self.assertEqual(calls[0][1]['token'],'REST-TOKEN'); self.assertNotIn('token',calls[1][1])
        self.assertTrue(calls[1][1]['signed'])

class FullFlowTests(OrchestrationTests):
    def dependencies(self, rollback=None):
        import copy
        import hmac
        from datetime import datetime, timezone
        p=self.p; context=self.context; manifest=self.manifest; config=self.config; policy=self.policy()
        context=context|{'manifest_sha256':p.rt.sha256(manifest),'candidate_digest':policy['registry']+'/candidate@sha256:'+'4'*64,'candidate_run_id':'41','candidate_run_attempt':1}
        policy=policy|{'toolkit_lock_sha256':'5'*64,'runtime_service_origin':'https://runtime.example'}
        candidate_context={key:context[key] for key in p.CONTEXT_FIELDS}|{'run_id':'41','run_attempt':1}
        candidate={'protocol_version':3,'context':candidate_context,'build_input_sha256':p.digest(p.canonical(self.build_input)),
                   'owned_images':{role:manifest['images'][role]|{'platform':'linux/amd64'} for role in p.OWNED},
                   **{key:self.build_input[key] for key in ('dependency_images','migrations','toolchain','secret_versions','rollback_source_sha','rollback_manifest_sha256')},
                   'created_at':'2026-11-03T11:00:00Z'}
        approval={key:context[key] for key in ('repository_id','repository_owner_id','environment','source_sha','service_config_sha256','manifest_sha256',
                                             'candidate_digest','candidate_run_id','candidate_run_attempt','workflow_sha','trust_policy_sha256')}
        approval.update(protocol_version=3,rollback_manifest_sha256=candidate['rollback_manifest_sha256'],build_input_sha256=candidate['build_input_sha256'],
                        approved_by='owner',issued_at='2026-11-03T11:30:00Z',expires_at='2026-11-03T13:00:00Z')
        # Explicit test-only cryptographic fixture. The HMAC authenticates local
        # fixture statements/identities, not GitHub, Fulcio or an actual upload.
        fixture_key=b'local-test-root-not-a-provider-key'
        signed_approval={'approval_bytes':p.canonical(approval),'key_sha256':next(iter(policy['approval_keys'])),
                         'signature_bytes':hmac.digest(fixture_key,p.canonical(approval),'sha256')}
        class Dependencies:
            def __init__(this): this.statements={}; this.calls=[]; this.completed=False
            def prepare(this,*args): this.calls.append('prepare')
            def cleanup(this): this.calls.append('cleanup')
            def now(this): return datetime(2026,11,3,12,5,tzinfo=timezone.utc)
            def run(this,ctx,completed):
                return run_fixture(ctx) if completed else run_fixture(ctx)|{'status':'in_progress','conclusion':None}
            def load_candidate(this,*args): return copy.deepcopy(candidate)
            def load_approval(this,*args): return signed_approval
            def verify_approval(this,envelope,policy):
                p.require(hmac.compare_digest(hmac.digest(fixture_key,envelope['approval_bytes'],'sha256'),envelope['signature_bytes']))
            def verify_image(this,*args): this.calls.append('verify_image')
            def verify_image_evidence(this,*args): this.calls.append('verify_image_evidence')
            def store(this,statement,ctx,prefix):
                data=p.canonical(statement); identity={key:ctx[key] for key in ('workflow_sha','workflow_ref')}
                identity['run_invocation_uri']='https://github.com/lucronn/autodata/actions/runs/'+ctx['run_id']+'/attempts/'+str(ctx['run_attempt'])
                signature=hmac.digest(fixture_key,p.canonical({'statement':statement,'identity':identity}),'sha256')
                uri='https://evidence.example/'+prefix+'@sha256:'+p.digest(data)
                this.statements[uri]=(data,identity,signature)
                return {prefix+'_uri':uri,prefix+'_sha256':p.digest(data),prefix+'_bundle_sha256':p.digest(signature)}
            def sign_source(this,statement,ctx): return this.store(statement,ctx,'source_statement')
            def sign_upload(this,statement,ctx): return this.store(statement,ctx,'upload_statement')
            def verify_signed(this,uri,expected,expected_bundle,ctx):
                data,identity,signature=this.statements[uri]
                p.require(p.digest(signature)==expected_bundle and p.digest(data)==expected)
                p.require(hmac.compare_digest(signature,hmac.digest(fixture_key,p.canonical({'statement':p.strict_json(data),'identity':identity}),'sha256')))
                return data,identity
            def upload(this,archive,ctx):
                this.calls.append('upload'); this.inner=archive
                buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as output: output.writestr('release.zip',archive)
                this.outer=buffer.getvalue()
                return {'protocol_version':3,'artifact_id':'91','digest':'sha256:'+p.digest(this.outer),'digestMismatch':False,
                        'runtime_service_origin':policy['runtime_service_origin'],'upload_request_sha256':p.digest(p.canonical(p.upload_request(archive,ctx))),
                        'upload_started_at':'2026-11-03T12:00:00Z','upload_finished_at':'2026-11-03T12:00:01Z',
                        'toolkit_lock_sha256':policy['toolkit_lock_sha256'],'control_workflow_sha':ctx['workflow_sha'],'run_id':ctx['run_id'],'run_attempt':ctx['run_attempt']}
            def artifact_metadata(this,artifact_id):
                return {'id':int(artifact_id),'name':p.artifact_name(context),'expired':False,'digest':'sha256:'+p.digest(this.outer),
                        'size_in_bytes':len(this.outer),'workflow_run':{'id':int(context['run_id']),'repository_id':int(context['repository_id'])},
                        'created_at':'2026-11-03T12:00:00Z','expires_at':'2026-11-10T12:00:00Z'}
            def download(this,artifact_id): return this.outer
        return Dependencies(), context, policy, signed_approval

    def test_finalize_and_independent_verify_use_same_bytes_without_build(self):
        p=self.p; deps,context,policy,approval=self.dependencies()
        result=p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],approval,context,policy,dependencies=deps)
        self.assertEqual(result['status'],'uploaded_unaccepted'); self.assertFalse(result['provenance_authenticated'])
        binding=result['binding']
        verified=p.verify_authenticated_publication(self.manifest,self.config,binding,context,policy,dependencies=deps)
        self.assertEqual(verified['status'],'publication_verified'); self.assertFalse(verified['deployment_authorized'])
        self.assertFalse(hasattr(deps,'build'))
        # Re-sign with a valid local older-attempt identity. Crypto validation
        # succeeds; the exact originating-attempt check must reject it.
        uri=binding['upload_statement_uri']; data,identity,signature=deps.statements[uri]
        older=deps.store(p.strict_json(data),context|{'run_attempt':1},'upload_statement')
        old_binding=binding|older
        deps.verify_signed(older['upload_statement_uri'],older['upload_statement_sha256'],older['upload_statement_bundle_sha256'],context)
        with self.assertRaises(p.AdapterError): p.verify_authenticated_publication(self.manifest,self.config,old_binding,context,policy,dependencies=deps)
        deps.statements[uri]=(data,identity,signature)
        self.assertEqual(p.verify_authenticated_publication(self.manifest,self.config,binding,context,policy,dependencies=deps)['status'],'publication_verified')
        for changed in (binding|{'artifact_id':'90'},binding|{'artifact_bytes':binding['artifact_bytes']+1},binding|{'artifact_digest':'sha256:'+'0'*64}):
            with self.assertRaises(p.AdapterError): p.verify_authenticated_publication(self.manifest,self.config,changed,context,policy,dependencies=deps)

    def test_previous_manifest_survives_finalize_and_verify(self):
        import copy
        p=self.p; previous=copy.deepcopy(self.manifest); previous['source_sha']='9'*40; previous['rollback_source_sha']='8'*40
        self.manifest['rollback_source_sha']=previous['source_sha']
        self.build_input.update(rollback_source_sha=previous['source_sha'],rollback_manifest_sha256=p.rt.sha256(previous))
        deps,context,policy,approval=self.dependencies(previous)
        result=p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],approval,context,policy,rollback_manifest=previous,dependencies=deps)
        self.assertEqual(result['binding']['rollback_manifest_sha256'],p.rt.sha256(previous))
        verified=p.verify_authenticated_publication(self.manifest,self.config,result['binding'],context,policy,rollback_manifest=previous,dependencies=deps)
        self.assertEqual(verified['status'],'publication_verified')
        with self.assertRaises(p.AdapterError):
            p.verify_authenticated_publication(self.manifest,self.config,result['binding'],context,policy,dependencies=deps)

    def tracked_operations(self, dependencies):
        calls=[]
        for name in vars(type(dependencies)):
            if name.startswith('_') or not callable(getattr(dependencies,name,None)): continue
            original=getattr(dependencies,name)
            def track(*args,_name=name,_original=original,**kwargs):
                calls.append(_name)
                return _original(*args,**kwargs)
            setattr(dependencies,name,track)
        return calls

    def test_upload_owner_pins_fail_before_all_finalize_and_verify_callbacks(self):
        p=self.p; deps,context,policy,approval=self.dependencies()
        binding=p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],approval,context,policy,dependencies=deps)['binding']
        self.assertEqual(p.verify_authenticated_publication(self.manifest,self.config,binding,context,policy,dependencies=deps)['status'],'publication_verified')
        calls=self.tracked_operations(deps)
        cases=[('missing toolkit',{'toolkit_lock_sha256'}),('missing origin',{'runtime_service_origin'}),
               ('missing both',{'toolkit_lock_sha256','runtime_service_origin'})]
        for name,value in [('null toolkit',None),('empty toolkit',''),('bool toolkit',False),('short toolkit','a'*63),('upper toolkit','A'*64)]:
            cases.append((name,{'toolkit_lock_sha256':value}))
        for value in (None,'',False,'http://runtime.example','https://*.example','https://user@runtime.example',
                      'https://runtime.example/path','https://runtime.example/','https://runtime.example?token=x',
                      'https://runtime.example#fragment','https://runtime.example:444','https://runtime.example:443',
                      'https://127.0.0.1','https://Runtime.Example','https://runtime.example\n'):
            cases.append(('origin '+repr(value),{'runtime_service_origin':value}))
        for name,change in cases:
            bad=dict(policy)
            if type(change) is set:
                for key in change: bad.pop(key)
            else: bad.update(change)
            for operation in ('finalize','verify'):
                calls.clear()
                with self.subTest(name=name,operation=operation):
                    with self.assertRaises(p.AdapterError):
                        if operation=='finalize':
                            p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],approval,context,bad,dependencies=deps)
                        else: p.verify_authenticated_publication(self.manifest,self.config,binding,context,bad,dependencies=deps)
                    self.assertEqual(calls,[],'invalid owner inputs reached dependency operations')

    def test_null_upload_observation_cannot_authorize_missing_owner_pins(self):
        p=self.p; deps,context,policy,approval=self.dependencies()
        original=deps.upload
        def null_upload(archive,ctx):
            return original(archive,ctx)|{'toolkit_lock_sha256':None,'runtime_service_origin':None}
        deps.upload=null_upload
        bad={key:value for key,value in policy.items() if key not in ('toolkit_lock_sha256','runtime_service_origin')}
        with self.assertRaises(p.AdapterError):
            p.finalize_authenticated_publication(self.manifest,self.config,context['candidate_digest'],approval,context,bad,dependencies=deps)


class ToolPinTests(unittest.TestCase):
    def test_owner_approval_verifier_requires_pinned_binary_key_and_real_signature_result(self):
        import os
        import subprocess
        import tempfile
        p=load()
        self.assertTrue(hasattr(p,'PinnedCosignApproval'),'pinned detached verifier missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(['/usr/bin/openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(root/'private.pem')],check=True,capture_output=True)
            subprocess.run(['/usr/bin/openssl','pkey','-in',str(root/'private.pem'),'-pubout','-out',str(root/'public.pem')],check=True,capture_output=True)
            data=b'{"approved":"local fixture"}'
            (root/'approval').write_bytes(data)
            subprocess.run(['/usr/bin/openssl','dgst','-sha256','-sign',str(root/'private.pem'),'-out',str(root/'signature'),str(root/'approval')],check=True,capture_output=True)
            signature=(root/'signature').read_bytes(); key=(root/'public.pem').read_bytes()
            key_hash=p.digest(key)
            # A local executable fixture implements the reviewed verify-blob
            # argv contract and delegates the actual signature check to OpenSSL.
            tool=root/'cosign-fixture'
            tool.write_text("""#!/usr/bin/python3
import subprocess,sys,json
a=sys.argv
if a[1]=='version':
    print(json.dumps({'gitVersion':'local-test-fixture'}))
    sys.exit(0)
assert '--offline' in a and '--insecure-ignore-tlog' in a
r=subprocess.run(['/usr/bin/openssl','dgst','-sha256','-verify',a[a.index('--key')+1],'-signature',a[a.index('--signature')+1],a[-1]],capture_output=True)
sys.exit(r.returncode)
""")
            tool.chmod(0o700)
            verifier=p.PinnedCosignApproval({'path':str(tool),'sha256':p.digest(tool.read_bytes()),'version':'local-test-fixture'},
                                           {key_hash:key})
            envelope={'approval_bytes':data,'signature_bytes':signature,'key_sha256':key_hash}
            verifier.verify(envelope)
            for changed in (envelope|{'approval_bytes':data+b' '},envelope|{'key_sha256':'f'*64},envelope|{'signature_bytes':b'tampered'}):
                with self.assertRaises(p.AdapterError): verifier.verify(changed)
            tool.write_text('#!/bin/sh\nexit 0\n')
            with self.assertRaises(p.AdapterError): verifier.verify(envelope)

class AdversarialWireTests(unittest.TestCase):
    def setUp(self): self.p=load()

    def test_descriptor_with_and_without_signature_and_illegal_metadata(self):
        import struct
        p=self.p; inner=b'inner'*200
        class Unseekable(io.BytesIO):
            def seekable(self): return False
            def seek(self,*args): raise io.UnsupportedOperation()
        output=Unseekable()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive: archive.writestr('release.zip',inner)
        data=output.getvalue()
        self.assertEqual(p.decode_actions_outer_zip(data,p.digest(inner),len(inner)),inner)
        position=data.index(b'PK\x07\x08'); no_signature=bytearray(data[:position]+data[position+4:])
        offset=struct.unpack_from('<I',no_signature,len(no_signature)-6)[0]
        struct.pack_into('<I',no_signature,len(no_signature)-6,offset-4)
        self.assertEqual(p.decode_actions_outer_zip(bytes(no_signature),p.digest(inner),len(inner)),inner)
        bad=bytearray(data); central=bad.index(b'PK\x01\x02')
        struct.pack_into('<H',bad,central+4,(3<<8)|20)
        struct.pack_into('<I',bad,central+38,0o120777<<16)
        with self.assertRaises(p.AdapterError): p.decode_actions_outer_zip(bytes(bad),p.digest(inner),len(inner))
        for changed in (data[:-1], data[:50]+bytes([data[50]^1])+data[51:]):
            with self.assertRaises(p.AdapterError): p.decode_actions_outer_zip(changed,p.digest(inner),len(inner))

    def test_private_dns_blocks_before_connect(self):
        p=self.p; calls=[]
        transport=p.PinnedHTTPS('/etc/ssl/certs/ca-certificates.crt',lambda host,deadline:['169.254.169.254'],
                               connect_factory=lambda *args,**kwargs:calls.append(args))
        import time
        with self.assertRaises(p.AdapterError):
            transport.get('https://api.github.com/x',origins={'api.github.com'},deadline=time.monotonic()+1,maximum=100)
        self.assertEqual(calls,[])

    def test_provider_exception_redaction(self):
        p=self.p
        @p._redacted_boundary
        def secret_failure(): raise RuntimeError('token=SECRET signed-url?private=SECRET')
        with self.assertRaises(p.AdapterError) as error: secret_failure()
        self.assertEqual(str(error.exception),'operation_failed')

class PrivateDirectoryTests(unittest.TestCase):
    def test_private_directory_rejects_symlink_parent_and_world_access(self):
        import os
        import tempfile
        p=load()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); parent=root/'private'; parent.mkdir(mode=0o700)
            p.private_write(parent,'data',b'bytes')
            alias=root/'alias'; alias.symlink_to(parent,target_is_directory=True)
            with self.assertRaises((p.AdapterError,OSError)): p.private_read(alias,'data',100)
            parent.chmod(0o755)
            with self.assertRaises((p.AdapterError,OSError)): p.private_read(parent,'data',100)

    def test_fifo_private_output_is_rejected_without_waiting_for_writer(self):
        import os
        import signal
        import subprocess
        import sys
        import tempfile
        probe='''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import publisher_adapters as p
parent=Path(sys.argv[2])
os.mkfifo(parent/'output',0o600)
try:
    p.private_read(parent,'output',100)
except p.AdapterError:
    print('rejected nonregular output')
else:
    raise AssertionError('FIFO accepted')
'''
        with tempfile.TemporaryDirectory() as directory:
            child=subprocess.Popen([sys.executable,'-c',probe,str(HERE),directory],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                try: out,err=child.communicate(timeout=3)
                except subprocess.TimeoutExpired: self.fail('private_read blocked while opening FIFO')
                self.assertEqual(child.returncode,0,err.decode())
                self.assertEqual(out,b'rejected nonregular output\n')
            finally:
                try: os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                child.communicate(timeout=3)

class SignalOwnershipTests(unittest.TestCase):
    def owner_probe(self, ignore_term, second_signal=False, final_wait=False):
        import os
        import signal
        import subprocess
        import sys
        import tempfile
        import time
        child_code='''import os,signal,sys,time
from pathlib import Path
assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK,set()), 'child inherited blocked SIGTERM'
if sys.argv[2]=='ignore':
    signal.signal(signal.SIGTERM,lambda *_: Path(sys.argv[1]+'.cleanup').write_text('TERM received'))
Path(sys.argv[1]).write_text(str(os.getpid()))
if sys.argv[2]=='closed': os.close(1); os.close(2)
time.sleep(30)
'''
        owner_code='''import signal,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import publisher_adapters as p
if sys.argv[3]=='closed':
    real_wait=p.subprocess.Popen.wait
    def marked_wait(child,*args,**kwargs):
        if kwargs.get('timeout',1)<=.1: Path(sys.argv[2]+'.waiting').write_text('final wait')
        return real_wait(child,*args,**kwargs)
    p.subprocess.Popen.wait=marked_wait
if sys.argv[5]=='second':
    def caller_handler(*_):
        pid=int(Path(sys.argv[2]).read_text())
        try: __import__('os').kill(pid,0)
        except ProcessLookupError: print('second signal after cleanup')
        else: raise AssertionError('caller handler ran before child reap')
    signal.signal(signal.SIGTERM,caller_handler)
previous=signal.getsignal(signal.SIGTERM)
previous_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
try:
    p.bounded_process([sys.executable,'-c',sys.argv[4],sys.argv[2],sys.argv[3]],cwd=Path(sys.argv[2]).parent,deadline=time.monotonic()+30)
except p.AdapterError as error:
    assert str(error)=='operation_cancelled',str(error)
    assert signal.getsignal(signal.SIGTERM)==previous
    assert signal.pthread_sigmask(signal.SIG_BLOCK,set())==previous_mask
    print('cancelled and restored')
else:
    raise AssertionError('cancellation not reported')
'''
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'child.pid'
            owner=subprocess.Popen([sys.executable,'-c',owner_code,str(HERE),str(marker),'closed' if final_wait else 'ignore' if ignore_term else 'normal',child_code,'second' if second_signal else 'single'],
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            child_pid=None
            try:
                deadline=time.monotonic()+3
                while not marker.exists() and time.monotonic()<deadline and owner.poll() is None: time.sleep(.01)
                self.assertTrue(marker.exists(),'owned child did not reach ready marker')
                child_pid=int(marker.read_text())
                if final_wait:
                    waiting_marker=Path(str(marker)+'.waiting')
                    deadline=time.monotonic()+3
                    while not waiting_marker.exists() and time.monotonic()<deadline and owner.poll() is None: time.sleep(.01)
                    self.assertTrue(waiting_marker.exists(),'owner did not reach bounded final wait')
                started=time.monotonic()
                os.kill(owner.pid,signal.SIGTERM)
                if second_signal:
                    cleanup_marker=Path(str(marker)+'.cleanup')
                    deadline=time.monotonic()+3
                    while not cleanup_marker.exists() and time.monotonic()<deadline and owner.poll() is None: time.sleep(.01)
                    self.assertTrue(cleanup_marker.exists(),'cleanup TERM not received by child')
                    os.kill(owner.pid,signal.SIGTERM)
                out,err=owner.communicate(timeout=6)
                if ignore_term: self.assertGreaterEqual(time.monotonic()-started,1.9,'TERM grace skipped')
                try: os.kill(child_pid,0)
                except ProcessLookupError: child_exists=False
                else: child_exists=True
                self.assertFalse(child_exists,'isolated child survived owner SIGTERM or was not reaped')
                self.assertEqual(owner.returncode,0,err.decode())
                self.assertEqual(out,(b'second signal after cleanup\n' if second_signal else b'')+b'cancelled and restored\n')
            finally:
                if child_pid is not None:
                    try: os.killpg(child_pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                try: os.killpg(owner.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                owner.communicate(timeout=3)

    def test_owner_sigterm_terminates_and_reaps_child(self): self.owner_probe(False)

    def test_owner_sigterm_kills_and_reaps_sigterm_ignoring_child(self): self.owner_probe(True)

    def test_owner_sigterm_during_final_wait(self): self.owner_probe(False,final_wait=True)

    def test_second_pending_signal_reaches_caller_only_after_cleanup(self): self.owner_probe(True,True)

    def isolated_probe(self, code):
        import os
        import signal
        import subprocess
        import sys
        import tempfile
        prefix='''import os,signal,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import publisher_adapters as p
directory=Path(sys.argv[2]); pidfile=directory/'child.pid'
previous=signal.getsignal(signal.SIGTERM)
mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
'''
        suffix='''
assert signal.getsignal(signal.SIGTERM)==previous
assert signal.pthread_sigmask(signal.SIG_BLOCK,set())==mask
if pidfile.exists():
    try: os.kill(int(pidfile.read_text()),0)
    except ProcessLookupError: pass
    else: raise AssertionError('child survived or was not reaped')
print('ok')
'''
        with tempfile.TemporaryDirectory() as directory:
            owner=subprocess.Popen([sys.executable,'-c',prefix+code+suffix,str(HERE),directory],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                out,err=owner.communicate(timeout=8)
                self.assertEqual(owner.returncode,0,err.decode())
                self.assertEqual(out,b'ok\n')
            finally:
                pidfile=Path(directory)/'child.pid'
                if pidfile.exists():
                    try: os.killpg(int(pidfile.read_text()),signal.SIGKILL)
                    except ProcessLookupError: pass
                try: os.killpg(owner.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                owner.communicate(timeout=3)

    def test_pending_sigterm_before_spawn_cancels_without_child(self):
        self.isolated_probe('''
real_signal=signal.signal
def install(sig,handler):
    result=real_signal(sig,handler)
    if handler is not previous:
        assert signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK,set())
        os.kill(os.getpid(),signal.SIGTERM)
    return result
with patch.object(signal,'signal',side_effect=install), patch.object(p.subprocess,'Popen',side_effect=AssertionError('spawn forbidden')) as spawn:
    try: p.bounded_process([sys.executable,'-c','pass'],cwd=directory,deadline=time.monotonic()+3)
    except p.AdapterError as error: assert str(error)=='operation_cancelled',str(error)
    else: raise AssertionError('pending cancellation ignored')
    assert spawn.call_count==0
''')

    def test_sigterm_during_popen_and_before_handle_assignment(self):
        for phase in ('inside','returned'):
            with self.subTest(phase=phase):
                self.isolated_probe('''
phase=PHASE
real_popen=p.subprocess.Popen
real_execute=real_popen._execute_child
def execute(instance,*args,**kwargs):
    real_execute(instance,*args,**kwargs)
    pidfile.write_text(str(instance.pid))
    if phase=='inside': os.kill(os.getpid(),signal.SIGTERM)
def spawn(*args,**kwargs):
    with patch.object(real_popen,'_execute_child',execute): child=real_popen(*args,**kwargs)
    pidfile.write_text(str(child.pid))
    if phase=='returned': os.kill(os.getpid(),signal.SIGTERM)
    return child
with patch.object(p.subprocess,'Popen',side_effect=spawn):
    try: p.bounded_process([sys.executable,'-c','import time; time.sleep(30)'],cwd=directory,deadline=time.monotonic()+3)
    except p.AdapterError as error: assert str(error)=='operation_cancelled',str(error)
    else: raise AssertionError('assignment cancellation ignored')
'''.replace('PHASE',repr(phase)))

    def test_nested_executor_rejected_without_replacing_owner(self):
        self.isolated_probe('''
real_popen=p.subprocess.Popen
def spawn(*args,**kwargs):
    handler=signal.getsignal(signal.SIGTERM)
    try: p.bounded_process([sys.executable,'-c','pass'],cwd=directory,deadline=time.monotonic()+3)
    except p.AdapterError as error: assert str(error)=='missing_dependency',str(error)
    else: raise AssertionError('nested invocation permitted')
    assert signal.getsignal(signal.SIGTERM)==handler
    return real_popen(*args,**kwargs)
with patch.object(p.subprocess,'Popen',side_effect=spawn):
    assert p.bounded_process([sys.executable,'-c','pass'],cwd=directory,deadline=time.monotonic()+3)[0]==0
''')

    def test_child_sigterm_mask_is_unblocked(self):
        import sys
        import tempfile
        import time
        p=load()
        with tempfile.TemporaryDirectory() as directory:
            result=p.bounded_process([sys.executable,'-c','import signal; assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK,set()); print("unblocked")'],cwd=Path(directory),deadline=time.monotonic()+3)
        self.assertEqual(result,(0,b'unblocked\n',b''))

    def test_cleanup_failure_is_fixed_and_restores_ownership(self):
        self.isolated_probe('''
with patch.object(p.os,'killpg',side_effect=PermissionError('sensitive cleanup detail')):
    try: p.bounded_process([sys.executable,'-c','pass'],cwd=directory,deadline=time.monotonic()+3)
    except p.AdapterError as error: assert str(error)=='cleanup_failed',str(error)
    else: raise AssertionError('cleanup failure became success')
# A fresh invocation proves ownership was cleared even after cleanup failure.
assert p.bounded_process([sys.executable,'-c','pass'],cwd=directory,deadline=time.monotonic()+3)[0]==0
''')

    def test_non_main_thread_and_blocked_sigterm_fail_before_spawn(self):
        import signal
        import tempfile
        import threading
        import time
        from unittest.mock import patch
        p=load(); errors=[]
        with tempfile.TemporaryDirectory() as directory:
            def call():
                try: p.bounded_process(['/usr/bin/python3','-c','pass'],cwd=Path(directory),deadline=time.monotonic()+1)
                except BaseException as error: errors.append(error)
            with patch.object(p.subprocess,'Popen',side_effect=AssertionError('spawn forbidden')) as spawn:
                thread=threading.Thread(target=call); thread.start(); thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(errors),1); self.assertIsInstance(errors.pop(),p.AdapterError)
                self.assertEqual(spawn.call_count,0)
                previous=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM})
                try: call()
                finally: signal.pthread_sigmask(signal.SIG_SETMASK,previous)
                self.assertEqual(len(errors),1); self.assertIsInstance(errors.pop(),p.AdapterError)
                self.assertEqual(spawn.call_count,0)

    def test_signal_handler_and_mask_restored_after_all_exit_paths(self):
        import signal
        import tempfile
        import time
        p=load(); previous=signal.getsignal(signal.SIGTERM)
        previous_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
        def caller_handler(signum,frame): raise AssertionError('unexpected signal')
        signal.signal(signal.SIGTERM,caller_handler)
        try:
            with tempfile.TemporaryDirectory() as directory:
                p.bounded_process(['/usr/bin/python3','-c','print("ok")'],cwd=Path(directory),deadline=time.monotonic()+3)
                for argv,limit,seconds in ((['/absent-publisher-test-binary'],100,3),
                                           (['/usr/bin/python3','-c','print("x"*1000)'],100,3),
                                           (['/usr/bin/python3','-c','import time; time.sleep(5)'],100,.05)):
                    with self.assertRaises((p.AdapterError,OSError)):
                        p.bounded_process(argv,cwd=Path(directory),deadline=time.monotonic()+seconds,maximum=limit)
                    self.assertIs(signal.getsignal(signal.SIGTERM),caller_handler)
                    self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK,set()),previous_mask)
        finally:
            signal.signal(signal.SIGTERM,previous)
            signal.pthread_sigmask(signal.SIG_SETMASK,previous_mask)

class StreamingRegistryTests(unittest.TestCase):
    def setUp(self): self.p = load()

    def inventory(self, layers):
        p = self.p
        config = p.canonical({'architecture': 'amd64', 'os': 'linux'})
        manifest = p.canonical({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                               'config': {'digest': 'sha256:' + p.digest(config), 'size': len(config)}, 'layers': layers})
        objects = {'sha256:' + p.digest(config): config, 'sha256:' + p.digest(manifest): manifest}
        return 'registry.example/repo/api@sha256:' + p.digest(manifest), objects

    def test_large_layer_hashes_original_file_chunks_and_closes_stream(self):
        import tempfile
        import time
        p = self.p
        with tempfile.TemporaryFile() as original:
            block = b'x' * 65536
            h = hashlib.sha256()
            for _ in range(80): original.write(block); h.update(block)
            original.seek(0)
            size = 80 * len(block); layer = 'sha256:' + h.hexdigest(); closed = []
            reference, objects = self.inventory([{'digest': layer, 'size': size}])
            def chunks():
                try:
                    while True:
                        data = original.read(65536)
                        if not data: break
                        yield data
                finally: closed.append(True)
            result = p.verify_registry_image(reference, lambda r,k,d: chunks() if d == layer else objects[d],
                                             deadline=time.monotonic() + 3)
            self.assertEqual(result['platform'], 'linux/amd64'); self.assertEqual(closed, [True])

    def test_stream_rejects_changed_truncated_overlong_empty_and_oversized_chunks(self):
        import time
        p = self.p; layer = 'sha256:' + p.digest(b'abc')
        reference, objects = self.inventory([{'digest': layer, 'size': 3}])
        for pieces in ([b'abd'], [b'ab'], [b'abcd'], [b'',b'abc'], ['abc'], [b'x' * (p.MiB + 1)]):
            closed=[]
            def chunks():
                try: yield from pieces
                finally: closed.append(True)
            with self.subTest(pieces=str(pieces)[:30]), self.assertRaises(p.AdapterError):
                p.verify_registry_image(reference, lambda r,k,d: chunks() if d == layer else objects[d], deadline=time.monotonic()+1)
            self.assertEqual(closed,[True])

    def test_byte_layer_fetch_cannot_succeed_after_total_deadline(self):
        import time
        p = self.p; layer = 'sha256:' + p.digest(b'abc')
        reference, objects = self.inventory([{'digest': layer, 'size': 3}])
        def fetch(r, k, d):
            if d == layer:
                time.sleep(.08)
                return b'abc'
            return objects[d]
        with self.assertRaisesRegex(p.AdapterError, 'operation_timed_out'):
            p.verify_registry_image(reference, fetch, deadline=time.monotonic() + .03)

    def test_stream_deadline_and_layer_aggregate_bounds_stop_before_fetch(self):
        import time
        p = self.p; layer = 'sha256:' + p.digest(b'abc')
        reference, objects = self.inventory([{'digest': layer, 'size': 3}])
        with self.assertRaises(p.AdapterError):
            p.verify_registry_image(reference, lambda r,k,d: iter([b'abc']) if d == layer else objects[d], deadline=time.monotonic()-1)
        calls=[]
        reference,objects=self.inventory([{'digest':layer,'size':1024*p.MiB+1}])
        def fetch(r,k,d): calls.append(d); return objects[d]
        with self.assertRaises(p.AdapterError): p.verify_registry_image(reference, fetch)
        self.assertEqual(len(calls),2)
        reference,objects=self.inventory([{'digest':layer,'size':1024*p.MiB}]*5)
        calls.clear()
        with self.assertRaises(p.AdapterError): p.verify_registry_image(reference, fetch)
        self.assertEqual(len(calls),2)


class RealHTTP10TransportTests(unittest.TestCase):
    def test_exact_length_eof_accepts_original_bytes_and_rejects_truncation(self):
        import http.server
        import socket
        import ssl
        import subprocess
        import tempfile
        import threading
        import time
        p = load()
        # The TLS and HTTP streams are real. Only the connect boundary maps a
        # pinned public test peer to the disposable local TLS listener.
        class TestPeer(socket.socket):
            def getpeername(self): return ('8.8.8.8', 443)
        payload = b'original-http10-bytes'
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200)
                length = len(payload) + (1 if self.path == '/truncated' else 0)
                self.send_header('Content-Length', str(length)); self.end_headers()
                self.wfile.write(payload)
        with tempfile.TemporaryDirectory() as directory:
            cert = Path(directory) / 'cert.pem'; key = Path(directory) / 'key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                            '-subj','/CN=api.github.com','-addext','subjectAltName=DNS:api.github.com',
                            '-keyout',str(key),'-out',str(cert)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); tls.load_cert_chain(cert, key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            def connect(address, timeout):
                raw = socket.create_connection(server.server_address, timeout=timeout)
                return TestPeer(fileno=raw.detach())
            transport = p.PinnedHTTPS(str(cert), lambda host, deadline: ['8.8.8.8'], connect_factory=connect)
            try:
                self.assertEqual(transport.get('https://api.github.com/exact', origins={'api.github.com'},
                                               deadline=time.monotonic()+3, maximum=100), (200, payload))
                with self.assertRaises(p.AdapterError):
                    transport.get('https://api.github.com/truncated', origins={'api.github.com'},
                                  deadline=time.monotonic()+3, maximum=100)
                with self.assertRaisesRegex(p.AdapterError, 'output_overflow'):
                    transport.get('https://api.github.com/exact', origins={'api.github.com'},
                                  deadline=time.monotonic()+3, maximum=3)
            finally:
                server.shutdown(); server.server_close(); thread.join(3)
