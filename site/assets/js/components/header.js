import { lockScroll, unlockScroll, resetScrollLock } from '../utils/scroll-lock.js';

// Класс панели/backdrop — из kit-компонента nav-drawer (механика общая
// для th+vn). z-bump шапки над backdrop — site-local.
const NAV_OPEN_CLASS      = 'nav-drawer--open';
const BACKDROP_VISIBLE    = 'nav-drawer__backdrop--visible';
const DRAWER_OPEN_CLASS   = 'site-header--drawer-open';
const DROPDOWN_OPEN_CLASS = 'site-header__dropdown--open';

// Брейкпоинт перехода drawer → горизонтальная навигация. У vn — 1024px
// (длинные ярлыки не влезают в строку раньше ~1016px); kit .nav-drawer
// сбросился бы уже на 768px, но header.css держит off-canvas до 1024px
// (vn-override). Совпадает с @media шапки.
const DESKTOP_MQ = '(min-width: 1024px)';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

const SUPPORTS_INERT = 'inert' in HTMLElement.prototype;

export function initHeader() {
  const header = document.querySelector('.site-header');
  if (!header) return;

  const burger = header.querySelector('.site-header__burger');
  const nav    = header.querySelector('.site-header__nav');
  if (!burger || !nav) return;

  // Кнопка ✕ внутри панели (из kit-разметки nav-drawer)
  const closeBtn = nav.querySelector('.nav-drawer__close');

  // Backdrop — создаём один раз, не дублируем
  let backdrop = document.querySelector('.nav-drawer__backdrop');
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.className = 'nav-drawer__backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    document.body.appendChild(backdrop);
  }

  const main   = document.querySelector('main');
  const footer = document.querySelector('footer');
  let lastFocused = null;

  // ---------- Утилиты ----------

  function getFocusable() {
    return Array.from(nav.querySelectorAll(FOCUSABLE_SELECTOR));
  }

  function focusFirst() {
    const items = getFocusable();
    if (items.length > 0) {
      items[0].focus();
    } else {
      if (!nav.hasAttribute('tabindex')) nav.setAttribute('tabindex', '-1');
      nav.focus();
    }
  }

  function setInert(active) {
    [main, footer].forEach((el) => {
      if (!el) return;
      if (SUPPORTS_INERT) {
        if (active) el.setAttribute('inert', '');
        else        el.removeAttribute('inert');
      } else {
        if (active) el.setAttribute('aria-hidden', 'true');
        else        el.removeAttribute('aria-hidden');
      }
    });
  }

  function setNavAccessibility(open) {
    if (!SUPPORTS_INERT) return;
    const isMobile = !window.matchMedia(DESKTOP_MQ).matches;
    if (isMobile) {
      if (open) nav.removeAttribute('inert');
      else      nav.setAttribute('inert', '');
    } else {
      nav.removeAttribute('inert');
    }
  }

  // ---------- Drawer ----------

  function setOpen(open) {
    nav.classList.toggle(NAV_OPEN_CLASS, open);
    backdrop.classList.toggle(BACKDROP_VISIBLE, open);
    header.classList.toggle(DRAWER_OPEN_CLASS, open);
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    setNavAccessibility(open);

    if (open) {
      lockScroll();
      setInert(true);
      lastFocused = document.activeElement;
      focusFirst();
    } else {
      unlockScroll();
      setInert(false);
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus();
      }
    }
  }

  burger.setAttribute('aria-expanded', 'false');
  setNavAccessibility(false);

  burger.addEventListener('click', (e) => {
    e.stopPropagation();
    setOpen(!nav.classList.contains(NAV_OPEN_CLASS));
  });

  backdrop.addEventListener('click', () => setOpen(false));

  // Крестик ✕ закрывает; фокус возвращается на бургер (setOpen вернёт его
  // на lastFocused = бургер, открывавший меню).
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      setOpen(false);
      burger.focus();
    });
  }

  // Закрываем drawer при клике по ссылке внутри
  nav.addEventListener('click', (e) => {
    const link = e.target.closest('.site-header__nav-link');
    if (link && !link.closest('.site-header__dropdown-toggle')) {
      setOpen(false);
    }
  });

  // Закрываем drawer при переходе на desktop
  const mq = window.matchMedia(DESKTOP_MQ);
  mq.addEventListener('change', (e) => {
    if (e.matches && nav.classList.contains(NAV_OPEN_CLASS)) {
      setOpen(false);
    }
    setNavAccessibility(nav.classList.contains(NAV_OPEN_CLASS));
    // Закрыть все дропдауны при смене брейкпоинта
    closeAllDropdowns();
  });

  // bfcache
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) {
      resetScrollLock();
      if (nav.classList.contains(NAV_OPEN_CLASS)) setOpen(false);
      setNavAccessibility(false);
      closeAllDropdowns();
    }
  });

  // ---------- Dropdown «Аппаратная косметология» ----------

  const dropdownItems = header.querySelectorAll('.site-header__nav-item--has-dropdown');

  function closeAllDropdowns() {
    dropdownItems.forEach((item) => {
      const toggle   = item.querySelector('.site-header__dropdown-toggle');
      const dropdown = item.querySelector('.site-header__dropdown');
      if (!dropdown || !toggle) return;
      item.classList.remove(DROPDOWN_OPEN_CLASS);
      toggle.setAttribute('aria-expanded', 'false');
      dropdown.setAttribute('aria-hidden', 'true');
    });
  }

  function toggleDropdown(item) {
    const toggle   = item.querySelector('.site-header__dropdown-toggle');
    const dropdown = item.querySelector('.site-header__dropdown');
    if (!toggle || !dropdown) return;

    const isOpen = item.classList.contains(DROPDOWN_OPEN_CLASS);

    // Закрыть остальные
    dropdownItems.forEach((other) => {
      if (other !== item) {
        const t = other.querySelector('.site-header__dropdown-toggle');
        const d = other.querySelector('.site-header__dropdown');
        if (!t || !d) return;
        other.classList.remove(DROPDOWN_OPEN_CLASS);
        t.setAttribute('aria-expanded', 'false');
        d.setAttribute('aria-hidden', 'true');
      }
    });

    // Переключить текущий
    item.classList.toggle(DROPDOWN_OPEN_CLASS, !isOpen);
    toggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
    dropdown.setAttribute('aria-hidden', isOpen ? 'true' : 'false');
  }

  dropdownItems.forEach((item) => {
    const toggle = item.querySelector('.site-header__dropdown-toggle');
    if (!toggle) return;

    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleDropdown(item);
    });
  });

  // Закрыть дропдаун при клике снаружи
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.site-header__nav-item--has-dropdown')) {
      closeAllDropdowns();
    }
  });

  // Клавиатура: Escape закрывает дропдаун / drawer
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      // Если открыт дропдаун — закрываем его
      const openItem = header.querySelector(`.${DROPDOWN_OPEN_CLASS}`);
      if (openItem) {
        const toggle = openItem.querySelector('.site-header__dropdown-toggle');
        closeAllDropdowns();
        if (toggle) toggle.focus();
        return;
      }
      // Если открыт drawer — закрываем его
      if (nav.classList.contains(NAV_OPEN_CLASS)) {
        setOpen(false);
        burger.focus();
      }
    }

    // Focus-trap внутри drawer (только без inert, только на мобиле/планшете)
    if (!SUPPORTS_INERT && e.key === 'Tab' && nav.classList.contains(NAV_OPEN_CLASS)) {
      const items = getFocusable();
      if (!items.length) return;
      const first = items[0];
      const last  = items[items.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    }
  });
}
