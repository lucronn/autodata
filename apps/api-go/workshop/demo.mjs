// Public, repository-authored sample. All state lasts only for this page visit.
const sample = Object.freeze({
  year: '2026',
  make: 'Example Motors',
  model: 'Sample',
  configuration: 'Demonstration trim',
  title: 'Understanding this sample manual',
  provenance: 'Illustrative content authored for this demo; not supplied by Bankone or Banktwo. Not vehicle service information.',
  introduction: 'This fictional manual shows how the Workshop article index and reader fit together. The vehicle and its demonstration trim are examples created for this page.',
  navigation: 'Choose the sample vehicle, search the article title, and open the reader. Back to article index and Browse return you to the list. Changing a vehicle choice clears the choices that follow it.',
  scope: 'This sample contains no vehicle service procedures or specifications. It does not describe an actual vehicle. No real purchase or vehicle access is granted.',
});
const sampleArticles = Object.freeze([
  { title: sample.title, kind: 'Sample overview', description: sample.introduction },
  { title: 'Diagnostics sample', kind: 'Diagnostics', description: 'This fictional page shows where diagnostic guidance would be presented. It contains no tests, values, or fault-finding instructions.' },
  { title: 'Repair procedures sample', kind: 'Repair procedures', description: 'This fictional page demonstrates a procedure layout. It contains no steps, tools, torque values, or safety instructions for a real vehicle.' },
  { title: 'Maintenance intervals sample', kind: 'Maintenance intervals', description: 'This fictional page shows an interval category without any actual mileage, time, or service recommendation.' },
  { title: 'Specifications sample', kind: 'Specifications', description: 'This fictional page shows a specification category without real measurements, limits, or settings.' },
  { title: 'Fluids sample', kind: 'Fluids', description: 'This fictional page shows a fluids category without any real fluid type, quantity, or replacement guidance.' },
  { title: 'Wiring diagrams sample', kind: 'Wiring diagrams', description: 'This fictional page shows where an electrical diagram would appear. It contains no circuit, wire color, pin number, or actual diagram.' },
  { title: 'Component locations sample', kind: 'Component locations', description: 'This fictional page shows a component-location category without a real part position or removal instruction.' },
  { title: 'Technical service bulletins sample', kind: 'Technical service bulletins', description: 'This fictional page shows a bulletin category without a real bulletin, manufacturer claim, or applicability statement.' },
  { title: 'Diagnostic trouble codes sample', kind: 'Diagnostic trouble codes', description: 'This fictional page shows a trouble-code category without a real code, definition, cause, or repair advice.' },
]);
const $ = id => document.getElementById(id);
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};
const selection = ['year', 'make', 'model', 'configuration'];
const prompts = ['Choose sample year', 'Choose year first', 'Choose make first', 'Choose model first'];
const caption = `${sample.year} ${sample.make} ${sample.model}`;
let demoPurchased = false;
let checkoutReviewOpen = false;

$('demo-banner').hidden = false;
document.querySelector('.wordmark').href = '/workshop/?demo=1';
document.querySelector('.masthead p').textContent = 'Explore a fictional vehicle and sample article.';
document.querySelector('.region-note').textContent = 'Fictional sample catalog';
$('picker-title').textContent = 'Try the sample vehicle';
$('welcome-title').textContent = 'Explore the sample manual.';
document.querySelector('#welcome p').textContent = 'Choose the fictional year, make, model, and demonstration trim above. All choices stay in this page.';
document.querySelector('.welcome-note').textContent = 'Sample content only.';
$('search').placeholder = 'Try “understanding”';
$('search').setAttribute('spellcheck', 'false');
$('search').setAttribute('autocapitalize', 'off');
$('search').setAttribute('autocorrect', 'off');
for (const id of ['signin', 'signout', 'purchase-action', 'check-order', 'my-vehicles', 'library-more', 'agreement', 'print', 'source-review-load']) {
  $(id).disabled = true;
}
$('signin').textContent = 'Sign-in unavailable in demo';
$('print').textContent = 'Print unavailable in demo';
for (const id of ['signout', 'check-order', 'my-vehicles', 'library', 'account-status', 'purchase-terms', 'activity', 'loading-progress', 'source-review']) {
  $(id).hidden = true;
}
$('source-review-link').removeAttribute('href');
$('purchase-title').textContent = 'Try a demo purchase';
$('purchase-selection').textContent = `${caption} · ${sample.configuration}`;
$('purchase-price').textContent = '$20 USD · Illustrative price — no charge will be made';
$('library-intro').textContent = 'This fictional vehicle exists only in this page. No account purchase or real vehicle access is granted.';
$('purchase').hidden = false;

function renderDemoPurchase() {
  const selected = $('configuration').value === sample.configuration;
  $('purchase-action').disabled = !selected || checkoutReviewOpen;
  $('purchase-action').textContent = demoPurchased ? 'Open demo articles' : 'Try $20 demo checkout — no charge';
  $('purchase-message').textContent = demoPurchased
    ? 'Demo purchase complete. No payment, account purchase, or vehicle access was created.'
    : selected
      ? 'Review the illustrative checkout. Confirming makes no charge and unlocks only fictional sample articles.'
      : 'Choose the fictional sample vehicle to try a no-charge checkout.';
  $('demo-checkout').hidden = !checkoutReviewOpen;
}
function showCatalog() {
  $('reader').hidden = true;
  $('library').hidden = true;
  $('catalog').hidden = !demoPurchased || $('configuration').value !== sample.configuration;
  $('welcome').hidden = !$('catalog').hidden;
}
function openArticle(event, article) {
  event.preventDefault();
  if (!demoPurchased || $('configuration').value !== sample.configuration) return;
  $('catalog').hidden = true;
  $('reader').hidden = false;
  $('reader-vehicle').textContent = caption;
  $('reader-engine').textContent = sample.configuration;
  $('article-kind').textContent = `${article.kind} · Not service information`;
  $('article-title').textContent = article.title;
  $('article-note').textContent = sample.provenance;
  $('article-note').hidden = false;
  $('article-content').replaceChildren(
    node('p', article.description),
    ...(article === sampleArticles[0] ? [node('h3', 'Explore the layout'), node('p', sample.navigation)] : []),
    node('h3', 'About this sample'), node('p', sample.scope),
  );
  $('reference-data').replaceChildren(node('dt', 'Illustrative reference'), node('dd', sample.provenance));
  $('article-reference').open = false;
  $('article-title').focus();
}
function renderArticles() {
  if (!demoPurchased) {
    $('articles').replaceChildren();
    $('no-results').hidden = true;
    $('catalog-count').textContent = '';
    return;
  }
  const query = $('search').value.trim().toLowerCase();
  const matches = sampleArticles.filter(article => `${article.title} ${article.kind}`.toLowerCase().includes(query));
  $('articles').replaceChildren();
  if (matches.length) {
    const list = node('ul', undefined, 'article-list');
    for (const article of matches) {
      const item = node('li');
      const link = node('a');
      link.href = '#reader';
      link.append(node('span', article.title), node('span', article.kind, 'article-type'));
      link.addEventListener('click', event => openArticle(event, article));
      item.append(link); list.append(item);
    }
    $('articles').append(list);
  }
  $('no-results').hidden = Boolean(matches.length);
  $('catalog-count').textContent = `${matches.length} ${matches.length === 1 ? 'sample article' : 'sample articles'} · Repository-authored demonstration`;
}
function configure(index, enabled) {
  const id = selection[index];
  const placeholder = node('option', enabled ? `Choose ${id === 'configuration' ? 'sample trim' : `sample ${id}`}` : prompts[index]);
  placeholder.value = '';
  $(id).replaceChildren(placeholder);
  $(id).disabled = !enabled;
  if (enabled) {
    const option = node('option', sample[id]);
    option.value = sample[id]; $(id).append(option);
  }
}
function restoreSampleSelection() {
  selection.forEach((id, index) => {
    configure(index, true);
    $(id).value = sample[id];
  });
  $('search').value = '';
  renderDemoPurchase(); renderArticles(); showCatalog();
  $('completion-status').textContent = 'Fictional sample articles are ready. No real vehicle access is granted.';
}
selection.forEach((id, index) => {
  configure(index, index === 0);
  $(id).addEventListener('change', () => {
    checkoutReviewOpen = false;
    for (let child = index + 1; child < selection.length; child++) {
      configure(child, child === index + 1 && $(id).value === sample[id]);
    }
    $('search').value = '';
    $('vehicle-caption').textContent = `${caption} · ${sample.configuration} · Fictional sample`;
    renderDemoPurchase(); renderArticles(); showCatalog();
    $('completion-status').textContent = $('configuration').value
      ? demoPurchased ? 'Fictional sample articles are ready. No real vehicle access is granted.' : 'Demo checkout ready. No charge will be made.'
      : 'Choose the fictional sample vehicle to try a no-charge checkout.';
  });
});
$('purchase-action').addEventListener('click', () => {
  if ($('configuration').value !== sample.configuration) return;
  if (demoPurchased) { showCatalog(); $('catalog-title').focus(); return; }
  if (checkoutReviewOpen) return;
  checkoutReviewOpen = true;
  $('demo-checkout-selection').textContent = `${caption} · ${sample.configuration}`;
  renderDemoPurchase();
  $('demo-checkout-title').focus();
});
$('demo-checkout-cancel').addEventListener('click', () => {
  if (!checkoutReviewOpen) return;
  checkoutReviewOpen = false;
  renderDemoPurchase();
  $('purchase-action').focus();
});
$('demo-checkout-confirm').addEventListener('click', () => {
  if (!checkoutReviewOpen || demoPurchased || $('configuration').value !== sample.configuration) return;
  checkoutReviewOpen = false;
  demoPurchased = true;
  const item = node('li');
  const open = node('button', `${caption} · ${sample.configuration} · Fictional demo`);
  open.type = 'button';
  open.addEventListener('click', () => { restoreSampleSelection(); $('catalog-title').focus(); });
  item.append(open);
  $('library-items').replaceChildren(item);
  $('my-vehicles').disabled = false;
  $('my-vehicles').hidden = false;
  $('library-message').textContent = 'One fictional sample vehicle. No account purchase or real access.';
  renderDemoPurchase(); renderArticles(); showCatalog();
  $('completion-status').textContent = 'Demo purchase complete. No charge was made. Fictional sample articles are ready.';
  $('catalog-title').focus();
});
$('my-vehicles').addEventListener('click', () => {
  if (!demoPurchased) return;
  for (const id of ['welcome', 'catalog', 'reader']) $(id).hidden = true;
  $('library').hidden = false;
  $('library-title').focus();
});
$('search').addEventListener('input', renderArticles);
$('back').addEventListener('click', () => { showCatalog(); $('catalog-title').focus(); });
$('browse').addEventListener('click', () => {
  showCatalog();
  ($('catalog').hidden ? $('configuration').value ? $('purchase-action') : $('vehicle-picker') : $('catalog-title')).focus();
});
renderDemoPurchase();
showCatalog();
$('completion-status').textContent = 'Choose the fictional sample vehicle to try a no-charge checkout.';
