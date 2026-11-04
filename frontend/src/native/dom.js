import { ApiError } from '../api/client.js';

export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function button(text, className, action) {
  const node = element('button', className, text);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}

export function link(text, href, className) {
  const node = element('a', className, text);
  node.href = href;
  return node;
}

export function field(labelText, name, options = {}) {
  const label = element('label');
  label.append(element('span', '', labelText));
  const input = element(options.multiline ? 'textarea' : options.options ? 'select' : 'input');
  input.name = name;
  if (options.type) input.type = options.type;
  if (options.required) input.required = true;
  if (options.maxLength) input.maxLength = options.maxLength;
  if (options.minLength) input.minLength = options.minLength;
  if (options.options) {
    for (const [value, text] of options.options) input.add(new Option(text, value));
  }
  input.value = options.value ?? '';
  label.append(input);
  return label;
}

export function errorNotice(error, retry) {
  const notice = element('div', 'error-notice');
  notice.setAttribute('role', 'alert');
  const details = element('div');
  details.append(element('strong', '', error instanceof Error ? error.message : 'Не удалось выполнить запрос'));
  if (error instanceof ApiError && error.requestId) {
    const copy = button(`Запрос: ${error.requestId}`, 'request-id', () => navigator.clipboard.writeText(error.requestId));
    copy.title = 'Скопировать идентификатор запроса';
    details.append(copy);
  }
  notice.append(details);
  if (retry) notice.append(button('Повторить', 'button button--secondary', retry));
  return notice;
}

export function showModal(title, content, signal) {
  const previous = document.activeElement;
  const dialog = element('dialog', 'modal');
  const header = element('header', 'modal-header');
  const heading = element('h2', '', title);
  heading.id = `modal-${Date.now()}`;
  dialog.setAttribute('aria-labelledby', heading.id);
  const close = button('×', 'icon-button', () => dialog.close());
  close.setAttribute('aria-label', 'Закрыть');
  header.append(heading, close);
  dialog.append(header, content);
  document.body.append(dialog);
  const onAbort = () => dialog.close();
  signal?.addEventListener('abort', onAbort, { once: true });
  dialog.addEventListener('close', () => { signal?.removeEventListener('abort', onAbort); dialog.remove(); if (!signal?.aborted) previous?.focus(); }, { once: true });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.showModal();
  close.focus();
  return dialog;
}

export function heading(eyebrow, title, description) {
  const section = element('section', 'page-heading');
  const div = element('div');
  div.append(element('p', 'eyebrow', eyebrow), element('h1', '', title), element('p', 'page-description', description));
  section.append(div);
  return section;
}
