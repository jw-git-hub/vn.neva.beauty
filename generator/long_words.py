"""Мягкие переносы (U+00AD) в очень длинных словах названий прайса.

Исключение из решения 26.10 «слова названий прайса не рвутся переносом» — по решению
владельца 09.11.2026. «высококонцентрированная» (уход за лицом) не даёт таблице прайса
сжаться уже 404 px, и цены вылезают за карточку. Перенос по слогам через CSS
(hyphens: auto) зависит от словаря в браузере: в headless Chrome на Linux его нет,
и там слово не переносилось. Мягкий перенос ставит сборка — он одинаков во всех
браузерах. Видимы такие переносы только уже 404 px: шире service.css выключает их
(hyphens: none), и вид прежний.

Места переноса берутся из словаря pyphen (паттерны LibreOffice) для языка страницы.
Языка нет в словаре — текст не меняется. Данные салона не трогаются: перенос
ставится только в выводе страницы.
"""
import re
from functools import lru_cache

import pyphen

SOFT_HYPHEN = "­"
# Порог владельца: только слова от 20 букв и не короче 8 букв по обе стороны переноса.
MIN_WORD_LETTERS = 20
MIN_PART_LETTERS = 8
WORD_RE = re.compile(r"[^\W\d_]+")


@lru_cache(maxsize=None)
def dictionary(language):
    """Словарь переносов языка или None, если у pyphen такого языка нет."""
    code = pyphen.language_fallback(language)
    if code is None:
        return None
    return pyphen.Pyphen(lang=code, left=MIN_PART_LETTERS, right=MIN_PART_LETTERS)


def hyphenate_word(word, language):
    """Слово с мягкими переносами, если в нём не меньше MIN_WORD_LETTERS букв."""
    hyphenator = dictionary(language)
    if hyphenator is None or len(word) < MIN_WORD_LETTERS:
        return word
    return hyphenator.inserted(word, hyphen=SOFT_HYPHEN)


def soft_hyphenate(text, language):
    """Текст, где длинные слова получили мягкие переносы; остальное как было."""
    return WORD_RE.sub(lambda match: hyphenate_word(match.group(), language), text)
