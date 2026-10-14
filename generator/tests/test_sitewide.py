import unittest

import sitewide
from locales import parse_locale
from routes import Routes

BASE_URL = "https://vn.neva.beauty"
RU = parse_locale({"code": "ru", "html_lang": "ru", "og_locale": "ru_RU", "url_prefix": "",
                   "ui": {}}, "ru.yml")
EN = parse_locale({"code": "en", "html_lang": "en", "og_locale": "en_US", "url_prefix": "/en",
                   "ui": {}, "slugs": {"korrekciya-figury": "body-shaping"}}, "en.yml")
CONTENT = {
    "categories": [
        {"slug": "korrekciya-figury", "page_id": "korrekciya-figury", "is_page": True,
         "url": "/korrekciya-figury/"},
        {"slug": "uhod", "page_id": "uhod", "is_page": False, "url": "/uhod/"},
    ],
    "services": {"lpg-massazh": {}, "uhod": {}},
}
PAGE_IDS = ["lpg-massazh", "uhod", "korrekciya-figury"]


class SitemapPathsTest(unittest.TestCase):
    def test_order_is_home_services_categories(self):
        routes = Routes([RU], PAGE_IDS, BASE_URL)
        self.assertEqual(sitewide.sitemap_paths(CONTENT, routes, RU),
                         ["/", "/lpg-massazh/", "/uhod/", "/korrekciya-figury/"])

    def test_category_address_comes_from_routes_of_the_given_locale(self):
        """Адрес раздела берётся из таблицы маршрутов, а не из поля cat["url"]:
        иначе ключи changed (их строит build через routes.path) разошлись бы с sitemap."""
        routes = Routes([RU, EN], PAGE_IDS, BASE_URL)
        self.assertEqual(sitewide.sitemap_paths(CONTENT, routes, EN)[-1], "/en/body-shaping/")


class SitemapLastmodTest(unittest.TestCase):
    def test_unchanged_page_keeps_known_lastmod(self):
        known = {BASE_URL + "/": "2026-01-01"}
        xml = sitewide.build_sitemap(BASE_URL, ["/"], {"/": False}, known)
        self.assertIn("<loc>https://vn.neva.beauty/</loc><lastmod>2026-01-01</lastmod>", xml)


if __name__ == "__main__":
    unittest.main()
