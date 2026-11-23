BEGIN;

-- Corrective jobs record each real model request within their one leased job.
-- Preserve the existing three-attempt bound on all other rewrite profiles.
ALTER TABLE canonical_article_rewrite_attempts
    DROP CONSTRAINT canonical_article_rewrite_attempts_attempt_number_check,
    ADD CONSTRAINT canonical_article_rewrite_attempts_attempt_number_check CHECK (
        attempt_number BETWEEN 1 AND CASE
            WHEN profile_version = 'full-prose-auto-v3' THEN 12
            ELSE 3
        END
    );

INSERT INTO schema_migrations(version) VALUES ('051_source_bound_correction_attempts')
ON CONFLICT DO NOTHING;

COMMIT;
