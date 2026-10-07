import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import pg from "pg";

const connectionString = process.env.MIGRATION_DATABASE_URL || process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;
if (!connectionString) {
  console.error("Database migration requires MIGRATION_DATABASE_URL, DATABASE_URL_UNPOOLED, or DATABASE_URL.");
  process.exit(1);
}

const migrationPath = new URL("../db/001_api_keys.sql", import.meta.url);
const migration = await readFile(fileURLToPath(migrationPath), "utf8");
const client = new pg.Client({ connectionString, connectionTimeoutMillis: 5000 });
try {
  await client.connect();
  await client.query(migration);
  console.log("API key schema migration applied.");
} catch {
  console.error("API key schema migration failed; inspect the database permissions and migration state.");
  process.exitCode = 1;
} finally {
  await client.end().catch(() => undefined);
}
