import { getLiveness, getReadiness } from '../api/health.js';
import { element, link, heading, errorNotice } from './dom.js';
import { icon } from './icons.js';

export function dashboardPage(root, signal) {
  const page = element('div', 'page-stack');
  const top = heading('Рабочее пространство', 'Обзор склада', 'Управляйте справочниками, поступлениями и отчётом по поставкам.');
  top.append(link('Открыть поступления →', '/receipts', 'button button--primary'));
  const metrics = element('section', 'metric-grid'); metrics.setAttribute('aria-label', 'Сводка');
  for (const [label, value, detail] of [['Справочники', '3', 'Единицы, материалы, поставщики'], ['Поступления', '→', 'Черновики и проведение']]) {
    const card = element('article', 'metric-card'); const div = element('div');
    const badge = element('div', 'metric-icon'); badge.append(icon(label === 'Справочники' ? 'materials' : 'suppliers', 20));
    div.append(element('p', 'metric-label', label), element('p', 'metric-value', value), element('p', 'metric-detail', detail)); card.append(badge, div); metrics.append(card);
  }
  const grid = element('section', 'content-grid');
  const status = element('article', 'panel'); status.append(element('p', 'eyebrow', 'Готовность'), element('h2', '', 'Состояние системы'));
  const systemState = element('span', 'status-pill status-pill--neutral', 'Проверка…'); status.append(systemState);
  let live = false; let ready = false; let complete = 0;
  function updateState() { if (++complete === 2) { systemState.textContent = live && ready ? 'Система готова' : 'Требует внимания'; if (live && ready) systemState.className = 'status-pill status-pill--active'; } }
  const list = element('div', 'service-list'); const api = element('div', 'service-row', 'HTTP API: проверяется'); const db = element('div', 'service-row', 'PostgreSQL: проверяется'); list.append(api, db); status.append(list);
  const next = element('article', 'panel panel--accent'); next.append(element('p', 'eyebrow', 'Следующий шаг'), element('h2', '', 'Подготовьте справочники'), element('p', '', 'Начните с единиц измерения, затем добавьте материалы и поставщиков.'), link('Перейти к единицам →', '/units', 'text-link'));
  grid.append(status, next); page.append(top, metrics, grid); root.replaceChildren(page);
  getLiveness(signal).then(() => { if (!signal.aborted) { api.textContent = 'HTTP API: работает'; live = true; updateState(); } }).catch(() => { if (!signal.aborted) { api.textContent = 'HTTP API: недоступен'; updateState(); } });
  getReadiness(signal).then(() => { if (!signal.aborted) { db.textContent = 'PostgreSQL: принимает запросы'; ready = true; updateState(); } }).catch(() => { if (!signal.aborted) { db.textContent = 'PostgreSQL: недоступна'; updateState(); } });
}

export function adminPage(root, signal) {
  const page = element('div', 'page-stack');
  page.append(heading('Эксплуатация', 'Администрирование', 'Состояние обязательных сервисов и безопасные эксплуатационные действия.'));
  const errors = element('div'); page.append(errors);
  const grid = element('section', 'admin-grid');
  const api = element('article', 'service-card', 'HTTP API: проверка');
  const db = element('article', 'service-card', 'PostgreSQL: проверка'); grid.append(api, db);
  const policy = element('section', 'panel admin-policy'); policy.append(element('h2', '', 'Безопасность операций'), element('p', '', 'Восстановление должно выполняться сначала в отдельную БД. Перезапись существующей цели требует подтверждения точного окружения и отдельного разрешения.'));
  page.append(grid, policy); root.replaceChildren(page);
  let revision = 0;
  function refresh() {
    const current = ++revision;
    errors.replaceChildren();
    const active = () => !signal.aborted && current === revision;
    const failure = error => { if (active()) errors.replaceChildren(errorNotice(error, refresh)); };
    getLiveness(signal).then(() => { if (active()) api.textContent = 'HTTP API: работает'; }).catch(error => { if (active()) { api.textContent = 'HTTP API: недоступен'; failure(error); } });
    getReadiness(signal).then(() => { if (active()) db.textContent = 'PostgreSQL: готова'; }).catch(error => { if (active()) { db.textContent = 'PostgreSQL: недоступна'; failure(error); } });
  }
  refresh(); const timer = setInterval(refresh, 30000); signal.addEventListener('abort', () => clearInterval(timer), { once: true });
}
