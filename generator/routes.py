"""Таблица маршрутов: страница × язык → адрес.

Идентификатор страницы — ключ услуги или раздела из content.yml (русский слаг)
либо служебный HOME, PRIVACY, NOT_FOUND. Слаг — атрибут языка.
"""
import re

HOME = "home"
PRIVACY = "privacy"
NOT_FOUND = "404"
NOT_FOUND_FILE = "404.html"
INDEX_FILE = "index.html"
# Внутренние ссылки в текстах content.yml пишутся как href="/<идентификатор>/".
# (?!/) отсекает протокол-относительные «//host/x»: это внешний адрес, не страница.
_INTERNAL_HREF_RE = re.compile(r'href="/(?!/)([^"#?]*)([#?][^"]*)?"')
_SINGLE_QUOTED_HREF_RE = re.compile(r"href='/(?!/)")
# Слаг в адресе (спека §4): строчная латиница, цифры, дефисы между словами; без пустого
# значения, без «/» и без дефиса на краях или двойного дефиса.
_SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# Служебные идентификаторы, которые нельзя писать путём: главная — href="/".
_PATHLESS_IDS = (HOME, NOT_FOUND)


def _check_not_empty(locales):
    if not locales:
        raise ValueError("Список языков пуст: нужен хотя бы один язык")


def _check_main_in_root(locales):
    main = locales[0]
    if main.url_prefix:
        raise ValueError(f"Язык {main.code}: основной (первый) язык живёт в корне домена, "
                         f"а url_prefix = {main.url_prefix!r}")


def _check_unique_prefixes(locales):
    seen = {}
    for locale in locales:
        if locale.url_prefix in seen:
            raise ValueError(f"Язык {locale.code}: префикс {locale.url_prefix!r} "
                             f"уже занят языком {seen[locale.url_prefix]}")
        seen[locale.url_prefix] = locale.code


def _check_unique_html_langs(locales):
    seen = {}
    for locale in locales:
        if locale.html_lang in seen:
            raise ValueError(f"Язык {locale.code}: html_lang {locale.html_lang!r} "
                             f"уже у языка {seen[locale.html_lang]}, hreflang не различит их")
        seen[locale.html_lang] = locale.code


def _find_x_default(locales, code):
    for locale in locales:
        if locale.code == code:
            return locale
    raise ValueError(f"x_default_locale = {code!r}: такого языка нет среди "
                     f"{[locale.code for locale in locales]}")


def _check_slug_keys(locales, page_ids):
    for locale in locales:
        for page_id in locale.slugs:
            if page_id not in page_ids:
                raise ValueError(f"Язык {locale.code}: слаг для неизвестной страницы {page_id!r}")
            if page_id in _PATHLESS_IDS:
                raise ValueError(f"Язык {locale.code}: у страницы {page_id!r} нет собственного "
                                 f"слага — адрес главной и 404 задан префиксом языка")


def _check_slug_format(locales):
    for locale in locales:
        for page_id, slug in locale.slugs.items():
            if not (isinstance(slug, str) and _SLUG_RE.fullmatch(slug)):
                raise ValueError(f"Язык {locale.code}: слаг {slug!r} страницы {page_id!r} "
                                 f"должен быть из строчной латиницы, цифр и дефисов")


def _check_unique_slugs(locales, page_ids):
    for locale in locales:
        owners = {}
        for page_id in sorted(page_ids - {HOME, NOT_FOUND}):
            slug = locale.slug(page_id)
            if slug in owners:
                raise ValueError(f"Язык {locale.code}: слаг {slug!r} у страниц "
                                 f"{owners[slug]!r} и {page_id!r}")
            owners[slug] = page_id


class Routes:
    def __init__(self, locales, page_ids, base_url, x_default_locale, base_path=""):
        page_ids = set(page_ids) | {HOME, PRIVACY, NOT_FOUND}
        _check_not_empty(locales)
        _check_main_in_root(locales)
        _check_unique_prefixes(locales)
        _check_unique_html_langs(locales)
        _check_slug_keys(locales, page_ids)
        _check_slug_format(locales)
        _check_unique_slugs(locales, page_ids)
        self._locales = list(locales)
        self._x_default_locale = _find_x_default(locales, x_default_locale)
        self._page_ids = page_ids
        self._base_url = base_url
        self._base_path = base_path.rstrip("/")

    @property
    def locales(self):
        """Языки сайта в порядке site.yml."""
        return list(self._locales)

    def path(self, locale, page_id):
        """Путь страницы от корня сайта с префиксом языка: «/en/laser-hair-removal/»."""
        if page_id not in self._page_ids:
            raise ValueError(f"Неизвестная страница {page_id!r}")
        if page_id == HOME:
            return f"{locale.url_prefix}/"
        if page_id == NOT_FOUND:
            return f"{locale.url_prefix}/{NOT_FOUND_FILE}"
        return f"{locale.url_prefix}/{locale.slug(page_id)}/"

    def href(self, locale, page_id):
        """Ссылка для разметки: путь с base_path (превью по подпути)."""
        return self._base_path + self.path(locale, page_id)

    def not_found_redirects(self, locale):
        """Куда корневая 404 отправляет чужие языки: у основного языка — по префиксу и
        странице 404 каждого неосновного; у неосновного (своя 404 лежит у него) — никуда."""
        if locale.code != self._locales[0].code:
            return []
        return [{"prefix": f"{self._base_path}{other.url_prefix}/",
                 "page": self.href(other, NOT_FOUND)}
                for other in self._locales[1:]]

    def url(self, locale, page_id):
        """Абсолютный адрес для canonical, hreflang, sitemap и JSON-LD."""
        return self._base_url + self.path(locale, page_id)

    def out_file(self, locale, page_id):
        """Файл страницы относительно папки сайта."""
        path = self.path(locale, page_id).lstrip("/")
        return path if path.endswith(".html") else path + INDEX_FILE

    def alternates(self, page_id):
        """Абсолютные адреса страницы во всех языках: {html_lang: адрес}.
        Ключ — html_lang, потому что именно он нужен атрибуту hreflang."""
        return {locale.html_lang: self.url(locale, page_id) for locale in self._locales}

    def x_default(self, page_id):
        """Адрес для hreflang="x-default": язык из site.yml (x_default_locale).
        Не «первый язык»: по спеке x-default — английская версия, а корень домена
        может оставаться за русским."""
        return self.url(self._x_default_locale, page_id)

    def localize_links(self, locale, html):
        """Переводит внутренние ссылки текста в адреса языка страницы.
        Неизвестный идентификатор — ошибка сборки, а не битая ссылка на сайте;
        так же и ссылка в одинарных кавычках: регулярка её не увидит, и в чужом
        языке молча остался бы русский адрес."""
        if _SINGLE_QUOTED_HREF_RE.search(html):
            raise ValueError("Внутренняя ссылка в одинарных кавычках: пишите href=\"/...\"")
        return _INTERNAL_HREF_RE.sub(lambda match: self._localize_match(locale, match), html)

    def _localize_match(self, locale, match):
        path_id = match.group(1).strip("/")
        if path_id in _PATHLESS_IDS:
            raise ValueError(f"Служебный идентификатор {path_id!r} записан путём: "
                             f"главная пишется href=\"/\"")
        return f'href="{self.href(locale, path_id or HOME)}{match.group(2) or ""}"'
