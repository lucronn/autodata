"""Frozen, syntactically validated purchase notices; no I/O or legal approval."""
from dataclasses import dataclass
import json
import re

_KEYS = frozenset(('enabled', 'terms_version', 'terms_url', 'privacy_url', 'refund_url', 'contact_url', 'tax_notice'))
_URL_KEYS = ('terms_url', 'privacy_url', 'refund_url', 'contact_url')


def _forbidden(code):
    return (code <= 32 or 127 <= code <= 160 or code == 0x1680 or
            0x2000 <= code <= 0x200a or code in (0x2028, 0x2029, 0x202f, 0x205f, 0x3000, 0xfeff))


def _url(value):
    if not isinstance(value, str) or not 1 <= len(value.encode('utf-8')) <= 2048 or any(_forbidden(ord(c)) for c in value):
        raise ValueError('invalid purchase configuration')
    # Inspect raw authority before a URL library can normalize input.
    match = re.fullmatch(r'https://([^/?#]+)(/[^?#]*)?', value)
    if not match:
        raise ValueError('invalid purchase configuration')
    authority, path = match.group(1), match.group(2) or ''
    host = authority[:-4] if authority.endswith(':443') else authority
    labels = host.split('.')
    if (len(host) > 253 or len(labels) < 2 or
        any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels) or
        not re.fullmatch(r'[A-Za-z]{2,63}', labels[-1]) or
        re.search(r'%(?![A-Fa-f0-9]{2})', path)):
        raise ValueError('invalid purchase configuration')


@dataclass(frozen=True, slots=True)
class PurchaseConfig:
    enabled: bool = False
    terms_version: str = 'workshop-v1'
    terms_url: str | None = None
    privacy_url: str | None = None
    refund_url: str | None = None
    contact_url: str | None = None
    tax_notice: str | None = None

    def __post_init__(self):
        if type(self.enabled) is not bool or self.terms_version != 'workshop-v1':
            raise ValueError('invalid purchase configuration')
        if not self.enabled:
            if any(getattr(self, key) is not None for key in (*_URL_KEYS, 'tax_notice')):
                raise ValueError('invalid purchase configuration')
            return
        try:
            for key in _URL_KEYS:
                _url(getattr(self, key))
            notice = self.tax_notice
            if (not isinstance(notice, str) or not any(not _forbidden(ord(c)) for c in notice) or
                len(notice.encode('utf-8')) > 1024 or
                any(ord(c) < 32 or 127 <= ord(c) <= 159 or ord(c) in (0x2028, 0x2029) for c in notice)):
                raise ValueError('invalid purchase configuration')
        except (UnicodeError, TypeError):
            raise ValueError('invalid purchase configuration') from None

    @classmethod
    def from_public(cls, value):
        if not isinstance(value, dict) or set(value) != _KEYS:
            raise ValueError('invalid purchase configuration')
        return cls(**value)

    @classmethod
    def disabled(cls):
        return cls()

    def public(self):
        return {key: getattr(self, key) for key in ('enabled', 'terms_version', *_URL_KEYS, 'tax_notice')}


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate purchase configuration key')
        value[key] = item
    return value


def _nonfinite(_):
    raise ValueError('nonfinite purchase configuration')


def parse_purchase_config(raw):
    if raw is None or raw == '':
        return PurchaseConfig.disabled(), False
    try:
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > 16384:
            raise ValueError()
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        return PurchaseConfig.from_public(value), False
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return PurchaseConfig.disabled(), True
