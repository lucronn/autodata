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
from urllib.parse import unquote

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


def _paid_http_exact(value, fields, code='paid_http_body'):
    require(type(value) is dict and set(value) == set(fields), code)


def _paid_http_equal(value, expected, code='paid_http_body'):
    """Compare closed JSON projections without Python's bool/int equivalence."""
    require(type(value) is type(expected), code)
    if type(expected) is dict:
        _paid_http_exact(value, expected, code)
        for key in expected: _paid_http_equal(value[key], expected[key], code)
    elif type(expected) is list:
        require(len(value) == len(expected), code)
        for item, wanted in zip(value, expected): _paid_http_equal(item, wanted, code)
    else:
        require(value == expected, code)


def _paid_http_uuid(value, code='paid_http_binding'):
    try: _paid_uuid(value)
    except ContractError: raise ContractError(code) from None


def _paid_http_bodies(rows, selected, canonical_rows, configuration, vehicle, article):
    """Interpret retained JSON projections only; raw body hashes remain declarations."""
    _paid_http_equal(rows[0]['body'], dict(items=[dict(year=2024)], version='v1'))
    for index, ident, name in ((1, 'example', 'Example'), (2, 'car', 'Car')):
        _paid_http_equal(rows[index]['body'], dict(complete=False, hydrating=True,
            items=[dict(id=ident, name=name)], version='v1'))
    configs = rows[3]['body']
    _paid_http_exact(configs, ('complete', 'hydrating', 'items', 'version'))
    _paid_http_equal({key:configs[key] for key in ('complete', 'hydrating', 'version')},
                     dict(complete=False, hydrating=False, version='v1'))
    require(type(configs['items']) is list and len(configs['items']) == 3, 'paid_http_body')
    ids = []; scopes = []
    for config in configs['items']:
        _paid_http_exact(config, ('complete', 'id', 'make', 'model', 'region', 'trim', 'vehicle_id', 'year'))
        _paid_http_uuid(config['id']); ids.append(config['id'])
        scope = (config['trim'], config['region'])
        require(type(config['trim']) is str and type(config['region']) is str,
                'paid_http_binding')
        scopes.append(scope)
        _paid_http_equal({key:config[key] for key in ('complete', 'make', 'model', 'year', 'vehicle_id')},
            dict(complete=True, make='Example', model='Car', year=2024, vehicle_id=vehicle), 'paid_http_binding')
        require(config['id'] != vehicle and (config['id'] == configuration) ==
                (scope == ('Paid selected', 'US')), 'paid_http_binding')
    require(len(set(ids)) == 3 and set(scopes) == {('Paid selected', 'US'),
            ('Paid adjacent', 'US'), ('Paid other region', 'CA')}, 'paid_http_body')

    listing = rows[14]['body']
    _paid_http_exact(listing, ('complete', 'hydrating', 'items', 'progress', 'version'))
    _paid_http_equal({key:listing[key] for key in ('complete', 'hydrating', 'version')},
                     dict(complete=True, hydrating=False, version='v1'))
    _paid_http_equal(listing['progress'], dict(complete=True, percent=100, phase='indexing',
        processed=2, retryable=False, status='completed', total=2))
    scoped = [row for row in canonical_rows if row.get('vehicle_configuration_id') == configuration]
    require(len(scoped) == 2 and {row['provider_slug'] for row in scoped} == {'bankone', 'banktwo'},
            'paid_http_binding')
    by_id = {row['canonical_article_id']:row for row in scoped}
    require(article in by_id and by_id[article] == selected, 'paid_http_binding')
    for row in scoped:
        require(type(row.get('title')) is str and all(key in row and row[key] is None for key in
            ('current_source_revision_id', 'current_canonical_revision_id', 'current_job_id')),
            'paid_http_binding')
    require(type(listing['items']) is list and len(listing['items']) == 2, 'paid_http_body')
    listed = []
    fields = ('availability', 'canonical_article_id', 'canonical_revision_id', 'complete',
        'content_origin', 'content_status', 'id', 'images', 'processing', 'review_status',
        'source_revision_id', 'title', 'vehicle_id', 'view_revision')
    for item in listing['items']:
        _paid_http_exact(item, fields)
        _paid_http_uuid(item['id']); listed.append(item['id'])
        require(item['id'] in by_id, 'paid_http_binding')
        _paid_http_equal(item, dict(availability='unavailable', canonical_article_id=item['id'],
            canonical_revision_id=None, complete=False, content_origin=None, content_status='list_only',
            id=item['id'], images=[], processing=None, review_status='UNREVIEWED', source_revision_id=None,
            title=by_id[item['id']]['title'], vehicle_id=configuration, view_revision=None), 'paid_http_binding')
    require(len(set(listed)) == 2 and set(listed) == set(by_id), 'paid_http_body')

    request_ids = []
    for index in (*range(4, 14), 15, 16, 17):
        body = rows[index]['body']; _paid_http_exact(body, ('error',))
        error = body['error']; _paid_http_exact(error, ('code', 'details', 'message', 'request_id', 'retryable'))
        _paid_http_uuid(error['request_id'], 'paid_http_body'); request_ids.append(error['request_id'])
        if index < 8:
            code, message, details, retryable = ('ENTITLEMENT_REQUIRED',
                'Purchase access to this vehicle configuration.', {}, False)
        elif index == 8:
            code, message, details, retryable = ('CATALOG_NOT_FOUND', 'Catalog resource was not found.', {}, False)
        elif index < 14:
            code, message, details, retryable = ('UNAUTHENTICATED', 'Authentication is required.',
                                                dict(login_available=True), False)
        elif index == 15:
            code, message, details, retryable = ('CATALOG_SOURCE_UNAVAILABLE',
                'Article is temporarily unavailable.', dict(article_id=article, retry_after_seconds=2), True)
        elif index == 16:
            code, message, details, retryable = ('CATALOG_UNAVAILABLE', 'Catalog is temporarily unavailable.', {}, True)
        else:
            code, message, details, retryable = ('AUTHENTICATION_UNAVAILABLE',
                'Authentication is temporarily unavailable.', dict(login_available=True), True)
        if index == 15:
            _paid_http_exact(error['details'], ('article_id', 'retry_after_seconds'))
            require(error['details']['article_id'] == article, 'paid_http_binding')
        _paid_http_equal(error, dict(code=code, message=message, details=details,
            request_id=error['request_id'], retryable=retryable))
    require(len(set(request_ids)) == 13, 'paid_http_body')


def inspect_paid_http_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
        input_manifest_sha256, host_before_sha256, expected_driver_sha256,
        profile_version='paid-selector-v2'):
    """Unselected 18×2 HTTP projection consistency, never wire or transport authority."""
    result = inspect_paid_selector_work(store, candidate_sha=candidate_sha,
        trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256,
        input_manifest_sha256=input_manifest_sha256, host_before_sha256=host_before_sha256,
        expected_driver_sha256=expected_driver_sha256, profile_version=profile_version)

    def document(ref):
        require(ref in store.by_ref, 'paid_missing_raw')
        return ArtifactStore._read_bound_json(store, store.by_ref[ref]['artifact_id'],
            lambda raw: _strict_json(raw, MAX_RAW_JSON_BYTES, 'raw_json_size', exact_floats=True),
            candidate_sha, trusted_base_sha, profile_sha256)

    name = 'TestPostgresPaidCatalogGrantBeforeWork'; observed = []
    fields = ('method', 'path', 'owner_index', 'status', 'headers', 'body', 'body_sha256',
        'body_size', 'body_truncated', 'reader_before', 'reader_after', 'identity_before', 'identity_after')
    counts = [(0, 0)]*4 + [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)] + [(5, 5)]*5 + [
        (5, 6), (6, 7), (7, 8), (8, 9)]
    for bank in ('bankone', 'banktwo'):
        prefix = 'paid-access/'+bank+'/'+name+'/'
        measured = document(prefix+'measured-runtime.json')
        measurement = document(prefix+'go-measurement.json')
        rows = measured['http_observations']
        require(type(rows) is list and len(rows) == 18, 'paid_http_inventory')
        require(rows == measurement['http_observations'] and measured['reader_calls'] ==
                measurement['reader_calls'] and measured['identity_checks'] == measurement['identity_checks'],
                'paid_measurement_mismatch')
        require(measured['reader_calls'] == 0 and measured['identity_checks'] == 9 and
                measured['held_model_receipt'] is None, 'paid_http_counter')
        snapshot = measured['snapshots']['selectors']; article = snapshot['article']
        configuration, vehicle, aid = (article.get(key) for key in
            ('vehicle_configuration_id', 'vehicle_id', 'canonical_article_id'))
        for value in (configuration, vehicle, aid): _paid_http_uuid(value)
        require(configuration != vehicle, 'paid_http_binding')
        canonical_rows = snapshot['immutable_rows']['canonical_articles']
        selected = [row for row in canonical_rows if row['canonical_article_id'] == aid and
                    row['provider_slug'] == bank]
        require(len(selected) == 1 and selected[0].get('vehicle_configuration_id') == configuration and
                selected[0].get('vehicle_id') == vehicle, 'paid_http_binding')
        listing = '/v1/catalog/vehicles/'+configuration+'/articles'; detail = listing+'/'+aid
        media = '/v1/catalog/images/[sha256:e0b1bb59f4515880aab8a8b144d8f4e20236fcac5bbf55768f92fe3d17c02f01]'
        paths = ['/v1/catalog/years', '/v1/catalog/years/2024/makes',
            '/v1/catalog/years/2024/makes/example/models',
            '/v1/catalog/years/2024/makes/example/models/car/configurations',
            listing, detail, detail+'/source', detail+'/prepare', media,
            listing, detail, detail+'/source', detail+'/prepare', media, listing, detail, detail, detail]
        for index, row in enumerate(rows):
            _paid_http_exact(row, fields, 'paid_http_row')
            require(type(row['method']) is str and type(row['path']) is str and
                all(type(row[key]) is int for key in ('owner_index', 'status', 'body_size',
                    'reader_before', 'reader_after', 'identity_before', 'identity_after')) and
                type(row['body_sha256']) is str and re.fullmatch(r'[a-f0-9]{64}', row['body_sha256']) is not None and
                1 <= row['body_size'] <= 262144 and row['body_truncated'] is False, 'paid_http_row')
            require((row['method'], row['path'], row['owner_index'], row['status']) == (
                'POST' if index in (7, 12) else 'GET', paths[index],
                -1 if index < 4 else 1 if 9 <= index <= 13 else 0,
                200 if index < 4 or index == 14 else 403 if index < 8 else 404 if index == 8 else
                401 if index < 14 else 503), 'paid_http_route')
            require(row['reader_before'] == row['reader_after'] == 0 and
                (row['identity_before'], row['identity_after']) == counts[index], 'paid_http_counter')
            headers = {'Content-Type':'application/json'}
            if index >= 4: headers.update({'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'})
            if index == 15: headers['Retry-After'] = '2'
            _paid_http_equal(row['headers'], headers, 'paid_http_headers')
            require(type(row['body']) is dict, 'paid_http_body')
        for phase, identity in zip(('before', 'selectors', 'unpaid', 'expired', 'paid_cold', 'unavailable'),
                                   (0, 0, 5, 5, 7, 9)):
            require(measured['snapshots'][phase]['reader_calls'] == 0 and
                    measured['snapshots'][phase]['identity_checks'] == identity, 'paid_http_counter')
        _paid_http_bodies(rows, selected[0], canonical_rows, configuration, vehicle, aid)
        observed.append(name+'-'+bank)
    store.recheck()
    result['observed_http_case_ids'] = observed
    result['observed_http_observation_count'] = 36
    result['missing_validation_families'].extend(('paid_http_wire_body_provenance',
                                                 'paid_http_transport_authority'))
    return result


def _paid_scope_binding(snapshot, bank):
    """Bind terminal fixture chains; the third configuration has no retained region row."""
    code = 'paid_scope_binding'
    article = snapshot['article']
    configuration, vehicle, aid = (article.get(key) for key in
        ('vehicle_configuration_id', 'vehicle_id', 'canonical_article_id'))
    for value in (configuration, vehicle, aid): _paid_http_uuid(value, code)
    require(configuration != vehicle, code)
    paid = snapshot['paid_rows']; accounts = paid['customer_accounts']
    require({row['firebase_uid'] for row in accounts} == {'paid-owner-a', 'paid-owner-b'}, code)
    require(all(row['status'] == 'active' and row['firebase_project_id'] == 'fixture-project'
                for row in accounts), code)
    primary = {'workshop_orders':'order_id', 'dataset_requests':'dataset_request_id',
        'dataset_projections':'dataset_projection_id', 'entitlements':'entitlement_id'}
    for table, key in primary.items():
        rows = paid[table]
        require(len(rows) == 2, code)
        for row in rows: _paid_http_uuid(row[key], code)
        require(len({row[key] for row in rows}) == 2, code)
    scopes = []; products = []; used = {table:[] for table in primary}
    for owner in ('paid-owner-a', 'paid-owner-b'):
        account = next(row for row in accounts if row['firebase_uid'] == owner)
        organization = account['personal_organization_id']; _paid_http_uuid(organization, code)
        matches = [row for row in paid['workshop_orders'] if row['customer_account_id'] == account['customer_account_id']]
        require(len(matches) == 1, code); order = matches[0]
        for key in ('dataset_request_id', 'entitlement_id', 'dataset_product_id', 'organization_id', 'configuration_id'):
            _paid_http_uuid(order[key], code)
        require(order['organization_id'] == organization and order['amount_minor'] == 2000 and
            order['currency'] == 'USD' and order['livemode'] is False and order['status'] == 'paid' and
            order['region'] == 'US', code)
        requests = [row for row in paid['dataset_requests'] if row['dataset_request_id'] == order['dataset_request_id']]
        grants = [row for row in paid['entitlements'] if row['entitlement_id'] == order['entitlement_id']]
        require(len(requests) == len(grants) == 1, code)
        request, grant = requests[0], grants[0]
        projections = [row for row in paid['dataset_projections'] if
            row['dataset_request_id'] == request['dataset_request_id'] and row['entitlement_id'] == grant['entitlement_id']]
        require(len(projections) == 1, code); projection = projections[0]
        for row, keys in ((request, ('dataset_product_id','organization_id','correlation_id')),
                (grant, ('dataset_request_id','organization_id')),
                (projection, ('dataset_request_id','entitlement_id','dataset_product_id'))):
            for key in keys: _paid_http_uuid(row[key], code)
        require(request['correlation_id'] == order['order_id'] and
            request['organization_id'] == grant['organization_id'] == organization and
            grant['dataset_request_id'] == request['dataset_request_id'] and
            order['dataset_product_id'] == request['dataset_product_id'] == projection['dataset_product_id'] and
            request['vehicle_key'] == order['configuration_id'] and request['region'] == 'US', code)
        require(grant['status'] == 'active' and grant['revoked_at'] is None, code)
        if owner == 'paid-owner-a':
            require(order['configuration_id'] == configuration and all(grant[key] is None for key in
                ('customer_account_id', 'configuration_id', 'region', 'commerce_order_id')) and
                grant['revoke_reason'] == 'fixture', code)
        else:
            require(grant['customer_account_id'] == account['customer_account_id'] and
                grant['configuration_id'] == order['configuration_id'] and grant['region'] == 'US' and
                grant['commerce_order_id'] == order['order_id'] and grant['revoke_reason'] is None, code)
        scopes.append(order['configuration_id']); products.append(order['dataset_product_id'])
        for table, row in zip(primary, (order, request, projection, grant)):
            used[table].append(row[primary[table]])
    require(len(set(scopes)) == 2 and len(set(products)) == 1 and all(
        len(set(values)) == 2 and set(values) == {row[primary[table]] for row in paid[table]}
        for table, values in used.items()), code)
    canonical_rows = snapshot['immutable_rows']['canonical_articles']
    require(len(canonical_rows) == 8, code)
    configurations = set()
    for row in canonical_rows:
        require(row.get('vehicle_id') == vehicle, code)
        require('vehicle_configuration_id' in row, code)
        config = row['vehicle_configuration_id']
        if config is not None: _paid_http_uuid(config, code); configurations.add(config)
    require(len(configurations) == 3 and set(scopes) <= configurations and vehicle not in configurations, code)
    other = next(iter(configurations-set(scopes)))
    by_scope = {}
    for provider in ('bankone', 'banktwo'):
        for config in (*scopes, other, None):
            matches = [row for row in canonical_rows if row['provider_slug'] == provider and
                       row.get('vehicle_configuration_id') == config]
            require(len(matches) == 1, code); by_scope[provider, config] = matches[0]
    require(by_scope[bank, configuration]['canonical_article_id'] == aid, code)
    selected = [by_scope[provider, configuration] for provider in ('bankone', 'banktwo')]
    for row in selected:
        require(type(row.get('title')) is str and all(key in row and row[key] is None for key in
            ('current_source_revision_id','current_canonical_revision_id','current_job_id')), code)
    return configuration, vehicle, scopes[1], other, by_scope, selected


def _paid_scope_work(snapshot, *, final=False):
    code = 'paid_scope_work'
    for group in ('counts', 'ensure', 'selector_ensure', 'provider_calls', 'source_calls', 'asset_calls'):
        require(all(type(value) is int and value == 0 for value in snapshot[group].values()), code)
    for key in ('ensure_requests','selector_ensure_requests','workers'):
        require(snapshot[key] == [], code)
    require(snapshot['provider_traces'] == dict(bankone=[],banktwo=[]) and
        snapshot['model_calls'] == snapshot['payment_calls'] == 0 and snapshot['grant_calls'] == 9, code)
    _paid_http_equal(snapshot['proxy'], dict(request_received=0,upstream_completed=0,
        downstream_completed=0,downstream_waiting=0,response_captured=False,errors=[]), code)
    if not final:
        require(snapshot['reader_calls'] == 0 and snapshot['identity_checks'] == 11, 'paid_scope_counter')


def _paid_scope_bodies(rows, selected, configuration):
    code = 'paid_scope_body'; binding = 'paid_scope_binding'
    body = rows[0]['body']; _paid_http_exact(body, ('complete','hydrating','items','progress','version'), code)
    _paid_http_equal({key:body[key] for key in ('complete','hydrating','version')},
        dict(complete=True,hydrating=False,version='v1'), code)
    _paid_http_equal(body['progress'],dict(complete=True,percent=100,phase='indexing',processed=2,
        retryable=False,status='completed',total=2),code)
    require(type(body['items']) is list and len(body['items']) == 2, code)
    by_id = {row['canonical_article_id']:row for row in selected}; ids = []
    fields = ('availability','canonical_article_id','canonical_revision_id','complete','content_origin',
        'content_status','id','images','processing','review_status','source_revision_id','title','vehicle_id','view_revision')
    for item in body['items']:
        _paid_http_exact(item,fields,code); _paid_http_uuid(item['id'],binding)
        require(item['id'] in by_id,binding); ids.append(item['id'])
        _paid_http_equal(item,dict(availability='unavailable',canonical_article_id=item['id'],canonical_revision_id=None,
            complete=False,content_origin=None,content_status='list_only',id=item['id'],images=[],processing=None,
            review_status='UNREVIEWED',source_revision_id=None,title=by_id[item['id']]['title'],
            vehicle_id=configuration,view_revision=None),binding)
    require(set(ids) == set(by_id) and len(set(ids)) == 2,code)
    request_ids = []
    for index in range(1,11):
        body = rows[index]['body']; _paid_http_exact(body,('error',),code)
        error = body['error']; _paid_http_exact(error,('code','details','message','request_id','retryable'),code)
        _paid_http_uuid(error['request_id'],code); request_ids.append(error['request_id'])
        if index in (1,3,4,10):
            error_code,message = 'ENTITLEMENT_REQUIRED','Purchase access to this vehicle configuration.'
        elif index == 9:
            error_code,message = 'ENTITLEMENT_REVOKED','Access to this vehicle configuration was revoked.'
        else:
            error_code,message = 'CATALOG_NOT_FOUND','Catalog resource was not found.'
        _paid_http_equal(error,dict(code=error_code,details={},message=message,request_id=error['request_id'],retryable=False),code)
    require(len(set(request_ids)) == 10,code)


def inspect_paid_scope_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
        input_manifest_sha256, host_before_sha256, expected_driver_sha256,
        profile_version='paid-selector-v2'):
    """Unselected two-case terminal/projection consistency; no revocation-history authority."""
    result = inspect_paid_http_receipts(store, candidate_sha=candidate_sha,
        trusted_base_sha=trusted_base_sha,profile_sha256=profile_sha256,input_manifest_sha256=input_manifest_sha256,
        host_before_sha256=host_before_sha256,expected_driver_sha256=expected_driver_sha256,profile_version=profile_version)
    def document(ref):
        require(ref in store.by_ref,'paid_missing_raw')
        return ArtifactStore._read_bound_json(store,store.by_ref[ref]['artifact_id'],
            lambda raw:_strict_json(raw,MAX_RAW_JSON_BYTES,'raw_json_size',exact_floats=True),
            candidate_sha,trusted_base_sha,profile_sha256)
    name = 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation'; observed = []
    fields = ('method','path','owner_index','status','headers','body','body_sha256','body_size',
        'body_truncated','reader_before','reader_after','identity_before','identity_after')
    for bank in ('bankone','banktwo'):
        prefix = 'paid-access/'+bank+'/'+name+'/'
        measured = document(prefix+'measured-runtime.json'); measurement = document(prefix+'go-measurement.json')
        rows = measured['http_observations']
        require(type(rows) is list and len(rows) == 11,'paid_scope_inventory')
        require(rows == measurement['http_observations'] and measured['reader_calls'] == measurement['reader_calls'] and
            measured['identity_checks'] == measurement['identity_checks'],'paid_measurement_mismatch')
        require(measured['reader_calls'] == 0 and measured['identity_checks'] == 11 and
            measured['held_model_receipt'] is None,'paid_scope_counter')
        isolated = measured['snapshots']['isolated']; final = measured['final_snapshot']
        for snapshot, terminal in ((isolated,False),(final,True)):
            _paid_scope_work(snapshot,final=terminal); _paid_scope_binding(snapshot,bank)
        _paid_http_equal(final,{key:value for key,value in isolated.items() if key not in
            ('reader_calls','identity_checks')},'paid_scope_work')
        configuration, vehicle, adjacent, other, by_scope, selected = _paid_scope_binding(isolated,bank)
        listing = '/v1/catalog/vehicles/'+configuration+'/articles'
        paths = [listing,listing,'/v1/catalog/vehicles/'+vehicle+'/articles',
            '/v1/catalog/vehicles/'+adjacent+'/articles','/v1/catalog/vehicles/'+other+'/articles',
            listing+'?region=CA',listing+'/'+by_scope[bank,adjacent]['canonical_article_id'],
            listing+'/'+by_scope[bank,None]['canonical_article_id'],listing+'/legacy',listing,listing]
        for index,row in enumerate(rows):
            _paid_http_exact(row,fields,'paid_scope_row')
            require(type(row['method']) is str and type(row['path']) is str and all(type(row[key]) is int for key in
                ('owner_index','status','body_size','reader_before','reader_after','identity_before','identity_after')) and
                type(row['body_sha256']) is str and re.fullmatch(r'[a-f0-9]{64}',row['body_sha256']) is not None and
                1 <= row['body_size'] <= 262144 and row['body_truncated'] is False,'paid_scope_row')
            require((row['method'],row['path'],row['owner_index'],row['status']) == ('GET',paths[index],
                1 if index == 1 else 0,200 if index == 0 else 403 if index in (1,3,4,9,10) else 404),'paid_scope_route')
            require(row['reader_before'] == row['reader_after'] == 0 and
                (row['identity_before'],row['identity_after']) == (index,index+1),'paid_scope_counter')
            _paid_http_equal(row['headers'],{'Content-Type':'application/json','Cache-Control':'private, no-store',
                'X-Content-Type-Options':'nosniff'},'paid_scope_headers')
            require(type(row['body']) is dict,'paid_scope_body')
        _paid_scope_bodies(rows,selected,configuration); observed.append(name+'-'+bank)
    store.recheck()
    result['observed_scope_case_ids'] = observed
    result['observed_scope_http_observation_count'] = 22
    result['observed_scope_snapshot_count'] = 4
    result['missing_validation_families'].append('paid_scope_temporal_entitlement_provenance')
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


# Exact current-source contract frozen by the API21 K2 checkpoint. No producer
# imports, runtime spec loading, profile registration or CLI dispatch.
API21_SOURCE_SHA = 'b6279480dc57f81f11f93435ae5b3d10b5ae262f'
API21_SOURCE_TREE = '9105b372988ca2fc2827310c4806cb826a395bda'
API21_CASES = (('test_browser_google_exchange_checkout_library_real_api[chromium]',
  'test_browser_google_exchange_checkout_library_real_api',
  'chromium',
  'bankone'),
 ('test_browser_google_exchange_checkout_library_real_api[firefox]',
  'test_browser_google_exchange_checkout_library_real_api',
  'firefox',
  'bankone'),
 ('test_browser_google_exchange_checkout_library_real_api[webkit]',
  'test_browser_google_exchange_checkout_library_real_api',
  'webkit',
  'bankone'),
 ('test_browser_owned_source_canonical_and_media_real_api[chromium-bankone]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'chromium',
  'bankone'),
 ('test_browser_owned_source_canonical_and_media_real_api[chromium-banktwo]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'chromium',
  'banktwo'),
 ('test_browser_owned_source_canonical_and_media_real_api[firefox-bankone]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'firefox',
  'bankone'),
 ('test_browser_owned_source_canonical_and_media_real_api[firefox-banktwo]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'firefox',
  'banktwo'),
 ('test_browser_owned_source_canonical_and_media_real_api[webkit-bankone]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'webkit',
  'bankone'),
 ('test_browser_owned_source_canonical_and_media_real_api[webkit-banktwo]',
  'test_browser_owned_source_canonical_and_media_real_api',
  'webkit',
  'banktwo'),
 ('test_browser_account_scope_and_revocation_real_api[chromium-bankone]',
  'test_browser_account_scope_and_revocation_real_api',
  'chromium',
  'bankone'),
 ('test_browser_account_scope_and_revocation_real_api[chromium-banktwo]',
  'test_browser_account_scope_and_revocation_real_api',
  'chromium',
  'banktwo'),
 ('test_browser_account_scope_and_revocation_real_api[firefox-bankone]',
  'test_browser_account_scope_and_revocation_real_api',
  'firefox',
  'bankone'),
 ('test_browser_account_scope_and_revocation_real_api[firefox-banktwo]',
  'test_browser_account_scope_and_revocation_real_api',
  'firefox',
  'banktwo'),
 ('test_browser_account_scope_and_revocation_real_api[webkit-bankone]',
  'test_browser_account_scope_and_revocation_real_api',
  'webkit',
  'bankone'),
 ('test_browser_account_scope_and_revocation_real_api[webkit-banktwo]',
  'test_browser_account_scope_and_revocation_real_api',
  'webkit',
  'banktwo'),
 ('test_browser_signed_refund_blocks_old_links_real_api[chromium-bankone]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'chromium',
  'bankone'),
 ('test_browser_signed_refund_blocks_old_links_real_api[chromium-banktwo]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'chromium',
  'banktwo'),
 ('test_browser_signed_refund_blocks_old_links_real_api[firefox-bankone]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'firefox',
  'bankone'),
 ('test_browser_signed_refund_blocks_old_links_real_api[firefox-banktwo]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'firefox',
  'banktwo'),
 ('test_browser_signed_refund_blocks_old_links_real_api[webkit-bankone]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'webkit',
  'bankone'),
 ('test_browser_signed_refund_blocks_old_links_real_api[webkit-banktwo]',
  'test_browser_signed_refund_blocks_old_links_real_api',
  'webkit',
  'banktwo'))
API21_ASSERTIONS = {'test_browser_account_scope_and_revocation_real_api': ('official_sdk_cookie_and_pg_session',
                                                        'return_does_not_grant',
                                                        'signed_public_webhook_grants_once',
                                                        'permanent_owner_library_reload',
                                                        'permanent_owner_library_server_restart',
                                                        'paid_source_and_actual_s3_image',
                                                        'source_to_canonical_and_warm_reuse',
                                                        'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                                                        'account_and_exact_scope_isolation',
                                                        'logout_bfcache_and_firebase_disable_deny'),
 'test_browser_google_exchange_checkout_library_real_api': ('official_sdk_cookie_and_pg_session',
                                                            'return_does_not_grant',
                                                            'signed_public_webhook_grants_once',
                                                            'permanent_owner_library_reload',
                                                            'permanent_owner_library_server_restart',
                                                            'client_response_loss_same_key_one_checkout'),
 'test_browser_owned_source_canonical_and_media_real_api': ('official_sdk_cookie_and_pg_session',
                                                            'return_does_not_grant',
                                                            'signed_public_webhook_grants_once',
                                                            'permanent_owner_library_reload',
                                                            'permanent_owner_library_server_restart',
                                                            'paid_source_and_actual_s3_image',
                                                            'source_to_canonical_and_warm_reuse',
                                                            'warm_raw_runtime_unchanged_with_approved_s3_delivery'),
 'test_browser_signed_refund_blocks_old_links_real_api': ('official_sdk_cookie_and_pg_session',
                                                          'return_does_not_grant',
                                                          'signed_public_webhook_grants_once',
                                                          'permanent_owner_library_reload',
                                                          'permanent_owner_library_server_restart',
                                                          'paid_source_and_actual_s3_image',
                                                          'source_to_canonical_and_warm_reuse',
                                                          'warm_raw_runtime_unchanged_with_approved_s3_delivery',
                                                          'signed_full_refund_denies_old_content_and_media')}
API21_SOURCE_INPUTS = {'apps/api-go/workshop_browser_fixture_test.go': '7520a24bcfa06fe64810c6c17625563d29a2387c6d0531a61713f50b2098bf33',
 'scripts/dev/fixtures/workshop_customer/firebase_transport.js': '96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63',
 'scripts/dev/fixtures/workshop_customer/hostile_source.json': '076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1',
 'scripts/dev/fixtures/workshop_customer/scenarios.json': '83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9',
 'scripts/dev/fixtures/workshop_customer/stripe_checkout.html': '26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083',
 'scripts/dev/workshop_browser_smoke.py': '95f95f25de9c1718901f1dc99580a89d5588a17dd43b8a3a013f8b459e6ba2bc'}
API21_SOURCE_ASSETS = {'app.mjs': {'bytes': 37545,
             'sha256': '4a3e16b3b407e738ed013f4b7ae416fe6c47eb1548d123e90b5b867df5c74788'},
 'article-read.mjs': {'bytes': 2579,
                      'sha256': '2957242037d4bc3ce7894ae2c7e4bae1636406d0256dd75b6150e78c1c4e5178'},
 'auth.mjs': {'bytes': 7908,
              'sha256': 'ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2'},
 'catalog.mjs': {'bytes': 11688,
                 'sha256': 'cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52'},
 'commerce.mjs': {'bytes': 7369,
                  'sha256': 'e7f8e2fd45d6cd9f4ec2ef2f3a50d3f090f34e2562d4bbc58f9c23d06e8a1142'},
 'firebase-web.mjs': {'bytes': 112641,
                      'sha256': 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1'},
 'firebase-web.mjs.LEGAL.txt': {'bytes': 35536,
                                'sha256': '70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319'},
 'firebase-web.provenance.json': {'bytes': 2237,
                                  'sha256': '0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a'},
 'index.html': {'bytes': 10868,
                'sha256': '8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68'},
 'progress.mjs': {'bytes': 1076,
                  'sha256': 'dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48'},
 'styles.css': {'bytes': 20773,
                'sha256': 'c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c'}}
API21_MISSING_FAMILIES = ('actual_child_go_browser_exit_receipts',
 'parent_pytest_exit_and_command_receipts',
 'lost_response_pending_measurement_and_snapshot_raw',
 'checkout_idempotency_key_request_response_bytes_and_body_hashes',
 'signed_settlement_refund_http_bytes_and_authentic_delivery',
 'other_account_denial_http_status_and_response_bytes',
 'logout_disable_revocation_http_observations',
 'runtime_image_browser_cache_sdk_install_identity',
 'authenticated_capture_source_observer_and_containment',
 'global_worker_log_per_case_ownership_mapping',
 'finite_api_success_schedule',
 'junit_byte_preserving_capture_mapping',
 'all_final180_families_and_profile_promotion',
 'independent_authentic_raw_review')

API21_SUPPORT = ('child.log', 'result.json', 'ready.json', 'go-fixture.log',
                 'browser.stdout.log', 'browser.stderr.log', 'browser/evidence.json')
API21_MEASUREMENT = ('auth_sessions', 'workshop_orders', 'workshop_checkout_requests',
    'entitlements', 'dataset_requests', 'dataset_projections', 'payment_events',
    'hashed_sessions', 'sdk_cert_calls', 'sdk_user_calls', 'sdk_unexpected', 'image_reads')
API21_DURABLE = ('workshop_orders', 'workshop_checkout_requests', 'entitlements',
    'dataset_requests', 'dataset_projections', 'payment_events', 'orders', 'auth_sessions', 'hashed_sessions')


def _api21_identity(value, candidate, base, profile, version):
    expected = dict(candidate_sha=candidate, source_sha=candidate, producer_sha=candidate,
        producer_candidate_sha=candidate, candidate_tree=API21_SOURCE_TREE,
        source_tree=API21_SOURCE_TREE, tree_sha=API21_SOURCE_TREE, producer_tree=API21_SOURCE_TREE,
        trusted_base_sha=base, profile_sha256=profile, profile_version=version)
    pending = [(value, 0)]; nodes = 0
    while pending:
        item, depth = pending.pop(); nodes += 1
        require(depth <= 64 and nodes <= 100000, 'api21_json_complexity')
        if type(item) is dict:
            for key, nested in item.items():
                if key in expected:
                    require(type(nested) is str and nested == expected[key], 'api21_identity')
                if key in (*FLAGS, 'accepted', 'verified', 'release_authorized', 'profiles_enabled'):
                    require(nested is False, 'api21_forged_authority')
                if key in ('verified_case_ids', 'accepted_case_ids'):
                    require(type(nested) is list and nested == [], 'api21_forged_authority')
                if key in ('accepted_case_credit', 'accepted_new_case_credit'):
                    require(type(nested) is int and nested == 0, 'api21_forged_authority')
                pending.append((nested, depth+1))
        elif type(item) is list:
            pending.extend((nested, depth+1) for nested in item)


def _api21_elapsed(value):
    require(type(value) in (int, float) and value >= 0 and
            (type(value) is int or math.isfinite(value)), 'api21_elapsed')


def _api21_junit(raw):
    root = strict_junit_xml(raw)
    require(root.tag == 'testsuites' and root.attrib == {'name':'pytest tests'} and
            len(root) == 1 and root[0].tag == 'testsuite', 'api21_junit_structure')
    suite = root[0]
    exact(suite.attrib, ('name', 'errors', 'failures', 'skipped', 'tests', 'time', 'timestamp', 'hostname'))
    require(suite.get('name') == 'pytest', 'api21_junit_structure')
    timestamp(suite.get('timestamp')); string(suite.get('hostname'))
    def elapsed(text):
        require(type(text) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',text) is not None,
                'api21_junit_elapsed')
        require(Decimal(text).is_finite(), 'api21_junit_elapsed')
    elapsed(suite.get('time'))
    names = []; outcomes = []; counts = dict(errors=0, failures=0, skipped=0)
    require(not (root.text or '').strip() and not (suite.text or '').strip(), 'api21_junit_structure')
    for case in suite:
        require(case.tag == 'testcase' and not (case.text or '').strip() and
                not (case.tail or '').strip(), 'api21_junit_structure')
        exact(case.attrib, ('classname', 'name', 'time'))
        require(case.get('classname') == 'tests.test_workshop_browser_integration', 'api21_junit_identity')
        elapsed(case.get('time')); names.append(case.get('name'))
        require(len(case) <= 1, 'api21_junit_outcome')
        outcome = 'passed'
        if len(case):
            child = case[0]
            require(child.tag in ('failure', 'error', 'skipped') and len(child) == 0,
                    'api21_junit_outcome')
            require(set(child.attrib) <= {'message','type'} and not (child.tail or '').strip(),
                    'api21_junit_outcome')
            outcome = child.tag; counts[{'failure':'failures','error':'errors','skipped':'skipped'}[outcome]] += 1
        outcomes.append(outcome)
    require(names == [case[0] for case in API21_CASES], 'api21_case_inventory')
    require(suite.get('tests') == str(len(names)) and all(suite.get(key) == str(value)
                for key,value in counts.items()), 'api21_junit_counters')
    return outcomes


def _api21_measurement(value, scope, *, state):
    exact(value, (*API21_MEASUREMENT, 'orders'))
    for key in API21_MEASUREMENT: integer(value[key])
    require(value['hashed_sessions'] == value['auth_sessions'] and value['auth_sessions'] >= 1 and
            value['sdk_unexpected'] == 0 and value['sdk_cert_calls'] >= 1 and value['sdk_user_calls'] >= 2,
            'api21_measurement_identity')
    require(all(value[key] == 1 for key in ('workshop_orders','workshop_checkout_requests',
        'entitlements','dataset_requests','dataset_projections')) and value['payment_events'] ==
        (2 if state == 'revoked' else 1), 'api21_measurement_counts')
    array(value['orders']); require(len(value['orders']) == 1, 'api21_measurement_orders')
    order = value['orders'][0]
    exact(order, ('order_id', 'state', 'owner', 'configuration_id', 'region'))
    for key in ('order_id','owner','configuration_id'): _paid_uuid(order[key])
    require(order['state'] == state and order['configuration_id'] == scope['configuration'] and
            order['region'] == 'US', 'api21_measurement_scope')
    return order


def _api21_paid_rows(paid, scope, *, isolation, revoked):
    exact(paid, PAID_ROW_FIELDS)
    for table,fields in PAID_ROW_FIELDS.items():
        array(paid[table]); require(len(paid[table]) <= 64, 'api21_paid_row_limit')
        for row in paid[table]:
            exact(row, fields.split())
            for key,value in row.items():
                if value is None and key in PAID_ROW_NULLABLE[table]: continue
                if key in ('firebase_auth_time','amount_minor','preparation_attempts'): integer(value)
                elif key == 'livemode': require(type(value) is bool, 'api21_paid_scalar')
                elif key == 'preparation_index_job_ids':
                    array(value)
                    for item in value: _paid_uuid(item)
                    unique(value)
                else: string(value)
    accounts = paid['customer_accounts']
    require(len(accounts) == (2 if isolation else 1) and
        {row['firebase_uid'] for row in accounts} == ({'fixture-user','fixture-other'} if isolation else {'fixture-user'}),
        'api21_accounts')
    for row in accounts:
        _paid_uuid(row['customer_account_id']); _paid_uuid(row['personal_organization_id'])
        require(row['firebase_project_id'] == 'fixture-project' and row['status'] == 'active', 'api21_accounts')
        timestamp(row['created_at'])
    ids = [row['customer_account_id'] for row in accounts]; unique(ids)
    unique([row['personal_organization_id'] for row in accounts])
    owner = next(row for row in accounts if row['firebase_uid'] == 'fixture-user')
    sessions = paid['auth_sessions']
    require(len(sessions) == (3 if isolation else 1) and
            {row['customer_account_id'] for row in sessions} == set(ids), 'api21_sessions')
    require(all(sum(row['customer_account_id'] == account['customer_account_id'] for row in sessions) ==
        (2 if isolation and account['customer_account_id'] == owner['customer_account_id'] else 1) for account in accounts), 'api21_session_owners')
    tokens = []
    for row in sessions:
        require(re.fullmatch(r'\\x[a-f0-9]{64}',row['session_token_hash']) is not None, 'api21_session_hash')
        tokens.append(row['session_token_hash'])
        require(timestamp(row['created_at']) <= timestamp(row['expires_at']), 'api21_session_time')
        if row['revoked_at'] is not None: timestamp(row['revoked_at'])
    unique(tokens)
    for table in ('workshop_orders','entitlements','dataset_requests','dataset_projections'):
        require(len(paid[table]) == 1, 'api21_settlement_inventory')
    order,grant,request,projection = (paid[table][0] for table in
        ('workshop_orders','entitlements','dataset_requests','dataset_projections'))
    for row,keys in ((order, ('order_id','customer_account_id','organization_id','configuration_id',
            'dataset_request_id','dataset_product_id','entitlement_id')),
            (grant, ('entitlement_id','commerce_order_id','configuration_id','customer_account_id',
                'dataset_request_id','organization_id','payment_event_id')),
            (request, ('dataset_request_id','dataset_product_id','organization_id','correlation_id')),
            (projection, ('dataset_projection_id','dataset_request_id','dataset_product_id','entitlement_id'))):
        for key in keys: _paid_uuid(row[key])
    if request['vehicle_id'] is not None:
        _paid_uuid(request['vehicle_id'])
        require(request['vehicle_id'] == scope['vehicle'], 'api21_paid_scope')
    require(order['customer_account_id'] == grant['customer_account_id'] == owner['customer_account_id'] and
        order['organization_id'] == grant['organization_id'] == request['organization_id'] == owner['personal_organization_id'] and
        order['configuration_id'] == grant['configuration_id'] == request['vehicle_key'] == scope['configuration'] and
        order['region'] == grant['region'] == request['region'] == 'US' and
        order['order_id'] == grant['commerce_order_id'] == request['correlation_id'] and
        order['dataset_request_id'] == grant['dataset_request_id'] == request['dataset_request_id'] == projection['dataset_request_id'] and
        order['entitlement_id'] == grant['entitlement_id'] == projection['entitlement_id'] and
        order['dataset_product_id'] == request['dataset_product_id'] == projection['dataset_product_id'], 'api21_paid_scope')
    require(order['amount_minor'] == 2000 and order['currency'] == 'USD' and order['livemode'] is False and
        order['stripe_account_id'] == 'acct_fixture' and order['expected_price_id'] == 'price_fixture' and
        order['terms_version'] == 'workshop-v1' and order['status'] == ('revoked' if revoked else 'paid') and
        grant['status'] == ('revoked' if revoked else 'active'), 'api21_payment_binding')
    for row,key,reason in ((order,'revoked_at','revocation_reason_code'),(grant,'revoked_at','revoke_reason')):
        if revoked:
            timestamp(row[key]); require(row[reason] == 'full_refund', 'api21_revocation')
        else:
            require(row[key] is None and row[reason] is None, 'api21_revocation')
    for row,key in ((order,'paid_at'),(order,'created_at'),(order,'updated_at'),(grant,'granted_at'),
                    (request,'created_at'),(request,'updated_at'),(projection,'created_at')): timestamp(row[key])
    return order


def _api21_snapshot(snapshot, scope, *, work, isolation=False, revoked=False):
    exact(snapshot, ('article','asset_calls','counts','ensure','ensure_requests','grant_calls',
        'immutable_rows','immutable_sha256','model_calls','paid_rows','payment_calls','provider_calls',
        'provider_traces','proxy','selector_ensure','selector_ensure_requests','source_calls','workers'))
    for key in ('model_calls','grant_calls','payment_calls'): integer(snapshot[key])
    require(snapshot['payment_calls'] > 0, 'api21_payment_work')
    for group in ('ensure','selector_ensure'):
        counts=snapshot[group]; exact(counts, ('entered','completed','active'))
        for value in counts.values(): integer(value)
        require(counts['active'] == 0 and counts['entered'] == counts['completed'], 'api21_unfinished_work')
        requests=snapshot[group+'_requests']; array(requests)
        require(len(requests) == counts['entered'], 'api21_request_inventory')
        for request in requests:
            exact(request, ('scope','payload','request_id','started_at','completed','status',
                            'duration_seconds','finished_at'))
            require(request['completed'] is True and type(request['status']) is int and
                    request['status'] == 200 and type(request['payload']) is dict and
                    type(request['request_id']) is str and type(request['scope']) is str,
                    'api21_completed_request')
            _api21_elapsed(request['duration_seconds'])
            require(timestamp(request['started_at']) <= timestamp(request['finished_at']), 'api21_request_time')
    for group in ('provider_calls','source_calls','asset_calls'):
        exact(snapshot[group], ('bankone','banktwo'))
        for value in snapshot[group].values(): integer(value)
    traces=snapshot['provider_traces']; exact(traces, ('bankone','banktwo'))
    for bank,paths in traces.items():
        array(paths)
        require(len(paths) == snapshot['provider_calls'][bank], 'api21_provider_trace')
        for path in paths:
            string(path); require(path.startswith('/') and len(path) <= 4096, 'api21_provider_trace')
        resources=[unquote(path.split('/resources/',1)[1]) for path in paths if '/resources/' in path]
        require(snapshot['source_calls'][bank] == resources.count('body') and
                snapshot['asset_calls'][bank] == len(resources)-resources.count('body'), 'api21_resource_trace')
    proxy=snapshot['proxy']
    exact(proxy, ('request_received','upstream_completed','downstream_completed','downstream_waiting','response_captured','errors'))
    for key in ('request_received','upstream_completed','downstream_completed','downstream_waiting'): integer(proxy[key])
    require(type(proxy['response_captured']) is bool and proxy['errors'] == [] and
        proxy['request_received'] >= proxy['upstream_completed'] >= proxy['downstream_completed'] and
        proxy['downstream_waiting'] <= proxy['upstream_completed']-proxy['downstream_completed'], 'api21_proxy')
    require(proxy['request_received'] == proxy['upstream_completed'] == proxy['downstream_completed'] ==
        snapshot['model_calls'] and proxy['downstream_waiting'] == 0 and
        proxy['response_captured'] is (snapshot['model_calls'] > 0), 'api21_proxy_conservation')
    workers=snapshot['workers']; array(workers)
    require(len(workers) == (2 if work else 0), 'api21_worker_inventory')
    for worker in workers:
        exact(worker, ('kind','alive','exit_code'))
        require(worker['kind'] == 'cli' and worker['alive'] is True and worker['exit_code'] is None, 'api21_live_worker')
    rows=snapshot['immutable_rows']; exact(rows, PAID_PG_TABLES)
    for values in rows.values():
        array(values); require(len(values) <= 4096 and all(type(row) is dict and row for row in values), 'api21_pg_rows')
    digest(snapshot['immutable_sha256'])
    require(sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode('utf-8')) == snapshot['immutable_sha256'],
            'api21_row_hash')
    article=snapshot['article']; require(type(article) is dict, 'api21_article')
    require(article.get('canonical_article_id') == scope['article'] and article.get('provider_slug') == scope['provider'] and
        article.get('vehicle_configuration_id') == scope['configuration'] and article.get('vehicle_id') == scope['vehicle'],
        'api21_article')
    ids=[]
    for row in rows['canonical_articles']:
        _paid_uuid(row.get('canonical_article_id')); ids.append(row['canonical_article_id'])
        enum(row.get('provider_slug'), ('bankone','banktwo'))
    unique(ids)
    selected=[row for row in rows['canonical_articles'] if row['canonical_article_id'] == scope['article']]
    require(len(selected) == 1 and all(selected[0].get(key) == article.get(key) for key in
        ('provider_slug','vehicle_configuration_id','vehicle_id')), 'api21_article_seam')
    exact(snapshot['counts'], PAID_PG_COUNT_TABLES)
    for key,table in PAID_PG_COUNT_TABLES.items():
        integer(snapshot['counts'][key])
        counted=[]
        for row in rows[table]:
            require('canonical_article_id' in row, 'api21_count_row')
            if row['canonical_article_id'] is not None or table != 'source_fetch_jobs': _paid_uuid(row['canonical_article_id'])
            if table == 'source_fetch_jobs': string(row.get('job_kind'))
            if table == 'canonical_article_revisions': string(row.get('status'))
            if row['canonical_article_id'] != scope['article']: continue
            if key == 'article_jobs' and row['job_kind'] != 'article': continue
            if key == 'published_revisions' and row['status'] != 'published': continue
            counted.append(row)
        require(len(counted) == snapshot['counts'][key], 'api21_count_binding')
    if work:
        require(snapshot['model_calls'] > 0 and snapshot['counts']['published_revisions'] == 1, 'api21_warm_publication')
    order=_api21_paid_rows(snapshot['paid_rows'],scope,isolation=isolation,revoked=revoked)
    for table in ('customer_accounts','auth_sessions','workshop_orders'):
        require(rows[table] == snapshot['paid_rows'][table], 'api21_paid_row_seam')
    return order


def _api21_order_seam(measured, order):
    require(measured['order_id'] == order['order_id'] and measured['owner'] == order['customer_account_id'] and
        measured['configuration_id'] == order['configuration_id'] and measured['region'] == order['region'] and
        measured['state'] == order['status'], 'api21_order_seam')


def _api21_ready(ready, provider):
    exact(ready, ('version','kind','origin','certificate_sha256','sdk_sha256','scope'))
    require(ready['version'] == 'v1' and ready['kind'] == 'api-fixture', 'api21_ready_identity')
    digest(ready['certificate_sha256']); digest(ready['sdk_sha256'])
    match=re.fullmatch(r'https://127\.0\.0\.1:([1-9][0-9]{0,4})',ready['origin']) if type(ready['origin']) is str else None
    require(match is not None and int(match[1]) <= 65535, 'api21_ready_origin')
    scope=ready['scope']; exact(scope, ('configuration','adjacent','other_region','vehicle','article','unscoped','provider'))
    values=[]
    for key in ('configuration','adjacent','other_region','vehicle','article','unscoped'):
        _paid_uuid(scope[key]); values.append(scope[key])
    unique(values); require(scope['provider'] == provider, 'api21_ready_scope')
    return scope


def _api21_evidence(evidence, ready, engine, root, *, passed):
    fields=('engine_revisions','input_sha256','version','mode','candidate_sha','sdk_sha256',
        'playwright_version','results','provenance')
    require(type(evidence) is dict, 'api21_evidence')
    exact(evidence, (*fields,'browser_versions') if 'browser_versions' in evidence else fields)
    require(not passed or 'browser_versions' in evidence, 'api21_browser_versions')
    require(evidence['version'] == 'v1' and evidence['mode'] == 'api-fixture' and
        evidence['candidate_sha'] == API21_SOURCE_SHA and evidence['playwright_version'] == '1.64.1', 'api21_evidence_identity')
    revisions=evidence['engine_revisions']
    require(type(revisions) is dict and 0 < len(revisions) <= 32, 'api21_engine_revisions')
    for key,value in revisions.items():
        string(key); string(value); require(len(key) <= 96 and len(value) <= 256, 'api21_engine_revisions')
    if 'browser_versions' in evidence:
        exact(evidence['browser_versions'], (engine,)); string(evidence['browser_versions'][engine])
        require(len(evidence['browser_versions'][engine]) <= 256, 'api21_browser_versions')
    require(evidence['input_sha256'] == API21_SOURCE_INPUTS, 'api21_source_inputs')
    provenance=evidence['provenance']; exact(provenance, ('assets','certificate_sha256'))
    exact(provenance['assets'], API21_SOURCE_ASSETS)
    for name,asset in provenance['assets'].items():
        exact(asset, ('sha256','bytes')); digest(asset['sha256']); integer(asset['bytes'])
        require(asset == API21_SOURCE_ASSETS[name], 'api21_source_assets')
    require(evidence['sdk_sha256'] == ready['sdk_sha256'] == API21_SOURCE_ASSETS['firebase-web.mjs']['sha256'] and
        provenance['certificate_sha256'] == ready['certificate_sha256'], 'api21_provenance_seam')
    rows=evidence['results']; array(rows); require(len(rows) <= 1 and (not passed or len(rows) == 1), 'api21_result_inventory')
    if not rows:
        require('browser_versions' not in evidence, 'api21_browser_metadata_branch')
        return None
    row=rows[0]
    require(type(row) is dict and row.get('browser') == engine and row.get('scenario') == root,
            'api21_row_identity')
    enum(row.get('status'), ('passed','failed','unavailable'))
    if row['status'] != 'passed':
        fields=('browser','scenario','status','error')
        require(row['status'] != 'unavailable' or 'browser_versions' not in evidence,
                'api21_browser_metadata_branch')
        exact(row, (*fields,'elapsed_seconds') if row['status'] == 'failed' else fields)
        require(row['status'] != 'failed' or 'elapsed_seconds' in row, 'api21_failed_row')
        if 'elapsed_seconds' in row: _api21_elapsed(row['elapsed_seconds'])
        require(type(row['error']) is str and len(row['error']) <= 65536, 'api21_failed_row')
        require(not passed, 'api21_outcome_seam')
        return row
    exact(row, ('browser','scenario','elapsed_seconds','status','assertions','provider','requests','measurement','restart','warm'))
    require(row['provider'] == ready['scope']['provider'], 'api21_row_provider')
    _api21_elapsed(row['elapsed_seconds']); _paid_assertions(row['assertions'],API21_ASSERTIONS[root])
    requests=row['requests']; array(requests); require(len(requests) <= 8192, 'api21_request_limit')
    get_paths={'/workshop/','/workshop/purchase-config.json','/workshop/fonts/InstrumentSans.ttf',
               '/auth/config','/auth/session','/v1/catalog/years','/v1/workshop/quote','/v1/workshop/library'}
    get_paths.update('/workshop/'+name for name in API21_SOURCE_ASSETS)
    get_patterns=(r'/v1/workshop/orders/\{uuid\}',
        r'/v1/catalog/years/2024/makes(?:/example/models(?:/car/configurations)?)?',
        r'/v1/catalog/vehicles/\{uuid\}/articles(?:/\{uuid\}(?:/source)?)?',
        r'/v1/catalog/images/\{capability\}')
    for request in requests:
        exact(request, ('method','path'))
        method,path=request['method'],request['path']
        require(type(method) is str and type(path) is str, 'api21_request_template')
        allowed=(method == 'GET' and (path in get_paths or any(re.fullmatch(pattern,path) for pattern in get_patterns))) or (
            method == 'POST' and (path in ('/auth/firebase/session','/auth/logout','/v1/workshop/checkout-sessions') or
            re.fullmatch(r'/v1/catalog/vehicles/\{uuid\}/articles/\{uuid\}/prepare',path) is not None))
        require(allowed, 'api21_request_template')
    return row


def inspect_api21_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                           profile_version='api21-fixture-v1'):
    """Partial retained-byte consistency only. This function cannot grant credit."""
    digest(candidate_sha,40); digest(trusted_base_sha,40); digest(profile_sha256)
    require(candidate_sha == API21_SOURCE_SHA, 'api21_source_candidate')
    require(type(profile_version) is str and profile_version == 'api21-fixture-v1', 'api21_profile_version')
    required={'workshop-browser-api.xml'}; optional=set(); early_missing=set(); prefixes=[]
    for _,root,engine,provider in API21_CASES:
        prefix='workshop-browser/'+root+'/'+engine+'-'+provider+'/'
        prefixes.append(prefix); required.update(prefix+name for name in API21_SUPPORT)
        early_missing.update((prefix+'ready.json',prefix+'browser/evidence.json'))
        optional.add(prefix+'browser/'+engine+'/'+root+'-failure.png')
    require(required-early_missing <= set(store.by_ref) <= required|optional, 'api21_support_inventory')
    # Read every declared byte, including opaque diagnostic logs/screenshots.
    raw={}
    for ref,record in store.by_ref.items():
        require(record['visibility'] == 'private' and record['kind'] ==
            ('junit' if ref == 'workshop-browser-api.xml' else 'raw'), 'api21_artifact_declaration')
        raw[ref]=store.read(record['artifact_id'])
    outcomes=_api21_junit(raw['workshop-browser-api.xml'])
    observed=[]; diagnostics=[]; databases=[]
    for index,((case_id,root,engine,provider),prefix) in enumerate(zip(API21_CASES,prefixes)):
        docs={}
        for name in ('result.json','ready.json','browser/evidence.json'):
            if prefix+name not in raw: continue
            value=strict_raw_json(raw[prefix+name])
            _api21_identity(value,candidate_sha,trusted_base_sha,profile_sha256,profile_version)
            docs[name]=value
        result=docs['result.json']
        fields=('version','mode','candidate_sha','browser','provider','test','fixture_database','passed')
        require(type(result.get('passed')) is bool, 'api21_result_passed')
        passed=result['passed']
        if passed: exact(result, (*fields,'final_snapshot','worker_exits'))
        else:
            require(set(result) >= set(fields) and set(result) <= set((*fields,'final_snapshot','worker_exits')),
                    'api21_failed_result')
        require(result['version'] == 'v1' and result['mode'] == 'api-fixture' and
            result['candidate_sha'] == candidate_sha and result['browser'] == engine and
            result['provider'] == provider and result['test'] == root, 'api21_result_identity')
        database=result['fixture_database']; string(database)
        require(re.fullmatch(r'[a-z][a-z0-9_]{0,62}',database) is not None, 'api21_fixture_database')
        databases.append(database)
        ready=docs.get('ready.json'); evidence=docs.get('browser/evidence.json')
        require(not passed or ready is not None and evidence is not None, 'api21_support_inventory')
        require(ready is not None or evidence is None, 'api21_partial_provenance')
        scope=_api21_ready(ready,provider) if ready is not None else None
        row=_api21_evidence(evidence,ready,engine,root,passed=passed) if evidence is not None else None
        if evidence is None:
            require(not passed and 'final_snapshot' not in result and 'worker_exits' not in result,
                    'api21_partial_result')
        require((outcomes[index] == 'passed') == passed, 'api21_junit_result_seam')
        screenshot=prefix+'browser/'+engine+'/'+root+'-failure.png'
        require(not passed or screenshot not in raw, 'api21_success_screenshot')
        google=root == API21_CASES[0][1]; isolation=root == 'test_browser_account_scope_and_revocation_real_api'
        refund=root == 'test_browser_signed_refund_blocks_old_links_real_api'
        require('worker_exits' not in result or 'final_snapshot' in result, 'api21_retained_source_order')
        require('final_snapshot' not in result or row is not None and row['status'] == 'passed' and
                'browser_versions' in evidence,
                'api21_retained_source_order')
        final_order=None
        if 'final_snapshot' in result:
            final_order=_api21_snapshot(result['final_snapshot'],scope,work=not google,isolation=isolation,revoked=refund)
        if row is not None and row['status'] == 'passed':
            measurement=row['measurement']; measured=_api21_measurement(measurement,scope,state='revoked' if refund else 'paid')
            if final_order is not None:
                _api21_order_seam(measured,final_order)
                paid=result['final_snapshot']['paid_rows']
                for key in ('auth_sessions','workshop_orders','entitlements','dataset_requests','dataset_projections'):
                    require(measurement[key] == len(paid[key]), 'api21_measurement_pg_seam')
                require(measurement['workshop_checkout_requests'] == len(result['final_snapshot']['immutable_rows']['workshop_checkout_requests']),
                        'api21_measurement_pg_seam')
            restart=row['restart']; exact(restart, ('runtime_before','runtime_after','before','after'))
            for key in ('runtime_before','runtime_after'):
                exact(restart[key], ('application_generation',)); integer(restart[key]['application_generation'])
            require(restart['runtime_after']['application_generation'] == restart['runtime_before']['application_generation']+1,
                    'api21_restart_generation')
            for key in ('before','after'):
                order=_api21_measurement(restart[key],scope,state='paid')
                require(all(order[field] == measured[field] for field in ('order_id','owner','configuration_id','region')),
                        'api21_restart_order')
            require(all(restart['before'][key] == restart['after'][key] for key in API21_DURABLE), 'api21_restart_durability')
            for key in API21_MEASUREMENT:
                require(measurement[key] >= restart['after'][key], 'api21_measurement_regression')
            require(isolation or measurement['auth_sessions'] == restart['after']['auth_sessions'], 'api21_session_phase')
            warm=row['warm']
            if google: exact(warm, ())
            else:
                exact(warm, ('before','after','reader_before','reader_after'))
                for key in ('before','after'):
                    order=_api21_snapshot(warm[key],scope,work=True)
                    require(order['order_id'] == measured['order_id'] and order['customer_account_id'] == measured['owner'] and
                        order['configuration_id'] == measured['configuration_id'] and order['region'] == measured['region'],
                        'api21_warm_order')
                    if final_order is not None:
                        require(all(order[field] == final_order[field] for field in
                            ('order_id','customer_account_id','organization_id','configuration_id','dataset_request_id',
                             'dataset_product_id','entitlement_id')), 'api21_warm_order')
                for key in ('provider_calls','source_calls','asset_calls','model_calls','counts','immutable_sha256'):
                    require(warm['before'][key] == warm['after'][key], 'api21_warm_drift')
                integer(warm['reader_before']); integer(warm['reader_after'])
                require(warm['reader_after'] > warm['reader_before'] and measurement['image_reads'] >= warm['reader_after'],
                        'api21_warm_reader')
        if 'worker_exits' in result:
            exits=result['worker_exits']; array(exits)
            require(len(exits) == (0 if google else 2), 'api21_worker_cleanup_inventory')
            # Equal records are valid: source retains no distinct process identifiers.
            for worker in exits:
                exact(worker, ('kind','exit_code','terminated','intentional_cleanup','alive_before_cleanup'))
                require(worker['kind'] == 'cli' and type(worker['exit_code']) is int and
                    all(worker[key] is True for key in ('terminated','intentional_cleanup','alive_before_cleanup')),
                    'api21_worker_cleanup')
        if not passed:
            category='producer_partial' if row is None or row['status'] == 'passed' else 'producer_'+row['status']
            diagnostics.append(dict(case_id=case_id,category=category))
        else:
            observed.append(case_id)
    unique(databases); store.recheck()
    return dict(status='unavailable',complete=False,profile_version=profile_version,
        candidate_sha=candidate_sha,trusted_base_sha=trusted_base_sha,observed_case_ids=observed,
        verified_case_ids=[],accepted_case_credit=0,accepted_new_case_credit=0,diagnostics=diagnostics,
        missing_validation_families=list(API21_MISSING_FAMILIES),**{flag:False for flag in FLAGS})


# Current producer-v2 is a separate internal schema, never an enabled profile.
API21_V2_SOURCE_SHA = '6949eb1b1a5b93c9b2eb0579328e24c697f6f331'
API21_V2_SOURCE_TREE = '47ec54b1896c83a39b6637a6ce944d3620414f4e'
API21_V2_SOURCE_INPUTS = {'apps/api-go/workshop_browser_fixture_test.go': '7520a24bcfa06fe64810c6c17625563d29a2387c6d0531a61713f50b2098bf33',
 'scripts/dev/fixtures/workshop_customer/firebase_transport.js': '96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63',
 'scripts/dev/fixtures/workshop_customer/hostile_source.json': '076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1',
 'scripts/dev/fixtures/workshop_customer/scenarios.json': '83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9',
 'scripts/dev/fixtures/workshop_customer/stripe_checkout.html': '26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083',
 'scripts/dev/workshop_browser_smoke.py': 'e5424bfeb412d321638ebab31362774226d49caeacd53ffc929a54c00bbf9a7a',
 'workers/ingestion-python/tests/test_workshop_browser_integration.py': '1d83bcaa7e57b59cc2a6b8e64d9e4ab9dc327389c21a905b85dbec7267bc976b'}
API21_V2_INPUT_ORDER = ('scripts/dev/workshop_browser_smoke.py',
 'scripts/dev/fixtures/workshop_customer/scenarios.json',
 'scripts/dev/fixtures/workshop_customer/firebase_transport.js',
 'scripts/dev/fixtures/workshop_customer/hostile_source.json',
 'scripts/dev/fixtures/workshop_customer/stripe_checkout.html',
 'apps/api-go/workshop_browser_fixture_test.go',
 'workers/ingestion-python/tests/test_workshop_browser_integration.py')
API21_V2_SOURCE_ASSETS = {'app.mjs': {'bytes': 37870, 'sha256': '2bfe85a3f5e0b77bc55fe0c18b50b35a9bab6444f6a640bf6a6a36bd57ab4c46'},
 'article-read.mjs': {'bytes': 2579,
                      'sha256': '2957242037d4bc3ce7894ae2c7e4bae1636406d0256dd75b6150e78c1c4e5178'},
 'auth.mjs': {'bytes': 7908, 'sha256': 'ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2'},
 'catalog.mjs': {'bytes': 11688,
                 'sha256': 'cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52'},
 'commerce.mjs': {'bytes': 7369,
                  'sha256': 'e7f8e2fd45d6cd9f4ec2ef2f3a50d3f090f34e2562d4bbc58f9c23d06e8a1142'},
 'firebase-web.mjs': {'bytes': 112641,
                      'sha256': 'bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1'},
 'firebase-web.mjs.LEGAL.txt': {'bytes': 35536,
                                'sha256': '70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319'},
 'firebase-web.provenance.json': {'bytes': 2237,
                                  'sha256': '0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a'},
 'index.html': {'bytes': 10868, 'sha256': '8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68'},
 'progress.mjs': {'bytes': 1076,
                  'sha256': 'dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48'},
 'styles.css': {'bytes': 20773, 'sha256': 'c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c'}}
API21_V2_PHASES = {'test_browser_account_scope_and_revocation_real_api': ['setup',
                                                        'metadata',
                                                        'initial-measurement',
                                                        'signed-in-measurement',
                                                        'checkout-http',
                                                        'pending-checkout-measurement',
                                                        'return-without-grant-measurement',
                                                        'settlement-control',
                                                        'settled-measurement',
                                                        'owner-library-initial-http',
                                                        'owner-library-reload-http',
                                                        'library-reload-measurement',
                                                        'restart-before-measurement',
                                                        'runtime-before',
                                                        'restart-control',
                                                        'runtime-poll',
                                                        'owner-library-restart-http',
                                                        'restart-after-measurement',
                                                        'start-workers-control',
                                                        'source-page-http',
                                                        'source-image-http',
                                                        'source-review-http',
                                                        'release-model-control',
                                                        'warm-before-snapshot',
                                                        'reader-before-measurement',
                                                        'warm-page-http',
                                                        'warm-image-http',
                                                        'warm-pinned-source-http',
                                                        'warm-after-snapshot',
                                                        'reader-after-measurement',
                                                        'adjacent-denial',
                                                        'other-region-denial',
                                                        'unscoped-article-denial',
                                                        'legacy-vehicle-denial',
                                                        'other-catalogue-denial',
                                                        'other-library-http',
                                                        'other-image-denial',
                                                        'logout-image-denial',
                                                        'disable-control',
                                                        'disabled-image-denial',
                                                        'final-measurement'],
 'test_browser_google_exchange_checkout_library_real_api': ['setup',
                                                            'metadata',
                                                            'initial-measurement',
                                                            'signed-in-measurement',
                                                            'checkout-first-http',
                                                            'checkout-first-delivery',
                                                            'response-lost-measurement',
                                                            'response-lost-snapshot',
                                                            'checkout-retry-http',
                                                            'checkout-retry-delivery',
                                                            'pending-checkout-measurement',
                                                            'retry-pending-snapshot',
                                                            'return-without-grant-measurement',
                                                            'settlement-control',
                                                            'settled-measurement',
                                                            'owner-library-initial-http',
                                                            'owner-library-reload-http',
                                                            'library-reload-measurement',
                                                            'restart-before-measurement',
                                                            'runtime-before',
                                                            'restart-control',
                                                            'runtime-poll',
                                                            'owner-library-restart-http',
                                                            'restart-after-measurement',
                                                            'final-measurement'],
 'test_browser_owned_source_canonical_and_media_real_api': ['setup',
                                                            'metadata',
                                                            'initial-measurement',
                                                            'signed-in-measurement',
                                                            'checkout-http',
                                                            'pending-checkout-measurement',
                                                            'return-without-grant-measurement',
                                                            'settlement-control',
                                                            'settled-measurement',
                                                            'owner-library-initial-http',
                                                            'owner-library-reload-http',
                                                            'library-reload-measurement',
                                                            'restart-before-measurement',
                                                            'runtime-before',
                                                            'restart-control',
                                                            'runtime-poll',
                                                            'owner-library-restart-http',
                                                            'restart-after-measurement',
                                                            'start-workers-control',
                                                            'source-page-http',
                                                            'source-image-http',
                                                            'source-review-http',
                                                            'release-model-control',
                                                            'warm-before-snapshot',
                                                            'reader-before-measurement',
                                                            'warm-page-http',
                                                            'warm-image-http',
                                                            'warm-pinned-source-http',
                                                            'warm-after-snapshot',
                                                            'reader-after-measurement',
                                                            'final-measurement'],
 'test_browser_signed_refund_blocks_old_links_real_api': ['setup',
                                                          'metadata',
                                                          'initial-measurement',
                                                          'signed-in-measurement',
                                                          'checkout-http',
                                                          'pending-checkout-measurement',
                                                          'return-without-grant-measurement',
                                                          'settlement-control',
                                                          'settled-measurement',
                                                          'owner-library-initial-http',
                                                          'owner-library-reload-http',
                                                          'library-reload-measurement',
                                                          'restart-before-measurement',
                                                          'runtime-before',
                                                          'restart-control',
                                                          'runtime-poll',
                                                          'owner-library-restart-http',
                                                          'restart-after-measurement',
                                                          'start-workers-control',
                                                          'source-page-http',
                                                          'source-image-http',
                                                          'source-review-http',
                                                          'release-model-control',
                                                          'warm-before-snapshot',
                                                          'reader-before-measurement',
                                                          'warm-page-http',
                                                          'warm-image-http',
                                                          'warm-pinned-source-http',
                                                          'warm-after-snapshot',
                                                          'reader-after-measurement',
                                                          'refund-control',
                                                          'refund-old-image-denial',
                                                          'refund-source-denial',
                                                          'refund-detail-denial',
                                                          'revoked-measurement',
                                                          'final-measurement']}
API21_V2_REASONS = ('not_observed',
 'unsupported_byte_source',
 'not_required_image_body',
 'over_limit',
 'invalid_json',
 'invalid_utf8',
 'read_failed',
 'secret_detected',
 'launch_failed',
 'timeout',
 'cancelled',
 'assertion_failed',
 'http_failed',
 'close_failed',
 'signal_failed',
 'reap_failed',
 'mapping_unavailable',
 'log_not_finalized',
 'source_binding_failed',
 'publication_failed',
 'prior_failure',
 'internal_error')
API21_V2_MISSING_FAMILIES = ('actual_child_go_browser_exit_receipts',
 'parent_pytest_exit_and_command_receipts',
 'signed_settlement_refund_http_bytes_and_authentic_delivery',
 'runtime_image_browser_cache_sdk_install_identity',
 'authenticated_capture_source_observer_and_containment',
 'global_worker_log_per_case_ownership_mapping',
 'finite_api_success_schedule',
 'junit_byte_preserving_capture_mapping',
 'all_final180_families_and_profile_promotion',
 'independent_authentic_raw_review',
 'actual_engine_os_exit_and_descendant_reap',
 'original_go_webhook_request_signature_response_capture',
 'source_contract_current_integration_rebinding',
 'dto_trace_16MiB_producer_8MiB_consumer_conflict',
 'v2_consumer_schema_validator_and_profile',
 'producer_observations_are_unexecuted_until_separate_capture_gate')
API21_V2_COMMANDS = {'browser-runner': {'argv': ['$PYTHON',
                             '$REPO/scripts/dev/workshop_browser_smoke.py',
                             '--base-url',
                             '$ORIGIN',
                             '--mode',
                             'api-fixture',
                             '--browser',
                             '{engine}',
                             '--candidate-sha',
                             '6949eb1b1a5b93c9b2eb0579328e24c697f6f331',
                             '--output',
                             '$CASE/browser'],
                    'cwd': '.',
                    'logs': ['browser.stdout.log', 'browser.stderr.log'],
                    'observer_role': 'child-pytest'},
 'child-pytest': {'argv': ['$PYTHON',
                           '-m',
                           'pytest',
                           '-q',
                           '-p',
                           'no:cacheprovider',
                           'workers/ingestion-python/tests/test_workshop_browser_integration.py::{case_id}'],
                  'cwd': '.',
                  'logs': ['child.log', 'child.log'],
                  'observer_role': 'parent-pytest'},
 'go-test': {'argv': ['go',
                      'test',
                      '-count=1',
                      '-run',
                      '^TestWorkshopBrowserFixtureHTTP$',
                      '-timeout=85s',
                      '.'],
             'cwd': 'apps/api-go',
             'logs': ['go-fixture.log', 'go-fixture.log'],
             'observer_role': 'child-pytest'}}
API21_V2_PHASE_ROUTES = {'adjacent-denial': '/v1/catalog/vehicles/{adjacent}/articles',
 'checkout-first-http': '/v1/workshop/checkout-sessions',
 'checkout-http': '/v1/workshop/checkout-sessions',
 'checkout-retry-http': '/v1/workshop/checkout-sessions',
 'disable-control': '/__fixture/disable',
 'disabled-image-denial': '/v1/catalog/images/{capability}',
 'legacy-vehicle-denial': '/v1/catalog/vehicles/{vehicle}/articles',
 'logout-image-denial': '/v1/catalog/images/{capability}',
 'metadata': '/__fixture/metadata',
 'other-catalogue-denial': '/v1/catalog/vehicles/{configuration}/articles',
 'other-image-denial': '/v1/catalog/images/{capability}',
 'other-library-http': '/v1/workshop/library',
 'other-region-denial': '/v1/catalog/vehicles/{other_region}/articles',
 'refund-control': '/__fixture/payment/refund',
 'refund-detail-denial': '/v1/catalog/vehicles/{configuration}/articles/{article}',
 'refund-old-image-denial': '/v1/catalog/images/{capability}',
 'refund-source-denial': '/v1/catalog/vehicles/{configuration}/articles/{article}/source',
 'release-model-control': '/__fixture/control/release-model',
 'restart-control': '/__fixture/restart',
 'runtime-before': '/__fixture/runtime',
 'runtime-poll': '/__fixture/runtime',
 'settlement-control': '/__fixture/payment/settle',
 'source-image-http': '/v1/catalog/images/{capability}',
 'source-page-http': '/v1/catalog/vehicles/{configuration}/articles/{article}',
 'source-review-http': '/v1/catalog/vehicles/{configuration}/articles/{article}/source',
 'start-workers-control': '/__fixture/control/start-workers',
 'unscoped-article-denial': '/v1/catalog/vehicles/{configuration}/articles/{unscoped}',
 'warm-image-http': '/v1/catalog/images/{capability}',
 'warm-page-http': '/v1/catalog/vehicles/{configuration}/articles/{article}',
 'warm-pinned-source-http': '/v1/catalog/vehicles/{configuration}/articles/{article}/source'}
API21_V2_ROUTES = ('/__fixture/control/release-model',
 '/__fixture/control/start-workers',
 '/__fixture/disable',
 '/__fixture/measurement',
 '/__fixture/metadata',
 '/__fixture/payment/refund',
 '/__fixture/payment/settle',
 '/__fixture/restart',
 '/__fixture/runtime',
 '/__fixture/snapshot',
 '/v1/catalog/images/{capability}',
 '/v1/catalog/vehicles/{adjacent}/articles',
 '/v1/catalog/vehicles/{configuration}/articles',
 '/v1/catalog/vehicles/{configuration}/articles/{article}',
 '/v1/catalog/vehicles/{configuration}/articles/{article}/source',
 '/v1/catalog/vehicles/{configuration}/articles/{unscoped}',
 '/v1/catalog/vehicles/{other_region}/articles',
 '/v1/catalog/vehicles/{vehicle}/articles',
 '/v1/workshop/checkout-sessions',
 '/v1/workshop/library')

def _api21_v2_size(value, limit):
    try:
        raw=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise ContractError('api21_v2_json') from None
    require(len(raw)<=limit,'api21_v2_size')
    return len(raw)


def _api21_v2_reason(value, *, required=False):
    valid=type(value) is str and value in API21_V2_REASONS
    require(valid or value is None and not required,'api21_v2_reason')


def _api21_v2_binding(binding, case, role):
    case_id,root,engine,bank=case
    exact(binding,('binding_state','unavailable_reason','api_observability_version','run_id','attempt_id','case_id','root','engine','bank','candidate_sha','source_tree','source_input_sha256','producer_role'))
    require(binding['api_observability_version']=='api21-producer-v2' and binding['producer_role']==role and binding['root']==root and binding['engine']==engine,'api21_v2_binding')
    enum(binding['binding_state'],('complete','partial'));complete=binding['binding_state']=='complete'
    require(binding['unavailable_reason']==(None if complete else 'source_binding_failed'),'api21_v2_binding')
    fallback=not complete and role=='browser-runner' and binding['source_input_sha256'] is None
    for key in ('run_id','attempt_id'):
        value=binding[key]
        require(value is None and not complete or type(value) is str and re.fullmatch('[a-f0-9]{32}',value) is not None,'api21_v2_binding_token')
    if fallback:
        require(binding['candidate_sha']==API21_V2_SOURCE_SHA and all(binding[key] is None for key in ('run_id','attempt_id','case_id','bank','source_tree','source_input_sha256')),'api21_v2_browser_fallback')
        return False
    require(binding['case_id']==case_id and binding['bank']==bank,'api21_v2_binding_identity')
    candidate=binding['candidate_sha'];tree=binding['source_tree'];inputs=binding['source_input_sha256']
    assigned=candidate==API21_V2_SOURCE_SHA and tree==API21_V2_SOURCE_TREE
    require(assigned or not complete and role!='browser-runner' and candidate is None and tree is None,'api21_v2_binding_source')
    require(type(inputs) is dict,'api21_v2_binding_inputs')
    expected={key:API21_V2_SOURCE_INPUTS[key] for key in API21_V2_INPUT_ORDER[:len(inputs)]}
    require(inputs==expected and len(inputs)<=7 and (assigned or inputs=={}),'api21_v2_binding_inputs')
    if complete or role=='browser-runner':require(inputs==API21_V2_SOURCE_INPUTS,'api21_v2_binding_inputs')
    return complete


def _api21_v2_secret(raw, parsed, invalid):
    protected=re.compile(r'(?i)^(authorization|cookie|set-cookie|token|id_?token|access_?token|refresh_?token|password|csrf(?:_?token)?|firebase_?token|api_?key|client_secret|fixture_token|x-r3-fixture-token)$')
    pattern=re.compile(r'(?i)(bearer |__Host-autodata_session=|eyJ[A-Za-z0-9_-]+\.eyJ)')
    pending=[parsed];nodes=0
    while pending:
        value=pending.pop();nodes+=1;require(nodes<=100000,'api21_v2_body_complexity')
        if type(value) is dict:
            require(not any(protected.fullmatch(key) for key in value),'api21_v2_secret')
            pending.extend(value.values())
        elif type(value) is list:pending.extend(value)
        elif type(value) is str:require(pattern.search(value) is None,'api21_v2_secret')
    text=raw.decode('utf-8',errors='replace')
    require(pattern.search(text) is None and not any(protected.fullmatch(key) for key in re.findall(r'[\"\']([^\"\']+)[\"\']\s*:',text)),'api21_v2_secret')
    require(not invalid or '\\' not in text,'api21_v2_secret')


def _api21_v2_body(body, *, request=False, image=False, empty=False, passed=False):
    import base64
    import binascii
    exact(body,('availability','byte_source','encoding','base64','length','sha256','parsed','reason'))
    available=body['availability'];reason=body['reason'];_api21_v2_reason(reason)
    if available=='unavailable':
        require(body['byte_source']=='unavailable' and reason is not None and all(body[key] is None for key in ('encoding','base64','length','sha256','parsed')) and not passed,'api21_v2_unavailable_body')
        return None
    require(body['byte_source']==('playwright-request-post-data-buffer' if request else 'playwright-response-body'),'api21_v2_body_source')
    integer(body['length']);require(body['length']<=131072,'api21_v2_body_size');digest(body['sha256'])
    if available=='hash_only':
        require(image and not request and body['length']>0 and reason=='not_required_image_body' and all(body[key] is None for key in ('encoding','base64','parsed')),'api21_v2_hash_only')
        return None
    require(available=='retained' and body['encoding']=='base64' and type(body['base64']) is str and reason in (None,'invalid_json','invalid_utf8'),'api21_v2_retained_body')
    try:raw=base64.b64decode(body['base64'],validate=True)
    except (ValueError,binascii.Error):raise ContractError('api21_v2_body_base64') from None
    require(base64.b64encode(raw).decode('ascii')==body['base64'] and len(raw)==body['length'] and hashlib.sha256(raw).hexdigest()==body['sha256'],'api21_v2_body_digest')
    if not raw and empty and not request:
        require(reason is None and body['parsed'] is None,'api21_v2_empty_body');return raw
    parsed=None;failure=None
    try:
        raw.decode('utf-8',errors='strict')
        def pairs(items):
            result={}
            for key,value in items:
                require(key not in result,'api21_v2_duplicate_key');result[key]=value
            return result
        def nonfinite(_):raise ContractError('api21_v2_nonfinite')
        parsed=json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=pairs,parse_constant=nonfinite)
        _api21_v2_size(parsed,262144)
        # Canonical encoding checks Unicode scalar validity without replacing original bytes.
        json.dumps(parsed,ensure_ascii=False,allow_nan=False).encode('utf-8',errors='strict')
    except UnicodeError:failure='invalid_utf8'
    except (ContractError,ValueError,TypeError,RecursionError,OverflowError):failure='invalid_json'
    _api21_v2_secret(raw,parsed,failure is not None)
    require(reason==failure and (failure is None or body['parsed'] is None and not passed),'api21_v2_body_json')
    if failure is None:
        require(_api21_v2_json_equal(parsed,body['parsed']),'api21_v2_body_parsed')
    require(bool(raw) or not passed,'api21_v2_empty_body')
    return raw


def _api21_v2_json_equal(left,right):
    # JSON booleans and numbers are distinct, unlike Python's True == 1.
    def encoded(value):
        try:return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        except (ValueError,TypeError,RecursionError):raise ContractError('api21_v2_json') from None
    return encoded(left)==encoded(right)


def _api21_v2_hash(row, raw, allowed):
    exact(row,('ref','length','sha256'));ref=row['ref'];safe_ref(ref)
    require(ref in allowed and ref in raw,'api21_v2_hash_ref');integer(row['length']);digest(row['sha256'])
    require(row['length']==len(raw[ref]) and row['sha256']==hashlib.sha256(raw[ref]).hexdigest(),'api21_v2_hash')


def _api21_v2_process(process, case, role, raw, *, passed, publication=False):
    fields=('role','observer_role','argv','cwd','launched','events','return_code','return_code_source','wait_kind','intentional_cleanup','reaped','alive_final','started_us','finished_us','stdout_ref','stderr_ref','output_hashes')
    exact(process,fields);case_id,root,engine,bank=case;prefix='workshop-browser/'+root+'/'+engine+'-'+bank+'/'
    schedule=API21_V2_COMMANDS[role];expected=[part.replace('{case_id}',case_id).replace('{engine}',engine) for part in schedule['argv']]
    precommand=role=='browser-runner' and process['argv']==[] and not passed
    require(process['role']==role and process['observer_role']==schedule['observer_role'] and process['cwd']==schedule['cwd'] and (precommand or process['argv']==expected),'api21_v2_process_command')
    for key in ('launched','intentional_cleanup'):require(type(process[key]) is bool,'api21_v2_process_bool')
    for key in ('reaped','alive_final'):require(process[key] is None or type(process[key]) is bool,'api21_v2_process_bool')
    for key in ('started_us','finished_us'):
        if process[key] is not None:integer(process[key])
    if process['started_us'] is not None and process['finished_us'] is not None:require(process['finished_us']>=process['started_us'],'api21_v2_process_time')
    enum(process['return_code_source'],('wait','poll','unavailable'));enum(process['wait_kind'],('normal','cleanup','unavailable'))
    code=process['return_code'];require(code is None or type(code) is int,'api21_v2_process_code')
    events=process['events'];array(events);require(len(events)<=32,'api21_v2_process_events');kinds=[];last=-1
    allowed=('launch-requested','launch-succeeded','launch-failed','wait-completed','timeout','cancelled','term-requested','term-sent','kill-requested','kill-sent','signal-failed','reap-failed')
    for index,event in enumerate(events):
        exact(event,('seq','kind','elapsed_us','return_code','reason'));integer(event['seq'],1);integer(event['elapsed_us'])
        require(event['seq']==index+1 and event['elapsed_us']>=last,'api21_v2_process_sequence');last=event['elapsed_us'];enum(event['kind'],allowed);_api21_v2_reason(event['reason']);kind=event['kind']
        if kind=='launch-requested':require(not kinds,'api21_v2_process_sequence')
        elif kind in ('launch-succeeded','launch-failed'):require(kinds==['launch-requested'],'api21_v2_process_sequence')
        else:require('launch-requested' in kinds and 'launch-failed' not in kinds,'api21_v2_process_sequence')
        if kind=='wait-completed':require(type(event['return_code']) is int and process['launched'] and 'launch-succeeded' in kinds,'api21_v2_process_wait')
        else:require(event['return_code'] is None,'api21_v2_process_code')
        if kind=='term-sent':require(kinds[-1]=='term-requested','api21_v2_process_signal')
        if kind=='kill-sent':require(kinds[-1]=='kill-requested','api21_v2_process_signal')
        if kind=='kill-requested':require('term-requested' in kinds and 'timeout' in kinds,'api21_v2_process_signal')
        require(not kinds or kinds[-1]!='wait-completed','api21_v2_process_sequence');kinds.append(kind)
    if code is not None:
        require(process['launched'] and process['return_code_source'] in ('wait','poll') and process['wait_kind'] in ('normal','cleanup') and process['reaped'] is True and process['alive_final'] is False and process['finished_us'] is not None and process['started_us'] is not None,'api21_v2_process_wait')
        require(publication or kinds and kinds[-1]=='wait-completed' and events[-1]['return_code']==code,'api21_v2_process_wait')
    else:require(process['return_code_source']=='unavailable' and process['reaped'] is not True and process['finished_us'] is None,'api21_v2_process_wait')
    if not process['launched']:
        require(code is None and process['reaped'] is None and process['alive_final'] is None and process['wait_kind']=='unavailable' and kinds in ([],['launch-requested','launch-failed'],['launch-requested']),'api21_v2_process_unlaunched')
        if precommand:require(not kinds and process['started_us'] is None,'api21_v2_process_unlaunched')
    elif not publication:
        timeout=role=='browser-runner' and kinds==['launch-requested','timeout'] and code is None and events[-1]['reason']=='timeout'
        require('launch-succeeded' in kinds or timeout,'api21_v2_process_launch')
        if timeout:require(process['started_us'] is not None and process['reaped'] is None and process['alive_final'] is None and process['wait_kind']=='unavailable','api21_v2_process_timeout')
    refs=[prefix+name for name in schedule['logs']]
    require([process['stdout_ref'],process['stderr_ref']]==refs,'api21_v2_process_logs')
    hashes=process['output_hashes'];array(hashes);require(len(hashes)<=2,'api21_v2_process_hashes')
    for row in hashes:_api21_v2_hash(row,raw,refs)
    unique([row['ref'] for row in hashes])
    if process['reaped'] is True and not publication:require([row['ref'] for row in hashes]==list(dict.fromkeys(refs)),'api21_v2_process_hashes')
    else:require(not hashes,'api21_v2_process_hashes')
    signaling=any(kind in ('term-requested','term-sent','kill-requested','kill-sent','signal-failed') for kind in kinds)
    require(not signaling or process['intentional_cleanup'] and process['wait_kind']=='cleanup','api21_v2_process_cleanup')
    require(not process['intentional_cleanup'] or process['wait_kind']=='cleanup','api21_v2_process_cleanup')
    if passed:
        require(code==0 and process['launched'] and process['wait_kind']=='normal' and not process['intentional_cleanup'] and not publication and kinds==['launch-requested','launch-succeeded','wait-completed'],'api21_v2_process_success')


def _api21_v2_checkout(payload):
    from urllib.parse import urlsplit
    _paid_uuid(payload['idempotency_key']);identity=payload['checkout_identity'];exact(identity,('order_id','configuration_id','region','checkout_url'))
    for key in ('order_id','configuration_id'):_paid_uuid(identity[key])
    require(identity['region']=='US','api21_v2_checkout_scope');hosted=identity['checkout_url'];require(type(hosted) is str,'api21_v2_checkout_url')
    try:url=urlsplit(hosted)
    except ValueError:raise ContractError('api21_v2_checkout_url') from None
    require(url.scheme=='https' and url.netloc=='checkout.stripe.com' and re.fullmatch('/c/pay/cs_test_[a-f0-9]{32}',url.path) is not None and not url.query,'api21_v2_checkout_url')
    posted=payload['request']['parsed'];checkout=payload['response']['parsed']
    require(type(posted) is dict and type(checkout) is dict and posted.get('configuration_id')==identity['configuration_id'] and posted.get('region')=='US' and checkout.get('version')=='v1' and checkout.get('state')=='checkout' and {key:checkout.get(key) for key in identity}==identity,'api21_v2_checkout_identity')
    return identity


API21_V2_ASSERTION_PHASES = {
    'official_sdk_cookie_and_pg_session':'signed-in-measurement',
    'client_response_loss_same_key_one_checkout':'retry-pending-snapshot',
    'return_does_not_grant':'return-without-grant-measurement',
    'signed_public_webhook_grants_once':'settled-measurement',
    'permanent_owner_library_reload':'library-reload-measurement',
    'permanent_owner_library_server_restart':'restart-after-measurement',
    'paid_source_and_actual_s3_image':'source-review-http',
    'source_to_canonical_and_warm_reuse':'reader-after-measurement',
    'warm_raw_runtime_unchanged_with_approved_s3_delivery':'reader-after-measurement',
    'account_and_exact_scope_isolation':'other-image-denial',
    'logout_bfcache_and_firebase_disable_deny':'disabled-image-denial',
    'signed_full_refund_denies_old_content_and_media':'revoked-measurement',
}


def _api21_v2_measurement_shape(value):
    exact(value,(*API21_MEASUREMENT,'orders'))
    for key in API21_MEASUREMENT:integer(value[key])
    array(value['orders']);require(len(value['orders'])<=64,'api21_v2_measurement_orders')
    for order in value['orders']:
        exact(order,('order_id','state','owner','configuration_id','region'))
        for key in ('order_id','owner','configuration_id'):_paid_uuid(order[key])
        enum(order['state'],('open','paid','revoked'));require(order['region']=='US','api21_v2_measurement_scope')


def _api21_v2_http(payload,phase,*,passed):
    exact(payload,('kind','channel','method','route_template','actor','attempt','status','idempotency_key','request','response','checkout_identity'))
    route=payload['route_template'];string(route);require(route in API21_V2_ROUTES,'api21_v2_http_route')
    control=route.startswith('/__fixture/')
    expected_actor='fixture-control' if control else 'other' if phase.startswith('other-') else 'logged-out' if phase=='logout-image-denial' else 'disabled' if phase=='disabled-image-denial' else 'owner'
    require(payload['channel']==('fixture-control' if control else 'application') and payload['actor']==expected_actor,'api21_v2_http_actor')
    checkout=phase in ('checkout-first-http','checkout-retry-http','checkout-http')
    expected_method='POST' if checkout or phase.endswith('-control') else 'GET';require(payload['method']==expected_method,'api21_v2_http_method')
    attempt=payload['attempt'];integer(attempt,1);limit=100 if phase=='runtime-poll' else 16 if phase.startswith('owner-library-') else 2 if phase=='checkout-retry-http' else 1
    require(attempt<=limit and (phase!='checkout-retry-http' or attempt==2),'api21_v2_http_attempt')
    expected=API21_V2_PHASE_ROUTES.get(phase)
    if expected is None:
        if phase.endswith('-measurement'):expected='/__fixture/measurement'
        elif phase.endswith('-snapshot'):expected='/__fixture/snapshot'
        elif phase.startswith('owner-library-'):expected='/v1/workshop/library'
    require(route in expected if type(expected) is tuple else route==expected,'api21_v2_http_phase_route')
    status=payload['status']
    require(status is None or type(status) is int and 100<=status<=599,'api21_v2_http_status')
    allowed=(403,404) if phase in ('adjacent-denial','other-region-denial','unscoped-article-denial','legacy-vehicle-denial') else (404,) if phase=='other-image-denial' else (401,) if phase in ('logout-image-denial','disabled-image-denial') else (403,) if 'denial' in phase else (200,201) if checkout else (200,204) if phase.endswith('-control') else (200,)
    require(not passed or status in allowed,'api21_v2_http_status')
    image=phase in ('source-image-http','warm-image-http') and status==200
    response=payload['response'];_api21_v2_body(response,image=image,empty=status==204 and phase in ('restart-control','disable-control'),passed=passed)
    if status==204:require(phase in ('restart-control','disable-control') and response['length']==0 and response['availability']=='retained','api21_v2_empty_control')
    if 'denial' in phase and passed:require(response['availability']=='retained' and type(response['parsed']) is dict and bool(response['parsed']),'api21_v2_denial_body')
    if image and passed:require(response['length']>0,'api21_v2_image_body')
    if phase.endswith('-measurement') and status==200 and response['availability']=='retained' and response['reason'] is None:
        _api21_v2_measurement_shape(response['parsed'])
    if payload['request'] is not None:_api21_v2_body(payload['request'],request=True,passed=passed)
    if checkout:
        if passed or payload['checkout_identity'] is not None:
            require(payload['request'] is not None and payload['request']['availability']==response['availability']=='retained','api21_v2_checkout_body');_api21_v2_checkout(payload)
    else:require(payload['idempotency_key'] is None and payload['checkout_identity'] is None,'api21_v2_checkout_phase')


def _api21_v2_lifecycle(payload):
    exact(payload,('kind','operation','state','reason'));require(payload['kind']=='lifecycle','api21_v2_lifecycle')
    enum(payload['operation'],('setup','context-create','page-create','metadata','browser-launch','context-close','browser-close','fixture-stop','worker-start','worker-stop','runtime-close','publish'))
    enum(payload['state'],('requested','completed','failed','unavailable'));_api21_v2_reason(payload['reason'])
    require(payload['state']!='failed' or payload['reason'] is not None,'api21_v2_lifecycle_reason')
    require(payload['state'] in ('requested','completed','failed') and (payload['state']=='failed' or payload['reason'] is None),'api21_v2_lifecycle_reason')


def _api21_v2_browser_lifecycle(events,*,passed):
    # Frozen run()/api_case() setup, followed by case observations and finally cleanup.
    setup=[('setup','completed'),('metadata','requested'),('metadata','completed'),('browser-launch','requested'),('browser-launch','completed'),('context-create','requested'),('context-create','completed'),('page-create','requested'),('page-create','completed')]
    cursor=0;cleanup=[];phase='setup';failed=False
    for event in events:
        payload=event['payload']
        if payload['kind']!='lifecycle':
            trailing=not passed and payload['kind']=='http' and payload['channel']=='application' and event['phase']==phase and not any(op=='browser-close' for op,state in cleanup)
            require(cursor==len(setup) and (not cleanup and not failed or trailing),'api21_v2_lifecycle_order');phase=event['phase'];continue
        require(event['caused_by']==[],'api21_v2_lifecycle_cause')
        operation,state=payload['operation'],payload['state']
        if operation in ('context-close','browser-close'):
            if not passed and not cleanup:phase=event['phase']
            require(event['phase']==phase and cursor>=(7 if operation=='context-close' else 5),'api21_v2_cleanup_phase')
            require(state!='failed' or payload['reason']=='close_failed','api21_v2_cleanup_reason')
            cleanup.append((operation,state))
            # A browser may close after context creation failed, without a context close.
            expected=([('context-close','requested'),('context-close','completed')] if cursor>=7 else [])+[('browser-close','requested'),('browser-close','completed')]
            normalized=[(op,'completed' if st=='failed' else st) for op,st in cleanup]
            require(normalized==expected[:len(normalized)],'api21_v2_browser_cleanup')
        elif state=='failed':
            require(not passed and not cleanup and not failed,'api21_v2_lifecycle_failure');phase=event['phase']
            # Routing the new context can fail before page-create/requested.
            require(operation=='setup' or event['phase']=='setup' and (cursor<len(setup) and setup[cursor]==(operation,'completed') or operation=='page-create' and cursor==7),'api21_v2_lifecycle_failure')
            failed=True
        else:
            require(not cleanup and not failed and event['phase']=='setup' and cursor<len(setup) and (operation,state)==setup[cursor],'api21_v2_setup_schedule');cursor+=1
    if passed:
        require(cursor==len(setup) and cleanup==[('context-close','requested'),('context-close','completed'),('browser-close','requested'),('browser-close','completed')],'api21_v2_lifecycle_complete')


def _api21_v2_observations(observations,binding,case,row,*,passed):
    exact(observations,('binding','status','events','primary_failure','publication','unavailable_families','engine_os_exit','outer_pytest_exit'))
    require(observations['binding']==binding,'api21_v2_observation_binding');_api21_v2_terminal(observations,passed=passed)
    enum(observations['publication'],('written','failed','not_attempted'))
    missing=observations['unavailable_families'];array(missing);unique(missing);require(all(type(x) is str and x in (*API21_V2_MISSING_FAMILIES,*API21_MISSING_FAMILIES) for x in missing),'api21_v2_missing_families')
    _api21_v2_size(observations,1048576)
    events=observations['events'];array(events);require(len(events)<=512,'api21_v2_events');phases=API21_V2_PHASES[case[1]];seen=[];last=-1;elapsed=-1;by_phase={};assertions=[]
    for index,event in enumerate(events):
        exact(event,('seq','phase','caused_by','elapsed_us','payload'));integer(event['seq'],1);integer(event['elapsed_us']);require(event['seq']==index+1 and event['elapsed_us']>=elapsed,'api21_v2_event_sequence');elapsed=event['elapsed_us'];_api21_v2_size(event,262144)
        phase=event['phase'];require(type(phase) is str and phase in phases,'api21_v2_phase');rank=phases.index(phase);require(rank>=last,'api21_v2_phase_order');last=rank
        if phase not in seen:seen.append(phase)
        refs=event['caused_by'];array(refs);require(len(refs)<=8,'api21_v2_causes')
        for ref in refs:_api21_v2_ref(ref,index)
        payload=event['payload'];require(type(payload) is dict,'api21_v2_payload');kind=payload.get('kind')
        if kind=='http':_api21_v2_http(payload,phase,passed=passed)
        elif kind=='lifecycle':
            _api21_v2_lifecycle(payload)
            require(not passed or payload['state'] in ('requested','completed') and payload['reason'] is None,'api21_v2_success_lifecycle')
        elif kind=='producer-assertion':
            exact(payload,('kind','name','result','reason'));require(payload['name'] in API21_ASSERTIONS[case[1]] and (payload['result'] is None or type(payload['result']) is bool),'api21_v2_assertion');_api21_v2_reason(payload['reason']);assertions.append(payload['name']);require(not passed or payload['result'] is True,'api21_v2_assertion')
            require(phase==API21_V2_ASSERTION_PHASES[payload['name']] and any(p['kind']=='http' for p in by_phase.get(phase,[])),'api21_v2_assertion_order')
            require(payload['result'] is not True or payload['reason'] is None,'api21_v2_assertion_reason')
        elif kind=='checkout-delivery':
            exact(payload,('kind','attempt','state','http_event'));integer(payload['attempt'],1);require(phase in ('checkout-first-delivery','checkout-retry-delivery') and payload['attempt']==(1 if 'first' in phase else 2),'api21_v2_delivery')
            enum(payload['state'],('fetch-completed','response-abort-requested','response-aborted','response-fulfill-requested','response-fulfilled'))
            ref=payload['http_event'];_api21_v2_ref(ref,index);require(refs==[ref],'api21_v2_delivery_ref');target=events[ref['seq']-1]
            require(target['phase']==phase.replace('-delivery','-http') and target['payload']['kind']=='http' and target['payload']['attempt']==payload['attempt'],'api21_v2_delivery_ref')
        else:raise ContractError('api21_v2_payload_kind')
        by_phase.setdefault(phase,[]).append(payload)
    unique(assertions)
    for phase,payloads in by_phase.items():
        http=[p for p in payloads if p['kind']=='http'];attempts=[p['attempt'] for p in http];unique(attempts)
        if http:
            start=2 if phase=='checkout-retry-http' else 1;require(attempts==list(range(start,start+len(attempts))),'api21_v2_http_sequence')
    require(seen==list(phases[:len(seen)]),'api21_v2_phase_prefix')
    _api21_v2_browser_lifecycle(events,passed=passed)
    if passed:
        require(seen==list(phases) and observations['publication']=='written','api21_v2_phase_complete')
        for phase in phases:
            payloads=by_phase.get(phase,[]);http=[p for p in payloads if p['kind']=='http']
            if phase=='setup':require(all(p['kind']=='lifecycle' for p in payloads),'api21_v2_setup');continue
            if phase.endswith('-delivery'):
                states=['fetch-completed','response-abort-requested','response-aborted'] if 'first' in phase else ['fetch-completed','response-fulfill-requested','response-fulfilled']
                require([p['state'] for p in payloads if p['kind']=='checkout-delivery']==states,'api21_v2_delivery_sequence');continue
            require(bool(http) and (len(http)==1 or phase=='runtime-poll' or phase.startswith('owner-library-')),'api21_v2_http_cardinality')
        require(set(assertions)==set(API21_ASSERTIONS[case[1]]),'api21_v2_assertion_inventory')
        cleanup=[(e['payload']['operation'],e['payload']['state']) for e in events if e['payload']['kind']=='lifecycle' and e['payload']['operation'] in ('context-close','browser-close')]
        require(cleanup==[('context-close','requested'),('context-close','completed'),('browser-close','requested'),('browser-close','completed')],'api21_v2_browser_cleanup')
        _api21_v2_wire_semantics(by_phase,case,row)
    return by_phase


def _api21_v2_ref(ref, earlier):
    exact(ref,('stream','producer_role','seq'));integer(ref['seq'],1)
    require(ref['stream']=='observations' and ref['producer_role']=='browser-runner' and ref['seq']<=earlier,'api21_v2_reference')


def _api21_v2_terminal(value,*,passed):
    enum(value['status'],('passed','failed','partial','unavailable'));_api21_v2_reason(value['primary_failure'])
    require(value['engine_os_exit'] is None and value['outer_pytest_exit'] is None,'api21_v2_unobserved_exit')
    require(value['status']!='passed' or value['primary_failure'] is None,'api21_v2_sticky_failure')
    if passed:require(value['status']=='passed','api21_v2_outcome')



def _api21_v2_pending_snapshot(snapshot,identity,owner):
    exact(snapshot,('article','asset_calls','counts','ensure','ensure_requests','grant_calls','immutable_rows','immutable_sha256','model_calls','paid_rows','payment_calls','provider_calls','provider_traces','proxy','selector_ensure','selector_ensure_requests','source_calls','workers'))
    for key in ('grant_calls','model_calls'):integer(snapshot[key]);require(snapshot[key]==0,'api21_v2_pending_work')
    integer(snapshot['payment_calls'],1);require(snapshot['workers']==[],'api21_v2_pending_workers')
    for group in ('provider_calls','source_calls','asset_calls'):
        exact(snapshot[group],('bankone','banktwo'))
        for value in snapshot[group].values():integer(value);require(value==0,'api21_v2_pending_work')
    exact(snapshot['provider_traces'],('bankone','banktwo'));require(all(v==[] for v in snapshot['provider_traces'].values()),'api21_v2_pending_work')
    for group in ('ensure','selector_ensure'):
        exact(snapshot[group],('entered','completed','active'))
        require(all(type(v) is int and v==0 for v in snapshot[group].values()) and snapshot[group+'_requests']==[],'api21_v2_pending_work')
    exact(snapshot['counts'],('article_jobs','source_revisions','canonical_revisions','published_revisions','publication_events','source_observations'))
    require(all(type(v) is int and v==0 for v in snapshot['counts'].values()),'api21_v2_pending_work')
    exact(snapshot['proxy'],('request_received','upstream_completed','downstream_completed','downstream_waiting','response_captured','errors'))
    require(all(type(snapshot['proxy'][k]) is int and snapshot['proxy'][k]==0 for k in ('request_received','upstream_completed','downstream_completed','downstream_waiting')) and snapshot['proxy']['response_captured'] is False and snapshot['proxy']['errors']==[],'api21_v2_pending_work')
    paid=snapshot['paid_rows'];exact(paid,PAID_ROW_FIELDS)
    for table,fields in PAID_ROW_FIELDS.items():
        array(paid[table]);require(len(paid[table])<=64,'api21_v2_pending_rows')
        for item in paid[table]:exact(item,fields.split())
    require(len(paid['customer_accounts'])==len(paid['auth_sessions'])==len(paid['workshop_orders'])==1 and all(paid[k]==[] for k in ('entitlements','dataset_requests','dataset_projections')),'api21_v2_pending_grants')
    order=paid['workshop_orders'][0];account=paid['customer_accounts'][0];session=paid['auth_sessions'][0]
    require(order['status']=='open' and all(order[k]==identity[k] for k in ('order_id','configuration_id','region')) and order['customer_account_id']==account['customer_account_id']==session['customer_account_id']==owner and order['organization_id']==account['personal_organization_id'],'api21_v2_pending_owner')
    require(account['firebase_uid']=='fixture-user' and account['firebase_project_id']=='fixture-project' and account['status']=='active','api21_v2_pending_owner')
    for key in ('paid_at','dataset_request_id','entitlement_id'):require(order[key] is None,'api21_v2_pending_grants')
    require(type(order['amount_minor']) is int and order['amount_minor']==2000 and order['currency']=='USD' and order['livemode'] is False and order['stripe_account_id']=='acct_fixture' and order['expected_price_id']=='price_fixture','api21_v2_pending_payment')
    require(order['checkout_url']==identity['checkout_url'] and order['checkout_session_id']==identity['checkout_url'].split('/c/pay/')[1].split('#')[0],'api21_v2_pending_payment')
    rows=snapshot['immutable_rows'];exact(rows,PAID_PG_TABLES)
    for values in rows.values():array(values);require(len(values)<=4096 and all(type(r) is dict and r for r in values),'api21_v2_pending_rows')
    digest(snapshot['immutable_sha256']);require(hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest()==snapshot['immutable_sha256'],'api21_v2_pending_row_hash')
    for table in ('customer_accounts','auth_sessions','workshop_orders'):require(rows[table]==paid[table],'api21_v2_pending_row_seam')
    require(len(rows['workshop_checkout_requests'])==1 and rows['workshop_checkout_requests'][0].get('order_id')==identity['order_id'],'api21_v2_pending_request')

def _api21_v2_wire_semantics(by_phase,case,row):
    def http(phase):return [p for p in by_phase[phase] if p['kind']=='http']
    def value(phase):return http(phase)[-1]['response']['parsed']
    google=case[1]==API21_CASES[0][1];checkout=http('checkout-first-http' if google else 'checkout-http')[0];identity=_api21_v2_checkout(checkout)
    require(identity['configuration_id']==row['measurement']['orders'][0]['configuration_id'] and identity['order_id']==row['measurement']['orders'][0]['order_id'],'api21_v2_checkout_order')
    owner=row['measurement']['orders'][0]['owner']
    for phase in by_phase:
        if not phase.endswith('-measurement'):continue
        measure=value(phase)
        if phase in ('initial-measurement','signed-in-measurement'):
            require(measure['orders']==[] and all(measure[key]==0 for key in ('workshop_orders','workshop_checkout_requests','entitlements','dataset_requests','dataset_projections','payment_events')),'api21_v2_precheckout_counts')
        elif phase not in ('response-lost-measurement','pending-checkout-measurement','return-without-grant-measurement'):
            state='revoked' if phase=='revoked-measurement' or phase=='final-measurement' and case[1]=='test_browser_signed_refund_blocks_old_links_real_api' else 'paid'
            order=_api21_measurement(measure,dict(configuration=identity['configuration_id']),state=state)
            require(order['owner']==owner and order['order_id']==identity['order_id'],'api21_v2_measurement_owner')
    pending=value('pending-checkout-measurement');returned=value('return-without-grant-measurement')
    for measure in (pending,returned,value('response-lost-measurement') if google else pending):
        exact(measure,(*API21_MEASUREMENT,'orders'))
        for key in API21_MEASUREMENT:integer(measure[key])
        require(measure['workshop_orders']==measure['workshop_checkout_requests']==1 and all(measure[key]==0 for key in ('entitlements','dataset_requests','dataset_projections','payment_events')) and len(measure['orders'])==1,'api21_v2_pending_counts')
        order=measure['orders'][0];require(order['state']=='open' and order['owner']==row['measurement']['orders'][0]['owner'] and all(order[k]==identity[k] for k in ('order_id','configuration_id','region')),'api21_v2_pending_scope')
    if google:
        retry=http('checkout-retry-http')[0];require(retry['idempotency_key']==checkout['idempotency_key'] and retry['request']==checkout['request'] and retry['checkout_identity']==identity,'api21_v2_checkout_retry')
        snapshots=[value('response-lost-snapshot'),value('retry-pending-snapshot')]
        for snapshot in snapshots:
            _api21_v2_pending_snapshot(snapshot,identity,row['measurement']['orders'][0]['owner'])
            rows=snapshot['paid_rows'];orders=rows['workshop_orders'];require(len(orders)==1 and rows['entitlements']==[] and snapshot['grant_calls']==0,'api21_v2_pending_snapshot')
            order=orders[0];require(order['status']=='open' and all(order[k]==identity[k] for k in ('order_id','configuration_id','region')) and order['checkout_session_id']==identity['checkout_url'].split('/c/pay/')[1].split('#')[0],'api21_v2_pending_snapshot');integer(snapshot['payment_calls'],1)
        require(snapshots[0]['payment_calls']==snapshots[1]['payment_calls'],'api21_v2_retry_payment')
    initial=value('initial-measurement');signed=value('signed-in-measurement')
    require(signed['auth_sessions']==initial['auth_sessions']+1 and signed['hashed_sessions']==signed['auth_sessions'] and signed['sdk_cert_calls']>=1 and signed['sdk_user_calls']>=2 and signed['sdk_unexpected']==0,'api21_v2_signin')
    for phase in ('owner-library-initial-http','owner-library-reload-http','owner-library-restart-http'):
        responses=http(phase)
        def matching(payload):
            body=payload['response']['parsed']
            if type(body) is not dict or type(body.get('items')) is not list or len(body['items'])!=1:return False
            item=body['items'][0]
            return type(item) is dict and item.get('library_item_id')==identity['order_id'] and item.get('configuration_id')==identity['configuration_id'] and item.get('region')=='US' and item.get('access_state') in ('paid','preparing','viewable')
        require(1<=len(responses)<=16 and any(matching(p) for p in responses),'api21_v2_library')
    scope=dict(configuration=identity['configuration_id'])
    _api21_measurement(value('settled-measurement'),scope,state='paid')
    require(value('restart-before-measurement')==row['restart']['before'] and value('restart-after-measurement')==row['restart']['after'] and value('runtime-before')==row['restart']['runtime_before'] and value('runtime-poll')==row['restart']['runtime_after'] and value('final-measurement')==row['measurement'],'api21_v2_retained_measurement')
    if not google:
        warm=row['warm'];require(value('warm-before-snapshot')==warm['before'] and value('warm-after-snapshot')==warm['after'] and value('reader-before-measurement')['image_reads']==warm['reader_before'] and value('reader-after-measurement')['image_reads']==warm['reader_after'],'api21_v2_retained_warm')
    if 'other-library-http' in by_phase:require(value('other-library-http').get('items')==[],'api21_v2_other_library')
    if 'revoked-measurement' in by_phase:_api21_measurement(value('revoked-measurement'),scope,state='revoked')


def _api21_v2_business(result,row,evidence,scope,case,*,passed):
    _,root,engine,provider=case
    google=root == API21_CASES[0][1]; isolation=root == 'test_browser_account_scope_and_revocation_real_api'
    refund=root == 'test_browser_signed_refund_blocks_old_links_real_api'
    require(not passed or 'final_snapshot' in result and 'worker_exits' in result, 'api21_v2_success_snapshot')
    require('final_snapshot' not in result or row is not None and row['status'] == 'passed' and
            'browser_versions' in evidence,
            'api21_retained_source_order')
    final_order=None
    if 'final_snapshot' in result:
        final_order=_api21_snapshot(result['final_snapshot'],scope,work=not google,isolation=isolation,revoked=refund)
    if row is not None and 'measurement' in row:
        measurement=row['measurement']; measured=_api21_measurement(measurement,scope,state='revoked' if refund else 'paid')
        if final_order is not None:
            _api21_order_seam(measured,final_order)
            paid=result['final_snapshot']['paid_rows']
            for key in ('auth_sessions','workshop_orders','entitlements','dataset_requests','dataset_projections'):
                require(measurement[key] == len(paid[key]), 'api21_measurement_pg_seam')
            require(measurement['workshop_checkout_requests'] == len(result['final_snapshot']['immutable_rows']['workshop_checkout_requests']),
                    'api21_measurement_pg_seam')
        restart=row['restart']; exact(restart, ('runtime_before','runtime_after','before','after'))
        for key in ('runtime_before','runtime_after'):
            exact(restart[key], ('application_generation',)); integer(restart[key]['application_generation'])
        require(restart['runtime_after']['application_generation'] == restart['runtime_before']['application_generation']+1,
                'api21_restart_generation')
        for key in ('before','after'):
            order=_api21_measurement(restart[key],scope,state='paid')
            require(all(order[field] == measured[field] for field in ('order_id','owner','configuration_id','region')),
                    'api21_restart_order')
        require(all(restart['before'][key] == restart['after'][key] for key in API21_DURABLE), 'api21_restart_durability')
        for key in API21_MEASUREMENT:
            require(measurement[key] >= restart['after'][key], 'api21_measurement_regression')
        require(isolation or measurement['auth_sessions'] == restart['after']['auth_sessions'], 'api21_session_phase')
        warm=row['warm']
        if google: exact(warm, ())
        else:
            exact(warm, ('before','after','reader_before','reader_after'))
            for key in ('before','after'):
                order=_api21_snapshot(warm[key],scope,work=True)
                require(order['order_id'] == measured['order_id'] and order['customer_account_id'] == measured['owner'] and
                    order['configuration_id'] == measured['configuration_id'] and order['region'] == measured['region'],
                    'api21_warm_order')
                if final_order is not None:
                    require(all(order[field] == final_order[field] for field in
                        ('order_id','customer_account_id','organization_id','configuration_id','dataset_request_id',
                         'dataset_product_id','entitlement_id')), 'api21_warm_order')
            for key in ('provider_calls','source_calls','asset_calls','model_calls','counts','immutable_sha256'):
                require(warm['before'][key] == warm['after'][key], 'api21_warm_drift')
            integer(warm['reader_before']); integer(warm['reader_after'])
            require(warm['reader_after'] > warm['reader_before'] and measurement['image_reads'] >= warm['reader_after'],
                    'api21_warm_reader')
    if 'worker_exits' in result:
        exits=result['worker_exits']; array(exits)
        require(len(exits) <= 2 and (not passed or len(exits) == (0 if google else 2)), 'api21_v2_worker_cleanup_inventory')
        # Equal records are valid: source retains no distinct process identifiers.
        for worker in exits:
            exact(worker, ('kind','exit_code','terminated','intentional_cleanup','alive_before_cleanup'))
            require(worker['kind'] == 'cli' and type(worker['exit_code']) is int and
                all(worker[key] is True for key in ('terminated','intentional_cleanup','alive_before_cleanup')),
                'api21_worker_cleanup')

def _api21_v2_evidence(evidence,ready,case):
    case_id,root,engine,bank=case
    base=('version','mode','candidate_sha','api_observability_version','binding','results')
    metadata=('engine_revisions','input_sha256','sdk_sha256','playwright_version','provenance')
    has_metadata='engine_revisions' in evidence
    exact(evidence, (*base,*metadata,'browser_versions') if 'browser_versions' in evidence else (*base,*metadata) if has_metadata else base)
    require(evidence['version']=='v1' and evidence['mode']=='api-fixture' and evidence['candidate_sha']==API21_V2_SOURCE_SHA and evidence['api_observability_version']=='api21-producer-v2','api21_v2_evidence_identity')
    complete=_api21_v2_binding(evidence['binding'],case,'browser-runner')
    if has_metadata:
        require(ready is not None and evidence['playwright_version']=='1.64.1' and evidence['input_sha256']=={k:v for k,v in API21_V2_SOURCE_INPUTS.items() if k!='workers/ingestion-python/tests/test_workshop_browser_integration.py'},'api21_v2_provenance')
        revisions=evidence['engine_revisions'];require(type(revisions) is dict and 0<len(revisions)<=32,'api21_v2_engine_revisions')
        for key,value in revisions.items():string(key);string(value);require(len(key)<=96 and len(value)<=256,'api21_v2_engine_revisions')
        provenance=evidence['provenance'];exact(provenance,('assets','certificate_sha256'))
        require(provenance['assets']==API21_V2_SOURCE_ASSETS and provenance['certificate_sha256']==ready['certificate_sha256'] and evidence['sdk_sha256']==ready['sdk_sha256']==API21_V2_SOURCE_ASSETS['firebase-web.mjs']['sha256'],'api21_v2_provenance')
        for asset in provenance['assets'].values():exact(asset,('sha256','bytes'));digest(asset['sha256']);integer(asset['bytes'])
    if 'browser_versions' in evidence:
        require(has_metadata,'api21_v2_browser_versions');exact(evidence['browser_versions'],(engine,));string(evidence['browser_versions'][engine]);require(len(evidence['browser_versions'][engine])<=256,'api21_v2_browser_versions')
    rows=evidence['results'];array(rows);require(len(rows)==1,'api21_v2_result_inventory');row=rows[0]
    require(type(row) is dict and row.get('browser')==engine and row.get('scenario')==root,'api21_v2_row_identity');enum(row.get('status'),('passed','failed','unavailable'))
    full='measurement' in row
    if full:
        exact(row,('browser','scenario','elapsed_seconds','status','assertions','provider','requests','measurement','restart','warm','observations'))
        require(has_metadata and ready is not None and row['provider']==bank,'api21_v2_row_metadata');_api21_elapsed(row['elapsed_seconds'])
        assertions=row['assertions'];exact(assertions,API21_ASSERTIONS[root]);require(all(type(x) is bool for x in assertions.values()),'api21_v2_assertions')
        if row['status']=='passed':require(all(assertions.values()),'api21_v2_assertions')
        requests=row['requests']; array(requests); require(len(requests) <= 8192, 'api21_request_limit')
        get_paths={'/workshop/','/workshop/purchase-config.json','/workshop/fonts/InstrumentSans.ttf',
                   '/auth/config','/auth/session','/v1/catalog/years','/v1/workshop/quote','/v1/workshop/library'}
        get_paths.update('/workshop/'+name for name in API21_V2_SOURCE_ASSETS)
        get_patterns=(r'/v1/workshop/orders/\{uuid\}',
            r'/v1/catalog/years/2024/makes(?:/example/models(?:/car/configurations)?)?',
            r'/v1/catalog/vehicles/\{uuid\}/articles(?:/\{uuid\}(?:/source)?)?',
            r'/v1/catalog/images/\{capability\}')
        for request in requests:
            exact(request, ('method','path'))
            method,path=request['method'],request['path']
            require(type(method) is str and type(path) is str, 'api21_request_template')
            allowed=(method == 'GET' and (path in get_paths or any(re.fullmatch(pattern,path) for pattern in get_patterns))) or (
                method == 'POST' and (path in ('/auth/firebase/session','/auth/logout','/v1/workshop/checkout-sessions') or
                re.fullmatch(r'/v1/catalog/vehicles/\{uuid\}/articles/\{uuid\}/prepare',path) is not None))
            require(allowed, 'api21_request_template')
    else:
        exact(row,('browser','scenario','status','observations'));require(row['status']!='passed','api21_v2_minimal_row')
    passed=row['status']=='passed'
    require(not passed or complete and has_metadata and 'browser_versions' in evidence,'api21_v2_browser_success')
    phases=_api21_v2_observations(row['observations'],evidence['binding'],case,row,passed=passed)
    if passed:
        metadata=next(p['response']['parsed'] for p in phases['metadata'] if p['kind']=='http')
        require(metadata==dict(kind='api-fixture',scope=ready['scope']),'api21_v2_metadata_scope')
    require((row['observations']['status']=='passed')==passed,'api21_v2_observation_outcome')
    return row


def _api21_v2_sidecars(parent,child,result,case,raw,*,passed,used_workers):
    prefix='workshop-browser/'+case[1]+'/'+case[2]+'-'+case[3]+'/'
    exact(parent,('binding','status','child','child_artifacts','child_artifact_status','child_launch_cause','primary_failure','publication_failure','engine_os_exit','outer_pytest_exit'))
    _api21_v2_terminal(parent,passed=passed);_api21_v2_reason(parent['publication_failure']);publication=parent['publication_failure'] is not None
    require(not publication or parent['publication_failure']=='publication_failed' and parent['status']=='failed','api21_v2_publication')
    _api21_v2_process(parent['child'],case,'child-pytest',raw,passed=passed,publication=publication)
    artifacts=parent['child_artifacts'];array(artifacts);require(len(artifacts)<=8,'api21_v2_child_artifacts')
    expected=[prefix+name for name in (*API21_SUPPORT,'child-processes.json')]
    for artifact in artifacts:_api21_v2_hash(artifact,raw,expected)
    unique([a['ref'] for a in artifacts]);enum(parent['child_artifact_status'],('finalized','partial','unavailable'))
    if artifacts:require(parent['child']['reaped'] is True,'api21_v2_hash_before_reap')
    if parent['child_artifact_status']=='finalized':require([a['ref'] for a in artifacts]==expected,'api21_v2_finalized_artifacts')
    if passed:require(parent['child_artifact_status']=='finalized','api21_v2_finalized_artifacts')
    cause=parent['child_launch_cause']
    if cause is not None:
        exact(cause,('stream','producer_role','seq'));integer(cause['seq'],1)
        events=parent['child']['events'];require(cause['stream']=='process-child' and cause['producer_role']=='parent-pytest' and cause['seq']<=len(events) and events[cause['seq']-1]['kind']=='launch-succeeded','api21_v2_parent_launch_cause')
    if passed or not publication and any(e['kind']=='launch-succeeded' for e in parent['child']['events']):require(cause is not None,'api21_v2_parent_launch_cause')
    if child is None:
        require(not passed and parent['status']!='passed','api21_v2_unpublished_child');return
    exact(child,('binding','status','go','browser_runner','workers','worker_mapping_status','finalization_events','primary_failure','publication_failure','engine_os_exit','outer_pytest_exit'))
    _api21_v2_terminal(child,passed=passed);_api21_v2_reason(child['publication_failure']);publication=child['publication_failure'] is not None
    require(not publication or child['publication_failure']=='publication_failed' and child['status']=='failed','api21_v2_publication')
    for field,role in (('go','go-test'),('browser_runner','browser-runner')):_api21_v2_process(child[field],case,role,raw,passed=passed,publication=publication)
    events=child['finalization_events'];array(events);require(len(events)<=64,'api21_v2_finalization');last=-1;sequence=[]
    for index,event in enumerate(events):
        exact(event,('seq','phase','caused_by','elapsed_us','payload'));integer(event['seq'],1);integer(event['elapsed_us']);require(event['seq']==index+1 and event['elapsed_us']>=last and event['caused_by']==[],'api21_v2_finalization');last=event['elapsed_us'];_api21_v2_lifecycle(event['payload'])
        require(event['phase']==event['payload']['operation'] and event['phase'] in ('fixture-stop','worker-stop','runtime-close'),'api21_v2_finalization');sequence.append((event['phase'],event['payload']['state']))
        require(event['payload']['state']!='failed' or event['payload']['reason']=='close_failed','api21_v2_finalization_reason')
    success_sequence=[('fixture-stop','completed'),('worker-stop','requested'),('worker-stop','completed'),('runtime-close','requested'),('runtime-close','completed')]
    if passed:require(sequence==success_sequence,'api21_v2_finalization_order')
    else:
        # An exception can interrupt any normal prefix. finally retries unfinished
        # worker cleanup and closes the runtime, without emitting requested events.
        schedules=[]
        for count in range(len(success_sequence)+1):
            prefix=success_sequence[:count];schedules.append(prefix)
            if count==len(success_sequence):continue
            for worker_state in ('completed','failed'):
                for runtime_state in ('completed','failed'):
                    suffix=([('worker-stop',worker_state)] if count<3 else [])+[('runtime-close',runtime_state)]
                    schedules.extend(prefix+suffix[:end] for end in range(1,len(suffix)+1))
        require(sequence in schedules,'api21_v2_finalization_order')
    if ('runtime-close','completed') in sequence and ('worker-stop','completed') in sequence:require(sequence.index(('worker-stop','completed'))<sequence.index(('runtime-close','completed')),'api21_v2_finalization_order')
    workers=child['workers'];array(workers);require(len(workers)<=2,'api21_v2_workers');enum(child['worker_mapping_status'],('observed','unavailable','not_started'))
    exits=result.get('worker_exits',[]) if result is not None else []
    if child['worker_mapping_status']=='observed':require(len(workers)==2 and len(exits)==2,'api21_v2_worker_mapping_inventory')
    if child['worker_mapping_status']=='not_started':require(case[1]==API21_CASES[0][1] and workers==[],'api21_v2_worker_mapping_inventory')
    if passed:require(len(workers)==(0 if case[1]==API21_CASES[0][1] else 2) and child['worker_mapping_status']==('not_started' if not workers else 'observed'),'api21_v2_worker_inventory')
    for index,worker in enumerate(workers):
        exact(worker,('ordinal','kind','original_ref','mapping','alive_before_cleanup','intentional_cleanup','terminated','exit_code','reaped','log_finalized','log_hash','reason'))
        integer(worker['ordinal'],1);require(worker['ordinal']==index+1 and worker['kind']=='cli','api21_v2_worker_ordinal');ref=worker['original_ref'];require(type(ref) is str and re.fullmatch('worker-[a-f0-9]{32}\\.log',ref) is not None and ref not in used_workers,'api21_v2_worker_ref');used_workers.add(ref)
        enum(worker['mapping'],('observed','unavailable'));_api21_v2_reason(worker['reason'])
        for key in ('alive_before_cleanup','intentional_cleanup','terminated','reaped'):require(worker[key] is None or type(worker[key]) is bool,'api21_v2_worker_bool')
        require(type(worker['log_finalized']) is bool and (worker['exit_code'] is None or type(worker['exit_code']) is int),'api21_v2_worker_exit')
        if worker['mapping']=='observed':
            require(index<len(exits) and all(worker[key]==exits[index][key] for key in ('kind','alive_before_cleanup','intentional_cleanup','terminated','exit_code')) and worker['reaped'] is True and worker['reason'] is None,'api21_v2_worker_mapping')
        if worker['log_finalized']:
            require(worker['mapping']=='observed' and ('runtime-close','completed') in sequence,'api21_v2_log_finalization');_api21_v2_hash(worker['log_hash'],raw,[ref])
        else:require(worker['log_hash'] is None and not passed,'api21_v2_log_finalization')
        if passed:require(worker['mapping']=='observed' and worker['log_finalized'],'api21_v2_worker_success')
    if workers:require(('worker-stop','completed') in sequence or child['worker_mapping_status']=='unavailable','api21_v2_worker_cleanup')


def _api21_v2_inspect(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                      profile_version='api21-retained-v2'):
    """Inspect current retained bytes offline; never authenticate or accept a run."""
    digest(candidate_sha,40);digest(trusted_base_sha,40);digest(profile_sha256)
    require(candidate_sha==API21_V2_SOURCE_SHA and profile_version=='api21-retained-v2','api21_v2_selector')
    required={'workshop-browser-api.xml'};allowed=set(required);prefixes=[]
    for case in API21_CASES:
        _,root,engine,bank=case;prefix='workshop-browser/'+root+'/'+engine+'-'+bank+'/';prefixes.append(prefix)
        required.add(prefix+'parent-process.json');allowed.update(prefix+name for name in (*API21_SUPPORT,'parent-process.json','child-processes.json'));allowed.add(prefix+'browser/'+engine+'/'+root+'-failure.png')
    require(required<=set(store.by_ref),'api21_v2_support_inventory')
    raw={};total=0
    for ref,record in store.by_ref.items():
        require(ref in allowed or re.fullmatch('worker-[a-f0-9]{32}\\.log',ref) is not None,'api21_v2_support_inventory')
        require(record['visibility']=='private' and record['kind']==('junit' if ref=='workshop-browser-api.xml' else 'raw'),'api21_v2_artifact_declaration')
        data=store.read(record['artifact_id']);require(type(data) is bytes and len(data)<=8388608,'api21_v2_artifact_size');total+=len(data);require(total<=67108864,'api21_v2_total_size');raw[ref]=data
    outcomes=_api21_junit(raw['workshop-browser-api.xml']);observed=[];diagnostics=[];databases=[];run_ids=[];attempt_ids=[];used_workers=set();observation_bytes=0
    for index,(case,prefix) in enumerate(zip(API21_CASES,prefixes)):
        docs={}
        for name in ('parent-process.json','child-processes.json','result.json','ready.json','browser/evidence.json'):
            if prefix+name in raw:
                data=raw[prefix+name]
                require(len(data)<= (65536 if name=='parent-process.json' else 262144 if name=='child-processes.json' else 4194304),'api21_v2_document_size');docs[name]=strict_raw_json(data)
        parent=docs['parent-process.json'];parent_complete=_api21_v2_binding(parent['binding'],case,'parent-pytest')
        pb=parent['binding']
        if pb['run_id'] is not None:run_ids.append(pb['run_id'])
        if pb['attempt_id'] is not None:attempt_ids.append(pb['attempt_id'])
        child=docs.get('child-processes.json');result=docs.get('result.json');ready=docs.get('ready.json');evidence=docs.get('browser/evidence.json');row=None;scope=None
        require(parent_complete or not parent['child']['launched'] and child is None and result is None,'api21_v2_partial_launch')
        child_complete=False
        if child is not None:
            child_complete=_api21_v2_binding(child['binding'],case,'child-pytest')
            require(child_complete or not child['go']['launched'] and not child['browser_runner']['launched'],'api21_v2_partial_launch')
            if child_complete and parent_complete:require(child['binding']==dict(pb,producer_role='child-pytest'),'api21_v2_role_binding')
        if result is not None:
            require(type(result) is dict,'api21_v2_result');result_complete=_api21_v2_binding(result['binding'],case,'child-pytest')
            if child is not None:require(result['binding']==child['binding'],'api21_v2_result_binding')
            fields=('version','mode','candidate_sha','browser','provider','test','fixture_database','passed','api_observability_version','binding')
            require(set(fields)<=set(result)<=set((*fields,'final_snapshot','worker_exits')),'api21_v2_result_shape')
            require(result['version']=='v1' and result['mode']=='api-fixture' and result['candidate_sha']==result['binding']['candidate_sha'] and result['api_observability_version']=='api21-producer-v2' and (result['test'],result['browser'],result['provider'])==(case[1],case[2],case[3]) and type(result['passed']) is bool,'api21_v2_result_identity')
            database=result['fixture_database']
            require(database is None and not result['passed'] or type(database) is str and re.fullmatch('[a-z][a-z0-9_]{0,62}',database) is not None,'api21_v2_database')
            if database is not None:databases.append(database)
            require(not result['passed'] or result_complete and (child is None or child_complete and child['status']=='passed'),'api21_v2_child_success')
        if ready is not None:scope=_api21_ready(ready,case[3])
        if evidence is not None:
            row=_api21_v2_evidence(evidence,ready,case);observation_bytes+=_api21_v2_size(row['observations'],1048576);require(observation_bytes<=22020096,'api21_v2_run_observations')
            if evidence['binding']['binding_state']=='complete' and child is not None and child['binding']['binding_state']=='complete':require(evidence['binding']==dict(child['binding'],producer_role='browser-runner'),'api21_v2_role_binding')
        passed=outcomes[index]=='passed'
        require(not passed or child is not None and result is not None and result['passed'] and parent_complete and parent['status']=='passed' and row is not None and row['status']=='passed','api21_v2_outcome')
        require(not result or not result['passed'] or row is not None and row['status']=='passed','api21_v2_result_evidence')
        if parent['status']=='passed':require(passed and result is not None and result['passed'],'api21_v2_parent_success')
        if result is not None:
            _api21_v2_business(result,row,evidence,scope,case,passed=result['passed'])
        _api21_v2_sidecars(parent,child,result,case,raw,passed=passed,used_workers=used_workers)
        if passed:
            require(prefix+'browser/'+case[2]+'/'+case[1]+'-failure.png' not in raw,'api21_v2_success_screenshot');observed.append(case[0])
        else:diagnostics.append(dict(case_id=case[0],category='producer_partial'))
    require(len(set(run_ids))<=1,'api21_v2_run_binding');unique(attempt_ids);unique(databases)
    require({ref for ref in raw if re.fullmatch('worker-[a-f0-9]{32}\\.log',ref)}==used_workers,'api21_v2_worker_inventory')
    store.recheck()
    return dict(status='unavailable',complete=False,profile_version=profile_version,candidate_sha=candidate_sha,
        trusted_base_sha=trusted_base_sha,profile_sha256=profile_sha256,observed_case_ids=observed,verified_case_ids=[],
        accepted_case_credit=0,accepted_new_case_credit=0,diagnostics=diagnostics,missing_validation_families=list(API21_V2_MISSING_FAMILIES),
        release_state='unverified',**{flag:False for flag in FLAGS})


def inspect_api21_v2_receipts(store, *, candidate_sha, trusted_base_sha, profile_sha256,
                              profile_version='api21-retained-v2'):
    """Separate offline v2 entry point; malformed data yields nonsecret codes."""
    try:
        return _api21_v2_inspect(store,candidate_sha=candidate_sha,trusted_base_sha=trusted_base_sha,
            profile_sha256=profile_sha256,profile_version=profile_version)
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError,RecursionError,UnicodeError):
        raise ContractError('api21_v2_malformed_shape') from None


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
