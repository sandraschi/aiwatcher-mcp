import { test, expect } from '@playwright/test';
import { attachConsoleGuard, waitForAppReady } from './fixtures';

test.describe('Dashboard smoke', () => {
  test('loads dashboard with stats cards', async ({ page }) => {
    const consoleErrors: string[] = [];
    attachConsoleGuard(page, consoleErrors);

    await page.goto('/');
    await waitForAppReady(page);
    await expect(
      page.getByRole('heading', { name: 'AI Intelligence Dashboard', level: 1 }),
    ).toBeVisible();
    await expect(page.getByText('Active Feeds').first()).toBeVisible();

    expect(consoleErrors).toEqual([]);
  });

  test('tools page lists MCP tools from capabilities', async ({ page }) => {
    await page.goto('/tools');
    await waitForAppReady(page);
    await expect(page.getByRole('heading', { name: 'Tools Hub', level: 1 })).toBeVisible();
    await expect(page.getByText(/tools · dynamically discovered/i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
