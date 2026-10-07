// Появления секций и карточек при входе во вьюпорт (fade-up, одноразово).
const BLOCK_SELECTOR = "[data-reveal]";
const CARD_SELECTOR = "[data-reveal-children] > *";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
// Блок (заголовок секции, таблица) считается вошедшим, когда его пятнадцатая
// с небольшим часть показалась во вьюпорте, укороченном снизу на 10%.
const BLOCK_OBSERVER_OPTIONS = { rootMargin: "0px 0px -10% 0px", threshold: 0.15 };
// Шаг каскада: каждая следующая карточка ряда стартует на столько позже предыдущей.
const STAGGER_MS = 70;

function show(el, delayMs = 0) {
  if (delayMs) el.style.transitionDelay = `${delayMs}ms`;
  el.classList.add("is-visible");
}

function revealBlocks(entries, observer) {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    show(entry.target);
    observer.unobserve(entry.target);
  }
}

// Сетку наблюдаем не целиком, а по карточке. Порог блочного наблюдателя — доля
// высоты блока, и чем сетка выше, тем позже она появлялась: в одну колонку
// на телефоне первый ряд оставался прозрачным, пока в экран не въезжало
// пол-экрана пустого места, а самым высоким сеткам порог был недостижим вовсе.
// Карточки одного ряда стоят на одной высоте и входят во вьюпорт одним пакетом,
// в порядке разметки, поэтому каскад считается внутри ряда: первая карточка
// каждого ряда стартует сразу, а не ждёт своей очереди за всеми рядами выше.
function revealRows(entries, observer) {
  const shownInRow = new Map();
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    const rowTop = Math.round(entry.boundingClientRect.top);
    const position = shownInRow.get(rowTop) ?? 0;
    shownInRow.set(rowTop, position + 1);
    show(entry.target, position * STAGGER_MS);
    observer.unobserve(entry.target);
  }
}

const blocks = document.querySelectorAll(BLOCK_SELECTOR);
const cards = document.querySelectorAll(CARD_SELECTOR);

if (reduceMotion) {
  for (const el of [...blocks, ...cards]) show(el);
} else {
  const blockObserver = new IntersectionObserver(revealBlocks, BLOCK_OBSERVER_OPTIONS);
  // Без порога и без укороченного вьюпорта: карточке хватает первого пикселя.
  const rowObserver = new IntersectionObserver(revealRows);
  blocks.forEach((el) => blockObserver.observe(el));
  cards.forEach((el) => rowObserver.observe(el));
}
