import { API_ENDPOINTS, REQUEST_TIMEOUT_MS } from '../../../config/env.js';

export async function analyzePosting(postingText) {
  const posting = typeof postingText === 'string' ? postingText.trim() : '';

  if (!posting) {
    throw createApiError('EMPTY_POSTING', 'Job posting is empty.');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(API_ENDPOINTS.analyzePosting, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        chatInput: posting,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw createApiError(
        'HTTP_ERROR',
        `Request failed with status ${response.status}.`,
        { status: response.status }
      );
    }

    const data = await response.json();

    if (!data || typeof data !== 'object') {
      throw createApiError('INVALID_RESPONSE', 'Response is not valid JSON.');
    }

    if (typeof data.output !== 'string') {
      throw createApiError(
        'INVALID_RESPONSE',
        'Response JSON does not contain a valid "output" field.'
      );
    }

    return {
      output: data.output,
      cv_diff: typeof data.cv_diff === 'string' ? data.cv_diff.trim() : '',
      cv_markdown: typeof data.cv_markdown === 'string' ? data.cv_markdown.trim() : '',
    };
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw createApiError(
        'TIMEOUT',
        `Request timed out after ${REQUEST_TIMEOUT_MS} ms.`
      );
    }

    if (error?.code) {
      throw error;
    }

    throw createApiError(
      'NETWORK_ERROR',
      error?.message || 'Network request failed.'
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

function createApiError(code, message, details = {}) {
  const error = new Error(message);
  error.name = 'AnalyzePostingError';
  error.code = code;
  Object.assign(error, details);
  return error;
}