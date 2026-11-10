import unittest
from dataclasses import replace
from unittest import mock

import build
import translation
from locales import load_locale
from translation_problem import Problem
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

    def test_crooked_price_catalog_gives_lines_not_traceback(self):
        """Список вместо словаря, словарь вместо списка и подобное — строка в общем списке."""
        full = pseudo_prices(self.prices)
        for key, crooked in (("names", []), ("descs", ["a"]), ("sections", "x"),
                             ("overrides", ["a"]), ("overrides", {"lpg-massazh": []}),
                             ("overrides", {"lpg-massazh": {"names": ["x"]}})):
            with self.subTest(key=key, crooked=crooked):
                problems = self.problems(catalog={**full, key: crooked})
                self.assertTrue(any("должен быть словарём" in problem for problem in problems))
                mock.patch.stopall()

    def test_catalog_that_is_not_a_dictionary_gives_a_line(self):
        problems = self.problems(catalog=["a"])
        self.assertTrue(any(problem.startswith("prices: файл должен быть словарём")
                            for problem in problems))

    def test_ui_value_that_is_not_a_string_gives_a_line(self):
        for value in (5, None, {"note": None}):
            with self.subTest(value=value):
                self.english = replace(self.english, ui={**self.main.ui, "price.from": value})
                problems = self.problems()
                self.assertIn(f"ui price.from: перевод должен быть строкой, а не "
                              f"{type(value).__name__}", problems)
                mock.patch.stopall()

    def test_description_that_is_not_a_string_gives_a_line(self):
        site = pseudo_site(self.site)
        site["business"]["description"] = {"note": None}
        self.english = replace(self.english, site=site)
        self.assertIn("site business.description: нет перевода", self.problems())

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
        for field in ("tagline", "location", "hours", "business.description",
                      "locations[0].city", "locations[1].country"):
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
    def test_group_comes_from_the_problem_not_from_its_text(self):
        import translation_status
        problems = [Problem("ui nav.home: нет перевода", "content"),
                    Problem("home.seo_title: нет перевода", "ui")]
        groups = translation_status.grouped(problems)
        self.assertEqual({group: list(items) for group, items in groups.items()},
                         {"content": [problems[0]], "ui": [problems[1]]})

    def test_every_stage_tags_its_own_group(self):
        """Реальные проблемы пустого перевода раскладываются по стадиям, которые их нашли."""
        site, content, prices = build.load()
        locales = build.load_locales(site)
        english = replace(locales[1], ui={}, site={})
        with mock.patch("translation.load_overlay", return_value={}), \
                mock.patch("translation.load_price_catalog", return_value={}), \
                mock.patch("translation.privacy_exists", return_value=False), \
                mock.patch("translation.translation_lock.load_lock",
                           return_value={"content.home.seo_title": "0" * 16}):
            _, problems = translation.translation_problems(site, content, prices, english,
                                                           locales[0])
        self.assertLessEqual({"content", "ui", "site", "prices", "privacy", "замок"},
                             {problem.group for problem in problems})
        self.assertTrue(all(problem.startswith("ui ") for problem in problems
                            if problem.group == "ui"))
