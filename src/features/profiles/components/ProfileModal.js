import { createElement, appendChildren, setDisabled, setText } from '../../../shared/utils/dom.js';
import { UI_TEXT } from '../../../shared/constants/uiText.js';

// ─── Required fields for create mode (edit mode has no required fields) ────────

const CREATE_REQUIRED = new Set([
  'first_name', 'last_name', 'career_target', 'cv_text', 'market_research',
  'street_address', 'postal_code', 'city', 'email', 'phone_country_code', 'phone_number',
]);

// ─── Helper: create one labeled field, register in fieldRefs ──────────────────
//
// tag     — 'input' | 'textarea'
// attrs   — any HTML attributes (type, rows, placeholder, …)
// Note: never set required here — open() drives it dynamically per mode

function makeField(fieldRefs, key, labelText, tag, attrs = {}) {
  const wrapper = createElement('div', { className: 'profile-modal__field' });
  const label = createElement('label', {
    text: labelText,
    attrs: { for: `pf-${key}` },
  });
  const input = createElement(tag, {
    attrs: { id: `pf-${key}`, ...attrs },
  });
  fieldRefs[key] = input;
  appendChildren(wrapper, label, input);
  return wrapper;
}

// ─── Photo resize helper ──────────────────────────────────────────────────────

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

// ─── Modal factory ────────────────────────────────────────────────────────────

export function createProfileModal({ onSave, onClose }) {
  let currentProfile = null;
  let slowSaveTimer  = null;
  let hiddenAvatarValue = '';

  // Structure
  const modal = createElement('div', {
    className: 'profile-modal',
    attrs: { hidden: true },
  });
  const backdrop = createElement('div', { className: 'profile-modal__backdrop' });
  const panel    = createElement('div', { className: 'profile-modal__panel' });

  // Header
  const header   = createElement('header', { className: 'profile-modal__header' });
  const title    = createElement('h2', {
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

  // ── Avatar upload ──────────────────────────────────────────────────────────
  const avatarWrapper = createElement('div', { className: 'profile-modal__field' });
  const avatarLabel   = createElement('label', { text: 'Photo' });

  const avatarPreview = document.createElement('img');
  avatarPreview.className   = 'profile-modal__avatar-preview';
  avatarPreview.alt         = 'Profile photo preview';
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

  // ── Form fields ────────────────────────────────────────────────────────────
  const F = UI_TEXT.profiles.fields;
  const fieldRefs = {};

  // 1. Name row: [ First Name ] [ Last Name ]
  const nameRow = createElement('div', { className: 'profile-modal__field-row' });
  nameRow.appendChild(makeField(fieldRefs, 'first_name', F.first_name, 'input',
    { type: 'text', placeholder: 'Javier' }));
  nameRow.appendChild(makeField(fieldRefs, 'last_name', F.last_name, 'input',
    { type: 'text', placeholder: 'Briceño' }));
  body.appendChild(nameRow);

  // 2. Career Target
  body.appendChild(makeField(fieldRefs, 'career_target', F.career_target, 'input', {
    type: 'text',
    placeholder: 'Data Engineer Werkstudent — Python, SQL, Airflow',
  }));

  // 3. CV Text
  body.appendChild(makeField(fieldRefs, 'cv_text', F.cv_text, 'textarea',
    { rows: 12 }));

  // 4. Market Research
  body.appendChild(makeField(fieldRefs, 'market_research', F.market_research, 'textarea', {
    rows: 12,
    placeholder: 'Paste commute times, salary research, target cities, role demand notes, etc.',
  }));

  // 5. Email
  body.appendChild(makeField(fieldRefs, 'email', F.email, 'input',
    { type: 'email' }));

  // 6. Phone row: [ Country Code (~80px) ] [ Phone Number ]
  const phoneRow = createElement('div', { className: 'profile-modal__field-row' });
  const ccField  = makeField(fieldRefs, 'phone_country_code', F.phone_country_code, 'input',
    { type: 'text', placeholder: '+49' });
  ccField.classList.add('profile-modal__field--w80');
  phoneRow.appendChild(ccField);
  phoneRow.appendChild(makeField(fieldRefs, 'phone_number', F.phone_number, 'input',
    { type: 'text', placeholder: '151 23456789' }));
  body.appendChild(phoneRow);

  // 7. Street Address (full width)
  body.appendChild(makeField(fieldRefs, 'street_address', F.street_address, 'input',
    { type: 'text', placeholder: 'Musterstraße 12' }));

  // 8. Address row: [ Postal Code (~120px) ] [ City ]
  const addressRow  = createElement('div', { className: 'profile-modal__field-row' });
  const postalField = makeField(fieldRefs, 'postal_code', F.postal_code, 'input',
    { type: 'text', placeholder: '57076' });
  postalField.classList.add('profile-modal__field--w120');
  addressRow.appendChild(postalField);
  addressRow.appendChild(makeField(fieldRefs, 'city', F.city, 'input',
    { type: 'text', placeholder: 'Siegen' }));
  body.appendChild(addressRow);

  // 9. LinkedIn URL
  body.appendChild(makeField(fieldRefs, 'linkedin_url', F.linkedin_url, 'input',
    { type: 'url' }));

  // 10. GitHub URL
  body.appendChild(makeField(fieldRefs, 'github_url', F.github_url, 'input',
    { type: 'url' }));

  // ── Footer ─────────────────────────────────────────────────────────────────
  const footer    = createElement('footer', { className: 'profile-modal__footer' });
  const statusEl  = createElement('p',      { className: 'profile-modal__status' });
  const actions   = createElement('div',    { className: 'profile-modal__actions' });
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

  // ── Close ──────────────────────────────────────────────────────────────────
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

  // ── Save ───────────────────────────────────────────────────────────────────
  saveBtn.addEventListener('click', async () => {
    const data = collectFormData(fieldRefs);
    if (hiddenAvatarValue) data.avatar_url = hiddenAvatarValue;
    if (currentProfile?.id) data.profile_id = currentProfile.id;

    setDisabled(saveBtn, true);
    setText(saveBtn, UI_TEXT.profiles.savingButton);
    statusEl.textContent = '';
    statusEl.className   = 'profile-modal__status';

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
      statusEl.className   = 'profile-modal__status profile-modal__status--error';
      setDisabled(saveBtn, false);
      setText(saveBtn, UI_TEXT.profiles.saveButton);
    }
  });

  // ── Public API ─────────────────────────────────────────────────────────────
  return {
    element: modal,

    open(profile = null) {
      currentProfile    = profile;
      hiddenAvatarValue = profile?.avatar_url || '';

      setText(title, profile ? UI_TEXT.profiles.editTitle : UI_TEXT.profiles.createTitle);

      // Prefill all fields — composite fields handled explicitly
      fieldRefs.first_name.value         = profile?.first_name         ?? '';
      fieldRefs.last_name.value          = profile?.last_name          ?? '';
      fieldRefs.career_target.value      = profile?.career_target      ?? '';
      fieldRefs.cv_text.value            = profile?.cv_text            ?? '';
      fieldRefs.market_research.value    = profile?.market_research    ?? '';
      fieldRefs.email.value              = profile?.email              ?? '';
      fieldRefs.phone_country_code.value = profile?.phone_country_code ?? '+49';
      fieldRefs.phone_number.value       = profile?.phone_number       ?? '';
      fieldRefs.street_address.value     = profile?.street_address     ?? '';
      fieldRefs.postal_code.value        = profile?.postal_code        ?? '';
      fieldRefs.city.value               = profile?.city               ?? '';
      fieldRefs.linkedin_url.value       = profile?.linkedin_url       ?? '';
      fieldRefs.github_url.value         = profile?.github_url         ?? '';

      // Required state: all CREATE_REQUIRED fields are required in create mode,
      // no fields are required in edit mode.
      const isCreate = profile === null;
      for (const [key, input] of Object.entries(fieldRefs)) {
        const shouldRequire = isCreate && CREATE_REQUIRED.has(key);
        input.required = shouldRequire;
        input.closest('.profile-modal__field')
             ?.classList.toggle('profile-modal__field--required', shouldRequire);
      }

      if (hiddenAvatarValue) {
        avatarPreview.src           = hiddenAvatarValue;
        avatarPreview.style.display = 'block';
      } else {
        avatarPreview.src           = '';
        avatarPreview.style.display = 'none';
      }
      fileInput.value = '';

      setDisabled(saveBtn, false);
      setText(saveBtn, UI_TEXT.profiles.saveButton);
      statusEl.textContent = '';
      statusEl.className   = 'profile-modal__status';

      modal.hidden = false;
      document.addEventListener('keydown', handleEscape);
      fieldRefs.first_name?.focus();
    },

    close,
  };
}

// ─── Collect form data ────────────────────────────────────────────────────────
//
// Explicit key list — guarantees no deprecated fields (full_name, phone,
// location) ever appear in the payload sent to the webhook.

function collectFormData(fieldRefs) {
  const PAYLOAD_KEYS = [
    'first_name', 'last_name',
    'career_target', 'cv_text', 'market_research',
    'email',
    'phone_country_code', 'phone_number',
    'street_address', 'postal_code', 'city',
    'linkedin_url', 'github_url',
  ];
  const data = {};
  for (const key of PAYLOAD_KEYS) {
    const value = fieldRefs[key]?.value?.trim() ?? '';
    if (value) data[key] = value;
  }
  return data;
}
