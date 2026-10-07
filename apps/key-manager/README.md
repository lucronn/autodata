# AutoData API key manager

This standalone Vercel app manages keys for Bankone and Banktwo. It uses the
shared key-store schema in `db/001_api_keys.sql`; it is not part of either
public API deployment.

## Local checks

```sh
npm install
npm test
```

Apply the SQL migration once to a dedicated PostgreSQL database as its owner:

```sh
npm run db:migrate
```

The script prefers `MIGRATION_DATABASE_URL`, then `DATABASE_URL_UNPOOLED`, then
`DATABASE_URL`.

Create separate login roles for the manager, Bankone, and Banktwo, then grant
each login membership in `api_key_manager`, `bankone_key_runtime`, or
`banktwo_key_runtime` respectively. The runtime roles are restricted by
row-level security to their own service. The manager login can manage keys but
cannot change the append-only audit rows.

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
