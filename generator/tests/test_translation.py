import unittest
from dataclasses import replace
from unittest import mock

import build
import translation
from locales import load_locale
from tests.pseudo_translation import PREFIX, pseudo_content, pseudo_prices


class TranslationTest(unittest.TestCase):
    def setUp(self):
        _, self.content, self.prices = build.load()
        self.main = load_locale("ru")
        self.english = replace(self.main, code="en", html_lang="en", url_prefix="/en")

    def patched(self, overlay=None, catalog=None, privacy=True):
        return [mock.patch("translation.load_overlay",
                           return_value=pseudo_content(self.content) if overlay is None else overlay),
                mock.patch("translation.load_price_catalog",
                           return_value=pseudo_prices(self.prices) if catalog is None else catalog),
                mock.patch("translation.privacy_exists", return_value=privacy)]

    def problems(self, **kwargs):
        patches = self.patched(**kwargs)
        for patch in patches:
            patch.start()
        self.addCleanup(mock.patch.stopall)
        return translation.translation_problems(self.content, self.prices,
                                                self.english, self.main)[1]

    def test_main_language_is_master_copy(self):
        language = translation.prepare(self.content, self.prices, self.main, self.main)
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
            translation.prepare(self.content, self.prices, self.english, self.main)
        self.assertIn("home.seo_title: нет перевода", str(error.exception))
        self.assertIn("services.lpg-massazh.title: нет перевода", str(error.exception))

    def test_translated_content_is_used(self):
        for patch in self.patched():
            patch.start()
        self.addCleanup(mock.patch.stopall)
        language = translation.prepare(self.content, self.prices, self.english, self.main)
        self.assertTrue(language.content["home"]["seo_title"].startswith(PREFIX))

    def test_stale_lock_is_a_problem(self):
        with mock.patch("translation.translation_lock.load_lock",
                        return_value={"content.home.seo_title": "0" * 16}):
            problems = self.problems()
        self.assertTrue(any(problem.startswith("замок content.home.seo_title")
                            for problem in problems))
