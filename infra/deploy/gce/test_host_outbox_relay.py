"""Production relay contracts and opt-in disposable PostgreSQL/NATS smoke."""
import copy
import json
from pathlib import Path
import unittest

import test_host_runtime as fixtures

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SECRETS = ('AUTODATA_POSTGRES_PASSWORD', 'NATS_OUTBOX_USER', 'NATS_OUTBOX_PASSWORD')
COMMAND = ['python', '/app/scripts/outbox_relay.py', '--poll-seconds', '5', '--batch-size', '50', '--max-attempts', '3']


class RelayContracts(unittest.TestCase):
    def setUp(self):
        source = fixtures.ContractTests(); source.setUp()
        self.addCleanup(source.doCleanups)
        self.rt, self.config, self.manifest = source.rt, source.config, source.manifest

    def test_packaging_contains_relay_and_all_three_python_packages(self):
        image = (ROOT / 'workers/ingestion-python/Dockerfile').read_text()
        self.assertIn('COPY scripts/dev/outbox_relay.py ./scripts/outbox_relay.py', image)
        self.assertIn('COPY workers/enrichment-python/src ./enrichment-src', image)
        self.assertIn('ENV PYTHONPATH=/app/src:/app/contracts:/app/enrichment-src', image)

    def test_relay_is_required_backend_only_and_has_dedicated_authority(self):
        self.assertIn('outbox-relay', self.rt.NORMAL_SERVICES)
        graph = json.loads(self.rt.render_bundle(self.manifest, self.config)['compose.production.yaml'])
        relay = graph['services']['outbox-relay']
        self.assertEqual(relay['command'], COMMAND)
        self.assertEqual(relay['user'], '1000:1000')
        self.assertEqual(relay['networks'], {'backend': {'ipv4_address': '172.30.20.14'}})
        self.assertNotIn('ports', relay); self.assertNotIn('healthcheck', relay)
        self.assertEqual(relay['volumes'], [{'type':'bind', 'source':'/run/autodata/outbox-relay',
            'target':'/run/autodata/outbox-relay', 'read_only':True, 'bind':{'create_host_path':False}}])
        self.assertEqual(relay['depends_on'], {'postgres':{'condition':'service_healthy'}, 'nats':{'condition':'service_started'}})
        env = relay['environment']
        self.assertEqual(env['AUTODATA_POSTGRES_USER'], 'autodata_outbox')
        self.assertEqual(env['AUTODATA_NATS_URL'], 'nats://nats:4222')
        self.assertEqual(self.rt.SECRET_NAMES['outbox-relay'], SECRETS)
        self.assertFalse(any('S3' in name or 'STRIPE' in name or 'BANK' in name for name in env))

    def test_manifest_requires_matching_explicit_publisher_secret_versions(self):
        self.assertIn('outbox-relay', self.manifest['secret_versions'])
        self.rt.validate_manifest(self.manifest, self.config)
        for mutate in (lambda m: m['secret_versions'].pop('outbox-relay'),
                       lambda m: m['secret_versions']['outbox-relay'].pop('NATS_OUTBOX_USER'),
                       lambda m: m['secret_versions']['outbox-relay'].update(NATS_OUTBOX_USER='projects/autodata-host/secrets/other/versions/1'),
                       lambda m: m['secret_versions']['nats'].update(NATS_OUTBOX_PASSWORD='projects/autodata-host/secrets/other/versions/1')):
            candidate=copy.deepcopy(self.manifest); mutate(candidate)
            with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(candidate,self.config)

    def test_broker_publisher_acl_is_exact_and_metrics_remains_info_only(self):
        import re
        template=(HERE/'nats.conf.template').read_text()
        blocks=re.findall(r'publish: \{ allow: \[(.*?)\] \}',template,re.S)
        self.assertEqual(len(blocks),2)
        self.assertEqual(json.loads('['+blocks[0]+']'), ['$JS.API.INFO'])
        expected={'catalog.article.published','dataset.fast.requested','dataset.viewable','dataset.deep.requested',
            'dataset.section.published','dataset.enrichment.failed','dataset.review.requested',
            'dataset.revision.revoked','dataset.knowledge.fallback.requested',
            '$JS.API.STREAM.INFO.AUTODATA','$JS.API.STREAM.INFO.AUTODATA_CATALOG',
            '$JS.API.STREAM.CREATE.AUTODATA','$JS.API.STREAM.CREATE.AUTODATA_CATALOG'}
        self.assertEqual(set(json.loads('['+blocks[1]+']')),expected)
        self.assertEqual(template.count('subscribe: { allow: ["_INBOX.>"] }'),2)

    def test_provisioning_grants_only_outbox_delivery_columns(self):
        sql=(HERE/'runtime-grants.sql').read_text()
        self.assertIn('GRANT SELECT ON TABLE public.publication_events TO autodata_outbox;',sql)
        self.assertIn('GRANT UPDATE (delivery_status, delivery_attempts, delivery_lease_owner, delivery_lease_token,',sql)
        self.assertNotIn('GRANT INSERT',sql); self.assertNotIn('GRANT DELETE',sql)


# This fixture creates only a random internal Docker network and disposable
# containers. It never uses a host address, existing volume or external service.
# Build the real ingestion Dockerfile first, then explicitly opt in:
# AUTODATA_OUTBOX_RELAY_SMOKE=1 AUTODATA_OUTBOX_SMOKE_IMAGE=<local-image> python3 -m unittest discover -s infra/deploy/gce -p test_host_outbox_relay.py -v
import os
import subprocess
import tempfile
import time
import uuid


@unittest.skipUnless(os.getenv('AUTODATA_OUTBOX_RELAY_SMOKE') == '1', 'requires disposable local PostgreSQL/NATS smoke opt-in')
class RealRelaySmoke(unittest.TestCase):
    def docker(self, *args, data=None, timeout=60):
        result = subprocess.run(['/usr/bin/docker', *args], input=data, capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
        return result.stdout

    def setUp(self):
        self.image = os.environ['AUTODATA_OUTBOX_SMOKE_IMAGE']
        self.docker('image', 'inspect', self.image)
        self.prefix = 'autodata-outbox-smoke-' + uuid.uuid4().hex[:12]
        self.network = self.prefix
        self.pg, self.nats = self.prefix + '-pg', self.prefix + '-nats'
        self.addCleanup(self.cleanup)
        self.temp = tempfile.TemporaryDirectory(prefix=self.prefix)
        self.addCleanup(self.temp.cleanup)
        self.docker('network', 'create', '--internal', self.network)
        config = (HERE/'nats.conf.template').read_text()
        for name, value in {'NATS_METRICS_USER':'smoke_metrics', 'NATS_METRICS_PASSWORD':'smoke_metrics_only',
                            'NATS_OUTBOX_USER':'smoke_publisher', 'NATS_OUTBOX_PASSWORD':'smoke_publisher_only'}.items():
            config=config.replace('@@'+name+'@@', value)
        # Independent observer is exclusive to this disposable test. The two
        # deployed users retain the exact rendered production permission blocks.
        config=config.replace('  users: [', '  users: [\n    { user: "smoke_observer", password: "smoke_observer_only" },')
        config=config.replace('/data/jetstream', '/tmp/jetstream')
        target=Path(self.temp.name)/'nats.conf'; target.write_text(config); target.chmod(0o644)
        self.docker('run','-d','--name',self.nats,'--network',self.network,'--network-alias','nats',
                    '--mount',f'type=bind,src={target},dst=/etc/nats/smoke.conf,readonly',
                    'nats:2.10-alpine','-c','/etc/nats/smoke.conf')
        self.docker('run','-d','--name',self.pg,'--network',self.network,'--network-alias','postgres',
                    '-e','POSTGRES_DB=autodata','-e','POSTGRES_PASSWORD=smoke_admin_only','pgvector/pgvector:pg17')
        for attempt in range(80):
            result=subprocess.run(['/usr/bin/docker','exec',self.pg,'pg_isready','-h','127.0.0.1','-U','postgres','-d','autodata'],capture_output=True,timeout=5)
            if result.returncode==0: break
            time.sleep(.25)
        else: self.fail('disposable PostgreSQL failed to start')
        migration=subprocess.run(['/bin/sh',str(ROOT/'scripts/dev/migrate_sql.sh'),'--emit'],capture_output=True,timeout=20,check=True)
        self.sql(migration.stdout)
        self.sql(b"CREATE ROLE autodata_metrics LOGIN; CREATE ROLE autodata_outbox LOGIN PASSWORD 'smoke_db_only';")
        self.sql((HERE/'runtime-grants.sql').read_bytes())
        self.secret_dir=Path(self.temp.name)/'outbox-relay'; self.secret_dir.mkdir()
        for name,value in {'AUTODATA_POSTGRES_PASSWORD':'smoke_db_only','NATS_OUTBOX_USER':'smoke_publisher',
                           'NATS_OUTBOX_PASSWORD':'smoke_publisher_only'}.items():
            path=self.secret_dir/name; path.write_text(value); path.chmod(0o400)
        self.secret_dir.chmod(0o500)
        self.addCleanup(self.secret_dir.chmod,0o700)

    def cleanup(self):
        for name in (self.pg,self.nats):
            subprocess.run(['/usr/bin/docker','rm','-fv',name],capture_output=True,timeout=30)
        subprocess.run(['/usr/bin/docker','network','rm',self.network],capture_output=True,timeout=30)

    def sql(self, data):
        return self.docker('exec','-i',self.pg,'psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','autodata','-At',data=data)

    def client(self, code):
        return self.docker('run','--rm','--network',self.network,'--entrypoint','python',self.image,'-c',code)

    def relay(self):
        result=self.docker('run','--rm','--network',self.network,'--user','1000:1000','--read-only',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true',
            '--mount',f'type=bind,src={self.secret_dir},dst=/run/autodata/outbox-relay,readonly',
            '-e','AUTODATA_RUNTIME_SERVICE=outbox-relay','-e','AUTODATA_ENV=staging',
            '-e','AUTODATA_DB_ADDRESS=postgres:5432','-e','AUTODATA_POSTGRES_DB=autodata',
            '-e','AUTODATA_POSTGRES_USER=autodata_outbox','-e','AUTODATA_NATS_URL=nats://nats:4222',
            self.image,'python','/app/scripts/outbox_relay.py','--once','--batch-size','1','--max-attempts','3')
        return json.loads(result)

    def test_packaged_delivery_replay_outage_and_denied_authorities(self):
        self.client('import autodata_ingestion,autodata_enrichment.outbox,autodata_contracts; print("packaged imports passed")')
        self.docker('run','--rm',self.image,'python','/app/scripts/outbox_relay.py','--help')
        # Fully constrained canonical lineage, with no disabled FK/check/trigger.
        self.sql(b"""
INSERT INTO source_snapshots(source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,license_metadata,retrieved_at)
 VALUES ('10000000-0000-4000-8000-000000000001','fixture','fixture://relay','v1',repeat('1',64),'fixture/relay','{}',now());
INSERT INTO vehicles(vehicle_id,vehicle_key,make,model,model_year,region,source_snapshot_id,source_watermark)
 VALUES ('10000000-0000-4000-8000-000000000002','relay-smoke','Fixture','Car',2024,'US','10000000-0000-4000-8000-000000000001','v1');
INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id)
 VALUES ('10000000-0000-4000-8000-000000000003','bankone','10000000-0000-4000-8000-000000000002','vehicle:10000000-0000-4000-8000-000000000002','vehicle','article',repeat('2',64),'{}','10000000-0000-4000-8000-000000000001');
INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at)
 VALUES ('10000000-0000-4000-8000-000000000004','10000000-0000-4000-8000-000000000003',repeat('3',64),'10000000-0000-4000-8000-000000000001','[]','{"blocks":[{"text":"Remove pump."}]}','[]','Remove pump.','[]','readable','["fixture"]',now());
INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_version,connector_name,idempotency_key,status,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version)
 VALUES ('10000000-0000-4000-8000-000000000005','bankone','10000000-0000-4000-8000-000000000002','vehicle','v1','fixture','fixture-transform','completed','10000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000004',repeat('4',64),'ordered-article-v1','technical-prose-v1');
INSERT INTO canonical_article_revisions(canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata,published_at)
 VALUES ('10000000-0000-4000-8000-000000000006','10000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000004',repeat('4',64),'ordered-article-v1','technical-prose-v1','published','{}',repeat('5',64),'{"blocks":[{"text":"Take off pump."}]}','Take off pump.','[]','[]','{"passed":true,"changed_slots":["b1"],"evidence_ids":["fixture"]}',repeat('6',64),repeat('7',64),'{"model":"fixture","profile_version":"technical-prose-v1"}',now());
INSERT INTO publication_events(publication_event_id,event_type,event_version,canonical_article_id,canonical_article_revision_id,correlation_id,idempotency_key,payload,producer)
 VALUES ('10000000-0000-4000-8000-000000000007','catalog.article.published',1,'10000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000006','10000000-0000-4000-8000-000000000008','relay-smoke-idempotency','{"source_revision_id":"10000000-0000-4000-8000-000000000004","review_status":"UNREVIEWED"}','fixture');
""")
        result=self.relay(); self.assertEqual(result['published'],1)
        self.assertEqual(self.sql(b'SELECT delivery_status,delivery_attempts FROM publication_events;').strip(),b'published|1')
        observe='''
import asyncio,json,nats
async def main():
    nc=await nats.connect('nats://nats:4222',user='smoke_observer',password='smoke_observer_only')
    js=nc.jetstream(); info=await js.stream_info('AUTODATA_CATALOG'); assert info.state.messages==1
    msg=await js.get_msg('AUTODATA_CATALOG',seq=1)
    body=json.loads(msg.data); assert body['idempotency_key']=='relay-smoke-idempotency'
    assert body['event_id']=='10000000-0000-4000-8000-000000000007'
    assert body['canonical_article_id']=='10000000-0000-4000-8000-000000000003'
    assert body['source_revision_id']=='10000000-0000-4000-8000-000000000004'
    assert msg.headers['Nats-Msg-Id']=='relay-smoke-idempotency'
    await nc.close(); print('actual catalog envelope and Nats-Msg-Id passed')
asyncio.run(main())
'''
        self.client(observe)
        self.sql(b"UPDATE publication_events SET delivery_status='pending',delivered_at=NULL;")
        self.assertEqual(self.relay()['published'],1)
        self.client(observe)  # stream still contains exactly one de-duplicated event
        self.client('''
import asyncio,nats
async def denied(user,password,operation):
    errors=[]
    async def error_cb(error): errors.append(str(error))
    nc=await nats.connect('nats://nats:4222',user=user,password=password,error_cb=error_cb)
    try:
        js=nc.jetstream()
        if operation=='delete': await asyncio.wait_for(js.delete_stream('AUTODATA_CATALOG'),1)
        else: await js.publish(operation,b'denied',timeout=.5)
    except (nats.errors.TimeoutError,asyncio.TimeoutError): pass
    else: raise AssertionError('forbidden broker operation succeeded')
    await nc.flush(); await nc.close()
    assert any('permissions violation' in error.lower() for error in errors), errors
async def main():
    await denied('smoke_metrics','smoke_metrics_only','catalog.article.published')
    await denied('smoke_publisher','smoke_publisher_only','unrelated.subject')
    await denied('smoke_publisher','smoke_publisher_only','delete')
    print('metrics publication, unrelated publish and stream delete denied')
asyncio.run(main())
''')
        self.client('''
import psycopg
for statement in ("UPDATE publication_events SET payload='{}'", "DELETE FROM publication_events", "INSERT INTO publication_events(event_type) VALUES ('bad')", "UPDATE canonical_articles SET title='bad'"):
    with psycopg.connect(host='postgres',dbname='autodata',user='autodata_outbox',password='smoke_db_only') as conn:
        try: conn.execute(statement)
        except psycopg.errors.InsufficientPrivilege: pass
        else: raise AssertionError('forbidden database operation succeeded')
print('outbox canonical updates, insert/delete and canonical article writes denied')
''')
        self.sql(b"UPDATE publication_events SET delivery_status='pending',delivered_at=NULL;")
        self.docker('stop','-t','1',self.nats)
        result=self.relay(); self.assertEqual(result['status'],'skipped (broker unreachable)')
        self.assertEqual(result['claimed'],0)
        self.assertEqual(self.sql(b'SELECT delivery_status,delivered_at IS NULL FROM publication_events;').strip(),b'pending|t')
        self.client("import psycopg; c=psycopg.connect(host='postgres',dbname='autodata',user='autodata_outbox',password='smoke_db_only'); assert c.execute('SELECT count(*) FROM publication_events').fetchone()[0]==1; c.close()")
        print('packaged relay real delivery/replay/ACL/database-denials/outage: PASS')
