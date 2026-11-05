#!/usr/bin/python3 -I
"""Cache an accepted staging release and initialize its fresh PostgreSQL17 DB."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

# Installed root-owned sibling, never PYTHONPATH or ambient imports.
def sibling(name):
    path = Path(__file__).parent/(name+'.py')
    spec = importlib.util.spec_from_file_location('autodata_'+name,path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
p = sibling('host_provision')
require = p.require
BIN = '/opt/autodata/bin'
RELEASES = '/opt/autodata/releases'
PSQL = '/usr/lib/postgresql/17/bin/psql'
CONTAINER = 'autodata-production-postgres-1'
REGISTRY = '/run/autodata/registry'
ROLES = ('migrator','api','http','article','reconciler','metrics','outbox')
ROLE_FILES = ('admin',)+ROLES


def accepted_images(manifest,images):
    expected = [{'role':role,'reference':value['reference'],'image_id':value['image_id']} for role,value in sorted(manifest['images'].items())]
    require(images == expected); return expected

def secret(value):
    require(type(value) is bytes and 1 <= len(value) <= 16384 and not any(byte in value for byte in (b'\x00',b'\r',b'\n')))
    value.decode('utf-8'); return value

def password_sql(role,value):
    require(role in {'autodata_'+name for name in ROLES}); secret(value)
    # Hex is generated from bytes, contains no SQL metacharacters. format %L
    # performs server-side literal quoting; gexec never prints the statement.
    return ("SELECT pg_catalog.format('ALTER ROLE %I PASSWORD %L', '"+role+"', pg_catalog.convert_from(pg_catalog.decode('"+
            value.hex()+"','hex'),'UTF8')) \\gexec\n").encode()

def validate_resume(manifest,journal,observed,accepted):
    names = [item['name'][:-4] for item in manifest['migrations']['files']]
    require(type(journal) is dict and journal.get('source_sha') == manifest['source_sha'] and
            journal.get('operation') in ('initialize-fresh-staging-database','resume-created-staging-database') and
            journal.get('status') == 'incomplete' and 'postgres-created' in journal.get('stages',[]))
    require(type(observed) is list and observed == accepted and observed == names[:len(observed)]); return True

class Preparation:
    def __init__(self,pins,approval,config,runtime,executor=p.command):
        self.pins,self.a,self.config,self.rt,self.execute = pins,approval,config,runtime,executor
        self.deadline = time.monotonic()+2400
        self.manifest = None
    def run(self,argv,timeout=120,input_data=None,cleanup=False):
        if not cleanup:
            self.pins.recheck(); p.validate_approval(self.a,self.a['source_sha'],'images' if self.a['operation'] == 'cache-accepted-staging-images' else 'database')
        return self.execute(argv,timeout=timeout,deadline=self.deadline if cleanup else self.deadline-30,input_data=input_data)
    def prerequisites(self):
        observations = [p.strict_json(self.run(['/usr/bin/findmnt','--json','--list','--mountpoint',target,'--output','TARGET,UUID,FSTYPE,OPTIONS'])) for target in (p.DATA,p.RUN)]
        self.rt.validate_mount_observations(self.config,*observations)
        tables = {family:p.strict_json(self.run(['/usr/sbin/nft','--json','--numeric','list','table',family,'autodata_guard'])) for family in ('inet','bridge')}
        self.rt.validate_guard_tables(tables)
    def installed(self):
        sha = self.a['source_sha']; path = RELEASES+'/'+sha+'/release.json'
        raw = self.pins.read(path); require(p.digest(raw) == self.a['manifest_raw_sha256'])
        manifest,config = self.rt._installed_deploy_inputs(sha)
        require(manifest == p.strict_json(raw) and config == self.config and manifest.get('rollback_source_sha') is None)
        self.rt.validate_installed_migration_tree(manifest); self.manifest = manifest; return manifest
    def cached(self):
        observations = {}
        template = '{"image_id":{{json .ID}},"repo_digests":{{json .RepoDigests}},"os":{{json .Os}},"architecture":{{json .Architecture}},"variant":{{json .Variant}}}'
        for role,image in sorted(self.manifest['images'].items()):
            value = p.strict_json(self.run(p.DOCKER+['image','inspect','--platform','linux/amd64','--format',template,image['reference']]))
            p.exact(value,('image_id','repo_digests','os','architecture','variant'))
            require(type(value['repo_digests']) is list and 1 <= len(value['repo_digests']) <= 256 and image['reference'] in value['repo_digests'])
            require(all(type(item) is str for item in value['repo_digests']) and len(set(value['repo_digests'])) == len(value['repo_digests']))
            require(value['os'] == 'linux' and value['architecture'] == 'amd64' and value['variant'] == '')
            observations[role] = {'reference':image['reference'],'image_id':value['image_id'],'platform':'linux/amd64'}
        self.rt.validate_cached_images(self.manifest,observations); return observations
    def image_cleanup(self,identity):
        path = REGISTRY+'/config.json'; current = os.stat(path,follow_symlinks=False)
        require(p.metadata(current) == p.metadata(identity)); os.unlink(path)
        require(os.listdir(REGISTRY) == []); os.rmdir(REGISTRY)
        require(not os.path.lexists(REGISTRY))
    def images(self):
        self.prerequisites()
        directory = REGISTRY; self.pins.directory(directory,0o700)
        require(os.listdir(directory) == ['config.json'])
        raw = self.pins.read(directory+'/config.json'); require(p.digest(raw) == self.a['registry_config_sha256'])
        config_auth = p.strict_json(raw); p.exact(config_auth,('auths',)); require(type(config_auth['auths']) is dict)
        for registry,credentials in config_auth['auths'].items():
            require(p.match(registry,r'[a-z0-9.-]+(?::[0-9]+)?'))
            p.exact(credentials,('auth',)); require(type(credentials['auth']) is str and 1 <= len(credentials['auth']) <= 65536)
        identity = os.stat(directory+'/config.json',follow_symlinks=False)
        journal = None
        try:
            # Installer owns operation.lock: call outside both preparation locks.
            value = p.strict_json(self.run([BIN+'/deploy.sh','install',self.a['source_sha']],300))
            require(type(value) is dict and value.get('status') == 'passed' and value.get('source_sha') == self.a['source_sha'] and
                value.get('release_material_committed') is True and value.get('commit_state') == 'receipt_committed' and
                value.get('manifest_raw_sha256') == self.a['manifest_raw_sha256'] and value.get('service_config_sha256') == self.a['service_config_sha256'])
            make_state()
            with p.locked(p.RUN+'/state/operation.lock'), p.locked(p.DATA+'/operations/activation.lock'):
                self.prerequisites(); manifest = self.installed(); accepted_images(manifest,self.a['images'])
                journal = p.Journal(self.a); journal.value['manifest_raw_sha256'] = self.a['manifest_raw_sha256']; journal.save()
                for item in self.a['images']:
                    self.run(p.DOCKER+['--config',directory,'image','pull','--platform','linux/amd64',item['reference']],300)
                    self.cached_one(item)
                observations = self.cached(); journal.stage('images-verified'); journal.value['images'] = observations
        finally:
            # No success receipt until the exact operation-owned auth is gone.
            self.image_cleanup(identity)
        journal.success(); return journal.value
    def cached_one(self,item):
        output = self.run(p.DOCKER+['image','inspect','--platform','linux/amd64','--format',
            '{"id":{{json .ID}},"digests":{{json .RepoDigests}},"os":{{json .Os}},"arch":{{json .Architecture}},"variant":{{json .Variant}}}',item['reference']])
        value = p.strict_json(output); p.exact(value,('id','digests','os','arch','variant'))
        require(value['id'] == item['image_id'] and type(value['digests']) is list and item['reference'] in value['digests'] and
                value['os'] == 'linux' and value['arch'] == 'amd64' and value['variant'] == '')
    def compose(self,args,timeout=120,cleanup=False):
        directory = RELEASES+'/'+self.a['source_sha']
        return self.run(p.DOCKER+['compose','--project-name','autodata-production','--project-directory',directory,
            '--file',directory+'/compose.production.yaml','--env-file','/dev/null','--profile','migration']+args,timeout,cleanup=cleanup)
    def sql(self,sql,role='autodata_admin',timeout=120):
        require(role in ('autodata_admin','autodata_metrics'))
        return self.run(p.DOCKER+['exec','-i','--user','999:999','--workdir','/',CONTAINER,
            '/usr/bin/env','-i','PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin','LANG=C','LC_ALL=C',
            'HOME=/nonexistent','PGPASSFILE=/dev/null','PGSERVICEFILE=/dev/null',PSQL,'--no-psqlrc','--no-password',
            '--no-align','--tuples-only','--quiet','--host=/var/run/postgresql','--port=5432','--username='+role,
            '--dbname=autodata','--set=ON_ERROR_STOP=1'],timeout,input_data=sql)
    def no_applications(self,resume=False):
        require(not os.path.lexists('/opt/autodata/current'))
        output = self.run(p.DOCKER+['container','ls','--all','--format','{{.ID}} {{.Label "com.docker.compose.service"}}',])
        rows = output.decode('ascii').splitlines()
        require(all(p.match(row,r'[0-9a-f]{12,64} postgres') for row in rows) and len(rows) <= (1 if resume else 0))
    def role_facts(self):
        # Runtime role audit is independent of the later metrics collector.
        names = ','.join("'autodata_"+name+"'" for name in ROLES)
        query = ("SELECT json_agg(json_build_object('name',rolname,'safe',NOT(rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit) AND rolcanlogin AND NOT EXISTS(SELECT FROM pg_auth_members WHERE member=r.oid))) FROM pg_roles r WHERE rolname IN ("+names+");\n").encode()
        values = p.strict_json(self.sql(query)); require(type(values) is list and len(values) == len(ROLES))
        require({item.get('name') for item in values} == {'autodata_'+name for name in ROLES} and all(item == {'name':item['name'],'safe':True} for item in values))
    def database(self):
        self.prerequisites(); manifest = self.installed(); self.cached()
        role_sql = self.pins.read(BIN+'/host-bootstrap-roles.sql',0o444)
        grants = self.pins.read(BIN+'/runtime-grants.sql',0o444)
        require(p.digest(role_sql) == self.a['bootstrap_roles_sha256'] and p.digest(grants) == self.a['runtime_grants_sha256'])
        receipts = []
        for path in sorted(Path(p.RECEIPTS).glob('*.json')):
            raw = self.pins.read(str(path))
            if p.digest(raw) == self.a['image_cache_receipt_sha256']: receipts.append(p.strict_json(raw))
        require(len(receipts) == 1)
        prior = receipts[0]; require(prior.get('status') == 'passed' and prior.get('operation') == 'cache-accepted-staging-images' and
            prior.get('source_sha') == manifest['source_sha'] and prior.get('manifest_raw_sha256') == self.a['manifest_raw_sha256'] and
            prior.get('images') == {role:{'reference':value['reference'],'image_id':value['image_id'],'platform':'linux/amd64'} for role,value in manifest['images'].items()})
        self.pins.directory('/run/autodata/postgres',0o500,999,999)
        require(os.listdir('/run/autodata/postgres') == ['POSTGRES_PASSWORD'])
        normal = secret(self.pins.read('/run/autodata/postgres/POSTGRES_PASSWORD',0o400,16384,999,999))
        self.pins.directory('/run/autodata/migration',0o500,1000,1000)
        require(os.listdir('/run/autodata/migration') == ['PGPASSWORD'])
        migration = secret(self.pins.read('/run/autodata/migration/PGPASSWORD',0o400,16384,1000,1000))
        directory = '/run/autodata/database-bootstrap'; self.pins.directory(directory,0o700)
        require(sorted(os.listdir(directory)) == sorted(name+'-password' for name in ROLE_FILES))
        passwords = {name:secret(self.pins.read(directory+'/'+name+'-password',maximum=16384)) for name in ROLE_FILES}
        require(passwords['admin'] == normal and passwords['migrator'] == migration)
        cleanup_paths = [(directory+'/'+name+'-password',os.stat(directory+'/'+name+'-password',follow_symlinks=False)) for name in ROLE_FILES]
        cleanup_paths += [('/run/autodata/migration/PGPASSWORD',os.stat('/run/autodata/migration/PGPASSWORD',follow_symlinks=False))]
        journal = None; created = False
        try:
            make_state()
            with p.locked(p.RUN+'/state/operation.lock'), p.locked(p.DATA+'/operations/activation.lock'):
                self.prerequisites(); resume = self.a['resume'] is not None; self.no_applications(resume)
                self.pins.directory(p.DATA+'/postgres',0o700,999,999)
                if not resume: require(os.listdir(p.DATA+'/postgres') == [])
                else:
                    journals = []
                    for path in Path(p.RECEIPTS).glob('*.json'):
                        raw = self.pins.read(str(path))
                        if p.digest(raw) == self.a['resume']['journal_sha256']: journals.append(p.strict_json(raw))
                    require(len(journals) == 1)
                lifecycle = sibling('host_activation')
                bundle = self.rt.render_bundle(manifest,self.config)
                # Existing activation materializer requires its own Pins, keeping
                # exact immutable-content/recheck semantics in the inert release.
                with lifecycle.Pins() as installed_pins:
                    target = installed_pins.directory(RELEASES+'/'+manifest['source_sha'])
                    for name in ('compose.production.yaml','Caddyfile'):
                        lifecycle.materialize(installed_pins,target,name,bundle[name].encode())
                journal = p.Journal(self.a); journal.value.update(manifest_raw_sha256=self.a['manifest_raw_sha256'],image_cache_receipt_sha256=self.a['image_cache_receipt_sha256']); journal.save()
                self.compose(['up','-d','--no-deps','--pull','never','postgres']); created = True; journal.stage('postgres-created')
                end = min(self.deadline,time.monotonic()+120)
                while True:
                    try:
                        facts = p.strict_json(self.sql(b"SELECT json_build_object('user',current_user,'database',current_database(),'version',current_setting('server_version_num')::int,'super',rolsuper) FROM pg_roles WHERE rolname=current_user;\n"))
                        require(facts['user'] == 'autodata_admin' and facts['database'] == 'autodata' and 170000 <= facts['version'] < 180000 and facts['super'] is True); break
                    except Exception:
                        require(time.monotonic() < end); time.sleep(.1)
                self.rt.validate_postgres_container(manifest,p.strict_json(self.run(p.DOCKER+['container','inspect','--format',self.rt.POSTGRES_INSPECT_TEMPLATE,CONTAINER])))
                if resume:
                    observed = p.strict_json(self.sql(b"SELECT COALESCE(json_agg(version ORDER BY version COLLATE \"C\"),'[]'::json) FROM ONLY public.schema_migrations;\n"))
                    validate_resume(manifest,journals[0],observed,self.a['resume']['observed_ledger_prefix'])
                    require(journals[0].get('manifest_raw_sha256') == self.a['manifest_raw_sha256'])
                    self.role_facts()
                self.sql(role_sql)
                for name in ROLES: self.sql(password_sql('autodata_'+name,passwords[name]))
                self.role_facts(); journal.stage('roles-created')
                self.compose(['run','--rm','--no-deps','--pull','never','--name','autodata-migration-'+self.a['authorization_id'],'migration'],600)
                journal.stage('migrations-applied')
                self.sql(application_grants()+grants)
                self.role_facts()
                observation = self.rt.collect_postgres_schema(manifest); self.rt.validate_schema_ledger(manifest,observation)
                # Existing activation's final PGDATA owner/mode/version check.
                lifecycle.validate_data_directories(self.rt); self.no_applications(True)
                journal.stage('schema-verified')
        finally:
            # Remove one-shot container even when the client timed out. No DB
            # stop/down/volume deletion: preserve PostgreSQL for owner diagnosis.
            cleanup_ok = True
            if journal is not None:
                try:
                    name = 'autodata-migration-'+self.a['authorization_id']
                    self.run(p.DOCKER+['container','rm','--force',name],30,cleanup=True)
                except Exception:
                    # run --rm already removed it on normal completion; prove absence.
                    try:
                        output = self.run(p.DOCKER+['container','ls','--all','--quiet','--filter','name=^/'+name+'$'],30,cleanup=True)
                        require(output == b'')
                    except Exception: cleanup_ok = False
            for path,identity in cleanup_paths:
                try: require(p.metadata(os.stat(path,follow_symlinks=False)) == p.metadata(identity)); os.unlink(path)
                except Exception: cleanup_ok = False
            for path in (directory,'/run/autodata/migration'):
                try: require(not os.listdir(path)); os.rmdir(path)
                except Exception: cleanup_ok = False
            require(cleanup_ok)
        journal.success(); return journal.value

def application_grants():
    roles = 'autodata_api, autodata_http, autodata_article, autodata_reconciler'
    return ("REVOKE ALL ON DATABASE autodata FROM PUBLIC; REVOKE ALL ON SCHEMA public FROM PUBLIC;\n"
        "GRANT CONNECT ON DATABASE autodata TO "+roles+"; GRANT USAGE ON SCHEMA public TO "+roles+";\n"
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "+roles+";\n"
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "+roles+";\n"
        "REVOKE INSERT, UPDATE, DELETE ON public.schema_migrations FROM "+roles+";\n").encode()

def make_state():
    p.make_directory('/run/autodata/state'); p.make_directory('/var/lib/autodata/operations')

def main(argv):
    require(len(argv) == 2 and argv[0] in ('images','database')); p.validate_sha(argv[1]); require(os.getuid() == 0)
    with p.Pins() as pins:
        config = p.strict_json(pins.read('/etc/autodata/host.json')); require(config.get('environment') == 'staging')
        approval = p.validate_approval(p.strict_json(pins.read('/etc/autodata/host-prepare-approval.json')),argv[1],argv[0])
        raw = pins.read(p.BUNDLE+'/inventory.json',0o444); require(p.digest(raw) == approval['bundle_inventory_sha256'])
        entries = p.validate_inventory(p.BUNDLE,p.strict_json(raw),argv[1],pins)
        for item in entries:
            require(p.digest(pins.read('/'+item['path'],item['mode'])) == item['sha256'])
        rt = p.load_module(BIN+'/runtime-check.py','prepare_runtime'); require(rt.validate_config(config) == approval['service_config_sha256'])
        accepted = pins.read('/etc/autodata/publisher-accepted/'+argv[1]+'.json'); require(p.digest(accepted) == approval['publisher_acceptance_sha256'])
        pins.directory(p.RECEIPTS,0o700)
        prepared = []
        for path in Path(p.RECEIPTS).glob('*.json'):
            value = p.strict_json(pins.read(str(path)))
            if value.get('operation') == 'prepare-new-empty-staging-host' and value.get('status') == 'passed' and value.get('source_sha') == argv[1]: prepared.append(value)
        require(len(prepared) == 1 and prepared[0].get('bundle_inventory_sha256') == approval['bundle_inventory_sha256'] and
            prepared[0].get('service_config_sha256') == approval['service_config_sha256'])
        operation = Preparation(pins,approval,config,rt)
        return operation.images() if argv[0] == 'images' else operation.database()

if __name__ == '__main__':
    try: print(json.dumps(main(sys.argv[1:]),sort_keys=True))
    except Exception: print('{"status":"failed","production_ready":false}'); raise SystemExit(3)
