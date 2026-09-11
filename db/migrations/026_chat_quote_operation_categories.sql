ALTER TABLE chat_quote_revisions
    ADD COLUMN IF NOT EXISTS required_operations jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE chat_quote_revisions
    ADD COLUMN IF NOT EXISTS recommended_operations jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE chat_quote_revisions
    DROP CONSTRAINT IF EXISTS chat_quote_revisions_required_operations_array_check,
    DROP CONSTRAINT IF EXISTS chat_quote_revisions_recommended_operations_array_check;

ALTER TABLE chat_quote_revisions
    ADD CONSTRAINT chat_quote_revisions_required_operations_array_check
    CHECK (jsonb_typeof(required_operations) = 'array');

ALTER TABLE chat_quote_revisions
    ADD CONSTRAINT chat_quote_revisions_recommended_operations_array_check
    CHECK (jsonb_typeof(recommended_operations) = 'array');

INSERT INTO schema_migrations (version)
VALUES ('026_chat_quote_operation_categories')
ON CONFLICT (version) DO NOTHING;
