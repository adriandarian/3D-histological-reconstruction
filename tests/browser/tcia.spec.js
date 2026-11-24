import { test, expect } from "@playwright/test";

test("TCIA separates withheld pathologist contours from predicted extent", async ({ page }) => {
  await page.goto("/?dataset=tcia-prostate");
  await expect(page.locator("#source-readout")).toContainText("withheld level");
  await expect(page.locator("#evidence-class")).toHaveText("FAILED HELD-OUT H&E");
  await expect(page.locator("#volume-status")).toContainText("Failed held-out tumor localization. Predicted Dice C 0.0091, E 0.0000. Nearest anchor C 0.0434, E 0.0625.");
  await expect(page.locator("#section-image")).toHaveAttribute("href", /tcia-prostate[/]E[.]png$/);
  await expect(page.locator("#ray-host canvas")).toBeVisible();
  const image = page.locator("#source-image");
  const comparison = await image.evaluate(c => c.toDataURL());
  await page.locator("#reference-overlay").uncheck();
  expect(await image.evaluate(c => c.toDataURL())).not.toBe(comparison);
  await page.locator("#slice-z").fill("0");
  await expect(page.locator("#source-readout")).toContainText("aaa 0051 BSlice.tif");
  await expect(page.locator("#source-readout")).toContainText("pathologist contour anchor");
});
