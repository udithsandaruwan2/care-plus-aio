import { defineConfig, devices } from '@playwright/test';

const webBase = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173';
const apiBase = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000/api/v1';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: webBase,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  metadata: { apiBase },
});
