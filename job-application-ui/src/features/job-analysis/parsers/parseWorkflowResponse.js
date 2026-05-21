// src/features/job-analysis/parsers/parseWorkflowResponse.js

import { parseScoreHeader } from './parseScoreHeader.js';
import { stripHeader } from './stripHeader.js';
import { extractSections, createCvDiffSection } from './extractSections.js';
import { createResultModel } from '../model/resultModel.js';

export function parseWorkflowResponse(payload) {
  const safePayload = normalizePayload(payload);

  const rawOutput = safePayload.output;
  const cvDiff = safePayload.cv_diff;
  const cvMarkdown = safePayload.cv_markdown;
  const avatarUrl = safePayload.avatar_url;

  if (!rawOutput && !cvDiff) {
    return createEmptyResult();
  }

  const header = parseScoreHeader(rawOutput);
  const body = stripHeader(rawOutput);
  const language = detectLanguage(rawOutput);

  const bodySections = extractSections(body, {
    language,
    threshold: header.threshold,
  });
  const cvDiffSection = createCvDiffSection(cvDiff, { language, cvMarkdown });

  const sections = cvDiffSection
    ? [cvDiffSection, ...bodySections]
    : bodySections;

  return createResultModel({
    raw: rawOutput,
    company: header.company,
    role: header.role,
    language,
    avatarUrl,
    cvMarkdown,
    score: {
      company: header.company,
      role: header.role,
      value: header.score,
      threshold: header.threshold,
      dims: header.dims,
    },
    sections,
  });
}

function normalizePayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return {
      output: '',
      cv_diff: '',
    };
  }

  return {
    output: typeof payload.output === 'string' ? payload.output.trim() : '',
    cv_diff: typeof payload.cv_diff === 'string' ? payload.cv_diff.trim() : '',
    cv_markdown: typeof payload.cv_markdown === 'string' ? payload.cv_markdown.trim() : '',
    avatar_url: typeof payload.avatar_url === 'string' ? payload.avatar_url.trim() : '',
  };
}

function createEmptyResult() {
  return createResultModel({
    raw: '',
    company: '',
    role: '',
    language: 'de',
    score: {
      company: '',
      role: '',
      value: 0,
      threshold: 'fail',
      dims: {
        technical: 0,
        requirements: 0,
        role_fit: 0,
        location: 0,
        strategic: 0,
      },
    },
    sections: [],
  });
}

function detectLanguage(raw) {
  const text = normalizeText(raw).toLowerCase();

  if (
    text.includes('## cover letter') ||
    text.includes('| technical |') ||
    text.includes('| requirements |') ||
    text.includes('| role fit |') ||
    text.includes('| location |') ||
    text.includes('| strategic |')
  ) {
    return 'en';
  }

  return 'de';
}

function normalizeText(value) {
  return typeof value === 'string'
    ? value.replace(/\r\n?/g, '\n').trim()
    : '';
}
