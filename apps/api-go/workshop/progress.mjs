export const LOAD_STAGES = Object.freeze([
  Object.freeze({ key: 'year', label: 'Years', start: 0, end: 10 }),
  Object.freeze({ key: 'make', label: 'Makes', start: 10, end: 30 }),
  Object.freeze({ key: 'model', label: 'Models', start: 30, end: 50 }),
  Object.freeze({ key: 'configuration', label: 'Engine / trim', start: 50, end: 65 }),
  Object.freeze({ key: 'articles', label: 'Article catalog', start: 65, end: 95 }),
  Object.freeze({ key: 'article', label: 'Article', start: 95, end: 100 }),
]);

const fallback = LOAD_STAGES[0];

export function loadingProgress(key, { complete = false, catalogProgress = null } = {}) {
  const stage = LOAD_STAGES.find(item => item.key === key) || fallback;
  const processed = catalogProgress?.processed, total = catalogProgress?.total;
  const measurable = Number.isFinite(processed) && Number.isFinite(total) && total > 0 && processed >= 0 && processed <= total;
  return { ...stage, complete, percent: measurable ? Math.floor(processed / total * 100) : null, step: LOAD_STAGES.indexOf(stage) + 1, total: LOAD_STAGES.length };
}
