import { db, createSecret, requireSameOrigin, respondError, sendMethodNotAllowed, withTransaction } from "./_shared.js";

const services = new Set(["bankone", "banktwo"]);
const actor = "vercel-authenticated-session";

function validateCreate(body) {
  if (!body || !services.has(body.service)) throw Object.assign(new Error(), { status: 400, code: "INVALID_REQUEST", message: "Choose Bankone or Banktwo." });
  const label = typeof body.label === "string" ? body.label.trim() : "";
  if (!label || label.length > 100 || /[\u0000-\u001f]/.test(label)) throw Object.assign(new Error(), { status: 400, code: "INVALID_REQUEST", message: "Enter a label up to 100 characters." });
  let expiresAt = null;
  if (body.expiresAt) {
    expiresAt = new Date(body.expiresAt);
    if (!Number.isFinite(expiresAt.getTime()) || expiresAt.getTime() <= Date.now()) throw Object.assign(new Error(), { status: 400, code: "INVALID_REQUEST", message: "Expiry must be a future date." });
  }
  return { service: body.service, label, expiresAt };
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Vary", "Cookie");
  if (req.method !== "GET" && req.method !== "POST") return sendMethodNotAllowed(res, ["GET", "POST"]);
  try {
    if (req.method === "POST") requireSameOrigin(req);
    const pool = db();
    if (req.method === "GET") {
      const result = await pool.query(`
        SELECT id, service, label, key_prefix, created_at, expires_at, revoked_at, last_used_at
        FROM managed_api_keys ORDER BY created_at DESC LIMIT 500`);
      return res.status(200).json({ keys: result.rows });
    }

    const input = validateCreate(req.body);
    const secret = createSecret(input.service);
    const client = await pool.connect();
    try {
      const row = await withTransaction(client, async () => {
        const inserted = await client.query(`
          INSERT INTO managed_api_keys (service, label, key_digest, key_prefix, expires_at)
          VALUES ($1, $2, $3, $4, $5)
          RETURNING id, service, label, key_prefix, created_at, expires_at, revoked_at, last_used_at`,
          [input.service, input.label, secret.digest, secret.prefix, input.expiresAt]);
        await client.query(`INSERT INTO managed_api_key_audit (key_id, service, action, actor) VALUES ($1, $2, 'created', $3)`, [inserted.rows[0].id, input.service, actor]);
        return inserted.rows[0];
      });
      return res.status(201).json({ key: row, secret: secret.token });
    } finally {
      client.release();
    }
  } catch (error) {
    if (error?.status === 400) return res.status(400).json({ error: { code: "INVALID_REQUEST", message: error.message } });
    if (error?.status === 403) return res.status(403).json({ error: { code: "CSRF_REJECTED", message: error.message } });
    return respondError(res, error);
  }
}
