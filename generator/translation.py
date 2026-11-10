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
import translation_problem
from locales import LOCALES_DIR, PRIVACY_FILE, load_privacy, site_problems, ui_problems
from translation_problem import tag

CONTENT_FILE = "content.yml"
PRICES_FILE = "prices.yml"


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
    return tag(translation_problem.LOCK, translation_lock.lock_problems(locked, current))


def _data_problems(site, prices, raw_catalog, locale, main_locale):
    """Проблемы перевода вне текстов страниц: прайс, интерфейс, строки site, политика."""
    problems = tag(translation_problem.PRICES, price_translation.catalog_problems(prices, raw_catalog))
    problems += tag(translation_problem.UI, ui_problems(main_locale, locale))
    problems += tag(translation_problem.SITE, site_problems(site, locale))
    if not privacy_exists(locale.code):
        problems += tag(translation_problem.PRIVACY, [
            f"privacy: нет перевода политики (data/locales/{locale.code}/{PRIVACY_FILE})"])
    return problems


def _privacy_texts(locale, main_locale):
    """(русский html, перевод html) политики или None, если перевода нет."""
    if not privacy_exists(locale.code):
        return None
    return str(load_privacy(main_locale.code)), str(load_privacy(locale.code))


def _pair_problems(site, content, prices, merged, merge_problems, catalog, locale, main_locale):
    """Автотест пар «русская — английская строка»: числа, ссылки, теги, термины."""
    untranslated = [problem.partition(":")[0] for problem in merge_problems]
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
    merged, merge_texts = overlay.merge_translation(content, load_overlay(locale.code))
    merge_problems = tag(translation_problem.CONTENT, merge_texts)
    problems = list(merge_problems)
    raw_catalog = load_price_catalog(locale.code)
    catalog = price_translation.sanitized(raw_catalog)
    problems += _data_problems(site, prices, raw_catalog, locale, main_locale)
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
