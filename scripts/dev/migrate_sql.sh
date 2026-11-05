#!/bin/sh
# Fixed, reviewed SQL manifest. SQL bodies are embedded literally, never evaluated.
set -eu
LC_ALL=C
export LC_ALL
fail() { echo "migration runner: $*" >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
migrations_dir="$script_dir/../../db/migrations"
explicit=0
emit=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --emit) [ "$emit" -eq 0 ] || fail "duplicate --emit"; emit=1; shift ;;
        --migrations-dir)
            [ "$explicit" -eq 0 ] && [ "$#" -ge 2 ] || fail "--migrations-dir requires one absolute directory"
            case "$2" in /*) migrations_dir=$2 ;; *) fail "migration directory must be absolute" ;; esac
            explicit=1; shift 2 ;;
        *) fail "unsupported argument: $1" ;;
    esac
done
[ -d "$migrations_dir" ] && [ ! -L "$migrations_dir" ] || fail "invalid migration directory"
canonical=$(cat <<'MANIFEST'
001_extensions.sql
002_platform_spine.sql
003_canonical_vehicle.sql
004_normalized_source_bundle.sql
005_preserve_duplicate_article_ids.sql
006_backfill_article_source_locators.sql
007_link_evidence_to_revision.sql
008_publication_outbox_delivery.sql
009_feedback_evidence_link.sql
010_evidence_review_metadata.sql
011_feedback_review_metadata.sql
012_payment_fulfillment_reconciliation.sql
013_dataset_request_ownership.sql
014_normalized_article_content.sql
015_vehicle_identity_resolution.sql
016_catalog_article_configuration.sql
017_knowledge_catalog_evidence_index.sql
018_source_review_items.sql
019_article_content_provenance.sql
020_autoapi_article_fetch_jobs.sql
021_autoapi_article_fetch_job_retries.sql
022_job_plan_derived_articles.sql
023_catalog_article_images.sql
024_catalog_article_operations.sql
025_chat_quote_procedure.sql
026_chat_quote_operation_categories.sql
027_chat_runtime_durable_state.sql
028_vehicle_provider_mappings.sql
029_vehicle_catalog_sync.sql
030_vehicle_catalog_years.sql
031_catalog_article_classification.sql
032_catalog_article_source_original.sql
033_catalog_scope_coverage.sql
034_catalog_article_progress.sql
035_ordered_article_document.sql
036_source_fetch_jobs.sql
037_article_source_lifecycle.sql
038_article_transform_publication.sql
039_production_identity_sessions.sql
040_workshop_commerce.sql
MANIFEST
)
# Validate everything before producing even the first byte of SQL.
set -- $canonical
count=0
for path in "$migrations_dir"/* "$migrations_dir"/.[!.]* "$migrations_dir"/..?*; do
    [ -e "$path" ] || [ -L "$path" ] || continue
    [ -f "$path" ] && [ ! -L "$path" ] || fail "not a regular migration: $path"
    name=${path##*/}
    # The repository keeps an empty directory placeholder alongside SQL files.
    if [ "$name" = .gitkeep ] && [ ! -s "$path" ]; then continue; fi
    [ "$#" -gt 0 ] || fail "unsupported extra migration: $path"
    [ "$name" = "$1" ] || fail "manifest mismatch: expected $1, found $name"
    # No historical migration needs a backslash. Rejecting all backslashes also
    # prevents inline psql commands, including commands after SQL on one line.
    if grep -F '\' "$path" >/dev/null; then fail "psql metacommand/backslash in $name"; fi
    case "$name" in
        036_*|037_*|038_*|039_*|040_*)
            [ "$(sed '/^[[:space:]]*$/d' "$path" | head -n 1)" = 'BEGIN;' ] || fail "missing audited BEGIN in $name"
            [ "$(sed '/^[[:space:]]*$/d' "$path" | tail -n 1)" = 'COMMIT;' ] || fail "missing audited COMMIT in $name"
            [ "$(grep -Ec '^(BEGIN|COMMIT);$' "$path")" -eq 2 ] || fail "unsupported transaction delimiters in $name"
            grep -Eq "VALUES[[:space:]]*\\('${name%.sql}'\\)" "$path" >/dev/null || fail "missing audited marker in $name"
            ;;
        *) if grep -Eq '^(BEGIN|COMMIT);$' "$path"; then fail "unexpected outer transaction in $name"; fi ;;
    esac
    count=$((count + 1)); shift
done
[ "$count" -gt 0 ] || fail "empty migration manifest"
[ "$explicit" -eq 1 ] || [ "$#" -eq 0 ] || fail "incomplete canonical migration manifest"

emit_known_tables_check() {
cat <<'SQL'
DO $driver_baseline$
BEGIN
    IF EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=current_schema() AND c.relname IN (
            'customer_accounts',
            'auth_sessions',
            'workshop_orders',
            'workshop_checkout_requests',
            'dataset_products',
            'source_snapshots',
            'payment_events',
            'dataset_requests',
            'entitlements',
            'dataset_projections',
            'dataset_revisions',
            'dataset_section_status',
            'ingestion_jobs',
            'extraction_runs',
            'extraction_evidence',
            'publication_events',
            'feedback_items',
            'vehicles',
            'vehicle_specifications',
            'source_artifacts',
            'vehicle_models',
            'powertrains',
            'inventory_parts',
            'catalog_articles',
            'vehicle_identity_bases',
            'vehicle_configurations',
            'vehicle_aliases',
            'vehicle_identity_observations',
            'catalog_article_vehicle_links',
            'source_review_items',
            'autoapi_article_fetch_jobs',
            'derived_articles',
            'derived_article_revisions',
            'derived_article_lineage',
            'chat_queries',
            'chat_query_options',
            'chat_derived_article_keys',
            'chat_job_plans',
            'parts_price_snapshots',
            'parts_price_snapshot_refreshes',
            'chat_quote_revisions',
            'chat_visual_artifacts',
            'chat_worker_events',
            'chat_runtime_queries',
            'chat_runtime_queue',
            'chat_runtime_event_contexts',
            'chat_runtime_events',
            'chat_runtime_event_retries',
            'vehicle_provider_mappings',
            'vehicle_catalog_syncs',
            'vehicle_catalog_sync_scopes',
            'vehicle_catalog_years',
            'vehicle_catalog_hydration_scopes',
            'source_fetch_jobs',
            'canonical_articles',
            'canonical_article_source_revisions',
            'catalog_article_provider_scopes',
            'canonical_article_source_observations',
            'catalog_article_index_pages',
            'canonical_article_aliases',
            'canonical_article_revisions',
            'canonical_article_reviews',
            'canonical_article_rewrite_attempts'
        )
    ) THEN
        RAISE EXCEPTION 'missing or empty ledger with known application tables; adoption refused';
    END IF;
END
$driver_baseline$;
SQL
}
emit_driver() {
cat <<'SQL'
\set ON_ERROR_STOP on
SET default_transaction_isolation TO 'read committed';
SET lock_timeout TO '60s';
SELECT pg_advisory_lock(186,3738);
SELECT to_regclass('schema_migrations') IS NOT NULL AS autodata_ledger_exists \gset
\if :autodata_ledger_exists
DO $driver_shape$
DECLARE ledger oid := 'schema_migrations'::regclass;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_class WHERE oid=ledger AND relkind='r')
       OR (SELECT count(*) FROM pg_attribute WHERE attrelid=ledger AND attnum>0 AND NOT attisdropped) <> 2
       OR NOT EXISTS (SELECT FROM pg_attribute WHERE attrelid=ledger AND attname='version' AND atttypid='text'::regtype AND attnotnull)
       OR NOT EXISTS (SELECT FROM pg_attribute WHERE attrelid=ledger AND attname='applied_at' AND atttypid='timestamptz'::regtype AND attnotnull AND atthasdef)
       OR NOT EXISTS (SELECT FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attname='version' WHERE c.conrelid=ledger AND c.contype='p' AND c.conkey=ARRAY[a.attnum])
    THEN RAISE EXCEPTION 'invalid schema_migrations ledger shape'; END IF;
END
$driver_shape$;
SELECT NOT EXISTS(SELECT FROM schema_migrations) AS autodata_ledger_empty \gset
\if :autodata_ledger_empty
SQL
emit_known_tables_check
cat <<'SQL'
\endif
DO $driver_ledger$
BEGIN
    IF EXISTS (
        WITH expected(version, ordinal) AS (VALUES
SQL
ordinal=0
separator=''
for path in "$migrations_dir"/*.sql; do
    name=${path##*/}; ordinal=$((ordinal + 1))
    printf "%s('%s', %s)" "$separator" "${name%.sql}" "$ordinal"
    separator=',
'
done
cat <<'SQL'
        )
        SELECT FROM schema_migrations s LEFT JOIN expected e USING(version)
        WHERE e.version IS NULL
        UNION ALL
        SELECT FROM expected e WHERE e.ordinal <= (
            SELECT max(x.ordinal) FROM schema_migrations s JOIN expected x USING(version)
        ) AND e.ordinal <> 33 AND NOT EXISTS (
            SELECT FROM schema_migrations s WHERE s.version=e.version
        )
    ) THEN RAISE EXCEPTION 'unknown migration version or unexpected ledger gap'; END IF;
END
$driver_ledger$;
\else
SQL
emit_known_tables_check
cat <<'SQL'
\endif
SQL
for path in "$migrations_dir"/*.sql; do
    name=${path##*/}; version=${name%.sql}
    # Only001 can precede creation of the ledger. Never execute a query against
    # the ledger before001 has created it.
    if [ "$name" = '001_extensions.sql' ]; then
        printf '%s\n' '\if :autodata_ledger_exists'
    fi
    printf '%s\n' "SELECT EXISTS(SELECT FROM schema_migrations WHERE version='$version') AS autodata_skip \gset"
    if [ "$name" = '001_extensions.sql' ]; then
        printf '%s\n' '\else' '\set autodata_skip false' '\endif'
    fi
    printf '%s\n' '\if :autodata_skip' "\echo AUTODATA_SKIPPED $name" '\else'
    case "$name" in 036_*|037_*|038_*|039_*|040_*) ;; *) printf '%s\n' 'BEGIN;' ;; esac
    cat "$path"
    printf '\n'
    case "$name" in
        036_*|037_*|038_*|039_*|040_*) ;;
        *) printf '%s\n' "INSERT INTO schema_migrations(version) VALUES ('$version') ON CONFLICT(version) DO NOTHING;" ;;
    esac
    printf '%s\n' "DO \$driver_check\$ BEGIN IF NOT EXISTS (SELECT FROM schema_migrations WHERE version='$version') THEN RAISE EXCEPTION 'expected migration marker missing: $version'; END IF; END \$driver_check\$;"
    case "$name" in 036_*|037_*|038_*|039_*|040_*) ;; *) printf '%s\n' 'COMMIT;' ;; esac
    printf '%s\n' "\echo AUTODATA_APPLIED $name" '\endif'
done
printf '%s\n' 'SELECT pg_advisory_unlock(186,3738);'

}
if [ "$emit" -eq 1 ]; then
    emit_driver
else
    driver_file=$(mktemp "${TMPDIR:-/tmp}/autodata-migrate.XXXXXXXX")
    trap 'rm -f "$driver_file"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    emit_driver > "$driver_file"
    psql -X --set ON_ERROR_STOP=1 --file "$driver_file"
fi
