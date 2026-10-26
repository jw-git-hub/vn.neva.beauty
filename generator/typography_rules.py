"""Правила неразрывных пробелов для русского и английского текста.

Каждое правило — пара (регулярное выражение, замена) для одного куска видимого
текста между тегами. Списки слов — данные языка: русские правила в английский текст
не попадают и наоборот. Код, который применяет правила, — typography.py.
"""
import re

NO_BREAK_SPACE = " "
JOINED_SPACE = rf"\1{NO_BREAK_SPACE}"

# Слово не продолжается ни буквой, ни дефисом: «по-русски» и «e-mail» не трогаем.
NOT_AFTER_WORD = r"(?<![\w\-])"
NOT_BEFORE_WORD = r"(?![\w\-])"

# Группы тысяч: «2 500 000 đ» не рвётся посередине числа.
THOUSANDS_GROUPS = re.compile(r"(?<![\w.,])(\d{1,3}(?: \d{3})+)(?!\d)")
# Тире (и дефис с пробелами, которым прайс пишет «Эндосфера-терапия - Тело») с пробелом
# перед ним не начинает строку; после тире строку рвать можно.
SPACE_BEFORE_DASH = re.compile(r" (?=[—–-](?:\s|$))")

# Единицы, которые не отрываются от числа. «đ» и «%» одинаковы для обоих языков.
COMMON_UNITS = ("đ", "VND", "%")
RUSSIAN_UNITS = ("сеанс\\w*", "процедур\\w*", "мин\\w*", "час\\w*", "дн\\w*", "недел\\w*",
                 "мес\\w*", "лет", "год\\w*", "раз", "раза", "см", "мм", "мл", "кг")
ENGLISH_UNITS = ("sessions?", "treatments?", "minutes?", "mins?", "hours?", "days?", "weeks?",
                 "months?", "years?", "cm", "mm", "ml", "kg")

# Слова, которые не должны оставаться последними в строке: прижимаются к следующему слову.
RUSSIAN_LEADING = ("в", "во", "к", "ко", "с", "со", "у", "о", "об", "и", "а", "но", "да", "я",
                   "на", "по", "за", "из", "от", "до", "не", "ни", "для", "при", "без", "над",
                   "под", "про", "или", "как", "что")
ENGLISH_LEADING = ("a", "an", "the", "in", "on", "at", "to", "of", "by", "for", "and", "or",
                   "but", "as", "if", "so", "up", "is", "i", "with", "from", "&amp;")
# Частицы, которые не должны начинать строку: прижимаются к предыдущему слову.
RUSSIAN_TRAILING = ("бы", "же", "ли")


def _alternatives(words):
    return "|".join(words)


def _leading_words_rule(words):
    """Короткое слово + пробел → слово + неразрывный пробел."""
    return re.compile(rf"{NOT_AFTER_WORD}({_alternatives(words)}) ", re.IGNORECASE), JOINED_SPACE


def _trailing_particles_rule(words):
    """Слово + пробел + частица → слово + неразрывный пробел + частица."""
    pattern = rf"(?<=[\w»)]) (?=(?:{_alternatives(words)}){NOT_BEFORE_WORD})"
    return re.compile(pattern, re.IGNORECASE), NO_BREAK_SPACE


def _number_binds_rule(words):
    """Число + пробел + одно из слов → число не отрывается от слова."""
    pattern = rf"(?<=\d) (?=(?:{_alternatives(words)}){NOT_BEFORE_WORD})"
    return re.compile(pattern, re.IGNORECASE), NO_BREAK_SPACE


def _thousands_rule():
    return THOUSANDS_GROUPS, lambda match: match.group(1).replace(" ", NO_BREAK_SPACE)


def _dash_rule():
    return SPACE_BEFORE_DASH, NO_BREAK_SPACE


RULES_BY_LANGUAGE = {
    "ru": (_thousands_rule(), _number_binds_rule(RUSSIAN_UNITS + COMMON_UNITS),
           _number_binds_rule(RUSSIAN_LEADING), _dash_rule(),
           _leading_words_rule(RUSSIAN_LEADING), _trailing_particles_rule(RUSSIAN_TRAILING)),
    "en": (_thousands_rule(), _number_binds_rule(ENGLISH_UNITS + COMMON_UNITS),
           _number_binds_rule(ENGLISH_LEADING), _dash_rule(),
           _leading_words_rule(ENGLISH_LEADING)),
}
