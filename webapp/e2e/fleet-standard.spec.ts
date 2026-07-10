import { test, expect } from '@playwright/test';

const FE = 'http://127.0.0.1:10947';
const BE = 'http://127.0.0.1:10946';

test.describe('Fleet Standard Audit', () => {

	test('Backend health returns 200', async ({ request }) => {
		const resp = await request.get(`${BE}/api/health`);
		expect(resp.status()).toBe(200);
	});

	test('Frontend loads without crashing', async ({ page }) => {
		await page.goto(FE, { timeout: 15000 });
		await page.waitForSelector('#root', { timeout: 10000 });
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});
		await page.waitForTimeout(3000);
		expect(consoleErrors.length).toBe(0);
	});

	test('Dashboard has fleet data-testid attributes', async ({ page }) => {
		await page.goto(FE, { timeout: 15000 });
		await expect(page.locator('[data-testid="dashboard"]')).toBeAttached({ timeout: 10000 });
		await expect(page.locator('[data-testid="backend-status"]')).toBeAttached();
		await expect(page.locator('[data-testid="connection-status"]')).toBeAttached();
		await expect(page.locator('[data-testid="connection-label"]')).toBeAttached();
	});

	test('Dashboard has KPI cards', async ({ page }) => {
		await page.goto(FE, { timeout: 15000 });
		for (const testid of ['kpi-feeds', 'kpi-today', 'kpi-unread', 'kpi-critical']) {
			await expect(page.locator(`[data-testid="${testid}"]`)).toBeAttached({ timeout: 10000 });
		}
	});

	test('Chat page has fleet data-testid attributes', async ({ page }) => {
		await page.goto(`${FE}/chat`, { timeout: 15000 });
		await expect(page.locator('[data-testid="chat-page"]')).toBeAttached({ timeout: 10000 });
		await expect(page.locator('[data-testid="chat-controls"]')).toBeAttached();
		await expect(page.locator('[data-testid="chat-input"]')).toBeAttached();
		await expect(page.locator('[data-testid="chat-send"]')).toBeAttached();
		await expect(page.locator('[data-testid="chat-clear"]')).toBeAttached();
		await expect(page.locator('[data-testid="chat-export"]')).toBeAttached();
		await expect(page.locator('[data-testid="personality-select"]')).toBeAttached();
	});

	test('Navigation sidebar entries are clickable', async ({ page }) => {
		await page.goto(FE, { timeout: 15000 });
		const navLinks = page.locator('nav a');
		const count = await navLinks.count();
		expect(count).toBeGreaterThanOrEqual(10);
	});

	test('Chat page has example prompts', async ({ page }) => {
		await page.goto(`${FE}/chat`, { timeout: 15000 });
		await expect(page.locator('[data-testid="example-prompts"]')).toBeAttached({ timeout: 10000 });
		const promptButtons = page.locator('[data-testid="example-prompts"] button');
		const count = await promptButtons.count();
		expect(count).toBeGreaterThanOrEqual(6);
	});

});
