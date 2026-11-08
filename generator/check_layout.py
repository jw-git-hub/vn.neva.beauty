"""Проверка вёрстки «Популярного» на главной: текст карточки не наезжает на цену.
Падает (exit 1) при нарушении.

Зачем: название услуги капсом с разрядкой («M22 PHOTOREJUVENATION») на узком экране
выступает из своей коробки под цену. Это видно только глазами и только на части
ширин, а в собранном HTML не видно вовсе. Здесь сборка открывается в настоящем
Chrome на каждой ширине из списка, и для каждой карточки сверяются прямоугольники
строк текста (Range.getClientRects) с прямоугольником цены. Нет ни одной карточки
на странице — тоже ошибка: иначе проверка молча стала бы пустой.
Chrome берётся установленный (channel="chrome"), playwright install не нужен.
Сайт отдаёт http.server из стандартной библиотеки в потоке на свободном порту.
Запуск: python generator/check_layout.py"""
import functools
import http.server
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "vn.neva.beauty"
HOST = "127.0.0.1"
FREE_PORT = 0
PAGES = {"/": "ru", "/en/": "en"}
WIDTHS = (250, 270, 290, 300, 320, 340, 350, 360, 390, 420, 480, 559, 560, 600,
          640, 679, 680, 767, 768, 900, 1024, 1280, 1440)
VIEWPORT_HEIGHT = 800
BROWSER_CHANNEL = "chrome"
LANGUAGE_STORAGE_KEY = "neva.lang"
CARD_SELECTOR = ".popular-card"
INFO_SELECTOR = ".popular-card__info"
PRICE_SELECTOR = ".popular-card__price"
NAME_SELECTOR = ".popular-card__name"
# Анимацию появления снимаем до замера: иначе карточка ещё сдвинута и прозрачна.
REVEAL_SELECTOR = "[data-reveal],[data-reveal-children]>*"
VISIBLE_CLASS = "is-visible"

# Прямоугольники текста и цены каждой карточки: {name, price, lines}.
MEASURE_SCRIPT = f"""() => {{
  const box = r => ({{left: r.left, top: r.top, right: r.right, bottom: r.bottom}});
  const lineBoxes = el => {{
    const range = document.createRange();
    range.selectNodeContents(el);
    return [...range.getClientRects()].map(box);
  }};
  return [...document.querySelectorAll('{CARD_SELECTOR}')].map(card => ({{
    name: card.querySelector('{NAME_SELECTOR}').textContent.trim(),
    price: box(card.querySelector('{PRICE_SELECTOR}').getBoundingClientRect()),
    lines: lineBoxes(card.querySelector('{INFO_SELECTOR}')),
  }}));
}}"""
# Шрифты дожидаемся: от них зависит ширина строк, а значит и сам наезд.
REVEAL_SCRIPT = f"""async () => {{
  await document.fonts.ready;
  document.querySelectorAll('{REVEAL_SELECTOR}').forEach(el => {{
    el.style.transition = 'none';
    el.classList.add('{VISIBLE_CLASS}');
  }});
}}"""


def rects_overlap(first, second):
    """Прямоугольники пересекаются по площади; касание краями не в счёт."""
    width = min(first["right"], second["right"]) - max(first["left"], second["left"])
    height = min(first["bottom"], second["bottom"]) - max(first["top"], second["top"])
    return width > 0 and height > 0


def card_overlaps(card):
    """Хотя бы одна строка текста карточки задевает её цену."""
    return any(rects_overlap(line, card["price"]) for line in card["lines"])


def card_errors(url, width, cards):
    """Строки ошибок одной страницы на одной ширине."""
    if not cards:
        return [f"{url} {width} px: нет ни одной карточки «Популярного» ({CARD_SELECTOR})"]
    return [f"{url} {width} px: карточка «{card['name']}» — текст наезжает на цену"
            for card in cards if card_overlaps(card)]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Отдаёт файлы сборки и не засоряет вывод проверки журналом запросов."""

    def log_message(self, *args):
        pass


@contextmanager
def serve_site():
    """Сайт на свободном порту; поток и порт освобождаются на выходе."""
    handler = functools.partial(QuietHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer((HOST, FREE_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{HOST}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def open_page(browser, base_url, url, language):
    """Страница с зафиксированным языком (без автопереадресации по языку браузера)."""
    context = browser.new_context(viewport={"width": WIDTHS[0], "height": VIEWPORT_HEIGHT})
    context.add_init_script(
        f"localStorage.setItem('{LANGUAGE_STORAGE_KEY}', '{language}')")
    page = context.new_page()
    page.goto(base_url + url, wait_until="load")
    page.evaluate(REVEAL_SCRIPT)
    return page


def measure_widths(page, url):
    """Ошибки одной страницы на всех ширинах."""
    errors = []
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": VIEWPORT_HEIGHT})
        errors += card_errors(url, width, page.evaluate(MEASURE_SCRIPT))
    return errors


def collect_errors():
    from playwright.sync_api import sync_playwright
    errors = []
    with serve_site() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=BROWSER_CHANNEL)
        try:
            for url, language in PAGES.items():
                page = open_page(browser, base_url, url, language)
                errors += measure_widths(page, url)
                page.context.close()
        finally:
            browser.close()
    return errors


def main():
    errors = collect_errors()
    print(f"страниц: {len(PAGES)}, ширин: {len(WIDTHS)}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("LAYOUT OK — текст карточек «Популярного» не наезжает на цену")


if __name__ == "__main__":
    main()
