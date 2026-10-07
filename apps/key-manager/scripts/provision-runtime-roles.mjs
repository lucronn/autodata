import { randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import pg from "pg";

const baseUrl = process.env.DATABASE_URL;
const migrationUrl = process.env.DATABASE_URL_UNPOOLED || baseUrl;
if (!baseUrl || !migrationUrl) throw new Error("Neon database URLs are not configured in this environment.");

const projects = [
  { role: "api_key_manager_login", group: "api_key_manager", env: "API_KEYS_MANAGER_DATABASE_URL", service: "manager", cwd: "/Users/dull/Documents/ChatGPT/autodata-api-key-mgmt/apps/key-manager" },
  { role: "bankone_key_login", group: "bankone_key_runtime", env: "API_KEYS_DATABASE_URL", service: "bankone", cwd: "/Users/dull/Documents/ChatGPT/bankone-api-key-management" },
  { role: "banktwo_key_login", group: "banktwo_key_runtime", env: "API_KEYS_DATABASE_URL", service: "banktwo", cwd: "/tmp/banktwo-api-key-work" },
];
const client = new pg.Client({ connectionString: migrationUrl, connectionTimeoutMillis: 5000 });

try {
  await client.connect();
  for (const target of projects) {
    const { role, group, env, service } = target;
    const { rows } = await client.query("SELECT rolcanlogin FROM pg_roles WHERE rolname = $1", [role]);
    if (rows.length) throw new Error(`Runtime role ${role} already exists; refusing to rotate credentials automatically.`);
    const password = randomBytes(32).toString("base64url");
    const ddl = await client.query("SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', $1::text, $2::text) AS statement", [role, password]);
    await client.query(ddl.rows[0].statement);
    await client.query(`GRANT ${group} TO ${role}`);

    const runtimeUrl = new URL(baseUrl);
    runtimeUrl.username = role;
    runtimeUrl.password = password;
    const result = spawnSync("vercel", ["env", "add", env, "preview", "phobos/api-key-management", "--force", "--sensitive", "--yes", "--scope", "curtt"], {
      cwd: target.cwd,
      input: `${runtimeUrl.toString()}\n`,
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    if (result.status !== 0) {
      await client.query(`DROP ROLE ${role}`);
      throw new Error(`Could not configure the ${service} preview database secret.`);
    }
    console.log(`${service} preview database role and secret configured.`);
  }
} finally {
  await client.end().catch(() => undefined);
}
