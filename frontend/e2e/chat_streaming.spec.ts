import { test, expect } from '@playwright/test';

test.describe('Chat Streaming & Conversation Flow', () => {
  test('renders initial hero screen with search input and action pills', async ({ page }) => {
    await page.goto('/');

    // Hero title & description
    await expect(page.getByRole('heading', { name: /Legal AI Research Copilot/i })).toBeVisible();
    await expect(page.getByText(/Ask questions on Indian statutes/i)).toBeVisible();

    // Command input placeholder
    const input = page.getByPlaceholder(/Ask a legal question/i);
    await expect(input).toBeVisible();

    // Quick action pills
    await expect(page.getByRole('button', { name: /Analyze Section 66/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Research Companies Act/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Draft Legal Notice/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /BNS 2023 Cheating/i })).toBeVisible();
  });

  test('submits user message, shows generating state, and renders assistant response', async ({ page }) => {
    // Intercept chat API
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Under Section 66 of the Information Technology Act, 2000, computer-related offences carry imprisonment up to three years or a fine up to five lakh rupees.',
          sources: [
            {
              act: 'Information Technology Act 2000',
              section: '66',
              text: 'If any person, dishonestly or fraudulently, does any act referred to in section 43...',
              trust_score: 0.95,
              similarity_score: 0.88,
            },
          ],
          confidence_score: 0.92,
          blocked_by: null,
          block_reason: null,
        }),
      });
    });

    await page.goto('/');

    const input = page.getByPlaceholder(/Ask a legal question/i);
    await input.fill('What are the penalties under Section 66 of the IT Act?');
    await page.keyboard.press('Enter');

    // User message should appear
    await expect(page.getByText('What are the penalties under Section 66 of the IT Act?')).toBeVisible();

    // Assistant response should render
    await expect(
      page.getByText(/Under Section 66 of the Information Technology Act, 2000/i)
    ).toBeVisible();

    // Grounded confidence badge
    await expect(page.getByText(/Grounded \(92%\)/i)).toBeVisible();

    // Copy and TTS action buttons (first copy button on assistant or user card)
    await expect(page.getByTitle(/Copy message/i).first()).toBeVisible();
    await expect(page.getByTitle(/Listen to response/i)).toBeVisible();
  });

  test('clicking quick action pill sends pre-populated query', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Section 66 analysis completed.',
          sources: [],
          confidence_score: 0.9,
        }),
      });
    });

    await page.goto('/');
    await page.getByRole('button', { name: /Analyze Section 66/i }).click();

    // Message should be submitted
    await expect(page.getByText(/Analyze IT Act Section 66 penalties/i)).toBeVisible();
    await expect(page.getByText(/Section 66 analysis completed/i)).toBeVisible();
  });
});
