import { pullAt } from "./coordinates.js";
import OpenSeadragon from "openseadragon";
import { createVolume } from "./volume.js";
import { bindReadingSteps } from "./reading-steps.js";
import "./style.css";
import "./workspace.css";
import "./article.css";
import "./inline-figures.css";
import "./inline-stacks.css";
import "./serial-illustration.js";

const workspaceNav = document.querySelector(".workspace-nav");
const destinations = Array.from(workspaceNav.querySelectorAll("a"), link => ({
  link,
  section: document.querySelector(link.hash),
}));

function markCurrentSection() {
  const offset = workspaceNav.offsetHeight + 24;
  const visible = destinations.filter(({section}) => !section.hidden);
  const atEnd = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
  const active = atEnd ? visible.at(-1) :
    visible.findLast(({section}) => section.getBoundingClientRect().top <= offset) ?? visible[0];
  for (const destination of destinations) {
    if (destination === active) destination.link.setAttribute("aria-current", "location");
    else destination.link.removeAttribute("aria-current");
  }
}
window.addEventListener("scroll", markCurrentSection, {passive: true});
new ResizeObserver(markCurrentSection).observe(document.body);
markCurrentSection();

function addCameraGuide(panel) {
  const guide = document.querySelector("#camera-guide").content.cloneNode(true);
  guide.querySelector("[data-controls-help]").id = panel.id + "-camera-help";
  panel.querySelector(".camera-caption").append(guide);
}

function mountExplorer(root) {
  const dataset = root.id;
  const bridge = root.querySelector(".stack-bridge");
  const sequence = root.querySelector(".stack-sequence");
  sequence.prepend(document.querySelector("#explorer").content.cloneNode(true));
  bridge.after(document.querySelector("#stack-view").content.cloneNode(true));
  addCameraGuide(root);
  const ui = Object.fromEntries(
    [...root.querySelectorAll("[data-ui]")].map((element) => [
      element.dataset.ui,
      element,
    ]),
  );
  ui.section.id = dataset + "-section";
  ui.count.setAttribute("for", ui.section.id);
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
    index;
  function sectionTransform(frame = ui.frame.value) {
    if (frame !== "source") return new DOMMatrix();
    const { transform, shift } = data.sections[index];
    if (!transform) return new DOMMatrix().translate(...shift);
    const [[a, c, e], [b, d, f]] = transform;
    return new DOMMatrix([a, b, c, d, e, f]);
  }
  // The pull grid maps a displayed point to its position in the rigid frame.
  function registeredPoint(point, frame = ui.frame.value) {
    const rigid = sectionTransform(frame).transformPoint(point);
    const grid = data.sections[index].pullGrid;
    if (!grid || frame !== "source") return rigid;
    let aligned = rigid;
    for (let step = 0; step < 24; step++) {
      const [dx,dy] = pullAt(aligned, grid, data.width, data.height);
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
    const [dx, dy] = grid && ui.frame.value === "source" ? pullAt({x,y}, grid, data.width, data.height) : [0,0];
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
      "./data/" + dataset + "/manifest.json",
      document.baseURI,
    );
    try {
      const response = await fetch(path);
      if (!response.ok) throw Error("Manifest missing");
      const series = await response.json();
      if (!series.sections?.length) throw Error("Empty series");
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
      ui.replay.hidden = !volume;
      ui.section.max = data.sections.length - 1;
      x = Math.floor(data.width / 2);
      y = Math.floor(data.height / 2);
      showSection(Math.floor(data.sections.length / 2));
      viewer.addOnceHandler("open", () => viewer.viewport.goHome(true));
      const steps = sequence.querySelectorAll("[data-reading-step]");
      const toggle = sequence.querySelector("[data-reading-toggle]");
      toggle.disabled = false;
      const reading = bindReadingSteps(sequence, stepIndex => {
        const step = steps[stepIndex].dataset;
        ui.frame.value = step.frame;
        showSection(Number(step.section) - 1);
        if (step.landmark) {
          const [px, py] = step.landmark.split(",").map(Number);
          const point = registeredPoint({x: px, y: py}, "source");
          selectPoint(point.x, point.y);
        } else {
          selectPoint(Math.floor(data.width / 2), Math.floor(data.height / 2));
        }
        viewer.viewport.goHome(true);
      });
      const pauseOnControl = event => {
        const control = event.target.closest('button, input, select, summary, [data-ui="osd"], [data-ui="volume"] canvas');
        if (control && control !== toggle && control.closest(".stack-plate")) reading.pause();
      };
      for (const type of ["pointerdown", "keydown", "input", "change", "click"]) {
        root.addEventListener(type, pauseOnControl, true);
      }
    } catch {
      ui.status.textContent = `Series unavailable. Generate public/data/${dataset}/manifest.json with the Python pipeline and reload.`;
      sequence.dataset.readingDisabled = "";
      for (const panel of root.querySelectorAll("section, footer")) panel.hidden = true;
    }
  }
  ui.section.oninput = () => showSection(Number(ui.section.value));
  ui.frame.onchange = () => showSection(index);
  ui.prev.onclick = () => showSection(index - 1);
  ui.next.onclick = () => showSection(index + 1);
  ui.in.onclick = () => viewer.viewport.zoomBy(1.5);
  ui.out.onclick = () => viewer.viewport.zoomBy(1 / 1.5);
  ui.fit.onclick = () => viewer.viewport.goHome();
  ui.reset.onclick = () => volume?.reset();
  ui.replay.onclick = () => volume?.replay();
  load();
}

addCameraGuide(document.querySelector("#reconstruction"));
for (const panel of document.querySelectorAll(".datasets > article")) {
  mountExplorer(panel);
}

// Keep existing links to a dataset useful on narrow screens.
const linkedDataset = new URLSearchParams(location.search).get("dataset");
if (linkedDataset === "real" || linkedDataset === "synthetic") {
  document.getElementById(linkedDataset).scrollIntoView({block: "start"});
}
import "./reconstruction.js";
