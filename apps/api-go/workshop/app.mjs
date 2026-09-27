import { articlePresentation, configurationLabel, filterArticles, localImageURL, readCollection, requestJSON } from './catalog.mjs';
import { loadingProgress } from './progress.mjs';

const $ = id => document.getElementById(id);
const names = ['year', 'make', 'model', 'configuration'];
const singular = { year: 'year', make: 'make', model: 'model', configuration: 'engine / trim' };
const plural = { year: 'years', make: 'makes', model: 'models', configuration: 'configurations' };
const parents = { make: 'year', model: 'make', configuration: 'model' };
const rows = { year: [], make: [], model: [], configuration: [] };
let articles = [], vehicle = null, active = null, retryAction = null, limit = 60;

function token() {
  try { return localStorage.getItem('autodata-auth-token') || 'local:demo:dataset_viewer'; }
  catch { return 'local:demo:dataset_viewer'; }
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function setStatus(text, tone = 'ready', retry = null) {
  $('activity-text').textContent = text;
  $('activity').dataset.tone = tone;
  document.body.dataset.busy = String(tone === 'loading');
  $('loading-progress').hidden = tone !== 'loading';
  $('retry').hidden = !retry;
  $('cancel').hidden = tone !== 'loading';
  retryAction = retry;
}

function resetLoadingProgress() {
  $('loading-progress').hidden = true;
  $('loading-progress-catalog').hidden = true;
  $('loading-progress-bar').value = 0;
  $('loading-progress-catalog-bar').value = 0;
  $('loading-progress-percent').textContent = '0%';
  $('loading-progress-catalog-percent').textContent = '0%';
  $('loading-progress-detail').textContent = '';
  $('loading-progress-catalog-detail').textContent = '';
}

function catalogProgressDetail(progress) {
  if (!progress || typeof progress !== 'object') return '';
  const processed = Number(progress.processed || 0).toLocaleString();
  const total = Number(progress.total || 0).toLocaleString();
  const title = String(progress.current_title || 'Untitled article');
  if (progress.phase === 'indexing') return progress.detail || `Scanning article index (${processed}/${total})…`;
  if (progress.phase === 'normalizing') {
    return progress.detail || `Building catalog… Processing article ${processed}/${total} — ${title}`;
  }
  if (progress.phase === 'persisting') return progress.detail || `Saving ${total} catalog articles…`;
  return progress.detail || '';
}

function setLoadingProgress(stageKey, options = {}) {
  const progress = loadingProgress(stageKey, options);
  const detail = options.detail || `Working on ${progress.label.toLocaleLowerCase()}…`;
  const summary = `Step ${progress.step} of ${progress.total} · ${progress.label} · ${progress.percent}%`;
  const catalog = stageKey === 'articles' && options.catalogProgress && typeof options.catalogProgress === 'object'
    ? options.catalogProgress
    : null;
  const catalogPercent = catalog ? Math.min(100, Math.max(0, Number(catalog.percent) || 0)) : 0;
  const catalogDetail = catalogProgressDetail(catalog);
  $('loading-progress').hidden = false;
  $('loading-progress-stage').textContent = summary;
  $('loading-progress-percent').textContent = `${progress.percent}%`;
  $('loading-progress-bar').value = progress.percent;
  const displayDetail = catalogDetail ? `${catalogDetail} · Total progress ${progress.percent}%` : detail;
  $('loading-progress-bar').setAttribute('aria-valuetext', `${summary}. ${displayDetail}`);
  $('loading-progress-detail').textContent = displayDetail;
  $('loading-progress-catalog').hidden = !catalog;
  if (catalog) {
    $('loading-progress-catalog-percent').textContent = `${catalogPercent}%`;
    $('loading-progress-catalog-bar').value = catalogPercent;
    $('loading-progress-catalog-bar').setAttribute('aria-valuetext', `${catalogPercent}% catalog progress. ${catalogDetail}`);
    $('loading-progress-catalog-detail').textContent = catalogDetail;
  }
  $('activity-text').textContent = `${summary} — ${displayDetail}`;
}

function show(section) {
  for (const id of ['welcome', 'catalog', 'reader']) $(id).hidden = id !== section;
}

async function run(work, retry) {
  active?.abort();
  const controller = new AbortController();
  active = controller;
  try { await work(controller.signal); }
  catch (error) {
    if (!controller.signal.aborted) setStatus(error.message || 'The catalog could not be loaded. Try again.', 'error', retry);
  } finally {
    if (active === controller) { $('cancel').hidden = true; document.body.dataset.busy = 'false'; }
  }
}

function selection(name) { return rows[name].find(row => String(row.id ?? row.year) === $(name).value); }
function vehicleName() {
  return vehicle ? [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(' ') : '';
}
function pathTo(name) {
  const year = encodeURIComponent($('year').value);
  const make = encodeURIComponent($('make').value);
  const model = encodeURIComponent($('model').value);
  return {
    year: '/v1/catalog/years',
    make: `/v1/catalog/years/${year}/makes?region=US`,
    model: `/v1/catalog/years/${year}/makes/${make}/models?region=US`,
    configuration: `/v1/catalog/years/${year}/makes/${make}/models/${model}/configurations?region=US`,
  }[name];
}

function clearAfter(name) {
  active?.abort();
  for (const next of names.slice(names.indexOf(name) + 1)) {
    rows[next] = [];
    $(next).replaceChildren(new Option(`Choose ${parents[next]} first`, ''));
    $(next).disabled = true;
  }
  resetCatalogView();
  document.title = 'AutoData — The workshop reference';
  show('welcome');
}

function resetCatalogView() {
  vehicle = null; articles = [];
  $('search').value = '';
  $('catalog-count').textContent = '';
  $('articles').replaceChildren();
  $('article-content').replaceChildren();
  $('no-results').hidden = true;
  $('show-more').hidden = true;
  resetLoadingProgress();
  show('welcome');
}

function updateURL({ article = '', replace = false } = {}) {
  const params = new URLSearchParams();
  for (const name of names) if ($(name).value) params.set(name, $(name).value);
  if (article) params.set('article', article);
  if ($('search').value) params.set('q', $('search').value);
  const url = `${location.pathname}${params.size ? `?${params}` : ''}`;
  if (url !== location.pathname + location.search) history[replace ? 'replaceState' : 'pushState'](null, '', url);
}

function populate(name, items) {
  const previous = $(name).value;
  rows[name] = name === 'year' ? [...items].sort((a, b) => b.year - a.year) : items;
  const options = [new Option(`Choose ${singular[name]}`, '')];
  for (const item of rows[name]) {
    options.push(new Option(name === 'year' ? String(item.year) : name === 'configuration' ? configurationLabel(item) : item.name, String(item.id ?? item.year)));
  }
  $(name).replaceChildren(...options);
  $(name).value = previous;
  $(name).disabled = !items.length;
}

async function loadOptions(name, signal, desired = '') {
  setStatus(`Loading ${plural[name]}…`, 'loading');
  setLoadingProgress(name, { detail: `Requesting the ${plural[name]} catalog…` });
  $(name).replaceChildren(new Option(`Loading ${plural[name]}…`, ''));
  $(name).disabled = true;
  const retry = () => run(s => loadOptions(name, s), retry);
  const data = await readCollection(() => requestJSON(pathTo(name), { signal, token: token(), timeout: 20000 }), {
    signal, desired,
    onUpdate(result, meta) {
      populate(name, result.items);
      const detail = result.hydrating && !result.complete
        ? result.items.length ? `${result.items.length} ${plural[name]} available; checking for more (attempt ${meta.attempt} of ${meta.attempts})…` : `Finding available ${plural[name]} (attempt ${meta.attempt} of ${meta.attempts})…`
        : `${result.items.length} ${plural[name]} ready.`;
      setLoadingProgress(name, { ...meta, hydrating: Boolean(result.hydrating && !result.complete), complete: result.complete === true, detail });
    },
  });
  signal.throwIfAborted();
  if (!data.items.length) {
    setStatus(data.timedOut ? `Still waiting for ${plural[name]}. Retry to check again.` : `No ${plural[name]} are available for this selection. Try again or change the vehicle.`, 'error', retry);
  } else if (data.complete === false) {
    setStatus(`${data.items.length} ${plural[name]} available. The list may still be incomplete.`, 'ready', retry);
  } else {
    setStatus(`${data.items.length} ${plural[name]} available. Choose ${singular[name]} to continue.`);
  }
  if (desired) {
    const match = data.items.find(item => String(item.id ?? item.year) === desired);
    if (!match) throw new Error(`The saved ${singular[name]} is unavailable. Choose another option above.`);
    $(name).value = desired;
  }
}

async function loadArticles(signal, articleID = '') {
  vehicle = selection('configuration');
  if (!vehicle?.vehicle_id) {
    resetCatalogView();
    setStatus('Choose an engine / trim to open the article index.');
    return;
  }
  $('vehicle-caption').textContent = `${vehicleName()} / ${configurationLabel(vehicle)}`;
  $('catalog-count').textContent = 'Loading articles…';
  $('articles').replaceChildren(); $('no-results').hidden = true; $('show-more').hidden = true;
  show('catalog');
  setStatus('Opening the vehicle’s article index…', 'loading');
  setLoadingProgress('articles', { detail: 'Requesting the vehicle article catalog…' });
  const retry = () => run(s => loadArticles(s), retryArticles);
  const data = await readCollection(
    () => requestJSON(`/v1/catalog/vehicles/${encodeURIComponent(vehicle.vehicle_id)}/articles`, { signal, token: token(), timeout: 20000 }),
    {
      signal, attempts: 40, interval: 1500,
      onUpdate(result, meta) {
        const hydrating = Boolean(result.hydrating && !result.complete);
        if (result.items.length) {
          articles = result.items; limit = 60; renderArticles();
          setLoadingProgress('articles', {
            ...meta,
            hydrating,
            complete: result.complete === true,
            catalogProgress: result.progress,
            detail: hydrating ? `${result.items.length} articles available; checking for more (attempt ${meta.attempt} of ${meta.attempts})…` : `${result.items.length} articles ready.`,
          });
          if (!hydrating) setStatus('Article index ready.');
        } else if (result.hydrating) {
          setLoadingProgress('articles', {
            ...meta,
            hydrating: true,
            catalogProgress: result.progress,
            detail: `Finding this vehicle’s articles (attempt ${meta.attempt} of ${meta.attempts})…`,
          });
        }
      },
    },
  );
  signal.throwIfAborted();
  if (!Array.isArray(data.items)) throw new Error('The article index could not be read. Try again.');
  articles = data.items; limit = 60; renderArticles();
  if (!articles.length) setStatus(data.timedOut ? 'The catalog is still preparing this vehicle. Retry to check again.' : 'No articles were returned for this vehicle. Retry or choose a different configuration.', 'error', retry);
  else setStatus(`Article index ready for ${vehicleName()}.`);
  if (articleID) await loadArticle(articleID, signal);
}

function retryArticles() { run(s => loadArticles(s), retryArticles); }

function kindLabel(kind) {
  return ({ procedure: 'Procedure', repair_procedure: 'Procedure', specification: 'Specification', technical_service_bulletin: 'Bulletin', wiring_diagram: 'Wiring diagram' })[kind] || String(kind || 'Reference').replaceAll('_', ' ').replace(/^./, char => char.toUpperCase());
}

function articleURL(id) {
  const url = new URL(location.href);
  url.searchParams.set('article', id);
  return url.pathname + url.search;
}

function renderArticles() {
  const filtered = filterArticles(articles, $('search').value);
  const fragment = document.createDocumentFragment();
  for (const item of filtered.slice(0, limit)) {
    const li = element('li'), link = element('a');
    link.href = articleURL(item.id);
    link.append(element('span', item.title || 'Untitled article'), element('span', kindLabel(item.kind), 'article-type'));
    link.addEventListener('click', event => {
      if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault(); openArticle(item.id);
    });
    li.append(link); fragment.append(li);
  }
  $('articles').replaceChildren(fragment);
  $('catalog-count').textContent = $('search').value.trim() ? `${filtered.length.toLocaleString()} matching articles / ${articles.length.toLocaleString()} in this vehicle` : `${articles.length.toLocaleString()} articles. Choose one to open.`;
  $('no-results').hidden = filtered.length > 0 || !articles.length;
  $('show-more').hidden = filtered.length <= limit;
  $('show-more').textContent = `Show ${Math.min(60, filtered.length - limit)} more articles`;
}

function openArticle(id) {
  updateURL({ article: id });
  run(s => loadArticle(id, s), () => openArticle(id));
}

function addImage(parent, image, caption) {
  const url = localImageURL(image?.url, location.origin);
  const figure = element('figure');
  if (url) {
    const img = element('img'); img.src = url; img.alt = caption; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
    img.addEventListener('error', () => { img.replaceWith(element('p', 'This illustration could not be loaded.', 'image-missing')); });
    figure.append(img, element('figcaption', caption));
  } else {
    figure.append(element('p', 'This illustration is not available in the saved article.', 'image-missing'));
  }
  parent.append(figure);
}

function renderArticle(article) {
  const presentation = articlePresentation(article);
  const images = Array.isArray(article.images) ? article.images : [];
  const used = new Set();
  $('article-title').textContent = article.title || 'Untitled article';
  $('article-kind').textContent = kindLabel(article.kind);
  $('reader-vehicle').textContent = vehicleName();
  $('reader-engine').textContent = configurationLabel(vehicle);
  const notes = [];
  if (presentation.legacy) notes.push('Showing the saved article text; formatted steps are not available for this record.');
  if (!images.length) notes.push('No illustrations are available in this saved article.');
  if (!article.complete) notes.push('This article is incomplete.');
  $('article-note').hidden = !notes.length;
  $('article-note').textContent = notes.join(' ');
  const content = $('article-content'); content.replaceChildren();
  if (presentation.steps.length) {
    const list = element('ol', undefined, 'procedure-steps');
    for (const [index, step] of presentation.steps.entries()) {
      const li = element('li');
      li.append(element('span', `${step.number ?? index + 1}.`, 'step-number'));
      if (step.heading) li.append(element('h3', step.heading));
      for (const instruction of step.instructions || []) li.append(element('p', instruction));
      for (const id of step.image_ids || []) {
        const image = images.find(image => image.id === id);
        addImage(li, image, `Illustration for step ${step.number ?? index + 1}`); used.add(id);
      }
      list.append(li);
    }
    content.append(list);
  } else if (presentation.body.trim()) {
    content.append(element('div', presentation.body, 'body-text'));
  } else {
    content.append(element('p', 'This record has no readable article text. Return to the index or try loading it again.'));
  }
  const unplaced = images.filter(image => !used.has(image.id));
  if (unplaced.length) {
    const group = element('section'); group.append(element('h3', 'Article illustrations'));
    for (const [index, image] of unplaced.entries()) addImage(group, image, `Illustration ${index + 1}`);
    content.append(group);
  }
  $('reference-data').replaceChildren();
  for (const [label, value] of [['Article ID', article.id], ['Vehicle ID', article.vehicle_id], ['Saved content', article.complete ? 'Available' : 'Incomplete']]) {
    $('reference-data').append(element('dt', label), element('dd', String(value || 'Unavailable')));
  }
  $('article-reference').open = false;
  document.title = `${article.title || 'Article'} | ${vehicleName()} | AutoData`;
}

async function loadArticle(id, signal) {
  show('reader');
  $('article-title').textContent = articles.find(article => article.id === id)?.title || 'Opening article…';
  $('article-content').replaceChildren(); $('article-note').hidden = true; $('article-reference').hidden = true;
  $('article-kind').textContent = 'Loading article';
  $('reader-vehicle').textContent = vehicleName(); $('reader-engine').textContent = configurationLabel(vehicle);
  $('print').disabled = true;
  setStatus('Opening the article. First-time preparation can take a moment…', 'loading');
  setLoadingProgress('article', { detail: 'Retrieving the saved article…' });
  const data = await requestJSON(`/v1/catalog/vehicles/${encodeURIComponent(vehicle.vehicle_id)}/articles/${encodeURIComponent(id)}`, { signal, token: token() });
  signal.throwIfAborted();
  if (!data.article || typeof data.article !== 'object') throw new Error('The article response is empty. Return to the index or try again.');
  renderArticle(data.article);
  setLoadingProgress('article', { complete: true, detail: 'Article ready.' });
  $('article-reference').hidden = false;
  $('print').disabled = false;
  const readable = articlePresentation(data.article);
  if (!readable.steps.length && !readable.body.trim()) setStatus('This article has no readable content yet.', 'error', () => openArticle(id));
  else setStatus('Article opened.');
  $('article-title').focus({ preventScroll: true });
  $('reader').scrollIntoView({ block: 'start' });
}

for (const [index, name] of names.entries()) {
  $(name).addEventListener('change', () => {
    clearAfter(name); updateURL();
    if (!$(name).value) { setStatus(`Choose ${singular[name]} to continue.`); return; }
    const next = names[index + 1];
    const retry = next ? () => run(s => loadOptions(next, s), retry) : retryArticles;
    if (next) retry(); else retryArticles();
  });
}

$('retry').addEventListener('click', () => retryAction?.());
$('cancel').addEventListener('click', () => {
  active?.abort();
  setStatus('Loading stopped. Choose an option or try again.', 'ready', restoreRoute);
});
$('search').addEventListener('input', () => { limit = 60; updateURL({ replace: true }); renderArticles(); });
$('show-more').addEventListener('click', () => { const previous = limit; limit += 60; renderArticles(); $('articles').children[previous]?.querySelector('a').focus({ preventScroll: true }); });
$('back').addEventListener('click', () => {
  active?.abort(); updateURL(); show('catalog'); renderArticles();
  document.title = `${vehicleName()} | AutoData`;
  setStatus(`Article index ready for ${vehicleName()}.`);
  $('catalog-title').focus({ preventScroll: true });
});
$('print').addEventListener('click', () => window.print());

// All navigation, including browser Back and shared URLs, rebuilds from API IDs.
function restoreRoute() {
  active?.abort();
  for (const name of names) {
    rows[name] = [];
    $(name).replaceChildren(new Option(name === 'year' ? 'Loading years…' : `Choose ${parents[name]} first`, ''));
    $(name).disabled = true;
  }
  resetCatalogView();
  document.title = 'AutoData — The workshop reference';
  const params = new URLSearchParams(location.search);
  run(async signal => {
    for (const name of names) {
      const desired = params.get(name) || '';
      await loadOptions(name, signal, desired);
      if (!desired) {
        setStatus(`Choose ${singular[name]} to continue.`);
        return;
      }
    }
    $('search').value = params.get('q') || '';
    await loadArticles(signal, params.get('article') || '');
  }, restoreRoute);
}

window.addEventListener('popstate', restoreRoute);
restoreRoute();
