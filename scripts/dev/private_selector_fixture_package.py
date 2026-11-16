"""Build a fresh OFFLOADED review package. No Docker/SQL/HTTP dispatcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import private_selector_adapter_contract as c

REPO=Path(__file__).resolve().parents[2]
OFFLOADED_DEVICE=1792
EVIDENCE=Path('/home/corp/autodata-evidence')
TRANSPORT_SHA='a4fed281a6346219803a1914e3c286dc6fca80e1f423afd2793f82f4083e6c70'
ARCHIVE_SHA='4d1536d534a9327a4524b0e35cf234c83e5de4a8d18353fd6ca3b6343f7d5e74'
PACKAGE='/home/corp/autodata-candidate/private-initial-selector-a82b31d-20261115'

BOOTSTRAP_DEFAULTS={'CGO_ENABLED': '0', 'GOMODCACHE': '/opt/go-module-cache', 'GOTOOLCHAIN': 'local'}

def sha(data):return hashlib.sha256(data).hexdigest()


def environment(names,run):
    values={name:'' for name in names}
    overrides={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8',
        'PYTHONPATH':'/app/workers/ingestion-python/src:/app/packages/contracts/python',
        'PYTHONDONTWRITEBYTECODE':'1','AUTODATA_COMMERCE_MODE':'read_only',
        'AUTODATA_COMMERCE_READ_ONLY_MODE':'stripe_test','AUTODATA_ENV':'production',
        'AUTODATA_PUBLIC_ORIGIN':'https://autodata.cars.tk','AUTODATA_STRIPE_ACCOUNT_ID':'acct_fixture',
        'AUTODATA_STRIPE_PRICE_ID':'price_fixture','AUTODATA_INGESTION_INTERNAL_TOKEN':'fixture-internal',
        'AUTODATA_INGESTION_HTTP_ADDR':'127.0.0.1:3031','AUTODATA_DB_ADDRESS':'postgres:5432',
        'AUTODATA_POSTGRES_DB':'lifecycle_test_'+run,'AUTODATA_POSTGRES_USER':'lifecycle_test',
        'AUTODATA_POSTGRES_PASSWORD':'lifecycle_test_only','AUTODATA_S3_ADDRESS':'minio:9000',
        'AUTODATA_S3_ENDPOINT':'minio:9000','AUTODATA_S3_ACCESS_KEY':'fixture','AUTODATA_S3_SECRET_KEY':'fixture',
        'AUTODATA_S3_SECURE':'false','AUTODATA_SOURCE_BUCKET':'autodata-selector-fixture-'+run,
        'AUTODATA_S3_BUCKET':'autodata-selector-fixture-'+run,'AUTODATA_SOURCE_REGION':'US',
        'AUTODATA_SOURCE_PERSIST':'1','AUTODATA_MINIO_ROOT_USER':'fixture',
        'AUTODATA_MINIO_ROOT_PASSWORD':'fixture','AUTODATA_IMAGE_URL_KEY':'fixture-image-key-0000000000000000',
        'AUTODATA_NATS_ADDRESS':'nats:4222','AUTODATA_NATS_URL':'nats://nats:4222',
        'BANKONE_BASE_URL':'http://127.0.0.1:18311','BANKTWO_BASE_URL':'http://127.0.0.1:18312',
        'AUTODATA_BANKONE_API_KEY':'fixture','AUTODATA_BANKTWO_API_KEY':'fixture',
        'AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON':'{"enabled":false}'}
    c.require(set(overrides)<=set(names),'environment_names_missing')
    values.update(overrides)
    return values


def payload(role,run,env,bootstrap):
    return {'Image':c.TEST_IMAGE if role=='bootstrap' else c.IMAGE,
        'User':'','WorkingDir':'/app/workers/ingestion-python','Entrypoint':['/usr/local/bin/python'],
        'Cmd':['-B','-u','-c',bootstrap] if role=='bootstrap' else ['-m','autodata_ingestion.http_service'],
        'Env':[k+'='+v for k,v in sorted(env.items())],
        'OpenStdin':role=='bootstrap','StdinOnce':False,
        'HostConfig':{'NetworkMode':None,'ReadonlyRootfs':True,'Memory':768*c.MIB,'PidsLimit':128,
            'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'RestartPolicy':{'Name':'no'},
            'Tmpfs':{'/tmp':'rw,noexec,nosuid,size=67108864'},
            'Mounts':[{'Type':'bind','Source':PACKAGE+'/source','Target':'/app','ReadOnly':True}]}}


def review_files(names,run,*,repo=REPO):
    c.require(isinstance(names,list) and names==sorted(set(names))
              and all(isinstance(x,str) and x.replace('_','A').isalnum() for x in names),'environment_names')
    c.require(len(run)==32 and all(x in 'abcdef0123456789' for x in run),'run_id')
    files={}
    sources={'fixture_bootstrap.py':'scripts/dev/fixtures/private_selector_bootstrap.py',
        'fixture_client.py':'scripts/dev/fixtures/private_selector_client.py',
        'private_selector_local_transport.py':'scripts/dev/private_selector_local_transport.py',
        'private_selector_adapter_contract.py':'scripts/dev/private_selector_adapter_contract.py',
        'private_selector_image_fixture.py':'scripts/dev/private_selector_image_fixture.py'}
    for name,source in sources.items():files[name]=(repo/source).read_bytes()
    c.require(sha(files['private_selector_local_transport.py'])==TRANSPORT_SHA,'transport_byte_drift')
    env=environment(names,run)
    environments={'worker':env,'bootstrap':{**env,**BOOTSTRAP_DEFAULTS}}
    plan={'run_id':run,'network':{'id':None,'peer_identities':{}},'hostconfig_by_status':{},
        'synthetic_environment':environments,'execution_approved':False,
        'unresolved':['exact internal synthetic network and peer identities','current daemon/socket/data-root/capacity readback',
            'full Created/Running/Exited HostConfig hashes for both fixture roles','immutable physical source/archive and rollback inventories',
            'sealed physical launcher with external execution-seal SHA and root phase approval'],
        'lifetime_limits':{'host_fixture_client_seconds':120,'owned_initial_job_seconds':20,
            'configuration_requests_dispatched':0,'actual_image_executed':False}}
    for role in ('bootstrap','worker'):
        files['fixture-'+role+'.create.json']=json.dumps(payload(role,run,environments[role],files['fixture_bootstrap.py'].decode()),sort_keys=True,indent=2).encode()+b'\n'
    files['fixture-plan.json']=json.dumps(plan,sort_keys=True,indent=2).encode()+b'\n'
    artifact_files={'transport':'private_selector_local_transport.py','contract':'private_selector_adapter_contract.py',
        'fixture_adapter':'private_selector_image_fixture.py','fixture_bootstrap':'fixture_bootstrap.py',
        'fixture_client':'fixture_client.py','fixture_plan':'fixture-plan.json',
        'fixture_payload_bootstrap':'fixture-bootstrap.create.json','fixture_payload_worker':'fixture-worker.create.json'}
    artifacts={name:sha(files[path]) for name,path in artifact_files.items()}
    artifacts.update(archive=ARCHIVE_SHA,source_inventory=None)
    manifest={'phase':'fixture','run_id':run,'pins':c.PINS,'artifacts':artifacts,
        'home_cap':128*c.MIB,'docker_cap':64*c.MIB,'offloaded_cap':64*c.MIB,
        'execution_approved':False,'transport':{'sql_approved':False,'http_approved':False,
            'docker_start_free':None,'offloaded_root':None}}
    files['fixture-manifest.NOT-ADMITTED.json']=json.dumps(manifest,sort_keys=True,indent=2).encode()+b'\n'
    commands={'safe_now':[['/usr/bin/python3','-B','-m','unittest','discover','-s','scripts/dev/tests','-p','test_private_selector_fixture_package.py']],
        'execution_approved':False,'live_command':None,
        'future_launcher_requirement':'Verify physical external seal; import fixture_client.wrap_transport(LocalTransport); run Fixture(manifest,wrapped_transport) once only after root exact plan/command approval.',
        'actual_image_result':'NOT_RUN','provider_requests_dispatched':0}
    files['commands.json']=json.dumps(commands,sort_keys=True,indent=2).encode()+b'\n'
    return files


def build(output,names,run):
    output=Path(output)
    c.require(output.parent==EVIDENCE and output.parent.resolve()==EVIDENCE
              and output.parent.stat().st_dev==OFFLOADED_DEVICE,'offloaded_parent_required')
    files=review_files(names,run)
    c.require(sum(map(len,files.values()))<2*c.MIB,'review_package_bound')
    output.mkdir(mode=0o700)  # Refuse any existing directory; never overwrite evidence.
    c.require(output.stat().st_dev==OFFLOADED_DEVICE,'offloaded_output_required')
    try:
        for name,data in files.items():
            fd=os.open(output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        seal={'execution_approved':False,'actual_image_result':'NOT_RUN',
            'files':{name:{'sha256':sha(data),'bytes':len(data)} for name,data in files.items()}}
        fd=os.open(output/'package-seal.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(seal,stream,sort_keys=True,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        for directory in (output,output.parent):
            fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        return seal
    except Exception:raise c.Refused('review_build_incomplete_preserved_for_audit') from None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-review',action='store_true',required=True)
    parser.add_argument('--environment-names',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    value=build(args.output,json.loads(args.environment_names.read_text()),args.run_id)
    print(json.dumps({'status':'REVIEW_PACKAGE_ONLY_EXECUTION_HELD','files':len(value['files']),
        'execution_approved':False,'actual_image_result':'NOT_RUN'},sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
