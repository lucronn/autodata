// The fictional layout sample is separate from the real-data test checkout.
const params = new URLSearchParams(location.search);
const wantsDemo = params.get('demo') === '1';
const pickerStartup = globalThis.workshopPickerStartup;
const demoIndex = globalThis.workshopDemoIndex;
delete globalThis.workshopPickerStartup;
delete globalThis.workshopDemoIndex;
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
      if (pickerStartup?.takeYearPicker) pickerStartup.requestMake = requestJSON;
      const request = (path, options) => {
        const pending = pickerStartup?.get(path);
        if (!pending) return requestJSON(path, options);
        pickerStartup.delete(path);
        function forwardAbort(signal) {
          if (signal?.aborted) pending.controller.abort(signal.reason);
          else signal?.addEventListener('abort', () => pending.controller.abort(signal.reason), { once: true });
        }
        if (pending.rawResponse) return requestJSON(path, {
          ...options,
          async fetcher(resource, init) {
            forwardAbort(init.signal);
            return (await pending.response) ?? fetch(resource, init);
          },
        });
        forwardAbort(options?.signal);
        return pending.response;
      };
      const selectors = startSavedSelectorReads(params, request);
      return { request, selectors, years: selectors ? null : requestInitialYears(params, request) };
    })
    .catch(() => null);
  const initialAccount = wantsDemo ? undefined : Promise.all([import('./auth.mjs'), preview])
    .then(([{ readSessionBootstrap }, initial]) => readSessionBootstrap(initial?.request, {
      includeLibrary: params.get('view') === 'library' && !params.has('order'),
      route: params,
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
    const initial = await preview;
    const { bootstrap } = await import('./app.mjs');
    const purchasePath = '/workshop/purchase-config.json';
    const initialPurchaseConfig = pickerStartup?.has(purchasePath)
      ? initial?.request(purchasePath) : null;
    await bootstrap(initial?.years, initialAccount, {
      initialSelectors: initial?.selectors,
      initialYearPicker: pickerStartup?.takeYearPicker?.(),
      initialPurchaseConfig,
      initialReaderRequest: pickerStartup?.retainedReader,
      testCheckout: wantsDemo ? undefined : modeRequest.then(mode => mode.testCheckout === true),
      initialDemoIndex: openDemo ? demoIndex : null,
    });
  }
}
