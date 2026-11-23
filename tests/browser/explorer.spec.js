import { test, expect } from '@playwright/test';

for (const dataset of ['synthetic', 'real']) {
  test(`${dataset} sections, cursor and orbit`, async ({ page, request }) => {
    const response = await request.get(`/data/${dataset}/manifest.json`);
    const available = response.headers()['content-type']?.includes('application/json');
    test.skip(dataset === 'real' && !available, 'Generate the optional real dataset first');
    const manifest = await response.json();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.locator('#dataset').selectOption(dataset);
    const slider = page.locator('#section');
    await expect(slider).toHaveAttribute('max', String(manifest.sections.length - 1));
    const initial = Number(await slider.inputValue());
    await page.locator('#next').click();
    await expect(slider).toHaveValue(String(initial + 1));
    await page.locator('#prev').click();
    await expect(slider).toHaveValue(String(initial));
    const coords = page.locator('#coords');
    const before = await coords.textContent();
    await page.locator('#osd').click({position: {x: 135, y: 115}});
    await expect(coords).not.toHaveText(before);
    const raw = manifest.sections[initial].source;
    const sourceLoad = page.waitForRequest(req => decodeURI(req.url()).endsWith(raw));
    await page.locator('#frame').selectOption('source');
    await sourceLoad;
    await page.locator('#frame').selectOption('registered');
    const canvas = page.locator('#volume canvas');
    await expect(canvas).toBeVisible();
    const rect = await canvas.boundingBox();
    await page.waitForLoadState('networkidle');
    await canvas.click({position: {x: Math.round(rect.width / 2), y: Math.round(rect.height / 2)}});
    const match = (await coords.textContent()).match(/X (\d+) px.*Y (\d+) px/);
    expect(Math.abs(Number(match[1]) - manifest.width / 2)).toBeLessThan(10);
    expect(Math.abs(Number(match[2]) - manifest.height / 2)).toBeLessThan(10);
    const prior = await canvas.screenshot();
    await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
    await page.mouse.down();
    await page.mouse.move(rect.x + rect.width * .75, rect.y + rect.height * .65, {steps: 8});
    await page.mouse.up();
    await expect.poll(async () => (await canvas.screenshot()).equals(prior)).toBe(false);
    await page.locator('#reset').click();
    expect(errors).toEqual([]);
  });
}

test('an unavailable export explains how to recover', async ({ page }) => {
  await page.route('**/data/real/manifest.json', route => route.fulfill({status: 404}));
  await page.goto('/');
  await page.locator('#dataset').selectOption('real');
  await expect(page.locator('#status')).toContainText('public/data/real/manifest.json');
  await expect(page.locator('#section')).toBeDisabled();
  await page.locator('#dataset').selectOption('synthetic');
  await expect(page.locator('#count')).toContainText('/ 36');
  await expect(page.locator('#volume canvas')).toBeVisible();
});
