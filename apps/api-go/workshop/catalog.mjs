// Pure catalog helpers are shared by the browser and the regression suite.
export function configurationLabel(item) {
  const displacement = typeof item.engine === 'string' && /^\d+(?:\.\d+)?$/.test(item.engine);
  const engine = [displacement ? `${item.engine} L` : item.engine, item.engine_variant].filter(Boolean).join(' ');
  return [engine, item.trim, item.body_style, item.drivetrain].filter(Boolean).join(' / ') || 'Base configuration';
}

export function selectorLabel(name, item) {
  if (name === 'year') return String(item.year);
  if (name === 'configuration') {
    const label = configurationLabel(item);
    if (item.engine_variant_market_unverified === true) return `${label} · market unverified`;
    return item.configuration_unresolved === true ? `${label} · unverified` : label;
  }
  return item.market_unverified === true ? `${item.name} · market unverified` : item.name;
}

const articleSearchWhitespace = /\p{White_Space}+/u;

export function trimArticleSearch(value) {
  return value.replace(/^\p{White_Space}+|\p{White_Space}+$/gu, '');
}

export function articleSearchParams(value) {
  const query = trimArticleSearch(value);
  return [...query].length > 120 || query.split(articleSearchWhitespace).length > 8
    ? { title: query }
    : { q: query };
}

function articleTitleMatch(title) {
  // Match full titles with the same simple case folding as the API.
  const literal = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const exact = new RegExp(`^${literal}$`, 'iu');
  return item => exact.test(trimArticleSearch(item.title || ''));
}

export function prioritizeReadableTitle(items, query) {
  const matches = articleTitleMatch(query);
  const titles = [];
  const others = [];
  for (const item of items) {
    const destination = item.availability === 'available' && matches(item) ? titles : others;
    destination.push(item);
  }
  return titles.length ? [...titles, ...others] : items;
}

export function filterArticles(items, query) {
  const { title, q } = articleSearchParams(query);
  if (title) return items.filter(articleTitleMatch(title));
  const words = q.toLocaleLowerCase().split(articleSearchWhitespace).filter(Boolean);
  return items.filter(item => {
    const text = [item.title, item.component, item.kind, item.service_schedule].filter(Boolean).join(' ').toLocaleLowerCase();
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

export const DEFAULT_COLLECTION_POLL_INTERVAL_MS = 1500;
const DEFAULT_COLLECTION_POLL_WINDOW_MS = 60_000;
const DEFAULT_COLLECTION_POLL_ATTEMPTS = Math.ceil(
  DEFAULT_COLLECTION_POLL_WINDOW_MS / DEFAULT_COLLECTION_POLL_INTERVAL_MS,
);
const EMPTY_COLLECTION_PROBE_DELAY_MS = 350;
const EMPTY_COLLECTION_PROBE_TIMEOUT_MS = 500;
const FIRST_SELECTOR_CHOICES_FAST_WINDOW_MS = 22_000;
const PARTIAL_SELECTOR_FAST_WINDOW_MS = 8000;
const ENGINE_DISCOVERY_INTERVAL_MS = 4000;
const MAX_PARTIAL_SELECTOR_INTERVAL_MS = 12_000;

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
    waitForEmpty,
    emptyProbe,
    emptyProbeDelays = [EMPTY_COLLECTION_PROBE_DELAY_MS],
    backoffWithChoices = false,
    backoffWithoutChoices = false,
    retryEmptyTransientRead = false,
    stopWithChoices = false,
    hasChoices = data => data.items.length > 0,
    now = () => performance.now(),
  } = {},
) {
  let latest;
  let fastPollingSince;
  let emptyReadRetried = false;
  let partialInterval = interval;
  let waitingForRows = false;
  const pollUntil = backoffWithChoices ? now() + DEFAULT_COLLECTION_POLL_WINDOW_MS : Infinity;
  const fastWindow = stopWithChoices ? FIRST_SELECTOR_CHOICES_FAST_WINDOW_MS : PARTIAL_SELECTOR_FAST_WINDOW_MS;
  function update(data, attempt) {
    signal?.throwIfAborted();
    if (!Array.isArray(data?.items)) throw new Error('The catalog returned an unreadable list. Try again.');
    latest = data;
    onUpdate(latest, { attempt: attempt + 1, attempts });
    const usable = desired
      ? latest.items.some(item => String(item.id ?? item.year) === desired)
      : stopWithChoices && hasChoices(latest);
    return usable || !(latest.hydrating || latest.discovering) || latest.complete === true;
  }
  for (let attempt = 0; attempt < attempts; attempt++) {
    signal?.throwIfAborted();
    const remaining = Math.floor(pollUntil - now());
    if (remaining < 1 && latest) break;
    let data;
    try {
      const timeout = backoffWithChoices ? Math.max(1, remaining) : undefined;
      if (waitingForRows) {
        const started = now();
        data = await waitForEmpty(timeout);
        signal?.throwIfAborted();
        // A server without a listener can reply immediately. Continue at the
        // ordinary cadence while its catalog remains empty.
        if (data?.items?.length === 0 && data.hydrating && !data.complete)
          await wait(Math.max(0, Math.min(interval, remaining) - (now() - started)), signal);
      } else {
        data = await read(timeout);
      }
    } catch (error) {
      signal?.throwIfAborted();
      // A failed stored read does not end an active lookup for the first choices.
      if (retryEmptyTransientRead && !emptyReadRetried && latest?.items.length === 0 &&
          latest.hydrating && error instanceof CatalogRequestError && !error.retryAfterSeconds &&
          (error.status === 503 || (error.status === 0 && error.retryable)) &&
          attempt < attempts - 1 && now() + interval < pollUntil) {
        emptyReadRetried = true;
        await wait(interval, signal);
        continue;
      }
      // Keep the usable list already shown for this request scope.
      if (latest?.items.length && error instanceof CatalogRequestError &&
          (error.status === 0 || error.status === 408 || error.status === 429 || error.status >= 500))
        return { ...latest, refreshFailed: true };
      throw error;
    }
    if (update(data, attempt)) return latest;
    if (attempt === attempts - 1 || now() >= pollUntil) break;
    waitingForRows = Boolean(waitForEmpty && !hasChoices(latest) && latest.hydrating);
    if (waitingForRows) {
      if (now() + interval >= pollUntil) break;
      continue;
    }
    if (attempt === 0 && emptyProbe && !hasChoices(latest) && emptyProbeDelays[0] < interval) {
      // Check for newly stored rows without moving the regular poll.
      const started = now();
      const deadline = started + interval;
      for (const probeDelay of emptyProbeDelays) {
        if (probeDelay >= interval || hasChoices(latest)) break;
        await wait(Math.max(0, started + probeDelay - now()), signal);
        const timeout = Math.min(EMPTY_COLLECTION_PROBE_TIMEOUT_MS, Math.floor(deadline - now()));
        if (timeout < 1) break;
        signal?.throwIfAborted();
        const early = await emptyProbe(timeout);
        signal?.throwIfAborted();
        if (!Array.isArray(early?.items)) break;
        const active = early.hydrating || early.discovering;
        if ((hasChoices(early) || early.complete === true || (early.discovery_instance && !active)) &&
            update(early, attempt)) return latest;
        if (!active) break;
      }
      await wait(Math.max(0, deadline - now()), signal);
    } else {
      const checkedAt = now();
      // An empty make or model picker gates the next step. Check for its
      // first rows at the normal cadence through one bounded supplier job.
      if (backoffWithChoices && ((!desired && hasChoices(latest)) || backoffWithoutChoices)) {
        fastPollingSince ??= checkedAt;
        if (!desired && latest.discovering && !latest.hydrating)
          partialInterval = Math.max(partialInterval, ENGINE_DISCOVERY_INTERVAL_MS);
        if (checkedAt - fastPollingSince >= fastWindow)
          partialInterval = Math.min(partialInterval * 2, MAX_PARTIAL_SELECTOR_INTERVAL_MS);
      } else {
        fastPollingSince = undefined;
        partialInterval = interval;
      }
      if (checkedAt + partialInterval >= pollUntil) break;
      await wait(partialInterval, signal);
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
const previewSourceCheckPreference = 'workshop-preview-source-check';
const earlySourceCheckPreference = 'workshop-early-source-check';
const shortPublicationCheckPreference = 'workshop-short-publication-check';
const finishPublishedBodyPreference = 'workshop-finish-published-body';
const publicationStatusPreference = 'workshop-publication-status';
const retainedReaderSessionPreference = 'workshop-retained-reader-session';
export const selectedIndexSessionPreference = 'workshop-confirm-session';

export async function matchesRetainedReaderSession(response, csrf) {
  if (response?.status !== 200 || !/^[a-f0-9]{64}$/.test(response.readerSession ?? '') ||
      !csrf || !globalThis.crypto?.subtle) return false;
  try {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(csrf));
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') === response.readerSession;
  } catch {
    return false;
  }
}

export async function requestArticleJSON(path, {
  signal, timeout = 10000, readableBodyTimeout = 0, fetcher = fetch, method = 'GET', body, headers = {}, cache = 'no-store',
  preferShortSourceCheck = false, preferPreviewSourceCheck = false, preferEarlySourceCheck = false,
  preferShortPublicationCheck = false,
  finishPublishedBody = false, reportBodyNetworkError = false, publicationCheck, retainedReaderSession = false,
  onResponseStatus, onResponseDate, onSelectedIndexSession,
} = {}) {
  const preferences = [];
  if (preferShortSourceCheck) preferences.push(shortSourceCheckPreference);
  if (preferPreviewSourceCheck && method === 'GET') preferences.push(previewSourceCheckPreference);
  if (preferEarlySourceCheck && method === 'GET') preferences.push(earlySourceCheckPreference);
  if (preferShortPublicationCheck) preferences.push(shortPublicationCheckPreference);
  if (finishPublishedBody) preferences.push(finishPublishedBodyPreference);
  if (retainedReaderSession) preferences.push(retainedReaderSessionPreference);
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
    const response = await fetcher(path, {
      method, signal: combined, credentials: 'same-origin', cache,
      ...(onSelectedIndexSession || retainedReaderSession ? { redirect: 'error' } : {}),
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(preferences.length ? { Prefer: preferences.join(', ') } : {}),
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    onResponseStatus?.(response.status);
    const applied = response.headers.get('Preference-Applied');
    if (onSelectedIndexSession && response.status !== 401 &&
        applied?.split(',').some(preference => preference.trim() === selectedIndexSessionPreference)) {
      onSelectedIndexSession({
        exchangeCSRF: response.status === 204 ? response.headers.get('X-CSRF-Token') : null,
        expiresAt: response.headers.get('Workshop-Session-Expires'),
      });
    }
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
    // The HTTP status already establishes a denial or rate limit, even if
    // the optional error details did not arrive before the body deadline.
    if (![401, 403, 404, 410, 429].includes(response.status)) combined.throwIfAborted();
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
    const previewSourceCheck = preferPreviewSourceCheck && method === 'GET' && applied === previewSourceCheckPreference;
    const shortPublicationCheck = preferShortPublicationCheck && applied === shortPublicationCheckPreference;
    const publicationStatus = Boolean(publicationCheck && applied === publicationStatusPreference);
    const publicationCheckSupported = response.headers.get('Workshop-Publication-Check') === 'supported';
    onResponseDate?.(response.headers.get('Date'));
    return { status: response.status, data, retryAfterSeconds, shortSourceCheck, shortPublicationCheck,
      ...(retainedReaderSession ? { readerSession: response.headers.get('Workshop-Reader-Session') } : {}),
      ...(previewSourceCheck ? { previewSourceCheck } : {}),
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
const directMakePath = /^\/v1\/catalog\/years\/\d{4}\/makes\?region=US$/;
const directModelPath = /^\/v1\/catalog\/years\/\d{4}\/makes\/[a-z0-9-]+\/models\?region=US(?:&(?:stored_only|defer_refresh|optional_refresh)=1)?$/;
const directConfigurationPath = /^\/v1\/catalog\/years\/\d{4}\/makes\/[a-z0-9-]+\/models\/[a-z0-9-]+\/configurations\?region=US(?:&stored_only=1)?$/;
const directMakeTimeout = 175;
const directModelTimeout = 200;
const directConfigurationTimeout = 400;
const storedModelFallbackDelay = 100;
const storedConfigurationFallbackDelay = 150;
const directSelectorBodyTimeout = 1500;
const makeRouteKey = 'workshop:make-same-origin:';
const modelRouteKey = 'workshop:model-same-origin:';
const selectorRouteLifetime = 30000;
let directSelectorsUnavailable = false;

export function rememberSameOriginMake(path) {
  if (globalThis.location?.origin !== 'https://autodata.cars.tk' || !directMakePath.test(path)) return;
  rememberSameOriginSelector(makeRouteKey, path);
}

function rememberSameOriginSelector(key, path) {
  try {
    globalThis.sessionStorage?.setItem(key + path, String(Date.now() + selectorRouteLifetime));
  } catch {
    // The browser may restrict session storage.
  }
}

function hasRecentSameOriginSelector(key, path) {
  try {
    return Number(globalThis.sessionStorage?.getItem(key + path)) > Date.now();
  } catch {
    return false;
  }
}

function directSelectorURL(path, { method = 'GET', headers, body, preferSameOrigin }) {
  if (directSelectorsUnavailable || preferSameOrigin || method !== 'GET' || headers || body !== undefined ||
      globalThis.location?.origin !== 'https://autodata.cars.tk' ||
      typeof path !== 'string' ||
      !(directMakePath.test(path) || directModelPath.test(path) || directConfigurationPath.test(path))) return null;
  // A fast year selection on the cold page can already have cached this
  // exact list on the main origin before the catalog module was ready.
  if (directMakePath.test(path) && hasRecentSameOriginSelector(makeRouteKey, path)) return null;
  const catalog = globalThis.document?.getElementById('workshop-catalog-module');
  if (catalog?.dataset?.publicSelectors !== 'true' || !catalog.dataset.directSelectorOrigin) return null;
  return catalog.dataset.directSelectorOrigin + path;
}

async function fetchSelectorBeforeAbort(fetcher, resource, init) {
  const { signal } = init;
  signal.throwIfAborted();
  let onAbort;
  const cancelled = new Promise((_, reject) => {
    onAbort = () => reject(signal.reason);
    signal.addEventListener('abort', onAbort, { once: true });
  });
  try {
    // A browser can leave the transport promise pending after its signal is aborted.
    const response = Promise.resolve().then(() => {
      signal.throwIfAborted();
      return fetcher(resource, init);
    });
    return await Promise.race([response, cancelled]);
  } finally {
    signal.removeEventListener('abort', onAbort);
  }
}

function prepareStoredSelectorFallback(fetchSelector, resource, init, afterMs) {
  const controller = new AbortController();
  const signal = AbortSignal.any([init.signal, controller.signal]);
  const path = resource.replace(/&(?:defer_refresh|optional_refresh)=1$/, '') + '&stored_only=1';
  const prepared = { started: false, response: null, data: null, cancel: () => controller.abort() };
  prepared.pending = delay(afterMs, signal).then(async () => {
    prepared.started = true;
    const response = await fetchSelector(path, { ...init, signal, cache: 'no-store' });
    if (response.headers.has('Retry-After') || [401, 403, 429].includes(response.status)) {
      prepared.response = response;
    } else if (response.ok) {
      const data = await response.clone().json();
      signal.throwIfAborted();
      if (data?.version === 'v1' && Array.isArray(data.items) && data.items.length) {
        if (data.complete === true && !data.hydrating && !data.discovering) prepared.response = response;
        else prepared.data = data;
      }
    }
    return prepared.response;
  }).catch(() => null).finally(() => {
    if (!prepared.response) prepared.cancel();
  });
  return prepared;
}

async function readSelectorFallback(fetchSelector, resource, init, prepared, onStoredChoices) {
  if (!prepared?.started) {
    prepared?.cancel();
    return fetchSelector(resource, init);
  }
  if (prepared.response) return prepared.response;
  const regularRead = new AbortController();
  const regular = fetchSelector(resource, { ...init, signal: AbortSignal.any([init.signal, regularRead.signal]) });
  let waiting = true;
  const retained = prepared.pending.then(response => {
    if (response) return response;
    if (waiting && prepared.data && !init.signal.aborted) onStoredChoices(prepared.data);
    return regular;
  });
  try {
    const response = await Promise.race([regular, retained]);
    if (response === prepared.response) regularRead.abort();
    else prepared.cancel();
    return response;
  } catch (error) {
    prepared.cancel();
    throw error;
  } finally {
    waiting = false;
  }
}

export async function requestJSON(path, options = {}) {
  if (options.deferModelRefresh) path += '&defer_refresh=1';
  else if (options.optionalModelRefresh) path += '&optional_refresh=1';
  const direct = directSelectorURL(path, options);
  if (!direct) return (await requestArticleJSON(path, options)).data;
  const isMake = directMakePath.test(path);
  const isModel = directModelPath.test(path);
  // An embedded make list can leave the model as the first direct request.
  const connectionTimeout = isMake ? directMakeTimeout : isModel ? directModelTimeout : directConfigurationTimeout;
  const { fetcher = fetch } = options;
  const fetchSelector = (resource, init) => fetchSelectorBeforeAbort(fetcher, resource, init);
  const bodyDeadline = performance.now() + Math.max(1, Math.min(10000, options.timeout ?? 10000));
  let timeout = options.timeout;
  let sameOriginModelError;
  // A quick revisit can use the route that just returned model choices.
  if (isModel && hasRecentSameOriginSelector(modelRouteKey, path)) {
    let explicitRetryAfter = false;
    try {
      const { data } = await requestArticleJSON(path, {
        ...options,
        async fetcher(resource, init) {
          const response = await fetchSelector(resource, init);
          explicitRetryAfter = response.headers.has('Retry-After');
          return response;
        },
      });
      return data;
    } catch (error) {
      options.signal?.throwIfAborted();
      const remaining = Math.floor(bodyDeadline - performance.now());
      const transient = error instanceof CatalogRequestError && !explicitRetryAfter && !error.retryAfterSeconds &&
        ([502, 503, 504].includes(error.status) || (!error.status && (error.retryable || error.code === 'INVALID_RESPONSE')));
      if (!transient || remaining < 1) throw error;
      sameOriginModelError = error;
      timeout = remaining;
      try {
        globalThis.sessionStorage?.removeItem(modelRouteKey + path);
      } catch {
        // The browser may restrict session storage.
      }
    }
  }
  const connection = new AbortController();
  let rememberModelFallback = false;
  let canRetryDirectBody = false;
  let bodyTimer;
  const read = requestArticleJSON(path, {
    ...options,
    timeout,
    reportBodyNetworkError: true,
    async fetcher(resource, init) {
      init.signal.throwIfAborted();
      const deadline = setTimeout(() => connection.abort(), connectionTimeout);
      // The read-only probe can prepare an exact retained list while the
      // direct request is waiting for headers. Only a transport failure or
      // transient gateway error makes the prepared list eligible.
      const prepared = options.onStoredChoices && !sameOriginModelError && !isMake && !path.endsWith('&stored_only=1')
        ? prepareStoredSelectorFallback(fetchSelector, resource, init,
            isModel ? storedModelFallbackDelay : storedConfigurationFallbackDelay)
        : null;
      let response;
      try {
        response = await fetchSelector(direct, {
          ...init,
          signal: AbortSignal.any([init.signal, connection.signal]),
          credentials: 'omit',
          redirect: 'error',
          referrerPolicy: 'no-referrer',
        });
      } catch {
        init.signal.throwIfAborted();
        // The first lookup can outrun the connection hint. A short make timeout
        // still lets subsequent selectors use a connection that has since warmed.
        if (!isMake || !connection.signal.aborted) directSelectorsUnavailable = true;
      } finally {
        clearTimeout(deadline);
      }
      // The main origin can still serve recorded choices during an edge outage.
      // Preserve any explicit wait from the direct selector.
      if (response && (![502, 503, 504].includes(response.status) || response.headers.has('Retry-After'))) {
        prepared?.cancel();
        canRetryDirectBody = response.ok && !response.headers.has('Retry-After');
        if (canRetryDirectBody) {
          // Keep part of the overall budget available if the direct body stalls.
          bodyTimer = setTimeout(() => connection.abort(), directSelectorBodyTimeout);
        }
        return response;
      }
      init.signal.throwIfAborted();
      if (response?.body) void response.body.cancel().catch(() => {});
      if (sameOriginModelError) throw sameOriginModelError;
      const fallback = await readSelectorFallback(fetchSelector, resource, init, prepared, options.onStoredChoices);
      if (isMake && fallback.ok) rememberSameOriginMake(path);
      rememberModelFallback = isModel && connection.signal.aborted && fallback.ok;
      return fallback;
    },
  }).finally(() => clearTimeout(bodyTimer));
  try {
    const { data } = await read;
    if (rememberModelFallback && Array.isArray(data?.items) && data.items.length)
      rememberSameOriginSelector(modelRouteKey, path);
    return data;
  } catch (error) {
    options.signal?.throwIfAborted();
    const remaining = Math.floor(bodyDeadline - performance.now());
    // A stalled or truncated direct body can surface as a network error or invalid JSON.
    if (sameOriginModelError || !canRetryDirectBody || !(error instanceof CatalogRequestError) ||
        error.status || !(error.retryable || error.code === 'INVALID_RESPONSE') || remaining < 1) throw error;
    const fallback = await requestArticleJSON(path, { ...options, timeout: remaining, fetcher: fetchSelector });
    if (isMake) rememberSameOriginMake(path);
    return fallback.data;
  }
}

export function vehicleSelectorPath(name, selection) {
  const year = encodeURIComponent(selection.year ?? '');
  const make = encodeURIComponent(selection.make ?? '');
  const model = encodeURIComponent(selection.model ?? '');
  return {
    year: '/v1/catalog/years',
    make: `/v1/catalog/years/${year}/makes?region=US`,
    model: `/v1/catalog/years/${year}/makes/${make}/models?region=US`,
    configuration: `/v1/catalog/years/${year}/makes/${make}/models/${model}/configurations?region=US`,
  }[name];
}

export function requestStoredSelector(path, options, request = requestJSON) {
  const separator = path.includes('?') ? '&' : '?';
  return request(`${path}${separator}stored_only=1`, options);
}

export function startSavedSelectorReads(params, request = requestJSON) {
  const year = params.get('year') || '';
  // These routes can open without the vehicle hierarchy, or depend on the session.
  if (params.get('sample') === '1' || params.get('demo') === '1' ||
      params.has('order') || params.get('view') === 'library' || params.has('article') ||
      (params.has('configuration') && params.get('q')?.trim()) ||
      !/^\d{4}$/.test(year) || Number(year) < 1886 || Number(year) > 2100) return null;
  const controller = new AbortController();
  const selection = { year, make: params.get('make'), model: params.get('model') };
  const reads = {};
  for (const name of ['year', 'make', 'model', 'configuration']) {
    const path = vehicleSelectorPath(name, selection);
    // Years can continue loading while a selection changes below the year picker.
    reads[name] = (name === 'year' ? request(path) : requestStoredSelector(path, { signal: controller.signal }, request))
      .catch(() => null);
    const value = selection[name];
    if (!value || value.length > 128 || value === '.' || value === '..') break;
  }
  return { route: params.toString(), reads, abort: () => controller.abort() };
}

export function requestInitialYears(params, request = requestJSON) {
  if (params.has('configuration') || params.has('order') || params.get('view') === 'library') return null;
  return request('/v1/catalog/years').catch(() => null);
}
