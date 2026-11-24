import { test, expect } from '@playwright/test';

for (const selector of ['#ray-host', '#synthetic [data-ui="volume"]']) {
  test(`focused camera orbits, pans, zooms and resets in ${selector}`, async ({page}) => {
    await page.goto('/');
    const canvas = page.locator(selector + ' canvas');
    await page.waitForLoadState('networkidle');
    await canvas.scrollIntoViewIfNeeded();
    await canvas.focus();
    await expect(canvas).toHaveAccessibleDescription(/Orbit.*Pan.*Zoom/i);
    await canvas.press('Home');
    const original = await canvas.screenshot();
    for (const key of ['ArrowRight', 'Shift+ArrowUp', '=']) {
      await canvas.press(key);
      expect((await canvas.screenshot()).equals(original)).toBe(false);
      await canvas.press('Home');
      expect((await canvas.screenshot()).equals(original)).toBe(true);
    }
    await canvas.press('Tab');
    await expect(canvas).not.toBeFocused();
  });
}

test('only a primary click or keyboard pick moves the stack cursor', async ({page}) => {
  await page.goto('/');
  const panel = page.locator('#synthetic');
  const canvas = panel.locator('[data-ui="volume"] canvas');
  const coords = panel.locator('[data-ui="coords"]');
  await page.waitForLoadState('networkidle');
  await panel.locator('.stack-readout summary').click();
  await expect(coords).toContainText('Registered X');
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  const point = {x: Math.round(box.width / 2 + 18), y: Math.round(box.height / 2)};
  const original = await coords.innerText();
  await canvas.click({position: point, button: 'right'});
  await expect(coords).toHaveText(original);
  await canvas.click({position: point, modifiers: ['Shift']});
  await expect(coords).toHaveText(original);
  const x = box.x + point.x, y = box.y + point.y;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 48, y);
  await page.mouse.move(x, y);
  await page.mouse.up();
  await expect(coords).toHaveText(original);
  await canvas.click({position: point});
  await expect(coords).not.toHaveText(original);
  const picked = await coords.innerText();
  await canvas.press('Enter');
  await expect(coords).not.toHaveText(picked);
});
