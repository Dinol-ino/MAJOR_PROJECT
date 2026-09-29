import { test, expect } from './fixtures/auth';

test.describe('Research View & Network Mode', () => {
  test('reports the network mode in the header across views', async ({ page }) => {
    // Intercept mode endpoint
    await page.route('**/api/research/mode', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ mode: 'OFFLINE' }),
      });
    });

    await page.goto('/');

    // The header states the network mode; it is reported, never toggleable from the UI.
    const headerMode = page.locator('header [title*="No outbound network calls"]');
    await expect(headerMode).toBeVisible();

    // Switch view to Citation Graph
    await page.locator('aside').getByText(/Citation Graph/i).click();
    await expect(headerMode).toBeVisible();

    // Switch view to Statute Library
    await page.locator('aside').getByText(/Statute Library/i).click();
    await expect(headerMode).toBeVisible();
  });

  test('research view reports the indexed corpus and external research servers', async ({ page }) => {
    // Intercept MCP status endpoint
    await page.route('**/api/mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          current_network_mode: 'OFFLINE',
          total_registered_tools: 15,
          categories: ['LOCAL_RETRIEVAL', 'DOCUMENT_SEARCH', 'LEGAL_SEARCH', 'CURRENT_LAW'],
          active_servers: [
            {
              name: 'StitchMCP',
              description: 'Generative UI and wireframe synchronization.',
              enabled: true,
              allowed_tools: ['create_project', 'get_screen', 'generate_screen_from_text'],
            },
            {
              name: 'code-review-graph',
              description: 'AST and semantic graph analyzer.',
              enabled: true,
              allowed_tools: ['query_graph_tool', 'get_review_context_tool'],
            },
          ],
        }),
      });
    });

    await page.goto('/');

    // Navigate to the research view via the sidebar
    await page.locator('aside').getByText('Sources & Research', { exact: true }).click();

    // Check the research view renders its sections
    await expect(page.getByRole('heading', { name: /Statutory corpus \(local\)/i })).toBeVisible();
    await expect(page.locator('header [title*="No outbound network calls"]')).toBeVisible();

    await expect(page.getByRole('heading', { name: /Research capabilities/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /External research servers/i })).toBeVisible();

    // The corpus summary reports what is actually indexed, including whether dense
    // search is available - it is never presented as working when no model is loaded.
    await expect(page.getByText(/act\(s\), \d+ sections, \d+ indexed passages/i)).toBeVisible();
  });
});
