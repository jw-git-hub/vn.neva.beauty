import copy
import re
import unittest
import urllib.parse
from dataclasses import replace
from unittest import mock

from markupsafe import Markup

import build
import contacts
import pages
import taxonomy
from locales import load_locale
from routes import Routes
from tests.pseudo_translation import pseudo_content, pseudo_prices, pseudo_site


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
            build.build_locale(site, content, prices, locale, routes, "", locale)
        self.assertEqual(content, snapshot)
        self.assertEqual(site, site_snapshot)
        self.assertEqual(prices, prices_snapshot)


def build_pages_of_test_english(x_default_locale="en", ui_overrides=None):
    """Собирает страницы тестового английского (префикс /en, псевдоперевод «EN …»)
    рядом с русским, не пиша файлов. Возвращает {путь страницы: html}."""
    site, content, prices = build.load()
    russian = load_locale("ru")
    english = replace(russian, code="en", html_lang="en", og_locale="en_US", url_prefix="/en",
                      ui={**russian.ui, **(ui_overrides or {})},
                      site=pseudo_site(site))
    routes = Routes([russian, english], taxonomy.page_ids(content), site["base_url"],
                    x_default_locale)
    written = {}
    with mock.patch("build.write", side_effect=lambda path, html: written.update({path: html})), \
            mock.patch("build.load_privacy", return_value=Markup("<p>Privacy</p>")), \
            mock.patch("translation.load_overlay", return_value=pseudo_content(content)), \
            mock.patch("translation.load_price_catalog", return_value=pseudo_prices(prices)), \
            mock.patch("translation.privacy_exists", return_value=True):
        build.build_locale(site, content, prices, english, routes, "", russian)
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
        head = self.pages["en/privacy/index.html"].split("</head>")[0]
        self.assertIn('hreflang="en"', head)
        self.assertNotIn('hreflang="ru"', head)


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


WHATSAPP_HREF_RE = re.compile(r'href="(https://wa\.me/[^"]*)"')
TELEGRAM_HREF_RE = re.compile(r'href="(https://t\.me/[^"]*)"')


def contact_texts(html, href_re=WHATSAPP_HREF_RE):
    """Тексты обращения во всех ссылках канала на странице. По умолчанию — WhatsApp:
    у него текст есть всегда, а Telegram зависит от флага telegram_prefill."""
    return {urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("text", [""])[0]
            for url in href_re.findall(html)}


class ContactLinksInBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site, content, prices = build.load()
        locale = load_locale("ru")
        routes = Routes([locale], taxonomy.page_ids(content), site["base_url"], "ru")
        written = {}
        with mock.patch("build.write",
                        side_effect=lambda path, html: written.update({path: html})):
            build.build_locale(site, content, prices, locale, routes, "", locale)
        cls.pages = {path.relative_to(build.OUT).as_posix(): html
                     for path, html in written.items()}

    def test_service_page_links_carry_service_title(self):
        self.assertEqual(contact_texts(self.pages["lpg-massazh/index.html"]),
                         {"Здравствуйте! Хочу записаться на: LPG-массаж"})

    def test_telegram_links_follow_prefill_flag(self):
        prefilled = "telegram" in contacts.prefill_channels(build.load()[0]["contacts"])
        expected = "Здравствуйте! Хочу записаться на: LPG-массаж" if prefilled else ""
        self.assertEqual(contact_texts(self.pages["lpg-massazh/index.html"], TELEGRAM_HREF_RE),
                         {expected})

    def test_home_links_carry_generic_text(self):
        self.assertEqual(contact_texts(self.pages["index.html"]),
                         {"Здравствуйте! Хочу записаться"})

    def test_every_contact_link_is_tagged(self):
        html = self.pages["lpg-massazh/index.html"]
        links = re.findall(r'<a [^>]*href="https://(?:wa\.me|t\.me|instagram\.com)/[^>]*>', html)
        self.assertTrue(links)
        for link in links:
            self.assertIn("data-contact=", link)
            self.assertIn("data-place=", link)

    def test_faq_links_are_tagged_and_carry_text(self):
        html = self.pages["lpg-massazh/index.html"]
        self.assertIn('data-place="faq"', html)
        faq_links = re.findall(r'<a href="(https://wa\.me/[^"]*)" data-contact="whatsapp" '
                               r'data-place="faq"', html)
        self.assertTrue(faq_links)
        self.assertEqual(contact_texts(" ".join(f'href="{url}"' for url in faq_links)),
                         {"Здравствуйте! Хочу записаться на: LPG-массаж"})

    def test_russian_page_has_no_language_note(self):
        self.assertNotIn('hreflang="ru" ', self.pages["index.html"].split("<body>")[1])

    def test_metrika_reports_contact_with_page_id(self):
        html = self.pages["lpg-massazh/index.html"]
        self.assertIn('var PAGE = "lpg-massazh";', html)
        self.assertIn('"reachGoal", "contact"', html)
        self.assertIn('d.addEventListener("click", reportContact);', html)


class MessengerPlaceholderTest(unittest.TestCase):
    def test_messenger_placeholder_outside_href_is_error(self):
        """{whatsapp} вне href="…" дал бы голый адрес без текста и меток — мимо contacts.py."""
        with self.assertRaises(ValueError):
            pages.fill_tokens("пишите {whatsapp}", pages.content_tokens())


class TranslatedEnglishPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build_pages_of_test_english()

    def test_price_list_uses_translated_names(self):
        html = self.pages["en/lpg-massazh/index.html"]
        self.assertIn("EN LPG Массаж - Тело", html)

    def test_combo_survives_translation(self):
        """Комбо узнаётся по русскому «КОМБО» до перевода: в английском прайсе это карточка."""
        html = self.pages["en/lazernaya-epilyaciya/index.html"]
        self.assertIn('<div class="combo__name">EN КОМБО 1', html)

    def test_popular_card_shows_translated_name(self):
        self.assertIn('<span class="popular-card__name">EN LPG Массаж - Тело</span>',
                      self.pages["en/index.html"])

    def test_page_text_is_translated(self):
        self.assertIn("<h1>EN LPG-массаж</h1>", self.pages["en/lpg-massazh/index.html"])

    def test_samui_link_says_site_is_russian(self):
        html = self.pages["en/index.html"]
        self.assertIn('href="https://th.neva.beauty" hreflang="ru"', html)
        self.assertIn("сайт на русском", html)  # псевдоперевод берёт строки интерфейса русского


class EnglishHeadingTemplateTest(unittest.TestCase):
    def test_repeated_h2_can_carry_service_title(self):
        """Спека, раздел 12: английские «Prices», «See also», «Why it works» собираются
        с названием услуги, иначе h2 повторяются на всех страницах услуг."""
        pages = build_pages_of_test_english(ui_overrides={
            "service.price_title": "Prices — {title}",
            "service.related_title": "See also — {title}",
            "service.benefits_title": "Why it works — {title}"})
        html = pages["en/lpg-massazh/index.html"]
        for heading in ("Prices", "See also"):
            self.assertIn(f"<h2>{heading} — EN LPG-массаж</h2>", html)
        self.assertNotIn("{title}", html)
