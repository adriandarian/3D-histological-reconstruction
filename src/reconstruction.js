import { createRayVolume } from "./ray-volume.js";
import { pullAt } from "./coordinates.js";

const element = id => document.getElementById(id);
const controls = element("volume-controls");
const series = element("volume-series");
const source = element("source-image");
const slices = [["xy", 0, 1, 2], ["xz", 0, 2, 1], ["yz", 1, 2, 0]];
const axes = ["x", "y", "z"];
let current, renderer, loadController, sourceImage, sourceUrl;
let cursor = [0, 0, 0];

async function resource(url, method, signal) {
  const response = await fetch(url, {signal});
  if (!response.ok) throw Error("Unavailable asset " + url.pathname);
  return response[method]();
}

async function loadRegistration(url, expected, signal) {
  const bytes = await resource(url, "arrayBuffer", signal);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const hash = Array.from(digest, value => value.toString(16).padStart(2, "0")).join("");
  if (hash !== expected) throw Error("The slide registration differs from the one used to build the volume. Regenerate the pancreas export.");
  return JSON.parse(new TextDecoder().decode(bytes));
}

function renderSettings() {
  const radians = id => +element(id).value * Math.PI / 180;
  const a = radians("azimuth"), e = radians("elevation");
  renderer?.set({
    histology: element("histology").checked,
    tissue: element("tissue").checked,
    anatomy: element("anatomy").checked,
    opacity: +element("opacity").value,
    threshold: +element("threshold").value,
    clipNormal: [Math.cos(a) * Math.cos(e), Math.sin(a) * Math.cos(e), Math.sin(e)],
    clipOffset: element("clip-enable").checked ? +element("clip-offset").value : 1,
  });
}

function drawReslices() {
  const {dimensions, spacing, rgb, labels} = current;
  const strides = [1, dimensions[0], dimensions[0] * dimensions[1]];
  for (const [plane, u, v, fixed] of slices) {
    const canvas = element(plane);
    canvas.width = dimensions[u];
    canvas.height = dimensions[v];
    const scale = Math.min((canvas.parentElement.clientWidth - 12) / (canvas.width * spacing[u]),
      (canvas.parentElement.clientHeight - 12) / (canvas.height * spacing[v]));
    canvas.style.width = canvas.width * spacing[u] * scale + "px";
    canvas.style.height = canvas.height * spacing[v] * scale + "px";
    const ctx = canvas.getContext("2d");
    const image = ctx.createImageData(canvas.width, canvas.height);
    for (let row = 0; row < canvas.height; row++) {
      for (let col = 0; col < canvas.width; col++) {
        const voxel = cursor[fixed] * strides[fixed] + row * strides[v] + col * strides[u];
        const pixel = 4 * (row * canvas.width + col);
        const marked = labels[voxel] === 2 && element("overlay").checked;
        for (let k = 0; k < 3; k++) {
          const value = rgb[3 * voxel + k];
          image.data[pixel + k] = marked ? .55 * value + .45 * [255, 164, 23][k] : value;
        }
        image.data[pixel + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
    ctx.strokeStyle = "#008273";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cursor[u] + .5, 0);
    ctx.lineTo(cursor[u] + .5, canvas.height);
    ctx.moveTo(0, cursor[v] + .5);
    ctx.lineTo(canvas.width, cursor[v] + .5);
    ctx.stroke();
  }
}

function sourceProjection() {
  const [w,h] = current.dimensions;
  const section = current.registration?.sections[cursor[2]];
  const {width,height} = source;
  const transform = section?.transform;
  const inverse = transform
    ? new DOMMatrix([transform[0][0],transform[1][0],transform[0][1],transform[1][1],transform[0][2],transform[1][2]]).inverse()
    : new DOMMatrix().translate(...(section?.shift || [0,0])).inverse();
  return (x,y) => {
    const px = (x+.5)*width/w - .5, py = (y+.5)*height/h - .5;
    const delta = section?.pullGrid ? pullAt({x:px,y:py}, section.pullGrid, width,height) : [0,0];
    const p = inverse.transformPoint({x:px+delta[0], y:py+delta[1]});
    return [p.x+.5,p.y+.5]; // Canvas coordinates have their origin at the pixel edge.
  };
}

function drawSource() {
  if (!sourceImage) return;
  source.width = sourceImage.naturalWidth;
  source.height = sourceImage.naturalHeight;
  const ctx = source.getContext("2d");
  ctx.drawImage(sourceImage,0,0);
  const project = sourceProjection();
  const [w,h] = current.dimensions;
  const [cx,cy,z] = cursor;
  if (element("overlay").checked) {
    const has = (x,y) => x>=0 && x<w && y>=0 && y<h && current.labels[(z*h+y)*w+x]===2;
    ctx.beginPath();
    for (let y=0; y<h; y++) for (let x=0; x<w; x++) {
      if (!has(x,y)) continue;
      for (const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]) {
        if (has(x+dx,y+dy)) continue;
        const mx=x+dx/2, my=y+dy/2;
        ctx.moveTo(...project(mx-dy/2,my+dx/2));
        ctx.lineTo(...project(mx+dy/2,my-dx/2));
      }
    }
    ctx.strokeStyle="#ffb600";
    ctx.lineWidth=Math.max(.65,source.width/320);
    ctx.stroke();
  }
  const [x,y]=project(cx,cy);
  ctx.strokeStyle="#008273";
  ctx.lineWidth=Math.max(.5,source.width/480);
  const r=Math.max(2,source.width/55);
  ctx.beginPath();
  ctx.moveTo(x-r,y); ctx.lineTo(x+r,y);
  ctx.moveTo(x,y-r); ctx.lineTo(x,y+r);
  ctx.stroke();
  element("source-readout").textContent = `Section ${z+1} / ${current.dimensions[2]} · Source X ${Math.round(x-.5)}, Y ${Math.round(y-.5)} px`;
}

function showSource() {
  const z = cursor[2];
  const url = current.registration
    ? new URL(current.registration.sections[z].source, current.realBase).href
    : new URL(current.sections[z], current.base).href;
  if (url === sourceUrl) { drawSource(); return; }
  sourceUrl = url;
  sourceImage = null;
  source.width = 0;
  element("source-readout").textContent = "Loading section…";
  const image = new Image();
  image.onload = () => {
    if (url !== sourceUrl) return;
    sourceImage = image;
    drawSource();
  };
  image.onerror = () => {
    if (url === sourceUrl) element("source-readout").textContent = "Original section unavailable.";
  };
  image.src = url;
}

function select(point) {
  if (!current) return;
  cursor = point.map((n,i) => Math.min(current.dimensions[i]-1,Math.max(0,Math.round(n))));
  axes.forEach((axis,i) => {
    element("slice-"+axis).value=cursor[i];
    element(axis+"-value").value=cursor[i]+(axis==="z"?1:0);
  });
  renderer?.select(cursor[2],cursor[0],cursor[1]);
  drawReslices();
  showSource();
}

async function load() {
  loadController?.abort();
  loadController = new AbortController();
  const {signal} = loadController;
  renderer?.dispose();
  renderer = current = sourceImage = sourceUrl = null;
  source.width=0;
  controls.disabled = true;
  for (const [plane] of slices) element(plane).width=0;
  element("source-readout").textContent="";
  element("ray-host").textContent="";
  const status=element("volume-status");
  status.textContent="Loading reconstruction…";
  const base=new URL("./"+series.value+"/manifest.json",document.baseURI);
  const realBase=new URL("./data/real/manifest.json",document.baseURI);
  const real=series.value==="pancreas";
  try {
    const manifest=await resource(base,"json",signal);
    const asset=(name,method)=>resource(new URL(name,base),method,signal);
    const [rgbBuffer,labelBuffer,mesh,registration,foregroundBuffer] = await Promise.all([
      asset(manifest.rgb,"arrayBuffer"),asset(manifest.labels,"arrayBuffer"),
      manifest.mesh && asset(manifest.mesh,"json"),real ? loadRegistration(realBase,manifest.registrationSha256,signal) : null,
      manifest.foreground && asset(manifest.foreground,"arrayBuffer")
    ]);
    if(signal.aborted) return;
    const rgb=new Uint8Array(rgbBuffer), labels=new Uint8Array(labelBuffer);
    const {dimensions}=manifest;
    const count=dimensions.reduce((a,b)=>a*b,1);
    const foreground=foregroundBuffer ? new Uint8Array(foregroundBuffer) : labels;
    if (foreground.length !== count) throw Error("Inconsistent foreground dimensions");
    if(labels.length!==count || rgb.length!==3*count || (real && registration.sections.length!==dimensions[2]))
      throw Error("Inconsistent reconstruction dimensions");
    // Uncalibrated sections use unitless index coordinates on every axis.
    const spacing=manifest.spacing || [1,1,1];
    current={...manifest,base,realBase,registration,rgb,labels,dimensions,spacing};
    const rgba=new Uint8Array(4*count), anatomy=new Uint8Array(count);
    for(let i=0;i<count;i++){
      rgba[i*4]=rgb[i*3]; rgba[i*4+1]=rgb[i*3+1]; rgba[i*4+2]=rgb[i*3+2];
      rgba[i*4+3]=foreground[i] ? 255 : 0;
      anatomy[i]=Number(labels[i]===2);
    }
    element("anatomy-name").textContent=manifest.anatomyName || "Branching duct";
    axes.forEach((a,i)=>element("slice-"+a).max=dimensions[i]-1);
    status.textContent=real
      ? "Registered pancreas sections · Unknown XY and Z calibration. Depth follows retained section order. The bright cavity is an unverified candidate and registration errors or missing cuts can change its apparent continuity."
      : `Simulated branching duct · Voxel spacing ${spacing.join(" × ")} µm (X, Y, Z). Source sections and registered slices share coordinates.`;
    status.textContent+=" The volume interpolates color between sections. Reslices show sampled voxels. Outlines show algorithmic labels.";
    try {
      renderer=createRayVolume(element("ray-host"),{
        dimensions,spacing,rgba,labels:anatomy,
        mesh:mesh && {vertices:mesh.positions,faces:mesh.indices}
      },(x,y,z)=>{element("overlay").checked=true;select([x,y,z]);});
      controls.disabled=false;
      renderSettings();
    } catch(error) {
      console.warn(error);
      element("ray-host").textContent="3D rendering requires WebGL 2.";
    }
    const z = real ? 9 : Math.floor(dimensions[2]/2);
    const area = dimensions[0] * dimensions[1];
    const firstLabel = labels.subarray(z*area,(z+1)*area).indexOf(2);
    select(firstLabel < 0
      ? [Math.floor(dimensions[0]/2), Math.floor(dimensions[1]/2), z]
      : [firstLabel % dimensions[0], Math.floor(firstLabel/dimensions[0]), z]);
  } catch(error) {
    if(!signal.aborted) status.textContent="Could not load this reconstruction. "+error.message;
  }
}

series.onchange=load;
controls.oninput=renderSettings;
element("ray-reset").onclick=()=>renderer?.reset();
document.querySelector(".clip-controls").oninput=renderSettings;
element("overlay").onchange=()=>select(cursor);
axes.forEach((a,i)=>element("slice-"+a).oninput=event=>{
  const p=[...cursor]; p[i]=+event.target.value; select(p);
});
for (const [plane,u,v] of slices) element(plane).onclick=event=>{
  if(!current) return;
  const r=event.target.getBoundingClientRect(), p=[...cursor];
  p[u]=Math.floor((event.clientX-r.left)*current.dimensions[u]/r.width);
  p[v]=Math.floor((event.clientY-r.top)*current.dimensions[v]/r.height);
  select(p);
};
new ResizeObserver(()=>{if(current) drawReslices();}).observe(element("xy").parentElement);
load();
