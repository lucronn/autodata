const lifetimeMs = 5000;
const canonicalQuery = "?view=library";
const browserCachePolicy = "private, max-age=30, must-revalidate, no-transform";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const validators = ["range", "if-range", "if-match", "if-none-match", "if-modified-since", "if-unmodified-since"];

function isSavedEntry(request, url) {
  if (request.method !== "GET" || url.pathname !== "/workshop") return false;
  if (!request.headers.get("accept")?.includes("text/html")) return false;
  if (validators.some(name => request.headers.has(name))) return false;
  const cacheControl = request.headers.get("cache-control") || "";
  if (/(?:^|,)\s*(?:no-cache|no-store|max-age\s*=\s*0)(?:\s*(?:,|$))/.test(cacheControl.toLowerCase()) ||
      request.headers.get("pragma")?.toLowerCase().includes("no-cache")) return false;

  const params = url.searchParams;
  const keys = [...params.keys()].sort().join(",");
  if (keys === "view") return params.get("view") === "library";
  if (keys === "order") return uuid.test(params.get("order"));
  if (!["configuration,region", "article,configuration,region",
    "configuration,demo,region", "article,configuration,demo,region"].includes(keys)) return false;
  return uuid.test(params.get("configuration")) && /^[A-Z]{2}$/.test(params.get("region")) &&
    (!params.has("article") || uuid.test(params.get("article"))) &&
    (!params.has("demo") || params.get("demo") === "1");
}

function savedEntryReader(upstreamOrigin, publicHost, fetchDocument = fetch, regionCache) {
  const canonicalUrl = new URL("/workshop" + canonicalQuery, upstreamOrigin);
  const cacheKey = "workshop-entry-shell-v1:" + canonicalUrl.origin + ":" + publicHost;
  let document;
  let pending;

  function isFresh(entry) {
    const elapsed = Date.now() - entry?.storedAt;
    return elapsed >= 0 && elapsed < lifetimeMs;
  }

  async function readCanonicalDocument() {
    try {
      const response = await fetchDocument(canonicalUrl, {
        headers: {
          "accept": "text/html",
          "accept-encoding": "identity",
          "host": canonicalUrl.host,
          "x-forwarded-host": publicHost,
          "x-forwarded-proto": "https",
        },
        credentials: "omit",
        redirect: "error",
        signal: AbortSignal.timeout(2500),
      });
      const headers = response.headers;
      const tag = headers.get("etag");
      const vary = headers.get("vary");
      if (response.status !== 200 || !headers.get("content-type")?.startsWith("text/html") ||
          headers.has("set-cookie") || headers.get("cache-control") !== browserCachePolicy ||
          (vary && vary.toLowerCase() !== "accept-encoding") ||
          !/^W\/"[a-f0-9]{64}"$/.test(tag) ||
          headers.get("workshop-entry-shell") !== "1") return null;
      const body = await response.text();
      if (body.length > 100000 || !body.includes("<!doctype html>") ||
          !/\/workshop\/assets\/[a-f0-9]{64}\/bootstrap\.mjs/.test(body) ||
          /id="workshop-initial-(years|makes)"/.test(body)) return null;
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body));
      if (tag !== 'W/"' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("") + '"') {
        return null;
      }

      // Recompute transport headers for the decoded representation. A request
      // ID or an upstream edge response header belongs to the original read.
      const stored = new Headers();
      for (const name of [
        "cache-control", "content-type", "vary", "etag", "date", "referrer-policy", "permissions-policy",
        "strict-transport-security", "content-security-policy", "content-security-policy-report-only",
        "cross-origin-resource-policy", "cross-origin-opener-policy", "cross-origin-embedder-policy",
        "x-content-type-options", "x-frame-options", "x-robots-tag",
      ]) {
        const value = headers.get(name);
        if (value !== null) stored.set(name, value);
      }
      return { body, headers: [...stored], storedAt: Date.now() };
    } catch {
      return null;
    }
  }

  async function refresh() {
    let cache;
    try {
      cache = regionCache?.();
      const existing = await cache?.get(cacheKey);
      if (isFresh(existing)) {
        document = existing;
        return true;
      }
    } catch {
      // A cache failure leaves the canonical origin available.
    }
    document = await readCanonicalDocument();
    if (document && cache) {
      try {
        await cache.set(cacheKey, document, { ttl: lifetimeMs / 1000 });
      } catch {
        // The verified document is still available in this instance.
      }
    }
    return false;
  }

  return async (request, url = new URL(request.url)) => {
    if (!isSavedEntry(request, url)) return null;
    let hit = isFresh(document);
    if (!hit) {
      pending ??= refresh().finally(() => { pending = null; });
      hit = await pending;
    }
    if (!isFresh(document)) return null;
    const headers = new Headers(document.headers);
    headers.set("age", Math.floor((Date.now() - document.storedAt) / 1000).toString());
    headers.set("server-timing", "workshop-entry;desc=" + (hit ? "hit" : "fill"));
    headers.append("server-timing", "workshop-demo-detail");
    return new Response(document.body, { headers });
  };
}

export const config = { matcher: "/((?!workshop/assets/[a-f0-9]{64}/|workshop-demo-detail/).*)", runtime: "nodejs" };

import { getCache } from "@vercel/functions";

const UPSTREAM_ORIGIN = "https://autodata.curtis.click";
const PUBLIC_HOST = "autodata.cars.tk";
const PUBLIC_READ_USER_AGENT = "AutoData-Workshop-Proxy/1.0";

// These are the public read routes mounted by the Workshop API.
const PUBLIC_READ_PATHS = [
  /^\/openapi\.(?:json|yaml)$/,
  /^\/v1\/workshop\/quote$/,
  /^\/v1\/catalog\/years$/,
  /^\/v1\/catalog\/years\/[^/]+\/makes$/,
  /^\/v1\/catalog\/years\/[^/]+\/makes\/[^/]+\/models$/,
  /^\/v1\/catalog\/years\/[^/]+\/makes\/[^/]+\/models\/[^/]+\/configurations$/,
];

const readSavedEntry = savedEntryReader(UPSTREAM_ORIGIN, PUBLIC_HOST, fetch, getCache);

export default async function middleware(request) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const isPublicRead = ["GET", "HEAD", "OPTIONS"].includes(request.method) &&
    PUBLIC_READ_PATHS.some((pattern) => pattern.test(path));
  if (url.pathname.length > 1 && url.pathname.endsWith("/")) {
    url.pathname = path;
    if (!isPublicRead) {
      return Response.redirect(url, 308);
    }
  }

  const savedEntry = await readSavedEntry(request, url);
  if (savedEntry) return savedEntry;

  let upstream = new URL(UPSTREAM_ORIGIN);
  upstream.pathname = url.pathname;
  upstream.search = url.search;

  const headers = new Headers(request.headers);
  headers.set("host", new URL(UPSTREAM_ORIGIN).host);
  headers.set("x-forwarded-host", PUBLIC_HOST);
  headers.set("x-forwarded-proto", "https");
  if (isPublicRead) {
    // Identify this service for public API reads on the upstream connection.
    headers.set("user-agent", PUBLIC_READ_USER_AGENT);
  }

  const init = { method: request.method, headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  // Follow redirects within the upstream origin, including the Workshop UI's
  // canonical /workshop/ path.
  let response = await fetch(upstream, init);
  for (let i = 0; i < 5; i++) {
    if (![301, 302, 303, 307, 308].includes(response.status)) break;
    const location = response.headers.get("location");
    if (!location) break;
    const next = new URL(location, upstream);
    if (next.origin !== upstream.origin) break;
    upstream = next;
    response = await fetch(upstream, init);
  }

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  if (path === "/workshop" && request.method === "GET") {
    responseHeaders.append("server-timing", "workshop-demo-detail");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}
