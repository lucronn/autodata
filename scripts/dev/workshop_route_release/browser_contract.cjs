'use strict';
const WORKSHOP_ASSETS = Object.freeze([
  'app.mjs','article-read.mjs','auth.mjs','bootstrap.mjs','catalog.mjs','commerce.mjs','demo.mjs',
  'firebase-web.mjs','firebase-web.mjs.LEGAL.txt','firebase-web.provenance.json',
  'fonts/InstrumentSans.ttf','fonts/OFL.txt','index.html','progress.mjs','styles.css',
]);
const STATIC_GET_PATHS = new Set([
  '/workshop','/workshop/','/workshop/purchase-config.json','/workshop/demo-mode.json',
  ...WORKSHOP_ASSETS.map(name=>'/workshop/'+name),
]);
function requestDecision(method, value, appOrigin) {
  const url = new URL(value);
  if (url.origin !== appOrigin || url.username || url.password || url.hash) return 'deny_external';
  if (method === 'POST' && url.pathname === '/cdn-cgi/rum' && !url.search) return 'suppress_edge_telemetry';
  if (method !== 'GET') return 'deny_write';
  if (url.search) return 'deny_query';
  if (url.pathname === '/auth/config' || url.pathname === '/auth/session') return 'allow';
  if (url.pathname === '/v1/catalog/years') return 'suppress_catalog_prefetch';
  return STATIC_GET_PATHS.has(url.pathname) ? 'allow' : 'deny_unexpected_read';
}

function failure(code) { const error = new Error(code); error.code = code; return error; }
async function installRoutes(context, origin, { configGateTimeout = 6000, fulfillAllowed = null } = {}) {
  const appOrigin = new URL(origin).origin;
  const state = { blockedRequests: [], suppressedEdgeTelemetry: [], suppressedCatalogPrefetch: [], configRequests: 0, gateExpired: false };
  let releaseBarrier, gateTimer, released = false, resolveCatalog, resolveConfigHeld;
  const barrier = new Promise(resolve => { releaseBarrier = resolve; });
  const catalog = new Promise(resolve => { resolveCatalog = resolve; });
  const configHeld = new Promise(resolve => { resolveConfigHeld = resolve; });
  function releaseConfig() { released = true; clearTimeout(gateTimer); releaseBarrier(true); }
  await context.route('**/*', async route => {
    const request = route.request(); const url = new URL(request.url());
    const decision = requestDecision(request.method(), url.href, appOrigin);
    if (decision === 'suppress_edge_telemetry') {
      state.suppressedEdgeTelemetry.push({method:'POST',route:'cloudflare_rum',syntheticBrowserResponse:true,networkDispatched:false});
      return route.fulfill({status:204,body:''});
    }
    if (decision === 'suppress_catalog_prefetch') {
      state.suppressedCatalogPrefetch.push({ method: 'GET', route: 'catalog_year_prefetch', syntheticBrowserResponse: true, networkDispatched: false });
      resolveCatalog();
      return route.fulfill({ status:200, contentType:'application/json', body:JSON.stringify({items:[],complete:true,hydrating:false}) });
    }
    if (decision !== 'allow') {
      state.blockedRequests.push({ method: request.method(), origin: url.origin, pathname: url.pathname, reason: decision });
      return route.abort();
    }
    if (url.origin === appOrigin && url.pathname === '/auth/config') {
      state.configRequests++;
      if (!released) {
        resolveConfigHeld();
        gateTimer ??= setTimeout(() => { state.gateExpired = true; releaseBarrier(false); }, configGateTimeout);
        if (!await barrier) { state.blockedRequests.push({ method:'GET', origin:appOrigin, reason:'config_gate_deadline' }); return route.abort(); }
      }
    }
    if (fulfillAllowed && await fulfillAllowed(route, url)) return;
    return route.continue();
  });
  return { state, releaseConfig,
    isConfigHeld: () => !released && !state.gateExpired && state.configRequests > 0,
    async waitForConfigHeld(timeout = 5000) {
      let timer;
      try { await Promise.race([configHeld,new Promise((_,reject)=>{timer=setTimeout(()=>reject(failure('config_interception_missing')),timeout);})]); }
      finally { clearTimeout(timer); }
      if (released || state.gateExpired) throw failure('config_gate_not_held');
    },
    async waitForCatalogSuppression(timeout = 5000) {
    let timer;
    try { await Promise.race([catalog,new Promise((_,reject)=>{ timer=setTimeout(()=>reject(failure('catalog_suppression_missing')),timeout); })]); }
    finally { clearTimeout(timer); }
  } };
}
async function observeSignIn(page, origin, controller, { readyTimeout = 20000, attachmentTimeout = 5000, configHeldTimeout = 5000 } = {}) {
  try {
    const response = await page.goto(origin, { waitUntil:'commit', timeout:20000 });
    const button = page.locator('#signin'); await button.waitFor({ state:'attached', timeout:attachmentTimeout });
    await controller.waitForConfigHeld(configHeldTimeout);
    const initialDisabled = await button.isDisabled();
    if (!controller.isConfigHeld()) throw failure('config_gate_not_held');
    if (!initialDisabled) throw failure('initial_signin_enabled');
    controller.releaseConfig();
    try { await page.waitForFunction(()=>{ const button=document.querySelector('#signin'); return button && !button.disabled; },null,{timeout:readyTimeout}); }
    catch { throw failure('signin_ready_timeout'); }
    if (!controller.state.configRequests || controller.state.gateExpired) throw failure('config_gate_not_verified');
    return { htmlStatus:response?.status()??null, initialDisabled, configGateVerified:true };
  } finally { controller.releaseConfig(); }
}
module.exports = { WORKSHOP_ASSETS, requestDecision, installRoutes, observeSignIn };
