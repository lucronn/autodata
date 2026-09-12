(() => {
  "use strict";

  const CHAT_ROUTES = {
    query: "/chat/queries",
    selection: (queryId) => `/chat/queries/${encodeURIComponent(queryId)}/selections`,
    events: (queryId) => `/chat/queries/${encodeURIComponent(queryId)}/events`,
    legacyJobPlan: "/job-plans",
  };
  const TERMINAL_EVENT_LIMIT = 80;
  const state = {
    loading: false,
    queryId: null,
    payload: null,
    lastEventId: null,
    eventIds: new Set(),
    eventsController: null,
    lastAssistantMessage: null,
    terminalInitialized: false,
  };

  const $ = (id) => document.getElementById(id);

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function values(value) {
    return Array.isArray(value) ? value : [];
  }

  function hasValue(value) {
    return value !== null && value !== undefined && String(value).trim() !== "";
  }

  function pick(object, keys) {
    if (!isObject(object)) return undefined;
    for (const key of keys) {
      if (hasValue(object[key])) return object[key];
    }
    return undefined;
  }

  function text(value) {
    if (value === null || value === undefined) return "";
    return String(value).trim();
  }

  function authHeaders(extra = {}) {
    let token = "local:demo:dataset_viewer";
    try {
      token = window.localStorage.getItem("autodata-auth-token") || token;
    } catch (_error) {
      // The local demo token keeps the dashboard usable when storage is blocked.
    }
    const authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    return { Authorization: authorization, ...extra };
  }

  function newIdempotencyKey(prefix) {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return `${prefix}:${window.crypto.randomUUID()}`;
    }
    return `${prefix}:${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = hasValue(value) ? String(value) : "—";
  }

  function setSystemStatus(label, stateName = "idle") {
    const element = $("system-status");
    if (!element) return;
    element.textContent = label;
    element.dataset.state = stateName;
  }

  function setResultStatus(label, stateName = "idle") {
    const element = $("result-status");
    if (!element) return;
    element.textContent = label;
    element.dataset.state = stateName;
  }

  function setWorkerStatus(label, stateName = "idle") {
    const element = $("worker-connection");
    if (!element) return;
    element.textContent = label;
    element.dataset.state = stateName;
  }

  function replaceChildren(element, children) {
    if (!element) return;
    element.replaceChildren(...children);
  }

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function appendLabelValue(parent, label, value, className = "") {
    if (!hasValue(value)) return;
    const item = element("span", className);
    item.append(element("b", "field-label", label), document.createTextNode(String(value)));
    parent.append(item);
  }

  function formatNumber(value, suffix = "") {
    if (!hasValue(value)) return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return `${text(value)}${suffix}`;
    return `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
  }

  function formatHours(value) {
    return formatNumber(value, " h");
  }

  function formatPrice(part) {
    if (!isObject(part)) return "—";
    const amount = pick(part, ["amount", "price", "unit_price"]);
    if (!hasValue(amount)) return "—";
    const currency = text(pick(part, ["currency", "currency_code"]));
    const numeric = Number(amount);
    let formatted = text(amount);
    if (Number.isFinite(numeric)) {
      try {
        formatted = numeric.toLocaleString(undefined, { style: "currency", currency: currency || "USD" });
      } catch (_error) {
        formatted = `${numeric.toLocaleString()}${currency ? ` ${currency}` : ""}`;
      }
    }
    return currency && !Number.isFinite(numeric) ? `${formatted} ${currency}` : formatted;
  }

  function formatVehicle(vehicle) {
    if (!isObject(vehicle)) return "";
    const year = pick(vehicle, ["year", "model_year"]);
    const make = pick(vehicle, ["make", "manufacturer"]);
    const model = pick(vehicle, ["model", "model_name"]);
    const details = [
      pick(vehicle, ["trim"]),
      pick(vehicle, ["body_style"]),
      pick(vehicle, ["drivetrain", "drive"]),
      hasValue(pick(vehicle, ["engine_displacement_l", "engine_l"]))
        ? `${pick(vehicle, ["engine_displacement_l", "engine_l"])}L`
        : pick(vehicle, ["engine"]),
    ].filter(hasValue);
    return [year, make, model, ...details].filter(hasValue).join(" ");
  }

  function answerFrom(payload) {
    if (isObject(payload) && isObject(payload.answer)) return payload.answer;
    return isObject(payload) ? payload : {};
  }

  function vehicleOptionsFrom(payload, answer) {
    return values(payload?.vehicle_options).length
      ? values(payload.vehicle_options)
      : values(answer?.vehicle_options);
  }

  function dataStateFrom(payload, answer) {
    return text(pick(answer, ["data_state"])) || text(pick(payload, ["data_state"]));
  }

  function answerStatusFrom(payload, answer) {
    return text(pick(answer, ["answer_status", "status"])) || text(pick(payload, ["status"]));
  }

  function revisionFrom(payload, answer) {
    return pick(answer, ["revision_id", "source_revision_id"])
      || pick(payload, ["revision_id", "source_revision_id"]);
  }

  function sourceWatermarkFrom(payload, answer) {
    return pick(answer, ["source_watermark"])
      || pick(payload, ["source_watermark"])
      || pick(payload?.source, ["source_watermark", "source_version"]);
  }

  function statusLabel(dataState, answerStatus) {
    const stateLabel = text(dataState);
    const answerLabel = text(answerStatus);
    if (stateLabel && answerLabel) return `${answerLabel} · ${stateLabel}`;
    return stateLabel || answerLabel || "Processing";
  }

  function messageText(payload) {
    if (!isObject(payload)) return "The API returned no structured response.";
    if (isObject(payload.error)) {
      const code = text(payload.error.code);
      const message = text(payload.error.message) || "The API returned an error.";
      return code ? `${code}: ${message}` : message;
    }
    const answer = answerFrom(payload);
    const options = vehicleOptionsFrom(payload, answer);
    if (options.length) return `I found ${options.length} vehicle matches. Choose one below or reply with its number.`;
    const procedure = isObject(answer.procedure) ? answer.procedure : null;
    const quote = isObject(answer.quote) ? answer.quote : (isObject(answer.labor) ? answer.labor : null);
    const title = text(pick(procedure, ["title", "name", "article_title"]));
    const hours = pick(quote, ["total_hours", "total_labor_hours"]);
    const stateLabel = dataStateFrom(payload, answer);
    const lines = [];
    if (title) lines.push(title);
    if (hasValue(hours)) lines.push(`Total labor: ${formatHours(hours)}`);
    if (stateLabel) lines.push(`Data state: ${stateLabel}`);
    if (lines.length) return lines.join(" · ");
    if (text(payload.status) === "awaiting_vehicle") return "Vehicle selection is required before retrieval can begin.";
    return "The request is processing. Usable source data will remain visible as it arrives.";
  }

  function addMessage(kind, message) {
    const log = $("chat-log");
    if (!log) return null;
    const wrapper = element("div", `message ${kind}-message`);
    wrapper.append(element("span", "message-label", kind === "user" ? "You" : "AutoData"));
    wrapper.append(element("p", "", message));
    log.append(wrapper);
    wrapper.scrollIntoView({ block: "nearest" });
    if (kind === "assistant") state.lastAssistantMessage = wrapper;
    return wrapper;
  }

  function updateAssistantMessage(payload) {
    const message = messageText(payload);
    if (!state.lastAssistantMessage) {
      addMessage("assistant", message);
      return;
    }
    const paragraph = state.lastAssistantMessage.querySelector("p");
    if (paragraph) paragraph.textContent = message;
  }

  function errorFromPayload(payload, response) {
    if (isObject(payload?.error)) return payload.error;
    if (response && !response.ok) {
      return { message: `Request returned HTTP ${response.status}` };
    }
    return null;
  }

  async function requestJSON(url, options = {}) {
    const response = await fetch(url, options);
    const bodyText = await response.text();
    let payload = {};
    if (bodyText.trim()) {
      try {
        payload = JSON.parse(bodyText);
      } catch (_error) {
        payload = { error: { message: bodyText.trim() } };
      }
    }
    return { response, payload };
  }

  function resetAnswer() {
    closeEventStream();
    state.queryId = null;
    state.payload = null;
    state.lastEventId = null;
    state.eventIds = new Set();
    state.lastAssistantMessage = null;
    setResultStatus("Waiting for a question", "idle");
    $("answer-identity").hidden = true;
    $("vehicle-options").hidden = true;
    replaceChildren($("option-list"), []);
    setText("procedure-title", "No procedure yet");
    setText("procedure-generation", "A structured procedure will appear here.");
    $("review-badge").hidden = true;
    replaceChildren($("procedure-warnings"), []);
    $("procedure-warnings").hidden = true;
    replaceChildren($("procedure-steps"), [element("li", "empty-output", "Ask a question to load source-backed procedure steps.")]);
    replaceChildren($("procedure-visuals"), []);
    $("procedure-visuals").hidden = true;
    $("procedure-evidence").hidden = true;
    replaceChildren($("procedure-evidence"), []);
    setText("total-hours", "—");
    setText("overlap-hours", "Overlap details will appear with the quote.");
    setText("quote-state", "Awaiting data");
    replaceChildren($("labor-breakdown"), []);
    setText("parts-currency", "");
    replaceChildren($("parts-list"), [element("p", "empty-output", "No parts have been returned yet.")]);
    $("quote-evidence").hidden = true;
    replaceChildren($("quote-evidence"), []);
    setText("source-state", "No source accessed");
    replaceChildren($("source-links"), [element("p", "empty-output", "Source references will appear here when returned by the API.")]);
    $("source-raw").hidden = true;
    $("source-output").textContent = "";
    $("global-warnings").hidden = true;
    replaceChildren($("global-warnings"), []);
    $("json-output").textContent = "{}";
    resetTerminal();
  }

  function resetTerminal() {
    state.eventIds = new Set();
    state.terminalInitialized = false;
    setWorkerStatus("Idle", "idle");
    setText("worker-query-id", "No query connected");
    setText("worker-event-count", "0 events");
    replaceChildren($("worker-terminal"), [element("div", "terminal-empty", "Worker progress will appear here after a request.")]);
  }

  function renderVehicleOptions(payload, answer) {
    const target = $("option-list");
    const container = $("vehicle-options");
    const options = vehicleOptionsFrom(payload, answer);
    if (!options.length) {
      container.hidden = true;
      replaceChildren(target, []);
      return;
    }
    container.hidden = false;
    const buttons = options.map((option, index) => {
      const optionNumber = Number(option.option_number || index + 1);
      const button = element("button", "option-button");
      button.type = "button";
      button.dataset.optionNumber = String(optionNumber);
      button.dataset.vehicleId = text(option.vehicle_id || option.candidate_key);
      const number = element("span", "option-number", `${optionNumber}.`);
      const copy = element("span", "option-copy");
      copy.append(element("strong", "option-title", formatVehicle(option) || text(option.vehicle_id || option.candidate_key)));
      const details = [
        pick(option, ["region"]),
        pick(option, ["vehicle_id"]),
      ].filter(hasValue).join(" · ");
      if (details) copy.append(element("small", "option-details", details));
      button.append(number, copy);
      button.addEventListener("click", () => selectVehicle(optionNumber, option));
      return button;
    });
    replaceChildren(target, buttons);
  }

  function renderIdentity(payload, answer) {
    const vehicle = isObject(answer.vehicle) ? answer.vehicle : (isObject(payload.vehicle) ? payload.vehicle : null);
    const revision = revisionFrom(payload, answer);
    const watermark = sourceWatermarkFrom(payload, answer);
    const identity = $("answer-identity");
    if (!vehicle && !hasValue(revision) && !hasValue(watermark)) {
      identity.hidden = true;
      return;
    }
    identity.hidden = false;
    setText("answer-vehicle", formatVehicle(vehicle) || text(pick(vehicle, ["vehicle_id", "candidate_key"])));
    setText("answer-revision", revision);
    setText("answer-watermark", watermark);
  }

  function warningText(warning) {
    if (typeof warning === "string") return warning;
    if (!isObject(warning)) return text(warning);
    return text(pick(warning, ["message", "detail", "reason", "code"])) || JSON.stringify(warning);
  }

  function warningList(payload, answer, procedure) {
    const result = [];
    for (const item of [...values(payload.warnings), ...values(answer.warnings), ...values(procedure?.warnings)]) {
      const value = warningText(item);
      if (value && !result.includes(value)) result.push(value);
    }
    return result;
  }

  function renderWarnings(targetId, warnings) {
    const target = $(targetId);
    if (!warnings.length) {
      target.hidden = true;
      replaceChildren(target, []);
      return;
    }
    target.hidden = false;
    replaceChildren(target, warnings.map((warning) => {
      const item = element("div", "notice");
      item.append(element("span", "notice-icon", "!"), element("span", "", warning));
      return item;
    }));
  }

  function reviewState(procedure) {
    if (!isObject(procedure)) return "";
    const stateValue = text(pick(procedure, ["review_status", "review_state", "review_label"]));
    if (stateValue) return stateValue;
    if (procedure.requires_review === true) return "UNREVIEWED";
    return "";
  }

  function renderProcedure(payload, answer) {
    const procedure = isObject(answer.procedure) ? answer.procedure : null;
    if (!procedure) {
      setText("procedure-title", "No procedure yet");
      setText("procedure-generation", "The API has not returned a procedure.");
      renderWarnings("procedure-warnings", []);
      replaceChildren($("procedure-steps"), [element("li", "empty-output", "Procedure steps are not available yet.")]);
      $("review-badge").hidden = true;
      $("procedure-visuals").hidden = true;
      $("procedure-evidence").hidden = true;
      return;
    }
    setText("procedure-title", pick(procedure, ["title", "name", "article_title"]) || "Procedure");
    const generation = pick(procedure, ["generation", "generated_by", "generator", "model"]);
    setText("procedure-generation", generation ? `Generated by ${generation}` : "Generation source was not returned by the API.");
    const review = reviewState(procedure);
    const reviewBadge = $("review-badge");
    reviewBadge.hidden = !review || text(review).toLowerCase() === "approved";
    if (!reviewBadge.hidden) reviewBadge.textContent = text(review).toUpperCase();
    renderWarnings("procedure-warnings", warningList(payload, answer, procedure));

    const steps = values(procedure.steps);
    if (!steps.length) {
      replaceChildren($("procedure-steps"), [element("li", "empty-output", "The procedure contains no steps yet.")]);
    } else {
      replaceChildren($("procedure-steps"), steps.map((step) => {
        const item = element("li", "procedure-step");
        const instruction = pick(step, ["instruction", "action", "description", "text"]);
        item.append(element("span", "step-instruction", instruction || JSON.stringify(step)));
        const meta = element("div", "step-meta");
        appendLabelValue(meta, "Operation", pick(step, ["operation_id"]));
        const sources = values(step.source_article_ids).join(", ");
        const evidence = values(step.evidence_ids).join(", ");
        appendLabelValue(meta, "Source articles", sources);
        appendLabelValue(meta, "Evidence", evidence);
        for (const safety of values(step.safety_warnings)) appendLabelValue(meta, "Safety", safety, "safety-note");
        if (meta.childElementCount) item.append(meta);
        return item;
      }));
    }
    renderVisuals(payload, answer, procedure);
    renderEvidence("procedure-evidence", values(procedure.evidence));
  }

  function visualURL(visual) {
    if (typeof visual === "string") return visual;
    return text(pick(visual, ["derived_artifact_url", "url", "source_uri", "source_url"]));
  }

  function renderVisuals(payload, answer, procedure) {
    const visuals = values(procedure.visuals).length
      ? values(procedure.visuals)
      : (values(procedure.visual_artifacts).length ? values(procedure.visual_artifacts) : values(payload.images || answer.images));
    const target = $("procedure-visuals");
    const safeVisuals = visuals.filter((visual) => /^https?:\/\//i.test(visualURL(visual)));
    if (!safeVisuals.length) {
      target.hidden = true;
      replaceChildren(target, []);
      return;
    }
    target.hidden = false;
    replaceChildren(target, safeVisuals.map((visual) => {
      const url = visualURL(visual);
      const figure = element("figure", "visual-card");
      const image = document.createElement("img");
      image.src = url;
      image.alt = text(pick(visual, ["label", "alt", "description"])) || "Procedure visual";
      image.loading = "lazy";
      const caption = element("figcaption", "", image.alt);
      figure.append(image, caption);
      return figure;
    }));
  }

  function renderEvidence(targetId, evidence) {
    const target = $(targetId);
    const labels = evidence.map((item) => typeof item === "string" ? item : text(pick(item, ["evidence_id", "id", "locator"]))).filter(Boolean);
    if (!labels.length) {
      target.hidden = true;
      replaceChildren(target, []);
      return;
    }
    target.hidden = false;
    replaceChildren(target, [element("span", "evidence-label", "Evidence"), element("span", "evidence-values", labels.join(" · "))]);
  }

  function operationLabel(operation) {
    if (typeof operation === "string") return operation;
    if (!isObject(operation)) return text(operation);
    return text(pick(operation, ["name", "title", "operation", "description", "article_title", "operation_id"])) || JSON.stringify(operation);
  }

  function renderOperationGroup(target, label, operations) {
    if (!operations.length) return;
    const group = element("div", "operation-group");
    group.append(element("span", "operation-label", label));
    const list = element("ul", "operation-list");
    for (const operation of operations) list.append(element("li", "", operationLabel(operation)));
    group.append(list);
    target.append(group);
  }

  function renderQuote(payload, answer) {
    const quote = isObject(answer.quote) ? answer.quote : (isObject(answer.labor) ? answer.labor : null);
    const legacyLabor = isObject(payload.labor) ? payload.labor : null;
    const labor = quote || legacyLabor;
    const parts = values(quote?.parts).length ? values(quote.parts) : values(payload.parts);
    const hours = pick(labor, ["total_hours", "total_labor_hours"]);
    setText("total-hours", hasValue(hours) ? formatHours(hours) : "—");
    const overlap = pick(labor, ["overlap_hours_removed", "overlap_hours"]);
    setText("overlap-hours", hasValue(overlap) ? `Overlap removed: ${formatHours(overlap)}` : "No overlap value returned.");
    const quoteState = $("quote-state");
    quoteState.textContent = labor ? "Returned" : "Awaiting data";
    const breakdown = $("labor-breakdown");
    replaceChildren(breakdown, []);
    if (labor) {
      const metrics = [
        ["Required labor", pick(labor, ["required_hours"])],
        ["Recommended labor", pick(labor, ["recommended_hours"])],
      ];
      for (const [label, value] of metrics) {
        if (!hasValue(value)) continue;
        const metric = element("div", "labor-metric");
        metric.append(element("span", "", label), element("strong", "", formatHours(value)));
        breakdown.append(metric);
      }
      renderOperationGroup(breakdown, "Required operations", values(labor.required_operations));
      renderOperationGroup(breakdown, "Recommended operations", values(labor.recommended_operations));
      renderOperationGroup(breakdown, "Shared / overlap operations", values(labor.overlap_operations));
    }
    const currencies = [...new Set(parts.map((part) => text(pick(part, ["currency", "currency_code"]))).filter(Boolean))];
    setText("parts-currency", currencies.join(" / "));
    const partsTarget = $("parts-list");
    if (!parts.length) {
      replaceChildren(partsTarget, [element("p", "empty-output", "No parts have been returned yet.")]);
    } else {
      replaceChildren(partsTarget, parts.map((part) => {
        const row = element("div", "part-row");
        const name = text(pick(part, ["name", "description", "part_name", "source_part_number", "canonical_part_id"])) || "Part";
        const copy = element("div", "part-copy");
        copy.append(element("strong", "", name));
        const number = pick(part, ["source_part_number", "part_number"]);
        if (number && text(number) !== name) copy.append(element("small", "", String(number)));
        const price = element("div", "part-price");
        price.append(element("strong", "", formatPrice(part)));
        const pricedAt = pick(part, ["priced_at", "price_date"]);
        if (pricedAt) price.append(element("small", "", `Priced ${pricedAt}`));
        const freshness = text(pick(part, ["freshness", "price_freshness"]));
        if (freshness.toLowerCase() === "stale") price.append(element("span", "stale-badge", "STALE PRICE"));
        if (part.markup_applied === false) price.append(element("small", "no-markup", "Source price · no markup"));
        row.append(copy, price);
        return row;
      }));
    }
    renderEvidence("quote-evidence", values(quote?.evidence));
  }

  function sourceReferences(payload, answer) {
    const references = [
      ...values(answer.source_references),
      ...values(payload.source_references),
      ...values(payload.sources),
    ];
    const sourceURI = pick(payload.source, ["source_uri", "uri"])
      || pick(answer.source, ["source_uri", "uri"])
      || pick(payload, ["source_uri", "source_url"]);
    if (sourceURI) references.push({ uri: sourceURI });
    const seen = new Set();
    return references.filter((reference) => {
      const key = typeof reference === "string" ? reference : JSON.stringify(reference);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function referenceURL(reference) {
    if (typeof reference === "string") return reference;
    return text(pick(reference, ["uri", "source_uri", "url", "source_url"]));
  }

  function renderSource(payload, answer) {
    const dataState = dataStateFrom(payload, answer);
    const sourceState = $("source-state");
    sourceState.textContent = dataState || "No source state returned";
    sourceState.dataset.state = dataState || "idle";
    const links = sourceReferences(payload, answer);
    const target = $("source-links");
    if (!links.length) {
      replaceChildren(target, [element("p", "empty-output", "Source references will appear here when returned by the API.")]);
    } else {
      replaceChildren(target, links.map((reference) => {
        const url = referenceURL(reference);
        const label = typeof reference === "string" ? reference : text(pick(reference, ["label", "title", "source_snapshot_id", "source_version"])) || url;
        if (/^https?:\/\//i.test(url)) {
          const link = element("a", "source-link", label);
          link.href = url;
          link.target = "_blank";
          link.rel = "noreferrer noopener";
          return link;
        }
        return element("span", "source-link source-link-static", label || JSON.stringify(reference));
      }));
    }
    const raw = answer.source_unnormalized || payload.source_unnormalized || payload.raw_source;
    const rawTarget = $("source-raw");
    if (raw !== undefined && raw !== null) {
      rawTarget.hidden = false;
      $("source-output").textContent = JSON.stringify(raw, null, 2);
      rawTarget.querySelector("summary").textContent = dataState === "source_unnormalized"
        ? "View source_unnormalized data while normalization continues"
        : "View returned source data";
    } else {
      rawTarget.hidden = true;
      $("source-output").textContent = "";
    }
  }

  function renderGlobalWarnings(payload, answer) {
    const warnings = warningList(payload, answer, null);
    const target = $("global-warnings");
    if (!warnings.length) {
      target.hidden = true;
      replaceChildren(target, []);
      return;
    }
    target.hidden = false;
    replaceChildren(target, [element("strong", "", "Warnings")]);
    for (const warning of warnings) target.append(element("p", "", warning));
  }

  function renderWorkerStream(stream) {
    if (state.terminalInitialized) return;
    state.terminalInitialized = true;
    for (const event of values(stream)) renderWorkerEvent(event);
  }

  function renderPayload(payload, response) {
    state.payload = isObject(payload) ? payload : {};
    const answer = answerFrom(state.payload);
    const error = errorFromPayload(state.payload, response);
    if (error) {
      const message = text(error.message) || "The API returned an error.";
      setResultStatus(text(error.code) || "Request failed", "error");
      setSystemStatus("API request failed", "error");
      renderGlobalWarnings(state.payload, answer);
      $("json-output").textContent = JSON.stringify(state.payload, null, 2);
      return;
    }
    const dataState = dataStateFrom(state.payload, answer);
    const answerStatus = answerStatusFrom(state.payload, answer);
    setResultStatus(statusLabel(dataState, answerStatus), dataState === "unavailable" ? "error" : "ready");
    setSystemStatus(dataState === "normalized" ? "Cache served" : "Source-backed work active", "ready");
    renderVehicleOptions(state.payload, answer);
    renderIdentity(state.payload, answer);
    renderProcedure(state.payload, answer);
    renderQuote(state.payload, answer);
    renderSource(state.payload, answer);
    renderGlobalWarnings(state.payload, answer);
    renderWorkerStream(answer.worker_stream || state.payload.worker_stream);
    $("json-output").textContent = JSON.stringify(state.payload, null, 2);
  }

  function mergeObject(previous, update) {
    if (!isObject(previous)) return isObject(update) ? { ...update } : previous;
    if (!isObject(update)) return previous;
    const merged = { ...previous };
    for (const [key, value] of Object.entries(update)) {
      if (value === null || value === undefined) continue;
      if (isObject(value) && isObject(merged[key])) merged[key] = mergeObject(merged[key], value);
      else if (Array.isArray(value) && value.length === 0 && ["procedure", "quote"].includes(key)) continue;
      else merged[key] = value;
    }
    return merged;
  }

  function mergeAnswerUpdate(event) {
    const body = isObject(event.payload) ? event.payload : {};
    let update = isObject(body.answer) ? body.answer : (isObject(event.answer) ? event.answer : null);
    if (!update && text(event.event_type).includes("answer.updated")) update = body;
    if (!update || !state.payload) return;
    const current = answerFrom(state.payload);
    const merged = mergeObject(current, update);
    state.payload = { ...state.payload, answer: merged };
    if (hasValue(event.status) && event.status !== "processing") state.payload.status = event.status;
  }

  function eventMessage(event) {
    const body = isObject(event.payload) ? event.payload : {};
    return text(event.message) || text(body.message) || text(body.detail) || text(event.event_type) || "Worker event";
  }

  function renderWorkerEvent(event) {
    if (!isObject(event)) return;
    const eventId = text(event.event_id || event.id);
    if (eventId && state.eventIds.has(eventId)) return;
    if (eventId) state.eventIds.add(eventId);
    const queryId = text(event.query_id);
    if (queryId && state.queryId && queryId !== state.queryId) return;
    const terminal = $("worker-terminal");
    const empty = $("worker-empty");
    if (empty) empty.remove();
    const row = element("div", "terminal-row");
    const time = text(event.occurred_at || event.timestamp);
    const stage = text(event.stage || event.event_type) || "event";
    const status = text(event.status) || "update";
    const payload = isObject(event.payload) ? event.payload : {};
    const retry = pick(event, ["retry_count", "attempt"]) ?? pick(payload, ["retry_count", "attempt"]);
    const meta = element("div", "terminal-row-meta");
    meta.append(element("span", "terminal-time", time || "—"), element("span", "terminal-stage", stage), element("span", `terminal-status status-${status.toLowerCase()}`, status));
    if (hasValue(retry)) meta.append(element("span", "terminal-retry", `retry ${retry}`));
    row.append(meta, element("p", "terminal-message", eventMessage(event)));
    terminal.append(row);
    while (terminal.children.length > TERMINAL_EVENT_LIMIT) terminal.firstElementChild.remove();
    setText("worker-event-count", `${state.eventIds.size} event${state.eventIds.size === 1 ? "" : "s"}`);
    if (state.queryId) setText("worker-query-id", state.queryId);
    setWorkerStatus("Streaming", "ready");
  }

  function parseSSEBlock(block) {
    const event = {};
    const data = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("id:")) event.event_id = line.slice(3).trim();
      else if (line.startsWith("event:")) event.event_type = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return null;
    const raw = data.join("\n");
    try {
      return { ...event, ...JSON.parse(raw) };
    } catch (_error) {
      return { ...event, message: raw };
    }
  }

  async function readEventStream(response) {
    if (!response.body || typeof response.body.getReader !== "function") return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true }).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        const event = parseSSEBlock(block);
        if (event) handleProgressEvent(event);
      }
    }
    const finalEvent = parseSSEBlock(buffer);
    if (finalEvent) handleProgressEvent(finalEvent);
  }

  function handleProgressEvent(event) {
    if (!isObject(event)) return;
    if (event.event_id) state.lastEventId = text(event.event_id);
    renderWorkerEvent(event);
    mergeAnswerUpdate(event);
    if (state.payload) {
      renderPayload(state.payload);
      updateAssistantMessage(state.payload);
    }
  }

  function closeEventStream() {
    if (state.eventsController) state.eventsController.abort();
    state.eventsController = null;
  }

  async function openEventStream(queryId) {
    closeEventStream();
    if (!queryId) return;
    const controller = new AbortController();
    state.eventsController = controller;
    setWorkerStatus("Connecting", "idle");
    const headers = authHeaders({ Accept: "text/event-stream" });
    if (state.lastEventId) headers["Last-Event-ID"] = state.lastEventId;
    try {
      const response = await fetch(CHAT_ROUTES.events(queryId), {
        method: "GET",
        headers,
        signal: controller.signal,
      });
      if (!response.ok) {
        setWorkerStatus(`Unavailable · HTTP ${response.status}`, "error");
        return;
      }
      setWorkerStatus("Streaming", "ready");
      await readEventStream(response);
      if (!controller.signal.aborted) setWorkerStatus("Stream ended", "idle");
    } catch (error) {
      if (error.name !== "AbortError") setWorkerStatus("Stream unavailable", "error");
    } finally {
      if (state.eventsController === controller) state.eventsController = null;
    }
  }

  function setLoading(loading) {
    state.loading = loading;
    const button = $("query-form")?.querySelector("button[type=submit]");
    if (button) button.disabled = loading;
    const textarea = $("query");
    if (textarea) textarea.disabled = loading;
  }

  async function selectVehicle(optionNumber, option) {
    if (!state.queryId || state.loading) return;
    state.loading = true;
    setResultStatus("Applying vehicle match", "idle");
    const selection = { query_id: state.queryId, selection_type: "vehicle", option_number: Number(optionNumber) };
    const vehicleId = text(option?.vehicle_id);
    if (vehicleId) selection.vehicle_id = vehicleId;
    try {
      const { response, payload } = await requestJSON(CHAT_ROUTES.selection(state.queryId), {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json", "Idempotency-Key": newIdempotencyKey("selection") }),
        body: JSON.stringify(selection),
      });
      renderPayload(payload, response);
      if (response.ok || response.status === 202) {
        addMessage("assistant", messageText(payload));
        await openEventStream(state.queryId);
      }
    } catch (error) {
      setResultStatus("Selection failed", "error");
      addMessage("assistant", `Vehicle selection failed: ${error.message}`);
    } finally {
      state.loading = false;
    }
  }

  async function submitQuery(event) {
    event.preventDefault();
    const query = text($("query")?.value);
    if (!query) {
      setResultStatus("A request is required", "error");
      return;
    }
    const options = vehicleOptionsFrom(state.payload, answerFrom(state.payload));
    if (options.length && /^\d+$/.test(query)) {
      const optionNumber = Number(query);
      const option = options.find((item, index) => Number(item.option_number || index + 1) === optionNumber);
      if (option) {
        addMessage("user", query);
        $("query").value = "";
        await selectVehicle(optionNumber, option);
        return;
      }
    }
    if (state.loading) return;
    setLoading(true);
    resetAnswer();
    addMessage("user", query);
    setResultStatus("Finding the vehicle and the work", "idle");
    setSystemStatus("Request in flight", "idle");
    const idempotencyKey = newIdempotencyKey("chat");
    try {
      let result = await requestJSON(CHAT_ROUTES.query, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }),
        body: JSON.stringify({ message: query }),
      });
      if (result.response.status === 404 || result.response.status === 405) {
        // Compatibility with the pre-chat local API; the response remains authoritative.
        result = await requestJSON(CHAT_ROUTES.legacyJobPlan, {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }),
          body: JSON.stringify({ query, kind: "all", fallback: true }),
        });
      }
      state.payload = result.payload;
      state.queryId = text(result.payload?.query_id || result.payload?.id) || null;
      renderPayload(result.payload, result.response);
      if (result.response.ok || result.response.status === 202) {
        addMessage("assistant", messageText(result.payload));
        if (state.queryId) {
          setText("worker-query-id", state.queryId);
          await openEventStream(state.queryId);
        }
      } else {
        addMessage("assistant", messageText(result.payload));
      }
    } catch (error) {
      setResultStatus("Request failed", "error");
      setSystemStatus("API unavailable", "error");
      addMessage("assistant", `The local API could not answer: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  function bind() {
    $("query-form")?.addEventListener("submit", submitQuery);
    $("query")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        $("query-form")?.requestSubmit();
      }
    });
    for (const button of document.querySelectorAll("[data-query]")) {
      button.addEventListener("click", () => {
        $("query").value = button.dataset.query || "";
        $("query").focus();
      });
    }
    setWorkerStatus("Idle", "idle");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
