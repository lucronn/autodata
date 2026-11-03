import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { NavigationGeneration } from './workshop/article-read.mjs';
import { uuid, validScope } from './workshop/commerce.mjs';
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
test('reader is sequential, retains source during transient failure and stops at terminal canonical', async () => {
  const { readArticle } = await import('./workshop/article-read.mjs');
  const updates = [], waits = []; let now = 0, calls = 0;
  const versions = [{ status: 200, data: { article: { body: 'source', processing: { job_id: 'job', state: 'fetching' } } } }, new TypeError('network'), { status: 200, data: { article: { document: { blocks: [{ type: 'paragraph', text: 'canonical' }] }, processing: { job_id: 'job', state: 'completed' } } } }];
  const result = await readArticle(async () => { calls++; const value=versions.shift();if(value instanceof Error)throw value;return value; }, { now: () => now, wait: async ms => { waits.push(ms);now += ms; }, onUpdate: r => updates.push(r.data.article) });
  assert.equal(calls,3);assert.equal(updates.length,2);assert.deepEqual(waits,[1000,2000]);assert.equal(result.timedOut,false);
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
