let sequence = 0;

export function createId(prefix = 'id') {
  const safePrefix = normalizePrefix(prefix);
  const uniquePart = getUniquePart();

  return `${safePrefix}-${uniquePart}`;
}

export function createSectionId() {
  return createId('section');
}

export function createRenderedBlockId() {
  return createId('block');
}

export function createTempId() {
  return createId('temp');
}

export function createIdFactory(prefix = 'id') {
  const safePrefix = normalizePrefix(prefix);

  return function nextId() {
    return createId(safePrefix);
  };
}

function getUniquePart() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }

  sequence += 1;

  return [
    Date.now().toString(36),
    sequence.toString(36),
    Math.random().toString(36).slice(2, 8),
  ].join('');
}

function normalizePrefix(prefix) {
  const value = String(prefix ?? 'id')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return value || 'id';
}