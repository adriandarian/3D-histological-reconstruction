import "./evidence-inspector.css";

const el = id => document.getElementById("connection-" + id);
const flagLabels = {
  observed_contact: "Observed geometric contact",
  inferred_gap: "Inferred across missing sections",
  inferred_extent: "Interpolated tumor extent",
  registration_sensitive: "Alignment-sensitive",
  segmentation_sensitive: "Boundary-sensitive",
  contradicted: "Contradicted",
  verified_identity: "Independently verified identity",
  unresolved: "Identity unresolved",
  mixed_path: "Whole-path warning",
  split_depth_uncertain: "Split depth uncertain",
};
const severityOrder = ["contradicted", "mixed_path", "inferred_gap", "inferred_extent", "split_depth_uncertain",
  "registration_sensitive", "segmentation_sensitive", "unresolved", "verified_identity", "observed_contact"];
const svgNS = "http://www.w3.org/2000/svg";

function svgElement(tag, attributes) {
  const elem = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) elem.setAttribute(key, value);
  return elem;
}

function componentDiagram(edges, selected, activate) {
  const container = el("diagram");
  const left = [...new Set(edges.map(edge => edge.fromComponent))].sort((a, b) => a-b);
  const right = [...new Set(edges.map(edge => edge.toComponent))].sort((a, b) => a-b);
  const height = Math.max(100, 42 + 31*Math.max(left.length, right.length));
  const svg = svgElement("svg", {viewBox: `0 0 320 ${height}`, height, role:"group",
    "aria-label":"Select a link between earlier and later components"});
  const addText = (x, y, text, anchor) => {
    const label = svgElement("text", {x,y,"text-anchor":anchor});
    label.textContent = text;
    svg.append(label);
  };
  addText(18, 17, "Earlier", "start");
  addText(302, 17, "Later", "end");
  const nodeY = (list, id) => list.length === 1 ? (height+25)/2
    : 39 + (height-56)*list.indexOf(id)/(list.length-1);
  // Render the active connection last so its stroke stays visible at shared nodes.
  for (const edge of [...edges.filter(e => e !== selected), selected]) {
    const y1 = nodeY(left, edge.fromComponent), y2 = nodeY(right, edge.toComponent);
    const path = `M 68 ${y1} C 142 ${y1}, 178 ${y2}, 252 ${y2}`;
    const g = svgElement("g", {class:"connection-link", role:"button", tabindex:"0",
      "data-edge-id":edge.id, "aria-label":`Inspect component ${edge.fromComponent} to ${edge.toComponent}`,
      "aria-pressed":String(edge === selected)});
    g.append(svgElement("path", {d:path, class:"connection-link-hit"}),
      svgElement("path", {d:path, class:"connection-link-line"}));
    g.onclick = () => activate(edge);
    g.onkeydown = event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate(edge);
        // Selection redraws the SVG. Preserve keyboard position on the new edge.
        container.querySelector('[aria-pressed="true"]')?.focus();
      }
    };
    svg.append(g);
  }
  for (const [list, x, textX, anchor] of [[left,68,57,"end"], [right,252,263,"start"]]) {
    for (const id of list) {
      const y = nodeY(list, id);
      svg.append(svgElement("circle", {cx:x,cy:y,r:4.5}));
      addText(textX,y+4,`C${id}`,anchor);
    }
  }
  container.replaceChildren(svg);
}

export function createInspector({select, drawFlank}) {
  let graph, chosen, revision = 0;
  const byInterval = new Map();
  const byId = new Map();
  const sectionId = z => String(graph.sections[z]?.id ?? z);

  function clear() {
    revision++;
    graph = chosen = null;
    byInterval.clear();
    byId.clear();
    el("inspector").hidden = true;
    el("summary").hidden = true;
    el("interval").replaceChildren();
    el("choice").replaceChildren();
    el("diagram").replaceChildren();
    el("flanks").replaceChildren();
  }

  async function flank(container, point, side, coordinates, token) {
    const figure = document.createElement("figure");
    const caption = document.createElement("figcaption");
    const heading = document.createElement("strong");
    heading.textContent = side + " source section";
    caption.append(heading);
    figure.append(caption);
    container.append(figure);
    const output = document.createElement("p");
    if (!point) {
      output.textContent = "No supporting component located on this flank.";
      figure.append(output);
      return;
    }
    heading.textContent += " · " + sectionId(point[2]);
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-label", side + " source section with candidate boundary and coordinates");
    output.textContent = "Loading section…";
    figure.append(output);
    try {
      const {url, readout} = await drawFlank(canvas, point);
      if (token !== revision) return;
      output.textContent = readout;
      if (coordinates?.xy) {
        const native = document.createElement("p");
        native.textContent = `${coordinates.section} · ${coordinates.frame} · X ${coordinates.xy[0]}, Y ${coordinates.xy[1]}`;
        figure.append(native);
      }
      figure.insertBefore(canvas, output);
      const link = document.createElement("a");
      link.textContent = "Open source image";
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      caption.append(link);
    } catch {
      if (token === revision) output.textContent = "Source image unavailable.";
    }
  }

  function choose(edge, move = true) {
    const token = ++revision;
    const z = edge.a[2];
    const edges = byInterval.get(z);
    el("empty").hidden = true;
    el("body").hidden = false;
    if (!chosen || chosen.a[2] !== z) {
      el("choice").replaceChildren(...edges.map(e => new Option(
        `C${e.fromComponent} → C${e.toComponent} · ${e.contactPixels} contact px`, e.id)));
    }
    chosen = edge;
    const primary = severityOrder.filter(flag => edge.flags.includes(flag));
    const summary = el("summary");
    summary.textContent = `Inspect C${edge.fromComponent} → C${edge.toComponent} · ${primary.slice(0, 3).map(f => flagLabels[f]).join(" · ")}`;
    summary.dataset.flag = primary[0] || "";
    summary.hidden = false;
    el("interval").value = String(z);
    el("choice").value = String(edge.id);
    componentDiagram(edges, edge, choose);
    el("flags").replaceChildren(...severityOrder.filter(f => edge.flags.includes(f)).map(flag => {
      const span = document.createElement("span");
      span.dataset.flag = flag;
      span.textContent = flagLabels[flag];
      return span;
    }));
    el("reasons").replaceChildren(...edge.reasons.map(reason => {
      const li = document.createElement("li");
      li.textContent = reason;
      return li;
    }));
    el("path").textContent = edge.pathRisk;
    el("reference").textContent = edge.reference;
    el("contact").textContent = `${edge.contactPixels} shared XY pixel${edge.contactPixels === 1 ? "" : "s"} between C${edge.fromComponent} and C${edge.toComponent} on the reconstruction grid.`;
    const samples = [z, edge.b[2]].map(index =>
      `${sectionId(index)} (${graph.sections[index].measured ? "sampled" : "interpolated"})`).join(" → ");
    el("sampling").textContent = samples + (edge.missingSections?.length
      ? `. Missing sections (${edge.missingSections.length}): ${edge.missingSections.join(", ")}.` : ".");
    el("registration").textContent = graph.registration;
    el("segmentation").textContent = graph.segmentation;
    el("shifts").textContent = edge.alignmentAreas?.length
      ? "Shared pixels after displacing the later plane (ΔX, ΔY in pixels): " +
        graph.alignmentShiftsXY.map(([dx,dy],i) => `(${dx}, ${dy}) → ${edge.alignmentAreas[i]}`).join(", ") + "."
      : "Not evaluated.";
    el("boundary").textContent = Number.isFinite(edge.erodedContactPixels)
      ? `One-pixel erosion of both masks leaves ${edge.erodedContactPixels} shared pixels. One-pixel expansion ${edge.dilationFusion ? "merges previously separate components." : "does not merge a neighboring component in this test."}`
      : "Not evaluated.";
    const flanks = el("flanks");
    flanks.replaceChildren();
    flank(flanks, edge.flanks[0], "Earlier", edge.sourceCoordinates?.[0], token);
    flank(flanks, edge.flanks[1], "Later", edge.sourceCoordinates?.[1], token);
    if (move) select(edge.a, edge);
    return edge;
  }

  function load(data, defaultEdge) {
    clear();
    graph = data;
    el("inspector").hidden = false;
    for (const edge of graph.edges) {
      const z = edge.a[2];
      if (!byInterval.has(z)) byInterval.set(z, []);
      byInterval.get(z).push(edge);
      byId.set(String(edge.id), edge);
    }
    el("interval").replaceChildren(...[...byInterval.keys()].map(z =>
      new Option(`${sectionId(z)} → ${sectionId(z+1)}`, z)));
    el("interval").disabled = !graph.edges.length;
    if (!graph.edges.length) {
      el("empty").textContent = "No reconstructed component connections in this case.";
      el("empty").hidden = false;
      el("body").hidden = true;
      return;
    }
    const initial = byId.get(String(defaultEdge));
    choose(initial || graph.edges[0], Boolean(initial));
    if (!initial) el("summary").hidden = true;
  }
  function pick(x, y, z, componentId) {
    if (!graph) return null;
    let nearest, distance = Infinity;
    for (const edge of [...(byInterval.get(z) || []), ...(byInterval.get(z-1) || [])]) {
      const earlier = z === edge.a[2];
      const p = earlier ? edge.a : edge.b;
      if (componentId != null && componentId !== (earlier ? edge.fromComponent : edge.toComponent)) continue;
      const d = Math.hypot(x-p[0], y-p[1]);
      if (d < distance && (componentId != null || d < 1)) {
        nearest = edge;
        distance = d;
      }
    }
    if (nearest) {
      choose(nearest, false);
      return nearest;
    }
    revision++;
    chosen = null;
    el("summary").hidden = true;
    el("body").hidden = true;
    el("empty").textContent = "No incident connection for the selected region. Choose a section interval to inspect its graph.";
    el("empty").hidden = false;
    el("interval").selectedIndex = -1;
    return null;
  }
  el("interval").onchange = event => choose(byInterval.get(Number(event.target.value))[0]);
  el("choice").onchange = event => choose(byId.get(event.target.value));
  return {clear, load, pick, pickEdge: id => {
    const edge = byId.get(String(id));
    return edge ? choose(edge) : null;
  }};
}
