import { test, expect } from '@playwright/test';

test.describe('Error Handling & Resilience States', () => {
  test('gracefully handles backend 500 error during chat inference', async ({ page }) => {
    // Intercept chat API to simulate a 500 server error
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Model context length exceeded or Ollama backend disconnected.',
        }),
      });
    });

    await page.goto('/');

    const input = page.getByPlaceholder(/Ask a legal question/i);
    await input.fill('Trigger simulated backend error');
    await page.keyboard.press('Enter');

    // Friendly error message should render in conversation
    await expect(
      page.getByText(/Error: Failed to fetch response from backend inference engine/i)
    ).toBeVisible();

    // Red blocked/system error indicator
    await expect(page.getByText(/Blocked by SYSTEM Guard/i)).toBeVisible();
    await expect(page.getByText(/Model context length exceeded or Ollama backend disconnected/i)).toBeVisible();
  });
});
