"""Проверка: каждый знак на страницах есть в самохостовых шрифтах.

Шрифты подрезаны под нужный сайту набор знаков (make_fonts.py), поэтому новая
буква в тексте — латинская «z» в названии аппарата, вьетнамская диакритика в
адресе — отрисуется системным шрифтом. В вёрстке это выглядит как одна буква не
в ту гарнитуру: заметно, только если знать, куда смотреть.

Набор читается из самих .woff2, а не дублируется здесь константой: подрезал
шрифты иначе — проверка узнала об этом сама.

Запуск: `python generator/check_fonts.py`. Возвращает 1, если что-то не покрыто.
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "vn.neva.beauty"
FONTS = SITE / "assets" / "fonts"

# Знаки, которых нет ни в Manrope, ни в Cormorant, — их рисует системный шрифт.
# Пока таких нет: донг (đ) добавлен в подрезку, а не отдан системе.
FONT_FALLBACK_CHARS: set[str] = set()

# Служебные каталоги внутри папки деплоя: не страницы сайта и в git не входят.
SKIP_DIRS = {".superpowers"}


def font_charset():
    """Объединённый набор знаков всех самохостовых шрифтов."""
    charset = set()
    for path in sorted(FONTS.glob("*.woff2")):
        with TTFont(path) as font:
            charset.update(chr(code) for code in font.getBestCmap())
    return charset


def pages():
    for path in sorted(SITE.rglob("*.html")):
        if SKIP_DIRS.isdisjoint(part for part in path.parts):
            yield path


def visible_chars(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    texts = (node for node in soup.find_all(string=True)
             if node.parent.name not in ("script", "style"))
    return {c for text in texts for c in text if c.isprintable() and not c.isspace()}


def main():
    charset = font_charset()
    problems = []
    for path in pages():
        missing = sorted(visible_chars(path) - charset - FONT_FALLBACK_CHARS)
        if missing:
            problems.append(f"{path.relative_to(SITE.parent)}: знаков нет в шрифтах сайта: {''.join(missing)}")
    for problem in problems:
        print(problem)
    print(f"страниц проверено: {len(list(pages()))}, знаков в шрифтах: {len(charset)}, "
          f"проблем: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
