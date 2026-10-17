import json, re, urllib.parse, yaml
from pathlib import Path
from markupsafe import Markup
from jinja2 import Environment, FileSystemLoader, select_autoescape
import contacts, images, language_redirect, language_switch, pages, sitewide, taxonomy, translation
from locales import load_locale, load_privacy, localized_site
from routes import Routes

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "vn.neva.beauty"
ICONS = OUT / "assets" / "icons"

# Фон бренда (токен --bg из assets/css/tokens.css). Один источник для meta theme-color
# и для манифеста: браузер красит им адресную строку и заставку, и оба должны совпадать
# с реальным фоном страницы, иначе при запуске видна цветная вспышка.
THEME_COLOR = "#FBF4F0"

def icon(name, cls="icon"):
    svg = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    # Strip license comment, collapse multiline <svg ...> tag, replace class attribute
    svg = re.sub(r'<!--.*?-->\s*', '', svg, flags=re.DOTALL)
    svg = re.sub(r'<svg\s+', '<svg ', svg, count=1)
    svg = re.sub(r'<svg ([^>]*?)class="[^"]*"', f'<svg class="{cls}"', svg, count=1)
    return Markup(svg)

def load():
    site = yaml.safe_load((ROOT/"data/site.yml").read_text(encoding="utf-8"))
    content = yaml.safe_load((ROOT/"data/content.yml").read_text(encoding="utf-8"))
    prices = json.loads((ROOT/"data/prices.json").read_text(encoding="utf-8"))
    return site, content, prices

def load_locales(site):
    """Языки сайта в порядке site.yml; первый — основной. Список обязателен: молчаливое
    значение по умолчанию спрятало бы опечатку и расходилось бы с check_prices.py."""
    codes = site.get("locales")
    if not codes:
        raise ValueError("В site.yml не задан список языков locales (первый — основной)")
    return [load_locale(code) for code in codes]

def load_x_default_locale(site):
    """Язык для hreflang="x-default". Обязателен по той же причине, что и locales."""
    code = site.get("x_default_locale")
    if not code:
        raise ValueError("В site.yml не задан x_default_locale (язык для hreflang x-default)")
    return code

def write(path: Path, html: str) -> bool:
    """Пишет файл и возвращает True, если содержимое изменилось (нужно для lastmod в sitemap)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    changed = not path.exists() or path.read_text(encoding="utf-8") != html
    path.write_text(html, encoding="utf-8")
    print("→", path.relative_to(OUT.parent))
    return changed

def make_env(locale, routes, base_path, site):
    """Окружение Jinja одного языка: строки интерфейса и адреса берутся из языка."""
    e = Environment(loader=FileSystemLoader(ROOT/"templates"),
                    autoescape=select_autoescape(["html","j2"]))
    e.globals.update(
        icon=icon, theme_color=THEME_COLOR, base_path=base_path, locale=locale,
        t=locale.t, href=lambda page_id: routes.href(locale, page_id),
        language_links=lambda page: language_switch.language_links(routes, locale, page["id"]),
        language_redirect_config=lambda page: language_redirect.config(site, routes, locale, page["id"]),
        language_source_key=language_redirect.SOURCE_KEY,
        # Ссылка связи: адрес с текстом страницы и метки канала и места (contacts.py).
        contact=lambda channel, place, page: contacts.link_attrs(
            site["contacts"], channel, place,
            contacts.contact_message(locale, page.get("contact_title"))),
        alternates=routes.alternates, x_default=routes.x_default,
        # og:locale других языков для og:locale:alternate — в порядке таблицы маршрутов.
        alternate_og_locales=[other.og_locale for other in routes.locales
                              if other.code != locale.code],
        # Адаптивные картинки: ширины, sizes и пропорции берутся из images.py — оттуда же
        # make_images.py режет производные, поэтому разметка и файлы не разъезжаются.
        srcset=lambda stem, slot: images.srcset(stem, slot, base_path),
        img_sizes=images.sizes, img_width=images.width, img_height=images.height,
        card_image=images.related_stem,
        asset=lambda path: sitewide.asset_url(OUT, base_path, path),
    )
    return e

def build_locale(site, content, prices, locale, routes, base_path, main_locale):
    """Собирает все страницы одного языка. Возвращает ({путь: изменилась ли страница},
    контент языка). Контент языка — копия мастера или мастер с накладкой перевода
    (translation.prepare): сборка подставляет в тексты цены и ссылки, и следующий язык
    должен получить исходник, а не раскрытые плейсхолдеры."""
    language = translation.prepare(site, content, prices, locale, main_locale)
    site = localized_site(site, locale)
    content = language.content
    taxonomy.enrich_categories(content, routes, locale)
    taxonomy.fill_related(content)
    site["nav"] = taxonomy.build_nav(content, routes, locale)
    ctx = pages.BuildContext(site, content, prices, language.prices, locale, routes,
                             make_env(locale, routes, base_path, site),
                             [item.html_lang for item in routes.locales])
    changed = {}
    for page_id, html in pages.build_all(ctx, load_privacy(locale.code)):
        changed[routes.path(locale, page_id)] = write(OUT / routes.out_file(locale, page_id), html)
    return changed, content

def write_sitewide(site, contents, prices, locales, routes, changed, urls, base_path):
    """Файлы уровня сайта: sitemap, llms.txt (раздел на каждый язык), манифест каждого языка."""
    sitemap_path = OUT/"sitemap.xml"
    known_lastmods = sitewide.previous_lastmods(sitemap_path)  # читаем до перезаписи
    write(sitemap_path, sitewide.build_sitemap(site["base_url"], urls, changed, known_lastmods))
    write(OUT/"llms.txt", sitewide.build_llms_file(site, contents, prices, locales, routes))
    for locale in locales:
        manifest = sitewide.build_manifest(localized_site(site, locale), base_path,
                                           THEME_COLOR, locale.url_prefix)
        write(OUT/locale.url_prefix.lstrip("/")/"site.webmanifest", manifest)
    # CNAME — боевой домен для GitHub Pages. Кладём в артефакт, иначе workflow-деплой
    # каждый раз сбрасывает кастомный домен в настройках Pages. Хост берём из base_url.
    write(OUT/"CNAME", urllib.parse.urlsplit(site["base_url"]).netloc + "\n")

def main():
    site, content, prices = load()
    # Префикс пути для ссылок на ассеты/страницы: пусто на боевом домене (сайт в корне),
    # "/vn.neva.beauty" для превью на GitHub Pages по подпути проекта. SEO-URL не трогает.
    base_path = site.get("base_path", "").rstrip("/")
    locales = load_locales(site)
    routes = Routes(locales, taxonomy.page_ids(content), site["base_url"],
                    load_x_default_locale(site), base_path)
    sitewide.build_css_bundle(OUT)  # до страниц: отпечаток бандла стоит в каждой
    changed, urls, contents = {}, [], {}
    for locale in locales:
        locale_changed, contents[locale.code] = build_locale(
            site, content, prices, locale, routes, base_path, locales[0])
        changed.update(locale_changed)
        urls += sitewide.sitemap_paths(contents[locale.code], routes, locale)
    write_sitewide(site, contents, prices, locales, routes, changed, urls, base_path)

if __name__ == "__main__":
    main()
