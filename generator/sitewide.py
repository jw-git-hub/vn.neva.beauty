"""Файлы уровня сайта: CSS-бандл, sitemap.xml, llms.txt, манифест."""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import rcssmin

import pricing
from locales import localized_site
from routes import HOME

# Порядок каскада для единого bundle.min.css. Все CSS сайта склеиваются в один
# минифицированный файл → один render-blocking запрос вместо шести, общий кэш на
# весь сайт. fonts первым (@font-face), затем токены/база, затем постраничные слои.
CSS_BUNDLE_ORDER = ["fonts", "tokens", "base", "components",
                    "aurora", "reveal", "home", "service", "legal"]


def build_css_bundle(out_dir):
    """Склеивает CSS-слои в порядке каскада и минифицирует в единый bundle.min.css.
    Один render-blocking запрос вместо шести; относительные url() внутри (../fonts,
    ../img) работают и на превью по подпути, и на боевом домене."""
    css_dir = out_dir / "assets" / "css"
    parts = [f.read_text(encoding="utf-8")
             for name in CSS_BUNDLE_ORDER
             if (f := css_dir / f"{name}.css").exists()]
    bundle = rcssmin.cssmin("\n".join(parts))
    out = css_dir / "bundle.min.css"
    out.write_text(bundle, encoding="utf-8")
    print("→", out.relative_to(out_dir.parent), f"({len(bundle) // 1024} KB minified)")


def asset_url(out_dir, base_path, path):
    """Ссылка на ассет с отпечатком содержимого: `?v=1a2b3c4d`.

    Имена файлов постоянные, поэтому без отпечатка вернувшийся посетитель после
    деплоя получает из кэша старый CSS. Отпечаток меняется вместе с файлом
    и заставляет браузер скачать новую версию."""
    digest = hashlib.sha1((out_dir / path.lstrip("/")).read_bytes()).hexdigest()[:8]
    return f"{base_path}{path}?v={digest}"


def sitemap_paths(content, routes, locale):
    """Индексируемые страницы языка в порядке sitemap: главная, услуги, разделы.
    Политика и 404 закрыты от индексации и в sitemap не идут."""
    services = [routes.path(locale, service_id) for service_id in content["services"]]
    categories = [routes.path(locale, cat["page_id"])
                  for cat in content["categories"] if cat["is_page"]]
    return [routes.path(locale, HOME)] + services + categories


def previous_lastmods(path: Path) -> dict:
    """Достаёт lastmod из уже собранного sitemap: даты неизменившихся страниц переживают сборку."""
    if not path.exists():
        return {}
    pairs = re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>",
                       path.read_text(encoding="utf-8"))
    return dict(pairs)


def build_sitemap(base_url: str, urls: list, changed: dict, known: dict) -> str:
    """Собирает sitemap, обновляя lastmod только у реально изменившихся страниц.
    Иначе любая сборка (правка CSS, пересборка на CI) сообщала бы поисковикам о правке
    всего сайта и обесценивала сигнал lastmod."""
    today = date.today().isoformat()
    rows = []
    for url in urls:
        loc = base_url + url
        lastmod = today if changed.get(url, True) else known.get(loc, today)
        rows.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def _llms_about_lines(site, t):
    """Факты о центре для llms.txt — ровно те, что опубликованы на сайте.
    Точного адреса среди них нет: заказчик даёт его при записи."""
    return [t("llms.city", location=site["location"]), t("llms.booking"),
            t("llms.languages"), t("llms.currency", currency=site["business"]["currency"])]


def _llms_service_lines(content, prices, locale, routes):
    """Услуги для llms.txt: ссылка, краткое описание страницы и цена из прайса.
    Без описания и цены ассистенту приходится открывать все страницы, чтобы
    ответить «сколько стоит» — а карта сайта нужна как раз чтобы не пришлось."""
    lines = []
    for service_id, svc in content["services"].items():
        hint = pricing.price_hint(prices.get(service_id, []), locale.format_from)
        price = locale.t("llms.price", price=hint) if hint else ""
        lines.append(f"- [{svc['title']}]({routes.url(locale, service_id)}): {svc['seo_desc']}{price}")
    return lines


def build_llms(site, content, prices, locale, routes):
    """llms.txt — краткая карта сайта для ИИ-ассистентов (llmstxt.org)."""
    contacts, t = site["contacts"], locale.t
    lines = [t("llms.heading", brand=site["brand"]), "", t("llms.summary"), "", t("llms.about_title")]
    lines += _llms_about_lines(site, t)
    lines += ["", t("llms.categories_title")]
    lines += [f"- [{cat['title']}]({routes.url(locale, cat['page_id'])})"
              for cat in content["categories"]]
    lines += ["", t("llms.services_title")]
    lines += _llms_service_lines(content, prices, locale, routes)
    lines += ["", t("llms.contacts_title"),
              f"- WhatsApp: {contacts['whatsapp_url']}",
              f"- Telegram: {contacts['telegram_url']}",
              f"- Instagram: {contacts['instagram_url']}", ""]
    return "\n".join(lines)


def build_llms_file(site, contents, prices, locales, routes):
    """Весь llms.txt: блоки языков в порядке site.locales, основной язык первым.
    Блок кончается переводом строки, поэтому склейка даёт пустую строку между блоками
    и русская часть остаётся прежней байт в байт."""
    return "\n".join(
        build_llms(localized_site(site, locale), contents[locale.code], prices, locale, routes)
        for locale in locales)


def build_manifest(site, base_path, theme_color, url_prefix=""):
    """site.webmanifest — имя и иконка для «добавить на главный экран» на Android.
    Собирается, а не лежит статикой: пути внутри должны учитывать base_path, иначе
    на превью по подпути GitHub Pages манифест уводит на несуществующие иконки.
    purpose «any maskable» — одна иконка и как есть, и под маску адаптивных иконок:
    лотос занимает ~55 % кадра и не обрезается ни одной формой маски.
    url_prefix — префикс языка: манифест языка стартует с его главной (`/en/`), а
    иконки общие на весь сайт и лежат в корне."""
    icons = [{"src": f"{base_path}/icon-{size}.png", "sizes": f"{size}x{size}",
              "type": "image/png", "purpose": "any maskable"} for size in (192, 512)]
    manifest = {
        "name": f"{site['brand']} — {site['tagline']}",
        "short_name": site["brand"],
        "start_url": f"{base_path}{url_prefix}/",
        "display": "standalone",
        "background_color": theme_color,
        "theme_color": theme_color,
        "icons": icons,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
