// nav.js — мобильный drawer, дропдауны по клику, тень хедера при скролле
const header = document.querySelector('[data-header]');
const openBtn = document.querySelector('[data-drawer-open]');
const drawer = document.querySelector('[data-drawer]');
const overlay = document.querySelector('[data-overlay]');
const closeEls = document.querySelectorAll('[data-drawer-close]');

function setDrawer(open){
  drawer?.classList.toggle('is-open', open);
  overlay?.classList.toggle('is-open', open);
  document.body.classList.toggle('no-scroll', open);
  openBtn?.setAttribute('aria-expanded', String(open));
}
openBtn?.addEventListener('click', () => setDrawer(true));
closeEls.forEach(el => el.addEventListener('click', () => setDrawer(false)));
document.addEventListener('keydown', e => { if (e.key === 'Escape') setDrawer(false); });

// подсветка текущей страницы в меню (drawer + десктоп)
const current = location.pathname.replace(/\/+$/, '') || '/';
document.querySelectorAll('.drawer__link, .drawer__sub, .drawer__group-label, a.nav__link, .nav__sub, .nav__lead').forEach(link => {
  const path = new URL(link.href).pathname.replace(/\/+$/, '') || '/';
  if (path !== current) return;
  link.classList.add('is-active');
  link.closest('.nav__group')?.classList.add('is-active'); // подсветить раздел в шапке
});

const onScroll = () => header?.classList.toggle('is-scrolled', window.scrollY > 12);
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

document.querySelectorAll('.nav__toggle').forEach(btn => {
  btn.addEventListener('click', e => {
    e.preventDefault();
    const open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!open));
    btn.closest('.nav__group')?.classList.toggle('is-open', !open);
  });
});
