import { requestJSON, delay } from "./catalog.mjs";
export const uuid = (value) =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
    value,
  );
export const validScope = (s) =>
  s && uuid(s.configuration_id) && /^[A-Z]{2}$/.test(s.region);
export const sameScope = (a, b) =>
  validScope(a) &&
  validScope(b) &&
  a.configuration_id === b.configuration_id &&
  a.region === b.region;
export function validQuote(q, scope) {
  return Boolean(
    q?.version === "v1" &&
      sameScope(q, scope) &&
      q.product_key === "workshop-configuration-v1" &&
      typeof q.configuration_label === "string" &&
      q.configuration_label.length > 0 &&
      q.configuration_label.length <= 1024 &&
      q.amount_minor === 2000 &&
      q.currency === "USD" &&
      q.purchase_terms_version === "workshop-v1" &&
      q.purchasable === true,
  );
}
export function hostedCheckoutURL(value) {
  if (
    typeof value !== "string" ||
    /[\s\u0000-\u001f\u007f]/u.test(value) ||
    !value.startsWith("https://checkout.stripe.com/")
  )
    return null;
  try {
    const u = new URL(value);
    return u.protocol === "https:" &&
      u.hostname === "checkout.stripe.com" &&
      !u.port &&
      !u.username &&
      !u.password &&
      /^\/c\/pay\/[^/]+/.test(u.pathname)
      ? value
      : null;
  } catch {
    return null;
  }
}
export function validOrder(o, orderID) {
  return Boolean(
    o?.version === "v1" &&
      o.order_id === orderID &&
      uuid(orderID) &&
      validScope(o) &&
      (["expired", "canceled"].includes(o.state)
        ? o.retry_disposition === "new_key"
        : [
            "creating",
            "open",
            "processing",
            "paid",
            "reconciliation_required",
            "revoked",
          ].includes(o.state) && o.retry_disposition === "do_not_repay"),
  );
}
const validTime = (value) =>
  typeof value === "string" &&
  /(?:Z|\+00:00)$/.test(value) &&
  Number.isFinite(Date.parse(value));
export function validLibrary(data) {
  return Boolean(
    data?.version === "v1" &&
      Array.isArray(data.items) &&
      data.items.length <= 50 &&
      Object.hasOwn(data, "next_cursor") &&
      (data.next_cursor === null ||
        (typeof data.next_cursor === "string" &&
          data.next_cursor.length <= 2048)) &&
      data.items.every(
        (item) =>
          validScope(item) &&
          uuid(item.library_item_id) &&
          typeof item.label === "string" &&
          item.label.length <= 1024 &&
          ["paid", "preparing", "viewable", "revoked"].includes(
            item.access_state,
          ) &&
          (item.granted_at === null
            ? item.access_state === "revoked"
            : validTime(item.granted_at)),
      ),
  );
}
export function purchaseConfiguration(config, quote) {
  const keys = ["terms_url", "privacy_url", "refund_url", "contact_url"];
  return Boolean(
    config?.enabled === true &&
      config.terms_version === "workshop-v1" &&
      config.terms_version === quote?.purchase_terms_version &&
      typeof config.tax_notice === "string" &&
      config.tax_notice.trim() &&
      keys.every((key) => {
        if (
          typeof config[key] !== "string" ||
          /[\s\u0000-\u001f]/.test(config[key])
        )
          return false;
        try {
          const url = new URL(config[key]);
          return url.protocol === "https:" && !url.username && !url.password;
        } catch {
          return false;
        }
      }),
  );
}
const ATTEMPT_KEY = "autodata-checkout-attempt-v1";
export function createCheckout({
  request = requestJSON,
  storage = globalThis.sessionStorage,
  uuid: newUUID = () => crypto.randomUUID(),
} = {}) {
  let inflight = null, inflightScope = null, inflightSignal = null;
  const read = () => {
    try {
      const a = JSON.parse(storage?.getItem(ATTEMPT_KEY) || "null");
      return validScope(a) && uuid(a.key) && (!a.order_id || uuid(a.order_id))
        ? a
        : null;
    } catch {
      return null;
    }
  };
  const clear = () => {
    try {
      storage?.removeItem(ATTEMPT_KEY);
    } catch {}
  };
  const save = (attempt) => {
    try {
      storage?.setItem(ATTEMPT_KEY, JSON.stringify(attempt));
    } catch {}
  };
  const start = (scope, csrf, { signal } = {}) => {
    if (!validScope(scope) || !csrf)
      return Promise.reject(new Error("Purchase is unavailable."));
    if (inflight) {
      if (sameScope(inflightScope, scope) && !inflightSignal?.aborted)
        return inflight;
      // One stored attempt cannot safely represent two concurrent vehicles.
      // Let the old request settle before starting the new scope.
      return inflight.catch(() => {}).then(() => {
        signal?.throwIfAborted();
        return start(scope, csrf, { signal });
      });
    }
    const saved = read();
    const attempt = sameScope(saved, scope)
      ? saved
      : { ...scope, key: newUUID() };
    save(attempt);
    const body = {
      configuration_id: scope.configuration_id,
      region: scope.region,
      terms_version: "workshop-v1",
    };
    const pending = request("/v1/workshop/checkout-sessions", {
      method: "POST",
      signal,
      timeout: 10000,
      body,
      headers: { "X-CSRF-Token": csrf, "Idempotency-Key": attempt.key },
    })
      .then((data) => {
        signal?.throwIfAborted();
        if (
          data?.version !== "v1" ||
          !sameScope(data, scope) ||
          !uuid(data.order_id) ||
          !["checkout", "processing", "owned"].includes(data.state) ||
          (data.state === "checkout" &&
            (!hostedCheckoutURL(data.checkout_url) ||
              !validTime(data.provider_expires_at))) ||
          (data.state !== "checkout" && data.checkout_url) ||
          (data.state === "owned" && data.library_item_id !== data.order_id)
        )
          throw new Error("Purchase status is unavailable.");
        save({ ...attempt, order_id: data.order_id });
        return data;
      })
      .finally(() => {
        if (inflight === pending) {
          inflight = null;
          inflightScope = null;
          inflightSignal = null;
        }
      });
    inflight = pending;
    inflightScope = { ...scope };
    inflightSignal = signal;
    return pending;
  };
  return { read, clear, start };
}
export async function pollOrder(
  orderID,
  {
    request = requestJSON,
    signal,
    onUpdate = () => {},
    wait = delay,
    now = () => performance.now(),
    budgetMs = 120000,
  } = {},
) {
  if (!uuid(orderID)) throw new Error("This order is unavailable.");
  const deadline = now() + Math.min(120000, budgetMs);
  let attempt = 0,
    latest;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0;
    try {
      latest = await request(`/v1/workshop/orders/${orderID}`, {
        signal,
        timeout: Math.min(10000, Math.max(1, deadline - now())),
      });
      signal?.throwIfAborted();
      if (!validOrder(latest, orderID))
        throw new Error("Payment status is unavailable.");
      onUpdate(latest);
      if (["paid", "expired", "canceled", "revoked"].includes(latest.state))
        return { ...latest, timedOut: false };
    } catch (error) {
      signal?.throwIfAborted();
      if (
        !(
          error instanceof TypeError ||
          error.code === "NETWORK_UNAVAILABLE" ||
          ([429, 503].includes(error.status) && error.retryable)
        )
      )
        throw error;
      retryAfter = Number(error.retryAfterSeconds) || 0;
    }
    const remaining = deadline - now();
    if (remaining <= 0) break;
    await wait(
      Math.min(
        remaining,
        Math.max(
          [1000, 2000, 4000, 8000, 10000][Math.min(attempt++, 4)],
          retryAfter * 1000,
        ),
      ),
      signal,
    );
  }
  return { ...latest, timedOut: true };
}
