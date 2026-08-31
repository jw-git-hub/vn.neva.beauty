// nav.js — мобильный drawer, дропдауны по клику, тень хедера при скролле
const header = document.querySelector('[data-header]');
const openBtn = document.querySelector('[data-drawer-open]');
const drawer = document.querySelector('[data-drawer]');
const overlay = document.querySelector('[data-overlay]');
const closeEls = document.querySelectorAll('[data-drawer-close]');

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';
let focusBeforeDrawer = null;

function drawerFocusables(){
  return [...drawer.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null);
}

// Открытый drawer перекрывает страницу, поэтому Tab не должен уводить фокус
// под него: с последнего элемента прыгаем на первый и наоборот.
function trapTab(event){
  if (event.key !== 'Tab') return;
  const items = drawerFocusables();
  if (!items.length) return;
  const edge = event.shiftKey ? items[0] : items[items.length - 1];
  if (document.activeElement !== edge) return;
  event.preventDefault();
  (event.shiftKey ? items[items.length - 1] : items[0]).focus();
}

function moveFocusIntoDrawer(){
  focusBeforeDrawer = document.activeElement;
  drawerFocusables()[0]?.focus();
  document.addEventListener('keydown', trapTab);
}

function restoreFocusAfterDrawer(){
  document.removeEventListener('keydown', trapTab);
  focusBeforeDrawer?.focus();
  focusBeforeDrawer = null;
}

function setDrawer(open){
  if (!drawer || drawer.classList.contains('is-open') === open) return;
  drawer.classList.toggle('is-open', open);
  overlay?.classList.toggle('is-open', open);
  document.body.classList.toggle('no-scroll', open);
  openBtn?.setAttribute('aria-expanded', String(open));
  open ? moveFocusIntoDrawer() : restoreFocusAfterDrawer();
}
openBtn?.addEventListener('click', () => setDrawer(true));
closeEls.forEach(el => el.addEventListener('click', () => setDrawer(false)));
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  setDrawer(false);
  closeDropdowns();
});

// подсветка текущей страницы в меню (drawer + десктоп)
const current = location.pathname.replace(/\/+$/, '') || '/';
document.querySelectorAll('.drawer__link, .drawer__sub, .drawer__group-label, a.nav__link, .nav__sub, .nav__lead').forEach(link => {
  const path = new URL(link.href).pathname.replace(/\/+$/, '') || '/';
  if (path !== current) return;
  link.classList.add('is-active');
  link.closest('.nav__group')?.classList.add('is-active'); // подсветить раздел в шапке
});

const onScroll = () => header?.classList.toggle('is-scrolled', window.scrollY > 12);
// Первый замер — в кадре отрисовки: сразу после правки классов выше чтение
// scrollY заставляло браузер пересчитать вёрстку синхронно (37 мс на мобильном).
requestAnimationFrame(onScroll);
window.addEventListener('scroll', onScroll, { passive: true });

const navToggles = [...document.querySelectorAll('.nav__toggle')];

function setDropdown(btn, open){
  btn.setAttribute('aria-expanded', String(open));
  btn.closest('.nav__group')?.classList.toggle('is-open', open);
}

// Одновременно открытым остаётся только один список раздела.
function closeDropdowns(except){
  navToggles.forEach(btn => { if (btn !== except) setDropdown(btn, false); });
}

navToggles.forEach(btn => {
  btn.addEventListener('click', e => {
    e.preventDefault();
    const open = btn.getAttribute('aria-expanded') === 'true';
    closeDropdowns(btn);
    setDropdown(btn, !open);
  });
});

document.addEventListener('click', e => {
  if (!e.target.closest('.nav__group')) closeDropdowns();
});
