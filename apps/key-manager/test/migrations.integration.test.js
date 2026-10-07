import { randomBytes, randomUUID } from "node:crypto";
import { test } from "node:test";
import assert from "node:assert/strict";
import pg from "pg";
import { applyMigrations } from "../scripts/migrate.js";

const connectionString = process.env.API_KEYS_TEST_DATABASE_URL;

async function withSchema(callback) {
  const client = new pg.Client({ connectionString });
  const schema = `api_key_test_${randomUUID().replaceAll("-", "")}`;
  await client.connect();
  await client.query(`CREATE SCHEMA "${schema}"`);
  await client.query(`SET search_path TO "${schema}", public`);
  try {
    await callback(client);
  } finally {
    await client.query(`DROP SCHEMA "${schema}" CASCADE`);
    await client.end();
  }
}

test("clean install is versioned, repeatable, service-scoped, and immutable", { skip: !connectionString }, async () => {
  await withSchema(async (client) => {
    await applyMigrations(client);
    await applyMigrations(client);
    const versions = await client.query("SELECT version FROM api_key_schema_migrations ORDER BY version");
    assert.deepEqual(versions.rows.map((row) => row.version), ["001", "002"]);

    const id = randomUUID();
    const digest = randomBytes(32);
    await client.query(
      "INSERT INTO managed_api_keys (id, service, label, key_digest, key_prefix) VALUES ($1, 'bankone', 'fixture', $2, 'adk_bankone_')",
      [id, digest],
    );
    await assert.rejects(
      client.query("INSERT INTO managed_api_key_audit (key_id, service, action, actor) VALUES ($1, 'banktwo', 'created', 'test')", [id]),
      (error) => error.code === "23503",
    );
    await client.query("INSERT INTO managed_api_key_audit (key_id, service, action, actor) VALUES ($1, 'bankone', 'created', 'test')", [id]);
    await client.query("UPDATE managed_api_keys SET revoked_at = now() WHERE id = $1", [id]);
    await assert.rejects(
      client.query("UPDATE managed_api_keys SET revoked_at = NULL WHERE id = $1", [id]),
      /API key revocation is permanent/,
    );
    await assert.rejects(
      client.query("UPDATE managed_api_keys SET key_digest = $2 WHERE id = $1", [id, randomBytes(32)]),
      /API key identity fields are immutable/,
    );
    await assert.rejects(
      client.query("DELETE FROM managed_api_key_audit WHERE key_id = $1", [id]),
      /API key audit records are append-only/,
    );
  });
});

test("an incompatible legacy audit row blocks only the forward migration and can be repaired", { skip: !connectionString }, async () => {
  await withSchema(async (client) => {
    await client.query(`
      CREATE TABLE managed_api_keys (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(), service text NOT NULL CHECK (service IN ('bankone', 'banktwo')),
        label text NOT NULL, key_digest bytea NOT NULL UNIQUE, key_prefix text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz, revoked_at timestamptz, last_used_at timestamptz
      );
      CREATE TABLE managed_api_key_audit (
        id bigserial PRIMARY KEY, key_id uuid NOT NULL REFERENCES managed_api_keys(id) ON DELETE RESTRICT,
        service text NOT NULL CHECK (service IN ('bankone', 'banktwo')), action text NOT NULL,
        actor text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(), details jsonb NOT NULL DEFAULT '{}'::jsonb
      )`);
    const id = randomUUID();
    await client.query("INSERT INTO managed_api_keys (id, service, label, key_digest, key_prefix) VALUES ($1, 'bankone', 'fixture', $2, 'adk_bankone_')", [id, randomBytes(32)]);
    await client.query("INSERT INTO managed_api_key_audit (key_id, service, action, actor) VALUES ($1, 'banktwo', 'created', 'legacy')", [id]);

    await assert.rejects(applyMigrations(client), /mismatched service values/);
    const versionAfterFailure = await client.query("SELECT version FROM api_key_schema_migrations ORDER BY version");
    assert.deepEqual(versionAfterFailure.rows.map((row) => row.version), ["001"]);

    await client.query("UPDATE managed_api_key_audit SET service = 'bankone' WHERE key_id = $1", [id]);
    await applyMigrations(client);
    const versions = await client.query("SELECT version FROM api_key_schema_migrations ORDER BY version");
    assert.deepEqual(versions.rows.map((row) => row.version), ["001", "002"]);
  });
});
