import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@components': fileURLToPath(new URL('./src/components', import.meta.url)),
      '@styles': fileURLToPath(new URL('./src/styles', import.meta.url)),
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.test.ts'],
    css: false,
    globals: false,
  },
});
