import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// Image edges map to the XY plane. Y increases down the slide and Z follows section order.
export function createVolume(host, data, asset, onPoint, onError) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  host.replaceChildren(renderer.domElement);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(37, 1, 0.01, 100);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.minDistance = 0.3;
  controls.maxDistance = 9;
  const h = data.height / data.width;
  const count = data.sections.length;
  const dz =
    data.pixel_size_um && data.section_interval_um
      ? data.section_interval_um / (data.pixel_size_um * data.width)
      : 0.35 / Math.max(1, count - 1);
  const depth = dz * (count - 1);
  const zAt = (index) => dz * index - depth / 2;
  const plane = new THREE.PlaneGeometry(1, h);
  const textures = [];
  const materials = [];
  let alive = true;
  const render = () => {
    if (alive) renderer.render(scene, camera);
  };
  const loader = new THREE.TextureLoader();
  data.sections.forEach((section, i) => {
    const texture = loader.load(
      asset(section.texture),
      render,
      undefined,
      () => {
        if (alive) onError("A volume texture could not be loaded.");
      },
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    textures.push(texture);
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      side: THREE.DoubleSide,
      transparent: true,
      depthWrite: false,
      alphaTest: 0.015,
    });
    materials.push(material);
    const mesh = new THREE.Mesh(plane, material);
    mesh.position.z = zAt(i);
    scene.add(mesh);
  });
  const frameGeometry = new THREE.EdgesGeometry(plane);
  const frameMaterial = new THREE.LineBasicMaterial({
    color: 0xc4edac,
    depthTest: false,
    transparent: true,
  });
  const frame = new THREE.LineSegments(frameGeometry, frameMaterial);
  frame.renderOrder = 10;
  scene.add(frame);
  const markerGeometry = new THREE.SphereGeometry(0.012, 12, 8);
  const markerMaterial = new THREE.MeshBasicMaterial({
    color: 0xf8d45e,
    depthTest: false,
    transparent: true,
  });
  const marker = new THREE.Mesh(markerGeometry, markerMaterial);
  marker.renderOrder = 11;
  scene.add(marker);
  function reset() {
    const scale = Math.max(1, h, depth, 1 / camera.aspect);
    camera.up.set(0, 0, 1);
    camera.position.set(0.9 * scale, -1.5 * scale, 0.94 * scale);
    controls.target.set(0, 0, 0);
    controls.update();
    render();
  }
  function resize() {
    renderer.setSize(host.clientWidth, host.clientHeight, false);
    camera.aspect = host.clientWidth / host.clientHeight;
    camera.updateProjectionMatrix();
    render();
  }
  controls.addEventListener("change", render);
  resize();
  reset();
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  const ray = new THREE.Raycaster();
  let start;
  renderer.domElement.onpointerdown = (event) => {
    start = [event.clientX, event.clientY];
  };
  renderer.domElement.onpointerup = (event) => {
    if (
      !start ||
      Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4
    )
      return;
    const rect = renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(
      new THREE.Vector2(
        (2 * (event.clientX - rect.left)) / rect.width - 1,
        1 - (2 * (event.clientY - rect.top)) / rect.height,
      ),
      camera,
    );
    const hit = ray.ray.intersectPlane(
      new THREE.Plane(new THREE.Vector3(0, 0, 1), -frame.position.z),
      new THREE.Vector3(),
    );
    if (hit && Math.abs(hit.x) <= 0.5 && Math.abs(hit.y) <= h / 2)
      onPoint((hit.x + 0.5) * data.width, (0.5 - hit.y / h) * data.height);
  };
  return {
    reset,
    select(index, x, y) {
      frame.position.z = zAt(index);
      marker.position.set(
        x / data.width - 0.5,
        (0.5 - y / data.height) * h,
        frame.position.z,
      );
      render();
    },
    dispose() {
      alive = false;
      observer.disconnect();
      controls.dispose();
      for (const object of [
        ...textures,
        ...materials,
        plane,
        frameGeometry,
        frameMaterial,
        markerGeometry,
        markerMaterial,
      ])
        object.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
