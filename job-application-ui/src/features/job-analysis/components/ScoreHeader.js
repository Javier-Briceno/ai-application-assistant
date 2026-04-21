import { createElement, appendChildren } from '../../../shared/utils/dom.js';
import { getThresholdMeta, getDimensionMeta, getDimensionKeys } from '../utils/thresholdMeta.js';

export function createScoreHeader(score) {
  const meta = getThresholdMeta(score.threshold);

  const root = createElement('div', { className: 'score-header' });

  const company = createElement('div', {
    className: 'score-header__company',
    text: score.company,
  });

  const role = createElement('div', {
    className: 'score-header__role',
    text: score.role,
  });

  const row = createElement('div', { className: 'score-header__row' });

  const scoreNumber = createElement('div', {
    className: `score-number score-number--${score.threshold}`,
    text: String(score.value),
  });

  const barGroup = createElement('div', { className: 'score-bar-group' });
  const bar = createElement('div', { className: 'score-bar' });
  const barFill = createElement('div', {
    className: `score-bar__fill score-bar__fill--${score.threshold}`,
  });
  barFill.style.width = `${score.value}%`;

  const label = createElement('div', {
    className: `score-label score-label--${score.threshold}`,
    text: meta.summary,
  });

  appendChildren(bar, barFill);
  appendChildren(barGroup, bar, label);
  appendChildren(row, scoreNumber, barGroup);

  const dimsGrid = buildDimsGrid(score.dims);

  appendChildren(root, company, role, row, dimsGrid);

  return { element: root };
}

function buildDimsGrid(dims) {
  const grid = createElement('div', { className: 'dims-grid' });

  for (const key of getDimensionKeys()) {
    const meta = getDimensionMeta(key);
    const value = dims[key] ?? 0;

    const cell = createElement('div', { className: 'dim-cell' });

    const name = createElement('div', {
      className: 'dim-cell__name',
      text: meta.label,
    });

    const scoreEl = createElement('div', { className: 'dim-cell__score' });
    scoreEl.appendChild(document.createTextNode(String(value)));
    scoreEl.appendChild(
      createElement('span', { className: 'dim-cell__max', text: `/${meta.max}` })
    );

    appendChildren(cell, name, scoreEl);
    grid.appendChild(cell);
  }

  return grid;
}
