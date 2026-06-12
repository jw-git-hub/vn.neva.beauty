"""Извлекает прайс-листы из старых Tilda-страниц в data/prices.json.
Источник истины по ценам. Цены и названия НЕ нормализуются (переносятся дословно)."""
import json, re
from pathlib import Path
from bs4 import BeautifulSoup

OLD = Path(__file__).resolve().parent.parent / "lданные старого сайта"
OUT = Path(__file__).resolve().parent / "data" / "prices.json"

SLUG_FILE = {
    "lazernaya-epilyaciya": "page116772006.html",
    "lpg-massazh": "page116853986.html",
    "endosfera-terapiya": "page116855366.html",
    "ultrazvukovaya-kavitaciya": "page116856706.html",
    "esteticheskaya-kosmetologiya-i-uhod": "page117250526.html",
    "smas-lifting": "page117589196.html",
    "udalenie-tatuirovok-lazerom": "page118008586.html",
    "udalenye-permanentnogo-makiyazha": "page118018046.html",
    "morpheus-8-rf-lifting": "page118032546.html",
    "fotoomolozhenie-m22": "page118049356.html",
}

def clean(s): return re.sub(r"\s+", " ", s).strip()

def parse_page(html):
    """Возвращает [{section: str|None, items: [{name, desc, price}]}] в порядке документа.
    Секции — блоки t030__title; элементы — t812__pricelist-item.
    desc — уточнение позиции (напр. «1 сеанс»), различает одноимённые строки."""
    soup = BeautifulSoup(html, "html.parser")
    sections, current = [], {"section": None, "items": []}
    nodes = soup.select(".t030__title, .t812__pricelist-item")
    for node in nodes:
        cls = node.get("class", [])
        if "t030__title" in cls:
            txt = clean(node.get_text())
            if not txt:
                continue
            if current["items"]:
                sections.append(current)
            current = {"section": txt, "items": []}
        else:
            title = node.select_one(".t812__pricelist-item__title")
            price = node.select_one(".t812__pricelist-item__price")
            if not title or not price:
                continue
            name, val = clean(title.get_text()), clean(price.get_text())
            if not val:
                continue
            descr = node.select_one(".t812__pricelist-item__descr")
            desc = clean(descr.get_text()) if descr else ""
            current["items"].append({"name": name, "desc": desc, "price": val})
    if current["items"]:
        sections.append(current)
    return sections

def main():
    data = {}
    for slug, fname in SLUG_FILE.items():
        html = (OLD / fname).read_text(encoding="utf-8")
        data[slug] = parse_page(html)
        n = sum(len(s["items"]) for s in data[slug])
        print(f"{slug}: {n} позиций в {len(data[slug])} секциях")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT}")

if __name__ == "__main__":
    main()
