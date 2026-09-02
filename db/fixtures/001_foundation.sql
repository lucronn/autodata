INSERT INTO dataset_products (
    dataset_product_id, product_key, product_version, vehicle_selector,
    minimum_sections, price_minor, currency
) VALUES (
    '10000000-0000-0000-0000-000000000001',
    'vehicle-core-fixture', 1,
    '{"make":"Toyota","model":"Corolla","year":2024,"region":"US"}',
    '["vehicle_identity","source_metadata","specifications"]',
    0, 'USD'
) ON CONFLICT (dataset_product_id) DO NOTHING;

INSERT INTO source_snapshots (
    source_snapshot_id, adapter_name, source_uri, source_version,
    content_sha256, object_key, license_metadata, retrieved_at
) VALUES (
    '20000000-0000-0000-0000-000000000001',
    'fake-primary-source', 'fake://source/toyota-corolla-2024-us', 'fixture-v1',
    repeat('a', 64), 'fixtures/toyota-corolla-2024-us.json',
    '{"fixture":true,"terms":"local-only"}', '2026-09-02T00:00:00Z'
) ON CONFLICT (source_snapshot_id) DO NOTHING;

INSERT INTO payment_events (
    payment_event_id, provider_name, provider_event_id, event_type,
    verified, payload, occurred_at
) VALUES (
    '25000000-0000-0000-0000-000000000001',
    'fake', 'fake-payment-event-001', 'checkout.completed', true,
    '{"fixture":true,"amount_minor":0}', '2026-09-02T00:00:00Z'
) ON CONFLICT (payment_event_id) DO NOTHING;

INSERT INTO dataset_requests (
    dataset_request_id, dataset_product_id, vehicle_key, region, status,
    lane, source_snapshot_id, correlation_id, idempotency_key, processing_version
) VALUES (
    '30000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001', 'toyota-corolla-2024', 'US',
    'viewable', 'fast', '20000000-0000-0000-0000-000000000001',
    '31000000-0000-0000-0000-000000000001', 'fixture-request-001', 'fixture-v1'
) ON CONFLICT (dataset_request_id) DO NOTHING;

INSERT INTO entitlements (
    entitlement_id, organization_id, dataset_request_id, payment_event_id,
    provider_event_id, status, granted_at
) VALUES (
    '40000000-0000-0000-0000-000000000001',
    '41000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    '25000000-0000-0000-0000-000000000001',
    'fake-payment-event-001', 'active', '2026-09-02T00:00:00Z'
) ON CONFLICT (entitlement_id) DO NOTHING;

INSERT INTO dataset_projections (
    dataset_projection_id, dataset_product_id, dataset_request_id, entitlement_id
) VALUES (
    '50000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001'
) ON CONFLICT (dataset_projection_id) DO NOTHING;

INSERT INTO dataset_revisions (
    dataset_revision_id, dataset_projection_id, revision_number,
    availability, source_watermark, schema_version, changelog, content, published_at
) VALUES (
    '60000000-0000-0000-0000-000000000001',
    '50000000-0000-0000-0000-000000000001', 1, 'viewable', 'fixture-v1', 1,
    '{"kind":"initial-fast-lane-publication","fixture":true}',
    '{"vehicle_identity":{"make":"Toyota","model":"Corolla","year":2024},"source_metadata":{"source_version":"fixture-v1"},"specifications":{"status":"viewable"}}',
    '2026-09-02T00:00:00Z'
) ON CONFLICT (dataset_revision_id) DO NOTHING;

INSERT INTO dataset_section_status (
    dataset_section_status_id, dataset_projection_id, section_name,
    status, last_published_revision_id, updated_at
) VALUES
    ('70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'vehicle_identity', 'viewable', '60000000-0000-0000-0000-000000000001', '2026-09-02T00:00:00Z'),
    ('70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 'source_metadata', 'viewable', '60000000-0000-0000-0000-000000000001', '2026-09-02T00:00:00Z'),
    ('70000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000001', 'specifications', 'viewable', '60000000-0000-0000-0000-000000000001', '2026-09-02T00:00:00Z')
ON CONFLICT (dataset_section_status_id) DO NOTHING;
