export function mountApp(root, app) {
  if (!root) {
    throw new Error('mountApp: root element is required.');
  }

  if (!app) {
    throw new Error('mountApp: app instance is required.');
  }

  const { ui } = app;

  root.innerHTML = `
    <main class="app-shell">
      <section class="panel panel--input">
        <header class="panel__header">
          <div>
            <h1 class="app-title">${escapeHtml(ui.branding.title)}</h1>
            <p class="app-subtitle">${escapeHtml(ui.branding.subtitle)}</p>
          </div>
        </header>

        <div class="input-panel">
          <label class="input-panel__label" for="job-posting-input">
            ${escapeHtml(ui.input.label)}
          </label>

          <textarea
            id="job-posting-input"
            class="input-panel__textarea"
            placeholder="${escapeHtml(ui.input.placeholder)}"
          ></textarea>

          <div class="input-panel__actions">
            <button
              id="analyze-button"
              class="input-panel__submit"
              type="button"
            >
              ${escapeHtml(ui.input.submitText)}
            </button>
          </div>
        </div>
      </section>

      <section class="panel panel--result">
        <div
          id="status-bar"
          class="status-bar ${ui.status.active ? 'status-bar--active' : ''}"
        >
          <span class="status-bar__dot" aria-hidden="true"></span>
          <span id="status-text" class="status-bar__text">
            ${escapeHtml(ui.status.text)}
          </span>
        </div>

        <div id="result-root" class="result-root">
          <div class="empty-state">
            <div class="empty-state__glyph" aria-hidden="true">
              ${escapeHtml(ui.emptyState.glyph)}
            </div>
            <p class="empty-state__text">
              ${escapeHtml(ui.emptyState.text)}
            </p>
          </div>
        </div>
      </section>
    </main>
  `;

  const elements = {
    root,
    postingInput: root.querySelector('#job-posting-input'),
    analyzeButton: root.querySelector('#analyze-button'),
    statusBar: root.querySelector('#status-bar'),
    statusText: root.querySelector('#status-text'),
    resultRoot: root.querySelector('#result-root'),
  };

  const cleanupGlobalListeners = app.registerGlobalListeners?.({
    textarea: elements.postingInput,
    onSubmit: () => {
      elements.analyzeButton?.click();
    },
  });

  return {
    elements,
    cleanup() {
      if (typeof cleanupGlobalListeners === 'function') {
        cleanupGlobalListeners();
      }
    },
  };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}