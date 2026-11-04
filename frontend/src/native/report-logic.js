export function readReportFilters(search) {
  const params = new URLSearchParams(search);
  const rawSkip = Number(params.get('skip') ?? 0);
  return {
    from: params.get('from') ?? '',
    to: params.get('to') ?? '',
    supplierId: params.get('supplier_id') ?? '',
    materialId: params.get('material_id') ?? '',
    skip: Number.isSafeInteger(rawSkip) && rawSkip >= 0 ? rawSkip : 0,
    limit: 50,
  };
}

export function updateReportQuery(search, name, value) {
  const params = new URLSearchParams(search);
  if (value) {
    params.set(name, value);
  } else {
    params.delete(name);
  }
  if (name !== 'skip') params.set('skip', '0');
  return params.toString();
}
