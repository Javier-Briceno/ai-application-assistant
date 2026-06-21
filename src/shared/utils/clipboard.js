export async function copyToClipboard(text) {
  const value = normalizeClipboardText(text);

  if (!value) {
    throw createClipboardError('EMPTY_TEXT', 'There is no text to copy.');
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (error) {
      // sigue al fallback
    }
  }

  return copyWithFallback(value);
}

function copyWithFallback(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  textarea.style.left = '-9999px';

  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    const success = document.execCommand('copy');

    if (!success) {
      throw createClipboardError(
        'COPY_FAILED',
        'The browser could not copy the text.'
      );
    }

    return true;
  } catch (error) {
    if (error?.code) {
      throw error;
    }

    throw createClipboardError(
      'COPY_FAILED',
      error?.message || 'The browser could not copy the text.'
    );
  } finally {
    document.body.removeChild(textarea);
  }
}

function normalizeClipboardText(text) {
  return typeof text === 'string' ? text.trim() : '';
}

function createClipboardError(code, message) {
  const error = new Error(message);
  error.name = 'ClipboardError';
  error.code = code;
  return error;
}