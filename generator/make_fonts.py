"""Сборка самохостовых шрифтов: инстансы нужных начертаний + подрезка набора знаков.

Запускается руками, когда меняется набор начертаний: `python generator/make_fonts.py`.
Результат — `assets/fonts/*.woff2` и `assets/css/fonts.css` — коммитится.

Зачем: с Google Fonts шрифт приезжает разрезанным по алфавитам, и каждое
начертание тянет два файла — латиницу и кириллицу. Латинский кусок весит больше
кириллического (24 КБ против 14 КБ у Manrope) и приходит всегда: в его
`unicode-range` попадают цифры и знаки препинания, а они есть на любой странице.
Внутри — три сотни знаков под все европейские языки, из которых сайту нужны
латинские буквы, цифры и пунктуация.

Здесь из вариативного мастера режется по одному файлу на начертание сразу с
обоими алфавитами и только с теми знаками, которые сайту нужны.

Набор знаков намеренно шире, чем сейчас на страницах: под будущие правки текста
взяты алфавиты целиком, а не выборка по факту. Что знаки не разъехались с
текстом, следит проверка в check_content.py.
"""

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.subset import Subsetter, Options

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "sources" / "fonts"
OUT_DIR = ROOT.parent / "vn.neva.beauty" / "assets" / "fonts"
CSS_PATH = ROOT.parent / "vn.neva.beauty" / "assets" / "css" / "fonts.css"

# Начертания: какой файл-мастер, какие веса и под какую роль в вёрстке.
FACES = [
    ("Manrope", "Manrope[wght].ttf", (400, 500, 600, 700)),
    ("Cormorant", "Cormorant[wght].ttf", (600,)),
]

# Подложка на время загрузки. font-display:swap рисует текст системным шрифтом сразу,
# и без выравнивания метрик эти первые секунды выглядят чужой страницей: Georgia шире
# Cormorant на 14%, строки занимают другое число строк и прыгают при подмене.
# size-adjust — отношение средней ширины символа, замеренное на русском тексте сайта;
# ascent/descent — метрики фирменного шрифта, поделённые на size-adjust, потому что
# браузер масштабирует и переопределённые метрики тоже.
# Если ни один local() не нашёлся, правило просто не применяется и в силу вступает
# следующий шрифт списка — поведение не хуже прежнего.
FALLBACKS = [
    ("Cormorant Fallback", ("Georgia", "Noto Serif", "Times New Roman"),
     "size-adjust:88.5%;ascent-override:104.4%;descent-override:32.4%;line-gap-override:0%"),
    ("Manrope Fallback", ("Arial", "Roboto", "Helvetica Neue"),
     "size-adjust:102.7%;ascent-override:103.8%;descent-override:29.2%;line-gap-override:0%"),
]

BASIC_LATIN = "".join(chr(c) for c in range(0x20, 0x7F))
RUSSIAN = ("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
           "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
# Типографика: кавычки, тире, номер, градус, копирайт, знак умножения,
# неразрывный и узкий неразрывный пробел, мягкий перенос, ударение.
TYPOGRAPHY = "«»„“”‘’–—…№°©®×±§€₽•  ­́"
# Знаки, которых нет у th, но которые есть в текстах vn.
# đ — вьетнамский донг, валюта салона: стоит на 14 страницах из 24.
# Đ — заглавная пара к нему: в текстах пока не встречается, но взята заодно,
# чтобы «Đà Nẵng» в будущей правке не вылезло квадратом.
# · — разделитель в перечислениях, три страницы.
VIETNAM = "đĐ·"
CHARSET = BASIC_LATIN + RUSSIAN + TYPOGRAPHY + VIETNAM


def instance_of(master_path, weight):
    """Статический шрифт нужного веса из вариативного мастера."""
    font = TTFont(master_path)
    return instancer.instantiateVariableFont(font, {"wght": weight})


def subset(font):
    """Оставляет в шрифте только знаки из CHARSET."""
    options = Options()
    options.layout_features = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk"]
    options.flavor = "woff2"
    options.desubroutinize = True
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes={ord(c) for c in CHARSET})
    subsetter.subset(font)
    return font


def build_face(family, master, weight):
    font = subset(instance_of(SRC_DIR / master, weight))
    font.flavor = "woff2"
    path = OUT_DIR / f"{family.lower()}-{weight}.woff2"
    font.save(path)
    print(f"→ {path.name} {path.stat().st_size // 1024} КБ")
    return path.name


def css_rule(family, weight, filename):
    return (f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{weight};font-display:swap;"
            f"src:url('../fonts/{filename}') format('woff2')}}")


def fallback_rule(family, locals_, metrics):
    sources = ",".join(f"local('{name}')" for name in locals_)
    return f"@font-face{{font-family:'{family}';src:{sources};{metrics}}}"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rules = ["/* Самохостинг шрифтов — сгенерировано make_fonts.py. Не редактировать вручную. */"]
    for family, master, weights in FACES:
        for weight in weights:
            rules.append(css_rule(family, weight, build_face(family, master, weight)))
    rules.append("/* Подложка на время загрузки: системный шрифт с метриками фирменного. */")
    rules.extend(fallback_rule(*fallback) for fallback in FALLBACKS)
    CSS_PATH.write_text("\n".join(rules) + "\n", encoding="utf-8")
    print(f"→ {CSS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
