# Required reviewed immutable PG17 base, supplied by the protected publisher.
# No default/tag fallback and no downloads or source checkout on the VM.
ARG POSTGRES_IMAGE
FROM ${POSTGRES_IMAGE}
ARG POSTGRES_IMAGE
RUN printf '%s\n' "$POSTGRES_IMAGE" | grep -Eq '^([a-z0-9.-]+(:[0-9]+)?/)?[a-z0-9._/-]+@sha256:[0-9a-f]{64}$' \
    && psql --version | grep -Eq '^psql \(PostgreSQL\) 17\.'
COPY scripts/dev/migrate_sql.sh /release/scripts/dev/migrate_sql.sh
COPY db/migrations/*.sql /release/db/migrations/
COPY --chmod=0555 infra/deploy/gce/runtime-entrypoint.sh /usr/local/bin/autodata-runtime-entrypoint
USER 1000:1000
ENTRYPOINT ["/usr/local/bin/autodata-runtime-entrypoint"]
CMD ["sh", "/release/scripts/dev/migrate_sql.sh", "--migrations-dir", "/release/db/migrations"]
