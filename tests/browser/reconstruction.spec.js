import { test, expect } from '@playwright/test';

test('slice buttons move the source section and stop at its boundaries', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  const slider = page.locator('#slice-z');
  const previous = page.locator('[data-step-for="slice-z"][data-delta="-1"]');
  const next = page.locator('[data-step-for="slice-z"][data-delta="1"]');
  await expect(next).toBeEnabled();
  await slider.focus();
  await slider.press('Home');
  await expect(previous).toBeDisabled();
  await next.click();
  await expect(page.locator('#source-readout')).toContainText('Section 2 / 32');
  await previous.click();
  await expect(page.locator('#source-readout')).toContainText('Section 1 / 32');
  await slider.press('End');
  await expect(next).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('workspace navigation follows the selected section on a narrow screen', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  const nav = page.getByRole('navigation', {name: 'Workspace sections'});
  for (const name of ['Connection evidence', 'Plane-stack comparison', 'Orthogonal slices', 'Volume explorer']) {
    const link = nav.getByRole('link', {name});
    await link.click();
    await expect(link).toHaveAttribute('aria-current', 'location');
    const heading = page.locator(await link.getAttribute('href'));
    const [target, menu] = await Promise.all([heading.boundingBox(), nav.boundingBox()]);
    expect(target.y).toBeGreaterThanOrEqual(menu.y + menu.height - 1);
  }
});

test('a reader can follow a finding into its figure and switch cases', async ({page}) => {
  await page.goto('/');
  const plate = page.locator('#overview img');
  await expect.poll(() => plate.evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
  await page.locator('#discussion a[href*="dataset=capillary"]').click();
  await expect(page.locator('#volume-series')).toHaveValue('capillary');
  await expect(page.locator('#case-reading-note')).toContainText('cyan reference');
  await page.locator('#volume-series').selectOption('field-gap');
  await expect(page.locator('#case-reading-note')).toContainText('Seven sections');
});

async function pickVisibleSurface(page) {
  const view = page.locator('#ray-host canvas');
  const screenshot = await view.screenshot();
  // Choose a lit, blue surface pixel. The background is dark green and the cursor is yellow.
  const position = await page.evaluate(async png => {
    const image = new Image();
    image.src = 'data:image/png;base64,' + png;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(image, 0, 0);
    const pixels = ctx.getImageData(0,0,canvas.width,canvas.height).data;
    const hits = [];
    for (let i=0; i<pixels.length; i+=4) {
      if (pixels[i+2] > 150 && pixels[i+2] > pixels[i]+25)
        hits.push(i/4);
    }
    if (!hits.length) throw Error('No visible anatomy surface');
    const pixel = hits[Math.floor(hits.length*.75)];
    return {x: pixel%canvas.width, y: Math.floor(pixel/canvas.width)};
  }, screenshot.toString('base64'));
  await view.click({position});
}

test('a visible phantom surface opens the matching labeled source voxel', async ({page, request}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#source-readout')).toContainText('Section 17 / 32', {timeout:20000});
  await page.locator('#histology').uncheck();
  await page.locator('#overlay').uncheck();
  await pickVisibleSurface(page);
  await expect(page.locator('#overlay')).toBeChecked();
  const xyz = await Promise.all(['x','y','z'].map(async axis => Number(await page.locator('#slice-'+axis).inputValue())));
  const [x,y,z] = xyz;
  const manifest = await (await request.get('/branching/manifest.json')).json();
  const labels = await (await request.get('/branching/'+manifest.labels)).body();
  const [width,height,depth] = manifest.dimensions;
  expect(labels[(z*height+y)*width+x]).toBe(2);
  await expect(page.locator('#source-readout')).toHaveText(`Section ${z+1} / ${depth} · Source X ${x}, Y ${y} px`);
  const source = page.locator('#source-image');
  const withOutline = await source.evaluate(c => c.toDataURL());
  await page.locator('#overlay').uncheck();
  expect(await source.evaluate(c => c.toDataURL())).not.toBe(withOutline);
  await page.locator('#xz').click({position:{x:1,y:1}});
  await expect(page.locator('#slice-z')).toHaveValue('0');
  await expect(page.locator('#source-readout')).toContainText('Section 1 / 32');
  expect(errors).toEqual([]);
});

test('a cortical capillary pick links to its measured section and published reference', async ({page, request}) => {
  const manifest = await (await request.get('/capillary/manifest.json')).json();
  const labels = await (await request.get('/capillary/'+manifest.labels)).body();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/?dataset=capillary');
  await expect(page.locator('#source-readout')).toContainText('H01 section 600');
  await expect(page.locator('#volume-status')).toContainText('Registered serial electron micrographs');
  await expect(page.locator('#pair-evidence')).toContainText('600–601');
  await expect(page.locator('#source-readout')).toContainText('Author seed');
  await expect(page.locator('#pair-evidence')).toContainText('2 unmatched fragments');
  await expect(page.locator('#foreground-name')).toHaveText('Sampled EM field');

  await page.locator('#histology').uncheck();
  await page.locator('#overlay').uncheck();
  await pickVisibleSurface(page);
  await expect(page.locator('#overlay')).toBeChecked();
  const [x,y,z] = await Promise.all(['x','y','z'].map(async axis =>
    Number(await page.locator('#slice-'+axis).inputValue())));
  const [width,height] = manifest.dimensions;
  expect(labels[(z*height+y)*width+x]).toBe(2);
  await expect(page.locator('#source-readout')).toContainText('H01 section '+(600+z));
  const png = new URL(await page.locator('#source-png').getAttribute('href'));
  const location = new URL(await page.locator('#source-h01').getAttribute('href'));
  const state = JSON.parse(decodeURIComponent(location.hash.slice(2)));
  expect(state.position).toEqual([249800 + 8*(x+.5),175000 + 8*(y+.5),600+z+.5]);
  expect(png.pathname).toBe('/capillary/'+manifest.sections[z]);
  expect((await request.get(png.href)).headers()['content-type']).toContain('image/png');
  await expect(page.locator('#reference-tiff')).toHaveAttribute('href',
    new RegExp('image'+String(600+z).padStart(5,'0')+'z_249800x_175000y.tiff$'));

  const source = page.locator('#source-image');
  const withReference = await source.evaluate(c => c.toDataURL());
  await page.locator('#reference-overlay').uncheck();
  expect(await source.evaluate(c => c.toDataURL())).not.toBe(withReference);
  await page.locator('#slice-z').fill(String(manifest.dimensions[2]-1));
  await expect(page.locator('#pair-evidence')).toContainText('Last section');
  await expect(page.locator('#source-readout')).toContainText('Held-out comparison');
  await page.locator('#volume-series').selectOption('branching');
  await expect(page.locator('#capillary-evidence')).toBeHidden();
  await expect(page.locator('#reference-control')).toBeHidden();
  expect(errors).toEqual([]);
});

test("pancreas links each registered section to its unwarped source preview", async ({page, request}) => {
  await page.goto("/?dataset=pancreas");
  const registration = await (await request.get("/data/real/manifest.json")).json();
  await expect(page.locator("#evidence-class")).toHaveText("EXPLORATORY H&E");
  await expect(page.locator("#source-readout")).toContainText(registration.sections[9].filename);
  for (const z of [10, 9]) {
    await page.locator("#slice-z").fill(String(z));
    const section = registration.sections[z];
    await expect(page.locator("#source-readout")).toContainText(section.filename);
    await expect(page.locator("#source-readout")).toContainText("Registration: " + section.status);
    const link = page.locator("#section-image");
    await expect(link).toBeVisible();
    const url = new URL(await link.getAttribute("href"));
    expect(url.pathname).toBe("/data/real/" + section.source);
    expect((await request.get(url.href)).headers()["content-type"]).toMatch(/^image[/]/);
  }
});
