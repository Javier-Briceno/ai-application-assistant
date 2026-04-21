import {
  createElement,
  appendChildren,
  clearElement,
  setText,
  toggleClass,
} from '../../../shared/utils/dom.js';

export function createStatePanel(initialState = {}) {
  const root = createElement('div', {
    className: 'state-panel',
  });

  const card = createElement('div', {
    className: 'empty-state',
  });

  const glyph = createElement('div', {
    className: 'empty-state__glyph',
    text: initialState.glyph || '∅',
    attrs: {
      'aria-hidden': 'true',
    },
  });

  const text = createElement('p', {
    className: 'empty-state__text',
    text: initialState.text || '',
  });

  appendChildren(card, glyph, text);
  appendChildren(root, card);

  return {
    element: root,
    refs: {
      root,
      card,
      glyph,
      text,
    },

    showEmpty(state = {}) {
      applyState(card, glyph, text, {
        variant: 'empty',
        glyphText: state.glyph || '∅',
        message: state.text || '',
      });
    },

    showLoading(state = {}) {
      applyState(card, glyph, text, {
        variant: 'loading',
        glyphText: state.glyph || '◌',
        message: state.text || '',
      });
    },

    showError(state = {}) {
      applyState(card, glyph, text, {
        variant: 'error',
        glyphText: state.glyph || '!',
        message: state.text || '',
      });
    },

    clear() {
      clearElement(root);
    },
  };
}

function applyState(card, glyph, text, { variant, glyphText, message }) {
  resetVariants(card);

  toggleClass(card, 'state-panel--empty', variant === 'empty');
  toggleClass(card, 'state-panel--loading', variant === 'loading');
  toggleClass(card, 'state-panel--error', variant === 'error');

  setText(glyph, glyphText);
  setText(text, message);
}

function resetVariants(card) {
  card.classList.remove(
    'state-panel--empty',
    'state-panel--loading',
    'state-panel--error'
  );
}