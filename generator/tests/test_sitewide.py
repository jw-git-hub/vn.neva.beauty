import json
import re
import unittest
from unittest import mock

import build
import sitewide
import taxonomy
from locales import load_locale, localized_site, parse_locale
from routes import HOME, PRIVACY, Routes

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
        routes = Routes([RU], PAGE_IDS, BASE_URL, "ru")
        self.assertEqual(sitewide.sitemap_paths(CONTENT, routes, RU),
                         ["/", "/lpg-massazh/", "/uhod/", "/korrekciya-figury/"])

    def test_category_address_comes_from_routes_of_the_given_locale(self):
        """Адрес раздела берётся из таблицы маршрутов, а не из поля cat["url"]:
        иначе ключи changed (их строит build через routes.path) разошлись бы с sitemap."""
        routes = Routes([RU, EN], PAGE_IDS, BASE_URL, "ru")
        self.assertEqual(sitewide.sitemap_paths(CONTENT, routes, EN)[-1], "/en/body-shaping/")


class SitemapLastmodTest(unittest.TestCase):
    def test_unchanged_page_keeps_known_lastmod(self):
        known = {BASE_URL + "/": "2026-01-01"}
        xml = sitewide.build_sitemap(BASE_URL, ["/"], {"/": False}, known)
        self.assertIn("<loc>https://vn.neva.beauty/</loc><lastmod>2026-01-01</lastmod>", xml)


class BuildLlmsFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Настоящие данные сайта: контент обоих языков собирает build_locale без записи файлов."""
        cls.site, content, cls.prices = build.load()
        cls.locales = build.load_locales(cls.site)
        cls.routes = Routes(cls.locales, taxonomy.page_ids(content), cls.site["base_url"],
                            build.load_x_default_locale(cls.site))
        with mock.patch("build.write", return_value=False):
            cls.contents = {locale.code: build.build_locale(
                cls.site, content, cls.prices, locale, cls.routes, "", cls.locales[0])[1]
                for locale in cls.locales}

    def test_llms_russian_part_unchanged_and_english_follows(self):
        main = self.locales[0]
        russian = sitewide.build_llms(localized_site(self.site, main), self.contents[main.code],
                                      self.prices, main, self.routes)
        text = sitewide.build_llms_file(self.site, self.contents, self.prices,
                                        self.locales, self.routes)
        self.assertTrue(text.startswith(russian))
        self.assertTrue(text[len(russian):].startswith("\n# Neva Beauty — English\n"))
        english = text[len(russian):]
        self.assertIn("https://vn.neva.beauty/en/laser-hair-removal/", english)
        self.assertIsNone(re.search("[А-Яа-яЁё]", english))

    def english_block(self):
        main = self.locales[0]
        text = sitewide.build_llms_file(self.site, self.contents, self.prices,
                                        self.locales, self.routes)
        russian = sitewide.build_llms(localized_site(self.site, main), self.contents[main.code],
                                      self.prices, main, self.routes)
        return main, russian, text[len(russian):]

    def test_english_block_links_home_and_privacy_policy(self):
        english_locale = self.locales[1]
        _main, _russian, english = self.english_block()
        self.assertIn("## Pages\n"
                      f"- [Home]({self.routes.url(english_locale, HOME)})\n"
                      f"- [Privacy Policy]({self.routes.url(english_locale, PRIVACY)})\n", english)
        self.assertIn("https://vn.neva.beauty/en/privacy/", english)

    def test_russian_block_has_no_pages_section(self):
        main, russian, _english = self.english_block()
        self.assertEqual(main.llms_pages_title, "")
        self.assertNotIn(self.routes.url(main, PRIVACY), russian)
        self.assertNotIn(f"]({self.routes.url(main, HOME)})", russian)

RU_MANIFEST = """{
  "name": "Neva Beauty — Центр красоты · Дананг",
  "short_name": "Neva Beauty",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#FBF4F0",
  "theme_color": "#FBF4F0",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
"""
THEME_COLOR = "#FBF4F0"
SITE_RU = {"brand": "Neva Beauty", "tagline": "Центр красоты · Дананг"}
SITE_EN = {"brand": "Neva Beauty", "tagline": "Beauty Center · Da Nang"}


class BuildManifestTest(unittest.TestCase):
    def test_russian_manifest_is_unchanged(self):
        self.assertEqual(sitewide.build_manifest(SITE_RU, "", THEME_COLOR), RU_MANIFEST)

    def test_english_manifest_starts_at_language_root(self):
        manifest = json.loads(sitewide.build_manifest(SITE_EN, "", THEME_COLOR, "/en"))
        self.assertEqual(manifest["start_url"], "/en/")
        self.assertEqual(manifest["name"], "Neva Beauty — Beauty Center · Da Nang")

    def test_english_manifest_shares_icons_with_russian(self):
        manifest = json.loads(sitewide.build_manifest(SITE_EN, "", THEME_COLOR, "/en"))
        self.assertEqual([icon["src"] for icon in manifest["icons"]],
                         ["/icon-192.png", "/icon-512.png"])

    def test_base_path_precedes_language_prefix_in_start_url_only(self):
        manifest = json.loads(sitewide.build_manifest(SITE_EN, "/preview", THEME_COLOR, "/en"))
        self.assertEqual(manifest["start_url"], "/preview/en/")
        self.assertEqual(manifest["icons"][0]["src"], "/preview/icon-192.png")


class HeaderBackgroundFallbackTest(unittest.TestCase):
    """Браузер без color-mix (Safari до 16.2) должен получить запасной фон шапки."""
    HEADER_RULE_RE = re.compile(r"\.site-header\{[^}]*\}")
    GLASS_RULE = "@supports (background:color-mix(in srgb,red,blue)){.site-header{background:color-mix("

    @classmethod
    def setUpClass(cls):
        sitewide.build_css_bundle(build.OUT)
        cls.bundle = (build.OUT / "assets" / "css" / "bundle.min.css").read_text(encoding="utf-8")

    def test_plain_header_rule_has_opaque_fallback_without_color_mix(self):
        rule = self.HEADER_RULE_RE.search(self.bundle).group(0)
        self.assertIn("background:var(--bg)", rule)
        self.assertNotIn("color-mix", rule)

    def test_glass_background_is_applied_only_where_color_mix_is_supported(self):
        self.assertIn(self.GLASS_RULE, self.bundle)

    def test_fallback_comes_before_glass_rule(self):
        self.assertLess(self.bundle.index(".site-header{"), self.bundle.index(self.GLASS_RULE))


class TextWrapTest(unittest.TestCase):
    """Ровный перенос: заголовки balance, абзацы pretty."""

    @classmethod
    def setUpClass(cls):
        sitewide.build_css_bundle(build.OUT)
        cls.bundle = (build.OUT / "assets" / "css" / "bundle.min.css").read_text(encoding="utf-8")

    def test_headings_are_balanced(self):
        rule = re.search(r"h1,h2,h3,h4\{font-family[^}]*\}", self.bundle).group(0)
        self.assertIn("text-wrap:balance", rule)

    def test_paragraphs_are_pretty(self):
        self.assertIn("p{text-wrap:pretty}", self.bundle)


if __name__ == "__main__":
    unittest.main()
