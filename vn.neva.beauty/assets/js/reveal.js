// Появления секций и карточек при входе во вьюпорт (fade-up, одноразово).
const SELECTOR = "[data-reveal], [data-reveal-children]";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function reveal(el) {
  if (el.hasAttribute("data-reveal-children")) {
    [...el.children].forEach((child, i) => {
      child.style.transitionDelay = `${i * 70}ms`;
      child.classList.add("is-visible");
    });
  } else {
    el.classList.add("is-visible");
  }
}

const targets = document.querySelectorAll(SELECTOR);

if (reduceMotion) {
  targets.forEach(reveal);
} else {
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        reveal(entry.target);
        observer.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -10% 0px", threshold: 0.15 }
  );
  targets.forEach((el) => observer.observe(el));
}
