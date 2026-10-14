import copy
import unittest
from unittest import mock

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
