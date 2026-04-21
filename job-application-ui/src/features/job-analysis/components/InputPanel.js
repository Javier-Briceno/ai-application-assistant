import { createElement, appendChildren } from '../../../shared/utils/dom.js';

export function createInputPanel(ui) {
  const wrapper = createElement('div', {
    className: 'input-panel',
  });

  const branding = createBranding(ui?.branding);

  const label = createElement('label', {
    className: 'input-panel__label',
    text: ui?.input?.label || '',
    attrs: {
      for: 'job-posting-input',
    },
  });

  const textarea = createElement('textarea', {
    className: 'input-panel__textarea',
    attrs: {
      id: 'job-posting-input',
      placeholder: ui?.input?.placeholder || '',
      rows: 18,
      spellcheck: 'false',
      autocomplete: 'off',
      autocapitalize: 'off',
    },
  });

  const actions = createElement('div', {
    className: 'input-panel__actions',
  });

  const submitButton = createElement('button', {
    className: 'input-panel__submit',
    text: ui?.input?.submitText || ui?.input?.submitButton || 'Analyze',
    attrs: {
      id: 'analyze-button',
      type: 'button',
    },
  });

  appendChildren(actions, submitButton);
  appendChildren(wrapper, branding, label, textarea, actions);

  return {
    element: wrapper,
    refs: {
      postingInput: textarea,
      analyzeButton: submitButton,
      label,
    },
  };
}

function createBranding(brandingUi) {
  const header = createElement('header', {
    className: 'input-panel__branding',
  });

  const logo = createElement('div', {
    className: 'input-panel__logo',
    text: brandingUi?.logoText || 'JA',
    attrs: {
      'aria-hidden': 'true',
    },
  });

  const textWrap = createElement('div', {
    className: 'input-panel__branding-text',
  });

  const title = createElement('h1', {
    className: 'app-title',
    text: brandingUi?.title || '',
  });

  const subtitle = createElement('p', {
    className: 'app-subtitle',
    text: brandingUi?.subtitle || '',
  });

  appendChildren(textWrap, title, subtitle);
  appendChildren(header, logo, textWrap);

  return header;
}