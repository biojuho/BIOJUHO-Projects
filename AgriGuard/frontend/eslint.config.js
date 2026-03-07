import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import reactPlugin from 'eslint-plugin-react'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'playwright.config.js', 'tailwind.config.js', 'tests/e2e']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      react: reactPlugin,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'react/jsx-uses-vars': 'error',
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', caughtErrorsIgnorePattern: '^_' }],
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
])
