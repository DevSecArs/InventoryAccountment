export function statusLabel(status) {
  return ({ draft: 'Черновик', posted: 'Проведено' })[status] ?? status;
}

export function canWriteReceipts(role) {
  return role === 'admin' || role === 'operator';
}

export function validQuantity(value) {
  return /^\d+(\.\d{1,3})?$/.test(value) && /[1-9]/.test(value);
}

export function receiptInput(values) {
  if (!values.supplier_id || !values.material_id || !values.document_number.trim()) {
    throw new Error('Заполните обязательные поля');
  }
  if (!validQuantity(values.quantity)) {
    throw new Error('Укажите положительное число не более чем с тремя знаками.');
  }
  const date = new Date(values.received_at);
  if (!values.received_at || Number.isNaN(date.getTime())) {
    throw new Error('Укажите дату и время');
  }
  return {
    supplier_id: values.supplier_id,
    document_number: values.document_number,
    received_at: date.toISOString(),
    items: [{ material_id: values.material_id, quantity: values.quantity }],
  };
}
