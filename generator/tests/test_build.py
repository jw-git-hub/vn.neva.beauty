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
        locale = load_locale("ru")
        routes = Routes([locale], taxonomy.page_ids(content), site["base_url"])
        with mock.patch("build.write", return_value=False):
            build.build_locale(site, content, prices, locale, routes, "")
        self.assertEqual(content, snapshot)


class LoadLocalesTest(unittest.TestCase):
    def test_loads_languages_listed_in_site(self):
        self.assertEqual([locale.code for locale in build.load_locales({"locales": ["ru"]})],
                         ["ru"])

    def test_missing_or_empty_list_is_error(self):
        for site in ({}, {"locales": []}, {"locales": None}):
            with self.assertRaisesRegex(ValueError, "locales"):
                build.load_locales(site)


if __name__ == "__main__":
    unittest.main()
