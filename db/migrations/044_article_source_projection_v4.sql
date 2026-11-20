BEGIN;
ALTER TABLE canonical_article_source_revisions
 DROP CONSTRAINT canonical_article_source_revisions_projection_version_check,
 ADD CONSTRAINT canonical_article_source_revisions_projection_version_check
 CHECK (projection_version IN ('source-projection-v1', 'source-projection-v2',
                               'source-projection-v3', 'source-projection-v4'));

CREATE OR REPLACE FUNCTION prevent_article_source_projection_downgrade() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
 versions constant text[] := ARRAY['source-projection-v1', 'source-projection-v2',
                                   'source-projection-v3', 'source-projection-v4'];
 old_position integer;
 new_position integer;
BEGIN
 IF OLD.current_source_revision_id IS DISTINCT FROM NEW.current_source_revision_id THEN
   SELECT array_position(versions, projection_version) INTO old_position
   FROM canonical_article_source_revisions
   WHERE source_revision_id=OLD.current_source_revision_id;
   IF old_position > 1 THEN
     SELECT array_position(versions, projection_version) INTO new_position
     FROM canonical_article_source_revisions
     WHERE source_revision_id=NEW.current_source_revision_id;
     IF new_position IS NULL OR new_position < old_position THEN
       RAISE EXCEPTION 'source projection downgrade is not supported' USING ERRCODE='23514';
     END IF;
   END IF;
 END IF;
 RETURN NEW;
END $$;

INSERT INTO schema_migrations(version) VALUES ('044_article_source_projection_v4') ON CONFLICT DO NOTHING;
COMMIT;
