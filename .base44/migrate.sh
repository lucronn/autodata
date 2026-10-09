#!/bin/sh
# Base44 sandbox migration runner.
#
# The repository applies its forward-only migrations with a plain psql loop,
# which is not re-runnable. The preview stack may be brought up more than once
# (or recreated after a code/secret change), so this wrapper records applied
# files in a sandbox-local bookkeeping table and skips what is already there.
# It changes no migration file and no schema owned by the application.
set -eu

psql -v ON_ERROR_STOP=1 -q -c "
  CREATE TABLE IF NOT EXISTS base44_schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
  )" >/dev/null

for migration in /workspace/db/migrations/[0-9][0-9][0-9]_*.sql; do
  name=$(basename "$migration")
  applied=$(psql -tAq -c "SELECT 1 FROM base44_schema_migrations WHERE filename = '$name'")
  if [ "$applied" = "1" ]; then
    echo "skip   $name (already applied)"
    continue
  fi
  echo "apply  $name"
  psql --set ON_ERROR_STOP=1 -q --file "$migration"
  psql -v ON_ERROR_STOP=1 -q -c "INSERT INTO base44_schema_migrations (filename) VALUES ('$name')" >/dev/null
done

echo "migrations complete"
