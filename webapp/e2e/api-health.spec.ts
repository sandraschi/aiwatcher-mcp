import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

test.describe('API & proxy health', () => {
  test('backend /health responds', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:10946/health');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(body.server).toBe('aiwatcher-mcp');
    expect(body.version).toBeTruthy();
  });

  test('frontend proxies /api/health', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:10947/api/health');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe('ok');
  });

  test('frontend proxies /api/capabilities', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:10947/api/capabilities');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.server).toBeTruthy();
    expect(Array.isArray(body.tool_surface?.atomic_tools)).toBeTruthy();
  });

  test('frontend proxies /api/stats', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:10947/api/stats');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(typeof body.active_feeds).toBe('number');
  });
});
