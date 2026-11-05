BEGIN;
-- Projection changes append immutable rows; raw fingerprints remain unchanged.
ALTER TABLE canonical_article_source_revisions
 DROP CONSTRAINT canonical_article_source_revisions_projection_version_check,
 ADD CONSTRAINT canonical_article_source_revisions_projection_version_check
 CHECK (projection_version IN ('source-projection-v1', 'source-projection-v2'));

-- Resolve the historical automatically truncated constraint name by its columns.
DO $$
DECLARE old_unique text;
BEGIN
 SELECT conname INTO STRICT old_unique FROM pg_constraint
 WHERE conrelid='canonical_article_source_revisions'::regclass
   AND contype='u'
   AND conkey=ARRAY[
     (SELECT attnum FROM pg_attribute WHERE attrelid=conrelid AND attname='canonical_article_id'),
     (SELECT attnum FROM pg_attribute WHERE attrelid=conrelid AND attname='source_fingerprint')
   ]::smallint[];
 EXECUTE format('ALTER TABLE canonical_article_source_revisions DROP CONSTRAINT %I', old_unique);
END $$;
ALTER TABLE canonical_article_source_revisions
 ADD CONSTRAINT article_source_projection_identity
 UNIQUE (canonical_article_id, source_fingerprint, projection_version);

CREATE FUNCTION prevent_article_source_projection_downgrade() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.current_source_revision_id IS DISTINCT FROM NEW.current_source_revision_id
    AND EXISTS (SELECT 1 FROM canonical_article_source_revisions
                WHERE source_revision_id=OLD.current_source_revision_id
                  AND projection_version='source-projection-v2')
    AND (NEW.current_source_revision_id IS NULL OR EXISTS (
         SELECT 1 FROM canonical_article_source_revisions
         WHERE source_revision_id=NEW.current_source_revision_id
           AND projection_version='source-projection-v1'))
 THEN
   RAISE EXCEPTION 'source projection downgrade is not supported' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER article_source_projection_no_downgrade
 BEFORE UPDATE OF current_source_revision_id ON canonical_articles
 FOR EACH ROW EXECUTE FUNCTION prevent_article_source_projection_downgrade();

INSERT INTO schema_migrations(version) VALUES ('041_article_source_projection_v2') ON CONFLICT DO NOTHING;
COMMIT;
