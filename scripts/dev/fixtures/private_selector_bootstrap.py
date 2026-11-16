"""Owned synthetic DB seeder; import is inert, execution is container-only."""
import json
import os
import re
import subprocess
import signal
import threading
import sys
import uuid
from pathlib import Path


def ownership(env):
    name = env.get('AUTODATA_POSTGRES_DB', '')
    if not (re.fullmatch(r'lifecycle_test_[a-f0-9]{32}', name)
            and env.get('AUTODATA_DB_ADDRESS') == 'postgres:5432'
            and env.get('AUTODATA_POSTGRES_USER') == 'lifecycle_test'
            and env.get('AUTODATA_POSTGRES_PASSWORD') == 'lifecycle_test_only'):
        raise ValueError('synthetic_database_required')
    return name


def bootstrap(env, *, connect, identifier, migrate, seed, hold, cleanup_bucket=None, emit_cleanup=None):
    """Adapters are injected for offline tests; only this exact DB is touched."""
    name = ownership(env)
    created = False
    try:
        with connect('lifecycle_fixture', autocommit=True) as db:
            db.execute(identifier('CREATE DATABASE {}', name))
        created = True
        migrate(name)
        metadata = seed(name)
        expected = {'configuration', 'foreign_configuration', 'owner', 'organization', 'entitlement'}
        if set(metadata) != expected or any(str(uuid.UUID(x)) != x for x in metadata.values()):
            raise ValueError('synthetic_seed_contract')
        hold({'database': name, **metadata})
    finally:
        # Both cleanups are attempted even when readiness/behavior failed.
        database_removed = bucket_removed = False
        try:
            if created:
                with connect('lifecycle_fixture', autocommit=True) as db:
                    db.execute(identifier('DROP DATABASE IF EXISTS {} WITH (FORCE)', name))
                    row = db.execute('SELECT count(*) FROM pg_database WHERE datname=%s', (name,)).fetchone()
                    if row[0] != 0: raise ValueError('synthetic_database_cleanup_unknown')
                database_removed = True
        finally:
            if created and cleanup_bucket is not None:
                bucket_removed = cleanup_bucket() is True
            if emit_cleanup is not None:
                emit_cleanup({'database_removed': database_removed, 'bucket_removed': bucket_removed})


def main():
    name = ownership(os.environ)  # Refuse before importing any database adapter.
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    sys.path[:0] = ['/app/workers/ingestion-python/src', '/app/workers/ingestion-python/tests']
    os.environ['AUTODATA_LIFECYCLE_TEST'] = '1'
    from lifecycle_support import Repository, seed_configuration, seed_vehicle

    def connect(database, **kwargs):
        return psycopg.connect(host='postgres', dbname=database, user='lifecycle_test',
                               password='lifecycle_test_only', connect_timeout=2, **kwargs)

    def migrate(database):
        result = subprocess.run(['/bin/sh', '/app/scripts/dev/migrate_sql.sh'],
            env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PGHOST': 'postgres',
                 'PGDATABASE': database, 'PGUSER': 'lifecycle_test', 'PGPASSWORD': 'lifecycle_test_only'},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        if result.returncode: raise ValueError('synthetic_migration_failed')
        if stopping.is_set(): raise ValueError('synthetic_bootstrap_stopped')

    def seed(database):
        repo = Repository(database)
        configuration = str(seed_configuration(repo, seed_vehicle(repo)))
        foreign = str(seed_configuration(repo, seed_vehicle(repo)))
        order, request, entitlement = [str(uuid.uuid4()) for _ in range(3)]
        with repo.connect() as conn:
            account = conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture',%s) RETURNING customer_account_id,personal_organization_id", (uuid.uuid4().hex,)).fetchone()
            owner, org = str(account['customer_account_id']), str(account['personal_organization_id'])
            product = conn.execute("SELECT dataset_product_id FROM dataset_products WHERE product_key='workshop-configuration-v1'").fetchone()['dataset_product_id']
            conn.execute("""INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at) VALUES(%s,%s,%s,%s,'US',%s,'workshop-v1',2000,'USD','acct_fixture',false,'price_fixture',%s,'paid',now())""", (order,owner,org,configuration,product,uuid.uuid4().hex))
            conn.execute("""INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id) VALUES(%s,%s,%s,'US','purchased','fast',%s,%s,'workshop-v1',%s)""", (request,product,configuration,order,uuid.uuid4().hex,org))
            conn.execute("""INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id) VALUES(%s,%s,%s,%s,'active',now(),%s,%s,'US',%s)""", (entitlement,org,request,uuid.uuid4().hex,owner,configuration,order))
            conn.execute('UPDATE workshop_orders SET entitlement_id=%s,dataset_request_id=%s WHERE order_id=%s', (entitlement,request,order))
        return {'configuration':configuration,'foreign_configuration':foreign,'owner':owner,
                'organization':org,'entitlement':entitlement}

    def hold(metadata):
        print(json.dumps(metadata, sort_keys=True), flush=True)
        # Graceful container stop requests cleanup even before client execution.
        stopping.wait()

    def cleanup_bucket():
        from minio import Minio
        from minio.deleteobjects import DeleteObject
        from urllib3 import PoolManager, Timeout
        run = name.removeprefix('lifecycle_test_')
        bucket = 'autodata-selector-fixture-' + run
        if os.environ.get('AUTODATA_SOURCE_BUCKET') != bucket:
            raise ValueError('synthetic_bucket_required')
        client = Minio('minio:9000', access_key='fixture', secret_key='fixture', secure=False,
            http_client=PoolManager(timeout=Timeout(connect=2, read=2), retries=False))
        if client.bucket_exists(bucket):
            errors = list(client.remove_objects(bucket, [DeleteObject(x.object_name, version_id=x.version_id)
                for x in client.list_objects(bucket, recursive=True, include_version=True)]))
            if errors: raise ValueError('synthetic_bucket_cleanup_unknown')
            client.remove_bucket(bucket)
        return not client.bucket_exists(bucket)

    bootstrap(os.environ, connect=connect,
              identifier=lambda pattern,n: sql.SQL(pattern).format(sql.Identifier(n)),
              migrate=migrate, seed=seed, hold=hold, cleanup_bucket=cleanup_bucket,
              emit_cleanup=lambda value: print(json.dumps({'cleanup': value}, sort_keys=True), flush=True))


if __name__ == '__main__': main()
