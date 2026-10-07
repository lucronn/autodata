import { createHash, randomBytes } from "node:crypto";
import pg from "pg";

const { Pool } = pg;
let pool;

export function db() {
  if (!process.env.API_KEYS_MANAGER_DATABASE_URL) throw Object.assign(new Error("database unavailable"), { status: 503 });
  pool ??= new Pool({
    connectionString: process.env.API_KEYS_MANAGER_DATABASE_URL,
    max: 3,
    allowExitOnIdle: true,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 3_000,
    ssl: process.env.PGSSLMODE === "disable" ? false : { rejectUnauthorized: true },
  });
  return pool;
}

export function createSecret(service) {
  const secret = randomBytes(32).toString("base64url");
  const token = `adk_${service}_${secret}`;
  return { token, prefix: `adk_${service}_`, digest: createHash("sha256").update(token, "utf8").digest() };
}

export function digestSecret(token) {
  return createHash("sha256").update(token, "utf8").digest();
}

export function respondError(res, error) {
  const status = error?.status === 503 ? 503 : 500;
  res.status(status).json({ error: { code: status === 503 ? "KEY_STORE_UNAVAILABLE" : "INTERNAL_ERROR", message: status === 503 ? "Key management is temporarily unavailable." : "Request could not be completed." } });
}

export function sendMethodNotAllowed(res, allowed) {
  res.setHeader("Allow", allowed.join(", "));
  res.status(405).json({ error: { code: "METHOD_NOT_ALLOWED", message: "Method not allowed." } });
}

export function requireSameOrigin(req) {
  const origin = req.headers.origin;
  const forwardedHost = req.headers["x-forwarded-host"];
  const host = Array.isArray(forwardedHost) ? forwardedHost[0] : forwardedHost || req.headers.host;
  const forwardedProto = req.headers["x-forwarded-proto"];
  const proto = Array.isArray(forwardedProto) ? forwardedProto[0] : forwardedProto || "https";
  if (typeof origin !== "string" || !host || origin !== `${proto}://${host}`) {
    throw Object.assign(new Error(), { status: 403, code: "CSRF_REJECTED", message: "Request origin was rejected." });
  }
}

export async function withTransaction(client, callback) {
  await client.query("BEGIN");
  try {
    const result = await callback();
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }
}
