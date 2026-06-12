// Лёгкий параллакс частиц декора: двигаются медленнее скролла.
// Трансформ ставится на .decor__dot, дрейф-анимация живёт на ::before — не конфликтуют.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

if (!reduceMotion) {
  const sections = [...document.querySelectorAll(".has-decor")]
    .map((section) => ({
      section,
      dots: [...section.querySelectorAll(".decor__dot")].map((node) => ({
        node,
        depth: parseFloat(node.dataset.depth) || 0.05,
      })),
    }))
    .filter((entry) => entry.dots.length);

  let ticking = false;

  function update() {
    const viewportCenter = window.innerHeight / 2;
    for (const { section, dots } of sections) {
      const rect = section.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
      const offset = viewportCenter - (rect.top + rect.height / 2);
      for (const { node, depth } of dots) {
        node.style.transform = `translate3d(0, ${(offset * depth).toFixed(1)}px, 0)`;
      }
    }
    ticking = false;
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  }

  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll, { passive: true });
  update();
}
