import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const vertexShader = `
  out vec3 world;
  void main() {
    world = (modelMatrix * vec4(position, 1.)).xyz;
    gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.);
  }`;

const fragmentShader = `
  precision highp sampler3D;
  uniform sampler3D histology;
  uniform sampler2D meshColor, meshDepth;
  uniform mat4 inverseProjection, cameraWorld;
  uniform vec2 screen;
  uniform vec3 size, dimensions, normal;
  uniform float offset, threshold, opacity;
  uniform bool showHistology, showTissue;
  in vec3 world;
  out vec4 fragColor;
  void main() {
    vec3 ray = normalize(world - cameraPosition);
    vec3 invRay = sign(ray + vec3(1.e-20)) / max(abs(ray), vec3(1.e-10));
    vec3 bound0 = (-.5 * size - cameraPosition) * invRay;
    vec3 bound1 = ( .5 * size - cameraPosition) * invRay;
    vec3 entry = min(bound0, bound1), leave = max(bound0, bound1);
    float nearT = max(0., max(entry.x, max(entry.y, entry.z)));
    float farT = min(leave.x, min(leave.y, leave.z));
    vec2 uv = gl_FragCoord.xy / screen;
    vec4 surface = texture(meshColor, uv);
    if (surface.a > .5) {
      float depth = texture(meshDepth, uv).r;
      vec4 vp = inverseProjection * vec4(uv * 2. - 1., depth * 2. - 1., 1.);
      vec3 wp = (cameraWorld * vec4(vp.xyz / vp.w, 1.)).xyz;
      farT = min(farT, dot(wp - cameraPosition, ray));
    }
    vec4 accumulated = vec4(0.);
    if (showHistology || showTissue) {
      float span = max(0., farT - nearT);
      int count = int(clamp(ceil(span * length(ray * dimensions / size) * 1.5), 1., 1536.));
      float stepSize = span / float(count);
      for (int i = 0; i < 1536; ++i) {
        if (i >= count || accumulated.a > .99) break;
        float t = nearT + (float(i) + .5) * stepSize;
        vec3 centered = (cameraPosition + ray * t) / size * vec3(1., -1., 1.);
        if (dot(centered, normal) > offset) continue;
        vec4 voxel = texture(histology, centered + .5);
        float density = 1. - dot(voxel.rgb, vec3(.2126, .7152, .0722));
        float stain = showHistology ? max(0., density - threshold) : 0.;
        float tissue = showTissue ? voxel.a * .18 : 0.;
        float total = stain + tissue;
        vec3 color = (voxel.rgb * stain + vec3(.22,.70,.70) * tissue) / max(total,.00001);
        float a = 1. - exp(-total * opacity * 16. * stepSize);
        accumulated += (1. - accumulated.a) * a * vec4(color, 1.);
      }
    }
    vec4 result = accumulated + (1. - accumulated.a) * surface;
    if (result.a < .001) discard;
    fragColor = vec4(result.rgb / result.a, result.a);
  }`;

function flat(array) {
  return Array.isArray(array[0]) ? array.flat() : array;
}

export function createRayVolume(host, {dimensions, spacing, rgba, labels, mesh, uncertain, frameAnatomy}, onPick, onEdgePick) {
  const [nx, ny, nz] = dimensions;
  if (rgba.length !== nx * ny * nz * 4 || labels.length !== nx * ny * nz)
    throw new Error("Volume buffer size differs from its dimensions.");
  const extent = dimensions.map((n, i) => n * spacing[i]);
  if (!extent.every(value => value > 0 && Number.isFinite(value)))
    throw new Error("Volume spacing must be finite and positive.");
  const size = new THREE.Vector3(...extent).divideScalar(Math.max(...extent));
  const renderer = new THREE.WebGLRenderer({alpha:true, antialias:true});
  renderer.localClippingEnabled = true;
  renderer.setClearColor(0, 0);
  const canvas = renderer.domElement;
  host.replaceChildren(canvas);
  const camera = new THREE.PerspectiveCamera(35, 1, .01, 30);
  const controls = new OrbitControls(camera, canvas);
  controls.minDistance = .15;
  controls.maxDistance = 8;
  const scene = new THREE.Scene(), surfaces = new THREE.Scene();
  const texture = new THREE.Data3DTexture(rgba, nx, ny, nz);
  texture.format = THREE.RGBAFormat;
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  const target = new THREE.WebGLRenderTarget(1, 1);
  target.depthTexture = new THREE.DepthTexture(1, 1);
  const uniforms = Object.fromEntries(Object.entries({
    histology: texture, meshColor: target.texture, meshDepth: target.depthTexture,
    cameraWorld: camera.matrixWorld, inverseProjection: camera.projectionMatrixInverse,
    screen: new THREE.Vector2(), size, dimensions: new THREE.Vector3(...dimensions),
    normal: new THREE.Vector3(0,0,1), offset:1, threshold:.12, opacity:.3,
    showHistology:true, showTissue:false
  }).map(([key, value]) => [key, {value}]));
  const material = new THREE.ShaderMaterial({uniforms, vertexShader, fragmentShader,
    glslVersion:THREE.GLSL3, side:THREE.BackSide, transparent:true, depthWrite:false});
  const cube = new THREE.Mesh(new THREE.BoxGeometry(size.x,size.y,size.z), material);
  scene.add(cube);
  const clip = new THREE.Plane();
  function worldAt(x,y,z) {
    return new THREE.Vector3(((x+.5)/nx-.5)*size.x, (.5-(y+.5)/ny)*size.y,
      ((z+.5)/nz-.5)*size.z);
  }
  let anatomy;
  if (mesh && mesh.vertices.length) {
    const vertices = flat(mesh.vertices), positions = new Float32Array(vertices.length);
    for (let i=0; i<vertices.length; i+=3)
      worldAt(vertices[i],vertices[i+1],vertices[i+2]).toArray(positions,i);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions,3));
    const indices = flat(mesh.faces);
    const options = {side:THREE.DoubleSide, clippingPlanes:[clip]};
    const normalMaterial = new THREE.MeshNormalMaterial(options);
    let surfaceMaterial = normalMaterial;
    if (uncertain) {
      // Sample just inside each outward-facing voxel triangle in the original XYZ frame.
      const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
      const center = new THREE.Vector3(), certainFaces = [], uncertainFaces = [];
      for (let i=0; i<indices.length; i+=3) {
        a.fromArray(vertices,3*indices[i]);
        b.fromArray(vertices,3*indices[i+1]);
        c.fromArray(vertices,3*indices[i+2]);
        center.copy(a).add(b).add(c).multiplyScalar(1/3);
        const normal = b.sub(a).cross(c.sub(a)).normalize();
        center.addScaledVector(normal,-.25).round();
        const voxel = (center.z*ny+center.y)*nx+center.x;
        const faces = uncertain[voxel] ? uncertainFaces : certainFaces;
        faces.push(indices[i], indices[i+1], indices[i+2]);
      }
      geometry.setIndex(certainFaces.concat(uncertainFaces));
      geometry.addGroup(0,certainFaces.length,0);
      geometry.addGroup(certainFaces.length,uncertainFaces.length,1);
      surfaceMaterial = [normalMaterial, new THREE.MeshBasicMaterial({...options,color:0xff2592})];
    } else {
      geometry.setIndex(Array.from(indices));
    }
    geometry.computeVertexNormals();
    anatomy = new THREE.Mesh(geometry, surfaceMaterial);
    surfaces.add(anatomy);
  }
  const marker = new THREE.Mesh(new THREE.SphereGeometry(.009,12,8),
    new THREE.MeshBasicMaterial({color:0xffcc39, depthTest:false, transparent:true}));
  marker.visible = false;
  marker.renderOrder = 1;
  scene.add(marker);
  const edgeLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({color:0xff9d31, depthTest:false, transparent:true}));
  edgeLine.visible = false;
  edgeLine.renderOrder = 2;
  scene.add(edgeLine);
  const contactGeometry = new THREE.SphereGeometry(.009, 12, 8);
  const contactMaterial = new THREE.MeshBasicMaterial({color:0x00ffff, depthTest:false, transparent:true});
  const contacts = new THREE.Group();
  scene.add(contacts);

  function render() {
    renderer.setRenderTarget(target);
    renderer.render(surfaces, camera);
    renderer.setRenderTarget(null);
    renderer.render(scene, camera);
  }
  function resize() {
    const w = Math.max(1,host.clientWidth), h = Math.max(1,host.clientHeight);
    renderer.setSize(w,h,false);
    target.setSize(w,h);
    uniforms.screen.value.set(w,h);
    camera.aspect = w/h;
    camera.updateProjectionMatrix();
    render();
  }
  function reset() {
    camera.up.set(0,0,1);
    camera.position.set(.65,-1.9,.75).multiplyScalar(Math.max(1,1/camera.aspect));
    controls.target.set(0,0,0);
    if (frameAnatomy && anatomy) {
      anatomy.geometry.computeBoundingSphere();
      const bounds = anatomy.geometry.boundingSphere;
      controls.target.copy(bounds.center);
      const distance = 1.15 * bounds.radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2));
      camera.position.set(.65, -1.4, 1.2).setLength(distance * Math.max(1,1/camera.aspect)).add(bounds.center);
    }
    controls.update();
    render();
  }
  const ray = new THREE.Raycaster();
  let start;
  canvas.onpointerdown = e => { start = [e.clientX,e.clientY]; };
  canvas.onpointerup = e => {
    if (!start || Math.hypot(e.clientX-start[0],e.clientY-start[1])>4) return;
    const rect = canvas.getBoundingClientRect();
    ray.setFromCamera({x:2*(e.clientX-rect.left)/rect.width-1,y:1-2*(e.clientY-rect.top)/rect.height},camera);
    const contact = ray.intersectObjects(contacts.children)[0];
    if (contact) {
      onEdgePick(contact.object.userData.edge);
      return;
    }
    if (!anatomy?.visible) return;
    const hit = ray.intersectObject(anatomy).find(({point}) => clip.distanceToPoint(point)>=0);
    if (!hit) return;
    const voxel = [(.5+hit.point.x/size.x)*nx-.5,(.5-hit.point.y/size.y)*ny-.5,(.5+hit.point.z/size.z)*nz-.5];
    // An isosurface lies between voxel centers. Select its nearest labeled source sample.
    const [cx,cy,cz] = voxel.map(Math.round);
    let distance = Infinity, selected;
    for (let z=Math.max(0,cz-1);z<=Math.min(nz-1,cz+1);z++)
      for (let y=Math.max(0,cy-1);y<=Math.min(ny-1,cy+1);y++)
        for (let x=Math.max(0,cx-1);x<=Math.min(nx-1,cx+1);x++) {
          if (!labels[(z*ny+y)*nx+x]) continue;
          const d = Math.hypot((x-voxel[0])*spacing[0],(y-voxel[1])*spacing[1],(z-voxel[2])*spacing[2]);
          if (d < distance) { distance = d; selected = [x,y,z]; }
        }
    if (selected) onPick(...selected);
  };
  function set(options) {
    for (const [key,name] of Object.entries({histology:"showHistology",tissue:"showTissue",
      threshold:"threshold",opacity:"opacity",clipOffset:"offset"})) {
      if (options[key] !== undefined) uniforms[name].value = options[key];
    }
    if (anatomy && options.anatomy !== undefined) anatomy.visible = options.anatomy;
    if (options.clipNormal) uniforms.normal.value.fromArray(options.clipNormal).normalize();
    clip.normal.copy(uniforms.normal.value).multiply(new THREE.Vector3(-1,1,-1)).divide(size);
    clip.constant = uniforms.offset.value;
    clip.normalize();
    render();
  }
  controls.addEventListener("change", render);
  resize();
  reset();
  set({});
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  return {set,reset, showContacts(edges) {
    contacts.clear();
    for (const edge of edges) {
      const dot = new THREE.Mesh(contactGeometry, contactMaterial);
      dot.position.copy(worldAt(...edge.a)).lerp(worldAt(...edge.b), .5);
      dot.renderOrder = 3;
      dot.userData.edge = edge.id;
      contacts.add(dot);
    }
    render();
  },select(z,x,y,edge) {
    marker.position.copy(worldAt(x,y,z));
    marker.visible = true;
    edgeLine.visible = Boolean(edge);
    if (edge) {
      edgeLine.geometry.setFromPoints([worldAt(...edge.a),worldAt(...edge.b)]);
      edgeLine.geometry.computeBoundingSphere();
    }
    render();
  },dispose() {
    observer.disconnect();
    controls.dispose();
    contactGeometry.dispose();
    contactMaterial.dispose();
    for (const obj of [cube,marker,edgeLine,anatomy].filter(Boolean)) {
      for (const material of [].concat(obj.material)) material.dispose();
      obj.geometry.dispose();
    }
    target.dispose();
    texture.dispose();
    renderer.dispose();
    canvas.remove();
  }};
}
