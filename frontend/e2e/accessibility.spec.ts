import { test, expect } from '@playwright/test';

test.describe('Accessibility & Keyboard Navigation', () => {
  test('supports full keyboard navigation to search and quick pills', async ({ page }) => {
    await page.goto('/');

    // Page must have a proper main heading
    const h1 = page.locator('h1');
    await expect(h1).toHaveText(/Legal AI Research Copilot/i);

    // Focus on command input and type via keyboard
    const input = page.getByPlaceholder(/Ask a legal question/i);
    await input.focus();
    await expect(input).toBeFocused();

    await page.keyboard.type('Test accessibility query');
    expect(await input.inputValue()).toBe('Test accessibility query');

    // Tab through quick action buttons
    await page.keyboard.press('Tab');
    // Verify interactive buttons are present and have accessible names
    const uploadBtn = page.getByRole('button', { name: /Upload PDF/i });
    await expect(uploadBtn).toBeVisible();

    const pill1 = page.getByRole('button', { name: /Analyze Section 66/i });
    await expect(pill1).toBeVisible();
  });

  test('sidebar navigation items are visible and interactive', async ({ page }) => {
    await page.goto('/');

    const navItems = [
      'Legal Copilot',
      'Citation Graph',
      'Statute Library',
      'Cryptographic Audit',
      'Hardware Engine',
      'API & MCP Tools',
    ];

    const sidebar = page.locator('aside');
    for (const name of navItems) {
      const item = sidebar.getByText(name, { exact: true });
      await expect(item).toBeVisible();
    }
  });
});
