// The fictional layout sample is separate from the real-data test checkout.
const params = new URLSearchParams(location.search);
const wantsDemo = params.get('demo') === '1';
const pageReady = document.readyState === 'loading'
  ? new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }))
  : Promise.resolve();
if (params.get('sample') === '1' && !wantsDemo) {
  await pageReady;
  await import('./demo.mjs');
} else {
  if (!wantsDemo) {
    // Download the regular app and its helpers during the mode check.
    // The import below runs once the mode and checkout notice are set.
    for (const module of ['app', 'progress', 'commerce', 'article-read']) {
      const link = document.createElement('link');
      link.rel = 'modulepreload';
      link.href = `/workshop/${module}.mjs`;
      document.head.append(link);
    }
  }
  let testCheckoutReady = false;
  let openDemoReady = false;
  let preview = null;
  let initialAccount;
  try {
    const modeRequest = fetch('/workshop/demo-mode.json', { cache: 'no-store', credentials: 'same-origin' });
    if (!wantsDemo) {
      // The public years do not depend on checkout mode. Keep the result for
      // the first route without waiting for it to initialize the rest of the app.
      preview = import('./catalog.mjs')
        .then(({ requestInitialYears }) => ({ years: requestInitialYears(params) }))
        .catch(() => null);
      // Regular routes can read account status while the mode check runs.
      // The app still establishes the mode before consuming those results.
      initialAccount = import('./auth.mjs')
        .then(({ readSessionBootstrap }) => readSessionBootstrap())
        .catch(() => null);
    }
    const response = await modeRequest;
    if (response.ok) {
      const status = await response.json();
      testCheckoutReady = status?.enabled === true && Object.keys(status).length === 1;
      openDemoReady = status?.enabled === true && status?.access === 'open' && Object.keys(status).length === 2;
    }
  } catch {
    // An unavailable mode handshake must never be labeled a no-charge checkout.
  }
  // Startup requests can overlap the stylesheet and page parsing.
  await pageReady;
  if (wantsDemo && !testCheckoutReady && !openDemoReady) {
    document.getElementById('test-unavailable').hidden = false;
    document.querySelector('.site-header nav').hidden = true;
    document.querySelector('main').hidden = true;
  } else {
    document.getElementById('test-banner').hidden = !testCheckoutReady;
    document.getElementById('open-demo-banner').hidden = !(wantsDemo && openDemoReady);
    document.documentElement.dataset.workshopMode = wantsDemo && openDemoReady ? 'open-demo' : 'regular';
    const { bootstrap } = await import('./app.mjs');
    await bootstrap((await preview)?.years, initialAccount);
  }
}
