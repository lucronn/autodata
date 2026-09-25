export const LOAD_STAGES = Object.freeze([
  Object.freeze({ key: 'year', label: 'Years', start: 0, end: 10 }),
  Object.freeze({ key: 'make', label: 'Makes', start: 10, end: 30 }),
  Object.freeze({ key: 'model', label: 'Models', start: 30, end: 50 }),
  Object.freeze({ key: 'configuration', label: 'Engine / trim', start: 50, end: 65 }),
  Object.freeze({ key: 'articles', label: 'Article catalog', start: 65, end: 95 }),
  Object.freeze({ key: 'article', label: 'Article', start: 95, end: 100 }),
]);

const fallback = LOAD_STAGES[0];

export function loadingProgress(key, { attempt = 0, attempts = 1, hydrating = false, complete = false } = {}) {
  const stage = LOAD_STAGES.find(item => item.key === key) || fallback;
  const safeAttempts = Math.max(1, Number(attempts) || 1);
  const safeAttempt = Math.max(0, Number(attempt) || 0);
  const span = stage.end - stage.start;
  let percent = stage.start;
  if (complete) percent = stage.end;
  else if (hydrating) {
    const ratio = Math.min(0.85, safeAttempt / safeAttempts);
    percent = Math.min(stage.end - 1, stage.start + Math.max(1, Math.round(span * ratio)));
  }
  return {
    ...stage,
    percent,
    step: LOAD_STAGES.indexOf(stage) + 1,
    total: LOAD_STAGES.length,
  };
}
