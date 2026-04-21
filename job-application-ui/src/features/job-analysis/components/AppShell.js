// src/features/job-analysis/components/AppShell.js

import { createElement, appendChildren } from '../../../shared/utils/dom.js';

export function createAppShell() {
  const shell = createElement('main', {
    className: 'app-shell',
  });

  const inputPanelSection = createElement('section', {
    className: 'panel panel--input',
  });

  const resultPanelSection = createElement('section', {
    className: 'panel panel--result',
  });

  const inputMount = createElement('div', {
    className: 'app-shell__input-mount',
    attrs: {
      'data-slot': 'input-panel',
    },
  });

  const statusMount = createElement('div', {
    className: 'app-shell__status-mount',
    attrs: {
      'data-slot': 'status-bar',
    },
  });

  const resultMount = createElement('div', {
    className: 'app-shell__result-mount result-root',
    attrs: {
      'data-slot': 'result-panel',
    },
  });

  appendChildren(inputPanelSection, inputMount);
  appendChildren(resultPanelSection, statusMount, resultMount);
  appendChildren(shell, inputPanelSection, resultPanelSection);

  return {
    element: shell,
    refs: {
      inputMount,
      statusMount,
      resultMount,
      inputPanelSection,
      resultPanelSection,
    },
  };
}