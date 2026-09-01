// nav.js — мобильный drawer, дропдауны по клику, переключатель салонов,
// тень хедера при скролле, уборка отработавшего якоря из адреса
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
  // Замок вешаем и на <html>: с одного <body> он не доходит до окна, см. CSS.
  document.documentElement.classList.toggle('no-scroll', open);
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
  setLocMenu(false);
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
    setLocMenu(false);
    setDropdown(btn, !open);
  });
});

document.addEventListener('click', e => {
  if (!e.target.closest('.nav__group')) closeDropdowns();
  if (!e.target.closest('.loc')) setLocMenu(false);
});

// ===== переключатель салонов =====
// Кнопка стоит в строке города фирменного замка, а не отдельным пунктом меню:
// свободного места в шапке нет, причина — в комментарии к .site-header__cta.
const locGroup = document.querySelector('[data-loc]');
const locToggle = locGroup?.querySelector('[data-loc-toggle]');

function setLocMenu(open){
  if (!locGroup) return;
  locGroup.classList.toggle('is-open', open);
  locToggle?.setAttribute('aria-expanded', String(open));
}

locToggle?.addEventListener('click', () => {
  const open = locToggle.getAttribute('aria-expanded') === 'true';
  closeDropdowns();
  setLocMenu(!open);
});

// ===== отработавший якорь =====
// Браузер оставляет #services в адресе навсегда: кликнув «Услуги» и дочитав до
// вопросов и ответов, гость видит адрес, который обещает совсем другой блок.
// Стираем хэш, когда его секция ушла из окна, — и только после того, как она
// хотя бы раз была видна, иначе уборка опередила бы сам переход по ссылке.
// replaceState, а не pushState: лишняя запись в истории заставила бы «Назад»
// возвращать на ту же страницу.
let hashObserver = null;

function forgetHashWhenOffscreen(){
  hashObserver?.disconnect();
  hashObserver = null;
  const id = decodeURIComponent(location.hash.slice(1));
  const target = id && document.getElementById(id);
  if (!target) return;
  let wasVisible = false;
  hashObserver = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) { wasVisible = true; return; }
    if (!wasVisible) return;
    hashObserver.disconnect();
    hashObserver = null;
    history.replaceState(null, '', location.pathname + location.search);
  });
  hashObserver.observe(target);
}

window.addEventListener('hashchange', forgetHashWhenOffscreen);
forgetHashWhenOffscreen();
