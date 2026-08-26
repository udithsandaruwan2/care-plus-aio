import { expect, test } from '@playwright/test';

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000/api/v1';
const EMAIL = process.env.PLAYWRIGHT_PATIENT_EMAIL || 'demo.patient@careplus.local';
const PASSWORD = process.env.PLAYWRIGHT_PATIENT_PASSWORD || 'CarePlus!demo';

async function patientToken(request: import('@playwright/test').APIRequestContext): Promise<string> {
  const res = await request.post(`${API}/auth/token/`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.access as string;
}

test.describe('Serah text-turn happy path', () => {
  test('social greeting replies quickly without timeout', async ({ request }) => {
    const token = await patientToken(request);
    const started = Date.now();
    const res = await request.post(`${API}/voice/turn/`, {
      headers: { Authorization: `Bearer ${token}` },
      multipart: {
        text: 'hi how are you',
        has_prior_match: 'false',
        ui_language: 'English',
        voice: 'female',
      },
    });
    const elapsed = Date.now() - started;
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    expect(body.route).toBe('CHAT');
    expect(String(body.reply || '').length).toBeGreaterThan(0);
    expect(elapsed).toBeLessThan(5000);
  });

  test('login page loads for manual UI follow-up', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1')).toBeVisible({ timeout: 15_000 });
  });
});