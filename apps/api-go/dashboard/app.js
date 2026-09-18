(() => {
  "use strict";

  const REFRESH_INTERVAL_MS = 2500;
  const REFRESH_DEADLINE_MS = 5 * 60 * 1000;
  const ACTIVE_SYNC_STATES = new Set(["warming", "pending", "running", "partial", "failed"]);
  const state = {
    years: [],
    vehicles: [],
    catalogSync: null,
    decade: null,
    year: null,
    makeInitial: null,
    make: null,
    model: null,
    configuration: null,
    refreshStartedAt: 0,
    refreshTimer: null,
    loading: false,
    selectedVehicle: null,
  };

  const $ = (id) => document.getElementById(id);

  function authHeaders() {
    let token = "local:demo:dataset_viewer";
    try {
      token = window.localStorage.getItem("autodata-auth-token") || token;
    } catch (_error) {
      // The local demo token keeps the selector usable when storage is blocked.
    }
    return { Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}` };
  }

  function setStatus(message, stateName = "idle") {
    const status = $("status");
    status.textContent = message;
    status.dataset.state = stateName;
  }

  function validYear(value) {
    const year = Number(value);
    return Number.isInteger(year) && year >= 1886 && year <= 2100 ? year : null;
  }

  function uniqueSorted(values, compare = (left, right) => left.localeCompare(right)) {
    return [...new Set(values)].sort(compare);
  }

  function decadeFor(year) {
    return Math.floor(year / 10) * 10;
  }

  function makeInitial(make) {
    const first = String(make || "").trim().charAt(0).toUpperCase();
    return /[A-Z]/.test(first) ? first : "#";
  }

  function vehicleRowsForYear() {
    return state.vehicles.filter((vehicle) => validYear(vehicle.year) === state.year);
  }

  function vehicleRowsForMake() {
    return vehicleRowsForYear().filter(
      (vehicle) => String(vehicle.make || "").trim() === state.make,
    );
  }

  function vehicleRowsForModel() {
    return vehicleRowsForMake().filter(
      (vehicle) => String(vehicle.model || "").trim() === state.model,
    );
  }

  function makeNamesForYear() {
    return uniqueSorted(
      vehicleRowsForYear()
        .map((vehicle) => String(vehicle.make || "").trim())
        .filter(Boolean),
    );
  }

  function modelNamesForMake() {
    return uniqueSorted(
      vehicleRowsForMake()
        .map((vehicle) => String(vehicle.model || "").trim())
        .filter(Boolean),
    );
  }

  function configurationsForModel() {
    const configurations = [];
    vehicleRowsForModel().forEach((vehicle) => {
      (Array.isArray(vehicle.configurations) ? vehicle.configurations : []).forEach((configuration) => {
        if (configuration && configuration.configuration_key) configurations.push(configuration);
      });
    });
    const byKey = new Map();
    configurations.forEach((configuration) => byKey.set(configuration.configuration_key, configuration));
    return [...byKey.values()].sort((left, right) =>
      String(left.configuration_key).localeCompare(String(right.configuration_key)),
    );
  }

  function configurationLabel(configuration) {
    const parts = [];
    const displacement = Number(configuration.engine_displacement_l);
    if (Number.isFinite(displacement) && displacement > 0) parts.push(`${displacement.toFixed(1)}L engine`);
    else parts.push("Base configuration");
    if (configuration.drivetrain) parts.push(String(configuration.drivetrain));
    if (configuration.trim) parts.push(String(configuration.trim));
    return parts.join(" · ");
  }

  function button(label, className, dataset, onClick) {
    const control = document.createElement("button");
    control.type = "button";
    control.className = `choice-button ${className}`.trim();
    control.textContent = label;
    Object.entries(dataset || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null) control.dataset[key] = String(value);
    });
    control.addEventListener("click", onClick);
    return control;
  }

  function showPane(paneId, title, stepNumber) {
    ["decade-step", "year-step", "make-step", "model-step", "configuration-step"].forEach((id) => {
      $(id).hidden = id !== paneId;
    });
    $("step-title").textContent = `${stepNumber}. ${title}`;
  }

  function resetDownstream(from) {
    if (from <= 1) state.year = null;
    if (from <= 2) state.makeInitial = null;
    if (from <= 3) state.make = null;
    if (from <= 4) state.model = null;
    if (from <= 5) state.configuration = null;
    state.selectedVehicle = null;
  }

  function renderDecades() {
    showPane("decade-step", "Decade", 1);
    const list = $("decade-list");
    list.replaceChildren();
    const decades = uniqueSorted(state.years.map(decadeFor), (left, right) => right - left);
    decades.forEach((decade) => {
      const control = button(`${decade}s`, "", { decade }, () => {
        state.decade = decade;
        resetDownstream(1);
        renderYears();
        setStatus(`Choose a year from the ${decade}s.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.decade === decade));
      list.append(control);
    });
    if (!decades.length) list.append(document.createTextNode("No years are available."));
  }

  function renderYears() {
    showPane("year-step", "Year", 2);
    const list = $("year-list");
    list.replaceChildren();
    const years = state.years.filter((year) => decadeFor(year) === state.decade);
    years.forEach((year) => {
      const control = button(String(year), "", { year }, () => {
        state.year = year;
        resetDownstream(2);
        state.year = year;
        renderMakes();
        setStatus(`Choose a make available for ${year}.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.year === year));
      list.append(control);
    });
  }

  function groupMakesByInitial() {
    const groups = new Map();
    makeNamesForYear().forEach((make) => {
      const initial = makeInitial(make);
      if (!groups.has(initial)) groups.set(initial, []);
      groups.get(initial).push(make);
    });
    return groups;
  }

  function renderMakeLetters() {
    const list = $("make-letter-list");
    list.replaceChildren();
    const groups = groupMakesByInitial();
    uniqueSorted([...groups.keys()]).forEach((initial) => {
      const control = button(initial, "make-letter", { makeInitial: initial }, () => {
        state.makeInitial = initial;
        state.make = null;
        state.model = null;
        state.configuration = null;
        state.selectedVehicle = null;
        renderMakes();
        setStatus(`Choose a ${initial === "#" ? "make" : `${initial}-make`}.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.makeInitial === initial));
      list.append(control);
    });
    if (!groups.size) list.append(document.createTextNode("No makes are available for this year yet."));
    return groups;
  }

  function renderMakes() {
    showPane("make-step", "Make", 3);
    const groups = renderMakeLetters();
    const list = $("make-list");
    list.replaceChildren();
    list.hidden = state.makeInitial === null;
    const makes = groups.get(state.makeInitial) || [];
    makes.forEach((make) => {
      const control = button(make, "", { make }, () => {
        state.make = make;
        state.model = null;
        state.configuration = null;
        state.selectedVehicle = null;
        renderModels();
        setStatus(`Choose a ${make} model.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.make === make));
      list.append(control);
    });
  }

  function renderModels() {
    showPane("model-step", "Model", 4);
    const list = $("model-list");
    list.replaceChildren();
    const models = modelNamesForMake();
    models.forEach((model) => {
      const control = button(model, "", { model }, () => {
        state.model = model;
        state.configuration = null;
        state.selectedVehicle = null;
        renderConfigurations();
        setStatus(`Choose an engine or base configuration for ${model}.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.model === model));
      list.append(control);
    });
    if (!models.length) list.append(document.createTextNode("No models are available for this make yet."));
  }

  function renderConfigurations() {
    showPane("configuration-step", "Engine / base", 5);
    const list = $("configuration-list");
    list.replaceChildren();
    const configurations = configurationsForModel();
    configurations.forEach((configuration) => {
      const control = button(
        configurationLabel(configuration),
        "",
        { configuration: configuration.configuration_key },
        () => {
          state.configuration = configuration.configuration_key;
          state.selectedVehicle = {
            year: state.year,
            make: state.make,
            model: state.model,
            configuration,
          };
          updateSelectedVehicle();
          setStatus("Vehicle configuration selected.", "ready");
        },
      );
      control.setAttribute("aria-pressed", String(state.configuration === configuration.configuration_key));
      list.append(control);
    });
    if (!configurations.length) list.append(document.createTextNode("No engine/base configurations are available yet."));
  }

  function renderActiveStep() {
    if (state.decade === null) return renderDecades();
    if (state.year === null) return renderYears();
    if (state.make === null) return renderMakes();
    if (state.model === null) return renderModels();
    renderConfigurations();
  }

  function updateSelectedVehicle() {
    const selected = $("selected-vehicle");
    const hasSelection = Boolean(state.selectedVehicle);
    selected.hidden = !hasSelection;
    if (!hasSelection) {
      $("selected-label").textContent = "—";
      $("continue-button").disabled = true;
      return;
    }
    const configuration = state.selectedVehicle.configuration;
    $("selected-label").textContent = `${state.year} ${state.make} ${state.model} — ${configurationLabel(configuration)}`;
    $("continue-button").disabled = false;
  }

  function mergeSelectorPayload(payload) {
    state.catalogSync = payload.catalog_sync || null;
    state.vehicles = Array.isArray(payload.vehicles)
      ? payload.vehicles.filter((vehicle) => vehicle && typeof vehicle === "object" && validYear(vehicle.year) && String(vehicle.make || "").trim())
      : [];
    state.years = uniqueSorted(
      [
        ...(Array.isArray(payload.years) ? payload.years : []),
        ...state.vehicles.map((vehicle) => vehicle.year),
      ].map(validYear).filter(Boolean),
      (left, right) => right - left,
    );
  }

  function scheduleRefresh() {
    if (state.refreshTimer) window.clearTimeout(state.refreshTimer);
    const status = state.catalogSync && state.catalogSync.status;
    if (!ACTIVE_SYNC_STATES.has(status) || Date.now() - state.refreshStartedAt >= REFRESH_DEADLINE_MS) return;
    state.refreshTimer = window.setTimeout(() => {
      refreshSelectors();
    }, REFRESH_INTERVAL_MS);
  }

  async function refreshSelectors() {
    if (state.loading) return;
    state.loading = true;
    try {
      const response = await fetch("/vehicle-identities/selectors", { headers: authHeaders() });
      if (!response.ok) throw new Error(`Vehicle selectors returned HTTP ${response.status}`);
      const payload = await response.json();
      mergeSelectorPayload(payload);
      renderActiveStep();
      updateSelectedVehicle();
      const rowCount = Number(state.catalogSync && state.catalogSync.row_count) || state.vehicles.length;
      if (state.catalogSync && ACTIVE_SYNC_STATES.has(state.catalogSync.status)) {
        setStatus(`Catalog warming · ${rowCount.toLocaleString()} vehicle configurations available.`, "ready");
      } else if (state.years.length) {
        setStatus("Choose a decade to begin.", "ready");
      } else {
        setStatus("No vehicle years are available.", "error");
      }
      scheduleRefresh();
    } catch (error) {
      setStatus(`Vehicle list unavailable: ${error.message}`, "error");
      scheduleRefresh();
    } finally {
      state.loading = false;
    }
  }

  function loadSelectors() {
    state.refreshStartedAt = Date.now();
    refreshSelectors();
  }

  $("continue-button").addEventListener("click", () => {
    if (!state.selectedVehicle) return;
    $("instructions").textContent = "Vehicle selected. Continue with the repair request when ready.";
    setStatus(`${state.year} ${state.make} ${state.model} is ready for the next step.`, "ready");
  });

  loadSelectors();
})();
