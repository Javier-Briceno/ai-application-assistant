import { createSectionId } from '../../../shared/utils/ids.js';

export function extractSections(body, options = {}) {
  const normalizedBody = normalizeText(body);
  const language = normalizeLanguage(options.language);
  const threshold = normalizeThreshold(options.threshold);

  if (!normalizedBody) {
    return [];
  }

  const headingMatches = [...normalizedBody.matchAll(/^##\s+(.+)$/gm)];

  if (headingMatches.length === 0) {
    const fallbackSection = getFallbackSectionMeta({ language, threshold });

    return [
      createSection({
        key: fallbackSection.key,
        title: fallbackSection.title,
        kind: fallbackSection.kind,
        markdown: normalizedBody,
        text: normalizedBody,
      }),
    ];
  }

  const sections = [];

  for (let index = 0; index < headingMatches.length; index += 1) {
    const match = headingMatches[index];
    const nextMatch = headingMatches[index + 1];

    const title = match[1].trim();
    const start = match.index ?? 0;
    const end = nextMatch?.index ?? normalizedBody.length;
    const block = normalizedBody.slice(start, end).trim();

    if (!block) continue;

    sections.push(
      createSection({
        key: getSectionKey(title),
        title,
        kind: getSectionKind(title),
        markdown: block,
        text: stripMarkdownHeading(block),
      })
    );
  }

  return sections;
}

export function createCvDiffSection(cvDiff, options = {}) {
  const text = normalizeText(cvDiff);
  const language = normalizeLanguage(options.language);

  if (!text) {
    return null;
  }

  return createSection({
    key: 'cv_diff',
    title: language === 'en' ? 'Curriculum Vitae' : 'Lebenslauf',
    kind: 'diff',
    markdown: null,
    text,
    copyText: normalizeText(options.cvMarkdown) || filterDiffForCopy(text),
  });
}

export function getSectionKey(title) {
  const normalized = normalizeText(title).toLowerCase();

  if (normalized.includes('cv-anpassungen')) return 'cv_diff';
  if (normalized === 'cv diff') return 'cv_diff';
  if (normalized.includes('anschreiben')) return 'cover_letter';
  if (normalized.includes('cover letter')) return 'cover_letter';

  return (
    normalized
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'unknown'
  );
}

export function getSectionKind(title) {
  const key = getSectionKey(title);

  if (key === 'cv_diff') return 'diff';
  if (key === 'cover_letter') return 'letter';

  return 'markdown';
}

function createSection({ key, title, kind, markdown, text, copyText }) {
  return {
    id: createSectionId(),
    key,
    title,
    kind,
    markdown,
    text,
    copyText: normalizeText(copyText ?? text ?? markdown ?? ''),
  };
}

function filterDiffForCopy(text) {
  return text
    .split('\n')
    .filter((line) => !line.startsWith('- '))
    .map((line) => (line.startsWith('+ ') ? line.slice(2) : line))
    .join('\n')
    .trim();
}

function stripMarkdownHeading(block) {
  return block.replace(/^##\s+.+$/m, '').trim();
}

function normalizeLanguage(value) {
  return String(value || 'de').toLowerCase() === 'en' ? 'en' : 'de';
}

function normalizeThreshold(value) {
  return ['pass', 'caution', 'fail'].includes(value) ? value : 'fail';
}

function getFallbackSectionMeta({ language, threshold }) {
  if (threshold === 'fail') {
    return {
      key: 'gap_analysis',
      title: language === 'en' ? 'Gap Analysis' : 'Gap-Analyse',
      kind: 'markdown',
    };
  }

  return {
    key: 'cover_letter',
    title: language === 'en' ? 'Cover Letter' : 'Anschreiben',
    kind: 'letter',
  };
}

function normalizeText(value) {
  return typeof value === 'string'
    ? value.replace(/\r\n?/g, '\n').trim()
    : '';
}
