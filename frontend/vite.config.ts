import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

const reportDirectory = process.env.REPORT_DIR ?? 'coverage';

export default defineConfig(({ mode }) => {
  const apiProxyTarget =
    loadEnv(mode, '.', 'VITE_').VITE_API_PROXY_TARGET ??
    'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      hmr: { clientPort: 8080 },
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
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/vite-env.d.ts'],
        thresholds: { statements: 40, branches: 40, functions: 40, lines: 40 },
        reporter: ['text', 'html', 'cobertura'],
        reportsDirectory: reportDirectory,
      },
      reporters: ['default', 'junit'],
      outputFile: { junit: `${reportDirectory}/junit.xml` },
    },
  };
});
