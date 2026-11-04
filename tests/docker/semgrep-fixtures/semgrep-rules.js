export function safeView(name) {
  const node = document.createElement('p');
  // ok: local.javascript.security.audit.dangerous-html
  node.textContent = name;
  return node;
}

export function unsafeView(value) {
  const node = document.createElement('div');
  // ruleid: local.javascript.security.audit.dangerous-html
  node.innerHTML = value;
  // ruleid: local.javascript.security.audit.dangerous-html
  node.insertAdjacentHTML('beforeend', value);
  // ruleid: local.javascript.security.audit.dangerous-html
  node.outerHTML = value;
  // ruleid: local.javascript.security.audit.dynamic-code
  eval(value);
  // ruleid: local.javascript.security.audit.dynamic-code
  new Function(value);
  // ruleid: local.javascript.security.audit.document-write
  document.write(value);
}
