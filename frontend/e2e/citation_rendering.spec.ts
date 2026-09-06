import { test, expect } from '@playwright/test';

test.describe('Citation Rendering & Grounding Sources', () => {
  test('renders grounded citation sources with section badges and trust metrics', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Section 43 of the Information Technology Act covers penalty and compensation for damage to computer system.',
          sources: [
            {
              act: 'Information Technology Act 2000',
              section: '43',
              text: 'Penalty and compensation for damage to computer, computer system, etc. - If any person without permission of the owner or any other person who is incharge...',
              trust_score: 0.98,
              similarity_score: 0.91,
            },
            {
              act: 'Information Technology Act 2000',
              section: '66',
              text: 'Computer related offences - If any person, dishonestly or fraudulently, does any act referred to in section 43...',
              trust_score: 0.94,
              similarity_score: 0.86,
            },
          ],
          confidence_score: 0.96,
        }),
      });
    });

    await page.goto('/');

    const input = page.getByPlaceholder(/Ask a legal question/i);
    await input.fill('Explain IT Act Section 43 penalties');
    await page.keyboard.press('Enter');

    // Check Citation Header
    await expect(page.getByText(/Grounded Legal Sources & Citations \(2\)/i)).toBeVisible();

    // Check Source 1 Badges and Content
    await expect(page.getByText(/\[1\] Information Technology Act 2000/i)).toBeVisible();
    await expect(page.getByText('Section 43', { exact: true })).toBeVisible();
    await expect(page.getByText(/Trust: 98%/i)).toBeVisible();
    await expect(page.getByText(/Sim: 91%/i)).toBeVisible();
    await expect(page.getByText(/Penalty and compensation for damage to computer/i).first()).toBeVisible();

    // Check Source 2 Badges and Content
    await expect(page.getByText(/\[2\] Information Technology Act 2000/i)).toBeVisible();
    await expect(page.getByText('Section 66', { exact: true })).toBeVisible();
    await expect(page.getByText(/Trust: 94%/i)).toBeVisible();
    await expect(page.getByText(/Sim: 86%/i)).toBeVisible();
  });

  test('expands progressive disclosure ProvenancePanel to show full Phase 10 provenance metadata', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Section 447 of Companies Act 2013 defines punishment for fraud.',
          sources: [
            {
              act: 'Companies Act 2013',
              section: '447',
              text: 'Without prejudice to any liability including repayment of any debt...',
              trust_score: 0.99,
              similarity_score: 0.93,
              jurisdiction: 'India (Union / Ministry of Corporate Affairs)',
              document_version: 'v2024.2',
              publication_date: '2013-08-29',
              is_superseded: false,
              content_hash: 'sha256:447a19b88234fedcba00123',
            },
          ],
          confidence_score: 0.95,
        }),
      });
    });

    await page.goto('/');

    const input = page.getByPlaceholder(/Ask a legal question/i);
    await input.fill('Research Companies Act Section 447');
    await page.keyboard.press('Enter');

    // Click to expand provenance accordion
    const toggleBtn = page.getByRole('button', { name: /Show Provenance Details/i });
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();

    // Check Expanded Provenance Fields
    await expect(page.getByText(/Jurisdiction:/i)).toBeVisible();
    await expect(page.getByText(/India \(Union \/ Ministry of Corporate Affairs\)/i)).toBeVisible();
    await expect(page.getByText(/Status:/i)).toBeVisible();
    await expect(page.getByText(/Active Settled Law/i)).toBeVisible();
    await expect(page.getByText(/2013-08-29/i)).toBeVisible();
    await expect(page.getByText(/sha256:447a19b88234fedcba00123/i)).toBeVisible();

    // Check Hide toggle state
    await expect(page.getByRole('button', { name: /Hide Provenance Details/i })).toBeVisible();
  });
});
