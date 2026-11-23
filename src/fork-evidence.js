const names = {parent:"Parent", junction:"Junction", daughterA:"Daughter A", daughterB:"Daughter B"};
const colors = {parent:"#fff", junction:"#fff", daughterA:"#00e6e6", daughterB:"#fc83f2"};

export function drawTrace(ctx, project, points) {
  for (const {arm, x, y} of points) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const [cx, cy] = project(x,y);
    const radius = Math.max(2, ctx.canvas.width / 80);
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#172521";
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.strokeStyle = colors[arm];
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = colors[arm];
    ctx.font = "bold 10px sans-serif";
    const tag = {parent:"P", junction:"J", daughterA:"A", daughterB:"B"}[arm];
    ctx.strokeStyle = "#172521";
    ctx.strokeText(tag, cx + radius + 1, cy);
    ctx.fillText(tag, cx + radius + 1, cy);
  }
}

export function intervalText(plane) {
  const hits = plane.points.map(p => names[p.arm] + (p.hit === true ? " inside" : p.hit === false ? " outside" : " unscored"));
  const separation = plane.distinctDaughters === true ? "Daughters occupy distinct predicted regions."
    : plane.distinctDaughters === false ? "Separate daughter regions are unresolved." : "";
  return [hits.length ? hits.join(" · ") + "." : "Reference identity uncertain on this section. No points scored.", separation].filter(Boolean).join(" ");
}

export function nativeLocation(volume, cursor) {
  const fafb = Number.isInteger(volume.trace.skeletonId);
  const nativeNm = fafb ? [4,4,40] : [4,4,33];
  const [x,y,z] = cursor;
  const [x0,y0] = volume.sourceOrigin;
  const state = {
    dimensions: Object.fromEntries(["x","y","z"].map((axis,i) => [axis,[nativeNm[i]*1e-9,"m"]])),
    position: [x0 + (x+.5)*volume.spacing[0]*1000/nativeNm[0],
               y0 + (y+.5)*volume.spacing[1]*1000/nativeNm[1], volume.trace.planes[z].z+.5],
    layers:[{type:"image",name:"EM",source: fafb
      ? "precomputed://gs://neuroglancer-fafb-data/fafb_v14/fafb_v14_orig"
      : "precomputed://gs://h01-release/data/20210601/4nm_raw"}],
    crossSectionScale: 4, layout:"xy",
  };
  return "https://neuroglancer-demo.appspot.com/#!" + encodeURIComponent(JSON.stringify(state));
}

// Jump to the displayed section when its daughter is resolved, otherwise to
// the closest section with independently located and separately resolved arms.
export function locateArm(trace, validation, arm, from) {
  let best = null;
  for (const [z, plane] of trace.planes.entries()) {
    const point = plane.points.find(p => p.arm === arm && Number.isFinite(p.x) && Number.isFinite(p.y));
    if (!point) continue;
    const resolved = arm === "parent" || validation.planes[z].distinctDaughters === true;
    const rank = Math.abs(z-from) + (resolved ? 0 : trace.planes.length);
    if (!best || rank < best.rank) best = {rank, xyz:[point.x, point.y, z]};
  }
  return best?.xyz;
}
