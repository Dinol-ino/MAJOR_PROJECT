import { test, expect } from './fixtures/auth';

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

    // The failure is surfaced in the conversation, carrying the server's reason and
    // making no legal claim of its own.
    await expect(page.getByText(/The request could not be completed/i)).toBeVisible();
    await expect(
      page.getByText(/Model context length exceeded or Ollama backend disconnected/i),
    ).toBeVisible();

    // A failed request must never render sources or a grounding badge.
    await expect(page.getByText(/Grounded:/i)).toHaveCount(0);
    await expect(page.getByText(/Citations \(/i)).toHaveCount(0);
  });
});
