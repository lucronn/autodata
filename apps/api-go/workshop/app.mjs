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
const names = ["year", "make", "model", "configuration"];
const rows = Object.fromEntries(names.map((name) => [name, []]));
const navigation = new NavigationGeneration();
const checkout = createCheckout();
let vehicle = null,
  articles = [],
  currentArticle = null,
  renderedRevision = "",
  sourceURL = "",
  sourceRevision = "",
  sourceData = null;
let quote = null,
  merchant = null,
  access = "unknown",
  libraryCursor = null,
  libraryItems = [],
  currentOrder = "",
  retryAction = null,
  renewalUsed = false,
  renewal = null,
  renewalFailures = new Set(),
  viewGeneration = null,
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
function status(
  text,
  { error = false, busy = false, retry = null, complete = false } = {},
) {
  $("activity-text").textContent = text;
  $("activity").dataset.tone = error ? "error" : busy ? "loading" : "ready";
  $("critical-error").textContent = error ? text : "";
  if (complete) $("completion-status").textContent = text;
  $("cancel").hidden = !busy;
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
  for (const section of ["welcome", "catalog", "reader", "library"])
    $(section).hidden = section !== id;
}
function clearProtected() {
  articles = [];
  currentArticle = null;
  renderedRevision = "";
  sourceData = null;
  sourceURL = "";
  sourceRevision = "";
  renewalUsed = false;
  renewal = null;
  for (const id of [
    "articles",
    "article-content",
    "source-review-frame",
    "reference-data",
    "library-items",
  ])
    $(id).replaceChildren();
  $("article-title").textContent = "";
  $("catalog-count").textContent = "";
  $("article-note").textContent = "";
  $("source-review-meta").textContent = "";
  $("source-review").hidden = true;
  $("source-review-frame").hidden = true;
  $("print").disabled = true;
  document.body.dataset.printable = "false";
  $("reader").hidden = true;
  $("catalog").hidden = true;
  $("source-review-link").removeAttribute("href");
  libraryItems = [];
  libraryCursor = null;
  access = "unknown";
}
function invalidate() {
  navigation.clear();
  clearProtected();
}
async function operation(work, retry = null) {
  const g = navigation.next();
  viewGeneration = g;
  try {
    await work(g);
  } catch (error) {
    if (!g.current()) return;
    if ([401, 403, 410].includes(error.status)) {
      clearProtected();
      show("welcome");
      if (error.status === 401) {
        session.clear();
        void session.bootstrap();
      }
    }
    if (error.code === "ENTITLEMENT_REQUIRED") {
      access = "missing";
      show("welcome");
      renderPurchase();
      status("This vehicle is available to purchase.");
    } else if (error.code === "ENTITLEMENT_REVOKED") {
      access = "revoked";
      show("welcome");
      renderPurchase();
      status("Access to this vehicle has been revoked. Contact support.", {
        error: true,
      });
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
  for (const name of names) if ($(name).value) p.set(name, $(name).value);
  if (vehicle?.id) {
    p.set("configuration", vehicle.id);
    p.set("region", vehicle.region);
  }
  if (article) p.set("article", article);
  if ($("search").value) p.set("q", $("search").value);
  if (library) p.set("view", "library");
  const url = `${location.pathname}${p.size ? `?${p}` : ""}`;
  if (url !== location.pathname + location.search)
    history[replace ? "replaceState" : "pushState"](null, "", url);
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
function selectorPath(name) {
  const year = encodeURIComponent($("year").value),
    make = encodeURIComponent($("make").value),
    model = encodeURIComponent($("model").value);
  return {
    year: "/v1/catalog/years",
    make: `/v1/catalog/years/${year}/makes?region=US`,
    model: `/v1/catalog/years/${year}/makes/${make}/models?region=US`,
    configuration: `/v1/catalog/years/${year}/makes/${make}/models/${model}/configurations?region=US`,
  }[name];
}
async function loadOptions(name, g, desired = "") {
  status(`Loading ${name} choices…`, { busy: true });
  stage(name);
  $(name).disabled = true;
  const result = await readCollection(
    () => requestJSON(selectorPath(name), { signal: g.signal }),
    {
      signal: g.signal,
      desired,
      onUpdate(data) {
        if (g.current()) populate(name, data.items, desired);
      },
    },
  );
  if (!g.current()) return;
  if (
    desired &&
    !result.items.some((item) => String(item.id ?? item.year) === desired)
  )
    throw new Error(
      "This saved vehicle choice is unavailable. Choose another vehicle.",
    );
  status(
    result.items.length
      ? "Choose your vehicle to continue."
      : "No choices are available. Try again.",
    { retry: () => restoreRoute() },
  );
}
function renderPurchase() {
  if (!$("purchase")) return;
  $("purchase").hidden = !validScope(scope());
  $("purchase-selection").textContent =
    quote?.configuration_label ||
    [
      vehicle?.year,
      vehicle?.make,
      vehicle?.model,
      configurationLabel(vehicle || {}),
      vehicle?.region,
    ]
      .filter(Boolean)
      .join(" / ");
  const priced = validQuote(quote, scope()),
    configured = purchaseConfiguration(merchant, quote);
  $("purchase-price").textContent = priced
    ? "$20 USD · one-time"
    : "Price is currently unavailable.";
  $("purchase-terms").hidden = !configured;
  $("purchase-message").textContent =
    access === "revoked"
      ? "Access revoked. Contact the published support address."
      : access === "owned"
        ? "Owned. Open your articles without another purchase."
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
      : "Buy for $20 USD";
  $("purchase-action").disabled = !session.state.authenticated
    ? !session.state.ready
    : access === "owned"
      ? false
      : !(access === "missing" && priced && configured);
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
async function selectVehicle(g, articleID = "") {
  clearProtected();
  quote = null;
  $("agreement").checked = false;
  renderPurchase();
  if (!validScope(scope())) return;
  const selected = scope();
  try {
    const q = await requestJSON(
      `/v1/workshop/quote?configuration_id=${selected.configuration_id}&region=${selected.region}`,
      { signal: g.signal },
    );
    if (!g.current()) return;
    quote = validQuote(q, selected) ? q : null;
  } catch (error) {
    if (g.signal.aborted) throw error;
  }
  if (!g.current()) return;
  renderPurchase();
  if (!session.state.authenticated) {
    show("welcome");
    status("Sign in to check access to your selected vehicle.");
    return;
  }
  await loadArticles(g, articleID);
}
async function loadArticles(g, articleID = "") {
  stage("articles");
  status("Opening your article index…", { busy: true });
  const data = await readCollection(
    () => requestJSON(articlePath(), { signal: g.signal }),
    {
      signal: g.signal,
      desired: articleID,
      onUpdate(result) {
        if (!g.current()) return;
        articles = result.items;
        access = "owned";
        renderPurchase();
        show("catalog");
        renderArticles();
      },
    },
  );
  if (!g.current()) return;
  if (articleID) {
    if (!articles.some((item) => item.id === articleID))
      throw new Error("This article is unavailable for the selected vehicle.");
    await loadArticle(articleID, g);
  } else if (data.timedOut) {
    status("Your article index is still being prepared. Check again.", {
      retry: () => operation((next) => loadArticles(next)),
    });
  } else status("Article index ready.", { complete: true });
}

function renderArticles() {
  $("vehicle-caption").textContent =
    quote?.configuration_label || $("purchase-selection").textContent;
  const items = filterArticles(articles, $("search").value);
  const list = element("ul", undefined, "article-list");
  for (const item of items) {
    const li = element("li"),
      link = element("a", item.title || "Untitled article");
    const url = new URL(location.href);
    url.searchParams.set("article", item.id);
    link.href = url.pathname + url.search;
    link.addEventListener("click", (event) => {
      if (
        event.button ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      event.preventDefault();
      openArticle(item.id);
    });
    li.append(link);
    list.append(li);
  }
  $("articles").replaceChildren(list);
  $("catalog-count").textContent = `${items.length} articles`;
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
function addImage(parent, image, caption, g) {
  const figure = element("figure");
  const url = localImageURL(image?.url, location.origin),
    id = assetID(image);
  if (url && id) {
    const img = element("img");
    img.dataset.assetId = id;
    img.src = url;
    img.alt = caption || image.alt || "Article illustration";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => {
      if (g.current()) void renewMedia(g, img);
    });
    figure.append(img);
    if (caption) figure.append(element("figcaption", caption));
  } else
    figure.append(element("p", "Illustration unavailable.", "image-missing"));
  parent.append(figure);
}
function appendSource(parent, block, review, g) {
  const href = sourceReferenceURL(review, block);
  if (!href) return;
  const link = element("a", "Source ↗", "source-reference");
  link.href = "#source-review";
  link.addEventListener("click", (event) => {
    event.preventDefault();
    if (g.current())
      void loadSource(href, g).catch((error) => handleSourceError(error, g));
  });
  parent.append(link);
}
function renderBlocks(parent, blocks, images, review, g) {
  const find = (ref) =>
    images.find((image) =>
      [image.id, image.image_id, image.asset_id].includes(
        ref?.asset_id || ref?.image_id,
      ),
    );
  for (const block of blocks || []) {
    if (!block || typeof block !== "object") continue;
    const type = block.type;
    if (type === "heading")
      parent.append(
        element(
          `h${Math.max(3, Math.min(6, Number(block.level) || 3))}`,
          block.text ?? "",
        ),
      );
    else if (type === "paragraph" || type === "link")
      parent.append(element("p", block.text ?? ""));
    else if (type === "callout") {
      const aside = element("aside", undefined, "article-callout");
      aside.append(
        element("strong", block.label ?? "Note"),
        element("span", block.text ?? ""),
      );
      parent.append(aside);
    } else if (type === "image")
      addImage(parent, find(block), block.alt || block.caption, g);
    else if (type === "step") {
      const section = element("section", undefined, "procedure-step");
      if (Number.isInteger(block.number))
        section.append(element("span", `${block.number}.`, "step-number"));
      if (block.text) section.append(element("p", block.text));
      if (block.action) section.append(element("h3", block.action));
      for (const text of block.instructions || [])
        section.append(element("p", text));
      for (const ref of block.images || [])
        addImage(section, find(ref), ref.alt, g);
      parent.append(section);
    } else if (type === "ordered_list" || type === "unordered_list") {
      const list = element(type === "ordered_list" ? "ol" : "ul");
      for (const item of block.items || []) {
        const li = element("li");
        if (typeof item === "object") {
          li.append(element("p", item.text ?? ""));
          for (const ref of item.images || [])
            addImage(li, find(ref), ref.alt, g);
        } else li.textContent = String(item ?? "");
        list.append(li);
      }
      parent.append(list);
    } else if (type === "table") {
      const table = element("table", undefined, "article-table");
      if (block.label || block.caption)
        table.append(element("caption", block.label || block.caption));
      if (block.columns?.length) {
        const row = element("tr"),
          head = element("thead");
        for (const c of block.columns) {
          const th = element("th", typeof c === "object" ? (c.text ?? "") : c);
          th.scope = "col";
          row.append(th);
        }
        head.append(row);
        table.append(head);
      }
      const body = element("tbody");
      for (const values of block.rows || []) {
        const row = element("tr");
        for (const v of values || []) {
          const cell = element("td");
          if (v !== null && typeof v === "object") {
            cell.append(element("span", v.text ?? ""));
            for (const ref of v.images || [])
              addImage(cell, find(ref), ref.alt, g);
          } else cell.textContent = String(v ?? "");
          row.append(cell);
        }
        body.append(row);
      }
      table.append(body);
      const wrap = element("div", undefined, "table-scroll");
      wrap.append(table);
      parent.append(wrap);
    } else if (type === "break") parent.append(element("hr"));
    else
      parent.append(
        element(
          "aside",
          block.text ??
            block.unavailable_reason ??
            "This source block needs review.",
          "article-callout",
        ),
      );
    appendSource(parent, block, review, g);
  }
}
function renderContent(parent, article, g) {
  const presentation = articlePresentation(article),
    images = imageMap(article);
  if (presentation.documentBlocks.length)
    renderBlocks(
      parent,
      presentation.documentBlocks,
      images,
      article.source_review,
      g,
    );
  else if (presentation.steps.length) {
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
      } else renderBlocks(parent, [b], images, null, g);
    }
  else parent.append(element("p", "No readable content is available yet."));
}
function reconcileImages(parent, images, g) {
  for (const img of parent.querySelectorAll("img[data-asset-id]")) {
    const found = images.find(
      (image) => assetID(image) === img.dataset.assetId,
    );
    const url = localImageURL(found?.url, location.origin);
    if (url && img.src !== url && g.current()) {
      img.dataset.replacement = "1";
      img.src = url;
    }
  }
}
function renderArticle(article, g) {
  if (!g.current()) return;
  const revision =
    article.view_revision ||
    `${article.content_origin || "legacy"}:${article.source_revision_id || ""}:${article.canonical_revision_id || ""}`;
  if (revision !== renderedRevision) {
    const fragment = document.createDocumentFragment();
    renderContent(fragment, article, g);
    if (!g.current()) return;
    $("article-content").replaceChildren(fragment);
    renderedRevision = revision;
    renewalUsed = false;
    sourceData = null;
    $("source-review-frame").replaceChildren();
    $("source-review-frame").hidden = true;
  } else reconcileImages($("article-content"), imageMap(article), g);
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
  $("article-note").hidden = !processingArticle(article);
  $("article-note").textContent = processingArticle(article)
    ? "Preparing articles. Available source remains readable."
    : "";
  $("print").disabled = !readableArticle(article);
  document.body.dataset.printable = String(readableArticle(article));
  $("article-reference").hidden = false;
  $("source-review").hidden = !article.source_review?.available;
  const review = article.source_review;
  if (review?.available) {
    $("source-review-link").href = review.url;
    $("source-review-link").target = "_blank";
    $("source-review-link").rel = "noopener noreferrer";
    $("source-review-meta").textContent = "Stored source for this article.";
  }
  document.title = `${article.title || "Article"} | AutoData`;
}
async function loadArticle(id, g) {
  if (!session.state.authenticated) return;
  show("reader");
  $("print").disabled = true;
  $("article-content").replaceChildren();
  renderedRevision = "";
  sourceURL = "";
  renewalUsed = false;
  stage("article");
  status("Opening article…", { busy: true });
  const first = await requestArticleJSON(`${articlePath(id)}/prepare`, {
    method: "POST",
    body: {},
    headers: { "X-CSRF-Token": session.state.csrf },
    signal: g.signal,
  });
  if (!g.current()) return;
  if (first.data?.article) renderArticle(first.data.article, g);
  let initial = first;
  const result = await readArticle(
    (options) => {
      if (initial) {
        const value = initial;
        initial = null;
        return value;
      }
      return requestArticleJSON(articlePath(id), options);
    },
    {
      signal: g.signal,
      onUpdate(response) {
        if (g.current()) renderArticle(response.data.article, g);
      },
    },
  );
  if (!g.current()) return;
  const article = result.data?.article;
  status(
    result.timedOut
      ? "Preparation is taking longer. You can check again."
      : article?.processing?.state === "needs_review"
        ? "This article needs review."
        : article?.processing?.state === "failed"
          ? "Preparation could not finish. Available source can still be read."
          : readableArticle(article)
            ? "Article ready."
            : "No readable content is available.",
    { retry: () => openArticle(id), complete: readableArticle(article) },
  );
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
async function loadSource(value, g) {
  const requested = validSourceURL(value);
  if (!requested) throw new Error("This source reference is unavailable.");
  const selected = ++sourceRevision;
  sourceURL = requested.href;
  $("source-review-load").disabled = true;
  try {
    const data = await requestJSON(requested.pathname + requested.search, {
      signal: g.signal,
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
    if (data.document?.blocks?.length)
      renderBlocks(fragment, data.document.blocks, data.images || [], null, g);
    else if (data.source?.format === "json")
      fragment.append(element("pre", data.content ?? ""));
    else fragment.append(element("p", "Stored source is unavailable."));
    $("source-review-frame").replaceChildren(fragment);
    $("source-review-frame").hidden = false;
    sourceData = data;
    $("article-reference").open = true;
    $("source-review-meta").textContent = "Stored source loaded.";
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
  }
  status(error.message || "Stored source is unavailable.", { error: true });
}
async function renewMedia(g, failed) {
  if (!g.current()) return;
  if (failed.dataset.replacement === "1" || (renewalUsed && !renewal)) {
    failed.replaceWith(
      element(
        "p",
        "Illustration unavailable. Refresh this article to try again.",
        "image-missing",
      ),
    );
    return;
  }
  renewalFailures.add(failed);
  if (renewal) return renewal;
  renewalUsed = true;
  const revision = renderedRevision;
  renewal = (async () => {
    try {
      const response = await requestArticleJSON(
        articlePath(currentArticle.id),
        { signal: g.signal },
      );
      if (!g.current()) return;
      if (response.data?.article?.view_revision !== revision) {
        renderArticle(response.data.article, g);
        return;
      }
      renderArticle(response.data.article, g);
      if (sourceData && sourceURL) {
        const data = await requestJSON(sourceURL, { signal: g.signal });
        if (!g.current()) return;
        const requested = validSourceURL(sourceURL),
          returned = validSourceURL(data.source?.url);
        if (
          !returned ||
          returned.searchParams.get("source_revision_id") !==
            requested?.searchParams.get("source_revision_id")
        )
          throw new Error("The stored source changed.");
        reconcileImages($("source-review-frame"), data.images || [], g);
        sourceData = data;
      }
    } catch (error) {
      if (!g.current()) return;
      if ([401, 403, 410].includes(error.status)) {
        invalidate();
        show("welcome");
        status(error.message, { error: true });
      } else
        failed.replaceWith(
          element(
            "p",
            "Illustration unavailable. Refresh this article to try again.",
            "image-missing",
          ),
        );
    } finally {
      if (g.current()) {
        for (const image of renewalFailures) {
          if (image.isConnected && image.dataset.replacement !== "1")
            image.replaceWith(
              element(
                "p",
                "Illustration unavailable. Refresh this article to try again.",
                "image-missing",
              ),
            );
        }
        renewalFailures.clear();
        renewal = null;
      }
    }
  })();
  return renewal;
}
async function library(g, append = false) {
  clearReader();
  if (!session.state.authenticated) {
    show("welcome");
    status("Sign in to open My vehicles.");
    return;
  }
  show("library");
  status("Opening My vehicles…", { busy: true });
  const cursor = append ? libraryCursor : null;
  const data = await requestJSON(
    `/v1/workshop/library?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    { signal: g.signal },
  );
  if (!g.current()) return;
  if (!validLibrary(data))
    throw new Error("My vehicles is temporarily unavailable.");
  libraryItems = append ? [...libraryItems, ...data.items] : data.items;
  libraryCursor = data.next_cursor || null;
  $("library-items").replaceChildren();
  for (const item of libraryItems) {
    const li = element("li");
    li.append(
      element("h3", `${item.label} / ${item.region}`),
      element(
        "p",
        {
          paid: "Owned, ready to open",
          preparing: "Preparing articles",
          viewable: "Open articles",
          revoked: "Access revoked. Contact support.",
        }[item.access_state],
      ),
    );
    if (item.access_state !== "revoked") {
      const button = element("button", "Open articles");
      button.type = "button";
      button.addEventListener("click", () => {
        // A library item is an exact configuration/region route. A previous
        // browse hierarchy can belong to a different vehicle and must be cleared.
        for (const name of names) $(name).value = "";
        vehicle = {
          id: item.configuration_id,
          region: item.region,
          engine: item.label,
        };
        quote = null;
        updateURL();
        operation((g) => selectVehicle(g));
      });
      li.append(button);
    }
    $("library-items").append(li);
  }
  $("library-more").hidden = !libraryCursor;
  $("library-message").textContent = libraryItems.length
    ? ""
    : "No vehicles purchased yet. Browse to choose a vehicle.";
  status("My vehicles ready.", { complete: true });
}
function clearReader() {
  currentArticle = null;
  $("article-content").replaceChildren();
  $("source-review-frame").replaceChildren();
  $("reader").hidden = true;
  $("print").disabled = true;
  document.body.dataset.printable = "false";
}
async function checkOrder(g, id) {
  currentOrder = id;
  $("check-order").hidden = false;
  status("Checking payment status…", { busy: true });
  try {
    const result = await pollOrder(id, {
      signal: g.signal,
      onUpdate(order) {
        if (g.current())
          $("purchase-message").textContent =
            order.state === "paid"
              ? "Payment received. Checking article access."
              : "Payment is being confirmed. Do not pay again.";
      },
    });
    if (!g.current()) return;
    if (result.state === "paid") {
      vehicle = { id: result.configuration_id, region: result.region };
      await selectVehicle(g);
    } else if (["expired", "canceled"].includes(result.state)) {
      checkout.clear();
      status(
        "The previous payment attempt ended. Choose Buy again only when you are ready.",
      );
      renderPurchase();
    } else if (result.state === "revoked") {
      invalidate();
      access = "revoked";
      renderPurchase();
      status("Access revoked. Contact support.", { error: true });
    } else
      status(
        "Payment confirmation is still pending. Check payment status manually.",
        { retry: () => operation((g) => checkOrder(g, id)) },
      );
  } catch (error) {
    if (error.status === 404) checkout.clear();
    throw error;
  }
}
async function purchase() {
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
    !purchaseConfiguration(merchant, quote) ||
    access !== "missing"
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
      else await checkOrder(g, result.order_id);
    },
    () => purchase(),
  );
  renderPurchase();
}
async function signIn() {
  if (signingIn) return;
  signingIn = true;
  checkout.clear();
  try {
    await session.signIn();
  } finally {
    signingIn = false;
  }
  if (session.state.authenticated) {
    const order = new URLSearchParams(location.search).get("order");
    if (uuid(order)) operation((g) => checkOrder(g, order));
    else if (validScope(scope())) operation((g) => selectVehicle(g));
  }
}
async function bootstrap() {
  invalidate();
  await session.bootstrap();
  sessionEstablished = true;
  try {
    merchant = await requestJSON("/workshop/purchase-config.json");
  } catch {
    merchant = null;
  }
  await restoreRoute();
}
async function restoreRoute() {
  invalidate();
  show("welcome");
  const params = new URLSearchParams(location.search);
  return operation(
    async (g) => {
      const order = params.get("order");
      if (uuid(order)) {
        if (session.state.authenticated) await checkOrder(g, order);
        else status("Sign in to check this payment.");
        return;
      }
      if (params.get("view") === "library") {
        await library(g);
        return;
      }
      if (uuid(params.get("configuration")) && !params.get("year")) {
        vehicle = {
          id: params.get("configuration"),
          region: params.get("region"),
        };
        await selectVehicle(g, params.get("article") || "");
        return;
      }
      vehicle = null;
      quote = null;
      renderPurchase();
      for (const name of names) {
        const desired = params.get(name) || "";
        await loadOptions(name, g, desired);
        if (!g.current() || !desired) return;
      }
      vehicle = rows.configuration.find(
        (item) => item.id === $("configuration").value,
      );
      $("search").value = params.get("q") || "";
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
  history.pushState(null, "", "/workshop/");
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
$("library-more").addEventListener("click", () =>
  operation((g) => library(g, true)),
);
$("purchase-action").addEventListener("click", () => void purchase());
$("check-order").addEventListener("click", () => {
  if (currentOrder) operation((g) => checkOrder(g, currentOrder));
});
$("search").addEventListener("input", () => {
  updateURL({ replace: true });
  renderArticles();
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
$("back").addEventListener("click", () => {
  navigation.clear();
  clearReader();
  updateURL();
  show("catalog");
  renderArticles();
  $("catalog-title").focus({ preventScroll: true });
});
$("print").addEventListener("click", () => {
  if (readableArticle(currentArticle) && session.state.authenticated)
    window.print();
});
window.addEventListener("popstate", () => void restoreRoute());
window.addEventListener("pagehide", () => invalidate());
let lifecycleCheck = null;
async function recheck() {
  if (
    !sessionEstablished ||
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
  if (event.data === "invalidate") {
    invalidate();
    session.clear();
    void recheck();
  }
});
void bootstrap();
