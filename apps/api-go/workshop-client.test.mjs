import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { NavigationGeneration, processingArticle, readableArticle } from './workshop/article-read.mjs';
import { purchaseConfiguration, uuid, validQuote, validScope } from './workshop/commerce.mjs';
import { articlePresentation, configurationLabel, filterArticles, hasSourceReference, legacyArticleBlocks, localImageURL, readCollection, requestJSON, sourceReferenceURL } from './workshop/catalog.mjs';
import { LOAD_STAGES, loadingProgress } from './workshop/progress.mjs';

test('loading progress uses fixed ordered stages and caps incomplete hydration', () => {
  assert.deepEqual(LOAD_STAGES.map(stage => stage.key), ['year', 'make', 'model', 'configuration', 'articles', 'article']);
  assert.equal(loadingProgress('make', { complete: true }).complete, true);
  const partial = loadingProgress('make', { attempt: 40, attempts: 40, hydrating: true });
  assert.equal(partial.step, 2);
  assert.equal(partial.total, 6);
  assert.equal(partial.percent, null);
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
  assert.equal(configurationLabel({ engine: '2.0', trim: 'Base' }), '2.0 / Base');
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
test('library requires nullable cursor and accepts revoked never-granted tombstone', async () => {
  const { validLibrary } = await import('./workshop/commerce.mjs');
  const item = { ...scope, library_item_id: orderID, label: 'Vehicle', access_state: 'revoked', granted_at: null };
  for (const next_cursor of [null, '', 'opaque+/=']) assert.equal(validLibrary({ version: 'v1', items: [item], next_cursor }), true);
  for (const bad of [{ version: 'v1', items: [] }, { version: 'v1', items: [], next_cursor: 4 }, { version: 'v1', items: [{ ...item, access_state: 'paid' }], next_cursor: null }]) assert.equal(validLibrary(bad), false);
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
test('session bootstrap validates cookie authority and never loads SDK for existing session', async () => {
  const { createSession } = await import('./workshop/auth.mjs'); let sdkLoads=0;const calls=[];
  const session=createSession({request:async path=>{calls.push(path);return path==='/auth/config'?{version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'fixture',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123:web:abc'}}:{authenticated:true,roles:['dataset_viewer'],expires_at:'2099-01-01T00:00:00Z',csrf_token:'memory-only'};},loadSDK:async()=>{sdkLoads++;}});
  await session.bootstrap();assert.equal(session.state.authenticated,true);assert.equal(sdkLoads,0);assert.deepEqual(calls,['/auth/config','/auth/session']);
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

async function sessionPreparationHarness({ authenticated = false, persistence = async () => {}, constructProvider = () => {}, popup } = {}) {
  const { createSession } = await import('./workshop/auth.mjs');
  const calls = { loads: 0, initializations: 0, providers: 0, persistence: 0, popups: 0, signouts: 0, exchanges: 0 };
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
      assert.equal(forceRefresh, true);
      return { token: 'synthetic-token', authTime: new Date().toISOString() };
    },
    signOut: async actualAuth => { assert.equal(actualAuth, auth); calls.signouts++; },
  };
  const session = createSession({
    loadSDK: async () => { calls.loads++; return sdk; },
    onChange: state => changes.push({ ...state, providerPresent: provider !== undefined }),
    request: async (path, options) => {
      if (path === '/auth/config') return { version: 'v1', mode: 'firebase', login_available: true, providers: ['google.com'], firebase: { apiKey: 'fixture', authDomain: 'fixture-project.firebaseapp.com', projectId: 'fixture-project', appId: '1:123:web:abc' } };
      if (path === '/auth/session') {
        if (!authenticated) throw Object.assign(new Error('signed out'), { status: 401 });
        return { authenticated: true, roles: ['dataset_viewer'], csrf_token: 'cookie-csrf', expires_at: '2099-01-01T00:00:00Z' };
      }
      if (path === '/auth/logout') {
        assert.equal(options.headers['X-CSRF-Token'], 'cookie-csrf');
        authenticated = false;
        return null;
      }
      assert.equal(path, '/auth/firebase/session');
      assert.equal(options.method, 'POST');
      assert.deepEqual(options.body, { id_token: 'synthetic-token' });
      assert.deepEqual(options.headers, { 'X-Autodata-Session-Exchange': '1' });
      calls.exchanges++;
      authenticated = true;
      return null;
    },
  });
  return { session, calls, changes };
}

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

function sourceReviewHarness() {
  const navigation = new NavigationGeneration();
  const first = navigation.next();
  const state = { content: 'article A', status: 'A ready', view: 'reader' };
  const loads = [], errors = [];
  let click, rejectSource;
  const context = {
    currentArticle: { source_review: { url: '/article-A/source' } },
    viewGeneration: first,
    $: () => ({ addEventListener(event, callback) {
      assert.equal(event, 'click');
      click = callback;
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
    appSection('function handleSourceError(error, g) {', 'async function renewMedia(') +
    appSection('$("source-review-load").addEventListener', '$("back").addEventListener'),
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

function loginRouteHarness(search, { authenticate = true, signInError = null, login = null, library = null } = {}) {
  const navigation = new NavigationGeneration();
  const calls = { signIns: 0, checkoutClears: 0, checkouts: 0, routes: 0,
    selections: [], libraries: 0, orders: [], options: [], invalidations: 0 };
  const elements = new Map();
  const element = name => {
    if (!elements.has(name)) elements.set(name, { value: '' });
    return elements.get(name);
  };
  const configuration = { id: routeConfiguration, region: 'US' };
  const context = {
    URLSearchParams, uuid, validScope,
    location: { search }, signingIn: false,
    vehicle: { id: previousConfiguration, region: 'US' }, quote: null,
    names: ['year', 'make', 'model', 'configuration'],
    rows: { configuration: [configuration] }, $: element,
    checkout: { clear() { calls.checkoutClears++; }, start() { calls.checkouts++; } },
    session: { state: { authenticated: false }, async signIn() {
      calls.signIns++;
      if (login) await login();
      if (signInError) throw signInError;
      context.session.state.authenticated = authenticate;
    } },
    scope: () => ({ configuration_id: context.vehicle?.id, region: context.vehicle?.region }),
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
    async selectVehicle(g, article = '') {
      assert.equal(g.current(), true);
      calls.selections.push({ configuration: context.vehicle.id, region: context.vehicle.region, article });
    },
    async loadOptions(name, g, desired) {
      assert.equal(g.current(), true);
      calls.options.push({ name, desired });
      element(name).value = desired;
    },
  };
  runInNewContext(
    appSection('async function signIn() {', 'async function bootstrap() {') +
    appSection('async function restoreRoute() {', 'for (const [index, name] of names.entries())'),
    context,
  );
  return { context, calls, element };
}

const loginRoutes = [
  { name: 'My vehicles instead of a prior selected configuration', query: '?view=library',
    libraries: 1, orders: [], selections: [], options: [] },
  { name: 'the exact article in a direct configuration link',
    query: `?configuration=${routeConfiguration}&region=US&article=${routeArticle}`,
    libraries: 0, orders: [],
    selections: [{ configuration: routeConfiguration, region: 'US', article: routeArticle }], options: [] },
  { name: 'the article and search in a saved selector hierarchy',
    query: `?year=2020&make=toyota&model=rav4&configuration=${routeConfiguration}&region=US&article=${routeArticle}&q=brakes`,
    libraries: 0, orders: [],
    selections: [{ configuration: routeConfiguration, region: 'US', article: routeArticle }],
    options: [{ name: 'year', desired: '2020' }, { name: 'make', desired: 'toyota' },
      { name: 'model', desired: 'rav4' }, { name: 'configuration', desired: routeConfiguration }] },
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
    currentOrder: '', paidOrder: '', unconfirmedOrder: null, vehicle: null, quote: null, merchant: null, access: 'missing',
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
  const nodes = new Map();
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, {
      hidden: false, disabled: false, checked: id === 'agreement', value: '',
      textContent: '', dataset: {}, children: [],
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); }, removeAttribute() {},
    });
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
  const context = {
    $, location, history, URLSearchParams, URL, uuid, validScope, validQuote,
    purchaseConfiguration, configurationLabel, navigation,
    document: { title: '', body: { dataset: {} }, visibilityState: 'visible', createTextNode: text => ({ textContent: text }) },
    element: (tag, text) => ({ tag, textContent: text }),
    names: ['year', 'make', 'model', 'configuration'],
    vehicle: { id: scope.configuration_id, region: scope.region }, quote,
    merchant: merchantFixture(), access: 'missing', currentOrder: '', paidOrder: null, unconfirmedOrder: null,
    articles: [],
    sessionEstablished: true, signingIn: false,
    session: { state: { authenticated: true, ready: true, csrf: 'test-csrf' },
      async bootstrap() {}, clear() {
        context.session.state.authenticated = false;
        context.session.state.ready = false;
        context.renderPurchase();
      } },
    scope: () => ({ configuration_id: context.vehicle?.id, region: context.vehicle?.region }),
    checkout: { async start() {
      checkoutStarts++;
      return { version: 'v1', ...scope, order_id: orderID, state: 'processing' };
    }, clear() {} },
    async pollOrder(id, { onUpdate }) {
      assert.equal(id, orderID);
      orderReads++;
      const paid = { version: 'v1', ...scope, order_id: orderID, state: 'paid', retry_disposition: 'do_not_repay' };
      const response = orderResponses ? orderResponses.shift() : paid;
      if (response instanceof Error) throw response;
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
    renderArticles() { $('articles').replaceChildren(...context.articles.map(item => ({ id: item.id }))); },
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
  runInNewContext(
    (realArticleIndex ? appSection('function show(', 'function clearProtected()') : '') +
    (realArticleIndex ? appSection('function clearProtected()', 'function invalidate()') : '') +
    appSection('function invalidate(', 'function updateURL(') +
    appSection('function updateURL(', 'function populate(') +
    appSection('function renderPurchase(', 'async function selectVehicle(') +
    (realArticleIndex ? appSection('async function selectVehicle(', 'function renderArticles(') : '') +
    (articleOpenError ? appSection('function openArticle(', 'function validSourceURL(') : '') +
    appSection('async function checkOrder(', 'async function signIn()') +
    appSection('async function bootstrap()', 'for (const [index, name] of names.entries())') +
    appSection('let lifecycleCheck = null;', 'window.addEventListener("pageshow"'),
    context,
  );
  return { context, $, location, statuses,
    checkoutStarts: () => checkoutStarts, orderReads: () => orderReads };
}

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
  assert.match(h.statuses.at(-1).message, /do not pay again/);
  assert.equal(h.statuses.at(-1).options.retry, undefined);
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
  h.context.merchant = null;
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').disabled, true);
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
  };
  const h = paidPurchaseLifecycleHarness([], { orderResponses: [processing] });
  h.context.vehicle = null;
  h.context.quote = null;
  h.location.search = `?order=${orderID}`;
  await h.context.restoreRoute();
  assert.equal(h.context.vehicle?.id, scope.configuration_id);
  assert.equal(h.context.vehicle?.region, scope.region);
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

function articleIndexHarness(responses) {
  const navigation = new NavigationGeneration();
  const nodes = new Map();
  function element(tag, text = '', className = '') {
    return { tag, textContent: text, className, hidden: false, value: '', dataset: {}, attributes: {}, children: [], events: {},
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(name, callback) { this.events[name] = callback; },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      removeAttribute() {},
    };
  }
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, element('div'));
    return nodes.get(id);
  };
  const statuses = [], updates = [], opened = [], requests = [], results = [];
  const context = {
    $, element, URL, location: { href: 'https://cars.example/workshop?vehicle=B' },
    document: { body: { dataset: {} } },
    quote: null, articles: [], indexComplete: false, indexFailed: false, access: '', retryAction: null, filterArticles,
    stage() {}, renderPurchase() {}, show() {},
    articlePath: () => '/v1/catalog/vehicles/B/articles',
    requestJSON(path, options) {
      requests.push({ path, signal: options.signal });
      const response = responses[Math.min(requests.length - 1, responses.length - 1)];
      return typeof response === 'function' ? response() : Promise.resolve(response);
    },
    async readCollection(read, options) {
      const result = await readCollection(read, {
        ...options, attempts: 3, wait: async () => {},
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
    operation: callback => callback(navigation.next()),
    recordStatus: (text, options) => statuses.push({ text, ...options }),
  };
  runInNewContext(
    appSection('function status(', 'function stage(') +
    appSection('async function loadArticles(', 'const assetID =') +
    '\nconst actualStatus = status; status = (text, options = {}) => { recordStatus(text, options); actualStatus(text, options); };',
    context,
  );
  return { context, $, navigation, statuses, updates, opened, requests, results,
    load: (article = '', generation = navigation.next()) => context.loadArticles(generation, article) };
}

const indexResponse = (status, { complete = false, retryable = false, hydrating = false, items = [] } = {}) =>
  ({ items, complete, hydrating, progress: status ? { status, retryable } : null });

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
    assert.equal(h.$('completion-status').textContent, 'Article index ready. No articles are currently available.');
  }
});

test('actual article index flow keeps terminal, timed out, and nonhydrating outcomes incomplete', async () => {
  for (const [response, reads, text] of [
    [indexResponse('failed'), 1, /could not be prepared/],
    [indexResponse('pending', { hydrating: true }), 3, /still being prepared/],
    [indexResponse('pending'), 1, /still being prepared/],
    [indexResponse(null), 1, /still being prepared/],
  ]) {
    const h = articleIndexHarness([response]);
    await h.load();
    assert.equal(h.requests.length, reads);
    assert.equal(h.statuses.some(s => s.complete === true), false);
    assert.match(h.$('activity-text').textContent, text);
    assert.equal(h.$('completion-status').textContent, '');
    assert.equal(h.results[0].timedOut === true, reads === 3);
    assert.equal(typeof h.context.retryAction, response.progress?.status === 'failed' ? 'object' : 'function');
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
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  set textContent(value) { this.replaceChildren(); this._text = String(value); }
  get isConnected() { return this.tagName === 'body' || Boolean(this.parentNode?.isConnected); }
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
  dispatch(name, event = {}) { for (const handler of this.handlers.get(name) || []) handler(event); }
  querySelectorAll(selector) {
    assert.equal(selector, 'img[data-asset-id]');
    return mediaDescendants(this, 'img').filter(n => n.dataset.assetId !== undefined);
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
    'article-title', 'catalog-count', 'article-note', 'source-review-meta', 'source-review', 'print',
    'welcome', 'reader', 'catalog', 'library', 'source-review-link', 'reader-vehicle', 'reader-engine', 'purchase-selection',
    'article-kind', 'article-reference', 'source-review-load', 'check-order'];
  for (const id of ids) { const node = new ArticleMediaNode('div'); nodes.set(id, node); body.append(node); }
  const navigation = new NavigationGeneration(), g = navigation.next();
  const shows = [], statuses = [];
  const context = {
    URL, uuid, articlePresentation, localImageURL, sourceReferenceURL, processingArticle, readableArticle,
    document: { body, title: '', createElement: tag => new ArticleMediaNode(tag),
      createDocumentFragment: () => new ArticleMediaNode('#fragment') },
    location: { origin: 'https://cars.example' },
    $: id => { assert.ok(nodes.has(id), `known DOM node ${id}`); return nodes.get(id); },
    navigation, currentArticle: null, renderedRevision: '', sourceData: null, sourceURL: '', sourceRevision: 0,
    renewalUsed: false, renewal: null, renewalFailures: new Set(), articles: [], libraryItems: [], libraryCursor: null,
    currentOrder: '',
    access: 'granted', quote: { configuration_label: '2005 Toyota' }, vehicle: { region: 'US' },
    articlePath: id => `/v1/catalog/vehicles/v/articles/${id}`,
    requestArticleJSON: () => assert.fail('unexpected article request'),
    requestJSON: () => assert.fail('unexpected source request'),
    show: id => shows.push(id), status: (message, options) => statuses.push({ message, options }),
    ...overrides,
  };
  runInNewContext([
    appSection('const element =', 'const session ='),
    appSection('function clearProtected(', 'async function operation('),
    appSection('const assetID =', 'async function loadArticle('),
    appSection('function validSourceURL(', 'async function library('),
  ].join('\n'), context);
  return { context, g, nodes, navigation, shows, statuses,
    render(article) { context.renderArticle(article, g); return nodes.get('article-content'); },
    content(article) { const parent = new ArticleMediaNode('div'); body.append(parent); context.renderContent(parent, article, g); return parent; },
  };
}

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

test('retrying a visible article keeps its tab title while preparation fails', async () => {
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
  rejectPrepare(new Error('temporarily unavailable'));
  await assert.rejects(retry, /temporarily unavailable/);
  assert.equal(h.context.document.title, 'Pump service | AutoData');
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
    assert.equal(parent.children[2].textContent, 'Source ↗');
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
      images: [{ image_id: 'shared' }, { asset_id: 'row-only' }] },
  ], [{ id: 'shared', url: mediaURL('shared') }, { id: 'row-only', url: mediaURL('row-only') }]));
  assert.deepEqual(mediaIDs(parent), ['shared', 'row-only']);
  assert.deepEqual(mediaIDs(mediaDescendants(parent, 'td')[0]), ['shared']);
  assert.deepEqual(mediaTags(parent), ['div', 'figure']);
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
    assert.equal(h.nodes.get('article-note').textContent, note ? 'Preparing articles. Available source remains readable.' : '');
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
  response = { ...response, source: { url: mediaSourceURL.replace('11111111-', '22222222-') } };
  await assert.rejects(h.context.loadSource(mediaSourceURL, h.g), /source reference changed/);
  assert.equal(frame.children[0], first);
  const count = calls.length;
  await assert.rejects(h.context.loadSource('https://provider.example/source', h.g), /reference is unavailable/);
  assert.equal(calls.length, count);
  assert.equal(frame.children[0], first);
  assert.equal(frame.hidden, false);
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

test('article block media actual renewal shares one request and reconciles both shapes once per revision', async () => {
  const pending = deferredAuthOperation(), calls = [];
  const h = articleMediaHarness({ requestArticleJSON: (path, options) => { calls.push({ path, options }); return pending.promise; } });
  const parent = h.render(renewalFixture()), images = mediaDescendants(parent, 'img');
  assert.equal(images.length, 2);
  images[0].dispatch('error'); const renewal = h.context.renewal;
  images[1].dispatch('error');
  assert.equal(calls.length, 1); assert.equal(h.context.renewal, renewal);
  assert.equal(calls[0].path, '/v1/catalog/vehicles/v/articles/a'); assert.equal(calls[0].options.signal, h.g.signal);
  pending.resolve(renewedArticle()); await renewal;
  assert.deepEqual(mediaDescendants(parent, 'img'), images, 'stable revision retains image nodes');
  assert.deepEqual(images.map(n => n.src), ['https://cars.example/v1/catalog/images/v2.new-list', 'https://cars.example/v1/catalog/images/v2.new-callout']);
  assert.deepEqual(images.map(n => n.dataset.replacement), ['1', '1']);
  assert.equal(h.context.renewal, null); assert.equal(h.context.renewalFailures.size, 0);
  images[0].dispatch('error'); images[1].dispatch('error');
  assert.equal(calls.length, 1);
  assert.deepEqual(mediaIDs(parent), []);
  assert.equal(mediaDescendants(parent, 'figure')[0].textContent, 'Illustration unavailable. Refresh this article to try again.');
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
      [{ id: 'stored', url: mediaURL('old-stored') }], null, h.g);
    frame.hidden = false; h.context.sourceData = { source: { url: mediaSourceURL } }; h.context.sourceURL = 'https://cars.example' + mediaSourceURL;
    const image = mediaDescendants(frame, 'img')[0];
    assert.ok(image, 'stored-source callout must contain a retained figure');
    image.dispatch('error'); await h.context.renewal;
    assert.equal(calls.length, 1); assert.equal(calls[0].url, 'https://cars.example' + mediaSourceURL); assert.equal(calls[0].options.signal, h.g.signal);
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
    assert.ok(image); image.dispatch('error'); await h.context.renewal;
    assert.equal(h.g.current(), false);
    assert.equal(h.g.signal.aborted, true);
    for (const id of ['articles', 'article-content', 'source-review-frame', 'reference-data', 'library-items']) assert.equal(h.nodes.get(id).textContent, '', id);
    assert.equal(h.context.currentArticle, null); assert.equal(h.context.sourceData, null); assert.equal(h.context.sourceURL, '');
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
    h.context.sourceData = { source: { url: mediaSourceURL } }; h.context.sourceURL = mediaSourceURL;
    const image = mediaDescendants(h.nodes.get('article-content'), 'img')[0];
    assert.ok(image); image.dispatch('error'); const renewal = h.context.renewal;
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
 const $ = id => { if (!nodes.has(id)) nodes.set(id, {value:'',disabled:false,hidden:true,textContent:'',dataset:{}}); return nodes.get(id); };
 const statuses=[], displayed=[];
 const context={ $, navigation:new NavigationGeneration(), document:{body:{dataset:{}}}, retryAction:null, currentOrder:'', paidOrder:'', stage(){}, selectorPath:()=>'/choices', requestJSON:async()=>{if(response instanceof Error)throw response;return response;},
  readCollection:(read,options)=>readCollection(read,{...options,attempts:2,wait:async()=>{}}),
  populate(name,items,desired){displayed.push(items);$(name).disabled=!items.length;$(name).value=desired;},
  recordStatus:(text,options={})=>statuses.push({text,...options}), restoreRoute(){},
 };
 runInNewContext(appSection('function status(', 'function stage(')+appSection('async function operation(', 'function updateURL(')+appSection('async function loadOptions(', 'function renderPurchase(')+
  'const actualStatus = status; status = (text, options = {}) => { recordStatus(text, options); actualStatus(text, options); };',context);
 return {context,$,statuses,displayed,load:(desired='',current)=>context.operation(g=>context.loadOptions('configuration',current?{...g,current}:g,desired),()=>context.restoreRoute())};
}

test('actual selector timeout remains a retryable loading failure with partial rows preserved', async()=>{
 for(const items of [[],[{id:'cfg-1',engine:'2.0L',complete:true}]]) {
  const h=selectorOptionsHarness({items,complete:false,hydrating:true});
  await h.load();
  const last=h.statuses.at(-1);
  assert.equal(last.error,true);
  assert.match(last.text,/loading|load/i);
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
