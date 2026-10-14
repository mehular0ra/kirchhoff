import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'src/contracts/generated.ts']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Intentional patterns in this app: the "latest value" ref (callbacks read ref.current) and
      // resetting local state when a prop changes. Kept visible as warnings, not build blockers.
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      // shadcn files and hook+component modules export helpers next to components.
      'react-refresh/only-export-components': 'warn',
    },
  },
  {
    // P0 Firebase glue uses `any` for the App Check debug-token global and its mocks.
    files: ['src/firebase.ts', 'src/firebase.test.ts'],
    rules: { '@typescript-eslint/no-explicit-any': 'off' },
  },
])
