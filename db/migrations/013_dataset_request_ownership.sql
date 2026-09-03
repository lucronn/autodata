ALTER TABLE dataset_requests
    ADD COLUMN IF NOT EXISTS organization_id uuid;

UPDATE dataset_requests request
SET organization_id = entitlement.organization_id
FROM entitlements entitlement
WHERE entitlement.dataset_request_id = request.dataset_request_id
  AND request.organization_id IS NULL;

CREATE INDEX IF NOT EXISTS dataset_requests_organization_idx
    ON dataset_requests (organization_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('013_dataset_request_ownership')
ON CONFLICT (version) DO NOTHING;
