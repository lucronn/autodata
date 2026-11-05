"""Check supplied merchant preparation bytes offline; confer no operational authority.

The source identity is a declaration, owner/account references are unverified,
and prepared_offline means only that the supplied local bytes are consistent.
This module never injects a manifest, admits an artifact, or contacts a provider.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from urllib.parse import urlsplit

KINDS = ('terms', 'privacy', 'refund', 'contact')
SOURCE = {'sha': '6949eb1b1a5b93c9b2eb0579328e24c697f6f331',
          'tree': '47ec54b1896c83a39b6637a6ce944d3620414f4e'}
BUILD = {'sha256': 'bd7a4d022e89c76432cd5b8e086166252303710cb8cb24a72b5eeff31fc52559', 'bytes': 928}
EMBED = {'sha256': '6a6c78c4d84604ec4e626b49dc10e20603018e9db398c709073e689723801a77', 'bytes': 30491}
BASELINE = {'sha256': 'edb1d6d182c5eeee6c33885e873bc5b44ac7a3eb4465d9e92af5d1bc60d4b45f', 'bytes': 168}
AUTHORITY_KEYS = '''implementation implementation_dispatch provider runtime host host_execution docker network cloud dns capture profile_activation acceptance fixture_execution image_build_pull_install service_start payment account_mutation staging release merge deployment cutover secrets github_write code_approval ci_success merchant_enablement manifest_injection artifact_admission owner_approval stripe_test_acceptance live_sales'''.split()
EXTERNAL_PREREQUISITES = (
    'independent_owner_approval', 'published_policy_byte_verification',
    'approved_manifest_injection_rebuild', 'immutable_artifact_and_binary_binding',
    'exact_running_image_served_byte_capture',
    'authentic_stripe_test_enrollment_and_acceptance',
    'explicit_operational_release_authorization',
)


def _read(path: Path, limit: int) -> bytes | None:
    """Open once without following a leaf symlink; bound even changing files.

    O_NONBLOCK also prevents a nonregular input such as a FIFO from blocking
    before fstat can reject it. No content or exception text escapes this helper.
    """
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None  # fdopen owns the descriptor, including on errors.
            raw = stream.read(limit + 1)
        return raw if len(raw) <= limit else None
    except (OSError, ValueError, TypeError):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _binding(raw: bytes) -> dict[str, object]:
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate key')
        obj[key] = value
    return obj


def _nonfinite(value: str) -> None:
    raise ValueError('nonfinite value')


def _parse(raw: bytes | None) -> dict[str, object] | None:
    if raw is None:
        return None
    try:
        text = raw.decode('utf-8', errors='strict')
        if text.startswith('\ufeff'):
            return None
        obj = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        return obj if type(obj) is dict else None
    except (ValueError, UnicodeError, RecursionError):
        return None


def _text(value: object, maximum: int | None = None) -> bool:
    if type(value) is not str or not value.strip() or (maximum is not None and len(value) > maximum):
        return False
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        return False
    return True


def _digest(value: object) -> bool:
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _closed(obj: object, fields: dict) -> bool:
    return (type(obj) is dict and obj.keys() == fields.keys()
            and all(check(obj[key]) for key, check in fields.items()))


def _blob(obj: object) -> bool:
    return _closed(obj, {'sha256': _digest, 'bytes': _positive})


def _approval_schema(obj: object) -> bool:
    return _closed(obj, {
        'schema': _text, 'provenance': _text,
        'owner_approval_ref': lambda v: _text(v, 2048),
        'policy_revision': lambda v: _text(v, 256),
        'source': lambda v: _closed(v, {'sha': _text, 'tree': _text}),
        'build_recipe': _blob, 'embed_source': _blob,
        'manifest': lambda v: _closed(v, {'sha256': _digest, 'bytes': _positive,
                                        'served_path': _text, 'terms_version': _text}),
        'policies': lambda v: _closed(v, {k: lambda p: _closed(p, {
            'url': _text, 'sha256': _digest, 'bytes': _positive}) for k in KINDS}),
        'tax': lambda v: _closed(v, {'notice_sha256': _digest, 'notice_bytes': _positive,
                                   'final_price_treatment': _text,
                                   'owner_decision_ref': lambda r: _text(r, 2048)}),
        'product': lambda v: _closed(v, {'id': _text, 'currency': _text,
                                       'amount_minor': _positive, 'recurrence': _text}),
        'enrollment': lambda v: _closed(v, {'mode': _text, 'account_id': _text, 'price_id': _text}),
    })


def _manifest_schema(obj: object) -> bool:
    return _closed(obj, {'enabled': lambda v: type(v) is bool,
                         'terms_version': _text, 'tax_notice': _text,
                         **{k + '_url': _text for k in KINDS}})


def _url_valid(value: str, provenance: str) -> bool:
    # Validate the original string; never canonicalize it for tuple comparison.
    if any(c.isspace() or unicodedata.category(c) == 'Cc' for c in value) or '\\' in value or '#' in value:
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme != 'https' or not host or not parts.netloc
                or parts.username is not None or parts.password is not None
                or parts.netloc.endswith(':')):
            return False
        parts.port  # raises ValueError for a malformed/out-of-range port
    except ValueError:
        return False
    if provenance == 'synthetic':
        return True
    # A blacklist is a syntax guard only, never evidence of owner approval.
    host = host.lower().rstrip('.')
    if host == 'localhost' or any(host.endswith(s) for s in ('.localhost', '.local', '.test', '.invalid', '.example')):
        return False
    if any(host == domain or host.endswith('.' + domain) for domain in ('example.com', 'example.net', 'example.org')):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(segment in ('fixture', 'fixtures') for segment in parts.path.split('/'))


def evaluate_files(*, manifest: Path, approval: Path, policies: dict[str, Path],
                   build_recipe: Path, embed_source: Path) -> dict[str, object]:
    """Return deterministic local consistency evidence with all authorities false."""
    reasons: set[str] = set()
    raw_manifest = _read(manifest, 65536)
    raw_approval = _read(approval, 65536)
    raw_build = _read(build_recipe, 65536)
    raw_embed = _read(embed_source, 1048576)
    raw_policies: dict[str, bytes | None] = {}
    if type(policies) is not dict or set(policies) != set(KINDS):
        reasons.add('policy_mapping_invalid')
    for kind in KINDS:
        raw_policies[kind] = _read(policies[kind], 1048576) if type(policies) is dict and kind in policies else None
    for label, raw in [('manifest', raw_manifest), ('approval', raw_approval),
                       ('build_recipe', raw_build), ('embed_source', raw_embed),
                       *[(k + '_policy', raw_policies[k]) for k in KINDS]]:
        if raw is None:
            reasons.add(label + '_file_invalid')
    manifest_binding = _binding(raw_manifest) if raw_manifest is not None else None
    policy_bindings = {k: _binding(raw) if raw is not None else None for k, raw in raw_policies.items()}
    build_binding = _binding(raw_build) if raw_build is not None else None
    embed_binding = _binding(raw_embed) if raw_embed is not None else None
    baseline = manifest_binding == BASELINE
    candidate = _parse(raw_manifest)
    envelope = _parse(raw_approval)
    provenance = (envelope.get('provenance') if envelope is not None else None)
    if provenance not in ('synthetic', 'owner_supplied_unverified'):
        provenance = 'absent'
    if baseline:
        reasons.add('merchant_inputs_pending')
    elif candidate is None:
        reasons.add('manifest_json_invalid')
    elif not _manifest_schema(candidate):
        reasons.add('manifest_schema_invalid')
    else:
        if candidate['enabled'] is not True:
            reasons.add('manifest_enabled_invalid')
        if candidate['terms_version'] != 'workshop-v1':
            reasons.add('manifest_terms_version_invalid')
        if any(unicodedata.category(c) == 'Cc' and c not in '\n\t' for c in candidate['tax_notice']):
            reasons.add('tax_notice_invalid')
        for kind in KINDS:
            if not _url_valid(candidate[kind + '_url'], provenance):
                reasons.add(kind + '_url_invalid')
    if envelope is None:
        reasons.add('approval_json_invalid')
    elif not _approval_schema(envelope):
        reasons.add('approval_schema_invalid')
    else:
        if envelope['schema'] != 'workshop-merchant-preparation-v1':
            reasons.add('approval_schema_version_invalid')
        if provenance == 'absent':
            reasons.add('provenance_invalid')
        if envelope['source'] != SOURCE:
            reasons.add('source_identity_mismatch')
        for label, actual, pin in [('build_recipe', build_binding, BUILD), ('embed_source', embed_binding, EMBED)]:
            if actual != pin or envelope[label] != pin:
                reasons.add(label + '_binding_mismatch')
        declaration = envelope['manifest']
        if ({k: declaration[k] for k in ('sha256', 'bytes')} != manifest_binding
                or declaration['served_path'] != '/workshop/purchase-config.json'
                or declaration['terms_version'] != 'workshop-v1'):
            reasons.add('manifest_binding_mismatch')
        if not baseline and _manifest_schema(candidate):
            for kind in KINDS:
                declared = envelope['policies'][kind]
                if (declared['url'] != candidate[kind + '_url']
                        or {k: declared[k] for k in ('sha256', 'bytes')} != policy_bindings[kind]):
                    reasons.add(kind + '_policy_binding_mismatch')
            notice = candidate['tax_notice'].encode('utf-8')
            tax = envelope['tax']
            if (tax['notice_sha256'] != hashlib.sha256(notice).hexdigest()
                    or tax['notice_bytes'] != len(notice)):
                reasons.add('tax_notice_binding_mismatch')
        if envelope['tax']['final_price_treatment'] != 'owner_confirms_usd20_final_no_additional_tax_collection':
            reasons.add('tax_treatment_invalid')
        if envelope['product'] != {'id': 'workshop-configuration-v1', 'currency': 'USD', 'amount_minor': 2000, 'recurrence': 'one_time'}:
            reasons.add('product_invalid')
        enrollment = envelope['enrollment']
        if (enrollment['mode'] != 'stripe_test'
                or re.fullmatch(r'acct_[A-Za-z0-9]{1,251}', enrollment['account_id']) is None
                or re.fullmatch(r'price_[A-Za-z0-9]{1,250}', enrollment['price_id']) is None):
            reasons.add('enrollment_invalid')
    return {
        'schema': 'workshop-merchant-preparation-result-v1',
        'status': 'blocked' if reasons else 'prepared_offline', 'provenance': provenance,
        'manifest_sha256': manifest_binding['sha256'] if manifest_binding is not None else None,
        'manifest_bytes': manifest_binding['bytes'] if manifest_binding is not None else None,
        'baseline_disabled': baseline, 'reasons': sorted(reasons),
        'missing_external_prerequisites': list(EXTERNAL_PREREQUISITES),
        'authorities': dict.fromkeys(AUTHORITY_KEYS, False), 'accepted_case_credit': 0,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse otherwise echoes unknown argument values, which may be content.
        super().error('invalid command-line arguments')


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    for name in ('manifest', 'approval', 'build-recipe', 'embed-source'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--policy', action='append', required=True, metavar='KIND=PATH')
    args = parser.parse_args(argv)
    policies = {}
    for entry in args.policy:
        kind, separator, path = entry.partition('=')
        if not separator or kind not in KINDS or kind in policies or not path:
            parser.error('invalid policy mapping')
        policies[kind] = Path(path)
    if set(policies) != set(KINDS):
        parser.error('incomplete policy mapping')
    result = evaluate_files(manifest=args.manifest, approval=args.approval,
                            policies=policies, build_recipe=args.build_recipe,
                            embed_source=args.embed_source)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'prepared_offline' else 3


if __name__ == '__main__':
    raise SystemExit(main())
