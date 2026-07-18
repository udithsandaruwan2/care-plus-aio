// Root ESLint flat config. Per-app configs (apps/web, apps/mobile) extend this
// once those packages are scaffolded in Milestone M2 / M8.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import prettier from 'eslint-config-prettier';

export default [
  { ignores: ['**/dist/**', '**/build/**', '**/node_modules/**', '**/.expo/**', '**/.turbo/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  prettier,
];
