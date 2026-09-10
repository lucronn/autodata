const diagrams = {
  basic: `flowchart LR
  S[Source] --> N[Normalize]
  V[Vehicle] --> N
  N --> P[(PostgreSQL)]
  P --> A[Go API]
  A --> J[Structured JSON]`,
  mid: `flowchart LR
  subgraph I[Inputs]
    S[URL or file]
    V[Vehicle selection]
    Q[Prompt or keywords]
  end
  subgraph P[Processing]
    C[Universal capture]
    X[Immutable snapshot]
    R[Vehicle identity resolution]
    D[Normalize and dedupe]
  end
  subgraph O[Outcomes]
    F[Fast lane]
    Dp[Deep lane]
    Rev[Immutable revision]
  end
  S --> C --> X --> R --> D
  V --> R
  D --> F --> Rev
  Rev --> Dp --> Rev
  Q --> R
  Rev --> DB[(PostgreSQL + pgvector)]
  DB --> API[Go API]`,
  detailed: `flowchart TB
  subgraph INPUTS[Inputs]
    VF[Vehicle catalog<br/>year make model engine]
    AS[Article source<br/>URL file directory API]
    U[Vehicle selection + prompt]
  end
  subgraph EDGE[API and source boundary]
    API[Go API<br/>auth RBAC reads commands]
    AD[Provider-neutral adapter]
    SS[Immutable snapshot<br/>hash version license]
  end
  subgraph FAST[Fast lane / Python]
    VI[Vehicle identity<br/>aliases + configuration]
    AL[Article list metadata only]
    N[Normalize vocabulary]
    DD[Similarity dedupe<br/>95%+ review threshold]
    EV[Evidence + confidence]
    VC[Viewable contract]
  end
  subgraph BUS[NATS JetStream]
    FR[fast.requested]
    VP[dataset.viewable]
    DR[deep.requested]
    SP[section.published]
    DL[retry + dead letter]
  end
  subgraph DEEP[Deep lane / Python]
    EN[Targeted enrichment]
    EM[Embeddings + retrieval index]
    DQ[Quality checks]
  end
  subgraph DATA[Evidence-backed persistence]
    PG[(PostgreSQL)]
    VEC[(pgvector)]
    OBJ[(MinIO / S3)]
    PR[Projection revision<br/>section readiness + changelog]
  end
  subgraph READ[Fast read path]
    QM[Normalize prompt]
    WM{Warm match?}
    JSON[Structured JSON]
    COLD[Cold miss<br/>targeted request]
  end
  VF --> VI
  AS --> AD --> SS
  U --> API
  SS --> FR --> VI
  SS --> AL --> N --> DD --> EV --> VC
  VI --> PG
  VC --> VP --> PR
  VP --> DR --> EN --> EM --> DQ --> SP --> PR
  EN -->|failure| DL
  PR --> PG
  EV --> OBJ
  EM --> VEC
  API --> QM --> WM
  PG --> WM
  VEC --> WM
  WM -->|yes| JSON
  WM -->|no| COLD --> API
  PR --> JSON`,
};

const mermaidConfig = {
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'base',
  themeVariables: {
    background: '#0b1117',
    primaryColor: '#18242e',
    primaryTextColor: '#e9eeeb',
    primaryBorderColor: '#f1c75b',
    lineColor: '#8de2c9',
    secondaryColor: '#131d26',
    tertiaryColor: '#0b1117',
    clusterBkg: '#131d26',
    clusterBorder: '#52605f',
    fontFamily: 'DM Mono, monospace',
    fontSize: '12px',
  },
};

const wizardScreens = ['intro', 'problem', 'choice', 'proof', 'close'];
const wizardNames = ['INTRODUCTION', 'THE PROBLEM', 'THE CHOICE', 'THE PROOF', 'THE HANDOFF'];

function showScreen(screen, updateHash = true) {
  if (!wizardScreens.includes(screen)) return;
  const hasSelectedPath = Boolean(document.querySelector('.path-tab.is-active'));
  if ((screen === 'proof' || screen === 'close') && !hasSelectedPath) screen = 'choice';
  document.querySelectorAll('[data-screen]').forEach((section) => {
    const active = section.dataset.screen === screen;
    section.hidden = !active;
    section.classList.toggle('is-active', active);
    if (active) section.scrollTop = 0;
  });
  const index = wizardScreens.indexOf(screen);
  const number = document.querySelector('#wizard-step-number');
  const name = document.querySelector('#wizard-step-name');
  const fill = document.querySelector('#wizard-progress-fill');
  if (number) number.textContent = String(index + 1).padStart(2, '0');
  if (name) name.textContent = wizardNames[index];
  if (fill) fill.style.width = `${((index + 1) / wizardScreens.length) * 100}%`;
  if (updateHash) history.replaceState(null, '', `#${screen}`);
}

function setActivePath(path) {
  document.querySelectorAll('[data-path]').forEach((button) => {
    const active = button.dataset.path === path;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('[data-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.panel !== path;
  });
  const gate = document.querySelector('#selection-gate');
  if (gate) gate.hidden = Boolean(path);
  if (!path) return;
  const stepper = document.querySelector(`[data-stepper="${path}"]`);
  if (stepper) setActiveStep(stepper, 1);
}

function setActiveStep(stepper, requestedStep) {
  const path = stepper.dataset.stepper;
  const step = Math.max(1, Math.min(3, Number(requestedStep)));
  stepper.dataset.currentStep = String(step);

  stepper.querySelectorAll('[data-path-step]').forEach((panel) => {
    panel.hidden = panel.dataset.pathStep !== `${path}-${step}`;
  });
  stepper.querySelectorAll('[data-step-button]').forEach((button) => {
    const active = button.dataset.stepButton === `${path}-${step}`;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', String(active));
  });

  const count = stepper.querySelector(`[data-step-count="${path}"]`);
  if (count) count.textContent = String(step);
  const previous = stepper.querySelector(`[data-step-prev="${path}"]`);
  const next = stepper.querySelector(`[data-step-next="${path}"]`);
  if (previous) previous.disabled = step === 1;
  if (next) {
    next.disabled = false;
    next.innerHTML = step === 3 ? 'Continue to the proof <span>→</span>' : 'Next <span>→</span>';
  }

  if (path === 'a' && step === 2) {
    const generic = stepper.querySelector('.generic-diagram');
    if (generic) renderMermaid(generic, generic.textContent);
  }
  if (path === 'b' && step === 2) renderProfessional('basic');
}

async function renderMermaid(element, source) {
  if (!element) return;
  element.textContent = source;
  element.removeAttribute('data-processed');
  if (!window.mermaid) return;
  try {
    await window.mermaid.run({ nodes: [element] });
  } catch (error) {
    element.innerHTML = `<div class="error-text">Diagram source is available below.</div>`;
    console.error('Mermaid render failed', error);
  }
}

function renderProfessional(level) {
  const diagram = document.querySelector('#professional-diagram');
  const source = document.querySelector('#professional-source');
  const label = document.querySelector('#level-label');
  if (!diagram || !source || !label) return;
  label.textContent = level.toUpperCase();
  source.textContent = diagrams[level];
  document.querySelectorAll('[data-level]').forEach((button) => {
    const active = button.dataset.level === level;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  renderMermaid(diagram, diagrams[level]);
}

function setupCopy() {
  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const source = document.querySelector(`#${button.dataset.copy}`)?.innerText || '';
      try {
        await navigator.clipboard.writeText(source);
        const original = button.textContent;
        button.textContent = 'Copied';
        window.setTimeout(() => { button.textContent = original; }, 1400);
      } catch {
        button.textContent = 'Select text';
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  window.mermaid?.initialize(mermaidConfig);
  document.querySelectorAll('[data-path]').forEach((button) => {
    button.addEventListener('click', () => setActivePath(button.dataset.path));
  });
  document.querySelectorAll('[data-step-button]').forEach((button) => {
    button.addEventListener('click', () => {
      const stepper = button.closest('[data-stepper]');
      setActiveStep(stepper, button.dataset.stepButton.split('-')[1]);
    });
  });
  document.querySelectorAll('[data-step-next]').forEach((button) => {
    button.addEventListener('click', () => {
      const stepper = document.querySelector(`[data-stepper="${button.dataset.stepNext}"]`);
      const current = Number(stepper.dataset.currentStep);
      if (current === 3) {
        showScreen('proof');
        return;
      }
      setActiveStep(stepper, current + 1);
    });
  });
  document.querySelectorAll('[data-step-prev]').forEach((button) => {
    button.addEventListener('click', () => {
      const stepper = document.querySelector(`[data-stepper="${button.dataset.stepPrev}"]`);
      setActiveStep(stepper, Number(stepper.dataset.currentStep) - 1);
    });
  });
  document.querySelectorAll('[data-level]').forEach((button) => {
    button.addEventListener('click', () => renderProfessional(button.dataset.level));
  });
  document.querySelectorAll('[data-wizard-next], [data-wizard-nav]').forEach((control) => {
    control.addEventListener('click', (event) => {
      event.preventDefault();
      showScreen(control.dataset.wizardNext || control.dataset.wizardNav);
    });
  });
  setupCopy();
  setActivePath(null);
  showScreen('intro');
});
