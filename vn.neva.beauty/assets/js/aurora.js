// Деликатный pointer-parallax фонового слоя «Аврора»: при движении мыши слой
// смещается на несколько px, создавая ощущение глубины. Только transform.
// Пропускается на тач-устройствах (нет курсора — отслеживать нечего) и при
// включённом prefers-reduced-motion. Сам CSS-дрейф пятен работает всегда.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const isTouch = matchMedia("(pointer: coarse)").matches;
const aurora = document.querySelector(".aurora");

if (aurora && !reduceMotion && !isTouch) {
  const MAX_SHIFT = 14; // px
  let ticking = false;
  let targetX = 0;
  let targetY = 0;

  function apply() {
    aurora.style.setProperty("--px", `${targetX.toFixed(1)}px`);
    aurora.style.setProperty("--py", `${targetY.toFixed(1)}px`);
    ticking = false;
  }

  function onPointerMove(event) {
    const ratioX = event.clientX / window.innerWidth - 0.5;
    const ratioY = event.clientY / window.innerHeight - 0.5;
    targetX = -ratioX * MAX_SHIFT * 2;
    targetY = -ratioY * MAX_SHIFT * 2;
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(apply);
  }

  addEventListener("pointermove", onPointerMove, { passive: true });
}
