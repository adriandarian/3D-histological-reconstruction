// OrbitControls owns camera gestures. A pick is a separate, stationary primary tap.
export function bindVolumeInput(host, canvas, controls, reset, pick) {
  const listeners = new AbortController();
  const options = {signal: listeners.signal};
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "application");
  const article = host.closest("article");
  const seriesName = article?.querySelector("h2")?.textContent;
  canvas.setAttribute("aria-label", host.getAttribute("aria-label") || `${seriesName} 3D stack`);
  const hint = host.closest("section")?.querySelector("[data-controls-help]");
  if (hint) {
    hint.id ||= (host.id || article.id) + "-camera-help";
    canvas.setAttribute("aria-describedby", hint.id);
  }
  controls.cursorStyle = "grab";

  const orbitStep = Math.PI / 24;
  const panStep = 24;
  const zoomFactor = 0.9;
  canvas.addEventListener("keydown", event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
    switch (event.key) {
      case "ArrowLeft":
      case "ArrowRight": {
        const direction = event.key === "ArrowLeft" ? 1 : -1;
        if (event.shiftKey) controls.pan(-direction * panStep, 0);
        else controls.rotateLeft(direction * orbitStep);
        break;
      }
      case "ArrowUp":
      case "ArrowDown": {
        const direction = event.key === "ArrowUp" ? 1 : -1;
        if (event.shiftKey) controls.pan(0, -direction * panStep);
        else controls.rotateUp(direction * orbitStep);
        break;
      }
      case "+":
      case "=": controls.dollyIn(zoomFactor); break;
      case "-": controls.dollyOut(zoomFactor); break;
      case "Home": reset(); break;
      case "Enter": pick({x: 0, y: 0}); break;
      default: return;
    }
    event.preventDefault();
  }, options);

  let tap;
  const modified = event => event.shiftKey || event.ctrlKey || event.altKey || event.metaKey;
  canvas.addEventListener("pointerdown", event => {
    canvas.focus({preventScroll: true});
    tap = event.isPrimary && event.button === 0 && !modified(event)
      ? {id: event.pointerId, x: event.clientX, y: event.clientY}
      : null;
  }, options);
  function checkMovement(event) {
    if (tap && (modified(event) || Math.hypot(event.clientX - tap.x, event.clientY - tap.y) > 4)) tap = null;
  }
  canvas.addEventListener("pointermove", checkMovement, options);
  canvas.addEventListener("pointerup", event => {
    checkMovement(event);
    if (tap && tap.id === event.pointerId && event.button === 0) {
      const rect = canvas.getBoundingClientRect();
      pick({
        x: 2 * (event.clientX - rect.left) / rect.width - 1,
        y: 1 - 2 * (event.clientY - rect.top) / rect.height,
      });
    }
    tap = null;
  }, options);
  for (const type of ["pointercancel", "lostpointercapture"]) {
    canvas.addEventListener(type, () => { tap = null; }, options);
  }
  return () => listeners.abort();
}
