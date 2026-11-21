import {
  articlePresentation,
  configurationLabel,
  filterArticles,
  localImageURL,
  readCollection,
  requestJSON,
  requestArticleJSON,
  sourceReferenceURL,
} from "./catalog.mjs";
import { loadingProgress } from "./progress.mjs";
import { createSession } from "./auth.mjs";
import {
  createCheckout,
  validQuote,
  validScope,
  validLibrary,
  purchaseConfiguration,
  pollOrder,
  uuid,
} from "./commerce.mjs";
import {
  NavigationGeneration,
  readArticle,
  readableArticle,
  processingArticle,
} from "./article-read.mjs";

const $ = (id) => document.getElementById(id);
const openDemo = document.documentElement.dataset.workshopMode === 'open-demo';
if (openDemo) {
  for (const id of ['signin', 'signout', 'my-vehicles']) $(id).hidden = true;
  $('account-status').hidden = true;
  document.querySelector('.wordmark').href = '/workshop/?demo=1';
}
const demoPath = (path) => {
  if (!openDemo) return path;
  const url = new URL(path, location.origin);
  url.searchParams.set('demo', '1');
  return url.pathname + url.search;
};
const names = ["year", "make", "model", "configuration"];
const rows = Object.fromEntries(names.map((name) => [name, []]));
const navigation = new NavigationGeneration();
const searchNavigation = new NavigationGeneration();
const checkout = createCheckout({
  expectedMode: $('test-banner').hidden ? undefined : 'stripe_test',
});
let vehicle = null,
  articles = [],
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
  sourceImageRefresh = null,
  viewGeneration = null,
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
  { error = false, busy = false, retry = null, complete = false, cancelable = busy } = {},
) {
  $("activity-text").textContent = text;
  $("activity").dataset.tone = error ? "error" : busy ? "loading" : "ready";
  $("critical-error").textContent = error ? text : "";
  if (complete) $("completion-status").textContent = text;
  $("cancel").hidden = !cancelable;
  $("retry").hidden = !retry;
  retryAction = retry;
  $("loading-progress").hidden = !busy;
  document.body.dataset.busy = String(busy);
}
function stage(key) {
  const p = loadingProgress(key);
  $("loading-progress-stage").textContent =
    `Step ${p.step} of ${p.total} · ${p.label}`;
  $("loading-progress-bar").removeAttribute("value");
}
function show(id) {
  if (id !== "reader") document.title = "AutoData — The workshop reference";
  for (const section of ["welcome", "catalog", "reader", "library"])
    $(section).hidden = section !== id;
}
function clearProtected() {
  document.title = "AutoData — The workshop reference";
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
  indexLoaded = false;
  indexComplete = false;
  indexHydrating = false;
  indexFailed = false;
  resetReaderContent();
  for (const id of ["articles", "reference-data"])
    $(id).replaceChildren();
  $("article-title").textContent = "";
  $("catalog-count").textContent = "";
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
function resetSourceReview() {
  sourceImageRefresh = null;
  sourceURL = "";
  ++sourceRevision;
  displayedSourceRevision = sourceRevision;
  $("source-review").hidden = true;
  $("source-review-load").disabled = false;
  $("source-review-frame").replaceChildren();
  $("source-review-frame").hidden = true;
  $("source-review-link").removeAttribute("href");
  $("source-review-meta").textContent = "";
}
function resetReaderContent() {
  currentArticle = null;
  renderedRevision = "";
  articleImageRefresh = null;
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
  document.body.dataset.printable = "false";
}
function clearUnavailableArticle() {
  resetReaderContent();
  $("article-title").textContent = "Article unavailable";
  document.title = "AutoData — The workshop reference";
}
function invalidate() {
  navigation.clear();
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
  if (currentOrder) p.set("order", currentOrder);
  const url = `${location.pathname}${p.size ? `?${p}` : ""}`;
  if (url !== location.pathname + location.search)
    history[replace ? "replaceState" : "pushState"](null, "", url);
}
function rememberOrderRoute(id) {
  const params = new URLSearchParams(location.search);
  params.set("order", id);
  history.replaceState(null, "", `${location.pathname}?${params}`);
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
  rows[name] =
    name === "year" ? [...items].sort((a, b) => b.year - a.year) : items;
  $(name).replaceChildren(
    new Option(
      `Choose ${name === "configuration" ? "engine / trim" : name}`,
      "",
    ),
    ...rows[name].map(
      (item) =>
        new Option(
          name === "year"
            ? item.year
            : name === "configuration"
              ? configurationLabel(item)
              : item.name,
          String(item.id ?? item.year),
        ),
    ),
  );
  $(name).disabled = !items.length;
  if (desired) $(name).value = desired;
}
function selectorPath(name, selection) {
  const year = encodeURIComponent(selection?.year ?? $("year").value),
    make = encodeURIComponent(selection?.make ?? $("make").value),
    model = encodeURIComponent(selection?.model ?? $("model").value);
  return {
    year: "/v1/catalog/years",
    make: `/v1/catalog/years/${year}/makes?region=US`,
    model: `/v1/catalog/years/${year}/makes/${make}/models?region=US`,
    configuration: `/v1/catalog/years/${year}/makes/${make}/models/${model}/configurations?region=US`,
  }[name];
}
async function loadOptions(name, g, desired = "", initial = null) {
  status(`Loading ${name} choices…`, { busy: true });
  stage(name);
  $(name).disabled = true;
  const result = await readCollection(
    async () => {
      if (initial) {
        const response = await initial;
        initial = null;
        g.signal.throwIfAborted();
        if (response && (!desired || Array.isArray(response.items) &&
            response.items.some((item) => String(item.id ?? item.year) === desired))) return response;
        // A speculative response can precede the parent’s hydration.
      }
      return requestJSON(selectorPath(name), { signal: g.signal });
    },
    {
      signal: g.signal,
      desired,
      onUpdate(data) {
        if (g.current()) populate(name, data.items, desired);
      },
    },
  );
  if (!g.current()) return;
  const selected = desired && result.items.some(
    (item) => String(item.id ?? item.year) === desired,
  );
  if (!selected && (result.timedOut || result.complete === false))
    throw new Error(
      result.items.length
        ? "Some choices loaded, but the source catalog could not finish loading. Choose an available option or try again."
        : "The source catalog could not finish loading these choices. Try again.",
    );
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
  const priced = validQuote(quote, scope());
  const quotedLabel = priced ? `${quote.configuration_label} / ${quote.region}` : "";
  $("purchase").hidden = !validScope(scope());
  $("purchase-selection").textContent =
    vehicle?.orderLabel || quotedLabel ||
    [
      vehicle?.year,
      vehicle?.make,
      vehicle?.model,
      (vehicle?.engine || vehicle?.trim) && configurationLabel(vehicle),
      vehicle?.region,
    ]
      .filter(Boolean)
      .join(" / ");
  if (openDemo) {
    $("purchase").hidden = true;
    $("purchase-terms").hidden = true;
    return;
  }
  const configured = purchaseConfigured();
  $("purchase-price").textContent = priced
    ? "$20 USD · one-time"
    : "Price is currently unavailable.";
  $("purchase-terms").hidden = !configured;
  $("purchase-message").textContent =
    access === "revoked"
      ? "Access revoked. Contact the published support address."
      : access === "owned"
        ? "Owned. Open your articles without another purchase."
        : access === "pending" && session.state.authenticated
          ? "Payment received. Article access is still being checked. Use Check payment status; do not pay again."
          : confirming && session.state.authenticated
            ? "Payment confirmation is pending. Use Check payment status; do not pay again."
            : merchantRequest
              ? "Checking purchase availability…"
              : !configured
                ? "Purchasing is currently unavailable. You can keep browsing."
                : !session.state.authenticated
                  ? "Sign in to check access and purchase for your account."
                  : access === "missing"
                    ? "One purchase for this exact configuration and region. No renewal is required, subject to published terms and source availability."
                    : "Checking access. Try again if the service is unavailable.";
  $("purchase-action").textContent = !session.state.authenticated
    ? "Sign in with Google"
    : access === "owned"
      ? "Open articles"
      : access === "pending"
        ? "Payment received"
        : confirming
          ? "Payment pending"
          : "Buy for $20 USD";
  $("purchase-action").disabled = !session.state.authenticated
    ? !session.state.ready
    : access === "owned"
      ? false
      : !(access === "missing" && !confirming && priced && configured);
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
function purchaseConfigured() {
  return purchaseConfiguration(merchant, quote, {
    testCheckout: !$("test-banner").hidden,
    origin: globalThis.location?.origin,
  });
}
async function selectVehicle(g, articleID = "", { quoteMode = "eager", savedLink = false, reuseQuote = false } = {}) {
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
  const savedQuery = authorizedLink && !articleID ? $("search").value.trim() : "";
  const loadQuote = async () => {
    if (openDemo) return;
    if (merchantRequest) await merchantRequest;
    if (!g.current()) return;
    if (merchant?.enabled !== true) {
      renderPurchase();
      return;
    }
    try {
      const q = await requestJSON(
        `/v1/workshop/quote?configuration_id=${selected.configuration_id}&region=${selected.region}`,
        { signal: g.signal },
      );
      if (!g.current()) return;
      quote = validQuote(q, selected) ? q : null;
      renderPurchase();
      if (access === "owned") {
        const label = $("purchase-selection").textContent;
        $("vehicle-caption").textContent = label;
        $("reader-vehicle").textContent = label;
      }
    } catch {
      // The quote is optional for owned articles. Its absence keeps Buy disabled.
      if (g.current()) renderPurchase();
    }
  };
  const quoteRequest = !retainedQuote && quoteMode === "eager" && !directArticle && !savedQuery ? loadQuote() : null;
  if (!openDemo && !session.state.authenticated) {
    if (!retainedQuote && quoteMode !== "skip") await (quoteRequest ?? loadQuote());
    if (!g.current()) return;
    show("welcome");
    status("Sign in to check access to your selected vehicle.");
    return;
  }
  try {
    if (directArticle && await loadArticle(articleID, g, { savedLink: true })) return;
    if (savedQuery && await loadSavedSearch(g, savedQuery)) return;
    if (!g.current()) return;
    await loadArticles(g, articleID, { includePurchaseQuote: Boolean(retainedQuote) });
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
async function loadSavedSearch(g, query) {
  $("completion-status").textContent = "";
  stage("articles");
  status("Searching your articles…", { busy: true });
  const result = await requestJSON(articleRequestPath(undefined, "", { q: query }), { signal: g.signal })
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
  if (searchComplete) status("Article search ready.", { complete: true });
  else await loadArticles(g);
  return true;
}

async function loadArticles(g, articleID = "", { focusOnShow = false, includePurchaseQuote = false } = {}) {
  if (!g.current()) return;
  $("completion-status").textContent = "";
  stage("articles");
  status("Opening your article index…", { busy: true });
  await readCollection(
    () => requestJSON(articleRequestPath(), {
      signal: g.signal,
      headers: includePurchaseQuote ? { Prefer: "workshop-purchase-quote" } : undefined,
    }),
    {
      signal: g.signal,
      desired: articleID,
      onUpdate(result) {
        if (!g.current()) return;
        if (result.configuration?.id === vehicle.id &&
            result.configuration.region === vehicle.region)
          vehicle = result.configuration;
        const indexChanged = result.items.length !== articles.length ||
          result.items.some((item, index) => !sameArticleDescriptor(item, articles[index]));
        const completenessChanged = indexComplete !== (result.complete === true);
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
        const query = $("search").value.trim();
        if (query && (searchQuery !== query ||
          (!searchPending && searchItems === null && !searchError) ||
          indexChanged ||
          completenessChanged)) {
          if (indexChanged && searchQuery === query && searchItems)
            searchItems = searchHitsOnCurrentIndex(searchItems);
          scheduleArticleSearch({ fromIndex: true });
        }
        else renderArticles();
        if (focusOnShow) {
          focusOnShow = false;
          $("catalog-title").focus();
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
    showArticleIndexStatus(articleID);
  }
}

function showArticleIndexStatus(articleID = "") {
  if (indexComplete) {
    const ready = !indexLoaded && searchItems ? "Article search ready." :
      articles.length ? "Article index ready." : "Article index ready. No articles are currently available.";
    status(ready, { complete: true });
  } else if (indexFailed) {
    status("Your article index could not be prepared. Available articles can still be opened.", {
      complete: false,
    });
  } else {
    status("Your article index is still being prepared. Check again.", {
      complete: false,
      retry: () => operation((next) => loadArticles(next, articleID)),
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

function scheduleArticleSearch({ fromIndex = false } = {}) {
  const query = $("search").value.trim();
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
    searchItems = null;
    searchComplete = false;
  }
  searchPending = Boolean(query && vehicle?.id && access === "owned");
  searchError = false;
  renderArticles();
  if (!searchPending) return;
  const generation = searchNavigation.next();
  const vehicleID = vehicle.id;
  const region = vehicle.region;
  const current = () => generation.current() && vehicle?.id === vehicleID &&
    vehicle?.region === region && $("search").value.trim() === query;
  const startSearch = () => {
    searchTimer = null;
    searchRefreshPending = false;
    void requestJSON(articleRequestPath(undefined, "", { q: query }), {
      signal: generation.signal,
    }).then((result) => {
      if (!current()) return;
      const items = Array.isArray(result.items) ? result.items : [];
      // A newer index may retire or replace results from the older search.
      searchItems = searchRefreshPending ? searchHitsOnCurrentIndex(items) : items;
      searchComplete = result.complete === true;
      if (!indexLoaded) indexComplete = searchComplete;
      searchPending = false;
      if (searchRefreshPending) scheduleArticleSearch({ fromIndex: true });
      else renderArticles();
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
    });
  };
  if (fromIndex) startSearch();
  else searchTimer = setTimeout(startSearch, 300);
}

function renderArticleLinks(items) {
  const container = $("articles");
  let list = container.firstElementChild;
  if (!list) {
    list = element("ul", undefined, "article-list");
    list.setAttribute("role", "list");
    container.append(list);
  }
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
        openArticle(item.id);
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
  const retained = new Set(rows);
  for (const row of [...list.children]) if (!retained.has(row)) row.remove();
  for (const [index, row] of rows.entries()) {
    const previousRow = list.children[index] || null;
    if (row !== previousRow) list.insertBefore(row, previousRow);
  }
  // Moving a focused link can blur it. A removed result returns focus to the
  // index heading instead of activating an unrelated row at the same position.
  if (focused && focused !== document.activeElement) {
    const target = list.contains(focused) ? focused : $("catalog-title");
    target.focus({ preventScroll: true });
  }
}

function renderArticles() {
  $("vehicle-caption").textContent =
    quote?.configuration_label || $("purchase-selection").textContent;
  const query = $("search").value.trim();
  const searching = Boolean(query && searchQuery === query);
  const visible = openDemo ? articles.filter((item) => item.availability === 'available') : articles;
  const results = searching ? (searchItems || []) : filterArticles(visible, query);
  const items = openDemo ? results.filter((item) => item.availability === 'available') : results;
  renderArticleLinks(items);
  const resultsComplete = searching ? searchComplete && indexComplete : indexComplete;
  const countText = searching && searchPending
    ? "Searching articles…"
    : searching && searchError
      ? "Article search is unavailable. Try again."
      : indexFailed
        ? "Article index could not be prepared."
        : !resultsComplete
          ? `${items.length} articles so far. Article index is still being prepared.`
          : openDemo
            ? `${items.length} available articles · ${articles.length} indexed`
            : `${items.length} articles`;
  // Avoid mutating the polite live region with the same pending text on every keystroke.
  if ($("catalog-count").textContent !== countText) $("catalog-count").textContent = countText;
  $("no-results").textContent = searching && searchError
    ? "Article search is unavailable. Try again."
    : searching && searchPending
      ? "Searching articles…"
      : openDemo && articles.length > 0 && visible.length === 0
        ? "No articles are readable yet for this vehicle. Choose another vehicle or check back later."
        : indexFailed
          ? "This article index could not be prepared. Check the status above."
          : !resultsComplete
            ? "This article index is still being prepared. Check again shortly."
            : query && (articles.length > 0 || !indexLoaded)
              ? "No articles match this search. Try a component name or a shorter phrase."
              : "No articles are currently available for this vehicle.";
  $("no-results").hidden = items.length > 0;
}
const assetID = (image) =>
  image?.id || image?.image_id || image?.asset_id || "";
function imageMap(article) {
  return [
    ...(article?.images || []),
    ...(article?.steps || []).flatMap((step) => step.images || []),
  ];
}
function addImage(parent, image, caption, g, alt = caption) {
  const figure = element("figure");
  const url = localImageURL(image?.url, location.origin, { authMode: session.state.mode }),
    id = assetID(image);
  if (url && id) {
    const img = element("img");
    img.dataset.assetId = id;
    img.alt = alt || image.alt || caption || "Article illustration";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => {
      if (g.current()) void renewMedia(g, img);
    });
    img.src = url;
    figure.append(img);
    if (caption) figure.append(element("figcaption", caption));
  } else
    figure.append(element("p", "Illustration unavailable.", "image-missing"));
  parent.append(figure);
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
function renderBlocks(parent, blocks, imagesByID, review, g, sourceTarget = null) {
  const isListNumber = value =>
    Number.isInteger(value) && value >= -2147483648 && value <= 2147483647;
  const find = (ref) => {
    const id = ref?.asset_id || ref?.image_id || ref?.id;
    return id && ref.status !== "unavailable"
      ? imagesByID.get(id)
      : undefined;
  };
  const addReference = (target, ref) =>
    addImage(target, find(ref), ref?.caption || ref?.alt, g, ref?.alt);
  const renderInline = (target, value, textTag) => {
    if (!value || typeof value !== "object") {
      target.textContent = String(value ?? "");
      return;
    }
    if (value.text != null) target.append(element(textTag, value.text));
    if (value.asset_id || value.image_id || value.status === "unavailable")
      addReference(target, value);
    for (const ref of value.images || []) addReference(target, ref);
    if (Array.isArray(value.blocks)) renderBlocks(target, value.blocks, imagesByID, review, g, sourceTarget);
  };
  for (const block of blocks || []) {
    if (!block || typeof block !== "object") continue;
    const locate = sourceTarget !== null && block.block_id === sourceTarget.id;
    const childIndex = locate ? parent.children.length : 0;
    const type = block.type;
    if (type === "heading" || type === "paragraph" || type === "link") {
      const tag = type === "heading"
        ? `h${Math.max(3, Math.min(6, Number(block.level) || 3))}`
        : "p";
      parent.append(element(tag, block.text ?? ""));
      for (const ref of block.images || [])
        addImage(parent, find(ref), ref?.caption, g, ref?.alt);
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
      const trackCellImages = (cell) => {
        for (const img of cell.querySelectorAll("img[data-asset-id]"))
          cellImageIDs.add(img.dataset.assetId);
      };
      if (block.label || block.caption)
        table.append(element("caption", block.label || block.caption));
      if (block.columns?.length) {
        const row = element("tr"),
          head = element("thead");
        for (const c of block.columns) {
          const th = element("th");
          th.scope = "col";
          renderInline(th, c, "span");
          trackCellImages(th);
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
          renderInline(cell, value, "span");
          trackCellImages(cell);
          row.append(cell);
        }
        body.append(row);
      }
      table.append(body);
      const wrap = element("div", undefined, "table-scroll");
      wrap.append(table);
      parent.append(wrap);
      for (const ref of block.images || []) {
        const image = find(ref);
        if (image && cellImageIDs.has(assetID(image))) continue;
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
    if (locate) sourceTarget.node = parent.children[childIndex];
    appendSource(parent, block, review, g);
  }
}
function renderContent(parent, article, g) {
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
        addImage(section, image, image.alt, g);
      for (const id of step.image_ids || []) {
        const image = images.find((i) => assetID(i) === id);
        if (image) addImage(section, image, image.alt, g);
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
  img.replaceWith(element(
    "p",
    "Illustration unavailable. Refresh this article to try again.",
    "image-missing",
  ));
}
function renderArticle(article, g) {
  if (!g.current()) return;
  const revision =
    article.view_revision ||
    `${article.content_origin || "legacy"}:${article.source_revision_id || ""}:${article.canonical_revision_id || ""}`;
  const review = article.source_review;
  const previousReview = currentArticle?.source_review;
  const reviewURL = review?.available ? review.url : "";
  const previousURL = previousReview?.available ? previousReview.url : "";
  const sourceChanged = currentArticle?.id !== article.id ||
    currentArticle?.source_revision_id !== article.source_revision_id || previousURL !== reviewURL;
  if (revision !== renderedRevision || sourceChanged) {
    const fragment = document.createDocumentFragment();
    renderContent(fragment, article, g);
    if (!g.current()) return;
    $("article-content").replaceChildren(fragment);
    articleImageRefresh = null;
    sourceImageRefresh = null;
    if (renderedRevision) {
      // A new article projection can still cite the exact source already open.
      const pinnedID = !sourceChanged && validSourceURL(reviewURL)?.searchParams.get("source_revision_id");
      const displayedID = sourceURL && validSourceURL(sourceURL)?.searchParams.get("source_revision_id");
      if (!pinnedID || (sourceURL && displayedID !== pinnedID)) resetSourceReview();
    }
    renderedRevision = revision;
  }
  currentArticle = article;
  $("article-title").textContent = article.title || "Article";
  $("article-kind").textContent =
    article.content_origin === "canonical"
      ? "Workshop article"
      : article.content_origin === "source"
        ? "Stored source"
        : "Article";
  $("reader-vehicle").textContent =
    quote?.configuration_label || $("purchase-selection").textContent;
  $("reader-engine").textContent = vehicle.region;
  const readable = readableArticle(article);
  const processing = processingArticle(article);
  const notes = [];
  if (readable && processing) {
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
  if (review?.available) {
    $("source-review-link").href = demoPath(review.url);
    $("source-review-link").target = "_blank";
    $("source-review-link").rel = "noopener noreferrer";
    if (!sourceURL) $("source-review-meta").textContent = "Stored source for this article.";
  }
  document.title = `${article.title || "Article"} | AutoData`;
}
async function loadArticle(id, g, { savedLink = false } = {}) {
  if ((!openDemo && !session.state.authenticated) || !g.current()) return;
  const sameArticle = currentArticle?.id === id;
  resetReaderContent();
  if (!sameArticle) {
    $("article-title").textContent = "Opening article…";
    document.title = "AutoData — The workshop reference";
  }
  show("reader");
  $("article-title").focus();
  stage("article");
  status("Opening article…", { busy: true });
  const handleReadError = (error) => {
    if (g.current() && error.status === 404 && error.code === "CATALOG_NOT_FOUND")
      clearUnavailableArticle();
    throw error;
  };
  const paid = !openDemo && session.state.mode !== "local";
  const selected = vehicle;
  const matchesConfiguration = (configuration) =>
    configuration?.id === selected.id && configuration?.region === selected.region;
  const detailPath = articleRequestPath(id);
  const readOptions = { signal: g.signal, preferShortPublicationCheck: true };
  const first = await (paid
    ? requestArticleJSON(articleRequestPath(id, "/prepare"), {
        ...readOptions,
        method: "POST",
        body: {},
        preferShortSourceCheck: true,
        reportBodyNetworkError: true,
        headers: { "X-CSRF-Token": session.state.csrf },
      })
    : requestArticleJSON(detailPath, readOptions)).catch(async (error) => {
        if (paid && g.current() && error.status === 0 && error.code === "NETWORK_UNAVAILABLE") {
          // Prepare may have committed before the browser lost the response.
          const recovered = await requestArticleJSON(detailPath, { ...readOptions, preferShortSourceCheck: true })
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
      return requestArticleJSON(detailPath, options);
    },
    {
      signal: g.signal,
      onUpdate(response) {
        if (!g.current()) return;
        const article = response.data.article;
        renderArticle(article, g);
        if (!processingArticle(article)) return;
        const ready = readableArticle(article)
          ? article.content_origin === "source" ? "Stored source is ready." : "Article is readable."
          : "";
        if (ready === readingStatus) return;
        readingStatus = ready;
        if (ready) status(ready, { complete: true, cancelable: true });
        else status("Opening article…", { busy: true });
      },
    },
  ).catch(handleReadError);
  if (!g.current()) return;
  const article = result.data?.article;
  const readable = readableArticle(article);
  status(
    result.timedOut
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
    { retry: result.timedOut || !readable ? () => openArticle(id) : null, complete: readable },
  );
  return true;
}
function openArticle(id) {
  updateURL({ article: id });
  operation(
    (g) => loadArticle(id, g),
    () => openArticle(id),
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
async function loadSource(value, g, blockID = null) {
  const requested = validSourceURL(value);
  if (!requested) throw new Error("This source reference is unavailable.");
  const selected = ++sourceRevision;
  $("source-review-load").disabled = true;
  try {
    const data = await requestJSON(demoPath(requested.pathname + requested.search), {
      signal: g.signal,
      headers: sourceDocumentHeaders,
    });
    if (!g.current() || selected !== sourceRevision) return;
    const returned = validSourceURL(data.source?.url);
    if (
      !returned ||
      returned.pathname !== requested.pathname ||
      returned.searchParams.get("source_revision_id") !==
        requested.searchParams.get("source_revision_id")
    )
      throw new Error("The source reference changed. Reload this article.");
    const fragment = document.createDocumentFragment();
    const sourceTarget = blockID ? { id: blockID, node: null } : null;
    if (data.document?.blocks?.length)
      renderBlocks(fragment, data.document.blocks, indexRenderableImages(data.images), null, g, sourceTarget);
    else if (data.source?.format === "json")
      fragment.append(element("pre", data.content ?? ""));
    else fragment.append(element("p", "Stored source is unavailable."));
    $("source-review-frame").replaceChildren(fragment);
    $("source-review-frame").hidden = false;
    sourceImageRefresh = null;
    sourceURL = demoPath(requested.href);
    displayedSourceRevision = selected;
    $("article-reference").open = true;
    $("source-review-meta").textContent = "Stored source loaded.";
    if (blockID !== null) {
      const target = sourceTarget?.node || $("source-review-title");
      target.setAttribute("tabindex", "-1");
      target.focus();
    }
  } catch (error) {
    if (g.current() && selected === sourceRevision) throw error;
  } finally {
    if (g.current() && selected === sourceRevision)
      $("source-review-load").disabled = false;
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
  const visible = () => g.current() && failed.isConnected &&
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
      const response = await requestArticleJSON(articleRequestPath(currentArticle.id), { signal: g.signal });
      if (!current()) return [];
      renderArticle(response.data.article, g);
      return imageMap(response.data.article);
    } catch (error) {
      if (!current()) return [];
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
  // Later failures can reuse the same authorized response within this view.
  const pending = stored
    ? (sourceImageRefresh ??= refresh())
    : (articleImageRefresh ??= refresh());
  const images = await pending;
  if (!visible() || failed.dataset.replacement === "1") return;
  if (!current()) {
    // Media issued for the pre-publication view has a stale anchor.
    if (stored) return renewMedia(g, failed);
    return;
  }
  if (!retryImage(failed, images)) showUnavailableImage(failed);
}
async function library(g, append = false) {
  if (sessionRequest) {
    status("Checking your account…", { busy: true });
    await sessionRequest;
    if (!g.current()) return;
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
  const request = requestJSON(
    `/v1/workshop/library?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    { signal: g.signal },
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
    let summary = {
      paid: "Owned, ready to open",
      preparing: "Preparing articles",
      viewable: "Articles available",
      revoked: "Access revoked. Contact support.",
    }[item.access_state];
    if (item.access_state === "preparing") {
      if (item.content_error_code === "CATALOG_PREPARATION_REVIEW") {
        summary = "Article preparation needs review.";
      } else if (["CATALOG_PREPARATION_UNAVAILABLE", "CATALOG_SOURCE_UNAVAILABLE"].includes(item.content_error_code)) {
        summary = "Articles are temporarily unavailable.";
      }
    }
    li.append(heading, element("p", summary));
    if (item.access_state !== "revoked") {
      const button = element("button", "Open articles");
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
        operation((g) => selectVehicle(g, "", { quoteMode: "if-needed" }));
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
async function checkOrder(g, id, { earlyCheckoutCheck = false } = {}) {
  if (paidOrder?.id !== id) paidOrder = null;
  if (unconfirmedOrder?.id !== id) unconfirmedOrder = null;
  currentOrder = id;
  $("check-order").hidden = false;
  status("Checking payment status…", { busy: true });
  const selectOrderVehicle = (order) => {
    if (vehicle?.id !== order.configuration_id || vehicle?.region !== order.region) {
      clearProtected();
      vehicle = { id: order.configuration_id, region: order.region };
      quote = null;
    }
    if (typeof order.configuration_label === "string" && order.configuration_label.trim()) {
      const orderLabel = `${order.configuration_label} / ${order.region}`;
      if (vehicle.orderLabel !== orderLabel) vehicle = { ...vehicle, orderLabel };
    }
  };
  const rememberUnconfirmed = (order) => {
    const unresolved = ["creating", "open", "processing", "reconciliation_required"];
    if (unresolved.includes(order.state)) {
      unconfirmedOrder = {
        id, configuration_id: order.configuration_id, region: order.region,
      };
      selectOrderVehicle(order);
      renderPurchase();
    } else if (["paid", "expired", "canceled", "revoked"].includes(order.state) &&
      unconfirmedOrder?.id === id) {
      unconfirmedOrder = null;
    }
  };
  const result = await pollOrder(id, {
    signal: g.signal,
    earlyCheckoutCheck,
    onUpdate(order) {
      if (g.current()) {
        rememberUnconfirmed(order);
        $("purchase-message").textContent =
          order.state === "paid"
            ? "Payment received. Checking article access."
            : "Payment is being confirmed. Do not pay again.";
      }
    },
  }).catch((error) => {
    if (g.current() && error.status === 404) {
      if (paidOrder?.id === id) {
        clearProtected();
        access = "pending";
        renderPurchase();
        show("welcome");
        status("Payment was received, but order status is unavailable. Check payment status again or contact support; do not pay again.", {
          error: true,
        });
        return null;
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
  if (result.state) rememberUnconfirmed(result);
  if (["expired", "canceled", "revoked"].includes(result.state)) {
    currentOrder = "";
    paidOrder = null;
    $("check-order").hidden = true;
    clearOrderRoute(id);
  }
  if (result.state === "paid") {
    paidOrder = { id, configuration_id: result.configuration_id, region: result.region };
    selectOrderVehicle(result);
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
    if (!g.current()) return;
    currentOrder = "";
    paidOrder = null;
    $("check-order").hidden = true;
    clearOrderRoute(id, true);
  } else if (["expired", "canceled"].includes(result.state)) {
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
  } else
    status(
      "Payment confirmation is still pending. Check payment status manually.",
      { retry: () => operation((g) => checkOrder(g, id)) },
    );
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
      const result = await checkout.start(scope(), session.state.csrf, {
        signal: g.signal,
      });
      if (!g.current()) return;
      if (result.state === "checkout") location.assign(result.checkout_url);
      else if (result.state === "owned") await loadArticles(g);
      else {
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
  const route = location.search;
  try {
    await session.signIn();
  } finally {
    signingIn = false;
  }
  if (!session.state.authenticated) return;
  if (location.search === route) {
    const params = new URLSearchParams(route);
    const selected = scope();
    if (!params.has("order") && !params.has("view") && !params.has("article") &&
        validScope(selected) && selected.configuration_id === params.get("configuration") &&
        selected.region === params.get("region") &&
        names.every((name) => $(name).value === (params.get(name) || ""))) {
      // Public selector choices remain valid for the same displayed route.
      // Check paid access again with the newly confirmed session cookie.
      invalidate();
      await operation((g) => selectVehicle(g, "", { reuseQuote: true }), () => restoreRoute());
      return;
    }
  }
  await restoreRoute();
}
async function bootstrap() {
  invalidate();
  const params = new URLSearchParams(location.search);
  const years = !params.has("year") && !params.has("configuration") &&
    !params.has("order") && params.get("view") !== "library"
    ? requestJSON("/v1/catalog/years").catch(() => null)
    : null;
  if (openDemo) return restoreRoute(years);
  const configRequest = requestJSON("/workshop/purchase-config.json")
    .catch(() => null)
    .then((config) => {
      if (merchantRequest !== configRequest) return;
      merchant = config;
      merchantRequest = null;
    });
  merchant = null;
  merchantRequest = configRequest;
  const accountCheck = session.bootstrap().then(() => {
    if (sessionRequest !== accountCheck) return;
    sessionRequest = null;
    sessionEstablished = true;
  });
  sessionRequest = accountCheck;
  // The first route can restore public selectors while the account is checked.
  // Account actions wait for that same check and use the current navigation.
  if (sessionEstablished) await accountCheck;
  await Promise.all([accountCheck, restoreRoute(years)]);
}
async function restoreRoute(initialYears = null) {
  invalidate();
  show("welcome");
  const params = new URLSearchParams(location.search);
  // URL state is authoritative on history, sign-in, and direct-link restores.
  // A prior vehicle must not leave usable descendants or filter another index.
  for (const name of names) populate(name, []);
  $("search").value = params.get("q") || "";
  vehicle = null;
  quote = null;
  renderPurchase();
  return operation(
    async (g) => {
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
          await checkOrder(g, order, { earlyCheckoutCheck });
        } else status("Sign in to check this payment.");
        return;
      }
      if (!openDemo && params.get("view") === "library") {
        await library(g);
        return;
      }
      const articleID = params.get("article") || "";
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
        await selectVehicle(g, articleID, { savedLink: true });
        return;
      }
      const desired = Object.fromEntries(names.map((name) => [name, params.get(name) || ""]));
      const initial = { year: initialYears };
      // A complete saved picker route supplies every public path. Overlap the
      // initial reads, then validate each parent before exposing its children.
      const year = Number(desired.year);
      if (validScope(exact) && exact.region === "US" && /^\d{4}$/.test(desired.year) &&
          year >= 1886 && year <= 2100 && desired.make && desired.model) {
        for (const name of names) {
          if (initial[name]) continue;
          initial[name] = requestJSON(selectorPath(name, desired), { signal: g.signal })
            .catch(() => null);
        }
      }
      for (const name of names) {
        await loadOptions(name, g, desired[name], initial[name]);
        if (!g.current() || !desired[name]) return;
      }
      const configuration = rows.configuration.find(
        (item) => item.id === $("configuration").value,
      );
      if (params.has("region") && configuration?.region !== exact.region)
        throw new Error("This saved vehicle choice is unavailable in the selected region.");
      vehicle = configuration;
      await selectVehicle(g, params.get("article") || "");
    },
    () => restoreRoute(),
  );
}
for (const [index, name] of names.entries())
  $(name).addEventListener("change", () => {
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
  history.pushState(null, "", openDemo ? "/workshop/?demo=1" : "/workshop/");
  void restoreRoute();
});
$("my-vehicles").addEventListener("click", () => {
  invalidate();
  updateURL({ library: true });
  operation(
    (g) => library(g),
    () => operation((g) => library(g)),
  );
});
$("library-more").addEventListener("click", loadMoreLibrary);
$("purchase-action").addEventListener("click", () => void purchase());
$("check-order").addEventListener("click", () => {
  if (currentOrder) operation((g) => checkOrder(g, currentOrder));
});
$("search").addEventListener("input", () => {
  updateURL({ replace: true });
  const loadFullIndex = !$("search").value.trim() && !indexLoaded && access === "owned";
  if (loadFullIndex) indexComplete = false;
  scheduleArticleSearch();
  if (loadFullIndex) void operation((g) => loadArticles(g), () => restoreRoute());
});
$("retry").addEventListener("click", () => retryAction?.());
$("cancel").addEventListener("click", () => {
  navigation.clear();
  status("Loading stopped. You can try again.", {
    retry: () => restoreRoute(),
  });
});
$("source-review-load").addEventListener("click", () => {
  const g = viewGeneration;
  if (currentArticle && g?.current())
    void loadSource(currentArticle.source_review?.url, g).catch(
      (error) => handleSourceError(error, g),
    );
});
function returnToArticleIndex() {
  navigation.clear();
  clearReader();
  updateURL();
  $("completion-status").textContent = "";
  const needsIndex = !articles.length && !indexComplete && !searchItems;
  const refreshIndex = () => operation(
    (g) => loadArticles(g, "", { focusOnShow: needsIndex }), refreshIndex,
  );
  if (needsIndex) return refreshIndex();
  show("catalog");
  renderArticles();
  $("catalog-title").focus();
  if (indexHydrating) return refreshIndex();
  stage("articles");
  showArticleIndexStatus();
}
$("back").addEventListener("click", returnToArticleIndex);
$("print").addEventListener("click", () => {
  if (readableArticle(currentArticle) && (openDemo || session.state.authenticated))
    window.print();
});
window.addEventListener("popstate", () => void restoreRoute());
window.addEventListener("pagehide", () => invalidate());
let lifecycleCheck = null;
async function recheck() {
  if (
    !sessionEstablished ||
    openDemo ||
    signingIn ||
    document.visibilityState === "hidden" ||
    lifecycleCheck
  )
    return;
  lifecycleCheck = bootstrap();
  try {
    await lifecycleCheck;
  } finally {
    lifecycleCheck = null;
  }
}
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void recheck();
});
window.addEventListener("focus", () => void recheck());
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
void bootstrap();
