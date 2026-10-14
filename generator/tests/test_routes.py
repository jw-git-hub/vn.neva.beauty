import unittest

from locales import parse_locale
from routes import HOME, NOT_FOUND, PRIVACY, Routes


def make_locale(code, prefix, slugs=None, html_lang=None):
    return parse_locale({"code": code, "html_lang": html_lang or code, "og_locale": code,
                         "url_prefix": prefix, "ui": {}, "slugs": slugs or {}}, f"{code}.yml")


RU = make_locale("ru", "")
EN = make_locale("en", "/en", {"lpg-massazh": "lpg-massage"})
PAGE_IDS = ["lpg-massazh", "korrekciya-figury"]
BASE_URL = "https://vn.neva.beauty"


def make_routes(base_path=""):
    return Routes([RU, EN], PAGE_IDS, BASE_URL, base_path)


def build_routes(locales, base_path=""):
    return Routes(locales, PAGE_IDS, BASE_URL, base_path)


class ConstructorChecksTest(unittest.TestCase):
    def test_empty_locale_list_is_error(self):
        with self.assertRaisesRegex(ValueError, "языков"):
            build_routes([])

    def test_first_locale_must_live_in_root(self):
        with self.assertRaisesRegex(ValueError, "ru.*корне"):
            build_routes([make_locale("ru", "/ru"), EN])

    def test_url_prefixes_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "de.*префикс.*en"):
            build_routes([RU, EN, make_locale("de", "/en")])

    def test_slug_of_unknown_page_is_error(self):
        typo = make_locale("en", "/en", {"lpg-masazh": "lpg-massage"})
        with self.assertRaisesRegex(ValueError, "en.*lpg-masazh"):
            build_routes([RU, typo])

    def test_slugs_must_be_unique_within_language(self):
        clash = make_locale("en", "/en", {"lpg-massazh": "body", "korrekciya-figury": "body"})
        with self.assertRaisesRegex(ValueError, "en.*body"):
            build_routes([RU, clash])

    def test_slug_equal_to_id_of_another_page_is_error(self):
        clash = make_locale("en", "/en", {"lpg-massazh": "korrekciya-figury"})
        with self.assertRaisesRegex(ValueError, "en.*korrekciya-figury"):
            build_routes([RU, clash])

    def test_html_lang_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "html_lang"):
            build_routes([RU, make_locale("en", "/en", html_lang="ru")])

    def test_base_path_loses_trailing_slash(self):
        routes = build_routes([RU], "/vn.neva.beauty/")
        self.assertEqual(routes.href(RU, HOME), "/vn.neva.beauty/")


class PathTest(unittest.TestCase):
    def test_home(self):
        self.assertEqual(make_routes().path(RU, HOME), "/")
        self.assertEqual(make_routes().path(EN, HOME), "/en/")

    def test_page_uses_locale_slug(self):
        self.assertEqual(make_routes().path(RU, "lpg-massazh"), "/lpg-massazh/")
        self.assertEqual(make_routes().path(EN, "lpg-massazh"), "/en/lpg-massage/")

    def test_page_without_own_slug_keeps_id(self):
        self.assertEqual(make_routes().path(EN, "korrekciya-figury"), "/en/korrekciya-figury/")

    def test_service_pages(self):
        self.assertEqual(make_routes().path(RU, PRIVACY), "/privacy/")
        self.assertEqual(make_routes().path(EN, NOT_FOUND), "/en/404.html")

    def test_unknown_page_is_error(self):
        with self.assertRaisesRegex(ValueError, "net-takoy"):
            make_routes().path(RU, "net-takoy")


class AddressTest(unittest.TestCase):
    def test_href_carries_base_path(self):
        routes = make_routes("/vn.neva.beauty")
        self.assertEqual(routes.href(RU, "lpg-massazh"), "/vn.neva.beauty/lpg-massazh/")

    def test_url_is_absolute(self):
        self.assertEqual(make_routes().url(EN, "lpg-massazh"),
                         "https://vn.neva.beauty/en/lpg-massage/")

    def test_out_file(self):
        routes = make_routes()
        self.assertEqual(routes.out_file(RU, HOME), "index.html")
        self.assertEqual(routes.out_file(RU, "lpg-massazh"), "lpg-massazh/index.html")
        self.assertEqual(routes.out_file(EN, "lpg-massazh"), "en/lpg-massage/index.html")
        self.assertEqual(routes.out_file(RU, NOT_FOUND), "404.html")
        self.assertEqual(routes.out_file(EN, NOT_FOUND), "en/404.html")

    def test_alternates_cover_every_locale(self):
        self.assertEqual(make_routes().alternates("lpg-massazh"), {
            "ru": "https://vn.neva.beauty/lpg-massazh/",
            "en": "https://vn.neva.beauty/en/lpg-massage/",
        })


class HreflangTest(unittest.TestCase):
    def test_alternates_are_keyed_by_html_lang(self):
        en_us = make_locale("en", "/en", {"lpg-massazh": "lpg-massage"}, html_lang="en-US")
        self.assertEqual(build_routes([RU, en_us]).alternates("lpg-massazh"), {
            "ru": "https://vn.neva.beauty/lpg-massazh/",
            "en-US": "https://vn.neva.beauty/en/lpg-massage/",
        })

    def test_x_default_is_the_main_language_address(self):
        self.assertEqual(make_routes().x_default("lpg-massazh"),
                         "https://vn.neva.beauty/lpg-massazh/")


class LocalizeLinksTest(unittest.TestCase):
    def test_default_locale_keeps_links(self):
        html = 'см. <a href="/lpg-massazh/">LPG-массаж</a>'
        self.assertEqual(make_routes().localize_links(RU, html), html)

    def test_other_locale_gets_its_address(self):
        self.assertEqual(make_routes().localize_links(EN, '<a href="/lpg-massazh/">LPG</a>'),
                         '<a href="/en/lpg-massage/">LPG</a>')

    def test_home_link(self):
        self.assertEqual(make_routes().localize_links(EN, '<a href="/">home</a>'),
                         '<a href="/en/">home</a>')

    def test_base_path_is_prefixed(self):
        routes = make_routes("/vn.neva.beauty")
        self.assertEqual(routes.localize_links(RU, '<a href="/lpg-massazh/">LPG</a>'),
                         '<a href="/vn.neva.beauty/lpg-massazh/">LPG</a>')

    def test_anchor_is_preserved(self):
        self.assertEqual(make_routes().localize_links(EN, '<a href="/lpg-massazh/#faq">FAQ</a>'),
                         '<a href="/en/lpg-massage/#faq">FAQ</a>')

    def test_external_link_is_untouched(self):
        html = '<a href="https://wa.me/84357132621" target="_blank">WhatsApp</a>'
        self.assertEqual(make_routes().localize_links(EN, html), html)

    def test_unknown_page_is_error(self):
        with self.assertRaisesRegex(ValueError, "net-takoy"):
            make_routes().localize_links(RU, '<a href="/net-takoy/">x</a>')

    def test_protocol_relative_link_is_external(self):
        html = '<a href="//cdn.example.com/x">x</a>'
        self.assertEqual(make_routes().localize_links(EN, html), html)

    def test_single_quoted_internal_link_is_error(self):
        with self.assertRaisesRegex(ValueError, "одинарн"):
            make_routes().localize_links(EN, "<a href='/lpg-massazh/'>x</a>")

    def test_single_quoted_external_link_is_untouched(self):
        html = "<a href='https://wa.me/1'>x</a>"
        self.assertEqual(make_routes().localize_links(EN, html), html)

    def test_service_id_written_as_path_is_error(self):
        for bad in ("/home/", "/404/"):
            with self.assertRaisesRegex(ValueError, "лужебн"):
                make_routes().localize_links(RU, f'<a href="{bad}">x</a>')

    def test_privacy_link_is_legitimate(self):
        self.assertEqual(make_routes().localize_links(EN, '<a href="/privacy/">p</a>'),
                         '<a href="/en/privacy/">p</a>')


if __name__ == "__main__":
    unittest.main()
