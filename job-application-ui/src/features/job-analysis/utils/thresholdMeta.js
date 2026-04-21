export const THRESHOLD_META = Object.freeze({
  pass: Object.freeze({
    key: 'pass',
    label: 'Pass',
    summary: 'Match — Package generated',
    tone: 'success',
    className: 'threshold--pass',
  }),

  caution: Object.freeze({
    key: 'caution',
    label: 'Caution',
    summary: 'Borderline match — Review recommended',
    tone: 'warning',
    className: 'threshold--caution',
  }),

  fail: Object.freeze({
    key: 'fail',
    label: 'Fail',
    summary: 'Low match — Package generated with caution',
    tone: 'danger',
    className: 'threshold--fail',
  }),
});

export const DIMENSION_META = Object.freeze({
  technical: Object.freeze({
    key: 'technical',
    label: 'Technical',
    max: 40,
  }),

  requirements: Object.freeze({
    key: 'requirements',
    label: 'Requirements',
    max: 25,
  }),

  role_fit: Object.freeze({
    key: 'role_fit',
    label: 'Role Fit',
    max: 20,
  }),

  location: Object.freeze({
    key: 'location',
    label: 'Location',
    max: 10,
  }),

  strategic: Object.freeze({
    key: 'strategic',
    label: 'Strategic',
    max: 5,
  }),
});

export function getThresholdMeta(threshold) {
  return THRESHOLD_META[threshold] || THRESHOLD_META.fail;
}

export function getDimensionMeta(key) {
  return DIMENSION_META[key] || null;
}

export function getDimensionKeys() {
  return Object.keys(DIMENSION_META);
}

export function getDimensionMax(key) {
  return DIMENSION_META[key]?.max ?? 0;
}

export function getThresholdSummary(threshold) {
  return getThresholdMeta(threshold).summary;
}

export function getThresholdLabel(threshold) {
  return getThresholdMeta(threshold).label;
}

export function getThresholdClassName(threshold) {
  return getThresholdMeta(threshold).className;
}