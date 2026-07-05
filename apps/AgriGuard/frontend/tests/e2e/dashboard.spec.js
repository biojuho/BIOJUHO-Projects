// @ts-check
import { expect, test } from '@playwright/test';

const operatorToken = process.env.AGRIGUARD_BROWSER_OPERATOR_TOKEN || 'browser-smoke-token';

test.beforeEach(async ({ page }) => {
  await page.addInitScript((token) => {
    window.localStorage.setItem('agriguard-operator-token', token);
  }, operatorToken);
});

async function openMenuIfCollapsed(page) {
  const openMenuButton = page.getByRole('button', { name: 'Open menu' });
  if (await openMenuButton.isVisible()) {
    await openMenuButton.click();
  }
}

test.describe('AgriGuard Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');
    const content = page.locator('body');
    await expect(content).toBeVisible();
  });

  test('should display navigation links', async ({ page }) => {
    await page.goto('/');
    await openMenuIfCollapsed(page);
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  });

  test('should navigate to product registry', async ({ page }) => {
    await page.goto('/registry');
    await expect(page).toHaveURL(/registry/);
  });

  test('should navigate to QR scanner', async ({ page }) => {
    await page.goto('/scan');
    await expect(page).toHaveURL(/scan/);
    await expect(page.getByRole('heading', { name: 'Scan Product QR' })).toBeVisible();
  });

  test('should navigate to supply chain', async ({ page }) => {
    await page.goto('/supply-chain');
    await expect(page).toHaveURL(/supply-chain/);
    await expect(page.getByRole('heading', { name: 'Supply Chain Overview' })).toBeVisible();
  });

  test('should redirect unknown routes to dashboard', async ({ page }) => {
    await page.goto('/unknown-page');
    await expect(page).toHaveURL('/');
  });
});
