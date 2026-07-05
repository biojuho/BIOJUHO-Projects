// @ts-check
import { defineConfig, devices } from '@playwright/test';

const e2eHost = process.env.AGRIGUARD_E2E_HOST || '127.0.0.1';
const e2ePort = process.env.AGRIGUARD_E2E_PORT || '5183';
const baseURL = `http://${e2eHost}:${e2ePort}`;

/**
 * AgriGuard E2E Test Configuration
 * Run: npx playwright test
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: {
    command: `npm run dev -- --host ${e2eHost} --port ${e2ePort} --strictPort`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 30000,
  },
});
