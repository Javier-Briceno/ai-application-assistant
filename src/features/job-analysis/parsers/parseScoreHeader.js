const DEFAULT_DIMS = Object.freeze({
  technical: 0,
  requirements: 0,
  role_fit: 0,
  location: 0,
  strategic: 0,
});

const DIMENSION_PATTERNS = Object.freeze({
  technical: [/^\|\s*Technisch\s*\|\s*(\d+)/i, /^\|\s*Technical\s*\|\s*(\d+)/i],
  requirements: [/^\|\s*Anforderungen\s*\|\s*(\d+)/i, /^\|\s*Requirements\s*\|\s*(\d+)/i],
  role_fit: [/^\|\s*Rollenfit\s*\|\s*(\d+)/i, /^\|\s*Role\s*Fit\s*\|\s*(\d+)/i],
  location: [/^\|\s*Standort\s*\|\s*(\d+)/i, /^\|\s*Location\s*\|\s*(\d+)/i],
  strategic: [/^\|\s*Strategisch\s*\|\s*(\d+)/i, /^\|\s*Strategic\s*\|\s*(\d+)/i],
});

export function parseScoreHeader(rawText) {
  const raw = normalizeText(rawText);
  const lines = raw.split('\n').map((line) => line.trim());

  const result = {
    company: '',
    role: '',
    score: 0,
    threshold: 'fail',
    dims: createEmptyDims(),
  };

  for (const line of lines) {
    if (!line) continue;

    if (!result.role) {
      const roleMatch = line.match(/^##\s+(.+)$/);
      if (roleMatch) {
        result.role = roleMatch[1].trim();
        continue;
      }
    }

    if (!result.company) {
      const companyMatch = line.match(/^\*\*(.+?)\*\*\s*·\s*Score:/i);
      if (companyMatch) {
        result.company = companyMatch[1].trim();
      }
    }

    if (result.score === 0) {
      const scoreMatch = line.match(/\bScore:\s*(\d{1,3})\/100\b/i);
      if (scoreMatch) {
        result.score = clampScore(Number.parseInt(scoreMatch[1], 10));
      }
    }

    const threshold = parseThreshold(line);
    if (threshold) {
      result.threshold = threshold;
    }

    for (const [key, patterns] of Object.entries(DIMENSION_PATTERNS)) {
      const value = matchDimensionValue(line, patterns);
      if (value !== null) {
        result.dims[key] = value;
      }
    }
  }

  return result;
}

function parseThreshold(line) {
  if (line.includes('✅')) return 'pass';
  if (line.includes('⚠️') || line.includes('⚠')) return 'caution';
  if (line.includes('❌')) return 'fail';

  if (/\bThreshold:\s*pass\b/i.test(line) || /\bMatch\b/i.test(line)) {
    return 'pass';
  }

  if (/\bThreshold:\s*caution\b/i.test(line) || /\bBorderline\b/i.test(line) || /\bGrenzfall\b/i.test(line)) {
    return 'caution';
  }

  if (/\bThreshold:\s*fail\b/i.test(line) || /\bNot recommended\b/i.test(line) || /\bNicht empfohlen\b/i.test(line)) {
    return 'fail';
  }

  return null;
}

function matchDimensionValue(line, patterns) {
  for (const pattern of patterns) {
    const match = line.match(pattern);
    if (match) {
      return Number.parseInt(match[1], 10);
    }
  }

  return null;
}

function createEmptyDims() {
  return {
    technical: 0,
    requirements: 0,
    role_fit: 0,
    location: 0,
    strategic: 0,
  };
}

function normalizeText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function clampScore(value) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}