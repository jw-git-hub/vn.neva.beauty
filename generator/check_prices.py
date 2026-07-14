"""Парити-тест цен: сверяет data/prices.json (источник истины) с ценами в
сгенерированном HTML. Падает (exit 1) при любом расхождении — защищает
требование 100% точности цен.
Запуск: cd generator && ../.venv/bin/python check_prices.py"""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
NEW = ROOT.parent / "vn.neva.beauty"
PRICES = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def expected_side():
    """Эталон — прайсы из data/prices.json (источник истины)."""
    cnt = Counter(); counts = {}
    for slug, sections in PRICES.items():
        n = 0
        for sec in sections:
            for it in sec["items"]:
                if not clean(it["price"]):
                    continue
                cnt[(slug, clean(it["name"]), clean(it["price"]))] += 1; n += 1
        counts[slug] = n
    return cnt, counts


def new_side():
    """Факт — цены из сгенерированного vn.neva.beauty/<slug>/index.html."""
    cnt = Counter(); counts = {}
    for slug in PRICES:
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


exp_cnt, exp_c = expected_side()
new_cnt, new_c = new_side()

ok = True
for label, diff in (("MISSING (есть в prices.json, нет в HTML)", exp_cnt - new_cnt),
                    ("EXTRA (есть в HTML, нет в prices.json)", new_cnt - exp_cnt)):
    if diff:
        ok = False
        print(label + ":")
        for k, n in sorted(diff.items()):
            print("  ", n, k)

for slug in PRICES:
    if exp_c[slug] != new_c.get(slug, 0):
        ok = False
        print(f"COUNT MISMATCH {slug}: prices.json={exp_c[slug]} rendered={new_c.get(slug, 0)}")

print(f"expected_items={sum(exp_cnt.values())} rendered_items={sum(new_cnt.values())}")
print("PRICE PARITY OK" if ok else "PRICE PARITY FAILED")
sys.exit(0 if ok else 1)
