import { defineConfig } from 'vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  root: 'src',
  base: '/static/frontend/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@components': fileURLToPath(new URL('./src/components', import.meta.url)),
      '@styles': fileURLToPath(new URL('./src/styles', import.meta.url)),
    },
  },
  build: {
    outDir: fileURLToPath(new URL('../app/static/frontend/', import.meta.url)),
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./src/entries/main.ts', import.meta.url)),
        'island-monitor-wall': fileURLToPath(
          new URL('./src/entries/island-monitor-wall.ts', import.meta.url),
        ),
        'island-roi-editor': fileURLToPath(
          new URL('./src/entries/island-roi-editor.ts', import.meta.url),
        ),
        'island-agent-chat': fileURLToPath(
          new URL('./src/entries/island-agent-chat.ts', import.meta.url),
        ),
        'components-demo': fileURLToPath(
          new URL('./src/entries/components-demo.ts', import.meta.url),
        ),
      },
      output: {
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash][extname]',
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
});
