import json, re, urllib.parse, yaml, rcssmin
from datetime import date
from pathlib import Path
from markupsafe import Markup
from jinja2 import Environment, FileSystemLoader, select_autoescape
import schema

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "vn.neva.beauty"
ICONS = OUT / "assets" / "icons"

RELATED_COUNT = 3  # сколько карточек «Смотрите также» показываем на странице услуги

# Порядок каскада для единого bundle.min.css. Все CSS сайта склеиваются в один
# минифицированный файл → один render-blocking запрос вместо шести, общий кэш на
# весь сайт. fonts первым (@font-face), затем токены/база, затем постраничные слои.
CSS_BUNDLE_ORDER = ["fonts", "tokens", "base", "components",
                    "aurora", "reveal", "home", "service", "legal"]

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

def env():
    e = Environment(loader=FileSystemLoader(ROOT/"templates"),
                    autoescape=select_autoescape(["html","j2"]))
    e.filters["urlencode"] = lambda s: urllib.parse.quote(str(s))
    e.tests["match"] = lambda s, pat: re.match(pat, s) is not None
    e.globals["icon"] = icon
    return e

def write(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("→", path.relative_to(OUT.parent))

def build_css_bundle():
    """Склеивает CSS-слои в порядке каскада и минифицирует в единый bundle.min.css.
    Один render-blocking запрос вместо шести; относительные url() внутри (../fonts,
    ../img) работают и на превью по подпути, и на боевом домене."""
    css_dir = OUT / "assets" / "css"
    parts = [f.read_text(encoding="utf-8")
             for name in CSS_BUNDLE_ORDER
             if (f := css_dir / f"{name}.css").exists()]
    bundle = rcssmin.cssmin("\n".join(parts))
    out = css_dir / "bundle.min.css"
    out.write_text(bundle, encoding="utf-8")
    print("→", out.relative_to(OUT.parent), f"({len(bundle) // 1024} KB minified)")

def enrich_categories(content):
    """Обогащает категории (url, is_page) и переопределяет svc.category — единая таксономия."""
    categories = content["categories"]
    category_title_by_slug = {}
    for cat in categories:
        cat["is_page"] = len(cat["services"]) > 1
        cat["url"] = f"/{cat['slug']}/" if cat["is_page"] else f"/{cat['services'][0]}/"
        for svc_slug in cat["services"]:
            category_title_by_slug[svc_slug] = cat["title"]
    for slug, svc in content["services"].items():
        svc["category"] = category_title_by_slug[slug]

def fill_related(content):
    """Гарантирует ровно RELATED_COUNT связанных услуг: кураторский список,
    затем соседи по категории, затем прочие услуги — чтобы блок «Смотрите также»
    никогда не был короче остальных страниц."""
    services = content["services"]
    siblings_by_slug = {
        slug: [s for s in cat["services"] if s != slug]
        for cat in content["categories"] for slug in cat["services"]
    }
    for slug, svc in services.items():
        related = [r for r in dict.fromkeys(svc.get("related", [])) if r != slug and r in services]
        for pool in (siblings_by_slug.get(slug, []), services):
            for candidate in pool:
                if len(related) >= RELATED_COUNT:
                    break
                if candidate != slug and candidate not in related:
                    related.append(candidate)
        svc["related"] = related[:RELATED_COUNT]

def render_faq_contacts(faq, contacts, base_path=""):
    """Финализирует HTML-ответы FAQ: подставляет URL мессенджеров вместо плейсхолдеров
    {whatsapp}/{telegram}/{instagram} (единый источник — site.yml) и префиксует внутренние
    ссылки href="/..." на base_path — чтобы они работали и на превью по подпути."""
    tokens = {
        "{whatsapp}": contacts["whatsapp_url"],
        "{telegram}": contacts["telegram_url"],
        "{instagram}": contacts["instagram_url"],
    }
    result = []
    for item in faq:
        answer = item["a"]
        for token, url in tokens.items():
            answer = answer.replace(token, url)
        if base_path:
            answer = answer.replace('href="/', f'href="{base_path}/')
        result.append({"q": item["q"], "a": answer})
    return result


ADDON_MARK = "+"  # «+350 000 đ» — надбавка к процедуре, а не её самостоятельная цена
PRICE_RE = re.compile(r"^\+?\d[\d ]*đ$")  # единственная допустимая форма записи цены


def price_value(price):
    """Цена строкой из прайса → число («1 500 000 đ» → 1500000).
    Пустая цена — None (позиция без цены). Любая другая форма — ошибка сборки:
    просто вырезать цифры нельзя, иначе «1 000 000 – 2 000 000 đ» молча уедет
    в разметку как 10000002000000."""
    text = price.strip()
    if not text:
        return None
    if not PRICE_RE.match(text):
        raise ValueError(f"Непонятная цена в prices.json: {price!r}. Допустимые формы — "
                         f"«1 500 000 đ», «+350 000 đ» или пустая строка.")
    return int(re.sub(r"[^\d]", "", text))


def is_addon(item):
    return item["price"].strip().startswith(ADDON_MARK)


def price_aggregate(sections, currency):
    """Диапазон цен услуги (min/max/кол-во) для AggregateOffer — из строк прайса.
    Доплаты в диапазон не входят: иначе lowPrice занижает «услуги от» до надбавки,
    которую нельзя купить отдельно. Возвращает None, если цен нет."""
    values = [value for sec in sections for item in sec["items"]
              if not is_addon(item) and (value := price_value(item["price"])) is not None]
    if not values:
        return None
    return {"low": min(values), "high": max(values),
            "count": len(values), "currency": currency}


def popular_price(prices, slug, name):
    """Цена для карточки «Популярное» на главной. Одноимённые позиции есть в разных
    разделах прайса с разной ценой (эпиляция у женщин и мужчин) — тогда показываем
    «от <минимальной>»: молча взять первую значит показать мужчине женскую цену.
    Позиции нет в прайсе — ошибка сборки, иначе карточка уедет в прод без цены."""
    matches = [item["price"] for sec in prices.get(slug, []) for item in sec["items"]
               if item["name"] == name]
    if not matches:
        raise ValueError(f"«Популярное»: в прайсе {slug} нет позиции {name!r}")
    if len(set(matches)) == 1:
        return matches[0]
    return f"от {min(matches, key=price_value)}"


def offer_sections(sections):
    """Разделы прайса для JSON-LD: цена числом, название и описание — дословно.
    Позиции без цифр в цене пропускаем (нечего утверждать о цене)."""
    result = []
    for sec in sections:
        items = [{"name": item["name"], "desc": item.get("desc", ""), "price": value}
                 for item in sec["items"] if (value := price_value(item["price"])) is not None]
        if items:
            result.append({"title": sec.get("section") or "Цены", "items": items})
    return result


def build_llms(site, content):
    """llms.txt — краткая карта сайта для ИИ-ассистентов (llmstxt.org)."""
    base = site["base_url"]
    c = site["contacts"]
    lines = [
        f"# {site['brand']}",
        "",
        "> Центр красоты в Дананге (Вьетнам): аппаратная косметология, лазерная "
        "эпиляция, лифтинг и омоложение, уход за лицом и коррекция фигуры. "
        "Обслуживание на русском языке для русскоязычных клиентов.",
        "",
        "## Направления",
    ]
    for cat in content["categories"]:
        lines.append(f"- [{cat['title']}]({base}{cat['url']})")
    lines += ["", "## Услуги"]
    for slug, svc in content["services"].items():
        lines.append(f"- [{svc['title']}]({base}/{slug}/)")
    lines += [
        "",
        "## Контакты",
        f"- Локация: {site['location']}",
        f"- WhatsApp: {c['whatsapp_url']}",
        f"- Telegram: {c['telegram_url']}",
        f"- Instagram: {c['instagram_url']}",
        "",
    ]
    return "\n".join(lines)


def build_nav(categories, services):
    # label — короткая подпись для верхней панели, title — полное название для дровера/страниц
    nav = [{"label": "Главная", "title": "Главная", "url": "/"}]
    for cat in categories:
        item = {"label": cat.get("nav_label", cat["title"]), "title": cat["title"], "url": cat["url"]}
        if cat["is_page"]:
            item["children"] = [{"label": services[svc_slug]["title"], "slug": svc_slug} for svc_slug in cat["services"]]
        nav.append(item)
    return nav

def main():
    site, content, prices = load()
    e = env()
    # Префикс пути для ссылок на ассеты/страницы: пусто на боевом домене (сайт в корне),
    # "/vn.neva.beauty" для превью на GitHub Pages по подпути проекта. SEO-URL (base_url) не трогает.
    base_path = site.get("base_path", "").rstrip("/")
    e.globals["base_path"] = base_path
    build_css_bundle()  # единый минифицированный bundle.min.css
    enrich_categories(content)
    fill_related(content)
    site["nav"] = build_nav(content["categories"], content["services"])
    base_schema = schema.render(site)  # общий граф бизнеса — на всех страницах
    # главная
    home_faq = content["home"].get("faq", [])
    if home_faq:
        home_faq = render_faq_contacts(home_faq, site["contacts"], base_path)
        content["home"]["faq"] = home_faq
        home_schema = schema.render(site, [schema.faq_node(home_faq)])
    else:
        home_schema = base_schema
    for item in content["home"].get("popular", []):
        item["price"] = popular_price(prices, item["slug"], item["name"])
    page = {"url":"/", "seo_title": content["home"].get("seo_title","Neva Beauty — центр красоты в Дананге"),
            "seo_desc": content["home"].get("seo_desc",""), "schema_json": home_schema,
            "hero_image": "/assets/img/hero.webp"}  # LCP-элемент → preload в base.html.j2
    write(OUT/"index.html", e.get_template("home.html.j2").render(
        site=site, page=page, home=content["home"], categories=content["categories"]))
    # услуги
    tpl = e.get_template("service.html.j2")
    base_url = site["base_url"]
    provider_ref = {"@id": base_url + "/" + schema.BUSINESS_ID}
    area_name = site["business"]["address"]["locality"]
    currency = site["business"].get("currency")
    category_by_slug = {slug: cat for cat in content["categories"] for slug in cat["services"]}
    for slug, svc in content["services"].items():
        sections = prices.get(slug, [])
        cat = category_by_slug[slug]
        crumbs = [{"name": "Главная", "url": base_url + "/"}]
        if cat["is_page"]:
            crumbs.append({"name": cat["title"], "url": base_url + cat["url"]})
        crumbs.append({"name": svc["title"], "url": base_url + f"/{slug}/"})
        offers = offer_sections(sections)
        catalog = (schema.offer_catalog_node(f"{svc['title']} — цены", offers, currency)
                   if offers else None)
        nodes = [
            schema.breadcrumb_node(crumbs),
            schema.service_node(svc["title"], svc["intro"], provider_ref, area_name,
                                price_aggregate(sections, currency), catalog),
        ]
        if svc.get("faq"):
            svc["faq"] = render_faq_contacts(svc["faq"], site["contacts"], base_path)
            nodes.append(schema.faq_node(svc["faq"]))
        page = {"url": f"/{slug}/", "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"],
                "schema_json": schema.render(site, nodes),
                "hero_image": f"/assets/img/{svc['hero_image']}.webp"}  # LCP → preload
        write(OUT/slug/"index.html", tpl.render(
            site=site, page=page, svc=svc, slug=slug, category=cat,
            sections=sections, services=content["services"]))
    # категории (только группы с несколькими услугами)
    cat_tpl = e.get_template("category.html.j2")
    for cat in content["categories"]:
        if not cat["is_page"]:
            continue
        nodes = [
            schema.breadcrumb_node([
                {"name": "Главная", "url": base_url + "/"},
                {"name": cat["title"], "url": base_url + cat["url"]},
            ]),
            schema.item_list_node(cat["title"], [f"{base_url}/{slug}/" for slug in cat["services"]]),
        ]
        if cat.get("faq"):
            cat["faq"] = render_faq_contacts(cat["faq"], site["contacts"], base_path)
            nodes.append(schema.faq_node(cat["faq"]))
        page = {"url": cat["url"], "seo_title": cat["seo_title"], "seo_desc": cat["seo_desc"],
                "schema_json": schema.render(site, nodes)}
        write(OUT/cat["slug"]/"index.html", cat_tpl.render(
            site=site, page=page, cat=cat, services=content["services"]))
    # privacy (служебная — не индексируем)
    page = {"url":"/privacy/", "seo_title":"Политика конфиденциальности — Neva Beauty", "seo_desc":"",
            "schema_json": base_schema, "noindex": True}
    write(OUT/"privacy"/"index.html", e.get_template("privacy.html.j2").render(site=site, page=page))
    # 404 (служебная — не индексируем)
    page = {"url": "/404.html", "seo_title": "Страница не найдена — Neva Beauty", "seo_desc": "",
            "schema_json": base_schema, "noindex": True}
    write(OUT/"404.html", e.get_template("404.html.j2").render(site=site, page=page))
    # sitemap
    cat_urls = [cat["url"] for cat in content["categories"] if cat["is_page"]]
    # /privacy/ и /404.html — noindex, в sitemap не включаем
    urls = ["/"] + [f"/{slug}/" for slug in content["services"]] + cat_urls
    today = date.today().isoformat()
    rows = "\n".join(f'  <url><loc>https://vn.neva.beauty{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '\n</urlset>\n'
    write(OUT/"sitemap.xml", sitemap)
    # llms.txt — карта сайта для ИИ-ассистентов
    write(OUT/"llms.txt", build_llms(site, content))
    # CNAME — боевой домен для GitHub Pages. Кладём в артефакт, иначе workflow-деплой
    # каждый раз сбрасывает кастомный домен в настройках Pages. Хост берём из base_url.
    write(OUT/"CNAME", urllib.parse.urlsplit(base_url).netloc + "\n")

if __name__ == "__main__":
    main()
