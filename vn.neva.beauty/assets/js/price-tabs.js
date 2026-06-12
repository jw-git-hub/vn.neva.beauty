// price-tabs.js — переключение разделов прайс-листа
document.querySelectorAll('[data-pricelist]').forEach(pl => {
  const tabs = [...pl.querySelectorAll('.pricelist__tab')];
  const panels = [...pl.querySelectorAll('.pricelist__panel')];
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const i = tab.dataset.tab;
      tabs.forEach(t => {
        const on = t === tab;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', String(on));
      });
      panels.forEach(p => p.classList.toggle('is-active', p.dataset.panel === i));
    });
  });
});
