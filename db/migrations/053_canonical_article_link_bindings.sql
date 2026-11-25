BEGIN;

CREATE TABLE canonical_article_link_bindings (
    canonical_article_id uuid NOT NULL,
    source_revision_id uuid NOT NULL,
    canonical_article_revision_id uuid NOT NULL,
    block_id text NOT NULL
        CHECK (octet_length(block_id) BETWEEN 1 AND 256 AND block_id ~ '[^[:space:]]'),
    label_sha256 text NOT NULL
        CHECK (octet_length(label_sha256) = 64 AND label_sha256 COLLATE "C" ~ '^[0-9a-f]{64}$'),
    authored_id_sha256 text NOT NULL
        CHECK (octet_length(authored_id_sha256) = 64 AND authored_id_sha256 COLLATE "C" ~ '^[0-9a-f]{64}$'),
    target_ref_sha256 text NOT NULL
        CHECK (octet_length(target_ref_sha256) = 64 AND target_ref_sha256 COLLATE "C" ~ '^[0-9a-f]{64}$'),
    body_sha256 text NOT NULL
        CHECK (octet_length(body_sha256) = 64 AND body_sha256 COLLATE "C" ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (canonical_article_revision_id, block_id),
    FOREIGN KEY (canonical_article_revision_id, canonical_article_id, source_revision_id)
        REFERENCES canonical_article_revisions (canonical_article_revision_id, canonical_article_id, source_revision_id)
);

INSERT INTO schema_migrations(version) VALUES ('053_canonical_article_link_bindings')
ON CONFLICT DO NOTHING;

COMMIT;
