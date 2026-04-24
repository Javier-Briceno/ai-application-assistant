import { createElement, appendChildren, show, hide, setDisabled } from '../../../shared/utils/dom.js';
import { UI_TEXT } from '../../../shared/constants/uiText.js';

export function createProfileSelector({
  profiles = [],
  activeProfileId = null,
  isLoading = false,
  error = null,
  onProfileChange,
  onCreateClick,
  onEditClick,
}) {
  const root = createElement('div', { className: 'profile-selector' });

  const label = createElement('label', {
    className: 'profile-selector__label',
    text: UI_TEXT.profiles.selectorLabel,
  });

  const row = createElement('div', { className: 'profile-selector__row' });

  const select = createElement('select', { className: 'profile-selector__select' });

  const editBtn = createElement('button', {
    className: 'profile-selector__edit-btn',
    text: UI_TEXT.profiles.editButton,
    attrs: { type: 'button' },
  });
  hide(editBtn);

  const createBtn = createElement('button', {
    className: 'profile-selector__create-btn',
    text: UI_TEXT.profiles.createButton,
    attrs: { type: 'button' },
  });

  const errorEl = createElement('p', { className: 'profile-selector__error' });
  hide(errorEl);

  appendChildren(row, select, editBtn, createBtn);
  appendChildren(root, label, row, errorEl);

  select.addEventListener('change', () => {
    const profileId = select.value ? Number(select.value) : null;
    profileId ? show(editBtn) : hide(editBtn);
    onProfileChange?.(profileId);
  });

  editBtn.addEventListener('click', () => {
    const profileId = select.value ? Number(select.value) : null;
    if (profileId) onEditClick?.(profileId);
  });

  createBtn.addEventListener('click', () => onCreateClick?.());

  // Initial render
  if (isLoading) {
    applyLoadingState(select, createBtn, editBtn);
  } else {
    renderOptions(select, profiles, activeProfileId);
    if (activeProfileId) show(editBtn);
  }
  if (error) showError(errorEl, error);

  return {
    element: root,

    updateProfiles(newProfiles, newActiveId) {
      renderOptions(select, newProfiles, newActiveId);
      newActiveId ? show(editBtn) : hide(editBtn);
      hideError(errorEl);
      setDisabled(select, false);
      setDisabled(createBtn, false);
      setDisabled(editBtn, false);
    },

    setLoading(loading) {
      if (loading) {
        applyLoadingState(select, createBtn, editBtn);
      } else {
        setDisabled(select, false);
        setDisabled(createBtn, false);
        setDisabled(editBtn, false);
      }
    },

    setError(message) {
      showError(errorEl, message);
    },

    setDisabledState(disabled) {
      setDisabled(select, disabled);
      setDisabled(createBtn, disabled);
      setDisabled(editBtn, disabled);
    },
  };
}

function renderOptions(select, profiles, activeProfileId) {
  select.replaceChildren();

  const placeholder = createElement('option', {
    text: UI_TEXT.profiles.noProfileSelected,
    attrs: { value: '' },
  });
  select.appendChild(placeholder);

  for (const profile of profiles) {
    const option = createElement('option', {
      text: profile.full_name,
      attrs: {
        value: String(profile.id),
        ...(profile.id === activeProfileId ? { selected: true } : {}),
      },
    });
    select.appendChild(option);
  }
}

function applyLoadingState(select, createBtn, editBtn) {
  setDisabled(select, true);
  setDisabled(createBtn, true);
  setDisabled(editBtn, true);
  select.replaceChildren();
  select.appendChild(
    createElement('option', {
      text: UI_TEXT.profiles.loadingProfiles,
      attrs: { value: '' },
    })
  );
}

function showError(errorEl, message) {
  errorEl.textContent = message;
  show(errorEl);
}

function hideError(errorEl) {
  errorEl.textContent = '';
  hide(errorEl);
}
