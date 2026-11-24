import * as catalog from "./catalog.mjs";
import { createSession } from "./auth.mjs";
import * as commerce from "./commerce.mjs";
import {
  NavigationGeneration,
  readArticle,
  readableArticle,
  processingArticle,
} from "./article-read.mjs";

const {
  articlePresentation,
  articleSearchParams,
  configurationLabel,
  selectorLabel,
  delay,
  filterArticles,
  localImageURL,
  readCollection,
  requestJSON,
  requestArticleJSON,
  requestInitialYears,
  requestStoredSelector,
  selectedIndexSessionPreference,
  sourceReferenceURL,
  trimArticleSearch,
  vehicleSelectorPath,
} = catalog;
const {
  createCheckout,
  quoteConfigurationLabel,
  validQuote,
  validScope,
  validLibrary,
  purchaseConfiguration,
  pollOrder,
  readOrder,
  resumableCheckoutURL,
  sameScope,
  uuid,
} = commerce;

const $ = (id) => document.getElementById(id);
const openDemo = document.documentElement.dataset.workshopMode === 'open-demo';
if (openDemo) {
  for (const id of ['signin', 'signout', 'my-vehicles']) $(id).hidden = true;
  $('account-status').hidden = true;
  document.querySelector('.wordmark').href = '/workshop?demo=1';
}
const demoPath = (path) => {
  if (!openDemo) return path;
  const url = new URL(path, location.origin);
  url.searchParams.set('demo', '1');
  return url.pathname + url.search;
};
const names = ["year", "make", "model", "configuration"];
const loadingStages = [
  ["year", "Years"],
  ["make", "Makes"],
  ["model", "Models"],
  ["configuration", "Engine / trim"],
  ["articles", "Article catalog"],
  ["article", "Article"],
];
const rows = Object.fromEntries(names.map((name) => [name, []]));
const pickerStates = new Map();
const selectorCache = new Map();
const selectorCacheLifetime = 30_000;
const selectorCacheSize = 32;
const navigation = new NavigationGeneration();
const searchNavigation = new NavigationGeneration();
const checkout = createCheckout();
let testStripeMode = $("test-banner").hidden === false;
let checkoutModeReady = null;
let vehicle = null,
  articles = [],
  articlePage = 0,
  indexPage = null,
  pendingIndexPage = null,
  indexLoaded = false,
  indexComplete = false,
  indexHydrating = false,
  indexFailed = false,
  searchItems = null,
  searchQuery = "",
  searchPending = false,
  searchRefreshPending = false,
  searchComplete = false,
  searchError = false,
  searchTimer = null,
  currentArticle = null,
  renderedRevision = "",
  sourceURL = "",
  sourceRevision = 0,
  displayedSourceRevision = 0;
let quote = null,
  merchant = null,
  merchantRequest = null,
  access = "unknown",
  libraryCursor = null,
  libraryPageRequest = null,
  currentOrder = "",
  paidOrder = null,
  unconfirmedOrder = null,
  retryAction = null,
  articleImageRefresh = null,
  deferredArticleFigures = null,
  sourceImageRefresh = null,
  sourceDocumentRequest = null,
  mountedSource = null,
  viewGeneration = null,
  articleIndexOrigin = null,
  sessionRequest = null,
  sessionEstablished = false,
  signingIn = false;
const element = (tag, text, className) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = String(text);
  if (className) n.className = className;
  return n;
};
const session = createSession({
  onChange(state) {
    $("signin").hidden = state.authenticated;
    $("signin").disabled = !state.ready;
    $("signin").textContent = state.confirm
      ? "Confirm Google sign-in"
      : "Sign in with Google";
    $("signout").hidden = !state.authenticated && !state.csrf;
    $("account-status").textContent = state.message;
    renderPurchase();
  },
});
const scope = () => ({
  configuration_id: vehicle?.id,
  region: vehicle?.region,
});
const articlePath = (id) =>
  `/v1/catalog/vehicles/${encodeURIComponent(vehicle.id)}/articles${id ? `/${encodeURIComponent(id)}` : ""}`;
function articleRequestPath(id, suffix = "", query) {
  const params = new URLSearchParams(query);
  params.set("region", vehicle.region);
  return demoPath(`${articlePath(id)}${suffix}?${params}`);
}
function status(
  text,
  { error = false, busy = false, retry = null, retryText = "Try again", complete = false, cancelable = busy } = {},
) {
  $("activity-text").textContent = text;
  $("activity").dataset.tone = error ? "error" : busy ? "loading" : "ready";
  $("critical-error").textContent = error ? text : "";
  if (complete) $("completion-status").textContent = text;
  $("cancel").hidden = !cancelable;
  $("retry").hidden = !retry;
  if (retry) $("retry").textContent = retryText;
  retryAction = retry;
  $("loading-progress").hidden = !busy;
  document.body.dataset.busy = String(busy);
}
function stage(key) {
  const index = Math.max(0, loadingStages.findIndex(([stageKey]) => stageKey === key));
  $("loading-progress-stage").textContent =
    `Step ${index + 1} of ${loadingStages.length} · ${loadingStages[index][1]}`;
  $("loading-progress-bar").removeAttribute("value");
}
function show(id) {
  if (id !== "reader") document.title = "AutoData — The workshop reference";
  for (const section of ["welcome", "catalog", "reader", "library"])
    $(section).hidden = section !== id;
}
function clearProtected() {
  document.title = "AutoData — The workshop reference";
  articleIndexOrigin = null;
  searchNavigation.clear();
  clearTimeout(searchTimer);
  searchItems = null;
  searchQuery = "";
  searchPending = false;
  searchRefreshPending = false;
  searchComplete = false;
  searchError = false;
  searchTimer = null;
  articles = [];
  articlePage = 0;
  indexPage = null;
  pendingIndexPage = null;
  indexLoaded = false;
  indexComplete = false;
  indexHydrating = false;
  indexFailed = false;
  resetReaderContent();
  for (const id of ["articles", "reference-data"])
    $(id).replaceChildren();
  $("article-title").textContent = "";
  $("catalog-count").textContent = "";
  $("article-page-range").textContent = "";
  $("article-pages").hidden = true;
  $("article-prev").disabled = true;
  $("article-next").disabled = true;
  $("reader").hidden = true;
  $("catalog").hidden = true;
  clearLibrary();
  access = "unknown";
}
function clearLibrary() {
  $("library-items").replaceChildren();
  libraryCursor = null;
  libraryPageRequest = null;
  $("library-more").hidden = true;
  $("library-more").removeAttribute("aria-disabled");
  $("library-message").textContent = "";
}
function setSourceLoading(loading) {
  $("source-review-load").disabled = loading;
  $("open-original").disabled = loading;
  $("open-original").textContent = loading ? "Opening Original…" : "View Original";
  if (loading) $("original-error").hidden = true;
}
function resetSourceReview() {
  sourceImageRefresh = null;
  sourceDocumentRequest = null;
  mountedSource = null;
  sourceURL = "";
  ++sourceRevision;
  displayedSourceRevision = sourceRevision;
  delete $("reader").dataset.readingOriginal;
  $("source-review").hidden = true;
  $("open-original").hidden = true;
  $("original-error").hidden = true;
  $("back-to-article").hidden = true;
  setSourceLoading(false);
  $("source-review-frame").replaceChildren();
  $("source-review-frame").hidden = true;
  $("source-review-link").removeAttribute("href");
  $("source-review-meta").textContent = "";
}
function resetReaderContent() {
  currentArticle = null;
  renderedRevision = "";
  articleImageRefresh = null;
  deferredArticleFigures = null;
  resetSourceReview();
  $("article-content").replaceChildren();
  $("article-reference").hidden = true;
  $("article-reference").open = false;
  $("article-kind").textContent = "";
  $("article-note").hidden = true;
  $("article-note").textContent = "";
  $("reader-vehicle").textContent = "";
  $("reader-engine").textContent = "";
  $("print").disabled = true;
  $("print-status").hidden = true;
  document.body.dataset.printable = "false";
}
function clearUnavailableArticle() {
  resetReaderContent();
  $("article-title").textContent = "Article unavailable";
  document.title = "AutoData — The workshop reference";
}
function invalidate() {
  navigation.clear();
  cancelPickerRefreshes();
  currentOrder = "";
  paidOrder = null;
  unconfirmedOrder = null;
  $("check-order").hidden = true;
  clearProtected();
}
async function operation(work, retry = null) {
  const g = navigation.next();
  viewGeneration = g;
  try {
    await work(g);
  } catch (error) {
    if (!g.current()) return;
    const confirmedPaid = paidOrder?.id === currentOrder &&
      vehicle?.id === paidOrder.configuration_id &&
      vehicle?.region === paidOrder.region;
    if (confirmedPaid && error.code !== "ENTITLEMENT_REVOKED") rememberOrderRoute(currentOrder);
    if ([401, 403, 410].includes(error.status)) {
      clearProtected();
      show("welcome");
      if (error.status === 401) {
        session.clear();
        void session.bootstrap();
      }
    }
    if (error.code === "ENTITLEMENT_REVOKED") {
      if (confirmedPaid) {
        const id = currentOrder;
        currentOrder = "";
        paidOrder = null;
        $("check-order").hidden = true;
        clearOrderRoute(id);
      }
      access = "revoked";
      show("welcome");
      renderPurchase();
      status("Access to this vehicle has been revoked. Contact support.", {
        error: true,
      });
    } else if (confirmedPaid && error.status !== 401) {
      clearProtected();
      access = "pending";
      show("welcome");
      renderPurchase();
      status(error.code === "ENTITLEMENT_REQUIRED"
        ? "Payment received. Access is not ready. Check payment status again; do not pay again."
        : "Payment received, but articles are unavailable. Check payment status again or contact support; do not pay again.", {
        error: true,
      });
    } else if (error.code === "ENTITLEMENT_REQUIRED") {
      access = "missing";
      show("welcome");
      renderPurchase();
      status(!$("purchase-action").disabled &&
        $("purchase-action").textContent === "Buy for $20 USD"
          ? "This vehicle is available to purchase."
          : $("purchase-message").textContent);
    } else
      status(error.message || "AutoData is unavailable. Try again.", {
        error: true,
        retry,
      });
  } finally {
    if (g.current()) {
      $("cancel").hidden = true;
      $("loading-progress").hidden = true;
      document.body.dataset.busy = "false";
    }
  }
}
function updateURL({ article = "", replace = false, library = false } = {}) {
  const p = new URLSearchParams();
  if (openDemo) p.set('demo', '1');
  for (const name of names) if ($(name).value) p.set(name, $(name).value);
  if (vehicle?.id) {
    p.set("configuration", vehicle.id);
    p.set("region", vehicle.region);
  }
  if (article) p.set("article", article);
  if ($("search").value) p.set("q", $("search").value);
  if (library) p.set("view", "library");
  if (!article && currentOrder && new URLSearchParams(location.search).get("order") === currentOrder)
    p.set("order", currentOrder);
  const url = `${location.pathname}${p.size ? `?${p}` : ""}`;
  if (url !== location.pathname + location.search)
    history[replace ? "replaceState" : "pushState"](null, "", url);
}
function rememberOrderRoute(id) {
  const params = new URLSearchParams(location.search);
  params.delete("article");
  params.set("order", id);
  const query = `?${params}`;
  if (query !== location.search) history.replaceState(null, "", location.pathname + query);
  $("check-order").hidden = false;
}
function clearOrderRoute(id, keepVehicle = false) {
  const params = new URLSearchParams(location.search);
  if (params.get("order") !== id) return;
  params.delete("order");
  if (keepVehicle && validScope(scope())) {
    params.set("configuration", vehicle.id);
    params.set("region", vehicle.region);
  }
  history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
}
function populate(name, items, desired = "") {
  const select = $(name);
  const selected = desired || select.value;
  rows[name] = name === "year" ? [...items].sort((a, b) => b.year - a.year) : items;
  const options = rows[name].map((item) => [
    String(item.id ?? item.year),
    selectorLabel(name, item),
  ]);
  const unchanged = select.options.length === options.length + 1 && options.every(([value, label], index) =>
    select.options[index + 1].value === value && select.options[index + 1].text === label);
  if (!unchanged) {
    select.replaceChildren(
      new Option(`Choose ${name === "configuration" ? "engine / trim" : name}`, ""),
      ...options.map(([value, label]) => new Option(label, value)),
    );
  }
  const nextValue = options.some(([value]) => value === selected) ? selected : "";
  if (select.value !== nextValue) select.value = nextValue;
  select.disabled = !items.length;
}
function selectorPath(name, selection = { year: $("year").value, make: $("make").value, model: $("model").value }) {
  return vehicleSelectorPath(name, selection);
}
function cachedSelector(path) {
  if (session.state.mode !== "firebase") return null;
  const entry = selectorCache.get(path);
  if (entry?.expires > performance.now()) return entry.response;
  selectorCache.delete(path);
  return null;
}
function rememberSelector(path, name, response) {
  // Local mode protects the same paths with a dataset role. Reuse anonymous
  // Firebase selector responses only.
  if (session.state.mode !== "firebase" || !response.items.length || response.hydrating ||
      !(response.complete === true || (name === "year" && response.complete === undefined))) return;
  selectorCache.delete(path);
  selectorCache.set(path, { response, expires: performance.now() + selectorCacheLifetime });
  if (selectorCache.size > selectorCacheSize) selectorCache.delete(selectorCache.keys().next().value);
}
function usableEngineChoices(name, response) {
  return name === "configuration" && !response.hydrating && response.items.length > 0 &&
    response.items.every((item) => item.complete !== false);
}
function readStoredSelector(path, signal, timeout) {
  return requestStoredSelector(path, { signal, timeout }, requestJSON);
}
function cancelPickerRefreshes() {
  for (const picker of pickerStates.values()) picker.refresh?.abort();
}
async function readStoredPicker(picker, name, signal, timeout) {
  const stored = await readStoredSelector(picker.path, signal, timeout);
  signal.throwIfAborted();
  if (name !== "configuration" || stored.complete) return stored;
  if (stored.hydrating || stored.discovering) {
    picker.discoveryInstance = stored.discovery_instance;
  } else if (picker.discoveryInstance && stored.discovery_instance &&
      stored.discovery_instance !== picker.discoveryInstance) {
    // An idle peer cannot confirm that the scheduling instance has finished.
    const usable = usableEngineChoices(name, stored);
    return { ...stored, hydrating: !usable, discovering: usable };
  } else {
    picker.discoveryInstance = undefined;
  }
  return stored;
}
async function refreshPicker(name) {
  const picker = pickerStates.get(name);
  const select = $(name);
  if (!picker?.incomplete || select.disabled || picker.path !== selectorPath(name) ||
      picker.loading?.current() || (picker.refresh && !picker.refresh.signal.aborted)) return;
  const refresh = new AbortController();
  picker.refresh = refresh;
  try {
    await readCollection((timeout) => readStoredPicker(picker, name, refresh.signal, timeout), {
      signal: refresh.signal,
      // Only configurations distinguish active discovery from incomplete coverage.
      attempts: name === "configuration" ? undefined : 1,
      backoffWithChoices: true,
      onUpdate(data) {
        if (pickerStates.get(name) !== picker || picker.path !== selectorPath(name) || select.disabled)
          return;
        if (!data.items.length) return;
        picker.incomplete = data.complete !== true;
        rememberSelector(picker.path, name, data);
        const known = new Set(rows[name].map((item) => String(item.id ?? item.year)));
        const additional = data.items.filter((item) => !known.has(String(item.id ?? item.year)));
        if (!additional.length) return;
        if (name === "year") {
          populate(name, [...rows[name], ...additional]);
          return;
        }
        rows[name] = [...rows[name], ...additional];
        select.append(...additional.map((item) => new Option(selectorLabel(name, item), String(item.id))));
      },
    });
  } catch {
    // Opening a picker can still use its existing choices if the optional read fails.
  } finally {
    if (picker.refresh === refresh) picker.refresh = null;
  }
}
async function loadOptions(name, g, desired = "", initial = null) {
  const path = selectorPath(name);
  pickerStates.get(name)?.refresh?.abort();
  const picker = { path, incomplete: false, loading: g };
  pickerStates.set(name, picker);
  const cached = cachedSelector(path);
  const choice = (item) => String(item.id ?? item.year) === desired;
  const label = name === "configuration" ? "engine / trim" : name;
  const stopWithChoices = name !== "configuration" && !desired;
  let showingPartial = false;
  let requestedConfiguration = false;
  function trackDiscovery(response) {
    if (name === "configuration" && g.current() && (response.hydrating || response.discovering))
      picker.discoveryInstance = response.discovery_instance;
    return response;
  }
  function showChoices(data) {
    if (!g.current()) return;
    picker.incomplete = data.complete === false ||
      (data.complete !== true && Boolean(data.hydrating || data.discovering));
    populate(name, data.items, desired);
    if (!(data.hydrating || data.discovering)) return;
    const hasChoices = data.items.length > 0;
    if (hasChoices === showingPartial) return;
    showingPartial = hasChoices;
    if (hasChoices)
      status(`More ${label} choices are loading. You can choose an available option.`, { cancelable: true });
    else status(`Loading ${label} choices…`, { busy: true });
  }
  status(`Loading ${label} choices…`, { busy: true });
  stage(name);
  $(name).disabled = true;
  const result = await readCollection(
    async (timeout) => {
      if (cached && (!desired || cached.items.some(choice))) return cached;
      if (initial) {
        const response = await initial;
        initial = null;
        g.signal.throwIfAborted();
        if (Array.isArray(response?.items)) {
          if (name === "year" || (desired ? response.items.some(choice) : response.complete === true)) {
            if (name !== "year" && response.complete !== true)
              void requestJSON(path, { signal: g.signal }).then(trackDiscovery).catch(() => null);
            return response;
          }
          if (response.items.length) {
            // Make stored choices usable while the verified parent starts discovery.
            showChoices({ ...response, hydrating: true });
          }
        }
        // Stored descendants cannot start ingestion. A regular read can do so once the parent is valid.
      }
      if (name === "configuration") {
        if (requestedConfiguration) return readStoredPicker(picker, name, g.signal, timeout);
        requestedConfiguration = true;
      }
      const response = await requestJSON(path, { signal: g.signal, timeout });
      return trackDiscovery(response);
    },
    {
      signal: g.signal,
      desired,
      backoffWithChoices: true,
      stopWithChoices,
      async emptyProbe(timeout) {
        try {
          return await readStoredSelector(path, g.signal, timeout);
        } catch (error) {
          g.signal.throwIfAborted();
          if (error.status === 401 || error.status === 403) throw error;
          return null;
        }
      },
      onUpdate: showChoices,
    },
  ).finally(() => { picker.loading = null; });
  if (!g.current()) return;
  if (result !== cached) rememberSelector(path, name, result);
  const selected = desired && result.items.some(choice);
  const choicesReady = stopWithChoices && result.items.length > 0;
  if (!selected && (result.refreshFailed || result.timedOut || (result.complete === false && !choicesReady))) {
    if (!desired && result.items.length) {
      status(`Choose an available ${label}. Some choices could not be loaded.`, { retry: () => restoreRoute() });
      return;
    }
    throw new Error(
      result.items.length
        ? "Some choices loaded, but the source catalog could not finish loading. Choose an available option or try again."
        : "The source catalog could not finish loading these choices. Try again.",
    );
  }
  if (desired && !selected)
    throw new Error(
      "This saved vehicle choice is unavailable. Choose another vehicle.",
    );
  status(
    result.items.length
      ? "Choose your vehicle to continue."
      : "No choices are available for this selection. Choose another vehicle.",
  );
}
function renderPurchase() {
  if (!$("purchase")) return;
  const confirming = unconfirmedOrder?.id === currentOrder &&
    vehicle?.id === unconfirmedOrder.configuration_id &&
    vehicle?.region === unconfirmedOrder.region;
  const paymentReceived = session.state.authenticated && (access === "pending" ||
    (access === "unknown" && paidOrder !== null && paidOrder.id === currentOrder &&
      vehicle?.id === paidOrder.configuration_id && vehicle?.region === paidOrder.region));
  const priced = validQuote(quote, scope());
  const configured = !openDemo && priced && purchaseConfigured();
  const simulation = merchant?.checkout_mode === "simulation";
  const canPurchase = session.state.authenticated && access === "missing" && !confirming && configured;
  const canResume = Boolean(checkoutToResume());
  const purchaseLabel = vehicle?.orderLabel || (priced ? quote.configuration_label : vehicleIdentityLabel());
  $("purchase").hidden = !validScope(scope());
  $("purchase-selection").textContent =
    [purchaseLabel, vehicle?.region].filter(Boolean).join(" / ");
  $("purchase-consent").hidden = !canPurchase;
  $("agreement").disabled = !canPurchase;
  if (openDemo) {
    $("purchase").hidden = true;
    $("purchase-terms").hidden = true;
    return;
  }
  const price = $("purchase-price");
  price.hidden = !configured || access === "owned" || paymentReceived || (confirming && session.state.authenticated);
  price.textContent = price.hidden ? "" : simulation ? "No charge · simulated $20 USD" : "$20 USD · one-time";
  $("purchase-terms").hidden = !configured;
  $("purchase-message").textContent =
    access === "revoked"
      ? "Access revoked. Contact the published support address."
      : access === "owned"
        ? "Owned. Open your articles without another purchase."
        : paymentReceived
          ? simulation
            ? "Simulated purchase complete. Article access is still being checked."
            : "Payment received. Article access is still being checked. Use Check payment status; do not pay again."
          : confirming && session.state.authenticated
            ? pendingOrderMessage(unconfirmedOrder.state, canResume)
            : merchantRequest
              ? "Checking purchase availability…"
              : simulation && !session.state.authenticated
                ? "Sign in with Google to simulate purchase. No payment is collected."
                : !configured
                  ? "Purchasing is currently unavailable. You can keep browsing."
                  : !session.state.authenticated
                    ? "Sign in to check access and purchase for your account."
                    : access === "missing"
                      ? simulation
                        ? "Simulate this purchase to add the selected vehicle to My vehicles. No card details are needed."
                        : "One purchase for this exact configuration and region. No renewal is required, subject to published terms and source availability."
                      : "Checking access. Try again if the service is unavailable.";
  const action = $("purchase-action");
  action.hidden = session.state.authenticated && access !== "owned" &&
    !paymentReceived && !canResume && !confirming && !canPurchase;
  action.textContent = action.hidden ? "" : !session.state.authenticated
    ? "Sign in with Google"
    : access === "owned"
      ? "Open articles"
      : paymentReceived
        ? (simulation ? "Simulation complete" : "Payment received")
        : canResume
          ? "Continue checkout"
          : confirming
            ? ({ open: "Checkout open", unavailable: "Checkout status unavailable" }[unconfirmedOrder.state] || "Payment pending")
            : (simulation ? "Simulate purchase" : "Buy for $20 USD");
  action.disabled = !session.state.authenticated
    ? !session.state.ready
    : access === "owned"
      ? false
      : !canPurchase && !canResume;
  $("policy-links").replaceChildren();
  if (configured)
    for (const [field, label] of [
      ["terms_url", "Terms"],
      ["privacy_url", "Privacy"],
      ["refund_url", "Refund policy"],
      ["contact_url", "Contact"],
    ]) {
      const link = element("a", label);
      link.href = merchant[field];
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      $("policy-links").append(link, document.createTextNode(" · "));
    }
  $("tax-notice").textContent = configured ? merchant.tax_notice : "";
}
function checkoutToResume() {
  return unconfirmedOrder?.resumeUntil > Date.now() &&
    unconfirmedOrder.id === currentOrder && sameScope(unconfirmedOrder, scope()) &&
    session.state.authenticated && ["unknown", "missing"].includes(access) &&
    !openDemo ? unconfirmedOrder : null;
}
function pendingOrderMessage(state, canResume) {
  if (state === "open")
    return canResume
      ? "Checkout is open. Continue checkout for the same order or check payment status."
      : "Checkout is open. Check payment status before starting another payment.";
  if (state === "creating") return "Checkout is being prepared. Use Check payment status before starting another payment.";
  if (state === "reconciliation_required") return "Payment status needs verification. Use Check payment status. Do not pay again.";
  if (state === "unavailable") return "Checkout status is unavailable. Use Check payment status before starting another payment.";
  return "Payment confirmation is pending. Use Check payment status. Do not pay again.";
}
function vehicleIdentityLabel() {
  return [
    vehicle?.year,
    vehicle?.make,
    vehicle?.model,
    (vehicle?.engine || vehicle?.trim || vehicle?.body_style || vehicle?.drivetrain) &&
      configurationLabel(vehicle),
  ].filter(Boolean).join(" / ") || vehicle?.orderLabel || vehicle?.publicLabel || "";
}
function purchaseConfigured() {
  return purchaseConfiguration(merchant, quote, {
    testCheckout: !$("test-banner").hidden || merchant?.checkout_mode === "simulation",
    origin: globalThis.location?.origin,
  });
}
async function selectVehicle(g, articleID = "", {
  quoteMode = "eager", savedLink = false, reuseQuote = false, focusOnShow = false,
  focusArticle = "", indexAnchor = "", firstIndex = null,
} = {}) {
  if (!g.current()) return;
  // Keep the exact public price visible while paid access and purchase
  // availability are checked together for this same selection.
  const retainedQuote = reuseQuote && validQuote(quote, scope()) && purchaseConfigured() ? quote : null;
  clearProtected();
  quote = retainedQuote;
  $("agreement").checked = false;
  renderPurchase();
  if (!validScope(scope())) return;
  if (sessionRequest) {
    status("Checking your account…", { busy: true });
    await sessionRequest;
    if (!g.current()) return;
  }
  const selected = scope();
  const authorizedLink = savedLink && !openDemo && session.state.authenticated &&
    session.state.mode === "firebase";
  const directArticle = authorizedLink && uuid(articleID);
  const savedQuery = authorizedLink && !articleID ? trimArticleSearch($("search").value) : "";
  const guest = !openDemo && !session.state.authenticated;
  // A navigation can load commerce from the prior release during rollout.
  const needsPublicLabel = guest && savedLink && typeof quoteConfigurationLabel === "function" && !vehicleIdentityLabel();
  const loadQuote = async () => {
    if (openDemo) return;
    const current = () => g.current() && sameScope(selected, scope()) &&
      (!needsPublicLabel || !session.state.authenticated);
    if (!needsPublicLabel && merchantRequest) await merchantRequest;
    if (!current()) return;
    if (!needsPublicLabel && merchant?.enabled !== true) {
      renderPurchase();
      return;
    }
    try {
      const q = await requestJSON(
        `/v1/workshop/quote?configuration_id=${selected.configuration_id}&region=${selected.region}`,
        { signal: g.signal },
      );
      if (!current()) return;
      if (needsPublicLabel) {
        const label = quoteConfigurationLabel(q, selected).trim();
        if (label) vehicle = { ...vehicle, publicLabel: label };
        if (merchantRequest) {
          renderPurchase();
          await merchantRequest;
          if (!current()) return;
        }
      }
      quote = merchant?.enabled === true && validQuote(q, selected) ? q : null;
      renderPurchase();
      if (access === "owned") {
        $("vehicle-caption").textContent = $("purchase-selection").textContent;
      }
    } catch {
      // The quote is optional for owned articles. Its absence keeps Buy disabled.
      if (g.current()) renderPurchase();
    }
  };
  const quoteRequest = !retainedQuote && quoteMode === "eager" && !directArticle && !savedQuery ? loadQuote() : null;
  if (guest) {
    show("welcome");
    status("Sign in to check access to your selected vehicle.");
    if (!retainedQuote && quoteMode !== "skip") await (quoteRequest ?? loadQuote());
    return;
  }
  try {
    if (directArticle && await loadArticle(articleID, g, { savedLink: true })) return;
    if (savedQuery && await loadSavedSearch(g, savedQuery, focusArticle)) return;
    if (!g.current()) return;
    await loadArticles(g, articleID, { focusOnShow, focusArticle, indexAnchor, includePurchaseQuote: Boolean(retainedQuote), firstIndex });
  } catch (error) {
    // When a purchase is required, present the price or its unavailable state
    // with the access result so the UI does not announce a false checkout failure.
    if (g.current() && error.code === "ENTITLEMENT_REQUIRED" && quoteMode !== "skip") {
      if (retainedQuote && error.purchaseQuote !== undefined) {
        quote = validQuote(error.purchaseQuote, selected) ? error.purchaseQuote : null;
      } else {
        if (retainedQuote) quote = null;
        await (quoteRequest ?? loadQuote());
      }
    }
    throw error;
  }
}
async function loadSavedSearch(g, query, focusArticle = "") {
  $("completion-status").textContent = "";
  stage("articles");
  status("Searching your articles…", { busy: true });
  const result = await requestJSON(articleRequestPath(undefined, "", articleSearchParams(query)), { signal: g.signal })
    .catch((error) => {
      if ([401, 403, 410].includes(error.status)) throw error;
      // Let the ordinary index remain usable if standalone search is unavailable.
      return null;
    });
  if (!g.current()) return true;
  if (result?.configuration?.id !== vehicle.id || result.configuration.region !== vehicle.region ||
      !Array.isArray(result.items)) return false;
  vehicle = result.configuration;
  searchQuery = query;
  searchItems = result.items;
  searchComplete = result.complete === true;
  indexComplete = searchComplete;
  indexHydrating = !searchComplete;
  access = "owned";
  renderPurchase();
  show("catalog");
  renderArticles();
  if (focusArticle) focusArticleIndex(focusArticle);
  if (searchComplete) status("Article search ready.", { complete: true });
  else await loadArticles(g);
  return true;
}

function indexResponsePage(result, requested, configuration, offset, anchor) {
  if (!Object.hasOwn(result, "page")) return null;
  const page = result.page;
  if (!requested || !page || (!result.progress && (result.complete || result.hydrating || result.discovering)) ||
      result.configuration?.id !== configuration.id ||
      result.configuration.region !== configuration.region ||
      !Number.isSafeInteger(page.total) || page.total <= articlePageSize ||
      !Number.isSafeInteger(page.offset) || page.offset < 0 || page.offset >= page.total ||
      page.offset % articlePageSize !== 0 ||
      typeof page.revision !== "string" || !/^[0-9a-f]{64}$/.test(page.revision) ||
      result.items.length !== Math.min(articlePageSize, page.total - page.offset) ||
      (anchor ? page.offset > 0 && !result.items.some((item) => item.id === anchor)
        : page.offset !== Math.min(offset ?? 0, Math.floor((page.total - 1) / articlePageSize) * articlePageSize))) {
    throw new Error("The catalog returned an unreadable page. Try again.");
  }
  return page;
}

async function loadArticles(g, articleID = "", {
  focusOnShow = false, focusArticle = "", indexAnchor = "", offset = null,
  includePurchaseQuote = false, firstIndex = null,
} = {}) {
  if (!g.current()) return;
  const selected = { id: vehicle.id, region: vehicle.region };
  let offerPaging = !openDemo && !articleID && (!focusArticle || indexAnchor) &&
    !trimArticleSearch($("search").value);
  let showedAvailable = false;
  const pageQuery = indexAnchor ? { anchor: indexAnchor } : offset !== null ? { offset } : undefined;
  const previousFocus = focusArticle ? document.activeElement : null;
  $("completion-status").textContent = "";
  stage("articles");
  const visibleRows = !$("catalog").hidden && (articles.length > 0 || searchItems?.length > 0);
  status(visibleRows ? "Updating your article index…" : "Opening your article index…", {
    busy: !visibleRows,
    cancelable: true,
  });
  const requestIndex = (timeout) => {
    const prefer = [
      includePurchaseQuote && "workshop-purchase-quote",
      offerPaging && articleIndexPagePreferences,
    ].filter(Boolean).join(", ");
    return requestJSON(articleRequestPath(undefined, "", offerPaging ? pageQuery : undefined), {
      signal: g.signal,
      headers: prefer ? { Prefer: prefer } : undefined,
      timeout,
    });
  };
  const indexRead = await readCollection(
    () => {
      if (firstIndex) {
        const result = firstIndex;
        firstIndex = null;
        if (Object.hasOwn(result, "error")) throw result.error;
        return result.value;
      }
      return requestIndex();
    },
    {
      signal: g.signal,
      desired: articleID,
      backoffWithChoices: Boolean(offerPaging),
      // An owned index may gain stored rows shortly after its first empty read.
      // Keep the regular poll if this one short check misses them.
      emptyProbe: !visibleRows && !articleID && !openDemo && session.state.mode === "firebase"
        ? async (timeout) => {
          try {
            return await requestIndex(timeout);
          } catch (error) {
            g.signal.throwIfAborted();
            if (error.status === 0 || error.status === 408 || error.status >= 500) return null;
            throw error;
          }
        }
        : undefined,
      onUpdate(result) {
        if (!g.current()) return;
        if (pageQuery && (result.configuration?.id !== selected.id || result.configuration.region !== selected.region))
          throw new Error("The catalog returned the wrong vehicle. Try again.");
        const page = indexResponsePage(result, offerPaging, selected, offset, indexAnchor);
        // A legacy server can deliver a large full index while another source
        // loads. Keep local pagination stable when that same read settles.
        if (!page && result.items.length > articlePageSize) offerPaging = false;
        const wasPaged = indexPage !== null;
        if (result.configuration?.id === vehicle.id &&
            result.configuration.region === vehicle.region)
          vehicle = result.configuration;
        const indexChanged = page?.revision !== indexPage?.revision || page?.offset !== indexPage?.offset ||
          result.items.length !== articles.length ||
          result.items.some((item, index) => !sameArticleDescriptor(item, articles[index]));
        const completenessChanged = indexComplete !== (result.complete === true);
        if (wasPaged && !page) articlePage = (offset ?? indexPage.offset) / articlePageSize;
        indexPage = page;
        articles = result.items;
        indexLoaded = true;
        indexComplete = result.complete === true;
        indexHydrating = !indexComplete && result.hydrating === true;
        indexFailed =
          result.progress?.status === "failed" &&
          result.progress?.retryable !== true;
        access = "owned";
        renderPurchase();
        show("catalog");
        if (pendingIndexPage === g) pendingIndexPage = null;
        const query = trimArticleSearch($("search").value);
        if (!showedAvailable && !openDemo && !query && articles.length && indexHydrating) {
          showedAvailable = true;
          status("You can open the articles below while more sources load.", { cancelable: true });
        }
        if (query && (searchQuery !== query ||
          (!searchPending && searchItems === null && !searchError) ||
          indexChanged ||
          completenessChanged)) {
          if (searchQuery === query && (wasPaged || page)) {
            // A partial page cannot revalidate results elsewhere in the index.
            searchNavigation.clear();
            searchPending = false;
            searchItems = null;
          } else if (indexChanged && searchQuery === query && searchItems)
            searchItems = searchHitsOnCurrentIndex(searchItems);
          const origin = focusArticle;
          focusArticle = "";
          // Restore focus again when the protected search refreshes the rows.
          scheduleArticleSearch({ fromIndex: true, restoreFocus: origin ? () => {
            const active = document.activeElement;
            if (g.current() && (active === previousFocus || active === document.body))
              focusArticleIndex(origin);
          } : undefined });
        }
        else renderArticles();
        if (focusOnShow || focusArticle) {
          focusArticleIndex(focusArticle);
          focusArticle = "";
          focusOnShow = false;
        }
      },
    },
  );
  if (!g.current()) return;
  const requestedArticle = articles.find((item) => item.id === articleID);
  if (openDemo && requestedArticle && requestedArticle.availability !== 'available') {
    status('This article is indexed but not readable yet. Choose an available article.', { error: true });
  } else if (articleID && requestedArticle) {
    await loadArticle(articleID, g);
  } else if (articleID && indexComplete) {
    throw new Error("This article is unavailable for the selected vehicle.");
  } else {
    indexHydrating = false;
    showArticleIndexStatus(articleID, indexRead?.refreshFailed || (!indexRead?.progress && articles.length > 0));
  }
}

function showArticleIndexStatus(articleID = "", refreshFailed = false) {
  if (indexComplete) {
    const ready = !indexLoaded && searchItems ? "Article search ready." :
      articles.length ? "Article index ready." : "Article index ready. No articles are currently available.";
    status(ready, { complete: true });
  } else if (indexFailed) {
    status(articles.length
      ? "You can open the articles below. Some sources could not be reached."
      : "Your article index could not be prepared.", {
      complete: false,
    });
  } else {
    status(refreshFailed
      ? "You can open the articles below. The index update couldn’t load."
      : "Your article index is still being prepared. Check again.", {
      complete: false,
      retry: () => operation((next) => loadArticles(next, articleID, { offset: indexPage?.offset ?? null })),
    });
  }
}

const articleDescriptorFields = [
  "id", "title", "kind", "component", "availability", "content_status",
  "source_revision_id", "canonical_revision_id", "view_revision", "review_status",
];

function sameArticleDescriptor(item, current) {
  return current && articleDescriptorFields.every((field) => item[field] === current[field]);
}

function searchHitsOnCurrentIndex(items) {
  const descriptors = new Map(articles.map((item) => [item.id, item]));
  return items.filter((item) => sameArticleDescriptor(item, descriptors.get(item.id)));
}

function scheduleArticleSearch({ fromIndex = false, restoreFocus } = {}) {
  const query = trimArticleSearch($("search").value);
  const refresh = fromIndex && query === searchQuery;
  if (refresh && searchPending) {
    searchRefreshPending = true;
    renderArticles();
    return;
  }
  searchNavigation.clear();
  clearTimeout(searchTimer);
  searchTimer = null;
  searchQuery = query;
  searchRefreshPending = false;
  if (!refresh) {
    articlePage = 0;
    searchItems = null;
    searchComplete = false;
  }
  searchPending = Boolean(query && vehicle?.id && access === "owned");
  searchError = false;
  renderArticles({ keepFocus: refresh });
  if (!searchPending) return;
  const generation = searchNavigation.next();
  const vehicleID = vehicle.id;
  const region = vehicle.region;
  const current = () => generation.current() && vehicle?.id === vehicleID &&
    vehicle?.region === region && trimArticleSearch($("search").value) === query;
  const startSearch = () => {
    searchTimer = null;
    searchRefreshPending = false;
    void requestJSON(articleRequestPath(undefined, "", articleSearchParams(query)), {
      signal: generation.signal,
    }).then((result) => {
      if (!current()) return;
      const items = Array.isArray(result.items) ? result.items : [];
      // A newer index may retire or replace results from the older search.
      searchItems = searchRefreshPending ? searchHitsOnCurrentIndex(items) : items;
      searchComplete = result.complete === true;
      if (!indexLoaded) indexComplete = searchComplete;
      searchPending = false;
      if (searchRefreshPending) scheduleArticleSearch({ fromIndex: true, restoreFocus });
      else {
        renderArticles();
        restoreFocus?.();
      }
    }).catch((error) => {
      if (!current()) return;
      if ([401, 403, 410].includes(error.status)) {
        // Reuse the paid purchase boundary: a changed grant must not expose
        // cached rows or turn an already-paid order into another Buy action.
        void operation(async () => { throw error; });
        return;
      }
      searchPending = false;
      searchRefreshPending = false;
      searchItems = null;
      searchError = true;
      renderArticles();
      restoreFocus?.();
    });
  };
  if (fromIndex) startSearch();
  else searchTimer = setTimeout(startSearch, 300);
}

function renderArticleLinks(items) {
  const container = $("articles");
  const existingList = container.firstElementChild;
  const list = existingList || element("ul", undefined, "article-list");
  if (!existingList) list.setAttribute("role", "list");
  const active = document.activeElement;
  const focused = list.contains(active) ? active : null;
  const previous = new Map(Array.from(list.children, (row) => [row.dataset.articleId, row]));
  const url = new URL(location.href);
  const rows = items.map((item) => {
    let row = previous.get(item.id);
    if (!row) {
      row = element("li");
      row.dataset.articleId = item.id;
      const link = element("a");
      link.append(element("span"), element("span", undefined, "article-type"));
      link.addEventListener("click", (event) => {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        openArticle(item.id, link);
      });
      row.append(link);
    }
    previous.delete(item.id);
    const link = row.firstElementChild;
    const kind = typeof item.kind === "string"
      ? item.kind.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ")
      : "";
    const title = item.title || "Untitled article";
    const label = kind ? kind[0].toUpperCase() + kind.slice(1) : "Article";
    if (link.children[0].textContent !== title) link.children[0].textContent = title;
    if (link.children[1].textContent !== label) link.children[1].textContent = label;
    url.searchParams.set("article", item.id);
    const href = url.pathname + url.search;
    if (link.getAttribute("href") !== href) link.href = href;
    return row;
  });
  for (const row of previous.values()) row.remove();
  let next = list.firstElementChild;
  for (const row of rows) {
    if (row === next) next = next.nextElementSibling;
    else list.insertBefore(row, next);
  }
  if (!existingList) container.append(list);
  // Moving a focused link can blur it. A removed result returns focus to the
  // index heading instead of activating an unrelated row at the same position.
  if (focused && focused !== document.activeElement) {
    const target = list.contains(focused) ? focused : $("catalog-title");
    target.focus({ preventScroll: true });
  }
}

function renderArticles({ keepFocus = true } = {}) {
  $("vehicle-caption").textContent =
    quote?.configuration_label || $("purchase-selection").textContent;
  const query = trimArticleSearch($("search").value);
  const searching = Boolean(query && searchQuery === query);
  const localSearch = searching && searchItems === null;
  const page = query ? null : indexPage;
  const items = articleIndexItems(query);
  if (items.length && !localSearch && access === "owned" && paidOrder?.id === currentOrder &&
      vehicle?.id === paidOrder.configuration_id && vehicle?.region === paidOrder.region) {
    clearPaidOrderAction(currentOrder);
  }
  const total = page?.total ?? items.length;
  const lastPage = Math.max(0, Math.ceil(total / articlePageSize) - 1);
  const focusedID = keepFocus && !page ? document.activeElement?.parentElement?.dataset.articleId : "";
  if (focusedID) {
    const focusedIndex = items.findIndex((item) => item.id === focusedID);
    if (focusedIndex >= 0) articlePage = Math.floor(focusedIndex / articlePageSize);
  }
  articlePage = Math.min(articlePage, lastPage);
  const start = page?.offset ?? articlePage * articlePageSize;
  const end = Math.min(start + articlePageSize, total);
  renderArticleLinks(page ? items : items.slice(start, end));
  const pages = $("article-pages");
  const previous = $("article-prev");
  const next = $("article-next");
  const active = document.activeElement;
  pages.hidden = lastPage === 0;
  previous.disabled = start === 0;
  next.disabled = end === total;
  if ((active === previous || active === next) && (pages.hidden || active.disabled))
    focusArticleIndex();
  const range = lastPage > 0 ? `${start + 1}–${end} of ${total}` : "";
  if ($("article-page-range").textContent !== range) $("article-page-range").textContent = range;
  const articleCount = `${total} ${total === 1 ? "article" : "articles"}`;
  const resultsComplete = searching ? searchComplete && indexComplete : indexComplete;
  const indexUnavailable = indexFailed && !articles.length;
  const noPartialMatches = searching && indexFailed && !indexUnavailable && !items.length;
  let countText = searching && searchPending
    ? "Searching articles…"
    : searching && searchError
      ? "Article search is unavailable. Try again."
      : indexUnavailable
        ? "Article index could not be prepared."
        : !resultsComplete
          ? `${total} articles so far. Article index is still being prepared.`
          : openDemo
            ? `${items.length} available articles · ${articles.length} indexed`
            : `${total} articles`;
  const localSearchSource = indexPage ? "loaded page" : "loaded index";
  if (items.length && searching && searchPending)
    countText = `${articleCount} from the ${localSearchSource}. Searching…`;
  else if (items.length && searching && searchError)
    countText = `${articleCount} from the ${localSearchSource}. Search could not refresh.`;
  else if (items.length && (indexFailed || (!resultsComplete && !indexHydrating)))
    countText = `${articleCount} from available sources.`;
  else if (noPartialMatches && !searchPending && !searchError)
    countText = "0 articles from available sources.";
  // Avoid mutating the polite live region with the same pending text on every keystroke.
  if ($("catalog-count").textContent !== countText) $("catalog-count").textContent = countText;
  $("no-results").textContent = searching && searchError
    ? "Article search is unavailable. Try again."
    : searching && searchPending
      ? "Searching articles…"
      : openDemo && articles.length > 0 && !articles.some((item) => item.availability === "available")
        ? "No articles are readable yet for this vehicle. Choose another vehicle or check back later."
        : indexUnavailable
          ? "This article index could not be prepared. Check the status above."
          : noPartialMatches
            ? "No articles from available sources match this search."
            : !resultsComplete
              ? "This article index is still being prepared. Check again shortly."
              : query && (articles.length > 0 || !indexLoaded)
                ? "No articles match this search. Try a component name or a shorter phrase."
                : "No articles are currently available for this vehicle.";
  $("no-results").hidden = items.length > 0;
}

function focusArticleIndex(id) {
  const query = trimArticleSearch($("search").value);
  if (id && (!indexPage || query)) {
    const index = articleIndexItems(query).findIndex((item) => item.id === id);
    const page = Math.floor(index / articlePageSize);
    if (page >= 0 && page !== articlePage) {
      articlePage = page;
      renderArticles({ keepFocus: false });
    }
  }
  const row = id && Array.from($("articles").firstElementChild?.children || [])
    .find((item) => item.dataset.articleId === id);
  const link = row?.firstElementChild;
  const target = link || $("catalog-title");
  target.focus({ preventScroll: Boolean(link) });
  link?.scrollIntoView({ behavior: "instant", block: "nearest" });
}
const articlePageSize = 100;
const articleIndexPagePreferences = "workshop-index-pages, workshop-index-live-pages";
function articleIndexItems(query) {
  const visible = openDemo ? articles.filter((item) => item.availability === "available") : articles;
  if (query && query === searchQuery && searchItems !== null)
    return openDemo ? searchItems.filter((item) => item.availability === "available") : searchItems;
  return query ? filterArticles(visible, query) : visible;
}
function moveArticlePage(direction) {
  if (indexPage && !trimArticleSearch($("search").value)) {
    const offset = indexPage.offset + direction * articlePageSize;
    const selected = scope();
    const load = () => {
      if (access !== "owned" || $("catalog").hidden || !sameScope(selected, scope()) ||
          trimArticleSearch($("search").value) || pendingIndexPage?.current() ||
          !indexPage || offset < 0 || offset >= indexPage.total) return;
      return operation(async (g) => {
        pendingIndexPage = g;
        try {
          await loadArticles(g, "", { offset });
        } catch (error) {
          if (g.current() && error.status === 404) {
            clearProtected();
            show("welcome");
            renderPurchase();
          }
          throw error;
        } finally {
          if (pendingIndexPage === g) pendingIndexPage = null;
        }
      }, () => indexPage ? load() : restoreRoute());
    };
    return load();
  }
  articlePage = Math.max(0, articlePage + direction);
  renderArticles({ keepFocus: false });
}
const assetID = (image) =>
  image?.id || image?.image_id || image?.asset_id || "";
const imageReferenceID = (reference) =>
  reference?.asset_id || reference?.image_id || reference?.id || "";
const missingSourceImage = (reference) =>
  reference?.status === "unavailable" &&
  reference.unavailable_reason === "SOURCE_NOT_FOUND";
const missingImagePlacement = (id, caption) => JSON.stringify([id, caption || ""]);
const pendingSourceImageText = "Preparing illustration…";
const unavailableImageText = "Illustration unavailable.";
function imageMap(article) {
  return [
    ...(article?.images || []),
    ...(article?.steps || []).flatMap((step) => step.images || []),
  ];
}
function addImage(parent, image, reference, g, figures = null, useAltCaption = false) {
  const { caption, alt } = reference || {};
  const figure = element("figure");
  const url = localImageURL(image?.url, location.origin, { authMode: session.state.mode }),
    id = assetID(image);
  const available = Boolean(url && id);
  const missing = missingSourceImage(reference);
  const preparing = reference?.unavailable_reason === "SOURCE_MEDIA_PENDING";
  const visibleCaption = available && useAltCaption ? caption || alt : caption;
  if (available) {
    figure.dataset.assetId = id;
    const img = element("img");
    img.dataset.assetId = id;
    const imageAlt = alt === undefined ? visibleCaption : alt;
    img.alt = imageAlt || image.alt || visibleCaption || "Article illustration";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => {
      if (g.current()) void renewMedia(g, img);
    });
    if (figures) figures.push({ img, url });
    else img.src = url;
    figure.append(img);
  } else {
    const missingID = missing ? imageReferenceID(reference) : "";
    if (missingID) figure.dataset.missingImagePlacement = missingImagePlacement(missingID, caption);
    const placeholder = element("p", preparing ? pendingSourceImageText : unavailableImageText, "image-missing");
    if (preparing) placeholder.dataset.pendingSourceImage = "";
    figure.append(placeholder);
  }
  if ((available || missing || preparing) && visibleCaption)
    figure.append(element("figcaption", visibleCaption));
  parent.append(figure);
}
function startArticleFigures(figures) {
  const loadNearViewport = new Set(figures.map(({ url }) => url)).size >= 7;
  for (const { img, url } of figures) {
    if (loadNearViewport) {
      img.loading = "lazy";
      img.dataset.figurePending = "";
      img.addEventListener("load", () => { delete img.dataset.figurePending; }, { once: true });
    }
    img.src = url;
  }
  return figures.length ? { figures, printing: false } : null;
}
function releaseArticleFigures(group) {
  for (const { img } of group?.figures || [])
    if (img.isConnected && img.loading === "lazy") img.loading = "eager";
}
function appendSource(parent, block, review, g) {
  const href = sourceReferenceURL(review, block);
  if (!href) return;
  const link = element("a", "View source", "source-reference");
  link.href = "#source-review";
  link.addEventListener("click", (event) => {
    event.preventDefault();
    if (g.current())
      void loadSource(href, g, block.block_id || "").catch((error) => handleSourceError(error, g));
  });
  parent.append(link);
}
function indexRenderableImages(images) {
  const imagesByID = new Map();
  for (const image of Array.isArray(images) ? images : []) {
    if (!image || image.status === "unavailable") continue;
    for (const id of [image.id, image.image_id, image.asset_id]) {
      if (id && !imagesByID.has(id)) imagesByID.set(id, image);
    }
  }
  return imagesByID;
}
function renderBlocks(parent, blocks, imagesByID, review, g, sourceTargets = null, figures = null) {
  const isListNumber = value =>
    Number.isInteger(value) && value >= -2147483648 && value <= 2147483647;
  const find = (ref) => {
    const id = imageReferenceID(ref);
    return id && ref.status !== "unavailable"
      ? imagesByID.get(id)
      : undefined;
  };
  const addReference = (target, ref, useAltCaption = true) =>
    addImage(target, find(ref), ref, g, figures, useAltCaption);
  const renderInline = (target, value, textTag) => {
    if (!value || typeof value !== "object") {
      target.textContent = String(value ?? "");
      return;
    }
    if (value.text != null) target.append(element(textTag, value.text));
    if (value.asset_id || value.image_id || value.status === "unavailable")
      addReference(target, value);
    for (const ref of value.images || []) addReference(target, ref);
    if (Array.isArray(value.blocks)) renderBlocks(target, value.blocks, imagesByID, review, g, sourceTargets, figures);
  };
  for (const block of blocks || []) {
    if (!block || typeof block !== "object") continue;
    const sourceID = sourceTargets && block.block_id;
    const childIndex = sourceID ? parent.children.length : 0;
    const type = block.type;
    if (type === "heading" || type === "paragraph" || type === "link") {
      const tag = type === "heading"
        ? `h${Math.max(3, Math.min(6, Number(block.level) || 3))}`
        : "p";
      parent.append(element(tag, block.text ?? ""));
      for (const ref of block.images || [])
        addReference(parent, ref, false);
    } else if (type === "callout") {
      const aside = element("aside", undefined, "article-callout");
      const content = element("div");
      content.append(element("span", block.text ?? ""));
      for (const ref of block.images || []) addReference(content, ref);
      aside.append(element("strong", block.label ?? "Note"), content);
      parent.append(aside);
    } else if (type === "image")
      addReference(parent, block);
    else if (type === "step") {
      const section = element("section", undefined, "procedure-step");
      if (Number.isInteger(block.number))
        section.append(element("span", `${block.number}.`, "step-number"));
      if (block.text) section.append(element("p", block.text));
      if (block.action) section.append(element("h3", block.action));
      for (const text of block.instructions || [])
        section.append(element("p", text));
      for (const ref of block.images || []) addReference(section, ref);
      parent.append(section);
    } else if (type === "ordered_list" || type === "unordered_list") {
      const ordered = type === "ordered_list";
      const list = element(ordered ? "ol" : "ul");
      if (ordered && isListNumber(block.start))
        list.setAttribute("start", String(block.start));
      for (const item of block.items || []) {
        const li = element("li");
        if (ordered && isListNumber(item?.number))
          li.setAttribute("value", String(item.number));
        renderInline(li, item, "p");
        list.append(li);
      }
      parent.append(list);
      for (const ref of block.images || []) addReference(parent, ref);
    } else if (type === "table") {
      const table = element("table", undefined, "article-table");
      const cellImageIDs = new Set();
      const cellMissingImages = new Set();
      const trackCellImages = (cell) => {
        for (const figure of cell.querySelectorAll("figure")) {
          const { assetId, missingImagePlacement: placement } = figure.dataset;
          if (assetId) cellImageIDs.add(assetId);
          if (placement) cellMissingImages.add(placement);
        }
      };
      const renderCell = (cell, value) => {
        const rowspan = value?.rowspan, colspan = value?.colspan;
        if (Number.isInteger(rowspan) && rowspan > 1 && rowspan <= 65534)
          cell.rowSpan = rowspan;
        if (Number.isInteger(colspan) && colspan > 1 && colspan <= 1000)
          cell.colSpan = colspan;
        renderInline(cell, value, "span");
        trackCellImages(cell);
      };
      if (block.label || block.caption)
        table.append(element("caption", block.label || block.caption));
      if (block.columns?.length) {
        const row = element("tr"),
          head = element("thead");
        for (const c of block.columns) {
          const th = element("th");
          th.scope = "col";
          renderCell(th, c);
          row.append(th);
        }
        head.append(row);
        table.append(head);
      }
      const body = element("tbody");
      for (const values of block.rows || []) {
        const cells = Array.isArray(values) ? values : values?.cells;
        if (!Array.isArray(cells)) continue;
        const row = element("tr");
        for (const value of cells) {
          const cell = element("td");
          renderCell(cell, value);
          row.append(cell);
        }
        body.append(row);
      }
      table.append(body);
      const wrap = element("div", undefined, "table-scroll");
      wrap.append(table);
      parent.append(wrap);
      for (const ref of block.images || []) {
        if (cellImageIDs.has(assetID(find(ref)))) continue;
        if (missingSourceImage(ref) &&
            cellMissingImages.has(missingImagePlacement(imageReferenceID(ref), ref.caption))) continue;
        addReference(parent, ref);
      }
    } else if (type === "break") parent.append(element("hr"));
    else
      parent.append(
        element(
          "aside",
          block.text ||
            block.unavailable_reason ||
            "This source block needs review.",
          "article-callout",
        ),
      );
    if (sourceID) sourceTargets.set(sourceID, parent.children[childIndex]);
    appendSource(parent, block, review, g);
  }
}
function renderContent(parent, article, g, figures = null) {
  const presentation = articlePresentation(article),
    images = imageMap(article),
    imagesByID = indexRenderableImages(images);
  if (presentation.documentBlocks.length)
    renderBlocks(
      parent,
      presentation.documentBlocks,
      imagesByID,
      article.source_review,
      g,
      null,
      figures,
    );
  else if (presentation.steps.length) {
    renderBlocks(parent, presentation.introBlocks, imagesByID, null, g);
    for (const step of presentation.steps) {
      const section = element("section", undefined, "procedure-step");
      if (Number.isInteger(step.number))
        section.append(element("span", `${step.number}.`, "step-number"));
      if (step.action || step.heading)
        section.append(element("h3", step.action || step.heading));
      for (const text of step.instructions || [])
        section.append(element("p", text));
      for (const image of step.images || [])
        addImage(section, image, { alt: image.alt }, g, null, true);
      for (const id of step.image_ids || []) {
        const image = images.find((i) => assetID(i) === id);
        if (image) addImage(section, image, { alt: image.alt }, g, null, true);
      }
      parent.append(section);
    }
  } else if (presentation.blocks.length)
    for (const b of presentation.blocks) {
      if (b.type === "step") {
        const section = element("section", undefined, "procedure-step");
        section.append(element("span", `${b.number}.`, "step-number"));
        for (const part of b.parts || [])
          section.append(element("p", part.text ?? ""));
        parent.append(section);
      } else renderBlocks(parent, [b], imagesByID, null, g);
    }
  else parent.append(element("p", "No readable content is available yet."));
}
function retryImage(img, images) {
  const found = images.find(
    (image) => image.status !== "unavailable" && assetID(image) === img.dataset.assetId,
  );
  const url = localImageURL(found?.url, location.origin, { authMode: session.state.mode });
  if (!url || img.src === url) return false;
  img.dataset.replacement = "1";
  img.src = url;
  return true;
}
function showUnavailableImage(img) {
  if ($("source-review-frame").contains(img)) mountedSource = null;
  img.replaceWith(element(
    "p",
    "Illustration unavailable. Refresh this article to try again.",
    "image-missing",
  ));
}
const articleDetailOrders = new WeakMap();
const articleDetailSequence = Symbol();
function articleDetailOrder(g, id) {
  const current = articleDetailOrders.get(g.signal);
  if (current?.id === id) return current;
  const order = { id, issued: 0, accepted: null };
  articleDetailOrders.set(g.signal, order);
  return order;
}
async function requestArticleDetail(order, path, options) {
  const sequence = ++order.issued;
  const response = await requestArticleJSON(path, options);
  return { ...response, [articleDetailSequence]: sequence };
}
function acceptArticleDetail(order, response) {
  if (!response?.data?.article || typeof response.data.article !== "object") return response;
  // Overlapping detail reads can arrive in either order. A late success can
  // use the newer accepted view without replaying an earlier snapshot.
  if (order.accepted?.[articleDetailSequence] > response[articleDetailSequence]) return order.accepted;
  order.accepted = response;
  return response;
}
function articleViewRevision(article) {
  return article.view_revision ||
    `${article.content_origin || "legacy"}:${article.source_revision_id || ""}:${article.canonical_revision_id || ""}`;
}
function originalSourceReview(article) {
  return article?.original_source_review?.available ? article.original_source_review : article?.source_review;
}
function renderArticle(article, g, redraw = false) {
  if (!g.current()) return;
  const revision = articleViewRevision(article);
  const review = originalSourceReview(article);
  const previousOriginal = originalSourceReview(currentArticle);
  const originalURL = review?.available ? review.url : "";
  const previousOriginalURL = previousOriginal?.available ? previousOriginal.url : "";
  const referenceURL = article.source_review?.available ? article.source_review.url : "";
  const previousReferenceURL = currentArticle?.source_review?.available ? currentArticle.source_review.url : "";
  const sourceChanged = currentArticle?.id !== article.id ||
    currentArticle?.source_revision_id !== article.source_revision_id || previousReferenceURL !== referenceURL;
  const rebuildArticle = redraw || revision !== renderedRevision || sourceChanged;
  const processing = processingArticle(article);
  if (renderedRevision && (rebuildArticle || previousOriginalURL !== originalURL)) {
    const revisionForURL = (url) => validSourceURL(url)?.searchParams.get("source_revision_id");
    const pins = [referenceURL, originalURL].map(revisionForURL).filter(Boolean);
    const activeReads = [sourceURL, sourceDocumentRequest?.key].filter(Boolean);
    if (sourceChanged || !pins.length || activeReads.some((url) => !pins.includes(revisionForURL(url)))) {
      resetSourceReview();
    }
  }
  if (rebuildArticle) {
    const fragment = document.createDocumentFragment();
    const figures = !openDemo && session.state.mode === "firebase" && article.document?.blocks?.length ? [] : null;
    renderContent(fragment, article, g, figures);
    if (!g.current()) return;
    $("article-content").replaceChildren(fragment);
    deferredArticleFigures = figures ? startArticleFigures(figures) : null;
    $("print-status").hidden = true;
    articleImageRefresh = null;
    sourceImageRefresh = null;
    renderedRevision = revision;
  }
  // A retained preview can outlive the job without changing its view revision.
  if (article.source_body_preview && (rebuildArticle || processing !== processingArticle(currentArticle))) {
    const message = processing ? pendingSourceImageText : unavailableImageText;
    for (const placeholder of $("article-content").querySelectorAll("[data-pending-source-image]")) {
      if (placeholder.textContent !== message) placeholder.textContent = message;
    }
  }
  currentArticle = article;
  $("article-title").textContent = article.title || "Article";
  $("article-kind").textContent =
    article.source_body_preview
      ? "Supplier source"
      : article.content_origin === "canonical"
      ? "Workshop article"
      : article.content_origin === "source"
        ? "Stored source"
        : "Article";
  $("reader-vehicle").textContent = vehicleIdentityLabel();
  $("reader-engine").textContent = vehicle.region;
  const readable = readableArticle(article);
  const notes = [];
  if (readable && processing && article.source_body_preview) {
    notes.push("Showing the supplier text while the full article is prepared.");
  } else if (readable && processing) {
    const rewriting = article.content_origin === "source" &&
      ["normalizing", "rewriting", "validating", "publishing"].includes(article.processing.state);
    notes.push(rewriting ? "Preparing the Workshop rewrite." : "An update is in progress.");
  }
  if (readable && article.review_status === "UNREVIEWED" && (!processing || article.content_origin === "canonical")) {
    notes.push("Draft content has not been reviewed. Check the stored source before using this procedure.");
  }
  $("article-note").hidden = !notes.length;
  $("article-note").textContent = notes.join(" ");
  $("print").disabled = !readable;
  document.body.dataset.printable = String(readable);
  $("article-reference").hidden = false;
  $("source-review").hidden = !review?.available;
  $("open-original").hidden = !originalURL;
  if (review?.available) {
    $("source-review-link").href = demoPath(review.url);
    $("source-review-link").target = "_blank";
    $("source-review-link").rel = "noopener noreferrer";
    if (!sourceURL) $("source-review-meta").textContent = "Stored source for this article.";
  }
  document.title = `${article.title || "Article"} | AutoData`;
}
function showArticleReadStatus(id, article, timedOut = false) {
  const readable = readableArticle(article);
  const checkUpdate = readable && !openDemo && session.state.mode === "firebase" &&
    (timedOut || article.content_origin === "source");
  status(
    timedOut
      ? readable ? "Article is readable. You can check for an update again." : "Preparation is taking longer. You can check again."
      : article?.processing?.state === "needs_review"
        ? readable
          ? article.content_origin === "source"
            ? "Stored source is readable. Article preparation needs review."
            : "Article is readable. An update needs review."
          : "This article needs review."
        : article?.processing?.state === "failed"
          ? readable ? "Preparation could not finish. The available article is still readable." : "Article preparation could not finish."
          : readable
            ? "Article ready."
            : "No readable content is available.",
    {
      retry: checkUpdate
        ? () => openArticle(id, null, { refreshOnly: true })
        : timedOut || !readable ? () => openArticle(id) : null,
      retryText: checkUpdate ? "Check for an update" : undefined,
      complete: readable,
    },
  );
}
async function loadArticle(id, g, { savedLink = false, refreshOnly = false } = {}) {
  if ((!openDemo && !session.state.authenticated) || !g.current()) return;
  const sameArticle = currentArticle?.id === id;
  let refreshVisibleArticle = sameArticle && !$("reader").hidden && readableArticle(currentArticle);
  const heading = $("article-title");
  if (!refreshVisibleArticle) resetReaderContent();
  if (!sameArticle) {
    heading.textContent = "Opening article…";
    document.title = "AutoData — The workshop reference";
  }
  show("reader");
  stage("article");
  if (refreshVisibleArticle)
    status("Checking for an article update…", { cancelable: true });
  else {
    status("Opening article…", { busy: true });
    heading.focus();
  }
  let readerAlignment = sameArticle ? null : new AbortController();
  if (readerAlignment) {
    const controller = readerAlignment;
    const signal = AbortSignal.any([g.signal, controller.signal]);
    const keepPosition = () => controller.abort();
    for (const type of ["wheel", "touchmove", "keydown", "pointerdown"])
      window.addEventListener(type, keepPosition, { passive: true, signal });
  }
  const handleReadError = (error) => {
    if (g.current() && error.status === 404 && error.code === "CATALOG_NOT_FOUND")
      clearUnavailableArticle();
    throw error;
  };
  const prepare = !refreshOnly && !openDemo && session.state.mode !== "local";
  const selected = vehicle;
  const matchesConfiguration = (configuration) =>
    configuration?.id === selected.id && configuration?.region === selected.region;
  const order = articleDetailOrder(g, id);
  const detailPath = articleRequestPath(id);
  const readOptions = { signal: g.signal, preferShortPublicationCheck: true };
  let initialReadStartedAt = performance.now();
  const first = await (prepare
    ? requestArticleDetail(order, articleRequestPath(id, "/prepare"), {
        ...readOptions,
        method: "POST",
        body: {},
        preferShortSourceCheck: true,
        reportBodyNetworkError: true,
        headers: { "X-CSRF-Token": session.state.csrf },
      })
    : requestArticleDetail(order, detailPath, readOptions)).catch(async (error) => {
        if (prepare && g.current() && error.status === 0 && error.code === "NETWORK_UNAVAILABLE") {
          // Prepare may have committed before the browser lost the response.
          initialReadStartedAt = performance.now();
          const recovered = await requestArticleDetail(order, detailPath, { ...readOptions, preferShortSourceCheck: true })
            .catch((detailError) => {
              g.signal.throwIfAborted();
              if ([401, 403, 404, 410].includes(detailError.status)) return handleReadError(detailError);
              return null;
            });
          if (!g.current()) return null;
          const article = recovered?.data?.article;
          const configuration = recovered?.data?.configuration;
          if (article?.id === id && (matchesConfiguration(configuration) || !savedLink && !configuration) &&
              (recovered.status === 200 && readableArticle(article) ||
               recovered.status === 202 && processingArticle(article))) return recovered;
        }
        if (savedLink && error.status === 404) return null;
        return handleReadError(error);
      });
  if (!g.current()) return;
  if (savedLink) {
    const configuration = first?.data?.configuration;
    if (!matchesConfiguration(configuration)) return false;
    vehicle = configuration;
    access = "owned";
    renderPurchase();
  }
  let initial = first;
  let readingStatus = "";
  const result = await readArticle(
    (options) => {
      if (initial) {
        const value = initial;
        initial = null;
        return value;
      }
      return requestArticleDetail(order, detailPath, options);
    },
    {
      signal: g.signal,
      initialReadStartedAt,
      selectResponse: (response) => acceptArticleDetail(order, response),
      onUpdate(response) {
        if (!g.current()) return;
        const article = response.data.article;
        const readable = readableArticle(article);
        renderArticle(article, g, refreshVisibleArticle);
        refreshVisibleArticle = false;
        if (readerAlignment && readable) {
          const controller = readerAlignment;
          readerAlignment = null;
          requestAnimationFrame(() => {
            if (controller.signal.aborted) return;
            controller.abort();
            if (!g.current() || document.activeElement !== heading) return;
            if (heading.getBoundingClientRect().bottom > 0)
              $("reader").scrollIntoView({ behavior: "instant", block: "start" });
          });
        }
        if (paidOrder && article.id === id && readable &&
            paidOrder.configuration_id === selected.id && paidOrder.region === selected.region)
          completePaidOrder(paidOrder.id);
        if (!processingArticle(article)) return;
        let ready = "";
        if (readable) {
          if (article.source_body_preview) ready = "Source text is ready.";
          else if (article.content_origin === "source") ready = "Stored source is ready.";
          else ready = "Article is readable.";
        }
        if (ready === readingStatus) return;
        readingStatus = ready;
        if (ready) status(ready, { complete: true, cancelable: true });
        else status("Opening article…", { busy: true });
      },
    },
  ).catch(handleReadError);
  if (!g.current()) return;
  showArticleReadStatus(id, result.data?.article, result.timedOut);
  return true;
}
function openArticle(id, indexLink = null, { refreshOnly = false } = {}) {
  const indexURL = location.href;
  const params = indexLink && new URL(indexURL).searchParams;
  updateURL({ article: id });
  if (indexURL !== location.href) {
    articleIndexOrigin = params && !params.has("article") && !params.has("order") &&
      params.get("configuration") === vehicle?.id && params.get("region") === vehicle?.region &&
      access === "owned" && session.state.authenticated && session.state.csrf
      ? { indexURL, readerURL: location.href, indexLink, articleID: id, configuration: scope(), csrf: session.state.csrf,
          paged: Boolean(indexPage && !params.has("q")) }
      : null;
  }
  operation(
    (g) => {
      if (articleIndexOrigin && articleIndexOrigin.readerURL === location.href)
        articleIndexOrigin.generation = g;
      return loadArticle(id, g, { refreshOnly });
    },
    () => openArticle(id, null, { refreshOnly }),
  );
}
function validSourceURL(value) {
  try {
    const u = new URL(value, location.origin);
    return u.origin === location.origin &&
      u.pathname === `${articlePath(currentArticle.id)}/source` &&
      uuid(u.searchParams.get("source_revision_id"))
      ? u
      : null;
  } catch {
    return null;
  }
}
const sourceDocumentHeaders = { Prefer: "workshop-source-document" };
async function loadSource(value, g, blockID = null, { focusSource = false } = {}) {
  const requested = validSourceURL(value);
  if (!requested) throw new Error("This source reference is unavailable.");
  const query = new URLSearchParams(requested.search);
  // The JSON document is independent of the clicked evidence marker.
  query.delete("evidence_id");
  query.delete("source_locator");
  query.sort();
  const key = `${requested.pathname}?${query}`;
  const selected = ++sourceRevision;
  setSourceLoading(true);
  let pending;
  try {
    if (sourceDocumentRequest?.key !== key || sourceDocumentRequest.signal !== g.signal) {
      const response = requestJSON(demoPath(requested.pathname + requested.search), {
        signal: g.signal,
        headers: sourceDocumentHeaders,
      });
      sourceDocumentRequest = { key, signal: g.signal, response };
    }
    pending = sourceDocumentRequest;
    const data = await pending.response;
    if (!g.current() || selected !== sourceRevision) return;
    const returned = validSourceURL(data.source?.url);
    if (
      !returned ||
      returned.pathname !== requested.pathname ||
      returned.searchParams.get("source_revision_id") !==
        requested.searchParams.get("source_revision_id")
    )
      throw new Error("The source reference changed. Reload this article.");
    const blocks = data.document?.blocks;
    const images = indexRenderableImages(data.images);
    const revision = data.view_revision;
    const stable = !openDemo && session.state.mode === "firebase" && blocks?.length &&
      typeof revision === "string" && revision;
    const assets = stable && JSON.stringify([...images].map(([id, image]) => [
      id, Boolean(localImageURL(image.url, location.origin, { authMode: session.state.mode })),
    ]));
    // After a fresh authorized read, keep images already fetching for the same
    // source projection. Media URLs rotate even when the displayed view agrees.
    const keep = blockID !== null && stable && mountedSource?.key === key &&
      mountedSource.signal === g.signal && mountedSource.articleRevision === renderedRevision &&
      mountedSource.revision === revision && mountedSource.assets === assets;
    let targets = mountedSource?.targets;
    if (!keep) {
      const fragment = document.createDocumentFragment();
      const figures = !openDemo && session.state.mode === "firebase" ? [] : null;
      targets = stable || blockID !== null ? new Map() : null;
      if (blocks?.length) renderBlocks(fragment, blocks, images, null, g, targets, figures);
      else if (data.source?.format === "json")
        fragment.append(element("pre", data.content ?? ""));
      else fragment.append(element("p", "Stored source is unavailable."));
      $("source-review-frame").replaceChildren(fragment);
      if (figures) startArticleFigures(figures);
      mountedSource = stable ? { key, signal: g.signal, articleRevision: renderedRevision, revision, assets, targets } : null;
      sourceImageRefresh = null;
      displayedSourceRevision = selected;
    }
    $("source-review-frame").hidden = false;
    $("back-to-article").hidden = false;
    sourceURL = demoPath(requested.href);
    $("article-reference").open = true;
    $("source-review-meta").textContent = "Stored source loaded.";
    if (blockID !== null || focusSource) {
      const target = targets?.get(blockID) || $("source-review-title");
      target.setAttribute("tabindex", "-1");
      if (focusSource) $("reader").dataset.readingOriginal = "true";
      target.focus({ preventScroll: focusSource });
      if (focusSource) target.scrollIntoView({ behavior: "instant", block: "start" });
    }
  } catch (error) {
    if (g.current() && selected === sourceRevision) throw error;
  } finally {
    if (sourceDocumentRequest === pending) sourceDocumentRequest = null;
    if (g.current() && selected === sourceRevision) setSourceLoading(false);
  }
}
function handleSourceError(error, g) {
  if (!g.current()) return;
  if ([401, 403, 410].includes(error.status)) {
    invalidate();
    show("welcome");
  } else if (error.status === 404 && error.code === "CATALOG_NOT_FOUND") {
    resetSourceReview();
  }
  status(error.message || "Stored source is unavailable.", { error: true });
}
function recentImageRefresh(previous, refresh) {
  const startedAt = Date.now();
  // Offscreen figures may first load long after the previous renewal's signed URLs have expired.
  return previous && startedAt >= previous.startedAt && startedAt - previous.startedAt < 30_000
    ? previous : { startedAt, images: refresh() };
}
async function renewMedia(g, failed) {
  if (!g.current() || !currentArticle || !failed.isConnected) return;
  if (failed.dataset.replacement === "1") {
    showUnavailableImage(failed);
    return;
  }
  const stored = $("source-review-frame").contains(failed);
  const revision = renderedRevision;
  const sourceSelection = displayedSourceRevision;
  const selectedSourceURL = sourceURL;
  const id = currentArticle.id;
  const detailPath = articleRequestPath(id);
  const sameArticle = () => g.current() && currentArticle?.id === id && articleRequestPath(id) === detailPath;
  const visible = () => sameArticle() && failed.isConnected &&
    (!stored || displayedSourceRevision === sourceSelection);
  const current = () => visible() && renderedRevision === revision;
  const refresh = async () => {
    try {
      if (stored) {
        const requested = validSourceURL(selectedSourceURL);
        if (!requested) return [];
        const data = await requestJSON(selectedSourceURL, { signal: g.signal, headers: sourceDocumentHeaders });
        if (!current()) return [];
        const returned = validSourceURL(data.source?.url);
        if (
          !returned ||
          returned.searchParams.get("source_revision_id") !==
            requested.searchParams.get("source_revision_id")
        )
          throw new Error("The stored source changed.");
        return data.images || [];
      }
      const order = articleDetailOrder(g, id);
      const response = await requestArticleDetail(order, detailPath, { signal: g.signal });
      if (!current()) return [];
      const article = response.data.article;
      if (acceptArticleDetail(order, response) === response) {
        renderArticle(article, g);
        return imageMap(article);
      }
      // An earlier response can renew the same projection's capabilities.
      return imageMap(article.id === id && articleViewRevision(article) === renderedRevision ? article : currentArticle);
    } catch (error) {
      if (stored ? !current() : !sameArticle()) return [];
      if ([401, 403, 410].includes(error.status)) {
        handleSourceError(error, g);
      } else if (error.status === 404 && error.code === "CATALOG_NOT_FOUND") {
        if (stored) handleSourceError(error, g);
        else {
          // Cancel any concurrent read of the article that just became unavailable.
          navigation.clear();
          clearUnavailableArticle();
          status(error.message, { error: true });
        }
      }
      return [];
    }
  };
  // Coalesce a burst of failed figures while keeping later scrolls eligible for a fresh read.
  const pending = stored
    ? (sourceImageRefresh = recentImageRefresh(sourceImageRefresh, refresh))
    : (articleImageRefresh = recentImageRefresh(articleImageRefresh, refresh));
  const images = await pending.images;
  if (!visible() || failed.dataset.replacement === "1") return;
  if (!current()) {
    // Media issued for the pre-publication view has a stale anchor.
    if (stored) return renewMedia(g, failed);
    return;
  }
  if (!retryImage(failed, images)) showUnavailableImage(failed);
}
async function library(g, append = false, { focusOnShow = false, initialAccountCheck = null } = {}) {
  if (!append) $("purchase").hidden = true;
  let initialPage;
  const accountCheck = initialAccountCheck ?? sessionRequest;
  if (accountCheck) {
    status("Checking your account…", { busy: true });
    const bundled = await accountCheck;
    if (!g.current()) return;
    if (!append && validLibrary(bundled)) initialPage = bundled;
  }
  if (append && (!libraryCursor || libraryPageRequest)) return;
  if (!append) {
    clearReader();
    clearLibrary();
  }
  if (!session.state.authenticated) {
    show("welcome");
    status("Sign in to open My vehicles.");
    return;
  }
  show("library");
  status(append ? "Loading more vehicles…" : "Opening My vehicles…", { busy: true });
  const cursor = append ? libraryCursor : null;
  const more = $("library-more");
  const request = initialPage ? Promise.resolve(initialPage) : requestJSON(
    `/v1/workshop/library?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    { signal: g.signal, headers: { Prefer: "workshop-library-catalog-empty" } },
  );
  libraryPageRequest = request;
  if (append) more.setAttribute("aria-disabled", "true");
  let data;
  try {
    data = await request;
  } finally {
    if (libraryPageRequest === request) {
      libraryPageRequest = null;
      if (append) more.removeAttribute("aria-disabled");
    }
  }
  if (!g.current()) return;
  if (!validLibrary(data))
    throw new Error("My vehicles is temporarily unavailable.");
  libraryCursor = data.next_cursor || null;
  const list = $("library-items");
  let firstHeading;
  for (const item of data.items) {
    const li = element("li");
    const heading = element("h3", `${item.label} / ${item.region}`);
    firstHeading ??= heading;
    const catalogUnavailable = item.catalog_available === false;
    let summary = {
      paid: "Owned, ready to open",
      preparing: "Preparing articles",
      viewable: "Articles available",
      revoked: "Access revoked. Contact support.",
    }[item.access_state];
    if (catalogUnavailable) {
      summary = "Owned. Service information is currently unavailable.";
    } else if (item.catalog_empty) {
      summary = "Owned. No articles are currently available for this vehicle.";
    } else if (item.access_state === "preparing") {
      if (item.content_error_code === "CATALOG_PREPARATION_REVIEW") {
        summary = "Article preparation needs review.";
      } else if (["CATALOG_PREPARATION_UNAVAILABLE", "CATALOG_SOURCE_UNAVAILABLE"].includes(item.content_error_code)) {
        summary = "Articles are temporarily unavailable.";
      }
    }
    li.append(heading, element("p", summary));
    if (item.access_state !== "revoked" && !catalogUnavailable) {
      const button = element("button", item.catalog_empty ? "Check article availability" : "Open articles");
      button.type = "button";
      button.addEventListener("click", () => {
        // A library item is an exact configuration/region route. A previous
        // browse hierarchy can belong to a different vehicle and must be cleared.
        for (const name of names) populate(name, []);
        $("search").value = "";
        vehicle = {
          id: item.configuration_id,
          region: item.region,
          engine: item.label,
        };
        quote = null;
        updateURL();
        show("welcome");
        const openIndex = () => operation(
          (g) => selectVehicle(g, "", { quoteMode: "if-needed", focusOnShow: true }), openIndex,
        );
        void openIndex();
      });
      li.append(button);
    }
    list.append(li);
  }
  const moveFocus = append && document.activeElement === more;
  more.hidden = !libraryCursor;
  if (moveFocus) {
    const target = firstHeading || (more.hidden ? $("library-title") : null);
    if (target) {
      target.setAttribute("tabindex", "-1");
      target.focus();
    }
  }
  $("library-message").textContent = list.children.length
    ? ""
    : "No vehicles purchased yet. Browse to choose a vehicle.";
  if (!append && focusOnShow) {
    const title = $("library-title");
    title.focus({ preventScroll: true });
    title.scrollIntoView({ behavior: "instant", block: "start" });
  }
  status("My vehicles ready.", { complete: true });
}
function loadMoreLibrary() {
  if (!libraryCursor || libraryPageRequest) return;
  return operation((g) => library(g, true), loadMoreLibrary);
}
function clearReader() {
  resetReaderContent();
  $("reader").hidden = true;
}
async function checkOrder(g, id, { earlyCheckoutCheck = false, returnedCheckout, resumeCheckoutFor } = {}) {
  if (paidOrder?.id !== id) paidOrder = null;
  if (unconfirmedOrder?.id !== id) unconfirmedOrder = null;
  currentOrder = id;
  $("check-order").hidden = false;
  status("Checking payment status…", { busy: true });
  const paidStatusUnavailable = "Payment was received, but order status is unavailable. Check payment status again or contact support; do not pay again.";
  const matchesSelection = (order) => order?.id === id &&
    vehicle?.id === order.configuration_id && vehicle?.region === order.region;
  let statusUnavailable = false;
  const rememberUnconfirmed = (order) => {
    const unresolved = ["creating", "open", "processing", "reconciliation_required"];
    if (unresolved.includes(order.state)) {
      unconfirmedOrder = {
        id, configuration_id: order.configuration_id, region: order.region,
        state: order.state,
        resumeUntil: resumableCheckoutURL(order) ? Date.parse(order.provider_expires_at) : 0,
      };
      selectOrderVehicle(order);
      renderPurchase();
    } else if (["paid", "expired", "canceled", "revoked"].includes(order.state) &&
      unconfirmedOrder?.id === id) {
      unconfirmedOrder = null;
    }
  };
  const updateOrder = (order) => {
    if (!g.current()) return;
    if (resumeCheckoutFor && (order.order_id !== id || !sameScope(resumeCheckoutFor, order)))
      throw new Error("This checkout could not be confirmed for the selected vehicle.");
    if (statusUnavailable) {
      statusUnavailable = false;
      status("Checking payment status…", { busy: true });
    }
    rememberUnconfirmed(order);
    if (order.state === "paid")
      $("purchase-message").textContent = "Payment received. Checking article access.";
  };
  const reading = resumeCheckoutFor
    ? readOrder(id, { signal: g.signal }).then(order => {
        updateOrder(order);
        return order;
      })
    : pollOrder(id, {
      signal: g.signal,
      earlyCheckoutCheck,
      returnedCheckout,
      onUpdate: updateOrder,
      onUnavailable() {
        if (!g.current()) return;
        statusUnavailable = true;
        const previous = matchesSelection(paidOrder) ? "Payment received. " :
          matchesSelection(unconfirmedOrder) ?
            unconfirmedOrder.state === "open" ? "Checkout was open at the last check. " : "Payment was pending at the last check. "
            : "";
        const message = previous ? `${previous}Status check is temporarily unavailable.` :
          "Payment status is temporarily unavailable.";
        status(`${message} Checking again…`, { busy: true });
      },
    });
  const result = await reading.catch((error) => {
    if (g.current() && error.status === 404) {
      if (paidOrder?.id === id) {
        rememberOrderRoute(id);
        clearProtected();
        access = "pending";
        renderPurchase();
        show("welcome");
        status(paidStatusUnavailable, { error: true });
        return null;
      }
      const knownOpen = matchesSelection(unconfirmedOrder) && ["open", "unavailable"].includes(unconfirmedOrder.state);
      if (resumeCheckoutFor || knownOpen) {
        unconfirmedOrder = { ...(resumeCheckoutFor || unconfirmedOrder), state: "unavailable", resumeUntil: 0 };
        renderPurchase();
        throw new Error("Checkout status could not be confirmed. Check payment status again.");
      }
      checkout.clear();
      currentOrder = "";
      paidOrder = null;
      unconfirmedOrder = null;
      $("check-order").hidden = true;
      clearOrderRoute(id);
      renderPurchase();
    }
    throw error;
  });
  if (!g.current() || !result) return;
  if (result.state && !resumeCheckoutFor) rememberUnconfirmed(result);
  const resumeURL = resumeCheckoutFor && checkoutToResume() && resumableCheckoutURL(result);
  if (resumeURL) {
    location.assign(resumeURL);
    return;
  }
  if (["expired", "canceled", "revoked"].includes(result.state)) {
    currentOrder = "";
    paidOrder = null;
    $("check-order").hidden = true;
    clearOrderRoute(id);
  }
  if (result.state === "paid") return openPaidOrder(g, result);
  if (["expired", "canceled"].includes(result.state)) {
    checkout.clear();
    const readyToBuy =
      access === "missing" &&
      validQuote(quote, scope()) &&
      purchaseConfigured();
    status(
      readyToBuy
        ? "The previous payment attempt ended. Choose Buy again only when you are ready."
        : "The previous payment attempt ended. Select your vehicle to check access before buying again.",
    );
    renderPurchase();
  } else if (result.state === "revoked") {
    invalidate();
    access = "revoked";
    renderPurchase();
    show("welcome");
    status("Access revoked. Contact support.", { error: true });
  } else {
    const confirmedPaid = matchesSelection(paidOrder);
    const pending = !confirmedPaid && matchesSelection(unconfirmedOrder);
    let message = "Payment status is temporarily unavailable. Try again.";
    if (confirmedPaid) message = paidStatusUnavailable;
    else if (pending && statusUnavailable) message = unconfirmedOrder.state === "open"
      ? "Checkout was open at the last check. The current status is unavailable. Try again."
      : "Payment was pending at the last check. The current status is unavailable. Try again.";
    else if (pending) message = unconfirmedOrder.state === "open"
      ? "Checkout is still open."
      : "Payment confirmation is still pending. Check payment status manually.";
    status(message, {
      error: !pending || statusUnavailable,
      retry: () => operation((g) => checkOrder(g, id)),
    });
  }
}
function checkPaymentStatus() {
  const button = $("check-order");
  const id = currentOrder;
  if (!id || button.getAttribute("aria-disabled") === "true") return;
  return operation(async (g) => {
    const enable = () => button.removeAttribute("aria-disabled");
    button.setAttribute("aria-disabled", "true");
    g.signal.addEventListener("abort", enable, { once: true });
    try {
      await checkOrder(g, id);
    } finally {
      g.signal.removeEventListener("abort", enable);
      if (g.current()) enable();
    }
  });
}
function selectOrderVehicle(order) {
  if (vehicle?.id !== order.configuration_id || vehicle?.region !== order.region) {
    clearProtected();
    vehicle = { id: order.configuration_id, region: order.region };
    quote = null;
  }
  if (typeof order.configuration_label === "string" && order.configuration_label.trim()) {
    const orderLabel = order.configuration_label;
    if (vehicle.orderLabel !== orderLabel) vehicle = { ...vehicle, orderLabel };
  }
}
async function openPaidOrder(g, order) {
  const id = order.order_id;
  currentOrder = id;
  paidOrder = { id, configuration_id: order.configuration_id, region: order.region };
  unconfirmedOrder = null;
  rememberOrderRoute(id);
  selectOrderVehicle(order);
  try {
    await selectVehicle(g, "", { quoteMode: "skip" });
  } catch (error) {
    if (!g.current()) return;
    if (error.code === "ENTITLEMENT_REVOKED") {
      currentOrder = "";
      paidOrder = null;
      $("check-order").hidden = true;
      clearOrderRoute(id);
      throw error;
    }
    if (error.status === 401) throw error;
    rememberOrderRoute(id);
    clearProtected();
    access = "pending";
    renderPurchase();
    show("welcome");
    status(error.code === "ENTITLEMENT_REQUIRED"
      ? "Payment received. Access is not ready. Check payment status again; do not pay again."
      : "Payment received, but articles are unavailable. Check payment status again or contact support; do not pay again.", {
      error: true,
    });
    return;
  }
  if (g.current()) completePaidOrder(id);
}
function clearPaidOrderAction(id) {
  const button = $("check-order");
  if (document.activeElement === button && !$("catalog").hidden) $("catalog-title").focus();
  button.hidden = true;
  clearOrderRoute(id, true);
}
function completePaidOrder(id) {
  if (currentOrder !== id || paidOrder?.id !== id) return;
  currentOrder = "";
  paidOrder = null;
  clearPaidOrderAction(id);
}
async function purchase() {
  if (openDemo) return;
  if (!session.state.authenticated) {
    await signIn();
    return;
  }
  if (access === "owned") {
    operation((g) => loadArticles(g));
    return;
  }
  const resumeCheckoutFor = checkoutToResume();
  if (resumeCheckoutFor) {
    const csrf = session.state.csrf;
    const resume = () => {
      if (!session.state.authenticated || session.state.csrf !== csrf ||
          !sameScope(resumeCheckoutFor, scope()) || (currentOrder && currentOrder !== resumeCheckoutFor.id))
        return;
      return operation(async (g) => {
        $("purchase-action").disabled = true;
        try {
          await checkOrder(g, resumeCheckoutFor.id, { resumeCheckoutFor });
        } finally {
          if (g.current()) renderPurchase();
        }
      }, resume);
    };
    await resume();
    return;
  }
  if (
    !validQuote(quote, scope()) ||
    !purchaseConfigured() ||
    access !== "missing" ||
    (unconfirmedOrder?.id === currentOrder &&
      vehicle?.id === unconfirmedOrder.configuration_id &&
      vehicle?.region === unconfirmedOrder.region)
  )
    return;
  if (!$("agreement").checked) {
    $("agreement-error").textContent =
      "Agree to the purchase terms before continuing.";
    $("agreement").setAttribute("aria-invalid", "true");
    $("agreement").focus();
    return;
  }
  $("agreement-error").textContent = "";
  $("agreement").removeAttribute("aria-invalid");
  await operation(
    async (g) => {
      $("purchase-action").disabled = true;
      $("purchase-consent").hidden = true;
      $("agreement").disabled = true;
      const purchaseLabel = quote.configuration_label;
      const mode = merchant?.checkout_mode === "simulation" ? "simulation"
        : testStripeMode ? "stripe_test" : undefined;
      const result = await checkout.start(scope(), session.state.csrf, {
        signal: g.signal,
        ...(mode ? { mode } : {}),
      });
      if (!g.current()) return;
      if (result.state === "checkout") location.assign(result.checkout_url);
      else if (result.state === "owned") {
        await openPaidOrder(g, { ...result, configuration_label: purchaseLabel });
      } else {
        unconfirmedOrder = {
          id: result.order_id,
          configuration_id: result.configuration_id,
          region: result.region,
        };
        rememberOrderRoute(result.order_id);
        await checkOrder(g, result.order_id, { earlyCheckoutCheck: true });
      }
    },
    () => purchase(),
  );
  renderPurchase();
}
async function signIn() {
  if (openDemo) return;
  if (signingIn) return;
  signingIn = true;
  checkout.clear();
  const pathname = location.pathname;
  const route = location.search;
  const params = new URLSearchParams(route);
  const generation = viewGeneration;
  const matchesSelection = () => {
    const selected = scope();
    return location.pathname === pathname && location.search === route &&
      !params.has("order") && !params.has("view") && !params.has("article") &&
      validScope(selected) && selected.configuration_id === params.get("configuration") &&
      selected.region === params.get("region") &&
      names.every((name) => $(name).value === (params.get(name) || ""));
  };
  const canConfirmIndex = () => generation?.current() && !sessionRequest &&
    typeof selectedIndexSessionPreference === "string" && session.state.mode === "firebase" &&
    !params.has("q") && matchesSelection();
  let firstIndex;
  try {
    firstIndex = await session.signIn(canConfirmIndex() ? {
      async confirmSelectedIndex(exchangeCSRF, signal) {
        if (!canConfirmIndex() || signal.aborted) return null;
        const selected = scope();
        const prefer = [
          selectedIndexSessionPreference,
          validQuote(quote, selected) && purchaseConfigured() && "workshop-purchase-quote",
          articleIndexPagePreferences,
        ].filter(Boolean).join(", ");
        let expiresAt;
        const firstIndex = await requestJSON(articleRequestPath(), {
          signal: AbortSignal.any([generation.signal, signal]),
          headers: { Prefer: prefer, "X-CSRF-Token": exchangeCSRF },
          onSelectedIndexSession(proof) { expiresAt = proof.expiresAt; },
        }).then(value => ({ value }), error => ({ error }));
        if (!canConfirmIndex() || signal.aborted) return null;
        if (Object.hasOwn(firstIndex, "value")) {
          const configuration = firstIndex.value?.configuration;
          if (configuration?.id !== selected.configuration_id || configuration?.region !== selected.region ||
              !Array.isArray(firstIndex.value?.items)) return { expiresAt, firstIndex: null };
        }
        return { expiresAt, firstIndex };
      },
    } : undefined);
  } finally {
    signingIn = false;
  }
  if (!session.state.authenticated) return;
  if (!merchant || merchant.checkout_mode === "simulation") loadPurchaseConfiguration();
  if (matchesSelection()) {
    // Apply access only for the public selection retained through sign-in.
    const confirmed = canConfirmIndex() ? firstIndex : null;
    invalidate();
    await operation((g) => selectVehicle(g, "", { reuseQuote: true, firstIndex: confirmed }), () => restoreRoute());
    return;
  }
  await restoreRoute();
}
export async function bootstrap(initialYears, initialAccount, { preservePicker = false, initialSelectors = null, testCheckout } = {}) {
  if (testCheckout) checkoutModeReady = testCheckout.then(enabled => {
    testStripeMode = enabled;
    $("test-banner").hidden = !enabled;
  });
  invalidate();
  const params = new URLSearchParams(location.search);
  const early = openDemo || preservePicker ? null : initialSelectors;
  if (!early) initialSelectors?.abort();
  const years = preservePicker || early ? null : initialYears ?? requestInitialYears(params);
  if (openDemo) return restoreRoute(years);
  loadPurchaseConfiguration();
  const accountCheck = checkAccount(initialAccount);
  if (preservePicker) {
    await Promise.all([accountCheck, operation((g) => selectVehicle(g), () => restoreRoute())]);
    return;
  }
  // The first route can restore public selectors while the account is checked.
  // Account actions wait for that same check and use the current navigation.
  if (sessionEstablished) await accountCheck;
  await Promise.all([accountCheck, restoreRoute(years, { initialSelectors: early, initialAccountCheck: accountCheck })]);
}
function loadPurchaseConfiguration() {
  const configRequest = requestJSON("/workshop/purchase-config.json").catch(() => null)
    .then(async (config) => {
      if (config?.checkout_mode !== "simulation") await checkoutModeReady;
      if (merchantRequest !== configRequest) return;
      merchant = config;
      merchantRequest = null;
    });
  merchant = null;
  merchantRequest = configRequest;
}
function checkAccount(initial) {
  const accountCheck = session.bootstrap({ initial }).then((library) => {
    if (sessionRequest !== accountCheck) return;
    sessionRequest = null;
    sessionEstablished = true;
    return library;
  });
  sessionRequest = accountCheck;
  return accountCheck;
}
async function confirmedSavedYear(desired, initial, region) {
  const year = Number(desired.year);
  if (!desired.model && !desired.configuration) {
    if (region !== "US") return null;
    const makes = await initial.make;
    // The makes endpoint only returns rows stored for the requested year and region.
    return Array.isArray(makes?.items) && makes.items.some(item =>
      typeof item?.id === "string" && item.id && (!desired.make || item.id === desired.make))
      ? { year } : null;
  }
  if (!desired.make || !desired.model || !initial.configuration) return null;
  const [makes, models, configurations] = await Promise.all([initial.make, initial.model, initial.configuration]);
  const includes = (result, id) => Array.isArray(result?.items) && result.items.some((item) => item?.id === id);
  if (!includes(makes, desired.make) || !includes(models, desired.model) ||
      !Array.isArray(configurations?.items) || !configurations.items.length ||
      (desired.configuration && !includes(configurations, desired.configuration))) return null;
  const slug = (value) => typeof value === "string"
    ? value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") : "";
  return configurations.items.every((item) => item?.complete === true && item.year === year &&
    item.region === region && slug(item.make) === desired.make && slug(item.model) === desired.model)
    ? { year } : null;
}

async function finishSavedYears(g, pending, confirmed) {
  const picker = pickerStates.get("year");
  const current = () => g.current() && pickerStates.get("year") === picker &&
    $("year").value === String(confirmed.year);
  // The year dropdown can already be used. Its existing read owns the refresh.
  if (picker) picker.loading = g;
  try {
    const path = selectorPath("year");
    let response = await pending;
    if (!current()) return;
    response ??= await requestJSON(path, { signal: g.signal });
    if (!current() || !Array.isArray(response?.items)) return;
    const includesYear = response.items.some((item) => item?.year === confirmed.year);
    populate("year", includesYear ? response.items : [...response.items, confirmed]);
    if (picker) picker.incomplete = !includesYear || response.complete !== true;
    if (includesYear) rememberSelector(path, "year", response);
  } catch {
    // The exact stored branch remains available if the broader year list fails.
  } finally {
    if (picker?.loading === g) picker.loading = null;
  }
}

async function restoreRoute(initialYears = null, {
  focusArticle = "", indexAnchor = "", initialSelectors = null, initialAccountCheck = null,
} = {}) {
  invalidate();
  show("welcome");
  const params = new URLSearchParams(location.search);
  const early = initialSelectors?.route === params.toString() ? initialSelectors : null;
  if (!early) initialSelectors?.abort();
  // URL state is authoritative on history, sign-in, and direct-link restores.
  // A prior vehicle must not leave usable descendants or filter another index.
  for (const name of names) populate(name, []);
  $("search").value = params.get("q") || "";
  vehicle = null;
  quote = null;
  renderPurchase();
  const restore = operation(
    async (g) => {
      if (early) g.signal.addEventListener("abort", early.abort, { once: true });
      const order = params.get("order");
      if (!openDemo && uuid(order)) {
        if (sessionRequest) {
          status("Checking your account…", { busy: true });
          await sessionRequest;
          if (!g.current()) return;
        }
        if (session.state.authenticated) {
          const attempt = checkout.read();
          const earlyCheckoutCheck = attempt?.order_id === order &&
            Date.parse(attempt.provider_expires_at) > Date.now() + 1000;
          await checkOrder(g, order, {
            earlyCheckoutCheck,
            returnedCheckout: earlyCheckoutCheck ? attempt : undefined,
          });
        } else status("Sign in to check this payment.");
        return;
      }
      if (!openDemo && params.get("view") === "library") {
        await library(g, false, { initialAccountCheck });
        return;
      }
      const articleID = params.get("article") || "";
      const indexOptions = focusArticle ? { quoteMode: "if-needed", focusArticle, indexAnchor } : {};
      const exact = { configuration_id: params.get("configuration"), region: params.get("region") };
      const hasHierarchy = Boolean(params.get("year"));
      const savedQuery = hasHierarchy && !openDemo && !articleID && validScope(exact) &&
        params.get("q")?.trim();
      if (savedQuery && sessionRequest) {
        status("Checking your account…", { busy: true });
        await sessionRequest;
        if (!g.current()) return;
      }
      const scopedSearch = savedQuery && session.state.authenticated && session.state.mode === "firebase";
      if (uuid(exact.configuration_id) &&
          (!hasHierarchy || scopedSearch || (uuid(articleID) && validScope(exact)))) {
        vehicle = { id: exact.configuration_id, region: exact.region };
        await selectVehicle(g, articleID, { savedLink: true, ...indexOptions });
        return;
      }
      const desired = Object.fromEntries(names.map((name) => [name, params.get(name) || ""]));
      const initial = { year: initialYears, ...early?.reads };
      const year = Number(desired.year);
      if (/^\d{4}$/.test(desired.year) && year >= 1886 && year <= 2100) {
        // Read stored choices in parallel. A deeper list remains hidden until
        // the parent is confirmed, and only then may it queue missing data.
        for (const name of names) {
          const path = selectorPath(name, desired);
          if (!initial[name] && !cachedSelector(path)) {
            const pending = name === "year" ? requestJSON(path, { signal: g.signal }) : readStoredSelector(path, g.signal);
            initial[name] = pending.catch(() => null);
          }
          if (!desired[name]) break;
        }
      }
      const fullYears = Promise.resolve(initial.year);
      // Verified stored choices can confirm the year while the broader list is in flight.
      const confirmed = initial.year && initial.make
        ? await Promise.race([
          fullYears.then(() => null),
          confirmedSavedYear(desired, initial, params.get("region") ?? "US"),
        ]) : null;
      if (!g.current()) return;
      if (confirmed) initial.year = { items: [confirmed], complete: false };
      let yearsRefresh;
      try {
        for (const name of names) {
          await loadOptions(name, g, desired[name], initial[name]);
          if (!g.current() || !desired[name]) return;
          if (name === "year" && confirmed) yearsRefresh = finishSavedYears(g, fullYears, confirmed);
        }
        const configuration = rows.configuration.find(
          (item) => item.id === $("configuration").value,
        );
        if (params.has("region") && configuration?.region !== exact.region)
          throw new Error("This saved vehicle choice is unavailable in the selected region.");
        vehicle = configuration;
        await selectVehicle(g, articleID, indexOptions);
      } finally {
        // Keep the startup reads alive until the year list has had time to fill.
        if (yearsRefresh) await yearsRefresh;
      }
    },
    () => restoreRoute(),
  );
  return early ? restore.finally(early.abort) : restore;
}
for (const [index, name] of names.entries()) {
  const select = $(name);
  select.addEventListener("pointerdown", (event) => {
    if (event.button === 0) void refreshPicker(name);
  });
  select.addEventListener("keydown", (event) => {
    if (!event.repeat && ["ArrowDown", "ArrowUp", "Enter", " ", "F4"].includes(event.key))
      void refreshPicker(name);
  });
  select.addEventListener("change", () => {
    invalidate();
    vehicle = null;
    quote = null;
    $("purchase").hidden = true;
    for (const next of names.slice(index + 1)) {
      rows[next] = [];
      populate(next, []);
    }
    show("welcome");
    updateURL();
    if (!$(name).value) return;
    const next = names[index + 1];
    if (next)
      operation(
        (g) => loadOptions(next, g),
        () => restoreRoute(),
      );
    else {
      vehicle = rows.configuration.find(
        (item) => item.id === $("configuration").value,
      );
      updateURL();
      operation((g) => selectVehicle(g));
    }
  });
}
$("signin").addEventListener("click", () => void signIn());
$("signout").addEventListener("click", async () => {
  invalidate();
  checkout.clear();
  show("welcome");
  const confirmed = await session.logout();
  channel?.postMessage("invalidate");
  status(
    confirmed
      ? "Signed out."
      : "Sign-out could not be confirmed. Retry sign-out.",
    { error: !confirmed },
  );
  renderPurchase();
});
$("browse").addEventListener("click", () => {
  invalidate();
  show("welcome");
  history.pushState(null, "", openDemo ? "/workshop?demo=1" : "/workshop");
  void restoreRoute();
});
$("my-vehicles").addEventListener("click", () => {
  invalidate();
  updateURL({ library: true });
  const openLibrary = (g) => library(g, false, { focusOnShow: true });
  operation(openLibrary, () => operation(openLibrary));
});
$("library-more").addEventListener("click", loadMoreLibrary);
$("purchase-action").addEventListener("click", () => void purchase());
$("check-order").addEventListener("click", checkPaymentStatus);
$("article-prev").addEventListener("click", () => moveArticlePage(-1));
$("article-next").addEventListener("click", () => moveArticlePage(1));
$("search").addEventListener("input", () => {
  if (pendingIndexPage?.current()) {
    navigation.clear();
    showArticleIndexStatus();
  }
  updateURL({ replace: true });
  const loadIndex = !trimArticleSearch($("search").value) && !indexLoaded && access === "owned";
  if (loadIndex) indexComplete = false;
  scheduleArticleSearch();
  if (loadIndex) void operation((g) => loadArticles(g), () => restoreRoute());
});
$("retry").addEventListener("click", () => retryAction?.());
$("cancel").addEventListener("click", () => {
  navigation.clear();
  cancelPickerRefreshes();
  status("Loading stopped. You can try again.", {
    retry: () => restoreRoute(),
  });
});
function openOriginal(focusSource) {
  const g = viewGeneration;
  if (currentArticle && g?.current())
    void loadSource(originalSourceReview(currentArticle)?.url, g, null, { focusSource }).catch((error) => {
      handleSourceError(error, g);
      if (focusSource && g.current() && !$("open-original").hidden) {
        $("original-error").textContent = error.message || "Stored source is unavailable.";
        $("original-error").hidden = false;
      }
    });
}
$("source-review-load").addEventListener("click", () => openOriginal(false));
$("open-original").addEventListener("click", () => openOriginal(true));
$("back-to-article").addEventListener("click", () => {
  if (!viewGeneration?.current()) return;
  delete $("reader").dataset.readingOriginal;
  const title = $("article-title");
  title.focus({ preventScroll: true });
  title.scrollIntoView({ behavior: "instant", block: "start" });
});
$("article-reference").addEventListener("toggle", () => {
  if (!$("article-reference").open) delete $("reader").dataset.readingOriginal;
});
function returnToArticleIndex() {
  const origin = articleIndexOrigin;
  if (origin?.returning) return;
  const fromKnownReader = origin && origin.readerURL === location.href;
  if (fromKnownReader && canReuseArticleIndex(origin)) {
    origin.returning = true;
    navigation.clear();
    history.back();
    return;
  }
  articleIndexOrigin = null;
  updateURL({ replace: true });
  return fromKnownReader ? restoreRoute() : showReturnedArticleIndex();
}
function canReuseArticleIndex(origin) {
  return access === "owned" && viewGeneration === origin.generation && session.state.authenticated &&
    session.state.csrf === origin.csrf && vehicle?.id === origin.configuration.configuration_id &&
    vehicle?.region === origin.configuration.region;
}
function restoreHistoryEntry() {
  const origin = articleIndexOrigin;
  articleIndexOrigin = null;
  const sameIndex = origin && origin.indexURL === location.href && canReuseArticleIndex(origin);
  if (sameIndex && origin.returning) {
    return showReturnedArticleIndex(origin.indexLink);
  }
  return restoreRoute(null, {
    focusArticle: sameIndex ? origin.articleID : "",
    indexAnchor: sameIndex && origin.paged && uuid(origin.articleID) ? origin.articleID : "",
  });
}
function showReturnedArticleIndex(indexLink = null) {
  navigation.clear();
  clearReader();
  $("completion-status").textContent = "";
  const needsIndex = !articles.length && !indexComplete && !searchItems;
  const refreshIndex = () => operation(
    (g) => loadArticles(g, "", { focusOnShow: needsIndex, offset: indexPage?.offset ?? null }), refreshIndex,
  );
  if (needsIndex) return refreshIndex();
  show("catalog");
  renderArticles();
  const focus = indexLink && $("articles").contains(indexLink) ? indexLink : $("catalog-title");
  focus.focus();
  if (indexHydrating) return refreshIndex();
  stage("articles");
  showArticleIndexStatus();
}
$("back").addEventListener("click", returnToArticleIndex);
async function printArticle() {
  if (!readableArticle(currentArticle) || (!openDemo && !session.state.authenticated)) return;
  const deferred = deferredArticleFigures;
  if (!deferred) {
    window.print();
    return;
  }
  if (deferred.printing) return;
  const g = viewGeneration;
  if (!g?.current()) return;
  deferred.printing = true;
  const message = $("print-status");
  try {
    releaseArticleFigures(deferred);
    const pending = deferred.figures.filter(({ img }) => img.isConnected && !img.complete);
    if (pending.length) {
      message.textContent = "Loading illustrations for printing…";
      message.hidden = false;
      await Promise.race([
        Promise.allSettled(pending.map(({ img }) => img.decode())),
        delay(15_000, g.signal),
      ]);
    }
    if (!g.current() || deferred !== deferredArticleFigures || !session.state.authenticated) return;
    if (deferred.figures.some(({ img }) => img.isConnected && (!img.complete || !img.naturalWidth))) {
      message.textContent = "Some illustrations are still unavailable. Try printing again.";
      message.hidden = false;
      return;
    }
    message.hidden = true;
    window.print();
  } catch (error) {
    if (!g.signal.aborted) throw error;
  } finally {
    deferred.printing = false;
  }
}
$("print").addEventListener("click", printArticle);
window.addEventListener("beforeprint", () => {
  if (document.body.dataset.printable === "true") releaseArticleFigures(deferredArticleFigures);
});
window.addEventListener("popstate", () => void restoreHistoryEntry());
window.addEventListener("pagehide", () => invalidate());
let lifecycleCheck = null;
let readerCheck = null;
async function recheck(preservePicker = false) {
  if (
    !sessionEstablished ||
    openDemo ||
    signingIn ||
    document.visibilityState === "hidden" ||
    lifecycleCheck
  )
    return;
  lifecycleCheck = preservePicker && !validScope(scope()) ? checkAccount() : bootstrap(undefined, undefined, { preservePicker });
  try {
    await lifecycleCheck;
  } finally {
    lifecycleCheck = null;
  }
}
async function recheckReader(g) {
  const opened = currentArticle;
  const selected = scope();
  const scopeMatches = (configuration) =>
    configuration?.id === selected.configuration_id && configuration?.region === selected.region;
  const reader = $("reader");
  const focused = document.activeElement;
  const restoreFocus = () => {
    if (reader.contains(focused) && document.activeElement === document.body)
      focused.focus({ preventScroll: true });
  };
  // Reopening a folded source will request a fresh authorized copy.
  if (sourceURL && !$("article-reference").open) resetSourceReview();
  const pinned = sourceURL ? validSourceURL(sourceURL) : null;
  if (sourceURL && !pinned) resetSourceReview();
  const pin = pinned?.searchParams.get("source_revision_id");
  const stagedPin = validSourceURL(opened.original_source_review?.url)?.searchParams.get("source_revision_id");
  const checkedSourceRevision = sourceRevision;
  const order = articleDetailOrder(g, opened.id);
  const { signal } = g;
  // Each view stays hidden until its own read verifies current access.
  reader.hidden = true;
  document.body.dataset.printable = "false";
  if (pinned) {
    $("source-review-frame").hidden = true;
    $("back-to-article").hidden = true;
    setSourceLoading(true);
    $("source-review-meta").textContent = "Checking the stored source…";
  }
  try {
    const articleRead = Promise.all([
      session.matchesCurrentSession({ signal }),
      requestArticleDetail(order, articleRequestPath(opened.id), { signal }),
    ]);
    const sourceRead = pinned ? requestJSON(pinned.pathname + pinned.search, { signal, headers: sourceDocumentHeaders })
      .then(value => ({ value }), error => ({ error })) : null;
    const [sameSession, detail] = await articleRead;
    if (!g.current()) return;
    const article = acceptArticleDetail(order, detail)?.data?.article;
    if (!sameSession || detail.status !== 200 || !scopeMatches(detail.data?.configuration) ||
        article?.id !== opened.id || !readableArticle(article) || processingArticle(article)) {
      invalidate();
      await recheck();
      return;
    }
    vehicle = detail.data.configuration;
    renderPurchase();
    renderArticle(article, g);
    if (articleViewRevision(opened) !== articleViewRevision(article) || opened.processing?.state !== article.processing?.state)
      showArticleReadStatus(opened.id, article);
    show("reader");
    restoreFocus();
    if (!sourceRead) return;
    const { value, error } = await sourceRead;
    if (!g.current()) return;
    if ([401, 403, 410].includes(error?.status)) throw error;
    if (sourceRevision !== checkedSourceRevision) return;
    const returned = validSourceURL(value?.source?.url);
    if (returned?.pathname === pinned.pathname &&
        returned.searchParams.get("source_revision_id") === pin) {
      $("source-review-frame").hidden = false;
      $("back-to-article").hidden = false;
      setSourceLoading(false);
      $("source-review-meta").textContent = "Stored source loaded.";
    } else {
      resetSourceReview();
      renderArticle(currentArticle, g);
      const stagedUnavailable = pin === stagedPin && error?.status === 404 && error.code === "CATALOG_NOT_FOUND";
      if (!stagedUnavailable && !$("source-review").hidden)
        $("source-review-meta").textContent = "The stored source could not be checked. Load it again to retry.";
    }
    restoreFocus();
  } catch (error) {
    if (!g.current()) return;
    invalidate();
    if ([401, 403, 410].includes(error.status)) {
      await operation(async () => { throw error; }, () => restoreRoute());
    } else {
      await recheck();
    }
  }
}
function recheckOnFocus() {
  const g = viewGeneration;
  if (g && readerCheck === g) return;
  const route = new URLSearchParams(location.search);
  if (session.state.mode === 'firebase' && !$('welcome').hidden && !currentOrder &&
      !route.has('order') && !route.has('view') && !route.has('article') &&
      (!validScope(scope()) || (route.get('configuration') === vehicle.id && route.get('region') === vehicle.region))) {
    void recheck(true);
    return;
  }
  if (!g?.current() || lifecycleCheck || !sessionEstablished || openDemo || signingIn ||
      document.visibilityState === "hidden" || !session.state.authenticated ||
      session.state.mode !== "firebase" || $("reader").hidden || !readableArticle(currentArticle) ||
      processingArticle(currentArticle) || sourceDocumentRequest || document.body.dataset.busy === "true") {
    void recheck();
    return;
  }
  readerCheck = g;
  void recheckReader(g).finally(() => {
    if (readerCheck === g) readerCheck = null;
  });
}
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void recheck();
});
window.addEventListener("focus", recheckOnFocus);
const channel =
  typeof BroadcastChannel === "function"
    ? new BroadcastChannel("autodata-session-invalidation")
    : null;
channel?.addEventListener("message", (event) => {
  if (!openDemo && event.data === "invalidate") {
    invalidate();
    session.clear();
    void recheck();
  }
});
