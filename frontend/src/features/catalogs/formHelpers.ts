export function nullable(value: string) {
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
}

export function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
