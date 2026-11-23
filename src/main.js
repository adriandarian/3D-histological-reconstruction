import OpenSeadragon from "openseadragon";
import { createVolume } from "./volume.js";
import "./style.css";

const ui = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [
    element.id,
    element,
  ]),
);
const viewer = OpenSeadragon({
  element: ui.osd,
  showNavigationControl: false,
  preserveViewport: true,
  animationTime: 0.25,
  maxZoomPixelRatio: 8,
  visibilityRatio: 0.35,
  gestureSettingsMouse: { clickToZoom: false },
});
let data,
  asset,
  volume,
  x,
  y,
  index,
  loadToken = 0;
function sectionTransform() {
  if (ui.frame.value !== "source") return new DOMMatrix();
  const { transform, shift } = data.sections[index];
  if (!transform) return new DOMMatrix().translate(...shift);
  const [[a, c, e], [b, d, f]] = transform;
  return new DOMMatrix([a, b, c, d, e, f]);
}
// The pull grid maps a displayed point to its position in the rigid frame.
function pullAt(point, grid) {
  const rows = grid.length, cols = grid[0].length;
  const u = Math.max(0, Math.min(1, point.x / (data.width - 1))) * (cols - 1);
  const v = Math.max(0, Math.min(1, point.y / (data.height - 1))) * (rows - 1);
  const i = Math.min(cols - 2, Math.floor(u)), j = Math.min(rows - 2, Math.floor(v));
  const fx = u - i, fy = v - j;
  return [0, 1].map(k => (1-fy)*((1-fx)*grid[j][i][k] + fx*grid[j][i+1][k])
                         + fy*((1-fx)*grid[j+1][i][k] + fx*grid[j+1][i+1][k]));
}
function registeredPoint(point) {
  const rigid = sectionTransform().transformPoint(point);
  const grid = data.sections[index].pullGrid;
  if (!grid || ui.frame.value !== "source") return rigid;
  let aligned = rigid;
  for (let step = 0; step < 24; step++) {
    const [dx,dy] = pullAt(aligned, grid);
    const next = {x: rigid.x - dx, y: rigid.y - dy};
    if (Math.hypot(next.x-aligned.x, next.y-aligned.y) < 0.001) return next;
    aligned = next;
  }
  return aligned;
}
function placeCross() {
  const image = viewer.world.getItemAt(0);
  if (!image || !data) {
    ui.cross.style.display = "none";
    return;
  }
  const grid = data.sections[index].pullGrid;
  const [dx, dy] = grid && ui.frame.value === "source" ? pullAt({x,y}, grid) : [0,0];
  const source = sectionTransform().inverse().transformPoint({ x: x+dx, y: y+dy });
  const point = viewer.viewport.pixelFromPoint(
    image.imageToViewportCoordinates(source.x, source.y),
    true,
  );
  Object.assign(ui.cross.style, {
    display: "block",
    left: point.x + "px",
    top: point.y + "px",
  });
}
function selectPoint(px, py) {
  x = Math.max(0, Math.min(data.width - 1, Math.round(px)));
  y = Math.max(0, Math.min(data.height - 1, Math.round(py)));
  ui.coords.textContent = "Registered X " + x + " px  ·  Y " + y + " px";
  volume?.select(index, x, y);
  placeCross();
}
viewer.addHandler("canvas-click", (event) => {
  const image = viewer.world.getItemAt(0);
  if (!event.quick || !image || !data) return;
  const point = image.viewportToImageCoordinates(
    viewer.viewport.pointFromPixel(event.position, true),
  );
  const registered = registeredPoint(point);
  if (
    point.x >= 0 &&
    point.y >= 0 &&
    point.x < data.width &&
    point.y < data.height
  )
    selectPoint(registered.x, registered.y);
});
for (const event of ["open", "animation", "resize", "viewport-change"])
  viewer.addHandler(event, placeCross);
viewer.addHandler("open-failed", () => {
  ui.status.textContent =
    "The section image could not be opened. Check the exported files.";
});
function showSection(value) {
  if (!data) return;
  index = Math.max(0, Math.min(value, data.sections.length - 1));
  const section = data.sections[index];
  ui.section.value = index;
  ui.prev.disabled = index === 0;
  ui.next.disabled = index === data.sections.length - 1;
  ui.count.textContent =
    index +
    1 +
    " / " +
    data.sections.length +
    (Number.isFinite(section.z_um) ? " · Z " + section.z_um + " µm" : "");
  ui.quality.textContent = Number.isFinite(section.score)
    ? "Rigid NCC   " +
      section.beforeScore.toFixed(3) +
      " → " +
      section.score.toFixed(3) +
      " · " +
      section.status
    : "Registration reference";
  viewer.open({
    type: "image",
    url: asset(section[ui.frame.value]),
    buildPyramid: false,
  });
  selectPoint(x, y);
}
async function load() {
  const token = ++loadToken;
  data = null;
  volume?.dispose();
  volume = null;
  viewer.close();
  ui.cross.style.display = "none";
  for (const key of [
    "count",
    "coords",
    "quality",
    "provenance",
    "volume",
    "scale",
  ])
    ui[key].textContent = "";
  for (const key of [
    "frame",
    "prev",
    "next",
    "section",
    "in",
    "out",
    "fit",
    "reset",
  ])
    ui[key].disabled = true;
  ui.status.textContent = "Loading series…";
  const path = new URL(
    "./data/" + ui.dataset.value + "/manifest.json",
    document.baseURI,
  );
  try {
    const response = await fetch(path);
    if (!response.ok) throw Error("Manifest missing");
    const series = await response.json();
    if (!series.sections?.length) throw Error("Empty series");
    if (token !== loadToken) return;
    data = series;
    asset = (file) => new URL(file, path).href;
    ui.status.textContent =
      data.name + (data.sections[0].pullGrid ? " / Local refinement" : "") +
      " · " +
      data.sections.length +
      " sections · " +
      data.width +
      " × " +
      data.height +
      " px";
    ui.provenance.textContent = data.attribution || data.kind;
    ui.scale.textContent =
      data.section_interval_um && data.pixel_size_um
        ? data.section_interval_um + " µm section interval"
        : "Illustrative depth · section index";
    try {
      volume = createVolume(ui.volume, data, asset, selectPoint, (message) => {
        ui.status.textContent = message;
      });
    } catch (error) {
      ui.volume.textContent = "3D view requires WebGL 2.";
      console.warn(error);
    }
    for (const key of ["frame", "section", "in", "out", "fit"])
      ui[key].disabled = false;
    ui.reset.disabled = !volume;
    ui.section.max = data.sections.length - 1;
    x = Math.floor(data.width / 2);
    y = Math.floor(data.height / 2);
    showSection(Math.floor(data.sections.length / 2));
    viewer.addOnceHandler("open", () => viewer.viewport.goHome(true));
  } catch {
    if (token === loadToken)
      ui.status.textContent =
        "Series unavailable. Generate public/data/" +
        ui.dataset.value +
        "/manifest.json with the Python pipeline, or choose another dataset.";
  }
}
if (new URLSearchParams(location.search).get("dataset") === "real")
  ui.dataset.value = "real";
ui.dataset.onchange = load;
ui.section.oninput = () => showSection(Number(ui.section.value));
ui.frame.onchange = () => showSection(index);
ui.prev.onclick = () => showSection(index - 1);
ui.next.onclick = () => showSection(index + 1);
ui.in.onclick = () => viewer.viewport.zoomBy(1.5);
ui.out.onclick = () => viewer.viewport.zoomBy(1 / 1.5);
ui.fit.onclick = () => viewer.viewport.goHome();
ui.reset.onclick = () => volume?.reset();
load();
