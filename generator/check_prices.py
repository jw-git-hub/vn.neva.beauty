"""Парити-тест цен: сверяет data/prices.json (источник истины) с ценами в
сгенерированном HTML (прайс-лист, карточки «Популярное», сравнительные таблицы)
и в JSON-LD (OfferCatalog + AggregateOffer). Падает (exit 1)
при любом расхождении — защищает требование 100% точности цен.
Сверяются не только цифры, но и раздел прайса, описание позиции и валюта:
в прайсе есть одноимённые позиции с разными ценами («Лоб» у женщин и мужчин),
поэтому позиция, уехавшая в соседний раздел, — такая же ошибка, как неверная цена.
Запуск: cd generator && ../.venv/bin/python check_prices.py"""
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
NEW = ROOT.parent / "vn.neva.beauty"
PRICES = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
CONTENT = yaml.safe_load((ROOT / "data" / "content.yml").read_text(encoding="utf-8"))
SITE = yaml.safe_load((ROOT / "data" / "site.yml").read_text(encoding="utf-8"))
CURRENCY = SITE["business"].get("currency")
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
PRICE_RE = re.compile(r"^\+?\d[\d ]*đ$")
LOCALE_CODES = SITE.get("locales", ["ru"])
HOME_FILE = "index.html"


class LocaleView:
    """То, что тесту нужно знать о языке: где лежат страницы и как на них
    пишутся «от …» и название раздела по умолчанию. Читается из файла языка
    напрямую, без модулей сборки."""

    def __init__(self, code):
        data = yaml.safe_load((ROOT / "data" / "locales" / f"{code}.yml").read_text(encoding="utf-8"))
        self.code = code
        self.prefix = data["url_prefix"].strip("/")
        self.slugs = data.get("slugs") or {}
        self.from_template = data["ui"]["price"]["from"]
        self.default_section = data["ui"]["service"]["price_section_default"]

    def page_file(self, slug=None):
        parts = [self.prefix] if self.prefix else []
        if slug:
            parts.append(self.slugs.get(slug, slug))
        return NEW.joinpath(*parts, HOME_FILE)

    def format_from(self, price):
        return self.from_template.format(price=price)


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


# price_number и is_addon — НАМЕРЕННАЯ копия логики build.py, а не импорт из неё.
# Тест обязан считать эталон независимо от проверяемого кода: с импортом любая ошибка
# разбора цены сойдётся сама с собой и тест останется зелёным. Не «устранять дублирование».

def price_number(price):
    """«1 500 000 đ» → 1500000. Пустая цена — None, любая другая форма — ошибка."""
    text = price.strip()
    if not text:
        return None
    if not PRICE_RE.match(text):
        raise ValueError(f"Непонятная цена в prices.json: {price!r}")
    return int(re.sub(r"[^\d]", "", text))


def is_addon(item):
    """Не самостоятельная цена услуги: надбавка «+350 000 đ» или помеченный
    флагом addon сопутствующий товар вроде костюма для LPG. В AggregateOffer
    и в OfferCatalog такие позиции не идут — в таблице прайса остаются."""
    return bool(item.get("addon")) or item["price"].strip().startswith("+")


def price_hint(sections, view):
    """Цена услуги одной строкой: точная, если в прайсе она одна, иначе «от <минимальной>».
    Так цена услуги показывается вне прайс-листа — в сравнительной таблице."""
    values = [clean(it["price"]) for sec in sections for it in sec["items"]
              if not is_addon(it) and price_number(it["price"]) is not None]
    if not values:
        return None
    return values[0] if len(set(values)) == 1 else view.format_from(min(values, key=price_number))


@lru_cache(maxsize=None)
def page_html(view, slug):
    return view.page_file(slug).read_text(encoding="utf-8")


def service_node(view, slug):
    """Узел Service из JSON-LD страницы услуги."""
    graph = json.loads(JSON_LD_RE.search(page_html(view, slug)).group(1))["@graph"]
    node = next((n for n in graph if n.get("@type") == "Service"), None)
    if node is None:
        sys.exit(f"В JSON-LD страницы {slug} нет узла Service")
    return node


def priced_sections(sections, view):
    """Разделы прайса с позициями, у которых есть цена: [(название, [(имя, описание,
    цена-числом, цена-строкой)])] в порядке из prices.json."""
    result = []
    for sec in sections:
        items = [(clean(it["name"]), clean(it.get("desc", "")), value, clean(it["price"]))
                 for it in sec["items"] if (value := price_number(it["price"])) is not None]
        if items:
            result.append((clean(sec.get("section") or view.default_section), items))
    return result


def catalog_offers(catalog):
    """Offer'ы каталога с номером раздела: вложенные OfferCatalog — разделы прайса,
    плоский список — единственный раздел (номер 0)."""
    elements = catalog.get("itemListElement", [])
    nested = [el for el in elements if el.get("@type") == "OfferCatalog"]
    if nested and len(nested) != len(elements):
        sys.exit("OfferCatalog смешивает разделы и позиции — разбор неоднозначен")
    if nested:
        return [(i, offer) for i, sec in enumerate(nested)
                for offer in sec.get("itemListElement", [])]
    return [(0, offer) for offer in elements]


def catalog_section_titles(catalog):
    return [el.get("name") for el in catalog.get("itemListElement", [])
            if el.get("@type") == "OfferCatalog"]


def report(label, expected, actual):
    """Печатает расхождения двух Counter'ов. Возвращает True, если их нет."""
    ok = True
    for title, diff in ((f"MISSING в {label} (есть в prices.json, нет в разметке)", expected - actual),
                        (f"EXTRA в {label} (есть в разметке, нет в prices.json)", actual - expected)):
        if diff:
            ok = False
            print(title + ":")
            for key, n in sorted(diff.items(), key=str):
                print("  ", n, key)
    return ok


# ---------- цены в HTML ----------

def expected_html(view):
    """Эталон — прайсы из data/prices.json (источник истины)."""
    cnt = Counter(); counts = {}
    for slug, sections in PRICES.items():
        n = 0
        for index, (_, items) in enumerate(priced_sections(sections, view)):
            for name, _, _, price_text in items:
                cnt[(slug, index, name, price_text)] += 1; n += 1
        counts[slug] = n
    return cnt, counts


def rendered_html(view):
    """Факт — цены из сгенерированного vn.neva.beauty/<slug>/index.html."""
    cnt = Counter(); counts = {}
    for slug in PRICES:
        soup = BeautifulSoup(page_html(view, slug), "html.parser")
        n = 0
        for index, panel in enumerate(soup.select(".pricelist__panel")):
            for row in panel.select(".pricelist__row"):
                name_el = row.select_one(".pricelist__name")
                d = name_el.select_one(".pricelist__desc")
                if d:
                    d.extract()
                price = row.select_one(".pricelist__price")
                cnt[(slug, index, clean(name_el.get_text()), clean(price.get_text()))] += 1; n += 1
            for c in panel.select(".combo"):
                cnt[(slug, index, clean(c.select_one(".combo__name").get_text()),
                     clean(c.select_one(".combo__price").get_text()))] += 1; n += 1
        counts[slug] = n
    return cnt, counts


# ---------- цены в JSON-LD ----------

def expected_offers():
    """Эталон каталога: позиции с числовой ценой, кроме доплат и товаров.
    Отбор тот же, что у диапазона: цену, которую нельзя заплатить за саму
    услугу, разметка утверждать не должна. Пустые после отбора разделы
    выпадают — как в pricing.offer_sections, иначе разъедутся номера разделов."""
    cnt = Counter()
    for slug, sections in PRICES.items():
        index = 0
        for sec in sections:
            kept = [(clean(it["name"]), clean(it.get("desc", "")), value)
                    for it in sec["items"] if not is_addon(it)
                    and (value := price_number(it["price"])) is not None]
            if not kept:
                continue
            for name, desc, price in kept:
                cnt[(slug, index, name, desc, price, CURRENCY)] += 1
            index += 1
    return cnt


def rendered_offers(view):
    """Факт — Offer'ы из hasOfferCatalog на странице услуги."""
    cnt = Counter(); mismatched = []
    for slug in PRICES:
        for index, offer in catalog_offers(service_node(view, slug).get("hasOfferCatalog", {})):
            offered = offer.get("itemOffered", {})
            desc = clean(offer.get("description", ""))
            if desc != clean(offered.get("description", "")):
                mismatched.append((slug, offered.get("name"), desc))
            cnt[(slug, index, clean(offered.get("name", "")), desc,
                 offer.get("price"), offer.get("priceCurrency"))] += 1
    return cnt, mismatched


# ---------- цены на карточках «Популярное» (главная) ----------

def expected_popular(view):
    """Эталон карточек главной: точная цена, а при одноимённых позициях в разных
    разделах прайса — «от <минимальной>» (см. pricing.popular_price)."""
    result = {}
    for item in CONTENT["home"].get("popular", []):
        matches = [clean(it["price"]) for sec in PRICES.get(item["slug"], [])
                   for it in sec["items"] if it["name"] == item["name"]]
        if not matches:
            sys.exit(f"«Популярное»: в прайсе {item['slug']} нет позиции {item['name']!r}")
        price = matches[0] if len(set(matches)) == 1 else view.format_from(min(matches, key=price_number))
        result[clean(item["name"])] = price
    return result


def rendered_popular(view):
    """Факт — цены на карточках «Популярное» собранной главной."""
    soup = BeautifulSoup(view.page_file().read_text(encoding="utf-8"), "html.parser")
    return {clean(card.select_one(".popular-card__name").get_text()):
            clean(card.select_one(".popular-card__price").get_text())
            for card in soup.select(".popular-card")}


# ---------- цены в сравнительных таблицах ----------

def expected_compare(view):
    """Эталон сравнительной таблицы: [(название услуги, цена одной строкой)]
    в порядке строк из content.yml."""
    result = {}
    for slug, svc in CONTENT["services"].items():
        rows = (svc.get("compare") or {}).get("rows")
        if rows:
            result[slug] = [(clean(CONTENT["services"][row["slug"]]["title"]),
                             price_hint(PRICES.get(row["slug"], []), view)) for row in rows]
    return result


def rendered_compare(view):
    """Факт — строки сравнительных таблиц на собранных страницах услуг."""
    result = {}
    for slug in PRICES:
        rows = []
        for row in BeautifulSoup(page_html(view, slug), "html.parser").select(".compare__table tbody tr"):
            name = row.select_one(".pricelist__name")
            desc = name.select_one(".pricelist__desc")
            if desc:
                desc.extract()
            rows.append((clean(name.get_text()),
                         clean(row.select_one(".pricelist__price").get_text())))
        if rows:
            result[slug] = rows
    return result


def expected_aggregates():
    """Эталон диапазона: min/max/кол-во по позициям без доплат."""
    result = {}
    for slug, sections in PRICES.items():
        values = [v for sec in sections for it in sec["items"]
                  if not is_addon(it) and (v := price_number(it["price"])) is not None]
        if values:
            result[slug] = (min(values), max(values), len(values), CURRENCY)
    return result


def rendered_aggregates(view):
    """Факт — цены услуги из Service.offers: AggregateOffer с диапазоном либо
    обычный Offer, если позиция в прайсе одна. Обе формы приводим к общему виду
    (min, max, count, валюта) — тогда подмена одной формы другой всё равно всплывёт
    как расхождение с прайсом: у Offer count всегда 1, у диапазона — число позиций."""
    result = {}
    for slug in PRICES:
        offers = service_node(view, slug).get("offers")
        if not offers:
            continue
        kind = offers.get("@type")
        if kind == "Offer":
            result[slug] = (offers["price"], offers["price"], 1, offers["priceCurrency"])
        elif kind == "AggregateOffer":
            result[slug] = (offers["lowPrice"], offers["highPrice"],
                            offers["offerCount"], offers["priceCurrency"])
        else:
            sys.exit(f"{slug}: Service.offers неизвестного типа {kind!r}")
    return result


if not (isinstance(CURRENCY, str) and re.fullmatch(r"[A-Z]{3}", CURRENCY)):
    sys.exit(f"business.currency в site.yml = {CURRENCY!r}: цены в разметке уйдут без валюты")

def compare_popular(view):
    """Карточки «Популярное» главной против прайса. True, если расхождений нет."""
    exp_popular, new_popular = expected_popular(view), rendered_popular(view)
    ok = True
    for name in sorted(set(exp_popular) | set(new_popular)):
        if exp_popular.get(name) != new_popular.get(name):
            ok = False
            print(f"POPULAR MISMATCH «{name}»: ожидалось {exp_popular.get(name)!r}, "
                  f"на главной {new_popular.get(name)!r}")
    return ok


def compare_tables(view):
    """Сравнительные таблицы и описания Offer'ов. True, если расхождений нет."""
    exp_compare, new_compare = expected_compare(view), rendered_compare(view)
    ok = True
    for slug in sorted(set(exp_compare) | set(new_compare)):
        if exp_compare.get(slug) != new_compare.get(slug):
            ok = False
            print(f"COMPARE MISMATCH {slug}: prices.json={exp_compare.get(slug)} "
                  f"на странице={new_compare.get(slug)}")
    for slug, name, desc in rendered_offers(view)[1]:
        ok = False
        print(f"DESCRIPTION MISMATCH {slug}: у Offer «{name}» описание {desc!r} "
              f"не совпадает с описанием в itemOffered")
    return ok


def compare_catalogs(view):
    """Разделы каталога, число позиций и диапазоны цен по каждой услуге. True, если расхождений нет."""
    _, exp_counts = expected_html(view)
    _, new_counts = rendered_html(view)
    exp_aggr, new_aggr = expected_aggregates(), rendered_aggregates(view)
    ok = True
    for slug, sections in PRICES.items():
        titles = [title for title, _ in priced_sections(sections, view)]
        catalog = service_node(view, slug).get("hasOfferCatalog", {})
        expected_titles = titles if len(titles) > 1 else []
        if catalog_section_titles(catalog) != expected_titles:
            ok = False
            print(f"SECTIONS MISMATCH {slug}: prices.json={expected_titles} "
                  f"JSON-LD={catalog_section_titles(catalog)}")
        if exp_counts[slug] != new_counts.get(slug, 0):
            ok = False
            print(f"COUNT MISMATCH {slug}: prices.json={exp_counts[slug]} rendered={new_counts.get(slug, 0)}")
        if exp_aggr.get(slug) != new_aggr.get(slug):
            ok = False
            print(f"AGGREGATE MISMATCH {slug}: prices.json={exp_aggr.get(slug)} "
                  f"JSON-LD={new_aggr.get(slug)} (low, high, count, currency)")
    return ok


def run(view):
    """Сверка цен одного языка. Возвращает True, если расхождений нет."""
    exp_html, _ = expected_html(view)
    new_html, _ = rendered_html(view)
    exp_offers = expected_offers()
    new_offers, _ = rendered_offers(view)
    ok = report("HTML", exp_html, new_html)
    ok &= report("JSON-LD", exp_offers, new_offers)
    ok &= compare_popular(view)
    ok &= compare_tables(view)
    ok &= compare_catalogs(view)
    print(f"[{view.code}] html_items={sum(new_html.values())} jsonld_offers={sum(new_offers.values())} "
          f"aggregates={len(rendered_aggregates(view))} popular={len(rendered_popular(view))} "
          f"compare_rows={sum(len(rows) for rows in rendered_compare(view).values())} currency={CURRENCY}")
    return ok


results = [run(LocaleView(code)) for code in LOCALE_CODES]
print("PRICE PARITY OK" if all(results) else "PRICE PARITY FAILED")
sys.exit(0 if all(results) else 1)
