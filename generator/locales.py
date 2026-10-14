"""Язык сайта как сменная деталь: коды, префикс адреса, строки интерфейса.

Ядро сборки не знает языков по имени. Язык описан файлом data/locales/<код>.yml;
новый язык — новый файл, без правок в коде.
"""
import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
LOCALES_DIR = ROOT / "data" / "locales"
REQUIRED_KEYS = ("code", "html_lang", "og_locale", "url_prefix", "ui")


def _flatten(tree, prefix=""):
    """Вложенный словарь строк → плоский, с ключами через точку."""
    flat = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


@dataclass(frozen=True)
class Locale:
    code: str
    html_lang: str
    og_locale: str
    url_prefix: str
    ui: dict
    slugs: dict = field(default_factory=dict)
    site: dict = field(default_factory=dict)
    browser_languages: tuple = ()

    def t(self, key, **params):
        """Строка интерфейса по ключу. Неизвестный ключ — ошибка сборки:
        пустое место на странице хуже упавшей сборки."""
        if key not in self.ui:
            raise KeyError(f"Нет строки интерфейса {key!r} в locales/{self.code}.yml")
        text = self.ui[key]
        return text.format(**params) if params else text

    def format_from(self, price):
        """«от <цена>» — единая формулировка нижней границы для всех страниц и файлов."""
        return self.t("price.from", price=price)

    def slug(self, page_id):
        """Слаг страницы в этом языке. Не задан — равен идентификатору."""
        return self.slugs.get(page_id, page_id)


def parse_locale(data, source):
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"{source}: нет обязательных ключей {missing}")
    return Locale(
        code=data["code"], html_lang=data["html_lang"], og_locale=data["og_locale"],
        url_prefix=data["url_prefix"].rstrip("/"), ui=_flatten(data["ui"]),
        slugs=data.get("slugs") or {}, site=data.get("site") or {},
        browser_languages=tuple(data.get("browser_languages") or ()),
    )


def load_locale(code, directory=LOCALES_DIR):
    path = directory / f"{code}.yml"
    locale = parse_locale(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    if locale.code != code:
        raise ValueError(f"{path.name}: code = {locale.code!r}, ожидался {code!r}")
    return locale


def _merge_dicts(base, override, path):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        key_path = f"{path}.{key}" if path else key
        if key not in base:
            raise ValueError(f"В настройках языка нет такого поля в site.yml: {key_path}")
        merged[key] = merge_overrides(base[key], value, key_path)
    return merged


def _merge_lists(base, override, path):
    both_of_dicts = all(isinstance(item, dict) for item in base + override)
    if not both_of_dicts or not base:
        return copy.deepcopy(override)
    if len(base) != len(override):
        raise ValueError(f"{path}: в site.yml {len(base)} элементов, в языке {len(override)}")
    return [merge_overrides(item, patch, f"{path}[{index}]")
            for index, (item, patch) in enumerate(zip(base, override))]


def merge_overrides(base, override, path=""):
    """Накладывает настройки языка на site.yml, не копируя его целиком.

    Словари сливаются по ключам, списки словарей — поэлементно, остальное
    заменяется. Ключ, которого нет в основе, — ошибка: опечатка в en.yml не должна
    молча добавлять лишнее поле. Исходные данные не меняются."""
    if isinstance(base, dict) and isinstance(override, dict):
        return _merge_dicts(base, override, path)
    if isinstance(base, list) and isinstance(override, list):
        return _merge_lists(base, override, path)
    return copy.deepcopy(override)


def localized_site(site, locale):
    """site.yml с переопределениями языка: слоган, локация, названия салонов."""
    return merge_overrides(site, locale.site)


def load_privacy(code, directory=LOCALES_DIR):
    """Текст политики конфиденциальности на языке — готовый HTML."""
    path = directory / code / "privacy.html"
    return Markup(path.read_text(encoding="utf-8").rstrip("\n"))
