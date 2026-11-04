import { listCatalog } from '../api/catalogs.js';
import { getSupplyReport, exportSupplyReport } from '../api/reports.js';
import { element, button, field, errorNotice, heading } from './dom.js';
import { readReportFilters, updateReportQuery } from './report-logic.js';

export function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
}

export function reportsPage(root, signal, navigate) {
  const filters = readReportFilters(location.search);
  const { from, to, supplierId, materialId, skip } = filters;
  const enabled = Boolean(from && to);
  const page = element('div', 'page-stack');
  const top = heading('Аналитика', 'Отчёт по поставкам', 'В отчёт входят только проведённые поступления. Итоги разделены по единицам измерения.');
  const exportErrors = element('div');
  const download = button('Скачать CSV', 'button button--secondary', async () => {
    exportErrors.replaceChildren(); download.disabled = true;
    try { const blob = await exportSupplyReport({ from, to, supplierId, materialId }, signal); if (signal.aborted) return; const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'supplies.csv'; anchor.click(); URL.revokeObjectURL(url); }
    catch (error) { if (!signal.aborted) exportErrors.replaceChildren(errorNotice(error)); }
    finally { download.disabled = !enabled; }
  }); download.disabled = !enabled; top.append(download);
  const panel = element('section', 'filter-panel'); const inputs = element('div', 'report-filters');
  const start = field('Начало периода', 'from', { type: 'datetime-local', value: localDateTime(from) });
  const end = field('Конец периода', 'to', { type: 'datetime-local', value: localDateTime(to) });
  const supplier = field('Поставщик', 'supplier_id', { options: [['', 'Все поставщики']] });
  const material = field('Материал', 'material_id', { options: [['', 'Все материалы']] });
  inputs.append(start, end, supplier, material); panel.append(inputs);
  const result = element('section', 'data-panel'); page.append(top, panel, exportErrors, result); root.replaceChildren(page);
  function update(name, value) {
    navigate(`/reports?${updateReportQuery(location.search, name, value)}`);
  }
  for (const node of [start, end]) node.querySelector('input').addEventListener('change', event => update(event.target.name, event.target.value ? new Date(event.target.value).toISOString() : ''));
  for (const node of [supplier, material]) node.querySelector('select').addEventListener('change', event => update(event.target.name, event.target.value));
  Promise.all(['suppliers', 'materials'].map(resource => listCatalog(resource, { skip: 0, limit: 1000, includeArchived: true }, signal))).then(([suppliers, materials]) => {
    if (signal.aborted) return;
    for (const [node, data, value] of [[supplier, suppliers, supplierId], [material, materials, materialId]]) { const select = node.querySelector('select'); for (const item of data.items) select.add(new Option(item.name, item.id)); select.value = value; }
  }).catch(error => { if (!signal.aborted) panel.append(errorNotice(error)); });
  if (!enabled) { result.append(element('div', 'compact-empty', 'Укажите начало и конец периода.')); return; }
  result.append(element('div', 'table-loading', 'Формирование отчёта…'));
  getSupplyReport(filters, signal).then(data => {
    if (signal.aborted) return; result.replaceChildren();
    if (!data.items.length) result.append(element('div', 'compact-empty', 'За период нет проведённых поступлений.'));
    else {
      const wrap = element('div', 'table-scroll'); const table = element('table'); const head = element('thead'); const row = element('tr');
      for (const label of ['Дата', 'Документ', 'Поставщик', 'Материал', 'Количество']) row.append(element('th', '', label)); head.append(row);
      const body = element('tbody');
      for (const item of data.items) { const tr = element('tr'); for (const value of [new Date(item.received_at).toLocaleString(), item.document_number, item.supplier_name, `${item.material_name} (${item.unit_code})`, item.quantity]) tr.append(element('td', '', value)); body.append(tr); }
      table.append(head, body); wrap.append(table); result.append(wrap);
    }
    const totals = element('div', 'panel panel-padding'); totals.append(element('strong', '', 'Итоги'));
    for (const item of data.totals) totals.append(element('p', '', `${item.material_name}: ${item.quantity} ${item.unit_code}`)); result.append(totals);
    const footer = element('div', 'pagination'); footer.append(element('span', '', `Всего строк: ${data.total}`)); const controls = element('div');
    const previous = button('Назад', 'button button--secondary', () => update('skip', String(Math.max(0, skip - 50)))); previous.disabled = skip === 0;
    const next = button('Далее', 'button button--secondary', () => update('skip', String(skip + 50))); next.disabled = skip + 50 >= data.total;
    controls.append(previous, next); footer.append(controls); result.append(footer);
  }).catch(error => { if (!signal.aborted) result.replaceChildren(errorNotice(error, () => navigate(location.href, true))); });
}
