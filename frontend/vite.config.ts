import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  const apiProxyTarget =
    loadEnv(mode, '.', 'VITE_').VITE_API_PROXY_TARGET ??
    'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      hmr: { clientPort: 80 },
      proxy: {
        '/api': apiProxyTarget,
        '/health': apiProxyTarget,
      },
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
      proxy: {
        '/api': apiProxyTarget,
        '/health': apiProxyTarget,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      restoreMocks: true,
    },
  };
});
