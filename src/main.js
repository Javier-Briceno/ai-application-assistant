import { initApp } from './app/initApp.js';
import { mountApp } from './app/mountApp.js';
import { createSubmitJobAnalysis } from './features/job-analysis/controller/submitJobAnalysis.js';
import { createStatePanel } from './features/job-analysis/components/StatePanel.js';
import { createResultPanel } from './features/job-analysis/components/ResultPanel.js';
import { createProfileSelector } from './features/profiles/components/ProfileSelector.js';
import { createProfileModal } from './features/profiles/components/ProfileModal.js';
import { createProfileController } from './features/profiles/controller/profileController.js';
import { clearElement } from './shared/utils/dom.js';
import { UI_TEXT } from './shared/constants/uiText.js';

function bootstrap() {
  const root = document.getElementById('app');

  if (!root) {
    throw new Error('App root "#app" not found.');
  }

  const app = initApp();
  const { elements } = mountApp(root, app);

  // ── Result area ────────────────────────────────────────────────────────────

  const statePanel = createStatePanel({
    glyph: UI_TEXT.emptyState.glyph,
    text: UI_TEXT.emptyState.message,
  });

  function mountStatePanel() {
    if (!elements.resultRoot.contains(statePanel.element)) {
      clearElement(elements.resultRoot);
      elements.resultRoot.appendChild(statePanel.element);
    }
  }

  mountStatePanel();

  // ── Profiles ───────────────────────────────────────────────────────────────

  // profileController is assigned after modal and selector are created.
  // Callbacks use a closure so by the time they fire, the variable is set.
  let profileController;

  const profileModal = createProfileModal({
    onSave: (profileData) => profileController.onSave(profileData),
    onClose: () => {},
  });
  document.body.appendChild(profileModal.element);

  const profileSelector = createProfileSelector({
    profiles: [],
    activeProfileId: null,
    isLoading: true,
    error: null,
    onProfileChange: (profileId) => profileController.onProfileChange(profileId),
    onCreateClick: () => profileController.onCreateClick(),
    onEditClick: (profileId) => profileController.onEditClick(profileId),
  });

  // Insert between branding header and input panel div
  const inputPanelSection = elements.root.querySelector('.panel--input');
  const inputPanelDiv = inputPanelSection.querySelector('.input-panel');
  inputPanelSection.insertBefore(profileSelector.element, inputPanelDiv);

  profileController = createProfileController({ app, profileSelector, profileModal });

  // ── Submit job analysis ────────────────────────────────────────────────────

  const submitJobAnalysis = createSubmitJobAnalysis({
    app,
    elements,

    renderLoading() {
      profileSelector.setDisabledState(true);
      mountStatePanel();
      statePanel.showLoading({
        glyph: UI_TEXT.loadingState.glyph,
        text: UI_TEXT.loadingState.message,
      });
    },

    renderResult(result) {
      profileSelector.setDisabledState(false);
      clearElement(elements.resultRoot);
      const { element } = createResultPanel(result);
      elements.resultRoot.appendChild(element);
    },

    renderError(errorState) {
      profileSelector.setDisabledState(false);
      mountStatePanel();
      statePanel.showError({
        glyph: '×',
        text: errorState.message,
      });
    },
  });

  elements.analyzeButton.addEventListener('click', submitJobAnalysis);
}

bootstrap();
