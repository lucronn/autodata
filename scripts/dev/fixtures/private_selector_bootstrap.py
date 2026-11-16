"""Owned synthetic DB seeder; import is inert, execution is container-only."""
import json
import os
import re
import subprocess
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


def bootstrap(env, *, connect, identifier, migrate, seed, hold):
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
        if created:
            with connect('lifecycle_fixture', autocommit=True) as db:
                db.execute(identifier('DROP DATABASE IF EXISTS {} WITH (FORCE)', name))


def main():
    name = ownership(os.environ)  # Refuse before importing any database adapter.
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
        # OpenStdin/StdinOnce are sealed by the host adapter; EOF cleans this DB.
        sys.stdin.buffer.read(1)

    bootstrap(os.environ, connect=connect,
              identifier=lambda pattern,n: sql.SQL(pattern).format(sql.Identifier(n)),
              migrate=migrate, seed=seed, hold=hold)


if __name__ == '__main__': main()
