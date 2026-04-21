import { initApp } from './app/initApp.js';
import { mountApp } from './app/mountApp.js';
import { createSubmitJobAnalysis } from './features/job-analysis/controller/submitJobAnalysis.js';
import { createStatePanel } from './features/job-analysis/components/StatePanel.js';
import { createResultPanel } from './features/job-analysis/components/ResultPanel.js';
import { clearElement } from './shared/utils/dom.js';
import { UI_TEXT } from './shared/constants/uiText.js';

function bootstrap() {
  const root = document.getElementById('app');

  if (!root) {
    throw new Error('App root "#app" not found.');
  }

  const app = initApp();
  const { elements } = mountApp(root, app);

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

  const submitJobAnalysis = createSubmitJobAnalysis({
    app,
    elements,

    renderLoading() {
      mountStatePanel();
      statePanel.showLoading({
        glyph: UI_TEXT.loadingState.glyph,
        text: UI_TEXT.loadingState.message,
      });
    },

    renderResult(result) {
      clearElement(elements.resultRoot);
      const { element } = createResultPanel(result);
      elements.resultRoot.appendChild(element);
    },

    renderError(errorState) {
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
