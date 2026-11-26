// The fictional layout sample is separate from the real-data test checkout.
const params = new URLSearchParams(location.search);
const wantsDemo = params.get('demo') === '1';
const pickerStartup = globalThis.workshopPickerStartup;
delete globalThis.workshopPickerStartup;
const pageReady = document.readyState === 'loading'
  ? new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }))
  : Promise.resolve();

async function readDemoMode() {
  try {
    const response = await fetch('/workshop/demo-mode.json', {
      cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) return {};
    const status = await response.json();
    return {
      testCheckout: status?.enabled === true && Object.keys(status).length === 1,
      openDemo: status?.enabled === true && status?.access === 'open' && Object.keys(status).length === 2,
    };
  } catch {
    return {};
  }
}

if (params.get('sample') === '1' && !wantsDemo) {
  await pageReady;
  await import('./demo.mjs');
} else {
  if (!wantsDemo && !pickerStartup) {
    // Download the regular app and its helpers during the startup reads.
    for (const module of ['app', 'commerce', 'article-read']) {
      const link = document.createElement('link');
      link.rel = 'modulepreload';
      link.href = new URL(`./${module}.mjs`, import.meta.url).href;
      document.head.append(link);
    }
  }
  const entry = document.documentElement.dataset;
  const openDemoInEntry = entry.workshopOpenDemo === 'true' ||
    entry.workshopDemoOrigins?.split(' ').includes(location.origin);
  const modeRequest = wantsDemo && openDemoInEntry
    ? Promise.resolve({ openDemo: true })
    : readDemoMode();
  const preview = wantsDemo ? null : import('./catalog.mjs')
    .then(({ requestJSON, requestInitialYears, startSavedSelectorReads }) => {
      const request = (path, options) => {
        const pending = pickerStartup?.get(path);
        if (!pending) return requestJSON(path, options);
        pickerStartup.delete(path);
        const signal = options?.signal;
        if (signal?.aborted) pending.controller.abort(signal.reason);
        else signal?.addEventListener('abort', () => pending.controller.abort(signal.reason), { once: true });
        return pending.response;
      };
      const selectors = startSavedSelectorReads(params, request);
      return { selectors, years: selectors ? null : requestInitialYears(params, request) };
    })
    .catch(() => null);
  const initialAccount = wantsDemo ? undefined : import('./auth.mjs')
    .then(({ readSessionBootstrap }) => readSessionBootstrap(undefined, {
      includeLibrary: params.get('view') === 'library' && !params.has('order'),
    }))
    .catch(() => null);
  const { testCheckout, openDemo } = wantsDemo ? await modeRequest : {};
  // Startup requests can overlap the stylesheet and page parsing.
  await pageReady;
  if (wantsDemo && !testCheckout && !openDemo) {
    document.getElementById('test-unavailable').hidden = false;
    document.querySelector('.site-header nav').hidden = true;
    document.querySelector('main').hidden = true;
  } else {
    document.getElementById('test-banner').hidden = !testCheckout;
    document.getElementById('open-demo-banner').hidden = !openDemo;
    document.documentElement.dataset.workshopMode = openDemo ? 'open-demo' : 'regular';
    const { bootstrap } = await import('./app.mjs');
    const initial = await preview;
    await bootstrap(initial?.years, initialAccount, {
      initialSelectors: initial?.selectors,
      testCheckout: wantsDemo ? undefined : modeRequest.then(mode => mode.testCheckout === true),
    });
  }
}
