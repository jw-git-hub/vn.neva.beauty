// Замер узкого экрана одной страницы. Возвращает массив строк-находок без повторов.
// drawerOpen — открыто ли боковое меню: тогда проверяется и оно, и всё внутри ящика.
(drawerOpen) => {
  const EDGE_TOLERANCE = 0.5;
  const FRAME_TOLERANCE = 1;
  const SCROLL_TOLERANCE = 1;
  const LINE_BREAK_MIN_SHIFT = 4;
  const MIN_TAP_SIZE = 44;
  const MAX_ROOTS = 6;
  const TEXT_PREVIEW_LENGTH = 34;
  const BREAK_BEFORE_LENGTH = 12;
  const BREAK_AFTER_LENGTH = 4;
  const TRANSPARENT = "rgba(0, 0, 0, 0)";
  const WORD_SEPARATOR = /\s+/g;
  const WORD_CHARACTER = /[\p{L}\p{N}]/u;
  const DRAWER_SELECTOR = "[data-drawer]";
  const DRAWER_OPEN_SELECTOR = "[data-drawer-open]";
  const DRAWER_CLOSE_SELECTOR = ".drawer__close";
  const FAQ_QUESTION_SELECTOR = ".faq__q";
  const HIDDEN_FOR_READERS_SELECTOR = ".visually-hidden";
  const DECORATIVE_SELECTOR = "[aria-hidden='true'],canvas,.aurora";
  const HEADING_SELECTOR = "h1,h2,h3,h4,summary.faq__q";
  const AUTO_HYPHENS = "auto";
  const SCROLLING_OVERFLOW = ["auto", "scroll"];

  const viewportWidth = innerWidth;
  const drawer = document.querySelector(DRAWER_SELECTOR);

  const className = (element) => {
    const raw = typeof element.className === "string" ? element.className : element.className.baseVal;
    return (raw || "").trim().split(/\s+/)[0];
  };
  const label = (element) => {
    const name = className(element);
    return element.tagName.toLowerCase() + (name ? "." + name : "");
  };
  const describe = (element, extra = "") => {
    const rect = element.getBoundingClientRect();
    const parent = element.parentElement ? " в " + label(element.parentElement) : "";
    const text = (element.textContent || "").trim().replace(WORD_SEPARATOR, " ").slice(0, TEXT_PREVIEW_LENGTH);
    return `${label(element)}${parent} L=${Math.round(rect.left)} R=${Math.round(rect.right)}${extra} «${text}»`;
  };
  const closestFixed = (element) => {
    for (let node = element; node && node !== document.documentElement; node = node.parentElement) {
      if (getComputedStyle(node).position === "fixed") return node;
    }
    return null;
  };
  const isShown = (element) => element.checkVisibility({ visibilityProperty: true, opacityProperty: false });
  const isReadable = (element) => isShown(element) && !element.closest(HIDDEN_FOR_READERS_SELECTOR);
  const isOutsideWindow = (rect) => rect.right > viewportWidth + EDGE_TOLERANCE || rect.left < -EDGE_TOLERANCE;
  const rootsOf = (elements) => {
    const set = new Set(elements);
    return [...set].filter((element) => !set.has(element.parentElement));
  };
  const isInScope = (element) => {
    if (!closestFixed(element)) return true;
    return drawerOpen && Boolean(drawer) && drawer.contains(element);
  };
  const scope = [...document.querySelectorAll("body *")].filter(isInScope);
  const scopeSet = new Set(scope);
  const textNodes = () => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const host = node.parentElement;
      if (node.data.trim() && scopeSet.has(host) && isReadable(host)) nodes.push(node);
    }
    return nodes;
  };
  const rangeOf = (node, start, end) => {
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, end);
    return range;
  };

  // Страница шире окна: корни выступающих элементов.
  const wideDocument = () => {
    const width = document.documentElement.scrollWidth;
    if (width <= viewportWidth) return [];
    const sticking = scope.filter((element) => {
      const rect = element.getBoundingClientRect();
      return !closestFixed(element) && rect.width > 0 && rect.right > viewportWidth + EDGE_TOLERANCE;
    });
    const roots = rootsOf(sticking).slice(0, MAX_ROOTS).map((element) => describe(element));
    return [`страница ${width} > ${viewportWidth}: ${roots.join(" | ") || "(текст или псевдоэлемент)"}`];
  };

  // Элемент обрезан предком с overflow-x, который сам целиком в окне: это не находка.
  const isClippedInside = (element) => {
    for (let node = element.parentElement; node && node !== document.body; node = node.parentElement) {
      if (getComputedStyle(node).overflowX === "visible") continue;
      return !isOutsideWindow(node.getBoundingClientRect());
    }
    return false;
  };
  const isBeyondEdge = (element) => {
    if (closestFixed(element) || !isReadable(element) || element.closest(DECORATIVE_SELECTOR)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && isOutsideWindow(rect) && !isClippedInside(element);
  };
  const beyondEdge = () => rootsOf(scope.filter(isBeyondEdge))
    .slice(0, MAX_ROOTS).map((element) => `за краем окна: ${describe(element)}`);

  // Свой горизонтальный скролл у блока.
  const ownScroll = () => scope.filter((element) => {
    if (!isReadable(element)) return false;
    const style = getComputedStyle(element);
    if (style.display === "inline" || style.display === "contents") return false;
    return SCROLLING_OVERFLOW.includes(style.overflowX)
      && element.scrollWidth > element.clientWidth + SCROLL_TOLERANCE;
  }).map((element) => `своя прокрутка: ${describe(element, ` sw=${element.scrollWidth} cw=${element.clientWidth}`)}`);

  // Рамка: правая граница, непрозрачный фон или обрезка по горизонтали.
  const isFrame = (element) => {
    const style = getComputedStyle(element);
    return parseFloat(style.borderRightWidth) > 0 || style.backgroundColor !== TRANSPARENT
      || style.overflowX !== "visible";
  };
  const closestFrame = (element) => {
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      if (isFrame(node)) return node;
    }
    return null;
  };
  const innerEdges = (frame) => {
    const rect = frame.getBoundingClientRect();
    const style = getComputedStyle(frame);
    return {
      left: rect.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      right: rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
    };
  };
  const frameFinding = (node) => {
    const frame = closestFrame(node.parentElement);
    if (!frame) return null;
    const edges = innerEdges(frame);
    const range = rangeOf(node, 0, node.length);
    const bad = [...range.getClientRects()].find((rect) => rect.width > 0
      && (rect.right > edges.right + FRAME_TOLERANCE || rect.left < edges.left - FRAME_TOLERANCE));
    if (!bad) return null;
    const extra = ` строка ${Math.round(bad.left)}–${Math.round(bad.right)} поле ${Math.round(edges.left)}–${Math.round(edges.right)}`;
    return `текст за полем рамки ${label(frame)}: ${describe(node.parentElement, extra)}`;
  };
  const textBeyondFrame = () => textNodes().map(frameFinding).filter(Boolean);

  // Слово рвётся без дефиса: ищем место разрыва внутри слова, которое легло на две строки.
  const wordsOf = (node) => [...node.data.matchAll(/\S+/g)].map((match) => ({
    start: match.index, end: match.index + match[0].length,
  }));
  const isSplitAcrossLines = (range) => {
    const tops = [...range.getClientRects()].map((rect) => rect.top);
    return tops.length > 1 && Math.max(...tops) - Math.min(...tops) > LINE_BREAK_MIN_SHIFT;
  };
  const topOfCharacter = (node, index) => {
    const rect = rangeOf(node, index, index + 1).getClientRects()[0];
    return rect ? rect.top : null;
  };
  const findBreakIndex = (node, word) => {
    let previousTop = null;
    for (let index = word.start; index < word.end; index++) {
      const top = topOfCharacter(node, index);
      if (top === null) continue;
      if (previousTop !== null && top - previousTop > LINE_BREAK_MIN_SHIFT) return index;
      previousTop = top;
    }
    return -1;
  };
  const textKind = (element) => {
    let block = element;
    while (block.parentElement && getComputedStyle(block).display === "inline") block = block.parentElement;
    return block.closest(HEADING_SELECTOR) ? "заголовок" : "текст";
  };
  const brokenWordFinding = (node, word) => {
    const index = findBreakIndex(node, word);
    if (index < 0 || !WORD_CHARACTER.test(node.data[index - 1]) || !WORD_CHARACTER.test(node.data[index])) return null;
    const before = node.data.slice(Math.max(word.start, index - BREAK_BEFORE_LENGTH), index);
    const after = node.data.slice(index, index + BREAK_AFTER_LENGTH);
    return `слово рвётся без дефиса (${textKind(node.parentElement)}): ${describe(node.parentElement, ` «…${before}/${after}…»`)}`;
  };
  const brokenWordsOf = (node) => {
    if (getComputedStyle(node.parentElement).hyphens === AUTO_HYPHENS) return [];
    return wordsOf(node)
      .filter((word) => isSplitAcrossLines(rangeOf(node, word.start, word.end)))
      .map((word) => brokenWordFinding(node, word)).filter(Boolean);
  };
  const brokenWords = () => textNodes().flatMap(brokenWordsOf);

  // «+» вопроса FAQ — псевдоэлемент, текстом его не поймать.
  const faqPlusFinding = (question) => {
    const range = document.createRange();
    range.selectNodeContents(question);
    const textRight = Math.max(...[...range.getClientRects()].map((rect) => rect.right));
    const style = getComputedStyle(question);
    const plusWidth = parseFloat(getComputedStyle(question, "::after").width) || 0;
    const end = textRight + (parseFloat(style.columnGap) || 0) + plusWidth;
    const edge = question.getBoundingClientRect().right - parseFloat(style.paddingRight);
    if (end <= edge + FRAME_TOLERANCE) return null;
    return `«+» FAQ за краем вопроса: ${describe(question, ` конец ${Math.round(end)} край ${Math.round(edge)}`)}`;
  };
  const faqPlus = () => [...document.querySelectorAll(FAQ_QUESTION_SELECTOR)]
    .filter(isShown).map(faqPlusFinding).filter(Boolean);

  // Кнопки меню не сжаты и не за краем окна.
  const buttonFinding = (selector) => {
    const button = document.querySelector(selector);
    if (!button || !isShown(button)) return null;
    const rect = button.getBoundingClientRect();
    const tooSmall = rect.width < MIN_TAP_SIZE - EDGE_TOLERANCE || rect.height < MIN_TAP_SIZE - EDGE_TOLERANCE;
    if (!tooSmall && rect.right <= viewportWidth + EDGE_TOLERANCE) return null;
    return `кнопка ${selector} ${rect.width.toFixed(1)}×${rect.height.toFixed(1)} R=${rect.right.toFixed(1)}`;
  };
  const menuButtons = () => [DRAWER_OPEN_SELECTOR, ...(drawerOpen ? [DRAWER_CLOSE_SELECTOR] : [])]
    .map(buttonFinding).filter(Boolean);

  // В открытом меню всё внутри ящика.
  const beyondDrawer = () => {
    if (!drawerOpen || !drawer) return [];
    const box = drawer.getBoundingClientRect();
    const rightEdge = Math.min(box.right, viewportWidth);
    const outside = [...drawer.querySelectorAll("*")].filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && (rect.right > rightEdge + EDGE_TOLERANCE || rect.left < box.left - EDGE_TOLERANCE);
    });
    return rootsOf(outside).map((element) => `меню за краем: ${describe(element)}`);
  };

  const findings = [
    ...wideDocument(), ...beyondEdge(), ...ownScroll(), ...brokenWords(),
    ...textBeyondFrame(), ...faqPlus(), ...menuButtons(), ...beyondDrawer(),
  ];
  return [...new Set(findings)];
}
