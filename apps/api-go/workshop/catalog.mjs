// Pure catalog helpers are shared by the browser and the regression suite.
export function configurationLabel(item) {
  return [item.engine, item.trim].filter(Boolean).join(' / ') || 'Base configuration';
}

export function filterArticles(items, query) {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return items.filter(item => {
    const text = `${item.title || ''} ${item.component || ''} ${item.kind || ''}`.toLocaleLowerCase();
    return words.every(word => text.includes(word));
  });
}

function normalizedArticleText(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function legacyParts(text) {
  const parts = [];
  const value = normalizedArticleText(text);
  const marker = /(?:^|\s)(NOTE|HINT|CAUTION|WARNING|IMPORTANT)\s*:\s*/gi;
  let cursor = 0;
  for (const match of value.matchAll(marker)) {
    const index = match.index + (match[0].startsWith(' ') ? 1 : 0);
    const before = value.slice(cursor, index).trim();
    if (before) parts.push({ type: 'text', text: before });
    parts.push({ type: 'callout', label: match[1].toUpperCase(), text: '' });
    cursor = match.index + match[0].length;
  }
  const remainder = value.slice(cursor).trim();
  if (remainder) {
    const last = parts.at(-1);
    if (last?.type === 'callout' && !last.text) last.text = remainder;
    else parts.push({ type: 'text', text: remainder });
  }
  return parts.length ? parts : [{ type: 'text', text: value }];
}

function legacyLeadBlocks(text) {
  const value = normalizedArticleText(text);
  if (!value) return [];
  const blocks = [];
  // Source extracts commonly put section headings directly before prose.
  // Split only all-caps phrases followed by a normal sentence; the remaining
  // text stays in exactly the same order and remains source text.
  const sectionPattern = /(?:^|\s)((?:[A-Z][A-Z0-9/&'().-]*\s+){1,}[A-Z][A-Z0-9/&'().-]*)(?=\s+[A-Z][a-z])/g;
  const headings = [...value.matchAll(sectionPattern)];
  if (!headings.length && /^[A-Z][A-Z0-9/&'(). -]+$/.test(value)) {
    blocks.push({ type: 'heading', text: value });
    return blocks;
  }
  let cursor = 0;
  for (const match of headings) {
    const before = value.slice(cursor, match.index).trim();
    if (before) {
      for (const part of legacyParts(before)) blocks.push(part.type === 'text'
        ? { type: 'paragraph', text: part.text }
        : part);
    }
    blocks.push({ type: 'heading', text: match[1].trim() });
    cursor = match.index + match[0].length;
  }
  const remainder = value.slice(cursor).trim();
  if (remainder) {
    for (const part of legacyParts(remainder)) blocks.push(part.type === 'text'
      ? { type: 'paragraph', text: part.text }
      : part);
  }
  return blocks;
}

export function legacyArticleBlocks(body) {
  const value = normalizedArticleText(body);
  if (!value) return [];
  // Numbered steps are frequently flattened by the source extractor
  // (`1.Remove...2.Install...`). A number followed by an uppercase word is a
  // safe boundary here: decimals and dates do not match it, and embedded
  // identifiers such as DLC1. do not have a word boundary before the digit.
  const matches = [...value.matchAll(/\b(\d{1,2})\.\s*(?=[A-Z])/g)];
  if (!matches.length) return legacyLeadBlocks(value);
  const blocks = legacyLeadBlocks(value.slice(0, matches[0].index));
  for (const [index, match] of matches.entries()) {
    const start = match.index + match[0].length;
    const end = matches[index + 1]?.index ?? value.length;
    const text = value.slice(start, end).trim();
    blocks.push({ type: 'step', number: Number(match[1]), parts: legacyParts(text) });
  }
  return blocks;
}

export function articlePresentation(article) {
  const steps = Array.isArray(article.steps) ? article.steps : [];
  // A partly empty legacy sequence must not silently discard its missing text.
  const usable = steps.length > 0 && steps.every(step =>
    step.heading?.trim() || step.instructions?.some(text => typeof text === 'string' && text.trim()));
  const body = String(article.body || '');
  return {
    steps: usable ? steps : [],
    body,
    blocks: usable ? [] : legacyArticleBlocks(body),
    legacy: steps.length > 0 && !usable,
  };
}

export function localImageURL(value, origin) {
  if (typeof value !== 'string') return null;
  if (/^data:image\/(png|jpeg|webp|gif);base64,[a-z\d+/=\s]+$/i.test(value)) return value;
  try {
    const url = new URL(value, origin);
    return ['http:', 'https:'].includes(url.protocol) && url.origin === origin ? url.href : null;
  } catch { return null; }
}

export function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted();
    const finish = () => { signal?.removeEventListener('abort', abort); resolve(); };
    const timer = setTimeout(finish, ms);
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export async function readCollection(read, { signal, onUpdate = () => {}, desired = '', attempts = 40, interval = 1500, wait = delay } = {}) {
  let latest;
  for (let attempt = 0; attempt < attempts; attempt++) {
    signal?.throwIfAborted();
    latest = await read();
    signal?.throwIfAborted();
    if (!Array.isArray(latest.items)) throw new Error('The catalog returned an unreadable list. Try again.');
    onUpdate(latest, { attempt: attempt + 1, attempts });
    // A saved selection can resume using an existing row while ingestion continues.
    if (desired && latest.items.some(item => String(item.id ?? item.year) === desired)) return latest;
    if (!latest.hydrating || latest.complete === true) return latest;
    if (attempt < attempts - 1) await wait(interval, signal);
  }
  return { ...latest, timedOut: true };
}

export async function requestJSON(path, { signal, token, timeout = 120000, fetcher = fetch } = {}) {
  const timeoutSignal = AbortSignal.timeout(timeout);
  const combined = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
  try {
    const response = await fetcher(path, {
      signal: combined,
      headers: { Accept: 'application/json', ...(token ? { Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}` } : {}) },
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) throw new Error('Your session cannot access this catalog. Check your AutoData access and try again.');
      if (response.status === 404) throw new Error('This article or vehicle could not be found. Return to the index and choose it again.');
      throw new Error(data?.error?.message || data?.message || `The catalog could not be loaded (HTTP ${response.status}). Try again.`);
    }
    if (!data || typeof data !== 'object') throw new Error('The catalog returned an unreadable response. Try again.');
    return data;
  } catch (error) {
    if (signal?.aborted) throw signal.reason;
    if (timeoutSignal.aborted) throw new Error('This is taking longer than expected. You can retry or choose another vehicle.');
    if (error instanceof TypeError) throw new Error('Cannot reach AutoData. Check the server connection and try again.');
    throw error;
  }
}
