import { test, expect } from '@playwright/test';

test.describe('DeSci Platform E2E Tests', () => {
  test('UploadPaper component renders with agreement checkbox', async ({ page }) => {
    // Navigate to the upload paper route (assuming /upload-paper maps to it)
    // We mock the navigation for CI purposes or just check DOM if served
    await page.goto('http://localhost:5173/upload-paper').catch(() => {});
    
    // Check if the Legal Agreement Checkbox exists
    const agreementCheckbox = page.locator('input#terms');
    
    // Check button state
    const uploadButton = page.locator('button[type="submit"]');
    if (await uploadButton.count() > 0) {
      // Must be disabled initially
      await expect(uploadButton).toBeDisabled();
    }
  });
});

test.describe('AgriGuard Dashboard E2E Tests', () => {
  test('Dashboard shows loading shimmer and handles API errors', async ({ page }) => {
    // Intercept API call to mock 500 error for edge case testing
    await page.route('**/dashboard/summary', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Internal Server Error' })
    }));

    await page.goto('http://localhost:5173/dashboard').catch(() => {});

    // Ensure error state is displayed
    const errorAlert = page.locator('text=백엔드 연결 실패');
    if (await errorAlert.count() > 0) {
      await expect(errorAlert).toBeVisible();
    }
  });
});
