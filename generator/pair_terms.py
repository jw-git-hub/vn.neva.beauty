"""Обязательные термины глоссария: узнаём русский термин в строке и ищем английское слово.

Термин с полем required обязан дать это слово в английской строке (глоссарий,
столбец «Обязателен в паре»). Русский термин узнаётся по основам слов: падежи и
числа («LPG-массажа», «противопоказаниях») меняют окончание, но не начало. Где основа
ошибается, у термина есть поле ru_match — регулярное выражение для русского текста.
"""
import functools
import html
import re
from dataclasses import dataclass

import yaml

from locales import LOCALES_DIR

GLOSSARY_FILE = "glossary.yml"
TAG_RE = re.compile(r"<[^>]*>")
WORD_RE = re.compile(r"[^\W_]+")
MIN_STEM_LENGTH = 4  # слово короче не обрезается и ищется целиком
STEM_CUT = 2  # сколько букв отбрасывается с конца слова: окончание
WORD_START = r"(?<![^\W_])"
WORD_END = r"(?![^\W_])"
WORD_REST = r"[^\W_]*"  # остаток слова после основы: окончание любое
WORDS_SEPARATOR = r"[\W_]+"
ENGLISH_ENDINGS = r"(?:s|es|d|ed|ing|ly)?"  # scar → scars, lift → lifting, painless → painlessly


@dataclass(frozen=True)
class RequiredTerm:
    ru: str
    required: str
    russian_pattern: object  # re.Pattern: как термин выглядит в русском тексте
    english_pattern: object  # re.Pattern: как required выглядит в английском тексте


def fold(text):
    """Нижний регистр, ё = е: сравнение слов не зависит от регистра и «ё»."""
    return text.lower().replace("ё", "е")


def plain_text(text):
    """Текст без тегов и атрибутов (в них адреса и подписи), сущности раскрыты."""
    return html.unescape(TAG_RE.sub(" ", text))


def _word_pattern(word):
    if word.isascii() or len(word) < MIN_STEM_LENGTH:
        return re.escape(word) + WORD_END
    return re.escape(word[:max(MIN_STEM_LENGTH, len(word) - STEM_CUT)]) + WORD_REST


def stem_pattern(term_ru):
    """Слова термина идут подряд; у слова на кириллице отброшено окончание, а слова
    из латиницы и цифр, как и короткие, ищутся целиком."""
    words = WORD_RE.findall(fold(term_ru))
    return re.compile(WORD_START + WORDS_SEPARATOR.join(map(_word_pattern, words)))


def _russian_pattern(entry):
    if entry.get("ru_match"):
        return re.compile(fold(entry["ru_match"]), re.IGNORECASE)
    return stem_pattern(entry["ru"])


def _english_pattern(required):
    return re.compile(WORD_START + re.escape(fold(required)) + ENGLISH_ENDINGS + WORD_END)


def _term_of(entry):
    return RequiredTerm(entry["ru"], entry["required"], _russian_pattern(entry),
                        _english_pattern(entry["required"]))


@functools.lru_cache(maxsize=None)
def load_terms(code, directory=LOCALES_DIR):
    """Термины глоссария языка с полем required. Нет глоссария — нет обязательных терминов."""
    path = directory / code / GLOSSARY_FILE
    if not path.exists():
        return ()
    entries = yaml.safe_load(path.read_text(encoding="utf-8")).get("terms") or []
    return tuple(_term_of(entry) for entry in entries if entry.get("ru") and entry.get("required"))


def required_terms(russian_text, terms):
    """[(термин, найденный фрагмент)] — по одному на каждое required, в порядке глоссария."""
    text = fold(plain_text(russian_text))
    hits = {}
    for term in terms:
        found = term.russian_pattern.search(text)
        if found and term.required not in hits:
            hits[term.required] = (term, found.group(0))
    return list(hits.values())


def english_has(term, english_text):
    return bool(term.english_pattern.search(fold(plain_text(english_text))))
