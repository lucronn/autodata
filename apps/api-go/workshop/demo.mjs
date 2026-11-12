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
  scope: 'This sample contains no vehicle service procedures or specifications. It does not describe an actual vehicle. No purchase or vehicle access is granted.',
});
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

$('demo-banner').hidden = false;
document.querySelector('.wordmark').href = '/workshop/?sample=1';
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
$('purchase-action').textContent = 'Checkout unavailable in demo';
$('print').textContent = 'Print unavailable in demo';
for (const id of ['signout', 'check-order', 'my-vehicles', 'library', 'account-status', 'purchase-terms', 'activity', 'loading-progress', 'source-review']) {
  $(id).hidden = true;
}
$('source-review-link').removeAttribute('href');
$('purchase-title').textContent = 'Illustrative vehicle price';
$('purchase-selection').textContent = `${caption} · ${sample.configuration}`;
$('purchase-price').textContent = '$20 USD · Illustrative price — checkout unavailable in demo';
$('purchase-message').textContent = 'No payment, purchase or vehicle access is granted.';
$('purchase').hidden = false;

function showCatalog() {
  $('reader').hidden = true;
  $('catalog').hidden = !$('configuration').value;
  $('welcome').hidden = !$('catalog').hidden;
}
function openArticle(event) {
  event.preventDefault();
  $('catalog').hidden = true;
  $('reader').hidden = false;
  $('reader-vehicle').textContent = caption;
  $('reader-engine').textContent = sample.configuration;
  $('article-kind').textContent = 'Sample overview · Not service information';
  $('article-title').textContent = sample.title;
  $('article-note').textContent = sample.provenance;
  $('article-note').hidden = false;
  $('article-content').replaceChildren(
    node('p', sample.introduction),
    node('h3', 'Explore the layout'), node('p', sample.navigation),
    node('h3', 'About this sample'), node('p', sample.scope),
  );
  $('reference-data').replaceChildren(node('dt', 'Illustrative reference'), node('dd', sample.provenance));
  $('article-reference').open = false;
  $('article-title').focus();
}
function renderArticles() {
  const matches = sample.title.toLowerCase().includes($('search').value.trim().toLowerCase());
  $('articles').replaceChildren();
  if (matches) {
    const list = node('ul', undefined, 'article-list');
    const item = node('li');
    const link = node('a');
    link.href = '#reader';
    link.append(node('span', sample.title), node('span', 'Sample overview', 'article-type'));
    link.addEventListener('click', openArticle);
    item.append(link); list.append(item); $('articles').append(list);
  }
  $('no-results').hidden = matches;
  $('catalog-count').textContent = matches ? '1 sample article · Repository-authored demonstration' : '0 matching sample articles';
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
selection.forEach((id, index) => {
  configure(index, index === 0);
  $(id).addEventListener('change', () => {
    for (let child = index + 1; child < selection.length; child++) {
      configure(child, child === index + 1 && $(id).value === sample[id]);
    }
    $('search').value = '';
    $('vehicle-caption').textContent = `${caption} · ${sample.configuration} · Fictional sample`;
    renderArticles(); showCatalog();
    $('completion-status').textContent = $('configuration').value ? 'Sample article index ready. No vehicle access is granted.' : 'Choose the fictional sample vehicle to explore its article index.';
  });
});
$('search').addEventListener('input', renderArticles);
$('back').addEventListener('click', () => { showCatalog(); $('catalog-title').focus(); });
$('browse').addEventListener('click', () => {
  showCatalog();
  ($('catalog').hidden ? $('vehicle-picker') : $('catalog-title')).focus();
});
$('completion-status').textContent = 'Choose the fictional sample vehicle to explore its article index.';
