import unittest

from locales import parse_locale
from routes import HOME, NOT_FOUND, PRIVACY, Routes


def make_locale(code, prefix, slugs=None):
    return parse_locale({"code": code, "html_lang": code, "og_locale": code,
                         "url_prefix": prefix, "ui": {}, "slugs": slugs or {}}, f"{code}.yml")


RU = make_locale("ru", "")
EN = make_locale("en", "/en", {"lpg-massazh": "lpg-massage"})
PAGE_IDS = ["lpg-massazh", "korrekciya-figury"]
BASE_URL = "https://vn.neva.beauty"


def make_routes(base_path=""):
    return Routes([RU, EN], PAGE_IDS, BASE_URL, base_path)


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


if __name__ == "__main__":
    unittest.main()
