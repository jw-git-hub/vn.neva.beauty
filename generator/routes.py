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
_INTERNAL_HREF_RE = re.compile(r'href="/([^"#?]*)([#?][^"]*)?"')


class Routes:
    def __init__(self, locales, page_ids, base_url, base_path=""):
        self._locales = {locale.code: locale for locale in locales}
        self._page_ids = set(page_ids) | {HOME, PRIVACY, NOT_FOUND}
        self._base_url = base_url
        self._base_path = base_path

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

    def url(self, locale, page_id):
        """Абсолютный адрес для canonical, hreflang, sitemap и JSON-LD."""
        return self._base_url + self.path(locale, page_id)

    def out_file(self, locale, page_id):
        """Файл страницы относительно папки сайта."""
        path = self.path(locale, page_id).lstrip("/")
        return path if path.endswith(".html") else path + INDEX_FILE

    def alternates(self, page_id):
        """Абсолютные адреса страницы во всех языках: {код: адрес}."""
        return {code: self.url(locale, page_id) for code, locale in self._locales.items()}

    def localize_links(self, locale, html):
        """Переводит внутренние ссылки текста в адреса языка страницы.
        Неизвестный идентификатор — ошибка сборки, а не битая ссылка на сайте."""
        def replace(match):
            page_id = match.group(1).strip("/") or HOME
            return f'href="{self.href(locale, page_id)}{match.group(2) or ""}"'
        return _INTERNAL_HREF_RE.sub(replace, html)
