import { test, expect } from '@playwright/test';

test('a visible phantom surface opens the matching labeled source voxel', async ({page, request}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#source-readout')).toContainText('Section 17 / 32', {timeout:20000});
  await page.locator('#histology').uncheck();
  await page.locator('#overlay').uncheck();
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
