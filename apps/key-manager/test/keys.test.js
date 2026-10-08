import test from "node:test";
import assert from "node:assert/strict";
import { createSecret, digestSecret, requireSameOrigin } from "../api/_shared.js";

test("service keys have 256 bits of random secret and a reproducible SHA-256 digest", () => {
  const first = createSecret("bankone");
  const second = createSecret("bankone");
  assert.match(first.token, /^adk_bankone_[A-Za-z0-9_-]{43}$/);
  assert.equal(first.prefix, "adk_bankone_");
  assert.equal(first.digest.length, 32);
  assert.deepEqual(first.digest, digestSecret(first.token));
  assert.notDeepEqual(first.digest, second.digest);
  assert.ok(!first.digest.toString("utf8").includes(first.token));
});

test("dashboard mutation origin check accepts the exact request origin", () => {
  assert.doesNotThrow(() => requireSameOrigin({ headers: { origin: "https://manager.example", host: "manager.example", "x-forwarded-proto": "https" } }));
});

test("dashboard mutation origin check rejects absent and hostile origins", () => {
  assert.throws(() => requireSameOrigin({ headers: { host: "manager.example" } }), { status: 403 });
  assert.throws(() => requireSameOrigin({ headers: { origin: "https://evil.example", host: "manager.example", "x-forwarded-proto": "https" } }), { status: 403 });
});
