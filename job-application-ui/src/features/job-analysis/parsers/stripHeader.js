export function stripHeader(rawText) {
  const raw = normalizeText(rawText);

  if (!raw) {
    return '';
  }

  const lines = raw.split('\n');
  const boundaryIndex = findHeaderBoundary(lines);

  if (boundaryIndex === -1) {
    return raw;
  }

  return lines.slice(boundaryIndex + 1).join('\n').trim();
}

function findHeaderBoundary(lines) {
  let sawRole = false;
  let sawScoreLine = false;
  let sawTableHeader = false;
  let sawTableSeparator = false;
  let dimensionRowCount = 0;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();

    if (!line) {
      continue;
    }

    if (!sawRole && isRoleLine(line)) {
      sawRole = true;
      continue;
    }

    if (sawRole && !sawScoreLine && isScoreLine(line)) {
      sawScoreLine = true;
      continue;
    }

    if (sawScoreLine && !sawTableHeader && isTableHeaderLine(line)) {
      sawTableHeader = true;
      continue;
    }

    if (sawTableHeader && !sawTableSeparator && isTableSeparatorLine(line)) {
      sawTableSeparator = true;
      continue;
    }

    if (sawTableSeparator && isDimensionRow(line)) {
      dimensionRowCount += 1;
      continue;
    }

    if (
      sawRole &&
      sawScoreLine &&
      sawTableHeader &&
      sawTableSeparator &&
      dimensionRowCount > 0 &&
      line === '---'
    ) {
      return index;
    }
  }

  return findFirstStandaloneRule(lines);
}

function isRoleLine(line) {
  return /^##\s+.+$/.test(line);
}

function isScoreLine(line) {
  return /^\*\*.+?\*\*\s*·\s*Score:\s*\d{1,3}\/100\b/i.test(line);
}

function isTableHeaderLine(line) {
  return /^\|\s*Dimension\s*\|\s*Score\s*\|\s*Max\s*\|$/i.test(line);
}

function isTableSeparatorLine(line) {
  return /^\|\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|$/.test(line);
}

function isDimensionRow(line) {
  return /^\|\s*.+?\s*\|\s*\d+\s*\|\s*\d+\s*\|$/.test(line);
}

function findFirstStandaloneRule(lines) {
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].trim() === '---') {
      return index;
    }
  }

  return -1;
}

function normalizeText(value) {
  return typeof value === 'string'
    ? value.replace(/\r\n?/g, '\n').trim()
    : '';
}