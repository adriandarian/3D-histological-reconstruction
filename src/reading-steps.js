// A figure follows the paragraph nearest the reading line until the reader takes control.
export function bindReadingSteps(container, apply, moveCamera) {
  const steps = Array.from(container.querySelectorAll("[data-reading-step]"));
  const toggle = container.querySelector("[data-reading-toggle]");
  const stage = container.querySelector("[data-reading-stage]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let following = !reducedMotion.matches;
  let current = -1;
  let lastPosition = NaN;
  let frame = 0;

  function measure() {
    frame = 0;
    if (!following || container.hasAttribute("data-reading-disabled")) return;
    const bounds = container.getBoundingClientRect();
    if (!bounds.height || bounds.top > innerHeight * .7 || bounds.bottom < innerHeight * .28) return;

    let line = innerHeight * .55;
    if (stage) {
      const figure = stage.getBoundingClientRect();
      const paragraph = steps[0].getBoundingClientRect();
      if (paragraph.left < figure.right && paragraph.right > figure.left) {
        line = Math.max(line, Math.min(innerHeight * .86, figure.bottom + innerHeight * .12));
      }
    }
    let position = steps.length - 1;
    let previousCenter;
    for (const [index, step] of steps.entries()) {
      const rect = step.getBoundingClientRect();
      const center = rect.top + rect.height / 2;
      if (line <= center) {
        position = index === 0 ? 0 : index - 1 + (line - previousCenter) / (center - previousCenter);
        break;
      }
      previousCenter = center;
    }
    const nearest = Math.round(position);
    if (current !== nearest) {
      current = nearest;
      for (const [index, step] of steps.entries()) {
        if (index === current) step.setAttribute("aria-current", "step");
        else step.removeAttribute("aria-current");
      }
      apply(current);
    }
    const cameraPosition = reducedMotion.matches ? nearest : position;
    if (moveCamera && cameraPosition !== lastPosition) {
      lastPosition = cameraPosition;
      moveCamera(cameraPosition);
    }
  }

  function schedule() {
    if (following && !frame) frame = requestAnimationFrame(measure);
  }

  function setFollowing(value) {
    following = value;
    current = -1;
    lastPosition = NaN;
    steps.forEach(step => step.removeAttribute("aria-current"));
    toggle.textContent = following ? "Pause scroll control" : "Follow the text";
    container.dataset.following = String(following);
    schedule();
  }

  toggle.addEventListener("click", () => setFollowing(!following));
  // Let the browser scroll over a pinned canvas. In manual mode its own zoom handler runs.
  container.addEventListener("wheel", event => {
    if (following && !container.hasAttribute("data-reading-disabled") && !event.ctrlKey &&
        stage?.contains(event.target)) event.stopPropagation();
  }, {capture: true, passive: true});
  window.addEventListener("scroll", schedule, {passive: true});
  window.addEventListener("resize", schedule);
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) setFollowing(false);
  });
  new ResizeObserver(schedule).observe(container);
  setFollowing(following);
  return {
    refresh() { current = -1; lastPosition = NaN; schedule(); },
    pause() { if (following) setFollowing(false); },
  };
}
