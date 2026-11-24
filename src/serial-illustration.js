const plate = document.querySelector(".method-plate");
const rings = Array.from(plate.querySelectorAll("ellipse"));
const replay = plate.querySelector(".trace-replay");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let played = false;

function settleTrace() {
  for (const ring of rings) {
    for (const animation of ring.getAnimations()) animation.cancel();
  }
}

function traceOpenings() {
  settleTrace();
  if (reducedMotion.matches) return;
  played = true;
  rings.forEach((ring, index) => {
    ring.animate([
      {opacity: 0, strokeWidth: 2},
      {opacity: 1, strokeWidth: 6, offset: .35},
      {opacity: .45, strokeWidth: 3},
    ], {duration: 850, delay: index * 430, easing: "ease-in-out", fill: "backwards"});
  });
}

function setMotionPreference() {
  replay.hidden = reducedMotion.matches;
  if (reducedMotion.matches) settleTrace();
}

setMotionPreference();
reducedMotion.addEventListener("change", setMotionPreference);
replay.addEventListener("click", traceOpenings);
new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting) settleTrace();
  else if (!played && entry.intersectionRatio >= .55) traceOpenings();
}, {threshold: [0, .55]}).observe(plate.querySelector(".serial-illustration"));
