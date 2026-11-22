BEGIN;
ALTER TABLE canonical_article_source_revisions
 DROP CONSTRAINT canonical_article_source_revisions_projection_version_check,
 ADD CONSTRAINT canonical_article_source_revisions_projection_version_check
 CHECK (projection_version IN ('source-projection-v1', 'source-projection-v2', 'source-projection-v3'));

CREATE OR REPLACE FUNCTION prevent_article_source_projection_downgrade() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
 old_version text;
 new_version text;
BEGIN
 IF OLD.current_source_revision_id IS DISTINCT FROM NEW.current_source_revision_id THEN
   SELECT projection_version INTO old_version FROM canonical_article_source_revisions
   WHERE source_revision_id=OLD.current_source_revision_id;
   IF old_version IN ('source-projection-v2', 'source-projection-v3') THEN
     SELECT projection_version INTO new_version FROM canonical_article_source_revisions
     WHERE source_revision_id=NEW.current_source_revision_id;
     IF new_version IS NULL OR new_version='source-projection-v1'
        OR (old_version='source-projection-v3' AND new_version='source-projection-v2') THEN
       RAISE EXCEPTION 'source projection downgrade is not supported' USING ERRCODE='23514';
     END IF;
   END IF;
 END IF;
 RETURN NEW;
END $$;

INSERT INTO schema_migrations(version) VALUES ('043_article_source_projection_v3') ON CONFLICT DO NOTHING;
COMMIT;
