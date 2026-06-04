// @ts-check
import { expect, test } from '@playwright/test';

test.describe('AgriGuard Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');
    // Wait for either the dashboard content or the error state
    const content = page.locator('body');
    await expect(content).toBeVisible();
  });

  test('should display navigation links', async ({ page }) => {
    await page.goto('/');
    // Check sidebar/nav items exist
    await expect(page.getByText('Dashboard')).toBeVisible();
  });

  test('should navigate to product registry', async ({ page }) => {
    await page.goto('/registry');
    await expect(page).toHaveURL(/registry/);
  });

  test('should navigate to QR scanner', async ({ page }) => {
    await page.goto('/scan');
    await expect(page).toHaveURL(/scan/);
    // QR scanner page should show scan-related content
    await expect(page.getByRole('heading', { name: 'Scan Product QR' })).toBeVisible();
  });

  test('should navigate to supply chain', async ({ page }) => {
    await page.goto('/supply-chain');
    await expect(page).toHaveURL(/supply-chain/);
  });

  test('should redirect unknown routes to dashboard', async ({ page }) => {
    await page.goto('/unknown-page');
    await expect(page).toHaveURL('/');
  });
});
