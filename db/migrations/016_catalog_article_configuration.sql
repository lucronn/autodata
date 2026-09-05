ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS vehicle_configuration_id uuid
        REFERENCES vehicle_configurations(vehicle_configuration_id);

CREATE INDEX IF NOT EXISTS catalog_articles_configuration_idx
    ON catalog_articles (vehicle_configuration_id)
    WHERE vehicle_configuration_id IS NOT NULL;

COMMENT ON COLUMN catalog_articles.vehicle_configuration_id IS
    'Resolved vehicle configuration when source evidence identifies trim or engine dimensions; NULL is permitted for a coarse vehicle article.';

INSERT INTO schema_migrations (version)
VALUES ('016_catalog_article_configuration')
ON CONFLICT (version) DO NOTHING;
