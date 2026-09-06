import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Document Upload Workflow', () => {
  test('rejects non-PDF files with alert dialog', async ({ page }) => {
    await page.goto('/');

    let alertMessage = '';
    page.on('dialog', async (dialog) => {
      alertMessage = dialog.message();
      await dialog.accept();
    });

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test_file.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Non-pdf text content'),
    });

    expect(alertMessage).toMatch(/Only PDF documents are supported/i);
  });

  test('successfully uploads a single PDF document', async ({ page }) => {
    // Intercept single upload
    await page.route('**/api/upload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          filename: 'test_document.pdf',
          chunks_added: 4,
          session_id: 'WKD1234',
        }),
      });
    });

    await page.goto('/');

    const fixturePath = path.join(__dirname, 'fixtures', 'test_document.pdf');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(fixturePath);

    // Verify success indicator badge (+4 chunks)
    await expect(page.getByText(/\+4 chunks/i)).toBeVisible();
  });

  test('successfully uploads batch of PDF documents', async ({ page }) => {
    // Intercept batch upload
    await page.route('**/api/upload/batch', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          total_files: 2,
          total_chunks: 8,
        }),
      });
    });

    await page.goto('/');

    const docPath = path.join(__dirname, 'fixtures', 'test_document.pdf');
    const malPath = path.join(__dirname, 'fixtures', 'test_malicious.pdf');

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([docPath, malPath]);

    // Verify batch success indicator badge
    await expect(page.getByText(/2 PDFs \(\+8 chunks\)/i)).toBeVisible();
  });
});
