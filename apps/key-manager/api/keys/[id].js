import { db, requireSameOrigin, respondError, sendMethodNotAllowed, withTransaction } from "../_shared.js";

const actor = "vercel-authenticated-session";
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "DELETE") return sendMethodNotAllowed(res, ["DELETE"]);
  try { requireSameOrigin(req); } catch { return res.status(403).json({ error: { code: "CSRF_REJECTED", message: "Request origin was rejected." } }); }
  const id = req.query?.id;
  if (typeof id !== "string" || !uuidPattern.test(id)) return res.status(400).json({ error: { code: "INVALID_REQUEST", message: "Invalid key id." } });
  try {
    const client = await db().connect();
    try {
      const result = await withTransaction(client, async () => {
        const updated = await client.query(`UPDATE managed_api_keys SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL RETURNING id, service, label, key_prefix, created_at, expires_at, revoked_at, last_used_at`, [id]);
        if (updated.rowCount) {
          await client.query(`INSERT INTO managed_api_key_audit (key_id, service, action, actor) VALUES ($1, $2, 'revoked', $3)`, [updated.rows[0].id, updated.rows[0].service, actor]);
          return updated.rows[0];
        }
        const existing = await client.query(`SELECT id, service, label, key_prefix, created_at, expires_at, revoked_at, last_used_at FROM managed_api_keys WHERE id = $1`, [id]);
        return existing.rows[0];
      });
      if (!result) return res.status(404).json({ error: { code: "NOT_FOUND", message: "Key not found." } });
      return res.status(200).json({ key: result });
    } finally {
      client.release();
    }
  } catch (error) {
    return respondError(res, error);
  }
}
