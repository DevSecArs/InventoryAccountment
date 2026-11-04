export function shouldNavigate(event, anchor, origin) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (!anchor || anchor.hasAttribute('download') || (anchor.target && anchor.target.toLowerCase() !== '_self')) return false;
  const url = new URL(anchor.href, origin);
  return url.origin === origin && (url.protocol === 'http:' || url.protocol === 'https:');
}

export function startRouter(render) {
  const navigate = (url, replace = false) => {
    history[replace ? 'replaceState' : 'pushState'](null, '', url);
    render();
  };
  document.addEventListener('click', event => {
    const anchor = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!shouldNavigate(event, anchor, location.origin)) return;
    const url = new URL(anchor.href);
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    event.preventDefault();
    navigate(`${url.pathname}${url.search}${url.hash}`);
  });
  window.addEventListener('popstate', render);
  return navigate;
}
