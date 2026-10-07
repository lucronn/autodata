import { randomBytes } from "node:crypto";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import pg from "pg";

const baseUrl = process.env.DATABASE_URL;
const migrationUrl = process.env.DATABASE_URL_UNPOOLED || baseUrl;
if (!baseUrl || !migrationUrl) throw new Error("Neon database URLs are not configured in this environment.");

const projects = [
  { role: "api_key_manager_login", group: "api_key_manager", env: "API_KEYS_MANAGER_DATABASE_URL", service: "manager", projectId: "prj_sCYgKp8AyaSNZUQjKxhVxAcPig3Z" },
  { role: "bankone_key_login", group: "bankone_key_runtime", env: "API_KEYS_DATABASE_URL", service: "bankone", projectId: "prj_kA9iKMsEYxA3nnOA6UMN6zuFNnyK" },
  { role: "banktwo_key_login", group: "banktwo_key_runtime", env: "API_KEYS_DATABASE_URL", service: "banktwo", projectId: "prj_Gcm46f7DqS30uZCz3MAoNhKettsY" },
];
const client = new pg.Client({ connectionString: migrationUrl, connectionTimeoutMillis: 5000 });

try {
  await client.connect();
  for (const target of projects) {
    const { role, group, env, service, projectId } = target;
    const { rows } = await client.query("SELECT rolcanlogin FROM pg_roles WHERE rolname = $1", [role]);
    if (rows.length) throw new Error(`Runtime role ${role} already exists; refusing to rotate credentials automatically.`);
    const password = randomBytes(32).toString("base64url");
    const ddl = await client.query("SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', $1::text, $2::text) AS statement", [role, password]);
    await client.query(ddl.rows[0].statement);
    await client.query(`GRANT ${group} TO ${role}`);

    const runtimeUrl = new URL(baseUrl);
    runtimeUrl.username = role;
    runtimeUrl.password = password;
    const tempDir = mkdtempSync(join(tmpdir(), "autodata-key-env-"));
    const requestPath = join(tempDir, "request.json");
    try {
      writeFileSync(requestPath, JSON.stringify({ key: env, value: runtimeUrl.toString(), type: "sensitive", target: ["preview"] }), { mode: 0o600 });
      const result = spawnSync("vercel", ["api", `/v10/projects/${projectId}/env`, "-X", "POST", "--input", requestPath, "--scope", "curtt"], { encoding: "utf8" });
      let response;
      try { response = JSON.parse(result.stdout); } catch { response = null; }
      if (result.status !== 0 || !response?.created || response.failed?.length) {
        await client.query(`DROP ROLE ${role}`);
        throw new Error(`Could not configure the ${service} preview database secret.`);
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
    console.log(`${service} preview database role and secret configured.`);
  }
} finally {
  await client.end().catch(() => undefined);
}
