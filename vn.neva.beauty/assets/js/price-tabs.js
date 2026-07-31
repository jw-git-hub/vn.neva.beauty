// price-tabs.js — переключение разделов прайс-листа (паттерн ARIA tabs)
const STEP_BY_KEY = { ArrowRight: 1, ArrowLeft: -1 };

function selectTab(tabs, current, moveFocus) {
  tabs.forEach((tab) => {
    const on = tab === current;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1; // в Tab-обход попадает только активная вкладка
    document.getElementById(tab.getAttribute("aria-controls")).classList.toggle("is-active", on);
  });
  if (moveFocus) current.focus();
}

document.querySelectorAll("[data-pricelist]").forEach((pricelist) => {
  const tabs = [...pricelist.querySelectorAll(".pricelist__tab")];
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => selectTab(tabs, tab, false));
    tab.addEventListener("keydown", (event) => {
      const step = STEP_BY_KEY[event.key];
      if (!step) return;
      event.preventDefault();
      selectTab(tabs, tabs[(i + step + tabs.length) % tabs.length], true);
    });
  });
});
