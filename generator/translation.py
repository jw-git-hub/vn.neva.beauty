"""Данные перевода одного языка: тексты, прайс, строки интерфейса, политика.

Основной язык (первый в site.yml, живёт в корне) — мастер: его данные берутся как
есть. Любой другой язык собирается из data/locales/<код>/: накладки content.yml,
словаря prices.yml и privacy.html. Все проблемы перевода собираются в один список:
сборка падает сразу со всем списком, и этот же список печатает translation_status.py.
"""
import copy
from dataclasses import dataclass

import yaml

import overlay
import pair_exceptions
import pair_terms
import price_translation
import translation_lock
import translation_pairs
from locales import LOCALES_DIR, load_privacy, site_problems, ui_problems

CONTENT_FILE = "content.yml"
PRICES_FILE = "prices.yml"
PRIVACY_FILE = "privacy.html"


@dataclass(frozen=True)
class LanguageData:
    content: dict
    prices: object  # price_translation.PriceTranslation


def _load_yaml(code, name, directory):
    path = directory / code / name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_overlay(code, directory=LOCALES_DIR):
    return _load_yaml(code, CONTENT_FILE, directory)


def load_price_catalog(code, directory=LOCALES_DIR):
    return _load_yaml(code, PRICES_FILE, directory)


def privacy_exists(code, directory=LOCALES_DIR):
    return (directory / code / PRIVACY_FILE).exists()


def _lock_problems(site, content, locale, main_locale):
    """Замок ставится после одобрения перевода (этап 12). Нет замка — нечего сверять."""
    locked = translation_lock.load_lock(locale.code)
    if locked is None:
        return []
    current = translation_lock.source_fingerprints(site, content, main_locale,
                                                   load_privacy(main_locale.code))
    return translation_lock.lock_problems(locked, current)


def _data_problems(site, prices, catalog, locale, main_locale):
    """Проблемы перевода вне текстов страниц: прайс, интерфейс, строки site, политика."""
    problems = price_translation.catalog_problems(prices, catalog)
    problems += ui_problems(main_locale, locale)
    problems += site_problems(site, locale)
    if not privacy_exists(locale.code):
        problems.append(f"privacy: нет перевода политики "
                        f"(data/locales/{locale.code}/{PRIVACY_FILE})")
    return problems


def _privacy_texts(locale, main_locale):
    """(русский html, перевод html) политики или None, если перевода нет."""
    if not privacy_exists(locale.code):
        return None
    return str(load_privacy(main_locale.code)), str(load_privacy(locale.code))


def _pair_problems(site, content, prices, merged, merge_problems, catalog, locale, main_locale):
    """Автотест пар «русская — английская строка»: числа, ссылки, теги, термины."""
    untranslated = {problem.partition(":")[0] for problem in merge_problems}
    pairs = (translation_pairs.content_pairs(content, merged, untranslated)
             + translation_pairs.site_pairs(site, locale.site)
             + translation_pairs.price_pairs(prices, catalog)
             + translation_pairs.privacy_pairs(_privacy_texts(locale, main_locale)))
    return translation_pairs.pair_problems(pairs, pair_terms.load_terms(locale.code),
                                           pair_exceptions.load_exceptions(locale.code))


def translation_problems(site, content, prices, locale, main_locale, check_lock=True):
    """(данные языка, все проблемы перевода). Основной язык проблем не имеет."""
    if locale.code == main_locale.code:
        return LanguageData(copy.deepcopy(content),
                            price_translation.PriceTranslation.identity()), []
    merged, problems = overlay.merge_translation(content, load_overlay(locale.code))
    catalog = load_price_catalog(locale.code)
    merge_problems = list(problems)
    problems += _data_problems(site, prices, catalog, locale, main_locale)
    problems += _pair_problems(site, content, prices, merged, merge_problems, catalog,
                               locale, main_locale)
    if check_lock:
        problems += _lock_problems(site, content, locale, main_locale)
    return LanguageData(merged, price_translation.PriceTranslation(catalog)), problems


def prepare(site, content, prices, locale, main_locale):
    """Данные языка для сборки. Перевод с проблемами — ошибка со всем списком."""
    language, problems = translation_problems(site, content, prices, locale, main_locale)
    if problems:
        raise ValueError(f"Перевод {locale.code} не готов, проблем: {len(problems)}. "
                         f"Список — python generator/translation_status.py {locale.code}\n"
                         + "\n".join(problems))
    return language
