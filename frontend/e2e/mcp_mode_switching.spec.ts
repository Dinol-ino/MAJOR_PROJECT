import { test, expect } from '@playwright/test';

test.describe('MCP Gateway & Network Mode Switching', () => {
  test('always shows ModeIndicator in header across views', async ({ page }) => {
    // Intercept mode endpoint
    await page.route('**/api/research/mode', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ mode: 'OFFLINE' }),
      });
    });

    await page.goto('/');

    // Header ModeIndicator must be visible on main chat view
    const headerMode = page.locator('header').getByText(/Mode: OFFLINE/i);
    await expect(headerMode).toBeVisible();

    // Switch view to Citation Graph
    await page.locator('aside').getByText(/Citation Graph/i).click();
    await expect(headerMode).toBeVisible();

    // Switch view to Statute Library
    await page.locator('aside').getByText(/Statute Library/i).click();
    await expect(headerMode).toBeVisible();
  });

  test('navigates to MCP Gateway view and displays server status and network mode', async ({ page }) => {
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

    // Navigate to MCP Tools via Sidebar text item
    await page.getByText(/API & MCP Tools/i).click();

    // Check Header & Network Mode in view
    await expect(page.getByRole('heading', { name: /MCP Gateway & Tool Permissions/i })).toBeVisible();
    await expect(page.locator('header').getByText(/Mode: OFFLINE/i)).toBeVisible();

    // Check Categories Banner
    await expect(page.getByText(/Active Tool Categories & Policies/i)).toBeVisible();
    await expect(page.getByText('LOCAL_RETRIEVAL')).toBeVisible();
    await expect(page.getByText('DOCUMENT_SEARCH')).toBeVisible();

    // Check Registered Servers
    await expect(page.getByText('StitchMCP')).toBeVisible();
    await expect(page.getByText('code-review-graph')).toBeVisible();
    await expect(page.getByText(/create_project/i)).toBeVisible();

    // Check REST API Reference
    await expect(page.getByText(/Core REST API Endpoints/i)).toBeVisible();
    await expect(page.getByText('/chat', { exact: true })).toBeVisible();
    await expect(page.getByText('/mcp/tool-call')).toBeVisible();
  });
});
