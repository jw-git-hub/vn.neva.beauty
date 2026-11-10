"""Обязательные термины глоссария: узнаём русский термин в строке и ищем английское слово.

Термин с полем required обязан дать это слово в английской строке (глоссарий,
столбец «Обязателен в паре»), и каждый термин — своё вхождение: «коррекция фигуры» и
«лифтинг и омоложение» в одной строке требуют «non-surgical» дважды. Русский термин
узнаётся по основам слов: падежи и числа («LPG-массажа», «противопоказаниях») меняют
окончание, но не начало. Где основа ошибается, у термина есть поле ru_match —
регулярное выражение для русского текста.
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


@dataclass(frozen=True)
class MissingWord:
    """Слово required, которое стоит в переводе реже, чем русских терминов его требуют."""
    required: str
    found: tuple  # ((термин, фрагмент русского текста), …) — по одному на термин
    present: int  # сколько раз слово стоит в переводе

    @property
    def shortfall(self):
        return len(self.found) - self.present


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


def _spans_by_word(matches):
    """{слово required: [(начало, конец)]} — все места, где стоят его термины."""
    spans = {}
    for term, found in matches:
        spans.setdefault(term.required, []).extend(found)
    return spans


def _inside_longer(span, spans):
    """Место лежит внутри более длинного места термина с тем же словом required."""
    start, end = span
    return any(outer_start <= start and end <= outer_end and outer_end - outer_start > end - start
               for outer_start, outer_end in spans)


def required_terms(russian_text, terms):
    """[(термин, найденный фрагмент)] в порядке глоссария — термины, каждому из которых
    нужно своё вхождение слова required. Не в счёт термин внутри более длинного с тем же
    словом («восстановления» в «длительного восстановления») и термин на месте уже
    посчитанного (одинаковые термины разных разделов глоссария). Повтор термина в
    строке — один термин."""
    text = fold(plain_text(russian_text))
    matches = [(term, [found.span() for found in term.russian_pattern.finditer(text)])
               for term in terms]
    spans = _spans_by_word(matches)
    claimed, counted = set(), []
    for term, found in matches:
        own = [span for span in found if (term.required, span) not in claimed
               and not _inside_longer(span, spans[term.required])]
        if own:
            claimed.update((term.required, span) for span in own)
            counted.append((term, text[slice(*own[0])]))
    return counted


def _group_by_word(found_terms):
    grouped = {}
    for term, fragment in found_terms:
        grouped.setdefault(term.required, []).append((term, fragment))
    return grouped


def missing_words(russian_text, english_text, terms):
    """[MissingWord] в порядке глоссария: слова required, которых в переводе меньше, чем
    русских терминов, требующих их (required_terms). Вхождения слова не перекрываются."""
    english = fold(plain_text(english_text))
    found = [MissingWord(word, tuple(pairs), len(pairs[0][0].english_pattern.findall(english)))
             for word, pairs in _group_by_word(required_terms(russian_text, terms)).items()]
    return [missing for missing in found if missing.shortfall > 0]
