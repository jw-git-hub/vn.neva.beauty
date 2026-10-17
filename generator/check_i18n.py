"""Проверка языков сайта во всех собранных страницах. Падает (exit 1) при нарушении.

Английская версия ломается тихо: страница открывается и выглядит правильно, а поисковик
видит лишний hreflang на закрытой странице, ссылка ведёт на несуществующий файл или в
русский раздел, а в разметку попала кириллица. Здесь это ловится по собранным файлам:
  - hreflang и canonical каждой страницы сверены с одной таблицей маршрутов, поэтому
    взаимность пар следует сама: обе страницы пары читают одни и те же адреса;
  - структура страницы (заголовки, вопросы FAQ, строки прайса, типы JSON-LD)
    одинакова на всех языках;
  - ссылки, картинки и манифест неосновных языков указывают на существующие файлы,
    а ссылки на страницы — внутрь своего языка;
  - в неосновных языках нет кириллицы вне элементов с чужим lang;
  - sitemap содержит canonical каждой собранной страницы без noindex, без повторов и
    без лишнего; ожидаемый список берётся из самих страниц, а не из функции сборки sitemap;
  - у каждой страницы языка есть собранный файл, а под префиксом языка нет страниц,
    которых таблица маршрутов не знает (остались от прежнего адреса).
Запуск: python generator/check_i18n.py"""
import copy
import json
import re
import sys
import urllib.parse
from collections import Counter, namedtuple

from bs4 import BeautifulSoup

import build
import check_contacts
import taxonomy
from routes import INDEX_FILE, Routes

SITE = check_contacts.SITE
SITEMAP_FILE = "sitemap.xml"
X_DEFAULT = "x-default"
NOINDEX_TOKEN = "noindex"
HTML_EXTENSION = ".html"
# Селекторы строк прайса — те же, что в check_prices.py: позиции панелей и комбо.
PRICE_ROW_SELECTOR = ".pricelist__panel .pricelist__row, .pricelist__panel .combo"
JSON_LD_SELECTOR = 'script[type="application/ld+json"]'
# Всё, что тянется с адреса: ссылки, подключения, картинки, карточка превью.
ADDRESSED_SELECTOR = "a[href], link[href], img[src], meta[property='og:image'][content]"
ADDRESS_ATTRIBUTES = ("href", "src", "content")
# Кириллица буквой или записью \\uXXXX (так |tojson пишет её в скриптах): блок U+0400–U+045F.
CYRILLIC_PATTERN = r"(?:[А-Яа-яЁё]|\\u04[0-5][0-9a-fA-F])"
# Фрагмент вокруг кириллицы: 20 знаков до буквы, сама буква и 39 после — всего до 60.
FRAGMENT_RE = re.compile(r"[^\n]{0,20}" + CYRILLIC_PATTERN + r"[^\n]{0,39}")
FRAGMENT_LENGTH = 60
FRAGMENT_LIMIT = 3
FRAGMENT_SEPARATOR = " | "
SITEMAP_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")

# Всё, что проверкам страницы нужно знать о сайте.
Setup = namedtuple("Setup", "routes base_url base_path")
Signature = namedtuple("Signature", "headings faq_questions price_rows json_ld_types")
# Итог обхода страниц: ошибки, отпечатки {страница: {язык: Signature}}, число прочитанных
# страниц и адреса, которые обязаны быть в sitemap.
PageReport = namedtuple("PageReport", "errors signatures checked indexable_urls")
SIGNATURE_LABELS = {"headings": "уровни заголовков", "faq_questions": "вопросов FAQ",
                    "price_rows": "строк прайса", "json_ld_types": "типы JSON-LD"}


def is_noindex(soup):
    """Страница закрыта от индексации своим meta robots, а не списком в проверке."""
    robots = soup.find("meta", attrs={"name": "robots"})
    return bool(robots) and NOINDEX_TOKEN in robots.get("content", "").lower()


def alternate_pairs(soup):
    """Все (hreflang, href) страницы; повтор остаётся повтором."""
    return [(link["hreflang"], link.get("href", ""))
            for link in soup.select("link[rel~=alternate][hreflang]")]


def expected_alternates(page_id, routes):
    pairs = [(locale.html_lang, routes.url(locale, page_id)) for locale in routes.locales]
    return pairs + [(X_DEFAULT, routes.x_default(page_id))]


def hreflang_errors(soup, page_id, locale, routes, noindex):
    """Индексируемая страница: свой canonical и полный набор hreflang со всеми языками
    и x-default. Закрытая от индексации: ни одного hreflang."""
    found = alternate_pairs(soup)
    if noindex:
        return [f"{page_id} [{locale.code}]: hreflang на странице noindex: {found}"] if found else []
    return canonical_errors(soup, page_id, locale, routes) \
        + alternate_errors(found, page_id, locale, routes)


def canonical_errors(soup, page_id, locale, routes):
    canonical = soup.find("link", rel="canonical")
    actual = canonical.get("href") if canonical else None
    expected = routes.url(locale, page_id)
    if actual == expected:
        return []
    return [f"{page_id} [{locale.code}]: canonical {actual!r}, ожидался {expected!r}"]


def alternate_errors(found, page_id, locale, routes):
    expected = sorted(expected_alternates(page_id, routes))
    if sorted(found) == expected:
        return []
    return [f"{page_id} [{locale.code}]: hreflang {sorted(found)}, ожидались {expected}"]


def json_ld_nodes(soup):
    """Узлы JSON-LD страницы: из @graph, из списка или сам объект."""
    nodes = []
    for script in soup.select(JSON_LD_SELECTOR):
        data = json.loads(script.string or "null")
        nodes += data.get("@graph", [data]) if isinstance(data, dict) else list(data or [])
    return nodes


def count_type(data, type_name):
    """Сколько узлов указанного @type во вложенной структуре."""
    if isinstance(data, dict):
        own = 1 if data.get("@type") == type_name else 0
        return own + sum(count_type(value, type_name) for value in data.values())
    if isinstance(data, list):
        return sum(count_type(item, type_name) for item in data)
    return 0


def node_type_name(node):
    node_type = node.get("@type", "")
    return "+".join(sorted(node_type)) if isinstance(node_type, list) else str(node_type)


def signature(soup):
    """Отпечаток структуры страницы: он обязан совпасть на всех языках."""
    nodes = json_ld_nodes(soup)
    headings = tuple(int(tag.name[1]) for tag in soup.find_all(re.compile(r"^h[1-6]$")))
    return Signature(headings=headings,
                     faq_questions=count_type(nodes, "Question"),
                     price_rows=len(soup.select(PRICE_ROW_SELECTOR)),
                     json_ld_types=tuple(sorted(node_type_name(node) for node in nodes)))


def signature_errors(page_id, signatures, main_code):
    """Отпечаток страницы каждого языка против основного. signatures: {код языка: Signature}."""
    if main_code not in signatures:
        return []
    main = signatures[main_code]
    errors = []
    for code, current in signatures.items():
        for field in Signature._fields:
            if getattr(current, field) != getattr(main, field):
                errors.append(f"{page_id} [{code}]: {SIGNATURE_LABELS[field]} "
                              f"{getattr(current, field)}, у {main_code}: {getattr(main, field)}")
    return errors


def site_path(address, base_url, base_path):
    """Путь внутри сайта (без base_path, запроса и якоря) или None для чужих адресов."""
    address = address.strip()
    if address.startswith(base_url):
        address = address[len(base_url):] or "/"
    if not address.startswith("/") or address.startswith("//"):
        return None
    path = urllib.parse.unquote(urllib.parse.urlsplit(address).path)
    if base_path and (path == base_path or path.startswith(base_path + "/")):
        path = path[len(base_path):] or "/"
    return path


def is_page_path(path):
    """Каталог или .html — страница; файл с другим расширением (css, jpg, xml) — нет."""
    last = path.rstrip("/").rsplit("/", 1)[-1]
    return path.endswith("/") or path.endswith(HTML_EXTENSION) or "." not in last


def file_exists(site_dir, path):
    target = site_dir / path.lstrip("/")
    return (target / INDEX_FILE).is_file() if target.is_dir() else target.is_file()


def is_language_switch(tag, locale):
    """Ссылка с hreflang чужого языка (переключатель, Самуи) уходит из языка намеренно."""
    return tag.name == "a" and tag.get("hreflang") not in (None, locale.html_lang)


def link_problem(tag, path, locale, site_dir):
    if not file_exists(site_dir, path):
        return f"нет файла {path}"
    prefix = locale.url_prefix + "/"
    if tag.name == "a" and is_page_path(path) and not is_language_switch(tag, locale) \
            and not (path + "/").startswith(prefix):
        return f"ссылка {path} ведёт за пределы {prefix}"
    return None


def link_errors(soup, page_name, locale, main_locale, site_dir, base_url, base_path=""):
    """Ссылки, подключения и картинки неосновного языка: файл существует, страница
    лежит под префиксом языка. Основной язык этой проверкой не охватывается."""
    if locale.code == main_locale.code:
        return []
    errors = []
    for tag in soup.select(ADDRESSED_SELECTOR):
        address = next(tag[name] for name in ADDRESS_ATTRIBUTES if tag.has_attr(name))
        path = site_path(address, base_url, base_path)
        problem = link_problem(tag, path, locale, site_dir) if path is not None else None
        if problem:
            errors.append(f"{page_name}: <{tag.name}> {address!r}: {problem}")
    return errors


def primary_language(lang):
    """Основной подтег языка: «en-GB» и «EN» дают «en»."""
    return (lang or "").split("-")[0].lower()


def without_foreign_language(soup):
    """Копия страницы без элементов с чужим языком; en-GB на английской странице
    остаётся — проверяется только основной подтег."""
    page_language = primary_language(soup.html.get("lang") if soup.html else None)
    copied = copy.copy(soup)
    for element in copied.find_all(lang=True):
        if not element.decomposed and primary_language(element.get("lang")) != page_language:
            element.decompose()
    return copied


def cyrillic_errors(soup, page_name):
    """Кириллица в разметке неосновного языка: текст, атрибуты, скрипты, JSON-LD."""
    html = str(without_foreign_language(soup))
    fragments = [match.group().strip() for match in FRAGMENT_RE.finditer(html)]
    if not fragments:
        return []
    shown = FRAGMENT_SEPARATOR.join(fragments[:FRAGMENT_LIMIT])
    return [f"{page_name}: кириллица ({len(fragments)} мест): {shown}"]


def sitemap_errors(sitemap_text, expected_urls):
    """<loc> sitemap равны ожидаемым адресам без повторов."""
    found = Counter(SITEMAP_LOC_RE.findall(sitemap_text))
    errors = [f"sitemap: нет адреса {url}" for url in expected_urls if url not in found]
    errors += [f"sitemap: лишний адрес {url}" for url in found if url not in expected_urls]
    errors += [f"sitemap: адрес {url} повторён {count} раз"
               for url, count in found.items() if count > 1]
    return errors


def indexable_urls_of(soup):
    """canonical страницы, если она открыта для индексации; иначе пусто. Список — чтобы
    складывать результаты страниц."""
    canonical = soup.find("link", rel="canonical")
    if is_noindex(soup) or not canonical or not canonical.get("href"):
        return []
    return [canonical["href"]]


def page_errors(soup, name, page_id, locale, setup):
    """Проверки одной страницы, не требующие сравнения с другими языками."""
    errors = hreflang_errors(soup, page_id, locale, setup.routes, is_noindex(soup))
    main_locale = setup.routes.locales[0]
    errors += link_errors(soup, name, locale, main_locale, SITE, setup.base_url, setup.base_path)
    if locale.code != main_locale.code:
        errors += cyrillic_errors(soup, name)
    return errors


def stale_page_errors(site_dir, locales, expected_files):
    """Страницы под префиксом неосновного языка, которых нет среди ожидаемых файлов:
    после смены адреса старый файл остался бы в сборке. expected_files: {код языка: файлы}."""
    errors = []
    for locale in locales[1:]:
        for found in sorted((site_dir / locale.url_prefix.lstrip("/")).rglob("*" + HTML_EXTENSION)):
            if found not in expected_files.get(locale.code, set()):
                errors.append(f"лишняя страница: {found.relative_to(site_dir.parent)}")
    return errors


def check_pages(site, content, setup):
    """Обход всех ожидаемых страниц: PageReport. Нет файла пары — ошибка, а не сбой."""
    errors, signatures, urls, expected_files, checked = [], {}, [], {}, 0
    for locale, page_id, path in check_contacts.locale_pages(site, content, setup.routes.locales):
        expected_files.setdefault(locale.code, set()).add(path)
        shown = str(path.relative_to(SITE.parent))
        if not path.is_file():
            errors.append(f"нет пары: {shown}")
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        errors += page_errors(soup, shown, page_id, locale, setup)
        signatures.setdefault(page_id, {})[locale.code] = signature(soup)
        urls += indexable_urls_of(soup)
        checked += 1
    errors += stale_page_errors(SITE, setup.routes.locales, expected_files)
    return PageReport(errors, signatures, checked, urls)


def make_setup(site, content):
    base_path = site.get("base_path", "").rstrip("/")
    locales = build.load_locales(site)
    routes = Routes(locales, taxonomy.page_ids(content), site["base_url"],
                    build.load_x_default_locale(site), base_path)
    return Setup(routes, site["base_url"], base_path)


def main():
    site, content, _ = build.load()
    setup = make_setup(site, content)
    report = check_pages(site, content, setup)
    errors = list(report.errors)
    main_code = setup.routes.locales[0].code
    for page_id, by_locale in report.signatures.items():
        errors += signature_errors(page_id, by_locale, main_code)
    errors += sitemap_errors((SITE / SITEMAP_FILE).read_text(encoding="utf-8"),
                             report.indexable_urls)
    print(f"страниц проверено: {report.checked}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("I18N OK — пары языков, hreflang, ссылки и алфавит в порядке")


if __name__ == "__main__":
    main()
