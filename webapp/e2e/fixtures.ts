import { expect, type Page } from '@playwright/test';

/** Sidebar nav — must match Shell.tsx NAV labels */
export const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', heading: 'AI Intelligence Dashboard' },
  { href: '/news', label: 'News Feed', heading: 'News Feed' },
  { href: '/bundles', label: 'Bundles', heading: 'Interest Bundles' },
  { href: '/feeds', label: 'Sources', heading: 'Feed Sources' },
  { href: '/digest', label: 'Digest', heading: 'Daily Intelligence Digest' },
  { href: '/apps', label: 'Fleet Apps', heading: 'Fleet Apps Hub' },
  { href: '/tools', label: 'Tools', heading: 'Tools Hub' },
  { href: '/help', label: 'Docs', heading: 'Documentation Hub' },
  { href: '/settings', label: 'Settings', heading: 'Settings & Configuration' },
  { href: '/tests', label: 'Tests', heading: 'System Tests' },
  { href: '/logs', label: 'Logs', heading: 'System Logs' },
] as const;

export async function waitForAppReady(page: Page) {
  await expect(page.getByText('AIWatcher').first()).toBeVisible();
}

export async function navigateViaSidebar(page: Page, label: string) {
  await page.getByRole('link', { name: label, exact: true }).click();
}

export async function expectPageHeading(page: Page, heading: string) {
  await expect(page.getByRole('heading', { name: heading, level: 1 })).toBeVisible({
    timeout: 15_000,
  });
}

export function attachConsoleGuard(page: Page, errors: string[]) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (!text.includes('favicon') && !text.includes('Fleet discovery failed')) {
        errors.push(text);
      }
    }
  });
  page.on('pageerror', (err) => errors.push(err.message));
}
