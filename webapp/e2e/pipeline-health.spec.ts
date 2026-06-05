import { test, expect } from '@playwright/test';
import { attachConsoleGuard, waitForAppReady } from './fixtures';

test.describe('Pipeline health card', () => {
  test('dashboard shows open-weight pipeline status', async ({ page }) => {
    const consoleErrors: string[] = [];
    attachConsoleGuard(page, consoleErrors);

    await page.goto('/');
    await waitForAppReady(page);

    const card = page.getByText(/open-weight pipeline/i).first();
    await expect(card).toBeVisible({ timeout: 20_000 });

    const healthy = page.getByText(/open-weight pipeline ok/i);
    const degraded = page.getByText(/pipeline degraded/i);
    await expect(healthy.or(degraded)).toBeVisible({ timeout: 15_000 });

    expect(consoleErrors).toEqual([]);
  });

  test('pipeline liveness API returns structured health', async ({ request }) => {
    const resp = await request.get('/api/pipeline/liveness?stale_hours=48');
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.success).toBe(true);
    expect(typeof data.healthy).toBe('boolean');
    expect(Array.isArray(data.alerts)).toBe(true);
    expect(data.checked_at).toBeTruthy();
  });

  test('poll feeds completes and pipeline card stays visible', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const pollBtn = page.getByRole('button', { name: 'Poll Feeds' });
    await pollBtn.click();
    await expect(pollBtn).toBeEnabled({ timeout: 90_000 });
    await expect(page.getByText(/poll complete|new items ingested/i)).toBeVisible({
      timeout: 90_000,
    });
    await expect(page.getByText(/open-weight pipeline/i).first()).toBeVisible();
  });
});
