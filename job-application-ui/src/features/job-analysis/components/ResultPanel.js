import { createElement } from '../../../shared/utils/dom.js';
import { createScoreHeader } from './ScoreHeader.js';
import { createMarkdownContent } from './MarkdownContent.js';

/**
 * @param {Object} result  - result model (includes avatarUrl, cvMarkdown)
 */
export function createResultPanel(result) {
  const root = createElement('div', { className: 'result-panel' });

  const { element: scoreHeaderEl } = createScoreHeader(result.score);
  root.appendChild(scoreHeaderEl);

  if (result.sections.length > 0) {
    const { element: contentEl } = createMarkdownContent(result.sections, {
      avatarUrl: result.avatarUrl || '',
      cvMarkdown: result.cvMarkdown || result.cvDiff?.copyText || '',
    });
    root.appendChild(contentEl);
  }

  return { element: root };
}
