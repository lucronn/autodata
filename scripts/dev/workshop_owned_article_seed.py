"""Authored fixture seed for the fixed private M2A project; never payments/grants.

Host entry requires actual six-resource admission and an exact empty-auth receipt.
The inside mode runs only in the admitted ingestion container, with local env.
Partial failures preserve all stores and require review; no reset/delete/upsert.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time
import uuid

FIXTURES = Path(__file__).parent / 'fixtures/workshop_owned_article'
SOURCE_KEY = 'owned-fixture/article.json'
OWNED_TABLES = ('source_snapshots','extraction_evidence','vehicles','vehicle_identity_bases','vehicle_configurations','catalog_articles')
INSERT_TABLES = OWNED_TABLES
COMMERCE_TABLES = ('payment_events','dataset_requests','entitlements','dataset_projections','dataset_revisions','customer_accounts','auth_sessions','workshop_checkout_requests','workshop_orders')
MIGRATIONS = Path(__file__).resolve().parents[2] / 'db/migrations'
COUNT_TABLES = tuple(sorted(set(re.findall(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?([a-z_]+)', '\n'.join(p.read_text() for p in sorted(MIGRATIONS.glob('*.sql'))), re.I)) - {'schema_migrations'}))
TARGET = {'db_host':'postgres','database':'workshop_owned_article_m2a','db_user':'workshop_owned_article_m2a','s3_endpoint':'minio:9000','bucket':'workshop-owned-article-m2a-sources','commerce_mode':'disabled','env':'test'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_fixture(root=FIXTURES):
    root=Path(root)
    if root.is_symlink() or set(p.name for p in root.iterdir())!={'article.json','diagram.png'}:raise ValueError('fixture_files')
    for name in ('article.json','diagram.png'):
        if (root/name).is_symlink() or (root/name).stat().st_size>65536:raise ValueError('fixture_size')
    f=json.loads((root/'article.json').read_bytes())
    if f.get('version')!=1 or f.get('ownership')!='authored-synthetic' or set(f)!={'version','ownership','ids','vehicle','article','image'}:raise ValueError('fixture_ownership_schema')
    if set(f['ids'])!={'snapshot','evidence','vehicle','base','configuration','article'}:raise ValueError('fixture_ids')
    for key,value in f['ids'].items():
        if str(uuid.uuid5(uuid.NAMESPACE_URL,'autodata:owned-article-m2a:v1:'+key))!=value:raise ValueError('fixture_uuid')
    if f['vehicle']!={'make':'Owned','model':'Training Bench','year':2026,'region':'US','trim':'Fictional rig','engine':'1.0'}:raise ValueError('fixture_vehicle')
    article=f['article']
    if set(article)!={'article_id','title','kind','body','steps'} or article['article_id']!='owned-training-dial-v1' or article['kind']!='procedure' or len(article['steps'])!=2:raise ValueError('fixture_article')
    if any(not isinstance(article[k],str) or not article[k] or len(article[k])>1000 for k in ('title','body')):raise ValueError('fixture_text')
    for index,step in enumerate(article['steps'],1):
        if set(step)!={'number','heading','instructions'} or step['number']!=index or not isinstance(step['heading'],str) or not step['heading'] or len(step['instructions'])!=1 or not isinstance(step['instructions'][0],str) or not step['instructions'][0]:raise ValueError('fixture_steps')
    image=f['image'];raw=(root/'diagram.png').read_bytes()
    if set(image)!={'file','id','alt','sha256','width','height'} or image['file']!='diagram.png' or image['id']!='owned-diagram' or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR' or len(raw)<33:raise ValueError('fixture_png')
    if struct.unpack('>II',raw[16:24])!=(64,48) or (image['width'],image['height'])!=(64,48) or digest(raw)!=image['sha256']:raise ValueError('fixture_image_hash')
    return f


def target_errors(config):
    return [] if config==TARGET else ['target_contract']


def seed_preconditions(counts,object_count,marker,fixture_sha):
    errors=[]
    if set(counts)!=set(COUNT_TABLES):errors.append('table_set')
    if marker is not None and marker.get('fixture_sha256')!=fixture_sha:errors.append('fixture_marker')
    expected={name:(1 if name=='dataset_products' or marker is not None and name in OWNED_TABLES else 0) for name in COUNT_TABLES}
    if counts!=expected:errors.append('row_counts')
    if object_count!=(2 if marker is not None else 0):errors.append('object_count')
    return errors


def row_values(f,fixture_sha):
    """Only these six tables are writable; parameter values never become SQL."""
    ids=f['ids'];v=f['vehicle'];article=f['article'];locator='article.json#/article'
    j=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'))
    steps=[{**step,**({'image_ids':[f['image']['id']]} if index==0 else {})} for index,step in enumerate(article['steps'])]
    return {
      'source_snapshots':{'source_snapshot_id':ids['snapshot'],'adapter_name':'owned-synthetic-m2a','source_uri':'urn:autodata:owned-article-m2a:v1','source_version':'1','content_sha256':fixture_sha,'object_key':SOURCE_KEY,'license_metadata':j({'ownership':'authored-synthetic','external_exposure':False}),'retrieved_at':'2026-11-15T00:00:00Z'},
      'extraction_evidence':{'extraction_evidence_id':ids['evidence'],'source_snapshot_id':ids['snapshot'],'locator':locator,'artifact_key':SOURCE_KEY,'extracted_text':article['body'],'confidence':1,'reviewer_state':'approved'},
      'vehicles':{'vehicle_id':ids['vehicle'],'vehicle_key':'owned-training-bench-2026-us','make':v['make'],'model':v['model'],'model_year':v['year'],'region':v['region'],'source_snapshot_id':ids['snapshot'],'source_watermark':fixture_sha},
      'vehicle_identity_bases':{'vehicle_identity_base_id':ids['base'],'canonical_base_key':'owned-training-bench-2026-us','vehicle_id':ids['vehicle'],'make':v['make'],'model':v['model'],'model_year':v['year'],'region':v['region'],'source_snapshot_id':ids['snapshot'],'extraction_evidence_id':ids['evidence'],'source_locator':locator,'evidence_locator':locator,'evidence_confidence':1,'reviewer_state':'approved'},
      'vehicle_configurations':{'vehicle_configuration_id':ids['configuration'],'configuration_key':'owned-training-bench-2026-us-1.0-fictional','vehicle_identity_base_id':ids['base'],'vehicle_id':ids['vehicle'],'trim':v['trim'],'engine_displacement_l':v['engine'],'source_snapshot_id':ids['snapshot'],'extraction_evidence_id':ids['evidence'],'source_locator':locator,'evidence_locator':locator,'evidence_confidence':1,'reviewer_state':'approved'},
      'catalog_articles':{'catalog_article_id':ids['article'],'vehicle_id':ids['vehicle'],'vehicle_configuration_id':ids['configuration'],'article_id':article['article_id'],'bucket':'Owned training','title':article['title'],'sort_order':1,'source_snapshot_id':ids['snapshot'],'source_locator':locator,'evidence_locator':locator,'evidence_confidence':1,'body':article['body'],'steps':j(steps),'images':j([{'id':f['image']['id'],'alt':f['image']['alt'],'media_type':'image/png','storage_key':'procedure-images/'+f['image']['sha256']}]),'provider':'owned-synthetic-m2a','content_kind':'procedure','content_status':'content_complete','source_original':j(f),'normalized_document':j({'schema_version':1,'normalization_version':'ordered-article-v1','blocks':[]})}}


def inside(request):
    # Dependencies are intentionally resolved only inside the fixed cached image.
    import psycopg
    from psycopg import sql
    from minio import Minio
    from urllib3 import PoolManager
    from urllib3.util import Timeout
    config={'db_host':os.environ.get('AUTODATA_DB_ADDRESS','').split(':')[0],'database':os.environ.get('AUTODATA_POSTGRES_DB'),'db_user':os.environ.get('AUTODATA_POSTGRES_USER'),'s3_endpoint':os.environ.get('AUTODATA_S3_ENDPOINT'),'bucket':os.environ.get('AUTODATA_SOURCE_BUCKET'),'commerce_mode':os.environ.get('AUTODATA_COMMERCE_MODE'),'env':os.environ.get('AUTODATA_ENV')}
    if target_errors(config) or os.environ.get('AUTODATA_DB_ADDRESS')!='postgres:5432' or os.environ.get('AUTODATA_SOURCE_PERSIST')!='0':raise ValueError('inside_target')
    if Path(__file__).resolve()!=Path('/src/scripts/dev/workshop_owned_article_seed.py'):raise ValueError('inside_source')
    f=load_fixture();raw=(FIXTURES/'article.json').read_bytes();fixture_sha=digest(raw)
    if request.get('fixture_sha256')!=fixture_sha or request.get('action') not in ('inspect','seed'):raise ValueError('inside_request')
    s3=Minio(TARGET['s3_endpoint'],access_key=os.environ['AUTODATA_S3_ACCESS_KEY'],secret_key=os.environ['AUTODATA_S3_SECRET_KEY'],secure=False,http_client=PoolManager(timeout=Timeout(connect=2,read=5),retries=False))
    bucket=TARGET['bucket'];buckets=sorted(b.name for b in s3.list_buckets())
    if buckets!=[bucket]:raise ValueError('bucket_set')
    objects=sorted(item.object_name for item in s3.list_objects(bucket,recursive=True))
    db=psycopg.connect(host='postgres',port=5432,dbname=TARGET['database'],user=TARGET['db_user'],password=os.environ['AUTODATA_POSTGRES_PASSWORD'],connect_timeout=3,options='-c statement_timeout=5000 -c lock_timeout=2000')
    def counts(cur):
        actual={r[0] for r in cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        if actual!=set(COUNT_TABLES)|{'schema_migrations'}:raise ValueError('actual_table_set')
        return {name:cur.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0] for name in COUNT_TABLES}
    expected_rows=row_values(f,fixture_sha)
    with db:
      with db.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(27111542)')
        before=counts(cur)
        errors=seed_preconditions(before,len(objects),request.get('marker'),fixture_sha)
        if errors:raise ValueError('seed_preconditions')
        if request['action']=='seed' and request.get('marker') is None:
            for key,data,mime in [(SOURCE_KEY,raw,'application/json'),('procedure-images/'+f['image']['sha256'],(FIXTURES/'diagram.png').read_bytes(),'image/png')]:
                s3.put_object(bucket,key,io.BytesIO(data),len(data),content_type=mime)
            for table,values in expected_rows.items():
                cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),list(values.values()))
        after=counts(cur)
        if request['action']=='seed':
            if seed_preconditions(after,2,{'fixture_sha256':fixture_sha},fixture_sha):raise ValueError('seed_post_counts')
            # Compare every explicitly inserted column, not only PKs/counts.
            for table,values in expected_rows.items():
                columns=list(values)
                actual=cur.execute(sql.SQL('SELECT {} FROM {}').format(sql.SQL(',').join(map(sql.Identifier,columns)),sql.Identifier(table))).fetchall()
                if len(actual)!=1:raise ValueError('row_readback')
                for key,got in zip(columns,actual[0]):
                    expected=values[key]
                    if key=='retrieved_at':continue
                    if isinstance(got,(dict,list)):equal=got==json.loads(expected)
                    elif key.endswith('_id'):equal=str(got)==expected
                    elif key in ('confidence','evidence_confidence','engine_displacement_l'):equal=float(got)==float(expected)
                    else:equal=got==expected
                    if not equal:raise ValueError('row_readback')
    proof=[]
    objects=sorted(item.object_name for item in s3.list_objects(bucket,recursive=True))
    if request['action']=='seed':
        if objects!=sorted([SOURCE_KEY,'procedure-images/'+f['image']['sha256']]):raise ValueError('object_readback_set')
        for key,expected,mime in [(SOURCE_KEY,raw,'application/json'),('procedure-images/'+f['image']['sha256'],(FIXTURES/'diagram.png').read_bytes(),'image/png')]:
            obj=s3.get_object(bucket,key)
            try:data=obj.read(65537)
            finally:obj.close();obj.release_conn()
            metadata=s3.stat_object(bucket,key)
            if data!=expected or metadata.content_type!=mime:raise ValueError('object_readback')
            proof.append({'object_key':key,'mime':mime,'bytes':len(data),'sha256':digest(data)})
    return {'fixture_sha256':fixture_sha,'counts':after,'objects':proof,'object_count':len(objects),'row_references':f['ids'],'schema_references':['002_platform_spine','003_canonical_vehicle','004_normalized_source_bundle','014_normalized_article_content','015_vehicle_identity_resolution','016_catalog_article_configuration','023_catalog_article_images','031_catalog_article_classification','035_ordered_article_document'],'commerce_zero':all(after.get(k,0)==0 for k in COMMERCE_TABLES),'action':request['action']}


def auth_gate_errors(action,auth,manifest_hash,marker_hash,binding):
    if action=='inspect':return []
    if action!='seed':return ['action_contract']
    expected={'manifest_sha256':manifest_hash,'accepted_sha256':marker_hash,'binding':list(binding),'ready':True,'catalog_local_token':True,'missing_token_401':True,'wrong_role_403':True,'customer_session_401':True,'all_operational_rows_empty':True,'s3_objects_empty':True}
    return [] if auth==expected else ['empty_auth_gate']


def host(action):
    import workshop_owned_article_forwarder as f
    import workshop_owned_article_admission as a
    lock=f.acquire_lock()
    try:
        check,manifest_hash,marker_hash=f.make_checker();binding=check()
        accepted,_=f.read_private(f.PRIVATE/'accepted-state.json')
        auth=f.read_private(f.PRIVATE/'empty-auth-probe.json')[0] if action=='seed' else None
        if auth_gate_errors(action,auth,manifest_hash,marker_hash,binding):raise ValueError('empty_auth_gate')
        fixture_sha=digest((FIXTURES/'article.json').read_bytes());load_fixture()
        path=f.PRIVATE/'owned-seed.json';marker=None
        if path.exists():
            marker,_=f.read_private(path)
            if marker.get('manifest_sha256')!=manifest_hash or marker.get('accepted_sha256')!=marker_hash:raise ValueError('seed_binding')
        selected=[key for key,value in accepted['containers'].items() if value=='ingestion-http']
        result=subprocess.run(['/usr/bin/docker','--host','unix:///var/run/docker.sock','exec','-i',selected[0],'python','/src/scripts/dev/workshop_owned_article_seed.py','--inside'],input=json.dumps({'action':action,'fixture_sha256':fixture_sha,'marker':marker}),capture_output=True,text=True,timeout=40,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/nonexistent'})
        if result.returncode or len(result.stdout)>65536:raise ValueError('inside_failed_preserve_state')
        proof=json.loads(result.stdout);check()
        if proof['fixture_sha256']!=fixture_sha or not proof['commerce_zero']:raise ValueError('seed_receipt')
        proof.update(manifest_sha256=manifest_hash,accepted_sha256=marker_hash,binding=list(binding))
        if action=='seed':
            # Exclusive lock spans guard, inside operation and atomic receipt write.
            temp=f.PRIVATE/'owned-seed.pending'
            fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as out:json.dump(proof,out,sort_keys=True);out.write('\n')
            os.replace(temp,path)
        return proof
    finally:os.close(lock)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inside',action='store_true');parser.add_argument('--action',choices=('inspect','seed'),default='inspect');args=parser.parse_args()
    try:
        result=inside(json.loads(sys.stdin.read(65537))) if args.inside else host(args.action)
        print(json.dumps(result,sort_keys=True))
    except Exception:
        print(json.dumps({'ok':False,'error':'owned_seed_failed_preserve_state'}));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
