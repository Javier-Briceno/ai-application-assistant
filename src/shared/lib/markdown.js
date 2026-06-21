let isConfigured = false;

export function renderMarkdown(markdownText) {
  const source = normalizeMarkdown(markdownText);
  const marked = getMarkedInstance();

  ensureMarkedConfigured(marked);

  return marked.parse(source);
}

export function hasMarkdownParser() {
  return Boolean(globalThis.marked);
}

export function configureMarkdown(options = {}) {
  const marked = getMarkedInstance();

  if (typeof marked.setOptions === 'function') {
    marked.setOptions({
      breaks: true,
      gfm: true,
      ...options,
    });
  }

  isConfigured = true;
}

function ensureMarkedConfigured(marked) {
  if (isConfigured) return;

  if (typeof marked.setOptions === 'function') {
    marked.setOptions({
      breaks: true,
      gfm: true,
    });
  }

  isConfigured = true;
}

function getMarkedInstance() {
  const marked = globalThis.marked;

  if (!marked || typeof marked.parse !== 'function') {
    throw new Error(
      'Markdown parser not available. Make sure marked is loaded before the app starts.'
    );
  }

  return marked;
}

function normalizeMarkdown(value) {
  return typeof value === 'string' ? value.trim() : '';
}