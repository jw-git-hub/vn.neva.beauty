"""Автотест пар «русская — английская строка»: числа, плейсхолдеры, ссылки, теги, термины.

Переводчик может потерять «6 сеансов», сломать ссылку, пропустить абзац или заменить
«LPG-массаж» общим словом — глазом это в тысяче строк не найти. Каждая пара проверяется
механически, а находки входят в общий список проблем перевода (translation.py): сборка
падает, translation_status.py их показывает. Проблемы с адресом строки — как у замка
и накладки, сообщения по-русски. Отступления — pair_exceptions.yml (pair_exceptions.py).
Плейсхолдеры строк интерфейса проверяет locales.ui_problems, цифры перед đ — прайс.
"""
import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup

import overlay
import pair_exceptions
import pair_terms
import price_translation
from locales import site_strings
from pair_exceptions import Finding

CHECK_NUMBERS, CHECK_PLACEHOLDERS, CHECK_LINKS = "numbers", "placeholders", "links"
CHECK_TAGS, CHECK_TERMS = "tags", pair_exceptions.TERMS_CHECK
CHECKS = (CHECK_NUMBERS, CHECK_PLACEHOLDERS, CHECK_LINKS, CHECK_TAGS, CHECK_TERMS)

CHECKS_OF_PAGE = CHECKS
CHECKS_OF_SITE = (CHECK_NUMBERS, CHECK_PLACEHOLDERS)
CHECKS_OF_PRICE = (CHECK_NUMBERS,)
CHECKS_OF_PRIVACY = (CHECK_LINKS, CHECK_TAGS)
SEO_FIELDS = ("seo_title", "seo_desc")  # обещания там намеренно опущены: терминов нет
PRICE_KINDS = ("sections", "names")  # описания прайса уже под масками
PRIVACY_PATH = "privacy"

NUMBER_SEPARATORS = "    "  # пробел, неразрывный, узкий неразрывный, тонкий
NUMBER_RE = re.compile(rf"\d+(?:[{NUMBER_SEPARATORS}]\d{{3}}(?!\d))*(?:[.,]\d+)?")
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
DISCLAIMER_LANGUAGE = "ru"  # абзац-оговорка английской политики ссылается на русскую
BLOCK_TAGS = ("p", "li", "td", "th", "dd", "blockquote")  # оговорка — этот элемент целиком


@dataclass(frozen=True)
class Pair:
    path: str
    ru: str
    en: str  # None — перевода нет, это уже названо другой проверкой
    checks: tuple
    is_document: bool = False  # политика: теги сравниваются по порядку во всём документе


def _page_checks(path):
    return CHECKS_OF_PAGE if path.rpartition(".")[2] not in SEO_FIELDS \
        else tuple(check for check in CHECKS_OF_PAGE if check != CHECK_TERMS)


def _text_or_none(value):
    return value if isinstance(value, str) and value.strip() else None


def content_pairs(content, merged, untranslated_paths):
    """Тексты страниц: путь как у overlay.source_strings. Непереведённое — без пары."""
    russian, english = overlay.source_strings(content), overlay.source_strings(merged)
    return [Pair(path, text, None if path in untranslated_paths else english.get(path),
                 _page_checks(path)) for path, text in russian.items()]


def site_pairs(site, locale_site):
    english = site_strings(locale_site)
    return [Pair(f"site {path}", text, _text_or_none(english.get(path)), CHECKS_OF_SITE)
            for path, text in site_strings(site).items()]


def _price_label(kind, key, owner=None):
    return f"prices {kind} «{key}»" + (f" ({owner})" if owner else "")


def _price_dictionaries(catalog):
    """[(услуга или None, вид, словарь)] — общие словари и переопределения услуг."""
    found = [(None, kind, catalog.get(kind) or {}) for kind in PRICE_KINDS]
    for service_id, kinds in (catalog.get(price_translation.OVERRIDES) or {}).items():
        found += [(service_id, kind, (kinds or {}).get(kind) or {}) for kind in PRICE_KINDS]
    return found


def _translated_price_pairs(catalog):
    return {_price_label(kind, key, owner): Pair(_price_label(kind, key, owner), key,
                                                 _text_or_none(value), CHECKS_OF_PRICE)
            for owner, kind, dictionary in _price_dictionaries(catalog)
            for key, value in dictionary.items()}


def price_pairs(prices, catalog):
    """Разделы и названия прайса: ключ словаря — русская строка, значение — перевод.
    Строки прайса без перевода тоже становятся парами — без английской стороны."""
    pairs = _translated_price_pairs(catalog)
    for _, kind, key in price_translation.required_keys(prices):
        label = _price_label(kind, key)
        if kind in PRICE_KINDS:
            pairs.setdefault(label, Pair(label, key, None, CHECKS_OF_PRICE))
    return list(pairs.values())


def privacy_pairs(privacy):
    """Политика целиком: (русский html, английский html) или None, если перевода нет."""
    if privacy is None:
        return []
    return [Pair(PRIVACY_PATH, privacy[0], privacy[1], CHECKS_OF_PRIVACY, is_document=True)]


def _numbers_of(text):
    plain = PLACEHOLDER_RE.sub(" ", pair_terms.plain_text(text))
    return [re.sub(f"[{NUMBER_SEPARATORS}]", "", raw).replace(",", ".")
            for raw in NUMBER_RE.findall(plain)]


def _show(items):
    return "[" + ", ".join(items) + "]"


def _by_value(numbers):
    return sorted(numbers, key=float)


def _numbers(pair, terms):
    russian, english = _numbers_of(pair.ru), _numbers_of(pair.en)
    if Counter(russian) == Counter(english):
        return []
    message = (f"числа: в русском {_show(_by_value(russian))}, "
               f"в переводе {_show(_by_value(english))}")
    return [Finding(pair.path, CHECK_NUMBERS, message)]


def _placeholders(pair, terms):
    russian, english = PLACEHOLDER_RE.findall(pair.ru), PLACEHOLDER_RE.findall(pair.en)
    if Counter(russian) == Counter(english):
        return []
    message = (f"плейсхолдеры: в русском {_show(sorted(russian))}, "
               f"в переводе {_show(sorted(english))}")
    return [Finding(pair.path, CHECK_PLACEHOLDERS, message)]


def _document(html_text):
    """Разбор html без абзаца-оговорки: элемента, в котором ссылка hreflang="ru"."""
    soup = BeautifulSoup(html_text, "html.parser")
    while (link := soup.find("a", hreflang=DISCLAIMER_LANGUAGE)) is not None:
        (link.find_parent(BLOCK_TAGS) or link).decompose()
    return soup


def _difference(russian, english):
    lost, extra = Counter(russian) - Counter(english), Counter(english) - Counter(russian)
    parts = [f"нет в переводе {_show(sorted(lost.elements()))}"] if lost else []
    return parts + ([f"лишнее в переводе {_show(sorted(extra.elements()))}"] if extra else [])


def _links(pair, terms):
    hrefs = [[link["href"] for link in _document(text).find_all("a", href=True)]
             for text in (pair.ru, pair.en)]
    parts = _difference(*hrefs)
    return [Finding(pair.path, CHECK_LINKS, "ссылки: " + "; ".join(parts))] if parts else []


def _tag_names(text):
    return [tag.name for tag in _document(text).find_all(True)]


def _tag_at(names, index):
    return f"<{names[index]}>" if index < len(names) else "конец документа"


def _sequence_message(russian, english):
    index = next((i for i, (a, b) in enumerate(zip(russian, english)) if a != b),
                 min(len(russian), len(english)))
    return (f"теги: порядок расходится на позиции {index + 1} (в русском {_tag_at(russian, index)}, "
            f"в переводе {_tag_at(english, index)}); всего тегов в русском {len(russian)}, "
            f"в переводе {len(english)}")


def _tags(pair, terms):
    russian, english = _tag_names(pair.ru), _tag_names(pair.en)
    if pair.is_document:
        message = _sequence_message(russian, english) if russian != english else None
    else:
        parts = _difference(russian, english)
        message = "теги: " + "; ".join(parts) if parts else None
    return [Finding(pair.path, CHECK_TAGS, message)] if message else []


def _terms(pair, terms):
    return [Finding(pair.path, CHECK_TERMS,
                    f"термины: в русском «{fragment}» (термин «{term.ru}»), "
                    f"в переводе нет «{term.required}»", term.required)
            for term, fragment in pair_terms.required_terms(pair.ru, terms)
            if not pair_terms.english_has(term, pair.en)]


CHECKERS = {CHECK_NUMBERS: _numbers, CHECK_PLACEHOLDERS: _placeholders, CHECK_LINKS: _links,
            CHECK_TAGS: _tags, CHECK_TERMS: _terms}


def pair_findings(pair, terms):
    found = []
    for check in pair.checks:
        found += CHECKERS[check](pair, terms)
    return found


def pair_problems(pairs, terms, exceptions):
    """Проблемы всех пар: «<путь>: <что не так>» плюс проблемы самих исключений."""
    findings = [finding for pair in pairs if pair.en is not None
                for finding in pair_findings(pair, terms)]
    kept, problems = pair_exceptions.apply_exceptions(
        findings, exceptions, CHECKS, {pair.path for pair in pairs},
        {pair.path for pair in pairs if pair.en is not None})
    return [f"{finding.path}: {finding.message}" for finding in kept] + problems
