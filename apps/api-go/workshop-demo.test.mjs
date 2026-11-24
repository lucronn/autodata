import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
const source = name => readFileSync(new URL(`./workshop/${name}`, import.meta.url), 'utf8');
test('HTML starts only the isolated bootstrap', () => {
  assert.match(source('index.html'), /src="\/workshop\/bootstrap.mjs"/);
  assert.doesNotMatch(source('index.html'), /src="\/workshop\/(app|demo)\.mjs"/);
  assert.match(source('index.html'), /Test checkout — no real charge/);
  assert.match(source('index.html'), /Sample — fictional content/);
});
test('the entry page preloads the catalog helper before starting bootstrap', () => {
  assert.match(source('index.html'), /rel="modulepreload" href="\/workshop\/catalog\.mjs"[\s\S]*src="\/workshop\/bootstrap\.mjs"/);
});
test('sign-in is inert in initial HTML until async app readiness', () => {
  const button = source('index.html').match(/<button\b[^>]*\bid="signin"[^>]*>/)?.[0];
  assert.ok(button, 'the sign-in button must be present');
  assert.match(button, /\sdisabled(?:\s|>)/, 'the static button must not accept clicks before app.mjs attaches its handler');
});
test('real demo uses the ordinary app only in test mode; sample stays separate', async () => {
  assert.ok(existsSync(new URL('./workshop/bootstrap.mjs', import.meta.url)), 'bootstrap must exist');
  const code = source('bootstrap.mjs').replaceAll('import(', 'loadModule(');
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
    await runInNewContext(`(async () => { ${code} })()`, {
      AbortSignal, URLSearchParams, location: { search }, document: {
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
      { tag: 'link', rel: 'modulepreload', href: '/workshop/app.mjs' },
      { tag: 'link', rel: 'modulepreload', href: '/workshop/progress.mjs' },
      { tag: 'link', rel: 'modulepreload', href: '/workshop/commerce.mjs' },
      { tag: 'link', rel: 'modulepreload', href: '/workshop/article-read.mjs' },
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
  const code = source('bootstrap.mjs').replaceAll('import(', 'loadModule(');
  for (const response of [
    async () => { throw new Error('network unavailable'); },
    async () => ({ ok: false, json: async () => ({ enabled: true }) }),
    async () => ({ ok: true, json: async () => ({ enabled: true, extra: 'unexpected' }) }),
    async () => ({ ok: true, json: async () => ({ enabled: 'true' }) }),
  ]) {
    const loaded = [];
    const nodes = new Map(['test-banner', 'open-demo-banner', 'test-unavailable'].map(id => [id, { hidden: true }]));
    const main = { hidden: false };
    await runInNewContext(`(async () => { ${code} })()`, {
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
  const code = source('bootstrap.mjs').replaceAll('import(', 'loadModule(');
  let releaseMode;
  let modeConfirmation;
  const result = Promise.resolve({ items: [{ year: 2024 }] });
  const account = [{ status: 'fulfilled', value: {} }];
  const events = [];
  const banner = { hidden: true };
  const started = runInNewContext(`(async () => { ${code} })()`, {
    AbortSignal, URLSearchParams, location: { search: '' }, document: {
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
  const code = source('bootstrap.mjs').replaceAll('import(', 'loadModule(');
  const loaded = [];
  const nodes = new Map(['test-banner', 'open-demo-banner', 'test-unavailable'].map(id => [id, { hidden: true }]));
  const root = { dataset: {} };
  await runInNewContext(`(async () => { ${code} })()`, {
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
