ALTER TABLE autoapi_article_fetch_jobs
    DROP CONSTRAINT IF EXISTS autoapi_article_fetch_jobs_status_check;

ALTER TABLE autoapi_article_fetch_jobs
    ADD CONSTRAINT autoapi_article_fetch_jobs_status_check
    CHECK (status IN ('pending', 'processing', 'completed', 'needs_review', 'failed', 'dead_letter'));

COMMENT ON COLUMN autoapi_article_fetch_jobs.attempt_count IS
    'Number of worker claims; a failed job moves to dead_letter after the configured maximum.';

INSERT INTO schema_migrations (version)
VALUES ('021_autoapi_article_fetch_job_retries')
ON CONFLICT (version) DO NOTHING;
