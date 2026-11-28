BEGIN;

CREATE TABLE banktwo_authored_article_referrals (
    parent_article_id uuid NOT NULL,
    parent_source_revision_id uuid NOT NULL,
    authored_path_sha256 text NOT NULL CHECK (authored_path_sha256 COLLATE "C" ~ '^[a-f0-9]{64}$'),
    target_article_id uuid NOT NULL REFERENCES canonical_articles(canonical_article_id),
    descriptor_source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    inline_slots jsonb NOT NULL CHECK (jsonb_typeof(inline_slots)='array' AND jsonb_array_length(inline_slots)<=128),
    PRIMARY KEY (parent_article_id, parent_source_revision_id, authored_path_sha256),
    FOREIGN KEY (parent_source_revision_id, parent_article_id)
        REFERENCES canonical_article_source_revisions(source_revision_id, canonical_article_id),
    CHECK (parent_article_id <> target_article_id)
);

CREATE INDEX banktwo_authored_article_referrals_target
    ON banktwo_authored_article_referrals (target_article_id, descriptor_source_snapshot_id);

INSERT INTO schema_migrations(version) VALUES ('055_banktwo_authored_article_referrals')
ON CONFLICT DO NOTHING;

COMMIT;
