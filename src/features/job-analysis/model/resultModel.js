const DIMENSION_KEYS = [
  'technical',
  'requirements',
  'role_fit',
  'location',
  'strategic',
];

const DIMENSION_MAX = Object.freeze({
  technical: 40,
  requirements: 25,
  role_fit: 20,
  location: 10,
  strategic: 5,
});

const VALID_THRESHOLDS = ['pass', 'caution', 'fail'];
const VALID_SECTION_KINDS = ['markdown', 'diff', 'letter', 'unknown'];

export function createResultModel(input = {}) {
  const score = normalizeScore(input.score);
  const sections = normalizeSections(input.sections);

  return Object.freeze({
    raw: normalizeString(input.raw),
    company: normalizeString(input.company),
    role: normalizeString(input.role),
    language: normalizeLanguage(input.language),
    avatarUrl: normalizeString(input.avatarUrl),
    cvMarkdown: normalizeString(input.cvMarkdown),
    score,
    sections,
    cvDiff: findSectionByKey(sections, 'cv_diff'),
    coverLetter: findSectionByKey(sections, 'cover_letter'),
    meta: Object.freeze({
      hasContent: sections.length > 0,
      hasScore: score.value > 0 || Boolean(score.company || score.role),
      sectionCount: sections.length,
    }),
  });
}

export function createResultSection(input = {}) {
  const key = normalizeSectionKey(input.key);
  const title = normalizeString(input.title) || humanizeSectionKey(key);
  const markdown = normalizeNullableString(input.markdown);
  const text = normalizeString(input.text);
  const copyText = normalizeString(input.copyText || text || markdown || '');

  return Object.freeze({
    id: normalizeString(input.id),
    key,
    title,
    kind: normalizeSectionKind(input.kind, key),
    markdown,
    text,
    copyText,
  });
}

export function isResultModel(value) {
  return Boolean(
    value &&
      typeof value === 'object' &&
      value.score &&
      typeof value.score === 'object' &&
      Array.isArray(value.sections)
  );
}

export function getDimensionMax(key) {
  return DIMENSION_MAX[key] ?? 0;
}

export function getDimensionKeys() {
  return [...DIMENSION_KEYS];
}

function normalizeScore(input = {}) {
  const dimsInput = input.dims || {};

  const dims = Object.freeze({
    technical: normalizeDimensionScore(dimsInput.technical, 'technical'),
    requirements: normalizeDimensionScore(dimsInput.requirements, 'requirements'),
    role_fit: normalizeDimensionScore(dimsInput.role_fit, 'role_fit'),
    location: normalizeDimensionScore(dimsInput.location, 'location'),
    strategic: normalizeDimensionScore(dimsInput.strategic, 'strategic'),
  });

  return Object.freeze({
    company: normalizeString(input.company),
    role: normalizeString(input.role),
    value: clampNumber(input.value, 0, 100),
    threshold: normalizeThreshold(input.threshold),
    dims,
  });
}

function normalizeSections(sections) {
  if (!Array.isArray(sections)) {
    return Object.freeze([]);
  }

  return Object.freeze(
    sections
      .map((section) => createResultSection(section))
      .filter((section) => section.text || section.markdown)
  );
}

function findSectionByKey(sections, key) {
  return sections.find((section) => section.key === key) || null;
}

function normalizeDimensionScore(value, key) {
  return clampNumber(value, 0, getDimensionMax(key));
}

function normalizeThreshold(value) {
  return VALID_THRESHOLDS.includes(value) ? value : 'fail';
}

function normalizeSectionKind(value, key) {
  if (VALID_SECTION_KINDS.includes(value)) {
    return value;
  }

  if (key === 'cv_diff') return 'diff';
  if (key === 'cover_letter') return 'letter';

  return 'markdown';
}

function normalizeSectionKey(value) {
  const key = normalizeString(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');

  return key || 'unknown';
}

function humanizeSectionKey(key) {
  if (key === 'cv_diff') return 'CV Diff';
  if (key === 'cover_letter') return 'Cover Letter';

  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function normalizeLanguage(value) {
  const language = normalizeString(value).toLowerCase();
  return language === 'en' ? 'en' : 'de';
}

function normalizeNullableString(value) {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = normalizeString(value);
  return normalized || null;
}

function normalizeString(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function clampNumber(value, min, max) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return min;
  }

  return Math.min(Math.max(number, min), max);
}