import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext as runVM } from 'node:vm';
import { NavigationGeneration, awaitingArticleRewrite, processingArticle, readableArticle, readyReprojectedSource } from './workshop/article-read.mjs';
import { pollOrder, purchaseConfiguration, quoteConfigurationLabel, readOrder, resumableCheckoutURL, sameScope, uuid, validQuote, validScope, validLibrary } from './workshop/commerce.mjs';
import { articlePresentation, articleSearchParams, CatalogRequestError, configurationLabel, delay, filterArticles, hasSourceReference, legacyArticleBlocks, localImageURL, readCollection, requestInitialYears, requestJSON, requestStoredSelector, selectedIndexSessionPreference, selectorLabel, sourceReferenceURL, startSavedSelectorReads, trimArticleSearch, vehicleSelectorPath } from './workshop/catalog.mjs';
import { LOAD_STAGES, loadingProgress } from './workshop/progress.mjs';

const paidPagePreferences = 'workshop-index-pages, workshop-index-live-pages';

// The app sections below run without the module bootstrap. Model the ordinary
// paid path unless a test explicitly opts into the open demo.
function runInNewContext(code, context) {
  context.openDemo ??= false;
  context.resumableCheckoutURL ??= resumableCheckoutURL;
  context.sameScope ??= sameScope;
  context.validScope ??= validScope;
  context.delay ??= delay;
  context.demoPath ??= path => path;
  context.articleSearchParams ??= articleSearchParams;
  context.trimArticleSearch ??= trimArticleSearch;
  context.requestInitialYears ??= params => requestInitialYears(params, context.requestJSON);
  context.requestStoredSelector ??= requestStoredSelector;
  context.vehicleSelectorPath ??= vehicleSelectorPath;
  context.sourceDocumentRequest ??= null;
  context.mountedSource ??= null;
  context.paidOrder ??= null;
  context.articleIndexOrigin ??= null;
  context.articlePage ??= 0;
  context.articleIndexPagePreferences ??= paidPagePreferences;
  context.indexPage ??= null;
  context.pendingIndexPage ??= null;
  context.performance ??= performance;
  context.pickerStates ??= new Map();
  context.cancelPickerRefreshes ??= () => {};
  context.selectorCache ??= new Map();
  context.selectorCacheLifetime ??= 30_000;
  context.selectorCacheSize ??= 32;
  context.cachedSelector ??= () => null;
  context.selectorLabel ??= selectorLabel;
  context.merchant ??= null;
  context.checkoutModeReady ??= null;
  context.testStripeMode ??= false;
  return runVM(code, context);
}

test('loading progress uses fixed ordered stages and caps incomplete hydration', () => {
  assert.deepEqual(LOAD_STAGES.map(stage => stage.key), ['year', 'make', 'model', 'configuration', 'articles', 'article']);
  assert.equal(loadingProgress('make', { complete: true }).complete, true);
  const partial = loadingProgress('make', { attempt: 40, attempts: 40, hydrating: true });
  assert.equal(partial.step, 2);
  assert.equal(partial.total, 6);
  assert.equal(partial.percent, null);
});

test('selector labels distinguish regional evidence from worldwide model names', () => {
  assert.equal(selectorLabel('model', { name: 'Avanza', market_unverified: true }), 'Avanza · market unverified');
  assert.equal(selectorLabel('model', { name: '4Runner' }), '4Runner');
  assert.equal(selectorLabel('make', { name: 'Toyota', market_unverified: true }), 'Toyota · market unverified');
  assert.equal(selectorLabel('year', { year: 2024 }), '2024');
  assert.equal(selectorLabel('configuration', { engine: '2.0' }), '2.0 L');
});

test('partial selector hydration expands until complete', async () => {
  const versions = [
    { items: [{ id: 'toyota' }], complete: false, hydrating: true },
    { items: [{ id: 'toyota' }, { id: 'ford' }], complete: true, hydrating: false },
  ];
  const updates = [];
  const attempts = [];
  const result = await readCollection(async () => versions.shift(), { onUpdate: (data, meta) => { updates.push(data.items.length); attempts.push(meta.attempt); }, wait: async () => {} });
  assert.deepEqual(updates, [1, 2]);
  assert.deepEqual(attempts, [1, 2]);
  assert.equal(result.complete, true);
});

test('persistent partial and empty scopes stop polling without claiming completeness', async () => {
  for (const items of [[], [{ id: 'partial' }]]) {
    let calls = 0;
    const result = await readCollection(async () => { calls++; return { items, complete: false, hydrating: true }; }, { attempts: 3, wait: async () => {} });
    assert.equal(calls, 3); assert.equal(result.timedOut, true); assert.equal(result.complete, false);
  }
});

test('a transient refresh preserves an already visible list in the current scope', async () => {
  const first = { items: [{ id: 'stored' }], complete: false, hydrating: true };
  const unavailable = new CatalogRequestError('Refresh unavailable', { status: 503 });
  for (const error of [unavailable, new CatalogRequestError('Network unavailable')]) {
    const updates = [];
    const result = await readCollection(async () => {
      if (updates.length) throw error;
      return first;
    }, { onUpdate: data => updates.push(data), wait: async () => {} });
    assert.deepEqual(updates, [first]);
    assert.deepEqual(result, { ...first, refreshFailed: true });
  }
  await assert.rejects(readCollection(async () => { throw unavailable; }), unavailable);
});

test('access and rate limit responses retain their status when the error body times out', async () => {
  const keepAlive = setTimeout(() => {}, 1000);
  try {
    for (const status of [401, 403, 404, 410, 429]) {
      await assert.rejects(requestJSON('/articles', {
        timeout: 10,
        fetcher: async (_path, { signal }) => ({
          ok: false,
          status,
          headers: new Headers(status === 429 ? { 'Retry-After': '2' } : {}),
          json: () => new Promise((_, reject) => {
            signal.addEventListener('abort', () => reject(signal.reason), { once: true });
          }),
        }),
      }), error => error instanceof CatalogRequestError && error.status === status &&
        error.retryAfterSeconds === (status === 429 ? 2 : 0));
    }
  } finally {
    clearTimeout(keepAlive);
  }
});

test('a denied refresh reaches the authorization handler after a visible list', async () => {
  for (const status of [401, 403, 404, 410]) {
    const denial = new CatalogRequestError('Access unavailable', { status });
    let attempts = 0;
    const opening = readCollection(async () => {
      if (attempts++) throw denial;
      return { items: [{ id: 'stored' }], complete: false, hydrating: true };
    }, { wait: async () => {} });
    await assert.rejects(opening, denial);
  }
});

for (const readyAtProbe of [true, false]) {
  test(`one stored probe ${readyAtProbe ? 'opens available choices early' : 'keeps ordinary polling deadlines'}`, async () => {
    const pending = { items: [], complete: false, hydrating: true };
    const ready = { items: [{ year: 2024 }], complete: true, hydrating: false };
    const normalReads = [], earlyReads = [];
    let clock = 0;
    const result = await readCollection(async () => {
      normalReads.push(clock);
      clock += 180;
      return normalReads.length === 1 ? pending : ready;
    }, {
      now: () => clock,
      wait: async ms => { clock += ms; },
      emptyProbe: async timeout => {
        earlyReads.push({ at: clock, timeout });
        clock += 180;
        return readyAtProbe ? ready : pending;
      },
    });
    assert.deepEqual(result, ready);
    assert.deepEqual(earlyReads, [{ at: 530, timeout: 500 }]);
    assert.deepEqual(normalReads, readyAtProbe ? [0] : [0, 1680]);
  });
}

test('a partial list with visible choices keeps the normal polling cadence', async () => {
  const partial = { items: [{ id: 'first' }], complete: false, hydrating: true };
  const ready = { ...partial, complete: true, hydrating: false };
  const steps = [partial, ready];
  const waits = [];
  await readCollection(async () => steps.shift(), {
    wait: async ms => { waits.push(ms); },
    emptyProbe: async () => assert.fail('a nonempty picker should not probe early'),
  });
  assert.deepEqual(waits, [1500]);
});

test('visible selector choices back off within the one-minute window', async () => {
  const partial = { items: [{ id: 'envision-awd' }], complete: false, hydrating: true };
  let clock = 0;
  const reads = [];
  const timeouts = [];
  const result = await readCollection(async timeout => {
    reads.push(clock);
    timeouts.push(timeout);
    clock += 150;
    return partial;
  }, {
    backoffWithChoices: true,
    now: () => clock,
    wait: async ms => { clock += ms; },
  });
  assert.deepEqual(reads, [0, 1650, 3300, 4950, 6600, 8250, 11400, 17550, 29700, 41850, 54000]);
  assert.equal(timeouts.at(-1), 6000);
  assert.ok(reads.at(-1) < 60_000);
  assert.equal(result.timedOut, true);
  assert.equal(result.complete, false);
  assert.deepEqual(result.items, partial.items);
});

test('a second supplier can publish choices within the original picker cadence', async () => {
  let clock = 0;
  const rows = [{ id: 'first' }];
  const later = { items: [...rows, { id: 'second' }], complete: true, hydrating: false };
  const result = await readCollection(async () =>
    clock >= 6500 ? later : { items: rows, complete: false, hydrating: true }, {
    backoffWithChoices: true, now: () => clock, wait: async ms => { clock += ms; },
  });
  assert.equal(clock, 7500);
  assert.deepEqual(result, later);
});

test('a saved choice missing from a partial list keeps the normal polling cadence', async () => {
  const partial = { items: [{ id: 'other' }], complete: false, hydrating: true };
  const found = { ...partial, items: [{ id: 'saved' }] };
  const replies = [partial, partial, found];
  const waits = [];
  const result = await readCollection(async () => replies.shift(), {
    desired: 'saved', backoffWithChoices: true, wait: async ms => { waits.push(ms); },
  });
  assert.deepEqual(waits, [1500, 1500]);
  assert.deepEqual(result, found);
});

test('obsolete requests never publish their result after vehicle selection changes', async () => {
  const controller = new AbortController();
  let resolveRead, updates = 0;
  const read = readCollection(() => new Promise(resolve => { resolveRead = resolve; }), { signal: controller.signal, onUpdate: () => updates++ });
  controller.abort(); resolveRead({ items: [{ id: 'old-vehicle' }], complete: true });
  await assert.rejects(read, { name: 'AbortError' }); assert.equal(updates, 0);
});

test('a saved choice can resume from a partially hydrated list', async () => {
  let calls = 0;
  const result = await readCollection(async () => { calls++; return { items: [{ id: 'saved' }], complete: false, hydrating: true }; }, { desired: 'saved' });
  assert.equal(calls, 1); assert.equal(result.complete, false);
});

test('transport errors, malformed payloads and authentication failures remain failures', async () => {
  await assert.rejects(readCollection(async () => ({ items: null })), /unreadable list/);
  await assert.rejects(requestJSON('/x', { fetcher: async () => new Response('{}', { status: 404 }) }), /could not be found/);
  await assert.rejects(requestJSON('/x', { fetcher: async () => new Response('{}', { status: 401 }) }), /cannot access/);
  await assert.rejects(requestJSON('/x', { fetcher: async () => new Response('invalid') }), /unreadable response/);
});

test('procedure order and illustrations are retained; empty legacy steps use full text', () => {
  const steps = [{ number: 9, heading: 'Remove', instructions: ['Keep original instruction'], image_ids: ['image-1'] }, { number: 2, instructions: ['Install'] }];
  assert.deepEqual(articlePresentation({ steps }).steps, steps);
  const old = articlePresentation({ steps: [{ number: 1, instructions: [] }], body: 'Retained full text' });
  assert.equal(old.legacy, true); assert.equal(old.body, 'Retained full text'); assert.deepEqual(old.steps, []);
  assert.deepEqual(articlePresentation({ steps: [steps[0], {}], body: 'All instructions' }).steps, []);
});

test('ordered document blocks are preferred over compatibility steps', () => {
  const presentation = articlePresentation({
    steps: [{ number: 1, instructions: ['legacy projection'] }],
    document: { blocks: [
      { type: 'heading', text: 'REMOVAL', source_order: 1 },
      { type: 'image', image_id: 'figure-1', source_order: 2 },
      { type: 'paragraph', text: 'Remove the seal.', source_order: 3 },
    ] },
  });
  assert.deepEqual(presentation.documentBlocks.map(block => block.type), ['heading', 'image', 'paragraph']);
  assert.deepEqual(presentation.steps, [{ number: 1, instructions: ['legacy projection'] }]);
  assert.deepEqual(presentation.blocks, []);
});

test('flattened legacy article text becomes ordered readable blocks', () => {
  const blocks = legacyArticleBlocks('SERVICE PROCEDURE 1.Remove the cover. 2.Install the gasket. NOTE: Tighten evenly.');
  assert.deepEqual(blocks.map(block => block.type), ['heading', 'step', 'step']);
  assert.equal(blocks[1].number, 1);
  assert.equal(blocks[1].parts[0].text, 'Remove the cover.');
  assert.equal(blocks[2].parts[0].text, 'Install the gasket.');
  assert.deepEqual(blocks[2].parts[1], { type: 'callout', label: 'NOTE', text: 'Tighten evenly.' });
  assert.deepEqual(legacyArticleBlocks('CIRCUIT DESCRIPTION If the ECU detects trouble.').map(block => block.type), ['heading', 'paragraph']);
});

test('article paragraph boundaries remain visible to the reader', () => {
  const blocks = legacyArticleBlocks('ACCELERATION TYPE\n\nRemote sensors are mounted in the vehicle.\n\nThey cannot be repaired.');
  assert.deepEqual(blocks.map(block => block.type), ['heading', 'paragraph', 'paragraph']);
  assert.equal(blocks[1].text, 'Remote sensors are mounted in the vehicle.');
  assert.equal(blocks[2].text, 'They cannot be repaired.');
});

test('legacy descriptions get readable paragraph breaks without changing text order', () => {
  const body = 'First sentence explains the system. Second sentence identifies the location. Third sentence describes the connector. Fourth sentence explains the service limit.';
  const blocks = legacyArticleBlocks(body);
  assert.deepEqual(blocks.map(block => block.type), ['paragraph', 'paragraph']);
  assert.equal(`${blocks[0].text} ${blocks[1].text}`, body);
});

test('image rendering does not contact original providers or accept script URLs', () => {
  assert.equal(localImageURL('/images/a.png', 'http://localhost:8080'), null);
  assert.equal(localImageURL('/v1/catalog/images/v2.opaque', 'http://localhost:8080'), 'http://localhost:8080/v1/catalog/images/v2.opaque');
  for (const url of ['https://provider.example/a.png', '//provider.example/a.png', 'javascript:alert(1)', 'data:image/svg+xml,<svg/>', 'artifact://missing']) assert.equal(localImageURL(url, 'http://localhost:8080'), null);
  assert.equal(localImageURL('data:image/png;base64,YQ==', 'http://localhost:8080', { compatibility: true }), 'data:image/png;base64,YQ==');
});

test('source references stay same-origin and retain evidence locator context', () => {
  const review = { url: '/v1/catalog/vehicles/v/articles/a/source' };
  const block = { evidence_ids: ['e-7'], source_locator: 'body[3]' };
  assert.equal(hasSourceReference(block), true);
  assert.equal(sourceReferenceURL(review, block), '/v1/catalog/vehicles/v/articles/a/source?evidence_id=e-7&source_locator=body%5B3%5D');
  assert.equal(sourceReferenceURL(review, { text: 'no evidence' }), null);
  assert.equal(sourceReferenceURL({ url: 'https://provider.example/source' }, block), null);
});

test('search matches all words without changing catalog order or IDs', () => {
  const articles = [{ id: 'one', title: 'Oil Pump Removal', kind: 'procedure' }, { id: 'two', title: 'Water Pump' }, { id: 'three', title: 'Oil Pump Installation' }];
  assert.deepEqual(filterArticles(articles, ' PUMP oil ').map(a => a.id), ['one', 'three']);
  assert.deepEqual(filterArticles(articles, ''), articles);
  assert.equal(configurationLabel({ engine: '2.0', trim: 'Base' }), '2.0 L / Base');
  assert.equal(configurationLabel({ engine: '2.0 L', trim: 'Sport' }), '2.0 L / Sport');
  assert.equal(configurationLabel({ engine: 'Hybrid' }), 'Hybrid');
  assert.equal(configurationLabel({ engine: '6.0', engine_variant: 'CNG', trim: 'Base' }), '6.0 L CNG / Base');
  assert.equal(configurationLabel({ engine_variant: 'LPG' }), 'LPG');
  assert.equal(configurationLabel({}), 'Base configuration');
});

const longArticleTitle = 'Rear axle (A+B) [R.*] alignment and torque specifications after replacing the right side drive shaft';

test('search switches to exact title beyond the protected keyword bounds', () => {
  const eight = 'one two three four five six seven eight';
  const nine = `${eight}\u0085nine`;
  assert.deepEqual(articleSearchParams(`\u0085${eight}\u00a0`), { q: eight });
  assert.deepEqual(articleSearchParams(nine), { title: nine });
  assert.deepEqual(articleSearchParams('𐐀'.repeat(120)), { q: '𐐀'.repeat(120) });
  assert.deepEqual(articleSearchParams('𐐀'.repeat(121)), { title: '𐐀'.repeat(121) });
  assert.deepEqual(articleSearchParams('𐐀'.repeat(1000)), { title: '𐐀'.repeat(1000) });
});

test('local exact title matching trims and folds the whole literal title', () => {
  const query = `ς ${longArticleTitle.toLowerCase()}`;
  const exact = { id: 'exact', title: `\u0085Σ ${longArticleTitle}\u00a0` };
  const extended = { id: 'extended', title: `${query} update` };
  const component = { id: 'component', title: 'Other article', component: query };
  const spacing = { id: 'spacing', title: query.replace('alignment and', 'alignment  and') };
  assert.deepEqual(filterArticles([extended, component, exact, spacing], ` ${query} `), [exact]);
});

const scope = { configuration_id: '11111111-1111-4111-8111-111111111111', region: 'US' };
const orderID = '22222222-2222-4222-8222-222222222222';
const quote = { version: 'v1', ...scope, product_key: 'workshop-configuration-v1', configuration_label: '2005 Toyota / 2.4L / US', amount_minor: 2000, currency: 'USD', purchase_terms_version: 'workshop-v1', purchasable: true };
test('quote requires server price and exact configuration/region', async () => {
  const { validQuote } = await import('./workshop/commerce.mjs');
  assert.equal(validQuote(quote, scope), true);
  for (const change of [{ amount_minor: 1 }, { region: 'CA' }, { purchase_terms_version: 'unknown' }, { configuration_id: orderID }, { purchasable: false }]) assert.equal(validQuote({ ...quote, ...change }, scope), false);
});
test('checkout URL validation preserves opaque fragment and rejects ambiguous hosts', async () => {
  const { hostedCheckoutURL } = await import('./workshop/commerce.mjs');
  const url = 'https://checkout.stripe.com/c/pay/cs_test_123#opaque%2Ffragment';
  assert.equal(hostedCheckoutURL(url), url);
  for (const value of ['https://checkout.stripe.com:443/c/pay/x', 'https://checkout.stripe.com.evil/c/pay/x', 'https://user@checkout.stripe.com/c/pay/x', 'https://checkout.stripe.com/c/pay/', 'https://checkout.stripe.com/c/pay/x\n', '//checkout.stripe.com/c/pay/x']) assert.equal(hostedCheckoutURL(value), null);
});
test('order discriminants cannot grant access or create automatic replacement', async () => {
  const { validOrder } = await import('./workshop/commerce.mjs');
  assert.equal(validOrder({ version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' }, orderID), true);
  assert.equal(validOrder({ version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'new_key' }, orderID), false);
});

function orderPollFixture(responses, options = {}) {
  let elapsed = 0;
  const reads = [];
  const updates = [];
  const result = pollOrder(orderID, {
    earlyCheckoutCheck: true,
    ...options,
    now: () => elapsed,
    async wait(duration, signal) {
      elapsed += duration;
      options.afterWait?.(elapsed);
      signal?.throwIfAborted();
    },
    async request(path, { signal, timeout, onResponseDate }) {
      assert.equal(path, `/v1/workshop/orders/${orderID}`);
      assert.equal(signal, options.signal);
      reads.push({ time: elapsed, timeout });
      const response = responses.shift();
      assert.notEqual(response, undefined, 'unexpected extra order read');
      if (response instanceof Error) {
        elapsed += response.elapsed || 0;
        throw response;
      }
      onResponseDate?.(options.responseDate ?? new Date().toUTCString());
      if (typeof response !== 'string') return response;
      return { version: 'v1', ...scope, order_id: orderID, state: response,
        retry_disposition: ['expired', 'canceled'].includes(response) ? 'new_key' : 'do_not_repay' };
    },
    onUpdate: order => updates.push(order.state),
  });
  return { result, reads, updates, times: () => reads.map(read => read.time) };
}

test('checkout return checks once at 350 ms after an ordinary pending response', async () => {
  for (const state of ['open', 'processing']) {
    const probe = orderPollFixture([state, 'paid']);
    const result = await probe.result;
    assert.deepEqual(probe.times(), [0, 350]);
    assert.equal(probe.reads[1].timeout, 650);
    assert.deepEqual(probe.updates, [state, 'paid']);
    assert.equal(result.state, 'paid');
    assert.equal(result.timedOut, false);
  }
});

test('a matching hosted checkout return can check early without moving either fallback', async () => {
  const returnedCheckout = { ...scope, order_id: orderID,
    provider_expires_at: new Date(Date.now() + 60_000).toISOString() };
  const timeout = Object.assign(new TypeError('Probe timed out'), { elapsed: 100 });
  const lateTimeout = Object.assign(new TypeError('Later check timed out'), { elapsed: 400 });
  const busy = Object.assign(new Error('Try again'), { status: 429, retryable: true, retryAfterSeconds: 2 });
  const resumable = {
    ...returnedCheckout, version: 'v1', state: 'open', retry_disposition: 'do_not_repay',
    checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_fixture',
  };
  const nearExpiry = {
    ...resumable, provider_expires_at: new Date(Date.now() + 1000).toISOString(),
  };
  for (const [label, responses, starts] of [
    ['early payment', ['open', 'paid'], [0, 250]],
    ['miss until the short fallback', ['open', 'processing', 'paid'], [0, 250, 350]],
    ['payment between the early and ordinary checks', ['open', 'open', 'processing', 'paid'], [0, 250, 350, 600]],
    ['a server-confirmed open checkout', ['open', 'open', resumable, 'paid'], [0, 250, 350, 600]],
    ['an open checkout near expiry on the server clock', ['open', 'open', nearExpiry, 'paid'], [0, 250, 350, 1000]],
    ['open without an active checkout link', ['open', 'open', 'open', 'paid'], [0, 250, 350, 1000]],
    ['miss until the regular fallback', ['open', 'open', 'processing', 'processing', 'paid'], [0, 250, 350, 600, 1000]],
    ['timeout at the short fallback', ['open', timeout, 'paid'], [0, 250, 350]],
    ['later check times out at the regular fallback', ['open', 'open', 'processing', lateTimeout, 'paid'], [0, 250, 350, 600, 1000]],
    ['overload', ['open', busy, 'paid'], [0, 250, 2250]],
    ['overload at the later check', ['open', 'processing', 'processing', busy, 'paid'], [0, 250, 350, 600, 2600]],
    ['provider reconciliation', ['open', 'reconciliation_required', 'paid'], [0, 250, 1250]],
    ['revoked', ['open', 'revoked'], [0, 250]],
  ]) {
    const probe = orderPollFixture(responses, { returnedCheckout });
    assert.equal((await probe.result).state, label === 'revoked' ? 'revoked' : 'paid', label);
    assert.deepEqual(probe.times(), starts, label);
    assert.equal(probe.reads[1].timeout, 100, label);
    if (starts.includes(600)) assert.equal(probe.reads[3].timeout, 400, label);
  }
});

test('the extra checkout return check requires current receipt scope and expiry', async () => {
  const returnedCheckout = { ...scope, order_id: orderID,
    provider_expires_at: new Date(Date.now() + 60_000).toISOString() };
  for (const [receipt, earlyCheckoutCheck] of [
    [{ ...returnedCheckout, order_id: scope.configuration_id }, true],
    [{ ...returnedCheckout, configuration_id: orderID }, true],
    [{ ...returnedCheckout, region: 'CA' }, true],
    [{ ...returnedCheckout, provider_expires_at: new Date(Date.now() + 500).toISOString() }, true],
    [{ ...returnedCheckout, provider_expires_at: 'invalid' }, true],
    [returnedCheckout, false],
  ]) {
    const probe = orderPollFixture(['open', 'paid'], { returnedCheckout: receipt, earlyCheckoutCheck });
    assert.equal((await probe.result).state, 'paid');
    assert.deepEqual(probe.times(), [0, earlyCheckoutCheck ? 350 : 1000]);
  }
});

test('checkout confirmation clean miss keeps the original schedule and adds one read', async () => {
  const probe = orderPollFixture(['open', 'open', 'processing', 'processing', 'paid']);
  assert.equal((await probe.result).state, 'paid');
  assert.deepEqual(probe.times(), [0, 350, 1000, 3000, 7000]);
});

test('ordinary order checks and reconciliation retain their first delay', async () => {
  for (const [state, earlyCheckoutCheck] of [['open', false], ['reconciliation_required', true], ['creating', true]]) {
    const probe = orderPollFixture([state, 'paid'], { earlyCheckoutCheck });
    assert.equal((await probe.result).state, 'paid');
    assert.deepEqual(probe.times(), [0, 1000]);
  }
});

test('checkout confirmation keeps terminal, invalid, and denied order responses terminal', async () => {
  for (const state of ['paid', 'expired', 'canceled', 'revoked']) {
    const probe = orderPollFixture([state]);
    assert.equal((await probe.result).state, state);
    assert.deepEqual(probe.times(), [0]);
  }
  const wrongOrder = { version: 'v1', ...scope, order_id: scope.configuration_id,
    state: 'open', retry_disposition: 'do_not_repay' };
  const wrong = orderPollFixture([wrongOrder]);
  await assert.rejects(wrong.result, /Payment status is unavailable/);
  assert.deepEqual(wrong.times(), [0]);
  const denied = orderPollFixture(['open', Object.assign(new Error('Order is unavailable'), { status: 404 })]);
  await assert.rejects(denied.result, /Order is unavailable/);
  assert.deepEqual(denied.times(), [0, 350]);
});

test('checkout confirmation respects failure backoff and retry hints', async () => {
  const retryable = (status, retryAfterSeconds) => Object.assign(new Error('Please retry'), { status, retryable: true, retryAfterSeconds });
  for (const [responses, times, outages] of [
    [[retryable(503, 2), 'open', 'paid'], [0, 2000, 4000], 1],
    [['open', retryable(429, 3), 'paid'], [0, 350, 3350], 1],
    [['open', retryable(503), 'paid'], [0, 350, 1350], 1],
    [['open', retryable(503), 'open', retryable(503), 'paid'], [0, 350, 1350, 3350, 7350], 2],
    [['open', 'reconciliation_required', 'paid'], [0, 350, 1350], 0],
    [['open', new TypeError('network unavailable'), 'paid'], [0, 350, 1000], 0],
  ]) {
    let announced = 0;
    const probe = orderPollFixture(responses, { onUnavailable: () => announced++ });
    assert.equal((await probe.result).state, 'paid');
    assert.deepEqual(probe.times(), times);
    assert.equal(announced, outages);
  }
});

test('checkout confirmation respects cancellation and absolute budget', async () => {
  const controller = new AbortController();
  const aborted = orderPollFixture(['open'], { signal: controller.signal, afterWait: () => controller.abort() });
  await assert.rejects(aborted.result, { name: 'AbortError' });
  assert.deepEqual(aborted.times(), [0]);
  const short = orderPollFixture(['open'], { budgetMs: 900 });
  assert.equal((await short.result).timedOut, true);
  assert.deepEqual(short.reads, [{ time: 0, timeout: 900 }]);
  const tight = orderPollFixture(['open', 'open', 'open'], { budgetMs: 1100 });
  assert.equal((await tight.result).timedOut, true);
  assert.deepEqual(tight.reads, [{ time: 0, timeout: 1100 }, { time: 350, timeout: 650 }, { time: 1000, timeout: 100 }]);
});

test('library requires nullable cursor and accepts revoked never-granted tombstone', async () => {
  const { validLibrary } = await import('./workshop/commerce.mjs');
  const item = { ...scope, library_item_id: orderID, label: 'Vehicle', access_state: 'revoked', granted_at: null };
  for (const next_cursor of [null, '', 'opaque+/=']) assert.equal(validLibrary({ version: 'v1', items: [item], next_cursor }), true);
  for (const bad of [{ version: 'v1', items: [] }, { version: 'v1', items: [], next_cursor: 4 }, { version: 'v1', items: [{ ...item, access_state: 'paid' }], next_cursor: null }]) assert.equal(validLibrary(bad), false);
});
test('library accepts a confirmed empty catalog for an owned available configuration', async () => {
  const { validLibrary } = await import('./workshop/commerce.mjs');
  const item = { ...scope, library_item_id: orderID, label: 'Vehicle', access_state: 'paid',
    granted_at: '2026-11-16T00:00:00Z', catalog_empty: true };
  const valid = item => validLibrary({ version: 'v1', items: [item], next_cursor: null });
  assert.equal(valid(item), true);
  for (const access_state of ['preparing', 'viewable', 'revoked']) {
    assert.equal(valid({ ...item, access_state }), false);
  }
  for (const value of [false, null, 'true']) assert.equal(valid({ ...item, catalog_empty: value }), false);
  assert.equal(valid({ ...item, catalog_available: false }), false);
});
test('checkout attempt shares one in-flight request and retries the same key/body', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const values = new Map(), calls = []; let release;
  const storage = { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
  const checkout = createCheckout({ storage, uuid: () => orderID, request: (path, options) => { calls.push(options); return new Promise(resolve => { release = resolve; }); } });
  const a = checkout.start(scope, 'csrf'); const b = checkout.start(scope, 'csrf');
  assert.equal(calls.length, 1);
  release({ version: 'v1', ...scope, order_id: orderID, state: 'processing' });
  await Promise.all([a,b]);
  const c = checkout.start(scope, 'fresh-csrf');
  release({ version: 'v1', ...scope, order_id: orderID, state: 'processing' }); await c;
  assert.equal(calls[0].headers['Idempotency-Key'], calls[1].headers['Idempotency-Key']);
  assert.deepEqual(calls[0].body, calls[1].body);
  assert.ok(![...values.values()].join('').includes('csrf'));
});
test('main Workshop simulation sends an explicit mode and refuses a Stripe redirect', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const calls = [];
  const checkout = createCheckout({ uuid: () => orderID, request: async (path, options) => {
    calls.push([path, options.body]);
    return calls.length === 1
      ? { version: 'v1', ...scope, order_id: orderID, state: 'owned', library_item_id: orderID }
      : { version: 'v1', ...scope, order_id: orderID, state: 'checkout',
          checkout_url: 'https://checkout.stripe.com/c/pay/test', provider_expires_at: '2027-01-01T00:00:00Z' };
  } });
  assert.equal((await checkout.start(scope, 'csrf', { mode: 'simulation' })).state, 'owned');
  await assert.rejects(checkout.start(scope, 'csrf', { mode: 'simulation' }), /Purchase status is unavailable/);
  assert.deepEqual(calls.map(([path, body]) => [path, body.expected_mode]), [
    ['/v1/workshop/checkout-sessions', 'simulation'], ['/v1/workshop/checkout-sessions', 'simulation'],
  ]);
});

test('banner-bearing test tab asserts test mode on each checkout request', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const calls = [];
  const storage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
  const checkout = createCheckout({ expectedMode: 'stripe_test', storage, uuid: () => orderID,
    request: async (path, options) => { calls.push([path, options]); return { version: 'v1', ...scope, order_id: orderID, state: 'processing' }; } });
  await checkout.start(scope, 'csrf');
  await checkout.start(scope, 'csrf');
  assert.equal(calls.length, 2);
  for (const [path, options] of calls) {
    assert.equal(path, '/v1/workshop/checkout-sessions');
    assert.equal(options.body.expected_mode, 'stripe_test');
  }
});
test('checkout attempt for a new configuration or region waits and uses its own response and key', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  for (const nextScope of [
    { configuration_id: '55555555-5555-4555-8555-555555555555', region: 'US' },
    { ...scope, region: 'CA' },
  ]) {
    const nextOrder = '88888888-8888-4888-8888-888888888888';
    const keys = ['66666666-6666-4666-8666-666666666666', '77777777-7777-4777-8777-777777777777'];
    const values = new Map(), calls = [], releases = [];
    const storage = { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
    const checkout = createCheckout({ storage, uuid: () => keys.shift(), request: (_path, options) => {
      calls.push(options);
      return new Promise(resolve => releases.push(resolve));
    } });
    const first = checkout.start(scope, 'csrf');
    const second = checkout.start(nextScope, 'csrf');
    assert.notStrictEqual(second, first);
    assert.equal(calls.length, 1);
    releases[0]({ version: 'v1', ...scope, order_id: orderID, state: 'processing' });
    const firstResult = await first;
    assert.equal(firstResult.configuration_id, scope.configuration_id);
    assert.equal(firstResult.region, scope.region);
    await new Promise(setImmediate);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].body.configuration_id, nextScope.configuration_id);
    assert.equal(calls[1].body.region, nextScope.region);
    assert.notEqual(calls[0].headers['Idempotency-Key'], calls[1].headers['Idempotency-Key']);
    releases[1]({ version: 'v1', ...nextScope, order_id: nextOrder, state: 'processing' });
    const result = await second;
    assert.equal(result.configuration_id, nextScope.configuration_id);
    assert.equal(result.region, nextScope.region);
    const savedAttempt = JSON.parse([...values.values()][0]);
    assert.equal(savedAttempt.configuration_id, nextScope.configuration_id);
    assert.equal(savedAttempt.region, nextScope.region);
  }
});
test('aborted queued checkout attempt does not send another vehicle request', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const nextScope = { configuration_id: '55555555-5555-4555-8555-555555555555', region: 'US' };
  const calls = []; let release;
  const storage = new Map();
  const checkout = createCheckout({ storage: {
    getItem: k => storage.get(k) ?? null,
    setItem: (k,v) => storage.set(k,v),
    removeItem: k => storage.delete(k),
  }, uuid: () => '66666666-6666-4666-8666-666666666666', request: (_path, options) => {
    calls.push(options);
    return new Promise(resolve => { release = resolve; });
  } });
  const first = checkout.start(scope, 'csrf');
  const controller = new AbortController();
  const queued = checkout.start(nextScope, 'csrf', { signal: controller.signal });
  controller.abort();
  release({ version: 'v1', ...scope, order_id: orderID, state: 'processing' });
  await first;
  await assert.rejects(queued, { name: 'AbortError' });
  assert.equal(calls.length, 1);
});
test('checkout attempt restarts same vehicle after the old navigation aborts', async () => {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const values = new Map(), calls = [], releases = [];
  const checkout = createCheckout({ storage: {
    getItem: k => values.get(k) ?? null,
    setItem: (k,v) => values.set(k,v),
    removeItem: k => values.delete(k),
  }, uuid: () => '66666666-6666-4666-8666-666666666666', request: (_path, options) => {
    calls.push(options);
    return new Promise(resolve => releases.push(resolve));
  } });
  const old = new AbortController();
  const first = checkout.start(scope, 'csrf', { signal: old.signal });
  const firstRejected = assert.rejects(first, { name: 'AbortError' });
  old.abort();
  const replacement = checkout.start(scope, 'fresh-csrf', { signal: new AbortController().signal });
  releases[0]({ version: 'v1', ...scope, order_id: orderID, state: 'processing' });
  await firstRejected;
  await new Promise(setImmediate);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].headers['Idempotency-Key'], calls[1].headers['Idempotency-Key']);
  releases[1]({ version: 'v1', ...scope, order_id: orderID, state: 'processing' });
  assert.equal((await replacement).order_id, orderID);
});
test('reader is sequential, retains source during transient failure and stops at terminal canonical', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const updates = [], waits = []; let now = 0, calls = 0;
  const versions = [{ status: 200, data: { article: { body: 'source', processing: { job_id: 'job', state: 'fetching' } } } }, new TypeError('network'), { status: 200, data: { article: { document: { blocks: [{ type: 'paragraph', text: 'canonical' }] }, processing: { job_id: 'job', state: 'completed' } } } }];
  const result = await readArticle(async () => { calls++; const value=versions.shift();if(value instanceof Error)throw value;return value; }, { now: () => now, wait: async ms => { waits.push(ms);now += ms; }, onUpdate: r => updates.push(r.data.article) });
  assert.equal(calls,3);assert.equal(updates.length,2);assert.deepEqual(waits,[1000,2000]);assert.equal(result.timedOut,false);
});
test('reader shows pinned stored source while the rewrite is waiting for its model', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const article = {
    body: 'Stored fixture source.',
    content_origin: 'source',
    source_revision_id: 'fixture-source',
    processing: { job_id: 'fixture-job', state: 'failed', retryable: true, error_code: 'MODEL_NOT_CONFIGURED' },
  };
  let reads = 0;
  const result = await readArticle(async () => {
    reads++;
    return { status: 200, data: { article } };
  }, { wait: async () => assert.fail('readable source must stop polling while its model is unavailable') });
  assert.equal(reads, 1);
  assert.equal(result.data.article, article);
  assert.equal(result.timedOut, false);
  assert.equal(processingArticle({ ...article, source_revision_id: null }), true);
  assert.equal(processingArticle({
    ...article, processing: { ...article.processing, error_code: 'CAPTURE_DEADLINE' },
  }), true);
});
test('reader offers one early cold confirmation and keeps the regular second check', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const pending = {
    status: 202,
    retryAfterSeconds: 1,
    data: { article: { processing: { job_id: 'same-job', state: 'fetching_source' } } },
  };
  const complete = { status: 200, data: { article: { body: 'Published procedure' } } };
  for (const [name, middle, expected] of [
    ['source takes a second longer', [pending, pending], [1000, 1000, 2000]],
    ['change of job', [{ ...pending, data: { article: { processing: { job_id: 'new-job', state: 'queued' } } } }], [1000, 2000]],
    ['retryable overload', [Object.assign(new Error('service busy'), { status: 503, retryable: true, retryAfterSeconds: 7 })], [1000, 7000]],
    ['readable source', [{ status: 200, retryAfterSeconds: 2, data: { article: {
      body: 'Stored procedure', processing: { job_id: 'same-job', state: 'rewriting' },
    } } }], [1000, 2000]],
  ]) {
    let now = 0;
    const responses = [pending, ...middle, complete], waits = [];
    const result = await readArticle(async () => {
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    }, { now: () => now, wait: async ms => { waits.push(ms); now += ms; } });
    assert.deepEqual(waits, expected, name);
    assert.equal(result.data.article.body, 'Published procedure', name);
  }
});
test('reader counts time spent preparing toward the first short source check', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const pending = { status: 202, shortSourceCheck: true, data: {
    article: { processing: { job_id: 'job', state: 'fetching_source' } },
  } };
  const replacement = { ...pending, data: {
    article: { processing: { job_id: 'replacement', state: 'fetching_source' } },
  } };
  const timedOut = Symbol('advanced response timed out');
  const stored = { status: 200, data: { article: { body: 'Stored procedure' } } };
  for (const [elapsed, initial, replies, expected] of [
    [49, pending, [stored], [49, 199]],
    [50, pending, [stored], [50, 150]],
    [74, pending, [stored], [74, 150]],
    [95, pending, [pending, stored], [95, 150, 245]],
    [95, pending, [replacement, stored], [95, 150, 245]],
    [95, pending, [timedOut, stored], [95, 150, 245]],
    [175, pending, [pending, stored], [175, 175, 325]],
    [95, { ...pending, retryAfterSeconds: 3 }, [stored], [95, 3095]],
  ]) {
    let now = elapsed;
    const starts = [];
    const responses = [initial, ...replies];
    const result = await readArticle(async ({ timeout, readableBodyTimeout }) => {
      starts.push(now);
      const response = responses.shift();
      if (response === timedOut) {
        assert.equal(timeout, 95);
        assert.equal(readableBodyTimeout, 95);
        now += timeout;
        throw new TypeError('Probe timed out');
      }
      return response;
    }, { initialReadStartedAt: 0, now: () => now, wait: async ms => { now += ms; } });
    assert.deepEqual(starts, expected);
    assert.equal(result.data.article.body, 'Stored procedure');
  }
});

test('reader checks negotiated cold source early and preserves scheduled reads on a miss', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const prepare = { status: 202, shortSourceCheck: true, data: {
    article: { processing: { job_id: 'job', state: 'queued' } },
  } };
  const pending = { status: 202, retryAfterSeconds: 1, data: prepare.data };
  const fetching = { ...prepare, data: { article: { processing: { job_id: 'job', state: 'fetching_source' } } } };
  const stored = { status: 200, retryAfterSeconds: 1, data: { article: {
    body: 'Stored procedure', content_origin: 'source', processing: { job_id: 'job', state: 'rewriting' },
  } } };
  const complete = { status: 200, data: { article: { body: 'Published procedure' } } };
  const overload = Object.assign(new Error('Busy'), { status: 429, retryable: true, retryAfterSeconds: 5 });
  const unhintedOverload = Object.assign(new Error('Busy'), { status: 503, retryable: true });
  const invalidResponse = Object.assign(new Error('Unreadable reply'), { code: 'INVALID_RESPONSE' });
  const networkFailure = new TypeError('Network failed');
  const timedOut = Symbol('timed out');
  const delayedFetching = Symbol('fetching response after the third probe slot');

  for (const [label, responses, expectedStarts] of [
    ['source ready before the original first probe', [prepare, stored, complete], [0, 150, 1150]],
    ['initial timeout preserves the original first probe', [prepare, timedOut, stored, complete], [0, 150, 250, 1250]],
    ['initial transient catalog failure preserves the original first probe', [prepare, unhintedOverload, stored, complete], [0, 150, 250, 1250]],
    ['initial unreadable reply preserves the original first probe', [prepare, invalidResponse, stored, complete], [0, 150, 250, 1250]],
    ['initial overload respects a retry hint', [prepare, overload, complete], [0, 150, 5150]],
    ['initial failure honors server retry hint', [prepare, pending, stored, complete], [0, 150, 1150, 2150]],
    ['source ready at the original first probe', [prepare, stored, complete], [0, 250, 1250]],
    ['source ready at second probe', [prepare, prepare, stored, complete], [0, 250, 500, 1500]],
    ['active capture can finish before the half-second slot', [prepare, fetching, stored, complete], [0, 250, 375, 1375]],
    ['active capture still pending at the extra check', [prepare, fetching, fetching, fetching, stored, complete], [0, 250, 375, 500, 750, 1750]],
    ['extra check timeout preserves the remaining reads', [prepare, fetching, timedOut, fetching, stored, complete], [0, 250, 375, 500, 750, 1750]],
    ['extra check honors server retry hint', [prepare, fetching, pending, complete], [0, 250, 375, 1375]],
    ['extra check honors overload', [prepare, fetching, overload, complete], [0, 250, 375, 5375]],
    ['a replacement job at the extra check rejoins the regular cadence',
      [prepare, fetching, { ...fetching, data: { article: { processing: { job_id: 'next-job', state: 'fetching_source' } } } }, complete],
      [0, 250, 375, 1000]],
    ['source ready at third probe', [prepare, prepare, fetching, stored, complete], [0, 250, 500, 750, 1750]],
    ['pending at both probes', [prepare, prepare, prepare, pending, stored, complete], [0, 250, 500, 1000, 2000, 3000]],
    ['third miss retains the ordinary read', [prepare, prepare, fetching, fetching, complete], [0, 250, 500, 750, 1000]],
    ['a slow second response rejoins the ordinary read', [prepare, prepare, delayedFetching, complete], [0, 250, 500, 1000]],
    ['same capture finishes just after the ordinary read',
      [prepare, fetching, fetching, fetching, fetching, fetching, stored, complete], [0, 250, 375, 500, 750, 1000, 1250, 2250]],
    ['late miss retains the next ordinary read',
      [prepare, fetching, fetching, fetching, fetching, fetching, fetching, complete], [0, 250, 375, 500, 750, 1000, 1250, 2000]],
    ['late timeout retains the next ordinary read',
      [prepare, fetching, fetching, fetching, fetching, fetching, timedOut, complete], [0, 250, 375, 500, 750, 1000, 1250, 2000]],
    ['late check honors overload',
      [prepare, fetching, fetching, fetching, fetching, fetching, overload, complete], [0, 250, 375, 500, 750, 1000, 1250, 6250]],
    ['ordinary read with explicit delay cannot add a late check',
      [prepare, fetching, fetching, fetching, fetching, { ...fetching, retryAfterSeconds: 4 }, complete], [0, 250, 375, 500, 750, 1000, 5000]],
    ['third probe honors overload', [prepare, prepare, fetching, overload, complete], [0, 250, 500, 750, 5750]],
    ['retry hint at first probe', [prepare, pending, pending, stored, complete], [0, 250, 1250, 2250, 3250]],
    ['retry hint at second probe', [prepare, prepare, pending, complete], [0, 250, 500, 1500]],
    ['network failure at first probe', [prepare, networkFailure, stored, complete], [0, 250, 500, 1500]],
    ['network failure at first probe prevents a third', [prepare, networkFailure, fetching, complete], [0, 250, 500, 1000]],
    ['network failure at second probe prevents a third', [prepare, prepare, networkFailure, complete], [0, 250, 500, 1000]],
    ['first probe cannot delay second probe', [prepare, timedOut, stored, complete], [0, 250, 500, 1500]],
    ['overload applies to subsequent reads', [prepare, overload, pending, complete], [0, 250, 5250, 6250]],
    ['overload without a hint skips the second probe', [prepare, unhintedOverload, complete], [0, 250, 1000]],
    ['a replacement job rejoins the regular check', [prepare, { ...prepare, data: { article: { processing: { job_id: 'next-job', state: 'queued' } } } }, complete], [0, 250, 1000]],
    ['a replacement job at the second probe prevents a third', [prepare, prepare, { ...prepare, data: { article: { processing: { job_id: 'next-job', state: 'fetching_source' } } } }, complete], [0, 250, 500, 1000]],
    ['explicit wait overrides the preference', [{ ...prepare, retryAfterSeconds: 4 }, complete], [0, 4000]],
  ]) {
    let now = 0;
    const actual = [];
    const addsPendingInitialCheck = responses[0] === prepare && expectedStarts[1] !== 150;
    const queuedResponses = addsPendingInitialCheck ? [prepare, ...responses] : responses;
    const expected = addsPendingInitialCheck ? [0, 150, ...expectedStarts.slice(1)] : expectedStarts;
    const result = await readArticle(async ({ timeout, readableBodyTimeout, preferShortSourceCheck }) => {
      actual.push(now);
      const headerBudget = { 150: 100, 250: 250, 375: 125, 500: 500, 750: 250 };
      const bodyBudget = { 150: 850, 250: 750, 375: 625, 500: 750, 750: 500 };
      const confirmedAtOrdinaryRead = now === 1000 && [
        'third miss retains the ordinary read',
        'a slow second response rejoins the ordinary read',
        'same capture finishes just after the ordinary read',
        'late miss retains the next ordinary read',
        'late timeout retains the next ordinary read',
        'late check honors overload',
        'ordinary read with explicit delay cannot add a late check',
      ].includes(label);
      const late = now === 1250 && expectedStarts.includes(750) && expectedStarts.includes(1000);
      assert.equal(preferShortSourceCheck, now in headerBudget || confirmedAtOrdinaryRead || late, label);
      if (now in headerBudget) assert.equal(timeout, headerBudget[now], label);
      if (late) assert.equal(timeout, 750, label);
      assert.equal(readableBodyTimeout, late ? 1000 : bodyBudget[now], label);
      const next = queuedResponses.shift();
      if (next === timedOut) {
        now += timeout;
        throw networkFailure;
      }
      if (next === delayedFetching) {
        now += 300;
        return fetching;
      }
      if (next instanceof Error) throw next;
      return next;
    }, { now: () => now, wait: async ms => { now += ms; } });
    assert.deepEqual(actual, expected, label);
    assert.equal(result.data.article.body, 'Published procedure', label);
  }
});
test('reader credits time spent awaiting the prepared response before polling', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const prepared = { status: 202, shortSourceCheck: true, data: {
    article: { processing: { job_id: 'job', state: 'queued' } },
  } };
  const complete = { status: 200, data: { article: { body: 'Stored procedure' } } };
  const stalledBody = Symbol('stalled body');
  for (const [elapsed, responses, expectedStarts] of [
    [12, [prepared, complete], [12, 162]],
    [150, [prepared, complete], [150, 150]],
    [164, [prepared, prepared, complete], [164, 164, 314]],
    [164, [prepared, stalledBody, complete], [164, 164, 314]],
    [164, [prepared, prepared, prepared, complete], [164, 164, 314, 414]],
    [164, [prepared, { ...prepared, retryAfterSeconds: 2 }, complete], [164, 164, 2164]],
    [164, [{ ...prepared, retryAfterSeconds: 2 }, complete], [164, 2164]],
  ]) {
    let now = elapsed;
    const starts = [];
    const result = await readArticle(async ({ readableBodyTimeout }) => {
      starts.push(now);
      const next = responses.shift();
      assert.ok(next);
      if (next === stalledBody) {
        now += readableBodyTimeout;
        throw new TypeError('The response body did not arrive');
      }
      return next;
    }, {
      initialReadStartedAt: 0,
      now: () => now,
      wait: async (milliseconds) => { now += milliseconds; },
    });
    assert.deepEqual(starts, expectedStarts);
    assert.equal(result.data.article.body, 'Stored procedure');
  }
});
test('reader checks an active, slow first capture without delaying its regular read', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  for (const [sourceReadyAt, expectedVisibleAt, expectedLateStarts] of [
    [5056, 5622, [5502]],
    [5950, 6622, [5502, 6502]],
    [7800, 8622, [5502, 6502, 8502]],
    [9700, 10742, [5502, 6502, 8502, 10622]],
    [11600, 12742, [5502, 6502, 8502, 10622, 12622]],
  ]) {
    let now = 142;
    let visibleAt;
    const lateStarts = [];
    await readArticle(async ({ preferShortSourceCheck, timeout, readableBodyTimeout }) => {
      const initial = now === 142;
      if (now > 5000 && visibleAt === undefined) lateStarts.push(now);
      if (now === 5502 || now === 10622) {
        const budget = now === 5502 ? 1000 : 2000;
        assert.equal(timeout, budget);
        assert.equal(readableBodyTimeout, budget);
        assert.equal(preferShortSourceCheck, true);
      }
      if (now === 6502) assert.equal(timeout, 2000);
      if (!initial) now += 120;
      if (visibleAt !== undefined) return { status: 200, data: { article: { body: 'Published article' } } };
      const processing = { job_id: 'job', state: initial ? 'queued' : 'fetching_source' };
      if (now >= sourceReadyAt) return { status: 200, retryAfterSeconds: 1, data: { article: {
        content_origin: 'source', body: 'Stored source preview', processing,
      } } };
      const short = initial || preferShortSourceCheck;
      return { status: 202, shortSourceCheck: short, retryAfterSeconds: short ? 0 : 1, data: { article: { processing } } };
    }, {
      initialReadStartedAt: 0,
      now: () => now,
      wait: async milliseconds => { now += milliseconds; },
      onUpdate(response) {
        if (response.data.article.content_origin === 'source') visibleAt = now;
      },
    });
    assert.equal(visibleAt, expectedVisibleAt);
    assert.deepEqual(lateStarts, expectedLateStarts);
  }
});

test('the added cold capture check keeps the midpoint, retry floor, and access denial', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const processing = { job_id: 'same-job', state: 'fetching_source' };
  const pending = { status: 202, retryAfterSeconds: 1, data: { article: { processing } } };
  const done = { status: 200, data: { article: { content_origin: 'source', body: 'Stored procedure' } } };
  const denied = Object.assign(new Error('Access revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const retry = Object.assign(new Error('Rate limited'), { status: 429, retryable: true, retryAfterSeconds: 4 });
  const invalid = Object.assign(new Error('Invalid response'), { code: 'INVALID_RESPONSE' });
  for (const [error, nextRead] of [[invalid, 6000], [new TypeError('Network error'), 6000], [retry, 9000], [denied, undefined]]) {
    let now = 0;
    const starts = [];
    const read = readArticle(async () => {
      starts.push(now);
      if (now === 5000) throw error;
      return now >= 5600 ? done : pending;
    }, { now: () => now, wait: async ms => { now += ms; } });
    if (nextRead === undefined) await assert.rejects(read, error);
    else assert.equal((await read).data.article.body, 'Stored procedure');
    assert.deepEqual(starts, [0, 1000, 2000, 4000, 5000, ...(nextRead === undefined ? [] : [nextRead])]);
  }
});

test('an opted-in readable preview gets one bounded check before its regular read', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const processing = { job_id: 'capture-job', state: 'fetching_source' };
  const pending = { status: 202, shortSourceCheck: true, data: { article: { processing } } };
  const preview = { status: 200, previewSourceCheck: true, data: { article: {
    content_origin: 'source', source_body_preview: true, source_revision_id: null, body: 'Readable preview', processing,
  } } };
  const stored = { status: 200, data: { article: {
    content_origin: 'source', source_revision_id: 'stored-revision', body: 'Stored source',
  } } };
  const busy = Object.assign(new Error('Too many requests'), { status: 429, retryable: true, retryAfterSeconds: 4 });
  const denied = Object.assign(new Error('Access revoked'), { status: 403 });
  for (const [label, firstPreview, early, expected] of [
    ['stored source ready', preview, stored, [0, 150, 400]],
    ['repeat preview', preview, preview, [0, 150, 400, 1150]],
    ['transient error', preview, new TypeError('Network failed'), [0, 150, 400, 1150]],
    ['rate limit', preview, busy, [0, 150, 400, 4400]],
    ['revoked grant', preview, denied, [0, 150, 400]],
    ['no negotiation', { ...preview, retryAfterSeconds: 1, previewSourceCheck: false }, null, [0, 150, 1150]],
    ['explicit hint', { ...preview, retryAfterSeconds: 3 }, null, [0, 150, 3150]],
  ]) {
    let now = 0;
    const starts = [], shown = [];
    const reading = readArticle(async (options) => {
      starts.push(now);
      if (now === 0) return pending;
      if (now === 150) return firstPreview;
      if (now === 400) {
        assert.equal(options.timeout, 750, label);
        assert.equal(options.readableBodyTimeout, 750, label);
        if (early instanceof Error) throw early;
        return early;
      }
      return stored;
    }, {
      now: () => now,
      wait: async ms => { now += ms; },
      onUpdate: response => shown.push(response.data.article.body),
    });
    if (early === denied) await assert.rejects(reading, denied);
    else assert.equal((await reading).data.article.source_revision_id, 'stored-revision', label);
    assert.equal(shown[1], 'Readable preview', label);
    assert.deepEqual(starts, expected, label);
  }
});

test('the preview source preference is offered on reads only', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  for (const method of ['GET', 'POST']) {
    const preference = 'workshop-preview-source-check';
    const response = await requestArticleJSON('/article', {
      method, preferShortSourceCheck: true, preferPreviewSourceCheck: true,
      fetcher: async (_, options) => {
        const expected = method === 'GET' ? `workshop-short-source-check, ${preference}` : 'workshop-short-source-check';
        assert.equal(options.headers.Prefer, expected);
        return new Response('{"article":{"id":"a"}}', { headers: { 'Preference-Applied': preference } });
      },
    });
    assert.equal(response.previewSourceCheck, method === 'GET' ? true : undefined);
  }
});

test('readable capture previews can show newer source before scheduled reads', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const processing = { job_id: 'job', state: 'fetching_source', retry_after_seconds: 1 };
  const wrapper = { status: 200, data: { article: {
    content_origin: 'source', source_body_preview: true, source_revision_id: null,
    view_revision: 'wrapper', document: { blocks: [{ type: 'paragraph', text: 'Attachment label.' }] }, processing,
  } } };
  const linked = { ...wrapper, data: { article: {
    ...wrapper.data.article, view_revision: 'linked',
    document: { blocks: [{ type: 'paragraph', text: 'Linked document text.' }] },
  } } };
  const original = { ...wrapper, data: { article: {
    ...linked.data.article, source_body_preview: false, source_revision_id: 'source',
    view_revision: 'original', processing: { ...processing, state: 'rewriting' },
  } } };
  const done = { ...original, data: { article: {
    ...original.data.article, view_revision: 'published', processing: { ...processing, state: 'completed' },
  } } };
  let now = 0;
  const starts = [], firstVisible = new Map();
  await readArticle(async (options) => {
    starts.push(now);
    if (now === 4000) {
      assert.equal(options.timeout, 1000);
      assert.equal(options.readableBodyTimeout, 1000);
    }
    if (now <= 3500) return wrapper;
    if (now === 5000 || now === 11000) {
      const budget = now === 5000 ? 2000 : 4000;
      assert.equal(options.timeout, budget);
      assert.equal(options.readableBodyTimeout, budget);
    }
    if (now <= 7100) return linked;
    if (now < 15000) return original;
    return done;
  }, {
    now: () => now, wait: async ms => { now += ms; },
    onUpdate(response) {
      const view = response.data.article.view_revision;
      if (!firstVisible.has(view)) firstVisible.set(view, now);
    },
  });
  assert.deepEqual(starts, [0, 1000, 3000, 4000, 5000, 7000, 11000, 15000]);
  assert.deepEqual([...firstVisible], [['wrapper', 0], ['linked', 4000], ['original', 11000], ['published', 15000]]);
});

test('a first capture preview at a midpoint preserves the scheduled Original read', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const pending = { status: 202, retryAfterSeconds: 1, data: { article: {
    processing: { job_id: 'job', state: 'fetching_source' },
  } } };
  const stored = { status: 200, data: { article: {
    content_origin: 'source', source_revision_id: 'revision', body: 'Stored Original',
  } } };
  const busy = Object.assign(new Error('Busy'), { status: 503, retryable: true, retryAfterSeconds: 4 });
  const slowDownload = Symbol('slow Original download');
  for (const [job, storedAt, confirmation, expectedStarts] of [
    ['job', 6900, null, [0, 1000, 2000, 4000, 5000, 6000, 7000]],
    ['job', 6900, slowDownload, [0, 1000, 2000, 4000, 5000, 6000, 7000]],
    ['job', 7800, null, [0, 1000, 2000, 4000, 5000, 6000, 7000, 8000]],
    ['job', 7800, busy, [0, 1000, 2000, 4000, 5000, 6000, 7000, 11000]],
    ['job', 10500, null, [0, 1000, 2000, 4000, 5000, 6000, 7000, 8000, 14000]],
    ['other-job', 7800, null, [0, 1000, 2000, 4000, 5000, 6000, 7000, 14000]],
  ]) {
    let now = 0;
    const starts = [], previews = [];
    const preview = { status: 200, retryAfterSeconds: 1, data: { article: {
      content_origin: 'source', source_body_preview: true, source_revision_id: null,
      body: 'Readable attachment preview', processing: { job_id: job, state: 'fetching_source' },
    } } };
    const result = await readArticle(async ({ timeout, readableBodyTimeout, preferShortSourceCheck }) => {
      starts.push(now);
      if (now === 7000 && job === 'job') {
        assert.equal(timeout, 7000);
        assert.equal(readableBodyTimeout, undefined);
        assert.equal(preferShortSourceCheck, false);
        if (confirmation === slowDownload) now += 1100;
        else if (confirmation) throw confirmation;
      }
      if (now >= storedAt) return stored;
      if (now < 5900) return pending;
      return preview;
    }, {
      now: () => now,
      wait: async milliseconds => { now += milliseconds; },
      onUpdate(response) {
        if (response.data.article.source_body_preview) previews.push(now);
      },
    });
    assert.equal(previews.at(0), 6000);
    assert.deepEqual(starts, expectedStarts);
    assert.equal(result.data.article.source_revision_id, 'revision');
  }
});

test('capture preview checks preserve retry floors, access errors and cancellation', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const article = {
    content_origin: 'source', source_body_preview: true, source_revision_id: null, body: 'Preview',
    processing: { job_id: 'job', state: 'fetching_source' },
  };
  const done = { status: 200, data: { article: { body: 'Stored procedure' } } };
  const busy = Object.assign(new Error('Busy'), { status: 503, retryable: true, retryAfterSeconds: 4 });
  const denied = Object.assign(new Error('Access revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const ordinary = [0, 1000, 3000, 7000, 15000, 25000];
  const probed = [0, 1000, 3000, 4000, 5000, 7000, 11000, 15000, 25000];
  for (const [label, data, retryAfterSeconds, outcome, starts] of [
    ['steady capture', article, 1, null, probed],
    ['transient transport failure', article, 1, new TypeError('Network failed'), probed],
    ['explicit retry floor', article, 1, busy, [0, 1000, 3000, 4000, 5000, 9000, 13000, 17000, 27000]],
    ['revoked grant', article, 1, denied, [0, 1000, 3000, 4000, 5000]],
    ['aborted preview check', article, 1, 'abort', [0, 1000, 3000, 4000, 5000]],
    ['no preview contract', { ...article, source_body_preview: undefined }, 1, null, ordinary],
    ['stored revision', { ...article, source_revision_id: 'source' }, 1, null, ordinary],
    ['no retry hint', article, 0, null, ordinary],
  ]) {
    let now = 0;
    const actual = [], shown = [];
    const controller = new AbortController();
    const reading = readArticle(async ({ signal }) => {
      assert.equal(signal, controller.signal);
      actual.push(now);
      if (now === 5000 && outcome instanceof Error) throw outcome;
      if (now === 5000 && outcome === 'abort') controller.abort();
      if (now >= 25000) return done;
      return { status: 200, retryAfterSeconds, data: { article: data } };
    }, {
      signal: controller.signal, now: () => now, wait: async ms => { now += ms; },
      onUpdate() { shown.push(now); },
    });
    if (outcome === 'abort' || outcome === denied) {
      await assert.rejects(reading, outcome === 'abort' ? { name: 'AbortError' } : denied);
      assert.deepEqual(shown, [0, 1000, 3000, 4000]);
    } else {
      assert.equal((await reading).data.article.body, 'Stored procedure', label);
    }
    assert.deepEqual(actual, starts, label);
  }
});

test('an active source preview checks for retained media during the longest backoff', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const preview = { status: 200, previewSourceCheck: true, data: { article: {
    content_origin: 'source', source_body_preview: true, source_revision_id: null,
    body: 'Readable source preview', processing: { job_id: 'job', state: 'fetching_source' },
  } } };
  const stored = { status: 200, data: { article: {
    content_origin: 'source', source_revision_id: 'revision',
    body: 'Stored procedure', images: [{ id: 'retained-figure' }],
  } } };
  const busier = Object.assign(new Error('Busy'), { status: 503, retryable: true, retryAfterSeconds: 7 });
  const initial = [0, 250, 1000, 3000, 4000, 5000, 7000, 11000, 15000];
  for (const [storedAt, probeError, lateReads] of [
    [15100, null, [20000]],
    [20100, null, [20000, 25000]],
    [15100, busier, [20000, 27000]],
  ]) {
    let now = 0;
    const reads = [], visible = [];
    const result = await readArticle(async ({ timeout, readableBodyTimeout }) => {
      reads.push(now);
      if (now === 20000) {
        assert.equal(timeout, 5000);
        assert.equal(readableBodyTimeout, 5000);
        if (probeError) throw probeError;
      }
      return now < storedAt ? preview : stored;
    }, {
      now: () => now, wait: async ms => { now += ms; },
      onUpdate(response) {
        if (response.data.article.images?.length) visible.push(now);
      },
    });
    assert.deepEqual(reads, [...initial, ...lateReads]);
    assert.deepEqual(visible, [lateReads.at(-1)]);
    assert.equal(result.data.article.source_revision_id, 'revision');
  }
});

test('reader confirms newly visible source once before resuming publication backoff', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const pending = { status: 202, retryAfterSeconds: 1, data: {
    article: { processing: { job_id: 'job', state: 'fetching_source' } },
  } };
  const stored = { status: 200, data: { article: {
    content_origin: 'source', body: 'Stored source',
    processing: { job_id: 'job', state: 'rewriting', retry_after_seconds: 1 },
  } } };
  const refresh = { status: 200, retryAfterSeconds: 2, data: { article: {
    ...stored.data.article, content_origin: 'canonical',
    processing: { job_id: 'job', state: 'rewriting' },
  } } };
  const complete = { status: 200, data: { article: { content_origin: 'canonical', body: 'Ready' } } };
  const overloaded = Object.assign(new Error('busy'), { status: 503, retryable: true, retryAfterSeconds: 7 });
  for (const [label, responsePrefix, expectedWaits] of [
    ['finish at the earlier probe', [pending, stored], [1000, 1000]],
    ['resume the regular second and third waits', [pending, stored, stored, stored], [1000, 1000, 1000, 4000]],
    ['one early probe even after several cold reads', [pending, pending, stored, stored, stored], [1000, 1000, 1000, 1000, 4000]],
    ['initially readable source needs no extra probe', [stored, stored, stored], [1000, 2000, 4000]],
    ['published refresh preserves its backoff', [refresh, refresh], [2000, 2000]],
    ['a longer HTTP hint takes precedence', [pending, { ...stored, retryAfterSeconds: 6 }], [1000, 6000]],
    ['overload on the early read honors the hint', [pending, stored, overloaded], [1000, 1000, 7000]],
    ['a transient error on the early read still makes the regular check', [pending, stored, new TypeError('network')], [1000, 1000, 1000]],
  ]) {
    let now = 0;
    const responses = [...responsePrefix, complete];
    const waits = [];
    const result = await readArticle(async () => {
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    }, { now: () => now, wait: async ms => { waits.push(ms); now += ms; } });
    assert.deepEqual(waits, expectedWaits, label);
    assert.equal(result.data.article.body, 'Ready', label);
    assert.equal(result.timedOut, false, label);
  }

  // The early confirmation cannot consume time reserved for the regular read.
  let now = 0;
  const starts = [];
  const responses = [pending, stored, overloaded, complete];
  await readArticle(async ({ timeout }) => {
    starts.push(now);
    const next = responses.shift();
    if (next === overloaded) {
      assert.equal(timeout, 1000);
      now += timeout;
      throw new TypeError('network');
    }
    return next;
  }, { now: () => now, wait: async ms => { now += ms; } });
  assert.deepEqual(starts, [0, 1000, 2000, 3000]);
});

test('reader checks for first publication early and preserves the regular read on a miss', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const pending = { status: 202, shortSourceCheck: true, data: {
    article: { processing: { job_id: 'job', state: 'queued' } },
  } };
  const source = { status: 200, shortPublicationCheck: true, data: {
    article: { body: 'Stored', content_origin: 'source', processing: { job_id: 'job', state: 'rewriting' } },
  } };
  const timed = { ...source, shortPublicationCheck: false, retryAfterSeconds: 1 };
  const changedJob = { ...source, data: {
    article: { ...source.data.article, processing: { ...source.data.article.processing, job_id: 'different-job' } },
  } };
  const ready = { status: 200, data: { article: { body: 'Published', content_origin: 'canonical' } } };
  const busy = Object.assign(new Error('Busy'), { status: 503, retryable: true, retryAfterSeconds: 7 });

  for (const [label, responses, expected] of [
    ['publication already ready for the probe', [pending, source, ready], [0, 150, 650]],
    ['publication ready after the first probe', [source, source, ready], [0, 500, 750]],
    ['regular read preserved', [pending, source, source, source, timed, ready], [0, 150, 650, 900, 1150, 2150]],
    ['initially readable article', [source, source, source, timed, ready], [0, 500, 750, 1000, 3000]],
    ['job changed during the first probe', [source, changedJob, ready], [0, 500, 1000]],
    ['short read no longer offered', [source, timed, ready], [0, 500, 1500]],
    ['first probe returned after the second probe would start', [source, source, ready], [0, 500, 1000]],
    ['network failure rejoins regular read', [source, new TypeError('Network failed'), ready], [0, 500, 1000]],
    ['second probe timeout rejoins regular read', [source, source, new TypeError('Network failed'), ready], [0, 500, 750, 1000]],
    ['overload wins over the regular read', [source, busy, ready], [0, 500, 7500]],
    ['second probe overload', [source, source, busy, ready], [0, 500, 750, 7750]],
    ['explicit server delay wins', [{ ...source, retryAfterSeconds: 6 }, ready], [0, 6000]],
  ]) {
    let now = 0;
    const starts = [], qualifiers = [];
    const result = await readArticle(async ({ timeout, preferShortPublicationCheck, finishPublishedBody, readableBodyTimeout }) => {
      starts.push(now);
      qualifiers.push(preferShortPublicationCheck);
      if (label === 'initially readable article') {
        assert.equal(Boolean(finishPublishedBody), now === 500 || now === 750);
        assert.equal(readableBodyTimeout, now === 500 || now === 750 ? 10000 : undefined);
      }
      const next = responses.shift();
      if (label === 'network failure rejoins regular read' && next instanceof TypeError) {
        assert.equal(timeout, 500);
        now += timeout;
      }
      if (label === 'second probe timeout rejoins regular read' && next instanceof TypeError) {
        assert.equal(timeout, 250);
        now += timeout;
      }
      if (label === 'first probe returned after the second probe would start' && now === 500) now += 300;
      if (next instanceof Error) throw next;
      return next;
    }, { now: () => now, wait: async ms => { now += ms; } });
    assert.deepEqual(starts, expected, label);
    assert.equal(qualifiers[0], true, label);
    if (label === 'initially readable article') assert.deepEqual(qualifiers, [true, true, true, false, false]);
    assert.equal(result.data.article.body, 'Published', label);
  }
});

test('a ready body gets the ordinary read time within the remaining reader budget', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  let now = 0;
  let reads = 0;
  const result = await readArticle(async (options) => {
    if (++reads === 1) {
      return { status: 200, shortPublicationCheck: true, data: {
        article: { body: 'Stored', content_origin: 'source', processing: { job_id: 'job', state: 'rewriting' } },
      } };
    }
    assert.equal(now, 500);
    assert.equal(options.timeout, 500);
    assert.equal(options.finishPublishedBody, true);
    assert.equal(options.readableBodyTimeout, 1500);
    now += 1200;
    return { status: 200, data: { article: { body: 'Published', content_origin: 'canonical' } } };
  }, { now: () => now, wait: async ms => { now += ms; }, budgetMs: 2000 });
  assert.equal(reads, 2);
  assert.equal(result.data.article.body, 'Published');
});

test('early publication reads keep the displayed source with a negotiated pending reply', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const article = {
    id: 'article', content_origin: 'source', source_revision_id: 'source', body: 'Stored',
    processing: { job_id: 'job', state: 'rewriting' },
  };
  const source = { status: 200, shortPublicationCheck: true, publicationCheckSupported: true, data: { article } };
  const ready = { status: 200, data: { article: { body: 'Published' } } };
  const pending = { status: 200, publicationStatus: true, data: {
    version: 'v1', article_id: 'article', job_id: 'job', source_revision_id: 'source', state: 'validating',
  } };
  const wrongSource = { ...pending, data: { ...pending.data, source_revision_id: 'other', retry_after_seconds: 6 } };
  const serverDelay = { ...pending, retryAfterSeconds: 6 };
  const changed = { ...source, shortPublicationCheck: false, data: {
    article: { ...article, body: 'New source', source_revision_id: 'new', processing: { job_id: 'new-job', state: 'validating' } },
  } };
  for (const [label, responses, expectedTimes, expectedUpdates] of [
    ['ready by the extra check', [source, ready], [0, 250], ['Stored', 'Published']],
    ['ready on the original first check', [source, pending, ready], [0, 250, 500], ['Stored', 'Published']],
    ['ready on the original second check', [source, pending, pending, ready], [0, 250, 500, 750], ['Stored', 'Published']],
    ['still processing', [source, pending, pending, pending, ready], [0, 250, 500, 750, 1000], ['Stored', 'Published']],
    ['mismatched extra reply preserves the original first check', [source, wrongSource, ready], [0, 250, 500], ['Stored', 'Published']],
    ['mismatched original reply', [source, pending, wrongSource, ready], [0, 250, 500, 1000], ['Stored', 'Published']],
    ['network failure preserves the original checks', [source, new TypeError('Network failed'), pending, ready], [0, 250, 500, 750], ['Stored', 'Published']],
    ['real server delay', [source, serverDelay, ready], [0, 250, 6250], ['Stored', 'Published']],
    ['changed source renders the full response', [source, pending, changed, ready], [0, 250, 500, 1000], ['Stored', 'New source', 'Published']],
  ]) {
    let now = 0;
    const starts = [], selected = [], rendered = [];
    const result = await readArticle(async (options) => {
      starts.push(now);
      if (now === 250 || now === 500 || now === 750) {
        assert.deepEqual(options.publicationCheck, { articleId: 'article', sourceRevisionId: 'source', jobId: 'job' }, label);
        assert.equal(options.finishPublishedBody, true, label);
        assert.equal(options.timeout, (now === 250 ? 500 : 1000) - now, label);
      } else {
        assert.equal(options.publicationCheck, undefined, label);
      }
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    }, {
      now: () => now, wait: async ms => { now += ms; },
      selectResponse(response) { selected.push(response.data.article.body); return response; },
      onUpdate(response) { rendered.push(response.data.article.body); },
    });
    assert.deepEqual(starts, expectedTimes, label);
    assert.deepEqual(selected, expectedUpdates, label);
    assert.deepEqual(rendered, expectedUpdates, label);
    assert.equal(result.data.article.body, 'Published', label);
  }
  const captureQueued = { status: 202, shortSourceCheck: true, data: {
    article: { processing: { job_id: 'job', state: 'queued' } },
  } };
  const responses = [captureQueued, source, pending, pending, pending, pending, ready];
  let now = 0;
  const optionsByRead = [];
  const result = await readArticle(async (options) => {
    optionsByRead.push({ time: now, check: options.publicationCheck, timeout: options.timeout });
    return responses.shift();
  }, { now: () => now, wait: async ms => { now += ms; } });
  assert.deepEqual(optionsByRead.map(({ time }) => time), [0, 150, 400, 650, 900, 1150, 2150]);
  assert.deepEqual(optionsByRead.filter(({ check }) => check).map(({ time, timeout }) => [time, timeout]),
    [[400, 250], [650, 500], [900, 250], [1150, 1000]]);
  assert.equal(result.data.article.body, 'Published');

  const controller = new AbortController();
  let reads = 0;
  await assert.rejects(readArticle(async () => {
    reads++;
    return source;
  }, {
    signal: controller.signal,
    wait: async (delay) => {
      assert.equal(delay, 250);
      controller.abort();
    },
  }), { name: 'AbortError' });
  assert.equal(reads, 1);
});

test('negotiated publication checks can open ready text and keep ordinary deadlines on a miss', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const source = {
    status: 200, publicationCheckSupported: true, data: { article: {
      id: 'article', content_origin: 'source', source_revision_id: 'source', body: 'Stored',
      processing: { job_id: 'job', state: 'rewriting' },
    } },
  };
  const ready = { status: 200, data: { article: { body: 'Published' } } };
  const compact = { status: 200, publicationStatus: true, data: {
    version: 'v1', article_id: 'article', job_id: 'job', source_revision_id: 'source', state: 'validating',
  } };
  const denied = Object.assign(new Error('Denied'), { status: 403 });
  const badJSON = Object.assign(new Error('Incomplete'), { code: 'INVALID_RESPONSE' });
  for (const [label, response, lastAt, expectedProbe] of [
    ['ready', ready, 5000, true],
    ['matching pending checks again in the long wait', compact, 15000, true],
    ['ready during the long wait', [compact, ready], 9000, true],
    ['late body timeout preserves the ordinary read', [compact, badJSON], 15000, true],
    ['changed source requires another confirmation', compact, 15000, true],
    ['retry hint', { ...compact, data: { ...compact.data, retry_after_seconds: 6 } }, 11000, true],
    ['mismatched anchor cannot supply a body retry hint', { ...compact, data: { ...compact.data, job_id: 'other', retry_after_seconds: 6 } }, 7000, true],
    ['network loss', new TypeError('Disconnected'), 7000, true],
    ['incomplete response', badJSON, 7000, true],
    ['full response fallback', source, 7000, true],
    ['access revoked', denied, 5000, true],
    ['old server', null, 7000, false],
    ['explicit source wait', 6, 9000, false],
  ]) {
    let now = 0;
    const starts = [], probes = [], shown = [];
    const result = readArticle(async (options) => {
      starts.push(now);
      if (options.publicationCheck) {
        probes.push(now);
        assert.deepEqual(options.publicationCheck, { articleId: 'article', sourceRevisionId: 'source', jobId: 'job' });
        assert.equal(options.timeout, 2000);
        assert.equal(options.readableBodyTimeout, probes.length === 1 ? 10000 : 6000);
        assert.equal(options.finishPublishedBody, true);
        const probeResponse = Array.isArray(response) ? response[probes.length - 1] : response;
        if (probeResponse instanceof Error) {
          if (probes.length === 2) now += options.readableBodyTimeout;
          throw probeResponse;
        }
        return probeResponse;
      }
      if (now === lastAt) return ready;
      if (label === 'changed source requires another confirmation' && now >= 7000) {
        return { ...source, data: { article: { ...source.data.article, source_revision_id: 'source-2' } } };
      }
      if (response === null) return { ...source, publicationCheckSupported: false };
      if (response === 6 && now === 3000) return { ...source, retryAfterSeconds: 6 };
      if (now === 0 || response === ready && now === 3000) return { ...source, retryAfterSeconds: 1 };
      return source;
    }, { now: () => now, wait: async ms => { now += ms; }, onUpdate: ({ data }) => shown.push(data.article.body) });
    if (response === denied) await assert.rejects(result, error => error === denied);
    else assert.equal((await result).data.article.body, 'Published');
    const lateProbe = Array.isArray(response) || label === 'matching pending checks again in the long wait';
    assert.deepEqual(probes, lateProbe ? [5000, 9000] : expectedProbe ? [5000] : [], label);
    assert.equal(starts.at(-1), lastAt, label);
    assert.equal(shown.filter(item => item === 'Stored').length,
      lateProbe || label === 'full response fallback' || label === 'changed source requires another confirmation' ? 4 : 3,
      label);
  }
});

test('article transport negotiates publication status with exact retained source and job headers', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const checked = await requestArticleJSON('/article', {
    publicationCheck: { jobId: 'job', sourceRevisionId: 'source' },
    finishPublishedBody: true,
    fetcher: async (url, { method, headers }) => {
      assert.equal(url, '/article');
      assert.equal(method, 'GET');
      assert.equal(headers.Prefer, 'workshop-finish-published-body, workshop-publication-status');
      assert.equal(headers['X-Workshop-Publication-Job'], 'job');
      assert.equal(headers['X-Workshop-Source-Revision'], 'source');
      return new Response(JSON.stringify({ version: 'v1', job_id: 'job' }), {
        headers: { 'Preference-Applied': 'workshop-publication-status', 'Retry-After': '4' },
      });
    },
  });
  assert.equal(checked.publicationStatus, true);
  assert.equal(checked.retryAfterSeconds, 4);
  await assert.rejects(requestArticleJSON('/article', {
    publicationCheck: { jobId: 'job', sourceRevisionId: 'source' },
    fetcher: async () => new Response('{', { headers: { 'Retry-After': '12' } }),
  }), (error) => error.code === 'INVALID_RESPONSE' && error.retryAfterSeconds === 12);
  const offered = await requestArticleJSON('/article', {
    fetcher: async () => new Response(JSON.stringify({ article: {} }), {
      headers: { 'Workshop-Publication-Check': 'supported' },
    }),
  });
  assert.equal(offered.publicationCheckSupported, true);
});

test('only a confirmed published response can finish streaming past the early header deadline', async (t) => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const preference = 'workshop-finish-published-body';
  const deadlines = [];
  t.mock.method(AbortSignal, 'timeout', (duration) => {
    const controller = new AbortController();
    deadlines.push({ duration, controller });
    return controller.signal;
  });
  for (const [status, applied, hint, expire, aborted] of [
    [200, preference, '', 'short', false],
    [200, preference, '', 'body', true],
    [200, preference, '', 'navigation', true],
    [200, 'workshop-short-publication-check', '', 'short', true],
    [200, '', '', 'short', true],
    [200, preference, '7', 'short', true],
    [202, preference, '', 'short', true],
  ]) {
    deadlines.length = 0;
    const navigation = new AbortController();
    const started = deferredAuthOperation();
    let release, requestSignal;
    const result = requestArticleJSON('/article', {
      timeout: 500, readableBodyTimeout: 1000, finishPublishedBody: true,
      preferShortPublicationCheck: true, signal: navigation.signal,
      fetcher: async (_url, { signal, headers }) => {
        assert.equal(headers.Prefer, `workshop-short-publication-check, ${preference}`);
        requestSignal = signal;
        return {
          status, ok: true, headers: new Headers({
            ...(applied ? { 'Preference-Applied': applied } : {}),
            ...(hint ? { 'Retry-After': hint } : {}),
          }),
          json: () => new Promise((resolve, reject) => {
            release = resolve;
            signal.addEventListener('abort', () => reject(signal.reason), { once: true });
            started.resolve();
          }),
        };
      },
    });
    const outcome = result.catch(error => error);
    await Promise.race([started.promise, outcome.then(error => { throw error; })]);
    assert.deepEqual(deadlines.map(({ duration }) => duration), [500, 1000]);
    if (expire === 'navigation') navigation.abort(new Error('Scope changed'));
    else deadlines[expire === 'short' ? 0 : 1].controller.abort();
    assert.equal(requestSignal.aborted, aborted);
    if (!aborted) release({ article: { body: 'Published' } });
    if (expire === 'navigation') assert.equal(await outcome, navigation.signal.reason);
    else if (aborted) assert.equal((await outcome).code, 'NETWORK_UNAVAILABLE');
    else assert.equal((await outcome).data.article.body, 'Published');
  }
});

test('an article body interrupted by its deadline remains retryable', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  await assert.rejects(requestArticleJSON('/article', {
    timeout: 10,
    fetcher: async (_url, { signal }) => ({
      status: 200, ok: true, headers: new Headers(),
      json: () => new Promise((_resolve, reject) => {
        const guard = setTimeout(() => reject(new Error('test timeout')), 500);
        signal.addEventListener('abort', () => {
          clearTimeout(guard);
          reject(signal.reason);
        }, { once: true });
      }),
    }),
  }), { code: 'NETWORK_UNAVAILABLE', retryable: true });
});
test('a short source read can finish a successful body by the regular deadline', async (t) => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const deadlines = [];
  t.mock.method(AbortSignal, 'timeout', (duration) => {
    const controller = new AbortController();
    deadlines.push({ duration, controller });
    return controller.signal;
  });
  for (const [status, expire, cancels, retryAfter] of [
    [200, 0, false],
    [202, 0, true],
    [undefined, 0, true],
    [200, 1, true],
    [200, 'navigation', true],
    [503, undefined, false, '7'],
    [503, 0, true, '7'],
    [503, 'navigation', true, '7'],
  ]) {
    deadlines.length = 0;
    const navigation = new AbortController();
    let release, requestSignal, started;
    const bodyStarted = new Promise(resolve => { started = resolve; });
    const waitForBody = () => new Promise((resolve, reject) => {
      requestSignal.addEventListener('abort', () => reject(requestSignal.reason), { once: true });
      release = resolve;
      started();
    });
    const response = requestArticleJSON('/article', {
      timeout: 250, readableBodyTimeout: 750, signal: navigation.signal,
      fetcher: async (_url, { signal }) => {
        requestSignal = signal;
        if (!status) return waitForBody();
        return {
          status, ok: status < 400, json: waitForBody,
          headers: new Headers(retryAfter ? { 'Retry-After': retryAfter } : {}),
        };
      },
    });
    await bodyStarted;
    assert.deepEqual(deadlines.map(({ duration }) => duration), [250, 750]);
    if (expire === 'navigation') navigation.abort(new Error('Scope changed'));
    else deadlines[expire]?.controller.abort();
    assert.equal(requestSignal.aborted, cancels);
    if (!cancels) release({ article: { body: 'Stored procedure' }, error: { retryable: true } });
    if (expire === 'navigation') await assert.rejects(response, navigation.signal.reason);
    else if (cancels) await assert.rejects(response, { code: 'NETWORK_UNAVAILABLE', retryable: true, retryAfterSeconds: retryAfter ? 7 : 0 });
    else if (retryAfter) await assert.rejects(response, { status: 503, retryAfterSeconds: 7, retryable: true });
    else assert.equal((await response).data.article.body, 'Stored procedure');
  }
});
test('reader retries failed jobs until canonical without losing source', async () => {
  const { readArticle, processingArticle, readableArticle } = await import('./workshop/article-read.mjs');
  let now = 0, reads = 0, inFlight = 0, maxInFlight = 0;
  const waits = [], updates = [];
  const source = {
    content_origin: 'source', body: 'Stored source remains readable',
    processing: { job_id: 'job', state: 'failed', retryable: true, retry_after_seconds: 3 },
  };
  const responses = [source,
    { ...source, processing: { job_id: 'job', state: 'queued' } },
    { ...source, processing: { job_id: 'job', state: 'rewriting' } },
    { content_origin: 'canonical', body: 'Published canonical', processing: { job_id: 'job', state: 'completed', retryable: false } },
  ];
  const result = await readArticle(async () => {
    reads++; inFlight++; maxInFlight = Math.max(maxInFlight, inFlight);
    try {
      await Promise.resolve();
      assert.ok(responses.length, 'must stop after canonical completion');
      return { status: 200, data: { article: responses.shift() } };
    } finally { inFlight--; }
  }, {
    now: () => now,
    wait: async ms => { waits.push(ms); now += ms; },
    onUpdate: response => updates.push(response.data.article),
  });
  assert.equal(processingArticle(source), true);
  assert.equal(reads, 4);
  assert.equal(maxInFlight, 1);
  assert.deepEqual(waits, [3000, 2000, 4000]);
  assert.equal(updates.length, 4);
  assert.ok(updates.slice(0, 3).every(readableArticle));
  assert.ok(updates.slice(0, 3).every(article => article.body === source.body));
  assert.equal(updates.filter(article => article.content_origin === 'canonical').length, 1);
  assert.equal(result.data.article.content_origin, 'canonical');
  assert.equal(result.timedOut, false);
});
test('reader keeps nonretryable failures and completed outcomes terminal', async () => {
  const { readArticle, processingArticle } = await import('./workshop/article-read.mjs');
  for (const processing of [
    { job_id: 'job', state: 'failed', retryable: false },
    { job_id: 'job', state: 'failed' },
    { job_id: 'job', state: 'failed', retryable: 'true' },
    ...['completed', 'needs_review', 'withdrawn'].map(state => ({ job_id: 'job', state, retryable: true })),
    { state: 'failed', retryable: true },
  ]) {
    const source = { content_origin: 'source', body: 'Retained source', processing };
    let reads = 0;
    const updates = [];
    const result = await readArticle(async () => {
      reads++;
      return { status: 200, data: { article: source } };
    }, {
      now: () => 0,
      wait: async () => assert.fail('terminal outcomes must not wait for another read'),
      onUpdate: response => updates.push(response.data.article),
    });
    assert.equal(processingArticle(source), false);
    assert.equal(reads, 1);
    assert.deepEqual(updates, [source]);
    assert.equal(result.data.article, source);
    assert.equal(result.timedOut, false);
  }
});
test('reader retains retryable failed source when the absolute budget expires', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const source = {
    content_origin: 'source', body: 'Retained source',
    processing: { job_id: 'job', state: 'failed', retryable: true, retry_after_seconds: 9 },
  };
  let now = 0, reads = 0;
  const waits = [], updates = [];
  const result = await readArticle(async () => {
    reads++;
    return { status: 200, data: { article: source } };
  }, {
    budgetMs: 5000, now: () => now,
    wait: async ms => { waits.push(ms); now += ms; },
    onUpdate: response => updates.push(response.data.article),
  });
  assert.equal(reads, 1);
  assert.equal(now, 5000);
  assert.deepEqual(waits, [5000]);
  assert.deepEqual(updates, [source]);
  assert.equal(result.data.article, source);
  assert.equal(result.timedOut, true);
});
test('reader navigation abort during retryable failure backoff prevents later reads and updates', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const navigation = new NavigationGeneration();
  const generation = navigation.next();
  const source = {
    content_origin: 'source', body: 'Retained source',
    processing: { job_id: 'job', state: 'failed', retryable: true, retry_after_seconds: 3 },
  };
  let reads = 0, waits = 0;
  const updates = [];
  await assert.rejects(readArticle(async () => {
    reads++;
    return { status: 200, data: { article: source } };
  }, {
    signal: generation.signal, now: () => 0,
    wait: async (ms, signal) => {
      waits++;
      assert.equal(ms, 3000);
      assert.equal(signal, generation.signal);
      navigation.clear();
      signal.throwIfAborted();
    },
    onUpdate: response => updates.push(response.data.article),
  }), { name: 'AbortError' });
  assert.equal(reads, 1);
  assert.equal(waits, 1);
  assert.deepEqual(updates, [source]);
  assert.equal(generation.current(), false);
  const later = navigation.next();
  assert.equal(later.current(), true);
  assert.equal(later.signal.aborted, false);
});
test('reader honors retry-after and absolute budget without extra request', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs'); let now=0,calls=0;
  const result = await readArticle(async () => {calls++;return {status:202,data:{article:{processing:{job_id:'job',state:'queued'}}},retryAfterSeconds:9};}, {budgetMs:5000,now:()=>now,wait:async ms=>{now+=ms;}});
  assert.equal(calls,1);assert.equal(now,5000);assert.equal(result.timedOut,true);
});
test('generation invalidation aborts every old callback', async () => {
  const { NavigationGeneration } = await import('./workshop/article-read.mjs');
  const g = new NavigationGeneration();const a=g.next();const b=g.next();assert.equal(a.signal.aborted,true);assert.equal(a.current(),false);assert.equal(b.current(),true);g.clear();assert.equal(b.current(),false);
});
test('initial session bootstrap consumes the prestarted account reads once', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  const config = { version: 'v1', mode: 'firebase', login_available: true, providers: ['google.com'],
    firebase: { apiKey: 'fixture', authDomain: 'fixture-project.firebaseapp.com', projectId: 'fixture-project', appId: '1:123:web:abc' } };
  const active = { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'initial-claim' };
  const requests = [];
  const account = createSession({ request: async path => {
    requests.push(path);
    return path === '/auth/config' ? config : { ...active, csrf_token: 'current-claim' };
  } });
  const initial = Promise.allSettled([Promise.resolve(config), Promise.resolve(active)]);
  await account.bootstrap({ initial });
  assert.deepEqual(requests, []);
  assert.equal(account.state.authenticated, true);
  assert.equal(account.state.csrf, 'initial-claim');
  await account.bootstrap();
  assert.deepEqual(requests, ['/auth/config', '/auth/session']);
  assert.equal(account.state.csrf, 'current-claim');
});

test('prestarted account results cannot reopen a canceled or signed-out session', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  const initial = deferredAuthOperation();
  const account = createSession({ request: async () => { throw new Error('unexpected duplicate account request'); } });
  const pending = account.bootstrap({ initial: initial.promise });
  account.clear();
  initial.resolve([
    { status: 'fulfilled', value: { mode: 'firebase' } },
    { status: 'fulfilled', value: { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'stale' } },
  ]);
  await pending;
  assert.equal(account.state.authenticated, false);
  assert.equal(account.state.csrf, '');
});

test('session bootstrap validates cookie authority and never loads SDK for existing session', async () => {
  const { createSession } = await import('./workshop/auth.mjs'); let sdkLoads=0;const calls=[];
  const session=createSession({request:async path=>{calls.push(path);return path==='/auth/config'?{version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'fixture',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123:web:abc'}}:{authenticated:true,roles:['dataset_viewer'],expires_at:'2099-01-01T00:00:00Z',csrf_token:'memory-only'};},loadSDK:async()=>{sdkLoads++;}});
  await session.bootstrap();assert.equal(session.state.authenticated,true);assert.equal(sdkLoads,0);assert.deepEqual(calls,['/auth/config','/auth/session']);
});
test('session validation starts while login configuration is in flight', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  let release;
  const calls = [];
  const session = createSession({
    request: async path => {
      calls.push(path);
      if (path === '/auth/config') return new Promise(resolve => { release = resolve; });
      return { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'fixture' };
    },
  });
  const pending = session.bootstrap();
  assert.deepEqual(calls, ['/auth/config', '/auth/session']);
  assert.equal(session.state.authenticated, false);
  release({ mode: 'local' });
  await pending;
  assert.equal(session.state.authenticated, true);
  assert.equal(session.state.mode, 'local');
});

test('a verified Firebase session opens before public login configuration and reuses it for sign-out', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  const settings = deferredAuthOperation();
  const calls = [];
  const sdk = {
    GoogleAuthProvider: class {},
    initializeApp: () => ({}), initializeAuth: () => ({}), setPersistence: async () => {},
  };
  const session = createSession({
    loadSDK: async () => { calls.push('sdk'); return sdk; },
    request: async (path, options) => {
      calls.push(path);
      if (path === '/auth/config') return settings.promise;
      if (path === '/auth/logout') {
        assert.equal(options.headers['X-CSRF-Token'], 'verified');
        return null;
      }
      assert.equal(path, '/auth/session');
      return { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z',
        csrf_token: 'verified', ...(options.headers?.Prefer === 'workshop-session-mode' ? { mode: 'firebase' } : {}) };
    },
  });
  const pending = session.bootstrap();
  try {
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(session.state.authenticated, true);
    assert.equal(session.state.mode, 'firebase');
    assert.equal(session.state.csrf, 'verified');
    assert.deepEqual(calls, ['/auth/config', '/auth/session']);
    const logout = session.logout();
    assert.equal(session.state.authenticated, false);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(session.state.message, 'Signed out.');
    assert.equal(session.state.ready, false);
    settings.resolve({ version: 'v1', mode: 'firebase', login_available: true, providers: ['google.com'],
      firebase: { apiKey: 'fixture', authDomain: 'fixture-project.firebaseapp.com',
        projectId: 'fixture-project', appId: '1:123:web:abc' } });
    assert.equal(await logout, true);
    assert.equal(session.state.ready, true);
    assert.equal(session.state.csrf, '');
    assert.deepEqual(calls, ['/auth/config', '/auth/session', '/auth/logout', 'sdk']);
  } finally {
    settings.resolve(null);
    await pending;
  }
});

test('saved Library startup requests its first page with the verified Firebase session', async () => {
  const { createSession, readSessionBootstrap } = await import('./workshop/auth.mjs');
  const library = { version: 'v1', items: [], next_cursor: null };
  const calls = [];
  const request = async (path, options) => {
    calls.push([path, options.headers?.Prefer]);
    if (path === '/auth/config') return new Promise(() => {});
    return { mode: 'firebase', authenticated: true, roles: ['dataset_viewer'],
      expires_at: '2099-01-01T00:00:00Z', csrf_token: 'verified', workshop_library: library };
  };
  const session = createSession({ request });
  assert.equal(await session.bootstrap({ initial: readSessionBootstrap(request, { includeLibrary: true }) }), library);
  assert.equal(session.state.authenticated, true);
  assert.deepEqual(calls, [
    ['/auth/config', undefined],
    ['/auth/session', 'workshop-session-mode, workshop-session-library'],
  ]);
});

test('session mode cannot accelerate a missing dataset role, CSRF token or unexpired session', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  for (const invalid of [{ roles: [] }, { csrf_token: '' }, { expires_at: '2000-01-01T00:00:00Z' }]) {
    const settings = deferredAuthOperation();
    const session = createSession({ request: async path => path === '/auth/config' ? settings.promise : {
      authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z',
      csrf_token: 'verified', mode: 'firebase', ...invalid,
    } });
    const pending = session.bootstrap();
    try {
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(session.state.mode, null);
      assert.equal(session.state.authenticated, false);
    } finally {
      settings.resolve({ mode: 'firebase' });
      await pending;
    }
    assert.equal(session.state.authenticated, false);
    assert.equal(session.state.csrf, '');
  }
});

test('Firebase persistence is awaited before popup and token exchange clears SDK user', async () => {
  const { createSession }=await import('./workshop/auth.mjs');const calls=[];let release;
  const user={}; const sdk={initializeApp:()=>({}),initializeAuth:(_,options)=>{assert.equal(options.persistence,'NONE');return {};},inMemoryPersistence:'NONE',browserPopupRedirectResolver:{},setPersistence:()=>new Promise(resolve=>{release=resolve;}),GoogleAuthProvider:class{},signInWithPopup:async()=>{calls.push('popup');return{user};},getIdTokenResult:async()=>({token:'synthetic-token',authTime:new Date().toISOString()}),signOut:async()=>{calls.push('sdk-signout');}};
  let loggedIn=false;const session=createSession({loadSDK:async()=>sdk,request:async(path,options)=>{if(path==='/auth/config')return{version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'fixture',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123:web:abc'}};if(path==='/auth/session'){if(!loggedIn){const error=new Error();error.status=401;throw error;}return{authenticated:true,roles:['dataset_viewer'],expires_at:'2099-01-01T00:00:00Z',csrf_token:'csrf'};}assert.equal(path,'/auth/firebase/session');assert.equal(options.body.id_token,'synthetic-token');assert.equal(options.headers['X-Autodata-Session-Exchange'],'1');loggedIn=true;calls.push('exchange');}});
  const bootstrap=session.bootstrap();await new Promise(resolve=>setImmediate(resolve));assert.equal(session.state.ready,false);release();await bootstrap;await session.signIn();assert.deepEqual(calls,['popup','exchange','sdk-signout']);assert.equal(session.state.authenticated,true);
});
test('cookie transport sends JSON/CSRF without bearer, honors response status and safe retry metadata', async () => {
  const { requestArticleJSON, CatalogRequestError } = await import('./workshop/catalog.mjs');
  let options;
  const result = await requestArticleJSON('/v1/catalog/vehicles/a/articles/b/prepare', { method:'POST',body:{},headers:{'X-CSRF-Token':'csrf'},fetcher:async(_,o)=>{options=o;return new Response('{"article":{"id":"b"}}',{status:202,headers:{'Retry-After':'3'}});} });
  assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.equal(options.body,'{}');assert.equal(options.headers.Authorization,undefined);assert.equal(result.status,202);assert.equal(result.retryAfterSeconds,3);
  await assert.rejects(requestJSON('/x',{fetcher:async()=>new Response('{"error":{"code":"ENTITLEMENT_REQUIRED","message":"PRIVATE SECRET","retryable":false,"request_id":"safe-id"}}',{status:403})}),e=>e instanceof CatalogRequestError&&e.code==='ENTITLEMENT_REQUIRED'&&!e.message.includes('PRIVATE'));
});
test('selected index transport limits receipt handling to acknowledged private responses and disallows redirects', async () => {
  const expiresAt = '2099-01-01T00:00:00Z';
  const responses = [
    new Response(null, { status: 204, headers: {
      'Preference-Applied': selectedIndexSessionPreference, 'X-CSRF-Token': 'exchanged-csrf',
    } }),
    new Response('{"error":{"code":"ENTITLEMENT_REQUIRED"}}', { status: 403, headers: {
      'Preference-Applied': `workshop-purchase-quote, ${selectedIndexSessionPreference}`,
      'Workshop-Session-Expires': expiresAt,
    } }),
    new Response('{"error":{"code":"UNAUTHENTICATED"}}', { status: 401, headers: {
      'Preference-Applied': selectedIndexSessionPreference, 'Workshop-Session-Expires': expiresAt,
    } }),
    new Response('{"items":[]}', { status: 200, headers: { 'Workshop-Session-Expires': expiresAt } }),
  ];
  const proofs = [];
  const options = {
    onSelectedIndexSession: proof => proofs.push(proof),
    fetcher: async (_path, request) => {
      assert.equal(request.redirect, 'error');
      assert.equal(request.credentials, 'same-origin');
      assert.equal(request.cache, 'no-store');
      return responses.shift();
    },
  };
  assert.equal(await requestJSON('/auth/firebase/session', options), null);
  await assert.rejects(requestJSON('/articles', options), error => error.code === 'ENTITLEMENT_REQUIRED');
  await assert.rejects(requestJSON('/articles', options), error => error.status === 401);
  assert.deepEqual(await requestJSON('/articles', options), { items: [] });
  assert.deepEqual(proofs, [{ exchangeCSRF: 'exchanged-csrf', expiresAt: null }, { exchangeCSRF: null, expiresAt }]);
});
test('indeterminate stage progress does not derive percentages from retries', () => {
  assert.equal(loadingProgress('make',{attempt:2,attempts:40,hydrating:true}).percent,null);
  assert.equal(loadingProgress('make',{attempt:39,attempts:40,hydrating:true}).percent,null);
});
test('sign-out confirmation failure never reports revocation and allows same-CSRF retry', async()=>{
  const {createSession}=await import('./workshop/auth.mjs');let logoutCalls=0;
  const s=createSession({request:async(path,options)=>{if(path==='/auth/config')return{login_available:false};if(path==='/auth/session')return{authenticated:true,roles:['dataset_viewer'],expires_at:'2099-01-01T00:00:00Z',csrf_token:'csrf'};assert.equal(options.headers['X-CSRF-Token'],'csrf');if(++logoutCalls===1)throw new TypeError('network');}});
  await s.bootstrap();assert.equal(await s.logout(),false);assert.equal(s.state.authenticated,false);assert.match(s.state.message,/could not be confirmed/);assert.equal(await s.logout(),true);
});
test('cookie recheck after invalidation reuses the initialized memory SDK and enables explicit login',async()=>{
  const {createSession}=await import('./workshop/auth.mjs');let initialized=0;
  const sdk={initializeApp:()=>({}),initializeAuth:()=>{initialized++;return{};},inMemoryPersistence:'NONE',browserPopupRedirectResolver:{},setPersistence:async()=>{},GoogleAuthProvider:class{}};
  const s=createSession({loadSDK:async()=>sdk,request:async path=>{if(path==='/auth/config')return{version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'fixture',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123:web:abc'}};const e=new Error();e.status=401;throw e;}});
  await s.bootstrap();assert.equal(s.state.ready,true);s.clear();await s.bootstrap();assert.equal(s.state.ready,true);assert.equal(initialized,1);
});

test('confirmed cookie-only logout prepares memory-only SDK for the next explicit sign-in', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  let loaded = 0;
  const sdk = { initializeApp: () => ({}), initializeAuth: () => ({}), setPersistence: async () => {}, inMemoryPersistence: {}, browserPopupRedirectResolver: {}, GoogleAuthProvider: class {}, signOut: async () => {} };
  const account = createSession({ request: async path => path === '/auth/config' ? {version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'fixture',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123:web:abc'}} : path === '/auth/session' ? {authenticated:true,roles:['dataset_viewer'],expires_at:'2099-01-01T00:00:00Z',csrf_token:'csrf'} : null, loadSDK: async () => { loaded++; return sdk; } });
  await account.bootstrap();
  assert.equal(loaded, 0);
  assert.equal(await account.logout(), true);
  assert.equal(account.state.ready, true);
  assert.equal(loaded, 1);
});

// Keep SDK/browser transport external while exercising the real session state machine.
function deferredAuthOperation() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

test('session confirmation checks the same cookie proof without replacing client sign-in state', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  const calls = [];
  const snapshot = { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'first' };
  const pending = deferredAuthOperation();
  const session = createSession({ request: async path => {
    calls.push(path);
    if (path === '/auth/config') return { mode: 'firebase' };
    return calls.length === 5 ? pending.promise : snapshot;
  } });
  await session.bootstrap();
  assert.equal(await session.matchesCurrentSession(), true);
  snapshot.csrf_token = 'different';
  assert.equal(await session.matchesCurrentSession(), false);
  assert.equal(session.state.csrf, 'first');
  const beforeClear = session.matchesCurrentSession();
  session.clear();
  pending.resolve({ ...snapshot, csrf_token: 'first' });
  assert.equal(await beforeClear, false);
  assert.deepEqual(calls, ['/auth/config', '/auth/session', '/auth/session', '/auth/session', '/auth/session']);
});

async function sessionPreparationHarness({
  authenticated = false, persistence = async () => {}, constructProvider = () => {}, popup,
  sdkSignOut = async () => {}, serverLogout = async () => {},
  exchangeCSRF = null, sessionCSRF = 'cookie-csrf',
  tokenResult = () => {
    const time = new Date().toISOString();
    return { token: 'synthetic-token', authTime: time, issuedAtTime: time };
  },
} = {}) {
  const { createSession } = await import('./workshop/auth.mjs');
  const calls = { loads: 0, initializations: 0, providers: 0, persistence: 0, popups: 0, signouts: 0, exchanges: 0, sessionReads: 0, tokenRefreshes: [] };
  const changes = [], user = {}, auth = {};
  let provider;
  const sdk = {
    initializeApp: () => ({}),
    initializeAuth: (_app, options) => {
      assert.equal(options.persistence, sdk.inMemoryPersistence);
      assert.equal(options.popupRedirectResolver, sdk.browserPopupRedirectResolver);
      calls.initializations++;
      return auth;
    },
    inMemoryPersistence: {}, browserPopupRedirectResolver: {},
    setPersistence: (actualAuth, value) => {
      assert.equal(actualAuth, auth);
      assert.equal(value, sdk.inMemoryPersistence);
      return persistence(++calls.persistence);
    },
    GoogleAuthProvider: class {
      constructor() { constructProvider(++calls.providers); provider = this; }
    },
    signInWithPopup: (actualAuth, actualProvider) => {
      calls.popups++;
      assert.equal(actualAuth, auth);
      assert.ok(actualProvider instanceof sdk.GoogleAuthProvider);
      assert.equal(actualProvider, provider);
      return popup ? popup() : Promise.resolve({ user });
    },
    getIdTokenResult: async (actualUser, forceRefresh) => {
      assert.equal(actualUser, user);
      calls.tokenRefreshes.push(Boolean(forceRefresh));
      return tokenResult(forceRefresh);
    },
    signOut: async actualAuth => { assert.equal(actualAuth, auth); await sdkSignOut(++calls.signouts); },
  };
  const session = createSession({
    loadSDK: async () => { calls.loads++; return sdk; },
    onChange: state => changes.push({ ...state, providerPresent: provider !== undefined }),
    request: async (path, options) => {
      if (path === '/auth/config') return { version: 'v1', mode: 'firebase', login_available: true, providers: ['google.com'], firebase: { apiKey: 'fixture', authDomain: 'fixture-project.firebaseapp.com', projectId: 'fixture-project', appId: '1:123:web:abc' } };
      if (path === '/auth/session') {
        calls.sessionReads++;
        if (!authenticated) throw Object.assign(new Error('signed out'), { status: 401 });
        return { authenticated: true, roles: ['dataset_viewer'], csrf_token: sessionCSRF, expires_at: '2099-01-01T00:00:00Z' };
      }
      if (path === '/auth/logout') {
        assert.equal(options.headers['X-CSRF-Token'], 'cookie-csrf');
        await serverLogout();
        authenticated = false;
        return null;
      }
      assert.equal(path, '/auth/firebase/session');
      assert.equal(options.method, 'POST');
      assert.deepEqual(options.body, { id_token: 'synthetic-token' });
      assert.deepEqual(options.headers, {
        'X-Autodata-Session-Exchange': '1',
        ...(options.onSelectedIndexSession ? { Prefer: selectedIndexSessionPreference } : {}),
      });
      if (exchangeCSRF) options.onSelectedIndexSession({ exchangeCSRF });
      calls.exchanges++;
      authenticated = true;
      return null;
    },
  });
  return { session, calls, changes };
}

test('selected index checks the exchanged cookie after SDK sign-out', async () => {
  const cleanupStarted = deferredAuthOperation();
  const cleanup = deferredAuthOperation();
  const { session, calls } = await sessionPreparationHarness({
    exchangeCSRF: 'cookie-csrf',
    sdkSignOut() { cleanupStarted.resolve(); return cleanup.promise; },
  });
  await session.bootstrap();
  const index = { value: { items: [] } };
  let indexReads = 0;
  const signingIn = session.signIn({
    confirmSelectedIndex(csrf, signal) {
      assert.equal(csrf, 'cookie-csrf');
      assert.equal(signal.aborted, false);
      assert.equal(calls.signouts, 1);
      indexReads++;
      return { expiresAt: '2099-01-01T00:00:00Z', firstIndex: index };
    },
  });
  await cleanupStarted.promise;
  assert.equal(indexReads, 0);
  assert.equal(session.state.authenticated, false);
  cleanup.resolve();
  assert.equal(await signingIn, index);
  assert.equal(indexReads, 1);
  assert.equal(session.state.authenticated, true);
  assert.equal(session.state.csrf, 'cookie-csrf');
  assert.equal(calls.sessionReads, 1);
});

test('a cookie replaced during SDK sign-out cannot provide a selected index', async () => {
  const cleanupStarted = deferredAuthOperation();
  const cleanup = deferredAuthOperation();
  let browserCSRF = 'cookie-csrf';
  const { session, calls } = await sessionPreparationHarness({
    exchangeCSRF: 'cookie-csrf',
    sessionCSRF: 'other-cookie',
    sdkSignOut() { cleanupStarted.resolve(); return cleanup.promise; },
  });
  await session.bootstrap();
  const signingIn = session.signIn({
    confirmSelectedIndex(csrf) {
      return browserCSRF === csrf
        ? { expiresAt: '2099-01-01T00:00:00Z', firstIndex: { value: { items: ['old account'] } } }
        : null;
    },
  });
  await cleanupStarted.promise;
  browserCSRF = 'other-cookie';
  cleanup.resolve();
  assert.equal(await signingIn, undefined);
  assert.equal(session.state.authenticated, false);
  assert.equal(calls.sessionReads, 2);
});

test('selected index negotiation falls back to the cookie read and rejects a different cookie', async t => {
  for (const [name, exchangeCSRF, sessionCSRF, confirmed] of [
    ['older exchange', null, 'cookie-csrf', true],
    ['older index', 'cookie-csrf', 'cookie-csrf', true],
    ['replaced cookie', 'cookie-csrf', 'other-cookie', false],
  ]) {
    await t.test(name, async () => {
      const { session, calls } = await sessionPreparationHarness({ exchangeCSRF, sessionCSRF });
      await session.bootstrap();
      let indexes = 0;
      assert.equal(await session.signIn({
        confirmSelectedIndex() {
          indexes++;
          return { firstIndex: { value: { items: ['discarded'] } } };
        },
      }), undefined);
      assert.equal(indexes, exchangeCSRF ? 1 : 0);
      assert.equal(calls.sessionReads, 2);
      assert.equal(session.state.authenticated, confirmed);
    });
  }
});

test('auth generation change aborts an in-flight selected index', async () => {
  const started = deferredAuthOperation();
  const { session, calls } = await sessionPreparationHarness({ exchangeCSRF: 'cookie-csrf' });
  await session.bootstrap();
  const signingIn = session.signIn({
    confirmSelectedIndex(_csrf, signal) {
      started.resolve(signal);
      return new Promise(resolve => signal.addEventListener('abort', () => resolve(null), { once: true }));
    },
  });
  const signal = await started.promise;
  session.clear();
  assert.equal(signal.aborted, true);
  assert.equal(await signingIn, undefined);
  assert.equal(session.state.authenticated, false);
  assert.equal(calls.sessionReads, 1);
});

test('Firebase sign-in reuses recent popup tokens and refreshes older or unreadable issuance', async t => {
  for (const [name, issuedAt, expected] of [
    ['recent', new Date().toISOString(), [false]],
    ['older', new Date(Date.now() - 245_000).toISOString(), [false, true]],
    ['unreadable', undefined, [false, true]],
    ['future', new Date(Date.now() + 90_000).toISOString(), [false, true]],
  ]) {
    await t.test(name, async () => {
      const { session, calls } = await sessionPreparationHarness({
        tokenResult(forceRefresh) {
          const time = new Date().toISOString();
          return { token: 'synthetic-token', authTime: time, issuedAtTime: forceRefresh ? time : issuedAt };
        },
      });
      await session.bootstrap();
      await session.signIn();
      assert.deepEqual(calls.tokenRefreshes, expected);
      assert.equal(calls.exchanges, 1);
      assert.equal(calls.signouts, 1);
      assert.equal(session.state.authenticated, true);
      assert.equal(session.state.csrf, 'cookie-csrf');
    });
  }
});

test('server revocation starts while Firebase logout is pending', async () => {
  const sdkStarted = deferredAuthOperation();
  const sdkFinished = deferredAuthOperation();
  const serverFinished = deferredAuthOperation();
  let serverStarted = false;
  const { session } = await sessionPreparationHarness({
    sdkSignOut(attempt) {
      if (attempt === 2) {
        sdkStarted.resolve();
        return sdkFinished.promise;
      }
    },
    serverLogout() {
      serverStarted = true;
      return serverFinished.promise;
    },
  });
  await session.bootstrap();
  await session.signIn();
  const logout = session.logout();
  await sdkStarted.promise;
  try {
    assert.equal(serverStarted, true);
    assert.equal(session.state.authenticated, false);
    assert.equal(session.state.message, 'Signing out…');
  } finally {
    sdkFinished.resolve();
    serverFinished.resolve();
    assert.equal(await logout, true);
  }
  assert.equal(session.state.message, 'Signed out.');
});

test('logout preparation preserves provider readiness across an epoch-changing bootstrap', async () => {
  const started = deferredAuthOperation(), firstPersistence = deferredAuthOperation();
  const { session, calls, changes } = await sessionPreparationHarness({
    authenticated: true,
    persistence: attempt => {
      if (attempt === 1) { started.resolve(); return firstPersistence.promise; }
      return Promise.resolve();
    },
  });
  await session.bootstrap();
  assert.equal(calls.loads, 0, 'cookie authority needs no SDK recovery');
  const logout = session.logout();
  await started.promise;
  assert.equal(session.state.ready, false);
  try {
    await session.bootstrap();
    assert.equal(session.state.ready, true);
    assert.equal(calls.providers, 1, 'ready must include a Google provider');
  } finally {
    firstPersistence.resolve();
    assert.equal(await logout, true);
  }
  assert.ok(changes.filter(state => state.ready).every(state => state.providerPresent));
  const signingIn = session.signIn();
  assert.equal(calls.popups, 1, 'popup starts before yielding');
  await signingIn;
  assert.equal(calls.initializations, 1);
  assert.equal(calls.providers, 1);
  assert.equal(calls.exchanges, 1);
  assert.equal(session.state.authenticated, true);
  assert.equal(session.state.csrf, 'cookie-csrf');
});

test('provider constructor failures stay unavailable until an existing-auth retry succeeds', async () => {
  const { session, calls, changes } = await sessionPreparationHarness({
    constructProvider: attempt => { if (attempt <= 2) throw new Error('private constructor detail'); },
  });
  for (let attempt = 1; attempt <= 2; attempt++) {
    await assert.doesNotReject(session.bootstrap());
    assert.equal(session.state.ready, false);
    assert.equal(session.state.message, 'Google sign-in is unavailable. You can keep browsing.');
    await assert.rejects(session.signIn(), /Sign-in is unavailable/);
    assert.equal(calls.popups, 0);
  }
  await session.bootstrap();
  assert.equal(session.state.ready, true);
  assert.equal(calls.initializations, 1);
  assert.equal(calls.providers, 3);
  assert.ok(changes.filter(state => state.ready).every(state => state.providerPresent));
  await session.signIn();
  assert.equal(session.state.authenticated, true);
  assert.equal(calls.exchanges, 1);
});

test('existing-auth persistence failure stays unavailable and permits a later retry', async () => {
  const { session, calls } = await sessionPreparationHarness({
    persistence: async attempt => { if (attempt === 2) throw new Error('private persistence detail'); },
  });
  await session.bootstrap();
  assert.equal(session.state.ready, true);
  await assert.doesNotReject(session.bootstrap());
  assert.equal(session.state.ready, false);
  assert.equal(session.state.message, 'Google sign-in is unavailable. You can keep browsing.');
  await assert.rejects(session.signIn(), /Sign-in is unavailable/);
  assert.equal(calls.popups, 0);
  await session.bootstrap();
  assert.equal(session.state.ready, true);
  await session.signIn();
  assert.equal(session.state.authenticated, true);
});

for (const pausedAttempt of [1, 2]) {
  test(`stale ${pausedAttempt === 1 ? 'initial' : 'existing-auth'} preparation failure cannot overwrite current readiness`, async () => {
    const started = deferredAuthOperation(), pendingPersistence = deferredAuthOperation();
    const { session, changes } = await sessionPreparationHarness({
      persistence: attempt => {
        if (attempt === pausedAttempt) { started.resolve(); return pendingPersistence.promise; }
        return Promise.resolve();
      },
    });
    if (pausedAttempt === 2) await session.bootstrap();
    const staleBootstrap = session.bootstrap();
    await started.promise;
    await session.bootstrap();
    assert.equal(session.state.ready, true);
    const currentState = { ...session.state }, changeCount = changes.length;
    pendingPersistence.reject(new Error('private stale failure'));
    await assert.doesNotReject(staleBootstrap);
    assert.deepEqual(session.state, currentState);
    assert.equal(changes.length, changeCount);
    await session.signIn();
    assert.equal(session.state.authenticated, true);
  });
}

for (const mode of ['synchronous popup invocation', 'asynchronous popup rejection']) {
  test(`${mode} failure restores readiness without deferring the popup`, async () => {
    const error = Object.assign(new Error('private popup detail'), { code: 'auth/internal-error' });
    const { session, calls } = await sessionPreparationHarness({
      popup: () => { if (mode === 'synchronous popup invocation') throw error; return Promise.reject(error); },
    });
    await session.bootstrap();
    let signingIn;
    assert.doesNotThrow(() => { signingIn = session.signIn(); });
    assert.ok(signingIn instanceof Promise);
    assert.equal(calls.popups, 1, 'popup starts before yielding');
    assert.equal(session.state.ready, false);
    await assert.doesNotReject(signingIn);
    assert.equal(session.state.ready, true);
    assert.equal(session.state.authenticated, false);
    assert.equal(session.state.csrf, '');
    assert.equal(session.state.message, 'Google sign-in is unavailable. You can keep browsing.');
    assert.equal(calls.signouts, 1);
    assert.equal(calls.exchanges, 0);
  });
}

// Execute production app boundaries without starting its browser bootstrap.
function appSection(start, end) {
  const source = readFileSync(new URL('./workshop/app.mjs', import.meta.url), 'utf8');
  assert.equal(source.split(start).length, 2, `unique app boundary: ${start}`);
  assert.equal(source.split(end).length, 2, `unique app boundary: ${end}`);
  const first = source.indexOf(start), last = source.indexOf(end);
  assert.ok(last > first, 'app boundaries are ordered');
  return source.slice(first, last);
}

function installArticleRequestPath(context) {
  context.URLSearchParams = URLSearchParams;
  context.demoPath ??= (path) => path;
  runInNewContext(appSection('function articleRequestPath(', 'function status('), context);
}

function sourceReviewHarness() {
  const navigation = new NavigationGeneration();
  const first = navigation.next();
  const state = { content: 'article A', status: 'A ready', view: 'reader' };
  const loads = [], errors = [];
  let click, rejectSource;
  const context = {
    currentArticle: { source_review: { url: '/article-A/source' } },
    viewGeneration: first,
    $: id => ({ addEventListener(event, callback) {
      if (id === 'source-review-load') {
        assert.equal(event, 'click');
        click = callback;
      }
    } }),
    loadSource(url, generation) {
      loads.push({ url, generation });
      return new Promise((_, reject) => { rejectSource = reject; });
    },
    invalidate() { navigation.clear(); state.content = ''; },
    show(view) { state.view = view; },
    status(message) { state.status = message; },
  };
  runInNewContext(
    appSection('function originalSourceReview(', 'function renderArticle(') +
    appSection('function handleSourceError(error, g) {', 'async function renewMedia(') +
    appSection('function openOriginal(', '$("back").addEventListener'),
    context,
  );
  const handleError = context.handleSourceError;
  context.handleSourceError = (error, generation) => {
    errors.push(generation);
    handleError(error, generation);
  };
  return { context, state, first, loads, errors, navigation,
    click: () => click(), reject: error => rejectSource(error) };
}

for (const failure of ['AbortError', 401, 403, 410]) {
  test(`source review ignores stale ${failure} after selection A changes to B`, async () => {
    const h = sourceReviewHarness();
    h.click();
    assert.equal(h.loads.length, 1);
    assert.equal(h.loads[0].url, '/article-A/source');
    assert.equal(h.loads[0].generation, h.first);
    const second = h.navigation.next();
    h.context.viewGeneration = second;
    Object.assign(h.state, { content: 'article B', status: 'B ready', view: 'reader' });
    const error = failure === 'AbortError'
      ? new DOMException('Source A canceled', 'AbortError')
      : Object.assign(new Error('Source A denied'), { status: failure });
    h.reject(error);
    await new Promise(setImmediate);
    assert.deepEqual(h.state, { content: 'article B', status: 'B ready', view: 'reader' });
    assert.equal(second.current(), true);
    assert.deepEqual(h.errors, [h.first]);
  });
}

for (const failure of [401, 403, 410]) {
  test(`source review still clears current selection on ${failure}`, async () => {
    const h = sourceReviewHarness();
    h.click();
    h.reject(Object.assign(new Error('Current source denied'), { status: failure }));
    await new Promise(setImmediate);
    assert.deepEqual(h.state, { content: '', status: 'Current source denied', view: 'welcome' });
    assert.equal(h.first.current(), false);
    assert.deepEqual(h.errors, [h.first]);
  });
}

for (const unavailable of ['article', 'generation', 'canceled generation']) {
  test(`source review does not load without a current ${unavailable}`, () => {
    const h = sourceReviewHarness();
    if (unavailable === 'article') h.context.currentArticle = null;
    else if (unavailable === 'generation') h.context.viewGeneration = null;
    else h.navigation.clear();
    h.click();
    assert.equal(h.loads.length, 0);
    assert.equal(h.errors.length, 0);
    assert.deepEqual(h.state, { content: 'article A', status: 'A ready', view: 'reader' });
  });
}

const routeConfiguration = '11111111-1111-4111-8111-111111111111';
const routeArticle = '22222222-2222-4222-8222-222222222222';
const routeOrder = '33333333-3333-4333-8333-333333333333';
const previousConfiguration = '44444444-4444-4444-8444-444444444444';

function loginRouteHarness(search, { authenticate = true, signInError = null, login = null, library = null, selectorRead = null, confirmSelectedIndex = null } = {}) {
  const navigation = new NavigationGeneration();
  const calls = { signIns: 0, checkoutClears: 0, checkouts: 0, routes: 0,
    selections: [], selectionOptions: [], libraries: 0, orders: [], options: [], selectorReads: [], invalidations: 0 };
  const elements = new Map();
  const element = name => {
    if (!elements.has(name)) elements.set(name, { value: '', disabled: false, children: [],
      get options() { return this.children; },
      replaceChildren(...children) { this.children = children; this.value = ''; } });
    return elements.get(name);
  };
  const configuration = { id: routeConfiguration, region: 'US' };
  const context = {
    URLSearchParams, AbortSignal, uuid, validScope, configurationLabel, selectedIndexSessionPreference, validQuote,
    Option: function(text, value) { return { text, value }; },
    location: { pathname: '/workshop/', search }, signingIn: false, sessionRequest: null, viewGeneration: navigation.next(),
    vehicle: { id: previousConfiguration, region: 'US' }, quote: null,
    merchant: { enabled: true }, merchantRequest: null,
    names: ['year', 'make', 'model', 'configuration'],
    rows: { configuration: [configuration] }, $: element,
    checkout: { read: () => null, clear() { calls.checkoutClears++; }, start() { calls.checkouts++; } },
    session: { state: { authenticated: false, mode: 'firebase' }, async signIn(options) {
      calls.signIns++;
      if (login) await login();
      if (signInError) throw signInError;
      const result = await confirmSelectedIndex?.(options);
      context.session.state.authenticated = authenticate;
      return result;
    } },
    scope: () => ({ configuration_id: context.vehicle?.id, region: context.vehicle?.region }),
    articleRequestPath: () => `/v1/catalog/vehicles/${context.vehicle.id}/articles?region=${context.vehicle.region}`,
    purchaseConfigured: () => true,
    invalidate() { calls.invalidations++; navigation.clear(); },
    show() {}, status() {}, renderPurchase() {},
    async operation(work) { calls.routes++; return work(navigation.next()); },
    async library(g) {
      assert.equal(g.current(), true);
      calls.libraries++;
      if (library) await library();
    },
    async checkOrder(g, id) {
      assert.equal(g.current(), true);
      calls.orders.push(id);
    },
    async selectVehicle(g, article = '', options) {
      assert.equal(g.current(), true);
      calls.selections.push({ configuration: context.vehicle.id, region: context.vehicle.region, article });
      calls.selectionOptions.push(options);
    },
    async requestJSON(path, options) {
      calls.selectorReads.push({ path, signal: options.signal });
      return selectorRead?.(path, options);
    },
    async loadOptions(name, g, desired, initial) {
      assert.equal(g.current(), true);
      calls.options.push({ name, desired });
      const response = await initial;
      if (!g.current()) return;
      if (response) {
        if (desired && !response.items.some(item => String(item.id ?? item.year) === desired)) throw new Error('Unavailable choice');
        return context.populate(name, response.items, desired);
      }
      context.populate(name, name === 'configuration' ? [configuration] :
        [name === 'year' ? { year: Number(desired) || 2026 } : { id: desired || 'choice', name: desired }], desired);
    },
  };
  runInNewContext(
    appSection('function populate(', 'async function loadOptions(') +
    appSection('async function signIn() {', 'export async function bootstrap(') +
    appSection('function loadPurchaseConfiguration(', 'function checkAccount(') +
    appSection('async function confirmedSavedYear(', 'for (const [index, name] of names.entries())'),
    context,
  );
  return { context, calls, element };
}

test('the engine picker distinguishes configurations that share a displacement and trim', () => {
  const h = loginRouteHarness('');
  const shared = { engine: '2.0', trim: 'Sport' };
  const variants = [
    { ...shared, id: routeConfiguration, body_style: 'Coupe', drivetrain: '2WD' },
    { ...shared, id: previousConfiguration, body_style: 'Sedan', drivetrain: 'AWD' },
  ];
  h.context.populate('configuration', variants, previousConfiguration);
  assert.deepEqual(Array.from(h.element('configuration').options.slice(1), ({ text, value }) => [text, value]), [
    ['2.0 L / Sport / Coupe / 2WD', routeConfiguration],
    ['2.0 L / Sport / Sedan / AWD', previousConfiguration],
  ]);
  assert.equal(h.element('configuration').value, previousConfiguration);
});

test('the engine picker displays an unverified variant without allowing selection', () => {
  const h = loginRouteHarness('');
  const common = { engine: '6.0', trim: 'Base' };
  const legacy = { ...common, id: routeConfiguration };
  const variant = { ...common, id: previousConfiguration, engine_variant: 'CNG' };
  h.context.populate('configuration', [legacy, { ...variant, engine_variant_market_unverified: true }], previousConfiguration);
  const select = h.element('configuration');
  assert.deepEqual(Array.from(select.options.slice(1), ({ text, value, disabled }) => [text, value, disabled]), [
    ['6.0 L / Base', routeConfiguration, false],
    ['6.0 L CNG / Base · market unverified', previousConfiguration, true],
  ]);
  assert.equal(select.value, '');
  h.context.populate('configuration', [legacy, variant], previousConfiguration);
  assert.equal(select.options[2].text, '6.0 L CNG / Base');
  assert.equal(select.options[2].disabled, false);
  assert.equal(select.value, previousConfiguration);
});

test('checkout return checks sooner only for the matching, unexpired checkout', async () => {
  const future = new Date(Date.now() + 60_000).toISOString();
  const past = new Date(Date.now() - 60_000).toISOString();
  for (const [attempt, expected] of [
    [{ order_id: routeOrder, provider_expires_at: future }, true],
    [{ order_id: routeOrder, provider_expires_at: past }, false],
    [{ order_id: routeOrder }, false],
    [{ order_id: previousConfiguration, provider_expires_at: future }, false],
    [null, false],
  ]) {
    const h = loginRouteHarness(`?order=${routeOrder}`);
    h.context.session.state.authenticated = true;
    h.context.checkout.read = () => attempt;
    const checks = [];
    h.context.checkOrder = async (_g, id, { earlyCheckoutCheck, returnedCheckout }) =>
      checks.push([id, earlyCheckoutCheck, returnedCheckout]);
    await h.context.restoreRoute();
    assert.deepEqual(checks, [[routeOrder, expected, expected ? attempt : undefined]]);
  }
});

test('checkout return waits for the initial account check and drops a canceled navigation', async () => {
  for (const canceled of [false, true]) {
    const h = loginRouteHarness(`?order=${routeOrder}`);
    const account = deferredAuthOperation();
    h.context.sessionRequest = account.promise;
    const loading = h.context.restoreRoute();
    assert.deepEqual(h.calls.orders, []);
    if (canceled) h.context.invalidate();
    h.context.session.state.authenticated = true;
    account.resolve();
    await loading;
    assert.deepEqual(h.calls.orders, canceled ? [] : [routeOrder]);
  }
});

test('an owned Firebase saved search can restore its exact scope without the selector hierarchy', async () => {
  const query = `?year=2020&make=toyota&model=rav4&configuration=${routeConfiguration}&region=US&q=oil+pump`;
  const h = loginRouteHarness(query);
  h.context.session.state.authenticated = true;
  h.context.session.state.mode = 'firebase';
  await h.context.restoreRoute();
  assert.equal(h.element('search').value, 'oil pump');
  assert.deepEqual(h.calls.options, []);
  assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: '' }]);
});

const loginRoutes = [
  { name: 'My vehicles instead of a prior selected configuration', query: '?view=library',
    libraries: 1, orders: [], selections: [], options: [] },
  { name: 'the exact article in a direct configuration link',
    query: `?configuration=${routeConfiguration}&region=US&article=${routeArticle}`,
    libraries: 0, orders: [],
    selections: [{ configuration: routeConfiguration, region: 'US', article: routeArticle }], options: [] },
  { name: 'the article and search in a saved selector hierarchy',
    query: `?year=2020&make=toyota&model=rav4&configuration=${routeConfiguration}&region=US&article=${routeArticle}&q=brakes`,
    libraries: 0, orders: [], options: [],
    selections: [{ configuration: routeConfiguration, region: 'US', article: routeArticle }] },
  { name: 'the order return before the library or prior configuration',
    query: `?order=${routeOrder}&view=library&configuration=${routeConfiguration}&region=US&article=${routeArticle}`,
    libraries: 0, orders: [routeOrder], selections: [], options: [] },
];
for (const route of loginRoutes) {
  test(`login route resumes ${route.name} without checkout replay`, async () => {
    const h = loginRouteHarness(route.query);
    await h.context.signIn();
    assert.equal(h.calls.libraries, route.libraries);
    assert.deepEqual(h.calls.orders, route.orders);
    assert.deepEqual(h.calls.selections, route.selections);
    assert.deepEqual(h.calls.options, route.options);
    assert.equal(h.calls.routes, 1);
    assert.equal(h.calls.invalidations, 1);
    assert.equal(h.calls.signIns, 1);
    assert.equal(h.calls.checkoutClears, 1);
    assert.equal(h.calls.checkouts, 0);
    assert.equal(h.context.signingIn, false);
    if (route.query.includes('q=brakes')) assert.equal(h.element('search').value, 'brakes');
  });
}

const selectedCheckoutRoute = `?year=2020&make=toyota&model=rav4&configuration=${routeConfiguration}&region=US`;

function selectedCheckoutHarness(options) {
  const h = loginRouteHarness(selectedCheckoutRoute, options);
  h.context.vehicle = { id: routeConfiguration, region: 'US' };
  ['2020', 'toyota', 'rav4', routeConfiguration].forEach((value, index) => {
    const name = h.context.names[index];
    const item = name === 'year' ? { year: 2020 } : { id: value, name: value };
    h.context.populate(name, [item], value);
  });
  return h;
}

test('sign-in rechecks paid access for the displayed selection without reloading selector choices', async () => {
  const h = selectedCheckoutHarness();
  const before = h.context.names.map(name => h.element(name).children);
  await h.context.signIn();
  assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: '' }]);
  assert.equal(h.calls.selectionOptions[0]?.reuseQuote, true);
  assert.deepEqual(h.calls.options, []);
  assert.equal(h.calls.invalidations, 1);
  assert.equal(h.calls.checkoutClears, 1);
  assert.equal(h.calls.checkouts, 0);
  assert.equal(h.calls.selectorReads.length, 0, 'known regular purchase config does not need a refresh');
  h.context.names.forEach((name, index) => assert.equal(h.element(name).children, before[index]));
});

test('sign-in refreshes unknown purchase config without letting a guest reply replace it', async t => {
  for (const guestStatus of ['pending', 'failed']) {
    await t.test(guestStatus, async () => {
      const h = selectedCheckoutHarness();
      const guest = deferredAuthOperation(), owner = deferredAuthOperation();
      const reads = [];
      h.context.requestJSON = path => {
        assert.equal(path, '/workshop/purchase-config.json');
        const signedIn = h.context.session.state.authenticated;
        reads.push(signedIn ? 'owner' : 'guest');
        return signedIn ? owner.promise : guest.promise;
      };
      h.context.loadPurchaseConfiguration();
      const guestRequest = h.context.merchantRequest;
      if (guestStatus === 'failed') {
        guest.reject(new Error('Purchase configuration unavailable'));
        await guestRequest;
      }
      assert.equal(h.context.merchant, null);

      await h.context.signIn();
      assert.deepEqual(reads, ['guest', 'owner']);
      const ownerConfig = { enabled: true, checkout_mode: 'simulation' };
      owner.resolve(ownerConfig);
      await h.context.merchantRequest;
      if (guestStatus === 'pending') {
        guest.resolve({ enabled: false, checkout_mode: 'simulation' });
        await guestRequest;
      }
      assert.equal(h.context.merchant, ownerConfig);
      assert.equal(h.context.merchantRequest, null);
    });
  }
});

test('selected sign-in hands off the exact negotiated index and purchase quote error once', async () => {
  const revoked = Object.assign(new Error('Revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const h = selectedCheckoutHarness({
    async confirmSelectedIndex(options) {
      const { expiresAt, firstIndex } = await options.confirmSelectedIndex('exchange-csrf', new AbortController().signal);
      assert.equal(expiresAt, '2099-01-01T00:00:00Z');
      return firstIndex;
    },
    selectorRead(path, options) {
      assert.equal(path, `/v1/catalog/vehicles/${routeConfiguration}/articles?region=US`);
      assert.equal(options.headers.Prefer, `workshop-confirm-session, workshop-purchase-quote, ${paidPagePreferences}`);
      assert.equal(options.headers['X-CSRF-Token'], 'exchange-csrf');
      options.onSelectedIndexSession({ expiresAt: '2099-01-01T00:00:00Z' });
      throw revoked;
    },
  });
  h.context.quote = { ...scopedQuoteFixture(), configuration_id: routeConfiguration, region: 'US' };
  await h.context.signIn();
  assert.equal(h.calls.selectionOptions[0].firstIndex.error, revoked);
  assert.equal(h.calls.selectorReads.length, 1);
});

test('buffered index success needs a matching stored configuration and usable list', async t => {
  const exact = { id: routeConfiguration, region: 'US' };
  for (const [name, response, accepted] of [
    ['exact', { configuration: exact, items: [] }, true],
    ['other configuration', { configuration: { ...exact, id: previousConfiguration }, items: [] }, false],
    ['other region', { configuration: { ...exact, region: 'CA' }, items: [] }, false],
    ['missing metadata', { items: [] }, false],
    ['malformed list', { configuration: exact }, false],
  ]) {
    await t.test(name, async () => {
      const h = selectedCheckoutHarness({
        async confirmSelectedIndex(options) {
          const result = await options.confirmSelectedIndex('exchange-csrf', new AbortController().signal);
          assert.equal(result.expiresAt, '2099-01-01T00:00:00Z');
          return result.firstIndex;
        },
        selectorRead(_path, options) {
          options.onSelectedIndexSession({ expiresAt: '2099-01-01T00:00:00Z' });
          return response;
        },
      });
      await h.context.signIn();
      const firstIndex = h.calls.selectionOptions[0].firstIndex;
      if (accepted) assert.equal(firstIndex.value, response);
      else assert.equal(firstIndex, null);
    });
  }
});

test('superseding the picker generation aborts the early index even if the route returns to the same vehicle', async () => {
  const started = deferredAuthOperation();
  const h = selectedCheckoutHarness({
    async confirmSelectedIndex(options) {
      assert.equal(await options.confirmSelectedIndex('exchange-csrf', new AbortController().signal), null);
    },
    selectorRead(_path, { signal }) {
      started.resolve(signal);
      return new Promise(resolve => signal.addEventListener('abort', () => resolve({ items: [] }), { once: true }));
    },
  });
  const signingIn = h.context.signIn();
  const signal = await started.promise;
  h.context.invalidate();
  assert.equal(signal.aborted, true);
  await signingIn;
  assert.equal(h.calls.selectionOptions[0].firstIndex, null);
});

for (const change of ['URL', 'selector', 'region']) {
  test(`sign-in falls back to full restoration when the checkout ${change} changes`, async () => {
    const pending = deferredAuthOperation();
    const h = selectedCheckoutHarness({ login: () => pending.promise });
    const signIn = h.context.signIn();
    if (change === 'URL') h.context.location.search = '?view=library';
    if (change === 'selector') h.element('model').value = 'different-model';
    if (change === 'region') h.context.vehicle.region = 'CA';
    pending.resolve();
    await signIn;
    if (change === 'URL') {
      assert.equal(h.calls.libraries, 1);
      assert.deepEqual(h.calls.selections, []);
    } else {
      assert.equal(h.calls.options.length, 4);
      assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: '' }]);
    }
    assert.equal(h.calls.checkouts, 0);
  });
}

function seedPriorRoute(h) {
  for (const name of h.context.names) {
    h.context.populate(name, [name === 'year' ? { year: 1999 } : { id: 'prior', name: 'Prior vehicle' }]);
    h.element(name).value = 'prior';
  }
  h.element('search').value = 'old vehicle only';
  h.context.quote = { configuration_label: 'Prior vehicle' };
}

for (const query of ['', '&q=brake+pads']) {
  test(`direct article route restores its own query ${query || '(empty)'} and clears prior selector options`, async () => {
    const h = loginRouteHarness(`?configuration=${routeConfiguration}&region=US&article=${routeArticle}${query}`);
    seedPriorRoute(h);
    await h.context.restoreRoute();
    assert.equal(h.element('search').value, query ? 'brake pads' : '');
    for (const name of h.context.names) {
      assert.equal(h.element(name).value, '');
      assert.equal(h.element(name).disabled, true);
      assert.equal(h.element(name).children.length, 1);
      assert.equal(h.context.rows[name].length, 0);
    }
    assert.equal(h.context.quote, null);
    assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: routeArticle }]);
  });
}

for (const query of ['?view=library', `?order=${routeOrder}`]) {
  test(`non-selector route ${query} drops prior vehicle context and query`, async () => {
    const h = loginRouteHarness(query);
    seedPriorRoute(h);
    await h.context.restoreRoute();
    assert.equal(h.context.vehicle, null);
    assert.equal(h.context.quote, null);
    assert.equal(h.element('search').value, '');
    for (const name of h.context.names) {
      assert.equal(h.element(name).value, '');
      assert.equal(h.element(name).disabled, true);
      assert.equal(h.context.rows[name].length, 0);
    }
  });
}

test('partial saved hierarchy clears stale descendants before restoring its chosen year', async () => {
  const h = loginRouteHarness('?year=2020&q=oil');
  seedPriorRoute(h);
  await h.context.restoreRoute();
  assert.equal(h.element('year').value, '2020');
  assert.equal(h.element('make').value, '');
  assert.equal(h.element('model').disabled, true);
  assert.equal(h.element('configuration').disabled, true);
  assert.equal(h.context.vehicle, null);
  assert.equal(h.element('search').value, 'oil');
  assert.deepEqual(h.calls.options, [{ name: 'year', desired: '2020' }, { name: 'make', desired: '' }]);
});

test('returning to the displayed year and make overlaps reads but hides models until the parents are checked', async () => {
  const year = deferredAuthOperation();
  const h = selectedCheckoutHarness({ selectorRead(path) {
    if (path.endsWith('/years')) return year.promise;
    if (path.includes('/models?')) return { items: [{ id: 'rav4', name: 'RAV4' }] };
    return { items: [{ id: 'toyota', name: 'Toyota' }] };
  } });
  h.context.location.search = '?year=2020&make=toyota';
  const opening = h.context.restoreRoute();
  assert.deepEqual(h.calls.selectorReads.map(({ path }) => path), [
    '/v1/catalog/years', '/v1/catalog/years/2020/makes?region=US&stored_only=1',
    '/v1/catalog/years/2020/makes/toyota/models?region=US&stored_only=1',
  ]);
  assert.equal(new Set(h.calls.selectorReads.map(({ signal }) => signal)).size, 1);
  assert.equal(h.element('model').disabled, true);
  assert.equal(h.element('configuration').disabled, true);
  assert.equal(h.context.vehicle, null);
  year.resolve({ items: [{ year: 2020 }] });
  await opening;
  assert.deepEqual(h.context.names.map(name => h.element(name).value), ['2020', 'toyota', '', '']);
  assert.equal(h.element('model').disabled, false);
  assert.equal(h.element('configuration').disabled, true);
  assert.deepEqual(h.calls.selections, []);
});

test('history only previews stored descendants until the new parent is validated', async () => {
  const h = selectedCheckoutHarness({ selectorRead(path) {
    if (path.endsWith('/years')) return { items: [{ year: 2020 }] };
    return { items: [{ id: 'different', name: 'Different make' }] };
  } });
  h.context.location.search = '?year=2020&make=different';
  await h.context.restoreRoute();
  assert.deepEqual(h.calls.selectorReads.map(({ path }) => path), [
    '/v1/catalog/years', '/v1/catalog/years/2020/makes?region=US&stored_only=1',
    '/v1/catalog/years/2020/makes/different/models?region=US&stored_only=1',
  ]);
  assert.deepEqual(h.calls.selections, []);
});

test('saved hierarchy restores all exact vehicle choices and query over prior state', async () => {
  const h = loginRouteHarness(`?year=2020&make=toyota&model=rav4&configuration=${routeConfiguration}&region=US&q=pump`);
  seedPriorRoute(h);
  await h.context.restoreRoute();
  assert.deepEqual(h.context.names.map(name => h.element(name).value), ['2020', 'toyota', 'rav4', routeConfiguration]);
  assert.equal(h.element('search').value, 'pump');
  assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: '' }]);
});

const savedPickerRoute = '?year=2024&make=buick-truck&model=envision-awd';
const savedPickerPaths = [
  '/v1/catalog/years',
  '/v1/catalog/years/2024/makes?region=US&stored_only=1',
  '/v1/catalog/years/2024/makes/buick-truck/models?region=US&stored_only=1',
  '/v1/catalog/years/2024/makes/buick-truck/models/envision-awd/configurations?region=US&stored_only=1',
];
const savedPickerRows = [
  { items: [{ year: 2024 }], complete: true },
  { items: [{ id: 'buick-truck', name: 'Buick Truck' }], complete: true },
  { items: [{ id: 'envision-awd', name: 'Envision AWD' }], complete: true },
  { items: [{ id: routeConfiguration, region: 'US', engine: '2.0' }], complete: true },
];

test('startup starts each saved picker read once and restores the hierarchy in parent order', async () => {
  const year = deferredAuthOperation();
  const earlyCalls = [];
  const initialSelectors = startSavedSelectorReads(new URLSearchParams(savedPickerRoute), async (path, { signal }) => {
    const index = earlyCalls.push({ path, signal }) - 1;
    return index === 0 ? year.promise : savedPickerRows[index];
  });
  assert.deepEqual(earlyCalls.map(({ path }) => path), savedPickerPaths);
  assert.equal(new Set(earlyCalls.map(({ signal }) => signal)).size, 1);
  const h = loginRouteHarness(savedPickerRoute);
  h.context.rows.configuration = [];
  h.element('configuration').disabled = true;
  const loading = h.context.restoreRoute(null, { initialSelectors });
  await new Promise(setImmediate);
  assert.equal(h.element('configuration').disabled, true);
  assert.deepEqual(h.calls.selectorReads, []);
  year.resolve(savedPickerRows[0]);
  await loading;
  assert.deepEqual(h.calls.selectorReads, []);
  assert.deepEqual(h.context.names.map(name => h.element(name).value), ['2024', 'buick-truck', 'envision-awd', '']);
  assert.equal(h.element('configuration').disabled, false);
  assert.equal(h.context.rows.configuration[0].id, routeConfiguration);
  assert.equal(earlyCalls[0].signal.aborted, true);
});

const storedPickerConfiguration = {
  id: routeConfiguration, year: 2024, make: 'Buick Truck', model: 'Envision AWD',
  region: 'US', engine: '2.0', complete: true,
};
const fullPickerYears = { items: [{ year: 2024 }, { year: 2022 }, { year: 2026 }], complete: true };

function setupSlowSavedYears(route, configuration = storedPickerConfiguration, makes = savedPickerRows[1]) {
  const year = deferredAuthOperation();
  const response = { items: [configuration], complete: true };
  const initialSelectors = startSavedSelectorReads(new URLSearchParams(route), async path => {
    const index = savedPickerPaths.indexOf(path);
    if (index === 0) return year.promise;
    if (index === 1) return makes;
    return index === 3 ? response : savedPickerRows[index];
  });
  const h = loginRouteHarness(route);
  const opening = h.context.restoreRoute(null, { initialSelectors });
  return { ...h, opening, year, initialSelectors };
}

for (const hasMake of [false, true]) {
  test(`saved ${hasMake ? 'year and make' : 'year'} opens its stored choices while the full year list loads`, async () => {
    const route = hasMake ? '?year=2024&make=buick-truck' : '?year=2024';
    const h = setupSlowSavedYears(route);
    await new Promise(setImmediate);
    const expected = ['2024', hasMake ? 'buick-truck' : '', '', ''];
    assert.deepEqual(h.context.names.map(name => h.element(name).value), expected);
    assert.equal(h.element('year').disabled, false);
    assert.equal(h.element('make').disabled, false);
    assert.equal(h.element('model').disabled, !hasMake);
    assert.equal(h.element('configuration').disabled, true);
    assert.deepEqual(h.calls.selections, []);

    h.year.resolve(fullPickerYears);
    await h.opening;
    assert.deepEqual(h.context.names.map(name => h.element(name).value), expected);
    assert.deepEqual(h.element('year').children.slice(1).map(option => option.value), ['2026', '2024', '2022']);
    assert.deepEqual(h.calls.selectorReads, []);
  });
}

test('a saved model preview cannot establish the year when the requested make is missing', async () => {
  const makes = { items: [{ id: 'ford', name: 'Ford' }], complete: true };
  const h = setupSlowSavedYears('?year=2024&make=buick-truck', undefined, makes);
  const rejected = assert.rejects(h.opening, /Unavailable choice/);
  await new Promise(setImmediate);
  assert.equal(h.element('year').disabled, true);
  assert.equal(h.element('model').disabled, true);
  assert.deepEqual(h.calls.selections, []);

  h.year.resolve(fullPickerYears);
  await rejected;
  assert.equal(h.element('year').value, '2024');
  assert.equal(h.element('model').disabled, true);
});

for (const exact of [false, true]) {
  test(`a verified saved ${exact ? 'configuration' : 'model'} is usable before its full year list`, async () => {
    const route = exact ? `${savedPickerRoute}&configuration=${routeConfiguration}&region=US` : savedPickerRoute;
    const h = setupSlowSavedYears(route);
    await new Promise(setImmediate);
    const expected = ['2024', 'buick-truck', 'envision-awd', exact ? routeConfiguration : ''];
    assert.deepEqual(h.context.names.map(name => h.element(name).value), expected);
    assert.equal(h.element('configuration').disabled, false);
    assert.equal(h.element('year').children.length, 2);
    assert.deepEqual(h.calls.selections, exact ? [{ configuration: routeConfiguration, region: 'US', article: '' }] : []);

    h.year.resolve(fullPickerYears);
    await h.opening;
    assert.deepEqual(h.context.names.map(name => h.element(name).value), expected);
    assert.deepEqual(h.element('year').children.slice(1).map(option => option.value), ['2026', '2024', '2022']);
    assert.deepEqual(h.calls.selectorReads, []);
  });
}

test('an inconsistent saved configuration cannot establish the year early', async () => {
  const route = `${savedPickerRoute}&configuration=${routeConfiguration}&region=US`;
  const h = setupSlowSavedYears(route, { ...storedPickerConfiguration, region: 'CA' });
  const rejected = assert.rejects(h.opening, /unavailable in the selected region/);
  await new Promise(setImmediate);
  assert.equal(h.element('configuration').disabled, true);
  assert.deepEqual(h.calls.selections, []);
  h.year.resolve(fullPickerYears);
  await rejected;
  assert.deepEqual(h.calls.selections, []);
});

test('a late year list cannot update a superseded saved picker', async () => {
  const h = setupSlowSavedYears(savedPickerRoute);
  await new Promise(setImmediate);
  assert.equal(h.element('configuration').disabled, false);
  h.context.invalidate();
  h.context.populate('year', [{ year: 2001 }], '2001');
  h.year.resolve(null);
  await h.opening;
  assert.deepEqual(h.element('year').children.slice(1).map(option => option.value), ['2001']);
  assert.equal(h.element('year').value, '2001');
  assert.deepEqual(h.calls.selectorReads, []);
});

test('the pending saved year list owns the dropdown refresh until its rows arrive', async () => {
  const h = setupSlowSavedYears(savedPickerRoute);
  const picker = { path: '/v1/catalog/years', incomplete: true };
  h.context.pickerStates.set('year', picker);
  await new Promise(setImmediate);
  assert.equal(h.element('year').disabled, false);
  assert.equal(picker.loading.current(), true);
  await h.context.refreshPicker('year');
  assert.deepEqual(h.calls.selectorReads, []);
  h.year.resolve(fullPickerYears);
  await h.opening;
  assert.equal(picker.loading, null);
  assert.equal(picker.incomplete, false);
});

test('early saved selectors skip independent or session-dependent routes', () => {
  for (const search of [
    '', '?year=upcoming&make=buick-truck', '?year=1700',
    ...['sample=1', 'demo=1', 'view=library', `order=${routeOrder}`, `configuration=${routeConfiguration}&q=brakes`,
      `configuration=${routeConfiguration}&region=US&article=${routeArticle}`].map(suffix => `${savedPickerRoute}&${suffix}`),
  ]) {
    assert.equal(startSavedSelectorReads(new URLSearchParams(search), async () => assert.fail(search)), null, search);
  }
});

test('early reads stop at the first unresolved selector and keep incomplete year rows', async () => {
  const calls = [];
  const partial = { items: [{ year: 2023 }], complete: false, hydrating: true };
  const initial = startSavedSelectorReads(new URLSearchParams('?year=2024&model=envision-awd'), async path => {
    calls.push(path);
    return partial;
  });
  assert.deepEqual(calls, savedPickerPaths.slice(0, 2));
  assert.equal(await initial.reads.year, partial);
  initial.abort();
});

test('the first incomplete year read can restore the saved choice without a second request', async () => {
  const partial = { ...savedPickerRows[0], complete: false, hydrating: true };
  const initialSelectors = startSavedSelectorReads(new URLSearchParams('?year=2024'), async path => {
    if (path === '/v1/catalog/years') return partial;
    assert.equal(path, savedPickerPaths[1]);
    return savedPickerRows[1];
  });
  const h = selectorOptionsHarness(() => assert.fail('the saved year is already available'));
  h.context.selectorPath = () => '/v1/catalog/years';
  await h.load('2024', undefined, initialSelectors.reads.year, 'year');
  assert.deepEqual(h.requests, []);
  assert.deepEqual(h.displayed, [partial.items]);
  assert.equal(h.$('year').value, '2024');
  initialSelectors.abort();
});

test('other stored years are visible while waiting for a missing saved year', async () => {
  const partial = { items: [{ year: 2023 }], complete: false, hydrating: true };
  const complete = { items: [...partial.items, { year: 2024 }], complete: true };
  const pending = deferredAuthOperation();
  const h = selectorOptionsHarness(() => pending.promise);
  h.context.selectorPath = () => '/v1/catalog/years';
  const opening = h.load('2024', undefined, Promise.resolve(partial), 'year');
  await new Promise(setImmediate);
  assert.deepEqual(h.displayed, [partial.items]);
  assert.equal(h.$('year').disabled, false);
  assert.equal(h.$('year').value, '');
  assert.deepEqual(h.requests, ['/v1/catalog/years']);
  pending.resolve(complete);
  await opening;
  assert.deepEqual(h.displayed, [partial.items, complete.items]);
  assert.equal(h.$('year').value, '2024');
});

test('superseding a saved picker restore aborts every early request and leaves stale choices hidden', async () => {
  const response = deferredAuthOperation();
  let signal;
  const initialSelectors = startSavedSelectorReads(new URLSearchParams(savedPickerRoute), async (_path, options) => {
    signal = options.signal;
    return response.promise;
  });
  const h = loginRouteHarness(savedPickerRoute);
  const loading = h.context.restoreRoute(null, { initialSelectors });
  h.context.invalidate();
  assert.equal(signal.aborted, true);
  response.resolve(savedPickerRows[0]);
  await loading;
  assert.equal(h.element('year').disabled, true);
  assert.equal(h.element('configuration').disabled, true);
  assert.deepEqual(h.calls.selectorReads, []);
});

test('a changed startup route discards early selector rows and reads only its own hierarchy', async () => {
  let signal;
  const initialSelectors = startSavedSelectorReads(new URLSearchParams(savedPickerRoute), async (_path, options) => {
    signal = options.signal;
    return null;
  });
  const h = loginRouteHarness('?year=2025', { selectorRead(path) {
    if (path.endsWith('/years')) return { items: [{ year: 2025 }] };
    return { items: [{ id: 'toyota', name: 'Toyota' }] };
  } });
  await h.context.restoreRoute(null, { initialSelectors });
  assert.equal(signal.aborted, true);
  assert.deepEqual(h.calls.selectorReads.map(({ path }) => path), [
    '/v1/catalog/years', '/v1/catalog/years/2025/makes?region=US&stored_only=1',
  ]);
  assert.deepEqual(h.context.names.map(name => h.element(name).value), ['2025', '', '', '']);
});

test('a complete saved vehicle overlaps public reads but validates parents before opening the exact scope', async () => {
  const year = deferredAuthOperation();
  const h = loginRouteHarness(selectedCheckoutRoute, { selectorRead(path) {
    if (path.endsWith('/years')) return year.promise;
    if (path.includes('/configurations?')) return { items: [{ id: routeConfiguration, region: 'US', engine: '2.0' }] };
    if (path.includes('/models?')) return { items: [{ id: 'rav4', name: 'RAV4' }] };
    return { items: [{ id: 'toyota', name: 'Toyota' }] };
  } });
  const restored = h.context.restoreRoute();
  assert.deepEqual(h.calls.selectorReads.map(({ path }) => path), [
    '/v1/catalog/years', '/v1/catalog/years/2020/makes?region=US&stored_only=1',
    '/v1/catalog/years/2020/makes/toyota/models?region=US&stored_only=1',
    '/v1/catalog/years/2020/makes/toyota/models/rav4/configurations?region=US&stored_only=1',
  ]);
  assert.equal(new Set(h.calls.selectorReads.map(r => r.signal)).size, 1);
  await new Promise(setImmediate);
  assert.deepEqual(h.calls.selections, []);
  assert.equal(h.element('configuration').disabled, true);
  year.resolve({ items: [{ year: 2020 }] });
  await restored;
  assert.deepEqual(h.calls.selections, [{ configuration: routeConfiguration, region: 'US', article: '' }]);
});

test('a saved selector never opens a different region or falls through a missing parent', async () => {
  const wrongRegion = loginRouteHarness(selectedCheckoutRoute.replace('region=US', 'region=CA'));
  await assert.rejects(wrongRegion.context.restoreRoute(), /unavailable in the selected region/);
  assert.deepEqual(wrongRegion.calls.selections, []);
  assert.equal(wrongRegion.context.vehicle, null);

  const missingParent = loginRouteHarness(selectedCheckoutRoute, { selectorRead(path) {
    if (path.endsWith('/years')) return { items: [] };
    throw new Error('A prefetched descendant can fail independently');
  } });
  await assert.rejects(missingParent.context.restoreRoute(), /Unavailable choice/);
  assert.deepEqual(missingParent.calls.selections, []);
  assert.equal(missingParent.element('configuration').disabled, true);
});

test('My vehicles activation clears the previous vehicle search and selector options in its saved URL', async () => {
  const h = loginRouteHarness('?view=library');
  const location = { pathname: '/workshop/', search: '?view=library&q=old+vehicle+only' };
  seedPriorRoute(h);
  const makeElement = (tag, text) => ({
    tag, textContent: text, children: [], events: {},
    append(...nodes) { this.children.push(...nodes); },
    addEventListener(name, callback) { this.events[name] = callback; },
  });
  const list = makeElement('ul');
  list.replaceChildren = () => { list.children = []; };
  const get = h.context.$;
  get('library-more').removeAttribute = () => {};
  h.context.$ = id => id === 'library-items' ? list : get(id);
  Object.assign(h.context, {
    location, URLSearchParams, validLibrary, element: makeElement,
    history: { pushState(_state, _title, url) { location.search = new URL(url, 'https://workshop.example').search; } },
    currentOrder: '', libraryPageRequest: null, libraryCursor: null, clearReader() {},
    session: { state: { authenticated: true } },
    async requestJSON(path, options) {
      assert.equal(path, '/v1/workshop/library?limit=20');
      assert.equal(options.headers.Prefer, 'workshop-library-catalog-empty');
      return { version: 'v1', next_cursor: null, items: [{
        configuration_id: routeConfiguration, region: 'US', library_item_id: routeOrder,
        label: 'Purchased vehicle', access_state: 'viewable', granted_at: '2026-11-16T00:00:00Z',
      }, {
        configuration_id: '44444444-4444-4444-8444-444444444444', region: 'CA',
        library_item_id: '55555555-5555-4555-8555-555555555555', label: 'Other purchased vehicle',
        access_state: 'paid', granted_at: '2026-11-16T00:00:00Z', catalog_available: false,
      }, {
        configuration_id: '66666666-6666-4666-8666-666666666666', region: 'US',
        library_item_id: '77777777-7777-4777-8777-777777777777', label: 'Revoked vehicle',
        access_state: 'revoked', granted_at: null,
      }, {
        configuration_id: '99999999-9999-4999-8999-999999999999', region: 'US',
        library_item_id: '88888888-8888-4888-8888-888888888888', label: 'Empty catalog vehicle',
        access_state: 'paid', granted_at: '2026-11-16T00:00:00Z', catalog_empty: true,
      }] };
    },
  });
  runInNewContext(appSection('function updateURL(', 'function rememberOrderRoute(') +
    appSection('function clearLibrary(', 'function resetSourceReview(') +
    appSection('async function library(', 'function clearReader('), h.context);
  await h.context.library({ signal: new AbortController().signal, current: () => true });
  assert.equal(list.children[0].children[1].textContent, 'Articles available');
  assert.equal(list.children[1].children[0].textContent, 'Other purchased vehicle / CA');
  assert.equal(list.children[1].children[1].textContent, 'Owned. Service information is currently unavailable.');
  assert.equal(list.children[1].children.length, 2);
  assert.equal(list.children[2].children[1].textContent, 'Access revoked. Contact support.');
  assert.equal(list.children[2].children.length, 2);
  assert.equal(list.children[3].children[1].textContent, 'Owned. No articles are currently available for this vehicle.');
  assert.equal(list.children[3].children[2].textContent, 'Check article availability');
  list.children[0].children[2].events.click();
  assert.equal(h.element('search').value, '');
  const route = new URLSearchParams(location.search);
  assert.equal(route.get('configuration'), routeConfiguration);
  assert.equal(route.get('region'), 'US');
  for (const name of ['year', 'make', 'model', 'q', 'view']) assert.equal(route.has(name), false);
  for (const name of h.context.names) {
    assert.equal(h.context.rows[name].length, 0);
    assert.equal(h.element(name).disabled, true);
  }
  list.children[3].children[2].events.click();
  assert.deepEqual(h.calls.selections, [
    { configuration: routeConfiguration, region: 'US', article: '' },
    { configuration: '99999999-9999-4999-8999-999999999999', region: 'US', article: '' },
  ]);
});

for (const outcome of ['canceled', 'failed']) {
  test(`login route stays put after ${outcome} sign-in without checkout replay`, async () => {
    const h = loginRouteHarness('?view=library', { authenticate: false });
    await h.context.signIn();
    assert.equal(h.calls.signIns, 1);
    assert.equal(h.calls.routes, 0);
    assert.equal(h.calls.invalidations, 0);
    assert.equal(h.calls.libraries, 0);
    assert.deepEqual(h.calls.selections, []);
    assert.deepEqual(h.calls.orders, []);
    assert.deepEqual(h.calls.options, []);
    assert.equal(h.calls.checkouts, 0);
    assert.equal(h.context.signingIn, false);
  });
}

test('login route preserves a rejected sign-in and resets its guard without restoring', async () => {
  const error = new Error('Sign-in transport unavailable');
  const h = loginRouteHarness('?view=library', { signInError: error });
  await assert.rejects(h.context.signIn(), received => received === error);
  assert.equal(h.calls.signIns, 1);
  assert.equal(h.calls.routes, 0);
  assert.equal(h.calls.invalidations, 0);
  assert.equal(h.calls.libraries, 0);
  assert.equal(h.calls.checkouts, 0);
  assert.equal(h.context.signingIn, false);
});

test('login route shares the existing sign-in guard rather than starting another popup', async () => {
  let finish;
  const login = new Promise(resolve => { finish = resolve; });
  const h = loginRouteHarness('?view=library', { login: () => login });
  const first = h.context.signIn();
  assert.equal(h.context.signingIn, true);
  await h.context.signIn();
  assert.equal(h.calls.signIns, 1);
  assert.equal(h.calls.checkoutClears, 1);
  assert.equal(h.calls.routes, 0);
  finish();
  await first;
  assert.equal(h.calls.libraries, 1);
  assert.equal(h.calls.routes, 1);
  assert.equal(h.calls.checkouts, 0);
  assert.equal(h.context.signingIn, false);
});

test('login route awaits restoration completion before signIn resolves', async () => {
  let finish;
  const library = new Promise(resolve => { finish = resolve; });
  const h = loginRouteHarness('?view=library', { library: () => library });
  let completed = false;
  const pending = h.context.signIn().then(() => { completed = true; });
  await new Promise(setImmediate);
  assert.equal(h.calls.libraries, 1);
  assert.equal(completed, false);
  finish();
  await pending;
  assert.equal(completed, true);
  assert.equal(h.calls.checkouts, 0);
});

test('navigation invalidation clears prior order status', () => {
  const button = { hidden: false };
  const context = {
    currentOrder: '11111111-1111-4111-8111-111111111111',
    navigation: { clear() {} },
    clearProtected() {},
    $: id => { assert.equal(id, 'check-order'); return button; },
  };
  runInNewContext(appSection('function invalidate(', 'async function operation('), context);
  context.invalidate();
  assert.equal(button.hidden, true);
  assert.equal(context.currentOrder, '');
});

function orderStatusHarness(response, { selectionError = null } = {}) {
  const nodes = {
    'check-order': { hidden: true },
    'purchase-message': { textContent: '' },
  };
  let checkoutClears = 0;
  let selectionCalls = 0;
  const statuses = [];
  const context = {
    document: {},
    currentOrder: '', paidOrder: '', unconfirmedOrder: null, vehicle: null, quote: null, merchant: null, access: 'missing',
    URLSearchParams, location: { pathname: '/workshop/', search: `?order=${orderID}` },
    history: { replaceState() { assert.fail('the known order route should not need rewriting'); } },
    $: id => nodes[id],
    validScope, scope: () => ({ configuration_id: context.vehicle?.id, region: context.vehicle?.region }),
    validQuote: () => false, purchaseConfiguration: () => false,
    navigation: { clear() {} }, clearProtected() {}, clearOrderRoute() {},
    status(message) { statuses.push(message); }, renderPurchase() {}, show() {}, async selectVehicle() {
      const error = Array.isArray(selectionError) ? selectionError[selectionCalls] : selectionError;
      selectionCalls++;
      if (error) throw error;
    },
    checkout: { clear() { checkoutClears++; } },
    async pollOrder(id, { onUpdate }) {
      assert.equal(id, orderID);
      if (response instanceof Error) throw response;
      onUpdate(response);
      return response;
    },
  };
  runInNewContext(
    appSection('function invalidate(', 'async function operation(') +
    appSection('function rememberOrderRoute(', 'function clearOrderRoute(') +
    appSection('async function checkOrder(', 'async function purchase()'),
    context,
  );
  return {
    context, button: nodes['check-order'], statuses,
    checkoutClears: () => checkoutClears,
    check: () => context.checkOrder({ current: () => true, signal: {} }, orderID),
  };
}

for (const state of ['paid', 'expired', 'canceled', 'revoked']) {
  test(`order status clears terminal action after ${state}`, async () => {
    const response = {
      version: 'v1', order_id: orderID, ...scope, state,
      retry_disposition: ['expired', 'canceled'].includes(state) ? 'new_key' : 'do_not_repay',
      timedOut: false,
    };
    const h = orderStatusHarness(response);
    await h.check();
    assert.equal(h.context.currentOrder, '');
    assert.equal(h.button.hidden, true);
    assert.equal(h.checkoutClears(), ['expired', 'canceled'].includes(state) ? 1 : 0);
  });
}

test('order status clears missing action on current 404', async () => {
  const error = Object.assign(new Error('Order not found'), { status: 404 });
  const h = orderStatusHarness(error);
  await assert.rejects(h.check(), received => received === error);
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.button.hidden, true);
  assert.equal(h.checkoutClears(), 1);
});

test('paid article 404 keeps the settled order and offers status recheck, not purchase retry', async () => {
  const error = Object.assign(new Error('Article index not found'), { status: 404 });
  const h = orderStatusHarness({
    version: 'v1', order_id: orderID, ...scope, state: 'paid',
    retry_disposition: 'do_not_repay', timedOut: false,
  }, { selectionError: error });
  await h.check();
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.button.hidden, false);
  assert.equal(h.checkoutClears(), 0);
  assert.equal(h.context.access, 'pending');
  assert.match(h.statuses.at(-1), /do not pay again/);
});

test('paid access missing keeps status action without inviting repayment', async () => {
  const error = Object.assign(new Error('Access not ready'), {
    status: 403, code: 'ENTITLEMENT_REQUIRED',
  });
  const h = orderStatusHarness({
    version: 'v1', order_id: orderID, ...scope, state: 'paid',
    retry_disposition: 'do_not_repay', timedOut: false,
  }, { selectionError: [error, null] });
  await h.check();
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.button.hidden, false);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.checkoutClears(), 0);
  assert.match(h.statuses.at(-1), /Payment received.*do not pay again/);
  await h.check();
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.button.hidden, true);
});

function paidPurchaseLifecycleHarness(selectionErrors, { realArticleIndex = false, afterPartial = null, articleReadResponses = null, articleOpenError = null, orderResponses = null } = {}) {
  const navigation = new NavigationGeneration();
  const searchNavigation = new NavigationGeneration();
  const nodes = new Map();
  const $ = id => {
    if (!nodes.has(id)) {
      const attributes = new Map();
      const listeners = new Map();
      nodes.set(id, {
        hidden: false, disabled: false, checked: id === 'agreement', value: '',
        textContent: '', dataset: {}, children: [],
        get options() { return this.children; },
        replaceChildren(...children) { this.children = children; this.value = ''; },
        append(...children) { this.children.push(...children); },
        setAttribute(name, value) { attributes.set(name, value); },
        getAttribute(name) { return attributes.get(name) ?? null; },
        removeAttribute(name) { attributes.delete(name); },
        addEventListener(type, listener) { listeners.set(type, listener); },
        click() { return listeners.get('click')(); },
        focus() { context.document.activeElement = this; },
      });
    }
    return nodes.get(id);
  };
  const location = {
    pathname: '/workshop/',
    search: `?configuration=${scope.configuration_id}&region=${scope.region}`,
    assign() { throw new Error('Unexpected hosted checkout'); },
  };
  const history = {
    replaceState(_state, _unused, url) { location.search = new URL(url, 'https://workshop.example').search; },
    pushState(_state, _unused, url) { location.search = new URL(url, 'https://workshop.example').search; },
  };
  const statuses = [];
  let checkoutStarts = 0, orderReads = 0, selections = 0;
  const nextOrder = (id) => {
    assert.equal(id, orderID);
    orderReads++;
    const paid = { version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' };
    const response = orderResponses ? orderResponses.shift() : paid;
    if (response instanceof Error) throw response;
    return response;
  };
  const context = {
    $, location, history, URLSearchParams, URL, uuid, validScope, validQuote,
    purchaseConfiguration, configurationLabel, navigation, searchNavigation, rows: {},
    Option: function(text, value) { return { text, value }; },
    document: { title: '', body: { dataset: {} }, visibilityState: 'visible', createTextNode: text => ({ textContent: text }) },
    element: (tag, text) => ({ tag, textContent: text }),
    names: ['year', 'make', 'model', 'configuration'],
    vehicle: { id: scope.configuration_id, region: scope.region }, quote,
    merchant: merchantFixture(), merchantRequest: null, access: 'missing', currentOrder: '', paidOrder: null, unconfirmedOrder: null,
    articles: [], indexCatalogEmpty: false, searchItems: null, searchQuery: '', searchPending: false,
    searchComplete: false, searchError: false, searchTimer: null,
    sourceRevision: 0,
    clearTimeout() {},
    sessionEstablished: true, sessionRequest: null, signingIn: false,
    session: { state: { authenticated: true, ready: true, csrf: 'test-csrf' },
      async bootstrap() {}, clear() {
        context.session.state.authenticated = false;
        context.session.state.ready = false;
        context.renderPurchase();
      } },
    scope: () => ({ configuration_id: context.vehicle?.id, region: context.vehicle?.region }),
    checkout: { read: () => null, async start() {
      checkoutStarts++;
      return { version: 'v1', ...scope, order_id: orderID, state: 'processing' };
    }, clear() {} },
    readOrder: (id, { signal }) => readOrder(id, { signal, request: async () => nextOrder(id) }),
    async pollOrder(id, { onUpdate }) {
      const response = nextOrder(id);
      onUpdate(response);
      return response;
    },
    async selectVehicle() {
      const error = selectionErrors[selections++];
      if (error) throw error;
      context.access = 'owned';
    },
    clearProtected() { context.access = 'unknown'; },
    show() {},
    status(message, options = {}) { statuses.push({ message, options }); },
    stage() {}, articlePath: () => `/v1/catalog/vehicles/${scope.configuration_id}/articles`,
    filterArticles,
    renderArticleLinks(items) { $('articles').replaceChildren(...items.map(item => ({ id: item.id }))); },
    async loadArticle() { if (articleOpenError) throw articleOpenError; },
    readCollection: (read, options) => readCollection(read, {
      ...options, wait: async () => { if (afterPartial) await afterPartial(context); },
    }),
    async requestJSON(path) {
      if (!realArticleIndex) return merchantFixture();
      if (path.startsWith('/v1/workshop/quote')) return quote;
      if (path.includes('/articles')) {
        if (articleReadResponses) {
          const response = articleReadResponses.shift();
          if (response instanceof Error) throw response;
          return response;
        }
        if (!context.articles.length) return { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false };
        throw selectionErrors[0];
      }
      return merchantFixture();
    },
  };
  installArticleRequestPath(context);
  runInNewContext(
    (realArticleIndex ? appSection('function show(', 'function clearProtected()') : '') +
    (realArticleIndex ? appSection('function clearProtected()', 'function invalidate()') : '') +
    appSection('function invalidate(', 'function updateURL(') +
    appSection('function updateURL(', 'function selectorPath(') +
    appSection('function renderPurchase(', 'async function selectVehicle(') +
    (realArticleIndex ? appSection('async function selectVehicle(', 'function renderArticleLinks(') : '') +
    (realArticleIndex ? appSection('function renderArticles(', 'const assetID =') : '') +
    (articleOpenError ? appSection('function openArticle(', 'function validSourceURL(') : '') +
    appSection('async function checkOrder(', 'async function signIn()') +
    appSection('$("check-order").addEventListener', '$("search").addEventListener("input"') +
    appSection('async function bootstrap(', 'for (const [index, name] of names.entries())') +
    appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'),
    context,
  );
  return { context, $, location, statuses,
    checkoutStarts: () => checkoutStarts, orderReads: () => orderReads };
}

test('loopback TEST notices allow Buy and a deliberate retry after cancellation', async () => {
  const canceled = {
    version: 'v1', order_id: orderID, ...scope, state: 'canceled',
    retry_disposition: 'new_key',
  };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [canceled, canceled] });
  h.location.origin = 'http://localhost:3013';
  h.$('test-banner').hidden = false;
  h.context.testStripeMode = true;
  const start = h.context.checkout.start;
  h.context.checkout.start = (selection, csrf, options) => {
    assert.equal(options.mode, 'stripe_test');
    return start(selection, csrf, options);
  };
  for (const key of ['terms_url', 'privacy_url', 'refund_url', 'contact_url'])
    h.context.merchant[key] = `${h.location.origin}/workshop/test-notices/${key.slice(0, -4)}`;

  h.context.renderPurchase();
  assert.equal(h.$('purchase-action').disabled, false);
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.orderReads(), 1);
  assert.equal(h.$('purchase-action').disabled, false);
  assert.match(h.statuses.at(-1).message, /Choose Buy again/);
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 2);
  assert.equal(h.orderReads(), 2);
});

test('purchase consent is reserved for an actionable quote and still requires agreement', async () => {
  const h = paidPurchaseLifecycleHarness([]);
  h.context.session.state.authenticated = false;
  h.context.renderPurchase();
  assert.equal(h.$('purchase-action').textContent, 'Sign in with Google');
  assert.equal(h.$('purchase-consent').hidden, true);
  assert.equal(h.$('agreement').disabled, true);
  assert.equal(h.$('purchase-terms').hidden, false);

  h.context.session.state.authenticated = true;
  h.context.renderPurchase();
  assert.equal(h.$('purchase-action').disabled, false);
  assert.equal(h.$('purchase-consent').hidden, false);
  assert.equal(h.$('agreement').disabled, false);
  h.$('agreement').checked = false;
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 0);
  assert.equal(h.context.document.activeElement, h.$('agreement'));
  assert.equal(h.$('agreement').getAttribute('aria-invalid'), 'true');
  assert.match(h.$('agreement-error').textContent, /Agree to the purchase terms/);

  const held = deferredAuthOperation();
  const start = h.context.checkout.start;
  h.context.checkout.start = async (...args) => {
    await held.promise;
    return start(...args);
  };
  h.$('agreement').checked = true;
  const submitting = h.context.purchase();
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-consent').hidden, true);
  assert.equal(h.$('agreement').disabled, true);
  assert.equal(h.$('agreement').getAttribute('aria-invalid'), null);
  held.resolve();
  await submitting;
  assert.equal(h.checkoutStarts(), 1);
});

test('paid catalog withdrawal through purchase never invites repayment or a no-op purchase retry', async () => {
  const withdrawn = Object.assign(new Error('Catalog withdrawn'), { status: 410, code: 'CATALOG_WITHDRAWN' });
  const h = paidPurchaseLifecycleHarness([withdrawn]);
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.context.access, 'pending');
  assert.match(h.$('purchase-message').textContent, /Payment received.*do not pay again/);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-consent').hidden, true);
  assert.equal(h.$('agreement').disabled, true);
  assert.equal(h.$('purchase-terms').hidden, false);
  assert.equal(h.$('policy-links').children.filter(node => node.tag === 'a').length, 4);
  assert.equal(h.$('tax-notice').textContent, h.context.merchant.tax_notice);
  assert.match(h.statuses.at(-1).message, /do not pay again/);
  assert.equal(h.statuses.at(-1).options.retry, undefined);
});

test('paid return preserves confirmed payment while the entitled index is still opening', async () => {
  const index = deferredAuthOperation();
  const h = paidPurchaseLifecycleHarness([], { realArticleIndex: true, articleReadResponses: [index.promise] });
  h.location.search = `?order=${orderID}`;
  const opening = h.context.restoreRoute();
  await new Promise(setImmediate);
  assert.equal(h.context.access, 'unknown', 'payment confirmation does not grant article access');
  assert.equal(h.$('purchase-action').textContent, 'Payment received');
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-price').hidden, true);
  assert.match(h.$('purchase-message').textContent, /Payment received.*do not pay again/);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.equal(h.$('articles').children.length, 0);

  index.resolve({ items: [{ id: routeArticle, title: 'Private article' }], complete: true, hydrating: false });
  await opening;
  assert.equal(h.context.access, 'owned');
  assert.equal(h.$('purchase-action').textContent, 'Open articles');
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
  assert.equal(h.checkoutStarts(), 0);
});

test('paid partial article index is cleared when a later poll withdraws the catalog', async () => {
  const withdrawn = Object.assign(new Error('Catalog withdrawn'), { status: 410, code: 'CATALOG_WITHDRAWN' });
  const h = paidPurchaseLifecycleHarness([withdrawn], { realArticleIndex: true });
  await h.context.purchase();
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.context.articles.length, 0);
  assert.equal(h.$('articles').children.length, 0);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
});

test('search during a partial paid index keeps its order resume route after withdrawal', async () => {
  const withdrawn = Object.assign(new Error('Catalog withdrawn'), { status: 410, code: 'CATALOG_WITHDRAWN' });
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([withdrawn], {
    realArticleIndex: true,
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
      withdrawn, required,
    ],
    afterPartial(context) {
      context.$('search').value = 'pump';
      context.updateURL({ replace: true });
    },
  });
  await h.context.purchase();
  assert.equal(h.context.access, 'pending');
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.equal(h.$('articles').children.length, 0);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  await h.context.recheck();
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.context.currentOrder, orderID);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
});

test('a useful partial paid index can save and restore the exact reader before hydration finishes', async () => {
  let partialReads = 0;
  const restored = [];
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    articleReadResponses: [
      { items: [], hydrating: true, complete: false },
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
    ],
    async afterPartial(context) {
      const params = new URLSearchParams(h.location.search);
      if (++partialReads === 1) {
        assert.equal(params.get('order'), orderID);
        return;
      }
      assert.equal(params.has('order'), false);
      assert.equal(params.get('configuration'), scope.configuration_id);
      assert.equal(params.get('region'), scope.region);
      assert.equal(context.paidOrder?.id, orderID);
      context.updateURL({ article: routeArticle });
      assert.equal(new URLSearchParams(h.location.search).has('order'), false);
      await context.restoreRoute();
    },
  });
  h.location.search = `?order=${orderID}`;
  h.context.session.state.mode = 'firebase';
  h.context.loadArticle = async (id, _g, options) => {
    restored.push({ id, configuration: h.context.vehicle.id, region: h.context.vehicle.region, savedLink: options.savedLink });
    return true;
  };
  await h.context.restoreRoute();
  assert.equal(partialReads, 2);
  assert.equal(h.orderReads(), 1);
  assert.equal(h.checkoutStarts(), 0);
  assert.deepEqual(restored, [{ id: routeArticle, configuration: scope.configuration_id, region: scope.region, savedLink: true }]);
});

test('opening a partial paid article cannot turn its entitlement error into Buy', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
    ],
    articleOpenError: required,
    async afterPartial(context) {
      assert.equal(context.$('articles').children.length, 1);
      context.openArticle(routeArticle);
      await new Promise(setImmediate);
    },
  });
  await h.context.purchase();
  assert.equal(h.orderReads(), 1);
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.$('articles').children.length, 0);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  assert.equal(h.$('purchase-action').disabled, true);
});

for (const [label, statusCode] of [['not found', 404], ['withdrawn', 410], ['unavailable', 503]]) {
  test(`opening a partial paid article that is ${label} keeps no-repay pending UI`, async () => {
    const error = Object.assign(new Error(`Article ${label}`), { status: statusCode, code: 'HTTP_ERROR' });
    const h = paidPurchaseLifecycleHarness([], {
      realArticleIndex: true,
      articleReadResponses: [
        { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
      ],
      articleOpenError: error,
      async afterPartial(context) {
        context.openArticle(routeArticle);
        await new Promise(setImmediate);
      },
    });
    await h.context.purchase();
    assert.equal(h.context.access, 'pending');
    assert.equal(h.context.currentOrder, orderID);
    assert.equal(h.context.paidOrder?.id, orderID);
    assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
    assert.equal(h.$('check-order').hidden, false);
    assert.equal(h.$('articles').children.length, 0);
    assert.match(h.$('purchase-message').textContent, /do not pay again/);
    assert.doesNotMatch(h.$('purchase-action').textContent, /Buy|Open articles/);
    assert.equal(h.$('purchase-action').disabled, true);
  });
}

test('revoked partial paid article clears terminal order action and resume route', async () => {
  const revoked = Object.assign(new Error('Access revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
    ],
    articleOpenError: revoked,
    async afterPartial(context) {
      context.openArticle(routeArticle);
      await new Promise(setImmediate);
    },
  });
  await h.context.purchase();
  assert.equal(h.context.access, 'revoked');
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.context.paidOrder, null);
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(h.$('articles').children.length, 0);
  assert.match(h.$('purchase-message').textContent, /Access revoked/);
});

test('unauthorized partial paid article requires sign-in and retains owner-only order recovery', async () => {
  const unauthorized = Object.assign(new Error('Sign in again'), { status: 401 });
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: false, complete: true },
    ],
    articleOpenError: unauthorized,
    async afterPartial(context) {
      context.openArticle(routeArticle);
      await new Promise(setImmediate);
    },
  });
  await h.context.purchase();
  assert.equal(h.context.session.state.authenticated, false);
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.equal(h.$('articles').children.length, 0);
  assert.match(h.$('purchase-action').textContent, /Sign in/);
  h.context.session.state.authenticated = true;
  h.context.session.state.ready = true;
  await h.context.restoreRoute();
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.access, 'owned');
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
});

test('order 404 on status recheck after partial paid index clears private rows without inviting repayment', async () => {
  const missingOrder = Object.assign(new Error('Order not found'), { status: 404 });
  const paid = { version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' };
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    orderResponses: [paid, missingOrder],
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
    ],
    async afterPartial(context) {
      assert.equal(context.$('articles').children.length, 1);
      await context.operation(g => context.checkOrder(g, orderID));
    },
  });
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.$('welcome').hidden, false);
  assert.match(h.$('purchase-message').textContent, /do not pay again/);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  assert.equal(h.$('purchase-action').disabled, true);
});

test('revoked order on status recheck after partial paid index shows terminal guidance', async () => {
  const paid = { version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' };
  const revoked = { version: 'v1', ...scope, order_id: orderID, state: 'revoked', retry_disposition: 'do_not_repay' };
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true,
    orderResponses: [paid, revoked],
    articleReadResponses: [
      { items: [{ id: routeArticle, title: 'Private article' }], hydrating: true, complete: false },
    ],
    async afterPartial(context) {
      assert.equal(context.$('articles').children.length, 1);
      await context.operation(g => context.checkOrder(g, orderID));
    },
  });
  await h.context.purchase();
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.access, 'revoked');
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.context.paidOrder, null);
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.$('welcome').hidden, false);
  assert.equal(h.$('catalog').hidden, true);
  assert.match(h.$('purchase-message').textContent, /Access revoked/);
});

test('processing order alone does not claim confirmed paid access on an entitlement error', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.currentOrder = orderID;
  await h.context.operation(async () => { throw required; });
  assert.equal(h.context.access, 'missing');
});

test('the authorized owned vehicle shows its article action without purchase pricing', () => {
  const { context, $ } = paidPurchaseLifecycleHarness([]);
  for (const availableQuote of [null, quote]) {
    context.quote = availableQuote;
    context.access = 'owned';
    context.renderPurchase();
    assert.equal($('purchase-price').hidden, true);
    assert.equal($('purchase-price').textContent, '');
    assert.equal($('purchase-action').textContent, 'Open articles');
    assert.equal($('purchase-action').disabled, false);
    assert.match($('purchase-message').textContent, /Owned/);

    context.access = 'missing';
    context.renderPurchase();
    assert.equal($('purchase-price').hidden, !availableQuote);
    assert.equal($('purchase-price').textContent, availableQuote ? '$20 USD · one-time' : '');
    assert.equal($('purchase-action').hidden, !availableQuote);
    assert.equal($('purchase-action').disabled, !availableQuote);
  }
});

test('purchase availability status reports unavailable without a quote', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.quote = null;
  await h.context.operation(async () => { throw required; });
  assert.equal(h.context.access, 'missing');
  assert.equal(h.$('purchase-action').disabled, true);
  assert.match(h.$('purchase-message').textContent, /Purchasing is currently unavailable/);
  assert.match(h.statuses.at(-1).message, /Purchasing is currently unavailable/);
});

test('purchase availability status reports unavailable without merchant configuration', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.merchant = { enabled: false };
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').hidden, true);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-price').hidden, true);
  assert.equal(h.$('purchase-price').textContent, '');
  assert.match(h.statuses.at(-1).message, /Purchasing is currently unavailable/);
});

test('purchase availability status keeps valid quote invitation', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').disabled, false);
  assert.equal(h.statuses.at(-1).message, 'This vehicle is available to purchase.');
});

test('purchase availability status requests sign-in instead of inviting purchase', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.session.state.authenticated = false;
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').textContent, 'Sign in with Google');
  assert.equal(h.$('purchase-action').disabled, false);
  assert.match(h.statuses.at(-1).message, /Sign in to check access and purchase/);
});

test('purchase availability status keeps validated processing order no-repay guidance', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const processing = { version: 'v1', order_id: orderID, ...scope, state: 'processing', retry_disposition: 'do_not_repay', timedOut: true };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing] });
  await h.context.operation(g => h.context.checkOrder(g, orderID));
  assert.equal(h.context.unconfirmedOrder?.id, orderID);
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-action').textContent, 'Payment pending');
  assert.match(h.statuses.at(-1).message, /confirmation is pending.*do not pay again/i);
});

test('an order-only return shows the pending vehicle and status without a purchase price', async () => {
  const label = '2024 Example Car 2.0 L';
  const open = { version: 'v1', order_id: orderID, ...scope, state: 'open', configuration_label: label,
    retry_disposition: 'do_not_repay', timedOut: true };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [open] });
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.$('purchase-selection').textContent, `${label} / ${scope.region}`);
  assert.equal(h.$('purchase-price').hidden, true);
  assert.equal(h.$('purchase-price').textContent, '');
  assert.equal(h.$('purchase-action').textContent, 'Checkout open');
  assert.match(h.$('purchase-message').textContent, /Checkout is open/);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.checkoutStarts(), 0);
});

test('resuming a returned checkout rechecks the exact order and opens its original session', async () => {
  const checkoutURL = 'https://checkout.stripe.com/c/pay/cs_test_original';
  const open = { version: 'v1', order_id: orderID, ...scope, state: 'open',
    retry_disposition: 'do_not_repay', checkout_url: checkoutURL, provider_expires_at: '2099-01-01T00:00:00Z' };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [open, open] });
  const destinations = [];
  h.location.assign = url => destinations.push(url);
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.$('purchase-action').textContent, 'Continue checkout');
  assert.equal(h.$('purchase-action').disabled, false);
  assert.equal(h.$('purchase-consent').hidden, true);
  assert.equal(h.context.quote, null);
  assert.equal(h.context.unconfirmedOrder.checkout_url, undefined);
  await h.context.purchase();
  assert.equal(h.orderReads(), 2);
  assert.deepEqual(destinations, [checkoutURL]);
  assert.equal(h.checkoutStarts(), 0);
});

for (const [name, response] of [
  ['expired', { state: 'expired', retry_disposition: 'new_key' }],
  ['processing', { state: 'processing', retry_disposition: 'do_not_repay' }],
  ['other region', { state: 'open', retry_disposition: 'do_not_repay', region: 'GB',
    checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_other', provider_expires_at: '2099-01-01T00:00:00Z' }],
  ['other order', { state: 'open', retry_disposition: 'do_not_repay', order_id: '00000000-0000-4000-8000-000000000094',
    checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_other', provider_expires_at: '2099-01-01T00:00:00Z' }],
  ['untrusted link', { state: 'open', retry_disposition: 'do_not_repay',
    checkout_url: 'https://payments.example.invalid/c/pay/fixture', provider_expires_at: '2099-01-01T00:00:00Z' }],
  ['incomplete link', { state: 'open', retry_disposition: 'do_not_repay',
    checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_old' }],
]) {
  test(`checkout continuation stays on the Workshop when the fresh response is ${name}`, async () => {
    const base = { version: 'v1', order_id: orderID, ...scope, retry_disposition: 'do_not_repay' };
    const open = { ...base, state: 'open', checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_original',
      provider_expires_at: '2099-01-01T00:00:00Z' };
    const h = paidPurchaseLifecycleHarness([], { orderResponses: [open, { ...base, ...response }] });
    const destinations = [];
    h.location.assign = url => destinations.push(url);
    h.location.search = `?order=${orderID}`;
    await h.context.restoreRoute();
    await h.context.purchase();
    assert.deepEqual(destinations, []);
    assert.equal(h.orderReads(), 2);
    assert.equal(h.checkoutStarts(), 0);
    assert.equal(h.context.vehicle.region, scope.region);
  });
}

test('retrying an unavailable continuation only checks the original order', async () => {
  const open = { version: 'v1', order_id: orderID, ...scope, state: 'open', retry_disposition: 'do_not_repay',
    checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_original', provider_expires_at: '2099-01-01T00:00:00Z' };
  const missing = Object.assign(new Error('Order not found'), { status: 404 });
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [open, missing, missing, missing] });
  await h.context.purchase();
  assert.equal(h.$('purchase-action').textContent, 'Continue checkout');
  assert.equal(h.checkoutStarts(), 1);
  await h.context.purchase();
  assert.equal(h.orderReads(), 2);
  assert.equal(h.$('purchase-action').textContent, 'Checkout status unavailable');
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-consent').hidden, true);
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  await h.statuses.at(-1).options.retry();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.orderReads(), 3);
  await h.context.operation(g => h.context.checkOrder(g, orderID));
  assert.equal(h.orderReads(), 4);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('check-order').hidden, false);
});

test('processing checkout timeout keeps status check without an enabled Buy action', async () => {
  const processing = {
    version: 'v1', order_id: orderID, ...scope, state: 'processing',
    retry_disposition: 'do_not_repay', timedOut: true,
  };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing, processing] });
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.context.access, 'missing');
  assert.match(h.$('purchase-message').textContent, /confirmation.*do not pay again/i);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy|Payment received/);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.equal(h.$('purchase-consent').hidden, true);
  assert.equal(h.$('agreement').disabled, true);
  await h.context.purchase(); // Direct activation must not start a second checkout.
  assert.equal(h.checkoutStarts(), 1);
});

test('owner-only processing route recovery keeps a scoped confirmation-pending action', async () => {
  const processing = {
    version: 'v1', order_id: orderID, ...scope, state: 'processing',
    retry_disposition: 'do_not_repay', timedOut: true,
  };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing] });
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.checkoutStarts(), 0);
  assert.equal(h.orderReads(), 1);
  assert.equal(h.context.unconfirmedOrder?.id, orderID);
  assert.equal(h.context.access, 'unknown'); // Route restoration invalidates prior access.
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy|Payment received/);
  h.context.vehicle = { id: previousConfiguration, region: scope.region };
  h.context.quote = { ...quote, configuration_id: previousConfiguration };
  h.context.access = 'missing'; // A separate access check found the other scope purchasable.
  h.context.renderPurchase();
  assert.equal(h.$('purchase-action').disabled, false);
  assert.match(h.$('purchase-action').textContent, /Buy for \$20 USD/);
});

test('fresh order-only return reveals Check payment status after owner validation', async () => {
  const processing = {
    version: 'v1', order_id: orderID, ...scope, state: 'processing',
    retry_disposition: 'do_not_repay', timedOut: true,
    configuration_label: '2005 Toyota 2.4 L XLE',
  };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing] });
  h.context.vehicle = null;
  h.context.quote = null;
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.context.vehicle?.id, scope.configuration_id);
  assert.equal(h.context.vehicle?.region, scope.region);
  assert.equal(h.$('purchase-selection').textContent, '2005 Toyota 2.4 L XLE / US');
  assert.equal(h.$('purchase').hidden, false);
  assert.equal(h.$('check-order').hidden, false);
  assert.equal(h.$('purchase-action').disabled, true);
  assert.match(h.$('purchase-message').textContent, /confirmation.*do not pay again/i);
  assert.equal(h.checkoutStarts(), 0);
});

for (const state of ['creating', 'open', 'reconciliation_required']) {
  test(`unresolved ${state} order keeps a validated no-repay action`, async () => {
    const processing = {
      version: 'v1', order_id: orderID, ...scope, state: 'processing',
      retry_disposition: 'do_not_repay', timedOut: true,
    };
    const unresolved = { ...processing, state };
    const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing, unresolved] });
    await h.context.purchase();
    await h.context.operation(g => h.context.checkOrder(g, orderID));
    assert.equal(h.context.currentOrder, orderID);
    assert.equal(h.context.unconfirmedOrder?.id, orderID);
    assert.equal(h.$('check-order').hidden, false);
    assert.equal(h.$('purchase-action').disabled, true);
    assert.doesNotMatch(h.$('purchase-action').textContent, /Buy|Payment received/);
    await h.context.purchase();
    assert.equal(h.checkoutStarts(), 1);
  });
}

test('a URL-only missing order never claims pending confirmation', async () => {
  const missing = Object.assign(new Error('Order not found'), { status: 404 });
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [missing] });
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.checkoutStarts(), 0);
  assert.equal(h.context.unconfirmedOrder, null);
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.$('check-order').hidden, true);
  assert.doesNotMatch(h.$('purchase-message').textContent, /Payment confirmation is pending|Payment received/);
});

test('a missing processing order clears the pending action and allows a fresh purchase', async () => {
  const processing = {
    version: 'v1', order_id: orderID, ...scope, state: 'processing',
    retry_disposition: 'do_not_repay', timedOut: true,
  };
  const missing = Object.assign(new Error('Order not found'), { status: 404 });
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing, missing] });
  await h.context.purchase();
  assert.equal(h.$('purchase-action').disabled, true);
  await h.context.operation(g => h.context.checkOrder(g, orderID));
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.context.unconfirmedOrder, null);
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(h.$('purchase-action').disabled, false);
  assert.match(h.$('purchase-action').textContent, /Buy for \$20 USD/);
});

for (const state of ['expired', 'canceled', 'revoked', 'paid']) {
  test(`processing order resolving as ${state} does not retain a stale pending action`, async () => {
    const processing = {
      version: 'v1', order_id: orderID, ...scope, state: 'processing',
      retry_disposition: 'do_not_repay', timedOut: true,
    };
    const resolved = {
      version: 'v1', order_id: orderID, ...scope, state,
      retry_disposition: ['expired', 'canceled'].includes(state) ? 'new_key' : 'do_not_repay',
    };
    const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing, resolved] });
    await h.context.purchase();
    await h.context.operation(g => h.context.checkOrder(g, orderID));
    assert.equal(h.context.unconfirmedOrder, null);
    assert.equal(h.context.currentOrder, '');
    assert.equal(h.$('check-order').hidden, true);
    if (['expired', 'canceled'].includes(state)) {
      assert.equal(h.$('purchase-action').disabled, false);
      assert.equal(h.$('purchase-consent').hidden, false);
      assert.equal(h.$('agreement').disabled, false);
      assert.match(h.$('purchase-action').textContent, /Buy for \$20 USD/);
      assert.match(h.statuses.at(-1).message, /Choose Buy again/);
    } else if (state === 'revoked') {
      assert.equal(h.context.access, 'revoked');
      assert.equal(h.$('purchase-action').disabled, true);
      assert.match(h.$('purchase-message').textContent, /Access revoked/);
    } else {
      assert.equal(h.context.access, 'owned');
      h.context.renderPurchase(); // The harness selectVehicle stub does not render its success path.
      assert.match(h.$('purchase-action').textContent, /Open articles/);
      assert.equal(h.$('purchase-consent').hidden, true);
      assert.equal(h.$('agreement').disabled, true);
      assert.equal(h.$('purchase-terms').hidden, false);
    }
  });
}

for (const state of ['expired', 'canceled']) {
  test(`fresh order-only ${state} result gives a usable next step`, async () => {
    const processing = {
      version: 'v1', order_id: orderID, ...scope, state: 'processing',
      retry_disposition: 'do_not_repay', timedOut: true,
    };
    const terminal = { ...processing, state, retry_disposition: 'new_key' };
    const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing, terminal] });
    h.context.vehicle = null;
    h.context.quote = null;
    h.location.search = `?order=${orderID}`;
    await h.context.restoreRoute();
    await h.context.operation(g => h.context.checkOrder(g, orderID));
    assert.equal(h.context.currentOrder, '');
    assert.equal(h.context.unconfirmedOrder, null);
    assert.equal(h.$('purchase-action').disabled, true);
    assert.match(h.statuses.at(-1).message, /select.*vehicle.*check access/i);
    assert.doesNotMatch(h.statuses.at(-1).message, /Choose Buy again/);
  });
}

test('confirmed paid marker for another vehicle does not mask missing access', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.currentOrder = orderID;
  h.context.paidOrder = { id: orderID, ...scope };
  h.context.vehicle = { id: previousConfiguration, region: scope.region };
  await h.context.operation(async () => { throw required; });
  assert.equal(h.context.access, 'missing');
});

test('a confirmed payment marker cannot describe another scope, a signed-out viewer, or revoked access', () => {
  const h = paidPurchaseLifecycleHarness([]);
  h.context.currentOrder = orderID;
  h.context.paidOrder = { id: orderID, ...scope };
  for (const [vehicle, authenticated, access] of [
    [{ id: previousConfiguration, region: scope.region }, true, 'unknown'],
    [{ id: scope.configuration_id, region: 'CA' }, true, 'unknown'],
    [{ id: scope.configuration_id, region: scope.region }, false, 'unknown'],
    [{ id: scope.configuration_id, region: scope.region }, true, 'revoked'],
  ]) {
    h.context.vehicle = vehicle;
    h.context.session.state.authenticated = authenticated;
    h.context.access = access;
    h.context.renderPurchase();
    assert.doesNotMatch(h.$('purchase-message').textContent, /Payment received/);
    if (access === 'revoked') assert.match(h.$('purchase-message').textContent, /Access revoked/);
  }
});

test('paid processing checkout survives focus recheck without a second Buy invitation', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([required, required]);
  await h.context.purchase();
  assert.equal(h.orderReads(), 1);
  assert.equal(h.context.access, 'pending');
  await h.context.recheck();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.context.access, 'pending');
  assert.equal(h.$('check-order').hidden, false);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  assert.match(h.$('purchase-message').textContent, /do not pay again/);
});

test('confirmed article access replaces the resumed order route with its vehicle route', async () => {
  const required = Object.assign(new Error('Access not ready'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = paidPurchaseLifecycleHarness([required, null]);
  await h.context.purchase();
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  await h.context.recheck();
  const route = new URLSearchParams(h.location.search);
  assert.equal(route.has('order'), false);
  assert.equal(route.get('configuration'), scope.configuration_id);
  assert.equal(route.get('region'), scope.region);
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(h.context.access, 'owned');
});

const ownedCheckout = { version: 'v1', ...scope, order_id: orderID, library_item_id: orderID, state: 'owned' };
const checkoutPaidOrder = { version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' };
const checkoutReadyIndex = { items: [{ id: routeArticle, title: 'Purchased article' }], complete: true, hydrating: false };
const checkoutPost = ['POST', '/v1/workshop/checkout-sessions'];
const checkoutOrderGet = ['GET', `/v1/workshop/orders/${orderID}`];
const checkoutIndexGet = ['GET', `/v1/catalog/vehicles/${scope.configuration_id}/articles?region=${scope.region}`];

test('an explicit payment check ignores repeat clicks and focuses the recovered index', async () => {
  const unavailable = Object.assign(new Error('Index unavailable'), { status: 503 });
  const h = paidPurchaseLifecycleHarness([], {
    realArticleIndex: true, articleReadResponses: [unavailable, checkoutReadyIndex],
  });
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  const response = deferredAuthOperation();
  let checks = 0;
  h.context.pollOrder = () => { checks++; return response.promise; };
  const button = h.$('check-order');
  button.focus();
  button.click();
  button.click();
  assert.equal(checks, 1);
  assert.equal(button.getAttribute('aria-disabled'), 'true');
  assert.equal(h.context.document.activeElement, button);
  response.resolve(checkoutPaidOrder);
  await new Promise(setImmediate);
  assert.equal(button.hidden, true);
  assert.equal(button.getAttribute('aria-disabled'), null);
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  assert.equal(h.location.search, `?configuration=${scope.configuration_id}&region=${scope.region}`);
  assert.equal(h.checkoutStarts(), 0);
});

test('navigation unlocks an explicit status check and stale completion cannot unlock a newer check', async () => {
  const unavailable = Object.assign(new Error('Index unavailable'), { status: 503 });
  const h = paidPurchaseLifecycleHarness([unavailable]);
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  const oldResponse = deferredAuthOperation();
  const newResponse = deferredAuthOperation();
  const pendingChecks = [oldResponse, newResponse];
  h.context.pollOrder = () => pendingChecks.shift().promise;
  const button = h.$('check-order');
  button.click();
  assert.equal(button.getAttribute('aria-disabled'), 'true');
  h.context.navigation.clear();
  assert.equal(button.getAttribute('aria-disabled'), null);
  button.click();
  h.$('my-vehicles').focus();
  oldResponse.resolve(checkoutPaidOrder);
  await new Promise(setImmediate);
  assert.equal(button.getAttribute('aria-disabled'), 'true');
  newResponse.resolve(checkoutPaidOrder);
  await new Promise(setImmediate);
  assert.equal(button.hidden, true);
  assert.equal(button.getAttribute('aria-disabled'), null);
  assert.equal(h.context.document.activeElement, h.$('my-vehicles'));
});

async function ownedCheckoutHarness(indexResponses, { checkoutResponse = ownedCheckout, orderResponses = [] } = {}) {
  const { createCheckout } = await import('./workshop/commerce.mjs');
  const h = paidPurchaseLifecycleHarness([], { realArticleIndex: true, articleReadResponses: indexResponses });
  const requests = [];
  const storage = new Map();
  Object.assign(h.context, { indexLoaded: false, indexComplete: false, indexCatalogEmpty: false, indexHydrating: false, indexFailed: false });
  h.$('check-order').hidden = true;
  h.context.checkout = createCheckout({
    storage: {
      getItem: key => storage.get(key),
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    uuid: () => 'bc32b7a1-1111-4111-8111-111111111111',
    request: async (path, options) => {
      requests.push([options.method, path]);
      assert.deepEqual(options.body, { ...scope, terms_version: 'workshop-v1' });
      return checkoutResponse;
    },
  });
  const requestJSON = h.context.requestJSON;
  h.context.requestJSON = async (path, options) => {
    requests.push(['GET', path]);
    return requestJSON(path, options);
  };
  h.context.pollOrder = (id, options) => pollOrder(id, {
    ...options,
    request: async path => {
      requests.push(['GET', path]);
      const next = orderResponses.shift();
      assert.ok(next, 'unexpected order status read');
      if (next instanceof Error) throw next;
      return next;
    },
  });
  return { ...h, requests };
}

for (const [known, message, feedback] of [
  ['paid', /Payment was received.*order status is unavailable.*do not pay again/,
    'Payment received. Status check is temporarily unavailable. Checking again…'],
  ['pending', /^Payment was pending at the last check\. The current status is unavailable\./,
    'Payment was pending at the last check. Status check is temporarily unavailable. Checking again…'],
  ['unknown', /^Payment status is temporarily unavailable\. Try again\.$/,
    'Payment status is temporarily unavailable. Checking again…'],
]) {
  test(`order status timeout describes ${known} payment accurately and can recover`, async () => {
    const previouslyPaid = known === 'paid';
    const label = 'Fixture selected XLE 2.4 L';
    const indexError = Object.assign(new Error('Index unavailable'), { status: 503, code: 'CATALOG_UNAVAILABLE' });
    const h = await ownedCheckoutHarness(previouslyPaid ? [indexError, checkoutReadyIndex] : [checkoutReadyIndex]);
    if (previouslyPaid) {
      h.context.quote = { ...h.context.quote, configuration_label: label };
      await h.context.purchase();
    } else {
      h.location.search = `?order=${orderID}`;
    }
    const readsAt = [];
    const feedbackAt = [];
    let now = 0;
    let recovered = false;
    const recordStatus = h.context.status;
    h.context.status = (text, options) => {
      if (text.endsWith('Checking again…')) feedbackAt.push([now, text, options.busy]);
      recordStatus(text, options);
    };
    h.context.pollOrder = (id, options) => pollOrder(id, {
      ...options,
      now: () => now,
      wait: async elapsed => { now += elapsed; },
      request: (path, readOptions) => requestJSON(path, {
        ...readOptions,
        fetcher: async () => {
          assert.equal(path, checkoutOrderGet[1]);
          h.requests.push(checkoutOrderGet);
          readsAt.push(now);
          if (recovered) return new Response(JSON.stringify(checkoutPaidOrder));
          if (known === 'pending' && readsAt.length === 1) {
            return new Response(JSON.stringify({ ...checkoutPaidOrder, state: 'processing', configuration_label: label }));
          }
          return new Response(JSON.stringify({ error: { code: 'COMMERCE_UNAVAILABLE', retryable: true } }), { status: 503 });
        },
      }),
    });
    if (previouslyPaid) await h.context.operation(g => h.context.checkOrder(g, orderID));
    else await h.context.restoreRoute();

    const attempts = [0, 1000, 3000, 7000, 15000, 25000, 35000, 45000, 55000, 65000, 75000, 85000, 95000, 105000, 115000];
    const initial = previouslyPaid ? [checkoutPost, checkoutIndexGet] : [];
    assert.deepEqual(feedbackAt, [[known === 'pending' ? 1000 : 0, feedback, true]]);
    assert.deepEqual(readsAt, attempts);
    assert.equal(now, 120000);
    assert.deepEqual(h.requests, [...initial, ...attempts.map(() => checkoutOrderGet)]);
    const status = h.statuses.at(-1);
    assert.match(status.message, message);
    assert.equal(Boolean(status.options.error), true);
    assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
    assert.equal(h.context.paidOrder?.id, previouslyPaid ? orderID : undefined);
    assert.equal(h.context.unconfirmedOrder?.id, known === 'pending' ? orderID : undefined);
    assert.equal(h.context.access, previouslyPaid ? 'pending' : 'unknown');
    assert.equal(h.$('purchase').hidden, known === 'unknown');
    assert.equal(h.$('purchase-action').disabled, true);
    if (known !== 'unknown') {
      assert.equal(h.$('purchase-selection').textContent, `${label} / ${scope.region}`);
      assert.equal(h.$('check-order').hidden, false);
      assert.match(h.$('purchase-message').textContent, /do not pay again/i);
    }

    recovered = true;
    await status.options.retry();
    assert.deepEqual(h.requests, [...initial, ...attempts.map(() => checkoutOrderGet), checkoutOrderGet, checkoutIndexGet]);
    assert.equal(h.context.access, 'owned');
    assert.equal(h.$('check-order').hidden, true);
    assert.equal(h.location.search, `?configuration=${scope.configuration_id}&region=${scope.region}`);
  });
}

test('a checkout returning owned opens the exact index directly', async () => {
  const h = await ownedCheckoutHarness([checkoutReadyIndex]);
  await h.context.purchase();
  assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet]);
  assert.equal(h.context.access, 'owned');
  assert.equal(h.$('articles').children.length, 1);
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(h.context.paidOrder, null);
  assert.equal(h.location.search, `?configuration=${scope.configuration_id}&region=${scope.region}`);
});

test('a confirmed empty owned checkout offers one scoped availability check', async () => {
  const empty = indexResponse('completed', { complete: true });
  const h = await ownedCheckoutHarness([empty, checkoutReadyIndex]);
  await h.context.purchase();
  assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet]);
  assert.equal(h.$('purchase-message').textContent, 'Owned. No articles are currently available for this vehicle.');
  assert.equal(h.$('purchase-action').textContent, 'Check article availability');
  assert.equal(h.$('purchase-action').disabled, false);
  assert.equal(h.$('catalog-count').textContent, '0 articles');

  await h.context.purchase();
  assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet, checkoutIndexGet]);
  assert.equal(h.$('purchase-action').textContent, 'Open articles');
  assert.equal(h.$('catalog-count').textContent, '1 article');
});

test('an owned checkout keeps the confirmed payment on scoped index failures and can recheck', async () => {
  for (const [status, code] of [[503, 'CATALOG_UNAVAILABLE'], [403, 'ENTITLEMENT_REQUIRED']]) {
    const error = Object.assign(new Error('Index unavailable'), { status, code });
    const h = await ownedCheckoutHarness([error, checkoutReadyIndex], { orderResponses: [checkoutPaidOrder] });
    h.context.vehicle = { id: scope.configuration_id, region: scope.region };
    const purchaseLabel = '2005 Toyota / 2.4 L';
    h.context.quote = { ...h.context.quote, configuration_label: purchaseLabel };
    await h.context.purchase();
    assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet]);
    assert.equal(h.context.access, 'pending');
    assert.equal(h.context.paidOrder?.id, orderID);
    assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
    assert.equal(h.$('purchase-action').disabled, true);
    assert.equal(h.$('purchase-selection').textContent, `${purchaseLabel} / ${scope.region}`);
    assert.equal(h.$('check-order').hidden, false);
    assert.match(h.statuses.at(-1).message, /Payment received.*do not pay again/);
    assert.equal(h.statuses.at(-1).options.retry, undefined);
    await h.context.purchase();
    await h.context.operation(g => h.context.checkOrder(g, orderID));
    assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet, checkoutOrderGet, checkoutIndexGet]);
    assert.equal(h.context.access, 'owned');
    assert.equal(h.$('check-order').hidden, true);
    assert.equal(h.location.search, `?configuration=${scope.configuration_id}&region=${scope.region}`);
  }
});

test('the owned checkout handoff keeps an owner-only recovery route for signing in again', async () => {
  const unauthorized = Object.assign(new Error('Sign in again'), { status: 401 });
  const h = await ownedCheckoutHarness([unauthorized, checkoutReadyIndex], { orderResponses: [checkoutPaidOrder] });
  await h.context.purchase();
  assert.equal(h.context.session.state.authenticated, false);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.match(h.$('purchase-action').textContent, /Sign in/);
  h.context.session.state.authenticated = true;
  h.context.session.state.ready = true;
  await h.context.restoreRoute();
  assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet, checkoutOrderGet, checkoutIndexGet]);
  assert.equal(h.context.access, 'owned');
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
});

test('the owned checkout stays confirmed on a missing status read and honors terminal revocation', async () => {
  const unavailable = Object.assign(new Error('Index unavailable'), { status: 503 });
  const missing = Object.assign(new Error('Order not found'), { status: 404 });
  const revoked = { ...checkoutPaidOrder, state: 'revoked' };
  const h = await ownedCheckoutHarness([unavailable], { orderResponses: [missing, revoked] });
  await h.context.purchase();
  await h.context.operation(g => h.context.checkOrder(g, orderID));
  assert.equal(h.context.access, 'pending');
  assert.equal(h.context.paidOrder?.id, orderID);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.match(h.statuses.at(-1).message, /Payment was received.*do not pay again/);
  await h.context.operation(g => h.context.checkOrder(g, orderID));
  assert.deepEqual(h.requests, [checkoutPost, checkoutIndexGet, checkoutOrderGet, checkoutOrderGet]);
  assert.equal(h.context.access, 'revoked');
  assert.equal(h.context.paidOrder, null);
  assert.equal(h.$('check-order').hidden, true);
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
});

test('malformed or differently scoped owned checkout replies cannot establish a paid handoff', async () => {
  for (const response of [{ ...ownedCheckout, library_item_id: undefined }, { ...ownedCheckout, region: 'CA' }]) {
    const h = await ownedCheckoutHarness([], { checkoutResponse: response });
    await h.context.purchase();
    assert.deepEqual(h.requests, [checkoutPost]);
    assert.equal(h.context.paidOrder, null);
    assert.equal(h.$('check-order').hidden, true);
    assert.equal(new URLSearchParams(h.location.search).has('order'), false);
    assert.match(h.statuses.at(-1).message, /Payment status|Purchase status/);
  }
});

test('a superseded owned checkout or article-index read cannot restore the previous payment route', async () => {
  for (const phase of ['checkout', 'index']) {
    const delayed = deferredAuthOperation();
    const h = await ownedCheckoutHarness(
      [phase === 'index' ? delayed.promise : checkoutReadyIndex],
      { checkoutResponse: phase === 'checkout' ? delayed.promise : ownedCheckout },
    );
    const payment = h.context.purchase();
    await new Promise(setImmediate);
    assert.deepEqual(h.requests, phase === 'checkout' ? [checkoutPost] : [checkoutPost, checkoutIndexGet]);
    h.context.invalidate();
    h.context.vehicle = { id: previousConfiguration, region: 'CA' };
    h.context.quote = null;
    h.context.updateURL();
    const selectedRoute = `?configuration=${previousConfiguration}&region=CA`;
    delayed.resolve(phase === 'checkout' ? ownedCheckout : checkoutReadyIndex);
    await payment;
    assert.equal(h.location.search, selectedRoute);
    assert.equal(h.context.paidOrder, null);
    assert.equal(h.$('check-order').hidden, true);
    assert.equal(h.$('articles').children.length, 0);
    assert.deepEqual(h.requests, phase === 'checkout' ? [checkoutPost] : [checkoutPost, checkoutIndexGet]);
  }
});

test('paid article authentication failure retains order route for sign-in recovery', async () => {
  const unauthorized = Object.assign(new Error('Sign in again'), { status: 401 });
  const h = paidPurchaseLifecycleHarness([unauthorized, null]);
  await h.context.purchase();
  assert.equal(h.checkoutStarts(), 1);
  assert.equal(h.orderReads(), 1);
  assert.equal(h.context.session.state.authenticated, false);
  assert.equal(new URLSearchParams(h.location.search).get('order'), orderID);
  assert.doesNotMatch(h.$('purchase-action').textContent, /Buy/);
  h.context.session.state.authenticated = true;
  await h.context.restoreRoute();
  assert.equal(h.orderReads(), 2);
  assert.equal(h.context.access, 'owned');
  assert.equal(new URLSearchParams(h.location.search).has('order'), false);
});

test('order status retains pending action when confirmation times out', async () => {
  const h = orderStatusHarness({
    version: 'v1', order_id: orderID, ...scope, state: 'processing',
    retry_disposition: 'do_not_repay', timedOut: true,
  });
  await h.check();
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.button.hidden, false);
  assert.equal(h.checkoutClears(), 0);
});

test('stale order status 404 does not clear newer checkout or action', async () => {
  let rejectOrder;
  let current = true;
  let checkoutClears = 0;
  const button = { hidden: true };
  const context = {
    currentOrder: '', paidOrder: '', unconfirmedOrder: null, $: () => button, status() {},
    pollOrder: () => new Promise((_, reject) => { rejectOrder = reject; }),
    checkout: { clear() { checkoutClears++; } },
  };
  runInNewContext(appSection('async function checkOrder(', 'async function purchase()'), context);
  const pending = context.checkOrder({ current: () => current, signal: {} }, orderID);
  const newerOrder = '55555555-5555-4555-8555-555555555555';
  context.currentOrder = newerOrder;
  current = false;
  const error = Object.assign(new Error('Old order not found'), { status: 404 });
  rejectOrder(error);
  await assert.rejects(pending, received => received === error);
  assert.equal(context.currentOrder, newerOrder);
  assert.equal(button.hidden, false);
  assert.equal(checkoutClears, 0);
});

function articleIndexHarness(responses, { wait = async () => {}, now = () => performance.now(), openDemo = false } = {}) {
  const navigation = new NavigationGeneration();
  const searchNavigation = new NavigationGeneration();
  const nodes = new Map();
  const document = { title: '', body: { dataset: {} }, activeElement: null };
  function element(tag, text = '', className = '') {
    return { tag, textContent: text, className, hidden: false, value: '', dataset: {}, attributes: {}, children: [], events: {}, parent: null,
      get firstElementChild() { return this.children[0] || null; },
      get parentElement() { return this.parent; },
      get nextElementSibling() {
        return this.parent?.children[this.parent.children.indexOf(this) + 1] || null;
      },
      contains(node) { return node === this || this.children.some(child => child.contains(node)); },
      remove() {
        if (!this.parent) return;
        if (this.contains(document.activeElement)) document.activeElement = document.body;
        this.parent.children.splice(this.parent.children.indexOf(this), 1);
        this.parent = null;
      },
      insertBefore(child, reference) {
        child.remove();
        this.children.splice(reference ? this.children.indexOf(reference) : this.children.length, 0, child);
        child.parent = this;
      },
      append(...children) { for (const child of children) this.insertBefore(child, null); },
      replaceChildren(...children) {
        for (const child of [...this.children]) child.remove();
        this.append(...children);
      },
      focus(options) { this.focusOptions = options; document.activeElement = this; },
      scrollIntoView(options) { this.scrollOptions = options; },
      addEventListener(name, callback) { this.events[name] = callback; },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return this.attributes[name] ?? this[name] ?? null; },
      removeAttribute() {},
    };
  }
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, element('div'));
    return nodes.get(id);
  };
  const statuses = [], updates = [], opened = [], requests = [], results = [], shown = [], clearedOrders = [];
  const context = {
    $, element, URL, uuid, readableArticle, openDemo,
    demoPath: path => openDemo ? `${path}${path.includes('?') ? '&' : '?'}demo=1` : path,
    location: { href: `https://cars.example/workshop?vehicle=B${openDemo ? '&demo=1' : ''}` },
    document,
    navigation, quote: null, vehicle: { id: 'B', region: 'US' }, articles: [], indexLoaded: false, indexComplete: false, indexCatalogEmpty: false, indexHydrating: false, indexFailed: false, access: '', retryAction: null, filterArticles,
    searchNavigation, searchItems: null, searchQuery: '', searchPending: false, searchComplete: false, searchError: false, searchTimer: null,
    currentArticle: null, renderedRevision: '', sourceURL: '', sourceRevision: 0, displayedSourceRevision: 0,
    sourceDocumentRequest: null,
    articleImageRefresh: null, sourceImageRefresh: null, libraryPageRequest: null, libraryCursor: null,
    currentOrder: '', paidOrder: null, unconfirmedOrder: null, viewGeneration: null,
    clearOrderRoute(id) { clearedOrders.push(id); },
    session: { state: { mode: 'firebase' }, clear() {}, async bootstrap() {} },
    setTimeout(callback) { callback(); return 1; }, clearTimeout() {}, updateURL() {},
    stage() {}, renderPurchase() {}, show(id) { shown.push(id); },
    articlePath: () => `/v1/catalog/vehicles/${context.vehicle.id}/articles`,
    scope: () => ({ configuration_id: context.vehicle.id, region: context.vehicle.region }),
    requestJSON(path, options) {
      requests.push({ path, signal: options.signal, prefer: options.headers?.Prefer, timeout: options.timeout });
      const response = responses[Math.min(requests.length - 1, responses.length - 1)];
      return typeof response === 'function' ? response() : Promise.resolve(response);
    },
    async readCollection(read, options) {
      const result = await readCollection(read, {
        ...options, attempts: 3, wait, now,
        onUpdate(data, meta) {
          options.onUpdate(data, meta);
          updates.push({ complete: data.complete, count: $('articles').children[0]?.children.length ?? 0,
            completion: $('completion-status').textContent,
            link: $('articles').children[0]?.children[0]?.children[0] });
        },
      });
      results.push(result);
      return result;
    },
    loadArticle: async (id, generation) => opened.push({ id, generation }),
    openArticle: id => opened.push({ id }),
    recordStatus: (text, options) => statuses.push({ text, ...options }),
  };
  installArticleRequestPath(context);
  runInNewContext(
    appSection('function status(', 'function stage(') +
    appSection('function clearProtected()', 'function updateURL(') +
    appSection('async function loadSavedSearch(', 'const assetID =') +
    appSection('function clearReader()', 'async function checkOrder(') +
    appSection('$("search").addEventListener("input"', '$("retry").addEventListener') +
    appSection('function rememberRetainedIndexArticle(', '$("print").addEventListener') +
    '\nconst actualStatus = status; status = (text, options = {}) => { recordStatus(text, options); actualStatus(text, options); };',
    context,
  );
  return { context, $, navigation, statuses, updates, opened, requests, results, shown, clearedOrders,
    load: (article = '', generation = navigation.next()) => context.loadArticles(generation, article) };
}

const indexResponse = (status, { complete = false, retryable = false, hydrating = false, items = [] } = {}) =>
  ({ items, complete, hydrating, progress: status ? { status, retryable } : null });

for (const inputType of ['insertFromPaste', 'insertFromDrop', 'insertReplacementText']) {
  test(`committed Workshop search input ${inputType} starts one protected search immediately`, async () => {
    const hit = { id: 'second-page', title: 'Oil pump' };
    const h = articleIndexHarness([
      indexResponse('completed', { complete: true, items: [{ id: 'first-page', title: 'Brakes' }] }),
      indexResponse('completed', { complete: true, items: [hit] }),
    ]);
    await h.load();
    h.context.setTimeout = () => assert.fail('a committed search must not wait for typing');
    const search = h.$('search');
    search.value = hit.title;
    search.events.input({ inputType });
    assert.equal(h.requests[1]?.path, '/v1/catalog/vehicles/B/articles?q=Oil+pump&region=US');
    await new Promise(setImmediate);
    assert.equal(h.$('articles').firstElementChild.firstElementChild.dataset.articleId, hit.id);
  });
}

test('Enter flushes a pending typed Workshop search exactly once', async () => {
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'first-page', title: 'Brakes' }] }),
    indexResponse('completed', { complete: true, items: [{ id: 'second-page', title: 'Oil pump' }] }),
  ]);
  await h.load();
  const pending = new Map();
  let nextTimer = 0;
  h.context.setTimeout = (callback, delay) => {
    assert.equal(delay, 150);
    pending.set(++nextTimer, callback);
    return nextTimer;
  };
  h.context.clearTimeout = id => pending.delete(id);
  const search = h.$('search');
  for (const value of ['oil', 'oil pump']) {
    search.value = value;
    search.events.input({ inputType: 'insertText' });
    assert.equal(pending.size, 1);
    assert.equal(h.requests.length, 1);
  }
  search.events.keydown({ key: 'Enter', isComposing: true, preventDefault: () => assert.fail('IME Enter was consumed') });
  assert.equal(h.requests.length, 1);
  let prevented = 0;
  const enter = { key: 'Enter', preventDefault: () => { prevented++; } };
  search.events.keydown(enter);
  search.events.keydown(enter);
  assert.equal(pending.size, 0);
  assert.equal(prevented, 1);
  assert.equal(h.requests.length, 2);
  assert.equal(h.requests[1].path, '/v1/catalog/vehicles/B/articles?q=oil+pump&region=US');
  await new Promise(setImmediate);
});

test('unchanged trimmed search text keeps in-flight and visible off-page results', async () => {
  const remote = deferredAuthOperation();
  const hit = { id: 'second-page', title: 'Oil pump' };
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'first-page', title: 'Brakes' }] }),
    () => remote.promise,
  ]);
  await h.load();
  const search = h.$('search');
  search.value = 'oil pump';
  search.events.input({ inputType: 'insertFromPaste' });
  const initialRequest = h.requests[1];
  search.value += ' ';
  search.events.input({ inputType: 'insertText' });
  assert.equal(initialRequest.signal.aborted, false);
  assert.equal(h.requests.length, 2);

  remote.resolve(indexResponse('completed', { complete: true, items: [hit] }));
  await new Promise(setImmediate);
  const row = h.$('articles').firstElementChild.firstElementChild;
  assert.equal(row.dataset.articleId, hit.id);
  search.value = `  ${search.value}`;
  search.events.input({ inputType: 'insertText' });
  assert.equal(h.$('articles').firstElementChild.firstElementChild, row);
  assert.equal(h.requests.length, 2);
});

test('returning from a direct reader focuses the first partial index without moving focus at completion', async () => {
  const article = { id: 'first', title: 'First procedure' };
  const completion = deferredAuthOperation();
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [article] }),
    () => completion.promise,
  ]);
  const routes = [];
  h.context.updateURL = (options) => routes.push(options.replace);
  const returned = h.$('back').events.click();
  await new Promise(setImmediate);
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  assert.deepEqual(routes, [true]);
  assert.equal(h.updates[0].count, 1);
  h.$('search').focus();
  completion.resolve(indexResponse('completed', { complete: true, items: [article, { id: 'added' }] }));
  await returned;
  assert.equal(h.context.document.activeElement, h.$('search'));
  assert.equal(h.updates.at(-1).count, 2);
});

test('returning to an interrupted partial index reuses the rows and resumes the scoped read', async () => {
  const article = { id: 'first', title: 'First procedure' };
  const nextPoll = deferredAuthOperation();
  const completion = deferredAuthOperation();
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [article] }),
    () => completion.promise,
  ], { wait: () => nextPoll.promise });
  const loading = h.load();
  await new Promise(setImmediate);
  h.navigation.next();
  nextPoll.resolve();
  await assert.rejects(loading, { name: 'AbortError' });

  const returned = h.$('back').events.click();
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  assert.equal(h.$('articles').firstElementChild.children.length, 1);
  assert.deepEqual(h.requests.map(request => request.path), [
    '/v1/catalog/vehicles/B/articles?region=US', '/v1/catalog/vehicles/B/articles?region=US',
  ]);
  assert.notEqual(h.requests[1].signal, h.requests[0].signal);
  completion.resolve(indexResponse('completed', { complete: true, items: [article, { id: 'added' }] }));
  await returned;
  assert.equal(h.updates.at(-1).count, 2);
  assert.equal(h.statuses.at(-1).text, 'Article index ready.');
});

async function openedIndexHistory(responses, { next = false, onRestore } = {}) {
  const article = { id: 'first', title: 'First procedure' };
  const h = articleIndexHarness(responses ?? [indexResponse('completed', { complete: true, items: [article] })]);
  const indexURL = `https://cars.example/workshop?configuration=${scope.configuration_id}&region=${scope.region}`;
  h.context.location.href = indexURL;
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  h.context.scope = () => ({ configuration_id: h.context.vehicle.id, region: h.context.vehicle.region });
  h.context.session.state = { authenticated: true, csrf: 'fixture-current' };
  const routes = [], back = [], restores = [];
  h.context.updateURL = ({ article = '', replace = false } = {}) => {
    routes.push({ article, replace });
    h.context.location.href = article ? `${indexURL}&article=${article}` : indexURL;
  };
  h.context.history = { back() { back.push(true); } };
  h.context.restoreRoute = (_years, { focusArticle = '', indexAnchor = '' } = {}) => {
    restores.push({ focusArticle, ...(indexAnchor ? { indexAnchor } : {}) });
    return onRestore?.(h, { focusArticle, indexAnchor });
  };
  runInNewContext(appSection('function openArticle(', 'function validSourceURL('), h.context);
  await h.load();
  if (next) await h.context.moveArticlePage(1);
  const link = h.$('articles').firstElementChild.firstElementChild.firstElementChild;
  link.events.click({ button: 0, preventDefault() {} });
  const returnToIndex = () => {
    h.context.location.href = indexURL;
    return h.context.restoreHistoryEntry();
  };
  return { ...h, link, routes, back, restores, returnToIndex };
}

test('in-app Back traverses the original index entry once and focuses its article link', async () => {
  const h = await openedIndexHistory();
  h.$('back').events.click();
  h.$('back').events.click();
  assert.deepEqual(h.back, [true]);
  h.returnToIndex();
  assert.deepEqual(h.routes, [{ article: 'first', replace: false }]);
  assert.equal(h.context.document.activeElement, h.link);
  assert.equal(h.link.focusOptions?.preventScroll, true);
  assert.equal(h.link.scrollOptions?.behavior, 'instant');
  assert.equal(h.link.scrollOptions?.block, 'center');
  assert.deepEqual(h.restores, []);
  assert.equal(h.requests.length, 1);
});

test('Back reuses exact readiness from the first readable source or publication', async t => {
  for (const origin of ['source', 'canonical']) {
    await t.test(origin, async () => {
      const h = await openedIndexHistory();
      assert.equal(h.link.dataset.retained, 'false');
      const article = { id: 'first', availability: 'available', content_origin: origin,
        document: { blocks: [{ type: 'paragraph', text: 'Protected article body.' }] },
        source_revision_id: routeConfiguration,
        canonical_revision_id: origin === 'canonical' ? routeArticle : null };
      h.context.currentArticle = article;
      h.context.searchItems = [{ id: 'first', title: 'Search result title' }];
      h.context.rememberRetainedIndexArticle(
        { status: 200, data: { configuration: h.context.vehicle, article } }, h.context.viewGeneration,
      );
      h.$('back').events.click();
      h.returnToIndex();
      assert.equal(h.link.dataset.retained, 'true');
      assert.equal(h.context.document.activeElement, h.link);
      assert.equal(h.context.currentArticle, null);
      assert.equal(h.requests.length, 1);
      assert.equal(h.context.articles[0].document, undefined);
      assert.equal(h.context.searchItems[0].document, undefined);
      assert.equal(h.context.searchItems[0].source_revision_id, routeConfiguration);
      assert.equal(h.context.searchItems[0].title, 'Search result title');
      let reopened;
      h.context.openArticle = (id, _link, options) => { reopened = { id, preferRetained: options.preferRetained }; };
      h.link.events.click({ button: 0, preventDefault() {} });
      assert.deepEqual(reopened, { id: 'first', preferRetained: true });
    });
  }
});

test('Back does not remember a preview, mismatched scope, or obsolete index response', async t => {
  for (const scenario of ['preview', 'wrong vehicle', 'wrong article', 'wrong account', 'old navigation']) {
    await t.test(scenario, async () => {
      const h = await openedIndexHistory();
      const article = { id: 'first', availability: 'available', content_origin: 'source',
        source_revision_id: routeConfiguration, source_body_preview: scenario === 'preview', body: 'Protected source.' };
      h.context.currentArticle = article;
      const configuration = { ...h.context.vehicle };
      const generation = scenario === 'old navigation' ? new NavigationGeneration().next() : h.context.viewGeneration;
      if (scenario === 'wrong vehicle') configuration.region = 'CA';
      if (scenario === 'wrong article') article.id = 'different';
      const stamp = h.context.session.state.csrf;
      if (scenario === 'wrong account') h.context.session.state.csrf = 'replaced';
      h.context.rememberRetainedIndexArticle({ status: 200, data: { configuration, article } }, generation);
      h.context.session.state.csrf = stamp;
      h.$('back').events.click();
      h.returnToIndex();
      assert.equal(h.link.dataset.retained, 'false');
      assert.equal(h.requests.length, 1);
    });
  }
});

test('in-app Back falls back to its index heading when the prior link is gone', async () => {
  const h = await openedIndexHistory();
  h.$('articles').replaceChildren();
  h.$('back').events.click();
  h.returnToIndex();
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  assert.equal(h.$('catalog-title').scrollOptions?.behavior, 'instant');
  assert.equal(h.$('catalog-title').scrollOptions?.block, 'nearest');
  assert.deepEqual(h.restores, []);
});

test('browser Back revalidates the index and only carries the originating article for the exact current session and scope', async () => {
  for (const change of ['browser', 'account', 'region']) {
    const h = await openedIndexHistory();
    if (change !== 'browser') {
      h.$('back').events.click();
      if (change === 'account') h.context.session.state.csrf = 'fixture-replaced';
      else h.context.vehicle.region = 'CA';
    }
    h.returnToIndex();
    assert.deepEqual(h.restores, [{ focusArticle: change === 'browser' ? 'first' : '' }], change);
    assert.notEqual(h.context.document.activeElement, h.link, change);
  }
});

test('a history return focuses the same authorized article after revalidation or the heading if removed', async () => {
  const wanted = { id: 'original-id', title: 'Original pump procedure' };
  const other = { id: 'alternate-id', title: wanted.title };
  for (const retained of [true, false]) {
    const held = deferredAuthOperation();
    const h = articleIndexHarness([() => held.promise]);
    const opening = h.context.loadArticles(h.navigation.next(), '', { focusArticle: wanted.id });
    assert.equal(h.context.document.activeElement, null);
    assert.equal(h.$('articles').children.length, 0);
    held.resolve(indexResponse('completed', { complete: true, items: retained ? [other, wanted] : [other] }));
    await opening;
    assert.equal(h.context.document.activeElement, retained
      ? h.$('articles').firstElementChild.children[1].firstElementChild
      : h.$('catalog-title'));
    if (retained) {
      assert.match(h.context.document.activeElement.href, /article=original-id/);
      assert.equal(h.context.document.activeElement.scrollOptions.behavior, 'instant');
    }
    assert.deepEqual(h.requests.map(request => request.path), ['/v1/catalog/vehicles/B/articles?region=US']);
  }
});

test('a revalidated search return focuses its exact originating hit', async () => {
  const wanted = { id: 'original-id', title: 'Oil pump' };
  const h = articleIndexHarness([{
    ...indexResponse('completed', { complete: true, items: [wanted] }),
    configuration: { id: 'B', region: 'US' },
  }]);
  h.$('search').value = 'pump';
  await h.context.loadSavedSearch(h.navigation.next(), 'pump', wanted.id);
  assert.equal(h.context.document.activeElement, h.$('articles').firstElementChild.firstElementChild.firstElementChild);
  assert.deepEqual(h.requests.map(request => request.path), ['/v1/catalog/vehicles/B/articles?q=pump&region=US']);
});

test('a history return shows loaded matches and restores focus after the protected search responds', async () => {
  const wanted = { id: 'original-id', title: 'Oil pump' };
  const other = { id: 'other-id', title: wanted.title };
  const configuration = { id: 'B', region: 'US' };
  for (const outcome of ['retained', 'removed', 'user moved focus']) {
    const search = deferredAuthOperation();
    const h = articleIndexHarness([
      () => Promise.reject(Object.assign(new Error('Temporarily unavailable'), { status: 503 })),
      { ...indexResponse('completed', { complete: true, items: [other, wanted] }), configuration },
      () => search.promise,
    ]);
    h.$('search').value = 'pump';
    const generation = h.navigation.next();
    h.$('article-title').focus();
    assert.equal(await h.context.loadSavedSearch(generation, 'pump', wanted.id), false);
    await h.context.loadArticles(generation, '', { focusArticle: wanted.id });
    assert.deepEqual(h.$('articles').firstElementChild.children.map(row => row.dataset.articleId), [other.id, wanted.id]);
    if (outcome === 'user moved focus') h.$('search').focus();
    else if (h.context.document.activeElement === h.$('article-title'))
      h.context.document.activeElement = h.context.document.body;
    search.resolve({ ...indexResponse('completed', { complete: true,
      items: outcome === 'removed' ? [other] : [other, wanted] }), configuration });
    await new Promise(setImmediate);
    const exactLink = h.$('articles').firstElementChild.children[1]?.firstElementChild;
    assert.equal(h.context.document.activeElement, outcome === 'retained' ? exactLink :
      outcome === 'removed' ? h.$('catalog-title') : h.$('search'), outcome);
    if (outcome === 'retained') {
      assert.match(exactLink.href, /article=original-id/);
      assert.equal(exactLink.scrollOptions.behavior, 'instant');
    }
    assert.deepEqual(h.requests.map(({ path }) => path), [
      '/v1/catalog/vehicles/B/articles?q=pump&region=US', '/v1/catalog/vehicles/B/articles?region=US',
      '/v1/catalog/vehicles/B/articles?q=pump&region=US',
    ]);
  }
});

test('complete saved search uses its scoped response and loads the full index only when cleared', async () => {
  const configuration = { id: 'B', region: 'US', year: 2024, make: 'Fixture', model: 'Touring' };
  const hit = { id: 'only-match', title: 'Oil pump repair' };
  const h = articleIndexHarness([
    { ...indexResponse('completed', { complete: true, items: [hit] }), configuration },
    { ...indexResponse('completed', { complete: true, items: [hit, { id: 'different', title: 'Brake pads' }] }), configuration },
  ]);
  h.$('search').value = 'pump';
  assert.equal(await h.context.loadSavedSearch(h.navigation.next(), 'pump'), true);
  assert.deepEqual(h.requests.map(({ path }) => path), ['/v1/catalog/vehicles/B/articles?q=pump&region=US']);
  assert.equal(h.context.vehicle.model, 'Touring');
  assert.equal(h.context.indexLoaded, false);
  assert.equal(h.context.access, 'owned');
  assert.equal(h.$('catalog-count').textContent, '1 article');
  assert.equal(h.$('articles').children[0].children.length, 1);
  assert.match(h.$('completion-status').textContent, /search ready/i);

  h.$('search').value = '';
  h.$('search').events.input();
  await new Promise(setImmediate);
  assert.deepEqual(h.requests.map(({ path }) => path), [
    '/v1/catalog/vehicles/B/articles?q=pump&region=US', '/v1/catalog/vehicles/B/articles?region=US',
  ]);
  assert.equal(h.context.indexLoaded, true);
  assert.equal(h.$('articles').children[0].children.length, 2);
});

test('saved search only shows results from a current exact-scope response', async () => {
  for (const configuration of [null, { id: 'B', region: 'CA' }, { id: 'C', region: 'US' }]) {
    const h = articleIndexHarness([{ ...indexResponse('completed', { complete: true }), configuration }]);
    assert.equal(await h.context.loadSavedSearch(h.navigation.next(), 'pump'), false);
    assert.equal(h.context.access, '');
    assert.deepEqual(h.shown, []);
  }
  const response = deferredAuthOperation();
  const h = articleIndexHarness([() => response.promise]);
  const opening = h.context.loadSavedSearch(h.navigation.next(), 'pump');
  h.navigation.clear();
  response.resolve({ ...indexResponse('completed', { complete: true }), configuration: { id: 'B', region: 'US' } });
  assert.equal(await opening, true);
  assert.equal(h.context.searchItems, null);
  assert.deepEqual(h.shown, []);
});

test('saved search still treats a grant denial as an authorization error', async () => {
  const denial = Object.assign(new Error('Access required'), { status: 403, code: 'ENTITLEMENT_REQUIRED' });
  const h = articleIndexHarness([() => Promise.reject(denial)]);
  await assert.rejects(h.context.loadSavedSearch(h.navigation.next(), 'pump'), denial);
  assert.deepEqual(h.shown, []);
});

test('a saved long title uses one protected exact search and retains its article link', async () => {
  const title = { id: 'long-title', title: longArticleTitle };
  const h = articleIndexHarness([{
    ...indexResponse('completed', { complete: true, items: [title] }),
    configuration: { id: 'B', region: 'US' },
  }]);
  h.context.location = new URL(`https://cars.example/workshop/?configuration=B&region=US&q=${encodeURIComponent(longArticleTitle)}`);
  h.$('search').value = h.context.location.searchParams.get('q');
  const generation = h.navigation.next();
  assert.equal(await h.context.loadSavedSearch(generation, h.$('search').value, title.id), true);
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].signal, generation.signal);
  assert.deepEqual(Object.fromEntries(new URL(h.requests[0].path, h.context.location).searchParams), {
    title: longArticleTitle, region: 'US',
  });
  assert.equal(h.context.indexLoaded, false);
  const link = h.context.document.activeElement;
  const route = new URL(link.href, h.context.location).searchParams;
  assert.equal(route.get('article'), title.id);
  assert.equal(route.get('q'), longArticleTitle);
  assert.equal(route.has('title'), false);
});

test('complete saved search can show an exact no-match result before the full index', async () => {
  const h = articleIndexHarness([{
    ...indexResponse('completed', { complete: true }), configuration: { id: 'B', region: 'US' },
  }]);
  h.$('search').value = 'alternator';
  assert.equal(await h.context.loadSavedSearch(h.navigation.next(), 'alternator'), true);
  assert.match(h.$('no-results').textContent, /no articles match this search/i);
  assert.equal(h.requests.length, 1);
});

test('a saved search on a confirmed empty catalog shows availability without another read', async () => {
  const empty = indexResponse('completed', { complete: true });
  const h = articleIndexHarness([{
    ...empty, configuration: { id: 'B', region: 'US' }, progress: { ...empty.progress, catalog_empty: true },
  }]);
  h.$('search').value = 'alternator';
  assert.equal(await h.context.loadSavedSearch(h.navigation.next(), 'alternator'), true);
  assert.equal(h.$('no-results').textContent, 'No articles are currently available for this vehicle.');
  assert.equal(h.$('completion-status').textContent, 'No articles are currently available for this vehicle.');
  h.$('search').value = 'starter';
  h.$('search').events.input();
  await new Promise(setImmediate);
  assert.equal(h.$('catalog-count').textContent, '0 articles');
  assert.equal(h.$('no-results').textContent, 'No articles are currently available for this vehicle.');
  assert.equal(h.requests.length, 1);
});

test('partial saved search displays matches while waiting for the full index', async () => {
  const configuration = { id: 'B', region: 'US' };
  const hit = { id: 'a', title: 'Pump repair', availability: 'available', source_revision_id: 'first' };
  const full = deferredAuthOperation();
  const response = { ...indexResponse('completed', { complete: true, items: [hit] }), configuration };
  const h = articleIndexHarness([
    { ...indexResponse('running', { hydrating: true, items: [hit] }), configuration },
    () => full.promise,
    response,
  ]);
  h.$('search').value = 'pump';
  const opening = h.context.loadSavedSearch(h.navigation.next(), 'pump');
  await new Promise(setImmediate);
  assert.equal(h.$('articles').children[0].children.length, 1);
  assert.match(h.$('catalog-count').textContent, /1 articles so far/);
  assert.equal(h.context.indexLoaded, false);
  full.resolve(response);
  assert.equal(await opening, true);
  assert.equal(h.context.indexLoaded, true);
  assert.deepEqual(h.requests.map(({ path }) => path), [
    '/v1/catalog/vehicles/B/articles?q=pump&region=US',
    '/v1/catalog/vehicles/B/articles?region=US',
    '/v1/catalog/vehicles/B/articles?q=pump&region=US',
  ]);
});

test('open demo requests the real index and shows only readable articles', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [
    { id: 'ready', title: 'Stored procedure', availability: 'available' },
    { id: 'waiting', title: 'Index only', availability: 'unavailable' },
  ] })], { openDemo: true });
  await h.load();
  assert.equal(h.requests[0].path, '/v1/catalog/vehicles/B/articles?region=US&demo=1');
  assert.equal(h.$('articles').children[0].children.length, 1);
  assert.match(h.$('catalog-count').textContent, /1 available articles · 2 indexed/);
});

test('open demo direct link to an indexed but unreadable article stays in the index', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [
    { id: 'waiting', title: 'Index only', availability: 'unavailable' },
  ] })], { openDemo: true });
  await h.load('waiting');
  assert.equal(h.opened.length, 0);
  assert.match(h.$('activity-text').textContent, /indexed but not readable yet/);
});

test('actual article index flow polls until explicit current completion', async () => {
  for (const responses of [
    [indexResponse('pending', { hydrating: true }), indexResponse('running', { hydrating: true }), indexResponse('completed', { complete: true })],
    [indexResponse('failed', { retryable: true, hydrating: true }), indexResponse('completed', { complete: true })],
  ]) {
    const h = articleIndexHarness(responses);
    await h.load();
    assert.equal(h.requests.length, responses.length);
    assert.equal(h.statuses.filter(s => s.complete === true).length, 1);
    assert.equal(h.updates.slice(0, -1).every(u => u.completion === ''), true);
    assert.equal(h.$('completion-status').textContent, 'No articles are currently available for this vehicle.');
  }
});

test('actual article index flow keeps terminal, timed out, and nonhydrating outcomes incomplete', async () => {
  for (const [response, reads, text] of [
    [indexResponse('failed'), 1, /could not be prepared/],
    [indexResponse('pending', { hydrating: true }), 4, /still being prepared/],
    [indexResponse('pending'), 1, /still being prepared/],
    [indexResponse(null), 1, /still being prepared/],
  ]) {
    const h = articleIndexHarness([response]);
    await h.load();
    assert.equal(h.requests.length, reads);
    assert.equal(h.statuses.some(s => s.complete === true), false);
    assert.match(h.$('activity-text').textContent, text);
    assert.equal(h.$('completion-status').textContent, '');
    assert.equal(h.results[0].timedOut === true, reads === 4);
    assert.equal(typeof h.context.retryAction, response.progress?.status === 'failed' ? 'object' : 'function');
  }
});

test('the first rows of an empty owned index appear on a short authenticated check', async () => {
  const empty = indexResponse('running', { hydrating: true });
  const first = { id: 'first-article', title: 'Oil pump repair' };
  const partial = indexResponse('running', { hydrating: true, items: [first] });
  const waitAfterFirstRows = deferredAuthOperation();
  let clock = 0;
  const h = articleIndexHarness([empty, partial, indexResponse('completed', { complete: true, items: [first] })], {
    now: () => clock,
    wait(ms) {
      clock += ms;
      if (ms === 1150) return waitAfterFirstRows.promise;
    },
  });
  const opening = h.load();
  await new Promise(setImmediate);
  assert.deepEqual(h.updates.map(update => update.count), [0, 1]);
  assert.equal(h.$('catalog').hidden, false);
  assert.equal(h.$('loading-progress').hidden, true);
  assert.match(h.$('activity-text').textContent, /open the articles below while more sources load/i);
  assert.equal(h.requests.length, 2);
  assert.equal(h.requests[0].path, h.requests[1].path);
  assert.equal(h.requests[0].signal, h.requests[1].signal);
  assert.equal(h.requests[0].prefer, paidPagePreferences);
  assert.equal(h.requests[1].prefer, paidPagePreferences);
  assert.equal(h.requests[1].timeout, 500);
  waitAfterFirstRows.resolve();
  await opening;
  assert.equal(h.requests.length, 3);
  assert.equal(h.$('completion-status').textContent, 'Article index ready.');
});

test('the index does not announce links for filtered or unreadable results', async () => {
  const configuration = { id: 'B', region: 'US' };
  const article = { id: 'first', title: 'Oil pump repair', availability: 'unavailable' };
  const partial = { ...indexResponse('running', { hydrating: true, items: [article] }), configuration };
  const final = { ...indexResponse('completed', { complete: true, items: [article] }), configuration };
  const noMatches = { ...indexResponse('running', { hydrating: true }), configuration };
  const openDemo = articleIndexHarness([partial, final], { openDemo: true });
  await openDemo.load();
  assert.equal(openDemo.statuses.some(status => status.text.includes('open the articles below')), false);

  const filtered = articleIndexHarness([partial, noMatches, final, noMatches]);
  filtered.$('search').value = 'cylinder';
  await filtered.load();
  assert.equal(filtered.statuses.some(status => status.text.includes('open the articles below')), false);
  assert.equal(filtered.$('articles').firstElementChild.children.length, 0);
});

test('a timed-out empty owned-index check keeps the ordinary polling deadline', async () => {
  const empty = indexResponse('running', { hydrating: true });
  const done = indexResponse('completed', { complete: true });
  let clock = 0;
  const reads = [];
  const h = articleIndexHarness([
    () => { reads.push(clock); return empty; },
    () => { reads.push(clock); clock += 500; throw new CatalogRequestError('Timed out'); },
    () => { reads.push(clock); return done; },
  ], { now: () => clock, wait: async (ms) => { clock += ms; } });
  await h.load();
  assert.deepEqual(reads, [0, 350, 1500]);
  assert.equal(h.requests[1].timeout, 500);
  assert.equal(h.$('completion-status').textContent, 'No articles are currently available for this vehicle.');
});

test('an empty owned-index check propagates access denial immediately', async () => {
  for (const status of [401, 403, 404, 410, 429]) {
    const denied = new CatalogRequestError('Access unavailable', { status });
    const h = articleIndexHarness([
      indexResponse('running', { hydrating: true }),
      () => { throw denied; },
    ]);
    await assert.rejects(h.load(), denied);
    assert.equal(h.requests.length, 2);
    assert.equal(h.updates.every(update => update.count === 0), true);
  }
});

test('partial index rows remain clickable during preparation and saved articles open immediately', async () => {
  const partial = indexResponse('running', { hydrating: true, items: [{ id: 'saved/article', title: 'Pump' }] });
  const h = articleIndexHarness([partial]);
  await h.load();
  assert.equal(h.requests.length, 3);
  assert.equal(h.updates[0].count, 1);
  const link = h.updates[0].link;
  assert.equal(new URL(link.href, 'https://cars.example').searchParams.get('article'), 'saved/article');
  let prevented = false;
  link.events.click({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(h.opened[0].id, 'saved/article');
  const saved = articleIndexHarness([partial]);
  await saved.load('saved/article');
  assert.equal(saved.requests.length, 1);
  assert.equal(saved.opened[0].id, 'saved/article');
  assert.equal(saved.statuses.some(s => s.complete === true), false);
});

test('saved article link survives an incomplete index and retries the same article', async () => {
  const pending = indexResponse('pending', { hydrating: true, items: [] });
  const ready = indexResponse('completed', { complete: true, items: [
    { id: 'saved/article', title: 'Oil pump', kind: 'procedure' },
  ] });
  const h = articleIndexHarness([pending, pending, pending, ready]);
  await h.load('saved/article');
  assert.equal(h.requests.length, 3);
  assert.equal(h.opened.length, 0);
  assert.match(h.$('activity-text').textContent, /still being prepared/i);
  assert.equal(h.$('retry').hidden, false);
  await h.context.retryAction();
  assert.equal(h.requests.length, 4);
  assert.equal(h.opened[0]?.id, 'saved/article');
});

test('saved article link missing from a complete index is unavailable', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [] })]);
  await assert.rejects(h.load('saved/article'), /unavailable for the selected vehicle/i);
  assert.equal(h.opened.length, 0);
});

test('saved article link missing from a failed index reports index failure', async () => {
  const h = articleIndexHarness([indexResponse('failed', { items: [] })]);
  await h.load('saved/article');
  assert.match(h.$('activity-text').textContent, /could not be prepared/i);
  assert.equal(h.$('retry').hidden, true);
  assert.equal(h.opened.length, 0);
});

test('nonempty explicit completed article index is ready after one read', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [{ id: 'saved', title: 'Pump' }] })]);
  await h.load();
  assert.equal(h.requests.length, 1);
  assert.equal(h.$('completion-status').textContent, 'Article index ready.');
});

test('a failed supplier index still shows articles returned by the available source', async () => {
  const h = articleIndexHarness([indexResponse('failed', { items: [{ id: 'oil-pump', title: 'Oil Pump' }] })]);
  await h.load();
  assert.equal(h.$('catalog-count').textContent, '1 article from available sources.');
  assert.equal(h.$('articles').firstElementChild.children[0].dataset.articleId, 'oil-pump');
  assert.equal(h.$('no-results').hidden, true);
  assert.match(h.$('activity-text').textContent, /open the articles below/i);
});

test('an unavailable poll keeps the authorized article links open and the index retryable', async () => {
  const item = { id: 'oil-pump', title: 'Oil Pump' };
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [item] }),
    () => Promise.reject(new CatalogRequestError('Refresh unavailable', { status: 503 })),
    indexResponse('completed', { complete: true, items: [item] }),
  ]);
  await h.load();
  assert.equal(h.context.access, 'owned');
  assert.equal(h.$('articles').firstElementChild.firstElementChild.dataset.articleId, item.id);
  assert.match(h.$('activity-text').textContent, /open the articles below/i);
  assert.equal(h.$('retry').hidden, false);
  await h.context.retryAction();
  assert.equal(h.$('completion-status').textContent, 'Article index ready.');
});

test('hydration reuses article rows and keeps keyboard focus on the same article ID', async () => {
  const polls = [deferredAuthOperation(), deferredAuthOperation()];
  const releases = [...polls];
  const first = { id: 'first/article', title: 'Pump service', kind: 'procedure' };
  const second = { ...first, id: 'second/article' };
  const added = { ...first, id: 'added/article' };
  const initial = indexResponse('running', { hydrating: true, items: [second, first] });
  const h = articleIndexHarness([initial, initial,
    indexResponse('completed', { complete: true, items: [first, second, added] })],
  { wait: () => polls.shift().promise });
  const loading = h.load();
  await new Promise(setImmediate);
  const list = h.$('articles').firstElementChild;
  const oldRows = [...list.children];
  const focused = oldRows[1].firstElementChild;
  focused.focus();
  releases[0].resolve();
  await new Promise(setImmediate);
  assert.equal(h.$('articles').firstElementChild, list);
  assert.equal(list.children[1].firstElementChild, focused);
  assert.equal(h.context.document.activeElement, focused);
  releases[1].resolve();
  await loading;
  assert.equal(h.$('articles').firstElementChild, list);
  assert.equal(list.children[0], oldRows[1]);
  assert.equal(list.children[1], oldRows[0]);
  assert.equal(h.context.document.activeElement, focused);
  assert.equal(new URL(focused.href, 'https://cars.example').searchParams.get('article'), first.id);
  for (const flags of [{button:1}, {ctrlKey:true}, {metaKey:true}, {altKey:true}, {shiftKey:true}]) {
    focused.events.click({ ...flags, preventDefault: () => assert.fail('modified click must stay native') });
  }
  assert.deepEqual(h.opened, []);
  focused.events.click({ preventDefault() {} });
  assert.deepEqual(h.opened, [{ id: first.id }]);

  h.context.articles = [second, added];
  h.context.renderArticles();
  assert.equal(focused.parent.parent, null);
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  assert.equal(h.$('articles').firstElementChild.children[0], oldRows[0]);
});

test('article index type labels show readable kinds beside titles without changing links', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [
    { id: 'source/procedure', title: 'Replace oil pump', kind: 'procedure' },
    { id: 'source/bulletin', title: 'Oil pressure notice', kind: 'technical_service_bulletin' },
    { id: 'source/other', title: 'Legacy entry', kind: 'legacy-content' },
  ] })]);
  await h.load();
  const list = h.$('articles').children[0];
  assert.equal(list.tag, 'ul');
  assert.equal(list.attributes.role, 'list');
  assert.deepEqual(list.children.map(row => row.children[0].children.map(span => span.textContent)), [
    ['Replace oil pump', 'Procedure'],
    ['Oil pressure notice', 'Technical service bulletin'],
    ['Legacy entry', 'Legacy content'],
  ]);
  assert.equal(new URL(list.children[0].children[0].href, 'https://cars.example').searchParams.get('article'), 'source/procedure');
});

test('large article indexes page stored descriptors and search beyond the visible page', async () => {
  const articles = Array.from({ length: 205 }, (_, index) => ({
    id: `article-${index + 1}`, title: `Service article ${index + 1}`,
  }));
  const [last] = articles.slice(-1);
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: articles }),
    indexResponse('completed', { complete: true, items: [last] }),
  ]);
  await h.load();
  const list = h.$('articles').firstElementChild;
  assert.equal(h.$('catalog-count').textContent, '205 articles');
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.equal(h.$('article-prev').disabled, true);
  assert.equal(list.children.length, 100);

  h.context.moveArticlePage(1);
  assert.equal(h.$('article-page-range').textContent, '101–200 of 205');
  assert.equal(list.firstElementChild.dataset.articleId, articles[100].id);
  h.context.focusArticleIndex(last.id);
  assert.equal(h.$('article-page-range').textContent, '201–205 of 205');
  assert.equal(h.$('article-next').disabled, true);
  assert.equal(h.context.document.activeElement.parent.dataset.articleId, last.id);
  h.context.moveArticlePage(-1);
  assert.equal(list.firstElementChild.dataset.articleId, articles[100].id);
  assert.equal(h.requests.length, 1);

  h.$('search').value = last.title;
  h.$('search').events.input();
  assert.equal(list.firstElementChild.dataset.articleId, last.id);
  await new Promise(setImmediate);
  assert.equal(h.$('article-pages').hidden, true);
  assert.equal(h.requests.length, 2);
  h.$('search').value = '';
  h.$('search').events.input();
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.equal(list.firstElementChild.dataset.articleId, articles[0].id);
  assert.equal(h.requests.length, 2);
  const focused = list.children[99].firstElementChild;
  focused.focus();
  h.context.articles = [{ id: 'new', title: 'New article' }, ...articles];
  h.context.renderArticles();
  assert.equal(h.$('article-page-range').textContent, '101–200 of 206');
  assert.equal(list.firstElementChild.firstElementChild, focused);
  assert.equal(h.context.document.activeElement, focused);
  h.$('article-next').focus();
  h.context.articles = articles.slice(0, 10);
  h.context.renderArticles();
  assert.equal(h.$('article-pages').hidden, true);
  assert.equal(h.context.document.activeElement, h.$('catalog-title'));
  h.context.articles = articles;
  h.context.renderArticles();
  assert.equal(h.$('article-pages').hidden, false);
  h.context.clearProtected();
  assert.equal(h.$('article-pages').hidden, true);
  assert.equal(h.$('article-page-range').textContent, '');
  assert.equal(h.$('article-prev').disabled, true);
  assert.equal(h.$('article-next').disabled, true);
});

const pageFixtureArticles = Array.from({ length: 205 }, (_, index) => ({
  id: `22222222-2222-4222-8222-${String(index + 1).padStart(12, '0')}`,
  title: `Service article ${index + 1}`,
}));
function pagedIndexResponse(offset, {
  descriptors = pageFixtureArticles, failed = false, hydrating = false, revision = 'a'.repeat(64),
} = {}) {
  return {
    ...indexResponse(hydrating ? 'running' : failed ? 'failed' : 'completed', {
      complete: !failed && !hydrating, hydrating, items: descriptors.slice(offset, offset + 100),
    }),
    configuration: { id: scope.configuration_id, region: scope.region },
    page: { offset, total: descriptors.length, revision },
  };
}

test('negotiated paid index reads one requested page and searches the whole terminal partial index', async () => {
  const hit = pageFixtureArticles[154];
  const h = articleIndexHarness([
    pagedIndexResponse(0, { failed: true }),
    pagedIndexResponse(100, { failed: true }),
    pagedIndexResponse(200, { failed: true }),
    indexResponse('failed', { items: [hit] }),
    indexResponse('failed'),
    pagedIndexResponse(100, { failed: true }),
  ]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  const rows = h.$('articles').firstElementChild;
  assert.equal(rows.children.length, 100);
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.equal(h.$('catalog-count').textContent, '205 articles from available sources.');
  assert.equal(h.$('article-prev').disabled, true);
  assert.equal(h.requests[0].path.split('?')[1], 'region=US');
  assert.equal(h.requests[0].prefer, paidPagePreferences);
  await h.context.moveArticlePage(1);
  assert.equal(rows.firstElementChild.dataset.articleId, pageFixtureArticles[100].id);
  assert.equal(h.$('article-page-range').textContent, '101–200 of 205');
  await h.context.moveArticlePage(1);
  assert.equal(rows.children.length, 5);
  assert.equal(h.$('article-page-range').textContent, '201–205 of 205');
  assert.equal(h.$('article-next').disabled, true);
  h.$('search').value = hit.title;
  h.$('search').events.input();
  assert.equal(rows.children.length, 0);
  await new Promise(setImmediate);
  assert.equal(rows.firstElementChild.dataset.articleId, hit.id);
  h.$('search').value = 'Alternator';
  h.$('search').events.input();
  await new Promise(setImmediate);
  assert.equal(h.$('catalog-count').textContent, '0 articles from available sources.');
  h.$('search').value = '';
  h.$('search').events.input();
  assert.equal(rows.firstElementChild.dataset.articleId, pageFixtureArticles[200].id);
  assert.equal(h.$('article-page-range').textContent, '201–205 of 205');
  await h.context.moveArticlePage(-1);
  assert.deepEqual(h.requests.map(({ path, prefer }) => [path.split('?')[1], prefer]), [
    ['region=US', paidPagePreferences],
    ['offset=100&region=US', paidPagePreferences],
    ['offset=200&region=US', paidPagePreferences],
    ['q=Service+article+155&region=US', undefined],
    ['q=Alternator&region=US', undefined],
    ['offset=100&region=US', paidPagePreferences],
  ]);
});

test('a paid index remains immediately pageable while another provider runs', async () => {
  const polls = Array.from({ length: 4 }, () => deferredAuthOperation());
  let nextPoll = 0;
  const added = {
    id: '99999999-9999-4999-8999-999999999999', title: 'New supplier procedure', availability: 'available',
  };
  const finished = pagedIndexResponse(200, {
    descriptors: [...pageFixtureArticles, added], revision: 'b'.repeat(64),
  });
  const h = articleIndexHarness([
    { ...indexResponse('running', { hydrating: true, items: pageFixtureArticles.slice(0, 1) }),
      configuration: { id: scope.configuration_id, region: scope.region } },
    pagedIndexResponse(0, { hydrating: true }),
    pagedIndexResponse(100, { hydrating: true }),
    pagedIndexResponse(200, { hydrating: true }),
    finished,
  ], { wait: () => polls[nextPoll++].promise });
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  // Start with one available descriptor, then allow the active snapshot to grow.
  const opening = h.load();
  await new Promise(setImmediate);
  assert.equal(h.$('articles').firstElementChild.children.length, 1);
  polls[0].resolve();
  await new Promise(setImmediate);
  assert.equal(h.requests[1].prefer, paidPagePreferences);
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.match(h.$('activity-text').textContent, /while more sources load/);
  const second = h.context.moveArticlePage(1);
  const canceled = assert.rejects(opening, { name: 'AbortError' });
  await new Promise(setImmediate);
  assert.equal(h.requests[1].signal.aborted, true);
  assert.equal(h.$('article-page-range').textContent, '101–200 of 205');
  const third = h.context.moveArticlePage(1);
  await new Promise(setImmediate);
  assert.equal(h.requests[2].signal.aborted, true);
  assert.equal(h.$('article-page-range').textContent, '201–205 of 205');
  for (const poll of polls.slice(1)) poll.resolve();
  await Promise.all([second, third, canceled]);
  assert.equal(h.$('article-page-range').textContent, '201–206 of 206');
  assert.equal(h.$('articles').firstElementChild.children.at(-1).dataset.articleId, added.id);
  assert.deepEqual(h.requests.map(({ path }) => new URL(path, 'https://cars.example').searchParams.get('offset')),
    [null, null, '100', '200', '200']);
});

test('paged reader Back reuses its index in-app and anchors a fresh browser history read', async () => {
  const anchor = pageFixtureArticles[100];
  const initial = [pagedIndexResponse(0), pagedIndexResponse(100)];
  const inApp = await openedIndexHistory(initial, { next: true });
  inApp.$('back').events.click();
  inApp.returnToIndex();
  assert.equal(inApp.context.document.activeElement, inApp.link);
  assert.equal(inApp.requests.length, 2);

  for (const retained of [true, false]) {
    const remaining = pageFixtureArticles.filter(item => item.id !== anchor.id);
    const descriptors = retained ? [...remaining, anchor] : remaining;
    const changed = pagedIndexResponse(retained ? 200 : 0, { descriptors, revision: 'b'.repeat(64) });
    const browser = await openedIndexHistory([...initial, changed], {
      next: true,
      onRestore({ context, navigation }, options) {
        context.clearProtected();
        return context.loadArticles(navigation.next(), '', options);
      },
    });
    await browser.returnToIndex();
    assert.deepEqual(browser.restores, [{ focusArticle: anchor.id, indexAnchor: anchor.id }]);
    assert.equal(browser.requests[2].path.split('?')[1], `anchor=${anchor.id}&region=US`);
    if (retained) {
      assert.equal(browser.$('article-page-range').textContent, '201–205 of 205');
      assert.equal(browser.context.document.activeElement.parent.dataset.articleId, anchor.id);
    } else {
      assert.equal(browser.$('article-page-range').textContent, '1–100 of 204');
      assert.equal(browser.context.document.activeElement, browser.$('catalog-title'));
    }
    assert.equal(browser.requests.length, 3);
  }
});

test('navigation and search discard a pending page and a denied page scrubs counts and rows', async () => {
  const late = deferredAuthOperation();
  const hit = pageFixtureArticles[154];
  const denial = new CatalogRequestError('Access revoked', { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const h = articleIndexHarness([
    pagedIndexResponse(0),
    () => late.promise,
    indexResponse('completed', { complete: true, items: [hit] }),
    () => Promise.reject(denial),
  ]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  const pending = h.context.moveArticlePage(1);
  assert.equal(h.context.moveArticlePage(1), undefined);
  assert.equal(h.requests.length, 2);
  h.$('search').value = hit.title;
  h.$('search').events.input();
  assert.equal(h.requests[1].signal.aborted, true);
  late.resolve(pagedIndexResponse(100));
  await pending;
  await new Promise(setImmediate);
  assert.equal(h.$('articles').firstElementChild.firstElementChild.dataset.articleId, hit.id);
  h.$('search').value = '';
  h.$('search').events.input();
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  await h.context.moveArticlePage(1);
  assert.equal(h.context.access, 'revoked');
  assert.equal(h.context.indexPage, null);
  assert.equal(h.$('catalog-count').textContent, '');
  assert.equal(h.$('article-page-range').textContent, '');
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.shown.at(-1), 'welcome');
});

test('a buffered paid page is rendered without another index request', async () => {
  const h = articleIndexHarness([]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.context.loadArticles(h.navigation.next(), '', { firstIndex: { value: pagedIndexResponse(0) } });
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.equal(h.requests.length, 0);
});

test('a legacy hydrating index keeps its local page when the index settles', async () => {
  const finish = deferredAuthOperation();
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: pageFixtureArticles }),
    indexResponse('completed', { complete: true, items: pageFixtureArticles }),
  ], { wait: () => finish.promise });
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  const opening = h.load();
  await new Promise(setImmediate);
  h.context.moveArticlePage(1);
  const focused = h.$('articles').firstElementChild.firstElementChild.firstElementChild;
  focused.focus();
  finish.resolve();
  await opening;
  assert.deepEqual(h.requests.map(({ path, prefer }) => [path.split('?')[1], prefer]), [
    ['region=US', paidPagePreferences],
    ['region=US', undefined],
  ]);
  assert.equal(h.$('article-page-range').textContent, '101–200 of 205');
  assert.equal(h.context.document.activeElement, focused);
});

test('a missing exact scope during a page read clears previously visible rows', async () => {
  const h = articleIndexHarness([
    pagedIndexResponse(0),
    () => Promise.reject(new CatalogRequestError('Missing vehicle', { status: 404, code: 'CATALOG_NOT_FOUND' })),
  ]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  await h.context.moveArticlePage(1);
  assert.equal(h.context.indexPage, null);
  assert.equal(h.$('catalog-count').textContent, '');
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.shown.at(-1), 'welcome');
});

test('paged search shows current-page matches during wait or transport failure', async () => {
  const failure = deferredAuthOperation();
  const h = articleIndexHarness([
    pagedIndexResponse(0), () => failure.promise,
    () => Promise.reject(new CatalogRequestError('Unavailable', { status: 503 })),
  ]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  h.$('search').value = 'Service article 100';
  h.$('search').events.input();
  const rows = h.$('articles').firstElementChild;
  assert.equal(rows.firstElementChild.dataset.articleId, pageFixtureArticles[99].id);
  assert.equal(h.$('catalog-count').textContent, '1 article from the loaded page. Searching…');
  failure.reject(new CatalogRequestError('Unavailable', { status: 503 }));
  await new Promise(setImmediate);
  assert.equal(rows.firstElementChild.dataset.articleId, pageFixtureArticles[99].id);
  assert.equal(h.$('catalog-count').textContent, '1 article from the loaded page. Search could not refresh.');
  h.$('search').value = 'No local matches';
  h.$('search').events.input();
  assert.equal(h.$('catalog-count').textContent, 'Searching articles…');
  await new Promise(setImmediate);
  assert.equal(h.$('catalog-count').textContent, 'Article search is unavailable. Try again.');
});

test('page refresh discards an in-flight search and accepts a fresh off-page result', async () => {
  for (const changed of ['revision', 'completeness']) {
    const page = deferredAuthOperation();
    const old = deferredAuthOperation();
    const fresh = deferredAuthOperation();
    const offPage = pageFixtureArticles[101];
    const h = articleIndexHarness([
      pagedIndexResponse(0, { failed: changed === 'completeness' }),
      () => page.promise, () => old.promise, () => fresh.promise,
    ]);
    h.context.vehicle = { id: scope.configuration_id, region: scope.region };
    await h.load();
    const updating = h.load();
    h.$('search').value = 'Procedure reference';
    h.$('search').events.input();
    page.resolve(pagedIndexResponse(0, { revision: (changed === 'revision' ? 'b' : 'a').repeat(64) }));
    await updating;
    assert.equal(h.requests[2].signal.aborted, true);
    old.resolve(indexResponse('completed', { complete: true, items: [pageFixtureArticles[102]] }));
    await new Promise(setImmediate);
    assert.equal(h.$('catalog-count').textContent, 'Searching articles…');
    fresh.resolve(indexResponse('completed', { complete: true, items: [offPage] }));
    await new Promise(setImmediate);
    assert.equal(h.$('articles').firstElementChild.firstElementChild.dataset.articleId, offPage.id);
    assert.equal(h.requests.length, 4);
  }
});

test('paid page negotiation rejects malformed shape and preserves an unpaged smaller fallback', async () => {
  const right = pagedIndexResponse(0);
  for (const response of [
    { ...right, configuration: { ...right.configuration, region: 'CA' } },
    { ...right, page: { ...right.page, revision: 'not-a-revision' } },
    { ...right, page: { ...right.page, offset: 100 } },
    { ...right, progress: null },
  ]) {
    const h = articleIndexHarness([response]);
    h.context.vehicle = { id: scope.configuration_id, region: scope.region };
    await assert.rejects(h.load(), /unreadable page/);
    assert.equal(h.$('articles').children.length, 0);
  }
  const h = articleIndexHarness([
    right,
    {
      ...indexResponse('completed', { complete: true, items: pageFixtureArticles.slice(0, 20) }),
      configuration: right.configuration,
    },
  ]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  await h.context.moveArticlePage(1);
  assert.equal(h.$('article-page-range').textContent, '');
  assert.equal(h.$('article-pages').hidden, true);
  assert.equal(h.$('catalog-count').textContent, '20 articles');
  assert.equal(h.requests.length, 2);
});

test('a paid page still displays stored rows when progress cannot be read', async () => {
  const h = articleIndexHarness([{ ...pagedIndexResponse(0), complete: false, progress: null }]);
  h.context.vehicle = { id: scope.configuration_id, region: scope.region };
  await h.load();
  assert.equal(h.$('articles').firstElementChild.children.length, 100);
  assert.equal(h.$('article-page-range').textContent, '1–100 of 205');
  assert.match(h.$('activity-text').textContent, /index update couldn’t load/);
  assert.equal(h.context.indexComplete, false);
});

test('a zero-match search keeps a failed partial index usable', async () => {
  const item = { id: 'one', title: 'Oil pump' };
  const h = articleIndexHarness([
    indexResponse('failed', { items: [item] }),
    indexResponse('failed'),
  ]);
  await h.load();
  assert.equal(h.$('catalog-count').textContent, '1 article from available sources.');
  h.$('search').value = 'Alternator';
  h.$('search').events.input();
  await new Promise(setImmediate);
  assert.equal(h.$('catalog-count').textContent, '0 articles from available sources.');
  assert.equal(h.$('no-results').textContent, 'No articles from available sources match this search.');
  h.$('search').value = '';
  h.$('search').events.input();
  assert.equal(h.$('articles').firstElementChild.firstElementChild.dataset.articleId, item.id);
});

test('article index empty states distinguish pending, completed empty and no search matches', async () => {
  const pending = articleIndexHarness([indexResponse('pending', { items: [] })]);
  await pending.load();
  assert.equal(pending.$('no-results').hidden, false);
  assert.match(pending.$('no-results').textContent, /still being prepared/i);

  const empty = articleIndexHarness([indexResponse('completed', { complete: true, items: [] })]);
  await empty.load();
  assert.equal(empty.$('no-results').hidden, false);
  assert.match(empty.$('no-results').textContent, /no articles are currently available/i);

  const search = articleIndexHarness([indexResponse('completed', { complete: true, items: [
    { id: 'source/pump', title: 'Oil pump', kind: 'procedure' },
  ] })]);
  await search.load();
  search.$('search').value = 'alternator';
  search.context.renderArticles();
  assert.equal(search.$('no-results').hidden, false);
  assert.match(search.$('no-results').textContent, /no articles match this search/i);
});

test('Workshop input searches owned article content through protected index query', async () => {
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'title-only', title: 'Service notes' }] }),
    indexResponse('completed', { complete: true, items: [{ id: 'content-hit', title: 'Service notes', kind: 'procedure' }] }),
  ]);
  await h.load();
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(h.requests[1].path, '/v1/catalog/vehicles/B/articles?q=ground+strap&region=US');
  const list = h.$('articles').children[0];
  assert.deepEqual(list.children.map(row => row.children[0].children[0].textContent), ['Service notes']);
  assert.equal(new URL(list.children[0].children[0].href, 'https://cars.example').searchParams.get('article'), 'content-hit');
  assert.equal(h.$('catalog-count').textContent, '1 article');
});

test('pasting a long title immediately finds only its exact off-page match', async () => {
  const article = { id: 'exact-title', title: longArticleTitle };
  const others = Array.from({ length: 101 }, (_, index) => ({ id: `other-${index}`, title: `Service article ${index}` }));
  others[0].title = `${longArticleTitle} supplement`;
  others[1].component = longArticleTitle;
  const response = deferredAuthOperation();
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [...others, article] }),
    () => response.promise,
  ]);
  h.context.location = new URL('https://cars.example/workshop/?configuration=B&region=US');
  h.context.names = [];
  h.context.history = { replaceState(_state, _title, url) { h.context.location = new URL(url, h.context.location); } };
  runInNewContext(appSection('function updateURL(', 'function rememberOrderRoute('), h.context);
  await h.load();
  assert.equal(h.$('article-page-range').textContent, '1–100 of 102');
  const paste = ` ${longArticleTitle.toLowerCase()} `;
  h.$('search').value = paste;
  h.$('search').events.input();
  const list = h.$('articles').firstElementChild;
  assert.deepEqual(list.children.map(row => row.dataset.articleId), [article.id]);
  assert.equal(h.$('article-pages').hidden, true);
  assert.equal(h.context.location.searchParams.get('q'), paste);
  assert.equal(h.context.location.searchParams.has('title'), false);
  assert.deepEqual(Object.fromEntries(new URL(h.requests[1].path, h.context.location).searchParams), {
    title: paste.trim(), region: 'US',
  });
  response.resolve(indexResponse('completed', { complete: true, items: [article] }));
  await new Promise(setImmediate);
  assert.deepEqual(list.children.map(row => row.dataset.articleId), [article.id]);
  assert.equal(h.requests.length, 2);
  h.$('search').value = '';
  h.$('search').events.input();
  assert.equal(h.$('article-page-range').textContent, '1–100 of 102');
  assert.equal(h.requests.length, 2);
});

test('open demo content search keeps its access marker and excludes unreadable hits', async () => {
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [
      { id: 'ready', title: 'Service notes', availability: 'available' },
      { id: 'waiting', title: 'Index only', availability: 'unavailable' },
    ] }),
    indexResponse('completed', { complete: true, items: [
      { id: 'ready', title: 'Service notes', availability: 'available' },
      { id: 'waiting', title: 'Index only', availability: 'unavailable' },
    ] }),
  ], { openDemo: true });
  await h.load();
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests[1].path, '/v1/catalog/vehicles/B/articles?q=ground+strap&region=US&demo=1');
  assert.equal(h.$('articles').children[0].children.length, 1);
});

test('changing hydration coalesces an in-flight query and only keeps current matching descriptors', async () => {
  const first = deferredAuthOperation(), followUp = deferredAuthOperation();
  const polls = [deferredAuthOperation(), deferredAuthOperation()];
  const same = { id: 'same', title: 'Pump service', availability: 'available', source_revision_id: 'rev-1' };
  const removed = { ...same, id: 'removed' };
  const changed = { ...same, id: 'changed' };
  const updated = { ...changed, source_revision_id: 'rev-2' };
  const added = { ...same, id: 'added' };
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [same, removed, changed] }),
    () => first.promise,
    indexResponse('running', { hydrating: true, items: [same, updated] }),
    indexResponse('completed', { complete: true, items: [same, updated, added] }),
    () => followUp.promise,
  ], { wait: () => polls.shift().promise });
  const releasePolls = [...polls];
  const timers = [];
  h.context.setTimeout = (callback, delay) => { timers.push(delay); callback(); return timers.length; };
  h.$('search').value = 'pump';
  const loading = h.load();
  await new Promise(setImmediate);
  const firstRequest = h.requests[1];
  assert.match(firstRequest.path, /\?q=pump&region=US$/);
  releasePolls[0].resolve();
  await new Promise(setImmediate);
  assert.equal(firstRequest.signal.aborted, false);
  releasePolls[1].resolve();
  await loading;
  assert.equal(h.requests.filter(request => request.path.includes('q=')).length, 1);
  first.resolve(indexResponse('running', { items: [same, removed, changed] }));
  await new Promise(setImmediate);
  assert.deepEqual(h.context.searchItems.map(item => item.id), ['same']);
  assert.equal(h.$('articles').children[0].children.length, 1);
  assert.equal(h.context.searchPending, true);
  assert.equal(h.requests.filter(request => request.path.includes('q=')).length, 2);
  followUp.resolve(indexResponse('completed', { complete: true, items: [same, added] }));
  await new Promise(setImmediate);
  assert.deepEqual(h.context.searchItems.map(item => item.id), ['same', 'added']);
  assert.equal(h.context.searchPending, false);
  assert.equal(h.$('catalog-count').textContent, '2 articles');
  assert.deepEqual(timers, []);
});

test('same-query hydration keeps settled hits and new queries show loaded matches during debounce', async () => {
  const poll = deferredAuthOperation(), refresh = deferredAuthOperation();
  const hit = { id: 'same', title: 'Pump service', availability: 'available', source_revision_id: 'rev-1' };
  const extra = { ...hit, id: 'other', title: 'More service notes' };
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [hit] }),
    indexResponse('running', { items: [hit] }),
    indexResponse('completed', { complete: true, items: [hit, extra] }),
    () => refresh.promise,
    indexResponse('completed', { complete: true, items: [extra] }),
  ], { wait: () => poll.promise });
  const typed = [];
  h.context.setTimeout = (callback, delay) => { typed.push({ callback, delay }); return typed.length; };
  h.$('search').value = 'pump';
  const loading = h.load();
  await new Promise(setImmediate);
  assert.equal(h.$('articles').children[0].children.length, 1);
  poll.resolve();
  await loading;
  assert.equal(h.$('articles').children[0].children.length, 1);
  assert.equal(h.context.searchPending, true);
  assert.deepEqual(typed, []);
  const refreshing = h.requests[3];
  h.$('search').value = 'notes';
  h.$('search').events.input();
  assert.equal(refreshing.signal.aborted, true);
  assert.deepEqual(h.$('articles').children[0].children.map(row => row.dataset.articleId), [extra.id]);
  assert.match(h.$('catalog-count').textContent, /loaded index.*searching/i);
  assert.deepEqual(typed.map(timer => timer.delay), [150]);
  typed[0].callback();
  refresh.resolve(indexResponse('completed', { complete: true, items: [hit] }));
  await new Promise(setImmediate);
  assert.deepEqual(h.context.searchItems.map(item => item.id), ['other']);
});

test('hydrating index polls do not restart a settled owned-content search', async () => {
  let releasePoll;
  const gate = new Promise(resolve => { releasePoll = resolve; });
  const pending = indexResponse('running', { hydrating: true, items: [{ id: 'index', title: 'Service notes' }] });
  const h = articleIndexHarness([
    pending,
    indexResponse('running', { items: [{ id: 'content-hit', title: 'Ground strap service' }] }),
    pending,
    pending,
  ], { wait: () => gate });
  const loading = h.load();
  await new Promise(resolve => setImmediate(resolve));
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.$('articles').children[0].children[0].children[0].children[0].textContent, 'Ground strap service');
  releasePoll();
  await loading;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests.filter(request => request.path.includes('?q=')).length, 1);
  assert.equal(h.$('articles').children[0].children[0].children[0].children[0].textContent, 'Ground strap service');
});

test('a completed index refreshes a formerly partial content search once', async () => {
  let releasePoll;
  const gate = new Promise(resolve => { releasePoll = resolve; });
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true, items: [{ id: 'index', title: 'Service notes' }] }),
    indexResponse('running', { items: [{ id: 'first', title: 'Ground strap service' }] }),
    indexResponse('completed', { complete: true, items: [{ id: 'index', title: 'Service notes' }, { id: 'new', title: 'More service notes' }] }),
    indexResponse('completed', { complete: true, items: [
      { id: 'first', title: 'Ground strap service' }, { id: 'new', title: 'New ground strap notes' },
    ] }),
  ], { wait: () => gate });
  const loading = h.load();
  await new Promise(resolve => setImmediate(resolve));
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.context.searchComplete, false);
  releasePoll();
  await loading;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests.filter(request => request.path.includes('?q=')).length, 2);
  assert.equal(h.context.searchComplete, true);
  assert.deepEqual(h.$('articles').children[0].children.map(row => row.children[0].children[0].textContent), [
    'Ground strap service', 'New ground strap notes',
  ]);
});

test('reopening an owned index removes a withdrawn content-search result', async () => {
  const privateItem = { id: 'private', title: 'Service notes', source_revision_id: 'source-1' };
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [privateItem] }),
    indexResponse('completed', { complete: true, items: [privateItem] }),
    indexResponse('completed', { complete: true, items: [] }),
  ]);
  await h.load();
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.$('articles').children[0].children.length, 1);
  await h.load();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests.filter(request => request.path.includes('?q=')).length, 1);
  assert.equal(h.requests.length, 3);
  assert.equal(h.$('articles').children[0].children.length, 0);
});

test('reopening an owned index refreshes content search after article revision changes', async () => {
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'article', title: 'Service notes', source_revision_id: 'source-1' }] }),
    indexResponse('completed', { complete: true, items: [{ id: 'article', title: 'Service notes', source_revision_id: 'source-1' }] }),
    indexResponse('completed', { complete: true, items: [{ id: 'article', title: 'Service notes', source_revision_id: 'source-2' }] }),
    indexResponse('completed', { complete: true, items: [] }),
  ]);
  await h.load();
  h.$('search').value = 'old procedure';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.$('articles').children[0].children.length, 1);
  await h.load();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests.filter(request => request.path.includes('?q=')).length, 2);
  assert.equal(h.$('articles').children[0].children.length, 0);
});

test('a complete index becoming incomplete retracts a definitive search no-match', async () => {
  const descriptor = { id: 'article', title: 'Service notes', source_revision_id: 'source-1' };
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [descriptor] }),
    indexResponse('completed', { complete: true, items: [] }),
    indexResponse('running', { items: [descriptor] }),
    indexResponse('running', { items: [] }),
  ]);
  await h.load();
  h.$('search').value = 'alternator';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(h.$('no-results').textContent, /no articles match/i);
  await h.load();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests.filter(request => request.path.includes('?q=')).length, 2);
  assert.match(h.$('no-results').textContent, /still being prepared/i);
  assert.doesNotMatch(h.$('no-results').textContent, /no articles match/i);
});

test('Workshop aborts a stale exact title search after a newer keyword query', async () => {
  let resolveOld;
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'index', title: 'Service notes' }] }),
    () => new Promise(resolve => { resolveOld = resolve; }),
    indexResponse('completed', { complete: true, items: [{ id: 'new', title: 'Battery service' }] }),
  ]);
  await h.load();
  h.$('search').value = longArticleTitle;
  h.$('search').events.input();
  h.$('search').value = 'battery';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests[1].signal.aborted, true);
  assert.equal(new URL(h.requests[1].path, 'https://cars.example').searchParams.get('title'), longArticleTitle);
  assert.equal(h.requests[2].path, '/v1/catalog/vehicles/B/articles?q=battery&region=US');
  assert.equal(h.$('articles').children[0].children[0].children[0].children[0].textContent, 'Battery service');
  resolveOld(indexResponse('completed', { complete: true, items: [{ id: 'old', title: 'Old result' }] }));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.$('articles').children[0].children[0].children[0].children[0].textContent, 'Battery service');
});

test('Workshop content search cannot publish after selected vehicle changes', async () => {
  let resolveOld;
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'private-b', title: 'Vehicle B repair' }] }),
    () => new Promise(resolve => { resolveOld = resolve; }),
  ]);
  await h.load();
  h.$('search').value = 'repair';
  h.$('search').events.input();
  h.context.vehicle = { id: 'C', region: 'US' };
  h.context.clearProtected();
  resolveOld(indexResponse('completed', { complete: true, items: [{ id: 'private-b', title: 'Vehicle B repair' }] }));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.requests[1].signal.aborted, true);
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.context.searchItems, null);
});

test('Workshop exact title search revocation clears private rows and returns to welcome', async () => {
  const denied = Object.assign(new Error('Grant revoked'), { status: 403 });
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'private', title: longArticleTitle }] }),
    () => Promise.reject(denied),
  ]);
  await h.load();
  h.$('search').value = longArticleTitle;
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.context.articles.length, 0);
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.$('catalog-count').textContent, '');
  assert.equal(h.shown.at(-1), 'welcome');
  assert.match(h.statuses.at(-1).text, /Grant revoked/i);
});

test('Workshop search grant revocation keeps a paid buyer out of a second checkout', async () => {
  const revoked = Object.assign(new Error('Grant revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'private', title: 'Private repair' }] }),
    () => Promise.reject(revoked),
  ]);
  await h.load();
  h.context.currentOrder = 'paid-order';
  h.context.paidOrder = { id: 'paid-order', configuration_id: 'B', region: 'US' };
  h.$('search').value = 'repair';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.context.access, 'revoked');
  assert.equal(h.context.currentOrder, '');
  assert.equal(h.context.paidOrder, null);
  assert.deepEqual(h.clearedOrders, ['paid-order']);
  assert.equal(h.$('articles').children.length, 0);
  assert.match(h.statuses.at(-1).text, /revoked.*support/i);
});

test('Workshop content search partial response never claims no matches', async () => {
  const h = articleIndexHarness([
    indexResponse('pending', { items: [{ id: 'index', title: 'Service notes' }] }),
    indexResponse('pending', { items: [] }),
  ]);
  await h.load();
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(h.$('no-results').textContent, /still being prepared/i);
  assert.doesNotMatch(h.$('no-results').textContent, /no articles match/i);
  assert.match(h.$('catalog-count').textContent, /still being prepared/i);
});

test('search can share an exact paid reader before the unfiltered index has articles', async () => {
  const refresh = deferredAuthOperation();
  const descriptor = { id: routeArticle, title: 'Oil pump' };
  const h = articleIndexHarness([
    indexResponse('running', { hydrating: true }),
    indexResponse('running', { hydrating: true, items: [descriptor] }),
  ], { wait: () => refresh.promise });
  const { context } = h;
  context.vehicle = { id: scope.configuration_id, region: scope.region };
  context.location = new URL(`https://cars.example/workshop/?order=${orderID}&q=pump`);
  context.URLSearchParams = URLSearchParams;
  context.validScope = validScope;
  context.scope = () => ({ configuration_id: context.vehicle.id, region: context.vehicle.region });
  context.history = { replaceState(_state, _unused, url) { context.location.href = new URL(url, context.location).href; } };
  context.currentOrder = orderID;
  context.paidOrder = { id: orderID, ...scope };
  runInNewContext(
    appSection('function clearOrderRoute(', 'function populate(') +
    appSection('function clearPaidOrderAction(', 'function completePaidOrder('),
    context,
  );
  const loading = h.load();
  try {
    await new Promise(setImmediate);
    assert.equal(context.location.searchParams.get('order'), orderID);
    h.$('search').value = 'pump';
    h.$('search').events.input();
    await new Promise(setImmediate);
    assert.equal(h.requests.length, 2);
    assert.equal(context.articles.length, 0);
    const link = h.$('articles').children[0].children[0].children[0];
    const params = new URL(link.href, context.location).searchParams;
    assert.equal(params.has('order'), false);
    assert.equal(params.get('configuration'), scope.configuration_id);
    assert.equal(params.get('region'), scope.region);
    assert.equal(params.get('article'), routeArticle);
    assert.equal(params.get('q'), 'pump');
    assert.equal(h.$('check-order').hidden, true);
    assert.equal(context.paidOrder.id, orderID);
  } finally {
    h.navigation.clear();
    refresh.resolve();
    await assert.rejects(loading, { name: 'AbortError' });
  }
});

test('Workshop search failure is announced in the polite result status', async () => {
  const h = articleIndexHarness([
    indexResponse('completed', { complete: true, items: [{ id: 'index', title: 'Service notes' }] }),
    () => Promise.reject(Object.assign(new Error('temporary outage'), { status: 503 })),
  ]);
  await h.load();
  h.$('search').value = 'ground strap';
  h.$('search').events.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(h.$('catalog-count').textContent, /search is unavailable/i);
  assert.match(h.$('no-results').textContent, /search is unavailable/i);
});

test('completed empty article index stays empty when a saved search query is present', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true, items: [] })]);
  h.$('search').value = 'alternator';
  await h.load();
  assert.equal(h.$('no-results').hidden, false);
  assert.match(h.$('no-results').textContent, /no articles are currently available/i);
});

test('article index terminal failure does not claim it is still being prepared', async () => {
  const h = articleIndexHarness([indexResponse('failed', { items: [] })]);
  await h.load();
  assert.equal(h.$('no-results').hidden, false);
  assert.match(h.$('no-results').textContent, /could not be prepared/i);
});

test('actual status DOM clears vehicle A completion immediately before vehicle B pending or terminal read resolves', async () => {
  for (const result of [indexResponse('pending', { hydrating: true }), indexResponse('failed')]) {
    let resolve;
    const h = articleIndexHarness([() => new Promise(done => { resolve = done; }), result]);
    h.context.status('Article index ready for vehicle A.', { complete: true });
    const loading = h.load();
    assert.equal(h.requests.length, 1);
    assert.equal(h.$('completion-status').textContent, '', 'clear A completion before awaiting B');
    resolve(result);
    await loading;
    assert.equal(h.$('completion-status').textContent, '');
  }
});

test('obsolete article index loads cannot clear or publish current navigation state', async () => {
  const h = articleIndexHarness([indexResponse('completed', { complete: true })]);
  const stale = h.navigation.next();
  h.navigation.next();
  h.context.status('Current vehicle is ready.', { complete: true });
  await h.load('', stale);
  assert.equal(h.requests.length, 0);
  assert.equal(h.$('completion-status').textContent, 'Current vehicle is ready.');

  let resolve;
  const inFlight = articleIndexHarness([() => new Promise(done => { resolve = done; })]);
  const loading = inFlight.load();
  inFlight.navigation.next();
  resolve(indexResponse('completed', { complete: true, items: [{ id: 'obsolete' }] }));
  await assert.rejects(loading, { name: 'AbortError' });
  assert.equal(inFlight.updates.length, 0);
  assert.equal(inFlight.statuses.some(s => s.complete === true), false);
});

test('generation changes without abort suppress in-flight article index rendering and ready copy', async () => {
  let resolve, current = true;
  const h = articleIndexHarness([() => new Promise(done => { resolve = done; })]);
  const generation = { signal: new AbortController().signal, current: () => current };
  const loading = h.load('', generation);
  current = false;
  resolve(indexResponse('completed', { complete: true, items: [{ id: 'obsolete' }] }));
  await loading;
  assert.equal(h.requests.length, 1);
  assert.equal(h.$('articles').children.length, 0);
  assert.equal(h.$('completion-status').textContent, '');
  assert.equal(h.statuses.some(s => s.complete === true), false);
});

const merchantFixture = () => ({
  enabled: true,
  terms_version: 'workshop-v1',
  terms_url: 'https://merchant.example/terms',
  privacy_url: 'https://merchant.example/privacy',
  refund_url: 'https://merchant.example/refunds',
  contact_url: 'https://merchant.example/contact',
  tax_notice: 'Synthetic fixture notice.',
});
const quoteTermsFixture = () => ({ purchase_terms_version: 'workshop-v1' });

test('paid access pending renders a non-Buy action even without merchant configuration', () => {
  for (const merchant of [merchantFixture(), null]) {
    const nodes = new Map();
    const $ = id => {
      if (!nodes.has(id)) nodes.set(id, {
        hidden: false, disabled: false, textContent: '',
        replaceChildren() {}, append() {},
      });
      return nodes.get(id);
    };
    const context = {
      $, validScope, validQuote, purchaseConfiguration, configurationLabel,
      scope: () => scope, quote, merchant, access: 'pending', currentOrder: '', unconfirmedOrder: null,
      vehicle: { id: scope.configuration_id, region: scope.region },
      session: { state: { authenticated: true, ready: true } },
      document: { createTextNode: text => ({ textContent: text }) },
      element: (tag, text) => ({ tag, textContent: text }),
    };
    runInNewContext(appSection('function renderPurchase(', 'async function selectVehicle('), context);
    context.renderPurchase();
    assert.match($('purchase-message').textContent, /Payment received.*do not pay again/);
    assert.equal($('purchase-action').disabled, true);
    assert.doesNotMatch($('purchase-action').textContent, /Buy/);
  }
});

test('checkout remains disabled while purchase settings are loading', () => {
  const nodes = new Map();
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, { replaceChildren() {}, append() {} });
    return nodes.get(id);
  };
  const context = {
    $, validScope, validQuote, purchaseConfiguration, configurationLabel,
    scope: () => scope, quote: scopedQuoteFixture(), merchant: null,
    merchantRequest: Promise.resolve(), access: 'missing', currentOrder: '', unconfirmedOrder: null,
    vehicle: { id: scope.configuration_id, region: scope.region },
    session: { state: { authenticated: true, ready: true } },
    document: { createTextNode: text => ({ textContent: text }) },
    element: (tag, text) => ({ tag, textContent: text }),
  };
  runInNewContext(appSection('function renderPurchase(', 'async function selectVehicle('), context);
  context.renderPurchase();
  assert.equal($('purchase-message').textContent, 'Checking purchase availability…');
  assert.equal($('purchase-action').disabled, true);
  assert.equal($('purchase-terms').hidden, true);
  context.merchant = merchantFixture();
  context.merchantRequest = null;
  context.renderPurchase();
  assert.equal($('purchase-action').disabled, false);
  assert.equal($('purchase-terms').hidden, false);
});

test('purchase readiness requires the supported terms contract', async t => {
  assert.equal(purchaseConfiguration(merchantFixture(), quoteTermsFixture()), true);
  for (const [label, version] of [
    ['missing', undefined], ['null', null], ['empty', ''], ['unsupported', 'workshop-v2'],
  ]) {
    await t.test(`matching ${label} terms remain unavailable`, () => {
      const config = { ...merchantFixture(), terms_version: version };
      const quote = { purchase_terms_version: version };
      assert.equal(purchaseConfiguration(config, quote), false);
    });
  }
  assert.equal(purchaseConfiguration(merchantFixture(), { purchase_terms_version: 'workshop-v2' }), false);
  assert.equal(purchaseConfiguration(merchantFixture(), {}), false);
  assert.equal(purchaseConfiguration(merchantFixture(), null), false);
  assert.equal(purchaseConfiguration(null, quoteTermsFixture()), false);
});

test('purchase readiness accepts only exact loopback TEST notice links', () => {
  const origin = 'http://localhost:3013';
  const config = merchantFixture();
  for (const key of ['terms_url', 'privacy_url', 'refund_url', 'contact_url'])
    config[key] = `${origin}/workshop/test-notices/${key.slice(0, -4)}`;
  const quote = quoteTermsFixture();
  assert.equal(purchaseConfiguration(config, quote), false);
  assert.equal(purchaseConfiguration(config, quote, { testCheckout: false, origin }), false);
  assert.equal(purchaseConfiguration(config, quote, { testCheckout: true, origin }), true);
  for (const badOrigin of ['http://localhost:3014', 'http://localhost',
    'http://localhost:3013/', 'http://localhost:3013.evil.test',
    'http://127.0.0.2:3013', 'https://localhost:3013'])
    assert.equal(purchaseConfiguration(config, quote, { testCheckout: true, origin: badOrigin }), false, badOrigin);
  for (const key of ['terms_url', 'privacy_url', 'refund_url', 'contact_url']) {
    for (const suffix of ['?x=1', '/', '#fragment', '-other'])
      assert.equal(purchaseConfiguration({ ...config, [key]: config[key] + suffix }, quote,
        { testCheckout: true, origin }), false, key + suffix);
  }
});

test('purchase readiness fails closed for unavailable merchant fields', () => {
  for (const enabled of [false, null, undefined, 'true', 1])
    assert.equal(purchaseConfiguration({ ...merchantFixture(), enabled }, quoteTermsFixture()), false);
  for (const tax_notice of [null, undefined, '', ' \n\t', 0])
    assert.equal(purchaseConfiguration({ ...merchantFixture(), tax_notice }, quoteTermsFixture()), false);
  for (const key of ['terms_url', 'privacy_url', 'refund_url', 'contact_url']) {
    for (const value of [null, undefined, '', '/terms', '//merchant.example/terms',
      'http://merchant.example/terms', 'javascript:alert(1)', 'data:text/plain,x',
      'https://user:pass@merchant.example/terms', 'https://merchant.example/has space',
      'https://merchant.example/line\nfeed', 'https://']) {
      assert.equal(purchaseConfiguration({ ...merchantFixture(), [key]: value }, quoteTermsFixture()), false, `${key}: ${String(value)}`);
    }
  }
});


// A deliberately bounded DOM model: production renderers/helpers run unchanged.
// This observes DOM/state contracts, not browser layout or accessibility trees.
class ArticleMediaNode {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.parentNode = null;
    this.dataset = {};
    this.attributes = new Map();
    this.handlers = new Map();
    this.hidden = false;
    this.disabled = false;
    this.open = false;
    this._text = '';
  }
  focus() { this.focusCalls = (this.focusCalls || 0) + 1; }
  scrollIntoView(options) { this.lastScroll = options; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  set textContent(value) { this.replaceChildren(); this._text = String(value); }
  get isConnected() { return this.tagName === 'body' || Boolean(this.parentNode?.isConnected); }
  contains(node) { return node === this || Boolean(node?.parentNode && this.contains(node.parentNode)); }
  get nextSibling() {
    const siblings = this.parentNode?.children || [];
    return siblings[siblings.indexOf(this) + 1] || null;
  }
  remove() {
    if (this.parentNode) {
      const siblings = this.parentNode.children;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentNode = null;
    }
  }
  append(...nodes) {
    for (const node of nodes) {
      if (node.tagName === '#fragment') this.append(...node.children);
      else { node.remove(); node.parentNode = this; this.children.push(node); }
    }
  }
  replaceChildren(...nodes) {
    for (const child of [...this.children]) child.remove();
    this._text = '';
    this.append(...nodes);
  }
  replaceWith(node) {
    if (!this.parentNode) return;
    const parent = this.parentNode, index = parent.children.indexOf(this);
    node.remove(); this.remove(); node.parentNode = parent;
    parent.children.splice(index, 0, node);
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); delete this[name]; }
  addEventListener(name, handler) {
    const handlers = this.handlers.get(name) || [];
    handlers.push(handler); this.handlers.set(name, handlers);
  }
  removeEventListener(name, handler) {
    this.handlers.set(name, (this.handlers.get(name) || []).filter(value => value !== handler));
  }
  dispatch(name, event = {}) { for (const handler of this.handlers.get(name) || []) handler(event); }
  querySelectorAll(selector) {
    if (selector === '[data-pending-source-image]')
      return mediaDescendants(this, 'p').filter(node => 'pendingSourceImage' in node.dataset);
    assert.equal(selector, 'figure');
    return mediaDescendants(this, 'figure');
  }
}
function mediaDescendants(node, tag) {
  return node.children.flatMap(child => [
    ...(child.tagName === tag ? [child] : []), ...mediaDescendants(child, tag),
  ]);
}
const mediaTags = node => node.children.map(n => n.tagName);
const mediaIDs = node => mediaDescendants(node, 'img').map(n => n.dataset.assetId);
const mediaURL = token => `/v1/catalog/images/v2.${token}`;
const mediaSourceURL = '/v1/catalog/vehicles/v/articles/a/source?source_revision_id=11111111-1111-4111-8111-111111111111';
function mediaArticle(blocks, images = [], changes = {}) {
  return { id: 'a', title: 'Pump service', content_origin: 'source', view_revision: 'view-1',
    source_revision_id: '11111111-1111-4111-8111-111111111111',
    document: { blocks }, images, ...changes };
}
function articleMediaHarness(overrides = {}) {
  const body = new ArticleMediaNode('body'), nodes = new Map();
  const ids = ['articles', 'article-content', 'source-review-frame', 'reference-data', 'library-items',
    'article-title', 'catalog-count', 'article-pages', 'article-page-range', 'article-prev', 'article-next',
    'article-note', 'source-review-meta', 'source-review', 'source-review-title', 'print', 'print-status',
    'welcome', 'reader', 'catalog', 'library', 'source-review-link', 'reader-vehicle', 'reader-engine', 'purchase', 'purchase-selection',
    'article-kind', 'article-reference', 'source-review-load', 'open-original', 'original-error', 'back-to-article', 'check-order',
    'library-more', 'library-message', 'library-title'];
  for (const id of ids) { const node = new ArticleMediaNode('div'); nodes.set(id, node); body.append(node); }
  const navigation = new NavigationGeneration(), searchNavigation = new NavigationGeneration(), g = navigation.next();
  const shows = [], statuses = [];
  const context = {
    URL, AbortController, AbortSignal, uuid, articlePresentation, configurationLabel, localImageURL, sourceReferenceURL,
    awaitingArticleRewrite, processingArticle, readableArticle, readyReprojectedSource,
    session: { state: { mode: null } }, sessionRequest: null,
    document: { body, title: '', createElement: tag => new ArticleMediaNode(tag),
      createDocumentFragment: () => new ArticleMediaNode('#fragment') },
    window: new EventTarget(),
    requestAnimationFrame() {},
    location: { origin: 'https://cars.example' },
    $: id => { assert.ok(nodes.has(id), `known DOM node ${id}`); return nodes.get(id); },
    navigation, searchNavigation, searchItems: null, searchQuery: '', searchPending: false,
    searchComplete: false, searchError: false, searchTimer: null, clearTimeout() {},
    currentArticle: null, articleIndexOrigin: null, renderedRevision: '', sourceURL: '', sourceRevision: 0, displayedSourceRevision: 0,
    articleImageRefresh: null, sourceImageRefresh: null, articles: [],
    libraryCursor: null, libraryPageRequest: null,
    currentOrder: '',
    access: 'granted', quote: { configuration_label: '2005 Toyota' }, vehicle: { region: 'US' },
    articlePath: id => `/v1/catalog/vehicles/v/articles/${id}`,
    requestArticleJSON: () => assert.fail('unexpected article request'),
    requestJSON: () => assert.fail('unexpected source request'),
    show: id => shows.push(id), status: (message, options) => statuses.push({ message, options }),
    ...overrides,
  };
  installArticleRequestPath(context);
  runInNewContext([
    appSection('const element =', 'const session ='),
    appSection('function clearProtected(', 'async function operation('),
    appSection('function vehicleIdentityLabel(', 'function purchaseConfigured('),
    appSection('const assetID =', 'async function loadArticle('),
    appSection('function rememberRetainedIndexArticle(', 'function returnToArticleIndex('),
    appSection('function validSourceURL(', 'async function library('),
  ].join('\n'), context);
  return { context, g, nodes, navigation, shows, statuses,
    render(article) { context.renderArticle(article, g); return nodes.get('article-content'); },
    content(article) { const parent = new ArticleMediaNode('div'); body.append(parent); context.renderContent(parent, article, g); return parent; },
  };
}

test('authored article links use the protected reader even when the target is off the index page', () => {
  const target = '11111111-1111-4111-8111-111111111111';
  const selected = { id: routeConfiguration, region: 'US' };
  const calls = [];
  const hrefs = [];
  const h = articleMediaHarness({
    session: { state: { authenticated: true, mode: 'firebase', csrf: 'fixture' } },
    vehicle: selected,
    location: { origin: 'https://cars.example', href: 'https://cars.example/workshop?article=origin' },
    scope: () => ({ configuration_id: h.context.vehicle.id, region: h.context.vehicle.region }),
    updateURL({ article }) {
      hrefs.push(article);
      h.context.location.href = 'https://cars.example/workshop?article=' + article;
    },
    operation(work) { return work(h.navigation.next()); },
    loadArticle(id, generation) { calls.push([id, generation.current()]); },
  });
  runInNewContext(appSection('function openArticle(', 'function validSourceURL('), h.context);
  h.context.articles = [{ id: 'origin' }];
  const source = h.content(mediaArticle([
    { type: 'link', text: 'Supplier reference', href: 'https://provider.invalid/private' },
    { type: 'link', text: 'Pump cover', target_article_id: target },
    { type: 'table', rows: [[{ blocks: [
      { type: 'link', text: 'Nested reference', target_article_id: target, href: 'javascript:alert(1)' },
      { type: 'link', text: 'Malformed', target_article_id: '../other' },
    ] }]] },
  ]));
  const links = mediaDescendants(source, 'a');
  assert.deepEqual(links.map(link => link.textContent), ['Pump cover', 'Nested reference']);
  for (const link of links) {
    const url = new URL(link.href, h.context.location.origin);
    assert.equal(url.pathname, '/workshop');
    assert.deepEqual([...url.searchParams], [
      ['configuration', selected.id], ['region', selected.region], ['article', target],
    ]);
  }
  assert.match(source.textContent, /Supplier reference/);
  assert.match(source.textContent, /Malformed/);

  let prevented = 0;
  const click = { button: 0, preventDefault() { prevented++; } };
  links[1].dispatch('click', { ...click, ctrlKey: true });
  assert.equal(prevented, 0);
  assert.deepEqual(calls, []);
  links[1].dispatch('click', click);
  assert.deepEqual(calls, [[target, true]]);
  assert.deepEqual(hrefs, [target]);
  assert.equal(h.context.articleIndexOrigin, null);
  assert.equal(h.g.current(), false);
  links[0].dispatch('click', click);
  assert.deepEqual(calls, [[target, true]], 'stale DOM cannot open another reader');
});

test('an authored link is inert after its vehicle or session changes', () => {
  for (const change of ['region', 'sign-out', 'account']) {
    const h = articleMediaHarness({
      session: { state: { authenticated: true, mode: 'firebase', csrf: 'first' } },
      vehicle: { id: routeConfiguration, region: 'US' },
      scope: () => ({ configuration_id: h.context.vehicle.id, region: h.context.vehicle.region }),
      openArticle() { assert.fail('stale link opened an article'); },
    });
    const source = h.content(mediaArticle([
      { type: 'link', text: 'Related procedure', target_article_id: '11111111-1111-4111-8111-111111111111' },
    ]));
    const [link] = mediaDescendants(source, 'a');
    if (change === 'region') h.context.vehicle.region = 'CA';
    else if (change === 'sign-out') h.context.session.state.authenticated = false;
    else h.context.session.state.csrf = 'second';
    link.dispatch('click', { button: 0, preventDefault() {} });
  }
});

function warmFigureHarness({ count = 7, origin = 'canonical', repeated = false } = {}) {
  const timeout = deferredAuthOperation(), printed = [];
  const window = Object.assign(new EventTarget(), { print() { printed.push(true); } });
  const h = articleMediaHarness({
    session: { state: { authenticated: true, mode: 'firebase' } }, window,
    delay(ms, signal) {
      assert.equal(ms, 15_000);
      signal.addEventListener('abort', () => timeout.reject(signal.reason), { once: true });
      return timeout.promise;
    },
  });
  h.context.viewGeneration = h.g;
  const assets = Array.from({ length: count }, (_, index) => ({ id: `figure-${index}`, url: mediaURL(repeated ? 'repeat' : index) }));
  const blocks = assets.map(({ id }) => ({ type: 'image', asset_id: id }));
  const content = h.render(mediaArticle(blocks, assets, { content_origin: origin }));
  const images = mediaDescendants(content, 'img');
  runInNewContext(appSection('async function printArticle()', '$("print").addEventListener') +
    appSection('window.addEventListener("beforeprint"', 'window.addEventListener("popstate"'), h.context);
  return { ...h, window, timeout, printed, images };
}

test('paid documents with many distinct figures load near the viewport and keep a placeholder until decode', () => {
  for (const origin of ['canonical', 'source']) {
    const h = warmFigureHarness({ origin });
    assert.ok(h.images.every(image => image.src && image.loading === 'lazy' && Object.hasOwn(image.dataset, 'figurePending')));
    h.images[0].dispatch('load');
    assert.equal(Object.hasOwn(h.images[0].dataset, 'figurePending'), false);
    assert.ok(Object.hasOwn(h.images[1].dataset, 'figurePending'));
    h.window.dispatchEvent(new Event('beforeprint'));
    assert.ok(h.images.every(image => image.loading === 'eager'));
  }
  for (const options of [{ count: 6 }, { repeated: true }]) {
    const h = warmFigureHarness(options);
    assert.ok(h.images.every(image => image.src && image.loading !== 'lazy' && !Object.hasOwn(image.dataset, 'figurePending')));
  }
});

test('reader Print releases offscreen images and waits for loaded figures or a visible failure marker', async () => {
  for (const finish of ['decoded', 'marked unavailable', 'failed', 'timeout', 'navigate']) {
    const h = warmFigureHarness();
    const decoding = deferredAuthOperation();
    for (const image of h.images) image.decode = () => decoding.promise;
    const printing = h.context.printArticle();
    assert.ok(h.images.every(image => image.loading === 'eager'), finish);
    assert.deepEqual(h.printed, [], finish);
    assert.match(h.nodes.get('print-status').textContent, /Loading illustrations/, finish);
    if (finish === 'navigate') h.navigation.clear();
    else if (finish === 'timeout') h.timeout.resolve();
    else if (finish === 'failed') decoding.reject(new Error('Image could not be decoded'));
    else {
      for (const image of h.images) {
        image.complete = true;
        image.naturalWidth = 200;
      }
      if (finish === 'marked unavailable') {
        h.images[0].naturalWidth = 0;
        h.context.showUnavailableImage(h.images[0]);
      }
      decoding.resolve();
    }
    await printing;
    const ready = finish === 'decoded' || finish === 'marked unavailable';
    assert.deepEqual(h.printed, ready ? [true] : [], finish);
    if (finish !== 'navigate') assert.equal(h.nodes.get('print-status').hidden, ready, finish);
  }
});

test('reader refocus shows the authorized article while its open Original is still being checked', async () => {
  const configuration = { id: routeConfiguration, region: 'US' };
  const article = mediaArticle([{ type: 'paragraph', text: 'Authorized article' }], [], {
    id: routeArticle,
    content_origin: 'canonical',
    source_review: { available: true, url: `/v1/catalog/vehicles/v/articles/${routeArticle}/source?source_revision_id=${routeOrder}` },
  });
  const account = deferredAuthOperation(), detail = deferredAuthOperation(), source = deferredAuthOperation();
  const calls = [];
  const h = articleMediaHarness({
    vehicle: configuration,
    scope: () => ({ configuration_id: configuration.id, region: configuration.region }),
    session: { state: { authenticated: true, mode: 'firebase' }, matchesCurrentSession: () => {
      calls.push('session'); return account.promise;
    } },
    requestArticleJSON(path, options) {
      assert.equal(path, `/v1/catalog/vehicles/v/articles/${routeArticle}?region=US`);
      assert.equal(options.signal, h.g.signal);
      calls.push('article'); return detail.promise;
    },
    requestJSON(path, options) {
      assert.equal(path, article.source_review.url);
      assert.equal(options.signal, h.g.signal);
      calls.push('source'); return source.promise;
    },
    renderPurchase() {},
    show(id) { h.nodes.get('reader').hidden = id !== 'reader'; },
  });
  h.context.document.visibilityState = 'visible';
  const content = h.render(article), main = content.children[0];
  h.context.sourceURL = article.source_review.url;
  h.nodes.get('article-reference').open = true;
  const frame = h.nodes.get('source-review-frame'), held = new ArticleMediaNode('p');
  held.textContent = 'Pinned source';
  frame.append(held);
  const focusTarget = h.nodes.get('source-review-load');
  h.nodes.get('reader').append(focusTarget);
  focusTarget.focus = () => {
    if (focusTarget.disabled) return;
    focusTarget.focusCalls = (focusTarget.focusCalls || 0) + 1;
    h.context.document.activeElement = focusTarget;
  };
  h.context.document.activeElement = focusTarget;
  runInNewContext(appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'), h.context);
  const checked = h.context.recheckReader(h.g);
  assert.deepEqual(calls, ['session', 'article', 'source']);
  assert.equal(h.nodes.get('reader').hidden, true);
  assert.equal(frame.hidden, true);
  assert.equal(h.context.document.body.dataset.printable, 'false');
  h.context.document.activeElement = h.context.document.body;
  detail.resolve({ status: 200, data: { configuration, article } });
  await new Promise(setImmediate);
  assert.equal(h.nodes.get('reader').hidden, true);
  account.resolve(true);
  await new Promise(setImmediate);
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(h.context.document.body.dataset.printable, 'true');
  assert.equal(content.children[0], main);
  assert.equal(frame.hidden, true);
  assert.equal(focusTarget.disabled, true);
  assert.equal(h.context.document.activeElement, h.context.document.body);
  source.resolve({ source: { url: article.source_review.url } });
  await checked;
  assert.equal(frame.hidden, false);
  assert.equal(frame.children[0], held);
  assert.equal(focusTarget.disabled, false);
  assert.equal(focusTarget.focusCalls, 1);
});

test('reader refocus discards a folded source so only the current account and article delay the reader', async () => {
  const configuration = { id: routeConfiguration, region: 'US' };
  const article = mediaArticle([{ type: 'paragraph', text: 'Authorized article' }], [], {
    id: routeArticle,
    content_origin: 'canonical',
    source_review: { available: true, url: `/v1/catalog/vehicles/v/articles/${routeArticle}/source?source_revision_id=${routeOrder}` },
  });
  const detail = deferredAuthOperation();
  const calls = [];
  const h = articleMediaHarness({
    vehicle: configuration,
    scope: () => ({ configuration_id: configuration.id, region: configuration.region }),
    session: { state: { authenticated: true, mode: 'firebase' }, async matchesCurrentSession() {
      calls.push('session'); return true;
    } },
    requestArticleJSON() { calls.push('article'); return detail.promise; },
    async requestJSON() { calls.push('source'); },
    renderPurchase() {},
    show(id) { h.nodes.get('reader').hidden = id !== 'reader'; },
  });
  h.render(article);
  h.context.sourceURL = article.source_review.url;
  h.nodes.get('article-reference').open = false;
  const frame = h.nodes.get('source-review-frame');
  frame.append(new ArticleMediaNode('p', 'Previously loaded source'));
  frame.hidden = false;
  runInNewContext(appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'), h.context);
  const checked = h.context.recheckReader(h.g);
  assert.deepEqual(calls, ['session', 'article']);
  assert.equal(frame.hidden, true);
  assert.equal(frame.textContent, '');
  assert.equal(h.nodes.get('open-original').hidden, false);
  assert.equal(h.nodes.get('source-review-link').href, article.source_review.url);
  assert.equal(h.nodes.get('reader').hidden, true);
  assert.equal(h.context.document.body.dataset.printable, 'false');
  detail.resolve({ status: 200, data: { configuration, article } });
  await checked;
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(h.context.document.body.dataset.printable, 'true');
  assert.equal(h.nodes.get('article-reference').open, false);
  assert.equal(h.nodes.get('source-review').hidden, false);
  assert.equal(h.context.sourceURL, '');
});

test('reader refocus clears an unavailable staged Original while keeping the authorized rewrite', async () => {
  const configuration = { id: routeConfiguration, region: 'US' };
  const path = `/v1/catalog/vehicles/v/articles/${routeArticle}/source?source_revision_id=`;
  const originalURL = path + mediaSourceURL.split('=')[1];
  const referenceURL = path + routeOrder;
  const article = mediaArticle([{ type: 'paragraph', text: 'Authorized article' }], [], {
    id: routeArticle, content_origin: 'canonical',
    source_review: { available: true, url: referenceURL },
  });
  const h = articleMediaHarness({
    vehicle: configuration, scope: () => ({ configuration_id: configuration.id, region: configuration.region }),
    session: { state: { authenticated: true, mode: 'firebase' }, async matchesCurrentSession() { return true; } },
    async requestArticleJSON() { return { status: 200, data: { configuration, article } }; },
    async requestJSON(url) {
      assert.equal(url, originalURL);
      throw Object.assign(new Error('Source is no longer available'), { status: 404, code: 'CATALOG_NOT_FOUND' });
    },
    renderPurchase() {},
    show(id) { h.nodes.get('reader').hidden = id !== 'reader'; },
  });
  const content = h.render({ ...article, original_source_review: { available: true, url: originalURL } });
  h.context.sourceURL = originalURL;
  h.nodes.get('article-reference').open = true;
  const frame = h.nodes.get('source-review-frame');
  frame.append(new ArticleMediaNode('p', 'Previously available staged source'));
  runInNewContext(appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'), h.context);
  await h.context.recheckReader(h.g);
  assert.equal(h.g.current(), true);
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(content.textContent, 'Authorized article');
  assert.equal(frame.hidden, true);
  assert.equal(frame.textContent, '');
  assert.equal(h.nodes.get('source-review-link').href, referenceURL);
});

async function recheckOpenedOriginal() {
  const configuration = { id: routeConfiguration, region: 'US' };
  const url = `/v1/catalog/vehicles/v/articles/${routeArticle}/source?source_revision_id=${routeOrder}`;
  const article = mediaArticle([{ type: 'paragraph', text: 'Authorized article' }], [], {
    id: routeArticle, content_origin: 'canonical', source_review: { available: true, url },
  });
  const pending = deferredAuthOperation(), requests = [], sessionEvents = [];
  const h = articleMediaHarness({
    vehicle: configuration, scope: () => ({ configuration_id: configuration.id, region: configuration.region }),
    session: {
      state: { authenticated: true, mode: 'firebase' },
      async matchesCurrentSession() { return true; },
      clear() { sessionEvents.push('clear'); },
      async bootstrap() { sessionEvents.push('bootstrap'); },
    },
    async requestArticleJSON() { return { status: 200, data: { configuration, article } }; },
    async requestJSON(path) {
      requests.push(path);
      if (requests.length === 2) return pending.promise;
      return { source: { url }, document: { blocks: [{ type: 'paragraph', text: 'Authorized Original' }] } };
    },
    cancelPickerRefreshes() {},
    renderPurchase() {},
    show(id) { h.nodes.get('reader').hidden = id !== 'reader'; h.shows.push(id); },
  });
  for (const id of ['cancel', 'loading-progress']) h.nodes.set(id, new ArticleMediaNode('div'));
  runInNewContext(appSection('async function operation(', 'function updateURL(') +
    appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'), h.context);
  const content = h.render(article), frame = h.nodes.get('source-review-frame');
  await h.context.loadSource(url, h.g);
  assert.equal(frame.textContent, 'Authorized Original');
  const checked = h.context.recheckReader(h.g);
  await new Promise(setImmediate);
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(frame.hidden, true);
  assert.deepEqual(requests, [url, url]);
  return { ...h, pending, checked, content, frame, requests, sessionEvents, url };
}

test('reader refocus keeps the same main DOM and allows an exact Original retry after 503', async () => {
  const h = await recheckOpenedOriginal(), main = h.content.children[0];
  h.pending.reject(Object.assign(new Error('Original temporarily unavailable'), { status: 503 }));
  await h.checked;

  assert.equal(h.g.current(), true);
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(h.context.document.body.dataset.printable, 'true');
  assert.equal(h.content.children[0], main);
  assert.equal(h.frame.hidden, true);
  assert.equal(h.frame.textContent, '');
  assert.equal(h.nodes.get('source-review-load').disabled, false);
  assert.equal(h.nodes.get('source-review-link').href, h.url);
  assert.match(h.nodes.get('source-review-meta').textContent, /load it again to retry/i);
  await h.context.loadSource(h.nodes.get('source-review-link').href, h.g);
  assert.deepEqual(h.requests, [h.url, h.url, h.url]);
  assert.equal(h.frame.hidden, false);
  assert.equal(h.frame.textContent, 'Authorized Original');
  assert.equal(h.content.children[0], main);
});

test('reader refocus clears both projections after an explicit Original access denial', async t => {
  for (const status of [401, 403, 410]) {
    await t.test(String(status), async () => {
      const h = await recheckOpenedOriginal();
      h.pending.reject(Object.assign(new Error('Original access denied'), { status }));
      await h.checked;

      assert.equal(h.g.current(), false);
      assert.equal(h.nodes.get('reader').hidden, true);
      assert.equal(h.context.document.body.dataset.printable, 'false');
      assert.equal(h.content.textContent, '');
      assert.equal(h.frame.textContent, '');
      assert.equal(h.context.sourceURL, '');
      assert.deepEqual(h.shows, ['reader', 'welcome']);
      assert.deepEqual(h.sessionEvents, status === 401 ? ['clear', 'bootstrap'] : []);
    });
  }
});

test('a late Original denial leaves the newly navigated reader intact', async () => {
  const h = await recheckOpenedOriginal();
  const next = h.navigation.next();
  h.context.resetReaderContent();
  h.context.renderArticle(mediaArticle([{ type: 'paragraph', text: 'Another article' }]), next);
  h.context.show('reader');
  const main = h.content.children[0];

  h.pending.reject(Object.assign(new Error('Old Original access denied'), { status: 403 }));
  await h.checked;
  assert.equal(next.current(), true);
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(h.content.children[0], main);
  assert.equal(h.content.textContent, 'Another article');
  assert.deepEqual(h.shows, ['reader', 'reader']);
});

test('opening My vehicles hides the previous purchase panel while Library is loading', async () => {
  const response = deferredAuthOperation();
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    requestJSON: () => response.promise,
  });
  const purchase = h.nodes.get('purchase');
  purchase.hidden = false;
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  const opening = h.context.library(h.g);
  assert.equal(purchase.hidden, true);
  response.resolve({ version: 'v1', next_cursor: null, items: [] });
  await opening;
  assert.equal(purchase.hidden, true);
});

test('a bundled first Library page is used only for the current signed-in route', async () => {
  const card = { configuration_id: routeConfiguration, library_item_id: routeOrder, label: 'Exact owned vehicle',
    region: 'US', access_state: 'viewable', granted_at: '2026-11-16T00:00:00Z' };
  const first = { version: 'v1', next_cursor: 'more', items: [card] };
  for (const scenario of ['valid', 'legacy', 'invalid', 'navigated', 'signed-out']) {
    const pending = deferredAuthOperation(), requests = [];
    const h = articleMediaHarness({
      session: { state: { authenticated: scenario !== 'signed-out' } }, validLibrary, clearReader() {},
      requestJSON: async path => { requests.push(path); return first; },
    });
    runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
    const opening = h.context.library(h.g, false, { initialAccountCheck: pending.promise });
    if (scenario === 'navigated') h.navigation.next();
    const bundled = scenario === 'invalid' ? { ...first, items: [{ ...card, region: '' }] }
      : scenario === 'legacy' ? undefined : first;
    pending.resolve(bundled);
    await opening;
    assert.deepEqual(requests, ['legacy', 'invalid'].includes(scenario) ? ['/v1/workshop/library?limit=20'] : []);
    const list = h.nodes.get('library-items');
    if (['navigated', 'signed-out'].includes(scenario)) assert.equal(list.children.length, 0);
    else assert.match(list.children[0].textContent, /Exact owned vehicle \/ US/);
  }
});

test('Library Load more makes one cursor request and keeps prior cards mounted', async () => {
  const page = (items, next_cursor) => ({ version: 'v1', items, next_cursor });
  const row = (configuration_id, library_item_id, label, access_state = 'viewable') => ({
    configuration_id, library_item_id, label, access_state, region: 'US',
    granted_at: access_state === 'revoked' ? null : '2026-11-16T00:00:00Z',
  });
  const first = row(routeConfiguration, routeOrder, 'Vehicle on page one');
  const second = row('22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333', 'Vehicle on page two', 'revoked');
  const pending = deferredAuthOperation(), calls = [];
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    requestJSON(path) {
      calls.push(path);
      return calls.length === 1 ? Promise.resolve(page([first], 'page/2')) : pending.promise;
    },
  });
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  const list = h.nodes.get('library-items'), more = h.nodes.get('library-more');
  await h.context.library(h.g);
  const originalCard = list.children[0];
  h.context.document.activeElement = more;
  const next = h.context.library(h.g, true);
  const duplicate = h.context.library(h.g, true);
  const busy = more.getAttribute('aria-disabled');
  pending.resolve(page([second], null));
  await Promise.all([next, duplicate]);
  assert.deepEqual(calls, ['/v1/workshop/library?limit=20', '/v1/workshop/library?limit=20&cursor=page%2F2']);
  assert.equal(busy, 'true');
  assert.equal(list.children[0], originalCard);
  assert.equal(list.children[1].children[0].focusCalls, 1);
  assert.match(list.children[1].textContent, /Vehicle on page two.*Access revoked/);
  assert.equal(mediaDescendants(list.children[1], 'button').length, 0);
  assert.equal(more.hidden, true);
  assert.equal(more.getAttribute('aria-disabled'), null);
});

test('an explicit Library open focuses and scrolls to the authorized cards after they render', async () => {
  const item = { configuration_id: routeConfiguration, library_item_id: routeOrder, label: 'Purchased engine',
    access_state: 'viewable', region: 'US', granted_at: '2026-11-16T00:00:00Z' };
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    requestJSON: async () => ({ version: 'v1', next_cursor: null, items: [item] }),
  });
  const title = new ArticleMediaNode('h2');
  const scrolls = [];
  title.scrollIntoView = options => {
    assert.equal(h.nodes.get('library-items').children.length, 1);
    scrolls.push([options.behavior, options.block]);
  };
  h.nodes.set('library-title', title);
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  await h.context.library(h.g);
  assert.equal(title.focusCalls ?? 0, 0);
  assert.deepEqual(scrolls, []);
  await h.context.library(h.navigation.next(), false, { focusOnShow: true });
  assert.equal(title.focusCalls, 1);
  assert.deepEqual(scrolls, [['instant', 'start']]);
});

test('a Library card retries the same exact vehicle and focuses its first article index', async () => {
  const item = { configuration_id: routeConfiguration, library_item_id: routeOrder, label: 'Purchased engine',
    access_state: 'viewable', region: 'CA', granted_at: '2026-11-16T00:00:00Z' };
  const attempts = [];
  let retryAction;
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    names: ['year', 'make', 'model', 'configuration'], populate() {}, updateURL() {},
    requestJSON: async () => ({ version: 'v1', next_cursor: '', items: [item] }),
    async selectVehicle(_g, _article, { quoteMode, focusOnShow }) {
      attempts.push({ ...h.context.vehicle, quoteMode, focusOnShow });
      if (attempts.length === 1) throw Object.assign(new Error('Unavailable'), { status: 503 });
    },
    operation(work, retry) {
      retryAction = retry;
      return work(h.navigation.next()).catch(() => {});
    },
  });
  h.nodes.set('search', new ArticleMediaNode('input'));
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  await h.context.library(h.g);
  h.nodes.get('library-items').children[0].children[2].dispatch('click');
  await new Promise(setImmediate);
  assert.equal(typeof retryAction, 'function');
  assert.equal(h.shows.at(-1), 'welcome');
  await retryAction();
  const expected = { id: item.configuration_id, region: item.region, engine: item.label,
    quoteMode: 'if-needed', focusOnShow: true };
  assert.deepEqual(attempts, [expected, expected]);
});

test('Library cards distinguish preparation review, temporary failure, and readable articles', async () => {
  const summaries = [
    ['preparing', 'CATALOG_PREPARATION_REVIEW', 'Article preparation needs review.'],
    ['preparing', 'CATALOG_PREPARATION_UNAVAILABLE', 'Articles are temporarily unavailable.'],
    ['preparing', 'CATALOG_SOURCE_UNAVAILABLE', 'Articles are temporarily unavailable.'],
    ['preparing', '', 'Preparing articles'],
    ['viewable', 'CATALOG_PREPARATION_REVIEW', 'Articles available'],
    ['revoked', 'CATALOG_PREPARATION_UNAVAILABLE', 'Access revoked. Contact support.'],
  ];
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    requestJSON: async () => ({ version: 'v1', next_cursor: '', items: summaries.map(([access_state, content_error_code], i) => ({
      configuration_id: routeConfiguration,
      library_item_id: String(i + 1) + '1111111-1111-4111-8111-111111111111',
      label: 'Fixture vehicle', region: 'US', access_state, content_error_code,
      granted_at: '2026-11-16T00:00:00Z',
    })) }),
  });
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  await h.context.library(h.g);
  const cards = h.nodes.get('library-items').children;
  assert.deepEqual(cards.map(card => card.children[1].textContent), summaries.map(row => row[2]));
  assert.deepEqual(cards.map(card => mediaDescendants(card, 'button').length), [1, 1, 1, 1, 1, 0]);
});

test('opening Library again clears the last empty result while waiting for a fresh page', async () => {
  const pending = deferredAuthOperation();
  const empty = { version: 'v1', next_cursor: '', items: [] };
  let reads = 0;
  const h = articleMediaHarness({
    session: { state: { authenticated: true } }, validLibrary, clearReader() {},
    requestJSON: () => ++reads === 1 ? Promise.resolve(empty) : pending.promise,
  });
  runInNewContext(appSection('async function library(', 'function clearReader('), h.context);
  await h.context.library(h.g);
  assert.match(h.nodes.get('library-message').textContent, /No vehicles purchased/);
  const reloading = h.context.library(h.navigation.next());
  assert.equal(h.nodes.get('library-message').textContent, '');
  const card = { library_item_id: routeOrder, configuration_id: routeConfiguration, region: 'US', label: 'New purchase',
    access_state: 'preparing', granted_at: '2026-11-16T00:00:00Z' };
  pending.resolve({ ...empty, items: [card] });
  await reloading;
  assert.match(h.nodes.get('library-items').textContent, /New purchase/);
});

test('clearing protected state also clears an earlier Library message and Load more cursor', () => {
  const h = articleMediaHarness();
  const more = h.nodes.get('library-more'), message = h.nodes.get('library-message');
  more.hidden = false;
  more.setAttribute('aria-disabled', 'true');
  message.textContent = 'No vehicles purchased yet.';
  h.context.libraryCursor = 'old-page';
  h.context.libraryPageRequest = Promise.resolve();
  h.context.clearProtected();
  assert.equal(h.context.libraryCursor, null);
  assert.equal(h.context.libraryPageRequest, null);
  assert.equal(more.hidden, true);
  assert.equal(more.getAttribute('aria-disabled'), null);
  assert.equal(message.textContent, '');
});

test('the retained Ford heading outline stays hierarchical in Published and Original', async () => {
  const authoredLevels = [1, 2, 3, 3, 2, 3, 3];
  const blocks = authoredLevels.map((level, index) => ({ type: 'heading', level, text: `Section ${index + 1}` }));
  const requests = [];
  const h = articleMediaHarness({
    async requestJSON(path) {
      requests.push(path);
      return { source: { url: mediaSourceURL }, document: { blocks } };
    },
  });
  const published = h.render(mediaArticle(blocks, [], { content_origin: 'canonical' }));
  assert.deepEqual(mediaTags(published), ['h3', 'h4', 'h5', 'h5', 'h4', 'h5', 'h5']);
  assert.deepEqual(published.children.map(node => node.dataset.headingStyle), Array(7).fill('3'));
  assert.deepEqual(requests, []);

  await h.context.loadSource(mediaSourceURL, h.g);
  const original = h.nodes.get('source-review-frame');
  assert.deepEqual(mediaTags(original), ['h4', 'h5', 'h6', 'h6', 'h5', 'h6', 'h6']);
  assert.deepEqual(original.children.map(node => node.textContent), blocks.map(block => block.text));
  assert.deepEqual(requests, [mediaSourceURL]);
});

test('nested article headings share the document outline and keep deep source targets', async () => {
  const deep = { type: 'heading', level: 6, block_id: 'deep', text: 'Final checks' };
  const blocks = [
    { type: 'heading', level: 4, text: 'Components' },
    { type: 'ordered_list', items: [{ blocks: [{
      type: 'table',
      columns: [{ blocks: [{ type: 'heading', level: 1, text: 'Service instructions' }] }],
      rows: [{ cells: [{ blocks: [deep, { type: 'image', asset_id: 'drawing' }] }] }],
    }] }] },
  ];
  const images = [{ id: 'drawing', url: mediaURL('drawing') }];
  const h = articleMediaHarness({
    requestJSON: async () => ({ source: { url: mediaSourceURL }, document: { blocks }, images }),
  });
  const published = h.render(mediaArticle(blocks, images, { content_origin: 'canonical' }));
  assert.deepEqual(mediaTags(published), ['h6', 'ol']);
  assert.deepEqual(mediaTags(mediaDescendants(published, 'th')[0]), ['h3']);
  const publishedCell = mediaDescendants(published, 'td')[0];
  assert.deepEqual(mediaTags(publishedCell), ['div', 'figure']);
  assert.equal(publishedCell.children[0].getAttribute('role'), 'heading');
  assert.equal(publishedCell.children[0].getAttribute('aria-level'), '8');
  assert.equal(publishedCell.children[0].dataset.headingStyle, '6');

  await h.context.loadSource(mediaSourceURL, h.g, 'deep');
  const original = h.nodes.get('source-review-frame');
  assert.deepEqual(mediaTags(original), ['div', 'ol']);
  assert.equal(original.children[0].getAttribute('aria-level'), '7');
  assert.deepEqual(mediaTags(mediaDescendants(original, 'th')[0]), ['h4']);
  const sourceCell = mediaDescendants(original, 'td')[0];
  assert.deepEqual(mediaTags(sourceCell), ['div', 'figure']);
  assert.equal(sourceCell.children[0].getAttribute('role'), 'heading');
  assert.equal(sourceCell.children[0].getAttribute('aria-level'), '9');
  assert.equal(sourceCell.children[0].getAttribute('tabindex'), '-1');
  assert.equal(sourceCell.children[0].focusCalls, 1);
  assert.deepEqual(mediaIDs(original), ['drawing']);
});

test('headings without an authored level use the reader base without changing known ranks', async () => {
  const blocks = [
    { type: 'heading', text: 'Unnumbered heading' },
    { type: 'heading', level: 4, text: 'Authored section' },
    { type: 'heading', level: 6, text: 'Authored detail' },
    { type: 'heading', level: 99, text: 'Invalid heading level' },
  ];
  const h = articleMediaHarness({
    requestJSON: async () => ({ source: { url: mediaSourceURL }, document: { blocks } }),
  });
  const published = h.render(mediaArticle(blocks, [], { content_origin: 'canonical' }));
  assert.deepEqual(mediaTags(published), ['h3', 'h3', 'h5', 'h3']);
  await h.context.loadSource(mediaSourceURL, h.g);
  assert.deepEqual(mediaTags(h.nodes.get('source-review-frame')), ['h4', 'h4', 'h6', 'h4']);
});

test('heading and paragraph illustrations keep their order, alt text, and caption', () => {
  const h = articleMediaHarness();
  const content = h.content(mediaArticle([
    { type: 'heading', level: 3, text: 'Locate the bracket', images: [{ asset_id: 'valid', alt: 'Bracket location', caption: 'View from above' }] },
    { type: 'paragraph', text: 'Check the alignment mark.', images: [{ asset_id: 'valid', alt: 'Alignment mark' }] },
    { type: 'step', text: 'Remove the bracket.' },
  ], [{ asset_id: 'valid', url: '/v1/catalog/images/v2.inline' }]));
  assert.deepEqual(content.children.slice(0, 5).map(node => node.tagName), ['h3', 'figure', 'p', 'figure', 'section']);
  assert.equal(mediaDescendants(content.children[1], 'img')[0].alt, 'Bracket location');
  assert.equal(mediaDescendants(content.children[1], 'figcaption')[0].textContent, 'View from above');
  assert.equal(mediaDescendants(content.children[3], 'img')[0].alt, 'Alignment mark');
});

test('full-size inspection uses the loaded figure and yields its keyboard scroll area', () => {
  const h = articleMediaHarness();
  const content = h.content(mediaArticle([
    { type: 'image', asset_id: 'ready', alt: 'Bolt locations', caption: 'Bracket fasteners' },
    { type: 'image', status: 'unavailable', unavailable_reason: 'SOURCE_NOT_FOUND', caption: 'Missing view' },
  ], [{ id: 'ready', url: mediaURL('ready') }]));
  const [button] = mediaDescendants(content, 'button');
  assert.equal(mediaDescendants(content, 'button').length, 1);
  const [img] = mediaDescendants(content, 'img');
  const viewport = img.parentNode;
  const src = img.src;
  assert.equal(button.hidden, true);
  button.dispatch('click');
  assert.equal(button.getAttribute('aria-pressed'), 'false');
  img.naturalWidth = 1100;
  img.dispatch('load');
  assert.equal(button.hidden, false);
  button.dispatch('click');
  assert.equal(button.getAttribute('aria-pressed'), 'true');
  assert.equal(viewport.getAttribute('tabindex'), '0');
  assert.equal(viewport.getAttribute('aria-label'), 'Bolt locations');
  assert.equal(img.src, src);
  assert.equal(img.parentNode, viewport);
  assert.equal(mediaDescendants(content, 'figcaption')[0].textContent, 'Bracket fasteners');
  viewport.scrollLeft = 105;
  button.dispatch('click');
  assert.equal(button.getAttribute('aria-pressed'), 'false');
  assert.equal(viewport.getAttribute('tabindex'), null);
  assert.equal(viewport.scrollLeft, 0);
  button.dispatch('click');
  img.dispatch('error');
  assert.equal(button.hidden, true);
  assert.equal(button.getAttribute('aria-pressed'), 'false');
  assert.equal(viewport.getAttribute('tabindex'), null);
  img.dispatch('load');
  h.navigation.clear();
  button.dispatch('click');
  assert.equal(button.getAttribute('aria-pressed'), 'false');
  assert.equal(img.src, src);
});

test('figure aliases keep the first available match and independent placement text', () => {
  const h = articleMediaHarness();
  const content = h.content(mediaArticle([
    { type: 'image', asset_id: 'shared', alt: 'First placement' },
    { type: 'table', rows: [[{ blocks: [{ type: 'image', asset_id: 'shared', alt: 'Nested placement' }] }]] },
  ], [
    { id: 'missing', asset_id: 'shared', status: 'unavailable' },
    { id: 'matched', image_id: 'shared', url: mediaURL('matched') },
    { id: 'shared', url: mediaURL('later') },
  ]));
  const images = mediaDescendants(content, 'img');
  assert.deepEqual(images.map(image => image.alt), ['First placement', 'Nested placement']);
  assert.deepEqual(images.map(image => image.src), Array(2).fill('https://cars.example' + mediaURL('matched')));
});

test('empty source block text displays the unavailable reason used by article search', () => {
  const h = articleMediaHarness();
  const content = h.content(mediaArticle([{ type: 'unavailable', text: '', unavailable_reason: 'Wiring diagram pending source review' }]));
  assert.match(content.textContent, /Wiring diagram pending source review/);
  const sourced = h.content(mediaArticle([{ type: 'unavailable', text: 'Visible source note', unavailable_reason: 'Hidden source reason' }]));
  assert.match(sourced.textContent, /Visible source note/);
  assert.doesNotMatch(sourced.textContent, /Hidden source reason/);
});

test('article tab title clears when protected content is invalidated', () => {
  const h = articleMediaHarness();
  h.render(mediaArticle([{ type: 'paragraph', text: 'Check pump.' }]));
  assert.equal(h.context.document.title, 'Pump service | AutoData');
  h.context.clearProtected();
  assert.equal(h.context.document.title, 'AutoData — The workshop reference');
});

test('article tab title clears on catalog and library navigation', () => {
  const nodes = Object.fromEntries(['welcome', 'catalog', 'reader', 'library']
    .map(id => [id, { hidden: true }]));
  const context = { document: { title: 'Pump service | AutoData' }, $: id => nodes[id] };
  runInNewContext(appSection('function show(', 'function clearProtected('), context);
  context.show('catalog');
  assert.equal(context.document.title, 'AutoData — The workshop reference');
  assert.equal(nodes.catalog.hidden, false);
  assert.equal(nodes.library.hidden, true);
  context.document.title = 'Other private article | AutoData';
  context.show('library');
  assert.equal(context.document.title, 'AutoData — The workshop reference');
  assert.equal(nodes.library.hidden, false);
  assert.equal(nodes.catalog.hidden, true);
});

test('article navigation focuses its visible heading once before preparation and preserves focus during updates', async () => {
  let resolvePrepare;
  const article = mediaArticle([{ type: 'paragraph', text: 'Ready content.' }]);
  const h = articleMediaHarness({
    session: { state: { authenticated: true, csrf: 'csrf' } },
    stage: () => {},
    requestArticleJSON: () => new Promise(resolve => { resolvePrepare = resolve; }),
    readArticle: async (read, { onUpdate }) => {
      const response = await read();
      onUpdate(response);
      h.nodes.get('print').focus();
      onUpdate(response);
      return response;
    },
  });
  runInNewContext([
    appSection('function show(', 'function clearProtected('),
    appSection('async function loadArticle(', 'function openArticle('),
  ].join('\n'), h.context);
  const pending = h.context.loadArticle('a', h.g);
  const title = h.nodes.get('article-title');
  assert.equal(h.nodes.get('reader').hidden, false);
  assert.equal(h.nodes.get('catalog').hidden, true);
  assert.equal(title.textContent, 'Opening article…');
  assert.equal(title.focusCalls, 1, 'focus must enter the reader while preparation is pending');
  resolvePrepare({ data: { article } });
  await pending;
  assert.equal(title.textContent, 'Pump service');
  assert.equal(title.focusCalls, 1, 'prepare and polling updates must not reclaim focus');
  assert.equal(h.nodes.get('print').focusCalls, 1);
});

test('a fresh article aligns its focused heading once unless the reader has already moved', async () => {
  for (const interruption of ['', 'heading below viewport', 'focus', 'past heading', 'wheel', 'navigation']) {
    const frames = [], alignments = [];
    const stored = { data: { article: mediaArticle([{ type: 'paragraph', text: 'Stored steps.' }]) } };
    const canonical = { data: { article: mediaArticle([{ type: 'paragraph', text: 'Published steps.' }], [],
      { content_origin: 'canonical', view_revision: 'view-2' }) } };
    const h = articleMediaHarness({
      window: new EventTarget(),
      session: { state: { authenticated: true, csrf: 'csrf' } },
      stage() {},
      requestAnimationFrame(callback) { frames.push(callback); },
      requestArticleJSON: async () => stored,
      async readArticle(read, { onUpdate }) {
        onUpdate(await read());
        onUpdate(canonical);
        return canonical;
      },
    });
    const heading = h.nodes.get('article-title');
    h.context.document.activeElement = heading;
    heading.getBoundingClientRect = () => ({
      bottom: interruption === 'past heading' ? -10 : interruption === 'heading below viewport' ? 1200 : 510,
    });
    h.nodes.get('reader').scrollIntoView = options => alignments.push(options.block);
    runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
    await h.context.loadArticle('a', h.g);
    assert.equal(frames.length, 1, interruption);
    if (interruption === 'focus') h.context.document.activeElement = h.nodes.get('print');
    if (interruption === 'wheel') h.context.window.dispatchEvent(new Event('wheel'));
    if (interruption === 'navigation') h.navigation.clear();
    frames[0]();
    const shouldAlign = !interruption || interruption === 'heading below viewport';
    assert.deepEqual(alignments, shouldAlign ? ['start'] : [], interruption);
  }
});

test('readable source ends the opening progress while the rewrite continues', async () => {
  const source = mediaArticle([{ type: 'paragraph', text: 'Original procedure.' }], [], {
    processing: { job_id: 'rewrite', state: 'rewriting' },
  });
  const canonical = mediaArticle([{ type: 'paragraph', text: 'Rewritten procedure.' }], [], {
    content_origin: 'canonical', view_revision: 'published', review_status: 'UNREVIEWED',
  });
  const available = deferredAuthOperation(), published = deferredAuthOperation();
  const h = articleMediaHarness({
    session: { state: { authenticated: true, csrf: 'csrf' } }, stage() {}, openDemo: false,
    requestArticleJSON: async () => ({ data: { article: source } }),
    async readArticle(read, { onUpdate }) {
      onUpdate(await read());
      onUpdate({ data: { article: source } });
      available.resolve();
      await published.promise;
      const response = { data: { article: canonical } };
      onUpdate(response);
      return response;
    },
  });
  runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
  const opening = h.context.loadArticle('a', h.g);
  await available.promise;
  assert.deepEqual(h.statuses.map(({ message }) => message), ['Opening article…', 'Stored source is ready.']);
  assert.equal(h.statuses.at(-1).options.busy, undefined);
  assert.equal(h.statuses.at(-1).options.cancelable, true);
  assert.equal(h.nodes.get('print').disabled, false);
  assert.equal(h.nodes.get('article-note').textContent, 'Preparing the Workshop rewrite.');
  published.resolve();
  await opening;
  assert.equal(h.statuses.at(-1).message, 'Article ready.');
  assert.match(h.nodes.get('article-note').textContent, /has not been reviewed/);
});

test('the reader displays supplier text before the original figures finish', async () => {
  const first = mediaArticle([
    { type: 'paragraph', text: 'Remove the retaining bolts.' },
    { type: 'image', status: 'unavailable', unavailable_reason: 'SOURCE_MEDIA_PENDING', caption: 'Retaining bolt locations' },
  ], [], {
    source_body_preview: true, source_revision_id: null, view_revision: 'supplier-body',
    processing: { job_id: 'capture', state: 'fetching_source' },
  });
  const full = mediaArticle([{ type: 'paragraph', text: 'Remove the retaining bolts.' }], [], {
    view_revision: 'stored-source',
  });
  const seen = deferredAuthOperation(), release = deferredAuthOperation();
  const h = articleMediaHarness({
    session: { state: { authenticated: true, csrf: 'csrf' } }, stage() {}, openDemo: false,
    requestArticleJSON: async () => ({ status: 200, data: { article: first } }),
    async readArticle(read, { onUpdate }) {
      onUpdate(await read());
      seen.resolve();
      await release.promise;
      const result = { status: 200, data: { article: full } };
      onUpdate(result);
      return result;
    },
  });
  runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
  const opening = h.context.loadArticle('a', h.g);
  await seen.promise;
  assert.equal(h.nodes.get('article-kind').textContent, 'Supplier source');
  assert.match(h.nodes.get('article-content').textContent, /Remove the retaining bolts/);
  assert.match(h.nodes.get('article-content').textContent, /Preparing illustration…Retaining bolt locations/);
  assert.equal(h.statuses.at(-1).message, 'Source text is ready.');
  release.resolve();
  await opening;
  assert.equal(h.nodes.get('article-kind').textContent, 'Stored source');
  assert.doesNotMatch(h.nodes.get('article-content').textContent, /Preparing illustration/);
});

test('same-revision supplier preview keeps its position when figure preparation fails', () => {
  const preview = mediaArticle([
    { type: 'paragraph', text: 'Remove the retaining bolts.' },
    { type: 'image', status: 'unavailable', unavailable_reason: 'SOURCE_MEDIA_PENDING', caption: 'Retaining bolt locations' },
    { type: 'image', asset_id: 'ready', caption: 'Released bolts' },
    { type: 'image', status: 'unavailable', unavailable_reason: 'SOURCE_NOT_FOUND', caption: 'Missing view' },
    { type: 'paragraph', text: 'Continue after the figures.' },
  ], [{ id: 'ready', url: mediaURL('ready') }], {
    source_body_preview: true, source_revision_id: null, view_revision: 'supplier-body',
    processing: { job_id: 'capture', state: 'fetching_source' },
  });
  const h = articleMediaHarness();
  const content = h.render(preview);
  const mounted = [...content.children];
  const [body, pending, prepared, unavailable] = mounted;
  const [placeholder, caption] = pending.children;
  const [image] = mediaDescendants(prepared, 'img');
  h.context.document.activeElement = h.nodes.get('print');
  const update = retryable => h.render({ ...preview, processing: { ...preview.processing, state: 'failed', retryable } });

  assert.equal(placeholder.textContent, 'Preparing illustration…');
  update(true);
  assert.equal(placeholder.textContent, 'Preparing illustration…');
  update(false);
  assert.equal(placeholder.textContent, 'Illustration unavailable.');
  assert.equal(content.children.length, mounted.length);
  for (const [index, node] of mounted.entries()) assert.equal(content.children[index], node);
  assert.equal(pending.children[0], placeholder);
  assert.equal(pending.children[1], caption);
  assert.equal(caption.textContent, 'Retaining bolt locations');
  assert.equal(body.textContent, 'Remove the retaining bolts.');
  assert.equal(mediaDescendants(prepared, 'img')[0], image);
  assert.equal(image.src, 'https://cars.example' + mediaURL('ready'));
  assert.equal(unavailable.children[0].textContent, 'Illustration unavailable.');
  assert.equal(h.context.document.activeElement, h.nodes.get('print'));

  const terminal = articleMediaHarness().render({ ...preview, processing: { ...preview.processing, state: 'failed', retryable: false } });
  assert.match(terminal.textContent, /Illustration unavailable\.Retaining bolt locations/);
  assert.doesNotMatch(terminal.textContent, /Preparing illustration/);
});

test('authoritative article not-found clears previously readable source and printing', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const { readArticle } = await import('./workshop/article-read.mjs');
  const source = mediaArticle([{ type: 'paragraph', text: 'Previously readable pump procedure.' }], [], {
    processing: { job_id: 'rewrite', state: 'rewriting' },
  });
  for (const status of [404, 503]) {
    let calls = 0, elapsed = 0;
    const h = articleMediaHarness({
      session: { state: { authenticated: true, csrf: 'fixture' } }, stage() {},
      viewGeneration: null, paidOrder: null, access: 'owned', articles: [{ id: 'another-article' }],
      requestArticleJSON(path, options) {
        return requestArticleJSON(path, { ...options, fetcher: async () => {
          if (calls++ === 0) return new Response(JSON.stringify({ article: source }));
          assert.match(h.nodes.get('article-content').textContent, /Previously readable pump procedure/);
          assert.equal(h.nodes.get('print').disabled, false);
          return new Response(JSON.stringify({ error: {
            code: status === 404 ? 'CATALOG_NOT_FOUND' : 'CATALOG_UNAVAILABLE', retryable: status === 503,
          } }), { status });
        } });
      },
      readArticle: (read, options) => readArticle(read, { ...options, now: () => elapsed,
        wait: async duration => { elapsed += duration; }, budgetMs: 2000 }),
    });
    for (const id of ['cancel', 'loading-progress']) h.nodes.set(id, new ArticleMediaNode('div'));
    runInNewContext(appSection('async function operation(', 'function updateURL(') +
      appSection('async function loadArticle(', 'function openArticle('), h.context);
    await h.context.operation(g => h.context.loadArticle('a', g));
    assert.equal(calls, 2);
    assert.equal(h.context.access, 'owned');
    assert.equal(h.context.articles.length, 1);
    if (status === 404) {
      assert.equal(h.nodes.get('article-content').textContent, '');
      assert.equal(h.nodes.get('print').disabled, true);
      assert.equal(h.context.document.body.dataset.printable, 'false');
      assert.equal(h.nodes.get('article-title').textContent, 'Article unavailable');
      assert.match(h.statuses.at(-1).message, /could not be found/);
    } else {
      assert.match(h.nodes.get('article-content').textContent, /Previously readable pump procedure/);
      assert.equal(h.nodes.get('print').disabled, false);
      assert.match(h.statuses.at(-1).message, /Article is readable/);
    }
  }
});

test('article detail not-found during image renewal invalidates only that reader', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const h = articleMediaHarness({
    session: { state: { authenticated: true, mode: 'firebase' } }, access: 'owned',
    requestArticleJSON: (path, options) => requestArticleJSON(path, { ...options, fetcher: async () =>
      new Response(JSON.stringify({ error: { code: 'CATALOG_NOT_FOUND' } }), { status: 404 }) }),
  });
  h.render(mediaArticle([{ type: 'image', asset_id: 'fixture' }, { type: 'paragraph', text: 'Readable procedure.' }],
    [{ id: 'fixture', url: mediaURL('fixture') }]));
  const image = mediaDescendants(h.nodes.get('article-content'), 'img')[0];
  await h.context.renewMedia(h.g, image);
  assert.equal(h.context.access, 'owned');
  assert.equal(h.g.current(), false);
  assert.equal(h.nodes.get('article-content').textContent, '');
  assert.equal(h.nodes.get('print').disabled, true);
  assert.match(h.statuses.at(-1).message, /could not be found/);
});

test('pinned source not-found clears its panel and preserves the canonical procedure', async () => {
  let calls = 0;
  const h = articleMediaHarness({
    requestJSON: (path, options) => requestJSON(path, { ...options, fetcher: async () => {
      if (calls++ === 0) return new Response(JSON.stringify({ source: { url: mediaSourceURL },
        document: { blocks: [{ type: 'paragraph', text: 'Retained source text' }] } }));
      return new Response(JSON.stringify({ error: { code: 'CATALOG_NOT_FOUND' } }), { status: 404 });
    } }),
  });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Canonical procedure' }], [], {
    content_origin: 'canonical', source_review: { available: true, url: mediaSourceURL },
  }));
  await h.context.loadSource(mediaSourceURL, h.g);
  assert.match(h.nodes.get('source-review-frame').textContent, /Retained source text/);
  await h.context.loadSource(mediaSourceURL, h.g).catch(error => h.context.handleSourceError(error, h.g));
  assert.equal(h.nodes.get('source-review-frame').textContent, '');
  assert.equal(h.nodes.get('source-review-frame').hidden, true);
  assert.equal(h.nodes.get('article-content').textContent, 'Canonical procedure');
  assert.equal(h.nodes.get('print').disabled, false);
  assert.equal(h.g.current(), true);
});

test('obsolete article navigation leaves current heading and focus alone', async () => {
  const h = articleMediaHarness({ session: { state: { authenticated: true } } });
  runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
  h.nodes.get('article-title').textContent = 'Current article';
  h.navigation.clear();
  await h.context.loadArticle('obsolete', h.g);
  assert.equal(h.nodes.get('article-title').textContent, 'Current article');
  assert.equal(h.nodes.get('article-title').focusCalls, undefined);
  assert.deepEqual(h.shows, []);
});

test('retrying a visible article keeps its source and tab title while preparation fails', async () => {
  let rejectPrepare;
  const h = articleMediaHarness({
    session: { state: { authenticated: true, csrf: 'csrf' } },
    stage: () => {},
    requestArticleJSON: () => new Promise((_, reject) => { rejectPrepare = reject; }),
  });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Check pump.' }]));
  runInNewContext([
    appSection('function show(', 'function clearProtected('),
    appSection('async function loadArticle(', 'function openArticle('),
  ].join('\n'), h.context);
  const retry = h.context.loadArticle('a', h.g);
  assert.equal(h.nodes.get('article-title').textContent, 'Pump service');
  assert.equal(h.context.document.title, 'Pump service | AutoData');
  assert.equal(h.nodes.get('article-content').textContent, 'Check pump.');
  rejectPrepare(new Error('temporarily unavailable'));
  await assert.rejects(retry, /temporarily unavailable/);
  assert.equal(h.context.document.title, 'Pump service | AutoData');
  assert.equal(h.nodes.get('article-content').textContent, 'Check pump.');
});

test('opening another article removes the previous source and disables printing until it loads', async () => {
  let resolvePrepare;
  const h = articleRouteHarness('firebase', path => {
    assert.equal(path, '/v1/catalog/vehicles/v/articles/b/prepare?region=US');
    return new Promise(resolve => { resolvePrepare = resolve; });
  });
  const previousArticle = mediaArticle([{ type: 'paragraph', text: 'Old procedure.' }], [], {
    review_status: 'UNREVIEWED', source_review: { available: true, url: mediaSourceURL },
  });
  h.render(previousArticle);
  h.context.requestJSON = async () => ({
    source: { url: mediaSourceURL },
    document: { blocks: [{ type: 'paragraph', text: 'Old source copy.' }] },
  });
  await h.context.loadSource(mediaSourceURL, h.g);
  assert.equal(h.nodes.get('source-review-frame').hidden, false);
  assert.equal(h.context.document.body.dataset.printable, 'true');

  const pending = h.context.loadArticle('b', h.navigation.next());
  assert.equal(h.nodes.get('article-title').textContent, 'Opening article…');
  assert.equal(h.context.document.title, 'AutoData — The workshop reference');
  assert.equal(h.context.currentArticle, null);
  assert.equal(h.nodes.get('article-kind').textContent, '');
  assert.equal(h.nodes.get('article-note').hidden, true);
  assert.equal(h.nodes.get('article-reference').open, false);
  assert.equal(h.nodes.get('source-review').hidden, true);
  assert.equal(h.nodes.get('source-review-link').href, undefined);
  assert.equal(h.nodes.get('source-review-frame').textContent, '');
  assert.equal(h.context.document.body.dataset.printable, 'false');

  const nextArticle = mediaArticle([{ type: 'paragraph', text: 'Next procedure.' }], [], {
    id: 'b', title: 'Seal service', view_revision: 'view-2',
  });
  resolvePrepare({ data: { article: nextArticle } });
  await pending;
  assert.equal(h.nodes.get('article-title').textContent, 'Seal service');
  assert.equal(h.nodes.get('article-content').textContent, 'Next procedure.');
  assert.equal(h.nodes.get('source-review').hidden, true);
  assert.equal(h.context.document.body.dataset.printable, 'true');
});

for (const [type, tag] of [['ordered_list', 'ol'], ['unordered_list', 'ul']]) {
  test(`article block media ${type} keeps normalized items and retained sibling figure order`, () => {
    const h = articleMediaHarness();
    const parent = h.content(mediaArticle([
      { type: 'paragraph', text: 'Before' },
      { type, items: ['Check pump.', 'Install seal.'], images: [{ asset_id: 'direct' }, { image_id: 'flattened' }] },
      { type: 'paragraph', text: 'After' },
    ], [{ id: 'unrelated', url: mediaURL('unused') }, { id: 'flattened', url: mediaURL('flat') }, { id: 'direct', url: mediaURL('direct') }]));
    assert.equal(mediaDescendants(parent, 'figure').length, 2, 'retained list block images must produce two figures');
    assert.deepEqual(mediaTags(parent), ['p', tag, 'figure', 'figure', 'p']);
    assert.deepEqual(mediaTags(parent.children[1]), ['li', 'li']);
    assert.deepEqual(parent.children[1].children.map(n => n.textContent), ['Check pump.', 'Install seal.']);
    assert.deepEqual(mediaIDs(parent), ['direct', 'flattened']);
    assert.deepEqual(mediaDescendants(parent, 'img').map(n => n.src), ['https://cars.example/v1/catalog/images/v2.direct', 'https://cars.example/v1/catalog/images/v2.flat']);
    assert.equal(parent.children[0].textContent, 'Before');
    assert.equal(parent.children.at(-1).textContent, 'After');
  });
}
for (const label of ['Warning', 'Note']) {
  test(`article block media ${label} callout groups text and direct/flattened figures in its second child`, () => {
    const h = articleMediaHarness();
    const parent = h.content(mediaArticle([
      { type: 'paragraph', text: 'Before' },
      { type: 'callout', label, text: 'Keep clear.', images: [{ asset_id: 'direct' }, { asset_id: 'flattened' }], evidence_ids: ['e-7'], source_locator: 'body[3]' },
      { type: 'paragraph', text: 'After' },
    ], [{ id: 'flattened', url: mediaURL('flat') }, { id: 'direct', url: mediaURL('direct') }], { source_review: { available: true, url: mediaSourceURL } }));
    const aside = parent.children[1];
    assert.equal(mediaDescendants(aside, 'figure').length, 2, 'retained callout images must produce two figures');
    assert.deepEqual(mediaTags(parent), ['p', 'aside', 'a', 'p']);
    assert.equal(aside.className, 'article-callout');
    assert.deepEqual(mediaTags(aside), ['strong', 'div']);
    assert.equal(aside.children[0].textContent, label);
    assert.deepEqual(mediaTags(aside.children[1]), ['span', 'figure', 'figure']);
    assert.equal(aside.children[1].children[0].textContent, 'Keep clear.');
    assert.deepEqual(mediaTags(aside.children[1].children[0]), []);
    assert.deepEqual(mediaIDs(aside), ['direct', 'flattened']);
    assert.equal(parent.children[2].textContent, 'View source');
    assert.equal(parent.children[3].textContent, 'After');
  });
}

test('article block media mixed document preserves each contextual placement and supported consumers', () => {
  const h = articleMediaHarness();
  const parent = h.content(mediaArticle([
    { type: 'ordered_list', items: ['First'], images: [{ asset_id: 'shared' }] },
    { type: 'callout', text: 'Careful', images: [{ asset_id: 'callout' }] },
    { type: 'step', number: 3, instructions: ['Remove'], images: [{ asset_id: 'step' }] },
    { type: 'table', columns: ['Part'], rows: [[{ text: 'Seal', images: [{ asset_id: 'cell' }] }]] },
    { type: 'image', asset_id: 'shared' },
  ], ['cell', 'step', 'callout', 'shared', 'unused'].map(id => ({ id, url: mediaURL(id) }))));
  assert.deepEqual(mediaIDs(parent), ['shared', 'callout', 'step', 'cell', 'shared']);
  assert.deepEqual(mediaTags(parent), ['ol', 'figure', 'aside', 'section', 'div', 'figure']);
  assert.deepEqual(mediaIDs(parent.children[3]), ['step']);
  assert.deepEqual(mediaIDs(mediaDescendants(parent, 'td')[0]), ['cell']);
});

for (const origin of ['source', 'canonical']) {
  test(`article table block image stays beside the semantic table in the ${origin} reader`, () => {
    const h = articleMediaHarness();
    const parent = h.render(mediaArticle([
      { type: 'table', caption: 'Torque values', columns: ['Part', 'Torque'], rows: [['Bolt', '30 Nm']],
        images: [{ asset_id: 'row-image', alt: 'Bolt orientation', url: 'https://provider.example/untrusted.png' }] },
      { type: 'paragraph', text: 'Continue after the table.' },
    ], [{ id: 'row-image', url: mediaURL('row'), alt: 'Pool description' }],
    { content_origin: origin, complete: origin === 'canonical' }));
    assert.deepEqual(mediaTags(parent), ['div', 'figure', 'p']);
    assert.deepEqual(mediaTags(parent.children[0]), ['table']);
    assert.equal(mediaDescendants(parent, 'caption')[0].textContent, 'Torque values');
    assert.deepEqual(mediaDescendants(parent, 'th').map(n => n.scope), ['col', 'col']);
    assert.deepEqual(mediaDescendants(parent, 'td').map(n => n.textContent), ['Bolt', '30 Nm']);
    assert.deepEqual(mediaIDs(parent), ['row-image']);
    const image = mediaDescendants(parent, 'img')[0];
    assert.equal(image.src, 'https://cars.example/v1/catalog/images/v2.row');
    assert.equal(image.alt, 'Bolt orientation');
    assert.equal(image.referrerPolicy, 'no-referrer');
    assert.equal(mediaDescendants(parent, 'figcaption')[0].textContent, 'Bolt orientation');
    assert.equal(parent.children[2].textContent, 'Continue after the table.');
  });
}

for (const [name, ref, pool] of [
  ['missing ID', { unavailable_reason: 'missing source image reference' }, { id: 'unrelated', url: mediaURL('unrelated') }],
  ['missing pool mapping', { asset_id: 'missing', url: mediaURL('untrusted') }, { id: 'unrelated', url: mediaURL('unrelated') }],
]) {
  test(`article table block image ${name} never borrows unrelated pool media`, () => {
    const h = articleMediaHarness();
    const parent = h.content(mediaArticle([
      { type: 'table', rows: [['Bolt']], images: [ref] },
    ], [pool]));
    assert.deepEqual(mediaIDs(parent), []);
    assert.deepEqual(mediaTags(parent), ['div', 'figure']);
    assert.deepEqual(mediaTags(parent.children[1]), ['p']);
    assert.equal(parent.children[1].textContent, 'Illustration unavailable.');
  });
}

test('article table cell image missing an ID never borrows unrelated pool media', () => {
  const h = articleMediaHarness();
  const parent = h.content(mediaArticle([
    { type: 'table', rows: [[{ text: 'Bolt', images: [{ status: 'unavailable' }] }]] },
  ], [{ id: 'unrelated', url: mediaURL('unrelated') }]));
  assert.deepEqual(mediaIDs(parent), []);
  const cell = mediaDescendants(parent, 'td')[0];
  assert.deepEqual(mediaTags(cell), ['span', 'figure']);
  assert.equal(cell.children[1].textContent, 'Illustration unavailable.');
});

test('article table block image already shown in a cell is not repeated', () => {
  const h = articleMediaHarness();
  const parent = h.content(mediaArticle([
    { type: 'table', rows: [[{ text: 'Bolt', images: [{ asset_id: 'shared' }] }]],
      images: [{ image_id: 'shared', caption: 'Summary description' }, { asset_id: 'row-only' }] },
  ], [{ id: 'shared', url: mediaURL('shared') }, { id: 'row-only', url: mediaURL('row-only') }]));
  assert.deepEqual(mediaIDs(parent), ['shared', 'row-only']);
  assert.deepEqual(mediaIDs(mediaDescendants(parent, 'td')[0]), ['shared']);
  assert.deepEqual(mediaTags(parent), ['div', 'figure']);
  assert.ok(!parent.textContent.includes('Summary description'));
});

test('unavailable chart captions stay at their authored positions across stored and rewritten views', () => {
  const h = articleMediaHarness();
  const caption = 'Pressure at <2,000> rpm & warm';
  const unavailable = { status: 'unavailable', unavailable_reason: 'SOURCE_NOT_FOUND' };
  const chart = { type: 'image', asset_id: 'chart', caption, alt: 'Pressure chart', ...unavailable };
  const detached = { ...chart, caption: 'Apply the outlet correction at altitude.' };
  const noCaption = { type: 'image', asset_id: 'no-caption', caption: '', alt: 'Alt only', ...unavailable };
  const inline = { asset_id: 'inline', caption: 'Inline figure caption', ...unavailable };
  const denied = { asset_id: 'denied', caption: 'Hidden denied caption', status: 'unavailable', unavailable_reason: 'FORBIDDEN' };
  const images = ['chart', 'no-caption', 'inline', 'denied', 'unrelated'].map(id => ({ id, url: mediaURL(id) }));
  for (const origin of ['source', 'canonical']) {
    const parent = h.render(mediaArticle([{
      type: 'table',
      columns: [
        { blocks: [
          { type: 'paragraph', text: 'Check the pressure scale.' },
          chart,
          { type: 'paragraph', text: 'Read the upper line.' },
        ] },
        { blocks: [noCaption] },
        inline,
      ],
      rows: [['Supply', '500 kPa', denied]],
      images: [chart, detached, inline, noCaption],
    }, { type: 'paragraph', text: 'Continue after the table.' }], images, { content_origin: origin, view_revision: origin }));
    assert.deepEqual(mediaTags(parent), ['div', 'figure', 'p']);
    assert.deepEqual(mediaIDs(parent), []);
    assert.equal(mediaDescendants(parent, 'figure').length, 5);
    const [ordered, unlabelled, inlineCell] = mediaDescendants(parent, 'th');
    assert.deepEqual(mediaTags(ordered), ['p', 'figure', 'p']);
    assert.equal(ordered.children[0].textContent, 'Check the pressure scale.');
    assert.equal(ordered.children[2].textContent, 'Read the upper line.');
    const captioned = ordered.children[1];
    assert.deepEqual(mediaTags(captioned), ['p', 'figcaption']);
    assert.equal(captioned.children[0].textContent, 'Illustration unavailable.');
    assert.equal(captioned.children[1].textContent, caption);
    assert.deepEqual(captioned.children[1].children, []);
    const [plain] = unlabelled.children;
    assert.deepEqual(mediaTags(plain), ['p']);
    assert.equal(plain.children[0].textContent, 'Illustration unavailable.');
    assert.equal(mediaDescendants(inlineCell, 'figcaption')[0].textContent, inline.caption);
    assert.deepEqual(mediaTags(parent.children[1]), ['p', 'figcaption']);
    assert.equal(parent.children[1].children[1].textContent, detached.caption);
    assert.equal(parent.children[2].textContent, 'Continue after the table.');
    assert.equal(mediaDescendants(parent, 'figcaption').length, 3);
    assert.ok(!parent.textContent.includes(denied.caption));
  }
});

for (const type of ['ordered_list', 'unordered_list', 'callout']) {
  for (const [name, ref] of [
    ['missing IDs', { status: 'unavailable', unavailable_reason: 'source image reference is missing' }],
    ['empty IDs', { asset_id: '', image_id: '' }],
  ]) {
    for (const origin of [undefined, 'source', 'canonical']) {
      test(`article block media ${type} rejects ${name} with a valid unrelated pool in ${origin || 'renderContent'}`, () => {
        const h = articleMediaHarness();
        const article = mediaArticle([{ type, items: ['Check'], text: 'Note', images: [ref] }],
          [{ id: 'unrelated', url: mediaURL('unrelated') }], origin ? { content_origin: origin } : {});
        const parent = origin ? h.render(article) : h.content(article);
        assert.equal(mediaDescendants(parent, 'img').length, 0, 'ID-less references must not render an unrelated pool image');
        const figures = mediaDescendants(parent, 'figure');
        assert.equal(figures.length, 1);
        assert.deepEqual(mediaTags(figures[0]), ['p']);
        assert.equal(figures[0].textContent, 'Illustration unavailable.');
        assert.equal(figures[0].children[0].className, 'image-missing');
        assert.equal(mediaDescendants(parent, 'figcaption').length, 0);
      });
    }
  }
}

for (const type of ['ordered_list', 'unordered_list', 'callout']) {
  for (const refKey of ['asset_id', 'image_id']) for (const poolKey of ['id', 'image_id', 'asset_id']) {
    test(`article block media ${type} resolves ${refKey} through pool ${poolKey} and ignores inline URL`, () => {
      const h = articleMediaHarness();
      const parent = h.content(mediaArticle([{ type, items: ['Check'], text: 'Note', images: [{ [refKey]: 'mapped', url: 'https://provider.example/inline' }] }],
        [{ [poolKey]: 'mapped', url: mediaURL('authorized') }]));
      assert.deepEqual(mediaIDs(parent), ['mapped']);
      const img = mediaDescendants(parent, 'img')[0];
      assert.equal(img.src, 'https://cars.example/v1/catalog/images/v2.authorized');
      assert.equal(img.referrerPolicy, 'no-referrer');
    });
  }
  const unavailable = [
    ['missing mapping', { asset_id: 'absent', url: mediaURL('inline') }, []],
    ['absent ID', { url: mediaURL('inline') }, [{ id: 'unrelated', url: mediaURL('safe') }]],
    ['missing URL', { asset_id: 'a' }, [{ id: 'a' }]],
    ['unavailable asset', { asset_id: 'a' }, [{ id: 'a', unavailable: true }]],
    ...['https://provider.example/image.png', 'javascript:alert(1)', 'data:image/png;base64,YQ==',
      '/images/unsafe.png', '/v1/catalog/images/notopaque', '//provider.example/v1/catalog/images/v2.a',
      'https://user:pass@cars.example/v1/catalog/images/v2.a', '/v1/catalog/images/v2.a?token=x', '/v1/catalog/images/v2.a#x']
      .map(url => [url, { asset_id: 'a' }, [{ id: 'a', url }]]),
  ];
  for (const [name, ref, images] of unavailable) {
    test(`article block media ${type} renders unavailable figure for ${name}`, () => {
      const h = articleMediaHarness(), parent = h.content(mediaArticle([{ type, items: ['Check'], text: 'Note', images: [ref] }], images));
      const figures = mediaDescendants(parent, 'figure');
      assert.equal(figures.length, 1);
      assert.deepEqual(mediaTags(figures[0]), ['p']);
      assert.equal(figures[0].children[0].textContent, 'Illustration unavailable.');
      assert.equal(figures[0].children[0].className, 'image-missing');
      assert.deepEqual(mediaIDs(parent), []);
      assert.equal(mediaDescendants(parent, 'figcaption').length, 0);
    });
  }
  for (const [name, refAlt, poolAlt, expectedAlt, captions] of [
    ['reference alt', '<b>Pump orientation</b>', 'Pool alt', '<b>Pump orientation</b>', ['<b>Pump orientation</b>']],
    ['absent reference alt', undefined, 'Pool alt', 'Pool alt', []],
    ['empty reference alt', '', 'Pool alt', 'Pool alt', []],
    ['default alt', undefined, undefined, 'Article illustration', []],
  ]) {
    test(`article block media ${type} keeps exact ${name} and caption policy`, () => {
      const h = articleMediaHarness(), parent = h.content(mediaArticle([{ type, items: ['Check'], text: 'Note', images: [{ asset_id: 'a', alt: refAlt }] }],
        [{ id: 'a', url: mediaURL('a'), alt: poolAlt }]));
      assert.equal(mediaDescendants(parent, 'img').length, 1);
      assert.equal(mediaDescendants(parent, 'img')[0].alt, expectedAlt);
      const renderedCaptions = mediaDescendants(parent, 'figcaption');
      assert.deepEqual(renderedCaptions.map(n => n.textContent), captions);
      assert.ok(renderedCaptions.every(n => n.children.length === 0), 'HTML-like caption stays inert text');
    });
  }
}

test('ordered article lists retain authored starts and item numbers as native attributes', () => {
  const h = articleMediaHarness();
  const parent = h.content(mediaArticle([
    { type: 'ordered_list', start: 0, items: [
      'Remove',
      { text: 'Inspect', number: -3, blocks: [
        { type: 'ordered_list', start: -2147483648, items: [{ text: 'Nested', number: 2147483647 }] },
      ] },
      'Fit',
      { text: 'Zero', number: 0 },
      { text: 'Fraction', number: 1.5 },
      { text: 'Out of range', number: 2147483648 },
      { text: 'String ordinal', number: '9' },
    ] },
    { type: 'ordered_list', items: ['Legacy sequence'] },
    { type: 'unordered_list', start: 6, items: [{ text: 'Bullet', number: 8 }] },
    { type: 'ordered_list', start: 2147483648, items: ['Invalid start'] },
  ]));
  assert.deepEqual(mediaTags(parent), ['ol', 'ol', 'ul', 'ol']);
  const [ordered, legacy, bullet, invalid] = parent.children;
  assert.equal(ordered.getAttribute('start'), '0');
  assert.deepEqual(ordered.children.map(item => item.getAttribute('value')), [null, '-3', null, '0', null, null, null]);
  const [nested] = mediaDescendants(ordered, 'ol');
  assert.equal(nested.getAttribute('start'), '-2147483648');
  assert.equal(nested.children[0].getAttribute('value'), '2147483647');
  assert.deepEqual([legacy, bullet, invalid].map(list => list.getAttribute('start')), [null, null, null]);
  assert.deepEqual([legacy, bullet, invalid].map(list => list.children[0].getAttribute('value')), [null, null, null]);
  assert.equal(legacy.textContent, 'Legacy sequence');
});

test('article block media object list item retains its own image alongside block sibling', () => {
  const h = articleMediaHarness(), parent = h.content(mediaArticle([
    { type: 'ordered_list', items: [{ text: 'Check', images: [{ asset_id: 'item' }] }], images: [{ asset_id: 'block' }] },
  ], [{ id: 'block', url: mediaURL('block') }, { id: 'item', url: mediaURL('item') }]));
  assert.deepEqual(mediaTags(parent), ['ol', 'figure']);
  assert.deepEqual(mediaTags(parent.children[0]), ['li']);
  assert.deepEqual(mediaIDs(parent.children[0].children[0]), ['item']);
  assert.deepEqual(mediaIDs(parent), ['item', 'block']);
});
for (const images of [undefined, []]) {
  test(`article block media empty ${images ? 'array' : 'absent'} media preserves text and native structure`, () => {
    const h = articleMediaHarness(), parent = h.content(mediaArticle([
      { type: 'ordered_list', items: ['Check'], images },
      { type: 'unordered_list', items: ['Install'], images },
      { type: 'callout', text: 'Keep clear.', images },
    ], [{ id: 'unused', url: mediaURL('unused') }]));
    assert.deepEqual(mediaTags(parent), ['ol', 'ul', 'aside']);
    assert.deepEqual(mediaIDs(parent), []);
    const aside = parent.children[2];
    assert.deepEqual(mediaTags(aside), ['strong', 'div']);
    assert.deepEqual(mediaTags(aside.children[1]), ['span']);
    assert.equal(aside.children[0].textContent, 'Note');
    assert.equal(aside.children[1].textContent, 'Keep clear.');
  });
}

for (const [origin, state, retryable, note] of [
  ['source', 'fetching', false, true], ['source', 'failed', true, true],
  ['source', 'failed', false, false], ['source', 'needs_review', false, false], ['canonical', 'completed', false, false],
]) {
  test(`article block media actual renderArticle retains ${origin}/${state}/${retryable} UI policy`, () => {
    const h = articleMediaHarness();
    h.render(mediaArticle([{ type: 'paragraph', text: 'Old view' }], [], { view_revision: 'old' }));
    const article = mediaArticle([
      { type: 'ordered_list', items: ['Check'], images: [{ asset_id: 'list' }] },
      { type: 'callout', label: 'Warning', text: 'Keep clear.', images: [{ asset_id: 'callout' }] },
    ], [{ id: 'callout', url: mediaURL('callout') }, { id: 'list', url: mediaURL('list') }], {
      content_origin: origin, processing: { job_id: 'job', state, retryable }, complete: origin === 'canonical',
      source_review: { available: true, url: mediaSourceURL },
      steps: [{ instructions: ['Conflicting legacy step'], images: [{ id: 'legacy', url: mediaURL('legacy') }] }], body: 'Conflicting body',
    });
    const before = JSON.stringify(article), parent = h.render(article);
    assert.deepEqual(mediaIDs(parent), ['list', 'callout']);
    assert.deepEqual(mediaTags(parent), ['ol', 'figure', 'aside']);
    assert.equal(parent.textContent.includes('Conflicting'), false);
    assert.equal(h.nodes.get('article-kind').textContent, origin === 'canonical' ? 'Workshop article' : 'Stored source');
    assert.equal(h.nodes.get('article-note').hidden, !note);
    assert.equal(h.nodes.get('article-note').textContent, note ? 'An update is in progress.' : '');
    assert.equal(h.nodes.get('print').disabled, false);
    assert.equal(h.context.document.body.dataset.printable, 'true');
    assert.equal(h.nodes.get('source-review').hidden, false);
    assert.equal(h.nodes.get('source-review-link').href, mediaSourceURL);
    assert.equal(JSON.stringify(article), before, 'rendering cannot change origin or completion');
    h.render(mediaArticle([], [], { view_revision: 'unreadable' }));
    assert.equal(h.nodes.get('print').disabled, true);
    assert.equal(h.context.document.body.dataset.printable, 'false');
  });
}

test('unreviewed Workshop prose shows a source check notice in the paid reader', () => {
  const h = articleMediaHarness();
  h.render(mediaArticle([{ type: 'paragraph', text: 'Draft steps.' }], [], {
    content_origin: 'canonical', review_status: 'UNREVIEWED',
  }));
  assert.equal(h.nodes.get('article-note').hidden, false);
  assert.match(h.nodes.get('article-note').textContent, /has not been reviewed/);
  h.render(mediaArticle([{ type: 'paragraph', text: 'Reviewed steps.' }], [], {
    content_origin: 'canonical', review_status: 'APPROVED',
  }));
  assert.equal(h.nodes.get('article-note').hidden, true);
});

test('article block media actual loadSource renders retained shapes and rejects changed or invalid references', async () => {
  const calls = [];
  let response = { source: { url: mediaSourceURL, format: 'json' }, document: { blocks: [
    { type: 'ordered_list', items: ['Stored check'], images: [{ asset_id: 'list' }] },
    { type: 'callout', text: 'Stored caution', images: [{ asset_id: 'callout' }] },
  ] }, images: [{ id: 'list', url: mediaURL('list') }, { id: 'callout', url: mediaURL('callout') }] };
  const h = articleMediaHarness({ requestJSON: async (path, options) => { calls.push({ path, options }); return response; } });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Article' }]));
  await h.context.loadSource(mediaSourceURL, h.g);
  const frame = h.nodes.get('source-review-frame'), first = frame.children[0];
  assert.deepEqual(mediaTags(frame), ['ol', 'figure', 'aside']);
  assert.deepEqual(mediaIDs(frame), ['list', 'callout']);
  assert.equal(frame.hidden, false);
  assert.equal(h.nodes.get('source-review-meta').textContent, 'Stored source loaded.');
  assert.equal(h.nodes.get('article-reference').open, true);
  assert.equal(h.nodes.get('source-review-load').disabled, false);
  assert.equal(calls[0].path, mediaSourceURL);
  assert.equal(calls[0].options.signal, h.g.signal);
  assert.equal(calls[0].options.headers.Prefer, 'workshop-source-document');
  response = { ...response, source: { url: mediaSourceURL.replace('11111111-', '22222222-') } };
  await assert.rejects(h.context.loadSource(mediaSourceURL, h.g), /source reference changed/);
  assert.equal(frame.children[0], first);
  const count = calls.length;
  await assert.rejects(h.context.loadSource('https://provider.example/source', h.g), /reference is unavailable/);
  assert.equal(calls.length, count);
  assert.equal(frame.children[0], first);
  assert.equal(frame.hidden, false);
});

test('an inline source reference focuses the matching nested figure in the pinned copy', async () => {
  const figure = { type: 'image', block_id: 'article:figure:2', asset_id: 'drawing', evidence_ids: ['page-1'] };
  const blocks = [{ type: 'table', rows: [[{ blocks: [{ ...figure, block_id: 'article:figure:1' }, figure] }]] }];
  const images = [{ id: 'drawing', url: mediaURL('figure') }];
  let requested;
  const h = articleMediaHarness({ requestJSON: async path => {
    requested = path;
    return { source: { url: mediaSourceURL }, document: { blocks }, images };
  } });
  const content = h.render(mediaArticle([
    { type: 'paragraph', block_id: 'article:introduction', text: 'Rewritten introduction' },
    ...blocks,
  ], images, { content_origin: 'canonical', source_review: { available: true, url: mediaSourceURL } }));
  const links = mediaDescendants(content, 'a');
  assert.equal(links.length, 2);
  assert.equal(links[1].textContent, 'View source');
  links[1].dispatch('click', { preventDefault() {} });
  await new Promise(setImmediate);
  const [first, cited] = mediaDescendants(h.nodes.get('source-review-frame'), 'figure');
  assert.equal(requested, `${mediaSourceURL}&evidence_id=page-1`);
  assert.equal(first.focusCalls, undefined);
  assert.equal(cited.getAttribute('tabindex'), '-1');
  assert.equal(cited.focusCalls, 1);
  await h.context.loadSource(mediaSourceURL, h.g, 'block-missing-in-copy');
  assert.equal(h.nodes.get('source-review-title').focusCalls, 1);
});

test('Original loads the verified capture and existing article citations keep their pinned source', async () => {
  const originalURL = mediaSourceURL.replaceAll('11111111', '22222222');
  const requested = [];
  const pending = deferredAuthOperation();
  const cite = { type: 'paragraph', block_id: 'existing', evidence_ids: ['old-page'], text: 'Published service instructions' };
  const figure = { type: 'image', asset_id: 'recovered', alt: 'Recovered illustration' };
  const source = {
    source: { url: originalURL }, document: { blocks: [figure] },
    images: [{ id: 'recovered', url: mediaURL('verified-figure') }],
  };
  const h = articleMediaHarness({ async requestJSON(path) {
    requested.push(path);
    if (path !== originalURL) {
      return { source: { url: mediaSourceURL }, document: { blocks: [{ ...cite, text: 'Pinned source passage' }] } };
    }
    return requested.length === 3 ? pending.promise : source;
  } });
  h.context.viewGeneration = h.g;
  runInNewContext(appSection('function openOriginal(', 'function returnToArticleIndex()'), h.context);
  const article = mediaArticle([cite], [], {
    content_origin: 'canonical',
    source_review: { available: true, url: mediaSourceURL },
    original_source_review: { available: true, url: originalURL },
  });
  const content = h.render(article), frame = h.nodes.get('source-review-frame');
  const original = h.nodes.get('source-review-load');
  const open = h.nodes.get('open-original');
  const back = h.nodes.get('back-to-article');
  const sourceTitle = h.nodes.get('source-review-title');
  assert.equal(open.hidden, false);
  const link = h.nodes.get('source-review-link');
  assert.equal(link.href, originalURL);
  assert.equal(requested.length, 0);
  open.dispatch('click');
  assert.equal(open.disabled, true);
  assert.equal(original.disabled, true);
  assert.equal(open.textContent, 'Opening Original…');
  await new Promise(setImmediate);
  assert.deepEqual(mediaIDs(frame), ['recovered']);
  assert.equal(sourceTitle.focusCalls, 1);
  assert.equal(sourceTitle.lastScroll.behavior, 'instant');
  assert.equal(h.nodes.get('reader').dataset.readingOriginal, 'true');
  assert.equal(open.disabled, false);
  assert.equal(open.textContent, 'View Original');
  assert.equal(back.hidden, false);
  back.dispatch('click');
  assert.equal(h.nodes.get('reader').dataset.readingOriginal, undefined);
  assert.equal(h.nodes.get('article-title').focusCalls, 1);
  assert.equal(h.nodes.get('article-title').lastScroll.behavior, 'instant');
  assert.deepEqual(requested, [originalURL]);

  const [citation] = mediaDescendants(content, 'a');
  citation.dispatch('click', { preventDefault() {} });
  await new Promise(setImmediate);
  assert.deepEqual(requested, [originalURL, `${mediaSourceURL}&evidence_id=old-page`]);
  assert.equal(frame.textContent, 'Pinned source passage');
  assert.equal(frame.children[0].focusCalls, 1);

  original.dispatch('click');
  assert.equal(original.disabled, true);
  h.render({ ...article, original_source_review: undefined });
  pending.resolve(source);
  await new Promise(setImmediate);
  assert.equal(frame.hidden, true);
  assert.equal(frame.children.length, 0);
  assert.equal(back.hidden, true);
  assert.equal(link.href, mediaSourceURL);
  assert.equal(original.disabled, false);
  assert.equal(mediaDescendants(content, 'a')[0], citation);
});

test('the Original shortcut shows a failed read beside the button and can retry', async () => {
  const request = deferredAuthOperation();
  let reads = 0;
  const h = articleMediaHarness({ requestJSON(path) {
    assert.equal(path, mediaSourceURL);
    if (++reads === 1) return Promise.reject(new Error('Stored source could not be loaded.'));
    return request.promise;
  } });
  h.context.viewGeneration = h.g;
  runInNewContext(appSection('function openOriginal(', 'function returnToArticleIndex()'), h.context);
  h.render(mediaArticle([{ type: 'paragraph', text: 'Published' }], [], {
    source_review: { available: true, url: mediaSourceURL },
  }));
  const open = h.nodes.get('open-original'), error = h.nodes.get('original-error');
  open.dispatch('click');
  await new Promise(setImmediate);
  assert.equal(open.disabled, false);
  assert.equal(error.hidden, false);
  assert.equal(error.textContent, 'Stored source could not be loaded.');
  assert.equal(h.nodes.get('source-review-title').focusCalls, undefined);

  open.dispatch('click');
  assert.equal(error.hidden, true);
  request.resolve({ source: { url: mediaSourceURL }, document: { blocks: [{ type: 'paragraph', text: 'Original' }] } });
  await new Promise(setImmediate);
  assert.equal(h.nodes.get('source-review-frame').textContent, 'Original');
  assert.equal(h.nodes.get('source-review-title').focusCalls, 1);
});

test('overlapping citations share one pinned read, focus the latest block and recheck access on a new read', async () => {
  const pending = deferredAuthOperation(), calls = [];
  const blocks = [
    { type: 'paragraph', block_id: 'first', text: 'First source instruction' },
    { type: 'paragraph', block_id: 'latest', text: 'Selected source instruction' },
  ];
  const h = articleMediaHarness({ requestJSON(path, options) {
    calls.push({ path, options });
    if (calls.length === 1) return pending.promise;
    return Promise.reject(Object.assign(new Error('Source access revoked'), { status: 403 }));
  } });
  h.render(mediaArticle(blocks, [], { source_review: { available: true, url: mediaSourceURL } }));
  const firstPath = `${mediaSourceURL}&evidence_id=first`;
  const secondPath = `${mediaSourceURL}&source_locator=body%5B2%5D`;
  const first = h.context.loadSource(firstPath, h.g, 'first');
  const last = h.context.loadSource(secondPath, h.g, 'latest').catch(error => h.context.handleSourceError(error, h.g));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, firstPath);
  assert.equal(calls[0].options.signal, h.g.signal);
  assert.equal(h.nodes.get('source-review-load').disabled, true);
  pending.resolve({ source: { url: mediaSourceURL }, document: { blocks } });
  await Promise.all([first, last]);
  const frame = h.nodes.get('source-review-frame');
  assert.equal(frame.children[0].focusCalls, undefined);
  assert.equal(frame.children[1].focusCalls, 1);
  assert.equal(h.nodes.get('source-review-load').disabled, false);

  await h.context.loadSource(secondPath, h.g, 'latest').catch(error => h.context.handleSourceError(error, h.g));
  assert.equal(calls.length, 2);
  assert.equal(calls[1].path, secondPath);
  assert.equal(frame.hidden, true);
  assert.deepEqual(h.shows, ['welcome']);
});

test('fresh citation authorization keeps pending figures and focuses the new exact block of the same source', async () => {
  const blocks = ['first', 'last'].map(id => ({
    type: 'image', block_id: id, asset_id: id, caption: `Stored ${id}`,
  }));
  const calls = [];
  let changed = false;
  const h = articleMediaHarness({
    session: { state: { authenticated: true, mode: 'firebase' } },
    async requestJSON(path, options) {
      calls.push({ path, signal: options.signal });
      return {
        source: { url: mediaSourceURL }, view_revision: 'same-retained-projection', document: { blocks },
        images: blocks.map(({ asset_id: id }) => ({
          id,
          ...(!changed || id === 'first' ? { url: mediaURL(`${id}-${calls.length}`) } : {}),
        })),
      };
    },
  });
  h.render(mediaArticle(blocks, [], {
    content_origin: 'canonical', source_review: { available: true, url: mediaSourceURL },
  }));
  const firstPath = `${mediaSourceURL}&evidence_id=first`;
  const lastPath = `${mediaSourceURL}&evidence_id=last`;
  await h.context.loadSource(firstPath, h.g, 'first');
  const frame = h.nodes.get('source-review-frame');
  const [first, last] = mediaDescendants(frame, 'figure');
  const [firstImage] = mediaDescendants(first, 'img');
  const displayed = h.context.displayedSourceRevision;
  await h.context.loadSource(lastPath, h.g, 'last');
  assert.deepEqual(calls.map(call => call.path), [firstPath, lastPath]);
  assert.ok(calls.every(call => call.signal === h.g.signal));
  assert.equal(frame.children[0], first);
  assert.equal(last.focusCalls, 1);
  assert.equal(firstImage.src, 'https://cars.example/v1/catalog/images/v2.first-1');
  assert.equal(h.context.displayedSourceRevision, displayed);

  changed = true;
  await h.context.loadSource(lastPath, h.g, 'last');
  assert.notEqual(frame.children[0], first);
  assert.equal(frame.children[1].focusCalls, 1);
  assert.match(frame.children[1].textContent, /Illustration unavailable/);
});

for (const type of ['ordered_list', 'unordered_list', 'callout']) {
  test(`article block media ${type} source evidence handler and image error obey current generation`, async () => {
    const loads = [], renewals = [];
    const h = articleMediaHarness();
    h.context.loadSource = async (url, g) => loads.push({ url, g });
    h.context.renewMedia = (g, img) => renewals.push({ g, img });
    const parent = h.content(mediaArticle([
      { type, items: ['Check'], text: 'Careful', images: [{ asset_id: 'a' }], evidence_ids: ['e-7'], source_locator: 'body[3]' },
      { type: 'paragraph', text: 'After' },
    ], [{ id: 'a', url: mediaURL('a') }], { source_review: { url: mediaSourceURL } }));
    assert.deepEqual(mediaTags(parent), type === 'callout' ? ['aside', 'a', 'p'] : [type === 'ordered_list' ? 'ol' : 'ul', 'figure', 'a', 'p']);
    const link = mediaDescendants(parent, 'a')[0], img = mediaDescendants(parent, 'img')[0];
    assert.ok(img, 'new block figure must expose the existing error handler');
    let prevented = 0;
    link.dispatch('click', { preventDefault() { prevented++; } }); img.dispatch('error');
    await Promise.resolve();
    assert.equal(loads.length, 1);
    assert.equal(loads[0].url, mediaSourceURL + '&evidence_id=e-7&source_locator=body%5B3%5D');
    assert.equal(loads[0].g, h.g);
    assert.equal(renewals.length, 1); assert.equal(renewals[0].img, img); assert.equal(renewals[0].g, h.g);
    h.navigation.next();
    link.dispatch('click', { preventDefault() { prevented++; } }); img.dispatch('error');
    assert.equal(prevented, 2); assert.equal(loads.length, 1); assert.equal(renewals.length, 1);
  });
}

function renewalFixture() {
  return mediaArticle([
    { type: 'ordered_list', items: ['Check'], images: [{ asset_id: 'list' }] },
    { type: 'callout', text: 'Careful', images: [{ asset_id: 'callout' }] },
  ], [{ id: 'list', url: mediaURL('old-list') }, { id: 'callout', url: mediaURL('old-callout') }]);
}
const renewedArticle = () => ({ data: { article: { ...renewalFixture(), images: [
  { id: 'list', url: mediaURL('new-list') }, { id: 'callout', url: mediaURL('new-callout') },
] } } });

test('unchanged article polls keep decoded and in-flight figures on their current requests', () => {
  const h = articleMediaHarness();
  const parent = h.render(renewalFixture());
  const [loaded, pending] = mediaDescendants(parent, 'img');
  Object.assign(loaded, { complete: true, naturalWidth: 24 });
  Object.assign(pending, { complete: false, naturalWidth: 0 });
  const originals = [loaded.src, pending.src];
  const incoming = renewedArticle().data.article;
  h.render({ ...incoming, processing: { job_id: 'workshop-reader', state: 'rewriting' } });
  assert.deepEqual(mediaDescendants(parent, 'img'), [loaded, pending]);
  assert.deepEqual([loaded.src, pending.src], originals);
  assert.deepEqual([loaded.dataset.replacement, pending.dataset.replacement], [undefined, undefined]);
  assert.match(h.nodes.get('article-note').textContent, /Preparing the Workshop rewrite/);

  h.render({ ...incoming, view_revision: 'published-view' });
  const [nextLoaded, nextPending] = mediaDescendants(parent, 'img');
  assert.notEqual(nextLoaded, loaded);
  assert.notEqual(nextPending, pending);
  assert.deepEqual([nextLoaded.src, nextPending.src], [
    'https://cars.example/v1/catalog/images/v2.new-list',
    'https://cars.example/v1/catalog/images/v2.new-callout',
  ]);
});

test('article block media actual renewal shares one request and reconciles both shapes once per revision', async () => {
  const pending = deferredAuthOperation(), calls = [];
  const h = articleMediaHarness({ requestArticleJSON: (path, options) => { calls.push({ path, options }); return pending.promise; } });
  const parent = h.render(renewalFixture()), images = mediaDescendants(parent, 'img');
  assert.equal(images.length, 2);
  const renewal = Promise.all(images.map(img => h.context.renewMedia(h.g, img)));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/v1/catalog/vehicles/v/articles/a?region=US'); assert.equal(calls[0].options.signal, h.g.signal);
  pending.resolve(renewedArticle()); await renewal;
  assert.deepEqual(mediaDescendants(parent, 'img'), images, 'stable revision retains image nodes');
  assert.deepEqual(images.map(n => n.src), ['https://cars.example/v1/catalog/images/v2.new-list', 'https://cars.example/v1/catalog/images/v2.new-callout']);
  assert.deepEqual(images.map(n => n.dataset.replacement), ['1', '1']);
  images[0].dispatch('error'); images[1].dispatch('error');
  assert.equal(calls.length, 1);
  assert.deepEqual(mediaIDs(parent), []);
  assert.equal(mediaDescendants(parent, 'figure')[0].textContent, 'Illustration unavailable. Refresh this article to try again.');
});

for (const race of ['same revision metadata', 'canonical publication', 'withdrawal', 'detail not found']) {
  test(`concurrent article detail responses preserve ${race}`, async () => {
    const { requestArticleJSON } = await import('./workshop/catalog.mjs');
    const { readArticle } = await import('./workshop/article-read.mjs');
    const id = '33333333-3333-4333-8333-333333333333';
    const vehicle = { id: '11111111-1111-4111-8111-111111111111', region: 'US' };
    const detail = `/v1/catalog/vehicles/${vehicle.id}/articles/${id}`;
    const source = mediaArticle([
      { type: 'paragraph', text: 'Synthetic retained procedure' },
      { type: 'image', asset_id: 'figure' },
    ], [{ id: 'figure', url: mediaURL('fixture-expired') }], {
      id, view_revision: 'fixture-source-view',
      processing: { job_id: 'fixture-job', state: 'rewriting' },
    });
    const needsReview = { ...source, processing: { job_id: 'fixture-job', state: 'needs_review' } };
    const renewal = { ...source, images: [{ id: 'figure', url: mediaURL('fixture-fresh') }] };
    const published = { ...renewal, view_revision: 'fixture-canonical-view', content_origin: 'canonical',
      document: { blocks: [{ type: 'paragraph', text: 'Synthetic published procedure' }, { type: 'image', asset_id: 'figure' }] },
      processing: { job_id: 'fixture-job', state: 'completed' } };
    const wire = article => new Response(JSON.stringify({ version: 'v1', configuration: vehicle, article }));
    const firstWait = deferredAuthOperation(), allowPoll = deferredAuthOperation();
    const secondStarted = deferredAuthOperation(), older = deferredAuthOperation();
    const requests = [];
    let clock = 0;
    const h = articleMediaHarness({
      session: { state: { authenticated: true, mode: 'firebase', csrf: 'fixture' } },
      vehicle, articlePath: () => detail, stage() {},
      requestArticleJSON: (path, options) => requestArticleJSON(path, {
        ...options, fetcher: async (_url, { method }) => {
          requests.push([method, path]);
          assert.equal(options.signal, h.g.signal);
          if (requests.length === 1) return wire(source);
          if (requests.length === 2) {
            secondStarted.resolve();
            return older.promise;
          }
          if (requests.length === 3) return wire(race === 'same revision metadata' ? needsReview : published);
          assert.equal(race, 'canonical publication');
          assert.equal(requests.length, 4);
          return wire(needsReview);
        },
      }),
      readArticle: (read, options) => readArticle(read, {
        ...options, now: () => clock,
        async wait(ms) { clock += ms; firstWait.resolve(); await allowPoll.promise; },
      }),
    });
    runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
    const opening = h.context.loadArticle(id, h.g);
    await firstWait.promise;
    const body = h.nodes.get('article-content');
    const failed = mediaDescendants(body, 'img')[0];
    const expected = [['POST', detail + '/prepare?region=US'], ['GET', detail + '?region=US'], ['GET', detail + '?region=US']];
    if (race === 'canonical publication' || race === 'detail not found') {
      allowPoll.resolve();
      await secondStarted.promise;
      await h.context.renewMedia(h.g, failed);
      assert.equal(body.textContent, 'Synthetic published procedure');
      if (race === 'detail not found') {
        older.resolve(new Response(JSON.stringify({ error: { code: 'CATALOG_NOT_FOUND' } }), { status: 404 }));
        await assert.rejects(opening, { status: 404, code: 'CATALOG_NOT_FOUND' });
        assert.equal(body.textContent, '');
        assert.equal(h.nodes.get('print').disabled, true);
        assert.equal(h.nodes.get('article-title').textContent, 'Article unavailable');
      } else {
        older.resolve(wire(needsReview));
        await opening;
        assert.equal(body.textContent, 'Synthetic published procedure');
        assert.equal(h.context.currentArticle.processing.state, 'completed');
        assert.equal(h.statuses.at(-1).message, 'Article ready.');
        assert.deepEqual(requests, expected);

        await h.context.renewMedia(h.g, mediaDescendants(body, 'img')[0]);
        assert.equal(body.textContent, 'Synthetic retained procedure');
        assert.equal(h.context.currentArticle.processing.state, 'needs_review');
        expected.push(['GET', detail + '?region=US']);
      }
    } else {
      const refreshing = h.context.renewMedia(h.g, failed);
      await secondStarted.promise;
      allowPoll.resolve();
      await opening;
      if (race === 'same revision metadata') {
        assert.equal(h.context.currentArticle.processing.state, 'needs_review');
        older.resolve(wire(renewal));
        await refreshing;
        assert.equal(h.context.currentArticle.processing.state, 'needs_review');
        assert.equal(h.nodes.get('article-note').textContent, '');
        assert.match(h.statuses.at(-1).message, /preparation needs review/);
        assert.equal(failed.src, 'https://cars.example/v1/catalog/images/v2.fixture-fresh');
      } else {
        assert.equal(body.textContent, 'Synthetic published procedure');
        older.resolve(new Response(JSON.stringify({ error: { code: 'CATALOG_WITHDRAWN' } }), { status: 410 }));
        await refreshing;
        assert.equal(body.textContent, '');
        assert.equal(h.nodes.get('print').disabled, true);
        assert.equal(h.g.current(), false);
        assert.equal(h.shows.at(-1), 'welcome');
      }
    }
    assert.deepEqual(requests, expected);
  });
}

test('a superseded article response still contributes its retry delay to an active read', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const current = { status: 200, data: { article: mediaArticle([], [], {
    processing: { job_id: 'fixture-job', state: 'rewriting' },
  }) } };
  const older = { ...current, retryAfterSeconds: 4 };
  const finished = { data: { article: mediaArticle([{ type: 'paragraph', text: 'Ready' }]) } };
  const responses = [older, finished], updates = [], waits = [];
  let clock = 0;
  await readArticle(async () => responses.shift(), {
    now: () => clock,
    async wait(ms) { waits.push(ms); clock += ms; },
    selectResponse: response => response === older ? current : response,
    onUpdate: response => updates.push(response),
  });
  assert.deepEqual(updates, [current, finished]);
  assert.deepEqual(waits, [4000]);
});

test('a figure that fails later reuses the refreshed article links', async () => {
  let requests = 0;
  const h = articleMediaHarness({ requestArticleJSON: async () => { requests++; return renewedArticle(); } });
  const [first, later] = mediaDescendants(h.render(renewalFixture()), 'img');
  await h.context.renewMedia(h.g, first);
  assert.equal(first.src, 'https://cars.example/v1/catalog/images/v2.new-list');
  assert.equal(later.src, 'https://cars.example/v1/catalog/images/v2.old-callout');
  await h.context.renewMedia(h.g, later);
  assert.equal(later.src, 'https://cars.example/v1/catalog/images/v2.new-callout');
  assert.equal(later.isConnected, true);
  assert.equal(requests, 1);
});

for (const stored of [false, true]) {
  test(`a delayed ${stored ? 'Original' : 'article'} figure renews expired media with a fresh scoped read`, async () => {
    let now = 1000, reads = 0;
    let openedSource = false;
    function nextImages() {
      const revision = ++reads;
      return ['list', 'callout'].map(id => ({ id, url: mediaURL(`${id}-${revision}`) }));
    }
    const article = renewalFixture();
    const h = articleMediaHarness({
      Date: { now: () => now },
      requestArticleJSON: async () => ({ status: 200, data: { article: { ...article, images: nextImages() } } }),
      requestJSON: async () => {
        const images = openedSource ? nextImages() : article.images;
        openedSource = true;
        return { source: { url: mediaSourceURL }, document: article.document, images };
      },
    });
    const publisher = h.render(article);
    if (stored) await h.context.loadSource(mediaSourceURL, h.g);
    const body = stored ? h.nodes.get('source-review-frame') : publisher;
    const [first, late] = mediaDescendants(body, 'img');
    await h.context.renewMedia(h.g, first);
    assert.ok(first.src.endsWith('list-1'));
    now += 301_000;
    await h.context.renewMedia(h.g, late);
    assert.equal(reads, 2);
    assert.ok(late.src.endsWith('callout-2'));
    assert.ok(late.isConnected);
  });
}

test('a pinned source figure refreshes only the selected source after article media have refreshed', async () => {
  let articleRequests = 0, sourceRequests = 0;
  const h = articleMediaHarness({
    requestArticleJSON: async () => { articleRequests++; return renewedArticle(); },
    requestJSON: async () => ({
      source: { url: mediaSourceURL }, document: renewalFixture().document,
      images: [{ id: 'list', url: mediaURL(++sourceRequests === 1 ? 'old-stored' : 'new-stored') }],
    }),
  });
  const [first] = mediaDescendants(h.render(renewalFixture()), 'img');
  await h.context.renewMedia(h.g, first);
  await h.context.loadSource(mediaSourceURL, h.g);
  const [stored] = mediaDescendants(h.nodes.get('source-review-frame'), 'img');
  await h.context.renewMedia(h.g, stored);
  assert.equal(stored.src, 'https://cars.example/v1/catalog/images/v2.new-stored');
  assert.equal(stored.isConnected, true);
  assert.equal(articleRequests, 1);
  assert.equal(sourceRequests, 2);
});
test('same-navigation publication prevents an outstanding media renewal from restoring the old revision', async () => {
  const pending = deferredAuthOperation();
  const h = articleMediaHarness({ requestArticleJSON: () => pending.promise });
  const parent = h.render(renewalFixture());
  const first = mediaDescendants(parent, 'img')[0];
  const renewal = h.context.renewMedia(h.g, first);
  const published = { ...renewedArticle().data.article, content_origin: 'canonical', view_revision: 'publication' };
  h.render(published);
  const next = mediaDescendants(parent, 'img')[0];
  assert.notEqual(next, first);
  pending.resolve({ data: { article: renewalFixture() } });
  await renewal;
  assert.equal(h.context.currentArticle.view_revision, 'publication');
  assert.equal(mediaDescendants(parent, 'img')[0], next);
  assert.equal(h.context.articleImageRefresh, null);
});

test('media renewal replaces failed figures within their scoped responses only', async () => {
  const pending = deferredAuthOperation(), calls = [];
  const h = articleMediaHarness({
    requestArticleJSON: () => pending.promise,
    requestJSON: async url => {
      calls.push(url);
      return { source: { url: mediaSourceURL }, images: [
        { id: 'list', url: mediaURL('new-stored-list') },
        { id: 'callout', url: mediaURL('new-stored-callout') },
      ] };
    },
  });
  const article = h.render(renewalFixture());
  const frame = h.nodes.get('source-review-frame');
  const [failedArticle, healthyArticle] = mediaDescendants(article, 'img');
  h.context.renderBlocks(frame, renewalFixture().document.blocks, h.context.indexRenderableImages([
    { id: 'list', url: mediaURL('old-stored-list') },
    { id: 'callout', url: mediaURL('old-stored-callout') },
  ]), null, h.g);
  const [healthySource, failedSource] = mediaDescendants(frame, 'img');
  h.context.sourceURL = 'https://cars.example' + mediaSourceURL;
  const renewal = Promise.all([h.context.renewMedia(h.g, failedArticle), h.context.renewMedia(h.g, failedSource)]);
  assert.deepEqual(calls, ['https://cars.example' + mediaSourceURL], 'pinned refresh starts while article response is pending');
  pending.resolve(renewedArticle());
  await renewal;
  assert.deepEqual(calls, ['https://cars.example' + mediaSourceURL]);
  assert.deepEqual([failedArticle, healthyArticle, healthySource, failedSource].map(img => img.src), [
    'https://cars.example/v1/catalog/images/v2.new-list',
    'https://cars.example/v1/catalog/images/v2.old-callout',
    'https://cars.example/v1/catalog/images/v2.old-stored-list',
    'https://cars.example/v1/catalog/images/v2.new-stored-callout',
  ]);
  assert.deepEqual([failedArticle, healthyArticle, healthySource, failedSource].map(img => img.dataset.replacement),
    ['1', undefined, undefined, '1']);
});

for (const changed of [false, true]) {
  test(`article block media actual renewal ${changed ? 'rejects changed' : 'reconciles matching'} stored-source revision`, async () => {
    const calls = [];
    const h = articleMediaHarness({ requestArticleJSON: async () => renewedArticle(), requestJSON: async (url, options) => {
      calls.push({ url, options });
      return { source: { url: changed ? mediaSourceURL.replace('11111111-', '22222222-') : mediaSourceURL },
        images: [{ id: 'stored', url: mediaURL('new-stored') }] };
    } });
    h.render(renewalFixture());
    const frame = h.nodes.get('source-review-frame');
    h.context.renderBlocks(frame, [{ type: 'callout', text: 'Stored', images: [{ asset_id: 'stored' }] }],
      h.context.indexRenderableImages([{ id: 'stored', url: mediaURL('old-stored') }]), null, h.g);
    frame.hidden = false; h.context.sourceURL = 'https://cars.example' + mediaSourceURL;
    const image = mediaDescendants(frame, 'img')[0];
    assert.ok(image, 'stored-source callout must contain a retained figure');
    await h.context.renewMedia(h.g, image);
    assert.equal(calls.length, 1); assert.equal(calls[0].url, 'https://cars.example' + mediaSourceURL); assert.equal(calls[0].options.signal, h.g.signal);
    assert.equal(calls[0].options.headers.Prefer, 'workshop-source-document');
    if (changed) {
      assert.deepEqual(mediaIDs(frame), []);
      assert.equal(frame.textContent, 'NoteStoredIllustration unavailable. Refresh this article to try again.');
    } else {
      assert.equal(mediaDescendants(frame, 'img')[0], image);
      assert.equal(image.src, 'https://cars.example/v1/catalog/images/v2.new-stored');
      assert.equal(image.dataset.replacement, '1');
    }
  });
}
for (const status of [401, 403, 410]) {
  test(`article block media actual renewal ${status} invalidates protected content and generation`, async () => {
    const h = articleMediaHarness({ requestArticleJSON: async () => { throw Object.assign(new Error('Access unavailable'), { status }); } });
    h.render(renewalFixture());
    for (const id of ['articles', 'source-review-frame', 'reference-data', 'library-items']) h.nodes.get(id).textContent = 'Protected';
    h.nodes.get('source-review-link').href = mediaSourceURL;
    const image = mediaDescendants(h.nodes.get('article-content'), 'img')[0];
    assert.ok(image); await h.context.renewMedia(h.g, image);
    assert.equal(h.g.current(), false);
    assert.equal(h.g.signal.aborted, true);
    for (const id of ['articles', 'article-content', 'source-review-frame', 'reference-data', 'library-items']) assert.equal(h.nodes.get(id).textContent, '', id);
    assert.equal(h.context.currentArticle, null); assert.equal(h.context.sourceImageRefresh, null); assert.equal(h.context.sourceURL, '');
    assert.equal(h.nodes.get('source-review-link').href, undefined);
    assert.equal(h.nodes.get('source-review-frame').hidden, true); assert.equal(h.nodes.get('print').disabled, true);
    assert.equal(h.context.document.body.dataset.printable, 'false');
    assert.deepEqual(h.shows, ['welcome']); assert.equal(h.statuses[0].message, 'Access unavailable'); assert.equal(h.statuses[0].options.error, true);
  });
}
for (const outcome of ['resolve', 'reject']) {
  test(`article block media actual renewal stale ${outcome} preserves newly selected content`, async () => {
    const pending = deferredAuthOperation(); let sourceCalls = 0;
    const h = articleMediaHarness({ requestArticleJSON: () => pending.promise, requestJSON: () => { sourceCalls++; assert.fail('stale renewal cannot fetch source'); } });
    h.render(renewalFixture());
    h.context.sourceURL = mediaSourceURL;
    const image = mediaDescendants(h.nodes.get('article-content'), 'img')[0];
    assert.ok(image); const renewal = h.context.renewMedia(h.g, image);
    h.context.invalidate(); const next = h.navigation.next();
    h.context.renderArticle(mediaArticle([{ type: 'paragraph', text: 'New selected article' }], [], { id: 'b', view_revision: 'view-b' }), next);
    h.nodes.get('source-review-frame').textContent = 'New source';
    if (outcome === 'resolve') pending.resolve(renewedArticle());
    else pending.reject(Object.assign(new Error('Stale denial'), { status: 403 }));
    await renewal;
    assert.equal(h.nodes.get('article-content').textContent, 'New selected article');
    assert.equal(h.nodes.get('source-review-frame').textContent, 'New source');
    assert.equal(h.context.currentArticle.id, 'b'); assert.equal(next.current(), true);
    assert.equal(sourceCalls, 0); assert.deepEqual(h.shows, []); assert.deepEqual(h.statuses, []);
  });
}

function selectorOptionsHarness(response) {
 const nodes = new Map();
 const $ = id => {
   if (!nodes.has(id)) nodes.set(id, {
     value:'', disabled:false, hidden:true, textContent:'', dataset:{}, options:[],
     append(...choices) { this.options.push(...choices); },
   });
   return nodes.get(id);
 };
 $('workshop-catalog-module').dataset.publicSelectors = 'true';
 class PickerOption {
   constructor(text, value) { Object.assign(this, {text, value}); }
 }
 const statuses=[], displayed=[];
 const requests=[], waits=[];
 let clock = 0;
 const context={ $, rows:{}, Option:PickerOption, AbortController, navigation:new NavigationGeneration(), document:{body:{dataset:{}}}, retryAction:null, currentOrder:'', paidOrder:'', stage(){}, selectorPath:()=>'/choices',
  async requestJSON(path, options) {
    requests.push(path);
    if (response instanceof Error) throw response;
    return typeof response === 'function' ? response(path, options) : response;
  },
  session:{ state:{mode:'firebase'} },
  readCollection:(read,options)=>readCollection(read,{
    ...options, attempts:options.attempts ?? 3, now:() => clock,
    async wait(ms) { waits.push(ms); clock += ms; },
  }),
  populate(name,items,desired='') {
    const select = $(name);
    const selected = desired || select.value;
    context.rows[name] = items;
    displayed.push(items);
    select.disabled = !items.length;
    select.options = items.map(item => context.pickerOption(context.pickerChoice(name, item)));
    select.value = select.options.some(option => option.value === selected && !option.disabled) ? selected : '';
  },
  recordStatus:(text,options={})=>statuses.push({text,...options}), restoreRoute(){},
 };
 runInNewContext(appSection('function status(', 'function stage(')+appSection('async function operation(', 'function updateURL(')+
  appSection('function pickerChoice(', 'function selectorPath(')+appSection('function canCachePublicSelectors(', 'function renderPurchase(')+
  'const actualStatus = status; status = (text, options = {}) => { recordStatus(text, options); actualStatus(text, options); };',context);
 return {context,$,statuses,displayed,requests,waits,load:(desired='',current,initial=null,name='configuration')=>context.operation(g=>context.loadOptions(name,current?{...g,current}:g,desired,initial),()=>context.restoreRoute())};
}

test('a delayed unverified engine variant appends disabled and keeps the exact selected option', async () => {
  const first = { id: 'engine-a', engine: '6.0', complete: true };
  const sibling = {
    ...first, id: 'engine-b', engine_variant: 'CNG', engine_variant_market_unverified: true,
  };
  const pending = deferredAuthOperation();
  const h = selectorOptionsHarness(path => path.includes('stored_only') ? pending.promise
    : { items: [first], complete: false });
  await h.load();
  const select = h.$('configuration');
  select.value = first.id;
  const option = select.options[0];
  const statuses = h.statuses.length;
  const reopening = h.context.refreshPicker('configuration');
  await h.context.refreshPicker('configuration');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
  assert.equal(select.disabled, false);
  assert.equal(select.value, first.id);
  assert.deepEqual(select.options, [option]);
  pending.resolve({ items: [first, sibling], complete: true });
  await reopening;
  assert.deepEqual(select.options.map(choice => choice.value), [first.id, sibling.id]);
  assert.equal(select.options[0], option);
  assert.equal(select.options[1].text, '6.0 L CNG · market unverified');
  assert.equal(select.options[1].disabled, true);
  assert.equal(select.value, first.id);
  assert.equal(h.statuses.length, statuses);
  await h.context.refreshPicker('configuration');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
});

test('a picker refresh enables the same engine variant when its market is verified', async () => {
  const first = { id: 'engine-a', engine: '6.0', complete: true };
  const variant = { ...first, id: 'engine-b', engine_variant: 'CNG' };
  const h = selectorOptionsHarness(path => path.includes('stored_only')
    ? { items: [first, variant], complete: true }
    : { items: [first, { ...variant, engine_variant_market_unverified: true }], complete: false });
  await h.load();
  const select = h.$('configuration');
  select.value = first.id;
  const originalOption = select.options[1];

  assert.equal(originalOption.text, '6.0 L CNG · market unverified');
  await h.context.refreshPicker('configuration');

  assert.equal(select.value, first.id);
  assert.equal(select.options.length, 2);
  assert.equal(select.options[1], originalOption);
  assert.equal(originalOption.text, '6.0 L CNG');
  assert.equal(originalOption.disabled, false);
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
});

test('an unverified base choice stays visible and cannot replace the selected exact engine', async () => {
  const exact = { id: 'exact-engine', engine: '3.5', complete: true };
  const base = { id: 'base', complete: true };
  const unresolved = { ...base, configuration_unresolved: true };
  const h = selectorOptionsHarness(path => path.includes('stored_only')
    ? { items: [exact, base], complete: true }
    : { items: [exact, unresolved], complete: false });
  await h.load(exact.id);
  const select = h.$('configuration');
  const option = select.options[1];
  assert.equal(option.text, 'Base configuration · unverified');
  assert.equal(option.disabled, true);
  assert.equal(select.value, exact.id);

  await h.context.refreshPicker('configuration');
  assert.equal(select.value, exact.id);
  assert.equal(select.options[1], option);
  assert.equal(option.text, 'Base configuration');
  assert.equal(option.disabled, false);
});

test('an unresolved saved base choice displays the missing evidence and remains unselected', async () => {
  const unresolved = { id: 'base', configuration_unresolved: true, complete: true };
  const h = selectorOptionsHarness({ items: [unresolved], complete: true });
  await h.load(unresolved.id);
  assert.equal(h.$('configuration').value, '');
  assert.equal(h.$('configuration').options[0].disabled, true);
  assert.match(h.statuses.at(-1).text, /saved configuration is unverified/);
});

test('raw engine choices render while one discovery request looks for a verified option', async () => {
  const unresolved = { id: 'base', configuration_unresolved: true, complete: true };
  const verified = { id: 'exact', engine: '2.0', complete: true };
  const preview = { items: [unresolved], complete: false, discovery_instance: 'scheduler' };
  let h;
  h = selectorOptionsHarness(path => {
    const current = h.$('configuration').options;
    assert.equal(current.length, 1);
    assert.equal(current[0].text, 'Base configuration · unverified');
    assert.equal(current[0].disabled, true);
    if (path.includes('stored_only')) return { items: [unresolved, verified], complete: true };
    return { ...preview, hydrating: true };
  });
  await h.load('', undefined, Promise.resolve(preview));
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, [350]);
  assert.ok(h.statuses.some(entry => entry.text === 'Checking sources for a verified engine or trim…'));
  assert.ok(!h.statuses.some(entry => entry.text.includes('You can choose an available option')));
  assert.equal(h.$('configuration').options[1].disabled, false);
});

test('a completed empty provider check keeps a raw-only picker visible without retrying', async () => {
  const unresolved = { id: 'base', configuration_unresolved: true, complete: true };
  const h = selectorOptionsHarness(path => ({
    items: [unresolved], complete: path.includes('stored_only'), hydrating: !path.includes('stored_only'),
  }));
  await h.load();
  await h.context.refreshPicker('configuration');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
  assert.equal(h.$('configuration').options[0].disabled, true);
  assert.match(h.statuses.at(-1).text, /No verified engine or trim is available/);
});

test('an engine reopen follows existing discovery through an idle peer using stored reads', async () => {
  const first = { id: 'engine-a', engine: '3.5', complete: true };
  const second = { id: 'engine-b', engine: '2.7', complete: true };
  const partial = { items: [first], complete: false, discovery_instance: 'scheduler', discovering: true };
  const reads = [
    partial,
    { items: [first], complete: false, discovery_instance: 'peer' },
    { items: [first, second], complete: true },
  ];
  const h = selectorOptionsHarness(() => reads.shift());
  await h.load(first.id);
  await h.context.refreshPicker('configuration');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, [4000]);
  assert.equal(h.$('configuration').value, first.id);
  assert.equal(h.$('configuration').options[1].value, second.id);
});

test('a stale reopen is canceled on parent change and never enters the new scope', async () => {
  const first = { id: 'engine-a', engine: '3.5' };
  const pending = deferredAuthOperation();
  let staleSignal;
  let path = '/old-parent';
  const h = selectorOptionsHarness((readPath, { signal }) => {
    if (readPath === '/old-parent?stored_only=1') {
      staleSignal = signal;
      return pending.promise;
    }
    return readPath === '/old-parent' ? { items: [first], complete: false }
      : { items: [{ id: 'current', engine: '5.0' }], complete: true };
  });
  h.context.selectorPath = () => path;
  await h.load();
  const opening = h.context.refreshPicker('configuration');
  h.context.cancelPickerRefreshes();
  path = '/new-parent';
  await h.load();
  pending.resolve({ items: [first, { id: 'stale', engine: '2.7' }], complete: true });
  await opening;
  assert.equal(staleSignal.aborted, true);
  assert.deepEqual(h.$('configuration').options.map(choice => choice.value), ['current']);
  await h.context.refreshPicker('configuration');
  assert.deepEqual(h.requests, ['/old-parent', '/old-parent?stored_only=1', '/new-parent']);
});

test('an incomplete model reopen reads storage once when hydration only describes coverage', async () => {
  const first = { id: 'original', name: 'Original' };
  const sibling = { id: 'new', name: 'New' };
  const h = selectorOptionsHarness(path => path.includes('stored_only')
    ? { items: [first, sibling], complete: false, hydrating: true }
    : { items: [first], complete: false, hydrating: true });
  await h.load('', null, null, 'model');
  assert.deepEqual(h.requests, ['/choices']);
  assert.equal(h.statuses.at(-1).text, 'Choose your vehicle to continue.');
  await h.context.refreshPicker('model');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, []);
  assert.deepEqual(h.$('model').options.map(choice => choice.value), [first.id, sibling.id]);
});

test('reselecting a make or model scope renders its incomplete choices before stored refresh finishes', async () => {
  for (const name of ['make', 'model']) {
    const first = { id: 'first' };
    const sibling = { id: 'sibling' };
    const original = { items: [first], complete: false, hydrating: true };
    const pending = deferredAuthOperation();
    const h = selectorOptionsHarness(path => path.includes('stored_only') ? pending.promise : original);
    await h.load('', null, null, name);
    assert.deepEqual(h.requests, ['/choices']);

    await h.load('', null, null, name);
    const select = h.$(name);
    select.value = first.id;
    const option = select.options[0];
    assert.equal(select.disabled, false);
    assert.equal(h.context.pickerStates.get(name).incomplete, true);
    await h.context.refreshPicker(name);
    assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);

    pending.resolve({ ...original, items: [first, sibling] });
    await new Promise(setImmediate);
    assert.equal(select.value, first.id);
    assert.equal(select.options[0], option);
    assert.deepEqual(select.options.map(choice => choice.value), [first.id, sibling.id]);
    assert.equal(h.context.cachedSelector('/choices').complete, false);
  }
});

test('a stale partial-cache refresh cannot add models to another parent or region', async () => {
  const first = { id: 'first' };
  const other = { id: 'other' };
  const pending = deferredAuthOperation();
  let refreshSignal;
  let path = '/first?region=US';
  const h = selectorOptionsHarness((url, { signal }) => {
    if (url === '/first?region=US&stored_only=1') {
      refreshSignal = signal;
      return pending.promise;
    }
    return url.startsWith('/first') ? { items: [first], complete: false, hydrating: true }
      : { items: [other], complete: true };
  });
  h.context.selectorPath = () => path;
  await h.load('', null, null, 'model');
  await h.load('', null, null, 'model');
  h.context.cancelPickerRefreshes();
  path = '/other?region=CA';
  await h.load('', null, null, 'model');

  pending.resolve({ items: [first, { id: 'late' }], complete: true });
  await new Promise(setImmediate);
  assert.equal(refreshSignal.aborted, true);
  assert.deepEqual(h.$('model').options.map(choice => choice.value), [other.id]);
  assert.deepEqual(h.requests, ['/first?region=US', '/first?region=US&stored_only=1', '/other?region=CA']);
  assert.equal(h.context.cachedSelector('/first?region=US').complete, false);
});

test('an incomplete model cache miss still reads normally for a saved choice', async () => {
  const partial = { items: [{ id: 'first' }], complete: false, hydrating: true };
  const missing = new CatalogRequestError('Models temporarily unavailable', { status: 503 });
  const responses = [partial, missing];
  const h = selectorOptionsHarness(() => {
    const response = responses.shift();
    if (response instanceof Error) throw response;
    return response;
  });
  await h.load('', null, null, 'model');
  assert.equal(h.context.cachedSelector('/choices', 'first').complete, false);
  assert.equal(h.context.cachedSelector('/choices', 'missing'), null);
  await h.load('missing', null, null, 'model');
  assert.deepEqual(h.requests, ['/choices', '/choices']);
  assert.equal(h.$('model').value, '');
  assert.equal(h.statuses.at(-1).error, true);
  assert.equal(h.statuses.at(-1).text, missing.message);
});

test('an unpinned year or make stays usable with its first rows', async () => {
  for (const [name, item] of [['year', { year: 2024 }], ['make', { id: 'buick-truck' }]]) {
    const partial = { items: [item], complete: false, hydrating: true };
    const h = selectorOptionsHarness(partial);
    await h.load('', null, name === 'year' ? Promise.resolve(partial) : null, name);
    assert.deepEqual(h.requests, name === 'year' ? [] : ['/choices']);
    assert.deepEqual(h.waits, []);
    assert.deepEqual(h.displayed, [[item]]);
    assert.equal(h.$(name).disabled, false);
    assert.equal(h.$('retry').hidden, true);
  }
});

test('an empty model still polls and settles as soon as stored rows become usable', async () => {
  const empty = { items: [], complete: false, hydrating: true };
  const partial = { ...empty, items: [{ id: 'available' }] };
  const responses = [empty, empty, partial];
  const h = selectorOptionsHarness(() => responses.shift());
  await h.load('', null, null, 'model');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1', '/choices']);
  assert.deepEqual(h.waits, [350, 1150]);
  assert.deepEqual(h.displayed, [[], partial.items]);
  assert.equal(h.$('model').disabled, false);
  assert.equal(h.$('retry').hidden, true);
});

test('an alternate model keeps polling for a missing saved model', async () => {
  const alternate = { id: 'alternate' };
  const wanted = { id: 'selected' };
  const partial = { items: [alternate], complete: false, hydrating: true };
  const responses = [partial, partial, { ...partial, items: [alternate, wanted] }];
  const h = selectorOptionsHarness(() => responses.shift());
  await h.load(wanted.id, null, null, 'model');
  assert.deepEqual(h.requests, ['/choices', '/choices', '/choices']);
  assert.deepEqual(h.waits, [1500, 1500]);
  assert.equal(h.$('model').value, wanted.id);
});

test('identical hydration snapshots preserve existing option nodes and the selected make', () => {
  const harness = loginRouteHarness('');
  const rows = [{ id: 'toyota', name: 'Toyota' }];
  harness.context.populate('make', rows, 'toyota');
  const first = harness.element('make').options[1];
  harness.context.populate('make', structuredClone(rows));
  assert.equal(harness.element('make').options[1], first);
  assert.equal(harness.element('make').value, 'toyota');
});

test('settled incomplete engine choices remain selectable and retry schedules once again', async () => {
  const h = selectorOptionsHarness({
    items: [{ id: 'engine', complete: true }], hydrating: false, discovering: false, complete: false,
  });
  h.context.restoreRoute = () => h.load();
  await h.load();
  assert.equal(h.$('configuration').disabled, false);
  assert.match(h.statuses.at(-1).text, /Choose an available engine/);
  assert.equal(h.statuses.some(status => status.error), false);
  assert.equal(h.$('retry').hidden, false);
  assert.deepEqual(h.requests, ['/choices']);
  assert.deepEqual(h.waits, []);
  await h.context.retryAction();
  assert.deepEqual(h.requests, ['/choices', '/choices']);
});

test('selectable engine choices expand after one scheduling read and slower storage-only polls', async () => {
  const first = { id: 'engine-a', complete: true };
  const second = { id: 'engine-b', complete: true };
  const partial = { items: [first], hydrating: false, discovering: true, complete: false };
  let checks = 0;
  const h = selectorOptionsHarness(() => {
    if (++checks > 1) {
      assert.equal(h.$('configuration').disabled, false);
      assert.match(h.statuses.at(-1).text, /More engine \/ trim choices are loading/);
    }
    return checks < 3 ? partial : { items: [first, second], hydrating: false, complete: true };
  });
  await h.load();
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, [4000, 4000]);
  assert.deepEqual(h.displayed, [[first], [first], [first, second]]);
  assert.equal(h.statuses.at(-1).text, 'Choose your vehicle to continue.');
});

test('a missing saved engine keeps the fast storage-only cadence until its row arrives', async () => {
  const alternate = { id: 'alternate', complete: true };
  const saved = { id: 'saved', complete: true };
  let checks = 0;
  const h = selectorOptionsHarness(() => ({
    items: ++checks < 3 ? [alternate] : [alternate, saved],
    hydrating: false, discovering: true, complete: false,
  }));
  await h.load('saved');
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, [1500, 1500]);
  assert.equal(h.$('configuration').value, 'saved');
  assert.equal(h.$('retry').hidden, true);
});

test('an idle peer does not end discovery started by another API instance', async () => {
  const first = { id: 'engine-a', complete: true };
  const second = { id: 'engine-b', complete: true };
  const responses = [
    { items: [first], discovering: true, complete: false, discovery_instance: 'one' },
    { items: [first], complete: false, discovery_instance: 'two' },
    { items: [first, second], complete: false, discovery_instance: 'one' },
  ];
  const h = selectorOptionsHarness(() => responses.shift());
  await h.load();
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1', '/choices?stored_only=1']);
  assert.deepEqual(h.waits, [4000, 4000]);
  assert.deepEqual(h.displayed.at(-1), [first, second]);
  assert.equal(h.$('configuration').disabled, false);
  assert.equal(h.$('retry').hidden, false);
});

test('usable prefetched engine choices appear while the verified-parent scheduling response is pending', async () => {
  const first = { id: 'engine-a', complete: true };
  const second = { id: 'engine-b', complete: true };
  const scheduled = deferredAuthOperation();
  const prefetched = { items: [first], hydrating: false, discovering: false, complete: false };
  const h = selectorOptionsHarness(path => path === '/choices'
    ? scheduled.promise
    : { items: [first, second], hydrating: false, complete: true });
  const load = h.load('', null, Promise.resolve(prefetched));
  try {
    await new Promise(setImmediate);
    assert.deepEqual(h.requests, ['/choices']);
    assert.deepEqual(h.displayed, [[first]]);
    assert.equal(h.$('configuration').disabled, false);
  } finally {
    scheduled.resolve({ ...prefetched, discovering: true });
    await load;
  }
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
  assert.equal(h.displayed.at(-1).length, 2);
  assert.equal(h.$('retry').hidden, true);
});

test('stored make and model choices are selectable before normal discovery replies', async () => {
  for (const [name, id] of [['make', 'buick-truck'], ['model', 'envision-awd']]) {
    const first = { id };
    const stored = { items: [first], complete: false, hydrating: true };
    const discovery = deferredAuthOperation();
    const h = selectorOptionsHarness(() => discovery.promise);
    const loading = h.load('', null, Promise.resolve(stored), name);
    try {
      await new Promise(setImmediate);
      assert.deepEqual(h.requests, ['/choices']);
      assert.deepEqual(h.displayed, [[first]]);
      assert.equal(h.$(name).disabled, false);
      assert.equal(h.context.document.body.dataset.busy, 'false');
    } finally {
      discovery.resolve({ ...stored, items: [first, { id: 'another' }] });
      await loading;
    }
    assert.deepEqual(h.requests, ['/choices']);
    assert.deepEqual(h.waits, []);
    assert.equal(h.displayed.at(-1).length, 2);
  }
});

test('switching vehicles aborts an in-flight storage-only engine read and ignores its choices', async () => {
  const first = { id: 'engine-a', complete: true };
  const second = { id: 'engine-b', complete: true };
  const stored = deferredAuthOperation();
  let storedSignal;
  const h = selectorOptionsHarness((path, { signal }) => {
    if (path === '/choices') return { items: [first], discovering: true, complete: false };
    storedSignal = signal;
    return stored.promise;
  });
  const load = h.load();
  try {
    await new Promise(setImmediate);
    assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
    assert.deepEqual(h.displayed, [[first]]);
    assert.equal(storedSignal.aborted, false);
  } finally {
    h.context.navigation.clear();
    stored.resolve({ items: [first, second], complete: true });
    await load;
  }
  assert.equal(storedSignal.aborted, true);
  assert.deepEqual(h.displayed, [[first]]);
  assert.deepEqual(h.requests, ['/choices', '/choices?stored_only=1']);
});

test('complete picker rows are reused only in their own scope and within their freshness window', async () => {
  const h = selectorOptionsHarness({ items: [{ id: 'engine' }], hydrating: false, complete: true });
  let time = 0;
  let scope = '/first';
  h.context.performance = { now: () => time };
  h.context.selectorPath = () => scope;
  await h.load();
  await h.load();
  scope = '/second';
  await h.load();
  time = 30_001;
  scope = '/first';
  await h.load();
  assert.deepEqual(h.requests, ['/first', '/second', '/first']);
});

test('explicitly public picker rows are reusable while sign-in settings are pending', async () => {
  for (const [name, item] of [
    ['year', { year: 2024 }],
    ['make', { id: 'buick-truck' }],
    ['model', { id: 'envision-awd' }],
    ['configuration', { id: 'engine', engine: '2.0', complete: true }],
  ]) {
    const h = selectorOptionsHarness({ items: [item], complete: true });
    h.context.session.state.mode = null;
    await h.load('', null, null, name);
    await h.load('', null, null, name);
    assert.deepEqual(h.requests, ['/choices'], name);
    assert.deepEqual(h.displayed, [[item], [item]]);
    assert.equal(h.$(name).options[0].value, String(item.id ?? item.year));
  }
});

test('local mode and a private picker shell never use cached selector rows', async () => {
  const h = selectorOptionsHarness({ items: [{ id: 'engine' }], complete: true });
  await h.load();
  h.context.session.state.mode = 'local';
  await h.load();
  await h.load();
  h.$('workshop-catalog-module').dataset.publicSelectors = 'false';
  h.context.session.state.mode = null;
  await h.load();
  h.context.session.state.mode = 'firebase';
  await h.load();
  assert.deepEqual(h.requests, ['/choices', '/choices', '/choices', '/choices', '/choices']);
});

test('a picker shell without a public marker keeps selector reads uncached', async () => {
  const h = selectorOptionsHarness({ items: [{ id: 'engine' }], complete: true });
  delete h.$('workshop-catalog-module').dataset.publicSelectors;
  await h.load();
  await h.load();
  assert.deepEqual(h.requests, ['/choices', '/choices']);
});

test('a prefetched selector miss is checked again after the parent was validated', async () => {
  const h = selectorOptionsHarness({ items: [{ id: 'selected' }], complete: true });
  await h.load('selected', null, Promise.resolve({ items: [], complete: true }));
  assert.deepEqual(h.requests, ['/choices']);
  assert.equal(h.$('configuration').value, 'selected');
});

test('saved rows in incomplete prefetched lists restore while discovery continues', async () => {
  const partial = { items: [{ id: 'selected' }], complete: false, hydrating: true };
  for (const name of ['make', 'model', 'configuration']) {
    const discovery = deferredAuthOperation();
    const h = selectorOptionsHarness(() => discovery.promise);
    const restored = h.load('selected', null, Promise.resolve(partial), name);
    try {
      await new Promise(setImmediate);
      assert.equal(h.$(name).disabled, false);
      assert.equal(h.$(name).value, 'selected');
      assert.deepEqual(h.requests, ['/choices']);
    } finally {
      discovery.resolve(partial);
      await restored;
    }
  }
});

test('a missing saved year reports the existing error without repeating the top-level read', async () => {
  const h = selectorOptionsHarness({ items: [{ year: 2020 }], complete: true });
  await h.load('2020', null, Promise.resolve({ items: [{ year: 2021 }], complete: true }), 'year');
  assert.deepEqual(h.requests, []);
  assert.equal(h.statuses.at(-1).error, true);
  assert.match(h.statuses.at(-1).text, /saved vehicle choice is unavailable/);
});

test('canceling a prefetched selector skips its fallback read', async () => {
  const h = selectorOptionsHarness({ items: [{ id: 'selected' }], complete: true });
  const held = deferredAuthOperation();
  const selected = h.load('selected', null, held.promise);
  h.context.navigation.clear();
  held.resolve(null);
  await selected;
  assert.deepEqual(h.requests, []);
  assert.deepEqual(h.displayed, []);
});

test('a selector timeout keeps populated choices usable and offers a retry', async()=>{
 for(const items of [[],[{id:'cfg-1',engine:'2.0L',complete:true}]]) {
  const h=selectorOptionsHarness({items,complete:false,hydrating:true});
  await h.load();
  const last=h.statuses.at(-1);
  assert.equal(Boolean(last.error), !items.length);
  assert.match(last.text, items.length ? /Choose an available engine/ : /loading|load/i);
  assert.doesNotMatch(last.text,/No choices|Choose your vehicle/);
  assert.equal(typeof last.retry,'function');
  assert.equal(h.$('retry').hidden,false);
  assert.equal(typeof h.context.retryAction,'function');
  assert.deepEqual(h.displayed.at(-1),items);
  assert.equal(h.$('configuration').disabled,!items.length);
 }
});
test('actual selector incomplete nonhydrating scope does not claim empty completion',async()=>{
 const h=selectorOptionsHarness({items:[],complete:false,hydrating:false});await h.load();
 assert.equal(h.statuses.at(-1).error,true);assert.equal(typeof h.statuses.at(-1).retry,'function');
 assert.equal(h.$('retry').hidden,false);assert.equal(typeof h.context.retryAction,'function');
});
test('selector success hides retry for completed and saved partial choices',async()=>{
 for(const [response,desired] of [
  [{items:[{id:'cfg-1',complete:true}],complete:true,hydrating:false},''],
  [{items:[],complete:true,hydrating:false},''],
  [{items:[{id:'cfg-1',complete:true}],complete:false,hydrating:true},'cfg-1'],
 ]) {
  const h=selectorOptionsHarness(response);await h.load(desired);
  assert.notEqual(h.statuses.at(-1).error,true);
  assert.equal(h.$('retry').hidden,true);
  assert.equal(h.context.retryAction,null);
 }
});
test('actual selector completed empty scope reports no choices without a loading failure',async()=>{
 const h=selectorOptionsHarness({items:[],complete:true,hydrating:false});await h.load();
 assert.match(h.statuses.at(-1).text,/No .*choices/i);assert.notEqual(h.statuses.at(-1).error,true);
});
test('missing saved selector is not declared unavailable until the scope completes',async()=>{
 const h=selectorOptionsHarness({items:[],complete:false,hydrating:true});await h.load('missing');
 assert.equal(h.statuses.at(-1).error,true);assert.doesNotMatch(h.statuses.at(-1).text,/saved.*unavailable/i);
 const complete=selectorOptionsHarness({items:[],complete:true,hydrating:false});
 await complete.load('missing');assert.match(complete.statuses.at(-1).text,/saved vehicle choice is unavailable/);
});
test('actual selector still resumes a saved row before background hydration completes',async()=>{
 const h=selectorOptionsHarness({items:[{id:'cfg-1',complete:true}],complete:false,hydrating:true});await h.load('cfg-1');
 assert.notEqual(h.statuses.at(-1).error,true);assert.equal(h.$('configuration').value,'cfg-1');
});
test('actual selector ignores results after generation changes',async()=>{
 const h=selectorOptionsHarness({items:[],complete:true,hydrating:false});await h.load('',()=>false);
 assert.equal(h.displayed.length,0);assert.equal(h.statuses.length,1);
});

test('actual selector source request failure retains its retry action',async()=>{
 const h=selectorOptionsHarness(new Error('Cannot reach AutoData. Try again.'));await h.load();
 assert.equal(h.statuses.at(-1).error,true);assert.match(h.statuses.at(-1).text,/Cannot reach/);
 assert.equal(typeof h.statuses.at(-1).retry,'function');
 assert.equal(h.$('retry').hidden,false);assert.equal(typeof h.context.retryAction,'function');
});
test('legacy selector responses without completion metadata remain usable',async()=>{
 const h=selectorOptionsHarness({items:[{year:2024}]});await h.load();
 assert.notEqual(h.statuses.at(-1).error,true);assert.match(h.statuses.at(-1).text,/Choose your vehicle/);
});

test('both Stripe hosted path forms preserve opaque tokens with strict authority', async () => {
 const { hostedCheckoutURL } = await import('./workshop/commerce.mjs');
 for (const prefix of ['c','g']) {
  const hosted = `https://checkout.stripe.com/${prefix}/pay/opaque_Checkout42#opaque%2Ffragment`;
  assert.equal(hostedCheckoutURL(hosted), hosted);
  for (const invalid of [hosted.replace('https:', 'http:'), hosted.replace('checkout.stripe.com', 'checkout.stripe.com.evil'), hosted.replace('checkout.stripe.com', 'user@checkout.stripe.com'), hosted.replace('checkout.stripe.com', 'checkout.stripe.com:443'), `https://checkout.stripe.com/${prefix}/pay/`, hosted+' ', hosted+'\u0000']) assert.equal(hostedCheckoutURL(invalid), null);
 }
 for (const invalid of ['https://checkout.stripe.com/pay/opaque','https://checkout.stripe.com/x/pay/opaque']) assert.equal(hostedCheckoutURL(invalid),null);
});

// These transports are local doubles; production session and route-selection code runs unchanged.
test('session exposes only explicit known config modes and resets mode when authority is cleared', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  for (const mode of ['local', 'firebase', undefined, null, 'LOCAL', 'other', true]) {
    let config = { mode };
    const session = createSession({ request: async path => {
      if (path === '/auth/config') return config;
      return { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'csrf' };
    }, loadSDK: () => assert.fail('an existing session needs no SDK') });
    assert.equal(session.state.mode, null);
    await session.bootstrap();
    assert.equal(session.state.authenticated, true);
    assert.equal(session.state.mode, ['local', 'firebase'].includes(mode) ? mode : null);
    session.clear();
    assert.equal(session.state.mode, null);
    assert.equal(session.state.authenticated, false);
    config = null;
    await session.bootstrap();
    assert.equal(session.state.mode, null);
  }
});

test('an explicit local config mode cannot authenticate an invalid session or enable Google login', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  const session = createSession({ request: async path => path === '/auth/config'
    ? { mode: 'local' }
    : { authenticated: true, roles: [], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'csrf' },
    loadSDK: () => assert.fail('local configuration must not initialize Firebase') });
  await session.bootstrap();
  assert.equal(session.state.mode, 'local');
  assert.equal(session.state.authenticated, false);
  assert.equal(session.state.csrf, '');
  assert.equal(session.state.available, false);
  assert.equal(session.state.ready, false);
});

test('failed or obsolete configuration reads cannot preserve or restore local session mode', async () => {
  const { createSession } = await import('./workshop/auth.mjs');
  let readConfig = async () => ({ mode: 'local' });
  const session = createSession({ request: async path => path === '/auth/config'
    ? readConfig()
    : { authenticated: true, roles: ['dataset_viewer'], expires_at: '2099-01-01T00:00:00Z', csrf_token: 'csrf' } });
  await session.bootstrap();
  assert.equal(session.state.mode, 'local');
  let release;
  readConfig = () => new Promise(resolve => { release = resolve; });
  const obsolete = session.bootstrap();
  assert.equal(session.state.mode, null, 'bootstrap must clear old mode before its first await');
  readConfig = async () => ({ mode: 'firebase' });
  await session.bootstrap();
  release({ mode: 'local' });
  await obsolete;
  assert.equal(session.state.mode, 'firebase');
  readConfig = async () => { throw new TypeError('offline'); };
  await session.bootstrap();
  assert.equal(session.state.mode, null);
  const controller = new AbortController();
  readConfig = async () => { controller.abort(); return { mode: 'local' }; };
  await session.bootstrap({ signal: controller.signal });
  assert.equal(session.state.mode, null);
});

const scopedQuoteFixture = () => ({
  ...scope, version: 'v1', product_key: 'workshop-configuration-v1',
  configuration_label: '2024 Example Car', amount_minor: 2000, currency: 'USD',
  purchase_terms_version: 'workshop-v1', purchasable: true,
});

function selectionQuoteHarness(merchant, { authenticated = true, openDemo = false, request = async () => scopedQuoteFixture() } = {}) {
  const navigation = new NavigationGeneration(), generation = navigation.next(), calls = [], opened = [], nodes = new Map();
  const shown = [];
  const context = {
    merchant, merchantRequest: null, openDemo, quote: null, access: "unknown", validScope, validQuote, uuid, configurationLabel,
    quoteConfigurationLabel,
    vehicle: { id: scope.configuration_id, region: scope.region },
    scope: () => ({ configuration_id: context.vehicle.id, region: context.vehicle.region }),
    session: { state: { authenticated } }, sessionRequest: null,
    clearProtected() {}, renderPurchase() {}, show: id => shown.push(id), status() {}, purchaseConfigured: () => context.merchant?.enabled === true,
    $: id => { if (!nodes.has(id)) nodes.set(id, {}); return nodes.get(id); },
    requestJSON: async (path, options) => { calls.push({ path, options }); return request(path, options); },
    loadArticles: async (g, id) => opened.push({ g, id }),
  };
  runInNewContext(appSection('function vehicleIdentityLabel(', 'function purchaseConfigured('), context);
  runInNewContext(appSection('async function selectVehicle(', 'async function loadArticles('), context);
  return { context, navigation, generation, calls, opened, shown };
}

test('an unnamed guest saved scope shows its public label while purchase configuration is pending', async () => {
  const config = deferredAuthOperation(), pending = deferredAuthOperation();
  const h = selectionQuoteHarness(null, { authenticated: false, request: () => pending.promise });
  h.context.merchantRequest = config.promise;
  const loading = h.context.selectVehicle(h.generation, '', { savedLink: true });
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].path, `/v1/workshop/quote?configuration_id=${scope.configuration_id}&region=${scope.region}`);
  assert.equal(h.calls[0].options.signal, h.generation.signal);
  assert.deepEqual(h.shown, ['welcome']);
  pending.resolve({ ...scopedQuoteFixture(), purchasable: false });
  await new Promise(setImmediate);
  assert.equal(h.context.vehicleIdentityLabel(), '2024 Example Car');
  assert.equal(h.context.quote, null);
  h.context.merchant = { enabled: false };
  h.context.merchantRequest = null;
  config.resolve();
  await loading;
  assert.equal(h.calls.length, 1);
  assert.equal(h.opened.length, 0);
});

test('the saved guest quote rejects a wrong or superseded scope and leaves known labels alone', async () => {
  for (const scenario of ['wrong region', 'wrong configuration', 'abort', 'new selection', 'known label']) {
    const pending = deferredAuthOperation();
    const h = selectionQuoteHarness({ enabled: false }, { authenticated: false, request: () => pending.promise });
    if (scenario === 'known label') h.context.vehicle.make = 'Known';
    const loading = h.context.selectVehicle(h.generation, '', { savedLink: true });
    assert.equal(h.calls.length, scenario === 'known label' ? 0 : 1, scenario);
    if (scenario === 'abort') h.navigation.next();
    if (scenario === 'new selection') h.context.vehicle = { ...h.context.vehicle, region: 'CA' };
    const response = { ...scopedQuoteFixture(), purchasable: false };
    if (scenario === 'wrong region') response.region = 'CA';
    if (scenario === 'wrong configuration') response.configuration_id = '22222222-2222-4222-8222-222222222222';
    pending.resolve(response);
    await loading;
    assert.equal(h.context.vehicleIdentityLabel(), scenario === 'known label' ? 'Known' : '', scenario);
    assert.equal(h.context.quote, null, scenario);
    assert.equal(h.opened.length, 0, scenario);
    assert.equal(h.generation.signal.aborted, scenario === 'abort', scenario);
  }
});

test('one saved guest quote can still supply an eligible price for an enabled merchant', async () => {
  const h = selectionQuoteHarness({ enabled: true }, { authenticated: false });
  await h.context.selectVehicle(h.generation, '', { savedLink: true });
  assert.equal(h.calls.length, 1);
  assert.equal(h.context.vehicleIdentityLabel(), '2024 Example Car');
  assert.ok(validQuote(h.context.quote, scope));
  assert.equal(h.opened.length, 0);
});

test('saved guest selection tolerates a commerce module without public label validation', async () => {
  for (const enabled of [false, true]) {
    const h = selectionQuoteHarness({ enabled }, { authenticated: false });
    h.context.quoteConfigurationLabel = undefined;
    await h.context.selectVehicle(h.generation, '', { savedLink: true });
    assert.deepEqual(h.shown, ['welcome']);
    assert.equal(h.calls.length, enabled ? 1 : 0);
    assert.equal(h.context.vehicleIdentityLabel(), '');
    assert.equal(validQuote(h.context.quote, scope), enabled);
    assert.equal(h.opened.length, 0);
  }
});

test('same-selection sign-in keeps the public price visible and uses the current quote returned with paid access', async () => {
  const h = selectionQuoteHarness({ enabled: true }, { authenticated: false });
  await h.context.selectVehicle(h.generation);
  const prior = h.context.quote;
  assert.equal(h.calls.length, 1);
  assert.equal(h.opened.length, 0);

  h.context.session.state.authenticated = true;
  h.context.$('agreement').checked = true;
  const current = { ...prior, configuration_label: '2024 Example Car 2.0 L' };
  const required = Object.assign(new Error('Purchase required'), { code: 'ENTITLEMENT_REQUIRED', purchaseQuote: current });
  h.context.loadArticles = async (_g, _id, options) => {
    assert.equal(options.includePurchaseQuote, true);
    assert.equal(h.context.quote, prior);
    h.opened.push(true);
    throw required;
  };
  await assert.rejects(h.context.selectVehicle(h.navigation.next(), '', { reuseQuote: true }), required);
  assert.equal(h.context.quote, current);
  assert.equal(h.context.$('agreement').checked, false);
  assert.equal(h.calls.length, 1);
  assert.equal(h.opened.length, 1);
});

test('sign-in stops using the old quote after an authoritative unavailable result or falls back for an older API', async () => {
  for (const [value, fetches, available] of [
    [null, 0, false],
    [{ ...scopedQuoteFixture(), region: 'CA' }, 0, false],
    [undefined, 1, true],
  ]) {
    const h = selectionQuoteHarness({ enabled: true });
    h.context.quote = scopedQuoteFixture();
    const required = Object.assign(new Error('Purchase required'), { code: 'ENTITLEMENT_REQUIRED', purchaseQuote: value });
    h.context.loadArticles = async () => { throw required; };
    await assert.rejects(h.context.selectVehicle(h.generation, '', { reuseQuote: true }), required);
    assert.equal(h.calls.length, fetches);
    assert.equal(validQuote(h.context.quote, scope), available);
  }
});

test('only a paid entitlement-required response can attach purchase quote details', async () => {
  for (const [status, code, value, expected] of [
    [403, 'ENTITLEMENT_REQUIRED', scopedQuoteFixture(), scopedQuoteFixture()],
    [403, 'ENTITLEMENT_REQUIRED', null, null],
    [401, 'ENTITLEMENT_REQUIRED', scopedQuoteFixture(), undefined],
    [403, 'ENTITLEMENT_REVOKED', scopedQuoteFixture(), undefined],
  ]) {
    await assert.rejects(requestJSON('/articles', { fetcher: async () => new Response(JSON.stringify({
      error: { code, details: { purchase_quote: value } },
    }), { status }) }), (error) => {
      assert.deepEqual(error.purchaseQuote, expected);
      return true;
    });
  }
});

test('a superseded region or disabled merchant cannot reuse a public quote after sign-in', async () => {
  for (const [merchant, prior, requests] of [
    [{ enabled: true }, { ...scopedQuoteFixture(), region: 'CA' }, 1],
    [{ enabled: false }, scopedQuoteFixture(), 0],
  ]) {
    const h = selectionQuoteHarness(merchant);
    h.context.quote = prior;
    await h.context.selectVehicle(h.generation, '', { reuseQuote: true });
    assert.notEqual(h.context.quote, prior);
    assert.equal(h.calls.length, requests);
    assert.equal(h.opened.length, 1);
  }
});

test('known-owned handoffs skip the quote and Library fetches a price only if access is missing', async () => {
  for (const quoteMode of ['skip', 'if-needed']) {
    const h = selectionQuoteHarness({ enabled: true });
    await h.context.selectVehicle(h.generation, '', { quoteMode });
    assert.equal(h.opened.length, 1);
    assert.equal(h.calls.length, 0);

    const required = Object.assign(new Error('Access required'), { code: 'ENTITLEMENT_REQUIRED' });
    h.context.loadArticles = async () => { throw required; };
    await assert.rejects(h.context.selectVehicle(h.generation, '', { quoteMode }), required);
    assert.equal(h.calls.length, quoteMode === 'if-needed' ? 1 : 0);
  }
});

test('saved exact Firebase links try the article before fetching index or quote', async () => {
  for (const [mode, openDemo, supported, index] of [
    ['firebase', false, true, false], ['firebase', false, false, true],
    ['local', false, true, true], ['firebase', true, true, true],
  ]) {
    const h = selectionQuoteHarness({ enabled: true }, { openDemo });
    h.context.session.state.mode = mode;
    const direct = [];
    h.context.loadArticle = async (id, generation, options) => {
      assert.equal(id, routeArticle);
      assert.equal(generation, h.generation);
      assert.equal(options.savedLink, true);
      direct.push(id);
      return supported;
    };
    await h.context.selectVehicle(h.generation, routeArticle, { savedLink: true });
    assert.equal(h.opened.length, Number(index));
    assert.equal(direct.length, Number(mode === 'firebase' && !openDemo));
    assert.equal(h.calls.length, Number(mode === 'local'));
  }
});

test('cold selection waits for confirmed authentication and leaves superseded choices alone', async () => {
  for (const canceled of [false, true]) {
    const h = selectionQuoteHarness({ enabled: true }, { authenticated: false });
    const account = deferredAuthOperation();
    h.context.sessionRequest = account.promise;
    const selecting = h.context.selectVehicle(h.generation);
    assert.equal(h.calls.length, 0);
    assert.equal(h.opened.length, 0);
    if (canceled) h.navigation.clear();
    h.context.session.state.authenticated = true;
    account.resolve();
    await selecting;
    assert.equal(h.opened.length, canceled ? 0 : 1);
    assert.equal(h.calls.length, canceled ? 0 : 1);
  }
});

test('open demo selects a vehicle without login, quote, or purchase', async () => {
  const h = selectionQuoteHarness({ enabled: true }, {
    authenticated: false, openDemo: true,
    request: () => assert.fail('open demo must not request a quote'),
  });
  await h.context.selectVehicle(h.generation, 'article-a');
  assert.equal(h.calls.length, 0);
  assert.equal(h.opened.length, 1);
  assert.equal(h.opened[0].id, 'article-a');
});

for (const merchant of [{ enabled: false }, null, {}, { enabled: 'true' }]) {
  test(`selection skips unusable quote for config ${JSON.stringify(merchant)} and still opens authorized articles`, async () => {
    const h = selectionQuoteHarness(merchant, { request: () => assert.fail('disabled quote must never be requested') });
    await h.context.selectVehicle(h.generation, 'article-a');
    assert.equal(h.calls.length, 0);
    assert.equal(h.context.quote, null);
    assert.equal(h.opened.length, 1);
    assert.equal(h.opened[0].id, 'article-a');
  });
}

test('disabled quote selection retains signed-out and obsolete-navigation boundaries', async () => {
  const signedOut = selectionQuoteHarness({ enabled: false }, { authenticated: false });
  await signedOut.context.selectVehicle(signedOut.generation);
  assert.equal(signedOut.calls.length, 0);
  assert.equal(signedOut.opened.length, 0);
  const stale = selectionQuoteHarness({ enabled: false });
  stale.navigation.clear();
  await stale.context.selectVehicle(stale.generation);
  assert.equal(stale.calls.length, 0);
  assert.equal(stale.opened.length, 0);
});

test('enabled purchasing keeps scoped quote validation, tolerated unavailable quote, and article reads', async () => {
  for (const result of [scopedQuoteFixture(), { ...scopedQuoteFixture(), amount_minor: 1 }, new Error('503')]) {
    const h = selectionQuoteHarness({ enabled: true }, { request: async () => {
      if (result instanceof Error) throw result;
      return result;
    } });
    await h.context.selectVehicle(h.generation, 'article-a');
    assert.equal(h.calls.length, 1);
    assert.equal(h.calls[0].path, `/v1/workshop/quote?configuration_id=${scope.configuration_id}&region=${scope.region}`);
    assert.equal(h.calls[0].options.signal, h.generation.signal);
    assert.equal(h.context.quote, validQuote(result, scope) ? result : null);
    assert.equal(h.opened.length, 1);
  }
});

test('startup restores an authenticated route before purchase configuration settles', async () => {
  let finishMerchant;
  const opened = [];
  const config = { enabled: true };
  const context = {
    URLSearchParams, location: { search: '?view=library' }, openDemo: false,
    merchant: null, merchantRequest: null, sessionEstablished: false, sessionRequest: null,
    session: { async bootstrap() {} }, invalidate() {}, renderPurchase() {},
    requestJSON(path) {
      assert.equal(path, '/workshop/purchase-config.json');
      return new Promise(resolve => { finishMerchant = resolve; });
    },
    async restoreRoute() { opened.push('library'); },
  };
  runInNewContext(appSection('async function bootstrap(', 'async function restoreRoute('), context);
  const booted = context.bootstrap();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(opened, ['library']);
  assert.equal(context.sessionEstablished, true);
  assert.equal(context.merchant, null);
  finishMerchant(config);
  await booted;
  await context.merchantRequest;
  assert.equal(context.merchant, config);
});

test('cold startup exposes the prefetched public years during the account check', async () => {
  const account = deferredAuthOperation();
  const requests = [], routes = [];
  const years = { items: [{ year: 2024 }] };
  const context = {
    URLSearchParams, location: { search: '' }, openDemo: false,
    merchant: null, merchantRequest: null, sessionEstablished: false, sessionRequest: null,
    session: { bootstrap: () => account.promise }, invalidate() {},
    async requestJSON(path) {
      requests.push(path);
      return path === '/v1/catalog/years' ? years : { enabled: false };
    },
    async restoreRoute(initialYears) { routes.push(await initialYears); },
  };
  runInNewContext(appSection('async function bootstrap(', 'async function restoreRoute('), context);
  const booted = context.bootstrap();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(routes, [years]);
  assert.deepEqual(requests, ['/v1/catalog/years', '/workshop/purchase-config.json']);
  assert.equal(context.sessionEstablished, false);
  account.resolve();
  await booted;
  assert.deepEqual(routes, [years]);
  assert.equal(context.sessionRequest, null);
  assert.equal(context.sessionEstablished, true);
});

test('the first selector renders while checkout mode confirmation is pending', async () => {
  const mode = deferredAuthOperation();
  const routes = [];
  const config = { enabled: true };
  const years = { items: [{ year: 2024 }] };
  const banner = { hidden: true };
  const context = {
    URLSearchParams, location: { search: '' }, openDemo: false, $: () => banner,
    merchant: null, merchantRequest: null, sessionEstablished: false, sessionRequest: null,
    session: { async bootstrap() {} }, invalidate() {},
    requestJSON: async () => config,
    async restoreRoute(initialYears) { routes.push(await initialYears); },
  };
  runInNewContext(appSection('async function bootstrap(', 'async function restoreRoute('), context);
  await context.bootstrap(Promise.resolve(years), null, { testCheckout: mode.promise });
  assert.deepEqual(routes, [years]);
  assert.equal(context.merchant, null);
  assert.equal(context.testStripeMode, false);
  assert.equal(banner.hidden, true);
  mode.resolve(true);
  await context.merchantRequest;
  assert.equal(context.merchant, config);
  assert.equal(context.testStripeMode, true);
  assert.equal(banner.hidden, false);
});

test('simulation purchase settings are usable while the separate demo mode read is pending', async () => {
  const mode = deferredAuthOperation();
  const config = { enabled: true, checkout_mode: 'simulation' };
  const context = {
    URLSearchParams, location: { search: '?view=library' }, openDemo: false,
    merchant: null, merchantRequest: null, sessionEstablished: false, sessionRequest: null,
    session: { async bootstrap() {} }, invalidate() {}, async restoreRoute() {},
    requestJSON: async () => config,
  };
  runInNewContext(appSection('async function bootstrap(', 'async function restoreRoute('), context);
  await context.bootstrap(null, null, { testCheckout: mode.promise });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.merchant, config);
  assert.equal(context.merchantRequest, null);
});

test('a late purchase configuration response cannot overwrite a newer refresh', async () => {
  const replies = [];
  const context = {
    URLSearchParams, location: { search: '?view=library' }, openDemo: false,
    merchant: null, merchantRequest: null, sessionEstablished: false, sessionRequest: null,
    session: { async bootstrap() {} }, invalidate() {}, async restoreRoute() {},
    requestJSON(path) {
      assert.equal(path, '/workshop/purchase-config.json');
      return new Promise(resolve => replies.push(resolve));
    },
  };
  runInNewContext(appSection('async function bootstrap(', 'async function restoreRoute('), context);
  await context.bootstrap();
  const first = context.merchantRequest;
  await context.bootstrap();
  const latest = context.merchantRequest;
  const disabled = { enabled: false };
  replies[1](disabled);
  await latest;
  replies[0]({ enabled: true });
  await first;
  assert.equal(context.merchant, disabled);
  assert.equal(context.merchantRequest, null);
});

test('owned articles can open before the purchase settings and scoped quote arrive', async () => {
  let finishMerchant;
  const h = selectionQuoteHarness(null);
  h.context.merchantRequest = new Promise(resolve => { finishMerchant = resolve; });
  await h.context.selectVehicle(h.generation, 'article-a');
  assert.equal(h.opened[0]?.id, 'article-a');
  assert.equal(h.calls.length, 0);
  h.context.merchant = { enabled: true };
  finishMerchant();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls.length, 1);
  assert.equal(validQuote(h.context.quote, scope), true);
});

test('an obsolete vehicle cannot request a quote when purchase settings arrive', async () => {
  let finishMerchant;
  const h = selectionQuoteHarness(null);
  h.context.merchantRequest = new Promise(resolve => { finishMerchant = resolve; });
  await h.context.selectVehicle(h.generation, 'article-a');
  h.navigation.clear();
  h.context.merchant = { enabled: true };
  finishMerchant();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls.length, 0);
  assert.equal(h.context.quote, null);
});

test('owned articles open while a scoped quote is still in flight', async () => {
  let release;
  const h = selectionQuoteHarness({ enabled: true }, {
    request: () => new Promise(resolve => { release = resolve; }),
  });
  await h.context.selectVehicle(h.generation, 'article-a');
  assert.equal(h.calls.length, 1);
  assert.equal(h.opened[0]?.id, 'article-a');
  assert.equal(h.context.quote, null);
  h.context.access = 'owned';
  const identity = '2024 / Example / Car / 2.0 L';
  h.context.$('reader-vehicle').textContent = identity;
  h.context.renderPurchase = () => {
    h.context.$('purchase-selection').textContent = `${h.context.quote.configuration_label} / ${h.context.quote.region}`;
  };
  release(scopedQuoteFixture());
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(validQuote(h.context.quote, scope), true);
  assert.equal(h.context.$('vehicle-caption').textContent, h.context.$('purchase-selection').textContent);
  assert.equal(h.context.$('reader-vehicle').textContent, identity);
});

test('obsolete quote cannot publish after selection is canceled', async () => {
  for (const reject of [false, true]) {
    let resolveRequest, rejectRequest;
    const h = selectionQuoteHarness({ enabled: true }, { request: () => new Promise((resolve, fail) => { resolveRequest = resolve; rejectRequest = fail; }) });
    await h.context.selectVehicle(h.generation);
    assert.equal(h.opened.length, 1);
    h.navigation.clear();
    if (reject) rejectRequest(new DOMException('canceled', 'AbortError'));
    else resolveRequest(scopedQuoteFixture());
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.context.quote, null);
  }
});

function articleRouteHarness(mode, request, authenticated = true, openDemo = false) {
  const h = articleMediaHarness({
    session: { state: { mode, authenticated, csrf: 'csrf' } }, stage() {}, requestArticleJSON: request,
    readArticle: async (read, options) => {
      const { readArticle } = await import('./workshop/article-read.mjs');
      return readArticle(read, { ...options, wait: async () => {} });
    },
  });
  h.context.openDemo = openDemo;
  h.context.demoPath = path => openDemo ? `${path}${path.includes('?') ? '&' : '?'}demo=1` : path;
  runInNewContext(appSection('async function loadArticle(', 'function openArticle('), h.context);
  return h;
}

function retainedReaderHarness(request) {
  const configuration = { id: routeConfiguration, region: 'US', engine: '3.5' };
  const gracePeriod = deferredAuthOperation();
  const calls = [];
  let probeSignal;
  const h = articleRouteHarness('firebase', (path, options) => {
    calls.push({ path, ...options });
    return request(path, options);
  });
  h.context.vehicle = configuration;
  h.context.articlePath = id => `/v1/catalog/vehicles/${configuration.id}/articles/${id}`;
  h.context.renderPurchase = () => {};
  h.context.delay = (ms, signal) => {
    if (probeSignal) return delay(ms, signal);
    assert.equal(ms, 250);
    probeSignal = signal;
    signal.addEventListener('abort', () => gracePeriod.reject(signal.reason), { once: true });
    return gracePeriod.promise;
  };
  return { ...h, configuration, calls, gracePeriod,
    get probeSignal() { return probeSignal; } };
}

function refocusingStoredSource({ ended = false } = {}) {
  const source = mediaArticle([
    { type: 'paragraph', text: 'Stored Ford procedure.' },
    { type: 'image', asset_id: 'figure' },
  ], [{ id: 'figure', url: mediaURL('refocus') }], {
    id: routeArticle, processing: { job_id: routeOrder, state: 'rewriting' },
  });
  const published = { ...source, content_origin: 'canonical', view_revision: 'published',
    processing: { ...source.processing, state: 'completed' } };
  const account = deferredAuthOperation(), detail = deferredAuthOperation();
  const waiting = deferredAuthOperation(), releasePoll = deferredAuthOperation();
  const checked = deferredAuthOperation();
  const accountReads = [];
  let getReads = 0, bootstraps = 0, polls = 0, time = 1000;
  const h = retainedReaderHarness(async (_path, options) => {
    if (options.method === 'POST') return { status: 200, data: { configuration: h.configuration, article: source } };
    if (++getReads === 1) return detail.promise;
    return { status: 200, data: { configuration: h.configuration, article: published } };
  });
  for (const id of ['cancel', 'loading-progress']) h.nodes.set(id, new ArticleMediaNode('div'));
  Object.assign(h.context, {
    viewGeneration: h.g, sessionEstablished: true, signingIn: false, currentOrder: '',
    scope: () => ({ configuration_id: h.configuration.id, region: h.configuration.region }),
    bootstrap() {
      bootstraps++;
      h.context.invalidate();
    },
    show(id) { h.nodes.get('reader').hidden = id !== 'reader'; },
    performance: { now: () => time },
    async readArticle(read, options) {
      const { readArticle } = await import('./workshop/article-read.mjs');
      const run = ++polls;
      const result = await readArticle(read, {
        ...options,
        now: () => time,
        async wait(milliseconds, signal) {
          if (ended && run === 1) {
            time += 120_000;
            return;
          }
          waiting.resolve();
          await releasePoll.promise;
          signal?.throwIfAborted();
          time += milliseconds;
        },
      });
      if (result.data?.article?.view_revision === 'published') checked.resolve();
      return result;
    },
  });
  h.context.document.visibilityState = 'visible';
  h.context.location.search = '?' + new URLSearchParams({
    configuration: h.configuration.id, region: h.configuration.region, article: routeArticle,
  });
  h.context.session.matchesCurrentSession = ({ signal }) => {
    accountReads.push(signal);
    return account.promise;
  };
  runInNewContext(appSection('async function operation(', 'function updateURL(') +
    appSection('let lifecycleCheck = null;', 'const channel ='), h.context);
  const opening = h.context.loadArticle(routeArticle, h.g).catch(error => {
    if (h.g.current()) throw error;
  });
  const ready = ended ? opening : waiting.promise;
  return { ...h, account, accountReads, detail, source, ready, releasePoll, checked,
    bootstraps: () => bootstraps, polls: () => polls,
    focus() { h.context.window.dispatchEvent(new Event('focus')); },
    methods() { return h.calls.map(call => call.method || 'GET'); },
    async dispose() {
      h.navigation.clear();
      releasePoll.resolve();
      account.resolve(false);
      detail.resolve(null);
      await opening;
    },
  };
}

test('refocusing a stored article reuses its authorized figure DOM while rewriting', async t => {
  for (const ended of [false, true]) {
    await t.test(ended ? 'resumes an ended poll' : 'keeps an active poll', async () => {
      const h = refocusingStoredSource({ ended });
      try {
        await h.ready;
        const content = h.nodes.get('article-content'), reader = h.nodes.get('reader');
        const [figure] = mediaDescendants(content, 'img');
        assert.ok(figure?.src);
        assert.deepEqual(h.methods(), ['POST']);
        h.focus();
        h.focus();
        assert.equal(h.bootstraps(), 0);
        assert.equal(h.g.current(), true);
        assert.deepEqual(h.accountReads, [h.g.signal]);
        assert.deepEqual(h.methods(), ['POST', 'GET']);
        assert.equal(h.calls[1].path,
          `/v1/catalog/vehicles/${h.configuration.id}/articles/${routeArticle}?region=US`);
        assert.equal(reader.hidden, true);
        assert.equal(h.context.document.body.dataset.printable, 'false');
        assert.equal(mediaDescendants(content, 'img')[0], figure);
        h.detail.resolve({ status: 200, data: { configuration: h.configuration, article: h.source } });
        await new Promise(setImmediate);
        assert.equal(reader.hidden, true);
        h.account.resolve(true);
        await new Promise(setImmediate);
        assert.equal(reader.hidden, false);
        assert.equal(h.context.document.body.dataset.printable, 'true');
        assert.match(content.textContent, /Stored Ford procedure/);
        assert.equal(mediaDescendants(content, 'img')[0], figure);
        assert.equal(h.polls(), ended ? 2 : 1);
        assert.deepEqual(h.methods(), ['POST', 'GET']);
        h.releasePoll.resolve();
        await h.checked.promise;
        assert.equal(h.context.currentArticle.content_origin, 'canonical');
        assert.deepEqual(h.methods(), ['POST', 'GET', 'GET']);
      } finally {
        await h.dispose();
      }
    });
  }
});

test('refocusing a stored article clears held text and figures on exact access denial', async () => {
  const h = refocusingStoredSource();
  try {
    await h.ready;
    h.focus();
    assert.equal(h.bootstraps(), 0);
    assert.deepEqual(h.methods(), ['POST', 'GET']);
    h.account.resolve(true);
    h.detail.reject(Object.assign(new Error('Article access was revoked'), { status: 403, code: 'ENTITLEMENT_REVOKED' }));
    await new Promise(setImmediate);
    const content = h.nodes.get('article-content');
    assert.equal(h.g.current(), false);
    assert.equal(h.nodes.get('reader').hidden, true);
    assert.equal(h.context.document.body.dataset.printable, 'false');
    assert.equal(content.textContent, '');
    assert.deepEqual(mediaDescendants(content, 'img'), []);
    assert.equal(h.bootstraps(), 0);
  } finally {
    await h.dispose();
  }
});

test('publication during refocus keeps the reader unavailable for printing until access is verified', async () => {
  const h = refocusingStoredSource();
  try {
    await h.ready;
    const content = h.nodes.get('article-content'), reader = h.nodes.get('reader');
    const [figure] = mediaDescendants(content, 'img');
    h.focus();
    h.releasePoll.resolve();
    await h.checked.promise;
    assert.equal(reader.hidden, true);
    assert.equal(h.context.document.body.dataset.printable, 'false');
    assert.equal(mediaDescendants(content, 'img')[0], figure);
    h.detail.resolve({ status: 200, data: { configuration: h.configuration, article: h.source } });
    h.account.resolve(true);
    await new Promise(setImmediate);
    assert.equal(reader.hidden, false);
    assert.equal(h.context.document.body.dataset.printable, 'true');
    assert.equal(h.context.currentArticle.content_origin, 'canonical');
    assert.deepEqual(h.methods(), ['POST', 'GET', 'GET']);
  } finally {
    await h.dispose();
  }
});

test('a slow paid prepare opens retained text before the POST finishes on saved and regular entries', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  for (const savedLink of [true, false]) {
    const prepare = deferredAuthOperation(), poll = deferredAuthOperation(), polling = deferredAuthOperation();
    const source = mediaArticle([{ type: 'paragraph', text: 'Stored Ford procedure.' }], [], {
      source_body_preview: true, source_revision_id: null,
    });
    const published = mediaArticle([{ type: 'paragraph', text: 'Published Ford procedure.' }], [], {
      content_origin: 'canonical', view_revision: 'published',
    });
    const h = retainedReaderHarness((_path, options) => {
      if (options.method === 'POST') return prepare.promise;
      return { status: 200, data: { article: h.calls.length === 2 ? source : published, configuration: h.configuration } };
    });
    h.context.readArticle = (read, options) => readArticle(read, {
      ...options, wait: ms => { assert.equal(ms, 2000); polling.resolve(); return poll.promise; },
    });
    const opening = h.context.loadArticle('a', h.g, { savedLink });
    assert.deepEqual(h.calls.map(call => call.method), ['POST']);
    assert.equal(h.calls[0].headers['X-CSRF-Token'], 'csrf');
    assert.equal(h.calls[0].preferEarlySourceCheck, undefined);
    assert.equal(h.nodes.get('article-content').textContent, '');
    h.gracePeriod.resolve();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.nodes.get('article-content').textContent, 'Stored Ford procedure.');
    assert.equal(h.nodes.get('print').disabled, false);
    assert.equal(h.statuses.at(-1).message, 'Source text is ready.');
    assert.equal(h.nodes.get('reader-engine').textContent, 'US');
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].path, `/v1/catalog/vehicles/${h.configuration.id}/articles/a?region=US`);
    assert.equal(h.calls[1].headers, undefined);
    assert.equal(h.calls[1].preferEarlySourceCheck, true);
    prepare.resolve({ status: 202, retryAfterSeconds: 2, data: { configuration: h.configuration,
      article: { id: 'a', processing: { job_id: 'queued', state: 'fetching_source' } },
    } });
    await polling.promise;
    assert.equal(h.nodes.get('article-content').textContent, 'Stored Ford procedure.');
    assert.equal(h.calls.length, 2);
    poll.resolve();
    assert.equal(await opening, true);
    assert.equal(h.nodes.get('article-content').textContent, 'Published Ford procedure.');
    assert.equal(h.calls[2].preferEarlySourceCheck, undefined);
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET', 'GET']);
  }
});

test('a fast paid prepare cancels the optional check without adding a GET', async () => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Ready Ford procedure.' }]);
  const h = retainedReaderHarness((_path, options) => {
    assert.equal(options.method, 'POST');
    return { status: 200, data: { article, configuration: h.configuration } };
  });
  assert.equal(await h.context.loadArticle('a', h.g, { savedLink: true }), true);
  assert.equal(h.probeSignal.aborted, true);
  assert.equal(h.calls.length, 1);
  assert.equal(h.nodes.get('article-content').textContent, 'Ready Ford procedure.');
});

test('a retained paid index entry opens through one fresh scoped GET', async () => {
  const detail = deferredAuthOperation();
  const article = mediaArticle([{ type: 'paragraph', text: 'Checked Ford procedure.' }], [], {
    content_origin: 'canonical',
  });
  const h = retainedReaderHarness(() => detail.promise);
  h.context.access = 'owned';
  const opening = h.context.loadArticle('a', h.g, { preferRetained: true });
  assert.equal(h.nodes.get('article-content').textContent, '');
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].method, undefined);
  assert.equal(h.calls[0].path, `/v1/catalog/vehicles/${h.configuration.id}/articles/a?region=US`);
  detail.resolve({ status: 200, data: { article, configuration: h.configuration } });
  assert.equal(await opening, true);
  assert.equal(h.calls.length, 1);
  assert.equal(h.nodes.get('article-content').textContent, 'Checked Ford procedure.');
});

test('a stale retained index entry can start preparation once', async t => {
  const ready = mediaArticle([{ type: 'paragraph', text: 'Newly available Ford source.' }]);
  for (const failure of [null, { status: 503, code: 'CATALOG_SOURCE_UNAVAILABLE', retryable: true }]) {
    await t.test(failure?.code || 'readable body is absent', async () => {
      const h = retainedReaderHarness((_path, options) => {
        if (options.method === 'POST') return { status: 200, data: { article: ready, configuration: h.configuration } };
        if (failure) throw Object.assign(new Error('Stored article is unavailable.'), failure);
        return { status: 200, data: { article: { id: 'a' }, configuration: h.configuration } };
      });
      h.context.access = 'owned';
      assert.equal(await h.context.loadArticle('a', h.g, { preferRetained: true }), true);
      assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['GET', 'POST']);
      assert.equal(h.calls[1].headers['X-CSRF-Token'], 'csrf');
      assert.equal(h.nodes.get('article-content').textContent, 'Newly available Ford source.');
    });
  }
});

test('a retained index read respects revocation, response identity, and navigation', async t => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Protected Ford source.' }]);
  for (const scenario of ['revoked', 'different configuration', 'different article', 'navigated away']) {
    await t.test(scenario, async () => {
      const h = retainedReaderHarness(() => {
        if (scenario === 'revoked') throw Object.assign(new Error('Access was revoked.'), { status: 403, code: 'ENTITLEMENT_REVOKED' });
        if (scenario === 'navigated away') h.navigation.clear();
        return { status: 200, data: {
          article: scenario === 'different article' ? { ...article, id: routeArticle } : article,
          configuration: scenario === 'different configuration' ? { ...h.configuration, region: 'CA' } : h.configuration,
        } };
      });
      h.context.access = 'owned';
      const opening = h.context.loadArticle('a', h.g, { preferRetained: true });
      if (scenario === 'navigated away') await opening;
      else await assert.rejects(opening, scenario === 'revoked' ? /revoked/ : /does not match/);
      assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['GET']);
      assert.equal(h.nodes.get('article-content').textContent, '');
    });
  }
});

test('stored diagrams and tables are ready while actual source errors still show review', () => {
  for (const code of ['CATALOG_SOURCE_REPROJECTED', 'CATALOG_SOURCE_UNAVAILABLE']) {
    const h = articleMediaHarness();
    const article = mediaArticle([{ type: 'image', asset_id: 'figure' }], [{ id: 'figure', url: mediaURL('exact') }], {
      review_status: 'UNREVIEWED', processing: { state: 'needs_review', error_code: code, retryable: false },
    });
    const reprojected = code === 'CATALOG_SOURCE_REPROJECTED';
    h.context.session.state.mode = 'firebase';
    h.context.renderArticle(article, h.g);
    h.context.showArticleReadStatus('a', article);
    assert.equal(h.nodes.get('article-note').hidden, reprojected);
    assert.equal(h.nodes.get('print').disabled, false);
    assert.equal(h.statuses.at(-1).options.complete, true);
    assert.equal(h.statuses.at(-1).message, reprojected ? 'Stored source ready.' :
      'Stored source is readable. Article preparation needs review.');
    assert.equal(Boolean(h.statuses.at(-1).options.retry), !reprojected);
  }
});

test('a saved cold article reuses a started GET after its prepare returns 202', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const { readArticle } = await import('./workshop/article-read.mjs');
  const prepare = deferredAuthOperation(), early = deferredAuthOperation(), getStarted = deferredAuthOperation();
  const waiting = deferredAuthOperation(), wait = deferredAuthOperation();
  const stored = mediaArticle([{ type: 'paragraph', text: 'Retained procedure.' }]);
  let aborted = false;
  const h = retainedReaderHarness((path, options) => requestArticleJSON(path, {
    ...options,
    async fetcher(_url, { method, signal, headers }) {
      const marked = headers.Prefer.split(', ').includes('workshop-early-source-check');
      if (method === 'POST') {
        assert.equal(marked, false);
        return prepare.promise;
      }
      assert.equal(marked, true);
      if (h.calls.length !== 2) assert.fail('the ordinary poll should reuse the first GET');
      signal.addEventListener('abort', () => { aborted = true; early.reject(signal.reason); }, { once: true });
      getStarted.resolve();
      return early.promise;
    },
  }));
  h.context.readArticle = (read, options) => readArticle(read, {
    ...options, wait: ms => { assert.equal(ms, 2000); waiting.resolve(); return wait.promise; },
  });
  const loading = h.context.loadArticle('a', h.g, { savedLink: true });
  h.gracePeriod.resolve();
  await getStarted.promise;
  prepare.resolve(new Response(JSON.stringify({ configuration: h.configuration,
    article: { id: 'a', processing: { job_id: 'durable', state: 'fetching_source' } },
  }), { status: 202, headers: { 'Retry-After': '2' } }));
  await waiting.promise;
  assert.equal(h.probeSignal.aborted, false);
  assert.equal(aborted, false);
  early.resolve(new Response(JSON.stringify({ configuration: h.configuration, article: stored })));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.nodes.get('article-content').textContent, 'Retained procedure.');
  assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
  wait.resolve();
  assert.equal(await loading, true);
  assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
});

test('HTTP 200 headers suppress a second download while the prepare body is still streaming', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const article = mediaArticle([{ type: 'paragraph', text: 'Retained Ford procedure.' }]);
  for (const interruptBody of [false, true]) {
    const headers = deferredAuthOperation();
    let body;
    const h = retainedReaderHarness((path, options) => requestArticleJSON(path, {
      ...options,
      onResponseStatus(status) {
        options.onResponseStatus?.(status);
        headers.resolve(status);
      },
      fetcher: async (_url, { method }) => method === 'POST'
        ? new Response(new ReadableStream({ start(controller) { body = controller; } }))
        : new Response(JSON.stringify({ configuration: h.configuration, article })),
    }));
    const loading = h.context.loadArticle('a', h.g, { savedLink: true });
    assert.equal(await headers.promise, 200);
    assert.equal(h.probeSignal.aborted, true);
    h.gracePeriod.resolve();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST']);
    if (interruptBody) body.error(new TypeError('Connection closed while reading the body'));
    else {
      body.enqueue(new TextEncoder().encode(JSON.stringify({ configuration: h.configuration, article })));
      body.close();
    }
    assert.equal(await loading, true);
    assert.equal(h.nodes.get('article-content').textContent, 'Retained Ford procedure.');
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), interruptBody ? ['POST', 'GET'] : ['POST']);
  }
});

test('an older readable prepare response cannot replace a newer exact article', async () => {
  const prepare = deferredAuthOperation();
  const oldArticle = mediaArticle([{ type: 'paragraph', text: 'Earlier source.' }]);
  const published = mediaArticle([{ type: 'paragraph', text: 'Newer publication.' }], [], {
    content_origin: 'canonical', view_revision: 'published',
  });
  const h = retainedReaderHarness((_path, options) => options.method === 'POST'
    ? prepare.promise
    : { status: 200, data: { article: published, configuration: h.configuration } });
  const opening = h.context.loadArticle('a', h.g, { savedLink: true });
  h.gracePeriod.resolve();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.nodes.get('article-content').textContent, 'Newer publication.');
  prepare.resolve({ status: 200, data: { article: oldArticle, configuration: h.configuration } });
  assert.equal(await opening, true);
  assert.equal(h.nodes.get('article-content').textContent, 'Newer publication.');
  assert.equal(h.context.currentArticle.view_revision, 'published');
  assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
});

test('a readable prepare response cancels an unfinished optional read without waiting', async () => {
  const prepare = deferredAuthOperation(), detail = deferredAuthOperation(), reading = deferredAuthOperation();
  const article = mediaArticle([{ type: 'paragraph', text: 'Ready Ford procedure.' }]);
  const h = retainedReaderHarness((_path, options) => {
    if (options.method === 'POST') return prepare.promise;
    reading.resolve(options.signal);
    return detail.promise;
  });
  const opening = h.context.loadArticle('a', h.g);
  h.gracePeriod.resolve();
  const signal = await reading.promise;
  prepare.resolve({ status: 200, data: { article, configuration: h.configuration } });
  assert.equal(await opening, true);
  assert.equal(signal.aborted, true);
  detail.resolve({ status: 200, data: { article: { ...article, title: 'Late duplicate' }, configuration: h.configuration } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.nodes.get('article-title').textContent, article.title);
  assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
});

test('verified scheduling failures reuse a pending exact read and can recover without issuing a second POST', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const article = mediaArticle([{ type: 'paragraph', text: 'Stored Ford procedure.' }]);
  for (const slow of [false, true]) {
    const prepare = deferredAuthOperation(), detail = deferredAuthOperation(), reading = deferredAuthOperation();
    const h = retainedReaderHarness((path, options) => requestArticleJSON(path, {
      ...options,
      fetcher: async (_url, { method, headers }) => {
        const marked = headers.Prefer.split(', ').includes('workshop-early-source-check');
        if (method === 'POST') {
          assert.equal(marked, false);
          return prepare.promise;
        }
        assert.equal(marked, slow);
        reading.resolve();
        return detail.promise;
      },
    }));
    const opening = h.context.loadArticle('a', h.g, { savedLink: true });
    if (slow) {
      h.gracePeriod.resolve();
      await reading.promise;
    }
    prepare.resolve(new Response(JSON.stringify({ error: { code: 'CATALOG_SCHEDULING_UNAVAILABLE', retryable: true } }), { status: 503 }));
    await reading.promise;
    detail.resolve(new Response(JSON.stringify({ article, configuration: h.configuration })));
    assert.equal(await opening, true);
    assert.equal(h.probeSignal.aborted, true);
    assert.equal(h.nodes.get('article-content').textContent, 'Stored Ford procedure.');
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
  }
  const h = retainedReaderHarness(async (_path, options) => {
    assert.equal(options.method, 'POST');
    throw new CatalogRequestError('Preparation denied.', { status: 503, code: 'CATALOG_SCHEDULING_UNAVAILABLE' });
  });
  await assert.rejects(h.context.loadArticle('a', h.g), { status: 503 });
  assert.equal(h.calls.length, 1);
});

test('a fast paid prepare outage opens the exact stored source and its figure', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const source = mediaArticle([
    { type: 'paragraph', text: 'Stored Ford procedure.' },
    { type: 'image', asset_id: 'figure' },
  ], [{ id: 'figure', url: mediaURL('stored') }]);
  const outages = [
    [503, JSON.stringify({ error: { code: 'CATALOG_UNAVAILABLE', retryable: true } })],
    [502, '<html>Bad Gateway</html>'],
    [503, '<html>Service Unavailable</html>'],
    [504, '<html>Gateway Timeout</html>'],
  ];
  for (const savedLink of [false, true]) {
    for (const [status, body] of outages) {
      const h = retainedReaderHarness((path, options) => requestArticleJSON(path, {
        ...options,
        fetcher: async (_url, { method }) => method === 'POST'
          ? new Response(body, { status })
          : new Response(JSON.stringify({ article: source, configuration: h.configuration })),
      }));
      assert.equal(await h.context.loadArticle('a', h.g, { savedLink }), true);
      const detailPath = `/v1/catalog/vehicles/${h.configuration.id}/articles/a`;
      assert.deepEqual(h.calls.map(call => [call.method || 'GET', call.path]), [
        ['POST', `${detailPath}/prepare?region=US`], ['GET', `${detailPath}?region=US`],
      ]);
      assert.equal(h.probeSignal.aborted, true);
      assert.equal(h.nodes.get('article-kind').textContent, 'Stored source');
      const content = h.nodes.get('article-content');
      assert.match(content.textContent, /Stored Ford procedure/);
      assert.deepEqual(mediaIDs(content), ['figure']);
    }
  }
});

test('a paid prepare outage keeps exact read denials and ignores another article or vehicle', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const source = mediaArticle([{ type: 'paragraph', text: 'Protected procedure.' }]);
  for (const result of ['revoked', 'other article', 'other vehicle', 'other region']) {
    const h = retainedReaderHarness((path, options) => requestArticleJSON(path, {
      ...options,
      fetcher: async (_url, { method }) => {
        if (method === 'POST') {
          return new Response(JSON.stringify({ error: { code: 'CATALOG_UNAVAILABLE', retryable: true } }), { status: 503 });
        }
        if (result === 'revoked') {
          return new Response(JSON.stringify({ error: { code: 'ENTITLEMENT_REVOKED' } }), { status: 403 });
        }
        return new Response(JSON.stringify({
          article: result === 'other article' ? { ...source, id: 'b' } : source,
          configuration: {
            ...h.configuration,
            id: result === 'other vehicle' ? routeOrder : h.configuration.id,
            region: result === 'other region' ? 'CA' : h.configuration.region,
          },
        }));
      },
    }));
    const expected = result === 'revoked'
      ? { status: 403, code: 'ENTITLEMENT_REVOKED' }
      : { status: 503, code: 'CATALOG_UNAVAILABLE' };
    await assert.rejects(h.context.loadArticle('a', h.g), expected);
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
    assert.equal(h.nodes.get('article-content').textContent, '');
    assert.equal(h.nodes.get('print').disabled, true);
  }
});

test('the optional prepare read ignores wrong articles and vehicles', async () => {
  const source = mediaArticle([{ type: 'paragraph', text: 'Protected text.' }]);
  for (const wrong of ['article', 'region', 'configuration']) {
    const prepare = deferredAuthOperation();
    const h = retainedReaderHarness((_path, options) => {
      if (options.method === 'POST') return prepare.promise;
      const article = wrong === 'article' ? { ...source, id: 'b' } : source;
      const configuration = { ...h.configuration,
        ...(wrong === 'region' ? { region: 'CA' } : wrong === 'configuration' ? { id: routeOrder } : {}),
      };
      return { status: 200, data: { article, configuration } };
    });
    const opening = h.context.loadArticle('a', h.g);
    h.gracePeriod.resolve();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.calls.length, 2);
    assert.equal(h.nodes.get('article-content').textContent, '');
    prepare.resolve({ status: 200, data: { article: source, configuration: h.configuration } });
    assert.equal(await opening, true);
  }
});

test('a terminal denial suppresses the optional prepare read and clears any provisional article', async () => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Protected text.' }]);
  for (const denyingRequest of ['GET', 'POST']) {
    for (const status of [401, 403, 410]) {
      const prepare = deferredAuthOperation();
      const denial = new CatalogRequestError('Article denied.', { status });
      const h = retainedReaderHarness((_path, options) => {
        if (options.method === 'POST') return prepare.promise;
        if (denyingRequest === 'GET') throw denial;
        return { status: 200, data: { article, configuration: h.configuration } };
      });
      const opening = h.context.loadArticle('a', h.g, { savedLink: true });
      const denied = assert.rejects(opening, error => error === denial);
      h.gracePeriod.resolve();
      if (denyingRequest === 'POST') {
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(h.nodes.get('article-content').textContent, 'Protected text.');
        prepare.reject(denial);
      }
      await denied;
      assert.equal(h.nodes.get('article-content').textContent, '');
      assert.equal(h.nodes.get('print').disabled, true);
      if (denyingRequest === 'GET') {
        prepare.resolve({ status: 200, data: { article, configuration: h.configuration } });
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(h.nodes.get('article-content').textContent, '');
      }
      assert.deepEqual(h.calls.map(call => call.method || 'GET'), ['POST', 'GET']);
    }
  }
});

test('navigation cancels the optional prepare read before or during its GET', async () => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Stale text.' }]);
  for (const duringRead of [false, true]) {
    const prepare = deferredAuthOperation(), detail = deferredAuthOperation(), reading = deferredAuthOperation();
    const h = retainedReaderHarness((_path, options) => {
      if (options.method === 'POST') return prepare.promise;
      reading.resolve();
      return detail.promise;
    });
    const opening = h.context.loadArticle('a', h.g, { savedLink: true });
    if (duringRead) {
      h.gracePeriod.resolve();
      await reading.promise;
    }
    h.navigation.next();
    assert.equal(h.probeSignal.aborted, true);
    if (duringRead) detail.resolve({ status: 200, data: { article, configuration: h.configuration } });
    prepare.resolve({ status: 200, data: { article, configuration: h.configuration } });
    await opening;
    assert.equal(h.nodes.get('article-content').textContent, '');
    assert.deepEqual(h.calls.map(call => call.method || 'GET'), duringRead ? ['POST', 'GET'] : ['POST']);
  }
});

test('a retained original can check for a later rewrite without hiding the source or preparing it again', async () => {
  const original = mediaArticle([{ type: 'paragraph', text: 'Remove the cover.' }], [], {
    processing: { job_id: 'old', state: 'needs_review', retryable: false },
  });
  const published = mediaArticle([{ type: 'paragraph', text: 'Take off the cover.' }], [], {
    content_origin: 'canonical', view_revision: 'view-published',
  });
  const authorized = deferredAuthOperation();
  const reads = [];
  const h = articleRouteHarness('firebase', (path, options) => {
    reads.push([path, options.method || 'GET']);
    return reads.length === 1 ? { status: 200, data: { article: original } } : authorized.promise;
  });
  h.context.openArticle = (id, link, options) => {
    assert.equal(link, null);
    return h.context.loadArticle(id, h.navigation.next(), options);
  };
  await h.context.loadArticle('a', h.g);
  const ready = h.statuses.at(-1);
  assert.equal(ready.options.retryText, 'Check for an update');
  const checking = ready.options.retry();
  assert.equal(h.nodes.get('article-content').textContent, 'Remove the cover.');
  assert.equal(h.nodes.get('print').disabled, false);
  assert.deepEqual(reads, [
    ['/v1/catalog/vehicles/v/articles/a/prepare?region=US', 'POST'],
    ['/v1/catalog/vehicles/v/articles/a?region=US', 'GET'],
  ]);
  authorized.resolve({ status: 200, data: { article: published } });
  await checking;
  assert.equal(h.nodes.get('article-content').textContent, 'Take off the cover.');
  assert.equal(h.statuses.at(-1).options.retry, null);
});

test('the saved reader uses the authorized configuration and can fall back on an older response', async () => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Stored procedure.' }]);
  const configuration = { id: routeConfiguration, region: 'US', year: 2024, make: 'Example', model: 'Car', engine: '2.0', trim: 'Sport' };
  const identity = '2024 / Example / Car / 2.0 L / Sport';
  for (const [scopeFromResponse, rendered] of [[configuration, true], [undefined, false],
    [{ ...configuration, region: 'CA' }, false]]) {
    const h = articleRouteHarness('firebase', async () => ({ data: { article, configuration: scopeFromResponse } }));
    h.context.vehicle = { id: routeConfiguration, region: 'US' };
    h.context.quote = null;
    h.context.access = 'unknown';
    h.context.renderPurchase = () => { h.nodes.get('purchase-selection').textContent = `${identity} / US`; };
    assert.equal(await h.context.loadArticle('a', h.g, { savedLink: true }), rendered);
    assert.equal(h.context.currentArticle, rendered ? article : null);
    assert.equal(h.context.access, rendered ? 'owned' : 'unknown');
    if (rendered) {
      assert.equal(h.nodes.get('reader-vehicle').textContent, identity);
      assert.equal(h.nodes.get('reader-engine').textContent, 'US');
      assert.equal(h.nodes.get('purchase-selection').textContent, `${identity} / US`);
    }
  }
  for (const status of [404, 403]) {
    const error = Object.assign(new Error('Unavailable'), { status });
    const h = articleRouteHarness('firebase', async () => { throw error; });
    h.context.vehicle = { id: routeConfiguration, region: 'US' };
    const direct = h.context.loadArticle('a', h.g, { savedLink: true });
    if (status === 404) assert.equal(await direct, false);
    else await assert.rejects(direct, error);
    assert.equal(h.context.currentArticle, null);
  }
});

test('the same vehicle identity remains visible after its stored article is published', () => {
  const vehicle = {
    id: routeConfiguration, region: 'CA', year: 2025, make: 'Example', model: 'Wagon',
    engine: '3.0 L', trim: 'Touring', body_style: 'Estate', drivetrain: 'AWD',
  };
  const h = articleMediaHarness({ vehicle, quote: null });
  const source = mediaArticle([{ type: 'paragraph', text: 'Stored procedure.' }]);
  const identity = '2025 / Example / Wagon / 3.0 L / Touring / Estate / AWD';
  const quotedIdentity = '2025 Example Wagon Touring 3.0 L Estate AWD';
  h.nodes.get('purchase-selection').textContent = `${identity} / CA`;
  h.render(source);
  const sourceLabel = h.nodes.get('reader-vehicle').textContent;
  h.context.quote = { ...scopedQuoteFixture(), configuration_id: vehicle.id, region: vehicle.region, configuration_label: quotedIdentity };
  h.nodes.get('purchase-selection').textContent = `${quotedIdentity} / CA`;
  h.render({ ...source, content_origin: 'canonical', view_revision: 'published' });
  assert.equal(sourceLabel, identity);
  assert.equal(h.nodes.get('reader-vehicle').textContent, identity);
  assert.equal(h.nodes.get('reader-engine').textContent, 'CA');
  assert.equal(h.nodes.get('purchase-selection').textContent, `${quotedIdentity} / CA`);
});

test('a legacy reader keeps the selected paid order label when configuration fields are absent', async () => {
  const article = mediaArticle([{ type: 'paragraph', text: 'Stored procedure.' }]);
  const h = articleRouteHarness('firebase', async () => ({ status: 200, data: { article } }));
  h.context.vehicle = { id: routeConfiguration, region: 'CA' };
  runInNewContext(appSection('function selectOrderVehicle(', 'async function openPaidOrder('), h.context);
  h.context.selectOrderVehicle({
    configuration_id: routeConfiguration, region: 'CA', configuration_label: '2025 Example Wagon Touring 3.0 L',
  });
  assert.equal(await h.context.loadArticle('a', h.g), true);
  assert.equal(h.nodes.get('reader-vehicle').textContent, '2025 Example Wagon Touring 3.0 L');
  assert.equal(h.nodes.get('reader-engine').textContent, 'CA');
});

test('lost paid prepare recovers stored source or a durable job with scoped GETs only', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const configuration = { id: routeConfiguration, region: 'CA', engine: 'Synthetic 2.0 L' };
  const ready = mediaArticle([{ type: 'paragraph', text: 'Retained procedure.' }]);
  const pending = { id: 'a', processing: { job_id: 'committed-job', state: 'fetching_source' } };
  for (const [savedLink, detailReplies] of [
    [false, [{ article: ready }]],
    [true, [{ article: ready, configuration }]],
    [true, [{ article: pending, configuration }, { article: ready, configuration }]],
  ]) {
    const calls = [];
    let now = 0;
    const h = articleRouteHarness('firebase', (path, options) => requestArticleJSON(path, {
      ...options,
      fetcher: async (_url, { method, headers }) => {
        calls.push({ path, method, headers, signal: options.signal, startedAt: now });
        if (method === 'POST') {
          now += 300;
          throw new TypeError('The connection was reset after prepare');
        }
        const data = detailReplies.shift();
        assert.ok(data, 'only the initial recovery and durable job polling may read');
        now += 2;
        const response = data.article === pending
          ? { status: 202, headers: { 'Preference-Applied': 'workshop-short-source-check' } }
          : { status: 200 };
        return new Response(JSON.stringify(data), response);
      },
    }));
    const expectedCalls = detailReplies.length + 1;
    h.context.performance = { now: () => now };
    h.context.readArticle = (read, options) => readArticle(read, {
      ...options, now: () => now, wait: async (milliseconds) => { now += milliseconds; },
    });
    h.context.articlePath = id => `/v1/catalog/vehicles/${routeConfiguration}/articles/${id}`;
    h.context.vehicle = { id: routeConfiguration, region: 'CA' };
    h.context.quote = null;
    h.context.access = 'unknown';
    h.context.renderPurchase = () => { h.nodes.get('purchase-selection').textContent = h.context.vehicle.engine; };
    assert.equal(await h.context.loadArticle('a', h.g, { savedLink }), true);
    assert.equal(calls.length, expectedCalls);
    assert.deepEqual(calls.map(({ method }) => method), ['POST', ...Array(expectedCalls - 1).fill('GET')]);
    assert.deepEqual(calls.map(({ startedAt }) => startedAt), expectedCalls === 3 ? [0, 300, 452] : [0, 300]);
    assert.equal(calls[0].path, `/v1/catalog/vehicles/${routeConfiguration}/articles/a/prepare?region=CA`);
    assert.equal(calls[0].headers['X-CSRF-Token'], 'csrf');
    for (const call of calls.slice(1)) {
      assert.equal(call.path, `/v1/catalog/vehicles/${routeConfiguration}/articles/a?region=CA`);
      assert.equal(call.headers['X-CSRF-Token'], undefined);
    }
    assert.ok(calls.every(({ signal }) => signal === h.g.signal));
    assert.equal(h.nodes.get('article-content').textContent, 'Retained procedure.');
    if (savedLink) {
      assert.equal(h.context.access, 'owned');
      assert.equal(h.nodes.get('reader-vehicle').textContent, configuration.engine);
    }
  }
});

test('an interrupted prepare body can recover after success without a retry delay', async () => {
  const { requestArticleJSON } = await import('./workshop/catalog.mjs');
  const configuration = { id: routeConfiguration, region: 'US' };
  const article = mediaArticle([{ type: 'paragraph', text: 'Retained procedure.' }]);
  for (const [status, malformed, retryAfter, expected] of [
    [200, false, 0, null],
    [202, false, 0, null],
    [202, false, 7, { status: 0, code: 'INVALID_RESPONSE' }],
    [200, true, 0, { status: 0, code: 'INVALID_RESPONSE' }],
    [401, false, 0, { status: 401 }],
    [403, false, 0, { status: 403 }],
    [410, false, 0, { status: 410 }],
    [429, false, 7, { status: 429, retryAfterSeconds: 7 }],
    [503, false, 7, { status: 503, retryAfterSeconds: 7 }],
  ]) {
    const calls = [];
    const h = articleRouteHarness('firebase', (path, options) => requestArticleJSON(path, {
      ...options,
      fetcher: async (_url, { method }) => {
        calls.push([method, path]);
        if (method === 'GET') return new Response(JSON.stringify({ configuration, article }));
        const interruptedBody = malformed ? '{"article":' : new ReadableStream({
          start(controller) { controller.error(new TypeError('The response was truncated')); },
        });
        return new Response(interruptedBody, { status, headers: retryAfter ? { 'Retry-After': String(retryAfter) } : {} });
      },
    }));
    h.context.vehicle = configuration;
    h.context.renderPurchase = () => {};
    const loading = h.context.loadArticle('a', h.g, { savedLink: true });
    if (expected) await assert.rejects(loading, expected);
    else assert.equal(await loading, true);
    const prepare = ['POST', '/v1/catalog/vehicles/v/articles/a/prepare?region=US'];
    const detail = ['GET', '/v1/catalog/vehicles/v/articles/a?region=US'];
    assert.deepEqual(calls, expected ? [prepare] : [prepare, detail]);
    assert.equal(Boolean(h.context.currentArticle), !expected);
  }
});

test('paid prepare recovery requires a usable exact article and honors authoritative denial', async () => {
  const lost = Object.assign(new Error('Cannot reach AutoData.'), { status: 0, code: 'NETWORK_UNAVAILABLE' });
  const configuration = { id: routeConfiguration, region: 'US' };
  const article = mediaArticle([{ type: 'paragraph', text: 'Protected procedure.' }]);
  const detailError = status => Object.assign(new Error('Detail unavailable'), {
    status, code: status === 404 ? 'CATALOG_NOT_FOUND' : 'HTTP_ERROR',
  });
  for (const detail of [
    ...[401, 403, 410, 404, 429, 503].map(detailError),
    { status: 200, data: { article } },
    { status: 200, data: { article, configuration: { ...configuration, region: 'CA' } } },
    { status: 200, data: { article, configuration: { ...configuration, id: routeOrder } } },
    { status: 200, data: { article: { ...article, id: 'b' }, configuration } },
    { status: 200, data: { article: { id: 'a' }, configuration } },
    { status: 202, data: { article: { id: 'a' }, configuration } },
  ]) {
    let calls = 0;
    const h = articleRouteHarness('firebase', async () => {
      if (++calls === 1) throw lost;
      if (detail instanceof Error) throw detail;
      return detail;
    });
    h.context.vehicle = configuration;
    const expected = [401, 403, 404, 410].includes(detail.status) ? detail : lost;
    await assert.rejects(h.context.loadArticle('a', h.g, { savedLink: true }), error => error === expected);
    assert.equal(calls, 2);
    assert.equal(h.context.currentArticle, null);
    assert.equal(h.nodes.get('print').disabled, true);
    if (detail.status === 404) assert.equal(h.nodes.get('article-title').textContent, 'Article unavailable');
  }
});

test('only a current paid transport failure can start a prepare recovery GET', async () => {
  const lost = Object.assign(new Error('Cannot reach AutoData.'), { status: 0, code: 'NETWORK_UNAVAILABLE' });
  for (const [mode, demo, error] of [
    ['local', false, lost], ['firebase', true, lost],
    ...[401, 403, 410, 429, 503].map(status => ['firebase', false, Object.assign(new Error('Prepare unavailable'),
      { status, code: 'NETWORK_UNAVAILABLE' })]),
  ]) {
    let calls = 0;
    const h = articleRouteHarness(mode, async () => { calls++; throw error; }, !demo, demo);
    await assert.rejects(h.context.loadArticle('a', h.g), failure => failure === error);
    assert.equal(calls, 1);
  }
  for (const duringRecovery of [false, true]) {
    const inflight = deferredAuthOperation(), detailStarted = deferredAuthOperation();
    const methods = [];
    const h = articleRouteHarness('firebase', async (_path, options) => {
      methods.push(options.method || 'GET');
      if (!duringRecovery) return inflight.promise;
      if (options.method === 'POST') throw lost;
      detailStarted.resolve();
      return inflight.promise;
    });
    const opening = h.context.loadArticle('a', h.g);
    if (duringRecovery) await detailStarted.promise;
    h.navigation.next();
    if (duringRecovery) {
      inflight.resolve({ status: 200, data: { article: mediaArticle([{ type: 'paragraph', text: 'Obsolete.' }]) } });
      await opening;
    } else {
      inflight.reject(lost);
      await assert.rejects(opening, error => error === lost);
    }
    assert.equal(h.g.signal.aborted, true);
    assert.equal(h.context.currentArticle, null);
    assert.deepEqual(methods, duringRecovery ? ['POST', 'GET'] : ['POST']);
  }
});

test('open demo reads an article with GET and no session or checkout', async () => {
  const calls = [], article = mediaArticle([{ type: 'paragraph', text: 'Stored procedure.' }]);
  const h = articleRouteHarness('firebase', async (path, options) => {
    calls.push({ path, options });
    return { data: { article } };
  }, false, true);
  await h.context.loadArticle('a', h.g);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/v1/catalog/vehicles/v/articles/a?region=US&demo=1');
  assert.equal(calls[0].options.method, undefined);
});

for (const mode of ['local', 'firebase', undefined, null, 'LOCAL', 'other']) {
  test(`article opening mode ${String(mode)} uses only its authorized real route`, async () => {
    const calls = [], article = mediaArticle([{ type: 'paragraph', text: 'Stored procedure.' }]);
    const h = articleRouteHarness(mode, async (path, options) => { calls.push({ path, options }); return { data: { article } }; });
    h.context.vehicle = { ...h.context.vehicle, make: 'Example', model: 'Car', engine: '2.0 L' };
    await h.context.loadArticle('a', h.g);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].path, mode === 'local' ? '/v1/catalog/vehicles/v/articles/a?region=US' : '/v1/catalog/vehicles/v/articles/a/prepare?region=US');
    assert.equal(calls[0].options.method || 'GET', mode === 'local' ? 'GET' : 'POST');
    assert.equal(calls[0].options.signal, h.g.signal);
    if (mode === 'local') {
      assert.equal(calls[0].options.body, undefined);
      assert.equal(calls[0].options.headers, undefined);
    } else {
      assert.deepEqual(Object.keys(calls[0].options.body), []);
      assert.equal(calls[0].options.headers['X-CSRF-Token'], 'csrf');
    }
    assert.match(h.nodes.get('article-content').textContent, /Stored procedure/);
    assert.equal(h.context.currentArticle, article);
    assert.equal(h.nodes.get('reader-vehicle').textContent, 'Example / Car / 2.0 L');
    assert.equal(h.nodes.get('reader-engine').textContent, 'US');
  });
}

test('local mode preserves actual GET polling responses and session authorization', async () => {
  const calls = [], ready = mediaArticle([{ type: 'paragraph', text: 'Stored result.' }]);
  const h = articleRouteHarness('local', async (path, options) => {
    calls.push({ path, options });
    return { data: { article: calls.length === 1 ? { ...ready, processing: { job_id: 'job', state: 'running' } } : ready } };
  });
  await h.context.loadArticle('a', h.g);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(c => c.path === '/v1/catalog/vehicles/v/articles/a?region=US' && !c.options.method));
  assert.equal(h.context.currentArticle, ready);
  const signedOut = articleRouteHarness('local', () => assert.fail('local mode does not grant a session'), false);
  await signedOut.context.loadArticle('a', signedOut.g);
  assert.equal(signedOut.context.currentArticle, null);
});

for (const mode of ['local', 'firebase']) {
  test(`article ${mode} route rejects canceled reads and cannot publish obsolete responses`, async () => {
    for (const reject of [false, true]) {
      let resolveRead, rejectRead;
      const h = articleRouteHarness(mode, () => new Promise((resolve, fail) => { resolveRead = resolve; rejectRead = fail; }));
      const pending = h.context.loadArticle('a', h.g);
      h.navigation.clear();
      if (reject) rejectRead(new DOMException('canceled', 'AbortError'));
      else resolveRead({ data: { article: mediaArticle([{ type: 'paragraph', text: 'Obsolete content.' }]) } });
      if (reject) await assert.rejects(pending, { name: 'AbortError' });
      else await pending;
      assert.equal(h.context.currentArticle, null);
      assert.doesNotMatch(h.nodes.get('article-content').textContent, /Obsolete/);
    }
  });
}

const legacyIntroSteps = [
  { number: 1, heading: 'Set the marker', instructions: ['Turn the blue training dial to the square marker.'], image_ids: ['owned-diagram'] },
  { number: 2, heading: 'Confirm the marker', instructions: ['Check that the orange marker sits beside the blue square.'] },
];
const legacyIntroText = 'Wholly authored synthetic training instructions for a fictional bench. This fixture describes no real vehicle.';
function legacyIntroArticle(body, changes = {}) {
  return mediaArticle([], [{ id: 'owned-diagram', url: mediaURL('owned'), alt: 'Authored training diagram' }], {
    body, steps: structuredClone(legacyIntroSteps), ...changes,
  });
}
const occurrences = (text, part) => text.split(part).length - 1;

test('legacy introduction stays visible once before ordered usable steps and their image', () => {
  const article = legacyIntroArticle(legacyIntroText), before = JSON.stringify(article);
  const h = articleMediaHarness(), parent = h.content(article), text = parent.textContent;
  assert.equal(occurrences(text, legacyIntroText), 1);
  assert.ok(text.indexOf(legacyIntroText) < text.indexOf(legacyIntroSteps[0].heading));
  assert.ok(text.indexOf(legacyIntroSteps[0].instructions[0]) < text.indexOf(legacyIntroSteps[1].heading));
  for (const step of legacyIntroSteps) {
    assert.equal(occurrences(text, step.heading), 1);
    assert.equal(occurrences(text, step.instructions[0]), 1);
  }
  assert.deepEqual(mediaTags(parent), ['p', 'section', 'section']);
  assert.deepEqual(mediaIDs(parent), ['owned-diagram']);
  assert.equal(JSON.stringify(article), before, 'presentation cannot change retained source or projections');
});

test('legacy numbered replay retains leading headings and callouts without repeated steps', () => {
  const body = 'TRAINING\n\nAuthored introductory note.\n\nNOTE: Keep the bench clear. 1.Set the marker Turn the blue training dial to the square marker. 2.Confirm the marker Check that the orange marker sits beside the blue square.';
  const parent = articleMediaHarness().content(legacyIntroArticle(body));
  assert.deepEqual(mediaTags(parent), ['h3', 'p', 'aside', 'section', 'section']);
  assert.match(parent.textContent, /TRAININGAuthored introductory note\.NoteKeep the bench clear\./i);
  for (const step of legacyIntroSteps) assert.equal(occurrences(parent.textContent, step.instructions[0]), 1);
  assert.deepEqual(mediaIDs(parent), ['owned-diagram']);
});

for (const instructionsOnly of [false, true]) {
  for (const intro of ['', legacyIntroText]) {
    test(`legacy unnumbered complete replay ${instructionsOnly ? 'instructions' : 'headings'} keeps only ${intro ? 'distinct intro' : 'steps'}`, () => {
      const replay = legacyIntroSteps.flatMap(step => [...(instructionsOnly ? [] : [step.heading]), ...step.instructions]).join('\n');
      const article = legacyIntroArticle([intro, replay].filter(Boolean).join('\n\n'));
      const presentation = articlePresentation(article), parent = articleMediaHarness().content(article);
      assert.equal(presentation.introBlocks.length, intro ? 1 : 0);
      if (intro) assert.equal(occurrences(parent.textContent, intro), 1);
      for (const step of legacyIntroSteps) {
        assert.equal(occurrences(parent.textContent, step.heading), 1);
        assert.equal(occurrences(parent.textContent, step.instructions[0]), 1);
      }
    });
  }
}

test('legacy whitespace-only replay differences normalize without changing retained introduction', () => {
  const replay = legacyIntroSteps.flatMap(step => [step.heading, ...step.instructions]).join('\t\r\n');
  const presentation = articlePresentation(legacyIntroArticle('Distinct intro.\n\n'+replay.replaceAll(' ', '\u00a0')));
  assert.deepEqual(presentation.introBlocks, [{ type: 'paragraph', text: 'Distinct intro.' }]);
});

test('legacy numbered step projections from normalization do not create an introduction', () => {
  const steps = [{ action: 'Set the marker', instructions: ['Turn the blue dial.'] }, { action: 'Confirm the marker', instructions: ['Observe the orange marker.'] }];
  const body = steps.map((step, i) => `${i + 1}. ${step.action}\n${step.instructions.join('\n')}`).join('\n');
  assert.deepEqual(articlePresentation({ body, steps }).introBlocks, []);
});

test('legacy partial or differently punctuated unnumbered overlap is preserved without fuzzy deletion', () => {
  for (const body of ['Turn the blue training dial to the square marker.', 'turn the blue training dial to the square marker. Check that the orange marker sits beside the blue square.', 'Turn the blue training dial to the square marker! Check that the orange marker sits beside the blue square.']) {
    const presentation = articlePresentation(legacyIntroArticle(body));
    assert.equal(presentation.introBlocks.map(block => block.text).join(' '), body);
  }
});

test('legacy intro decimals and unrelated numbers remain text; action wins over stale heading in replay', () => {
  const steps = [{ action: 'Set marker', heading: 'Old heading', instructions: ['Use 1.5 turns.'] }];
  assert.deepEqual(articlePresentation({ body: 'Model CTX1.5 reference. Set marker Use 1.5 turns.', steps }).introBlocks,
    [{ type: 'paragraph', text: 'Model CTX1.5 reference.' }]);
  assert.equal(articlePresentation({ body: 'Old heading Use 1.5 turns.', steps }).introBlocks[0].text, 'Old heading', 'distinct stale heading is retained while exact instruction replay is removed');
});

test('legacy introduction never overrides document authority or changes partial-step and empty-body fallbacks', () => {
  const article = legacyIntroArticle(legacyIntroText, { document: { blocks: [{ type: 'paragraph', text: 'Authoritative ordered text.' }] } });
  assert.deepEqual(articlePresentation(article).introBlocks, []);
  const authoritative = articleMediaHarness().content(article);
  assert.equal(authoritative.textContent, 'Authoritative ordered text.');
  assert.deepEqual(mediaIDs(authoritative), []);
  const incomplete = articlePresentation({ body: 'Retain entire fallback.', steps: [legacyIntroSteps[0], {}] });
  assert.deepEqual(incomplete.introBlocks, []);
  assert.deepEqual(incomplete.steps, []);
  assert.deepEqual(incomplete.blocks, [{ type: 'paragraph', text: 'Retain entire fallback.' }]);
  const empty = articleMediaHarness().content(legacyIntroArticle(''));
  assert.deepEqual(mediaTags(empty), ['section', 'section']);
});

test('legacy introduction HTML-like text is inert through actual DOM construction', () => {
  const attack = '<img src=x onerror="globalThis.introExecuted=true"> Authored note.';
  const parent = articleMediaHarness().content(legacyIntroArticle(attack));
  assert.equal(parent.children[0].tagName, 'p');
  assert.equal(parent.children[0].textContent, attack);
  assert.equal(parent.children[0].children.length, 0);
  assert.deepEqual(mediaIDs(parent), ['owned-diagram'], 'only the real structured-step illustration is present');
  assert.equal(globalThis.introExecuted, undefined);
});

for (const [name, body] of [
  ['unrelated warranty list', 'Owned reference. 1. Warranty covers the fictional dial. 2. Storage requires a dry training bench.'],
  ['partial procedure', 'Owned reference. 1. Set the marker Turn the blue training dial to the square marker.'],
  ['changed ordinal', 'Owned reference. 7. Set the marker Turn the blue training dial to the square marker. 8. Confirm the marker Check that the orange marker sits beside the blue square.'],
  ['reordered procedure', 'Owned reference. 2. Confirm the marker Check that the orange marker sits beside the blue square. 1. Set the marker Turn the blue training dial to the square marker.'],
  ['changed instruction', 'Owned reference. 1. Set the marker Turn the blue training dial to a different marker. 2. Confirm the marker Check that the orange marker sits beside the blue square.'],
]) {
  test(`legacy unmatched numbered ${name} retains complete text and ordinals in actual renderer`, () => {
    const article = legacyIntroArticle(body), before = JSON.stringify(article);
    const intro = articlePresentation(article).introBlocks;
    assert.ok(intro.every(block => block.type !== 'step'), 'parts-only legacy steps cannot reach structured renderBlocks');
    const parent = articleMediaHarness().content(article), text = parent.textContent;
    assert.ok(text.includes(body), 'all unmatched numbered body text remains visible verbatim');
    assert.ok(text.indexOf(body) < text.lastIndexOf(legacyIntroSteps[0].heading));
    assert.equal(parent.children.filter(node => node.tagName === 'section').length, 2, 'only actual structured steps become procedure sections');
    assert.equal(JSON.stringify(article), before);
  });
}

test('legacy numbered instructions-only exact replay retains introduction and renders instructions once', () => {
  const body = `${legacyIntroText} 1. ${legacyIntroSteps[0].instructions[0]} 2. ${legacyIntroSteps[1].instructions[0]}`;
  const parent = articleMediaHarness().content(legacyIntroArticle(body));
  assert.equal(occurrences(parent.textContent, legacyIntroText), 1);
  for (const step of legacyIntroSteps) assert.equal(occurrences(parent.textContent, step.instructions[0]), 1);
});

const localOpaqueImagePath = token => `/v1/catalog/images/${token}`;
const localOpaqueImageToken = 'AbCd0123_-'.repeat(15);
test('local opaque image URLs require explicit local mode and retain strict URL boundaries', () => {
  const origin = 'https://cars.example', path = localOpaqueImagePath(localOpaqueImageToken);
  assert.equal(localImageURL(path, origin, { authMode: 'local' }), origin + path);
  for (const authMode of [undefined, null, 'firebase', 'LOCAL', true])
    assert.equal(localImageURL(path, origin, { authMode }), null);
  for (const authMode of ['local', 'firebase', undefined]) {
    assert.equal(localImageURL('/v1/catalog/images/v2.opaque', origin, { authMode }), origin + '/v1/catalog/images/v2.opaque');
    for (const value of [
      'https://cars.example.attacker.test' + path, 'https://other.cars.example' + path,
      'http://cars.example' + path, 'https://cars.example:444' + path,
      'https://user:pass@cars.example' + path, path + '?src=external', path + '#fragment',
      '/other/' + localOpaqueImageToken, path + '/extra', path + '.png', path + '=',
      '/v1/catalog/images/' + 'a'.repeat(37), '/v1/catalog/images/' + 'a'.repeat(41),
      '/v1/catalog/images/' + 'a'.repeat(6001), '/v1/catalog/images/%41' + localOpaqueImageToken,
      'data:image/png;base64,YQ==', 'javascript:alert(1)', path + '\n',
    ]) assert.equal(localImageURL(value, origin, { authMode }), null, value);
  }
});

test('local referenced step images render and retry with opaque tokens without broad compatibility', () => {
  const image = { id: 'local-image', url: localOpaqueImagePath(localOpaqueImageToken), alt: 'Stored diagram' };
  const article = mediaArticle([], [image], { steps: [{ number: 1, action: 'Inspect', instructions: ['Inspect the stored diagram.'], image_ids: ['local-image'] }] });
  for (const mode of ['local', 'firebase', undefined]) {
    const h = articleMediaHarness({ session: { state: { mode } } });
    const parent = h.render(article);
    const images = mediaDescendants(parent, 'img');
    assert.equal(images.length, mode === 'local' ? 1 : 0);
    if (mode === 'local') {
      assert.equal(images[0].src, 'https://cars.example' + image.url);
      assert.equal(images[0].referrerPolicy, 'no-referrer');
      const replacement = localOpaqueImagePath('ZyXw9876_-'.repeat(15));
      assert.equal(h.context.retryImage(images[0], [{ ...image, url: replacement }]), true);
      assert.equal(images[0].src, 'https://cars.example' + replacement);
      h.navigation.clear();
      void h.context.renewMedia(h.g, images[0]);
      assert.equal(images[0].src, 'https://cars.example' + replacement);
    }
  }
});

// Shared with Go search tests; these are hand-authored visible/hidden terms,
// checked against current articlePresentation and the actual reader DOM harness.
const searchRendererFixtures = JSON.parse(readFileSync(new URL('./testdata/workshop-search-renderer.json', import.meta.url), 'utf8'));
for (const fixture of searchRendererFixtures) test(`search renderer fixture: ${fixture.name}`, () => {
  const article = mediaArticle([], [], fixture.article);
  const presentation = articlePresentation(article);
  assert.equal(presentation.introBlocks.length > 0, fixture.has_intro);
  const parent = articleMediaHarness().render(article);
  const rendered = parent.textContent;
  const lower = rendered.toLowerCase();
  const imageAlt = mediaDescendants(parent, 'img').map(image => image.alt).join(' ').toLowerCase();
  for (const query of fixture.visible_queries) {
    for (const word of query.toLowerCase().split(/\s+/)) assert.ok(lower.includes(word), `${query} is visible`);
  }
  for (const query of fixture.accessible_queries || []) assert.ok(imageAlt.includes(query.toLowerCase()), `${query} is an image alternative`);
  for (const query of fixture.hidden_queries) assert.ok(!lower.includes(query.toLowerCase()) && !imageAlt.includes(query.toLowerCase()), `${query} remains hidden`);
  for (const phrase of fixture.once) assert.equal(rendered.split(phrase).length - 1, 1, `${phrase} renders once`);
});

test('source and canonical viewers retain nested list and table cell content', () => {
  for (const origin of ['source', 'canonical']) {
    const h = articleMediaHarness();
    const parent = h.render(mediaArticle([
      { type: 'unordered_list', items: ['Legacy item', { text: 'Inspect', blocks: [
        { type: 'ordered_list', items: ['Nested operation'] },
        { type: 'image', asset_id: 'list', alt: 'Inspect', caption: 'List detail' },
      ] }] },
      { type: 'table', caption: 'Table title', columns: [{ text: 'Diagram' }],
        rows: [{ cells: [{ text: 'Cell detail', blocks: [
          { type: 'image', asset_id: 'cell', alt: 'View', caption: 'Cell view' },
          { type: 'paragraph', text: 'Nested cell instruction' },
        ] }] }], images: [{ asset_id: 'cell' }] },
      { type: 'link', text: 'Related manual', href: 'https://provider.invalid/private.pdf' },
    ], ['cell', 'list'].map(id => ({ id, url: mediaURL(id) })), { content_origin: origin }));
    assert.deepEqual(mediaIDs(parent), ['list', 'cell']);
    assert.deepEqual(mediaIDs(mediaDescendants(parent, 'td')[0]), ['cell']);
    assert.equal(mediaDescendants(parent, 'ol')[0].textContent, 'Nested operation');
    assert.deepEqual(mediaDescendants(parent, 'figcaption').map(node => node.textContent), ['List detail', 'Cell view']);
    assert.equal(mediaDescendants(parent, 'th')[0].textContent, 'Diagram');
    assert.match(parent.textContent, /Nested cell instruction/);
    assert.match(parent.textContent, /Related manual/);
    assert.equal(mediaDescendants(parent, 'a').length, 0);
  }
});

test('source and published viewers place each occurrence of a shared retained PDF figure', () => {
  const diagrams = [{ id: 'shared', url: mediaURL('shared-pdf') }];
  const blocks = [
    { type: 'paragraph', text: 'Open the pump cover.' },
    { type: 'image', block_id: 'page-1-figure', asset_id: 'shared', alt: 'Figure from page 1' },
    { type: 'paragraph', text: 'Inspect the seal.' },
    { type: 'image', block_id: 'page-2-figure', asset_id: 'shared', alt: 'Figure from page 2' },
    { type: 'paragraph', text: 'Install the replacement.' },
  ];
  for (const content_origin of ['source', 'canonical']) {
    const parent = articleMediaHarness().content(mediaArticle(blocks, diagrams, { content_origin }));
    assert.deepEqual(mediaTags(parent), ['p', 'figure', 'p', 'figure', 'p']);
    const occurrences = mediaDescendants(parent, 'img');
    assert.deepEqual(occurrences.map(image => image.alt), ['Figure from page 1', 'Figure from page 2']);
    assert.equal(occurrences[0].src, occurrences[1].src);
  }
});

test('first publication keeps the approved source panel and its cited focus', async () => {
  const review = { available: true, url: mediaSourceURL };
  const figure = { type: 'image', block_id: 'pinned-figure', asset_id: 'drawing', alt: 'Original drawing' };
  const images = [{ id: 'drawing', url: mediaURL('original') }];
  let requests = 0;
  const h = articleMediaHarness({ requestJSON: async () => {
    requests++;
    return { source: { url: mediaSourceURL }, document: { blocks: [figure] }, images };
  } });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Original instructions' }], [], { source_review: review }));
  await h.context.loadSource(mediaSourceURL, h.g, figure.block_id);
  const frame = h.nodes.get('source-review-frame'), cited = mediaDescendants(frame, 'figure')[0];
  assert.equal(cited.focusCalls, 1);

  const content = h.render(mediaArticle([{ type: 'paragraph', text: 'Published procedure' }], [], {
    source_review: review, view_revision: 'view-2', content_origin: 'canonical',
  }));
  assert.equal(content.textContent, 'Published procedure');
  assert.equal(frame.hidden, false);
  assert.equal(frame.children[0], cited);
  assert.equal(cited.focusCalls, 1);
  assert.equal(h.nodes.get('source-review-meta').textContent, 'Stored source loaded.');
  assert.equal(requests, 1);

  h.render(mediaArticle([{ type: 'paragraph', text: 'Published procedure' }], [], {
    source_review: { available: false }, view_revision: 'view-2', content_origin: 'canonical',
  }));
  assert.equal(frame.hidden, true);
  assert.equal(frame.children.length, 0);
});

test('a source review can finish during publication while its approved pin stays the same', async () => {
  const pending = deferredAuthOperation();
  const review = { available: true, url: mediaSourceURL };
  const h = articleMediaHarness({ requestJSON: () => pending.promise });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Original' }], [], { source_review: review }));
  const load = h.context.loadSource(mediaSourceURL, h.g);
  h.render(mediaArticle([{ type: 'paragraph', text: 'Published' }], [], {
    view_revision: 'view-2', content_origin: 'canonical', source_review: review,
  }));
  assert.equal(h.nodes.get('source-review-load').disabled, true);
  pending.resolve({ source: { url: mediaSourceURL }, document: { blocks: [{ type: 'paragraph', text: 'Original' }] } });
  await load;
  assert.equal(h.nodes.get('source-review-frame').hidden, false);
  assert.equal(h.nodes.get('source-review-frame').textContent, 'Original');
  assert.equal(h.nodes.get('source-review-load').disabled, false);
});

test('an in-flight source figure repair uses the new publication anchor for the retained panel', async () => {
  const stale = deferredAuthOperation();
  const review = { available: true, url: mediaSourceURL };
  const figure = { type: 'image', asset_id: 'drawing', alt: 'Original drawing' };
  const source = token => ({
    source: { url: mediaSourceURL },
    document: { blocks: [figure] },
    images: [{ id: 'drawing', url: mediaURL(token) }],
  });
  const requests = [];
  const h = articleMediaHarness({ requestJSON: async url => {
    requests.push(url);
    if (requests.length === 2) return stale.promise;
    return source(requests.length === 1 ? 'original' : 'published-anchor');
  } });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Original' }], [], { source_review: review }));
  await h.context.loadSource(mediaSourceURL, h.g);
  const frame = h.nodes.get('source-review-frame'), img = mediaDescendants(frame, 'img')[0];
  const repair = h.context.renewMedia(h.g, img);
  assert.equal(requests.length, 2);
  h.render(mediaArticle([{ type: 'paragraph', text: 'Published' }], [], {
    view_revision: 'view-2', content_origin: 'canonical', source_review: review,
  }));
  stale.resolve(source('stale-anchor'));
  await repair;
  assert.equal(mediaDescendants(frame, 'img')[0], img);
  assert.equal(img.src, 'https://cars.example' + mediaURL('published-anchor'));
  assert.equal(requests.length, 3);
});

test('a late stored-source response cannot reopen the panel after the approved pin changes', async () => {
  const pending = deferredAuthOperation();
  const h = articleMediaHarness({ requestJSON: () => pending.promise });
  h.render(mediaArticle([{ type: 'paragraph', text: 'Source displayed' }], [], {
    source_review: { available: true, url: mediaSourceURL },
  }));
  const load = h.context.loadSource(mediaSourceURL, h.g);
  assert.equal(h.nodes.get('source-review-load').disabled, true);
  h.render(mediaArticle([{ type: 'paragraph', text: 'Workshop revision' }], [], {
    view_revision: 'view-2', content_origin: 'canonical',
    source_review: { available: true, url: mediaSourceURL.replace('11111111-', '22222222-') },
  }));
  pending.resolve({
    source: { url: mediaSourceURL },
    document: { blocks: [{ type: 'paragraph', text: 'Old source' }] },
  });
  await load;
  assert.equal(h.nodes.get('source-review-frame').hidden, true);
  assert.equal(h.nodes.get('source-review-frame').textContent, '');
  assert.equal(h.nodes.get('source-review-load').disabled, false);
  assert.equal(h.context.sourceURL, '');
});

test('a stale media renewal cannot clear a newly opened pinned source', async () => {
  const pending = deferredAuthOperation(), renewalRequested = deferredAuthOperation();
  const newerURL = mediaSourceURL.replace('11111111-', '22222222-');
  const calls = [];
  const source = (url, label) => ({
    source: { url },
    document: { blocks: [{ type: 'callout', text: label, images: [{ asset_id: 'stored' }] }] },
    images: [{ id: 'stored', url: mediaURL(label) }],
  });
  const h = articleMediaHarness({
    requestArticleJSON: async () => renewedArticle(),
    requestJSON: async url => {
      calls.push(url);
      if (calls.length === 2) {
        renewalRequested.resolve();
        return pending.promise;
      }
      return url === newerURL ? source(newerURL, 'new-source') : source(mediaSourceURL, 'old-source');
    },
  });
  h.render(renewalFixture());
  await h.context.loadSource(mediaSourceURL, h.g);
  const frame = h.nodes.get('source-review-frame');
  const renewal = h.context.renewMedia(h.g, mediaDescendants(frame, 'img')[0]);
  await renewalRequested.promise;
  assert.equal(calls.length, 2);
  await h.context.loadSource(newerURL, h.g);
  pending.reject(Object.assign(new Error('Expired source'), { status: 403 }));
  await renewal;
  assert.match(frame.textContent, /new-source/);
  assert.equal(mediaDescendants(frame, 'img')[0].src, 'https://cars.example/v1/catalog/images/v2.new-source');
  assert.equal(h.context.sourceURL, 'https://cars.example' + newerURL);
  assert.equal(h.g.current(), true);
  assert.deepEqual(h.shows, []);
});
