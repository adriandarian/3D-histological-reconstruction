import { test, expect } from "@playwright/test";

test("TCIA separates withheld pathologist contours from predicted extent", async ({ page }) => {
  await page.goto("/?dataset=tcia-prostate");
  await expect(page.locator("#source-readout")).toContainText("withheld level");
  await expect(page.locator("#ray-host canvas")).toBeVisible();
  const image = page.locator("#source-image");
  const comparison = await image.evaluate(c => c.toDataURL());
  await page.locator("#reference-overlay").uncheck();
  expect(await image.evaluate(c => c.toDataURL())).not.toBe(comparison);
  await page.locator("#slice-z").fill("0");
  await expect(page.locator("#source-readout")).toContainText("aaa 0051 BSlice.tif");
  await expect(page.locator("#source-readout")).toContainText("pathologist contour anchor");
});
