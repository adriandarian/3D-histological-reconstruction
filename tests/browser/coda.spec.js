import { existsSync } from "node:fs";
import { test, expect } from "@playwright/test";

test("locally generated CODA trace maps the distal section to the native slide", async ({ page, request }) => {
  test.skip(!existsSync("public/data/coda-lung/manifest.json"), "Generate the pinned CODA slides locally");
  const manifest = await (await request.get("/data/coda-lung/manifest.json")).json();
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
});
