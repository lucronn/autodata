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
function openArticle(event) {
  event.preventDefault();
  if (!demoPurchased || $('configuration').value !== sample.configuration) return;
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
  if (!demoPurchased) {
    $('articles').replaceChildren();
    $('no-results').hidden = true;
    $('catalog-count').textContent = '';
    return;
  }
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
  open.addEventListener('click', () => { showCatalog(); $('catalog-title').focus(); });
  item.append(open);
  $('library-items').replaceChildren(item);
  $('my-vehicles').disabled = false;
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
