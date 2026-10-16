import unittest
from dataclasses import replace
from unittest import mock

import build
import translation
from locales import load_locale
from tests.pseudo_translation import (PREFIX, pseudo_content, pseudo_pair_patches, pseudo_prices,
                                      pseudo_site)


class TranslationTest(unittest.TestCase):
    def setUp(self):
        _, self.content, self.prices = build.load()
        self.main = load_locale("ru")
        self.site = build.load()[0]
        self.english = replace(self.main, code="en", html_lang="en", url_prefix="/en",
                               site=pseudo_site(self.site))

    def patched(self, overlay=None, catalog=None, privacy=True, exceptions=()):
        return [mock.patch("translation.load_overlay",
                           return_value=pseudo_content(self.content) if overlay is None else overlay),
                mock.patch("translation.load_price_catalog",
                           return_value=pseudo_prices(self.prices) if catalog is None else catalog),
                mock.patch("translation.privacy_exists", return_value=privacy),
                *pseudo_pair_patches(exceptions)]

    def problems(self, **kwargs):
        patches = self.patched(**kwargs)
        for patch in patches:
            patch.start()
        self.addCleanup(mock.patch.stopall)
        return translation.translation_problems(self.site, self.content, self.prices,
                                                self.english, self.main)[1]

    def test_main_language_is_master_copy(self):
        language = translation.prepare(self.site, self.content, self.prices, self.main, self.main)
        self.assertEqual(language.content, self.content)
        self.assertIsNot(language.content, self.content)

    def test_full_pseudo_translation_has_no_problems(self):
        self.assertEqual(self.problems(), [])

    def test_empty_translation_lists_every_gap(self):
        problems = self.problems(overlay={}, catalog={}, privacy=False)
        self.assertIn("privacy: нет перевода политики (data/locales/en/privacy.html)", problems)
        self.assertGreater(len(problems), 369)

    def test_prepare_raises_with_whole_list(self):
        for patch in self.patched(overlay={}):
            patch.start()
        self.addCleanup(mock.patch.stopall)
        with self.assertRaises(ValueError) as error:
            translation.prepare(self.site, self.content, self.prices, self.english, self.main)
        self.assertIn("home.seo_title: нет перевода", str(error.exception))
        self.assertIn("services.lpg-massazh.title: нет перевода", str(error.exception))

    def test_translated_content_is_used(self):
        for patch in self.patched():
            patch.start()
        self.addCleanup(mock.patch.stopall)
        language = translation.prepare(self.site, self.content, self.prices, self.english, self.main)
        self.assertTrue(language.content["home"]["seo_title"].startswith(PREFIX))

    def test_site_strings_need_translation(self):
        self.english = replace(self.english, site={})
        problems = self.problems()
        for field in ("tagline", "location", "hours", "locations[0].city", "locations[1].country"):
            self.assertIn(f"site {field}: нет перевода", problems)

    def test_pair_findings_are_part_of_translation_problems(self):
        overlay = pseudo_content(self.content)
        overlay["home"]["seo_title"] += " 5"
        self.assertIn("home.seo_title: числа: в русском [], в переводе [5]",
                      self.problems(overlay=overlay))

    def test_pair_exceptions_are_applied(self):
        overlay = pseudo_content(self.content)
        overlay["home"]["seo_title"] += " 5"
        exceptions = [{"path": "home.seo_title", "check": "numbers", "reason": "тест"}]
        self.assertEqual(self.problems(overlay=overlay, exceptions=exceptions), [])

    def test_stale_lock_is_a_problem(self):
        with mock.patch("translation.translation_lock.load_lock",
                        return_value={"content.home.seo_title": "0" * 16}):
            problems = self.problems()
        self.assertTrue(any(problem.startswith("замок content.home.seo_title")
                            for problem in problems))


class StatusGroupsTest(unittest.TestCase):
    def test_groups(self):
        import translation_status
        self.assertEqual({translation_status.group_of(problem) for problem in (
            "ui nav.home: нет перевода", "home.seo_title: нет перевода",
            "prices names «Лоб»: нет перевода (lpg-massazh)", "privacy: нет перевода политики",
            "замок privacy: в мастере строки больше нет")},
            {"ui", "content", "prices", "privacy", "замок"})
