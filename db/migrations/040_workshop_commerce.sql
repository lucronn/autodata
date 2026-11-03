BEGIN;

ALTER TABLE customer_accounts
    ADD CONSTRAINT customer_accounts_owner_pair UNIQUE (customer_account_id, personal_organization_id);

CREATE TABLE workshop_orders (
    order_id uuid PRIMARY KEY,
    customer_account_id uuid NOT NULL REFERENCES customer_accounts(customer_account_id),
    organization_id uuid NOT NULL,
    configuration_id uuid NOT NULL REFERENCES vehicle_configurations(vehicle_configuration_id),
    region text NOT NULL CHECK (region ~ '^[A-Z]{2}$'),
    dataset_product_id uuid NOT NULL REFERENCES dataset_products(dataset_product_id),
    terms_version text NOT NULL CHECK (terms_version = 'workshop-v1'),
    amount_minor bigint NOT NULL CHECK (amount_minor = 2000),
    currency char(3) NOT NULL CHECK (currency = 'USD'),
    stripe_account_id text NOT NULL CHECK (btrim(stripe_account_id) <> ''),
    livemode boolean NOT NULL,
    expected_price_id text NOT NULL CHECK (btrim(expected_price_id) <> ''),
    provider_idempotency_key text NOT NULL UNIQUE CHECK (btrim(provider_idempotency_key) <> ''),
    status text NOT NULL CHECK (status IN ('creating','open','processing','paid','expired','canceled','reconciliation_required','revoked')),
    checkout_session_id text UNIQUE,
    payment_intent_id text UNIQUE,
    checkout_url text,
    provider_expires_at timestamptz,
    first_create_attempt_at timestamptz NOT NULL,
    last_reconciled_at timestamptz,
    dataset_request_id uuid UNIQUE REFERENCES dataset_requests(dataset_request_id),
    entitlement_id uuid UNIQUE REFERENCES entitlements(entitlement_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    paid_at timestamptz,
    revoked_at timestamptz,
    revocation_reason_code text CHECK (revocation_reason_code IN ('full_refund','chargeback_lost','administrative')),
    preparation_state text NOT NULL DEFAULT 'pending' CHECK (preparation_state IN ('pending','index_queued','index_ready','retry','blocked')),
    preparation_attempts integer NOT NULL DEFAULT 0 CHECK (preparation_attempts >= 0),
    preparation_next_attempt_at timestamptz NOT NULL DEFAULT now(),
    preparation_lease_owner uuid,
    preparation_lease_expires_at timestamptz,
    preparation_index_job_ids uuid[] NOT NULL DEFAULT '{}',
    preparation_last_error_code text CHECK (preparation_last_error_code IN ('CATALOG_PREPARATION_UNAVAILABLE','CATALOG_PREPARATION_REVIEW','CATALOG_SOURCE_UNAVAILABLE')),
    FOREIGN KEY (customer_account_id, organization_id)
        REFERENCES customer_accounts(customer_account_id, personal_organization_id)
);
CREATE UNIQUE INDEX workshop_orders_live_scope_idx
    ON workshop_orders(customer_account_id, configuration_id, region)
    WHERE status IN ('creating','open','processing','paid','reconciliation_required');
CREATE INDEX workshop_orders_owner_library_idx
    ON workshop_orders(customer_account_id, created_at DESC, order_id DESC);
CREATE INDEX workshop_orders_preparation_idx
    ON workshop_orders(preparation_next_attempt_at) WHERE status = 'paid' AND preparation_state <> 'index_ready';

CREATE TABLE workshop_checkout_requests (
    customer_account_id uuid NOT NULL REFERENCES customer_accounts(customer_account_id),
    client_idempotency_key uuid NOT NULL,
    canonical_request_sha256 bytea NOT NULL CHECK (octet_length(canonical_request_sha256) = 32),
    order_id uuid NOT NULL REFERENCES workshop_orders(order_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (customer_account_id, client_idempotency_key)
);
ALTER TABLE entitlements
    ADD COLUMN customer_account_id uuid REFERENCES customer_accounts(customer_account_id),
    ADD COLUMN configuration_id uuid REFERENCES vehicle_configurations(vehicle_configuration_id),
    ADD COLUMN region text CHECK (region ~ '^[A-Z]{2}$'),
    ADD COLUMN commerce_order_id uuid UNIQUE REFERENCES workshop_orders(order_id),
    ADD CONSTRAINT entitlements_commerce_scope_complete CHECK (
        (customer_account_id IS NULL AND configuration_id IS NULL AND region IS NULL AND commerce_order_id IS NULL)
        OR (customer_account_id IS NOT NULL AND configuration_id IS NOT NULL AND region IS NOT NULL AND commerce_order_id IS NOT NULL)),
    ADD CONSTRAINT entitlements_customer_owner_pair FOREIGN KEY (customer_account_id, organization_id)
        REFERENCES customer_accounts(customer_account_id, personal_organization_id);
CREATE UNIQUE INDEX entitlements_active_customer_scope_idx
    ON entitlements(customer_account_id, configuration_id, region)
    WHERE status = 'active' AND customer_account_id IS NOT NULL;

INSERT INTO dataset_products(product_key,product_version,vehicle_selector,minimum_sections,price_minor,currency,active)
VALUES ('workshop-configuration-v1',1,'{"scope":"configuration_region","version":1}','[]',2000,'USD',true)
ON CONFLICT (product_key,product_version) DO NOTHING;

INSERT INTO schema_migrations(version) VALUES ('040_workshop_commerce') ON CONFLICT DO NOTHING;
COMMIT;
