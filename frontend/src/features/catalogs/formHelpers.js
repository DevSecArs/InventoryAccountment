export function nullable(value) {
  const normalized = value.trim();
  return normalized === '' ? null : normalized;
}

export function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
