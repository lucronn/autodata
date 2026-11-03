BEGIN;
CREATE TABLE canonical_article_revisions (
 canonical_article_revision_id uuid PRIMARY KEY,
 canonical_article_id uuid NOT NULL REFERENCES canonical_articles(canonical_article_id), source_revision_id uuid NOT NULL,
 transformation_key text NOT NULL UNIQUE CHECK(transformation_key ~ '^[a-f0-9]{64}$'),
 normalization_version text NOT NULL CHECK(length(btrim(normalization_version))>0), rewrite_profile_version text NOT NULL CHECK(length(btrim(rewrite_profile_version))>0),
 status text NOT NULL CHECK(status IN ('building','validated','published','rejected')),
 normalized_source_document jsonb NOT NULL CHECK(jsonb_typeof(normalized_source_document)='object'),
 normalized_source_hash text NOT NULL CHECK(normalized_source_hash ~ '^[a-f0-9]{64}$'),
 canonical_document jsonb NOT NULL CHECK(jsonb_typeof(canonical_document)='object'),
 canonical_body text NOT NULL, canonical_steps jsonb NOT NULL CHECK(jsonb_typeof(canonical_steps)='array'),
 canonical_images jsonb NOT NULL CHECK(jsonb_typeof(canonical_images)='array'),
 validation_report jsonb NOT NULL CHECK(jsonb_typeof(validation_report)='object'),
 validation_hash text NOT NULL CHECK(validation_hash ~ '^[a-f0-9]{64}$'),
 rewrite_result_hash text NOT NULL CHECK(rewrite_result_hash ~ '^[a-f0-9]{64}$'),
 model_metadata jsonb NOT NULL CHECK(jsonb_typeof(model_metadata)='object'),
 review_status text NOT NULL DEFAULT 'UNREVIEWED' CHECK(review_status IN ('UNREVIEWED','APPROVED','REJECTED')),
 created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz,
 CHECK ((status = 'published') = (published_at IS NOT NULL)),
 CHECK(status<>'published' OR COALESCE((jsonb_typeof(canonical_document->'blocks')='array' AND jsonb_array_length(canonical_document->'blocks')>0 AND
   validation_report->>'passed'='true' AND jsonb_typeof(validation_report->'changed_slots')='array' AND jsonb_array_length(validation_report->'changed_slots')>0 AND
   length(btrim(canonical_body))>0 AND model_metadata<>'{}'::jsonb AND length(model_metadata->>'model')>0 AND length(model_metadata->>'profile_version')>0 AND
   jsonb_typeof(validation_report->'evidence_ids')='array' AND jsonb_array_length(validation_report->'evidence_ids')>0),false)),
 FOREIGN KEY(transformation_key,canonical_article_id,source_revision_id,normalization_version,rewrite_profile_version) REFERENCES source_fetch_jobs(transformation_key,canonical_article_id,source_revision_id,normalization_version,rewrite_profile_version),
 FOREIGN KEY(source_revision_id,canonical_article_id) REFERENCES canonical_article_source_revisions(source_revision_id,canonical_article_id),
 UNIQUE(canonical_article_id,source_revision_id,normalization_version,rewrite_profile_version),
 UNIQUE(canonical_article_revision_id,canonical_article_id),
 UNIQUE(canonical_article_revision_id,canonical_article_id,source_revision_id)
);
CREATE FUNCTION reject_published_article_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF OLD.status='published' OR OLD.published_at IS NOT NULL THEN RAISE EXCEPTION 'immutable published article'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$;
CREATE TRIGGER immutable_published_article BEFORE UPDATE OR DELETE ON canonical_article_revisions FOR EACH ROW EXECUTE FUNCTION reject_published_article_mutation();
CREATE TABLE canonical_article_reviews (
 canonical_article_review_id uuid PRIMARY KEY, canonical_article_revision_id uuid NOT NULL REFERENCES canonical_article_revisions(canonical_article_revision_id),
 authorized_reviewer_id text NOT NULL CHECK(length(btrim(authorized_reviewer_id))>0), decision text NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
 reason text NOT NULL CHECK(length(btrim(reason))>0), reviewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER immutable_article_review BEFORE UPDATE OR DELETE ON canonical_article_reviews FOR EACH ROW EXECUTE FUNCTION reject_article_immutable_mutation();
CREATE TABLE canonical_article_rewrite_attempts (
 rewrite_attempt_id uuid PRIMARY KEY,
 source_fetch_job_id uuid NOT NULL REFERENCES source_fetch_jobs(source_fetch_job_id), canonical_article_revision_id uuid REFERENCES canonical_article_revisions(canonical_article_revision_id),
 lease_token bigint NOT NULL CHECK(lease_token>0), attempt_number integer NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
 provider text NOT NULL, model text NOT NULL, profile_version text NOT NULL,
 prompt_hash text NOT NULL CHECK(prompt_hash ~ '^[a-f0-9]{64}$'), input_hash text NOT NULL CHECK(input_hash ~ '^[a-f0-9]{64}$'),
 status text NOT NULL CHECK(status IN ('prepared','dispatched','succeeded','failed','ambiguous')),
 response jsonb CHECK(response IS NULL OR (jsonb_typeof(response)='object' AND octet_length(response::text)<=1048576)), response_hash text CHECK(response_hash ~ '^[a-f0-9]{64}$'),
 error_code text CHECK(error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,95}$'),
 created_at timestamptz NOT NULL DEFAULT now(), dispatched_at timestamptz, completed_at timestamptz,
 UNIQUE(source_fetch_job_id,lease_token,attempt_number)
);
CREATE FUNCTION enforce_article_attempt_owner() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.canonical_article_revision_id IS NOT NULL AND NOT EXISTS (
 SELECT 1 FROM source_fetch_jobs j JOIN canonical_article_revisions r ON r.canonical_article_id=j.canonical_article_id AND r.transformation_key=j.transformation_key
 WHERE j.source_fetch_job_id=NEW.source_fetch_job_id AND r.canonical_article_revision_id=NEW.canonical_article_revision_id)
 THEN RAISE EXCEPTION 'rewrite attempt ownership mismatch' USING ERRCODE='23503'; END IF; RETURN NEW; END $$;
CREATE TRIGGER article_attempt_owner BEFORE INSERT OR UPDATE ON canonical_article_rewrite_attempts FOR EACH ROW EXECUTE FUNCTION enforce_article_attempt_owner();
ALTER TABLE canonical_articles ADD COLUMN current_canonical_revision_id uuid,
 ADD CONSTRAINT canonical_article_revision_has_source CHECK(current_canonical_revision_id IS NULL OR current_source_revision_id IS NOT NULL),
 ADD CONSTRAINT canonical_article_current_revision_owner_fk FOREIGN KEY(current_canonical_revision_id,canonical_article_id) REFERENCES canonical_article_revisions(canonical_article_revision_id,canonical_article_id),
 ADD CONSTRAINT canonical_article_current_revision_fk FOREIGN KEY(current_canonical_revision_id,canonical_article_id,current_source_revision_id) REFERENCES canonical_article_revisions(canonical_article_revision_id,canonical_article_id,source_revision_id);
ALTER TABLE publication_events ADD COLUMN canonical_article_id uuid,
 ADD COLUMN canonical_article_revision_id uuid,
 ADD COLUMN delivery_lease_owner uuid, ADD COLUMN delivery_lease_token bigint NOT NULL DEFAULT 0 CHECK(delivery_lease_token>=0), ADD COLUMN delivery_lease_expires_at timestamptz, ADD COLUMN next_delivery_at timestamptz,
 ADD CONSTRAINT publication_article_owner_fk FOREIGN KEY(canonical_article_revision_id,canonical_article_id) REFERENCES canonical_article_revisions(canonical_article_revision_id,canonical_article_id),
 ADD CONSTRAINT publication_article_envelope_check CHECK (
 (event_type='catalog.article.published' AND canonical_article_id IS NOT NULL AND canonical_article_revision_id IS NOT NULL AND event_version=1 AND dataset_request_id IS NULL AND dataset_projection_id IS NULL AND dataset_revision_id IS NULL) OR
 (event_type<>'catalog.article.published' AND canonical_article_id IS NULL AND canonical_article_revision_id IS NULL)),
 ADD CONSTRAINT publication_delivery_lease_check CHECK((delivery_status='processing' AND delivery_lease_owner IS NOT NULL AND delivery_lease_token>0 AND delivery_lease_expires_at IS NOT NULL) OR (delivery_status<>'processing' AND delivery_lease_owner IS NULL AND delivery_lease_expires_at IS NULL));
ALTER TABLE publication_events DROP CONSTRAINT publication_events_delivery_status_check;
ALTER TABLE publication_events ADD CONSTRAINT publication_events_delivery_status_check CHECK(delivery_status IN ('pending','processing','published','failed','dead_letter'));
CREATE UNIQUE INDEX publication_article_event_once ON publication_events(event_type,canonical_article_revision_id) WHERE canonical_article_revision_id IS NOT NULL;
CREATE VIEW catalog_article_current AS
WITH selected AS (
 SELECT a.*, s.source_revision_id, s.body_source_snapshot_id, s.source_document,s.source_images,s.source_body,s.source_steps,s.captured_at,
   r.canonical_article_revision_id, r.canonical_document,r.canonical_images,r.canonical_body,r.canonical_steps,
   COALESCE(review.decision,r.review_status,'UNREVIEWED') AS effective_review,
   j.source_fetch_job_id,j.status AS job_status,j.phase,j.retryable AS job_retryable,j.next_attempt_at,j.error_code,
   snap.content_sha256, observation.body_provider_revision AS source_version,snap.retrieved_at,
   (SELECT entry->>'media_type' FROM jsonb_array_elements(s.resource_manifest) entry WHERE entry->>'role'='body' LIMIT 1) AS media_type,
   (a.takedown_status<>'active' OR EXISTS (
      SELECT 1 FROM source_snapshots blocked WHERE blocked.takedown_status<>'active' AND (blocked.source_snapshot_id=s.body_source_snapshot_id OR EXISTS (
        SELECT 1 FROM jsonb_array_elements(COALESCE(s.resource_manifest,'[]'::jsonb)) entry WHERE entry->>'sha256'=blocked.content_sha256::text)))) AS suppressed
 FROM canonical_articles a
 LEFT JOIN canonical_article_source_revisions s ON s.source_revision_id=a.current_source_revision_id
 LEFT JOIN canonical_article_revisions r ON r.canonical_article_revision_id=a.current_canonical_revision_id AND r.status='published'
   AND r.source_revision_id=a.current_source_revision_id AND r.normalization_version=a.target_normalization_version AND r.rewrite_profile_version=a.target_rewrite_profile_version
 LEFT JOIN LATERAL (SELECT decision FROM canonical_article_reviews WHERE canonical_article_revision_id=r.canonical_article_revision_id ORDER BY reviewed_at DESC,canonical_article_review_id DESC LIMIT 1) review ON true
 LEFT JOIN source_fetch_jobs j ON j.source_fetch_job_id=a.current_job_id
 LEFT JOIN source_snapshots snap ON snap.source_snapshot_id=s.body_source_snapshot_id
 LEFT JOIN LATERAL (SELECT body_provider_revision FROM canonical_article_source_observations WHERE source_revision_id=s.source_revision_id AND canonical_article_id=a.canonical_article_id ORDER BY request_generation DESC,captured_at DESC,source_observation_id DESC LIMIT 1) observation ON true
), chosen AS (
 SELECT *, (canonical_article_revision_id IS NOT NULL AND effective_review<>'REJECTED' AND NOT suppressed) AS use_canonical FROM selected
)
SELECT canonical_article_id, vehicle_id, vehicle_configuration_id,title,kind,component,provider_slug,source_vehicle_ref,source_article_ref,
 CASE WHEN NOT suppressed THEN source_revision_id END AS source_revision_id,
 CASE WHEN use_canonical THEN canonical_article_revision_id END AS canonical_revision_id,
 CASE WHEN use_canonical THEN 'canonical' WHEN source_revision_id IS NOT NULL AND NOT suppressed THEN 'source' END AS content_origin,
 CASE WHEN suppressed THEN 'unavailable' WHEN source_revision_id IS NOT NULL THEN 'available' WHEN job_status IN ('pending','processing') OR (job_status='failed' AND job_retryable) THEN 'pending' ELSE 'unavailable' END AS availability,
 CASE WHEN suppressed THEN NULL WHEN use_canonical THEN canonical_document ELSE source_document END AS document,
 CASE WHEN suppressed THEN NULL WHEN use_canonical THEN canonical_images ELSE source_images END AS images,
 CASE WHEN suppressed THEN NULL WHEN use_canonical THEN canonical_body ELSE source_body END AS body,
 CASE WHEN suppressed THEN NULL WHEN use_canonical THEN canonical_steps ELSE source_steps END AS steps,
 source_fetch_job_id AS job_id,
 CASE WHEN effective_review='REJECTED' AND canonical_article_revision_id IS NOT NULL THEN 'needs_review' WHEN job_status='dead_letter' THEN 'failed' WHEN job_status='pending' THEN 'queued' WHEN job_status='processing' THEN phase ELSE job_status END AS processing_state,
 CASE WHEN job_status='dead_letter' OR effective_review='REJECTED' THEN false ELSE COALESCE(job_retryable,false) END AS retryable,
 CASE WHEN job_status='failed' AND job_retryable THEN GREATEST(0,ceil(extract(epoch FROM next_attempt_at-clock_timestamp()))::integer) END AS retry_after_seconds,
 CASE WHEN effective_review='REJECTED' AND canonical_article_revision_id IS NOT NULL THEN 'CANONICAL_REVIEW_REJECTED' ELSE error_code END AS processing_error_code,
 CASE WHEN use_canonical THEN effective_review ELSE 'UNREVIEWED' END AS review_status,updated_at,
 CASE WHEN suppressed AND takedown_status='active' THEN 'takedown' ELSE takedown_status END AS takedown_status,
 body_source_snapshot_id AS source_snapshot_id, content_sha256 AS source_content_sha256,source_version,media_type AS source_media_type,captured_at AS source_captured_at
FROM chosen;
INSERT INTO schema_migrations(version) VALUES('038_article_transform_publication') ON CONFLICT DO NOTHING;
COMMIT;
