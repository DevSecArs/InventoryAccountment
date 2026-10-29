import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Vitest без globals не регистрирует автоматическую очистку Testing Library.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
