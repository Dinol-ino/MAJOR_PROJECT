import { test, expect } from './fixtures/auth';

test.describe('Chat Streaming & Conversation Flow', () => {
  test('renders initial hero screen with search input and action pills', async ({ page }) => {
    await page.goto('/');

    // Hero title & description
    await expect(
      page.getByRole('heading', { name: /Legal research, grounded in your sources/i }),
    ).toBeVisible();
    await expect(page.getByText(/Answers cite the passages they rely on/i)).toBeVisible();

    // Command input placeholder
    const input = page.getByPlaceholder(/Ask a legal question/i);
    await expect(input).toBeVisible();

    // Quick action pills are generated from the indexed corpus, not hardcoded.
    await expect(page.getByTestId('quick-action').first()).toBeVisible();
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
          // The UI reads grounding_score on a 0-100 scale (MessageContent.jsx).
          grounding_score: 92,
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

    // Grounding badge
    await expect(page.getByText(/Grounded: 92%/i)).toBeVisible();

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
    // The pill submits its own prompt (which differs from its label), so assert that
    // a user turn was created and the answer rendered - not on any particular wording.
    await page.getByTestId('quick-action').first().click();
    await expect(page.getByTestId('user-message')).toHaveCount(1);
    await expect(page.getByText(/Section 66 analysis completed/i)).toBeVisible();
  });
});
