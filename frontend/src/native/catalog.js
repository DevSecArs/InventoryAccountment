import { listCatalog, listSiUnitOptions, createCatalog, updateCatalog, archiveCatalog, purgeCatalog } from '../api/catalogs.js';
import { catalogInput, catalogCells, pagination } from './catalog-logic.js';
import { icon } from './icons.js';
import { element, button, field, errorNotice, showModal, heading } from './dom.js';

const settings = {
  units: { title: 'Единицы измерения', single: 'единицу', description: 'Единый справочник единиц хранения материалов. Используемые единицы нельзя архивировать.' },
  materials: { title: 'Материалы', single: 'материал', description: 'Номенклатура склада с закреплёнными единицами измерения.' },
  suppliers: { title: 'Поставщики', single: 'поставщика', description: 'Контрагенты, от которых поступают материалы на склад.' },
};

export function catalogPage(root, resource, user, signal) {
  const config = settings[resource];
  let skip = 0;
  const limit = 20;
  let search = '';
  let archived = false;
  let revision = 0;
  let related = [];
  const page = element('div', 'page-stack');
  const top = heading('Справочник', config.title, config.description);
  top.append(button(`Добавить ${config.single}`, 'button button--primary', () => openForm(null)));
  const panel = element('section', 'data-panel');
  const toolbar = element('div', 'catalog-toolbar');
  const searchForm = element('form', 'search-form');
  searchForm.setAttribute('role', 'search');
  const searchLabel = field('Поиск', 'search');
  searchLabel.className = 'search-control'; searchLabel.querySelector('span').className = 'sr-only';
  searchLabel.querySelector('input').placeholder = 'Поиск';
  const submit = element('button', 'button button--secondary', 'Найти');
  submit.type = 'submit';
  searchForm.append(searchLabel, submit);
  searchForm.addEventListener('submit', event => { event.preventDefault(); search = searchForm.elements.search.value; skip = 0; load(); });
  const archiveLabel = field('Показывать архив', 'archived', { type: 'checkbox' });
  archiveLabel.className = 'checkbox-control';
  archiveLabel.querySelector('input').addEventListener('change', event => { archived = event.target.checked; skip = 0; load(); });
  toolbar.append(searchForm, archiveLabel);
  const result = element('div');
  const footer = element('footer', 'pagination');
  panel.append(toolbar, result, footer);
  page.append(top, panel);
  root.replaceChildren(page);

  async function load() {
    const current = ++revision;
    result.replaceChildren(element('div', 'table-loading', 'Загрузка данных…'));
    try {
      const calls = [listCatalog(resource, { skip, limit, search, includeArchived: archived }, signal)];
      if (resource === 'units') calls.push(listSiUnitOptions(signal));
      if (resource === 'materials') calls.push(listCatalog('units', { skip: 0, limit: 1000 }, signal));
      const [data, options] = await Promise.all(calls);
      if (signal.aborted || current !== revision) return;
      related = resource === 'materials' ? options.items : options ?? [];
      renderRows(data);
    } catch (error) {
      if (signal.aborted || current !== revision) return;
      result.replaceChildren(errorNotice(error, load));
    }
  }

  function renderRows(data) {
    result.replaceChildren();
    if (!data.items.length) {
      const empty = element('div', 'compact-empty');
      empty.append(element('strong', '', 'Записи не найдены'), element('span', '', 'Измените фильтры или создайте первую запись.'));
      result.append(empty);
    } else {
      const wrap = element('div', 'table-scroll');
      const table = element('table');
      const labels = resource === 'units' ? ['Код', 'Наименование', 'Изменено', 'Состояние'] : resource === 'materials' ? ['Артикул', 'Наименование', 'Единица', 'Изменено', 'Состояние'] : ['Код', 'Наименование', 'Контакт', 'Телефон', 'Изменено', 'Состояние'];
      const head = element('thead');
      const headRow = element('tr');
      for (const label of [...labels, 'Действия']) headRow.append(element('th', '', label));
      head.append(headRow);
      const body = element('tbody');
      for (const item of data.items) {
        const row = element('tr', item.archived_at ? 'row--archived' : '');
        const values = catalogCells(resource, item, related);
        for (const [index, value] of values.entries()) {
          const cell = element('td');
          if (index === values.length - 1) cell.append(element('span', `status-pill ${item.archived_at ? 'status-pill--archived' : 'status-pill--active'}`, value));
          else cell.textContent = value;
          row.append(cell);
        }
        const actions = element('td', 'row-actions');
        if (!item.archived_at) {
          const edit = button('', 'table-action', () => openForm(item)); edit.append(icon('edit', 17));
          edit.setAttribute('aria-label', `Изменить запись ${item.id}`);
          const archive = button('', 'table-action table-action--danger', () => mutate(item, false)); archive.append(icon('archive', 17));
          archive.setAttribute('aria-label', `Архивировать запись ${item.id}`);
          actions.append(edit, archive);
        } else if (user.role === 'admin') { const purge = button('', 'table-action table-action--danger', () => mutate(item, true)); purge.append(icon('delete', 17)); purge.setAttribute('aria-label', `Удалить архивную запись ${item.id}`); actions.append(purge); }
        row.append(actions); body.append(row);
      }
      table.append(head, body); wrap.append(table); result.append(wrap);
    }
    const bounds = pagination(skip, limit, data.total);
    footer.replaceChildren(element('span', '', `${bounds.from}–${bounds.to} из ${data.total}`));
    const controls = element('div');
    const previous = button('‹', 'icon-button', () => { skip = bounds.previous; load(); });
    previous.disabled = skip === 0; previous.setAttribute('aria-label', 'Предыдущая страница');
    const next = button('›', 'icon-button', () => { skip += limit; load(); });
    next.disabled = !bounds.hasNext; next.setAttribute('aria-label', 'Следующая страница');
    controls.append(previous, next); footer.append(controls);
  }

  async function mutate(item, purge) {
    if (!window.confirm(`${purge ? 'Безвозвратно удалить архивную запись' : 'Архивировать запись'} «${item.name}»?`)) return;
    try { await (purge ? purgeCatalog(resource, item.id, signal) : archiveCatalog(resource, item.id, signal)); if (!signal.aborted) load(); }
    catch (error) { if (!signal.aborted) result.prepend(errorNotice(error)); }
  }

  function openForm(item) {
    const form = element('form', 'entity-form');
    const fields = [];
    if (resource === 'units' && !item) {
      fields.push(field('Единица СИ', 'code', { required: true, options: [['', 'Выберите единицу'], ...related.map(option => [option.code, `${option.code} — ${option.name}`])] }));
    } else fields.push(field(resource === 'materials' ? 'Артикул' : 'Код', resource === 'materials' ? 'sku' : 'code', { required: true, maxLength: 50, value: item?.[resource === 'materials' ? 'sku' : 'code'] }));
    if (resource === 'materials') fields.push(field('Единица измерения', 'unit_id', { required: true, value: item?.unit_id, options: [['', 'Выберите единицу'], ...related.map(unit => [unit.id, `${unit.code} — ${unit.name}`])] }));
    if (resource !== 'units' || item) fields.push(field('Наименование', 'name', { required: true, maxLength: 200, value: item?.name }));
    if (resource === 'materials') fields.push(field('Описание', 'description', { multiline: true, maxLength: 5000, value: item?.description }));
    if (resource === 'suppliers') {
      for (const [name, label, maxLength, type] of [['contact_person', 'Контактное лицо', 100], ['phone', 'Телефон', 50], ['email', 'Email', undefined, 'email'], ['address', 'Адрес', 5000]]) fields.push(field(label, name, { maxLength, type, multiline: name === 'address', value: item?.[name] }));
    }
    if (resource === 'units') {
      form.append(...fields);
    } else {
      const grid = element('div', 'form-grid');
      grid.append(...fields.splice(0, resource === 'materials' ? 2 : 5));
      form.append(grid, ...fields);
    }
    const actions = element('div', 'form-actions');
    const save = element('button', 'button button--primary', 'Сохранить'); save.type = 'submit';
    const cancel = button('Отмена', 'button button--secondary', () => dialog.close());
    actions.append(cancel, save); form.append(actions);
    const dialog = showModal(item ? `Изменить ${config.single}` : `Добавить ${config.single}`, form, signal);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      form.querySelector('.error-notice')?.remove();
      let values;
      try { values = catalogInput(resource, Object.fromEntries(new FormData(form)), Boolean(item), related); }
      catch (error) { form.prepend(errorNotice(error)); return; }
      save.disabled = true;
      try { await (item ? updateCatalog(resource, item.id, values, signal) : createCatalog(resource, values, signal)); if (!signal.aborted) { dialog.close(); load(); } }
      catch (error) { if (!signal.aborted) form.prepend(errorNotice(error)); }
      finally { save.disabled = false; }
    });
  }
  load();
}
