"""Язык сайта как сменная деталь: коды, префикс адреса, строки интерфейса.

Ядро сборки не знает языков по имени. Язык описан файлом data/locales/<код>.yml;
новый язык — новый файл, без правок в коде.
"""
import copy
from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter

import yaml
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
LOCALES_DIR = ROOT / "data" / "locales"
DEFAULT_OG_IMAGE = "/assets/img/og-default.jpg"
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
    og_image: str = DEFAULT_OG_IMAGE  # карточка превью ссылок этого языка
    llms_pages_title: str = ""  # заголовок раздела главной и политики в llms.txt; пусто — раздела нет

    def t(self, key, **params):
        """Строка интерфейса по ключу. Неизвестный ключ — ошибка сборки:
        пустое место на странице хуже упавшей сборки."""
        if key not in self.ui:
            raise KeyError(f"Нет строки интерфейса {key!r} в locales/{self.code}.yml")
        # Формат всегда, даже без параметров: строка с {title}, которому шаблон
        # не передал значение, должна уронить сборку, а не выйти на страницу скобками.
        return self.ui[key].format(**params)

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
    if not isinstance(data["url_prefix"], str):
        raise ValueError(f"{source}: url_prefix должен быть строкой (\"\" для корня), "
                         f"а не {data['url_prefix']!r}")
    return Locale(
        code=data["code"], html_lang=data["html_lang"], og_locale=data["og_locale"],
        url_prefix=data["url_prefix"].rstrip("/"), ui=_flatten(data["ui"]),
        slugs=data.get("slugs") or {}, site=data.get("site") or {},
        browser_languages=tuple(data.get("browser_languages") or ()),
        og_image=data.get("og_image", DEFAULT_OG_IMAGE),
        llms_pages_title=data.get("llms_pages_title", ""),
    )


def load_locale(code, directory=LOCALES_DIR):
    path = directory / f"{code}.yml"
    locale = parse_locale(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    if locale.code != code:
        raise ValueError(f"{path.name}: code = {locale.code!r}, ожидался {code!r}")
    return locale


_KIND_NAMES = {dict: "словарь", list: "список"}


def _kind(value):
    return _KIND_NAMES.get(type(value), "значение")


def _check_same_container(base, override, path):
    """Словарь или список из site.yml нельзя молча заменить чем-то другим
    (`business: ~` в файле языка стёр бы весь блок)."""
    if isinstance(base, (dict, list)) and type(base) is not type(override):
        raise ValueError(f"{path}: в site.yml {_kind(base)}, в языке {_kind(override)}")


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
    _check_same_container(base, override, path)
    if isinstance(base, dict) and isinstance(override, dict):
        return _merge_dicts(base, override, path)
    if isinstance(base, list) and isinstance(override, list):
        return _merge_lists(base, override, path)
    return copy.deepcopy(override)


def localized_site(site, locale):
    """site.yml с переопределениями языка: слоган, локация, названия салонов."""
    return merge_overrides(site, locale.site, f"locales/{locale.code}.yml site")


def load_privacy(code, directory=LOCALES_DIR):
    """Текст политики конфиденциальности на языке — готовый HTML."""
    path = directory / code / "privacy.html"
    if not path.exists():
        raise FileNotFoundError(f"Нет текста политики конфиденциальности языка {code}: {path}")
    return Markup(path.read_text(encoding="utf-8").rstrip("\n"))


# Строки site.yml на языке сайта (спека, раздел 5). Пути, а не имена полей:
# business.address.country — код страны, его не переводят.
SITE_TEXT_FIELDS = ("tagline", "location", "hours")
SITE_LOCATION_FIELDS = ("city", "country")


def _location_strings(places):
    return {f"locations[{index}].{field}": place[field]
            for index, place in enumerate(places or []) if isinstance(place, dict)
            for field in SITE_LOCATION_FIELDS if field in place}


def site_strings(site):
    """Строки site.yml, которые язык переводит: {путь: текст}."""
    strings = {field: site[field] for field in SITE_TEXT_FIELDS if field in site}
    strings.update(_location_strings(site.get("locations")))
    return strings


def site_problems(site, locale):
    """Каждая строка site_strings должна быть в переопределениях site файла языка."""
    provided = site_strings(locale.site)
    return [f"site {path}: нет перевода" for path in site_strings(site)
            if not (isinstance(provided.get(path), str) and provided[path].strip())]


def _params(text):
    """Имена параметров строки: «от {price}» → {"price"}. Удвоенные скобки — не параметр."""
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def _key_problem(main, other, key):
    if key not in other.ui:
        return f"ui {key}: нет перевода"
    lost = sorted(_params(main.ui[key]) - _params(other.ui[key]))
    return f"ui {key}: потерян параметр {{{lost[0]}}}" if lost else None


def ui_problems(main, other):
    """Строки интерфейса перевода против основного языка. Ключи совпадают, параметры
    русской строки сохранены: «from» вместо «from {price}» молча убрал бы цену."""
    problems = [problem for key in sorted(main.ui)
                if (problem := _key_problem(main, other, key))]
    problems += [f"ui {key}: лишний ключ — в основном языке его нет"
                 for key in sorted(set(other.ui) - set(main.ui))]
    return problems
