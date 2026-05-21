import { createElement, appendChildren, setDisabled, setText } from '../../../shared/utils/dom.js';
import { UI_TEXT } from '../../../shared/constants/uiText.js';

const FIELDS = [
  { key: 'full_name',       tag: 'input',    type: 'text',  required: true,  rows: null },
  { key: 'career_target',   tag: 'input',    type: 'text',  required: true,  rows: null },
  { key: 'cv_text',         tag: 'textarea', type: null,    required: true,  rows: 12   },
  { key: 'guide_text_de',   tag: 'textarea', type: null,    required: true,  rows: 6    },
  { key: 'guide_text_en',   tag: 'textarea', type: null,    required: true,  rows: 6    },
  { key: 'market_research', tag: 'textarea', type: null,    required: true,  rows: 12   },
  { key: 'email',           tag: 'input',    type: 'email', required: false, rows: null },
  { key: 'phone',           tag: 'input',    type: 'text',  required: false, rows: null },
  { key: 'location',        tag: 'input',    type: 'text',  required: false, rows: null },
  { key: 'linkedin_url',    tag: 'input',    type: 'url',   required: false, rows: null },
  { key: 'github_url',      tag: 'input',    type: 'url',   required: false, rows: null },
];

function resizeAndEncode(file, maxWidth = 400) {
  return new Promise(resolve => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, maxWidth / img.width);
      const canvas = document.createElement('canvas');
      canvas.width  = img.width  * scale;
      canvas.height = img.height * scale;
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    img.src = url;
  });
}

export function createProfileModal({ onSave, onClose }) {
  let currentProfile = null;
  let slowSaveTimer = null;
  let hiddenAvatarValue = '';

  // Structure
  const modal = createElement('div', {
    className: 'profile-modal',
    attrs: { hidden: true },
  });
  const backdrop = createElement('div', { className: 'profile-modal__backdrop' });
  const panel = createElement('div', { className: 'profile-modal__panel' });

  // Header
  const header = createElement('header', { className: 'profile-modal__header' });
  const title = createElement('h2', {
    className: 'profile-modal__title',
    text: UI_TEXT.profiles.createTitle,
  });
  const closeBtn = createElement('button', {
    className: 'profile-modal__close',
    text: '×',
    attrs: { type: 'button', 'aria-label': 'Close' },
  });
  appendChildren(header, title, closeBtn);

  // Body
  const body = createElement('div', { className: 'profile-modal__body' });

  // Avatar upload
  const avatarWrapper = createElement('div', { className: 'profile-modal__field' });
  const avatarLabel = createElement('label', { text: 'Photo' });

  const avatarPreview = document.createElement('img');
  avatarPreview.className = 'profile-modal__avatar-preview';
  avatarPreview.alt = 'Profile photo preview';
  avatarPreview.style.display = 'none';

  const fileInput = createElement('input', {
    attrs: { type: 'file', accept: 'image/*' },
  });

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    if (file.size > 500_000) {
      alert('Please use an image under 500KB.');
      fileInput.value = '';
      return;
    }
    hiddenAvatarValue = await resizeAndEncode(file);
    avatarPreview.src = hiddenAvatarValue;
    avatarPreview.style.display = 'block';
  });

  appendChildren(avatarWrapper, avatarLabel, avatarPreview, fileInput);
  body.appendChild(avatarWrapper);

  // Text / textarea fields
  const fieldRefs = {};
  for (const field of FIELDS) {
    const wrapper = createElement('div', { className: 'profile-modal__field' });
    const fieldLabel = createElement('label', {
      text: UI_TEXT.profiles.fields[field.key],
      attrs: { for: `pf-${field.key}` },
    });

    const input =
      field.tag === 'textarea'
        ? createElement('textarea', {
            attrs: {
              id: `pf-${field.key}`,
              rows: field.rows,
              ...(field.required ? { required: true } : {}),
            },
          })
        : createElement('input', {
            attrs: {
              id: `pf-${field.key}`,
              type: field.type,
              ...(field.required ? { required: true } : {}),
            },
          });

    fieldRefs[field.key] = input;
    appendChildren(wrapper, fieldLabel, input);
    body.appendChild(wrapper);
  }

  // Footer
  const footer = createElement('footer', { className: 'profile-modal__footer' });
  const statusEl = createElement('p', { className: 'profile-modal__status' });
  const actions = createElement('div', { className: 'profile-modal__actions' });
  const cancelBtn = createElement('button', {
    className: 'profile-modal__cancel',
    text: UI_TEXT.profiles.cancelButton,
    attrs: { type: 'button' },
  });
  const saveBtn = createElement('button', {
    className: 'profile-modal__save',
    text: UI_TEXT.profiles.saveButton,
    attrs: { type: 'button' },
  });
  appendChildren(actions, cancelBtn, saveBtn);
  appendChildren(footer, statusEl, actions);

  appendChildren(panel, header, body, footer);
  appendChildren(modal, backdrop, panel);

  // Close
  function close() {
    modal.hidden = true;
    clearTimeout(slowSaveTimer);
    currentProfile = null;
    document.removeEventListener('keydown', handleEscape);
    onClose?.();
  }

  function handleEscape(e) {
    if (e.key === 'Escape') close();
  }

  closeBtn.addEventListener('click', close);
  cancelBtn.addEventListener('click', close);
  backdrop.addEventListener('click', close);

  // Save
  saveBtn.addEventListener('click', async () => {
    const data = collectFormData(fieldRefs);
    if (hiddenAvatarValue) data.avatar_url = hiddenAvatarValue;

    if (currentProfile?.id) {
      data.profile_id = currentProfile.id;
    }

    setDisabled(saveBtn, true);
    setText(saveBtn, UI_TEXT.profiles.savingButton);
    statusEl.textContent = '';
    statusEl.className = 'profile-modal__status';

    slowSaveTimer = setTimeout(() => {
      statusEl.textContent = 'Saving... this may take a few minutes';
    }, 5000);

    try {
      await onSave(data);
      clearTimeout(slowSaveTimer);
      close();
    } catch (error) {
      clearTimeout(slowSaveTimer);
      statusEl.textContent = error?.message || 'Save failed. Please try again.';
      statusEl.className = 'profile-modal__status profile-modal__status--error';
      setDisabled(saveBtn, false);
      setText(saveBtn, UI_TEXT.profiles.saveButton);
    }
  });

  return {
    element: modal,

    open(profile = null) {
      currentProfile = profile;
      hiddenAvatarValue = profile?.avatar_url || '';

      setText(
        title,
        profile ? UI_TEXT.profiles.editTitle : UI_TEXT.profiles.createTitle
      );

      for (const field of FIELDS) {
        fieldRefs[field.key].value = profile?.[field.key] ?? '';
      }

      if (hiddenAvatarValue) {
        avatarPreview.src = hiddenAvatarValue;
        avatarPreview.style.display = 'block';
      } else {
        avatarPreview.src = '';
        avatarPreview.style.display = 'none';
      }
      fileInput.value = '';

      setDisabled(saveBtn, false);
      setText(saveBtn, UI_TEXT.profiles.saveButton);
      statusEl.textContent = '';
      statusEl.className = 'profile-modal__status';

      modal.hidden = false;
      document.addEventListener('keydown', handleEscape);
      fieldRefs['full_name']?.focus();
    },

    close,
  };
}

function collectFormData(fieldRefs) {
  const data = {};
  for (const field of FIELDS) {
    const value = fieldRefs[field.key]?.value?.trim() ?? '';
    if (value) data[field.key] = value;
  }
  return data;
}
