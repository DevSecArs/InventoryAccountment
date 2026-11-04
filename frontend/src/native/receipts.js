import { listReceipts, createReceipt, deleteReceipt, postReceipt, getReceiptHistory } from '../api/receipts.js';
import { listCatalog } from '../api/catalogs.js';
import { element, button, field, errorNotice, showModal, heading } from './dom.js';
import { statusLabel, canWriteReceipts, validQuantity, receiptInput } from './receipt-logic.js';

export function receiptsPage(root, user, signal) {
  let skip = 0; let search = ''; let revision = 0; let mutationPending = false;
  const page = element('div', 'page-stack');
  const top = heading('Документы', 'Поступления', 'Черновики проводятся синхронно и после проведения доступны только для просмотра.');
  const writer = canWriteReceipts(user.role);
  if (writer) top.append(button('Создать поступление', 'button button--primary', createDialog));
  const panel = element('section', 'data-panel'); const toolbar = element('div', 'catalog-toolbar');
  const form = element('form', 'search-form'); const input = field('Номер документа', 'search'); input.className = 'search-control'; input.querySelector('span').className = 'sr-only'; input.querySelector('input').placeholder = 'Номер документа';
  const submit = element('button', 'button button--secondary', 'Найти'); submit.type = 'submit'; form.append(input, submit);
  form.addEventListener('submit', event => { event.preventDefault(); search = form.elements.search.value.trim(); skip = 0; load(); }); toolbar.append(form);
  const result = element('div'); const footer = element('div', 'pagination'); panel.append(toolbar, result, footer); page.append(top, panel); root.replaceChildren(page);
  async function load() {
    const current = ++revision; result.replaceChildren(element('div', 'table-loading', 'Загрузка…'));
    try {
      const data = await listReceipts({ skip, limit: 20, search }, signal);
      if (signal.aborted || current !== revision) return;
      result.replaceChildren();
      if (!data.items.length) result.append(element('div', 'compact-empty', 'Нет поступлений по заданным условиям.'));
      else {
        const wrap = element('div', 'table-scroll'); const table = element('table'); const head = element('thead'); const header = element('tr');
        for (const text of ['Номер', 'Поставщик', 'Дата', 'Статус', 'Действия']) header.append(element('th', '', text)); head.append(header);
        const body = element('tbody');
        for (const receipt of data.items) {
          const row = element('tr');
          for (const value of [receipt.document_number, receipt.supplier_name ?? receipt.supplier_id, new Date(receipt.received_at).toLocaleString(), statusLabel(receipt.status)]) row.append(element('td', '', value));
          const actions = element('td', 'row-actions receipt-actions'); actions.append(button('Открыть', 'table-action', () => details(receipt)));
          if (receipt.status === 'draft' && writer) {
            actions.append(button('Провести', 'table-action', () => mutate(receipt, true)), button('Удалить', 'table-action table-action--danger', () => mutate(receipt, false)));
          }
          row.append(actions); body.append(row);
        }
        table.append(head, body); wrap.append(table); result.append(wrap);
      }
      footer.replaceChildren(element('span', '', `Всего: ${data.total}`)); const controls = element('div');
      const previous = button('Назад', 'button button--secondary', () => { skip = Math.max(0, skip - 20); load(); }); previous.disabled = skip === 0;
      const next = button('Далее', 'button button--secondary', () => { skip += 20; load(); }); next.disabled = skip + 20 >= data.total;
      controls.append(previous, next); footer.append(controls);
    } catch (error) { if (!signal.aborted && current === revision) result.replaceChildren(errorNotice(error, load)); }
  }
  async function mutate(receipt, post) {
    if (mutationPending || !confirm(post ? 'Провести документ? После этого его нельзя будет изменить.' : 'Удалить черновик?')) return;
    mutationPending = true;
    const controls = result.querySelectorAll('.receipt-actions button');
    controls.forEach(control => { control.disabled = true; });
    try { await (post ? postReceipt(receipt.id, signal) : deleteReceipt(receipt.id, signal)); if (!signal.aborted) await load(); }
    catch (error) { if (!signal.aborted) result.prepend(errorNotice(error)); }
    finally { mutationPending = false; controls.forEach(control => { control.disabled = false; }); }
  }
  function details(receipt) {
    const content = element('div', 'entity-form'); content.append(element('p', '', statusLabel(receipt.status)));
    for (const item of receipt.items) content.append(element('p', '', `${item.material_name ?? item.material_id}: ${item.quantity} ${item.unit_code ?? ''}`));
    content.append(button('Показать историю', 'button button--secondary', async () => {
      const history = element('div', 'entity-form', 'Загрузка…'); const dialog = showModal('История статусов', history, signal);
      try {
        const data = await getReceiptHistory(receipt.id, signal); if (signal.aborted || !dialog.open) return;
        history.replaceChildren();
        if (!data.items.length) history.append(element('p', '', 'История для документа до внедрения функции отсутствует.'));
        for (const item of data.items) history.append(element('p', '', `${new Date(item.changed_at).toLocaleString()}: ${statusLabel(item.from_status)} → ${statusLabel(item.to_status)}`));
      } catch (error) { if (!signal.aborted && dialog.open) history.replaceChildren(errorNotice(error)); }
    }));
    showModal(`Поступление ${receipt.document_number}`, content, signal);
  }
  async function createDialog() {
    const content = element('div', 'entity-form', 'Загрузка…'); const dialog = showModal('Новое поступление', content, signal);
    try {
      const [suppliers, materials, units] = await Promise.all(['suppliers', 'materials', 'units'].map(resource => listCatalog(resource, { skip: 0, limit: 1000, includeArchived: resource === 'units' }, signal)));
      if (signal.aborted || !dialog.open) return;
      const form = element('form', 'entity-form');
      form.append(field('Поставщик', 'supplier_id', { required: true, options: [['', 'Выберите поставщика'], ...suppliers.items.map(item => [item.id, item.name])] }), field('Номер документа', 'document_number', { required: true }), field('Дата и время (часовой пояс браузера)', 'received_at', { type: 'datetime-local', required: true }), field('Материал', 'material_id', { required: true, options: [['', 'Выберите материал'], ...materials.items.map(item => [item.id, item.name])] }), field('Количество', 'quantity', { required: true }));
      const quantity = form.elements.quantity; quantity.inputMode = 'decimal';
      const quantityLabel = quantity.parentElement.querySelector('span');
      form.elements.material_id.addEventListener('change', () => { const material = materials.items.find(item => item.id === form.elements.material_id.value); const unit = units.items.find(item => item.id === material?.unit_id); quantityLabel.textContent = `Количество${unit ? ` (${unit.code})` : ''}`; });
      const actions = element('div', 'form-actions'); const save = element('button', 'button button--primary', 'Сохранить'); save.type = 'submit'; save.disabled = true;
      const hint = element('small'); hint.hidden = true; quantity.parentElement.append(hint);
      const validate = () => { const invalid = !validQuantity(quantity.value); quantity.setCustomValidity(invalid ? 'Укажите положительное число не более чем с тремя знаками.' : ''); quantity.setAttribute('aria-invalid', String(invalid && quantity.value !== '')); hint.hidden = !invalid || quantity.value === ''; hint.textContent = hint.hidden ? '' : quantity.validationMessage; save.disabled = invalid; };
      quantity.addEventListener('input', validate);
      actions.append(button('Отмена', 'button button--secondary', () => dialog.close()), save); form.append(actions);
      form.addEventListener('submit', async event => {
        event.preventDefault(); form.querySelector('.error-notice')?.remove(); validate(); if (!form.reportValidity()) return;
        let values;
        try { values = receiptInput(Object.fromEntries(new FormData(form))); }
        catch (error) { form.prepend(errorNotice(error)); return; }
        save.disabled = true;
        try { await createReceipt(values, signal); if (!signal.aborted) { dialog.close(); load(); } }
        catch (error) { if (!signal.aborted && dialog.open) form.prepend(errorNotice(error)); }
        finally { save.disabled = false; }
      });
      content.replaceChildren(form);
    } catch (error) { if (!signal.aborted && dialog.open) content.replaceChildren(errorNotice(error)); }
  }
  load();
}
