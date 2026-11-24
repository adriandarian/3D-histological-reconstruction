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
    const panel = page.locator(`#${dataset}`);
    const other = page.locator(dataset === 'real' ? '#synthetic' : '#real');
    const otherSlider = other.getByRole('slider');
    await page.waitForLoadState('networkidle');
    const otherSection = await otherSlider.inputValue();
    const slider = panel.locator('[data-ui="section"]');
    await expect(slider).toHaveAttribute('max', String(manifest.sections.length - 1));
    const initial = Number(await slider.inputValue());
    await panel.locator('[data-ui="next"]').click();
    await expect(slider).toHaveValue(String(initial + 1));
    await expect(otherSlider).toHaveValue(otherSection);
    await panel.locator('[data-ui="prev"]').click();
    await expect(slider).toHaveValue(String(initial));
    const coords = panel.locator('[data-ui="coords"]');
    const before = await coords.textContent();
    const slideViewer = panel.locator('[data-ui="osd"]');
    const slideBounds = await slideViewer.boundingBox();
    await slideViewer.click({position: {
      x: Math.floor(slideBounds.width / 2 + 24),
      y: Math.floor(slideBounds.height / 2),
    }});
    await expect(coords).not.toHaveText(before);
    const raw = manifest.sections[initial].source;
    const sourceLoad = page.waitForRequest(req => decodeURI(req.url()).endsWith(raw));
    await panel.locator('[data-ui="frame"]').selectOption('source');
    await sourceLoad;
    await panel.locator('[data-ui="frame"]').selectOption('registered');
    const canvas = panel.locator('[data-ui="volume"] canvas');
    await expect(canvas).toBeVisible();
    await canvas.scrollIntoViewIfNeeded();
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
    await panel.locator('[data-ui="reset"]').click();
    expect(errors).toEqual([]);
  });
}

test('an unavailable export explains how to recover', async ({ page }) => {
  await page.route('**/data/real/manifest.json', route => route.fulfill({status: 404}));
  await page.goto('/');
  let panel = page.locator('#real');
  await expect(panel.locator('[data-ui="status"]')).toContainText('public/data/real/manifest.json');
  await expect(panel.locator('[data-ui="section"]')).toBeHidden();
  panel = page.locator('#synthetic');
  await expect(panel.locator('[data-ui="count"]')).toContainText('/ 36');
  await expect(panel.locator('[data-ui="volume"] canvas')).toBeVisible();
});
test('a point selected in a rotated source section maps into the registered frame', async ({ page, request }) => {
  const response = await request.get('/data/real/manifest.json');
  test.skip(!response.headers()['content-type']?.includes('application/json'), 'Generate real series first');
  const manifest = await response.json();
  const index = manifest.sections.findIndex(s => Math.abs(s.transform?.[1][0]) > 0.03);
  test.skip(index < 0, 'Requires an export containing a rotated section');
  await page.goto('/?dataset=real');
  const panel = page.locator('#real');
  const slider = panel.locator('[data-ui="section"]');
  await expect(slider).toHaveAttribute('max', String(manifest.sections.length - 1));
  await slider.fill(String(index));
  await page.waitForLoadState('networkidle');
  const slide = panel.locator('[data-ui="osd"]');
  const click = async () => {
    await slide.click();
    return (await panel.locator('[data-ui="coords"]').textContent()).match(/\d+/g).map(Number);
  };
  const [x,y] = await click();
  await panel.locator('[data-ui="frame"]').selectOption('source');
  await page.waitForLoadState('networkidle');
  const [rx,ry] = await click();
  const [[a,b,dx],[c,d,dy]] = manifest.sections[index].transform;
  const grid = manifest.sections[index].pullGrid;
  const correction = [0, 0];
  if (grid) {
    const u = rx / (manifest.width - 1) * (grid[0].length - 1);
    const v = ry / (manifest.height - 1) * (grid.length - 1);
    for (const row of new Set([Math.floor(v), Math.ceil(v)])) {
      for (const col of new Set([Math.floor(u), Math.ceil(u)])) {
        const weight = (1 - Math.abs(v - row)) * (1 - Math.abs(u - col));
        for (let k = 0; k < 2; k++) correction[k] += grid[row][col][k] * weight;
      }
    }
  }
  expect(Math.abs(rx + correction[0] - (a*x+b*y+dx))).toBeLessThan(2);
  expect(Math.abs(ry + correction[1] - (c*x+d*y+dy))).toBeLessThan(2);
});
