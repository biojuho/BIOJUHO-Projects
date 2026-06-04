// @ts-check
import { defineConfig, devices } from '@playwright/test';

const runtimeEnv = process['env'];
const baseURL = runtimeEnv.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173';
const parsedBaseURL = new URL(baseURL);
const devHost = parsedBaseURL.hostname || '127.0.0.1';
const devPort = parsedBaseURL.port || (parsedBaseURL.protocol === 'https:' ? '443' : '80');
const reuseExistingServer = runtimeEnv.PLAYWRIGHT_REUSE_SERVER === '1';

/**
 * AgriGuard E2E Test Configuration
 * Run: npx playwright test
 *
 * Set PLAYWRIGHT_BASE_URL and PLAYWRIGHT_REUSE_SERVER=1 to verify an already-running
 * local server without accidentally reusing an unrelated app on the default port.
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
    command: `npm run dev -- --host ${devHost} --port ${devPort} --strictPort`,
    url: baseURL,
    reuseExistingServer,
    timeout: 30000,
  },
});
