import json, re, urllib.parse, yaml
from datetime import date
from pathlib import Path
from markupsafe import Markup
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "vn.neva.beauty"
ICONS = OUT / "assets" / "icons"

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

def main():
    site, content, prices = load()
    e = env()
    # главная
    page = {"url":"/", "seo_title": content["home"].get("seo_title","Neva Beauty — центр красоты в Дананге"),
            "seo_desc": content["home"].get("seo_desc","")}
    write(OUT/"index.html", e.get_template("home.html.j2").render(
        site=site, page=page, home=content["home"], prices=prices))
    # услуги
    tpl = e.get_template("service.html.j2")
    for slug, svc in content["services"].items():
        page = {"url": f"/{slug}/", "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"]}
        write(OUT/slug/"index.html", tpl.render(
            site=site, page=page, svc=svc, slug=slug,
            sections=prices.get(slug, []), services=content["services"]))
    # privacy
    page = {"url":"/privacy/", "seo_title":"Политика конфиденциальности — Neva Beauty", "seo_desc":""}
    write(OUT/"privacy"/"index.html", e.get_template("privacy.html.j2").render(site=site, page=page))
    # 404
    page = {"url": "/404.html", "seo_title": "Страница не найдена — Neva Beauty", "seo_desc": ""}
    write(OUT/"404.html", e.get_template("404.html.j2").render(site=site, page=page))
    # sitemap
    urls = ["/"] + [f"/{slug}/" for slug in content["services"]] + ["/privacy/"]
    today = date.today().isoformat()
    rows = "\n".join(f'  <url><loc>https://vn.neva.beauty{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '\n</urlset>\n'
    write(OUT/"sitemap.xml", sitemap)

if __name__ == "__main__":
    main()
