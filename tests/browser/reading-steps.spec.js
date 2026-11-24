import {test, expect} from '@playwright/test';

async function read(step) {
  await step.evaluate(node => node.scrollIntoView({block: 'center'}));
  await expect(step).toHaveAttribute('aria-current', 'step');
}

test('reading forward and backward selects the corresponding part of the duct', async ({page}) => {
  await page.goto('/');
  const chapter = page.locator('#reconstruction');
  await expect(chapter.locator('#branch-story')).not.toHaveAttribute('data-reading-disabled', '');
  const steps = chapter.locator('[data-reading-step]');
  await read(steps.first());
  const first = await page.locator('#slice-z').inputValue();
  await read(steps.last());
  await expect(page.locator('#slice-z')).not.toHaveValue(first);
  await read(steps.first());
  await expect(page.locator('#slice-z')).toHaveValue(first);
});

test('scroll guidance respects a reader who prefers reduced motion', async ({page}) => {
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.goto('/');
  const toggle = page.locator('#reconstruction [data-reading-toggle]');
  await expect(toggle).toHaveText('Follow the text');
  await toggle.click();
  await expect(toggle).toHaveText('Pause scroll control');
});

test('the camera travels between paragraphs and retraces the same intermediate view', async ({page}) => {
  await page.setViewportSize({width: 1200, height: 900});
  await page.goto('/');
  const story = page.locator('#branch-story');
  await expect(story).not.toHaveAttribute('data-reading-disabled', '');
  const steps = story.locator('[data-reading-step]');
  const canvas = story.locator('#ray-host canvas');
  const stops = await steps.evaluateAll(nodes => nodes.map(node => {
    const rect = node.getBoundingClientRect();
    return scrollY + rect.top + rect.height / 2 - innerHeight * .55;
  }));
  async function at(fraction) {
    const top = stops[0] + (stops[1] - stops[0]) * fraction;
    await page.evaluate(y => window.scrollTo(0, y), top);
    await expect(steps.first()).toHaveAttribute('aria-current', 'step');
    return canvas.screenshot();
  }
  const early = await at(.15);
  const middle = await at(.32);
  const later = await at(.44);
  expect(early.equals(middle)).toBe(false);
  expect(middle.equals(later)).toBe(false);
  expect((await at(.32)).equals(middle)).toBe(true);
});

test('the slide guide switches image frames, pauses for edits and resumes at the text', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  const chapter = page.locator('#synthetic');
  const steps = chapter.locator('[data-reading-step]');
  const slider = chapter.locator('[data-ui="section"]');
  const frame = chapter.locator('[data-ui="frame"]');
  await read(steps.nth(1));
  await expect(slider).toHaveValue('20');
  await expect(frame).toHaveValue('source');
  await read(steps.last());
  await expect(frame).toHaveValue('registered');
  await chapter.locator('[data-ui="next"]').click();
  await steps.first().evaluate(node => node.scrollIntoView({block:'center'}));
  await expect(slider).toHaveValue('21');
  await chapter.getByRole('button', {name: 'Follow the text'}).click();
  await expect(slider).toHaveValue('18');
});
