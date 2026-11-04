import { getCurrentUser, logout } from '../api/auth.js';
import { ApiError, setCsrfToken, setUnauthorizedHandler } from '../api/client.js';
import { element, button, link } from './dom.js';
import { startRouter } from './router.js';
import { icon } from './icons.js';
import { loginPage, profilePage } from './auth.js';
import { catalogPage } from './catalog.js';
import { receiptsPage } from './receipts.js';
import { reportsPage } from './reports.js';
import { dashboardPage, adminPage } from './overview.js';

export function start() {
const root = document.getElementById('root');
let user = null;
let controller = new AbortController();
let navigate;
const navigation = [['/', 'Обзор'], ['/units', 'Единицы измерения'], ['/materials', 'Материалы'], ['/suppliers', 'Поставщики'], ['/receipts', 'Поступления'], ['/reports', 'Отчёты'], ['/admin', 'Администрирование']];

function acceptSession(result) { user = result.user; setCsrfToken(result.csrf_token); navigate('/', true); }
function shell() {
  const app = element('div', 'app-shell'); const header = element('header', 'topbar'); const sidebar = element('aside', 'sidebar');
  const menu = button('', 'icon-button menu-button', () => { const open = sidebar.classList.toggle('sidebar--open'); menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню'); menu.replaceChildren(icon(open ? 'close' : 'menu')); scrim.hidden = !open; }); menu.append(icon('menu'));
  menu.setAttribute('aria-label', 'Открыть меню'); menu.setAttribute('aria-expanded', 'false');
  const brand = element('div', 'brand-mark'); brand.append(icon('materials', 24)); brand.setAttribute('aria-hidden', 'true');
  const copy = element('div', 'brand-copy'); copy.append(element('span', 'brand-title', 'Складской учёт'), element('span', 'brand-subtitle', 'InventoryAccountment'));
  const profile = link(user.full_name, '/profile', 'profile-link'); profile.prepend(icon('user', 18)); profile.setAttribute('aria-label', 'Открыть личный кабинет');
  const signout = button('Выйти', 'text-button topbar-logout', async () => {
    signout.disabled = true;
    try { await logout(); user = null; setCsrfToken(undefined); navigate('/login'); }
    catch (error) { if (error instanceof ApiError && error.status === 401) return; header.append(element('span', 'error-notice', error.message)); signout.disabled = false; }
  });
  header.append(menu, brand, copy, element('div', 'environment-badge', 'Локальная среда'), profile, signout);
  const nav = element('nav'); nav.setAttribute('aria-label', 'Основная навигация');
  for (const [path, label] of navigation) { const item = link(label, path, `nav-item${location.pathname === path ? ' nav-item--active' : ''}`); item.prepend(icon(path === '/' ? 'overview' : path.slice(1))); nav.append(item); }
  sidebar.append(nav);
  const scrim = button('', 'sidebar-scrim', () => { sidebar.classList.remove('sidebar--open'); scrim.hidden = true; menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', 'Открыть меню'); menu.replaceChildren(icon('menu')); }); scrim.hidden = true; scrim.setAttribute('aria-label', 'Закрыть меню');
  const main = element('main', 'main-content'); main.id = 'main-content'; app.append(header, sidebar, scrim, main); root.replaceChildren(app); return main;
}
function render() {
  controller.abort(); controller = new AbortController(); const signal = controller.signal;
  if (!user) { if (location.pathname !== '/login') { navigate('/login', true); return; } loginPage(root, acceptSession, signal); return; }
  if (location.pathname === '/login') { navigate('/', true); return; }
  const main = shell(); const path = location.pathname;
  if (path === '/') dashboardPage(main, signal);
  else if (['/units', '/materials', '/suppliers'].includes(path)) catalogPage(main, path.slice(1), user, signal);
  else if (path === '/receipts') receiptsPage(main, user, signal);
  else if (path === '/reports') reportsPage(main, signal, navigate);
  else if (path === '/admin') adminPage(main, signal);
  else if (path === '/profile') profilePage(main, user, updated => { user = updated; render(); }, signal);
  else if (path !== '/404') navigate('/404', true);
  else { const page = element('section', 'empty-state empty-state--page'); page.append(element('p', 'error-code', '404'), element('h1', '', 'Страница не найдена'), element('p', '', 'Проверьте адрес или вернитесь на обзор склада.'), link('Вернуться на обзор', '/', 'button button--primary')); main.replaceChildren(page); }
}

navigate = startRouter(render);
setUnauthorizedHandler(() => { user = null; setCsrfToken(undefined); if (location.pathname !== '/login') navigate('/login', true); });
root.replaceChildren(element('main', 'auth-page', 'Проверка сессии…'));
getCurrentUser().then(result => { user = result.user; setCsrfToken(result.csrf_token); render(); }).catch(error => {
  if (error instanceof ApiError && error.status === 401) { render(); return; }
  const message = element('main', 'auth-page'); message.append(element('p', '', error.message), button('Повторить', 'button button--secondary', () => location.reload())); root.replaceChildren(message);
});

}

