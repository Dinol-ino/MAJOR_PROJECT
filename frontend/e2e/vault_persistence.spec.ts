import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Real backend, no mocked routes: a lawyer's vault and its documents must survive a page
 * reload, and the original file must be downloadable afterwards (canonical store).
 */
test.describe('Project Vault persistence (real backend)', () => {
  test('vault + uploaded PDF survive reload; original is retrievable', async ({ page }) => {
    const matter = `Matter ${Date.now()}`;
    await page.goto('/');

    await page.getByTitle('Create new matter vault').click();
    await page.getByPlaceholder(/Matter name/i).fill(matter);
    await page.keyboard.press('Enter');
    await expect(page.getByText(matter, { exact: true })).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles(path.join(__dirname, 'fixtures', 'matter_clause.pdf'));
    await expect(page.getByText(/matter_clause\.pdf/i).first()).toBeVisible({ timeout: 20000 });
    await expect(page.getByText(/^ready$/i).first()).toBeVisible({ timeout: 30000 });

    // Reload: everything is reconstructed from the backend, not from page state.
    await page.reload();
    await page.getByText(matter, { exact: true }).click();
    await expect(page.getByText('matter_clause.pdf').first()).toBeVisible();
    await expect(page.getByText(/^ready$/i).first()).toBeVisible();

    // The stored original comes back byte-for-byte a PDF.
    const token = await page.evaluate(() => localStorage.getItem('dfrag_auth_token'));
    const auth = { Authorization: `Bearer ${token}` };
    const vaults = await (await page.request.get('/api/vaults', { headers: auth })).json();
    const vault = vaults.vaults.find((v: any) => v.vault_name === matter || v.name === matter);
    const docs = await (await page.request.get(`/api/vaults/${vault.id}/documents`, { headers: auth })).json();
    const doc = docs.documents[0];
    const file = await page.request.get(`/api/vaults/${vault.id}/documents/${doc.document_id || doc.doc_id}/file`, { headers: auth });
    expect(file.status()).toBe(200);
    expect((await file.body()).subarray(0, 5).toString()).toBe('%PDF-');
  });
});
