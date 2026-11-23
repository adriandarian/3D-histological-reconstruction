import { test, expect } from "@playwright/test";

test("locally generated CODA trace maps the distal section to the native slide", async ({ page, request }) => {
  const response = await request.get("/data/coda-lung/manifest.json");
  test.skip(!response.headers()["content-type"]?.includes("application/json"), "Requires the local CODA image export");
  const manifest = await response.json();
  await page.goto("/?dataset=coda-lung");
  await expect(page.locator("#source-readout")).toContainText("lungs_021.ndpi");
  await expect(page.locator("#ray-host canvas")).toBeVisible();
  await page.locator("#slice-z").fill("19");
  const readout = page.locator("#source-readout");
  await expect(readout).toContainText("lungs_039.ndpi");
  await expect(readout).toContainText("190 µm");
  const [x,y] = await Promise.all(["x","y"].map(axis => page.locator("#slice-"+axis).inputValue()));
  const section = manifest.sourceSections[19];
  const position = await page.evaluate(({section, x, y, width}) => {
    const ctx = document.querySelector("#source-image");
    const [a,b] = section.transform;
    const matrix = new DOMMatrix([a[0],b[0],a[1],b[1],a[2],b[2]]).inverse();
    const scale = ctx.width / width;
    const p = matrix.transformPoint({x:(+x+.5)*scale-.5, y:(+y+.5)*scale-.5});
    return [p.x,p.y].map((v,i) => Math.floor(section.origin[i]+(v+.5)*section.step));
  }, {section, x, y, width:manifest.dimensions[0]});
  await expect(readout).toContainText("X "+position[0]+", Y "+position[1]);
  await expect(page.locator("#z-value")).toHaveText("39");
  const graph = await request.get("/data/coda-lung/connections.json");
  if (graph.headers()["content-type"]?.includes("application/json")) {
    await page.locator("#connection-interval").selectOption("18");
    await expect(page.locator("#connection-sampling")).toContainText("undistributed section 038");
    await expect(page.locator("#connection-flanks canvas")).toHaveCount(2);
    await expect(page.locator("#connection-flanks")).toContainText("NDPI level-zero pixel edges");
    await expect(page.locator('#connection-flags [data-flag="verified_identity"]')).toHaveCount(0);
  }
});

test("absent local-only data clears the previous selection and preserves review status", async ({ page }) => {
  await page.route("**/data/coda-lung/manifest.json", route => route.fulfill({status: 404}));
  await page.goto("/");
  await expect(page.locator("#section-image")).toBeVisible();
  await page.locator("#volume-series").selectOption("coda-lung");
  await expect(page.locator("#volume-status")).toContainText("local CODA reconstruction is unavailable");
  await expect(page.locator("#evidence-class")).toHaveText("LOCAL-ONLY H&E / REVIEW PENDING");
  await expect(page.locator("#section-image")).toBeHidden();
  await expect(page.locator("#source-readout")).toBeEmpty();
  await expect(page.locator("#ray-host canvas")).toHaveCount(0);
  await page.locator("#volume-series").selectOption("branching");
  await expect(page.locator("#section-image")).toBeVisible();
});
