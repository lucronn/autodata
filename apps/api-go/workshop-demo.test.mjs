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
test('demo purchase review can cancel, confirm once, and resets on a new page visit', () => {
  const $ = demoDOM();
  assert.equal($('purchase-action').disabled, true);
  for (const [id, value] of [['year', '2026'], ['make', 'Example Motors'], ['model', 'Sample'], ['configuration', 'Demonstration trim']]) {
    $(id).value = value; $(id).fire('change');
  }
  assert.equal($('catalog').hidden, true, 'selecting a sample must not grant demo access');
  assert.equal($('purchase-action').disabled, false);
  assert.match($('purchase-price').textContent, /no charge/i);
  $('purchase-action').fire('click');
  assert.equal($('demo-checkout').hidden, false);
  assert.equal($('demo-checkout-title').focused, true);
  assert.equal($('purchase-action').disabled, true);
  $('demo-checkout-cancel').fire('click');
  assert.equal($('demo-checkout').hidden, true);
  assert.equal($('catalog').hidden, true);
  assert.equal($('purchase-action').focused, true);
  $('purchase-action').fire('click');
  $('browse').fire('click');
  assert.equal($('demo-checkout').hidden, true, 'Browse closes an unfinished review');
  assert.equal($('purchase-action').disabled, false, 'Browse restores an enabled demo action');
  assert.equal($('catalog').hidden, true);
  $('purchase-action').fire('click');
  $('demo-checkout-confirm').fire('click');
  assert.equal($('demo-checkout').hidden, true);
  assert.equal($('catalog').hidden, false);
  assert.equal($('my-vehicles').disabled, false);
  assert.equal($('my-vehicles').hidden, false, 'the sample library must be reachable after demo purchase');
  assert.match($('purchase-message').textContent, /no (?:payment|charge)/i);
  $('demo-checkout-confirm').fire('click');
  assert.equal($('library-items').children.length, 1, 'a duplicate confirmation must not add a second sample vehicle');
  const fresh = demoDOM();
  assert.equal(fresh('purchase-action').disabled, true);
  assert.equal(fresh('catalog').hidden, true);
  assert.equal(fresh('library').hidden, true);
});
test('selectors, search, reader, back and reset work after demo purchase', () => {
  const $ = demoDOM();
  assert.equal($('demo-banner').hidden, false);
  assert.equal($('year').disabled, false); assert.equal($('make').disabled, true);
  for (const [id, value] of [['year', '2026'], ['make', 'Example Motors'], ['model', 'Sample'], ['configuration', 'Demonstration trim']]) {
    assert.equal($(id).disabled, false); $(id).value = value; $(id).fire('change');
  }
  assert.equal($('catalog').hidden, true);
  $('purchase-action').fire('click'); $('demo-checkout-confirm').fire('click');
  assert.equal($('catalog').hidden, false); assert.match($('purchase-price').textContent, /\$20 USD/);
  for (const id of ['signin', 'check-order']) assert.equal($(id).disabled, true);
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
test('demo purchase opens fictional Workshop categories and an in-page sample library', () => {
  const $ = demoDOM();
  for (const [id, value] of [['year', '2026'], ['make', 'Example Motors'], ['model', 'Sample'], ['configuration', 'Demonstration trim']]) {
    $(id).value = value; $(id).fire('change');
  }
  $('purchase-action').fire('click'); $('demo-checkout-confirm').fire('click');
  const links = $('articles').children[0].children.map(item => item.children[0]);
  assert.equal(links.length, 10, 'overview plus all nine requested data categories');
  const titles = links.map(link => link.children[0].textContent);
  for (const category of ['Diagnostics', 'Repair procedures', 'Maintenance intervals', 'Specifications', 'Fluids', 'Wiring diagrams', 'Component locations', 'Technical service bulletins', 'Diagnostic trouble codes']) {
    assert.ok(titles.includes(`${category} sample`), `${category} fixture is reachable`);
  }
  $('search').value = 'diagnostic trouble codes'; $('search').fire('input');
  assert.equal($('articles').children[0].children.length, 1);
  $('articles').children[0].children[0].children[0].fire('click');
  assert.equal($('reader').hidden, false);
  assert.equal($('article-title').textContent, 'Diagnostic trouble codes sample');
  assert.match($('article-kind').textContent, /Not service information/);
  assert.match($('article-note').textContent, /not supplied by Bankone or Banktwo/);
  $('back').fire('click');
  assert.equal($('catalog').hidden, false);
  $('my-vehicles').fire('click');
  assert.equal($('library').hidden, false);
  assert.match($('library-intro').textContent, /No account purchase or real vehicle access/);
  assert.equal($('library-items').children.length, 1);
  $('library-items').children[0].children[0].fire('click');
  assert.equal($('library').hidden, true);
  assert.equal($('catalog').hidden, false);
  $('year').value = ''; $('year').fire('change');
  assert.equal($('catalog').hidden, true);
  $('my-vehicles').fire('click');
  assert.equal($('library').hidden, false);
  $('library-items').children[0].children[0].fire('click');
  assert.equal($('configuration').value, 'Demonstration trim', 'opening the saved sample restores its picker selection');
  assert.equal($('catalog').hidden, false, 'the saved sample reopens its article index after picker reset');
});
