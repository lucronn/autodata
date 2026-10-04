import test from 'node:test';
import assert from 'node:assert/strict';
import { articlePresentation, configurationLabel, filterArticles, legacyArticleBlocks, localImageURL, readCollection, requestJSON } from './workshop/catalog.mjs';
import { LOAD_STAGES, loadingProgress } from './workshop/progress.mjs';

test('loading progress uses fixed ordered stages and caps incomplete hydration', () => {
  assert.deepEqual(LOAD_STAGES.map(stage => stage.key), ['year', 'make', 'model', 'configuration', 'articles', 'article']);
  assert.equal(loadingProgress('make', { complete: true }).percent, 30);
  const partial = loadingProgress('make', { attempt: 40, attempts: 40, hydrating: true });
  assert.equal(partial.step, 2);
  assert.equal(partial.total, 6);
  assert.equal(partial.percent, 27);
  assert.ok(partial.percent < 30);
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
  assert.equal(localImageURL('/images/a.png', 'http://localhost:8080'), 'http://localhost:8080/images/a.png');
  for (const url of ['https://provider.example/a.png', '//provider.example/a.png', 'javascript:alert(1)', 'data:image/svg+xml,<svg/>', 'artifact://missing']) assert.equal(localImageURL(url, 'http://localhost:8080'), null);
  assert.equal(localImageURL('data:image/png;base64,YQ==', 'http://localhost:8080'), 'data:image/png;base64,YQ==');
});

test('search matches all words without changing catalog order or IDs', () => {
  const articles = [{ id: 'one', title: 'Oil Pump Removal', kind: 'procedure' }, { id: 'two', title: 'Water Pump' }, { id: 'three', title: 'Oil Pump Installation' }];
  assert.deepEqual(filterArticles(articles, ' PUMP oil ').map(a => a.id), ['one', 'three']);
  assert.deepEqual(filterArticles(articles, ''), articles);
  assert.equal(configurationLabel({ engine: '2.0', trim: 'Base' }), '2.0 / Base');
});
