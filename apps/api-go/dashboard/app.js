(() => {
  "use strict";

  const REFRESH_INTERVAL_MS = 2500;
  const REFRESH_DEADLINE_MS = 5 * 60 * 1000;
  const ACTIVE_SYNC_STATES = new Set(["warming", "pending", "running", "partial", "failed"]);
  const state = {
    years: [], vehicles: [], catalogSync: null, decade: null, year: null,
    makeInitial: null, make: null, model: null, configuration: null,
    refreshStartedAt: 0, refreshTimer: null, loading: false, selectedVehicle: null,
    activeQueryId: null, eventAbort: null, terminalLines: [], terminalKeys: new Set(),
    choicePromptQueryId: null,
  };

  const $ = (id) => document.getElementById(id);
  function authHeaders() {
    let token = "local:demo:dataset_viewer";
    try { token = window.localStorage.getItem("autodata-auth-token") || token; } catch (_error) { /* local fallback */ }
    return { Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}` };
  }
  function setStatus(message, stateName = "idle") { $("status").textContent = message; $("status").dataset.state = stateName; }
  function validYear(value) { const year = Number(value); return Number.isInteger(year) && year >= 1886 && year <= 2100 ? year : null; }
  function uniqueSorted(values, compare = (left, right) => left.localeCompare(right)) { return [...new Set(values)].sort(compare); }
  function decadeFor(year) { return Math.floor(year / 10) * 10; }
  function makeInitial(make) { const first = String(make || "").trim().charAt(0).toUpperCase(); return /[A-Z]/.test(first) ? first : "#"; }
  function vehicleRowsForYear() { return state.vehicles.filter((vehicle) => validYear(vehicle.year) === state.year); }
  function vehicleRowsForMake() { return vehicleRowsForYear().filter((vehicle) => String(vehicle.make || "").trim() === state.make); }
  function vehicleRowsForModel() { return vehicleRowsForMake().filter((vehicle) => String(vehicle.model || "").trim() === state.model); }
  function makeNamesForYear() { return uniqueSorted(vehicleRowsForYear().map((vehicle) => String(vehicle.make || "").trim()).filter(Boolean)); }
  function modelNamesForMake() { return uniqueSorted(vehicleRowsForMake().map((vehicle) => String(vehicle.model || "").trim()).filter(Boolean)); }
  function configurationsForModel() {
    const byKey = new Map();
    vehicleRowsForModel().forEach((vehicle) => (Array.isArray(vehicle.configurations) ? vehicle.configurations : []).forEach((configuration) => {
      if (configuration && configuration.configuration_key) byKey.set(configuration.configuration_key, configuration);
    }));
    return [...byKey.values()].sort((left, right) => String(left.configuration_key).localeCompare(String(right.configuration_key)));
  }
  function configurationLabel(configuration) {
    const parts = []; const displacement = Number(configuration.engine_displacement_l);
    if (Number.isFinite(displacement) && displacement > 0) parts.push(`${displacement.toFixed(1)}L engine`); else parts.push("Base configuration");
    if (configuration.drivetrain) parts.push(String(configuration.drivetrain));
    if (configuration.trim) parts.push(String(configuration.trim));
    return parts.join(" · ");
  }
  function button(label, className, dataset, onClick) {
    const control = document.createElement("button"); control.type = "button"; control.className = `choice-button ${className}`.trim(); control.textContent = label;
    Object.entries(dataset || {}).forEach(([key, value]) => { if (value !== undefined && value !== null) control.dataset[key] = String(value); });
    control.addEventListener("click", onClick); return control;
  }
  function showPane(paneId, title, stepNumber) {
    ["decade-step", "year-step", "make-step", "model-step", "configuration-step"].forEach((id) => { $(id).hidden = id !== paneId; });
    $("step-title").textContent = `${stepNumber}. ${title}`; $("back-button").hidden = paneId === "decade-step";
  }
  function resetDownstream(from) {
    if (from <= 1) state.year = null; if (from <= 2) state.makeInitial = null; if (from <= 3) state.make = null; if (from <= 4) state.model = null; if (from <= 5) state.configuration = null; state.selectedVehicle = null;
  }
  function renderDecades() {
    showPane("decade-step", "Decade", 1); const list = $("decade-list"); list.replaceChildren();
    uniqueSorted(state.years.map(decadeFor), (left, right) => right - left).forEach((decade) => {
      const control = button(`${decade}s`, "", { decade }, () => { state.decade = decade; resetDownstream(1); renderYears(); setStatus(`Choose a year from the ${decade}s.`, "ready"); });
      control.setAttribute("aria-pressed", String(state.decade === decade)); list.append(control);
    });
    if (!state.years.length) list.append(document.createTextNode("No years are available."));
  }
  function renderYears() {
    showPane("year-step", "Year", 2); const list = $("year-list"); list.replaceChildren();
    state.years.filter((year) => decadeFor(year) === state.decade).forEach((year) => {
      const control = button(String(year), "", { year }, () => { resetDownstream(2); state.year = year; renderMakes(); setStatus(`Choose a make available for ${year}.`, "ready"); });
      control.setAttribute("aria-pressed", String(state.year === year)); list.append(control);
    });
  }
  function groupMakesByInitial() {
    const groups = new Map(); makeNamesForYear().forEach((make) => { const initial = makeInitial(make); if (!groups.has(initial)) groups.set(initial, []); groups.get(initial).push(make); }); return groups;
  }
  function renderMakeLetters() {
    const list = $("make-letter-list"); list.replaceChildren(); const groups = groupMakesByInitial();
    uniqueSorted([...groups.keys()]).forEach((initial) => {
      const control = button(initial, "make-letter", { makeInitial: initial }, () => { state.makeInitial = initial; state.make = null; state.model = null; state.configuration = null; state.selectedVehicle = null; renderMakes(); setStatus(`Choose a ${initial === "#" ? "make" : `${initial}-make`}.`, "ready"); });
      control.setAttribute("aria-pressed", String(state.makeInitial === initial)); list.append(control);
    });
    if (!groups.size) list.append(document.createTextNode("No makes are available for this year yet.")); return groups;
  }
  function renderMakes() {
    showPane("make-step", "Make", 3); const groups = renderMakeLetters(); const list = $("make-list"); list.replaceChildren(); list.hidden = state.makeInitial === null;
    (groups.get(state.makeInitial) || []).forEach((make) => {
      const control = button(make, "", { make }, () => { state.make = make; state.model = null; state.configuration = null; state.selectedVehicle = null; renderModels(); setStatus(`Choose a ${make} model.`, "ready"); });
      control.setAttribute("aria-pressed", String(state.make === make)); list.append(control);
    });
  }
  function renderModels() {
    showPane("model-step", "Model", 4); const list = $("model-list"); list.replaceChildren(); const models = modelNamesForMake();
    models.forEach((model) => {
      const control = button(model, "", { model }, () => { state.model = model; state.configuration = null; state.selectedVehicle = null; renderConfigurations(); setStatus(`Choose an engine or base configuration for ${model}.`, "ready"); });
      control.setAttribute("aria-pressed", String(state.model === model)); list.append(control);
    });
    if (!models.length) list.append(document.createTextNode("No models are available for this make yet."));
  }
  function renderConfigurations() {
    showPane("configuration-step", "Engine / base", 5); const list = $("configuration-list"); list.replaceChildren(); const configurations = configurationsForModel();
    configurations.forEach((configuration) => {
      const control = button(configurationLabel(configuration), "", { configuration: configuration.configuration_key }, () => {
        state.configuration = configuration.configuration_key; state.selectedVehicle = { year: state.year, make: state.make, model: state.model, configuration }; updateSelectedVehicle(); setStatus("Vehicle configuration selected. Continue to open the repair workspace.", "ready");
      });
      control.setAttribute("aria-pressed", String(state.configuration === configuration.configuration_key)); list.append(control);
    });
    if (!configurations.length) list.append(document.createTextNode("No engine/base configurations are available yet."));
  }
  function renderActiveStep() { if (state.decade === null) return renderDecades(); if (state.year === null) return renderYears(); if (state.make === null) return renderMakes(); if (state.model === null) return renderModels(); renderConfigurations(); }
  function updateSelectedVehicle() {
    const selected = $("selected-vehicle"); const hasSelection = Boolean(state.selectedVehicle); selected.hidden = !hasSelection;
    if (!hasSelection) { $("selected-label").textContent = "—"; $("continue-button").disabled = true; return; }
    const configuration = state.selectedVehicle.configuration; $("selected-label").textContent = `${state.year} ${state.make} ${state.model} — ${configurationLabel(configuration)}`; $("continue-button").disabled = false;
  }
  function goBack() {
    if (state.configuration !== null) { state.configuration = null; state.selectedVehicle = null; renderConfigurations(); setStatus("Choose an engine or base configuration.", "ready"); return; }
    if (state.model !== null) { state.model = null; state.selectedVehicle = null; renderModels(); setStatus(`Choose a model for ${state.make}.`, "ready"); return; }
    if (state.make !== null) { state.make = null; state.makeInitial = null; renderMakes(); setStatus(`Choose a make available for ${state.year}.`, "ready"); return; }
    if (state.makeInitial !== null) { state.makeInitial = null; renderMakes(); setStatus(`Choose a make available for ${state.year}.`, "ready"); return; }
    if (state.year !== null) { state.year = null; renderYears(); setStatus(`Choose a year from the ${state.decade}s.`, "ready"); return; }
    state.decade = null; resetDownstream(1); renderDecades(); setStatus("Choose a decade to begin.", "ready");
  }
  function mergeSelectorPayload(payload) {
    state.catalogSync = payload.catalog_sync || null;
    state.vehicles = Array.isArray(payload.vehicles) ? payload.vehicles.filter((vehicle) => vehicle && typeof vehicle === "object" && validYear(vehicle.year) && String(vehicle.make || "").trim()) : [];
    state.years = uniqueSorted([...(Array.isArray(payload.years) ? payload.years : []), ...state.vehicles.map((vehicle) => vehicle.year)].map(validYear).filter(Boolean), (left, right) => right - left);
  }
  function scheduleRefresh() {
    if (state.refreshTimer) window.clearTimeout(state.refreshTimer); const status = state.catalogSync && state.catalogSync.status;
    if (!ACTIVE_SYNC_STATES.has(status) || Date.now() - state.refreshStartedAt >= REFRESH_DEADLINE_MS) return; state.refreshTimer = window.setTimeout(refreshSelectors, REFRESH_INTERVAL_MS);
  }
  async function refreshSelectors() {
    if (state.loading) return; state.loading = true;
    try {
      const response = await fetch("/vehicle-identities/selectors", { headers: authHeaders() }); if (!response.ok) throw new Error(`Vehicle selectors returned HTTP ${response.status}`);
      mergeSelectorPayload(await response.json()); renderActiveStep(); updateSelectedVehicle(); const rowCount = Number(state.catalogSync && state.catalogSync.row_count) || state.vehicles.length;
      if (state.catalogSync && ACTIVE_SYNC_STATES.has(state.catalogSync.status)) setStatus(`Catalog warming · ${rowCount.toLocaleString()} vehicle configurations available.`, "ready"); else if (state.years.length) setStatus("Choose a decade to begin.", "ready"); else setStatus("No vehicle years are available.", "error"); scheduleRefresh();
    } catch (error) { setStatus(`Vehicle list unavailable: ${error.message}`, "error"); scheduleRefresh(); } finally { state.loading = false; }
  }
  function openWorkspace() {
    if (!state.selectedVehicle) return; $("workspace").hidden = false; $("workspace-vehicle").textContent = $("selected-label").textContent; $("instructions").textContent = "Ask for a repair result in plain language. The agent will show its work as it runs."; $("chat-input").focus(); setStatus("Repair workspace ready.", "ready");
  }
  function closeWorkspace() { abortEvents(); $("workspace").hidden = true; $("chat-result").hidden = true; $("chat-options").hidden = true; $("chat-options").replaceChildren(); $("chat-input").value = ""; state.activeQueryId = null; state.choicePromptQueryId = null; setStatus("Choose an engine or base configuration.", "ready"); }
  function escapeHtml(value) { const element = document.createElement("span"); element.textContent = value == null ? "" : String(value); return element.innerHTML; }
  function appendChat(text, speaker = "AutoData") { const log = $("chat-log"); const empty = log.querySelector(".chat-empty"); if (empty) empty.remove(); const item = document.createElement("p"); item.className = `chat-message ${speaker.toLowerCase()}`; item.innerHTML = `<strong>${speaker}</strong> ${escapeHtml(text)}`; log.append(item); log.scrollTop = log.scrollHeight; }
  function clearChatOptions() { const options = $("chat-options"); options.replaceChildren(); options.hidden = true; }
  function renderVehicleOptions(query) {
    const options = Array.isArray(query && query.vehicle_options) ? query.vehicle_options.filter((option) => option && option.clickable !== false && option.option_number && option.label) : [];
    const container = $("chat-options"); container.replaceChildren();
    if (!options.length) { container.hidden = true; return false; }
    const heading = document.createElement("p"); heading.className = "chat-options-heading"; heading.textContent = "Available vehicle configurations — choose one:"; container.append(heading);
    options.forEach((option) => {
      const choice = button(`${option.option_number}. ${option.label}`, "chat-option", { optionNumber: option.option_number }, () => selectVehicleOption(query.query_id, option));
      choice.setAttribute("aria-label", `Choose option ${option.option_number}: ${option.label}`); container.append(choice);
    });
    container.hidden = false; return true;
  }
  async function selectVehicleOption(queryId, option) {
    const controls = Array.from($("chat-options").querySelectorAll("button")); controls.forEach((control) => { control.disabled = true; });
    appendChat(`${option.option_number}. ${option.label}`, "You"); appendTerminal(`Vehicle option ${option.option_number} selected.`);
    try {
      const response = await fetch(`/chat/queries/${encodeURIComponent(queryId)}/selections`, { method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json", "Idempotency-Key": `dashboard:${queryId}:selection:${option.option_number}` }, body: JSON.stringify(option.selection || { selection_type: "vehicle", option_number: option.option_number, vehicle_id: option.vehicle_id, candidate_key: option.candidate_key }) });
      if (!response.ok) throw new Error(`Vehicle selection returned HTTP ${response.status}`);
      const query = await response.json(); state.activeQueryId = queryId; clearChatOptions(); renderQuery(query); streamChatEvents(queryId); const finalQuery = await pollQuery(queryId); appendQueryCompletion(finalQuery);
    } catch (error) { controls.forEach((control) => { control.disabled = false; }); appendTerminal(`Vehicle selection failed: ${error.message}`); appendChat("I could not apply that choice. Please try it again."); }
  }
  function appendQueryCompletion(query) { if (!query) return; if (query.status === "available") appendChat("The result is ready below."); else if (query.status === "failed" || query.status === "dead_letter") appendChat("The agent could not complete that request. See the worker terminal for the current status."); }
  function setTerminalStatus(text) { $("worker-status").textContent = text; }
  function appendTerminal(message, key = "") { const text = String(message || "").trim(); if (!text || (key && state.terminalKeys.has(key))) return; if (key) state.terminalKeys.add(key); state.terminalLines.push(text); state.terminalLines = state.terminalLines.slice(-80); const terminal = $("worker-terminal"); terminal.replaceChildren(); state.terminalLines.forEach((line) => { const item = document.createElement("div"); item.textContent = line; terminal.append(item); }); terminal.scrollTop = terminal.scrollHeight; }
  function eventMessage(event) { const payload = event && event.payload; return payload && payload.message ? payload.message : `${event.stage || "worker"} ${event.status || "updated"}`; }
  function renderQuery(query) {
    if (!query) return; const answer = query.answer || {}; const procedure = answer.procedure;
    if (query.status === "awaiting_vehicle") {
      const warning = (answer.warnings || []).map((item) => item && item.message).filter(Boolean)[0] || "Choose a vehicle configuration to continue.";
      if (state.choicePromptQueryId !== query.query_id) { appendChat(warning); state.choicePromptQueryId = query.query_id; }
      if (!renderVehicleOptions(query)) { appendChat("No vehicle options were returned. Please retry the request."); }
      setTerminalStatus("awaiting choice"); return;
    }
    if (state.choicePromptQueryId === query.query_id) { state.choicePromptQueryId = null; clearChatOptions(); }
    if (query.status === "failed") { appendChat((answer.warnings || []).map((warning) => warning.message).join(" ") || "The agent could not complete this request."); return; }
    if (!procedure && !answer.quote) return;
    $("chat-result").hidden = false; const quote = answer.quote || {}; const hours = quote.total_hours ?? quote.total_labor_hours ?? quote.required_hours; const title = procedure && procedure.title ? procedure.title : "Requested service";
    $("chat-answer").innerHTML = `<h3>${escapeHtml(title)}</h3><p>${hours == null ? "Labor time is being verified." : `${escapeHtml(Number(hours).toFixed(2))} labor hours`}${quote.overlap_hours_removed ? ` · ${escapeHtml(Number(quote.overlap_hours_removed).toFixed(2))} hours overlap removed` : ""}</p><p class="review-note">${escapeHtml(procedure && procedure.review_label ? procedure.review_label : "Source-backed result")}</p>`;
    $("procedure-markdown").textContent = procedure && procedure.markdown ? procedure.markdown : "Markdown procedure is being prepared.";
  }
  function abortEvents() { if (state.eventAbort) state.eventAbort.abort(); state.eventAbort = null; }
  async function streamChatEvents(queryId) {
    abortEvents(); const controller = new AbortController(); state.eventAbort = controller;
    try {
      const response = await fetch(`/chat/queries/${encodeURIComponent(queryId)}/events`, { headers: authHeaders(), signal: controller.signal }); if (!response.ok || !response.body) return; const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) { const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const frames = buffer.split("\n\n"); buffer = frames.pop(); frames.forEach((frame) => { const data = frame.split("\n").find((line) => line.startsWith("data:")); if (!data) return; try { const event = JSON.parse(data.slice(5).trim()); appendTerminal(eventMessage(event), event.event_id); setTerminalStatus(event.status || "working"); } catch (_error) { /* ignore malformed event */ } }); }
    } catch (error) { if (error.name !== "AbortError") appendTerminal("Event stream unavailable; durable status polling continues."); }
  }
  async function pollQuery(queryId) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const response = await fetch(`/chat/queries/${encodeURIComponent(queryId)}`, { headers: authHeaders() }); if (!response.ok) throw new Error(`Chat query returned HTTP ${response.status}`); const query = await response.json(); (query.answer && Array.isArray(query.answer.worker_stream) ? query.answer.worker_stream : []).forEach((workerEvent) => appendTerminal(workerEvent.message || eventMessage(workerEvent), workerEvent.event_id)); renderQuery(query);
      if (query.status === "awaiting_vehicle") { setTerminalStatus("awaiting choice"); renderQuery(query); return query; }
      if (["available", "failed", "dead_letter"].includes(query.status)) { setTerminalStatus(query.status); appendTerminal(`Query ${query.status}.`); return query; }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    appendTerminal("Query is still processing; it remains available in durable worker state."); return null;
  }
  async function submitChat(event) {
    event.preventDefault(); const message = $("chat-input").value.trim(); if (!message || !state.selectedVehicle) return;
    appendChat(message, "You"); $("chat-input").value = ""; $("chat-send").disabled = true; state.terminalLines = []; state.terminalKeys = new Set(); $("worker-terminal").replaceChildren(); setTerminalStatus("starting"); appendTerminal("Agent received the request.");
    try {
      const response = await fetch("/chat/queries", { method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json", "Idempotency-Key": `dashboard:${crypto.randomUUID()}` }, body: JSON.stringify({ message, request_params: { vehicle: { year: state.year, make: state.make, model: state.model, ...state.selectedVehicle.configuration } } }) });
      if (!response.ok) throw new Error(`Chat request returned HTTP ${response.status}`); const query = await response.json(); state.activeQueryId = query.query_id; appendTerminal(`Query ${query.query_id} accepted.`); renderQuery(query); streamChatEvents(query.query_id); const finalQuery = await pollQuery(query.query_id); appendQueryCompletion(finalQuery);
    } catch (error) { appendTerminal(`Request failed: ${error.message}`); appendChat("I could not complete that request. Try again when the worker is available."); setTerminalStatus("failed"); } finally { $("chat-send").disabled = false; }
  }

  $("back-button").addEventListener("click", goBack);
  $("continue-button").addEventListener("click", openWorkspace);
  $("workspace-back-button").addEventListener("click", () => { closeWorkspace(); renderConfigurations(); $("selected-vehicle").hidden = false; });
  $("chat-form").addEventListener("submit", submitChat);
  state.refreshStartedAt = Date.now(); refreshSelectors();
})();
