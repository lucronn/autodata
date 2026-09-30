import { articlePresentation, configurationLabel, filterArticles, localImageURL, readCollection, requestJSON } from './catalog.mjs';
import { loadingProgress } from './progress.mjs';

const $ = id => document.getElementById(id);
const names = ['year', 'make', 'model', 'configuration'];
const singular = { year: 'year', make: 'make', model: 'model', configuration: 'engine / trim' };
const plural = { year: 'years', make: 'makes', model: 'models', configuration: 'configurations' };
const parents = { make: 'year', model: 'make', configuration: 'model' };
const rows = { year: [], make: [], model: [], configuration: [] };
let articles = [], vehicle = null, active = null, retryAction = null;

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
  if (progress.phase === 'indexing') return progress.detail || 'Retrieving the article index from AutoAPItwo…';
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
        ? result.items.length ? `${result.items.length} ${plural[name]} currently available; checking saved catalog coverage…` : `Checking the saved ${plural[name]} catalog…`
        : `${result.items.length} ${plural[name]} ready.`;
      setLoadingProgress(name, { ...meta, hydrating: Boolean(result.hydrating && !result.complete), complete: result.complete === true, detail });
    },
  });
  signal.throwIfAborted();
  if (!data.items.length) {
    setStatus(data.timedOut ? `Still waiting for the ${plural[name]} catalog. Retry to check again.` : `No ${plural[name]} are available for this selection. Try again or change the vehicle.`, 'error', retry);
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
  $('articles').replaceChildren(); $('no-results').hidden = true;
  show('catalog');
  setStatus('Opening the vehicle’s article index…', 'loading');
  setLoadingProgress('articles', { detail: 'Requesting the vehicle article catalog…' });
  const retry = () => run(s => loadArticles(s), retryArticles);
  const data = await readCollection(
    () => requestJSON(`/v1/catalog/vehicles/${encodeURIComponent(vehicle.vehicle_id)}/articles`, { signal, token: token(), timeout: 20000 }),
    {
      signal,
      onUpdate(result, meta) {
        const hydrating = Boolean(result.hydrating && !result.complete);
        const progressDetail = catalogProgressDetail(result.progress);
        const waitingDetail = progressDetail || 'Retrieving the full article list from the configured sources…';
        if (result.items.length) {
          articles = result.items; renderArticles();
          setLoadingProgress('articles', {
            ...meta,
            hydrating,
            complete: result.complete === true,
            catalogProgress: result.progress,
            detail: hydrating ? `${result.items.length.toLocaleString()} articles currently available. ${waitingDetail}` : `${result.items.length.toLocaleString()} articles ready.`,
          });
          if (!hydrating) setStatus('Article index ready.');
        } else if (result.hydrating) {
          setLoadingProgress('articles', {
            ...meta,
            hydrating: true,
            catalogProgress: result.progress,
            detail: waitingDetail,
          });
        }
      },
    },
  );
  signal.throwIfAborted();
  if (!Array.isArray(data.items)) throw new Error('The article index could not be read. Try again.');
  articles = data.items; renderArticles();
  const finalProgressDetail = catalogProgressDetail(data.progress);
  if (!articles.length) {
    const detail = finalProgressDetail || (data.timedOut
      ? 'The full article list is still being retrieved from the configured sources.'
      : 'No articles were returned for this vehicle.');
    setStatus(`${detail} Retry to check again.`, 'error', retry);
  } else if (data.timedOut) {
    setStatus(`${articles.length.toLocaleString()} articles are available so far. ${finalProgressDetail || 'The full article list is still being retrieved in the background.'} Retry to check again.`, 'ready', retry);
  }
  else setStatus(`Article index ready for ${vehicleName()}.`);
  if (articleID) await loadArticle(articleID, signal);
}

function retryArticles() { run(s => loadArticles(s), retryArticles); }

function kindLabel(kind) {
  return ({ procedure: 'Procedure', repair_procedure: 'Procedure', specification: 'Specification', technical_service_bulletin: 'Bulletin', wiring_diagram: 'Wiring diagram' })[kind] || String(kind || 'Reference').replaceAll('_', ' ').replace(/^./, char => char.toUpperCase());
}

const articleCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

function displayLabel(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, character => character.toUpperCase());
}

const titleCategoryRules = [
  ['Scheduled maintenance', /\b\d{3,6}\s*(?:miles?|kilometers?|km)\b|\bmaintenance\b|\b(?:routine|normal|severe) service\b/i],
  ['Safety systems', /\b(?:airbags?|srs|supplemental restraints?|seat ?belts?|occupant restraints?|restraints?|safety)\b/i],
  ['Parts and labor', /\bparts?\s*(?:and|&)\s*labor\b/i],
  ['Air conditioning and heating', /\b(?:a\s*\/\s*c|air conditioning|evaporator|condenser|blower|heater|hvac|compressor|refrigerant|manifold gauge|evacuating system|charging the system)\b/i],
  ['Brakes', /\b(?:brakes?|abs|anti-?lock|calipers?|rotors?|master cylinders?|brake pads?|brake lines?|park brake|(?:front|rear|wheel) speed sensor)\b/i],
  ['Cooling system', /\b(?:cooling system|cooling fans?|cooling fan motors?|cooling fan relays?|radiator|thermostat|coolant|water pump)\b/i],
  ['Transmission and drivetrain', /\b(?:transmissions?|clutch(?:es)?|torque converters?|differentials?|axles?|transfer(?: cases?)?|driveshafts?|drive shafts?|transaxles?|planetary gears?|shift solenoids?|a\/t|m\/t|atf|drivetrain|gearbox|pinion|ring gear|shift interlock|shift lock|lock-up|automatic shift schedule|valve body|magnetic clutch|propeller shaft|(?:input|output) shaft|extension housing)\b/i],
  ['Fuel and emissions', /\b(?:fuel|emissions?|oxygen|o2|catalyst|catalytic|evap|injectors?|egr|mil on|emission control)\b/i],
  ['Steering and suspension', /\b(?:steering|suspension|shocks?|struts?|tie rods?|ball joints?|control arms?|wheel alignment|wheel balance|power steering)\b/i],
  ['Body and interior', /\b(?:doors?|windows?|seats?|sunvisors?|dashboard|trim|mirrors?|hood|trunks?|bumpers?|windshields?|wipers?|washers?|roof|sunroof|paint|rust|acid rain|keyless|keys?|defogger|wind noise|wind (?:turbulence|whistle)|instrument cluster|instrument panel|cruise control|radio|audio|cassette|sound systems?|clock|speaker|am[- ]?fm|am or fm|no power coming in|headlights?|horns?|lights?|locks?|body|frame|fender|interior|antitheft|arming|disarming|homelink|cigarette lighter|foamed material)\b/i],
  ['Engine', /\b(?:engine|air induction|oil|timing|camshafts?|crankshafts?|valves?|cylinders?|pistons?|spark plugs?|ignition|throttles?|accelerators?|intake|exhaust|drive belts?|idle(?:-up)?|oil pressure|gaskets?|breathers?|engine controls?|spark control|connecting rod)\b/i],
  ['Specifications and reference', /\b(?:specifications?|specs|service data|torque(?! converter)|fluid capacities?|capacities|dimensions|tightening|fluid levels?|fluid pressures?|clearance|pressure|volume|standard voltage|specific gravity)\b/i],
  ['Diagnostics and service', /\b(?:dtc|p\d{4}|p codes?|trouble codes?|diagnos(?:is|tic|tics|e|ing)?|diagnostic|symptoms?|troubleshoot(?:ing)?|inspections?|test(?:ing|s)?|checks?|warning systems?|indicator checks?|how to proceed|problem symptoms?|ecu data monitor|monitor descriptions?|obd|readiness|preliminary checks?|code definition|mode \$06|normal mode)\b/i],
  ['Electrical', /\b(?:electrical|batter(?:y|ies)|alternators?|starters?|fuses?|relays?|wiring|harness|circuits?|sockets?|sensors?|switches?|lamps?|ground|power distribution|computer data|ecm|ecu|electronic control|terminals?|speed sensor|indicator lamp|warning light|junction block|j\/b|r\/b|schematic|tachometer|magnetic switch|brush(?:es)?|mobile communications)\b/i],
  ['General service procedures', /\b(?:adjustments?|after assembly|assemble|assembly|basic subassembly|cleaning|disassembl(?:e|y)|disposal(?: procedures?)?|general procedure|installations?|on[- ]vehicle|overhaul|preparation for disassembly|procedures?|removals?|replacement|reassembly|service and repair)\b/i],
  ['Tools and service information', /\b(?:tools?|equipment|sst|adapter|gauge|service hints?|owner instructions?|owners instructions?|manual corrections?)\b/i],
];

function articleCategory(item) {
  const component = String(item.component || '').trim();
  if (component) return displayLabel(component);
  const title = String(item.title || '').trim();
  const inferred = titleCategoryRules.find(([, pattern]) => pattern.test(title));
  if (inferred) return inferred[0];
  const kind = kindLabel(item.kind);
  return ({
    Reference: 'General reference',
    Procedure: 'General service procedures',
    Specification: 'Specifications and reference',
    'Wiring diagram': 'Electrical',
  })[kind] || kind;
}

function compareArticles(left, right) {
  return articleCollator.compare(left.title || 'Untitled article', right.title || 'Untitled article')
    || articleCollator.compare(kindLabel(left.kind), kindLabel(right.kind))
    || articleCollator.compare(left.id || '', right.id || '');
}

function articleGroups(items) {
  const groups = new Map();
  for (const item of items) {
    const label = articleCategory(item);
    const key = label.toLocaleLowerCase();
    if (!groups.has(key)) groups.set(key, { label, items: [] });
    groups.get(key).items.push(item);
  }
  return [...groups.values()]
    .map(group => ({ ...group, items: group.items.slice().sort(compareArticles) }))
    .sort((left, right) => articleCollator.compare(left.label, right.label));
}

function renderCategoryArticles(list, group) {
  for (const item of group.items) {
    const li = element('li'), link = element('a');
    link.href = articleURL(item.id);
    link.append(element('span', item.title || 'Untitled article'), element('span', kindLabel(item.kind), 'article-type'));
    link.addEventListener('click', event => {
      if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault(); openArticle(item.id);
    });
    li.append(link); list.append(li);
  }
}

function articleURL(id) {
  const url = new URL(location.href);
  url.searchParams.set('article', id);
  return url.pathname + url.search;
}

function renderArticles() {
  const filtered = filterArticles(articles, $('search').value);
  const groups = articleGroups(filtered);
  const fragment = document.createDocumentFragment();
  const hasSearch = Boolean($('search').value.trim());
  for (const group of groups) {
    const category = element('details', undefined, 'article-category');
    category.open = hasSearch;
    const summary = element('summary', undefined, 'article-category-summary');
    summary.append(element('h3', group.label), element('span', `${group.items.length.toLocaleString()} article${group.items.length === 1 ? '' : 's'}`, 'article-category-count'));
    category.append(summary);
    const list = element('ul', undefined, 'article-list');
    if (hasSearch) renderCategoryArticles(list, group);
    category.addEventListener('toggle', () => {
      if (category.open) {
        if (!list.childElementCount) renderCategoryArticles(list, group);
      } else {
        list.replaceChildren();
      }
    });
    category.append(list); fragment.append(category);
  }
  $('articles').replaceChildren(fragment);
  $('catalog-count').textContent = $('search').value.trim()
    ? `${filtered.length.toLocaleString()} matching articles across ${groups.length.toLocaleString()} categories / ${articles.length.toLocaleString()} in this vehicle`
    : `${articles.length.toLocaleString()} articles across ${groups.length.toLocaleString()} categories. Choose a category to open.`;
  $('no-results').hidden = filtered.length > 0 || !articles.length;
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

function documentImage(images, block) {
  const key = String(block?.image_id || block?.asset_id || '').trim();
  return images.find(image => [image.id, image.image_id, image.asset_id, image.storage_key].some(value => value && String(value) === key)) || null;
}

function renderDocumentBlocks(parent, blocks, images) {
  let list = null;
  let listType = '';
  const flush = () => { if (list) { parent.append(list); list = null; listType = ''; } };
  const appendListItem = (type, text, number) => {
    if (!text) return;
    if (!list || listType !== type) {
      flush();
      list = element(type === 'ol' ? 'ol' : 'ul', undefined, type === 'ol' ? 'procedure-steps' : 'article-list');
      if (type === 'ol' && Number.isInteger(number)) list.start = number;
      listType = type;
    }
    const li = element('li');
    if (type === 'ol') li.append(element('span', `${number ?? list.children.length + 1}.`, 'step-number'));
    li.append(element('p', text));
    list.append(li);
  };
  for (const block of blocks) {
    if (!block || typeof block !== 'object') continue;
    const type = String(block.type || 'unknown');
    if (type === 'step') {
      appendListItem('ol', String(block.text || '').trim(), Number.isInteger(block.number) ? block.number : undefined);
      continue;
    }
    if (type === 'ordered_list' || type === 'unordered_list') {
      const listTypeName = type === 'ordered_list' ? 'ol' : 'ul';
      for (const item of block.items || []) appendListItem(listTypeName, String(item || '').trim());
      continue;
    }
    flush();
    if (type === 'heading') {
      const level = Math.max(3, Math.min(6, Number(block.level) || 3));
      parent.append(element(`h${level}`, block.text || ''));
    } else if (type === 'paragraph' || type === 'link') {
      if (type === 'link' && block.href && /^\/(?!\/)/.test(block.href)) {
        const link = element('a', block.text || ''); link.href = block.href; link.target = '_blank'; link.rel = 'noreferrer'; parent.append(link);
      } else parent.append(element('p', block.text || ''));
    } else if (type === 'callout') {
      const callout = element('aside', undefined, 'article-callout');
      callout.append(element('strong', block.label || 'Note'), element('span', block.text || ''));
      parent.append(callout);
    } else if (type === 'image') {
      const image = documentImage(images, block);
      if (image) addImage(parent, image, block.alt || 'Article illustration');
      else parent.append(element('p', block.unavailable_reason || 'This illustration is not available in the saved article.', 'image-missing'));
    } else if (type === 'table') {
      const table = element('table', undefined, 'article-table');
      if (block.label) table.append(element('caption', block.label));
      if (Array.isArray(block.columns) && block.columns.length) {
        const head = element('thead'), row = element('tr');
        for (const column of block.columns) row.append(element('th', column));
        head.append(row); table.append(head);
      }
      const body = element('tbody');
      for (const values of block.rows || []) {
        const row = element('tr');
        for (const value of values || []) {
          const cell = element('td');
          if (value && typeof value === 'object') {
            if (value.text) cell.append(element('span', value.text));
            for (const reference of value.images || []) {
              const image = documentImage(images, reference);
              if (image) addImage(cell, image, reference.alt || 'Article illustration');
              else cell.append(element('p', 'This illustration is not available in the saved article.', 'image-missing'));
            }
          } else cell.textContent = String(value || '');
          row.append(cell);
        }
        body.append(row);
      }
      table.append(body); parent.append(table);
    } else if (type === 'break') {
      parent.append(element('hr'));
    } else if (type === 'unknown') {
      const unknown = element('aside', undefined, 'article-callout');
      unknown.append(element('strong', 'Source block needs review'), element('span', block.text || 'The source block was retained but has no display-specific structure.'));
      parent.append(unknown);
    }
  }
  flush();
}

function renderLegacyBlocks(parent, blocks) {
  let list = null;
  const flush = () => { if (list) { parent.append(list); list = null; } };
  for (const block of blocks) {
    if (block.type === 'step') {
      if (!list) list = element('ol', undefined, 'procedure-steps');
      const li = element('li');
      li.append(element('span', `${block.number}.`, 'step-number'));
      for (const part of block.parts || []) {
        if (part.type === 'callout') {
          const callout = element('aside', undefined, 'article-callout');
          callout.append(element('strong', part.label), element('span', part.text));
          li.append(callout);
        } else if (part.text) li.append(element('p', part.text));
      }
      list.append(li);
      continue;
    }
    flush();
    if (block.type === 'heading') parent.append(element('h3', block.text, 'legacy-heading'));
    else if (block.type === 'callout') {
      const callout = element('aside', undefined, 'article-callout');
      callout.append(element('strong', block.label), element('span', block.text));
      parent.append(callout);
    } else if (block.text) parent.append(element('p', block.text));
  }
  flush();
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
  if (presentation.legacy) notes.push('This saved article was formatted for display from the source text; source order is preserved.');
  if (!images.length) notes.push('No illustrations are available in this saved article.');
  if (!article.complete) notes.push('This article is incomplete.');
  $('article-note').hidden = !notes.length;
  $('article-note').textContent = notes.join(' ');
  const content = $('article-content'); content.replaceChildren();
  if (presentation.documentBlocks.length) {
    renderDocumentBlocks(content, presentation.documentBlocks, images);
  } else if (presentation.steps.length) {
    const list = element('ol', undefined, 'procedure-steps');
    for (const [index, step] of presentation.steps.entries()) {
      const li = element('li');
      li.append(element('span', `${step.number ?? index + 1}.`, 'step-number'));
      if (step.heading) li.append(element('h3', step.heading));
      for (const instruction of step.instructions || []) li.append(element('p', instruction));
      for (const id of step.image_ids || []) {
        const image = images.find(image => image.id === id || image.image_id === id);
        if (image) {
          addImage(li, image, `Illustration for step ${step.number ?? index + 1}`);
          used.add(image.id || image.image_id);
        }
      }
      list.append(li);
    }
    content.append(list);
  } else if (presentation.blocks.length) {
    renderLegacyBlocks(content, presentation.blocks);
  } else if (presentation.body.trim()) {
    content.append(element('div', presentation.body, 'body-text'));
  } else {
    content.append(element('p', 'This record has no readable article text. Return to the index or try loading it again.'));
  }
  const documentImageIDs = new Set(presentation.documentBlocks.flatMap(block => {
    if (block.type === 'image') return [block.image_id, block.asset_id];
    return (block.rows || []).flatMap(row => (row || []).flatMap(cell => cell?.images?.flatMap(image => [image.image_id, image.asset_id]) || []));
  }).filter(Boolean));
  const unplaced = images.filter(image => !used.has(image.id) && !documentImageIDs.has(image.id) && !documentImageIDs.has(image.image_id) && !documentImageIDs.has(image.storage_key));
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
  if (!readable.steps.length && !readable.blocks.length && !readable.body.trim()) setStatus('This article has no readable content yet.', 'error', () => openArticle(id));
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
$('search').addEventListener('input', () => { updateURL({ replace: true }); renderArticles(); });
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
