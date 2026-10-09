#!/bin/sh
# Liveness probe for a PostgreSQL polling process (the outbox relay).
#
# Opens and closes one read-only connection with the same environment the
# process uses, proving the poller can still reach its only dependency. It
# relays nothing and changes no state.
set -eu

python - <<'PY'
import os

import psycopg

host, port = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
connection = psycopg.connect(
    host=host,
    port=int(port),
    dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
    user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
    password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    connect_timeout=3,
)
connection.close()
PY
