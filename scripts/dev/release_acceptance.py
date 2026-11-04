#!/usr/bin/env python3
"""Bounded offline Workshop envelope diagnostics. No verification profiles enabled.

Candidate evidence is data only. The only subprocess is a read-only Git object
reader in this tool's owned checkout, with an isolated Git configuration.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import stat
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

CONTRACT = 'workshop-product-evidence-v1'
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_RAW_JSON_BYTES = 4 * 1024 * 1024
MAX_JSONL_RECORDS = 65536
MAX_XML_NODES = 20000
MAX_XML_DEPTH = 64
# Transport ceilings only; these do not enable any raw acceptance profile.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_REF = 'docs/agents/tasks/2026-11-03-production-release/r6-release.json'
GATES = ('deterministic_ci', 'contract_compatibility', 'schema_integrity',
         'source_provenance', 'data_quality', 'security', 'reliability', 'independent_review')
BINDINGS = ('source_manifest_artifact', 'migration_manifest_artifact',
            'production_images_artifact', 'sdk_provenance_artifact')
FIXTURE_SLOTS = ('fixture.identity', 'fixture.catalog', 'fixture.commerce', 'fixture.paid',
                 'fixture.browser_dto', 'fixture.browser_api', 'ci.required',
                 'security.application', 'images.production', 'review.independent')
STAGING_SLOTS = ('staging.population', 'staging.firebase_google', 'staging.stripe_test',
                 'staging.banks_model', 'staging.host_isolation', 'staging.restore_recovery',
                 'staging.alert_delivery', 'staging.independent_review')
SLOT_KINDS = dict(zip(FIXTURE_SLOTS + STAGING_SLOTS,
    ('identity', 'catalog', 'commerce', 'paid', 'browser_dto', 'browser_api', 'ci', 'security',
     'images', 'review', 'population', 'firebase_google', 'stripe_test', 'banks_model',
     'host_isolation', 'restore_recovery', 'alert_delivery', 'review')))
ARTIFACT_KINDS = ('manifest', 'host_receipt', 'collector_result', 'junit', 'measurement',
                  'http_observations', 'ci_response', 'ci_log', 'scan', 'review', 'provenance', 'raw')
COUNTS = ('identity', 'catalog', 'commerce', 'paid', 'browser_dto', 'browser_api', 'total')
FLAGS = ('fixture_verified', 'product_candidate_verified', 'staging_verified',
         'deployment_authorized', 'cutover_verified')

# Literal inventories copied from inspected producer inputs, never imported from
# candidate modules. These are internal parser contracts, not enabled profiles.
PAID_GO_ROOTS = (
    'TestPostgresPaidCatalogGrantBeforeWork',
    'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
    'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
    'TestPostgresPaidCatalogContextualMediaAndRevocation',
    'TestPostgresPaidCatalogHistoricalSourceAndRights',
    'TestPostgresPaidCatalogCustomerLegacyRoutesDenied')
PAID_CASE_IDS = tuple(root+'-'+bank for root in PAID_GO_ROOTS for bank in ('bankone', 'banktwo'))

PAID_GO_PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
PAID_PHASES = (
    ('before', 'selectors', 'unpaid', 'expired', 'paid_cold', 'unavailable'),
    ('isolated',), ('cold', 'before_prepare', 'scheduled', 'source_held', 'published', 'reopened'),
    ('media_final',), ('rights_before', 'rights_denied', 'rights_final'), ('before', 'denied', 'final'))
PAID_CASE_ASSERTIONS = (
    ('public_selectors_metadata_only', 'unpaid_denied_before_work', 'expired_session_denied_before_work',
     'paid_gets_observational', 'unavailable_grant_denied_before_work'),
    ('exact_scope_grants', 'owner_region_configuration_isolation', 'canonical_only', 'revoked_and_legacy_denied'),
    ('explicit_prepare_only', 'shared_article_job', 'actual_model_response_held', 'source_readable_during_hold',
     'canonical_reused_two_owners', 'canonical_steps_preserved', 'payment_grants_persist'),
    ('actual_s3_reader', 'invalid_media_zero_reader', 'current_grant_identity_rechecked',
     'stale_context_zero_reader', 'media_security_headers'),
    ('source_html_json_media', 'historical_source_selected', 'rights_denied_before_reader',
     'source_sanitizer_no_private_leak'),
    ('thirteen_routes_denied_before_work', 'unauthenticated_401', 'explicit_local_compatibility'))
PAID_MIGRATION_ASSERTIONS = ('fresh_manifest_applied_001_040', 'empty_replay_noop_001_040',
                            'populated_replay_noop_001_040')
PAID_COLLECTOR_FILES = ('workshop-paid-access-tests.xml', 'workshop-paid-access-pytest.stdout.log',
    'workshop-paid-access-pytest.stderr.log', 'runner-input-before.json', 'runner-input-after.json',
    'runner-git-before.json', 'runner-git-after.json')
PAID_CASE_FILES = ('case-pytest.stderr.log', 'case-pytest.stdout.log', 'case-tests.xml',
    'go-command.json', 'go-events.jsonl', 'go-measurement.json', 'go-stderr.log', 'measured-runtime.json',
    'migration-driver.sql', 'migration-driver.stderr') + tuple(
        'migration-'+phase+suffix for phase in ('fresh', 'replay-empty', 'replay-populated')
        for suffix in ('.json', '.rows.json', '.schema.sql', '.stderr', '.stdout')) + (
    'populated-before.rows.json', 'populated-before.schema.sql')
PAID_MISSING_FAMILIES = ('paid_source_pg_bindings', 'paid_http_media_rights',
    'paid_selector_work_and_model', 'paid_migration_replay', 'paid_runtime_image_inputs',
    'paid_host_and_input_provenance', 'paid_supervisor_commands_and_isolation',
    'paid_supervisor_authority')


# SQL payloads outside these six paid tables remain opaque in this layer.
PAID_PG_TABLES = ('schema_migrations', 'catalog_articles', 'canonical_articles',
    'canonical_article_source_revisions', 'canonical_article_source_observations',
    'canonical_article_revisions', 'canonical_article_reviews',
    'canonical_article_rewrite_attempts', 'source_fetch_jobs', 'publication_events',
    'source_snapshots', 'catalog_article_provider_scopes', 'catalog_article_index_pages',
    'canonical_article_aliases', 'customer_accounts', 'auth_sessions',
    'workshop_orders', 'workshop_checkout_requests')
PAID_ROW_FIELDS = {
    'customer_accounts': 'created_at customer_account_id firebase_project_id firebase_uid personal_organization_id status',
    'auth_sessions': 'created_at customer_account_id expires_at firebase_auth_time revoked_at session_token_hash',
    'entitlements': 'commerce_order_id configuration_id customer_account_id dataset_request_id entitlement_id granted_at organization_id payment_event_id provider_event_id region revoke_reason revoked_at status',
    'workshop_orders': 'amount_minor checkout_session_id checkout_url configuration_id created_at currency customer_account_id dataset_product_id dataset_request_id entitlement_id expected_price_id first_create_attempt_at last_reconciled_at livemode order_id organization_id paid_at payment_intent_id preparation_attempts preparation_index_job_ids preparation_last_error_code preparation_lease_expires_at preparation_lease_owner preparation_next_attempt_at preparation_state provider_expires_at provider_idempotency_key region revocation_reason_code revoked_at status stripe_account_id terms_version updated_at',
    'dataset_requests': 'correlation_id created_at dataset_product_id dataset_request_id idempotency_key lane organization_id processing_version region source_snapshot_id status updated_at vehicle_id vehicle_key',
    'dataset_projections': 'created_at dataset_product_id dataset_projection_id dataset_request_id entitlement_id',
}
PAID_ROW_NULLABLE = {
    'customer_accounts': (), 'auth_sessions': ('revoked_at',),
    'entitlements': ('commerce_order_id', 'configuration_id', 'customer_account_id',
        'payment_event_id', 'region', 'revoke_reason', 'revoked_at'),
    'workshop_orders': ('checkout_session_id', 'checkout_url', 'last_reconciled_at',
        'payment_intent_id', 'preparation_last_error_code', 'preparation_lease_expires_at',
        'preparation_lease_owner', 'provider_expires_at', 'revocation_reason_code', 'revoked_at'),
    'dataset_requests': ('source_snapshot_id', 'vehicle_id'), 'dataset_projections': (),
}
PAID_PG_COUNT_TABLES = {'article_jobs': 'source_fetch_jobs',
    'source_revisions': 'canonical_article_source_revisions',
    'canonical_revisions': 'canonical_article_revisions',
    'published_revisions': 'canonical_article_revisions',
    'publication_events': 'publication_events',
    'source_observations': 'canonical_article_source_observations'}

PAID_MIGRATION_MANIFEST = (
    '001_extensions.sql',
    '002_platform_spine.sql',
    '003_canonical_vehicle.sql',
    '004_normalized_source_bundle.sql',
    '005_preserve_duplicate_article_ids.sql',
    '006_backfill_article_source_locators.sql',
    '007_link_evidence_to_revision.sql',
    '008_publication_outbox_delivery.sql',
    '009_feedback_evidence_link.sql',
    '010_evidence_review_metadata.sql',
    '011_feedback_review_metadata.sql',
    '012_payment_fulfillment_reconciliation.sql',
    '013_dataset_request_ownership.sql',
    '014_normalized_article_content.sql',
    '015_vehicle_identity_resolution.sql',
    '016_catalog_article_configuration.sql',
    '017_knowledge_catalog_evidence_index.sql',
    '018_source_review_items.sql',
    '019_article_content_provenance.sql',
    '020_autoapi_article_fetch_jobs.sql',
    '021_autoapi_article_fetch_job_retries.sql',
    '022_job_plan_derived_articles.sql',
    '023_catalog_article_images.sql',
    '024_catalog_article_operations.sql',
    '025_chat_quote_procedure.sql',
    '026_chat_quote_operation_categories.sql',
    '027_chat_runtime_durable_state.sql',
    '028_vehicle_provider_mappings.sql',
    '029_vehicle_catalog_sync.sql',
    '030_vehicle_catalog_years.sql',
    '031_catalog_article_classification.sql',
    '032_catalog_article_source_original.sql',
    '033_catalog_scope_coverage.sql',
    '034_catalog_article_progress.sql',
    '035_ordered_article_document.sql',
    '036_source_fetch_jobs.sql',
    '037_article_source_lifecycle.sql',
    '038_article_transform_publication.sql',
    '039_production_identity_sessions.sql',
    '040_workshop_commerce.sql',
)

DTO_ENGINES = ('chromium', 'firefox', 'webkit')
DTO_SCENARIOS = (
    'bankone-cascade', 'banktwo-cascade', 'dual-bank-coverage', 'one-bank-unavailable',
    'pending-no-content', 'source-to-canonical', 'source-rewrite-failure', 'review-required',
    'warm-reload', 'selection-change-in-flight', 'source-review-change-in-flight',
    'cancel-and-retry', 'history-restore', 'document-only', 'missing-media', 'withdrawal',
    'keyboard-print-mobile', 'source-media-isolation', 'auth-cookie-reload',
    'google-popup-exchange', 'google-popup-blocked', 'google-popup-cancelled',
    'google-stale-reauthentication', 'firebase-memory-persistence', 'signin-unavailable-local',
    'signin-malformed-config', 'session-expired', 'session-blocked', 'auth-dependency-unavailable',
    'quote-exact-scope', 'terms-config-unavailable', 'checkout-double-click-retry',
    'checkout-processing-return', 'checkout-untrusted-return', 'checkout-expired',
    'already-owned-no-pay', 'library-pagination-and-states', 'paid-prepare-before-poll',
    'media-renew-coalesced', 'logout-and-bfcache-clear')
DTO_CASE_IDS = tuple((engine, scenario) for engine in DTO_ENGINES for scenario in DTO_SCENARIOS)
DTO_ARCHIVE_LIMITS = {'browser/evidence.json': MAX_RAW_JSON_BYTES,
                      'go-fixture.log': MAX_ARTIFACT_BYTES, 'ready.json': MAX_RAW_JSON_BYTES}


# Fixed source-content expectations from the independently reviewed DTO gate.
# These are not populated from candidate receipts and establish no CI authority.
DTO_SOURCE_EXPECTATIONS_SHA = '99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d'
DTO_SOURCE_INPUTS = {
    'apps/api-go/workshop_browser_fixture_test.go': '7cf50daeb190686dc55c33c90056b87a62eece96640759b180f1282a0a1a6dd2',
    'scripts/dev/fixtures/workshop_customer/firebase_transport.js': '96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63',
    'scripts/dev/fixtures/workshop_customer/hostile_source.json': '076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1',
    'scripts/dev/fixtures/workshop_customer/scenarios.json': '83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9',
    'scripts/dev/fixtures/workshop_customer/stripe_checkout.html': '26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083',
    'scripts/dev/workshop_browser_smoke.py': '45299888e56a78679148f575ac071856f0a3c1941faf059cd586ff2980069de8',
}
DTO_SOURCE_ASSETS = {
    'app.mjs': {'sha256': 'bc1b0d5e1c1181c1ff2a833ab8dc8c9ab88bf84e38b00b018ffa5fc9206e5ab5',
        'bytes': 37127},
    'article-read.mjs': {'sha256': 'fefa9ba05d05e8a48f8135d07a53f92d7ef32bf848db075005981848cc8d8f08',
        'bytes': 2507},
    'auth.mjs': {'sha256': 'ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2',
        'bytes': 7908},
    'catalog.mjs': {'sha256': 'cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52',
        'bytes': 11688},
    'commerce.mjs': {'sha256': 'be291187bdbd3ef7faeb9ace6c244eed8a0b28b0edc91f1e01881c7d32c9ae26',
        'bytes': 7321},
    'firebase-web.mjs': {'sha256': 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1',
        'bytes': 112641},
    'firebase-web.mjs.LEGAL.txt': {'sha256': '70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319',
        'bytes': 35536},
    'firebase-web.provenance.json': {'sha256': '0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a',
        'bytes': 2237},
    'index.html': {'sha256': '8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68',
        'bytes': 10868},
    'progress.mjs': {'sha256': 'dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48',
        'bytes': 1076},
    'styles.css': {'sha256': 'c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c',
        'bytes': 20773},
}
DTO_BROWSER_VERSIONS = {'chromium': '156.0.8078.4', 'firefox': '157.0', 'webkit': '27.2'}
DTO_ENGINE_REVISIONS = {'chromium': '1248', 'chromium-headless-shell': '1248',
    'firefox': '1555', 'webkit': '2370', 'ffmpeg': '1013', 'winldd': '1007', 'android': '1001'}
DTO_REQUEST_ROUTES = {
    ('GET', '/__/auth/handler'): ('apiKey', 'appName', 'authType', 'eventId', 'providerId', 'redirectUrl', 'scopes', 'v'),
    ('GET', '/auth/config'): (),
    ('GET', '/auth/session'): (),
    ('GET', '/c/pay/fixture'): (),
    ('GET', '/js/api.js'): ('onload',),
    ('GET', '/v1/catalog/images/v2.expired-one'): (),
    ('GET', '/v1/catalog/images/v2.expired-two'): (),
    ('GET', '/v1/catalog/images/v2.renewed-one'): (),
    ('GET', '/v1/catalog/images/v2.renewed-two'): (),
    ('GET', '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles'): (),
    ('GET', '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333'): (),
    ('GET', '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/source'): ('source_revision_id',),
    ('GET', '/v1/catalog/vehicles/22222222-2222-4222-8222-222222222222/articles'): (),
    ('GET', '/v1/catalog/years'): (),
    ('GET', '/v1/catalog/years/2024/makes'): ('region',),
    ('GET', '/v1/catalog/years/2024/makes/fixture-make/models'): ('region',),
    ('GET', '/v1/catalog/years/2024/makes/fixture-make/models/fixture-model/configurations'): ('region',),
    ('GET', '/v1/projects'): ('key',),
    ('GET', '/v1/workshop/library'): ('cursor', 'limit'),
    ('GET', '/v1/workshop/orders/55555555-5555-4555-8555-555555555555'): (),
    ('GET', '/v1/workshop/quote'): ('configuration_id', 'region'),
    ('GET', '/workshop/'): ('configuration', 'make', 'model', 'order', 'region', 'year'),
    ('GET', '/workshop/app.mjs'): (),
    ('GET', '/workshop/article-read.mjs'): (),
    ('GET', '/workshop/auth.mjs'): (),
    ('GET', '/workshop/catalog.mjs'): (),
    ('GET', '/workshop/commerce.mjs'): (),
    ('GET', '/workshop/firebase-web.mjs'): (),
    ('GET', '/workshop/fonts/InstrumentSans.ttf'): (),
    ('GET', '/workshop/progress.mjs'): (),
    ('GET', '/workshop/purchase-config.json'): (),
    ('GET', '/workshop/styles.css'): (),
    ('POST', '/auth/firebase/session'): (),
    ('POST', '/auth/logout'): (),
    ('POST', '/v1/accounts:lookup'): ('key',),
    ('POST', '/v1/accounts:signInWithIdp'): ('key',),
    ('POST', '/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/prepare'): (),
    ('POST', '/v1/token'): ('key',),
    ('POST', '/v1/workshop/checkout-sessions'): (),
}
DTO_MISSING_FAMILIES = (
    'dto_scenario_assertion_provenance', 'dto_request_origin_and_response_provenance',
    'dto_source_execution_binding', 'dto_browser_installation_and_process_provenance',
    'dto_tls_capture_provenance', 'dto_sdk_build_provenance',
    'dto_supervisor_commands_and_cleanup', 'dto_host_and_input_provenance',
    'dto_authenticated_ci_archive_provenance', 'dto_supervisor_and_reviewer_authority')


class ContractError(ValueError):
    """A static diagnostic code, never candidate-controlled text."""


def require(condition, code='invalid_contract'):
    if not condition:
        raise ContractError(code)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'invalid_object_keys')


def string(value):
    require(type(value) is str and bool(value) and value == value.strip(), 'invalid_string')
    require(not any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value), 'invalid_string')


def identifier(value):
    require(type(value) is str and re.fullmatch(r'[a-z][a-z0-9_.-]{0,95}', value) is not None, 'invalid_identifier')


def digest(value, length=64):
    require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is not None, 'invalid_digest')


def safe_ref(value):
    string(value)
    require('\\' not in value and ':' not in value and not value.startswith('/') and
            all(part not in ('', '.', '..') for part in value.split('/')), 'unsafe_reference')


def enum(value, choices):
    require(type(value) is str and value in choices, 'invalid_enum')


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid_integer')


def array(value):
    require(type(value) is list, 'invalid_array')


def unique(values):
    require(len(values) == len(set(values)), 'duplicate_identity')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw, limit, size_code, *, exact_floats=False):
    require(type(raw) is bytes and len(raw) <= limit, size_code)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result

    def nonfinite(_):
        raise ContractError('nonfinite_number')

    def number(token):
        # Keep the existing nonfinite/overflow rejection even in exact mode.
        value = float(token)
        require(math.isfinite(value), 'nonfinite_number')
        return Decimal(token) if exact_floats else value

    def walk(value):
        if type(value) is float:
            require(math.isfinite(value), 'nonfinite_number')
        elif type(value) is str:
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), 'invalid_utf8')
        elif type(value) is dict:
            for key, item in value.items():
                walk(key); walk(item)
        elif type(value) is list:
            for item in value:
                walk(item)
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite,
                            parse_float=number)
        walk(result)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, InvalidOperation, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_json') from None
    require(type(result) is dict, 'invalid_json_object')
    return result


def strict_json(raw):
    """The envelope and trusted task retain their separate 2 MiB ceiling."""
    return _strict_json(raw, MAX_MANIFEST_BYTES, 'manifest_size')


def strict_raw_json(raw):
    """Explicit internal raw JSON parser; it cannot enable a profile."""
    return _strict_json(raw, MAX_RAW_JSON_BYTES, 'raw_json_size')


def _strict_jsonl(raw, *, exact_floats=False):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RAW_JSON_BYTES, 'jsonl_size')
    require(raw.endswith(b'\n'), 'incomplete_jsonl')
    require(raw.count(b'\n') <= MAX_JSONL_RECORDS, 'jsonl_record_limit')
    lines = raw.split(b'\n')[:-1]
    require(len(lines) <= MAX_JSONL_RECORDS, 'jsonl_record_limit')
    return [_strict_json(line, MAX_RAW_JSON_BYTES, 'raw_json_size',
                         exact_floats=exact_floats) for line in lines]


def strict_jsonl(raw):
    """Bounded complete UTF-8 object records, without interpreting Go outcomes."""
    return _strict_jsonl(raw)


def strict_junit_xml(raw):
    """Bounded non-namespaced JUnit syntax, never DTD/entity resolution."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RAW_JSON_BYTES, 'xml_size')
    try:
        text = raw.decode('utf-8')
        require(re.search(r'<!\s*(?:DOCTYPE|ENTITY)|<!--', text, re.I) is None,
                'unsafe_xml_declaration')
        # XML declarations may only advertise the decoding used above.
        declaration = re.match(r'^\ufeff?(<\?xml\s+[^?]*\?>)', text)
        body = text
        if declaration:
            encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]', declaration[1])
            require(encoding is None or encoding[1].lower() == 'utf-8', 'xml_encoding')
            body = text[declaration.end():]
        require('<?' not in body, 'unsafe_xml_declaration')
        parser = ET.XMLPullParser(events=('start', 'end'))
        depth = nodes = 0
        root = None
        for offset in range(0, len(text), 4096):
            parser.feed(text[offset:offset+4096])
            for event, element in parser.read_events():
                if event == 'start':
                    depth += 1; nodes += 1
                    require(depth <= MAX_XML_DEPTH and nodes <= MAX_XML_NODES, 'xml_complexity')
                    require(type(element.tag) is str and '{' not in element.tag and
                            all('{' not in name for name in element.attrib), 'xml_namespace')
                    if root is None:
                        root = element
                else:
                    depth -= 1
        parser.close()
        require(root is not None and root.tag in ('testsuite', 'testsuites') and depth == 0,
                'invalid_junit_root')
        return root
    except (UnicodeError, ET.ParseError, RecursionError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_xml') from None


def strict_dto_archive(raw):
    """Read the fixed three-member DTO ZIP in memory; never extract paths.

    Only observed ZIP32 stored/deflated regular files without descriptors,
    comments or extra fields are understood. Complete bounded deflate streams,
    local/central metadata and CRC must agree; hidden expansion is rejected.
    """
    require(type(raw) is bytes and 22 <= len(raw) <= MAX_ARTIFACT_BYTES, 'zip_size')
    require(raw[-22:-18] == b'PK\x05\x06', 'invalid_zip')
    end = struct.unpack_from('<4s4H2IH', raw, len(raw)-22)
    require(end[1:5] == (0, 0, 3, 3) and end[7] == 0, 'invalid_zip_directory')
    require(end[5]+end[6] == len(raw)-22, 'invalid_zip_directory')
    try:
        # Parse every central record from bytes: ZipInfo can silently truncate
        # overclaimed extra/comment lengths and hide disk/reserved fields.
        directory_end = len(raw)-22
        cursor = end[6]
        records = []
        for _ in range(3):
            require(cursor+46 <= directory_end, 'invalid_zip_directory')
            fields = struct.unpack_from('<4s6H3I5H2I', raw, cursor)
            (signature, _made_by, extract, flags, method, dos_time, dos_date,
             crc, compressed_size, size, name_size, extra_size, comment_size,
             disk_start, _internal_attr, external_attr, local_offset) = fields
            frame_end = cursor+46+name_size+extra_size+comment_size
            require(signature == b'PK\x01\x02' and frame_end <= directory_end and
                    extra_size == comment_size == disk_start == 0, 'invalid_zip_directory')
            name = raw[cursor+46:cursor+46+name_size].decode('ascii')
            safe_ref(name)
            require(stat.S_IFMT(external_attr >> 16) in (0, stat.S_IFREG) and
                    not (external_attr & 0x10), 'unsafe_zip_member')
            # The raw 16-bit extraction field includes the reserved high byte.
            require(extract in (10, 20) and flags in (0, 0x800) and
                    method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                    (method != zipfile.ZIP_DEFLATED or extract == 20), 'unsupported_zip_format')
            # Calendar/clock validity is separate from exact local/central equality.
            datetime(1980+(dos_date >> 9), (dos_date >> 5) & 15, dos_date & 31,
                     dos_time >> 11, (dos_time >> 5) & 63, (dos_time & 31)*2)
            metadata = (extract, flags, method, dos_time, dos_date, crc, compressed_size, size)
            records.append((name, metadata, local_offset))
            cursor = frame_end
        require(cursor == directory_end, 'invalid_zip_directory')
        names = [name for name, _, _ in records]
        unique(names)
        require(set(names) == set(DTO_ARCHIVE_LIMITS), 'dto_archive_inventory')
        offsets = sorted(offset for _, _, offset in records)
        unique(offsets)
        require(offsets[0] == 0, 'invalid_zip_layout')
        result = {}
        for name, metadata, offset in records:
            extract, flags, method, dos_time, dos_date, crc, compressed_size, size = metadata
            limit = DTO_ARCHIVE_LIMITS[name]
            require(size <= limit and compressed_size <= MAX_ARTIFACT_BYTES, 'zip_expansion_limit')
            require(offset <= end[6]-30, 'invalid_zip_layout')
            header = struct.unpack_from('<4s5H3I2H', raw, offset)
            require(header[0] == b'PK\x03\x04' and header[1:9] == metadata and
                    header[10] == 0, 'zip_header_mismatch')
            start = offset+30+header[9]
            finish = start+compressed_size
            next_offset = min((item for item in offsets if item > offset), default=end[6])
            require(finish == next_offset and raw[offset+30:start] == name.encode('ascii'),
                    'invalid_zip_layout')
            compressed = raw[start:finish]
            if method == zipfile.ZIP_STORED:
                data = compressed
            else:
                decoder = zlib.decompressobj(-15)
                data = decoder.decompress(compressed, limit+1)
                require(len(data) <= limit and decoder.eof and not decoder.unconsumed_tail and
                        not decoder.unused_data, 'zip_expansion_limit')
            require(len(data) == size and zlib.crc32(data) == crc, 'zip_content_mismatch')
            result[name] = data
        require(sum(map(len, result.values())) <= MAX_EVIDENCE_BYTES, 'zip_expansion_limit')
        return result
    except (UnicodeError, ValueError, struct.error, zlib.error) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_zip') from None


def paid_case_identities(case_ids):
    """Identity inventory only; does not corroborate producer assertions."""
    array(case_ids)
    for case_id in case_ids:
        string(case_id)
    unique(case_ids)
    require(set(case_ids) == set(PAID_CASE_IDS), 'paid_case_inventory')
    return PAID_CASE_IDS


def dto_case_identities(case_ids):
    """Explicit scenario/engine pairs only; cannot substitute DTO for API21."""
    array(case_ids)
    pairs = []
    for item in case_ids:
        exact(item, ('browser', 'scenario'))
        enum(item['browser'], DTO_ENGINES); enum(item['scenario'], DTO_SCENARIOS)
        pairs.append((item['browser'], item['scenario']))
    unique(pairs)
    require(set(pairs) == set(DTO_CASE_IDS), 'dto_case_inventory')
    return DTO_CASE_IDS


def _paid_duration(start, finish, maximum):
    first, last = timestamp(start), timestamp(finish)
    delta = last[0]-first[0]
    whole_seconds = delta.days*86400+delta.seconds
    # Compare fractional pairs directly: Decimal context rounding must not hide
    # an arbitrarily small overshoot at the fixed whole-second boundary.
    require(first <= last and (whole_seconds < maximum or
            whole_seconds == maximum and last[1] <= first[1]), 'paid_deadline')
    return first, last


def _paid_assertions(value, keys):
    exact(value, keys)
    require(all(flag is True for flag in value.values()), 'paid_assertion_failed')


def _paid_junit(raw, case_ids, maximum):
    root = strict_junit_xml(raw)
    require(all(not (node.text or '').strip() and not (node.tail or '').strip()
                for node in root.iter()), 'paid_junit_structure')
    require(root.tag == 'testsuites' and root.attrib == {'name': 'pytest tests'} and
            len(root) == 1 and root[0].tag == 'testsuite', 'paid_junit_structure')
    suite = root[0]
    exact(suite.attrib, ('name', 'errors', 'failures', 'skipped', 'tests', 'time', 'timestamp', 'hostname'))
    require(suite.get('name') == 'pytest' and suite.get('tests') == str(len(case_ids)) and
            all(suite.get(key) == '0' for key in ('errors', 'failures', 'skipped')), 'paid_junit_outcome')
    timestamp(suite.get('timestamp')); string(suite.get('hostname'))
    def elapsed(value, bound):
        require(type(value) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value) is not None,
                'paid_junit_elapsed')
        require(Decimal(value) <= bound, 'paid_deadline')
    elapsed(suite.get('time'), maximum)
    observed = []
    for case in suite:
        require(case.tag == 'testcase' and len(case) == 0, 'paid_junit_outcome')
        exact(case.attrib, ('classname', 'name', 'time'))
        require(case.get('classname') == 'tests.test_paid_catalog_api_integration', 'paid_junit_identity')
        name = case.get('name')
        require(name.startswith('test_required_paid_catalog_access[') and name.endswith(']'),
                'paid_junit_identity')
        observed.append(name[len('test_required_paid_catalog_access['):-1])
        elapsed(case.get('time'), 120)
    unique(observed)
    require(set(observed) == set(case_ids), 'paid_junit_inventory')


def _paid_go_outcome(raw, name, started, finished):
    # Decimal preserves the JSON token before a float can round across 0 or 90.
    events = _strict_jsonl(raw, exact_floats=True)
    first, last = timestamp(started), timestamp(finished)
    package_started = root_running = root_passed = package_passed = False
    previous = first
    for index, event in enumerate(events):
        action = event.get('Action')
        require(action not in ('fail', 'skip'), 'paid_go_execution_failed')
        enum(action, ('start', 'run', 'output', 'pass'))
        keys = {'Time', 'Action', 'Package'}
        if 'Test' in event: keys.add('Test')
        if action == 'output': keys.add('Output')
        if action == 'pass': keys.add('Elapsed')
        exact(event, keys)
        require(event['Package'] == PAID_GO_PACKAGE and not package_passed, 'paid_go_identity')
        moment = timestamp(event['Time'])
        require(first <= previous <= moment <= last, 'paid_go_timestamp')
        previous = moment
        test = event.get('Test')
        if 'Test' in event: require(test == name, 'paid_go_identity')
        if action == 'start':
            require(index == 0 and test is None and not package_started, 'paid_go_order')
            package_started = True
        else:
            require(package_started, 'paid_go_order')
        if action == 'run':
            require(test == name and not root_running and not root_passed, 'paid_go_order')
            root_running = True
        elif action == 'output':
            require(type(event['Output']) is str and (test is None or root_running), 'paid_go_order')
        elif action == 'pass':
            duration = event['Elapsed']
            require(type(duration) in (int, Decimal) and 0 <= duration <= 90,
                    'paid_go_elapsed')
            if test is not None:
                require(root_running and not root_passed, 'paid_go_order')
                root_running = False; root_passed = True
            else:
                require(root_passed and index == len(events)-1, 'paid_go_order')
                package_passed = True
    require(root_passed and package_passed, 'paid_go_incomplete')


def inspect_paid_common(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                        input_manifest_sha256, host_before_sha256, profile_version):
    """Inspect paid v2 common outcomes, always returning incomplete/unavailable.

    Exact source/PG/HTTP/media/migration/image/provenance corroboration is not
    implemented here. Booleans and matching copies cannot verify those families.
    This API is deliberately unselected by every disabled CLI profile.
    """
    digest(candidate_sha, 40); digest(trusted_base_sha, 40); digest(profile_sha256)
    digest(input_manifest_sha256); digest(host_before_sha256)
    require(type(profile_version) is str and profile_version == 'paid-selector-v2', 'paid_profile_version')
    def read(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return store.read(store.by_ref[ref]['artifact_id'])
    def document(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return store.read_raw_json(store.by_ref[ref]['artifact_id'], candidate_sha=candidate_sha,
            trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256)
    def hashes(value, refs, prefix=''):
        exact(value, refs)
        for ref in refs:
            digest(value[ref])
            require(sha256(read(prefix+ref)) == value[ref], 'paid_raw_hash_mismatch')
    def version(value):
        require(type(value['schema_version']) is int and value['schema_version'] == 1,
                'paid_raw_schema_version')
        require(value['candidate_sha'] == candidate_sha, 'paid_candidate_mismatch')
    def identity(value):
        version(value)
        require(value['candidate_origin'] == 'coordinator-host-plain-clone' and
                value['host_before_sha256'] == host_before_sha256 and
                value['input_manifest_sha256'] == input_manifest_sha256, 'paid_provenance_mismatch')
    require(sha256(read('inputs.sha256.json')) == input_manifest_sha256 and
            sha256(read('host-before.json')) == host_before_sha256, 'paid_provenance_mismatch')
    collector = document('workshop-paid-access.json')
    exact(collector, ('artifact_sha256', 'assertion_results', 'candidate_origin', 'candidate_sha',
        'case_results', 'failures', 'finished_at', 'host_before_sha256', 'input_manifest_sha256',
        'passed', 'pytest_exit_code', 'pytest_test_count', 'runner_git_observation', 'schema_version',
        'started_at', 'timed_out'))
    identity(collector)
    require(collector['passed'] is True and collector['timed_out'] is False and collector['failures'] == [] and
            type(collector['pytest_exit_code']) is int and collector['pytest_exit_code'] == 0 and
            type(collector['pytest_test_count']) is int and collector['pytest_test_count'] == 12,
            'paid_collector_failed')
    require(type(collector['runner_git_observation']) is dict, 'paid_runner_observation')
    start, finish = _paid_duration(collector['started_at'], collector['finished_at'], 1806)
    _paid_assertions(collector['assertion_results'], PAID_CASE_IDS)
    exact(collector['case_results'], PAID_CASE_IDS)
    hashes(collector['artifact_sha256'], PAID_COLLECTOR_FILES)
    _paid_junit(read('workshop-paid-access-tests.xml'), PAID_CASE_IDS, 1806)
    observed = []; databases = []
    for index, name in enumerate(PAID_GO_ROOTS):
        for bank in ('bankone', 'banktwo'):
            case_id = name+'-'+bank
            prefix = 'paid-access/'+bank+'/'+name+'/'
            result = document(prefix+'result.json')
            exact(result, ('artifact_sha256', 'assertion_results', 'candidate_origin', 'candidate_sha',
                'failures', 'finished_at', 'fixture_database', 'go_exit_code', 'go_test_name',
                'host_before_sha256', 'input_manifest_sha256', 'passed', 'phase_snapshots', 'provider',
                'schema_version', 'started_at', 'timed_out'))
            identity(result)
            require(canonical(result) == canonical(collector['case_results'][case_id]), 'paid_embedded_result_mismatch')
            require(result['provider'] == bank and result['go_test_name'] == name, 'paid_case_identity')
            require(result['passed'] is True and result['timed_out'] is False and result['failures'] == [] and
                    type(result['go_exit_code']) is int and result['go_exit_code'] == 0, 'paid_case_failed')
            first, last = _paid_duration(result['started_at'], result['finished_at'], 120)
            require(start <= first <= last <= finish, 'paid_case_timestamp')
            database = result['fixture_database']
            require(type(database) is str and re.fullmatch(r'lifecycle_test_[a-f0-9]{32}', database) is not None,
                    'paid_database_identity')
            databases.append(database)
            exact(result['phase_snapshots'], PAID_PHASES[index])
            require(all(type(value) is dict for value in result['phase_snapshots'].values()), 'paid_phase_shape')
            _paid_assertions(result['assertion_results'], PAID_CASE_ASSERTIONS[index]+PAID_MIGRATION_ASSERTIONS)
            hashes(result['artifact_sha256'], PAID_CASE_FILES, prefix)
            _paid_junit(read(prefix+'case-tests.xml'), (case_id,), 120)
            command = document(prefix+'go-command.json')
            exact(command, ('argv', 'cwd'))
            require(command == {'argv': ['go', 'test', '-json', '-count=1', '-timeout=90s', '-run', '^'+name+'$', '.'],
                                'cwd': '/workspace/apps/api-go'}, 'paid_go_command')
            _paid_go_outcome(read(prefix+'go-events.jsonl'), name, result['started_at'], result['finished_at'])
            measurement = document(prefix+'go-measurement.json')
            exact(measurement, ('assertion_results', 'held_model_receipt', 'http_observations',
                'identity_checks', 'observed_views', 'phase_snapshots', 'reader_calls'))
            _paid_assertions(measurement['assertion_results'], PAID_CASE_ASSERTIONS[index])
            require(canonical(measurement['phase_snapshots']) == canonical(result['phase_snapshots']),
                    'paid_phase_mismatch')
            measured = document(prefix+'measured-runtime.json')
            exact(measured, ('candidate_sha', 'final_snapshot', 'fixture_database', 'go_test_name',
                'held_model_receipt', 'http_observations', 'identity_checks', 'migrations', 'observed_views',
                'provider', 'reader_calls', 'schema_version', 'service_probes', 'snapshots', 'worker_exits'))
            version(measured)
            require(measured['fixture_database'] == database and measured['go_test_name'] == name and
                    measured['provider'] == bank, 'paid_measurement_identity')
            require(canonical(measured['snapshots']) == canonical(result['phase_snapshots']), 'paid_phase_mismatch')
            for key in ('held_model_receipt', 'http_observations', 'identity_checks', 'observed_views', 'reader_calls'):
                require(canonical(measured[key]) == canonical(measurement[key]), 'paid_measurement_mismatch')
            integer(measured['identity_checks'], 1); integer(measured['reader_calls'])
            require(measured['held_model_receipt'] is None or type(measured['held_model_receipt']) is dict,
                    'paid_held_receipt_shape')
            array(measured['http_observations'])
            require(all(type(value) is dict for value in measured['http_observations']), 'paid_http_shape')
            views = measured['observed_views']
            if index in (0, 1, 5):
                require(views is None or type(views) is list and not views, 'paid_view_inventory')
            else:
                array(views)
                require(len(views) == (3 if index == 2 else 2) and all(type(value) is dict for value in views),
                        'paid_view_inventory')
            require(all(type(measured[key]) is dict for key in ('final_snapshot', 'migrations', 'service_probes')),
                    'paid_deferred_family_shape')
            exits = measured['worker_exits']; array(exits)
            require(len(exits) == (2 if index in (2, 3, 4) else 0), 'paid_worker_inventory')
            for receipt in exits:
                exact(receipt, ('alive_before_cleanup', 'exit_code', 'intentional_cleanup', 'kind', 'terminated'))
                require(receipt['kind'] == 'cli' and receipt['alive_before_cleanup'] is True and
                        receipt['intentional_cleanup'] is True and receipt['terminated'] is True and
                        type(receipt['exit_code']) is int and receipt['exit_code'] == -15, 'paid_worker_cleanup')
            observed.append(case_id)
    unique(databases)
    paid_case_identities(observed)
    store.recheck()
    return dict(status='unavailable', complete=False, profile_version=profile_version,
        candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha, observed_case_ids=observed,
        verified_case_ids=[], missing_validation_families=list(PAID_MISSING_FAMILIES),
        **{flag: False for flag in FLAGS})


def _paid_uuid(value):
    require(type(value) is str and re.fullmatch(
        r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', value) is not None,
        'paid_pg_uuid')


def _paid_pg_rows(paid):
    """Closed paid row shapes and owner/order scope; not full commerce semantics."""
    exact(paid, PAID_ROW_FIELDS)
    for table, fields in PAID_ROW_FIELDS.items():
        array(paid[table])
        for row in paid[table]:
            exact(row, fields.split())
            for key, value in row.items():
                if value is None and key in PAID_ROW_NULLABLE[table]:
                    continue
                if key in ('firebase_auth_time', 'amount_minor', 'preparation_attempts'):
                    integer(value)
                elif key == 'livemode':
                    require(type(value) is bool, 'paid_pg_scalar')
                elif key == 'preparation_index_job_ids':
                    array(value)
                    for item in value: _paid_uuid(item)
                    unique(value)
                else:
                    require(type(value) is str, 'paid_pg_scalar')
    accounts = paid['customer_accounts']
    ids = [row['customer_account_id'] for row in accounts]
    require(len(ids) == 2, 'paid_pg_accounts')
    for value in ids: _paid_uuid(value)
    unique(ids)
    organizations = [row['personal_organization_id'] for row in accounts]
    for value in organizations: _paid_uuid(value)
    unique(organizations)
    unique([row['firebase_uid'] for row in accounts])
    sessions = paid['auth_sessions']
    require(len(sessions) >= 2 and {row['customer_account_id'] for row in sessions} == set(ids),
            'paid_pg_sessions')
    tokens = []
    for row in sessions:
        token = row['session_token_hash']
        require(re.fullmatch(r'\\x[a-f0-9]{64}', token) is not None, 'paid_pg_session_hash')
        tokens.append(token)
        require(timestamp(row['created_at']) <= timestamp(row['expires_at']), 'paid_pg_session_time')
        if row['revoked_at'] is not None: timestamp(row['revoked_at'])
    unique(tokens)
    orders = {}
    for row in paid['workshop_orders']:
        _paid_uuid(row['order_id'])
        require(row['order_id'] not in orders and row['customer_account_id'] in ids,
                'paid_pg_orders')
        _paid_uuid(row['configuration_id'])
        orders[row['order_id']] = row
    active = set(); grants = []
    for row in paid['entitlements']:
        _paid_uuid(row['entitlement_id']); grants.append(row['entitlement_id'])
        enum(row['status'], ('active', 'revoked'))
        if row['customer_account_id'] is None:
            # The frozen negative legacy fixture intentionally lacks structured scope.
            require(row['configuration_id'] is None and row['commerce_order_id'] is None and
                    row['region'] is None, 'paid_pg_legacy_scope')
            continue
        require(row['customer_account_id'] in ids and row['region'] in ('US', 'CA'), 'paid_pg_grant')
        _paid_uuid(row['configuration_id'])
        order = orders.get(row['commerce_order_id'])
        require(order is not None and all(order[key] == row[key] for key in
            ('customer_account_id', 'configuration_id', 'region')), 'paid_pg_order_scope')
        require(order['status'] == 'paid' and order['amount_minor'] == 2000 and order['currency'] == 'USD'
                and order['livemode'] is False and order['stripe_account_id'] == 'acct_fixture'
                and order['expected_price_id'] == 'price_fixture', 'paid_pg_payment_binding')
        if row['status'] == 'active':
            scope = (row['customer_account_id'], row['configuration_id'], row['region'])
            require(scope not in active and row['revoked_at'] is None, 'paid_pg_active_scope')
            timestamp(row['granted_at']); active.add(scope)
    unique(grants)


def _paid_pg_snapshot(snapshot, provider, *, final=False):
    """Check snapshot boundaries and PG bindings, leaving source payloads opaque."""
    keys = ('article', 'asset_calls', 'counts', 'ensure', 'ensure_requests', 'grant_calls',
        'immutable_rows', 'immutable_sha256', 'model_calls', 'paid_rows', 'payment_calls',
        'provider_calls', 'provider_traces', 'proxy', 'selector_ensure', 'selector_ensure_requests',
        'source_calls', 'workers') + (() if final else ('reader_calls', 'identity_checks'))
    exact(snapshot, keys)
    for key in ('model_calls', 'grant_calls', 'payment_calls') + (() if final else ('reader_calls', 'identity_checks')):
        integer(snapshot[key])
    require(snapshot['payment_calls'] == 0, 'paid_pg_payment_work')
    for group in ('ensure', 'selector_ensure'):
        value = snapshot[group]; exact(value, ('entered', 'completed', 'active'))
        for item in value.values(): integer(item)
        require(value['entered'] == value['completed'] + value['active'] and value['active'] == 0,
                'paid_pg_unfinished_work')
        requests = snapshot[group+'_requests']; array(requests)
        require(len(requests) == value['entered'] and all(type(row) is dict and row for row in requests),
                'paid_pg_request_inventory')
    for group in ('provider_calls', 'source_calls', 'asset_calls'):
        exact(snapshot[group], ('bankone', 'banktwo'))
        for item in snapshot[group].values(): integer(item)
    traces = snapshot['provider_traces']; exact(traces, ('bankone', 'banktwo'))
    for bank, trace in traces.items():
        array(trace)
        require(all(type(item) is str and item.startswith('/') for item in trace) and
                len(trace) == snapshot['provider_calls'][bank], 'paid_pg_provider_trace')
    proxy = snapshot['proxy']
    exact(proxy, ('request_received', 'upstream_completed', 'downstream_completed',
                  'downstream_waiting', 'response_captured', 'errors'))
    for key in ('request_received', 'upstream_completed', 'downstream_completed', 'downstream_waiting'):
        integer(proxy[key])
    require(type(proxy['response_captured']) is bool and proxy['errors'] == [] and
            proxy['request_received'] >= proxy['upstream_completed'] >= proxy['downstream_completed']
            and proxy['downstream_waiting'] <= proxy['upstream_completed'] - proxy['downstream_completed'],
            'paid_pg_proxy')
    array(snapshot['workers'])
    for worker in snapshot['workers']:
        exact(worker, ('kind', 'alive', 'exit_code'))
        require(worker['kind'] == 'cli' and type(worker['alive']) is bool and
            (worker['exit_code'] is None if worker['alive'] else type(worker['exit_code']) is int),
            'paid_pg_worker')
    rows = snapshot['immutable_rows']; exact(rows, PAID_PG_TABLES)
    for values in rows.values():
        array(values)
        require(all(type(row) is dict and row for row in values), 'paid_pg_row_shape')
    digest(snapshot['immutable_sha256'])
    # Frozen producer rows_digest uses JSON's default spacing and ASCII escaping.
    raw_hash = sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode('utf-8'))
    require(raw_hash == snapshot['immutable_sha256'], 'paid_pg_row_hash')
    article = snapshot['article']
    require(type(article) is dict, 'paid_pg_article')
    article_id = article.get('canonical_article_id'); _paid_uuid(article_id)
    require(article.get('provider_slug') == provider, 'paid_pg_provider')
    article_ids = []
    for row in rows['canonical_articles']:
        value = row.get('canonical_article_id'); _paid_uuid(value); article_ids.append(value)
        require(row.get('provider_slug') in ('bankone', 'banktwo'), 'paid_pg_provider')
    unique(article_ids)
    selected = [row for row in rows['canonical_articles'] if row['canonical_article_id'] == article_id]
    require(len(selected) == 1 and selected[0]['provider_slug'] == provider, 'paid_pg_article')
    exact(snapshot['counts'], PAID_PG_COUNT_TABLES)
    for key, table in PAID_PG_COUNT_TABLES.items():
        integer(snapshot['counts'][key])
        for row in rows[table]:
            require('canonical_article_id' in row, 'paid_pg_count_row')
            if row['canonical_article_id'] is not None or table != 'source_fetch_jobs':
                _paid_uuid(row['canonical_article_id'])
            if table == 'source_fetch_jobs':
                require(type(row.get('job_kind')) is str, 'paid_pg_count_row')
            if table == 'canonical_article_revisions':
                require(type(row.get('status')) is str, 'paid_pg_count_row')
        counted = [row for row in rows[table] if row['canonical_article_id'] == article_id]
        if key == 'article_jobs': counted = [row for row in counted if row['job_kind'] == 'article']
        if key == 'published_revisions': counted = [row for row in counted if row['status'] == 'published']
        require(len(counted) == snapshot['counts'][key], 'paid_pg_count_binding')
    _paid_pg_rows(snapshot['paid_rows'])
    for table in ('customer_accounts', 'auth_sessions', 'workshop_orders'):
        require(canonical(rows[table]) == canonical(snapshot['paid_rows'][table]), 'paid_pg_paid_row_seam')


def inspect_paid_pg_snapshots(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                              input_manifest_sha256, host_before_sha256, profile_version):
    """An explicit incomplete PG binding layer, never selected by disabled CLI."""
    result = inspect_paid_common(store, candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
        profile_sha256=profile_sha256, input_manifest_sha256=input_manifest_sha256,
        host_before_sha256=host_before_sha256, profile_version=profile_version)
    def document(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return store.read_raw_json(store.by_ref[ref]['artifact_id'], candidate_sha=candidate_sha,
            trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256)
    observed = 0
    for name in PAID_GO_ROOTS:
        for bank in ('bankone', 'banktwo'):
            prefix = 'paid-access/'+bank+'/'+name+'/'
            measured = document(prefix+'measured-runtime.json')
            probes = measured['service_probes']; exact(probes, ('postgres', 's3', 'nats'))
            pg = probes['postgres']; exact(pg, ('database', 'server_version_num', 'user'))
            require(pg['database'] == measured['fixture_database'] and pg['user'] == 'lifecycle_test' and
                type(pg['server_version_num']) is int and 170000 <= pg['server_version_num'] < 180000,
                'paid_pg_probe')
            s3 = probes['s3']; exact(s3, ('bucket', 'roundtrip_ok'))
            require(s3['roundtrip_ok'] is True and type(s3['bucket']) is str and
                re.fullmatch(r'lifecycle-[a-f0-9]{32}', s3['bucket']) is not None, 'paid_s3_probe')
            exact(probes['nats'], ('jetstream_account_info_ok',))
            require(probes['nats']['jetstream_account_info_ok'] is True, 'paid_nats_probe')
            for snapshot in measured['snapshots'].values():
                _paid_pg_snapshot(snapshot, bank); observed += 1
            final = measured['final_snapshot']; _paid_pg_snapshot(final, bank, final=True); observed += 1
            raw_rows = document(prefix+'migration-replay-populated.rows.json')
            require(canonical(raw_rows) == canonical(final['immutable_rows']), 'paid_pg_final_row_seam')
    store.recheck()
    result['observed_pg_snapshot_count'] = observed
    result['missing_validation_families'].append('paid_pg_row_semantics')
    return result


def _paid_migration_rows(rows):
    """Closed dump containers and ledger; other SQL row payloads remain opaque."""
    exact(rows, PAID_PG_TABLES)
    for values in rows.values():
        array(values)
        require(all(type(row) is dict and row for row in values), 'paid_migration_row_shape')
    ledger = rows['schema_migrations']
    require(len(ledger) == 40, 'paid_migration_ledger_inventory')
    versions = []
    for row in ledger:
        exact(row, ('version', 'applied_at'))
        require(type(row['version']) is str, 'paid_migration_version')
        versions.append(row['version']); timestamp(row['applied_at'])
    unique(versions)
    require(sorted(versions) == [name[:-4] for name in PAID_MIGRATION_MANIFEST],
            'paid_migration_ledger_inventory')


def inspect_paid_migration_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
        input_manifest_sha256, host_before_sha256, profile_version, expected_driver_sha256):
    """Check fixed v2 receipt consistency, never SQL execution or trust authority."""
    digest(expected_driver_sha256)
    result = inspect_paid_pg_snapshots(store, candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
        profile_sha256=profile_sha256, input_manifest_sha256=input_manifest_sha256,
        host_before_sha256=host_before_sha256, profile_version=profile_version)
    def read(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return store.read(store.by_ref[ref]['artifact_id'])
    def document(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return store.read_raw_json(store.by_ref[ref]['artifact_id'], candidate_sha=candidate_sha,
            trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256)
    def text(raw):
        require(type(raw) is bytes and 0 < len(raw) <= MAX_ARTIFACT_BYTES and b'\0' not in raw,
                'paid_migration_text')
        try: return raw.decode('utf-8')
        except UnicodeError: raise ContractError('paid_migration_text') from None
    def row_hash(rows):
        return sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode('utf-8'))
    observed = 0
    for name in PAID_GO_ROOTS:
        for bank in ('bankone', 'banktwo'):
            prefix = 'paid-access/'+bank+'/'+name+'/'
            migrations = document(prefix+'measured-runtime.json')['migrations']
            exact(migrations, ('manifest', 'driver_sha256', 'driver_exit_code', 'runner_sha256',
                               'fresh', 'empty_replay', 'populated_replay'))
            # Retained producer metadata only; source/runner authority remains missing.
            digest(migrations['runner_sha256'])
            require(migrations['manifest'] == list(PAID_MIGRATION_MANIFEST), 'paid_migration_manifest')
            require(type(migrations['driver_exit_code']) is int and migrations['driver_exit_code'] == 0,
                    'paid_migration_driver_exit')
            driver = read(prefix+'migration-driver.sql'); text(driver)
            require(migrations['driver_sha256'] == expected_driver_sha256 == sha256(driver),
                    'paid_migration_driver_hash')
            fresh_hashes = fresh_ledger = fresh_schema = None
            for phase, stem in (('fresh', 'fresh'), ('empty_replay', 'replay-empty'),
                                ('populated_replay', 'replay-populated')):
                entry = migrations[phase]
                command_keys = ('exit_code', 'timed_out', 'applied', 'skipped')
                hash_keys = tuple(kind+'_after_sha256' for kind in ('ledger', 'schema', 'data'))
                if phase != 'fresh': hash_keys += tuple(kind+'_before_sha256' for kind in ('ledger', 'schema', 'data'))
                exact(entry, command_keys+hash_keys)
                require(type(entry['exit_code']) is int and entry['exit_code'] == 0 and
                        entry['timed_out'] is False, 'paid_migration_command')
                expected = list(PAID_MIGRATION_MANIFEST)
                require(entry['applied'] == (expected if phase == 'fresh' else []) and
                        entry['skipped'] == ([] if phase == 'fresh' else expected), 'paid_migration_vector')
                for key in hash_keys: digest(entry[key])
                saved = document(prefix+'migration-'+stem+'.json'); exact(saved, command_keys)
                require(canonical(saved) == canonical({key:entry[key] for key in command_keys}),
                        'paid_migration_saved_command')
                markers = {'APPLIED': [], 'SKIPPED': []}
                stdout = read(prefix+'migration-'+stem+'.stdout')
                require(stdout.endswith(b'\n'), 'paid_migration_stdout')
                for line in text(stdout).split('\n'):
                    if 'AUTODATA_' not in line: continue
                    match = re.fullmatch(r'AUTODATA_(APPLIED|SKIPPED) ([a-z0-9_]+\.sql)', line)
                    require(match is not None, 'paid_migration_stdout')
                    markers[match[1]].append(match[2])
                require(markers['APPLIED'] == entry['applied'] and markers['SKIPPED'] == entry['skipped'],
                        'paid_migration_stdout')
                rows = document(prefix+'migration-'+stem+'.rows.json'); _paid_migration_rows(rows)
                if phase != 'populated_replay':
                    require(all(not values for table, values in rows.items() if table != 'schema_migrations'),
                            'paid_migration_nonempty_fresh')
                schema = read(prefix+'migration-'+stem+'.schema.sql'); text(schema)
                hashes = dict(ledger=row_hash(rows['schema_migrations']), schema=sha256(schema), data=row_hash(rows))
                require(all(entry[kind+'_after_sha256'] == value for kind,value in hashes.items()),
                        'paid_migration_after_hash')
                if phase == 'fresh':
                    fresh_hashes, fresh_ledger, fresh_schema = hashes, rows['schema_migrations'], schema
                else:
                    require(all(entry[kind+'_before_sha256'] == value for kind,value in hashes.items()),
                            'paid_migration_before_hash')
                require(canonical(rows['schema_migrations']) == canonical(fresh_ledger) and schema == fresh_schema,
                        'paid_migration_ledger_schema_drift')
                if phase == 'empty_replay':
                    require(hashes == fresh_hashes, 'paid_migration_empty_replay_drift')
                if phase == 'populated_replay':
                    before = document(prefix+'populated-before.rows.json'); _paid_migration_rows(before)
                    before_schema = read(prefix+'populated-before.schema.sql'); text(before_schema)
                    require(canonical(before) == canonical(rows) and before_schema == schema,
                            'paid_migration_populated_replay_drift')
                observed += 1
    store.recheck()
    result['observed_migration_phase_count'] = observed
    result['missing_validation_families'].extend(('paid_migration_schema_semantics',
                                                 'paid_migration_driver_provenance'))
    return result


def _paid_selector_requests(requests, first, last):
    """Closed metadata-only v2 requests, with exact decimal duration bounds."""
    array(requests)
    require(len(requests) == 3, 'paid_selector_request_inventory')
    scopes = []; keys = []
    for request in requests:
        exact(request, ('completed', 'duration_seconds', 'finished_at', 'payload',
                        'request_id', 'scope', 'started_at', 'status'))
        require(request['completed'] is True and type(request['status']) is int and
                request['status'] == 200 and request['request_id'] == '', 'paid_selector_request')
        duration = request['duration_seconds']
        require(type(duration) in (int, Decimal) and 0 <= duration <= 120,
                'paid_selector_duration')
        require(first <= timestamp(request['started_at']) <= timestamp(request['finished_at']) <= last,
                'paid_selector_timestamp')
        scope = request['scope']; enum(scope, ('makes', 'models', 'configurations'))
        fields = ('scope', 'year', 'region', 'idempotency_key')
        if scope != 'makes': fields += ('make',)
        if scope == 'configurations': fields += ('model',)
        payload = request['payload']; exact(payload, fields)
        require(payload['scope'] == scope and type(payload['year']) is int and
                payload['year'] == 2024 and payload['region'] == 'US' and
                (scope == 'makes' or payload['make'] == 'example') and
                (scope != 'configurations' or payload['model'] == 'car'), 'paid_selector_payload')
        key = payload['idempotency_key']
        require(type(key) is str and re.fullmatch(r'catalog-hydration:[a-f0-9]{24}', key) is not None,
                'paid_selector_idempotency_key')
        scopes.append(scope); keys.append(key)
    require(set(scopes) == {'makes', 'models', 'configurations'}, 'paid_selector_request_inventory')
    unique(keys)


def inspect_paid_selector_work(store, *, candidate_sha, trusted_base_sha, profile_sha256,
        input_manifest_sha256, host_before_sha256, expected_driver_sha256,
        profile_version='paid-selector-v2'):
    """Two-case selector/work receipt consistency; never acceptance or authority."""
    result = inspect_paid_migration_receipts(store, candidate_sha=candidate_sha,
        trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256,
        input_manifest_sha256=input_manifest_sha256, host_before_sha256=host_before_sha256,
        expected_driver_sha256=expected_driver_sha256, profile_version=profile_version)

    def document(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        # Preserve all reserved-identity checks and confined reopen/recheck rules.
        # Only this explicit layer opts into exact decimal JSON number tokens.
        return ArtifactStore._read_bound_json(store, store.by_ref[ref]['artifact_id'],
            lambda raw: _strict_json(raw, MAX_RAW_JSON_BYTES, 'raw_json_size', exact_floats=True),
            candidate_sha, trusted_base_sha, profile_sha256)

    routes = {'/v1/catalog/makes?year=2024',
              '/v1/catalog/models?year=2024&make=example',
              '/v1/catalog/configurations?year=2024&make=example&model=car'}
    phases = ('before', 'selectors', 'unpaid', 'expired', 'paid_cold', 'unavailable')
    zero = dict(entered=0, completed=0, active=0)
    observed = []; snapshot_count = 0
    name = 'TestPostgresPaidCatalogGrantBeforeWork'
    collector = document('workshop-paid-access.json')
    for bank in ('bankone', 'banktwo'):
        prefix = 'paid-access/'+bank+'/'+name+'/'
        measured = document(prefix+'measured-runtime.json')
        case = document(prefix+'result.json')
        measurement = document(prefix+'go-measurement.json')
        copies = (case['phase_snapshots'], measurement['phase_snapshots'],
                  collector['case_results'][name+'-'+bank]['phase_snapshots'])
        first, last = timestamp(case['started_at']), timestamp(case['finished_at'])
        snapshots = measured['snapshots']; selectors = snapshots['selectors']
        previous_grants = previous_identity = 0
        for phase in phases+('final_snapshot',):
            final = phase == 'final_snapshot'; before = phase == 'before'
            snapshot = measured['final_snapshot'] if final else snapshots[phase]
            require(snapshot['ensure'] == zero and snapshot['ensure_requests'] == [] and
                    all(value == 0 for value in snapshot['counts'].values()) and
                    all(snapshot[key] == 0 for key in ('model_calls', 'payment_calls')) and
                    all(value == 0 for key in ('source_calls', 'asset_calls')
                        for value in snapshot[key].values()) and snapshot['workers'] == [],
                    'paid_selector_article_work')
            proxy = snapshot['proxy']
            require(all(proxy[key] == 0 for key in ('request_received', 'upstream_completed',
                        'downstream_completed', 'downstream_waiting')) and
                    proxy['response_captured'] is False and proxy['errors'] == [], 'paid_selector_proxy_work')
            if not final:
                require(snapshot['reader_calls'] == 0, 'paid_selector_reader_work')
                require(snapshot['grant_calls'] >= previous_grants and
                        snapshot['identity_checks'] >= previous_identity, 'paid_selector_progression')
                previous_grants, previous_identity = snapshot['grant_calls'], snapshot['identity_checks']
            else:
                require(snapshot['grant_calls'] == previous_grants, 'paid_selector_final_grants')
            if phase == 'selectors':
                require(snapshot['grant_calls'] == snapshot['identity_checks'] == 0,
                        'paid_selector_metadata_identity')
            expected_count = 0 if before else 3
            require(snapshot['selector_ensure'] == dict(entered=expected_count,
                    completed=expected_count, active=0), 'paid_selector_request_inventory')
            requests = snapshot['selector_ensure_requests']
            if before:
                require(requests == [], 'paid_selector_request_inventory')
            else:
                _paid_selector_requests(requests, first, last)
                # Each item has been typed above; compare parsed numeric values
                # directly rather than converting Decimals to binary floats.
                require(requests == selectors['selector_ensure_requests'], 'paid_selector_request_drift')
            if not final:
                require(all(requests == copy[phase]['selector_ensure_requests'] for copy in copies),
                        'paid_selector_copy_drift')
            for provider in ('bankone', 'banktwo'):
                trace = snapshot['provider_traces'][provider]
                require(snapshot['provider_calls'][provider] == expected_count and
                        len(trace) == expected_count and set(trace) == (set() if before else routes),
                        'paid_selector_provider_routes')
                if not before:
                    require(trace == selectors['provider_traces'][provider], 'paid_selector_trace_drift')
            snapshot_count += 1
        observed.append(name+'-'+bank)
    store.recheck()
    result['observed_selector_case_ids'] = observed
    result['observed_selector_snapshot_count'] = snapshot_count
    result['missing_validation_families'].extend(('paid_selector_http_outcomes',
                                                 'paid_selector_request_provenance'))
    return result


def _dto_member_identity(value, candidate_sha, trusted_base_sha, profile_sha256):
    """Apply the existing reserved-identity rule to parsed archive members."""
    expected = dict(candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
                    profile_sha256=profile_sha256)
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is dict:
            for key, nested in item.items():
                if key in expected:
                    require(type(nested) is str and nested == expected[key], 'raw_identity_mismatch')
                pending.append(nested)
        elif type(item) is list:
            pending.extend(item)


def _dto_query_text(value, maximum):
    require(type(value) is str and not any(char in '\x00\r\n' for char in value), 'dto_query_text')
    require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), 'dto_query_text')
    require(len(value.encode('utf-8')) <= maximum, 'dto_query_text')


def _dto_requests(value, sdk_requests):
    array(value)
    require(len(value) <= 256, 'dto_request_limit')
    sdk_count = 0
    for request in value:
        exact(request, ('method', 'path', 'query'))
        method, path = request['method'], request['path']
        require(type(method) is str and type(path) is str and
                (method, path) in DTO_REQUEST_ROUTES, 'dto_request_route')
        query = request['query']
        require(type(query) is dict and len(query) <= 16, 'dto_query_shape')
        require(set(query) <= set(DTO_REQUEST_ROUTES[(method, path)]), 'dto_query_keys')
        for key, values in query.items():
            _dto_query_text(key, 64)
            array(values)
            require(1 <= len(values) <= 8, 'dto_query_values')
            for item in values:
                _dto_query_text(item, 512)
        sdk_count += path == '/workshop/firebase-web.mjs'
    integer(sdk_requests)
    require(sdk_requests <= 256 and sdk_requests == sdk_count, 'dto_sdk_requests')
    return len(value)


def inspect_dto_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                         profile_version='dto-fixture-v1'):
    """DTO120 receipt consistency only; no execution or verification authority."""
    digest(candidate_sha, 40); digest(trusted_base_sha, 40); digest(profile_sha256)
    require(type(profile_version) is str and profile_version == 'dto-fixture-v1', 'dto_profile_version')
    require('dto-artifact.zip' in store.by_ref, 'dto_missing_raw')
    record = store.by_ref['dto-artifact.zip']
    require(record['kind'] == 'raw', 'dto_archive_kind')
    members = strict_dto_archive(store.read(record['artifact_id']))
    documents = []
    for ref in ('browser/evidence.json', 'ready.json'):
        value = _strict_json(members[ref], MAX_RAW_JSON_BYTES, 'raw_json_size', exact_floats=True)
        _dto_member_identity(value, candidate_sha, trusted_base_sha, profile_sha256)
        documents.append(value)
    evidence, ready = documents
    exact(evidence, ('browser_versions', 'candidate_sha', 'engine_revisions', 'input_sha256',
        'mode', 'playwright_version', 'provenance', 'results', 'sdk_sha256', 'version'))
    require(evidence['version'] == 'v1' and evidence['mode'] == 'dto-fixture' and
            evidence['candidate_sha'] == candidate_sha and evidence['playwright_version'] == '1.64.1',
            'dto_evidence_identity')
    exact(evidence['browser_versions'], DTO_BROWSER_VERSIONS)
    exact(evidence['engine_revisions'], DTO_ENGINE_REVISIONS)
    require(evidence['browser_versions'] == DTO_BROWSER_VERSIONS and
            evidence['engine_revisions'] == DTO_ENGINE_REVISIONS, 'dto_browser_metadata')
    exact(evidence['input_sha256'], DTO_SOURCE_INPUTS)
    require(evidence['input_sha256'] == DTO_SOURCE_INPUTS, 'dto_source_inputs')
    provenance = evidence['provenance']
    exact(provenance, ('assets', 'certificate_sha256'))
    exact(provenance['assets'], DTO_SOURCE_ASSETS)
    for name, expected in DTO_SOURCE_ASSETS.items():
        asset = provenance['assets'][name]
        exact(asset, ('sha256', 'bytes'))
        integer(asset['bytes'])
        require(asset == expected, 'dto_source_assets')
    sdk_hash = DTO_SOURCE_ASSETS['firebase-web.mjs']['sha256']
    digest(provenance['certificate_sha256'])
    exact(ready, ('certificate_sha256', 'kind', 'origin', 'sdk_sha256', 'version'))
    require(ready['version'] == 'v1' and ready['kind'] == 'dto-fixture' and
            ready['sdk_sha256'] == evidence['sdk_sha256'] == sdk_hash, 'dto_readiness_identity')
    digest(ready['certificate_sha256'])
    require(ready['certificate_sha256'] == provenance['certificate_sha256'], 'dto_certificate_copy')
    origin = ready['origin']
    require(type(origin) is str, 'dto_readiness_origin')
    match = re.fullmatch(r'https://127\.0\.0\.1:([1-9][0-9]{0,4})', origin)
    require(match is not None and int(match[1]) <= 65535, 'dto_readiness_origin')
    rows = evidence['results']
    array(rows)
    require(len(rows) == 120, 'dto_case_inventory')
    identities = []; request_count = 0
    for row in rows:
        exact(row, ('browser', 'elapsed_seconds', 'requests', 'scenario', 'sdk_requests', 'status'))
        require(type(row['status']) is str and row['status'] == 'passed', 'dto_row_failed')
        elapsed = row['elapsed_seconds']
        require(type(elapsed) in (int, Decimal) and
                (type(elapsed) is int or elapsed.is_finite()) and 0 <= elapsed <= 120, 'dto_elapsed')
        identities.append(dict(browser=row['browser'], scenario=row['scenario']))
        request_count += _dto_requests(row['requests'], row['sdk_requests'])
        require(request_count <= 8192, 'dto_request_limit')
    pairs = dto_case_identities(identities)
    store.recheck()
    return dict(status='unavailable', complete=False, profile_version=profile_version,
        candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
        observed_case_ids=[dict(browser=engine, scenario=scenario) for engine, scenario in pairs],
        verified_case_ids=[], observed_request_count=request_count, observed_asset_count=11,
        source_expectations_sha=DTO_SOURCE_EXPECTATIONS_SHA,
        missing_validation_families=list(DTO_MISSING_FAMILIES), **{flag: False for flag in FLAGS})


def references(value, artifacts):
    array(value)
    for ref in value:
        identifier(ref)
        require(ref in artifacts, 'undeclared_artifact')
    unique(value)


def timestamp(value):
    require(type(value) is str, 'invalid_timestamp')
    match = re.fullmatch(r'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]+))?(?:Z|\+00:00)', value)
    require(match is not None, 'invalid_timestamp')
    try:
        # Preserve arbitrary RFC3339 fractional precision for exact ordering.
        return (datetime.fromisoformat(match[1]+'+00:00'), Decimal('0.'+(match[2] or '0')))
    except ValueError:
        raise ContractError('invalid_timestamp') from None


def parse_envelope(raw):
    """Validate structure and internal references; never read or trust raw evidence."""
    item = strict_json(raw)
    exact(item, ('contract', 'schema_version', 'candidate_sha', 'trusted_base_sha',
                 'requested_tier', 'task_ref', 'policy_sha256', 'bindings', 'artifacts', 'slots', 'eight_reports'))
    require(item['contract'] == CONTRACT, 'invalid_contract_version')
    require(type(item['schema_version']) is int and item['schema_version'] == 1, 'invalid_schema_version')
    digest(item['candidate_sha'], 40); digest(item['trusted_base_sha'], 40)
    digest(item['policy_sha256']); safe_ref(item['task_ref'])
    enum(item['requested_tier'], ('fixture', 'staging'))
    artifacts = {}
    refs = []
    array(item['artifacts'])
    for artifact in item['artifacts']:
        exact(artifact, ('artifact_id', 'kind', 'ref', 'sha256', 'bytes', 'visibility'))
        identifier(artifact['artifact_id']); enum(artifact['kind'], ARTIFACT_KINDS)
        safe_ref(artifact['ref']); digest(artifact['sha256']); integer(artifact['bytes'])
        enum(artifact['visibility'], ('private', 'public'))
        require(artifact['artifact_id'] not in artifacts, 'duplicate_artifact_id')
        artifacts[artifact['artifact_id']] = artifact
        refs.append(artifact['ref'])
    unique(refs)
    exact(item['bindings'], BINDINGS)
    # Multiple binding roles may index one manifest, but each must be declared.
    for ref in item['bindings'].values():
        identifier(ref); require(ref in artifacts, 'undeclared_artifact')
        require(artifacts[ref]['kind'] in ('manifest', 'provenance'), 'binding_artifact_kind')
    array(item['slots'])
    slots = []
    for slot in item['slots']:
        exact(slot, ('slot_id', 'kind', 'scope', 'candidate_sha', 'profile_sha256',
                     'result_artifact', 'host_receipt_artifact', 'raw_artifact_ids', 'command',
                     'started_at', 'finished_at', 'deadline_seconds', 'exit_code', 'timed_out'))
        enum(slot['slot_id'], SLOT_KINDS)
        require(slot['kind'] == SLOT_KINDS[slot['slot_id']], 'slot_kind_mismatch')
        enum(slot['scope'], ('fixture', 'staging'))
        require(item['requested_tier'] == 'staging' or slot['scope'] == 'fixture', 'tier_scope_mismatch')
        require(slot['scope'] == ('staging' if slot['slot_id'] in STAGING_SLOTS else 'fixture'), 'slot_scope_mismatch')
        digest(slot['candidate_sha'], 40)
        require(slot['candidate_sha'] == item['candidate_sha'], 'candidate_mismatch')
        digest(slot['profile_sha256'])
        for field, kind in (('result_artifact', 'collector_result'), ('host_receipt_artifact', 'host_receipt')):
            ref = slot[field]; identifier(ref)
            require(ref in artifacts and artifacts[ref]['kind'] == kind, 'slot_artifact_kind')
        references(slot['raw_artifact_ids'], artifacts)
        exact(slot['command'], ('argv', 'sha256'))
        argv = slot['command']['argv']; array(argv); require(bool(argv), 'empty_command')
        for arg in argv:
            # Empty argv operands are valid data, but not control characters.
            require(type(arg) is str and not any(ord(char) < 32 for char in arg), 'invalid_argv')
        require(bool(argv[0]), 'empty_command')
        digest(slot['command']['sha256'])
        require(sha256(canonical(argv)) == slot['command']['sha256'], 'command_hash_mismatch')
        start = timestamp(slot['started_at']); finish = timestamp(slot['finished_at'])
        require(finish >= start, 'negative_elapsed')
        integer(slot['deadline_seconds'], 1); integer(slot['exit_code'])
        require(type(slot['timed_out']) is bool, 'invalid_timeout')
        slots.append(slot['slot_id'])
    unique(slots)
    array(item['eight_reports'])
    gates = []
    finding_ids = []
    for report in item['eight_reports']:
        exact(report, ('gate_id', 'candidate_sha', 'scope', 'verdict', 'author_id',
                       'reviewer_id', 'artifact_ids', 'findings', 'reason_code'))
        enum(report['gate_id'], GATES); digest(report['candidate_sha'], 40)
        require(report['candidate_sha'] == item['candidate_sha'], 'candidate_mismatch')
        enum(report['scope'], ('fixture', 'staging'))
        require(item['requested_tier'] == 'staging' or report['scope'] == 'fixture', 'tier_scope_mismatch')
        enum(report['verdict'], ('pass', 'fail', 'pending', 'unavailable'))
        for role in ('author_id', 'reviewer_id'):
            if report[role] is None:
                require(report['verdict'] == 'pending', 'missing_report_identity')
            else:
                identifier(report[role])
        references(report['artifact_ids'], artifacts)
        if report['verdict'] == 'pass':
            require(report['reason_code'] is None, 'pass_reason')
        else:
            enum(report['reason_code'], ('missing', 'unavailable', 'invalid', 'failed',
                 'disagreement', 'not_required_at_fixture_tier'))
        array(report['findings'])
        for finding in report['findings']:
            exact(finding, ('finding_id', 'severity', 'blocking', 'status', 'artifact_ids'))
            identifier(finding['finding_id'])
            enum(finding['severity'], ('critical', 'high', 'medium', 'low', 'informational'))
            enum(finding['status'], ('open', 'resolved'))
            require(type(finding['blocking']) is bool, 'invalid_blocking')
            references(finding['artifact_ids'], artifacts)
            finding_ids.append(finding['finding_id'])
        gates.append(report['gate_id'])
    unique(gates); unique(finding_ids)
    require(set(gates) == set(GATES), 'missing_gate_report')
    return item


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class ArtifactStore:
    """Confined immutable transport, independent of any raw producer schema.

    Every read reopens files and rechecks the complete inventory. No bytes are
    cached across calls. A matching digest proves integrity, never authorship.
    """
    def __init__(self, root, artifacts, *, max_file_bytes=MAX_ARTIFACT_BYTES,
                 max_total_bytes=MAX_EVIDENCE_BYTES):
        integer(max_file_bytes, 1); integer(max_total_bytes, 1)
        require(max_file_bytes <= MAX_ARTIFACT_BYTES and max_total_bytes <= MAX_EVIDENCE_BYTES,
                'unsupported_transport_limit')
        root_path = os.fspath(root)
        string(root_path)
        require('..' not in root_path.split('/'), 'unsafe_evidence_root')
        self.root = os.path.abspath(root_path)
        self.closed = False
        self.artifacts = {}
        self.by_ref = {}
        self.directories = {''}
        array(artifacts)
        total = 0
        for record in artifacts:
            exact(record, ('artifact_id', 'kind', 'ref', 'sha256', 'bytes', 'visibility'))
            identifier(record['artifact_id']); safe_ref(record['ref']); digest(record['sha256'])
            enum(record['kind'], ARTIFACT_KINDS); enum(record['visibility'], ('private', 'public'))
            integer(record['bytes'])
            require(record['artifact_id'] not in self.artifacts and record['ref'] not in self.by_ref,
                    'duplicate_artifact_identity')
            require(record['bytes'] <= max_file_bytes, 'artifact_size_limit')
            total += record['bytes']
            require(total <= max_total_bytes, 'evidence_size_limit')
            # Snapshot declarations too: callers cannot mutate records after binding.
            record = dict(record)
            self.artifacts[record['artifact_id']] = record
            self.by_ref[record['ref']] = record
            parts = record['ref'].split('/')
            self.directories.update('/'.join(parts[:index]) for index in range(1, len(parts)))
        self.snapshot = self._inventory()

    def __enter__(self):
        require(not self.closed, 'artifact_store_closed')
        return self

    def __exit__(self, *_):
        self.closed = True

    def _open_root(self):
        # Open every absolute component with NOFOLLOW, including root ancestors.
        current = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for part in self.root.split('/')[1:]:
                if not part:
                    continue
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  dir_fd=current)
                os.close(current)
                current = next_fd
            return current
        except BaseException:
            os.close(current)
            raise

    def _inventory(self):
        require(not self.closed, 'artifact_store_closed')
        pending = []
        result = {}
        found = set()
        inodes = set()
        try:
            pending.append(('', self._open_root()))
            while pending:
                prefix, fd = pending.pop()
                try:
                    before = file_identity(os.fstat(fd))
                    result[prefix+'/'] = before
                    for name in os.listdir(fd):
                        ref = prefix+'/'+name if prefix else name
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            require(ref in self.directories, 'undeclared_inventory_entry')
                            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                            dir_fd=fd)
                            if file_identity(os.fstat(child)) != file_identity(info):
                                os.close(child)
                                raise ContractError('artifact_identity_drift')
                            pending.append((ref, child))
                        else:
                            require(stat.S_ISREG(info.st_mode), 'unsafe_evidence_file')
                            require(ref in self.by_ref, 'undeclared_inventory_entry')
                            require(info.st_nlink == 1 and (info.st_dev, info.st_ino) not in inodes,
                                    'aliased_evidence_inode')
                            require(info.st_size == self.by_ref[ref]['bytes'], 'artifact_size_mismatch')
                            found.add(ref); inodes.add((info.st_dev, info.st_ino))
                            result[ref] = file_identity(info)
                    require(file_identity(os.fstat(fd)) == before, 'artifact_identity_drift')
                finally:
                    os.close(fd)
            require(found == set(self.by_ref), 'missing_evidence_file')
            return result
        except OSError:
            raise ContractError('evidence_unavailable') from None
        finally:
            for _, fd in pending:
                os.close(fd)

    def recheck(self):
        require(self._inventory() == self.snapshot, 'artifact_identity_drift')

    def _open_file(self, ref):
        current = self._open_root()
        try:
            parts = ref.split('/')
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  dir_fd=current)
                os.close(current); current = next_fd
            return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                           dir_fd=current)
        finally:
            os.close(current)

    def read(self, artifact_id):
        identifier(artifact_id)
        require(artifact_id in self.artifacts, 'undeclared_artifact')
        self.recheck()
        record = self.artifacts[artifact_id]
        expected = self.snapshot[record['ref']]
        try:
            fd = self._open_file(record['ref'])
            try:
                require(file_identity(os.fstat(fd)) == expected, 'artifact_identity_drift')
                chunks = []
                remaining = record['bytes']+1
                while remaining:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk); remaining -= len(chunk)
                raw = b''.join(chunks)
                require(file_identity(os.fstat(fd)) == expected, 'artifact_identity_drift')
            finally:
                os.close(fd)
        except OSError:
            raise ContractError('evidence_unavailable') from None
        require(len(raw) == record['bytes'], 'artifact_size_mismatch')
        require(sha256(raw) == record['sha256'], 'artifact_hash_mismatch')
        self.recheck()
        return raw

    def read_identity_json(self, artifact_id, *, candidate_sha, trusted_base_sha, profile_sha256=None):
        """Explicit JSON reader; missing identity is never filled in or proof.

        This checks declared reserved identities only. Required fields and raw
        producer schemas remain unavailable until their own profile is frozen.
        """
        return self._read_bound_json(artifact_id, strict_json, candidate_sha,
                                     trusted_base_sha, profile_sha256)

    def read_raw_json(self, artifact_id, *, candidate_sha, trusted_base_sha, profile_sha256):
        """Explicit 4 MiB data reader reserved for internal typed validators.

        No CLI kind/filename selects this method. Profile authorization and
        completeness are separate from reserved-identity equality.
        """
        digest(profile_sha256)
        return self._read_bound_json(artifact_id, strict_raw_json, candidate_sha,
                                     trusted_base_sha, profile_sha256)

    def _read_bound_json(self, artifact_id, parser, candidate_sha, trusted_base_sha, profile_sha256):
        digest(candidate_sha, 40); digest(trusted_base_sha, 40)
        if profile_sha256 is not None:
            digest(profile_sha256)
        value = parser(self.read(artifact_id))
        expected = dict(candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
                        profile_sha256=profile_sha256)
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is dict:
                for key, nested in item.items():
                    if key in expected:
                        require(type(nested) is str and expected[key] is not None and nested == expected[key],
                                'raw_identity_mismatch')
                    pending.append(nested)
            elif type(item) is list:
                pending.extend(item)
        self.recheck()
        return value


@dataclass(frozen=True)
class TrustedInvocation:
    base_sha: str
    task_ref: str
    tier: str
    policy_sha256: str
    profile: dict


def git_read(base, ref):
    """Literal read-only object lookup, never candidate cwd/config or shell."""
    digest(base, 40); safe_ref(ref)
    env = {'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_NO_REPLACE_OBJECTS': '1',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1', 'LC_ALL': 'C'}
    try:
        result = subprocess.run(['/usr/bin/git', '--no-pager', '-c', 'core.hooksPath='+os.devnull,
            '-c', 'core.fsmonitor=false', 'cat-file', 'blob', base+':'+ref],
            cwd=REPO_ROOT, env=env, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ContractError('trusted_object_unavailable') from None
    require(result.returncode == 0, 'trusted_object_unavailable')
    require(len(result.stdout) <= MAX_MANIFEST_BYTES, 'trusted_object_size')
    return result.stdout


def load_trusted(base_sha, task_ref, requested_tier):
    """Consume only the pinned direct task; promotion is unavailable in milestone 1."""
    digest(base_sha, 40); safe_ref(task_ref); enum(requested_tier, ('fixture', 'staging'))
    require(task_ref == TASK_REF, 'unrecognized_trusted_task')
    task = strict_json(git_read(base_sha, task_ref))
    require(task.get('dispatch_mode') == 'coordinator-direct' and
            task.get('repository') == 'lucronn/autodata' and
            task.get('task_id') == 'production-release-r6-release', 'invalid_trusted_task')
    profile = task.get('product_evidence')
    exact(profile, ('contract', 'schema_version', 'policy_sha256', 'assembler_ref', 'assembler_sha256',
                    'evaluator_ref', 'evaluator_sha256', 'supervisor_profiles', 'bindings_profile',
                    'slot_profiles', 'ci_profile', 'report_profile', 'enabled_tiers'))
    require(profile['contract'] == CONTRACT and type(profile['schema_version']) is int and
            profile['schema_version'] == 1, 'invalid_profile_version')
    digest(profile['policy_sha256']); digest(profile['evaluator_sha256'])
    require(profile['assembler_ref'] == 'scripts/dev/release_acceptance.py' and
            profile['evaluator_ref'] == 'scripts/autonomy/validate_run.py', 'invalid_tool_reference')
    if profile['assembler_sha256'] is not None:
        digest(profile['assembler_sha256'])
    require(sha256(git_read(base_sha, '.autodata-autonomy-policy.json')) == profile['policy_sha256'], 'policy_hash_mismatch')
    require(sha256(git_read(base_sha, profile['evaluator_ref'])) == profile['evaluator_sha256'], 'evaluator_hash_mismatch')
    # Only the committed disabled planning profile is understood here. A future
    # promoted raw contract requires a separate gate and explicit implementation.
    require(profile['enabled_tiers'] == [] and type(profile['enabled_tiers']) is list,
            'unsupported_promoted_profile')
    require(profile['supervisor_profiles'] == [] and type(profile['supervisor_profiles']) is list,
            'unsupported_supervisor_profile')
    exact(profile['bindings_profile'], ('enabled',))
    require(profile['bindings_profile']['enabled'] is False, 'unsupported_bindings_profile')
    array(profile['slot_profiles'])
    ids = []
    for slot in profile['slot_profiles']:
        exact(slot, ('slot_id', 'enabled', 'expected_cases'))
        enum(slot['slot_id'], FIXTURE_SLOTS[:6]); require(slot['enabled'] is False, 'unsupported_slot_profile')
        integer(slot['expected_cases'], 1); ids.append(slot['slot_id'])
    unique(ids); require(set(ids) == set(FIXTURE_SLOTS[:6]), 'missing_slot_profile')
    exact(profile['ci_profile'], ('enabled', 'workflow_sha256', 'dto_upload_required'))
    require(profile['ci_profile']['enabled'] is False and profile['ci_profile']['dto_upload_required'] is True,
            'unsupported_ci_profile')
    digest(profile['ci_profile']['workflow_sha256'])
    require(sha256(git_read(base_sha, '.github/workflows/autonomous-verification.yml')) ==
            profile['ci_profile']['workflow_sha256'], 'workflow_hash_mismatch')
    exact(profile['report_profile'], ('enabled', 'gate_ids'))
    require(profile['report_profile']['enabled'] is False and profile['report_profile']['gate_ids'] == list(GATES),
            'unsupported_report_profile')
    return TrustedInvocation(base_sha, task_ref, requested_tier, profile['policy_sha256'], profile)


def diagnostic(mode, candidate=None, base=None, tier=None, manifest_hash=None):
    return dict(contract=CONTRACT, schema_version=1, candidate_sha=candidate, trusted_base_sha=base,
        requested_tier=tier, status='planned' if mode == 'plan' else 'unavailable',
        **{flag: False for flag in FLAGS}, derived_counts={key: 0 for key in COUNTS},
        gate_statuses={gate: {'status': 'unavailable', 'reason_code': 'unavailable'} for gate in GATES},
        missing_slots=list(FIXTURE_SLOTS + (STAGING_SLOTS if tier == 'staging' else ())),
        failures=[], input_manifest_sha256=manifest_hash, tool_sha256=sha256(Path(__file__).read_bytes()))


def assemble(envelope, trusted, mode, manifest_sha256=None):
    require(mode in ('plan', 'validate'), 'invalid_mode')
    require(envelope['trusted_base_sha'] == trusted.base_sha and envelope['task_ref'] == trusted.task_ref and
            envelope['requested_tier'] == trusted.tier and envelope['policy_sha256'] == trusted.policy_sha256,
            'trusted_invocation_mismatch')
    profiles = {profile['slot_id']: profile for profile in trusted.profile['slot_profiles']}
    for slot in envelope['slots']:
        if slot['slot_id'] in profiles:
            require(slot['profile_sha256'] == sha256(canonical(profiles[slot['slot_id']])),
                    'slot_profile_hash_mismatch')
        # Missing/disabled profiles remain unavailable, never inferred from raw.
    result = diagnostic(mode, envelope['candidate_sha'], trusted.base_sha, trusted.tier, manifest_sha256)
    # No supplied report, counter, file hash or execution flag can enable trust.
    result['failures'] = ['profiles_unavailable', 'raw_validation_unimplemented']
    if trusted.profile['assembler_sha256'] is None:
        result['failures'].append('assembler_unpromoted')
    return result, 0 if mode == 'plan' else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'validate'))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--evidence-root', required=True,
                        help='Dedicated declared raw input directory; plan does not read it')
    parser.add_argument('--trusted-base-sha', required=True)
    parser.add_argument('--task-ref', required=True)
    parser.add_argument('--requested-tier', required=True, choices=('fixture', 'staging'))
    args = parser.parse_args(argv)
    manifest_hash = None
    try:
        trusted = load_trusted(args.trusted_base_sha, args.task_ref, args.requested_tier)
        with Path(args.manifest).open('rb') as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
        require(len(raw) <= MAX_MANIFEST_BYTES, 'manifest_size')
        manifest_hash = sha256(raw)
        envelope = parse_envelope(raw)
        result, code = assemble(envelope, trusted, args.mode, manifest_hash)
        if args.mode == 'validate':
            with ArtifactStore(args.evidence_root, envelope['artifacts']) as store:
                for artifact in envelope['artifacts']:
                    store.read(artifact['artifact_id'])
                store.recheck()
    except (ContractError, OSError) as exc:
        result = diagnostic(args.mode, manifest_hash=manifest_hash)
        result['status'] = 'failed'
        result['failures'] = [str(exc) if isinstance(exc, ContractError) else 'input_unavailable']
        code = 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
