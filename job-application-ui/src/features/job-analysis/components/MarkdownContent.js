import { createElement } from '../../../shared/utils/dom.js';
import { renderMarkdown } from '../../../shared/lib/markdown.js';
import { copyToClipboard } from '../../../shared/utils/clipboard.js';

export function createMarkdownContent(sections) {
  const root = createElement('div', { className: 'content-body' });

  for (const section of sections) {
    const heading = buildHeading(section);
    const content = buildContent(section);
    root.appendChild(heading);
    root.appendChild(content);
  }

  return { element: root };
}

function buildHeading(section) {
  const h2 = createElement('h2');
  h2.appendChild(document.createTextNode(section.title));
  h2.appendChild(buildCopyButton(section));
  return h2;
}

function buildContent(section) {
  const div = createElement('div', { attrs: { id: section.id } });

  if (section.kind === 'letter') {
    const wrapper = createElement('div', { className: 'anschreiben-wrapper' });
    wrapper.innerHTML = renderMarkdown(section.text || '');
    div.appendChild(wrapper);
    return div;
  }

  if (section.kind === 'diff') {
    div.appendChild(buildDiffBlock(section.text || ''));
    return div;
  }

  div.innerHTML = renderMarkdown(section.text || '');
  return div;
}

function buildDiffBlock(text) {
  const block = createElement('div', { className: 'cv-diff' });

  for (const line of text.split('\n')) {
    const span = createElement('span', { className: classForDiffLine(line), text: line });
    block.appendChild(span);
    block.appendChild(document.createTextNode('\n'));
  }

  return block;
}

function classForDiffLine(line) {
  if (line.startsWith('+ ')) return 'cv-diff__line cv-diff__line--added';
  if (line.startsWith('- ')) return 'cv-diff__line cv-diff__line--removed';
  return 'cv-diff__line';
}

function buildCopyButton(section) {
  const btn = createElement('button', {
    className: 'copy-btn',
    text: 'Copy',
    attrs: { type: 'button' },
  });

  btn.addEventListener('click', async () => {
    try {
      await copyToClipboard(section.copyText || section.text || '');
      btn.textContent = 'Copied';
      btn.classList.add('copy-btn--copied');
      setTimeout(() => {
        btn.textContent = 'Copy';
        btn.classList.remove('copy-btn--copied');
      }, 2000);
    } catch (_) {
      // silent — clipboard may be unavailable in some contexts
    }
  });

  return btn;
}
