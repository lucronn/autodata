(() => {
  "use strict";

  const state = {
    years: [],
    vehicles: [],
    decade: null,
    year: null,
    makeInitial: null,
    make: null,
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

  function makeNamesForYear() {
    return uniqueSorted(
      vehicleRowsForYear()
        .map((vehicle) => String(vehicle.make || "").trim())
        .filter(Boolean),
    );
  }

  function button(label, className, dataset, onClick) {
    const control = document.createElement("button");
    control.type = "button";
    control.className = `choice-button ${className}`.trim();
    control.textContent = label;
    if (dataset.decade !== undefined) {
      control.setAttribute("data-decade", String(dataset.decade));
    }
    if (dataset.year !== undefined) {
      control.setAttribute("data-year", String(dataset.year));
    }
    if (dataset.makeInitial !== undefined) {
      control.setAttribute("data-make-initial", String(dataset.makeInitial));
    }
    if (dataset.make !== undefined) {
      control.setAttribute("data-make", String(dataset.make));
    }
    control.addEventListener("click", onClick);
    return control;
  }

  function renderDecades() {
    const decades = uniqueSorted(
      state.years.map(decadeFor),
      (left, right) => right - left,
    );
    const list = $("decade-list");
    list.replaceChildren();
    decades.forEach((decade) => {
      const control = button(`${decade}s`, "", { decade }, () => {
        state.decade = decade;
        state.year = null;
        state.makeInitial = null;
        state.make = null;
        state.selectedVehicle = null;
        renderDecades();
        renderYears();
        renderMakes();
        updateSelectedVehicle();
        setStatus(`Choose a year from the ${decade}s.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.decade === decade));
      list.append(control);
    });
    if (!decades.length) list.append(document.createTextNode("No years are available."));
  }

  function renderYears() {
    const step = $("year-step");
    const list = $("year-list");
    list.replaceChildren();
    step.hidden = state.decade === null;
    if (state.decade === null) return;
    const years = state.years.filter((year) => decadeFor(year) === state.decade);
    years.forEach((year) => {
      const control = button(String(year), "", { year }, () => {
        state.year = year;
        state.makeInitial = null;
        state.make = null;
        state.selectedVehicle = null;
        renderYears();
        renderMakes();
        updateSelectedVehicle();
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
        state.selectedVehicle = null;
        renderMakeLetters();
        renderMakes();
        updateSelectedVehicle();
        setStatus(`Choose a ${initial === "#" ? "make" : `${initial}-make`}.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.makeInitial === initial));
      list.append(control);
    });
    if (!groups.size) list.append(document.createTextNode("No makes are available for this year."));
    return groups;
  }

  function renderMakes() {
    const step = $("make-step");
    const list = $("make-list");
    list.replaceChildren();
    step.hidden = state.year === null;
    list.hidden = state.makeInitial === null;
    if (state.year === null) return;
    const groups = renderMakeLetters();
    const makes = groups.get(state.makeInitial) || [];
    makes.forEach((make) => {
      const control = button(make, "", { make }, () => {
        state.make = make;
        state.selectedVehicle = { year: state.year, make };
        renderMakes();
        updateSelectedVehicle();
        setStatus(`${state.year} ${make} selected.`, "ready");
      });
      control.setAttribute("aria-pressed", String(state.make === make));
      list.append(control);
    });
  }

  function updateSelectedVehicle() {
    const selected = $("selected-vehicle");
    const hasSelection = Boolean(state.selectedVehicle);
    selected.hidden = !hasSelection;
    $("selected-label").textContent = hasSelection
      ? `${state.selectedVehicle.year} ${state.selectedVehicle.make}`
      : "—";
    $("continue-button").disabled = !hasSelection;
  }

  async function loadSelectors() {
    try {
      const response = await fetch("/vehicle-identities/selectors", { headers: authHeaders() });
      if (!response.ok) throw new Error(`Vehicle selectors returned HTTP ${response.status}`);
      const payload = await response.json();
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
      renderDecades();
      setStatus(state.years.length ? "Choose a decade to begin." : "No vehicle years are available.", state.years.length ? "ready" : "error");
    } catch (error) {
      setStatus(`Vehicle list unavailable: ${error.message}`, "error");
    }
  }

  $("continue-button").addEventListener("click", () => {
    if (!state.selectedVehicle) return;
    $("instructions").textContent = "Vehicle selected. Continue with the repair request when ready.";
    setStatus(`${state.selectedVehicle.year} ${state.selectedVehicle.make} is ready for the next step.`, "ready");
  });

  loadSelectors();
})();
