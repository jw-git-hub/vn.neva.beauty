import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

import check_i18n
from locales import parse_locale
from routes import Routes

BASE_URL = "https://vn.neva.beauty"
PAGE_ID = "lpg-massazh"
PAGE_NAME = "en/lpg-massage/index.html"
RU_FILE = "lpg-massazh/index.html"


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
    table = ('<div class="pricelist__panel">' + '<div class="pricelist__row"></div>' * rows
             + '<div class="combo"></div></div>')
    return parse(f'<body>{headings}{table}'
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

    def test_combo_outside_price_panel_is_not_counted(self):
        soup = parse('<body><div class="pricelist__panel">'
                     '<div class="pricelist__row"></div><div class="combo"></div></div>'
                     '<div class="combo"></div></body>')
        self.assertEqual(check_i18n.signature(soup).price_rows, 2)

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

    def test_page_without_main_language_pair_is_skipped(self):
        signatures = {"en": check_i18n.signature(page())}
        self.assertEqual(check_i18n.signature_errors(PAGE_ID, signatures, "ru"), [])

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

    def test_og_image_without_content_does_not_crash(self):
        self.assertEqual(self.errors('<meta property="og:image">'), [])

    def test_missing_image_is_error(self):
        self.assertTrue(self.errors('<img src="/assets/img/gone.jpg">'))

    def test_page_link_with_base_url_is_checked_too(self):
        self.assertTrue(self.errors(f'<a href="{BASE_URL}/lpg-massazh/">x</a>'))

    def test_base_path_is_stripped(self):
        body = '<a href="/preview/en/lpg-massage/">a</a><img src="/preview/favicon.ico">'
        self.assertEqual(self.errors(body, base_path="/preview"), [])

    def test_root_link_without_base_path_is_error(self):
        """Файл /en/lpg-massage/ в сборке есть, но на превью по подпути ссылка ведёт мимо сайта."""
        for body in ('<a href="/en/lpg-massage/">a</a>', '<img src="/favicon.ico">',
                     '<link href="/en/site.webmanifest">', '<a href="/previewer/">a</a>'):
            with self.subTest(body=body):
                errors = self.errors(body, base_path="/preview")
                self.assertTrue(any("без префикса /preview" in error for error in errors))

    def test_base_path_alone_with_query_or_anchor_has_the_prefix(self):
        for address in ("/preview", "/preview/", "/preview#faq", "/preview?x=1", "/preview/en/"):
            with self.subTest(address=address):
                self.assertIsNone(check_i18n.base_path_problem(address, "/preview"))
        self.assertIsNotNone(check_i18n.base_path_problem("/previewer/", "/preview"))
        self.assertIsNone(check_i18n.base_path_problem("/en/", ""))

    def test_full_and_relative_addresses_are_not_base_path_errors(self):
        body = ('<a href="https://example.com/x">a</a><a href="//cdn.example.com/x.js">b</a>'
                '<a href="#faq">c</a><a href="tel:+84">d</a>')
        self.assertEqual(self.errors(body, base_path="/preview"), [])

    def test_main_language_root_link_without_base_path_is_error(self):
        errors = self.errors('<a href="/lpg-massazh/">x</a>', locale=RU, base_path="/preview")
        self.assertEqual(len(errors), 1)
        self.assertIn("без префикса /preview", errors[0])


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

    def test_escaped_cyrillic_in_script_is_error(self):
        for escaped in ("\\u041c\\u0430\\u0441", "\\u043C\\u0430", "\\u0401", "\\u0451"):
            with self.subTest(escaped=escaped):
                self.assertTrue(cyrillic(f'<script>var s = "{escaped}";</script>'))

    def test_extended_cyrillic_is_error(self):
        """Старая кириллица и буквы неславянских языков (U+0460–U+04FF) — тоже кириллица."""
        for letter in ("ѣ", "ҙ", "ӏ", "Ѡ"):
            with self.subTest(letter=letter):
                self.assertTrue(cyrillic(f"<p>word {letter} word</p>"))

    def test_escaped_extended_cyrillic_in_script_is_error(self):
        for escaped in ("\\u0463", "\\u0499", "\\u04CF", "\\u04ff"):
            with self.subTest(escaped=escaped):
                self.assertTrue(cyrillic(f'<script>var s = "{escaped}";</script>'))

    def test_escaped_latin_is_not_error(self):
        self.assertEqual(cyrillic('<script>var s = "\\u0041\\u00e9\\u2014";</script>'), [])

    def test_regional_variant_of_page_language_stays_checked(self):
        self.assertTrue(cyrillic('<p lang="en-GB">Привет</p>'))

    def test_other_language_with_region_is_skipped(self):
        self.assertEqual(cyrillic('<p lang="RU-ru">Привет</p>'), [])

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


class IndexableUrlsTest(unittest.TestCase):
    def test_canonical_of_indexable_page(self):
        soup = parse(f'<head><link rel="canonical" href="{EN_URL}"></head>')
        self.assertEqual(check_i18n.indexable_urls_of(soup), [EN_URL])

    def test_noindex_page_gives_nothing(self):
        soup = parse(f'<head><meta name="robots" content="noindex, follow">'
                     f'<link rel="canonical" href="{EN_URL}"></head>')
        self.assertEqual(check_i18n.indexable_urls_of(soup), [])

    def test_page_without_canonical_gives_nothing(self):
        self.assertEqual(check_i18n.indexable_urls_of(parse("<head></head>")), [])


class BuiltSiteTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.site_dir = Path(self._dir.name) / "site"
        self.expected = {"ru": {self.site_dir / RU_FILE},
                         "en": {self.site_dir / "en/lpg-massage/index.html"}}

    def write(self, name, html="<html></html>"):
        path = self.site_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def write_pair(self, english_head=None):
        self.write(RU_FILE, f'<html lang="ru"><head><link rel="canonical" href="{RU_URL}"></head></html>')
        head = english_head if english_head is not None else f'<link rel="canonical" href="{EN_URL}">'
        self.write("en/lpg-massage/index.html", f'<html lang="en"><head>{head}</head></html>')

    def run_check(self):
        pages = [(RU, PAGE_ID, self.site_dir / RU_FILE),
                 (EN, PAGE_ID, self.site_dir / "en/lpg-massage/index.html")]
        setup = check_i18n.Setup(ROUTES, BASE_URL, "")
        with mock.patch.object(check_i18n, "SITE", self.site_dir), \
                mock.patch.object(check_i18n.check_contacts, "locale_pages",
                                  return_value=pages):
            return check_i18n.check_pages({}, {}, setup)

    def test_indexable_urls_come_from_built_pages(self):
        self.write_pair()
        report = self.run_check()
        self.assertEqual(sorted(report.indexable_urls), sorted([RU_URL, EN_URL]))

    def test_noindex_page_is_not_expected_in_sitemap(self):
        self.write_pair(f'<meta name="robots" content="noindex"><link rel="canonical" href="{EN_URL}">')
        urls = self.run_check().indexable_urls
        errors = check_i18n.sitemap_errors(sitemap(RU_URL, EN_URL), urls)
        self.assertEqual(len(errors), 1)
        self.assertIn(EN_URL, errors[0])

    def test_indexable_page_missing_from_sitemap_is_error(self):
        self.write_pair()
        errors = check_i18n.sitemap_errors(sitemap(RU_URL), self.run_check().indexable_urls)
        self.assertEqual(len(errors), 1)
        self.assertIn(EN_URL, errors[0])

    def test_missing_pair_file_is_error_not_traceback(self):
        self.write(RU_FILE)
        report = self.run_check()
        self.assertEqual(report.checked, 1)
        missing = [error for error in report.errors if error.startswith("нет пары")]
        self.assertEqual(len(missing), 1)
        self.assertIn("en/lpg-massage/index.html", missing[0])

    def test_stale_page_under_language_prefix_is_error(self):
        self.write("en/old-slug/index.html")
        errors = check_i18n.stale_page_errors(self.site_dir, [RU, EN], self.expected)
        self.assertEqual(len(errors), 1)
        self.assertIn("лишняя страница", errors[0])
        self.assertIn("en/old-slug/index.html", errors[0])

    def test_expected_pages_under_prefix_pass(self):
        self.write("en/lpg-massage/index.html")
        self.assertEqual(check_i18n.stale_page_errors(self.site_dir, [RU, EN], self.expected), [])

    def test_main_language_root_is_not_scanned_for_stale_pages(self):
        self.write("about/index.html")
        self.assertEqual(check_i18n.stale_page_errors(self.site_dir, [RU, EN], self.expected), [])

    def test_cyrillic_in_non_html_file_under_prefix_is_error(self):
        self.write("en/site.webmanifest", '{"name": "Центр красоты"}')
        errors = check_i18n.language_file_errors(self.site_dir, [RU, EN])
        self.assertEqual(len(errors), 1)
        self.assertIn("en/site.webmanifest", errors[0])
        self.assertIn("кириллица", errors[0])

    def test_latin_non_html_file_and_main_language_files_pass(self):
        self.write("en/site.webmanifest", '{"name": "Beauty Center"}')
        self.write("site.webmanifest", '{"name": "Центр красоты"}')
        self.assertEqual(check_i18n.language_file_errors(self.site_dir, [RU, EN]), [])

    def test_cyrillic_in_non_html_file_is_reported_by_check_pages(self):
        self.write_pair()
        self.write("en/site.webmanifest", '{"name": "Центр"}')
        self.assertTrue(any("site.webmanifest" in error for error in self.run_check().errors))

    def test_check_pages_collects_signatures_and_count(self):
        self.write_pair()
        report = self.run_check()
        self.assertEqual(report.checked, 2)
        self.assertEqual(set(report.signatures), {PAGE_ID})
        self.assertEqual(set(report.signatures[PAGE_ID]), {"ru", "en"})

    def test_check_pages_reports_wrong_canonical(self):
        self.write_pair('<link rel="canonical" href="https://vn.neva.beauty/en/other/">')
        self.assertTrue(any("canonical" in error for error in self.run_check().errors))

    def test_stale_page_is_reported_by_check_pages(self):
        self.write_pair()
        self.write("en/old-slug/index.html")
        errors = self.run_check().errors
        self.assertTrue(any(error.startswith("лишняя страница") for error in errors))


class MainTest(unittest.TestCase):
    """main читает сборку, обходит страницы и сверяет отпечатки и sitemap: печатает итог
    и завершается кодом 0 или 1."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.site_dir = Path(self._dir.name) / "site"
        self.site_dir.mkdir()

    def run_main(self, report, sitemap_text):
        (self.site_dir / check_i18n.SITEMAP_FILE).write_text(sitemap_text, encoding="utf-8")
        output = io.StringIO()
        with mock.patch.object(check_i18n, "SITE", self.site_dir), \
                mock.patch.object(check_i18n.build, "load", return_value=({}, {}, {})), \
                mock.patch.object(check_i18n, "make_setup",
                                  return_value=check_i18n.Setup(ROUTES, BASE_URL, "")), \
                mock.patch.object(check_i18n, "check_pages", return_value=report), \
                contextlib.redirect_stdout(output):
            try:
                check_i18n.main()
                code = 0
            except SystemExit as exit_signal:
                code = exit_signal.code
        return code, output.getvalue()

    def signatures(self, english_headings=(1, 2)):
        make = lambda headings: check_i18n.Signature(headings, 0, 0, ())
        return {PAGE_ID: {"ru": make((1, 2)), "en": make(english_headings)}}

    def test_clean_site_prints_ok_and_exits_normally(self):
        report = check_i18n.PageReport([], self.signatures(), 2, [RU_URL, EN_URL])
        code, output = self.run_main(report, sitemap(RU_URL, EN_URL))
        self.assertEqual(code, 0)
        self.assertIn("страниц проверено: 2", output)
        self.assertIn("I18N OK", output)

    def test_page_errors_signature_and_sitemap_errors_all_fail_the_run(self):
        report = check_i18n.PageReport(["нет пары: en/x/index.html"], self.signatures((1, 3)),
                                       2, [RU_URL, EN_URL])
        code, output = self.run_main(report, sitemap(RU_URL))
        self.assertEqual(code, 1)
        self.assertIn("нет пары: en/x/index.html", output)
        self.assertIn("уровни заголовков", output)
        self.assertIn(f"sitemap: нет адреса {EN_URL}", output)
        self.assertNotIn("I18N OK", output)


if __name__ == "__main__":
    unittest.main()
