import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
const source = name => readFileSync(new URL(`./workshop/${name}`, import.meta.url), 'utf8');
test('HTML starts only the isolated bootstrap', () => {
  assert.match(source('index.html'), /src="\/workshop\/bootstrap.mjs"/);
  assert.doesNotMatch(source('index.html'), /src="\/workshop\/(app|demo)\.mjs"/);
});
test('only explicit demo=1 loads the demo module', async () => {
  assert.ok(existsSync(new URL('./workshop/bootstrap.mjs', import.meta.url)), 'bootstrap must exist');
  const code = source('bootstrap.mjs').replaceAll('import(', 'loadModule(');
  for (const [search, expected] of [['?demo=1', './demo.mjs'], ['', './app.mjs'], ['?demo=0', './app.mjs'], ['?demo=true', './app.mjs']]) {
    const loaded = [];
    await runInNewContext(`(async () => { ${code} })()`, { URLSearchParams, location: { search }, loadModule: async path => loaded.push(path) });
    assert.deepEqual(loaded, [expected]);
  }
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
