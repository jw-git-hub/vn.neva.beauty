"""Проверка вёрстки сборки в настоящем Chrome. Падает (exit 1) при нарушении.

Часть 1 — «Популярное» на главной: текст карточки не наезжает на цену. Название
услуги капсом с разрядкой («M22 PHOTOREJUVENATION») на узком экране выступает из
своей коробки под цену; сверяются прямоугольники строк текста (Range.getClientRects)
с прямоугольником цены. Нет ни одной карточки — тоже ошибка.

Часть 2 — узкие экраны по всей сборке: каждая страница обоих языков на ширинах от
250 px (обложки телефонов-раскладушек — 280–344 px, 250 — запас владельца), закрытая
и с открытым меню. Замер лежит в check_layout.js: страница не шире окна, ничего не
за краем, нет своей горизонтальной прокрутки, текст не на поле рамки, слова не рвутся
без дефиса, «+» вопроса FAQ на месте, кнопки меню не меньше 44 px, меню не вылезает
за ящик. Не нашлось ни одной страницы — ошибка: иначе проверка молча стала бы пустой.

Chrome берётся установленный (channel="chrome"), playwright install не нужен.
Сайт отдаёт http.server из стандартной библиотеки в потоке на свободном порту;
внешние запросы (Яндекс Метрика) блокируются.
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
# Узкие экраны: ширины из правила владельца (250, 280, 320, 350, 390), 360 — ходовой Android,
# остальные — по обе стороны ступеней узких правил (255.98, 279.98, 289.98, 299.98, 349.98 px)
# и 403 — край переноса длинного слова в прайсе (403.98 px, решение владельца 09.11.2026).
NARROW_WIDTHS = (250, 270, 280, 290, 300, 320, 340, 350, 360, 390, 403)
LANGUAGES = ("ru", "en")
ENGLISH_PREFIX = "/en/"
ENGLISH_DIRECTORY = "en"
NOT_FOUND_PAGE = "404.html"
PAGE_INDEX = "index.html"
STATE_CLOSED = "закрыто"
STATE_MENU = "меню"
STATES = (STATE_CLOSED, STATE_MENU)
MEASURE_FILE = ROOT / "check_layout.js"
DRAWER_OPEN_SELECTOR = "[data-drawer-open]"
DRAWER_SELECTOR = "[data-drawer]"
DETAILS_SELECTOR = "details"
PRICE_PANEL_SELECTOR = ".pricelist__panel"
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
# Скрытое по умолчанию содержимое тоже должно помещаться: все вкладки прайса и все
# ответы FAQ раскрываются до замера.
REVEAL_ALL_SCRIPT = f"""async () => {{
  await document.fonts.ready;
  document.querySelectorAll('{REVEAL_SELECTOR}').forEach(el => {{
    el.style.transition = 'none';
    el.classList.add('{VISIBLE_CLASS}');
  }});
  document.querySelectorAll('{DETAILS_SELECTOR}').forEach(el => {{ el.open = true; }});
  document.querySelectorAll('{PRICE_PANEL_SELECTOR}').forEach(el => {{ el.style.display = 'block'; }});
}}"""
# Меню открывается кликом в странице; при reduced motion переход почти нулевой, но на
# двух кадрах ящик иногда ещё не доехал, поэтому после них ждём конец его анимаций.
OPEN_DRAWER_SCRIPT = f"""async () => {{
  const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));
  document.querySelector('{DRAWER_OPEN_SELECTOR}').click();
  await nextFrame();
  await nextFrame();
  const drawer = document.querySelector('{DRAWER_SELECTOR}');
  await Promise.all(drawer.getAnimations().map(animation => animation.finished));
  await nextFrame();
}}"""
IS_DRAWER_BUTTON_VISIBLE_SCRIPT = f"""() => {{
  const button = document.querySelector('{DRAWER_OPEN_SELECTOR}');
  return Boolean(button) && button.checkVisibility();
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


def new_context(browser, base_url, language, width, reduced_motion="no-preference"):
    """Контекст с зафиксированным языком (без автопереадресации по языку браузера)
    и без внешних запросов: всё, что не с адреса локального сервера, отменяется."""
    context = browser.new_context(viewport={"width": width, "height": VIEWPORT_HEIGHT},
                                  reduced_motion=reduced_motion)
    context.add_init_script(
        f"localStorage.setItem('{LANGUAGE_STORAGE_KEY}', '{language}')")
    context.route(lambda url: not url.startswith(base_url), lambda route: route.abort())
    return context


def open_page(browser, base_url, url, language):
    """Страница «Популярного» с зафиксированным языком."""
    context = new_context(browser, base_url, language, WIDTHS[0])
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


def folders_with_index(directory, skipped=()):
    """Адреса папок каталога, где лежит index.html, по алфавиту (относительно directory)."""
    return sorted(entry.name for entry in directory.iterdir()
                  if entry.is_dir() and entry.name not in skipped
                  and (entry / PAGE_INDEX).is_file())


def list_site_pages(site):
    """Все собранные страницы: русские, затем английские (адреса с / в начале и конце)."""
    russian = [f"/{name}/" for name in folders_with_index(site, (ENGLISH_DIRECTORY,))]
    english = [f"{ENGLISH_PREFIX}{name}/"
               for name in folders_with_index(site / ENGLISH_DIRECTORY)]
    return (["/", f"/{NOT_FOUND_PAGE}"] + russian
            + [ENGLISH_PREFIX, f"{ENGLISH_PREFIX}{NOT_FOUND_PAGE}"] + english)


def page_language(url):
    """Язык страницы по адресу: en для /en/…, иначе ru."""
    return "en" if url.startswith(ENGLISH_PREFIX) else "ru"


def pages_of_language(pages, language):
    """Страницы одного языка из общего списка."""
    return [url for url in pages if page_language(url) == language]


def narrow_error(url, width, state, finding):
    """Строка ошибки узкого экрана."""
    return f"{url} {width} px [{state}]: {finding}"


def narrow_errors(url, width, state, findings):
    """Строки ошибок для всех находок одного состояния страницы."""
    return [narrow_error(url, width, state, finding) for finding in findings]


def no_pages_error():
    """Ошибка пустого списка страниц: без неё проверка молча стала бы пустой."""
    return "узкие экраны: не найдено ни одной страницы сборки — проверять нечего"


def measure_state(page, script, drawer_open):
    """Находки замера check_layout.js в закрытом состоянии или с открытым меню."""
    return page.evaluate(script, drawer_open)


def measure_page(page, base_url, url, script):
    """Ошибки одной страницы на текущей ширине: закрыто и (если есть кнопка) меню."""
    width = page.viewport_size["width"]
    page.goto(base_url + url, wait_until="load")
    page.evaluate(REVEAL_ALL_SCRIPT)
    errors = narrow_errors(url, width, STATE_CLOSED, measure_state(page, script, False))
    if page.evaluate(IS_DRAWER_BUTTON_VISIBLE_SCRIPT):
        page.evaluate(OPEN_DRAWER_SCRIPT)
        errors += narrow_errors(url, width, STATE_MENU, measure_state(page, script, True))
    return errors


def measure_language_at_width(browser, base_url, pages, language, width, script):
    """Один контекст на пару «язык × ширина»: одна вкладка обходит все страницы языка."""
    context = new_context(browser, base_url, language, width, reduced_motion="reduce")
    page = context.new_page()
    errors = []
    for url in pages_of_language(pages, language):
        errors += measure_page(page, base_url, url, script)
    context.close()
    return errors


def collect_narrow_errors(browser, base_url, pages):
    """Ошибки узких экранов по всем страницам, языкам и ширинам."""
    if not pages:
        return [no_pages_error()]
    script = MEASURE_FILE.read_text(encoding="utf-8")
    errors = []
    for width in NARROW_WIDTHS:
        for language in LANGUAGES:
            errors += measure_language_at_width(browser, base_url, pages, language, width, script)
    return errors


def collect_errors(pages):
    """Все ошибки: «Популярное» на главной и узкие экраны по всей сборке."""
    from playwright.sync_api import sync_playwright
    errors = []
    with serve_site() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=BROWSER_CHANNEL)
        try:
            for url, language in PAGES.items():
                page = open_page(browser, base_url, url, language)
                errors += measure_widths(page, url)
                page.context.close()
            errors += collect_narrow_errors(browser, base_url, pages)
        finally:
            browser.close()
    return errors


def main():
    pages = list_site_pages(SITE)
    errors = collect_errors(pages)
    print(f"«Популярное»: страниц {len(PAGES)}, ширин {len(WIDTHS)}")
    print(f"узкие экраны: страниц {len(pages)}, ширин {len(NARROW_WIDTHS)}, "
          f"состояний {len(STATES)}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("LAYOUT OK — текст карточек «Популярного» не наезжает на цену; "
          f"страницы сборки ({len(pages)}) на ширинах {NARROW_WIDTHS[0]}–{NARROW_WIDTHS[-1]} px "
          "помещаются в окно, закрытые и с открытым меню")


if __name__ == "__main__":
    main()
