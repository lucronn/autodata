# AutoData API key manager

This standalone Vercel app manages keys for Bankone and Banktwo. It uses the
shared key-store schema in `db/001_api_keys.sql`; it is not part of either
public API deployment.

## Local checks

```sh
npm install
npm test
```

To run the migration integration tests against PostgreSQL, set
`API_KEYS_TEST_DATABASE_URL`; without it, those tests are skipped.

Apply the numbered SQL migrations to a dedicated PostgreSQL database as its owner:

```sh
npm run db:migrate
```

The runner records each committed version in `api_key_schema_migrations` and
applies every migration in its own transaction. A failed migration rolls back
and stays unrecorded, so it can be safely retried after repair. Never edit an
already-recorded migration; add a forward migration. Migration `002` stops if
it finds audit rows whose service does not match the referenced key; repair
those rows under database-owner control, then rerun the migration. No migration
in this set deletes key or audit data.

Create separate login roles for the manager, Bankone, and Banktwo, then grant
each login membership in `api_key_manager`, `bankone_key_runtime`, or
`banktwo_key_runtime` respectively. The runtime roles are restricted by
row-level security to their own service. The manager login can manage keys but
cannot change the append-only audit rows.

The application roles cannot update or delete audit rows. Database-owner
operators can override database triggers, so owner-level recovery remains a
break-glass operation. Audit events use the fixed actor label
`vercel-authenticated-session`; Vercel's deployment gate does not expose the
individual user identity to these functions.

## Deployment requirements

Set this folder as the Vercel project's root directory and provide
`API_KEYS_MANAGER_DATABASE_URL` as a pooled TLS connection string for the
`api_key_manager` login. Enable
Vercel Authentication with Standard Deployment Protection. Do not attach a
production domain or public production alias; administrators access the
protected deployment URL. Restrict project membership to trusted key
administrators. Never place a database connection string or API key in the
static `public/` files.

The API functions return sanitized errors and disable response caching. Each
new key's plaintext is returned only in its create response; list responses
contain metadata only.
