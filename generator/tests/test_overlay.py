import copy
import unittest

import overlay

MASTER = {
    "home": {"seo_title": "Главная", "hero_title_lines": ["Красота", "в Дананге"],
             "faq": [{"q": "Вопрос?", "a": "Ответ."}],
             "popular": [{"slug": "lpg-massazh", "label": "LPG", "name": "LPG Массаж - Тело"}]},
    "services": {"lpg-massazh": {"title": "LPG-массаж", "hero_image": "lpg-massazh",
                                 "related": ["smas-lifting"]}},
}
FULL = {
    "home": {"seo_title": "Home", "hero_title_lines": ["Beauty in Da Nang"],
             "faq": [{"q": "Question?", "a": "Answer."}], "popular": [{"label": "LPG"}]},
    "services": {"lpg-massazh": {"title": "LPG Massage"}},
}


class MergeTranslationTest(unittest.TestCase):
    def test_full_translation_merges(self):
        merged, problems = overlay.merge_translation(MASTER, FULL)
        self.assertEqual(problems, [])
        self.assertEqual(merged["home"]["faq"][0]["q"], "Question?")
        self.assertEqual(merged["home"]["popular"][0]["name"], "LPG Массаж - Тело")
        self.assertEqual(merged["services"]["lpg-massazh"]["related"], ["smas-lifting"])

    def test_hero_lines_may_split_differently(self):
        merged, _ = overlay.merge_translation(MASTER, FULL)
        self.assertEqual(merged["home"]["hero_title_lines"], ["Beauty in Da Nang"])

    def test_master_is_not_mutated(self):
        snapshot = copy.deepcopy(MASTER)
        overlay.merge_translation(MASTER, FULL)
        self.assertEqual(MASTER, snapshot)

    def test_missing_field_is_named(self):
        partial = copy.deepcopy(FULL); del partial["home"]["faq"][0]["a"]
        self.assertEqual(overlay.merge_translation(MASTER, partial)[1],
                         ["home.faq[0].a: нет перевода"])

    def test_missing_subtree_names_every_field(self):
        partial = copy.deepcopy(FULL); del partial["services"]
        self.assertEqual(overlay.merge_translation(MASTER, partial)[1],
                         ["services.lpg-massazh.title: нет перевода"])

    def test_empty_overlay_lists_everything(self):
        problems = overlay.merge_translation(MASTER, {})[1]
        self.assertEqual(len(problems), len(overlay.source_strings(MASTER)))

    def test_extra_key_is_error(self):
        extra = copy.deepcopy(FULL); extra["home"]["subtitle"] = "Extra"
        self.assertIn("home.subtitle: лишний ключ — в мастере его нет",
                      overlay.merge_translation(MASTER, extra)[1])

    def test_untranslatable_field_is_error(self):
        wrong = copy.deepcopy(FULL); wrong["home"]["popular"][0]["name"] = "LPG Body"
        self.assertIn("home.popular[0].name: поле не переводится, в переводе его быть не должно",
                      overlay.merge_translation(MASTER, wrong)[1])

    def test_list_of_other_length_is_error(self):
        short = copy.deepcopy(FULL); short["home"]["faq"] = []
        self.assertIn("home.faq: в мастере 1 элементов, в переводе 0",
                      overlay.merge_translation(MASTER, short)[1])

    def test_empty_string_is_error(self):
        empty = copy.deepcopy(FULL); empty["home"]["seo_title"] = ""
        self.assertEqual(overlay.merge_translation(MASTER, empty)[1],
                         ["home.seo_title: перевод должен быть непустой строкой"])


class SourceStringsTest(unittest.TestCase):
    def test_paths_and_texts(self):
        strings = overlay.source_strings(MASTER)
        self.assertEqual(strings["home.faq[0].q"], "Вопрос?")
        self.assertEqual(strings["home.hero_title_lines"], "Красота\nв Дананге")
        self.assertEqual(strings["services.lpg-massazh.title"], "LPG-массаж")
        self.assertNotIn("home.popular[0].name", strings)

    def test_real_master_has_369_fields(self):
        import build
        self.assertEqual(len(overlay.source_strings(build.load()[1])), 369)
