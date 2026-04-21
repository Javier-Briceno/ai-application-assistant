// src/features/job-analysis/controller/submitJobAnalysis.js

import { analyzePosting } from '../api/analyzePosting.js';
import { parseWorkflowResponse } from '../parsers/parseWorkflowResponse.js';
import { UI_TEXT } from '../../../shared/constants/uiText.js';
import { setDisabled, setText, toggleClass } from '../../../shared/utils/dom.js';

export function createSubmitJobAnalysis({
  app,
  elements,
  renderLoading,
  renderResult,
  renderError,
  onSuccess,
  onFailure,
}) {
  if (!app?.state) {
    throw new Error('createSubmitJobAnalysis: app.state is required.');
  }

  if (!elements?.postingInput || !elements?.analyzeButton) {
    throw new Error(
      'createSubmitJobAnalysis: postingInput and analyzeButton are required.'
    );
  }

  const {
    postingInput,
    analyzeButton,
    statusBar,
    statusText,
  } = elements;

  return async function submitJobAnalysis() {
    if (app.state.isSubmitting) {
      return;
    }

    const posting = normalizeText(postingInput.value);

    if (!posting) {
      const errorState = createUiError('EMPTY_POSTING', UI_TEXT.errors.emptyPosting);

      app.state.posting = '';
      app.state.view = 'error';
      app.state.error = errorState;
      app.state.result = null;

      syncStatus(app.state, {
        statusBar,
        statusText,
        text: UI_TEXT.status.error,
        active: false,
      });

      renderError?.(errorState, app.state);
      onFailure?.(errorState, app.state);
      return;
    }

    app.state.posting = posting;
    app.state.isSubmitting = true;
    app.state.error = null;
    app.state.result = null;
    app.state.view = 'loading';

    setDisabled(analyzeButton, true);

    syncStatus(app.state, {
      statusBar,
      statusText,
      text: UI_TEXT.status.analyzing,
      active: true,
    });

    renderLoading?.(app.state);

    try {
      const payload = await analyzePosting(posting);
      const result = parseWorkflowResponse(payload);

      app.state.result = result;
      app.state.error = null;
      app.state.view = 'result';

      syncStatus(app.state, {
        statusBar,
        statusText,
        text: UI_TEXT.status.success,
        active: false,
      });

      renderResult?.(result, app.state);
      onSuccess?.(result, app.state);
    } catch (error) {
      const errorState = createUiError(
        error?.code || 'UNKNOWN_ERROR',
        mapErrorToUiMessage(error),
        error
      );

      app.state.result = null;
      app.state.error = errorState;
      app.state.view = 'error';

      syncStatus(app.state, {
        statusBar,
        statusText,
        text: UI_TEXT.status.error,
        active: false,
      });

      renderError?.(errorState, app.state);
      onFailure?.(errorState, app.state);
    } finally {
      app.state.isSubmitting = false;
      setDisabled(analyzeButton, false);
    }
  };
}

function syncStatus(state, { statusBar, statusText, text, active }) {
  state.status.text = text;
  state.status.active = active;

  if (statusText) {
    setText(statusText, text);
  }

  if (statusBar) {
    toggleClass(statusBar, 'status-bar--active', active);
  }
}

function mapErrorToUiMessage(error) {
  switch (error?.code) {
    case 'EMPTY_POSTING':
      return UI_TEXT.errors.emptyPosting;
    case 'TIMEOUT':
      return UI_TEXT.errors.timeout;
    case 'NETWORK_ERROR':
      return UI_TEXT.errors.network;
    case 'HTTP_ERROR':
    case 'INVALID_RESPONSE':
    default:
      return UI_TEXT.errors.generic;
  }
}

function createUiError(code, message, cause = null) {
  return {
    code,
    message,
    cause,
  };
}

function normalizeText(value) {
  return typeof value === 'string' ? value.trim() : '';
}