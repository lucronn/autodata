// Pure catalog helpers are shared by the browser and the regression suite.
export function configurationLabel(item) {
  const displacement = typeof item.engine === 'string' && /^\d+(?:\.\d+)?$/.test(item.engine);
  const engine = displacement ? `${item.engine} L` : item.engine;
  return [engine, item.trim, item.body_style, item.drivetrain].filter(Boolean).join(' / ') || 'Base configuration';
}

export function filterArticles(items, query) {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return items.filter(item => {
    const text = `${item.title || ''} ${item.component || ''} ${item.kind || ''}`.toLocaleLowerCase();
    return words.every(word => text.includes(word));
  });
}

export function sourceReferenceURL(sourceReview, block) {
  if (!sourceReview?.url || (!Array.isArray(block?.evidence_ids) && !String(block?.source_locator || '').trim())) return null;
  try {
    const origin = globalThis.location?.origin || 'http://localhost';
    const url = new URL(sourceReview.url, origin);
    if (url.origin !== origin) return null;
    const evidenceID = Array.isArray(block.evidence_ids) ? String(block.evidence_ids.find(Boolean) || '') : '';
    const locator = String(block.source_locator || '').trim();
    if (evidenceID) url.searchParams.set('evidence_id', evidenceID);
    if (locator) url.searchParams.set('source_locator', locator);
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

export function hasSourceReference(block) {
  return Boolean(Array.isArray(block?.evidence_ids) && block.evidence_ids.some(Boolean)) || Boolean(String(block?.source_locator || '').trim());
}

function normalizedArticleText(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
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

function readableParagraphs(text) {
  const value = String(text || '').trim();
  if (!value) return [];
  const sentences = value.split(/(?<=[.!?])\s+(?=[A-Z])/).filter(Boolean);
  if (sentences.length < 4) return [value];
  const paragraphs = [];
  let current = [];
  for (const sentence of sentences) {
    current.push(sentence.trim());
    if (current.length >= 3 || current.join(' ').length >= 520) {
      paragraphs.push(current.join(' '));
      current = [];
    }
  }
  if (current.length) paragraphs.push(current.join(' '));
  return paragraphs;
}

function appendLegacyPart(blocks, part) {
  if (part.type === 'text') {
    for (const paragraph of readableParagraphs(part.text)) blocks.push({ type: 'paragraph', text: paragraph });
  } else blocks.push(part);
}

function legacyLeadBlocks(text) {
  const value = normalizedArticleText(text);
  if (!value) return [];
  const blocks = [];
  // Source extracts commonly put section headings directly before prose.
  // Split only all-caps phrases followed by a normal sentence; the remaining
  // text stays in exactly the same order and remains source text.
  if (value.includes('\n')) {
    for (const paragraph of value.split(/\n{2,}/).map(part => part.trim()).filter(Boolean)) {
      for (const line of paragraph.split(/\n+/).map(part => part.trim()).filter(Boolean)) {
        if (/^[A-Z][A-Z0-9/&'().,\- ]{2,119}$/.test(line) && /[A-Z]/.test(line)) {
          blocks.push({ type: 'heading', text: line });
          continue;
        }
        for (const part of legacyParts(line)) {
          appendLegacyPart(blocks, part);
        }
      }
    }
    if (blocks.length) return blocks;
  }
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
      for (const part of legacyParts(before)) appendLegacyPart(blocks, part);
    }
    blocks.push({ type: 'heading', text: match[1].trim() });
    cursor = match.index + match[0].length;
  }
  const remainder = value.slice(cursor).trim();
  if (remainder) {
    for (const part of legacyParts(remainder)) appendLegacyPart(blocks, part);
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

// Legacy bodies can contain an introduction followed by a second projection of
// the same steps. Keep proven leading text; never guess at near-duplicate prose.
function legacyIntroductionBlocks(body, steps) {
  const blocks = legacyArticleBlocks(body);
  const firstStep = blocks.findIndex(block => block.type === 'step');
  if (firstStep !== -1) {
    const numbered = blocks.slice(firstStep);
    const normalized = text => normalizedArticleText(text).replace(/\s+/gu, ' ');
    const replay = numbered.length === steps.length && numbered.every((block, index) => {
      const step = steps[index];
      const ordinal = Number.isInteger(step.number) ? step.number : index + 1;
      const text = (block.parts || []).map(part => part.type === 'callout'
        ? `${part.label}: ${part.text}` : part.text).join(' ');
      const variants = [
        [step.action || step.heading, ...(step.instructions || [])],
        step.instructions || [],
      ].map(parts => normalized(parts.filter(part => typeof part === 'string').join(' ')));
      return block.type === 'step' && block.number === ordinal &&
        variants.some(variant => variant && variant === normalized(text));
    });
    // An unrelated numbered list is body text, not a replay. Leading-text
    // parsing retains its literal ordinals/parts without a fake step projection.
    return replay ? blocks.slice(0, firstStep) : legacyLeadBlocks(body);
  }

  const words = [...body.matchAll(/\S+/gu)];
  const sequences = [
    steps.flatMap(step => [step.action || step.heading, ...(step.instructions || [])]),
    steps.flatMap(step => step.instructions || []),
  ].map(parts => parts.filter(part => typeof part === 'string').join(' ').match(/\S+/gu) || [])
    .filter(sequence => sequence.length > 0)
    .sort((a, b) => b.length - a.length);
  for (const sequence of sequences) {
    const start = words.length - sequence.length;
    if (start >= 0 && sequence.every((word, index) => word === words[start + index][0])) {
      return legacyArticleBlocks(body.slice(0, words[start].index));
    }
  }
  return blocks;
}

export function articlePresentation(article) {
  const steps = Array.isArray(article.steps) ? article.steps : [];
  const documentBlocks = Array.isArray(article.document?.blocks) ? article.document.blocks : [];
  // A partly empty legacy sequence must not silently discard its missing text.
  const usable = steps.length > 0 && steps.every(step =>
    step.action?.trim() || step.heading?.trim() || step.instructions?.some(text => typeof text === 'string' && text.trim()));
  const body = String(article.body || '');
  return {
    steps: usable ? steps : [],
    documentBlocks,
    body,
    introBlocks: !documentBlocks.length && usable ? legacyIntroductionBlocks(body, steps) : [],
    blocks: documentBlocks.length || usable ? [] : legacyArticleBlocks(body),
    legacy: steps.length > 0 && !usable,
  };
}

export function localImageURL(value, origin, { compatibility = false, authMode = null } = {}) {
  if (typeof value !== 'string' || /[\s\u0000-\u001f]/.test(value)) return null;
  if (compatibility && /^data:image\/(png|jpeg|webp|gif);base64,[a-z\d+/=]+$/i.test(value)) return value;
  try {
    const url = new URL(value, origin);
    const paidPath = /^\/v1\/catalog\/images\/v2\.[a-zA-Z0-9_-]{1,6000}$/.test(url.pathname);
    const localToken = authMode === 'local'
      ? /^\/v1\/catalog\/images\/([a-zA-Z0-9_-]{38,6000})$/.exec(url.pathname)?.[1]
      : null;
    const localPath = localToken && localToken.length % 4 !== 1;
    return ['http:', 'https:'].includes(url.protocol) && url.origin === origin && !url.username && !url.password && !url.search && !url.hash && (compatibility || paidPath || localPath) ? url.href : null;
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

const DEFAULT_COLLECTION_POLL_INTERVAL_MS = 1500;
const DEFAULT_COLLECTION_POLL_WINDOW_MS = 60_000;
const DEFAULT_COLLECTION_POLL_ATTEMPTS = Math.ceil(
  DEFAULT_COLLECTION_POLL_WINDOW_MS / DEFAULT_COLLECTION_POLL_INTERVAL_MS,
);
const EMPTY_COLLECTION_PROBE_DELAY_MS = 350;
const EMPTY_COLLECTION_PROBE_TIMEOUT_MS = 500;

// Hydration polling is bounded to one minute. The UI reports source progress;
// this internal polling budget is not a user-facing attempt counter.
export async function readCollection(
  read,
  {
    signal,
    onUpdate = () => {},
    desired = '',
    attempts = DEFAULT_COLLECTION_POLL_ATTEMPTS,
    interval = DEFAULT_COLLECTION_POLL_INTERVAL_MS,
    wait = delay,
    emptyProbe,
    now = () => performance.now(),
  } = {},
) {
  let latest;
  function update(data, attempt) {
    signal?.throwIfAborted();
    if (!Array.isArray(data?.items)) throw new Error('The catalog returned an unreadable list. Try again.');
    latest = data;
    onUpdate(latest, { attempt: attempt + 1, attempts });
    // A saved selection can resume using an existing row while ingestion continues.
    return (desired && latest.items.some(item => String(item.id ?? item.year) === desired)) ||
      !(latest.hydrating || latest.discovering) || latest.complete === true;
  }
  for (let attempt = 0; attempt < attempts; attempt++) {
    signal?.throwIfAborted();
    if (update(await read(), attempt)) return latest;
    if (attempt === attempts - 1) break;
    if (attempt === 0 && emptyProbe && !latest.items.length && interval > EMPTY_COLLECTION_PROBE_DELAY_MS) {
      // Check newly stored options once without moving the regular polling schedule.
      const deadline = now() + interval;
      await wait(EMPTY_COLLECTION_PROBE_DELAY_MS, signal);
      const timeout = Math.min(EMPTY_COLLECTION_PROBE_TIMEOUT_MS, Math.floor(deadline - now()));
      if (timeout > 0) {
        signal?.throwIfAborted();
        const early = await emptyProbe(timeout);
        signal?.throwIfAborted();
        if (Array.isArray(early?.items) && (early.items.length || early.complete === true) && update(early, attempt)) return latest;
      }
      await wait(Math.max(0, deadline - now()), signal);
    } else {
      await wait(interval, signal);
    }
  }
  return { ...latest, timedOut: true };
}

export class CatalogRequestError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_UNAVAILABLE', retryable = false, retryAfterSeconds = 0, requestId = '', purchaseQuote } = {}) {
    super(message); Object.assign(this, { status, code, retryable, retryAfterSeconds, requestId });
    if (purchaseQuote !== undefined) this.purchaseQuote = purchaseQuote;
  }
}
function safeRequestMessage(status) {
  if (status === 401 || status === 403) return 'Your session cannot access this catalog. Sign in or check your access.';
  if (status === 404) return 'This article or vehicle could not be found. Return to the index.';
  if (status === 410) return 'This article is no longer available.';
  if (status === 409) return 'This article needs review before it can be opened.';
  return 'AutoData is temporarily unavailable. Try again.';
}
const shortSourceCheckPreference = 'workshop-short-source-check';
const shortPublicationCheckPreference = 'workshop-short-publication-check';
const finishPublishedBodyPreference = 'workshop-finish-published-body';
const publicationStatusPreference = 'workshop-publication-status';

export async function requestArticleJSON(path, {
  signal, timeout = 10000, readableBodyTimeout = 0, fetcher = fetch, method = 'GET', body, headers = {},
  preferShortSourceCheck = false, preferShortPublicationCheck = false,
  finishPublishedBody = false, reportBodyNetworkError = false, publicationCheck,
} = {}) {
  const preferences = [];
  if (preferShortSourceCheck) preferences.push(shortSourceCheckPreference);
  if (preferShortPublicationCheck) preferences.push(shortPublicationCheckPreference);
  if (finishPublishedBody) preferences.push(finishPublishedBodyPreference);
  if (publicationCheck) {
    preferences.push(publicationStatusPreference);
    headers = {
      ...headers,
      'X-Workshop-Publication-Job': publicationCheck.jobId,
      'X-Workshop-Source-Revision': publicationCheck.sourceRevisionId,
    };
  }
  const readTimeout = Math.max(1, Math.min(10000, timeout));
  const bodyTimeout = Math.min(10000, readableBodyTimeout);
  const earlyTimeout = bodyTimeout > readTimeout ? AbortSignal.timeout(readTimeout) : null;
  const timeoutSignal = AbortSignal.timeout(earlyTimeout ? bodyTimeout : readTimeout);
  const earlyController = earlyTimeout ? new AbortController() : null;
  const abortEarly = () => earlyController.abort(earlyTimeout.reason);
  earlyTimeout?.addEventListener('abort', abortEarly, { once: true });
  const signals = [timeoutSignal];
  if (signal) signals.push(signal);
  if (earlyController) signals.push(earlyController.signal);
  const combined = signals.length > 1 ? AbortSignal.any(signals) : timeoutSignal;
  let retryAfterSeconds = 0;
  try {
    const response = await fetcher(path, { method, signal: combined, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(preferences.length ? { Prefer: preferences.join(', ') } : {}), ...headers }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const applied = response.headers.get('Preference-Applied');
    const retry = response.headers.get('Retry-After');
    // Keep this header when a short probe times out receiving the body.
    retryAfterSeconds = retry && /^\d+$/.test(retry) ? Number(retry) : retry ? Math.max(0, Math.ceil((Date.parse(retry) - Date.now()) / 1000)) || 0 : 0;
    const confirmedPublication = applied === finishPublishedBodyPreference && retry === null;
    if (response.status === 200 && (!finishPublishedBody || confirmedPublication)) {
      earlyTimeout?.removeEventListener('abort', abortEarly);
    }
    let bodyError;
    const data = response.status === 204 ? null : await response.json().catch((error) => {
      bodyError = error;
      return null;
    });
    signal?.throwIfAborted();
    combined.throwIfAborted();
    if (!response.ok) {
      const error = data?.error;
      const code = typeof error?.code === 'string' ? error.code : 'HTTP_ERROR';
      throw new CatalogRequestError(safeRequestMessage(response.status), {
        status: response.status, code, retryable: error?.retryable === true, retryAfterSeconds,
        requestId: typeof error?.request_id === 'string' ? error.request_id : '',
        purchaseQuote: response.status === 403 && code === 'ENTITLEMENT_REQUIRED' ? error.details?.purchase_quote : undefined,
      });
    }
    if (reportBodyNetworkError && retryAfterSeconds === 0 && bodyError instanceof TypeError) throw bodyError;
    if (response.status !== 204 && (!data || typeof data !== 'object' || Array.isArray(data))) {
      throw new CatalogRequestError('The catalog returned an unreadable response. Try again.', {
        code: 'INVALID_RESPONSE', retryAfterSeconds,
      });
    }
    const shortSourceCheck = preferShortSourceCheck && applied === shortSourceCheckPreference;
    const shortPublicationCheck = preferShortPublicationCheck && applied === shortPublicationCheckPreference;
    const publicationStatus = Boolean(publicationCheck && applied === publicationStatusPreference);
    const publicationCheckSupported = response.headers.get('Workshop-Publication-Check') === 'supported';
    return { status: response.status, data, retryAfterSeconds, shortSourceCheck, shortPublicationCheck,
      ...(publicationStatus ? { publicationStatus } : {}),
      ...(publicationCheckSupported ? { publicationCheckSupported } : {}),
    };
  } catch (error) {
    signal?.throwIfAborted();
    if (error instanceof CatalogRequestError) throw error;
    if (combined.aborted || error instanceof TypeError) throw new CatalogRequestError('Cannot reach AutoData. Try again.', { retryable: true, retryAfterSeconds });
    throw error;
  } finally {
    earlyTimeout?.removeEventListener('abort', abortEarly);
  }
}
export async function requestJSON(path, options) { return (await requestArticleJSON(path, options)).data; }

export function requestInitialYears(params, request = requestJSON) {
  if (params.has('configuration') || params.has('order') || params.get('view') === 'library') return null;
  return request('/v1/catalog/years').catch(() => null);
}
