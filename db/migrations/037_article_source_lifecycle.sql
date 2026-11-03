BEGIN;
CREATE UNIQUE INDEX vehicle_configuration_vehicle_owner_key ON vehicle_configurations(vehicle_configuration_id, vehicle_id);
CREATE TABLE canonical_articles (
 canonical_article_id uuid PRIMARY KEY,
 provider_slug text NOT NULL CHECK (provider_slug IN ('bankone','banktwo')),
 vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
 vehicle_configuration_id uuid,
 scope_key text NOT NULL,
 source_vehicle_ref text NOT NULL CHECK (length(btrim(source_vehicle_ref)) BETWEEN 1 AND 1024 AND source_vehicle_ref !~ '[[:cntrl:]]'),
 source_article_ref text NOT NULL CHECK (length(btrim(source_article_ref)) BETWEEN 1 AND 2048 AND source_article_ref !~ '[[:cntrl:]]'),
 identity_key text NOT NULL UNIQUE CHECK (identity_key ~ '^[a-f0-9]{64}$'),
 descriptor jsonb NOT NULL CHECK (jsonb_typeof(descriptor)='object'),
 descriptor_source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
 title text, kind text, component text, source_sort_order integer,
 request_generation bigint NOT NULL DEFAULT 0 CHECK (request_generation>=0),
 target_normalization_version text NOT NULL DEFAULT 'ordered-article-v1' CHECK (length(btrim(target_normalization_version))>0),
 target_rewrite_profile_version text NOT NULL DEFAULT 'technical-prose-v1' CHECK (length(btrim(target_rewrite_profile_version))>0),
 current_job_id uuid,
 current_source_revision_id uuid,
 last_seen_catalog_generation bigint NOT NULL DEFAULT 0 CHECK (last_seen_catalog_generation>=0),
 membership_status text NOT NULL DEFAULT 'active' CHECK (membership_status IN ('active','retired')),
 takedown_status text NOT NULL DEFAULT 'active' CHECK (takedown_status IN ('active','takedown','expired')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (scope_key=CASE WHEN vehicle_configuration_id IS NULL THEN 'vehicle:'||vehicle_id::text ELSE 'configuration:'||vehicle_configuration_id::text END),
 FOREIGN KEY(vehicle_configuration_id,vehicle_id) REFERENCES vehicle_configurations(vehicle_configuration_id,vehicle_id),
 UNIQUE(provider_slug,scope_key,source_vehicle_ref,source_article_ref),
 UNIQUE(canonical_article_id,provider_slug,vehicle_id)
);
CREATE FUNCTION preserve_canonical_article_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF ROW(OLD.canonical_article_id,OLD.provider_slug,OLD.vehicle_id,OLD.vehicle_configuration_id,OLD.scope_key,OLD.source_vehicle_ref,OLD.source_article_ref,OLD.identity_key)
 IS DISTINCT FROM ROW(NEW.canonical_article_id,NEW.provider_slug,NEW.vehicle_id,NEW.vehicle_configuration_id,NEW.scope_key,NEW.source_vehicle_ref,NEW.source_article_ref,NEW.identity_key)
 THEN RAISE EXCEPTION 'immutable canonical article identity' USING ERRCODE='23514'; END IF; RETURN NEW; END $$;
CREATE TRIGGER immutable_canonical_article_identity BEFORE UPDATE ON canonical_articles FOR EACH ROW EXECUTE FUNCTION preserve_canonical_article_identity();
CREATE TABLE canonical_article_source_revisions (
 source_revision_id uuid PRIMARY KEY,
 canonical_article_id uuid NOT NULL REFERENCES canonical_articles(canonical_article_id),
 source_fingerprint text NOT NULL CHECK (source_fingerprint ~ '^[a-f0-9]{64}$'),
 body_source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
 resource_manifest jsonb NOT NULL CHECK (jsonb_typeof(resource_manifest)='array'),
 source_document jsonb NOT NULL CHECK (jsonb_typeof(source_document)='object' AND jsonb_typeof(source_document->'blocks')='array' AND jsonb_array_length(source_document->'blocks')>0),
 source_images jsonb NOT NULL CHECK(jsonb_typeof(source_images)='array'),
 source_body text NOT NULL CHECK(length(btrim(source_body))>0),
 source_steps jsonb NOT NULL CHECK(jsonb_typeof(source_steps)='array'),
 projection_version text NOT NULL DEFAULT 'source-projection-v1' CHECK(projection_version='source-projection-v1'),
 projection_status text NOT NULL CHECK(projection_status IN ('readable','partial')),
 evidence_manifest jsonb NOT NULL CHECK(jsonb_typeof(evidence_manifest)='array' AND jsonb_array_length(evidence_manifest)>0),
 captured_at timestamptz NOT NULL,
 UNIQUE(canonical_article_id,source_fingerprint), UNIQUE(source_revision_id,canonical_article_id)
);
CREATE FUNCTION reject_article_immutable_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable article lifecycle record'; END $$;
CREATE TRIGGER immutable_article_source BEFORE UPDATE OR DELETE ON canonical_article_source_revisions FOR EACH ROW EXECUTE FUNCTION reject_article_immutable_mutation();
CREATE TABLE catalog_article_provider_scopes (
 catalog_provider_scope_id uuid PRIMARY KEY,
 vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id), vehicle_configuration_id uuid,
 scope_key text NOT NULL,
 provider_slug text NOT NULL CHECK(provider_slug IN ('bankone','banktwo')),
 source_vehicle_ref text CHECK(source_vehicle_ref IS NULL OR (length(btrim(source_vehicle_ref)) BETWEEN 1 AND 1024 AND source_vehicle_ref !~ '[[:cntrl:]]')),
 resolution_source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
 generation bigint NOT NULL DEFAULT 0 CHECK(generation>=0), completed_generation bigint CHECK(completed_generation>=0),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','complete','partial','failed','needs_review','not_configured')),
 current_job_id uuid, next_cursor text, row_count integer NOT NULL DEFAULT 0 CHECK(row_count>=0), error_code text, retry_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(scope_key=CASE WHEN vehicle_configuration_id IS NULL THEN 'vehicle:'||vehicle_id::text ELSE 'configuration:'||vehicle_configuration_id::text END),
 FOREIGN KEY(vehicle_configuration_id,vehicle_id) REFERENCES vehicle_configurations(vehicle_configuration_id,vehicle_id),
 UNIQUE(scope_key,provider_slug), UNIQUE(catalog_provider_scope_id,provider_slug,vehicle_id)
);
ALTER TABLE source_fetch_jobs
 ADD COLUMN job_kind text NOT NULL DEFAULT 'legacy_batch' CHECK(job_kind IN ('legacy_batch','catalog_index','article')),
 ADD COLUMN canonical_article_id uuid,
 ADD COLUMN catalog_provider_scope_id uuid,
 ADD COLUMN source_revision_id uuid,
 ADD COLUMN request_generation bigint NOT NULL DEFAULT 0 CHECK(request_generation>=0),
 ADD COLUMN phase text NOT NULL DEFAULT 'queued' CHECK(phase IN ('queued','fetching_source','normalizing','rewriting','validating','publishing','completed')),
 ADD COLUMN transformation_key text UNIQUE CHECK(transformation_key ~ '^[a-f0-9]{64}$'),
 ADD COLUMN normalization_version text,
 ADD COLUMN rewrite_profile_version text,
 ADD COLUMN lease_owner uuid, ADD COLUMN lease_token bigint NOT NULL DEFAULT 0 CHECK(lease_token>=0),
 ADD COLUMN lease_expires_at timestamptz, ADD COLUMN heartbeat_at timestamptz, ADD COLUMN next_attempt_at timestamptz,
 ADD COLUMN max_attempts integer NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 3),
 ADD COLUMN error_code text CHECK(error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,95}$'),
 ADD COLUMN retryable boolean NOT NULL DEFAULT false,
 ADD COLUMN correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
 ADD CONSTRAINT source_job_owner_check CHECK(job_kind='legacy_batch' OR
   (job_kind='article' AND canonical_article_id IS NOT NULL AND catalog_provider_scope_id IS NULL AND length(btrim(normalization_version))>0 AND length(btrim(rewrite_profile_version))>0 AND normalization_version IS NOT NULL AND rewrite_profile_version IS NOT NULL) OR
   (job_kind='catalog_index' AND catalog_provider_scope_id IS NOT NULL AND canonical_article_id IS NULL AND source_revision_id IS NULL AND transformation_key IS NULL)),
 ADD CONSTRAINT source_job_lease_check CHECK(job_kind='legacy_batch' OR
   (status='processing' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL AND lease_token>0) OR
   (status<>'processing' AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)),
 ADD CONSTRAINT source_job_article_owner_fk FOREIGN KEY(canonical_article_id,provider_slug,canonical_vehicle_id) REFERENCES canonical_articles(canonical_article_id,provider_slug,vehicle_id),
 ADD CONSTRAINT source_job_scope_owner_fk FOREIGN KEY(catalog_provider_scope_id,provider_slug,canonical_vehicle_id) REFERENCES catalog_article_provider_scopes(catalog_provider_scope_id,provider_slug,vehicle_id),
 ADD CONSTRAINT source_job_source_owner_fk FOREIGN KEY(source_revision_id,canonical_article_id) REFERENCES canonical_article_source_revisions(source_revision_id,canonical_article_id),
 ADD CONSTRAINT source_job_transformation_owner UNIQUE(transformation_key,canonical_article_id,source_revision_id,normalization_version,rewrite_profile_version),
 ADD CONSTRAINT source_job_article_pair UNIQUE(source_fetch_job_id,canonical_article_id),
 ADD CONSTRAINT source_job_scope_pair UNIQUE(source_fetch_job_id,catalog_provider_scope_id);
CREATE UNIQUE INDEX source_job_article_generation ON source_fetch_jobs(canonical_article_id,request_generation) WHERE job_kind='article';
CREATE UNIQUE INDEX source_job_one_active_article ON source_fetch_jobs(canonical_article_id) WHERE job_kind='article' AND status IN ('pending','processing','failed');
CREATE UNIQUE INDEX source_job_scope_generation ON source_fetch_jobs(catalog_provider_scope_id,request_generation) WHERE job_kind='catalog_index';
ALTER TABLE canonical_articles ADD CONSTRAINT canonical_article_current_source_fk FOREIGN KEY(current_source_revision_id,canonical_article_id) REFERENCES canonical_article_source_revisions(source_revision_id,canonical_article_id),
 ADD CONSTRAINT canonical_article_source_has_job CHECK(current_source_revision_id IS NULL OR current_job_id IS NOT NULL),
 ADD CONSTRAINT canonical_article_current_job_fk FOREIGN KEY(current_job_id,canonical_article_id) REFERENCES source_fetch_jobs(source_fetch_job_id,canonical_article_id);
ALTER TABLE catalog_article_provider_scopes ADD CONSTRAINT catalog_scope_current_job_fk FOREIGN KEY(current_job_id,catalog_provider_scope_id) REFERENCES source_fetch_jobs(source_fetch_job_id,catalog_provider_scope_id);
CREATE TABLE canonical_article_source_observations (
 source_observation_id uuid PRIMARY KEY,
 canonical_article_id uuid NOT NULL REFERENCES canonical_articles(canonical_article_id),
 source_revision_id uuid NOT NULL,
 source_fetch_job_id uuid NOT NULL UNIQUE,
 request_generation bigint NOT NULL CHECK(request_generation>=0),
 body_provider_revision text NOT NULL,
 resource_provenance jsonb NOT NULL CHECK(jsonb_typeof(resource_provenance)='array'),
 captured_context jsonb NOT NULL CHECK(jsonb_typeof(captured_context)='object'),
 resolution_source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
 descriptor_source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
 captured_at timestamptz NOT NULL,
 FOREIGN KEY(source_revision_id,canonical_article_id) REFERENCES canonical_article_source_revisions(source_revision_id,canonical_article_id),
 FOREIGN KEY(source_fetch_job_id,canonical_article_id) REFERENCES source_fetch_jobs(source_fetch_job_id,canonical_article_id)
);
CREATE TRIGGER immutable_article_observation BEFORE UPDATE OR DELETE ON canonical_article_source_observations FOR EACH ROW EXECUTE FUNCTION reject_article_immutable_mutation();
CREATE TABLE catalog_article_index_pages (
 catalog_provider_scope_id uuid NOT NULL REFERENCES catalog_article_provider_scopes(catalog_provider_scope_id),
 generation bigint NOT NULL CHECK(generation>=0), page_number integer NOT NULL CHECK(page_number BETWEEN 0 AND 999),
 source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id), request_id uuid NOT NULL,
 provider_revision text NOT NULL, cursor_in text, cursor_out text, complete boolean NOT NULL,
 CHECK((complete AND cursor_out IS NULL) OR (NOT complete AND cursor_out IS NOT NULL)),
 PRIMARY KEY(catalog_provider_scope_id,generation,page_number)
);
CREATE TRIGGER immutable_article_index_page BEFORE UPDATE OR DELETE ON catalog_article_index_pages FOR EACH ROW EXECUTE FUNCTION reject_article_immutable_mutation();
ALTER TABLE catalog_articles ADD COLUMN canonical_article_id uuid REFERENCES canonical_articles(canonical_article_id);
CREATE TABLE canonical_article_aliases (
 catalog_article_id uuid PRIMARY KEY REFERENCES catalog_articles(catalog_article_id),
 canonical_article_id uuid NOT NULL REFERENCES canonical_articles(canonical_article_id),
 proof jsonb NOT NULL CHECK(jsonb_typeof(proof)='object' AND proof<>'{}'::jsonb), mapped_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE catalog_articles DROP CONSTRAINT IF EXISTS catalog_articles_content_status_check;
ALTER TABLE catalog_articles ADD CONSTRAINT catalog_articles_content_status_check CHECK(content_status IN ('list_only','content_complete','content_partial'));
INSERT INTO schema_migrations(version) VALUES('037_article_source_lifecycle') ON CONFLICT DO NOTHING;
COMMIT;
