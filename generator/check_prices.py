"""Парити-тест цен: сверяет цены старого сайта и сгенерированного HTML.
Падает (exit 1) при любом расхождении. Защищает требование 100% точности цен.
Запуск: cd generator && ../.venv/bin/python check_prices.py"""
import sys
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup
from extract_prices import OLD, SLUG_FILE, parse_page, clean

NEW = Path(__file__).resolve().parent.parent / "vn.neva.beauty"

def old_side():
    cnt = Counter(); raw = {}
    for slug, f in SLUG_FILE.items():
        html = (OLD / f).read_text(encoding="utf-8")
        for sec in parse_page(html):
            for it in sec["items"]:
                cnt[(slug, clean(it["name"]), clean(it["price"]))] += 1
        soup = BeautifulSoup(html, "html.parser")
        raw[slug] = sum(1 for e in soup.select(".t812__pricelist-item__price") if clean(e.get_text()))
    return cnt, raw

def new_side():
    cnt = Counter(); counts = {}
    for slug in SLUG_FILE:
        soup = BeautifulSoup((NEW / slug / "index.html").read_text(encoding="utf-8"), "html.parser")
        n = 0
        for row in soup.select(".pricelist__row"):
            name_el = row.select_one(".pricelist__name")
            d = name_el.select_one(".pricelist__desc")
            if d:
                d.extract()
            price = row.select_one(".pricelist__price")
            cnt[(slug, clean(name_el.get_text()), clean(price.get_text()))] += 1; n += 1
        for c in soup.select(".combo"):
            cnt[(slug, clean(c.select_one(".combo__name").get_text()),
                 clean(c.select_one(".combo__price").get_text()))] += 1; n += 1
        counts[slug] = n
    return cnt, counts

old_cnt, raw = old_side()
new_cnt, newc = new_side()

ok = True
for label, diff in (("MISSING (есть в старом, нет в новом)", old_cnt - new_cnt),
                    ("EXTRA (есть в новом, нет в старом)", new_cnt - old_cnt)):
    if diff:
        ok = False
        print(label + ":")
        for k, n in sorted(diff.items()):
            print("  ", n, k)

for slug in SLUG_FILE:
    if raw[slug] != newc[slug]:
        ok = False
        print(f"COUNT MISMATCH {slug}: raw_old={raw[slug]} new_rendered={newc[slug]}")

print(f"old_items={sum(old_cnt.values())} new_items={sum(new_cnt.values())} raw_total={sum(raw.values())}")
print("PRICE PARITY OK" if ok else "PRICE PARITY FAILED")
sys.exit(0 if ok else 1)
