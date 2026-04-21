export function $(selector, parent = document) {
  return parent.querySelector(selector);
}

export function $all(selector, parent = document) {
  return Array.from(parent.querySelectorAll(selector));
}

export function byId(id, parent = document) {
  return parent.getElementById(id);
}

export function clearElement(element) {
  if (!element) return;
  element.replaceChildren();
}

export function setText(element, value = '') {
  if (!element) return;
  element.textContent = String(value);
}

export function setHTML(element, html = '') {
  if (!element) return;
  element.innerHTML = html;
}

export function createElement(tag, options = {}) {
  const element = document.createElement(tag);

  const {
    className,
    text,
    html,
    attrs,
    dataset,
    children,
  } = options;

  if (className) {
    element.className = className;
  }

  if (text !== undefined) {
    element.textContent = String(text);
  }

  if (html !== undefined) {
    element.innerHTML = html;
  }

  if (attrs) {
    for (const [name, value] of Object.entries(attrs)) {
      if (value === false || value === null || value === undefined) continue;

      if (value === true) {
        element.setAttribute(name, '');
        continue;
      }

      element.setAttribute(name, String(value));
    }
  }

  if (dataset) {
    for (const [key, value] of Object.entries(dataset)) {
      element.dataset[key] = String(value);
    }
  }

  if (children?.length) {
    element.append(...children.filter(Boolean));
  }

  return element;
}

export function appendChildren(parent, ...children) {
  if (!parent) return;
  parent.append(...children.filter(Boolean));
}

export function toggleClass(element, className, force) {
  if (!element || !className) return;
  element.classList.toggle(className, force);
}

export function setDisabled(element, disabled = true) {
  if (!element) return;
  element.disabled = Boolean(disabled);
}

export function show(element) {
  if (!element) return;
  element.hidden = false;
}

export function hide(element) {
  if (!element) return;
  element.hidden = true;
}