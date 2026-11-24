import {test, expect} from "@playwright/test";

test("a 3D contact marker selects its evidence edge", async ({page}) => {
  await page.goto("/?dataset=field-gap");
  await page.locator("#connection-interval").selectOption("0");
  await page.locator("#contact-markers").check();
  // Isolate the selectable markers from the anatomy color shader.
  await page.locator("#anatomy").uncheck();
  await page.locator("#histology").uncheck();
  const canvas = page.locator("#ray-host canvas");
  const image = (await canvas.screenshot()).toString("base64");
  const points = await page.evaluate(async data => {
    const img = new Image();
    img.src = "data:image/png;base64," + data;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = img.width; c.height = img.height;
    const ctx = c.getContext("2d");
    ctx.drawImage(img,0,0);
    const rgba = ctx.getImageData(0,0,c.width,c.height).data;
    const centers = [];
    for (let i=0; i<rgba.length; i+=4) {
      if (rgba[i]>10 || rgba[i+1]<245 || rgba[i+2]<245) continue;
      const x=(i/4)%c.width, y=Math.floor(i/4/c.width);
      if (!centers.some(p => Math.hypot(p.x-x,p.y-y)<12)) centers.push({x,y});
    }
    return centers;
  }, image);
  expect(points.length).toBeGreaterThan(1);
  const previous = await page.locator("#connection-choice").inputValue();
  for (const point of points) {
    await canvas.click({position:point});
    if (await page.locator("#connection-choice").inputValue() !== previous) break;
  }
  await expect(page.locator("#connection-choice")).not.toHaveValue(previous);
  await expect(page.locator("#connection-flanks a")).toHaveCount(2);
});

test("an inconsistent evidence export leaves geometry available and withholds the graph", async ({page}) => {
  await page.route("**/connection-evidence/capillary.json", async route => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({json:{...json, labelsSha256:"stale"}});
  });
  await page.goto("/?dataset=capillary");
  await expect(page.locator("#volume-status")).toContainText("different source geometry or mask");
  await expect(page.locator("#connection-inspector")).toBeHidden();
  await expect(page.locator("#source-image")).toBeVisible();
});

test("a false path spanning seven missing sections opens only the two sampled flanks", async ({page, request}) => {
  const base = "/evidence-controls/field-gap/";
  const manifest = await (await request.get(base + "manifest.json")).json();
  expect(manifest.dice).toBeGreaterThan(.94);
  const requests = [];
  page.on("request", req => requests.push(new URL(req.url()).pathname));
  await page.goto("/?dataset=field-gap");
  const graph = page.locator("#connection-inspector");
  await expect(graph).toBeVisible();
  await expect(page.locator("#connection-summary")).toContainText("Contradicted");
  await expect(graph.locator("#connection-choice")).toHaveValue(manifest.defaultEdge);
  await expect(graph.locator("#connection-sampling")).toContainText("Missing sections (7)");
  await expect(graph.locator("#connection-path")).toContainText("distinct synthetic families");
  await expect(graph.locator("#connection-reference")).toContainText("Synthetic");
  await expect(graph.locator('[data-flag="verified_identity"]')).toHaveCount(0);
  const links = graph.locator("#connection-flanks a");
  for (const [i, index] of [[0,8], [1,16]]) {
    await expect(links.nth(i)).toHaveAttribute("href", new RegExp(`sections/0${String(index).padStart(2,"0")}.png$`));
    expect((await request.get(await links.nth(i).getAttribute("href"))).headers()["content-type"]).toContain("image/png");
  }
  await expect(graph.locator("#connection-flanks canvas")).toHaveCount(2);
  expect(requests.filter(path => /field-gap\/sections\/0(09|1[0-5])\.png$/.test(path))).toEqual([]);
  await graph.locator("#connection-interval").selectOption("0");
  const alternate = graph.locator('.connection-link[aria-pressed="false"]').first();
  const edge = await alternate.getAttribute("data-edge-id");
  await alternate.focus();
  await alternate.press("Enter");
  await expect(graph.locator("#connection-choice")).toHaveValue(edge);
  await expect(graph.locator('.connection-link[aria-pressed="true"]')).toBeFocused();
  await expect(page.locator("#slice-z")).toHaveValue("0");
  await expect(links.nth(0)).toHaveAttribute("href", /sections\/000\.png$/);
});

test("switching controls distinguishes planar fusion from uncertain split depth", async ({page}) => {
  await page.goto("/?dataset=fold");
  const choice = page.locator("#volume-series");
  const graph = page.locator("#connection-inspector");
  for (const [dataset, mechanism] of [["fold","fold"], ["dilation","one-pixel dilation"]]) {
    await choice.selectOption(dataset);
    await expect(graph.locator("#connection-reasons")).toContainText(mechanism + " fused synthetic profiles");
    await expect(graph.locator('[data-flag="contradicted"]')).toBeVisible();
    await expect(graph.locator("#connection-flanks a").first()).toHaveAttribute("href", new RegExp(dataset + "/sections/"));
  }
  await choice.selectOption("branch-depth");
  await expect(graph.locator('[data-flag="split_depth_uncertain"]')).toBeVisible();
  await expect(graph.locator("#connection-sampling")).toContainText("Missing sections (3)");
  await expect(graph.locator("#connection-flanks a").last()).toHaveAttribute("href", /branch-depth\/sections\/012.png$/);
  await graph.locator(".connection-methods summary").click();
  await expect(graph.locator("#connection-registration")).toContainText("Identity");
  await expect(graph.locator("#connection-shifts")).toContainText("(-2, 0)");
  await choice.selectOption("tcia-prostate");
  await expect(graph.locator("#connection-reasons")).toContainText("failed localization");
  await expect(graph.locator("#connection-flanks a").first()).toHaveAttribute("href", /tcia-prostate\//);
  await expect(graph.locator('[data-flag="verified_identity"]')).toHaveCount(0);
});

test("independent identity can be inspected only on a scoped traced edge", async ({page, request}) => {
  const data = await (await request.get("/connection-evidence/bifurcation.json")).json();
  const traced = data.edges.find(e => e.flags.includes("verified_identity"));
  const unresolved = data.edges.find(e => e.flags.includes("unresolved"));
  expect(traced).toBeTruthy();
  expect(unresolved).toBeTruthy();
  await page.goto("/?dataset=bifurcation");
  const graph = page.locator("#connection-inspector");
  for (const edge of [traced, unresolved]) {
    await graph.locator("#connection-interval").selectOption(String(edge.a[2]));
    await graph.locator("#connection-choice").selectOption(String(edge.id));
    await expect(graph.locator("#connection-reference")).toHaveText(edge.reference);
    await expect(graph.locator('[data-flag="verified_identity"]')).toHaveCount(edge === traced ? 1 : 0);
    await expect(graph.locator("#connection-path")).toContainText("unresolved");
    await expect(graph.locator("#connection-flanks figure").first()).toContainText(edge.sourceCoordinates[0].frame);
    await expect(graph.locator("#connection-flanks canvas")).toHaveCount(2);
  }
});
