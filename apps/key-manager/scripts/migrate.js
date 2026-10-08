import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const migrationsDirectory = fileURLToPath(new URL("../db/", import.meta.url));
const connectionString = process.env.MIGRATION_DATABASE_URL || process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;

export async function applyMigrations(client, directory = migrationsDirectory) {
  await client.query(`
    CREATE TABLE IF NOT EXISTS api_key_schema_migrations (
      version text PRIMARY KEY,
      applied_at timestamptz NOT NULL DEFAULT now()
    )`);

  const files = (await readdir(directory))
    .filter((name) => /^\d{3}_[a-z0-9_]+\.sql$/.test(name))
    .sort();

  for (const file of files) {
    const version = file.slice(0, 3);
    const { rowCount } = await client.query(
      "SELECT 1 FROM api_key_schema_migrations WHERE version = $1",
      [version],
    );
    if (rowCount) continue;

    const sql = await readFile(join(directory, file), "utf8");
    await client.query("BEGIN");
    try {
      await client.query(sql);
      await client.query("INSERT INTO api_key_schema_migrations (version) VALUES ($1)", [version]);
      await client.query("COMMIT");
      console.log(`Applied API key database migration ${file}.`);
    } catch (error) {
      await client.query("ROLLBACK").catch(() => undefined);
      throw error;
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (!connectionString) {
    console.error("Database migration requires MIGRATION_DATABASE_URL, DATABASE_URL_UNPOOLED, or DATABASE_URL.");
    process.exit(1);
  }
  const client = new pg.Client({ connectionString, connectionTimeoutMillis: 5000 });
  try {
    await client.connect();
    await applyMigrations(client);
    console.log("API key database migrations are current.");
  } catch {
    console.error("API key database migration failed and was rolled back; inspect the database schema and retry after repair.");
    process.exitCode = 1;
  } finally {
    await client.end().catch(() => undefined);
  }
}
