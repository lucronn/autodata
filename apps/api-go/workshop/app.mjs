import * as catalog from "./catalog.mjs";
import { createSession } from "./auth.mjs";
import * as commerce from "./commerce.mjs";
import {
  NavigationGeneration,
  awaitingArticleRewrite,
  readyReprojectedSource,
  readArticle,
  readableArticle,
  processingArticle,
} from "./article-read.mjs";

const {
  articlePresentation,
  articleSearchParams,
  configurationLabel,
  DEFAULT_COLLECTION_POLL_INTERVAL_MS,
  selectorLabel,
  delay,
  filterArticles,
  localImageURL,
  matchesRetainedReaderSession,
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
  demoIndexedCount = null,
  articlePage = 0,
  indexPage = null,
  pendingIndexPage = null,
  indexLoaded = false,
  indexComplete = false,
  indexCatalogEmpty = false,
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
  sourceFigureLoads = null,
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
    $("signin").disabled = !state.ready && !state.popupPending;
    $("signin").textContent = state.popupPending
      ? "Reopen Google sign-in"
      : state.confirm
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
  { error = false, busy = false, retry = null, retryText = "Try again", complete = false, cancelable = busy,
    announceOnly = false, modelAlternatives = null } = {},
) {
  $("activity-text").textContent = text;
  const alternatives = $("model-alternatives");
  if (modelAlternatives) {
    const model = $("model");
    const group = model.value;
    const path = selectorPath("configuration");
    if (alternatives.hidden || alternatives.dataset.path !== path) {
      alternatives.replaceChildren();
      alternatives.dataset.path = path;
    }
    const remaining = new Map(modelAlternatives.map(({ id, name }) => [id, name]));
    for (const button of Array.from(alternatives.children)) {
      if (remaining.get(button.value) === button.textContent) remaining.delete(button.value);
      else button.remove();
    }
    for (const [id, name] of remaining) {
      const button = document.createElement("button");
      button.type = "button";
      button.value = id;
      button.className = "text-button";
      button.textContent = name;
      button.addEventListener("click", () => {
        if (model.disabled || model.value !== group || selectorPath("configuration") !== path ||
            !Array.from(model.options).some(option => option.value === id && !option.disabled)) return;
        model.value = id;
        model.focus();
        model.dispatchEvent(new Event("change", { bubbles: true }));
      });
      alternatives.append(button);
    }
  }
  if (alternatives) alternatives.hidden = !modelAlternatives;
  $("activity").dataset.tone = error ? "error" : busy ? "loading" : "ready";
  $("activity").hidden = announceOnly;
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
  demoIndexedCount = null;
  articlePage = 0;
  indexPage = null;
  pendingIndexPage = null;
  indexLoaded = false;
  indexComplete = false;
  indexCatalogEmpty = false;
  indexHydrating = false;
  indexFailed = false;
  resetReaderContent();
  $("articles").replaceChildren();
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
function resetSourceReview({ keepControls = false } = {}) {
  sourceFigureLoads?.stopWatching?.();
  sourceFigureLoads = null;
  sourceImageRefresh = null;
  sourceDocumentRequest = null;
  mountedSource = null;
  sourceURL = "";
  ++sourceRevision;
  displayedSourceRevision = sourceRevision;
  delete $("reader").dataset.readingOriginal;
  if (!keepControls) {
    $("source-review").hidden = true;
    $("open-original").hidden = true;
    $("source-review-link").removeAttribute("href");
    $("source-review-meta").textContent = "";
  }
  $("original-error").hidden = true;
  $("back-to-article").hidden = true;
  setSourceLoading(false);
  $("source-review-frame").replaceChildren();
  $("source-review-frame").hidden = true;
}
function resetReaderContent() {
  currentArticle = null;
  renderedRevision = "";
  articleImageRefresh = null;
  deferredArticleFigures?.stopWatching?.();
  deferredArticleFigures = null;
  resetSourceReview();
  $("article-content").replaceChildren();
  $("reference-data").replaceChildren();
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
function updateURL({ article = "", replace = false, library = false, previousArticle = "" } = {}) {
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
  if (url !== location.pathname + location.search) {
    const state = previousArticle ? { workshopRelatedFrom: previousArticle } : null;
    history[replace ? "replaceState" : "pushState"](state, "", url);
  }
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
  const options = rows[name].map((item) => pickerChoice(name, item));
  const unchanged = select.options.length === options.length + 1 && options.every(({ value, label, disabled }, index) => {
    const option = select.options[index + 1];
    return option.value === value && option.text === label && option.disabled === disabled;
  });
  if (!unchanged) {
    select.replaceChildren(
      new Option(`Choose ${name === "configuration" ? "engine / trim" : name}`, ""),
      ...options.map(pickerOption),
    );
  }
  const nextValue = options.some(({ value, disabled }) => value === selected && !disabled) ? selected : "";
  if (select.value !== nextValue) select.value = nextValue;
  select.disabled = !items.length;
}
function pickerChoice(name, item) {
  return {
    value: String(item.id ?? item.year),
    label: selectorLabel(name, item),
    disabled: name === "configuration" && configurationChoiceDisabled(item),
  };
}
function configurationChoiceDisabled(item) {
  return item.configuration_unresolved === true || item.engine_variant_market_unverified === true;
}
function pickerOption({ value, label, disabled }) {
  const option = new Option(label, value);
  option.disabled = disabled;
  return option;
}
function selectorPath(name, selection = { year: $("year").value, make: $("make").value, model: $("model").value }) {
  return vehicleSelectorPath(name, selection);
}
function canCachePublicSelectors() {
  // The server marks this shell using the policy that mounts the selector routes.
  return $("workshop-catalog-module")?.dataset?.publicSelectors === "true" && session.state.mode !== "local";
}
function cachedSelector(path, desired = "") {
  if (!canCachePublicSelectors()) return null;
  const entry = selectorCache.get(path);
  if (entry?.expires > performance.now()) {
    const response = entry.response;
    if (response.complete === false && desired &&
        !response.items.some(item => String(item.id ?? item.year) === desired)) return null;
    return response;
  }
  selectorCache.delete(path);
  return null;
}
function rememberSelector(path, name, response, expires) {
  if (!canCachePublicSelectors() || !response.items.length || response.refreshFailed || response.timedOut) return;
  const complete = !response.hydrating &&
    (response.complete === true || (name === "year" && response.complete === undefined));
  // Makes and models can be chosen while their provider coverage is incomplete.
  const partialChoices = (name === "make" || name === "model") && response.complete === false;
  if (!complete && !partialChoices) return;
  selectorCache.delete(path);
  selectorCache.set(path, { response, expires: expires ?? performance.now() + selectorCacheLifetime });
  if (selectorCache.size > selectorCacheSize) selectorCache.delete(selectorCache.keys().next().value);
}
function pickerHasChoices(name, items) {
  return name === "configuration"
    ? items.some(item => !configurationChoiceDisabled(item))
    : items.length > 0;
}
function usableEngineChoices(name, response) {
  return name === "configuration" && !response.hydrating && pickerHasChoices(name, response.items) &&
    response.items.every((item) => item.complete !== false);
}
function groupedModelNames() {
  const selected = $("model").value;
  const group = rows.model.find((item) => item.id === selected);
  const names = group?.name?.split("/").map((name) => name.trim());
  const keys = names?.map((name) => name.toLowerCase());
  if (!keys || keys.length < 2 || keys.includes("") || new Set(keys).size !== keys.length) return null;
  return names;
}
function groupedModelChoices(names) {
  if (!names) return null;
  const selected = $("model").value;
  const choices = names.flatMap((name) => {
    const model = rows.model.find((item) => item.id !== selected && item.name?.toLowerCase() === name.toLowerCase());
    return model ? [{ id: model.id, name }] : [];
  });
  return choices.length ? choices : null;
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
  if (name === "year" || stored.complete) return stored;
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
async function refreshPicker(name, { followDiscovery = false, waitForDiscovery = false, startDiscovery = false, onChoices } = {}) {
  const picker = pickerStates.get(name);
  const select = $(name);
  if (!picker?.incomplete || select.disabled || picker.path !== selectorPath(name) ||
      picker.loading?.current() || (picker.refresh && !picker.refresh.signal.aborted)) return;
  const refresh = new AbortController();
  picker.refresh = refresh;
  try {
    if (waitForDiscovery) await delay(DEFAULT_COLLECTION_POLL_INTERVAL_MS, refresh.signal);
    await readCollection(async (timeout) => {
      if (!startDiscovery) return readStoredPicker(picker, name, refresh.signal, timeout);
      startDiscovery = false;
      const data = await requestJSON(picker.path, { signal: refresh.signal, timeout, optionalModelRefresh: true });
      if (data.hydrating || data.discovering) picker.discoveryInstance = data.discovery_instance;
      return data;
    }, {
      signal: refresh.signal,
      // Reopening checks a partial list once. A discovery in progress can keep adding rows.
      attempts: followDiscovery || name === "configuration" ? undefined : 1,
      backoffWithChoices: true,
      hasChoices: data => pickerHasChoices(name, data.items),
      onUpdate(data) {
        if (pickerStates.get(name) !== picker || picker.path !== selectorPath(name) || select.disabled)
          return;
        if (!data.items.length) return;
        picker.incomplete = data.complete !== true;
        rememberSelector(picker.path, name, data);
        const refreshMarketLabels = name === "make" || name === "model";
        if (refreshMarketLabels || (name === "configuration" && rows[name].some(configurationChoiceDisabled))) {
          const refreshed = new Map(data.items.map((item) => [String(item.id), item]));
          const options = new Map(Array.from(select.options, (option) => [option.value, option]));
          rows[name] = rows[name].map((item) => {
            const current = refreshed.get(String(item.id));
            if (!current) return item;
            if (!refreshMarketLabels &&
                (!configurationChoiceDisabled(item) || current.engine_variant !== item.engine_variant)) return item;
            const choice = pickerChoice(name, current);
            const option = options.get(choice.value);
            if (option) {
              if (option.text !== choice.label) option.text = choice.label;
              if (option.disabled !== choice.disabled) option.disabled = choice.disabled;
            }
            return current;
          });
        }
        const known = new Set(rows[name].map((item) => String(item.id ?? item.year)));
        const additional = data.items.filter((item) => !known.has(String(item.id ?? item.year)));
        if (additional.length && name === "year") {
          populate(name, [...rows[name], ...additional]);
        } else if (additional.length) {
          rows[name] = [...rows[name], ...additional];
          select.append(...additional.map((item) => pickerOption(pickerChoice(name, item))));
        }
        onChoices?.();
      },
    });
  } catch {
    // Opening a picker can still use its existing choices if the optional read fails.
  } finally {
    if (picker.refresh === refresh) picker.refresh = null;
  }
}
async function loadOptions(name, g, desired = "", initial = null, {
  initialIsLive = false, initialRequest, retry = () => restoreRoute(),
} = {}) {
  const path = selectorPath(name);
  pickerStates.get(name)?.refresh?.abort();
  const picker = { path, incomplete: false, loading: g };
  pickerStates.set(name, picker);
  const cached = cachedSelector(path);
  const choice = (item) => String(item.id ?? item.year) === desired;
  const label = name === "configuration" ? "engine / trim" : name;
  const stopWithChoices = name !== "configuration" && !desired;
  const groupNames = name === "configuration" && !desired ? groupedModelNames() : null;
  let modelAlternatives = groupedModelChoices(groupNames);
  let loadingStatus = modelAlternatives
    ? "Checking engines for this group. You can choose an individual model."
    : `Loading ${label} choices…`;
  let requestedSelector = false;
  function trackDiscovery(response) {
    if (g.current() && (response.hydrating || response.discovering))
      picker.discoveryInstance = response.discovery_instance;
    return response;
  }
  function showChoices(data) {
    if (!g.current()) return;
    picker.incomplete = data.complete === false ||
      (data.complete !== true && Boolean(data.hydrating || data.discovering));
    populate(name, data.items, desired);
    if (!(data.hydrating || data.discovering)) return;
    const hasChoices = pickerHasChoices(name, data.items);
    if (modelAlternatives && !hasChoices) return;
    const message = hasChoices
      ? `More ${label} choices are loading. You can choose an available option.`
      : data.items.length ? "Checking sources for a verified engine or trim…" : `Loading ${label} choices…`;
    if (message === loadingStatus) return;
    loadingStatus = message;
    status(message, data.items.length ? { cancelable: true } : { busy: true });
  }
  status(loadingStatus, { busy: true, modelAlternatives });
  stage(name);
  $(name).disabled = true;
  const result = await readCollection(
    async (timeout) => {
      if (cached && (!desired || cached.items.some(choice))) return trackDiscovery(cached);
      if (initial) {
        const response = await initial;
        initial = null;
        g.signal.throwIfAborted();
        if (Array.isArray(response?.items)) {
          if (initialIsLive) {
            requestedSelector = true;
            if (initialRequest?.sameOrigin && name === "model" && pickerHasChoices(name, response.items)) picker.sameOrigin = true;
            return trackDiscovery(response);
          }
          const discoveryActive = response.hydrating || response.discovering;
          const storedChoicesReady = desired
            ? response.items.some(choice)
            : response.complete === true || (stopWithChoices && discoveryActive && response.items.length > 0);
          if (name === "year" || storedChoicesReady) {
            // A stored read can only report discovery that has already started.
            if (name !== "year" && response.complete !== true && !discoveryActive)
              void requestJSON(path, { signal: g.signal, optionalModelRefresh: name === "model" })
                .then(trackDiscovery).catch(() => null);
            return trackDiscovery(response);
          }
          if (response.items.length) {
            // Make stored choices usable while the verified parent starts discovery.
            showChoices({ ...response, hydrating: true });
          }
        }
        // Stored descendants cannot start ingestion. A regular read can do so once the parent is valid.
      }
      if (name !== "year" && requestedSelector) return readStoredPicker(picker, name, g.signal, timeout);
      requestedSelector = true;
      const cache = canCachePublicSelectors() ? "default" : "no-store";
      const modelPicker = pickerStates.get("model");
      const preferSameOrigin = name === "configuration" && modelPicker?.sameOrigin && modelPicker.path === selectorPath("model");
      const response = await requestJSON(path, {
        signal: g.signal, timeout, cache, preferSameOrigin, deferModelRefresh: name === "model" && !desired,
      });
      return trackDiscovery(response);
    },
    {
      signal: g.signal,
      desired,
      backoffWithChoices: true,
      backoffWithoutChoices: name !== "year",
      retryEmptyTransientRead: name === "model",
      stopWithChoices,
      hasChoices: data => pickerHasChoices(name, data.items),
      async emptyProbe(timeout) {
        try {
          return await readStoredPicker(picker, name, g.signal, timeout);
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
  const incomplete = result.refreshFailed || result.timedOut || (result.complete === false && !choicesReady);
  if (groupNames && modelAlternatives?.length !== groupNames.length &&
      !pickerHasChoices(name, result.items) && pickerStates.get("model")?.incomplete) {
    let announcedChoices;
    const showAvailableModels = () => {
      if (!g.current()) return;
      modelAlternatives = groupedModelChoices(groupNames);
      const choices = modelAlternatives?.map(({ id }) => id).join("/") ?? "";
      if (announcedChoices === choices) return;
      announcedChoices = choices;
      const message = modelAlternatives
        ? "Checking for more individual models. You can choose an available model."
        : "Checking available models for this group…";
      status(message, { busy: true, modelAlternatives });
    };
    showAvailableModels();
    // Choosing the group canceled the picker refresh. Resume stored reads if its engine list is empty.
    await refreshPicker("model", { followDiscovery: true, onChoices: showAvailableModels });
    if (!g.current()) return;
  }
  if (modelAlternatives && !pickerHasChoices(name, result.items)) {
    status("No verified engine or trim loaded for this group. Choose an individual model.",
      { modelAlternatives, retry: incomplete ? retry : null });
    return;
  }
  if (!selected && incomplete) {
    if (!desired && result.items.length) {
      const message = pickerHasChoices(name, result.items)
        ? `Choose an available ${label}. Some choices could not be loaded.`
        : "No verified engine or trim loaded. Try again.";
      status(message, { retry });
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
  if (name === "configuration") {
    const desiredChoice = desired && result.items.find(choice);
    if (desiredChoice && configurationChoiceDisabled(desiredChoice))
      throw new Error("This saved configuration is unverified. Choose an available engine or trim.");
    if (result.items.length && result.items.every(configurationChoiceDisabled)) {
      status("No verified engine or trim is available for this vehicle. Choose another vehicle.");
      return;
    }
  }
  status(
    result.items.length
      ? "Choose your vehicle to continue."
      : "No choices are available for this selection. Choose another vehicle.",
  );
  if (name === "model" && !desired && result.refresh_deferred) {
    // Let a new empty lookup start first when the customer can already choose a model.
    void refreshPicker(name, { followDiscovery: true, waitForDiscovery: true, startDiscovery: true });
  } else if (result === cached && picker.incomplete) {
    void refreshPicker(name, { followDiscovery: name === "model" && !desired });
  } else if ((name === "make" || name === "model") && !desired && result.hydrating) {
    void refreshPicker(name, { followDiscovery: true, waitForDiscovery: true });
  }
}
function retryPicker(name) {
  const path = selectorPath(name);
  const retry = () => {
    if (selectorPath(name) === path)
      return operation((g) => loadOptions(name, g, "", null, { retry }), retry);
  };
  return retry;
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
        ? indexCatalogEmpty
          ? "Owned."
          : "Owned. Open your articles without another purchase."
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
    ? session.state.popupPending ? "Reopen Google sign-in" : "Sign in with Google"
    : access === "owned"
      ? (indexCatalogEmpty ? "Check article availability" : "Open articles")
      : paymentReceived
        ? (simulation ? "Simulation complete" : "Payment received")
        : canResume
          ? "Continue checkout"
          : confirming
            ? ({ open: "Checkout open", unavailable: "Checkout status unavailable" }[unconfirmedOrder.state] || "Payment pending")
            : (simulation ? "Simulate purchase" : "Buy for $20 USD");
  action.disabled = !session.state.authenticated
    ? !session.state.ready && !session.state.popupPending
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
    (vehicle?.engine || vehicle?.engine_variant || vehicle?.trim || vehicle?.body_style || vehicle?.drivetrain) &&
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
  focusArticle = "", indexAnchor = "", firstIndex = null, preferRetained = false, initialDemoIndex = null,
  initialRetainedReader = null,
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
    } catch (error) {
      if (needsPublicLabel && current() && error.code === "CONFIGURATION_NOT_FOUND") {
        vehicle = null;
        renderPurchase();
        status("This saved vehicle choice is unavailable in the selected region.");
        return;
      }
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
    if (openDemo && savedLink && uuid(articleID)) {
      const detail = initialDemoIndex?.detail;
      if (detail) g.signal.addEventListener("abort", initialDemoIndex.abort, { once: true });
      if (await loadArticle(articleID, g, { savedLink: true, initialDemoDetail: detail })) return;
      if (detail) initialDemoIndex = { ...initialDemoIndex, detail: null };
    }
    if (directArticle && await loadArticle(articleID, g, { savedLink: true, preferRetained, initialRetainedReader })) return;
    if (savedQuery && await loadSavedSearch(g, savedQuery, focusArticle)) return;
    if (!g.current()) return;
    await loadArticles(g, articleID, {
      focusOnShow, focusArticle, indexAnchor, includePurchaseQuote: Boolean(retainedQuote), firstIndex, initialDemoIndex,
    });
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

function hasSettledPartialSearch(result) {
  const progress = result.progress;
  return result.complete !== true && result.hydrating !== true && result.discovering !== true &&
    progress?.status === "failed" && progress.retryable === false &&
    Number.isSafeInteger(progress.processed) && progress.processed > 0;
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
  indexCatalogEmpty = searchComplete && result.items.length === 0 && result.progress?.catalog_empty === true;
  indexFailed = hasSettledPartialSearch(result);
  indexHydrating = !searchComplete && !indexFailed;
  access = "owned";
  renderPurchase();
  show("catalog");
  renderArticles();
  if (focusArticle) focusArticleIndex(focusArticle);
  if (searchComplete || indexFailed) showArticleIndexStatus();
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

function firstIndexPageForVehicle(index, configuration) {
  if (index?.version !== "v1" || index.configuration?.id !== configuration.id ||
      index.configuration.region !== configuration.region || !Array.isArray(index.items) || !index.items.length)
    return null;
  try {
    indexResponsePage(index, true, configuration, null);
    return { value: index };
  } catch {
    // An unusable first page falls back to the ordinary authorized index read.
    return null;
  }
}

async function loadArticles(g, articleID = "", {
  focusOnShow = false, focusArticle = "", indexAnchor = "", offset = null,
  includePurchaseQuote = false, firstIndex = null, initialDemoIndex = null,
} = {}) {
  if (!g.current()) return;
  const selected = { id: vehicle.id, region: vehicle.region };
  const demoDetail = openDemo ? initialDemoIndex?.detail : null;
  if (demoDetail) g.signal.addEventListener("abort", initialDemoIndex.abort, { once: true });
  let offerPaging = !openDemo && !articleID && (!focusArticle || indexAnchor) &&
    !trimArticleSearch($("search").value);
  // A saved-link fallback needs the requested descriptor even when its body is unavailable.
  const compactDemo = openDemo && !articleID;
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
    const path = articleRequestPath(undefined, "", offerPaging ? pageQuery : undefined);
    const options = { signal: g.signal, timeout };
    const prefer = [
      includePurchaseQuote && "workshop-purchase-quote",
      offerPaging && articleIndexPagePreferences,
      compactDemo && "workshop-demo-readable-index",
    ].filter(Boolean).join(", ");
    const startup = initialDemoIndex;
    initialDemoIndex = null;
    const fetcher = startup?.path === path && prefer === "workshop-demo-readable-index"
      ? async (_path, { signal }) => {
        signal.throwIfAborted();
        signal.addEventListener("abort", startup.abort, { once: true });
        const response = await startup.response;
        if (!response) throw new TypeError("The initial article index request did not return a response.");
        return response;
      } : undefined;
    return requestJSON(path, {
      ...options,
      fetcher,
      headers: prefer ? { Prefer: prefer } : undefined,
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
      // Give the first owned page one more chance to appear during the initial poll interval.
      emptyProbeDelays: offerPaging ? [350, 900] : undefined,
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
        demoIndexedCount = openDemo && Number.isSafeInteger(result.indexed_count) &&
          result.indexed_count >= articles.length ? result.indexed_count : null;
        indexLoaded = true;
        indexComplete = result.complete === true;
        indexCatalogEmpty = indexComplete && (demoIndexedCount ?? articles.length) === 0;
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
    await loadArticle(articleID, g, { initialDemoDetail: demoDetail, indexedArticle: requestedArticle });
  } else if (articleID && indexComplete) {
    throw new Error("This article is unavailable for the selected vehicle.");
  } else {
    indexHydrating = false;
    showArticleIndexStatus(articleID, indexRead?.refreshFailed || (!indexRead?.progress && articles.length > 0));
  }
}

function showArticleIndexStatus(articleID = "", refreshFailed = false) {
  if (indexComplete) {
    const ready = indexCatalogEmpty ? "No articles are currently available for this vehicle." :
      !indexLoaded && searchItems ? "Article search ready." : "Article index ready.";
    status(ready, { complete: true, announceOnly: indexCatalogEmpty });
  } else if (indexFailed) {
    let message = "Your article index could not be prepared.";
    if ((searchItems ?? articles).length)
      message = "You can open the articles below. Some sources could not be reached.";
    else if (articles.length || (!indexLoaded && searchItems))
      message = "Some sources could not be reached.";
    status(message, { complete: false });
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
  "id", "title", "kind", "component", "service_schedule", "availability", "content_status",
  "source_revision_id", "canonical_revision_id", "view_revision", "review_status", "source_body_preview",
];

function sameArticleDescriptor(item, current) {
  return current && articleDescriptorFields.every((field) => item[field] === current[field]);
}

function searchHitsOnCurrentIndex(items) {
  const descriptors = new Map(articles.map((item) => [item.id, item]));
  return items.filter((item) => sameArticleDescriptor(item, descriptors.get(item.id)));
}

function scheduleArticleSearch({ fromIndex = false, immediate = false, restoreFocus } = {}) {
  const query = trimArticleSearch($("search").value);
  const refresh = fromIndex && query === searchQuery;
  if (refresh && searchPending && !indexCatalogEmpty) {
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
  searchPending = Boolean(query && vehicle?.id && access === "owned" && !indexCatalogEmpty);
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
      if (!indexLoaded) {
        const exact = result.configuration?.id === vehicleID && result.configuration.region === region;
        indexComplete = searchComplete;
        indexFailed = exact && hasSettledPartialSearch(result);
        indexHydrating = !searchComplete && result.hydrating === true;
        indexCatalogEmpty = searchComplete && items.length === 0 && result.progress?.catalog_empty === true &&
          exact;
        renderPurchase();
      }
      searchPending = false;
      if (searchRefreshPending) scheduleArticleSearch({ fromIndex: true, restoreFocus });
      else {
        renderArticles();
        if (!indexLoaded && (indexComplete || indexFailed)) showArticleIndexStatus();
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
  if (fromIndex || immediate) startSearch();
  else searchTimer = setTimeout(startSearch, 150);
}

function hasRetainedArticleRevision(article) {
  return article.availability === "available" &&
    (article.content_origin === "canonical" && uuid(article.canonical_revision_id) ||
      article.content_origin === "source" && uuid(article.source_revision_id));
}

function hasSupplierPreview(article) {
  return article.availability === "available" && article.content_origin === "source" &&
    article.source_body_preview === true && article.source_revision_id == null && article.canonical_revision_id == null;
}

function rememberRetainedReader(response) {
  const { article, configuration } = response.data;
  if (openDemo || session.state.mode !== "firebase" || !session.state.authenticated ||
      response.status !== 200 || !uuid(article.id) || article.source_body_preview ||
      !readableArticle(article) || !hasRetainedArticleRevision(article)) return;
  const params = new URLSearchParams(location.search);
  if (params.get("article") === article.id && params.get("configuration") === configuration?.id &&
      params.get("region") === configuration?.region && history.state?.workshopArticleReadable !== true) {
    // Remember readiness only. Every history entry still reloads the authorized body.
    history.replaceState({ ...history.state, workshopArticleReadable: true }, "");
  }
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
      const metadata = element("span", undefined, "article-metadata");
      metadata.append(element("span", undefined, "article-type"), element("span", "Ready to read", "article-ready"));
      link.append(element("span"), metadata);
      link.addEventListener("click", (event) => {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        openArticle(item.id, link, { preferRetained: link.dataset.retained === "true" });
      });
      row.append(link);
    }
    previous.delete(item.id);
    const link = row.firstElementChild;
    const [type, ready] = link.children[1].children;
    link.dataset.retained = String(hasRetainedArticleRevision(item));
    const kind = typeof item.kind === "string"
      ? item.kind.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ")
      : "";
    const title = item.title || "Untitled article";
    const label = item.service_schedule || (kind ? kind[0].toUpperCase() + kind.slice(1) : "Article");
    if (link.children[0].textContent !== title) link.children[0].textContent = title;
    if (type.textContent !== label) type.textContent = label;
    ready.hidden = openDemo || item.availability !== "available";
    const readyLabel = item.source_body_preview ? "Supplier preview ready" : "Ready to read";
    if (ready.textContent !== readyLabel) ready.textContent = readyLabel;
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
  $("vehicle-caption").textContent = $("purchase-selection").textContent;
  const search = $("search");
  const query = trimArticleSearch(search.value);
  const focusedSearch = document.activeElement === search;
  $("article-search").hidden = indexCatalogEmpty;
  if (indexCatalogEmpty && focusedSearch) focusArticleIndex();
  const searching = Boolean(query && searchQuery === query);
  const localSearch = searching && searchItems === null;
  const page = query ? null : indexPage;
  const items = indexCatalogEmpty ? [] : articleIndexItems(query);
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
  const resultsComplete = indexComplete && (indexCatalogEmpty || !searching || searchComplete);
  const indexedCount = demoIndexedCount ?? articles.length;
  const indexUnavailable = indexFailed && !articles.length && (indexLoaded || !searchItems);
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
            ? `${items.length} available articles · ${indexedCount} indexed`
            : articleCount;
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
  $("no-results").textContent = indexCatalogEmpty
    ? "No articles are currently available for this vehicle."
    : searching && searchError
      ? "Article search is unavailable. Try again."
      : searching && searchPending
        ? "Searching articles…"
        : openDemo && indexedCount > 0 && !articles.some((item) => item.availability === "available")
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
  $("article-list-heading").hidden = items.length === 0;
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
  if (query && query === searchQuery && searchItems !== null) {
    const ready = searchItems.filter((item) => item.availability === "available");
    return openDemo ? ready : [...ready, ...searchItems.filter((item) => item.availability !== "available")];
  }
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
function appendFigureLabels(parent, layout, positioned) {
  for (const { left, top, font_size: fontSize, lines } of layout.labels) {
    const label = element("span", lines.join("\n"), "figure-label");
    if (positioned) {
      label.style.left = `${100 * left / layout.width}%`;
      label.style.top = `${100 * top / layout.height}%`;
      label.style.fontSize = `${100 * fontSize / layout.width}cqw`;
    }
    parent.append(label);
  }
}

function addImage(parent, image, reference, g, figures = null, useAltCaption = false) {
  const { caption, alt, figure_layout: layout } = reference || {};
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
    const viewport = element("div", undefined, "figure-viewport");
    const dimensions = image.raster_dimensions;
    if (!layout && dimensions && [dimensions.width, dimensions.height].every(
      value => Number.isInteger(value) && value >= 1 && value <= 10000
    )) {
      img.width = dimensions.width;
      img.height = dimensions.height;
      img.dataset.rasterPending = "";
      viewport.dataset.rasterPending = "";
      const settleGeometry = () => {
        delete viewport.dataset.rasterPending;
        delete img.dataset.rasterPending;
        img.removeAttribute("width");
        img.removeAttribute("height");
      };
      img.addEventListener("load", settleGeometry, { once: true });
      img.addEventListener("figureunavailable", settleGeometry, { once: true });
    }
    const size = element("button", undefined, "text-button figure-size");
    size.type = "button";
    size.hidden = true;
    size.setAttribute("aria-pressed", "false");
    const setFullSize = (fullSize) => {
      size.setAttribute("aria-pressed", String(fullSize));
      if (fullSize) {
        viewport.dataset.fullSize = "";
        viewport.setAttribute("tabindex", "0");
        viewport.setAttribute("role", "region");
        viewport.setAttribute("aria-label", img.alt);
      } else {
        delete viewport.dataset.fullSize;
        viewport.removeAttribute("tabindex");
        viewport.removeAttribute("role");
        viewport.removeAttribute("aria-label");
        viewport.scrollLeft = viewport.scrollTop = 0;
      }
    };
    size.addEventListener("click", () => {
      if (g.current() && !size.hidden) setFullSize(!("fullSize" in viewport.dataset));
    });
    img.addEventListener("load", () => {
      if (!g.current() || !img.naturalWidth) return;
      size.textContent = "Full size";
      size.hidden = false;
    });
    img.addEventListener("error", (event) => {
      size.hidden = true;
      size.textContent = "";
      if ("fullSize" in viewport.dataset) setFullSize(false);
      if (g.current() && (!event.isTrusted || !retryInterruptedFigure(g, img)))
        void renewMedia(g, img);
    });
    if (figures) figures.push({ img, url });
    else img.src = url;
    if (layout) {
      const placement = element("div", undefined, "positioned-figure");
      placement.style.setProperty("--figure-width", `${layout.width}px`);
      placement.style.setProperty("--figure-ratio", String(layout.width / layout.height));
      placement.style.aspectRatio = `${layout.width} / ${layout.height}`;
      placement.append(img);
      appendFigureLabels(placement, layout, true);
      viewport.append(placement);
    } else viewport.append(img);
    figure.append(size, viewport);
  } else {
    const missingID = missing ? imageReferenceID(reference) : "";
    if (missingID) figure.dataset.missingImagePlacement = missingImagePlacement(missingID, caption);
    const placeholder = element("p", preparing ? pendingSourceImageText : unavailableImageText, "image-missing");
    if (preparing) placeholder.dataset.pendingSourceImage = "";
    figure.append(placeholder);
    if (layout) appendFigureLabels(figure, layout, false);
  }
  if ((available || missing || preparing) && visibleCaption)
    figure.append(element("figcaption", visibleCaption));
  parent.append(figure);
}
const figureWatches = new WeakMap();
const figureLoadTimeout = 8_000;
function retryInterruptedFigure(g, img) {
  if (!img.isConnected || !img.src || img.dataset.transportRetried || img.dataset.replacement) return false;
  const url = img.src;
  const timings = globalThis.performance?.getEntriesByName?.(url, "resource");
  if (!timings) return false;
  const transfer = timings.at(-1);
  // Chromium records zero status for a failed transfer. WebKit can omit the entry.
  // A completed HTTP request belongs to the document's normal media renewal path.
  if (transfer && transfer.responseStatus !== 0) return false;
  img.dataset.transportRetried = "1";
  img.removeAttribute("src");
  requestAnimationFrame(() => {
    if (!g.current() || !img.isConnected || img.src) return;
    img.src = url;
    figureWatches.get(img)?.arm();
  });
  return true;
}
function watchFigureLoads(figures, g) {
  if (typeof IntersectionObserver !== "function") return;
  const observer = new IntersectionObserver((entries) => {
    for (const { target, isIntersecting } of entries) {
      const watch = figureWatches.get(target);
      if (watch) {
        watch.visible = isIntersecting;
        watch.arm();
      }
    }
  });
  for (const { img } of figures) {
    let timer;
    const clear = () => clearTimeout(timer);
    const watch = {
      visible: false,
      clear,
      arm() {
        clear();
        if (!watch.visible || !g.current() || !img.isConnected || img.complete) return;
        timer = setTimeout(() => {
          if (!img.complete) void renewMedia(g, img, true);
        }, figureLoadTimeout);
      },
    };
    figureWatches.set(img, watch);
    img.addEventListener("load", clear);
    img.addEventListener("error", clear);
    observer.observe(img);
  }
  let stopped = false;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    observer.disconnect();
    for (const { img } of figures) {
      const watch = figureWatches.get(img);
      watch.clear();
      img.removeEventListener("load", watch.clear);
      img.removeEventListener("error", watch.clear);
      figureWatches.delete(img);
    }
    g.signal.removeEventListener("abort", stop);
  };
  g.signal.addEventListener("abort", stop, { once: true });
  return stop;
}

function startArticleFigures(figures, g) {
  if (!figures.length) return null;
  const loadNearViewport = new Set(figures.map(({ url }) => url)).size >= 7;
  for (const { img, url } of figures) {
    if (loadNearViewport) {
      img.loading = "lazy";
      img.dataset.figurePending = "";
      img.addEventListener("load", () => { delete img.dataset.figurePending; }, { once: true });
    }
    img.src = url;
  }
  const stopWatching = watchFigureLoads(figures, g);
  return {
    figures, printing: null, imagesRefreshedAt: Date.now(),
    stopWatching() {
      stopWatching?.();
      this.printing?.abort();
    },
  };
}
function releaseArticleFigures(group) {
  for (const { img } of group?.figures || [])
    if (img.isConnected && img.loading === "lazy") img.loading = "eager";
}
async function waitForPrintFigures(pending, g, signal) {
  let timer, renewed = false;
  const watchForStall = () => {
    clearTimeout(timer);
    if (renewed || signal.aborted) return;
    timer = setTimeout(() => {
      renewed = true;
      if (signal.aborted) return;
      for (const { img } of pending)
        if (img.isConnected && !img.complete && img.dataset.replacement !== "1")
          void renewMedia(g, img, true);
    }, figureLoadTimeout);
  };
  try {
    watchForStall();
    // Wait through failed URLs. Give offscreen requests the same renewal
    // opportunity as visible figures once the batch stops making progress.
    await Promise.race([
      Promise.all(pending.map(({ img }) => new Promise(resolve => {
        const settled = () => {
          watchForStall();
          resolve();
        };
        img.addEventListener("load", settled, { once: true, signal });
        img.addEventListener("figureunavailable", settled, { once: true, signal });
      }))),
      delay(15_000, signal),
    ]);
  } finally {
    clearTimeout(timer);
  }
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
function authoredHeadingLevel(level) {
  return Number.isInteger(level) && level >= 1 && level <= 6 ? level : null;
}
function articleHeadingOutline(blocks, base) {
  let lowest = 6;
  const pending = [blocks];
  const includeChildren = (values) => {
    for (const value of values || []) {
      if (Array.isArray(value?.blocks)) pending.push(value.blocks);
    }
  };
  while (pending.length && lowest > 1) {
    for (const block of pending.pop() || []) {
      if (block?.type === "heading") {
        lowest = Math.min(lowest, authoredHeadingLevel(block.level) ?? lowest);
        if (lowest === 1) break;
      } else if (block?.type === "ordered_list" || block?.type === "unordered_list")
        includeChildren(block.items);
      else if (block?.type === "table") {
        includeChildren(block.columns);
        for (const row of block.rows || [])
          includeChildren(Array.isArray(row) ? row : row?.cells);
      }
    }
  }
  return { base, offset: base - lowest };
}
function articleReferenceLink(text, target, g) {
  if (!uuid(target) || (!openDemo && !session.state.authenticated)) return null;
  const selected = scope();
  if (!validScope(selected)) return null;
  const csrf = session.state.csrf;
  const url = new URL("/workshop", location.origin);
  url.searchParams.set("configuration", selected.configuration_id);
  url.searchParams.set("region", selected.region);
  url.searchParams.set("article", target);
  if (openDemo) url.searchParams.set("demo", "1");
  const link = element("a", text);
  link.href = url.pathname + url.search;
  link.addEventListener("click", (event) => {
    if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (g.current() && sameScope(selected, scope()) &&
        (openDemo || session.state.authenticated && session.state.csrf === csrf))
      openArticle(target, null, { referenceTitle: typeof text === "string" ? text : "" });
  });
  return link;
}

function articleLinkText(value, tag, g) {
  const text = value.text ?? "";
  if (value.type === "link") {
    const link = articleReferenceLink(text, value.target_article_id, g);
    if (!link) return element(tag, text);
    const wrapper = element(tag);
    wrapper.append(link);
    return wrapper;
  }
  if (typeof text !== "string" || !Array.isArray(value.article_links)) return element(tag, text);
  const matches = value.article_links.flatMap(reference => {
    const label = reference?.label;
    if (typeof label !== "string" || !label) return [];
    const start = text.indexOf(label);
    if (start < 0 || text.lastIndexOf(label) !== start) return [];
    const link = articleReferenceLink(label, reference.target_article_id, g);
    return link ? [{ start, end: start + label.length, link }] : [];
  }).sort((a, b) => a.start - b.start);
  if (!matches.length || matches.some((match, i) => i && match.start < matches[i - 1].end))
    return element(tag, text);
  const wrapper = element(tag);
  let position = 0;
  for (const { start, end, link } of matches) {
    if (start > position) wrapper.append(element("span", text.slice(position, start)));
    wrapper.append(link);
    position = end;
  }
  if (position < text.length) wrapper.append(element("span", text.slice(position)));
  return wrapper;
}
function renderBlocks(parent, blocks, imagesByID, review, g, sourceTargets = null, figures = null,
  outline = articleHeadingOutline(blocks, 3)) {
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
    if (value.text != null) target.append(articleLinkText(value, textTag, g));
    if (value.asset_id || value.image_id || value.status === "unavailable")
      addReference(target, value);
    for (const ref of value.images || []) addReference(target, ref);
    if (Array.isArray(value.blocks))
      renderBlocks(target, value.blocks, imagesByID, review, g, sourceTargets, figures, outline);
  };
  for (const block of blocks || []) {
    if (!block || typeof block !== "object") continue;
    const sourceID = sourceTargets && block.block_id;
    const childIndex = sourceID ? parent.children.length : 0;
    const type = block.type;
    if (type === "heading" || type === "paragraph" || type === "link") {
      if (type === "heading") {
        const authored = authoredHeadingLevel(block.level);
        const level = authored === null ? outline.base : authored + outline.offset;
        const heading = element(level <= 6 ? `h${level}` : "div", block.text ?? "", "article-heading");
        heading.dataset.headingStyle = String(Math.max(3, authored ?? 3));
        if (level > 6) {
          heading.setAttribute("role", "heading");
          heading.setAttribute("aria-level", String(level));
        }
        parent.append(heading);
      } else parent.append(articleLinkText(block, "p", g));
      for (const ref of block.images || [])
        addReference(parent, ref, false);
    } else if (type === "callout") {
      const aside = element("aside", undefined, "article-callout");
      const content = element("div");
      // A supplier schedule can carry its footnote line breaks as literal markup.
      const lines = block.label === "Footnote" && typeof block.text === "string"
        ? block.text.split(/<br\s*\/?>/i)
        : [block.text ?? ""];
      const labelText = element("span", lines[0]);
      for (const line of lines.slice(1)) labelText.append(element("br"), element("span", line));
      content.append(labelText);
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
      const renderCell = (cell, value, columnHeader = false) => {
        if (value?.table_header === true) {
          const scope = value.header_scope;
          if (["col", "row", "colgroup", "rowgroup"].includes(scope))
            cell.scope = scope;
        } else if (columnHeader) {
          cell.scope = "col";
        }
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
          renderCell(th, c, true);
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
          const cell = element(value?.table_header === true ? "th" : "td");
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
  } else if (presentation.blocks.length) {
    const outline = articleHeadingOutline(presentation.blocks, 3);
    for (const b of presentation.blocks) {
      if (b.type === "step") {
        const section = element("section", undefined, "procedure-step");
        section.append(element("span", `${b.number}.`, "step-number"));
        for (const part of b.parts || [])
          section.append(element("p", part.text ?? ""));
        parent.append(section);
      } else renderBlocks(parent, [b], imagesByID, null, g, null, null, outline);
    }
  } else parent.append(element("p", "No readable content is available yet."));
}
function retryImage(img, images) {
  const found = images.find(
    (image) => image.status !== "unavailable" && assetID(image) === img.dataset.assetId,
  );
  const url = localImageURL(found?.url, location.origin, { authMode: session.state.mode });
  if (!url || img.src === url) return false;
  img.dataset.replacement = "1";
  img.src = url;
  figureWatches.get(img)?.arm();
  return true;
}
function showUnavailableImage(img) {
  if ($("source-review-frame").contains(img)) mountedSource = null;
  const placeholder = element(
    "p",
    "Illustration unavailable. Refresh this article to try again.",
    "image-missing",
  );
  if (img.parentElement?.classList.contains("positioned-figure")) {
    const placement = img.parentElement;
    placement.before(placeholder);
    placement.classList.remove("positioned-figure");
    placement.style.removeProperty("aspect-ratio");
    for (const label of placement.querySelectorAll(".figure-label")) label.removeAttribute("style");
    img.remove();
  } else img.replaceWith(placeholder);
  img.dispatchEvent(new Event("figureunavailable"));
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
function sourceFingerprint(review) {
  const digest = review?.available ? review.content_sha256 : "";
  return typeof digest === "string" && /^[a-f0-9]{64}$/.test(digest) ? digest : "";
}
function renderArticle(article, g, redraw = false) {
  if (!g.current() || Object.hasOwn($("reader").dataset, "rechecking")) return;
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
    const figures = (openDemo || session.state.mode === "firebase") && article.document?.blocks?.length ? [] : null;
    renderContent(fragment, article, g, figures);
    if (!g.current()) return;
    deferredArticleFigures?.stopWatching?.();
    $("article-content").replaceChildren(fragment);
    deferredArticleFigures = figures ? startArticleFigures(figures, g) : null;
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
  const sourceHash = sourceFingerprint(article.source_review);
  const originalHash = sourceFingerprint(review);
  if (sourceHash !== sourceFingerprint(currentArticle?.source_review) ||
      originalHash !== sourceFingerprint(previousOriginal)) {
    const references = [];
    if (sourceHash) references.push(element("dt", "Source SHA-256"), element("dd", sourceHash));
    if (originalHash && originalHash !== sourceHash)
      references.push(element("dt", "Original SHA-256"), element("dd", originalHash));
    $("reference-data").replaceChildren(...references);
  }
  currentArticle = article;
  $("article-title").textContent = article.title || "Article";
  const articleKind =
    article.source_body_preview
      ? "Supplier source"
      : article.content_origin === "canonical"
      ? "Workshop article"
      : article.content_origin === "source"
        ? "Stored source"
        : "Article";
  $("article-kind").textContent = [articleKind, article.service_schedule].filter(Boolean).join(" · ");
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
  if (readable && article.review_status === "UNREVIEWED" && !readyReprojectedSource(article) &&
      (!processing || article.content_origin === "canonical")) {
    notes.push("Draft content has not been reviewed. Check the stored source before using this procedure.");
  }
  $("article-note").hidden = !notes.length;
  $("article-note").textContent = notes.join(" ");
  $("print").disabled = !readable;
  document.body.dataset.printable = String(readable);
  $("article-reference").hidden = !review?.available;
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
  if (readyReprojectedSource(article)) {
    status("Stored source ready.", { complete: true });
    return;
  }
  const readable = readableArticle(article);
  const checkUpdate = readable && !openDemo && session.state.mode === "firebase" &&
    (timedOut || article.content_origin === "source")
    ? () => openArticle(id, null, { refreshOnly: true })
    : null;
  const retryText = checkUpdate ? "Check for an update" : undefined;
  if (awaitingArticleRewrite(article)) {
    status("Stored source is ready. The Workshop rewrite is pending.", { retry: checkUpdate, retryText });
    return;
  }
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
      retry: checkUpdate || (timedOut || !readable ? () => openArticle(id) : null),
      retryText,
      complete: readable,
    },
  );
}
async function loadArticle(id, g, options) {
  if ((!openDemo && !session.state.authenticated) || !g.current()) return;
  const order = articleDetailOrder(g, id);
  order.loading = true;
  try {
    return await loadArticleView(id, g, order, options);
  } finally {
    order.loading = false;
  }
}
function canReturnToRelatedArticle(id) {
  if (!uuid(id) || !uuid(history.state?.workshopRelatedFrom) || history.state.workshopRelatedFrom === id ||
      (!openDemo && !session.state.authenticated)) return false;
  const params = new URLSearchParams(location.search);
  return params.get("article") === id && params.get("configuration") === vehicle?.id &&
    params.get("region") === vehicle?.region;
}
async function loadArticleView(id, g, order, {
  savedLink = false, refreshOnly = false, preferRetained = false, verifiedDetail = null,
  initialDemoDetail = null, indexedArticle = null, initialRetainedReader = null,
  referenceTitle = "",
} = {}) {
  const sameArticle = currentArticle?.id === id;
  let refreshVisibleArticle = sameArticle && !$("reader").hidden && readableArticle(currentArticle);
  const heading = $("article-title");
  if (!refreshVisibleArticle) resetReaderContent();
  if (!sameArticle) {
    const indexedTitle = indexedArticle?.id === id && typeof indexedArticle.title === "string"
      ? indexedArticle.title.trim() : "";
    const title = indexedTitle || referenceTitle.trim();
    heading.textContent = title || "Opening article…";
    document.title = title ? `${title} | AutoData` : "AutoData — The workshop reference";
    $("reader-vehicle").textContent = vehicleIdentityLabel();
    $("reader-engine").textContent = vehicle.region;
  }
  const backRelated = $("back-related");
  backRelated.hidden = !canReturnToRelatedArticle(id);
  backRelated.disabled = false;
  show("reader");
  stage("article");
  if (!verifiedDetail) {
    if (refreshVisibleArticle) status("Checking for an article update…", { cancelable: true });
    else {
      status("Opening article…", { busy: true });
      heading.focus();
    }
  }
  let readerAlignment = sameArticle ? null : new AbortController();
  if (readerAlignment) {
    const controller = readerAlignment;
    const signal = AbortSignal.any([g.signal, controller.signal]);
    const keepPosition = () => controller.abort();
    for (const type of ["wheel", "touchmove", "keydown", "pointerdown"])
      window.addEventListener(type, keepPosition, { passive: true, signal });
  }
  const selected = vehicle;
  const matchesConfiguration = (configuration) =>
    configuration?.id === selected.id && configuration?.region === selected.region;
  const detailPath = articleRequestPath(id);
  const savedDemo = openDemo && savedLink;
  const preferPreviewSourceCheck = !openDemo && session.state.mode === "firebase";
  const readOptions = {
    signal: g.signal, preferShortPublicationCheck: true, preferPreviewSourceCheck,
    ...(savedDemo && { headers: { Prefer: "workshop-short-publication-check, workshop-demo-fitment" } }),
  };
  const readInitialDetail = async () => {
    if (openDemo && (savedDemo || indexedArticle?.id === id) && initialDemoDetail?.path === detailPath) {
      const reply = await initialDemoDetail.response;
      g.signal.throwIfAborted();
      if (reply) {
        const response = await requestArticleDetail(order, detailPath, {
          ...readOptions, fetcher: async () => reply,
        }).catch((error) => {
          g.signal.throwIfAborted();
          if (error.status === 0) return null;
          throw error;
        });
        if (savedDemo && response) return response;
        // Publication may have changed while the index and detail were in flight.
        const article = response?.data?.article;
        if (response?.status === 200 && article?.id === id && readableArticle(article) &&
            (article.source_revision_id ?? null) === (indexedArticle.source_revision_id ?? null) &&
            (article.canonical_revision_id ?? null) === (indexedArticle.canonical_revision_id ?? null)) return response;
      }
    }
    return requestArticleDetail(order, detailPath, readOptions);
  };
  const deniesArticle = (status) => [401, 403, 404, 410].includes(status);
  const showSavedConfiguration = (configuration) => {
    vehicle = configuration;
    access = "owned";
    renderPurchase();
  };
  let retained = null;
  const olderThanRetained = (response) =>
    retained && retained[articleDetailSequence] > response[articleDetailSequence];
  const handleReadError = (error) => {
    if (g.current() && (retained && deniesArticle(error.status) ||
        error.status === 404 && error.code === "CATALOG_NOT_FOUND"))
      clearUnavailableArticle();
    throw error;
  };
  let retainedReadStartedAt;
  let pendingRetainedRead, retainedSession;
  const readFirst = preferRetained || (indexedArticle?.id === id && hasSupplierPreview(indexedArticle));
  if ((readFirst || initialRetainedReader) && !verifiedDetail && !refreshOnly && !openDemo &&
      session.state.mode === "firebase" && (savedLink || access === "owned") &&
      validScope({ configuration_id: selected.id, region: selected.region })) {
    // A saved route can already have a body authorized for the restored session.
    const startedAt = performance.now();
    try {
      let response;
      if (initialRetainedReader) {
        retainedSession = session.state.csrf;
        const sequence = ++order.issued;
        const verifyRetained = async (early) => {
          if (!early || !g.current() || !session.state.authenticated) return null;
          if (early.retry) return early;
          const sameSession = await matchesRetainedReaderSession(early, retainedSession);
          if (sameSession && g.current() && session.state.authenticated && session.state.csrf === retainedSession &&
              early.data?.article?.id === id && matchesConfiguration(early.data?.configuration) &&
              hasRetainedArticleRevision(early.data.article) && !early.data.article.source_body_preview &&
              readableArticle(early.data.article))
            return { ...early, [articleDetailSequence]: sequence };
          return null;
        };
        const early = await initialRetainedReader((pending) => {
          pendingRetainedRead = pending.then(verifyRetained).catch(() => null);
        });
        response = await verifyRetained(early);
        if (!g.current() || !session.state.authenticated) return;
        if (response?.retry) throw response.retry;
      }
      if (!response && readFirst) response = await requestArticleDetail(order, detailPath, readOptions);
      if (response) {
        const article = response.data?.article;
        if (article?.id !== id || !matchesConfiguration(response.data?.configuration))
          throw new Error("The article response does not match the selected vehicle.");
        if (response.status === 200 && readableArticle(article) ||
            response.status === 202 && processingArticle(article)) {
          verifiedDetail = response;
          retainedReadStartedAt = startedAt;
        }
      }
    } catch (error) {
      if (!g.current()) return;
      if (savedLink && error.status === 404) return false;
      const unavailable = error.status === 503 && error.retryable === true &&
        ["CATALOG_SOURCE_UNAVAILABLE", "CATALOG_UNAVAILABLE"].includes(error.code);
      const transport = error.status === 0 && error.code === "NETWORK_UNAVAILABLE";
      const gateway = [502, 503, 504].includes(error.status) && error.code === "HTTP_ERROR" && !error.retryAfterSeconds;
      if (!unavailable && !transport && !gateway) handleReadError(error);
    }
    if (!g.current()) return;
  }
  const prepare = !verifiedDetail && !refreshOnly && !openDemo && session.state.mode !== "local";
  let readingStatus = "Opening article…";
  const updateReader = (response, early = false) => {
    if (!g.current() || Object.hasOwn($("reader").dataset, "rechecking")) return;
    const article = response.data.article;
    const readable = readableArticle(article);
    if (retained && (!readable || olderThanRetained(response))) return;
    renderArticle(article, g, refreshVisibleArticle && !verifiedDetail);
    rememberIndexArticleReadiness(response, g);
    rememberRetainedReader(response);
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
    if (!early && !processingArticle(article)) return;
    let ready = "";
    if (readable) {
      if (article.source_body_preview) ready = "Source text is ready.";
      else if (article.content_origin === "source") ready = "Stored source is ready.";
      else ready = "Article is readable.";
    }
    const phase = article.processing?.state;
    const message = ready || (phase === "queued" ? "Waiting for the supplier article…"
      : phase === "fetching_source" ? "Fetching the supplier article…"
      : phase === "failed" ? "Waiting to retry article preparation…" : "Preparing the article…");
    if (message === readingStatus) return;
    readingStatus = message;
    status(message, ready ? { complete: true, cancelable: true } : { busy: true });
  };
  const canCheckRetained = prepare && session.state.mode === "firebase" &&
    validScope({ configuration_id: selected.id, region: selected.region });
  const earlyCheck = canCheckRetained && !refreshVisibleArticle ? new AbortController() : null;
  const earlySignal = earlyCheck && AbortSignal.any([g.signal, earlyCheck.signal]);
  let preparing = prepare;
  let keepEarlyRead = false;
  let initialReadStartedAt = retainedReadStartedAt ?? performance.now();
  let detailRead, detailStartedAt, detailPending = false;
  const pendingDetail = (response) => response?.status === 202 &&
    response.data?.article?.id === id && matchesConfiguration(response.data.configuration) &&
    processingArticle(response.data.article);
  const recoverDetail = (signal, preferEarlySourceCheck = false) => {
    if (!detailRead) {
      detailStartedAt = performance.now();
      detailPending = true;
      detailRead = requestArticleDetail(order, detailPath, {
        ...readOptions, signal, preferShortSourceCheck: true, preferEarlySourceCheck,
      })
        .catch((error) => {
          g.signal.throwIfAborted();
          if (deniesArticle(error.status)) throw error;
          return null;
        }).finally(() => { detailPending = false; });
    }
    return detailRead;
  };
  const primary = (verifiedDetail ? Promise.resolve(verifiedDetail) : prepare
    ? requestArticleDetail(order, articleRequestPath(id, "/prepare"), {
        ...readOptions,
        method: "POST",
        body: {},
        preferShortSourceCheck: true,
        reportBodyNetworkError: true,
        onResponseStatus(status) {
          if ((status === 200 || status === 202) && !detailRead || deniesArticle(status)) earlyCheck?.abort();
        },
        headers: { "X-CSRF-Token": session.state.csrf },
      })
    : readInitialDetail()).then((response) => {
      preparing = false;
      keepEarlyRead = Boolean(earlySignal && detailPending && pendingDetail(response));
      return response;
    }, async (error) => {
      const recover = preparing && g.current();
      preparing = false;
      const transport = error.status === 0 && error.code === "NETWORK_UNAVAILABLE";
      const catalogUnavailable = error.status === 503 && error.retryable === true &&
        ["CATALOG_SCHEDULING_UNAVAILABLE", "CATALOG_UNAVAILABLE"].includes(error.code);
      const gatewayUnavailable = [502, 503, 504].includes(error.status) &&
        error.code === "HTTP_ERROR" && !error.retryAfterSeconds;
      const prepareUnavailable = catalogUnavailable || gatewayUnavailable;
      if (recover && (transport || canCheckRetained && prepareUnavailable)) {
        // Reuse a check already in flight. Prepare may have committed despite the failure.
        const exact = Boolean(detailRead) || prepareUnavailable || savedLink;
        const recovered = await recoverDetail(g.signal);
        initialReadStartedAt = detailStartedAt;
        if (!g.current()) return null;
        const article = recovered?.data?.article;
        const configuration = recovered?.data?.configuration;
        if (article?.id === id && (matchesConfiguration(configuration) || !exact && !configuration) &&
            (recovered.status === 200 && readableArticle(article) ||
             recovered.status === 202 && processingArticle(article))) {
          return error.retryAfterSeconds > (recovered.retryAfterSeconds ?? 0)
            ? { ...recovered, retryAfterSeconds: error.retryAfterSeconds }
            : recovered;
        }
      }
      const demoWithoutBody = savedDemo && ["CATALOG_SOURCE_UNAVAILABLE", "CATALOG_REVIEW_REQUIRED",
        "CATALOG_PROCESSING_FAILED"].includes(error.code);
      if ((savedLink && error.status === 404) || demoWithoutBody) {
        if (retained && g.current()) clearUnavailableArticle();
        return null;
      }
      throw error;
    });
  // A fast prepare still supplies the first view. Only a slow, in-flight
  // prepare can start an optional exact read. Reuse the saved route's
  // authorized read when it completes before another request is due.
  const retainedPrepareDelayMs = 250;
  const retainedReadDelay = earlySignal && delay(retainedPrepareDelayMs, earlySignal).then(() => null);
  const retainedReadTrigger = retainedReadDelay && (pendingRetainedRead
    ? Promise.race([retainedReadDelay, pendingRetainedRead.then(response =>
        response?.status === 200 || response?.retry ? response : retainedReadDelay)])
    : retainedReadDelay);
  const earlyRead = retainedReadTrigger && retainedReadTrigger.then(async (savedResponse) => {
    if (!preparing || !g.current() || earlySignal.aborted) return;
    if (savedResponse && (savedResponse.retry || !session.state.authenticated ||
        session.state.csrf !== retainedSession)) return;
    const response = savedResponse ?? await recoverDetail(earlySignal, true);
    if ((!preparing && !keepEarlyRead) || !g.current() || earlySignal.aborted) return;
    if (pendingDetail(response)) return response;
    const article = response?.data?.article;
    const configuration = response?.data?.configuration;
    if (response?.status !== 200 || !matchesConfiguration(configuration) ||
        article?.id !== id || !readableArticle(article)) return;
    if (order.accepted?.[articleDetailSequence] > response[articleDetailSequence]) return;
    retained = response;
    if (savedLink) showSavedConfiguration(configuration);
    updateReader(response, true);
    return response;
  }, () => {});
  const first = await (earlyRead ? Promise.race([primary, earlyRead.then(() => primary)]) : primary)
    .catch(handleReadError)
    .finally(() => {
      preparing = false;
      if (!keepEarlyRead) earlyCheck?.abort();
    });
  if (!g.current()) return;
  if (savedLink) {
    const configuration = first?.data?.configuration;
    const unconfirmedDemo = savedDemo && (first?.status !== 200 || first.data?.article?.id !== id ||
      !readableArticle(first.data.article));
    if (!matchesConfiguration(configuration) || unconfirmedDemo) {
      if (retained) clearUnavailableArticle();
      return false;
    }
    showSavedConfiguration(configuration);
  }
  let initial = first;
  let reuseEarlyRead = keepEarlyRead;
  const polling = readArticle(
    async (options) => {
      if (initial) {
        const value = initial;
        initial = null;
        return value;
      }
      if (reuseEarlyRead) {
        reuseEarlyRead = false;
        // Use the in-flight read at the next scheduled slot within its time budget.
        const wait = Math.min(retainedPrepareDelayMs, Math.floor(options.timeout / 2));
        if (wait > 0) {
          const startedAt = performance.now();
          const response = await Promise.race([earlyRead, delay(wait, earlySignal).then(() => null)]);
          if (response) return response;
          const elapsed = Math.ceil(performance.now() - startedAt);
          options = { ...options, timeout: Math.max(1, options.timeout - elapsed),
            readableBodyTimeout: options.readableBodyTimeout && Math.max(1, options.readableBodyTimeout - elapsed) };
        }
      }
      return requestArticleDetail(order, detailPath, { ...options, preferPreviewSourceCheck });
    },
    {
      signal: keepEarlyRead ? earlySignal : g.signal,
      initialReadStartedAt,
      selectResponse(response) {
        // An older prepare can confirm an active job without replacing the retained view.
        const keepRetained = olderThanRetained(response) && !processingArticle(response.data?.article);
        return acceptArticleDetail(order, keepRetained ? retained : response);
      },
      onUpdate: updateReader,
    },
  );
  const result = await (keepEarlyRead ? Promise.race([polling, earlyRead.then(() => polling)]) : polling)
    .catch(handleReadError)
    .finally(() => earlyCheck?.abort());
  if (!g.current()) return;
  if (!Object.hasOwn($("reader").dataset, "rechecking"))
    showArticleReadStatus(id, retained ? currentArticle : result.data?.article, result.timedOut);
  return true;
}
function openArticle(id, indexLink = null, { refreshOnly = false, preferRetained = false, referenceTitle = "" } = {}) {
  const indexURL = location.href;
  const params = (indexLink || referenceTitle) && new URL(indexURL).searchParams;
  const sameVehicle = params && params.get("configuration") === vehicle?.id && params.get("region") === vehicle?.region;
  const previousArticle = referenceTitle && sameVehicle && uuid(currentArticle?.id) &&
    currentArticle.id !== id && params.get("article") === currentArticle.id ? currentArticle.id : "";
  const indexedArticle = indexLink && (searchItems?.find((item) => item.id === id) ||
    articles.find((item) => item.id === id));
  updateURL({ article: id, previousArticle });
  if (indexURL !== location.href) {
    articleIndexOrigin = indexLink && sameVehicle && !params.has("article") && !params.has("order") &&
      access === "owned" && session.state.authenticated && session.state.csrf
      ? { indexURL, readerURL: location.href, indexLink, articleID: id, configuration: scope(), csrf: session.state.csrf,
          paged: Boolean(indexPage && !params.has("q")) }
      : null;
  }
  operation(
    (g) => {
      if (articleIndexOrigin && articleIndexOrigin.readerURL === location.href)
        articleIndexOrigin.generation = g;
      return loadArticle(id, g, { refreshOnly, preferRetained, indexedArticle, referenceTitle });
    },
    () => openArticle(id, null, { refreshOnly, preferRetained, referenceTitle }),
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
function recentMediaURLs(issuedAt, now) {
  return issuedAt <= now && now - issuedAt < 30_000;
}

function sourceAssetAvailability(images) {
  return JSON.stringify([...images].map(([id, image]) => [
    id, Boolean(localImageURL(image.url, location.origin, { authMode: session.state.mode })),
  ]));
}

function refreshPendingFigures(view, images, failed = null) {
  const now = Date.now();
  if (recentMediaURLs(view.imagesRefreshedAt, now)) return false;
  const pending = view.figures.filter(({ img }) => "figurePending" in img.dataset &&
    (!failed || img !== failed && !img.complete));
  if (!pending.length) return false;
  // Lazy figures may make their first request after the earlier signed URLs
  // have expired. Leave downloaded figures in place and use the fresh read.
  view.imagesRefreshedAt = now;
  for (const { img } of pending) {
    const url = localImageURL(images.get(img.dataset.assetId)?.url, location.origin, { authMode: session.state.mode });
    if (!url || img.src === url) continue;
    delete img.dataset.replacement;
    img.src = url;
    figureWatches.get(img)?.arm();
  }
  return true;
}

function sourceDocumentKey(requested) {
  const query = new URLSearchParams(requested.search);
  // The JSON document is independent of the clicked evidence marker.
  query.delete("evidence_id");
  query.delete("source_locator");
  query.sort();
  return `${requested.pathname}?${query}`;
}

function matchesMountedSource(key, g) {
  return !openDemo && session.state.mode === "firebase" && mountedSource?.key === key &&
    mountedSource.signal === g.signal && mountedSource.articleRevision === renderedRevision;
}

function requestSourceDocument(path, g, key, sourceView) {
  const timeout = 10_000;
  const deadline = performance.now() + timeout;
  const options = {
    signal: g.signal,
    timeout,
    reportBodyNetworkError: true,
    headers: sourceView ? { ...sourceDocumentHeaders, "X-Workshop-Source-View": sourceView } : sourceDocumentHeaders,
  };
  const response = requestJSON(path, options).catch((error) => {
    g.signal.throwIfAborted();
    const remaining = Math.floor(deadline - performance.now());
    if (error.code !== "NETWORK_UNAVAILABLE" || error.status !== 0 || error.retryAfterSeconds || remaining <= 0)
      throw error;
    return requestJSON(path, { ...options, timeout: remaining });
  });
  return { key, signal: g.signal, sourceView, response };
}

async function loadSource(value, g, blockID = null, { focusSource = false, forceDocument = false, checkedRead } = {}) {
  const requested = validSourceURL(value);
  if (!requested) throw new Error("This source reference is unavailable.");
  const key = sourceDocumentKey(requested);
  const selected = ++sourceRevision;
  setSourceLoading(true);
  let pending;
  try {
    if (checkedRead?.key === key && checkedRead.signal === g.signal) {
      pending = checkedRead;
    } else {
      const sourceView = !forceDocument && matchesMountedSource(key, g) ? mountedSource.revision : "";
      if (sourceDocumentRequest?.key !== key || sourceDocumentRequest.signal !== g.signal ||
          sourceDocumentRequest.sourceView !== sourceView) {
        sourceDocumentRequest = requestSourceDocument(demoPath(requested.pathname + requested.search), g, key, sourceView);
      }
      pending = sourceDocumentRequest;
    }
    const { sourceView } = pending;
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
    const unchanged = data.document_unchanged === true && sourceView === revision;
    const stable = !openDemo && session.state.mode === "firebase" && (blocks?.length || unchanged) &&
      typeof revision === "string" && revision;
    const assets = stable && sourceAssetAvailability(images);
    // After a fresh authorized read, keep images already fetching for the same
    // source projection. Media URLs rotate even when the displayed view agrees.
    const keep = stable && matchesMountedSource(key, g) && mountedSource.revision === revision && mountedSource.assets === assets;
    if (data.document_unchanged === true && (!unchanged || !keep)) {
      // The mounted view may have changed while this request was in flight.
      if (sourceView) return loadSource(value, g, blockID, { focusSource, forceDocument: true });
      throw new Error("The stored source response is incomplete. Try again.");
    }
    let targets = mountedSource?.targets;
    if (!keep) {
      const fragment = document.createDocumentFragment();
      const figures = openDemo || session.state.mode === "firebase" ? [] : null;
      targets = stable || blockID !== null ? new Map() : null;
      if (blocks?.length)
        renderBlocks(fragment, blocks, images, null, g, targets, figures, articleHeadingOutline(blocks, 4));
      else if (data.source?.format === "json")
        fragment.append(element("pre", data.content ?? ""));
      else fragment.append(element("p", "Stored source is unavailable."));
      sourceFigureLoads?.stopWatching?.();
      $("source-review-frame").replaceChildren(fragment);
      sourceFigureLoads = figures ? startArticleFigures(figures, g) : null;
      mountedSource = stable ? {
        key, signal: g.signal, articleRevision: renderedRevision, revision, assets, targets, figures,
        imagesRefreshedAt: Date.now(),
      } : null;
      sourceImageRefresh = null;
      displayedSourceRevision = selected;
    } else if (refreshPendingFigures(mountedSource, images)) {
      displayedSourceRevision = selected;
      sourceImageRefresh = null;
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
  return previous && recentMediaURLs(previous.startedAt, startedAt)
    ? previous : { startedAt, images: refresh() };
}
async function renewMedia(g, failed, timedOut = false) {
  if (!g.current() || !currentArticle || !failed.isConnected) return;
  if (failed.dataset.replacement === "1") {
    showUnavailableImage(failed);
    return;
  }
  const stored = $("source-review-frame").contains(failed);
  const attemptedURL = failed.src;
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
        const key = sourceDocumentKey(requested);
        const source = matchesMountedSource(key, g) ? mountedSource : null;
        const read = requestSourceDocument(selectedSourceURL, g, key, source?.revision ?? "");
        const data = await read.response;
        if (!current()) return [];
        const returned = validSourceURL(data.source?.url);
        if (
          !returned ||
          returned.searchParams.get("source_revision_id") !==
            requested.searchParams.get("source_revision_id")
        )
          throw new Error("The stored source changed.");
        if (source && mountedSource === source && data.document_unchanged === true &&
            data.view_revision === source.revision) {
          const images = indexRenderableImages(data.images);
          if (sourceAssetAvailability(images) === source.assets)
            refreshPendingFigures(source, images, failed);
        }
        return data.images || [];
      }
      const figures = deferredArticleFigures;
      const order = articleDetailOrder(g, id);
      const canRefreshView = !openDemo && session.state.mode === "firebase" && Boolean(currentArticle.view_revision) &&
        order.accepted?.data?.article?.view_revision === revision && !processingArticle(currentArticle);
      const options = { signal: g.signal };
      let response = await requestArticleDetail(order, detailPath, canRefreshView
        ? { ...options, headers: { "X-Workshop-Article-Media-View": revision } } : options);
      if (!current()) return [];
      if (response.data.media_refresh !== undefined) {
        const media = response.data.media_refresh;
        const configuration = response.data.configuration;
        const images = indexRenderableImages(media?.images);
        if (canRefreshView && response.status === 200 && response.data.version === "v1" &&
            media?.article_id === id && media.view_revision === revision &&
            configuration?.id === vehicle.id && configuration.region === vehicle.region &&
            localImageURL(images.get(failed.dataset.assetId)?.url, location.origin, { authMode: session.state.mode })) {
          if (order.accepted[articleDetailSequence] > response[articleDetailSequence])
            return imageMap(order.accepted.data.article);
          // Only a full reply can supersede an in-flight article update.
          if (figures && deferredArticleFigures === figures) refreshPendingFigures(figures, images, failed);
          return media.images;
        }
        response = await requestArticleDetail(order, detailPath, options);
        if (!current() || !response.data.article) return [];
      }
      const article = response.data.article;
      if (acceptArticleDetail(order, response) === response) {
        renderArticle(article, g);
        const images = imageMap(article);
        const configuration = response.data.configuration;
        if (figures && deferredArticleFigures === figures && article.id === id && article.view_revision === revision &&
            configuration && configuration.id === vehicle.id && configuration.region === vehicle.region)
          refreshPendingFigures(figures, indexRenderableImages(images), failed);
        return images;
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
  if (!visible() || failed.dataset.replacement === "1" || failed.src !== attemptedURL ||
      timedOut && failed.complete && failed.naturalWidth) return;
  if (!current()) {
    // Media issued for the pre-publication view has a stale anchor.
    if (stored) return renewMedia(g, failed, timedOut);
    return;
  }
  if (!retryImage(failed, images)) showUnavailableImage(failed);
}
async function library(g, append = false, {
  focusOnShow = false, initialAccountCheck = null, restorePrevious = false, pageSize = 20,
} = {}) {
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
  const previous = !append && restorePrevious ? history.state?.workshopLibrary : null;
  const restoreCount = Number.isSafeInteger(previous?.visible) && previous.visible > 0 ? previous.visible : 0;
  const limit = Math.min(50, Math.max(pageSize, restoreCount));
  const more = $("library-more");
  const request = initialPage ? Promise.resolve(initialPage) : requestJSON(
    `/v1/workshop/library?limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
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
    li.dataset.libraryItemId = item.library_item_id;
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
        // Keep only the position. A return fetches the Library with current authorization.
        history.replaceState({
          ...history.state, workshopLibrary: { visible: list.children.length, selected: item.library_item_id },
        }, "");
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
  if (restoreCount) {
    while (g.current() && libraryCursor && list.children.length < restoreCount) {
      const loaded = list.children.length;
      await library(g, true, { pageSize: restoreCount - loaded });
      if (list.children.length === loaded) break;
    }
    if (!g.current()) return;
    const restored = Array.from(list.children).find(card => card.dataset.libraryItemId === previous.selected);
    const heading = restored?.children[0];
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
      heading.scrollIntoView({ behavior: "instant", block: "nearest" });
    }
  }
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
  const firstIndex = order.article_index && !trimArticleSearch($("search").value)
    ? firstIndexPageForVehicle(order.article_index, vehicle) : null;
  try {
    await selectVehicle(g, "", { quoteMode: "skip", firstIndex });
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
  if (signingIn && !session.state.popupPending) return;
  const attempt = Symbol();
  signingIn = attempt;
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
  let firstIndex, currentAttempt;
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
    currentAttempt = signingIn === attempt;
  } finally {
    if (signingIn === attempt) signingIn = false;
  }
  if (!currentAttempt || !session.state.authenticated) return;
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
export async function bootstrap(initialYears, initialAccount, {
  preservePicker = false, initialSelectors = null, testCheckout, initialDemoIndex = null, initialYearPicker = null,
  initialPurchaseConfig = null, initialReaderRequest = null,
} = {}) {
  if (testCheckout) checkoutModeReady = testCheckout.then(enabled => {
    testStripeMode = enabled;
    $("test-banner").hidden = !enabled;
  });
  invalidate();
  const params = new URLSearchParams(location.search);
  const early = openDemo || preservePicker ? null : initialSelectors;
  if (!early) initialSelectors?.abort();
  const years = preservePicker || early ? null : initialYears ?? requestInitialYears(params);
  if (openDemo) {
    const index = initialDemoIndex?.route === params.toString() ? initialDemoIndex : null;
    try {
      return await restoreRoute(years, { initialDemoIndex: index });
    } finally {
      initialDemoIndex?.abort();
    }
  }
  loadPurchaseConfiguration(initialPurchaseConfig);
  const accountCheck = checkAccount(initialAccount, preservePicker);
  if (preservePicker) {
    await Promise.all([accountCheck, operation((g) => selectVehicle(g), () => restoreRoute())]);
    return;
  }
  // The first route can restore public selectors while the account is checked.
  // Account actions wait for that same check and use the current navigation.
  if (sessionEstablished) await accountCheck;
  await Promise.all([accountCheck, restoreRoute(years, {
    initialSelectors: early, initialAccountCheck: accountCheck, initialYearPicker, initialReaderRequest,
  })]);
}
function loadPurchaseConfiguration(initial = null) {
  const configRequest = (initial ?? requestJSON("/workshop/purchase-config.json")).catch(() => null)
    .then(async (config) => {
      if (config?.checkout_mode !== "simulation") await checkoutModeReady;
      if (merchantRequest !== configRequest) return;
      merchant = config;
      merchantRequest = null;
    });
  merchant = null;
  merchantRequest = configRequest;
}
function checkAccount(initial, preserveGuestSignIn = false) {
  const accountCheck = session.bootstrap({ initial, preserveGuestSignIn }).then((library) => {
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

async function finishSavedYears(pending, confirmed) {
  const picker = pickerStates.get("year");
  const current = () => pickerStates.get("year") === picker &&
    $("year").value === String(confirmed.year);
  // Make, model, and engine changes leave this year picker in place.
  const refresh = { current };
  if (picker) picker.loading = refresh;
  try {
    const path = selectorPath("year");
    let response = await pending;
    if (!current()) return;
    response ??= await requestJSON(path);
    if (!current() || !Array.isArray(response?.items)) return;
    const includesYear = response.items.some((item) => item?.year === confirmed.year);
    populate("year", includesYear ? response.items : [...response.items, confirmed]);
    if (picker) picker.incomplete = !includesYear || response.complete !== true;
    if (includesYear) rememberSelector(path, "year", response);
  } catch {
    // The exact stored branch remains available if the broader year list fails.
  } finally {
    if (picker?.loading === refresh) picker.loading = null;
  }
}

async function restoreRoute(initialYears = null, {
  focusArticle = "", indexAnchor = "", initialSelectors = null, initialAccountCheck = null, initialDemoIndex = null,
  initialYearPicker = null, initialReaderRequest = null,
} = {}) {
  invalidate();
  show("welcome");
  const params = new URLSearchParams(location.search);
  const early = initialSelectors?.route === params.toString() ? initialSelectors : null;
  if (!early) initialSelectors?.abort();
  const readerStartup = initialReaderRequest?.route === params.toString() ? initialReaderRequest : null;
  if (!readerStartup) initialReaderRequest?.controller.abort();
  // URL state is authoritative on history, sign-in, and direct-link restores.
  // A prior vehicle must not leave usable descendants or filter another index.
  for (const name of names) {
    if (name !== "year" || !initialYearPicker) populate(name, []);
  }
  $("search").value = params.get("q") || "";
  vehicle = null;
  quote = null;
  renderPurchase();
  let retry = () => restoreRoute();
  const restore = operation(
    async (g) => {
      if (early) g.signal.addEventListener("abort", early.abort, { once: true });
      if (initialYearPicker) {
        const { snapshot, makeRead, makeSnapshots, makeSnapshotExpires, selectedMake = "", modelRead } = initialYearPicker;
        populate("year", snapshot.items);
        rememberSelector(selectorPath("year"), "year", snapshot);
        if (performance.now() < makeSnapshotExpires) {
          for (const [year, makes] of makeSnapshots) {
            rememberSelector(selectorPath("make", { year }), "make", makes, makeSnapshotExpires);
          }
        }
        if (!$("year").value) {
          stage("year");
          status("Choose your vehicle to continue.");
          return;
        }
        updateURL();
        const abortReads = () => {
          makeRead?.abort();
          modelRead?.abort();
        };
        g.signal.addEventListener("abort", abortReads, { once: true });
        try {
          await loadOptions("make", g, selectedMake, makeRead?.response, { initialIsLive: Boolean(makeRead) });
          if (g.current() && selectedMake && $("make").value === selectedMake) {
            updateURL();
            retry = retryPicker("model");
            await loadOptions("model", g, "", modelRead?.response, {
              initialIsLive: Boolean(modelRead), initialRequest: modelRead, retry,
            });
          }
        } finally {
          abortReads();
        }
        return;
      }
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
        await library(g, false, { initialAccountCheck, restorePrevious: true });
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
        let firstIndex = null;
        if (!openDemo && initialAccountCheck && !hasHierarchy && !articleID && !params.has("q") && validScope(exact)) {
          if (sessionRequest) status("Checking your account…", { busy: true });
          const result = await initialAccountCheck;
          if (!g.current()) return;
          if (session.state.authenticated && session.state.mode === "firebase")
            firstIndex = firstIndexPageForVehicle(result, vehicle);
        }
        const preferRetained = uuid(articleID) && history.state?.workshopArticleReadable === true;
        const detailPath = uuid(articleID) && !openDemo && sessionRequest && validScope(exact)
          ? articleRequestPath(articleID) : "";
        const startup = detailPath && readerStartup?.path === detailPath ? readerStartup : null;
        const earlyReader = detailPath ? startup?.controller ?? new AbortController() : null;
        let initialRetainedReader = null;
        if (earlyReader) {
          const signal = AbortSignal.any([g.signal, earlyReader.signal]);
          const response = requestArticleJSON(detailPath, {
            retainedReaderSession: true, preferShortPublicationCheck: true, signal,
            ...(startup && { fetcher: async (_path, request) => {
              request.signal.addEventListener("abort", () => earlyReader.abort(), { once: true });
              const reply = await startup.response;
              request.signal.throwIfAborted();
              if (!reply) throw new TypeError("The initial article request did not return a response.");
              return reply;
            } }),
          }).catch(error => error?.status === 429 || error?.retryAfterSeconds > 0 ? { retry: error } : null);
          // An unfamiliar link may need preparation. Give a slow probe only a
          // short window after session restoration before using that path.
          initialRetainedReader = async (onPending) => {
            if (preferRetained) return response;
            const initial = await Promise.race([response, delay(100, signal).then(() => undefined)]);
            if (initial === undefined) onPending?.(response);
            return initial ?? null;
          };
        }
        try {
          await selectVehicle(g, articleID, {
            savedLink: true, preferRetained, initialDemoIndex, initialRetainedReader,
            ...(firstIndex ? { firstIndex, quoteMode: "if-needed" } : {}), ...indexOptions,
          });
        } finally {
          earlyReader?.abort();
        }
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
          if (!initial[name] && !cachedSelector(path, desired[name])) {
            const pending = name === "year" ? requestJSON(path) : readStoredSelector(path, g.signal);
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
          if (name !== "year" && !desired[name]) retry = retryPicker(name);
          await loadOptions(name, g, desired[name], initial[name], { retry });
          if (!g.current() || !desired[name]) return;
          if (name === "year" && confirmed) yearsRefresh = finishSavedYears(fullYears, confirmed);
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
    () => retry(),
  );
  return early || readerStartup ? restore.finally(() => {
    early?.abort();
    readerStartup?.controller.abort();
  }) : restore;
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
    const next = names[index + 1];
    if (!next && select.value)
      vehicle = rows.configuration.find((item) => item.id === select.value);
    updateURL();
    if (!select.value) return;
    if (next) void retryPicker(next)();
    else operation((g) => selectVehicle(g));
  });
}
$("signin").addEventListener("click", (event) => {
  if (event?.detail > 1 && session.state.popupPending) return;
  void signIn();
});
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
$("purchase-action").addEventListener("click", (event) => {
  if (event?.detail > 1 && session.state.popupPending) return;
  void purchase();
});
$("check-order").addEventListener("click", checkPaymentStatus);
$("article-prev").addEventListener("click", () => moveArticlePage(-1));
$("article-next").addEventListener("click", () => moveArticlePage(1));
$("search").addEventListener("input", (event) => {
  const query = trimArticleSearch($("search").value);
  // Preserve the protected result when whitespace changes after dispatch.
  if (query && query === searchQuery && searchTimer === null && (searchPending || searchItems !== null)) return;
  if (pendingIndexPage?.current()) {
    navigation.clear();
    showArticleIndexStatus();
  }
  updateURL({ replace: true });
  const loadIndex = !query && !indexLoaded && access === "owned";
  if (loadIndex) {
    indexComplete = false;
    indexFailed = false;
  }
  const immediate = !event?.isComposing &&
    ["insertFromPaste", "insertFromDrop", "insertReplacementText"].includes(event?.inputType);
  scheduleArticleSearch({ immediate });
  if (loadIndex) void operation((g) => loadArticles(g), () => restoreRoute());
});
$("search").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.isComposing || searchTimer === null) return;
  event.preventDefault();
  scheduleArticleSearch({ immediate: true });
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
function rememberIndexArticleReadiness(response, g) {
  const origin = articleIndexOrigin;
  if (origin?.generation !== g || !canReuseArticleIndex(origin) || !g.current()) return;
  const { article, configuration } = response.data;
  if (article?.id !== origin.articleID || configuration?.id !== origin.configuration.configuration_id ||
      configuration?.region !== origin.configuration.region) return;
  const preview = hasSupplierPreview(article);
  origin.readiness = response.status === 200 && readableArticle(article) &&
    (preview || !article.source_body_preview && hasRetainedArticleRevision(article)) ? {
      availability: article.availability,
      content_origin: article.content_origin,
      content_status: article.content_status,
      source_body_preview: preview || undefined,
      source_revision_id: article.source_revision_id,
      canonical_revision_id: article.canonical_revision_id,
    } : null;
}
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
    if (origin.readiness && currentArticle?.id === origin.articleID) {
      // Copy only the authorized article's index metadata.
      for (const items of [articles, searchItems]) {
        const item = items?.find((article) => article.id === origin.articleID);
        if (item) Object.assign(item, origin.readiness);
      }
    }
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
  const link = indexLink && $("articles").contains(indexLink) ? indexLink : null;
  const target = link || $("catalog-title");
  target.focus({ preventScroll: true });
  target.scrollIntoView({ behavior: "instant", block: link ? "center" : "nearest" });
  if (indexHydrating) return refreshIndex();
  stage("articles");
  showArticleIndexStatus();
}
$("back").addEventListener("click", returnToArticleIndex);
$("back-related").addEventListener("click", () => {
  const back = $("back-related");
  const id = new URLSearchParams(location.search).get("article");
  if (back.hidden || back.disabled || !canReturnToRelatedArticle(id)) return;
  back.disabled = true;
  navigation.clear();
  history.back();
});
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
  const printing = new AbortController();
  deferred.printing = printing;
  const signal = AbortSignal.any([g.signal, printing.signal]);
  const message = $("print-status");
  const waiting = ({ img }) => img.isConnected && (!img.complete || !img.naturalWidth);
  try {
    releaseArticleFigures(deferred);
    const pending = deferred.figures.filter(waiting);
    if (pending.length) {
      message.textContent = "Loading illustrations for printing…";
      message.hidden = false;
      await waitForPrintFigures(pending, g, signal);
    }
    if (!g.current() || deferred !== deferredArticleFigures || (!openDemo && !session.state.authenticated)) return;
    if (deferred.figures.some(waiting)) {
      message.textContent = "Some illustrations are still unavailable. Try printing again.";
      message.hidden = false;
      return;
    }
    message.hidden = true;
    window.print();
  } catch (error) {
    if (!signal.aborted) throw error;
  } finally {
    printing.abort();
    deferred.printing = null;
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
  lifecycleCheck = preservePicker && !validScope(scope())
    ? checkAccount(undefined, true)
    : bootstrap(undefined, undefined, { preservePicker });
  try {
    await lifecycleCheck;
  } finally {
    lifecycleCheck = null;
  }
}
async function handleReaderCheckError(error, g, keepReadable = false) {
  if (!g.current()) return;
  const denied = [401, 403, 410].includes(error.status);
  if (keepReadable && !denied && error.status !== 404 && readableArticle(currentArticle)) {
    showArticleReadStatus(currentArticle.id, currentArticle, true);
    return;
  }
  invalidate();
  if (denied) {
    await operation(async () => { throw error; }, () => restoreRoute());
  } else {
    await recheck();
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
  const pinned = sourceURL && $("article-reference").open ? validSourceURL(sourceURL) : null;
  if (sourceURL && !pinned) resetSourceReview({ keepControls: true });
  const pin = pinned?.searchParams.get("source_revision_id");
  const stagedPin = validSourceURL(opened.original_source_review?.url)?.searchParams.get("source_revision_id");
  const checkedSourceRevision = sourceRevision;
  const order = articleDetailOrder(g, opened.id);
  const { signal } = g;
  const sourceFrame = $("source-review-frame");
  const backToArticle = $("back-to-article");
  const layout = pinned
    ? [reader, ...[sourceFrame, backToArticle].filter((node) => !node.hidden)]
    : [reader];
  const releaseLayout = () => {
    for (const node of layout) delete node.dataset.rechecking;
  };
  signal.addEventListener("abort", releaseLayout, { once: true });
  // Each view stays hidden until its own read verifies current access.
  for (const node of layout) node.dataset.rechecking = "";
  reader.hidden = true;
  document.body.dataset.printable = "false";
  if (pinned) {
    sourceFrame.hidden = true;
    backToArticle.hidden = true;
    setSourceLoading(true);
    $("source-review-meta").textContent = "Checking the stored source…";
  }
  try {
    const articleRead = Promise.all([
      session.matchesCurrentSession({ signal }),
      requestArticleDetail(order, articleRequestPath(opened.id), { signal, preferShortPublicationCheck: true }),
    ]);
    const sourceKey = pinned && sourceDocumentKey(pinned);
    const sourceRead = pinned && requestSourceDocument(pinned.pathname + pinned.search, g, sourceKey,
      matchesMountedSource(sourceKey, g) ? mountedSource.revision : "");
    const sourceFailure = sourceRead?.response.then(() => null, (error) => error);
    const [sameSession, detail] = await articleRead;
    if (!g.current()) return;
    const checked = acceptArticleDetail(order, detail);
    const article = checked?.data?.article;
    if (!sameSession || detail.status !== 200 || !scopeMatches(detail.data?.configuration) ||
        article?.id !== opened.id || !readableArticle(article)) {
      invalidate();
      await recheck();
      return;
    }
    vehicle = detail.data.configuration;
    renderPurchase();
    delete reader.dataset.rechecking;
    show("reader");
    renderArticle(article, g);
    rememberIndexArticleReadiness(checked, g);
    if (!processingArticle(article) && (articleViewRevision(opened) !== articleViewRevision(article) ||
        opened.processing?.state !== article.processing?.state))
      showArticleReadStatus(opened.id, article);
    restoreFocus();
    if (processingArticle(article) && !order.loading) {
      // A background tab can exhaust the first read's budget.
      void loadArticle(opened.id, g, { verifiedDetail: checked })
        .catch((error) => handleReaderCheckError(error, g, true));
    }
    if (!sourceRead) return;
    let error = await sourceFailure;
    if (!g.current()) return;
    if ([401, 403, 410].includes(error?.status)) throw error;
    if (sourceRevision !== checkedSourceRevision) return;
    if (!error) {
      try {
        await loadSource(pinned.href, g, null, { checkedRead: sourceRead });
      } catch (failure) {
        error = failure;
      }
    }
    if (!g.current()) return;
    if ([401, 403, 410].includes(error?.status)) throw error;
    if (error) {
      resetSourceReview();
      renderArticle(currentArticle, g);
      const stagedUnavailable = pin === stagedPin && error?.status === 404 && error.code === "CATALOG_NOT_FOUND";
      if (!stagedUnavailable && !$("source-review").hidden)
        $("source-review-meta").textContent = "The stored source could not be checked. Load it again to retry.";
    }
    restoreFocus();
  } catch (error) {
    await handleReaderCheckError(error, g);
  } finally {
    signal.removeEventListener("abort", releaseLayout);
    if (g.current()) releaseLayout();
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
      sourceDocumentRequest || document.body.dataset.busy === "true") {
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
