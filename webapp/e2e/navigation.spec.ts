import { test, expect } from '@playwright/test';
import {
  NAV_ITEMS,
  navigateViaSidebar,
  expectPageHeading,
  waitForAppReady,
} from './fixtures';

test.describe('Sidebar navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
  });

  for (const item of NAV_ITEMS) {
    test(`navigates to ${item.label} (${item.href})`, async ({ page }) => {
      await navigateViaSidebar(page, item.label);
      await expect(page).toHaveURL(new RegExp(`${item.href.replace('/', '\\/')}(\\?.*)?$`));
      await expectPageHeading(page, item.heading);
    });
  }

  test('brand AIWatcher is visible', async ({ page }) => {
    await expect(page.getByText('AIWatcher').first()).toBeVisible();
  });
});
