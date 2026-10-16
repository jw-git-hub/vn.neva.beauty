"""Псевдоперевод для тестов: «EN » перед каждой русской строкой. Даёт полную накладку
и полный словарь прайса той же формы, что настоящий перевод, — сборка английского
каркаса проверяется без настоящего перевода."""
import re
from unittest import mock

import overlay
import pair_terms
import price_translation as pt
import translation_pairs
from locales import load_privacy, site_strings

PREFIX = "EN "
TERMS_LOCALE = "en"


def _missing_required_words(pseudo):
    """Слова required глоссария, которых в псевдопереводе нет. Настоящий перевод ставит
    их сам, а русский текст с приставкой без них проверку терминов не пройдёт."""
    terms = pair_terms.load_terms(TERMS_LOCALE)
    return [term.required for term, _ in pair_terms.required_terms(pseudo, terms)
            if not pair_terms.english_has(term, pseudo)]


def _glue_digits(pseudo, word):
    """«Morpheus 8» → «Morpheus8», как велит глоссарий. Склейка вместо добавления слова:
    добавленное «Morpheus8» удвоило бы число 8, и проверка чисел сочла бы это потерей."""
    spaced = re.sub(r"(?<=\D)(?=\d)", r"\\s*", re.escape(word))
    return re.sub(spaced, word, pseudo, flags=re.IGNORECASE)


def _pseudo_text(text, with_terms):
    pseudo = PREFIX + text
    if not with_terms:
        return pseudo
    for word in _missing_required_words(pseudo):
        glued = _glue_digits(pseudo, word) if any(char.isdigit() for char in word) else pseudo
        pseudo = glued if glued != pseudo else pseudo + " " + word
    return pseudo


def _pseudo_leaf(value, with_terms):
    if isinstance(value, list):
        return [_pseudo_text(line, with_terms) for line in value]
    return _pseudo_text(value, with_terms)


def pseudo_pair_patches(exceptions=()):
    """Подмены для автотеста пар: политика перевода — русская, исключения заданы (по
    умолчанию их нет). Настоящая английская политика и pair_exceptions.yml в тестах
    каркаса не участвуют."""
    russian_privacy = load_privacy("ru")
    return [mock.patch("translation.load_privacy", return_value=russian_privacy),
            mock.patch("pair_exceptions.load_exceptions", return_value=list(exceptions))]


def pseudo_content(node):
    if isinstance(node, list):
        return [pseudo_content(item) for item in node]
    result = {}
    for key, value in node.items():
        if key in overlay.TRANSLATABLE_FIELDS:
            result[key] = _pseudo_leaf(value, key not in translation_pairs.SEO_FIELDS)
        elif overlay.is_container(value):
            result[key] = pseudo_content(value)
    return result


def pseudo_prices(prices):
    catalog = {kind: {} for kind in pt.KINDS}
    for _, kind, key in pt.required_keys(prices):
        catalog[kind][key] = PREFIX + key
    return catalog


def pseudo_site(site):
    """Переопределения site для языка: «EN » перед каждой строкой site_strings."""
    strings = site_strings(site)
    result = {path: PREFIX + text for path, text in strings.items() if "[" not in path}
    result["locations"] = [{field: PREFIX + place[field] for field in ("city", "country")}
                           for place in site["locations"]]
    return result
