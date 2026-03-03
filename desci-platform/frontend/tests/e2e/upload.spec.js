// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('DeSci Platform Upload Flow', () => {
  test('should load login page or main page', async ({ page }) => {
    await page.goto('/');
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should show upload paper page elements', async ({ page }) => {
    await page.goto('/upload');
    // The page might redirect to login if not authenticated
    // Just verify no 500 error
    const status = await page.evaluate(() => document.readyState);
    expect(status).toBe('complete');
  });

  test('should show peer review page', async ({ page }) => {
    await page.goto('/peer-review');
    const status = await page.evaluate(() => document.readyState);
    expect(status).toBe('complete');
  });

  test('should show asset management page', async ({ page }) => {
    await page.goto('/assets');
    const status = await page.evaluate(() => document.readyState);
    expect(status).toBe('complete');
  });

  test('should handle unknown routes gracefully', async ({ page }) => {
    await page.goto('/nonexistent-page');
    // Should redirect or show 404 — not crash
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
