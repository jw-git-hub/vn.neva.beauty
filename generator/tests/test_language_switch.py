import unittest

import build
import taxonomy
from language_switch import language_links
from locales import load_locale
from routes import Routes


class LanguageLinksTest(unittest.TestCase):
    def setUp(self):
        _, content, _ = build.load()
        self.ru, self.en = load_locale("ru"), load_locale("en")
        self.page_ids = taxonomy.page_ids(content)
        self.routes = Routes([self.ru, self.en], self.page_ids, "https://vn.neva.beauty", "en")

    def test_service_page_links_in_site_order(self):
        russian, english = language_links(self.routes, self.ru, "lpg-massazh")
        self.assertEqual((russian.code, russian.href, russian.is_current), ("ru", "/lpg-massazh/", True))
        self.assertEqual((english.code, english.href, english.is_current, english.html_lang),
                         ("en", "/en/lpg-massage/", False, "en"))

    def test_labels_come_from_target_language(self):
        russian, english = language_links(self.routes, self.ru, "home")
        self.assertEqual((english.short, english.name, english.label),
                         ("EN", "English", "EN — English version"))
        self.assertEqual((russian.short, russian.name, russian.label),
                         ("RU", "Русский", "RU — русская версия"))
        self.assertEqual(english.href, "/en/")

    def test_base_path_is_prefixed(self):
        routes = Routes([self.ru, self.en], self.page_ids, "https://vn.neva.beauty", "en",
                        "/vn.neva.beauty")
        self.assertEqual(language_links(routes, self.en, "home")[0].href, "/vn.neva.beauty/")
