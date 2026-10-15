"""Парити-тест цен: сверяет data/prices.json (источник истины) с ценами в
сгенерированном HTML (прайс-лист, карточки «Популярное», сравнительные таблицы)
и в JSON-LD (OfferCatalog + AggregateOffer). Падает (exit 1)
при любом расхождении — защищает требование 100% точности цен.
Сверяются не только цифры, но и раздел прайса, описание позиции и валюта:
в прайсе есть одноимённые позиции с разными ценами («Лоб» у женщин и мужчин),
поэтому позиция, уехавшая в соседний раздел, — такая же ошибка, как неверная цена.
Запуск: cd generator && ../.venv/bin/python check_prices.py"""
import copy
import json
import re
import sys
from collections import Counter, namedtuple
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import yaml
from bs4 import BeautifulSoup

# Модули сборки — только для названий на языке страницы (накладка текстов и словарь
# прайса). Разбор цен тест держит своей копией: price_number, is_addon, price_hint ниже.
import locales
import pricing
import translation

ROOT = Path(__file__).resolve().parent
NEW = ROOT.parent / "vn.neva.beauty"
PRICES = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
CONTENT = yaml.safe_load((ROOT / "data" / "content.yml").read_text(encoding="utf-8"))
SITE = yaml.safe_load((ROOT / "data" / "site.yml").read_text(encoding="utf-8"))
CURRENCY = SITE["business"].get("currency")
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
PRICE_RE = re.compile(r"^\+?\d[\d ]*đ$")
LOCALE_CODES = SITE.get("locales")
HOME_FILE = "index.html"
POPULAR_MISMATCH = "POPULAR MISMATCH «{key}»: ожидалось {expected!r}, на главной {rendered!r}"
COMPARE_MISMATCH = "COMPARE MISMATCH {key}: prices.json={expected} на странице={rendered}"
SECTIONS_MISMATCH = "SECTIONS MISMATCH {key}: prices.json={expected} JSON-LD={rendered}"
COUNT_MISMATCH = "COUNT MISMATCH {key}: prices.json={expected} rendered={rendered}"
AGGREGATE_MISMATCH = ("AGGREGATE MISMATCH {key}: prices.json={expected} "
                      "JSON-LD={rendered} (low, high, count, currency)")
DESCRIPTION_MISMATCH = ("DESCRIPTION MISMATCH {slug}: у Offer «{name}» описание {desc!r} "
                        "не совпадает с описанием в itemOffered")

# Пара «эталон из prices.json / факт из разметки» одной величины.
Pair = namedtuple("Pair", "expected rendered")


class LocaleView:
    """То, что тесту нужно знать о языке: где лежат страницы и как на них
    пишутся «от …» и название раздела по умолчанию. Читается из файла языка
    напрямую, без модулей сборки."""

    def __init__(self, code, main_code):
        data = yaml.safe_load((ROOT / "data" / "locales" / f"{code}.yml").read_text(encoding="utf-8"))
        self.code = code
        self.content, self.prices, self._price_translation = translated_data(code, main_code)
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

    def prices_name(self, slug, name):
        return self._price_translation.text(slug, "names", name)


def translated_data(code, main_code):
    """Тексты, прайс и переводчик прайса языка: основной — как в мастере, перевод —
    через модули перевода. Прайс — в виде для шаблона: признак комбо по русскому названию."""
    language = translation.prepare(CONTENT, PRICES, locales.load_locale(code),
                                   locales.load_locale(main_code))
    prices = {slug: language.prices.translate_sections(slug, pricing.price_view(sections))
              for slug, sections in PRICES.items()}
    return language.content, prices, language.prices


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


# price_number и is_addon — НАМЕРЕННАЯ копия логики generator/pricing.py, а не импорт из неё (как и вообще из модулей сборки).
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


@lru_cache(maxsize=None)
def page_soup(view, slug):
    """Страница услуги разбирается один раз: цены, таблица сравнения и название
    берутся из одного разбора. Дерево общее — не менять его (см. name_text)."""
    return BeautifulSoup(page_html(view, slug), "html.parser")


def name_text(name_element):
    """Название позиции без описания. Описание убирается из копии: разбор страницы
    лежит в кэше и нужен следующим сверкам нетронутым."""
    own = copy.copy(name_element)
    description = own.select_one(".pricelist__desc")
    if description:
        description.extract()
    return clean(own.get_text())


@lru_cache(maxsize=None)
def service_node(view, slug):
    """Узел Service из JSON-LD страницы услуги. Разбор JSON — один раз на слаг."""
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
    for slug, sections in view.prices.items():
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
        n = 0
        for index, panel in enumerate(page_soup(view, slug).select(".pricelist__panel")):
            for row in panel.select(".pricelist__row"):
                name = name_text(row.select_one(".pricelist__name"))
                price = row.select_one(".pricelist__price")
                cnt[(slug, index, name, clean(price.get_text()))] += 1; n += 1
            for c in panel.select(".combo"):
                cnt[(slug, index, clean(c.select_one(".combo__name").get_text()),
                     clean(c.select_one(".combo__price").get_text()))] += 1; n += 1
        counts[slug] = n
    return cnt, counts


PRICE_CELL_SELECTOR = ".pricelist__price, .combo__price"
POSITION_MISMATCH = "POSITION MISMATCH {slug} #{index}: {main_code}={expected!r} {code}={rendered!r}"


def price_sequence(soup):
    """Цены прайс-листа в порядке документа: строки таблицы и карточки комбо."""
    return [clean(cell.get_text()) for panel in soup.select(".pricelist__panel")
            for cell in panel.select(PRICE_CELL_SELECTOR)]


def position_mismatches(main, other):
    """n-я цена перевода против n-й цены основного языка: [(номер, основная, перевода)]."""
    size = max(len(main), len(other))
    padded = [(main + [None] * size)[:size], (other + [None] * size)[:size]]
    return [(index, expected, rendered)
            for index, (expected, rendered) in enumerate(zip(*padded)) if expected != rendered]


def report_positions(main_view, view):
    """Позиционное равенство: перевод не мог переставить или потерять цену."""
    ok = True
    for slug in PRICES:
        for index, expected, rendered in position_mismatches(
                price_sequence(page_soup(main_view, slug)), price_sequence(page_soup(view, slug))):
            ok = False
            print(POSITION_MISMATCH.format(slug=slug, index=index, main_code=main_view.code,
                                           code=view.code, expected=expected, rendered=rendered))
    return ok


# ---------- цены в JSON-LD ----------

def expected_offers(view):
    """Эталон каталога: позиции с числовой ценой, кроме доплат и товаров.
    Отбор тот же, что у диапазона: цену, которую нельзя заплатить за саму
    услугу, разметка утверждать не должна. Пустые после отбора разделы
    выпадают — как в pricing.offer_sections, иначе разъедутся номера разделов."""
    cnt = Counter()
    for slug, sections in view.prices.items():
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
        result[clean(view.prices_name(item["slug"], item["name"]))] = price
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
    services = view.content["services"]
    for slug, svc in services.items():
        rows = (svc.get("compare") or {}).get("rows")
        if rows:
            result[slug] = [(clean(services[row["slug"]]["title"]),
                             price_hint(PRICES.get(row["slug"], []), view)) for row in rows]
    return result


def rendered_compare(view):
    """Факт — строки сравнительных таблиц на собранных страницах услуг."""
    result = {}
    for slug in PRICES:
        rows = []
        for row in page_soup(view, slug).select(".compare__table tbody tr"):
            rows.append((name_text(row.select_one(".pricelist__name")),
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


def expected_section_titles(view):
    """Эталон заголовков разделов каталога: у услуги с одним разделом
    вложенных OfferCatalog нет, поэтому список пуст."""
    result = {}
    for slug, sections in view.prices.items():
        titles = [title for title, _ in priced_sections(sections, view)]
        result[slug] = titles if len(titles) > 1 else []
    return result


def rendered_section_titles(view):
    """Факт — заголовки вложенных OfferCatalog на странице услуги."""
    return {slug: catalog_section_titles(service_node(view, slug).get("hasOfferCatalog", {}))
            for slug in PRICES}


def collect(view):
    """Эталон и факт по каждой величине считаются здесь один раз на язык:
    разбор HTML и JSON-LD дорогой, сравнения берут готовые значения."""
    exp_html, exp_counts = expected_html(view)
    new_html, new_counts = rendered_html(view)
    new_offers, mismatched = rendered_offers(view)
    return SimpleNamespace(
        html=Pair(exp_html, new_html),
        counts=Pair(exp_counts, new_counts),
        offers=Pair(expected_offers(view), new_offers),
        descriptions=mismatched,
        popular=Pair(expected_popular(view), rendered_popular(view)),
        compare=Pair(expected_compare(view), rendered_compare(view)),
        sections=Pair(expected_section_titles(view), rendered_section_titles(view)),
        aggregates=Pair(expected_aggregates(), rendered_aggregates(view)),
    )


def report_mismatches(pair, template):
    """Печатает каждый ключ, по которому эталон и факт различаются.
    True, если расхождений нет."""
    ok = True
    for key in sorted(set(pair.expected) | set(pair.rendered)):
        expected, rendered = pair.expected.get(key), pair.rendered.get(key)
        if expected != rendered:
            ok = False
            print(template.format(key=key, expected=expected, rendered=rendered))
    return ok


def report_descriptions(mismatched):
    """Описание Offer'а должно совпадать с описанием его itemOffered. True, если так и есть."""
    for slug, name, desc in mismatched:
        print(DESCRIPTION_MISMATCH.format(slug=slug, name=name, desc=desc))
    return not mismatched


def summary_line(view, facts):
    return (f"[{view.code}] html_items={sum(facts.html.rendered.values())} "
            f"jsonld_offers={sum(facts.offers.rendered.values())} "
            f"aggregates={len(facts.aggregates.rendered)} popular={len(facts.popular.rendered)} "
            f"compare_rows={sum(len(rows) for rows in facts.compare.rendered.values())} "
            f"currency={CURRENCY}")


def run(view):
    """Сверка цен одного языка. Возвращает True, если расхождений нет.
    `&=` не обрывает цепочку: печатаются расхождения всех блоков сразу."""
    facts = collect(view)
    ok = report("HTML", *facts.html)
    ok &= report("JSON-LD", *facts.offers)
    ok &= report_mismatches(facts.popular, POPULAR_MISMATCH)
    ok &= report_mismatches(facts.compare, COMPARE_MISMATCH)
    ok &= report_descriptions(facts.descriptions)
    ok &= report_mismatches(facts.sections, SECTIONS_MISMATCH)
    ok &= report_mismatches(facts.counts, COUNT_MISMATCH)
    ok &= report_mismatches(facts.aggregates, AGGREGATE_MISMATCH)
    print(summary_line(view, facts))
    return ok


def main():
    if not (isinstance(CURRENCY, str) and re.fullmatch(r"[A-Z]{3}", CURRENCY)):
        sys.exit(f"business.currency в site.yml = {CURRENCY!r}: цены в разметке уйдут без валюты")
    if not LOCALE_CODES:
        sys.exit("В site.yml не задан список языков locales: без него нечего сверять")
    views = [LocaleView(code, LOCALE_CODES[0]) for code in LOCALE_CODES]
    results = [run(view) for view in views]
    results += [report_positions(views[0], view) for view in views[1:]]
    print("PRICE PARITY OK" if all(results) else "PRICE PARITY FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
