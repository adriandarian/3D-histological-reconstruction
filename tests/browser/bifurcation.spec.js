import { test, expect } from "@playwright/test";

for (const series of ["bifurcation", "vascular-fork"]) {
  test(`both daughters link to distinct regions on the same measured section in ${series}`, async ({ page, request }) => {
    const base = "/" + series + "/";
    const manifest = await (await request.get(base + "manifest.json")).json();
    const trace = await (await request.get(base + manifest.reference)).json();
    const result = await (await request.get(base + manifest.validation)).json();
    const z = result.planes.findIndex(row => row.distinctDaughters === true);
    expect(z).toBeGreaterThan(0);
    await page.goto("/?dataset=" + series);
    const readout = page.locator("#source-readout");
    await expect(readout).toContainText("EM section " + trace.planes[z].z);
    const row = result.planes[z];
    const arms = row.points.filter(p => ["daughterA","daughterB"].includes(p.arm));
    expect(new Set(arms.map(p => p.component)).size).toBe(2);
    expect(arms.every(p => p.hit)).toBe(true);
    const xy = [];
    for (const arm of ["daughterA", "daughterB"]) {
      const point = trace.planes[z].points.find(p => p.arm === arm);
      await page.locator('[data-arm="' + arm + '"]').click();
      await expect(page.locator("#slice-z")).toHaveValue(String(z));
      await expect(page.locator("#slice-x")).toHaveValue(String(Math.round(point.x)));
      await expect(page.locator("#slice-y")).toHaveValue(String(Math.round(point.y)));
      xy.push([point.x, point.y]);
    }
    expect(xy[0]).not.toEqual(xy[1]);
    const location = new URL(await page.locator("#fork-location").getAttribute("href"));
    expect(JSON.parse(decodeURIComponent(location.hash.slice(2))).position[2]).toBe(trace.planes[z].z+.5);
    await expect(page.locator("#fork-result")).toContainText("distinct predicted regions");
    await expect(page.locator("#fork-image")).toHaveAttribute("href", new RegExp(manifest.sections[z] + "$"));
    const outline = await page.locator("#source-image").evaluate(c => c.toDataURL());
    await page.locator("#point-overlay").uncheck();
    expect(await page.locator("#source-image").evaluate(c => c.toDataURL())).not.toBe(outline);
    await page.locator('[data-arm="parent"]').click();
    const parentZ = Number(await page.locator("#slice-z").inputValue());
    expect(trace.planes[parentZ].points.some(p => p.arm === "parent")).toBe(true);
    await page.locator("#volume-series").selectOption("branching");
    await expect(page.locator("#fork-evidence")).toBeHidden();
  });
}
