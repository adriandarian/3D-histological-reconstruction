import {test, expect} from '@playwright/test';

test('the serial-section trace plays on entry, replays, and settles for reduced motion', async ({page}) => {
  await page.goto('/');
  const plate = page.locator('.method-plate');
  const activeRings = () => plate.evaluate(node =>
    node.getAnimations({subtree: true}).filter(animation => animation.effect.target.tagName === 'ellipse').length);
  await plate.scrollIntoViewIfNeeded();
  await expect.poll(activeRings).toBeGreaterThan(0);
  await expect.poll(activeRings).toBe(0);
  await plate.getByRole('button', {name: 'Replay trace'}).click();
  await expect.poll(activeRings).toBeGreaterThan(0);
  await page.emulateMedia({reducedMotion: 'reduce'});
  await expect(plate.locator('.trace-replay')).toBeHidden();
  await expect.poll(activeRings).toBe(0);
});
