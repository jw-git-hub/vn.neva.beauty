"""Проверка заголовков во всех собранных страницах. Падает (exit 1) при нарушении.

Два правила. Первое — иерархия: ровно один h1, первый заголовок — h1, уровни идут
без пропусков. Второе — уникальность h2 по сайту: один и тот же h2 на нескольких
страницах не говорит ни клиенту, ни роботу, что именно под ним, и место в структуре
страницы тратится впустую. Правило перенесено с th.neva.beauty
(check_content.py, check_shared_headings).

Зачем: пропуск уровня (h1 → h3) ломает навигацию скринридером по заголовкам и
считается ошибкой у W3C, но внешне страница выглядит нормально — три страницы
жили с этим незамеченными. Проверка локальная, сети не требует.
Запуск: python generator/check_headings.py"""
import re
import sys
from collections import defaultdict
from functools import lru_cache
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


def page_name(page):
    return str(page.relative_to(SITE.parent))


@lru_cache(maxsize=None)
def parse(page):
    """Страница разбирается один раз: заголовки, h2 и язык берутся из одного разбора."""
    return BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")


def headings(page):
    """Заголовки страницы в порядке документа: [(уровень, текст)]."""
    return [(int(h.name[1]), re.sub(r"\s+", " ", h.get_text()).strip())
            for h in parse(page).find_all(HEADING_RE)]


def check(page, found):
    """Нарушения иерархии на одной странице."""
    name = page_name(page)
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


# Ключ — язык страницы (<html lang>): одинаковый h2 считается дублем только внутри языка.
# Известный остаток дублей h2, ещё не разобранный. Правило уникальности введено
# вместе с заголовками блока записи, а на эти три группы заказчик правку текста
# пока не давал. Список именной и конечный: новый дубль проверка поймает сразу,
# а этот остаток виден в коде и не притворяется, что его нет.
# Как это решено на th.neva.beauty: «Цены» → «Сколько стоит <услуга> …?»,
# «Смотрите также» → «Что выбирают вместе с услугой «<название>»» — оба
# собираются шаблоном из title страницы; «Почему это работает» потребует текста.
KNOWN_SHARED_H2 = {
    "ru": {
        "Почему это работает",
        "Цены",
        "Смотрите также",
    },
}


def main_h2(page):
    """h2 внутри <main>. Подвал не в счёт: «Услуги» и «Контакты» стоят там на
    каждой странице по определению, и это не дубли-заголовки, а навигация."""
    return [re.sub(r"\s+", " ", h.get_text()).strip() for h in parse(page).select("main h2")]


def page_lang(page):
    """Язык страницы из <html lang>. Без него дубли h2 нельзя отнести к языку — это ошибка страницы."""
    root = parse(page).html
    lang = root.get("lang") if root else None
    if not lang:
        sys.exit(f"{page_name(page)}: у страницы нет <html lang>, язык заголовков неизвестен")
    return lang


def shared_h2(pages_):
    """Один и тот же h2 на нескольких страницах одного языка."""
    seen = defaultdict(list)
    for page in pages_:
        lang = page_lang(page)
        for text in main_h2(page):
            if text not in KNOWN_SHARED_H2.get(lang, set()):
                seen[(lang, text)].append(page_name(page))
    errors = []
    for (lang, text), where in sorted(seen.items()):
        if len(where) > 1:
            shown = ", ".join(where[:3]) + ("…" if len(where) > 3 else "")
            errors.append(f"один и тот же h2 на {len(where)} страницах [{lang}] ({shown}): «{text}»")
    return errors


all_headings = [(page, headings(page)) for page in pages()]
errors = [error for page, found in all_headings for error in check(page, found)]
errors += shared_h2([page for page, _ in all_headings])
print(f"страниц проверено: {len(all_headings)}, "
      f"известных дублей в исключениях: {sum(len(known) for known in KNOWN_SHARED_H2.values())}")
print("\n".join(errors) if errors else "HEADINGS OK — иерархия без пропусков, h2 не повторяются")
sys.exit(1 if errors else 0)
