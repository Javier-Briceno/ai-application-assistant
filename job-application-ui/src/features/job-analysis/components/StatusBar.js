import { createElement, appendChildren, setText, toggleClass } from '../../../shared/utils/dom.js';

export function createStatusBar(initialStatus = {}) {
  const root = createElement('div', {
    className: buildClassName(Boolean(initialStatus.active)),
  });

  const dot = createElement('span', {
    className: 'status-bar__dot',
    attrs: {
      'aria-hidden': 'true',
    },
  });

  const text = createElement('span', {
    className: 'status-bar__text',
    text: initialStatus.text || '',
  });

  appendChildren(root, dot, text);

  return {
    element: root,
    refs: {
      root,
      dot,
      text,
    },
    setStatus(nextStatus = {}) {
      const nextText = typeof nextStatus.text === 'string' ? nextStatus.text : '';
      const isActive = Boolean(nextStatus.active);

      setText(text, nextText);
      toggleClass(root, 'status-bar--active', isActive);
    },
  };
}

function buildClassName(isActive) {
  return isActive ? 'status-bar status-bar--active' : 'status-bar';
}