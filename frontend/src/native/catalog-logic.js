import { nullable, formatDate } from '../features/catalogs/formHelpers.js';

export function catalogInput(resource, input, editing, options) {
  const values = { ...input };
  for (const key of ['code', 'sku', 'name']) {
    if (key in values) values[key] = values[key].trim();
  }
  if (resource === 'units' && !editing) {
    values.name = options.find(option => option.code === values.code)?.name ?? '';
  }
  if (resource === 'materials') {
    values.description = nullable(values.description);
  }
  if (resource === 'suppliers') {
    for (const key of ['contact_person', 'phone', 'email', 'address']) {
      values[key] = nullable(values[key]);
    }
  }
  if (!values.name || !(values.code || values.sku)) {
    throw new Error('Заполните обязательные поля');
  }
  return values;
}

export function catalogCells(resource, item, units) {
  let values;
  if (resource === 'units') {
    values = [item.code, item.name];
  } else if (resource === 'materials') {
    const unit = units.find(candidate => candidate.id === item.unit_id);
    values = [item.sku, item.name, unit?.name ?? item.unit_id];
  } else {
    values = [item.code, item.name, item.contact_person || '—', item.phone || '—'];
  }
  return [...values, formatDate(item.updated_at), item.archived_at ? 'В архиве' : (resource === 'units' ? 'Активна' : 'Активен')];
}

export function pagination(skip, limit, total) {
  return {
    from: total === 0 ? 0 : skip + 1,
    to: Math.min(skip + limit, total),
    previous: Math.max(0, skip - limit),
    hasNext: skip + limit < total,
  };
}
