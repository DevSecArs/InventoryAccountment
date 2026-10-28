import { describe, expect, it } from 'vitest';

import { formatDate, nullable } from './formHelpers';

describe('formHelpers', () => {
  it('нормализует пустые и непустые строки', () => {
    expect(nullable('  ')).toBeNull();
    expect(nullable('  ABC  ')).toBe('ABC');
  });

  it('форматирует дату и обозначает отсутствие даты', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('2026-01-01T12:00:00Z')).toContain('2026');
  });
});
