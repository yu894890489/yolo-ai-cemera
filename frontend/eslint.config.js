import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';

export default [
  {
    ignores: ['../app/static/frontend/**', 'node_modules/**'],
  },
  {
    files: ['src/**/*.ts'],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
      },
      globals: {
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        HTMLElement: 'readonly',
        HTMLInputElement: 'readonly',
        HTMLButtonElement: 'readonly',
        HTMLSelectElement: 'readonly',
        HTMLTextAreaElement: 'readonly',
        HTMLVideoElement: 'readonly',
        MouseEvent: 'readonly',
        KeyboardEvent: 'readonly',
        WebSocket: 'readonly',
        MessageEvent: 'readonly',
        CloseEvent: 'readonly',
        Event: 'readonly',
        CustomEvent: 'readonly',
        fetch: 'readonly',
        Response: 'readonly',
        RequestInit: 'readonly',
        AbortController: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        location: 'readonly',
        URL: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
    },
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['info', 'warn', 'error'] }],
    },
  },
];
