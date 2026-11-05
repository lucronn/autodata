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
