"""Проверка иерархии заголовков во всех собранных страницах: ровно один h1, первый
заголовок — h1, уровни идут без пропусков. Падает (exit 1) при нарушении.

Зачем: пропуск уровня (h1 → h3) ломает навигацию скринридером по заголовкам и
считается ошибкой у W3C, но внешне страница выглядит нормально — три страницы
жили с этим незамеченными. Проверка локальная, сети не требует.
Запуск: python generator/check_headings.py"""
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "vn.neva.beauty"
HEADING_RE = re.compile(r"^h[1-6]$")


def pages():
    """Собранные страницы сайта. Служебные папки (.superpowers и подобные) пропускаем:
    они есть локально, но не в чистом чекауте CI — иначе проверка ведёт себя по-разному."""
    return sorted(page for page in SITE.glob("**/*.html")
                  if not any(part.startswith(".") for part in page.relative_to(SITE).parts))


def headings(page):
    """Заголовки страницы в порядке документа: [(уровень, текст)]."""
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    return [(int(h.name[1]), re.sub(r"\s+", " ", h.get_text()).strip())
            for h in soup.find_all(HEADING_RE)]


def check(page, found):
    """Нарушения иерархии на одной странице."""
    name = page.relative_to(SITE.parent)
    if not found:
        return [f"{name}: на странице нет ни одного заголовка"]
    errors = []
    first_level, first_text = found[0]
    if first_level != 1:
        errors.append(f"{name}: первый заголовок — h{first_level} «{first_text}», а не h1")
    h1_count = sum(1 for level, _ in found if level == 1)
    if h1_count != 1:
        errors.append(f"{name}: h1 на странице {h1_count}, должен быть ровно один")
    for (previous, _), (current, text) in zip(found, found[1:]):
        if current > previous + 1:
            errors.append(f"{name}: h{previous} → h{current} «{text}» — пропущен уровень")
    return errors


errors = [error for page in pages() for error in check(page, headings(page))]
print(f"страниц проверено: {len(pages())}")
print("\n".join(errors) if errors else "HEADINGS OK — иерархия заголовков без пропусков")
sys.exit(1 if errors else 0)
