import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import check_i18n
from locales import parse_locale
from routes import Routes

BASE_URL = "https://vn.neva.beauty"
PAGE_ID = "lpg-massazh"
PAGE_NAME = "en/lpg-massage/index.html"


def make_locale(code, prefix, slugs=None):
    return parse_locale({"code": code, "html_lang": code, "og_locale": code,
                         "url_prefix": prefix, "ui": {}, "slugs": slugs or {}}, f"{code}.yml")


RU = make_locale("ru", "")
EN = make_locale("en", "/en", {PAGE_ID: "lpg-massage"})
ROUTES = Routes([RU, EN], [PAGE_ID], BASE_URL, "en")


def parse(html):
    return BeautifulSoup(html, "html.parser")


def alternates(*pairs):
    return "".join(f'<link rel="alternate" hreflang="{lang}" href="{href}">'
                   for lang, href in pairs)


RU_URL = f"{BASE_URL}/lpg-massazh/"
EN_URL = f"{BASE_URL}/en/lpg-massage/"
GOOD_ALTERNATES = alternates(("ru", RU_URL), ("en", EN_URL), ("x-default", EN_URL))


def hreflang(head, noindex=False, locale=EN):
    soup = parse(f"<html><head>{head}</head></html>")
    return check_i18n.hreflang_errors(soup, PAGE_ID, locale, ROUTES, noindex)


class HreflangErrorsTest(unittest.TestCase):
    def test_complete_set_passes(self):
        head = f'<link rel="canonical" href="{EN_URL}">{GOOD_ALTERNATES}'
        self.assertEqual(hreflang(head), [])

    def test_hreflang_on_noindex_page_is_error(self):
        self.assertTrue(hreflang(GOOD_ALTERNATES, noindex=True))

    def test_noindex_page_without_hreflang_passes(self):
        self.assertEqual(hreflang("", noindex=True), [])

    def test_missing_self_reference_is_error(self):
        head = (f'<link rel="canonical" href="{EN_URL}">'
                + alternates(("ru", RU_URL), ("x-default", EN_URL)))
        self.assertTrue(hreflang(head))

    def test_x_default_on_russian_is_error(self):
        head = (f'<link rel="canonical" href="{EN_URL}">'
                + alternates(("ru", RU_URL), ("en", EN_URL), ("x-default", RU_URL)))
        self.assertTrue(hreflang(head))

    def test_duplicate_alternate_is_error(self):
        head = f'<link rel="canonical" href="{EN_URL}">{GOOD_ALTERNATES}' \
               + alternates(("ru", RU_URL))
        self.assertTrue(hreflang(head))

    def test_foreign_canonical_is_error(self):
        head = f'<link rel="canonical" href="{RU_URL}">{GOOD_ALTERNATES}'
        self.assertTrue(hreflang(head))


def page(headings="<h1>A</h1><h2>B</h2>", questions=2, rows=1, types=("Service",)):
    faq = ",".join('{"@type": "Question"}' for _ in range(questions))
    nodes = ",".join(f'{{"@type": "{kind}"}}' for kind in types)
    graph = f'{{"@graph": [{nodes}, {{"@type": "FAQPage", "mainEntity": [{faq}]}}]}}'
    table = '<div class="pricelist__panel">' + '<div class="pricelist__row"></div>' * rows + "</div>"
    return parse(f'<body>{headings}{table}<div class="combo"></div>'
                 f'<script type="application/ld+json">{graph}</script></body>')


class SignatureTest(unittest.TestCase):
    def test_same_structure_gives_same_signature(self):
        self.assertEqual(check_i18n.signature(page()), check_i18n.signature(page()))

    def test_signature_counts_parts(self):
        sig = check_i18n.signature(page(questions=3, rows=2))
        self.assertEqual(sig.headings, (1, 2))
        self.assertEqual(sig.faq_questions, 3)
        self.assertEqual(sig.price_rows, 3)
        self.assertEqual(sig.json_ld_types, ("FAQPage", "Service"))

    def test_different_faq_count_is_error(self):
        signatures = {"ru": check_i18n.signature(page(questions=5)),
                      "en": check_i18n.signature(page(questions=4))}
        errors = check_i18n.signature_errors(PAGE_ID, signatures, "ru")
        self.assertEqual(len(errors), 1)
        self.assertIn("en", errors[0])
        self.assertIn(PAGE_ID, errors[0])

    def test_different_heading_levels_is_error(self):
        signatures = {"ru": check_i18n.signature(page()),
                      "en": check_i18n.signature(page(headings="<h1>A</h1><h3>B</h3>"))}
        self.assertTrue(check_i18n.signature_errors(PAGE_ID, signatures, "ru"))

    def test_different_json_ld_types_is_error(self):
        signatures = {"ru": check_i18n.signature(page(types=("Service",))),
                      "en": check_i18n.signature(page(types=("Service", "BreadcrumbList")))}
        self.assertTrue(check_i18n.signature_errors(PAGE_ID, signatures, "ru"))

    def test_equal_signatures_pass(self):
        signatures = {"ru": check_i18n.signature(page()), "en": check_i18n.signature(page())}
        self.assertEqual(check_i18n.signature_errors(PAGE_ID, signatures, "ru"), [])


class LinkErrorsTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.site_dir = Path(self._dir.name)
        for name in ("lpg-massazh/index.html", "index.html", "en/index.html",
                     "en/lpg-massage/index.html", "assets/img/og-en.jpg", "favicon.ico"):
            self.make_file(name)

    def make_file(self, name):
        path = self.site_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    def errors(self, body, locale=EN, base_path=""):
        soup = parse(f"<html><head></head><body>{body}</body></html>")
        return check_i18n.link_errors(soup, PAGE_NAME, locale, RU, self.site_dir,
                                      BASE_URL, base_path)

    def test_links_inside_language_pass(self):
        body = ('<a href="/en/lpg-massage/">a</a><link href="/favicon.ico">'
                '<img src="/assets/img/og-en.jpg?v=abc123">'
                f'<meta property="og:image" content="{BASE_URL}/assets/img/og-en.jpg">'
                '<a href="/en/#faq">b</a><a href="https://example.com/x">ext</a>'
                '<a href="tel:+84">tel</a>')
        self.assertEqual(self.errors(body), [])

    def test_main_language_is_not_checked(self):
        self.assertEqual(self.errors('<a href="/missing/">x</a>', locale=RU), [])

    def test_russian_page_link_without_hreflang_is_error(self):
        self.assertTrue(self.errors('<a href="/lpg-massazh/">x</a>'))

    def test_russian_page_link_with_hreflang_passes(self):
        self.assertEqual(self.errors('<a href="/lpg-massazh/" hreflang="ru">RU</a>'), [])

    def test_hreflang_of_own_language_does_not_exempt(self):
        self.assertTrue(self.errors('<a href="/lpg-massazh/" hreflang="en">x</a>'))

    def test_missing_manifest_is_error(self):
        errors = self.errors('<link rel="manifest" href="/en/site.webmanifest">')
        self.assertEqual(len(errors), 1)
        self.assertIn("site.webmanifest", errors[0])
        self.assertIn(PAGE_NAME, errors[0])

    def test_existing_manifest_passes(self):
        self.make_file("en/site.webmanifest")
        self.assertEqual(self.errors('<link rel="manifest" href="/en/site.webmanifest">'), [])

    def test_missing_og_image_is_error(self):
        body = f'<meta property="og:image" content="{BASE_URL}/assets/img/gone.jpg">'
        self.assertTrue(self.errors(body))

    def test_missing_image_is_error(self):
        self.assertTrue(self.errors('<img src="/assets/img/gone.jpg">'))

    def test_page_link_with_base_url_is_checked_too(self):
        self.assertTrue(self.errors(f'<a href="{BASE_URL}/lpg-massazh/">x</a>'))

    def test_base_path_is_stripped(self):
        body = '<a href="/preview/en/lpg-massage/">a</a><img src="/preview/favicon.ico">'
        self.assertEqual(self.errors(body, base_path="/preview"), [])


def cyrillic(body, head=""):
    soup = parse(f'<html lang="en"><head>{head}</head><body>{body}</body></html>')
    return check_i18n.cyrillic_errors(soup, PAGE_NAME)


class CyrillicErrorsTest(unittest.TestCase):
    def test_latin_page_passes(self):
        self.assertEqual(cyrillic("<p>Hello</p>"), [])

    def test_text_is_error(self):
        errors = cyrillic("<p>Привет</p>")
        self.assertEqual(len(errors), 1)
        self.assertIn(PAGE_NAME, errors[0])

    def test_aria_label_is_error(self):
        self.assertTrue(cyrillic('<a href="/" aria-label="русская версия">RU</a>'))

    def test_russian_link_with_lang_is_skipped(self):
        self.assertEqual(cyrillic('<a href="/" lang="ru">Русский</a>'), [])

    def test_lang_ru_with_cyrillic_attribute_is_skipped(self):
        body = '<a href="/" lang="ru" aria-label="RU — русская версия">RU</a>'
        self.assertEqual(cyrillic(body), [])

    def test_json_ld_is_error(self):
        script = '<script type="application/ld+json">{"name": "Массаж"}</script>'
        self.assertTrue(cyrillic("", head=script))

    def test_script_comment_is_error(self):
        self.assertTrue(cyrillic("<script>// повтор загрузки\nvar a = 1;</script>"))

    def test_at_most_three_short_fragments(self):
        body = "".join(f"<p>{'x' * 80} слово{index}</p>" for index in range(6))
        errors = cyrillic(body)
        self.assertEqual(len(errors), 1)
        fragments = errors[0].split("): ", 1)[1].split(check_i18n.FRAGMENT_SEPARATOR)
        self.assertLessEqual(len(fragments), 3)
        self.assertTrue(all(len(fragment) <= check_i18n.FRAGMENT_LENGTH
                            for fragment in fragments))

    def test_source_soup_is_not_modified(self):
        soup = parse('<html lang="en"><body><a lang="ru">Русский</a></body></html>')
        check_i18n.cyrillic_errors(soup, PAGE_NAME)
        self.assertIsNotNone(soup.find("a", lang="ru"))


def sitemap(*urls):
    rows = "".join(f"<url><loc>{url}</loc><lastmod>2026-10-17</lastmod></url>" for url in urls)
    return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


class SitemapErrorsTest(unittest.TestCase):
    EXPECTED = [BASE_URL + "/", BASE_URL + "/en/"]

    def test_exact_set_passes(self):
        self.assertEqual(check_i18n.sitemap_errors(sitemap(*self.EXPECTED), self.EXPECTED), [])

    def test_missing_url_is_error(self):
        errors = check_i18n.sitemap_errors(sitemap(BASE_URL + "/"), self.EXPECTED)
        self.assertEqual(len(errors), 1)
        self.assertIn(BASE_URL + "/en/", errors[0])

    def test_extra_url_is_error(self):
        urls = self.EXPECTED + [BASE_URL + "/privacy/"]
        self.assertTrue(check_i18n.sitemap_errors(sitemap(*urls), self.EXPECTED))

    def test_repeated_url_is_error(self):
        urls = self.EXPECTED + [BASE_URL + "/"]
        self.assertTrue(check_i18n.sitemap_errors(sitemap(*urls), self.EXPECTED))


if __name__ == "__main__":
    unittest.main()
