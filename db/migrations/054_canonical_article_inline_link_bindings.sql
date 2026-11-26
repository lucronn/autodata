BEGIN;

CREATE TABLE canonical_article_inline_link_bindings (
    canonical_article_id uuid NOT NULL,
    source_revision_id uuid NOT NULL,
    canonical_article_revision_id uuid NOT NULL,
    body_sha256 text NOT NULL CHECK (body_sha256 COLLATE "C" ~ '^[a-f0-9]{64}$'),
    block_id text NOT NULL CHECK (octet_length(block_id) BETWEEN 1 AND 256 AND block_id ~ '[^[:space:]]'),
    item_index integer NOT NULL CHECK (item_index >= -1),
    label text NOT NULL CHECK (octet_length(label) BETWEEN 1 AND 384 AND label ~ '[^[:space:]]'),
    label_sha256 text NOT NULL CHECK (label_sha256=encode(sha256(convert_to(label,'UTF8')),'hex')),
    authored_id_sha256 text NOT NULL CHECK (authored_id_sha256 COLLATE "C" ~ '^[a-f0-9]{64}$'),
    target_ref_sha256 text NOT NULL CHECK (target_ref_sha256 COLLATE "C" ~ '^[a-f0-9]{64}$'),
    PRIMARY KEY (canonical_article_revision_id, block_id, item_index, label_sha256),
    FOREIGN KEY (canonical_article_revision_id, canonical_article_id, source_revision_id)
        REFERENCES canonical_article_revisions (canonical_article_revision_id, canonical_article_id, source_revision_id)
);

INSERT INTO schema_migrations(version) VALUES ('054_canonical_article_inline_link_bindings')
ON CONFLICT DO NOTHING;

COMMIT;
