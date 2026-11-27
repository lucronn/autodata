import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { requestArticleJSON, requestInitialYears, startSavedSelectorReads } from './workshop/catalog.mjs';
import { readSessionBootstrap } from './workshop/auth.mjs';
const source = name => readFileSync(new URL(`./workshop/${name}`, import.meta.url), 'utf8');
const assetBase = `https://workshop.example/workshop/assets/${'a'.repeat(64)}/`;
const bootstrapCode = source('bootstrap.mjs').replaceAll('import(', 'loadModule(')
  .replaceAll('import.meta.url', JSON.stringify(assetBase + 'bootstrap.mjs'));
test('HTML starts only the isolated bootstrap', () => {
  assert.match(source('index.html'), /src="\/workshop\/bootstrap.mjs"/);
  assert.doesNotMatch(source('index.html'), /src="\/workshop\/(app|demo)\.mjs"/);
  assert.match(source('index.html'), /Test checkout — no real charge/);
  assert.match(source('index.html'), /Sample — fictional content/);
});
test('the entry page preloads the catalog helper before starting bootstrap', () => {
  assert.match(source('index.html'), /rel="modulepreload" href="\/workshop\/catalog\.mjs"[\s\S]*src="\/workshop\/bootstrap\.mjs"/);
});
const headPickerCode = source('index.html').match(/<script>([\s\S]+?)<\/script>/)[1];
const entrySettingsPaths = ['/auth/config', '/auth/session', '/workshop/purchase-config.json'];

function startHeadPicker(search, publicSelectors = true, {
  entry = {}, origin = 'https://workshop.example', initialYears = null, directSelectorOrigin, yearPicker,
  reply = path => ({ ok: true, json: async () => ({ items: [{ path }] }) }),
} = {}) {
  const calls = [], hints = [];
  let parsed;
  const catalogLink = {
    href: assetBase + 'catalog.mjs',
    dataset: { publicSelectors: String(publicSelectors), directSelectorOrigin },
  };
  const context = {
    URL, URLSearchParams, AbortSignal, AbortController, location: { search, origin },
    Option: function(text, value) { return { text: String(text), value: String(value) }; },
    MutationObserver: class {
      constructor(onMutation) { parsed = onMutation; }
      observe() {}
      disconnect() { parsed = null; }
    },
    document: {
      head: { append: link => hints.push(link.href) },
      createElement: () => ({}),
      documentElement: { dataset: entry },
      getElementById(id) {
        if (id === 'workshop-catalog-module') return catalogLink;
        if (id === 'workshop-initial-years') return initialYears === null ? null : { textContent: initialYears };
        if (id === 'year') return yearPicker;
        return {};
      },
    },
    fetch: async (path, options) => {
      calls.push({ path, options });
      return reply(path, options, calls);
    },
  };
  runInNewContext(headPickerCode, context);
  return { calls, hints, context, parseYear: () => parsed?.() };
}

test('entry starts matching stored reads and the saved selector consumes them once', async () => {
  const { calls, hints, context } = startHeadPicker('?year=2024&make=buick-truck&model=envision-awd');
  const root = '/v1/catalog/years';
  const savedPaths = [root, root + '/2024/makes?region=US&stored_only=1',
    root + '/2024/makes/buick-truck/models?region=US&stored_only=1',
    root + '/2024/makes/buick-truck/models/envision-awd/configurations?region=US&stored_only=1'];
  assert.deepEqual(calls.map(({ path }) => path), savedPaths);
  assert.deepEqual(hints, ['app', 'auth', 'commerce', 'article-read'].map(name => `${assetBase}${name}.mjs`));
  for (const { path, options } of calls) assert.equal(options.cache, path === root ? 'default' : 'no-store');
  let restored;
  context.loadModule = async path => {
    if (path === './catalog.mjs') {
      return { requestInitialYears, startSavedSelectorReads, requestJSON: () => assert.fail('duplicate selector read') };
    }
    if (path === './auth.mjs') return { readSessionBootstrap() {} };
    return { bootstrap(_years, _account, { initialSelectors }) { restored = initialSelectors; } };
  };
  await runInNewContext(`(async () => { ${bootstrapCode} })()`, context);
  assert.equal(calls.length, savedPaths.length + 1); // The app also reads its demo mode.
  assert.equal(calls.at(-1).path, '/workshop/demo-mode.json');
  assert.deepEqual(await restored.reads.configuration, { items: [{ path: savedPaths[3] }] });
  restored.abort();
  assert.ok(calls.slice(0, -1).every(({ options }) => options.signal.aborted));
});

test('the picker restores the complete entry snapshot and fetches when no usable snapshot exists', async () => {
  const root = '/v1/catalog/years';
  const snapshot = { version: 'v1', complete: true, hydrating: false, items: [{ year: 2024 }] };
  const { calls, context } = startHeadPicker('?year=2024', true, { initialYears: JSON.stringify(snapshot) });
  const makes = root + '/2024/makes?region=US&stored_only=1';
  assert.deepEqual(calls.map(({ path }) => path), [makes]);
  let restored;
  context.loadModule = async path => {
    if (path === './catalog.mjs') {
      return { requestInitialYears, startSavedSelectorReads, requestJSON: () => assert.fail('duplicate selector read') };
    }
    if (path === './auth.mjs') return { readSessionBootstrap() {} };
    return { bootstrap(_years, _account, { initialSelectors }) { restored = initialSelectors; } };
  };
  await runInNewContext(`(async () => { ${bootstrapCode} })()`, context);
  assert.equal(JSON.stringify(await restored.reads.year), JSON.stringify(snapshot));
  assert.deepEqual(calls.map(({ path }) => path), [makes, '/workshop/demo-mode.json']);
  for (const initialYears of ['{invalid', JSON.stringify({ ...snapshot, complete: false }),
    JSON.stringify({ ...snapshot, items: [] })]) {
    assert.deepEqual(startHeadPicker('', true, { initialYears }).calls.map(({ path }) => path), [...entrySettingsPaths, root]);
  }
});

test('the public entry offers stored years and passes the latest early make request to the app', async () => {
  const snapshot = { version: 'v1', complete: true, items: [{ year: 2023 }, { year: 2024 }] };
  const yearPicker = {
    disabled: true, options: [{ value: '' }], value: '',
    replaceChildren(...options) { this.options = options; },
    addEventListener(event, listener) { assert.equal(event, 'change'); this.change = listener; },
    removeEventListener(event, listener) { assert.equal(event, 'change'); assert.equal(this.change, listener); this.change = null; },
  };
  const { calls, parseYear, context } = startHeadPicker('', true, {
    initialYears: JSON.stringify(snapshot), yearPicker,
  });
  assert.equal(yearPicker.disabled, true);
  parseYear();
  assert.equal(yearPicker.disabled, false);
  assert.deepEqual(yearPicker.options.map(option => option.value), ['', '2024', '2023']);
  yearPicker.value = '2024';
  yearPicker.change();
  yearPicker.value = '2023';
  yearPicker.change();
  const makeReads = calls.slice(entrySettingsPaths.length);
  assert.deepEqual(makeReads.map(call => call.path), [2024, 2023].map(year => `/v1/catalog/years/${year}/makes?region=US`));
  assert.ok(makeReads.every(call => call.options.cache === 'default'));
  assert.equal(makeReads[0].options.signal.aborted, true);
  assert.equal(makeReads[1].options.signal.aborted, false);
  const available = [];
  context.workshopPickerStartup.requestMake = async (path, options) => {
    available.push({ path, options });
    return { items: [{ path }] };
  };
  yearPicker.value = '2024';
  yearPicker.change();
  assert.equal(makeReads[1].options.signal.aborted, true);
  assert.equal(calls.length, entrySettingsPaths.length + 2);
  assert.equal(available.length, 1);
  assert.equal(available[0].path, makeReads[0].path);
  assert.equal(available[0].options.cache, 'default');
  assert.equal(available[0].options.signal.aborted, false);
  const handoff = context.workshopPickerStartup.takeYearPicker();
  assert.equal(handoff.makeRead.year, '2024');
  assert.deepEqual(await handoff.makeRead.response, { items: [{ path: makeReads[0].path }] });
  assert.equal(yearPicker.value, '2024');
  assert.equal(yearPicker.change, null);
});

test('entry keeps independent, private and unconfirmed paths on their ordinary reads', () => {
  const completeSnapshot = JSON.stringify({ version: 'v1', complete: true, items: [{ year: 2024 }] });
  for (const search of ['?view=library', '?order=returning', '?article=saved', '?configuration=selected',
    '?year=2024&region=CA', '?sample=1', '?demo=1']) {
    const { calls, context } = startHeadPicker(search, true, { initialYears: completeSnapshot });
    assert.deepEqual(calls, [], search);
    assert.equal(context.workshopPickerStartup?.takeYearPicker, undefined, search);
  }
  assert.deepEqual(startHeadPicker('?year=2024', false).calls, []);
  assert.deepEqual(startHeadPicker('').calls.map(({ path }) => path), [...entrySettingsPaths, '/v1/catalog/years']);
  assert.deepEqual(startHeadPicker('?year=2024&make=%3Efoo&model=envision-awd').calls.map(({ path }) => path),
    ['/v1/catalog/years', '/v1/catalog/years/2024/makes?region=US&stored_only=1']);
});
test('the public picker starts one early connection for the eligible selector reads', () => {
  const directSelectorOrigin = 'https://autodata.curtis.click';
  const options = { origin: 'https://autodata.cars.tk', directSelectorOrigin };
  const { hints, calls } = startHeadPicker('', true, options);
  assert.deepEqual(hints.filter(href => href === directSelectorOrigin), [directSelectorOrigin]);
  assert.deepEqual(calls.map(({ path }) => path), [...entrySettingsPaths, '/v1/catalog/years']);
  assert.ok(!startHeadPicker('', false, options).hints.includes(directSelectorOrigin));
  for (const search of ['?view=library', '?sample=1', '?demo=1', '?article=chosen', '?order=returning']) {
    assert.ok(!startHeadPicker(search, true, options).hints.includes(directSelectorOrigin), search);
  }
  assert.ok(!startHeadPicker('', true, { directSelectorOrigin }).hints.includes(directSelectorOrigin));
});

test('account and purchase bootstrap consume the original entry reads and preserve a guest denial', async () => {
  for (const failedTransport of [false, true]) {
    const snapshot = { version: 'v1', complete: true, items: [{ year: 2024 }] };
    const purchase = { enabled: false, checkout_mode: 'simulation' };
    const { calls, context } = startHeadPicker('', true, {
      initialYears: JSON.stringify(snapshot),
      reply(path, _options, seen) {
        if (path === '/auth/config' && failedTransport && seen.length === 1)
          throw new TypeError('transport failure');
        if (path === '/auth/session')
          return Response.json({ error: { code: 'AUTH_REQUIRED' } }, { status: 401 });
        return Response.json(path === '/workshop/purchase-config.json' ? purchase : { version: 'v1' });
      },
    });
    assert.deepEqual(calls.map(call => call.path), entrySettingsPaths);
    assert.equal(calls[1].options.headers.Prefer, 'workshop-session-mode');
    assert.ok(calls.every(({ options }) => options.credentials === 'same-origin' && options.cache === 'no-store'));
    context.loadModule = async path => {
      if (path === './catalog.mjs') return {
        requestInitialYears, startSavedSelectorReads,
        async requestJSON(path, options) {
          return (await requestArticleJSON(path, { fetcher: context.fetch, ...options })).data;
        },
      };
      if (path === './auth.mjs') return { readSessionBootstrap };
      return { async bootstrap(years, account, { initialPurchaseConfig }) {
        assert.equal((await years).items[0].year, 2024);
        const [config, session] = await account;
        assert.deepEqual(await config, { status: 'fulfilled', value: { version: 'v1' } });
        const denied = await session;
        assert.equal(denied.status, 'rejected');
        assert.equal(denied.reason.status, 401);
        assert.equal(denied.reason.code, 'AUTH_REQUIRED');
        assert.deepEqual(await initialPurchaseConfig, purchase);
      } };
    };
    await runInNewContext(`(async () => { ${bootstrapCode} })()`, context);
    assert.deepEqual(calls.map(call => call.path), [
      ...entrySettingsPaths, '/workshop/demo-mode.json', ...(failedTransport ? ['/auth/config'] : []),
    ]);
  }
});
test('entry preloads the app for confirmed public demos without starting regular picker reads', () => {
  const entry = { workshopDemoOrigins: 'https://autodata.cars.tk https://autodata.curtis.click' };
  const search = '?demo=1&configuration=selected';
  const expected = ['app', 'auth', 'commerce', 'article-read'].map(name => assetBase + name + '.mjs');
  for (const options of [
    { entry, origin: 'https://autodata.cars.tk' },
    { entry, origin: 'https://autodata.curtis.click' },
    { entry: { workshopOpenDemo: 'true' } },
  ]) {
    const { calls, hints, context } = startHeadPicker(search, true, options);
    assert.deepEqual(hints, expected);
    assert.deepEqual(calls, []);
    assert.equal(context.workshopPickerStartup, undefined);
  }
  assert.deepEqual(startHeadPicker(search, true, { entry }).hints, []);
  assert.deepEqual(startHeadPicker('?sample=1', true, { entry: { workshopOpenDemo: 'true' } }).hints, []);
});
test('entry starts one exact public demo index read before importing the app', async () => {
  const entry = { workshopOpenDemo: 'true' };
  const configuration = 'cf544dfd-4570-589f-b3b4-23487d14e591';
  const search = `?demo=1&configuration=${configuration}&region=US`;
  const { calls, context } = startHeadPicker(search, true, { entry });
  const path = `/v1/catalog/vehicles/${configuration}/articles?region=US&demo=1`;
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, path);
  assert.equal(calls[0].options.headers.Prefer, 'workshop-demo-readable-index');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(context.workshopPickerStartup, undefined);
  const startup = context.workshopDemoIndex;
  let restored;
  context.loadModule = async module => {
    assert.equal(module, './app.mjs');
    return { bootstrap(_years, _account, { initialDemoIndex }) { restored = initialDemoIndex; } };
  };
  await runInNewContext(`(async () => { ${bootstrapCode} })()`, context);
  assert.equal(context.workshopDemoIndex, undefined);
  assert.equal(restored, startup);
  assert.equal((await restored.response).ok, true);
  assert.equal(calls.length, 1);
  restored.abort();
  assert.equal(calls[0].options.signal.aborted, true);
  assert.deepEqual(startHeadPicker(search).calls, []);
  for (const skipped of [search + '&article=saved', search + '&year=2015', search + '&q=filter',
    search.replace('region=US', 'region=us'), search.replace(configuration, 'invalid')]) {
    assert.deepEqual(startHeadPicker(skipped, true, { entry }).calls, [], skipped);
  }
});
test('a confirmed public demo link starts the exact detail without reading the index', () => {
  const configuration = 'cf544dfd-4570-589f-b3b4-23487d14e591';
  const article = '1cae3450-955a-5807-b72f-91010d396008';
  const base = `/v1/catalog/vehicles/${configuration}/articles`;
  const search = `?demo=1&configuration=${configuration}&region=US&article=${article}`;
  const options = { entry: { workshopOpenDemo: 'true' } };
  const { calls, context } = startHeadPicker(search, true, options);
  const detailPath = `${base}/${article}?region=US&demo=1`;
  assert.deepEqual(calls.map(({ path }) => path), [detailPath]);
  assert.equal(context.workshopDemoIndex.detail.path, detailPath);
  assert.equal(calls[0].options.headers.Prefer, 'workshop-short-publication-check, workshop-demo-fitment');
  assert.equal(calls[0].options.cache, 'no-store');
  context.workshopDemoIndex.abort();
  assert.ok(calls.every(({ options }) => options.signal.aborted));
  assert.deepEqual(startHeadPicker(search).calls, []);
  for (const suffix of ['&demo=0', '&region=CA', `&configuration=${configuration}`, `&article=${article}`]) {
    assert.deepEqual(startHeadPicker(search + suffix, true, options).calls, []);
  }
});
test('sign-in is inert in initial HTML until async app readiness', () => {
  const button = source('index.html').match(/<button\b[^>]*\bid="signin"[^>]*>/)?.[0];
  assert.ok(button, 'the sign-in button must be present');
  assert.match(button, /\sdisabled(?:\s|>)/, 'the static button must not accept clicks before app.mjs attaches its handler');
});
test('real demo uses the ordinary app only in test mode; sample stays separate', async () => {
  assert.ok(existsSync(new URL('./workshop/bootstrap.mjs', import.meta.url)), 'bootstrap must exist');
  const scenarios = [
    ['?sample=1', true, ['./demo.mjs'], false, 0],
    ['?demo=1', true, ['./app.mjs'], true, 1],
    ['?demo=1', false, [], false, 1],
    ['?demo=1&sample=1', false, [], false, 1],
    ['?order=22222222-2222-4222-8222-222222222222', true, ['./catalog.mjs', './auth.mjs', './app.mjs'], true, 1],
    ['', false, ['./catalog.mjs', './auth.mjs', './app.mjs'], false, 1],
  ];
  for (const [search, ready, expected, banner, fetchCount] of scenarios) {
    const loaded = [];
    const calls = [];
    const preload = [];
    const nodes = new Map(['test-banner', 'open-demo-banner', 'test-unavailable'].map(id => [id, { hidden: true }]));
    const main = { hidden: false };
    const nav = { hidden: false };
    await runInNewContext(`(async () => { ${bootstrapCode} })()`, {
      AbortSignal, URL, URLSearchParams, location: { search }, document: {
        documentElement: { dataset: {} },
        createElement: tag => ({ tag }),
        head: { append: element => preload.push(element) },
        getElementById: id => nodes.get(id),
        querySelector: selector => selector === 'main' ? main : nav,
      },
      fetch: async path => {
        calls.push({ path, preload: preload.slice(), imports: loaded.slice() });
        return { ok: true, json: async () => ({ enabled: ready }) };
      },
      loadModule: async path => {
        loaded.push(path);
        return {
          requestInitialYears: () => null,
          startSavedSelectorReads: () => null,
          readSessionBootstrap: () => null,
          async bootstrap(_years, _account, { testCheckout }) {
            if (testCheckout) nodes.get('test-banner').hidden = !(await testCheckout);
          },
        };
      },
    });
    assert.deepEqual(loaded, expected);
    assert.equal(nodes.get('test-banner').hidden, !banner);
    assert.equal(nodes.get('test-unavailable').hidden, !(search.includes('demo=1') && !ready));
    assert.equal(calls.length, fetchCount);
    assert.deepEqual(preload, fetchCount && !search.includes('demo=1') ? [
      { tag: 'link', rel: 'modulepreload', href: assetBase + 'app.mjs' },
      { tag: 'link', rel: 'modulepreload', href: assetBase + 'commerce.mjs' },
      { tag: 'link', rel: 'modulepreload', href: assetBase + 'article-read.mjs' },
    ] : []);
    if (fetchCount) assert.deepEqual(calls[0], {
      path: '/workshop/demo-mode.json', preload, imports: [],
    });
    if (search.includes('demo=1') && !ready) {
      assert.equal(main.hidden, true);
      assert.equal(nav.hidden, true);
    }
  }
});
test('real demo request fails closed on unavailable or malformed mode signal', async () => {
  for (const response of [
    async () => { throw new Error('network unavailable'); },
    async () => ({ ok: false, json: async () => ({ enabled: true }) }),
    async () => ({ ok: true, json: async () => ({ enabled: true, extra: 'unexpected' }) }),
    async () => ({ ok: true, json: async () => ({ enabled: 'true' }) }),
  ]) {
    const loaded = [];
    const nodes = new Map(['test-banner', 'open-demo-banner', 'test-unavailable'].map(id => [id, { hidden: true }]));
    const main = { hidden: false };
    await runInNewContext(`(async () => { ${bootstrapCode} })()`, {
      AbortSignal, URLSearchParams, location: { search: '?demo=1' },
      document: { documentElement: { dataset: {} }, getElementById: id => nodes.get(id), querySelector: () => main },
      fetch: response, loadModule: async path => loaded.push(path),
    });
    assert.deepEqual(loaded, []);
    assert.equal(nodes.get('test-banner').hidden, true);
    assert.equal(nodes.get('test-unavailable').hidden, false);
    assert.equal(main.hidden, true);
  }
});
test('regular startup opens the app with the first reads while checkout mode is pending', async () => {
  let releaseMode;
  let modeConfirmation;
  const result = Promise.resolve({ items: [{ year: 2024 }] });
  const account = [{ status: 'fulfilled', value: {} }];
  const events = [];
  const banner = { hidden: true };
  const started = runInNewContext(`(async () => { ${bootstrapCode} })()`, {
    AbortSignal, URL, URLSearchParams, location: { search: '' }, document: {
      documentElement: { dataset: {} },
      createElement: () => ({}), head: { append() {} },
      getElementById: id => id === 'test-banner' ? banner : {},
    },
    fetch(path) {
      assert.equal(path, '/workshop/demo-mode.json');
      events.push('mode requested');
      return new Promise(resolve => { releaseMode = resolve; });
    },
    async loadModule(path) {
      if (path === './catalog.mjs') {
        return { startSavedSelectorReads: () => null, requestInitialYears(params) {
          assert.equal(params.toString(), '');
          events.push('years requested');
          return result;
        } };
      }
      if (path === './auth.mjs') {
        return { readSessionBootstrap() {
          events.push('account requested');
          return account;
        } };
      }
      return { async bootstrap(years, initialAccount, { testCheckout }) {
        assert.equal(banner.hidden, true);
        assert.equal(years, result);
        assert.equal(await initialAccount, account);
        modeConfirmation = testCheckout;
        events.push('app bootstrapped');
      } };
    },
  });
  await new Promise(setImmediate);
  assert.deepEqual(events, ['mode requested', 'years requested', 'account requested', 'app bootstrapped']);
  releaseMode({ ok: true, json: async () => ({ enabled: true }) });
  await started;
  assert.equal(await modeConfirmation, true);
});
test('open demo handshake loads the real app without test checkout UI', async () => {
  const loaded = [];
  const nodes = new Map(['test-banner', 'open-demo-banner', 'test-unavailable'].map(id => [id, { hidden: true }]));
  const root = { dataset: {} };
  await runInNewContext(`(async () => { ${bootstrapCode} })()`, {
    AbortSignal, URLSearchParams,
    location: { search: '?demo=1' },
    document: { documentElement: root, getElementById: id => nodes.get(id), querySelector: () => ({ hidden: false }) },
    fetch: async () => ({ ok: true, json: async () => ({ enabled: true, access: 'open' }) }),
    loadModule: async path => {
      loaded.push(path);
      return { bootstrap() {} };
    },
  });
  assert.deepEqual(loaded, ['./app.mjs']);
  assert.equal(root.dataset.workshopMode, 'open-demo');
  assert.equal(nodes.get('open-demo-banner').hidden, false);
  assert.equal(nodes.get('test-banner').hidden, true);
});
// Minimal DOM surface for exercising actual event handlers without a runtime dependency.
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.hidden = false; this.disabled = false; this.value = ''; this.events = {}; this.attributes = {}; this.textContent = ''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.value = ''; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(event, callback) { this.events[event] = callback; }
  focus() { this.focused = true; }
  fire(event) { this.events[event]?.({ preventDefault() {} }); }
}
function demoDOM() {
  const elements = new Map([...source('index.html').matchAll(/id="([^"]+)"/g)].map(([, id]) => [id, new Element()]));
  const document = { getElementById: id => elements.get(id), createElement: tag => new Element(tag), querySelector: () => new Element() };
  runInNewContext(source('demo.mjs'), { document });
  return id => elements.get(id);
}
test('demo contains no imports, transport, storage, endpoints or HTML interpolation', () => {
  assert.ok(existsSync(new URL('./workshop/demo.mjs', import.meta.url)), 'demo module must exist');
  assert.doesNotMatch(source('demo.mjs'), /\b(?:import|fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage)\b|\/v1\/|\/auth\/|innerHTML|app\.mjs|auth\.mjs|commerce\.mjs/);
});
test('selectors, search, reader, back and reset work with purchase and sign-in disabled', () => {
  const $ = demoDOM();
  assert.equal($('demo-banner').hidden, false);
  assert.equal($('year').disabled, false); assert.equal($('make').disabled, true);
  for (const [id, value] of [['year', '2026'], ['make', 'Example Motors'], ['model', 'Sample'], ['configuration', 'Demonstration trim']]) {
    assert.equal($(id).disabled, false); $(id).value = value; $(id).fire('change');
  }
  assert.equal($('catalog').hidden, false); assert.match($('purchase-price').textContent, /\$20 USD/);
  for (const id of ['purchase-action', 'signin', 'check-order', 'my-vehicles']) assert.equal($(id).disabled, true);
  assert.equal($('articles').children.length, 1);
  $('search').value = 'no match'; $('search').fire('input'); assert.equal($('no-results').hidden, false);
  $('search').value = 'understanding'; $('search').fire('input'); assert.equal($('no-results').hidden, true);
  const list = $('articles').children[0]; list.children[0].children[0].fire('click');
  assert.equal($('reader').hidden, false); assert.match($('article-title').textContent, /Understanding this sample manual/);
  assert.match($('article-note').textContent, /not supplied by Bankone or Banktwo/); assert.equal($('source-review').hidden, true);
  $('back').fire('click'); assert.equal($('reader').hidden, true); assert.equal($('catalog').hidden, false);
  list.children[0].children[0].fire('click'); $('browse').fire('click'); assert.equal($('reader').hidden, true);
  $('year').value = ''; $('year').fire('change');
  for (const id of ['make', 'model', 'configuration']) { assert.equal($(id).value, ''); assert.equal($(id).disabled, true); }
  assert.equal($('catalog').hidden, true); assert.equal($('demo-banner').hidden, false);
});
