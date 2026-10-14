import copy
import unittest
from dataclasses import replace
from unittest import mock

from markupsafe import Markup

import build
import taxonomy
from locales import load_locale
from routes import Routes


class BuildLocaleIsolationTest(unittest.TestCase):
    def test_shared_content_is_not_mutated(self):
        """Сборка языка подставляет цены и ссылки в тексты. Следующий язык должен
        получить исходный контент, а не уже раскрытые плейсхолдеры предыдущего."""
        site, content, prices = build.load()
        snapshot = copy.deepcopy(content)
        site_snapshot, prices_snapshot = copy.deepcopy(site), copy.deepcopy(prices)
        locale = load_locale("ru")
        routes = Routes([locale], taxonomy.page_ids(content), site["base_url"], "ru")
        with mock.patch("build.write", return_value=False):
            build.build_locale(site, content, prices, locale, routes, "")
        self.assertEqual(content, snapshot)
        self.assertEqual(site, site_snapshot)
        self.assertEqual(prices, prices_snapshot)


def build_pages_of_test_english(x_default_locale="en"):
    """Собирает страницы тестового английского (префикс /en) рядом с русским, не пиша файлов.
    Возвращает {путь страницы: html}."""
    site, content, prices = build.load()
    russian = load_locale("ru")
    english = replace(russian, code="en", html_lang="en", og_locale="en_US", url_prefix="/en")
    routes = Routes([russian, english], taxonomy.page_ids(content), site["base_url"],
                    x_default_locale)
    written = {}
    with mock.patch("build.write", side_effect=lambda path, html: written.update({path: html})), \
            mock.patch("build.load_privacy", return_value=Markup("<p>Privacy</p>")):
        build.build_locale(site, content, prices, english, routes, "")
    return {path.relative_to(build.OUT).as_posix(): html for path, html in written.items()}


class HreflangInBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build_pages_of_test_english()

    def test_indexable_page_lists_every_language_and_x_default(self):
        html = self.pages["en/index.html"]
        for hreflang, address in (("ru", "https://vn.neva.beauty/"),
                                  ("en", "https://vn.neva.beauty/en/"),
                                  ("x-default", "https://vn.neva.beauty/en/")):
            self.assertIn(f'<link rel="alternate" hreflang="{hreflang}" href="{address}">', html)

    def test_service_page_declares_its_own_language(self):
        html = self.pages["en/privacy/index.html"]
        self.assertIn('hreflang="en"', html)
        self.assertNotIn('hreflang="ru"', html)


class LoadLocalesTest(unittest.TestCase):
    def test_loads_languages_listed_in_site(self):
        self.assertEqual([locale.code for locale in build.load_locales({"locales": ["ru"]})],
                         ["ru"])

    def test_missing_or_empty_list_is_error(self):
        for site in ({}, {"locales": []}, {"locales": None}):
            with self.assertRaisesRegex(ValueError, "locales"):
                build.load_locales(site)


class LoadXDefaultLocaleTest(unittest.TestCase):
    def test_returns_code_from_site(self):
        self.assertEqual(build.load_x_default_locale({"x_default_locale": "en"}), "en")

    def test_missing_key_is_error(self):
        for site in ({}, {"x_default_locale": None}, {"x_default_locale": ""}):
            with self.assertRaisesRegex(ValueError, "x_default_locale"):
                build.load_x_default_locale(site)


if __name__ == "__main__":
    unittest.main()
