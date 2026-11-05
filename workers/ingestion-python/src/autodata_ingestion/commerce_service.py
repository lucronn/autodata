"""Workshop's durable payment authority. Provider I/O never holds database locks."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from .purchase_config import PurchaseConfig, parse_purchase_config

PRODUCT = "workshop-configuration-v1"
TERMS = "workshop-v1"
LIVE = ('creating', 'open', 'processing', 'paid', 'reconciliation_required')


class CommerceError(ValueError):
    def __init__(self, code="INVALID_REQUEST", http_status=400):
        super().__init__(code)
        self.code, self.http_status = code, http_status


class CommerceResult(dict):
    def __init__(self, value, http_status=200):
        super().__init__(value)
        self.http_status = http_status


def exact_fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CommerceError()
    return value


def validate_uuid(value):
    if not isinstance(value, str):
        raise CommerceError()
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise CommerceError() from None
    if str(parsed) != value:
        raise CommerceError()
    return value


def validate_region(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Z]{2}', value):
        raise CommerceError()
    return value


def canonical_checkout_hash(configuration_id, region, terms):
    return hashlib.sha256(json.dumps([configuration_id, region, terms], separators=(',', ':')).encode()).digest()


def validate_checkout_url(value):
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == 'https' and parsed.hostname == 'checkout.stripe.com'
                 and parsed.netloc == 'checkout.stripe.com'
                 and parsed.path.startswith('/c/pay/') and len(parsed.path)>len('/c/pay/')
                 and not any(c.isspace() or ord(c)<32 or ord(c)==127 for c in value))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise CommerceError('PAYMENT_DEPENDENCY_UNAVAILABLE', 503)
    return value


def checkout_return_origin(environment, value):
    try:
        p = urlsplit(value)
        port = p.port
        host = p.hostname
        local = host == 'localhost'
        if host and not local:
            try:
                local = ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
        valid = (environment in {'development', 'test', 'staging', 'production'} and host
                 and not p.username and not p.password and not p.path and not p.query and not p.fragment
                 and (p.scheme == 'https' or (environment == 'test' and p.scheme == 'http' and local)))
        if environment == 'production':
            valid = valid and value in {'https://cars.tk', 'https://autodata.cars.tk'}
        if any(c.isspace() or ord(c)<32 for c in value) or p.netloc.endswith(':'):
            valid = False
        if not valid or (port is not None and not 1 <= port <= 65535):
            raise ValueError()
    except (ValueError, TypeError):
        raise CommerceError('COMMERCE_CONFIGURATION_INVALID', 503) from None
    return value


def validate_settlement(order, session):
    """Accept only the exact stored financial contract, including expanded intent."""
    def same_mode(value):
        return type(value) is bool and value == order['livemode']
    intent = session.get('payment_intent')
    lines = session.get('line_items', {}).get('data')
    valid = (session.get('mode') == 'payment' and session.get('payment_method_types') == ['card'] and same_mode(session.get('livemode'))
             and type(session.get('amount_total')) is int and session['amount_total'] == order['amount_minor']
             and session.get('currency') == order['currency'].lower()
             and session.get('payment_status') == 'paid' and session.get('status') == 'complete'
             and session.get('metadata', {}).get('order_id') == str(order['order_id'])
             and isinstance(lines, list) and len(lines) == 1 and lines[0].get('quantity') == 1
             and type(lines[0].get('quantity')) is int
             and lines[0].get('price', {}).get('id') == order['expected_price_id']
             and isinstance(intent, dict) and intent.get('metadata', {}).get('order_id') == str(order['order_id'])
             and intent.get('payment_method_types') == ['card']
             and same_mode(intent.get('livemode')) and intent.get('capture_method') == 'automatic'
             and intent.get('status') == 'succeeded' and intent.get('amount') == order['amount_minor']
             and type(intent.get('amount')) is int and type(intent.get('amount_received')) is int
             and intent['amount_received'] == order['amount_minor'] and intent.get('currency') == order['currency'].lower()
             and isinstance(intent.get('id'), str) and intent['id'].startswith('pi_'))
    if not valid:
        raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
    if order.get('payment_intent_id') and order['payment_intent_id'] != intent['id']:
        raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
    if order.get('checkout_session_id') and order['checkout_session_id'] != session.get('id'):
        raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
    return intent['id']


@dataclass(frozen=True)
class CommerceConfig:
    mode: str
    account_id: str
    price_id: str

    @property
    def livemode(self):
        return self.mode == 'stripe_live'


class CommerceService:
    def __init__(self, connection_factory, config, provider, *, clock=None, purchase_config=None):
        if config.mode not in {'stripe_test', 'stripe_live'} or not config.account_id or not config.price_id:
            raise CommerceError('COMMERCE_UNAVAILABLE', 503)
        if purchase_config is not None and type(purchase_config) is not PurchaseConfig:
            raise ValueError("validated purchase configuration required")
        self.__purchase_config = purchase_config if purchase_config is not None else PurchaseConfig.disabled()
        self.connect, self.config, self.provider = connection_factory, config, provider
        self.clock = clock or (lambda: datetime.now(UTC))

    @property
    def _purchase_config(self):
        return self.__purchase_config

    def purchase_configuration(self):
        return CommerceResult(self._purchase_config.public())

    @contextmanager
    def transaction(self):
        from psycopg.rows import dict_row
        with self.connect() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '3s'")
                    cursor.execute("SET LOCAL lock_timeout = '3s'")
                    yield connection, cursor

    def _account(self, cursor, account_id, organization_id):
        validate_uuid(account_id); validate_uuid(organization_id)
        cursor.execute("SELECT 1 FROM customer_accounts WHERE customer_account_id=%s AND personal_organization_id=%s AND status='active'", (account_id, organization_id))
        if not cursor.fetchone():
            raise CommerceError('CUSTOMER_ACCESS_REQUIRED', 403)

    def _scope(self, cursor, configuration_id, region):
        validate_uuid(configuration_id); validate_region(region)
        cursor.execute("""SELECT c.vehicle_configuration_id, concat_ws(' ',b.make,b.model,b.model_year::text,c.trim) AS label
            FROM vehicle_configurations c JOIN vehicle_identity_bases b USING(vehicle_identity_base_id)
            WHERE c.vehicle_configuration_id=%s AND b.region=%s
              AND c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected'""", (configuration_id, region))
        row = cursor.fetchone()
        if not row:
            raise CommerceError('CONFIGURATION_NOT_FOUND', 404)
        return row

    def _lock(self, cursor, account_id, configuration_id, region):
        key = int.from_bytes(hashlib.sha256(f'{account_id}:{configuration_id}:{region}'.encode()).digest()[:8], 'big', signed=True)
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', (key,))

    def _order(self, cursor, order_id):
        cursor.execute('SELECT * FROM workshop_orders WHERE order_id=%s FOR UPDATE', (order_id,))
        return cursor.fetchone()

    def _assert_merchant(self, order):
        if order['stripe_account_id'] != self.config.account_id or order['livemode'] != self.config.livemode or order['expected_price_id'] != self.config.price_id:
            raise CommerceError('COMMERCE_CONFIGURATION_INVALID', 503)

    def quote(self, configuration_id, region):
        with self.transaction() as (_, cursor):
            scope = self._scope(cursor, configuration_id, region)
            self._product(cursor)
        return CommerceResult(dict(version='v1', product_key=PRODUCT, configuration_id=configuration_id,
            region=region, configuration_label=scope['label'], amount_minor=2000, currency='USD',
            purchase_terms_version=TERMS, purchasable=True))

    def _product(self, cursor):
        cursor.execute("SELECT dataset_product_id FROM dataset_products WHERE product_key=%s AND product_version=1 AND active AND price_minor=2000 AND currency='USD'", (PRODUCT,))
        row = cursor.fetchone()
        if not row:
            raise CommerceError('COMMERCE_UNAVAILABLE', 503)
        return row['dataset_product_id']

    def _response(self, order, status=200):
        result = dict(version='v1', state='processing', order_id=str(order['order_id']), configuration_id=str(order['configuration_id']), region=order['region'])
        if order['status'] == 'revoked':
            raise CommerceError('ENTITLEMENT_REVOKED', 403)
        if order['status'] == 'paid':
            result.update(state='owned', library_item_id=str(order['order_id']))
            status = 200
        elif order['status'] == 'open' and order.get('checkout_url') and order.get('provider_expires_at') and order['provider_expires_at'] > self.clock():
            result.update(state='checkout', checkout_url=validate_checkout_url(order['checkout_url']), provider_expires_at=order['provider_expires_at'].isoformat())
        else:
            status = 202
        return CommerceResult(result, status)

    def checkout(self, account_id, organization_id, key, payload):
        exact_fields(payload, {'configuration_id', 'region', 'terms_version'})
        config_id = validate_uuid(payload['configuration_id']); region = validate_region(payload['region'])
        validate_uuid(key)
        if payload['terms_version'] != TERMS:
            raise CommerceError('TERMS_VERSION_REQUIRED', 409)
        if not self._purchase_config.enabled:
            raise CommerceError("COMMERCE_UNAVAILABLE", 503)
        digest = canonical_checkout_hash(config_id, region, TERMS)
        created = False
        with self.transaction() as (_, cursor):
            self._account(cursor, account_id, organization_id)
            self._lock(cursor, account_id, config_id, region)
            cursor.execute("SELECT 1 FROM entitlements WHERE customer_account_id=%s AND configuration_id=%s AND region=%s AND status='revoked' LIMIT 1", (account_id,config_id,region))
            if cursor.fetchone():
                raise CommerceError('ENTITLEMENT_REVOKED',403)
            cursor.execute('SELECT * FROM workshop_checkout_requests WHERE customer_account_id=%s AND client_idempotency_key=%s', (account_id, key))
            mapping = cursor.fetchone()
            if mapping:
                if bytes(mapping['canonical_request_sha256']) != digest:
                    raise CommerceError('IDEMPOTENCY_CONFLICT', 409)
                order = self._order(cursor, mapping['order_id'])
            else:
                cursor.execute("SELECT order_id FROM workshop_orders WHERE customer_account_id=%s AND configuration_id=%s AND region=%s AND status='revoked' LIMIT 1", (account_id, config_id, region))
                if cursor.fetchone():
                    raise CommerceError('ENTITLEMENT_REVOKED', 403)
                cursor.execute('SELECT order_id FROM workshop_orders WHERE customer_account_id=%s AND configuration_id=%s AND region=%s AND status=ANY(%s) LIMIT 1', (account_id, config_id, region, list(LIVE)))
                live = cursor.fetchone()
                if live:
                    order = self._order(cursor, live['order_id'])
                else:
                    self._scope(cursor, config_id, region)
                    order_id = str(uuid.uuid4())
                    cursor.execute("""INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,
                        amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,2000,'USD',%s,%s,%s,%s,'creating',%s) RETURNING *""",
                        (order_id, account_id, organization_id, config_id, region, self._product(cursor), TERMS, self.config.account_id,
                         self.config.livemode, self.config.price_id, f'workshop:checkout:{order_id}:v1', self.clock()))
                    order = cursor.fetchone(); created = True
                cursor.execute('INSERT INTO workshop_checkout_requests(customer_account_id,client_idempotency_key,canonical_request_sha256,order_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING', (account_id, key, digest, order['order_id']))
                cursor.execute('SELECT canonical_request_sha256,order_id FROM workshop_checkout_requests WHERE customer_account_id=%s AND client_idempotency_key=%s', (account_id, key))
                bound = cursor.fetchone()
                if bytes(bound['canonical_request_sha256']) != digest or bound['order_id'] != order['order_id']:
                    raise CommerceError('IDEMPOTENCY_CONFLICT', 409)
            self._assert_merchant(order)
        if order['status'] == 'creating':
            if self.clock() - order['first_create_attempt_at'] >= timedelta(hours=23):
                with self.transaction() as (_, cursor):
                    self._lock(cursor, account_id, config_id, region)
                    cursor.execute("UPDATE workshop_orders SET status='reconciliation_required',updated_at=now() WHERE order_id=%s AND status='creating' RETURNING *", (order['order_id'],))
                    order = cursor.fetchone() or self._order(cursor, order['order_id'])
            else:
                try:
                    session = self.provider.create_order_checkout(order)
                    url = validate_checkout_url(session.get('url'))
                    expires = datetime.fromtimestamp(session['expires_at'], UTC)
                    if not str(session.get('id', '')).startswith('cs_') or session.get('metadata', {}).get('order_id') != str(order['order_id']) or type(session.get('livemode')) is not bool or session['livemode'] != order['livemode'] or session.get('mode') != 'payment' or type(session.get('amount_total')) is not int or session['amount_total'] != 2000 or session.get('currency') != 'usd':
                        raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
                except Exception:
                    return self._response(order)
                with self.transaction() as (_, cursor):
                    self._lock(cursor, account_id, config_id, region)
                    current = self._order(cursor, order['order_id'])
                    if current['checkout_session_id'] and current['checkout_session_id'] != session['id']:
                        raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
                    cursor.execute("""UPDATE workshop_orders SET checkout_session_id=%s,checkout_url=%s,provider_expires_at=%s,
                        status=CASE WHEN status='creating' THEN 'open' ELSE status END,updated_at=now() WHERE order_id=%s RETURNING *""", (session['id'], url, expires, order['order_id']))
                    order = cursor.fetchone()
        elif order['status'] == 'open' and order['provider_expires_at'] <= self.clock():
            order = self._reconcile_expiry(order)
        return self._response(order, 201 if created else 200)

    def _reconcile_expiry(self, order):
        try:
            session = self.provider.retrieve_order_session(order['checkout_session_id'])
            if (session.get('id') != order['checkout_session_id'] or session.get('metadata', {}).get('order_id') != str(order['order_id'])
                or type(session.get('livemode')) is not bool or session['livemode'] != order['livemode'] or session.get('mode') != 'payment'):
                raise CommerceError('PAYMENT_FINANCIAL_CONFLICT',409)
            calls = 1
            if session.get('status') == 'complete':
                return order  # Only verified settlement grants ownership.
            if session.get('status') == 'open':
                session = self.provider.expire_order_session(order['checkout_session_id']); calls += 1
            intent = session.get('payment_intent')
            safe = session.get('status') == 'expired' and not intent
            if isinstance(intent, dict) and intent.get('status') != 'canceled' and calls < 2:
                if intent.get('metadata', {}).get('order_id') != str(order['order_id']) or intent.get('livemode') != order['livemode']:
                    raise CommerceError('PAYMENT_FINANCIAL_CONFLICT',409)
                intent = self.provider.cancel_payment_intent(intent['id']); calls += 1
            # An expanded canceled intent is authoritative; never infer from the clock.
            if isinstance(intent, dict):
                safe = (session.get('status') == 'expired' and intent.get('status') == 'canceled'
                        and intent.get('metadata', {}).get('order_id') == str(order['order_id'])
                        and type(intent.get('livemode')) is bool and intent['livemode'] == order['livemode'])
            if not safe:
                return order
        except Exception:
            return order
        with self.transaction() as (_, cursor):
            self._lock(cursor, str(order['customer_account_id']), str(order['configuration_id']), order['region'])
            current = self._order(cursor, order['order_id'])
            if current['status'] == 'open':
                cursor.execute("UPDATE workshop_orders SET status='expired',last_reconciled_at=now(),updated_at=now() WHERE order_id=%s RETURNING *", (order['order_id'],))
                current = cursor.fetchone()
            return current

    def order_status(self, account_id, organization_id, order_id):
        validate_uuid(order_id)
        with self.transaction() as (_, cursor):
            self._account(cursor, account_id, organization_id)
            cursor.execute('SELECT * FROM workshop_orders WHERE order_id=%s AND customer_account_id=%s', (order_id, account_id))
            order = cursor.fetchone()
            if not order:
                raise CommerceError('ORDER_NOT_FOUND', 404)
            self._assert_merchant(order)
        if order['status'] == 'open' and order['provider_expires_at'] <= self.clock():
            order = self._reconcile_expiry(order)
        return CommerceResult(dict(version='v1', order_id=order_id, configuration_id=str(order['configuration_id']), region=order['region'],
            state=order['status'], retry_disposition=('new_key' if order['status'] in {'expired', 'canceled'} else 'do_not_repay')))

    def webhook(self, signature, body):
        if not isinstance(signature, str) or not signature or len(signature.encode()) > 4096 or len(body) > 1048576:
            raise CommerceError()
        try:
            event = self.provider.verify_commerce_webhook({'Stripe-Signature': signature}, body)
        except ValueError:
            raise CommerceError('INVALID_STRIPE_SIGNATURE') from None
        if event['event_type'] == 'ignored':
            return CommerceResult({'status': 'ignored'})
        return self.reconcile_event(event)

    def reconcile_event(self, event):
        """Commit signed safe facts first; provider observations never alter replay data."""
        from psycopg.types.json import Jsonb
        from .payment_reconciliation import canonical_payment_payload
        if event.get('kind') != 'workshop' or event.get('provider_name') != 'stripe' or not event.get('provider_event_id'):
            raise CommerceError('INVALID_PAYMENT_EVENT')
        if type(event.get('livemode')) is not bool or event['livemode'] != self.config.livemode:
            raise CommerceError('PAYMENT_MODE_CONFLICT', 409)
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'autodata-payment:stripe:' + event['provider_event_id']))
        with self.transaction() as (_, cursor):
            cursor.execute("""INSERT INTO payment_events(payment_event_id,provider_name,provider_event_id,event_type,verified,payload,occurred_at,fulfillment_status)
                VALUES(%s,'stripe',%s,%s,true,%s,%s,'pending') ON CONFLICT(provider_event_id) DO NOTHING""",
                (event_id, event['provider_event_id'], event['event_type'], Jsonb(event), datetime.fromtimestamp(event['occurred_at'], UTC)))
            cursor.execute('SELECT payload,fulfillment_status FROM payment_events WHERE payment_event_id=%s FOR UPDATE', (event_id,))
            stored = cursor.fetchone()
            if not stored or canonical_payment_payload(stored['payload']) != canonical_payment_payload(event):
                raise CommerceError('PAYMENT_EVENT_CONFLICT', 409)
            if stored['fulfillment_status'] in {'fulfilled', 'failed'}:
                return CommerceResult({'status': 'accepted'})
            cursor.execute('UPDATE payment_events SET fulfillment_attempts=fulfillment_attempts+1 WHERE payment_event_id=%s', (event_id,))
            cursor.execute("""SELECT * FROM workshop_orders WHERE order_id::text=%s
                OR checkout_session_id=%s OR payment_intent_id=%s LIMIT 1""",
                (event.get('order_id'), event.get('checkout_session_id'), event.get('payment_intent_id')))
            order = cursor.fetchone()
        # PI metadata resolves early refund/dispute events without trusting browser data.
        intent = None
        calls = 0
        if not order and event.get('payment_intent_id'):
            try:
                intent = self.provider.retrieve_payment_intent(event['payment_intent_id']); calls += 1
            except Exception:
                raise CommerceError('PAYMENT_DEPENDENCY_UNAVAILABLE', 503) from None
            with self.transaction() as (_, cursor):
                cursor.execute('SELECT * FROM workshop_orders WHERE order_id::text=%s', (intent.get('metadata', {}).get('order_id'),))
                order = cursor.fetchone()
        if not order:
            return CommerceResult({'status': 'pending'})
        self._assert_merchant(order)
        kind = event['event_type']
        revoke_reason = None
        session = None
        try:
            if kind == 'charge.refunded':
                if event.get('refunded') is True and event.get('amount_refunded') == 2000 and event.get('amount') == 2000:
                    revoke_reason = 'full_refund'
            elif kind == 'charge.dispute.closed':
                if event.get('status') == 'lost' and event.get('amount') == 2000:
                    revoke_reason = 'chargeback_lost'
            elif kind in {'checkout.session.completed', 'payment_intent.succeeded'}:
                sid = event.get('checkout_session_id') or order['checkout_session_id']
                if not sid:
                    return CommerceResult({'status': 'pending'})
                session = self.provider.retrieve_order_session(sid); calls += 1
                if not isinstance(session.get('payment_intent'), dict) and session.get('payment_intent') and calls < 2:
                    session['payment_intent'] = self.provider.retrieve_payment_intent(session['payment_intent']); calls += 1
                payment_intent_id = validate_settlement(order, session)
                if event.get('payment_intent_id') and event['payment_intent_id'] != payment_intent_id:
                    raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
                if event.get('checkout_session_id') and event['checkout_session_id'] != session.get('id'):
                    raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
            elif kind == 'checkout.session.expired':
                self._reconcile_expiry(order)
            else:
                raise CommerceError('INVALID_PAYMENT_EVENT')
            if revoke_reason:
                if intent is None:
                    intent = self.provider.retrieve_payment_intent(event['payment_intent_id']); calls += 1
                if (intent.get('metadata', {}).get('order_id') != str(order['order_id'])
                    or type(intent.get('livemode')) is not bool or intent['livemode'] != order['livemode']
                    or intent.get('amount') != 2000 or intent.get('currency') != 'usd'
                    or event.get('currency') != 'usd' or intent.get('id') != event.get('payment_intent_id')
                    or (order.get('payment_intent_id') and order['payment_intent_id'] != intent['id'])):
                    raise CommerceError('PAYMENT_FINANCIAL_CONFLICT', 409)
        except CommerceError as error:
            with self.transaction() as (_, cursor):
                cursor.execute("UPDATE payment_events SET fulfillment_status='failed',last_fulfillment_error=%s WHERE payment_event_id=%s", (error.code, event_id))
            return CommerceResult({'status': 'quarantined'})
        except Exception:
            raise CommerceError('PAYMENT_DEPENDENCY_UNAVAILABLE', 503) from None
        with self.transaction() as (connection, cursor):
            self._lock(cursor, str(order['customer_account_id']), str(order['configuration_id']), order['region'])
            order = self._order(cursor, order['order_id'])
            self._assert_merchant(order)
            if revoke_reason:
                if order['entitlement_id']:
                    from .payment_reconciliation import revoke_entitlement
                    revoke_entitlement(connection, str(order['entitlement_id']), revoke_reason)
                cursor.execute("""UPDATE workshop_orders SET status='revoked',revoked_at=COALESCE(revoked_at,now()),
                    revocation_reason_code=COALESCE(revocation_reason_code,%s),payment_intent_id=COALESCE(payment_intent_id,%s),updated_at=now() WHERE order_id=%s""", (revoke_reason, intent['id'], order['order_id']))
            elif session and order['status'] != 'revoked':
                # Recheck immutable bindings under the scope lock after remote I/O.
                pid = validate_settlement(order, session)
                if order['status'] != 'paid':
                    request_id, entitlement_id, projection_id = [str(uuid.uuid5(uuid.UUID(str(order['order_id'])), name)) for name in ('request', 'entitlement', 'projection')]
                    cursor.execute("""INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id)
                        VALUES(%s,%s,%s,%s,'purchased','fast',%s,%s,'workshop-v1',%s)""",
                        (request_id, order['dataset_product_id'], str(order['configuration_id']), order['region'], order['order_id'], 'workshop:' + str(order['order_id']), order['organization_id']))
                    cursor.execute("""INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,payment_event_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id)
                        VALUES(%s,%s,%s,%s,%s,'active',now(),%s,%s,%s,%s)""",
                        (entitlement_id, order['organization_id'], request_id, event_id, event['provider_event_id'], order['customer_account_id'], order['configuration_id'], order['region'], order['order_id']))
                    cursor.execute('INSERT INTO dataset_projections(dataset_projection_id,dataset_product_id,dataset_request_id,entitlement_id) VALUES(%s,%s,%s,%s)',
                        (projection_id, order['dataset_product_id'], request_id, entitlement_id))
                    cursor.execute("""UPDATE workshop_orders SET status='paid',dataset_request_id=%s,entitlement_id=%s,paid_at=now(),checkout_session_id=%s,
                        payment_intent_id=%s,preparation_state='pending',preparation_next_attempt_at=now(),updated_at=now() WHERE order_id=%s""", (request_id, entitlement_id, session['id'], pid, order['order_id']))
            cursor.execute("UPDATE payment_events SET fulfillment_status='fulfilled',fulfilled_at=now(),last_fulfillment_error=NULL WHERE payment_event_id=%s", (event_id,))
        return CommerceResult({'status': 'accepted'})

    def grant_check(self, account_id, organization_id, configuration_id, region):
        with self.transaction() as (_, cursor):
            self._account(cursor, account_id, organization_id)
            validate_uuid(configuration_id); validate_region(region)
            cursor.execute("SELECT 1 FROM workshop_orders WHERE customer_account_id=%s AND configuration_id=%s AND region=%s AND stripe_account_id=%s AND livemode=%s AND status='revoked' LIMIT 1", (account_id,configuration_id,region,self.config.account_id,self.config.livemode))
            if cursor.fetchone():
                raise CommerceError('ENTITLEMENT_REVOKED',403)
            cursor.execute("""SELECT e.entitlement_id,e.status,o.order_id FROM entitlements e JOIN workshop_orders o ON o.order_id=e.commerce_order_id
                WHERE e.customer_account_id=%s AND e.configuration_id=%s AND e.region=%s AND o.stripe_account_id=%s AND o.livemode=%s
                ORDER BY e.granted_at DESC LIMIT 1""", (account_id, configuration_id, region, self.config.account_id, self.config.livemode))
            grant = cursor.fetchone()
            if not grant:
                raise CommerceError('ENTITLEMENT_REQUIRED', 403)
            if grant['status'] != 'active':
                raise CommerceError('ENTITLEMENT_REVOKED', 403)
            return CommerceResult(dict(entitlement_id=str(grant['entitlement_id']), order_id=str(grant['order_id']), configuration_id=configuration_id, region=region))

    def library(self, account_id, organization_id, cursor_value='', limit=20):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise CommerceError()
        after = None
        if cursor_value:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor_value + '=' * (-len(cursor_value) % 4)))
                if len(cursor_value) > 512 or len(decoded) != 3 or decoded[0] != account_id:
                    raise ValueError()
                after = (datetime.fromisoformat(decoded[1]), validate_uuid(decoded[2]))
            except Exception:
                raise CommerceError('INVALID_CURSOR') from None
        with self.transaction() as (_, cursor):
            self._account(cursor, account_id, organization_id)
            clause = 'AND (o.created_at,o.order_id)<(%s,%s)' if after else ''
            args = [account_id, self.config.account_id, self.config.livemode] + (list(after) if after else []) + [limit + 1]
            cursor.execute("""SELECT o.*,concat_ws(' ',b.make,b.model,b.model_year::text,c.trim) AS label,e.status AS grant_status,e.granted_at
                FROM workshop_orders o JOIN vehicle_configurations c ON c.vehicle_configuration_id=o.configuration_id
                JOIN vehicle_identity_bases b USING(vehicle_identity_base_id) LEFT JOIN entitlements e ON e.entitlement_id=o.entitlement_id
                WHERE o.customer_account_id=%s AND o.stripe_account_id=%s AND o.livemode=%s AND (o.status='revoked' OR e.entitlement_id IS NOT NULL) """ + clause + ' ORDER BY o.created_at DESC,o.order_id DESC LIMIT %s', args)
            rows = cursor.fetchall()
            items = []
            for order in rows[:limit]:
                state = 'paid'
                if order['status'] == 'revoked' or order['grant_status'] == 'revoked':
                    state = 'revoked'
                elif self._readable(cursor, order['configuration_id'], order['region']):
                    state = 'viewable'
                elif order['preparation_state'] != 'index_ready' or self._article_pending(cursor, order['configuration_id']):
                    state = 'preparing'
                item = dict(library_item_id=str(order['order_id']), configuration_id=str(order['configuration_id']), region=order['region'],
                    label=order['label'], access_state=state, granted_at=order['granted_at'].isoformat() if order['granted_at'] else None)
                if order['revoked_at']:
                    item['revoked_at'] = order['revoked_at'].isoformat()
                if order['preparation_last_error_code']:
                    item['content_error_code'] = order['preparation_last_error_code']
                items.append(item)
            next_cursor = ''
            if len(rows) > limit:
                last = rows[limit - 1]
                next_cursor = base64.urlsafe_b64encode(json.dumps([account_id, last['created_at'].isoformat(), str(last['order_id'])]).encode()).decode().rstrip('=')
            return CommerceResult(dict(version='v1', items=items, next_cursor=next_cursor))

    def _article_pending(self, cursor, configuration_id):
        cursor.execute("""SELECT 1 FROM source_fetch_jobs j JOIN canonical_articles a USING(canonical_article_id) WHERE a.vehicle_configuration_id=%s AND j.job_kind='article'
            AND (j.status IN ('pending','processing') OR (j.status='failed' AND j.retryable)) LIMIT 1""", (configuration_id,))
        return bool(cursor.fetchone())

    def _readable(self, cursor, configuration_id, region):
        cursor.execute("""SELECT 1 FROM catalog_article_current v JOIN canonical_articles a USING(canonical_article_id)
            JOIN vehicle_configurations c ON c.vehicle_configuration_id=a.vehicle_configuration_id
            JOIN vehicle_identity_bases b USING(vehicle_identity_base_id)
            WHERE a.vehicle_configuration_id=%s AND b.region=%s AND c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected'
            AND a.membership_status='active' AND EXISTS(SELECT 1 FROM source_snapshots descriptor WHERE descriptor.source_snapshot_id=a.descriptor_source_snapshot_id AND descriptor.takedown_status='active') AND v.takedown_status='active' AND v.availability='available'
            AND jsonb_typeof(v.document->'blocks')='array' AND jsonb_array_length(v.document->'blocks')>0
            AND NOT EXISTS(SELECT 1 FROM source_review_items q WHERE q.item_kind='quarantine' AND q.status<>'approved'
              AND (q.source_snapshot_ids ? a.descriptor_source_snapshot_id::text OR EXISTS(
                SELECT 1 FROM canonical_article_source_revisions s WHERE s.source_revision_id=a.current_source_revision_id
                AND (q.source_snapshot_ids ? s.body_source_snapshot_id::text OR EXISTS(
                  SELECT 1 FROM jsonb_array_elements(s.resource_manifest) resource JOIN source_snapshots asset ON asset.content_sha256::text=resource->>'sha256'
                  WHERE q.source_snapshot_ids ? asset.source_snapshot_id::text))))) LIMIT 1""", (configuration_id, region))
        return bool(cursor.fetchone())


def database_connection():
    import psycopg
    address = os.environ.get('AUTODATA_DB_ADDRESS', 'postgres:5432')
    host, port = address.rsplit(':', 1)
    return psycopg.connect(host=host, port=int(port), dbname=os.environ.get('AUTODATA_POSTGRES_DB', 'autodata'),
        user=os.environ.get('AUTODATA_POSTGRES_USER', 'autodata'), password=os.environ.get('AUTODATA_POSTGRES_PASSWORD', ''), connect_timeout=2)


def configured_commerce(*, connection_factory=database_connection):
    """Explicit runtime composition; no ambient credentials or implicit live mode."""
    mode = os.environ.get('AUTODATA_COMMERCE_MODE', 'disabled')
    if mode == 'disabled':
        return None
    if mode not in {'stripe_test', 'stripe_live'}:
        raise CommerceError('COMMERCE_CONFIGURATION_INVALID', 503)
    purchase_config, malformed = parse_purchase_config(os.environ.get('AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON'))
    if malformed:
        logging.getLogger(__name__).warning('Workshop purchase configuration invalid; new checkout disabled')
    origin = checkout_return_origin(os.environ.get('AUTODATA_ENV', ''), os.environ.get('AUTODATA_PUBLIC_ORIGIN', ''))
    key, webhook, account, price, token = [os.environ.get(name, '').strip() for name in
        ('AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET', 'AUTODATA_STRIPE_ACCOUNT_ID', 'AUTODATA_STRIPE_PRICE_ID', 'AUTODATA_INGESTION_INTERNAL_TOKEN')]
    if not all((key, webhook, account, price, token)) or not key.startswith('sk_live_' if mode == 'stripe_live' else 'sk_test_'):
        raise CommerceError('COMMERCE_CONFIGURATION_INVALID', 503)
    import stripe
    from .stripe_adapter import StripePaymentProvider
    client = stripe.StripeClient(key, max_network_retries=0, http_client=stripe.RequestsClient(timeout=8))
    provider = StripePaymentProvider(stripe_module=stripe, client=client, webhook_secret=webhook,
        success_url=origin + '/workshop/', cancel_url=origin + '/workshop/')
    service = CommerceService(connection_factory, CommerceConfig(mode, account, price), provider, purchase_config=purchase_config)
    # This network probe is outside a transaction and must succeed before readiness.
    try:
        provider.verify_merchant(account)
        provider.verify_price(price,service.config.livemode)
        with service.transaction() as (_, cursor):
            cursor.execute("SELECT 1 FROM schema_migrations WHERE version='040_workshop_commerce'")
            if not cursor.fetchone():
                raise ValueError()
            cursor.execute('SELECT 1 FROM workshop_orders WHERE stripe_account_id<>%s OR livemode<>%s LIMIT 1', (account, service.config.livemode))
            if cursor.fetchone():
                raise ValueError()
            service._product(cursor)
    except Exception:
        raise CommerceError('COMMERCE_CONFIGURATION_INVALID', 503) from None
    return service


def reconcile_workshop_preparation(connection, limit=10, *, scheduler=None, clock=None):
    """Lease paid intent, commit, schedule real shared index work, then acknowledge."""
    from psycopg.rows import dict_row
    if not 1 <= limit <= 10:
        raise ValueError('preparation batch must be between 1 and 10')
    if scheduler is None:
        from .catalog_service import ensure_catalog_hydration
        scheduler = ensure_catalog_hydration
    now = (clock or (lambda: datetime.now(UTC)))()
    owner = str(uuid.uuid4())
    with connection.transaction():
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SET LOCAL statement_timeout = '3s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
            cursor.execute("""WITH due AS (SELECT order_id FROM workshop_orders WHERE status='paid' AND preparation_state<>'index_ready'
                AND preparation_next_attempt_at<=%s AND (preparation_lease_expires_at IS NULL OR preparation_lease_expires_at<=%s)
                ORDER BY preparation_next_attempt_at,order_id LIMIT %s FOR UPDATE SKIP LOCKED)
                UPDATE workshop_orders o SET preparation_lease_owner=%s,preparation_lease_expires_at=%s,
                preparation_attempts=preparation_attempts+1 FROM due WHERE o.order_id=due.order_id RETURNING o.*""",
                (now, now, limit, owner, now + timedelta(seconds=30)))
            orders = cursor.fetchall()
    results = []
    for order in orders:
        state, code, jobs = 'retry', 'CATALOG_PREPARATION_UNAVAILABLE', []
        try:
            ack = scheduler(json.dumps(dict(scope='articles', vehicle_id=str(order['configuration_id']),
                vehicle_configuration_id=str(order['configuration_id']), idempotency_key=f"workshop-index:{order['configuration_id']}:{order['region']}:v1")))
            entries = ack.get('jobs', [])
            jobs = [validate_uuid(item['job_id']) for item in entries]
            if len(set(jobs)) != 2:
                raise ValueError('two durable provider jobs required')
            state = 'index_ready' if ack.get('state') == 'completed' else 'index_queued'
            code = None
            if ack.get('state') in {'failed', 'needs_review'}:
                state, code = 'blocked', 'CATALOG_PREPARATION_REVIEW'
        except Exception:
            pass
        delay = 15 if state == 'index_queued' else min(900, 15 * 2 ** min(order['preparation_attempts'] - 1, 6))
        with connection.transaction():
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3s'")
                cursor.execute("""UPDATE workshop_orders SET preparation_state=%s,preparation_last_error_code=%s,
                    preparation_index_job_ids=%s,preparation_next_attempt_at=%s,preparation_lease_owner=NULL,preparation_lease_expires_at=NULL,updated_at=now()
                    WHERE order_id=%s AND preparation_lease_owner=%s AND status='paid' RETURNING order_id""",
                    (state, code, jobs, now + timedelta(seconds=delay), order['order_id'], owner))
                if cursor.fetchone():
                    results.append(dict(order_id=str(order['order_id']), preparation_state=state))
    return results
