import { test, expect } from './fixtures/auth';

test.describe('Accessibility & Keyboard Navigation', () => {
  test('supports full keyboard navigation to search and quick pills', async ({ page }) => {
    await page.goto('/');

    // The workspace header names the active view; the hero states what the tool does.
    await expect(page.locator('header h1')).toHaveText(/Legal Copilot/i);
    await expect(
      page.getByRole('heading', { name: /Legal research, grounded in your sources/i }),
    ).toBeVisible();

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

    // Quick-action pills are derived from the indexed corpus, so assert on the
    // affordance rather than on any particular act being present.
    await expect(page.getByTestId('quick-action').first()).toBeVisible();
  });

  test('sidebar navigation items are visible and interactive', async ({ page }) => {
    await page.goto('/');

    const navItems = [
      'Legal Copilot',
      'Citation Graph',
      'Statute Library',
      'Hardware & Models',
      'Sources & Research',
      'Security & Integrity',
      'Settings',
    ];

    const sidebar = page.locator('aside');
    for (const name of navItems) {
      const item = sidebar.getByText(name, { exact: true });
      await expect(item).toBeVisible();
    }
  });
});
