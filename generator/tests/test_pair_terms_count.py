"""Обязательное слово считается по вхождениям: каждому русскому термину — своё.

Раньше слово засчитывалось, если стояло в переводе хотя бы раз, и второй термин с тем
же словом required («коррекция фигуры» и «лифтинг и омоложение» → «non-surgical») не
проверялся.
"""
import unittest

import pair_terms
import translation_pairs as tp
from tests.pseudo_translation import pseudo_content

TERMS = pair_terms.load_terms("en")
PATH = "services.x.faq[0].a"
TWO_TERMS = "Коррекция фигуры, лифтинг и омоложение — в Neva Beauty."
ONE_NON_SURGICAL = "Non-surgical body contouring, face lift and rejuvenation."  # «омоложение» → rejuvenation


def problems_of(ru, en, exceptions=()):
    return tp.pair_problems([tp.Pair(PATH, ru, en, tp.CHECKS_OF_PAGE)], TERMS, list(exceptions))


def counted(ru, word):
    return [term.ru for term, _ in pair_terms.required_terms(ru, TERMS) if term.required == word]


class TwoTermsOneWordTest(unittest.TestCase):
    def test_second_term_needs_its_own_occurrence(self):
        self.assertEqual(
            problems_of(TWO_TERMS, ONE_NON_SURGICAL),
            [f"{PATH}: термины: в русском «коррекция фигуры» (термин «Коррекция фигуры»), "
             "«лифтинг и омоложение» (термин «Лифтинг и омоложение»), "
             "в переводе «non-surgical» только 1 из 2 — по одному на термин"])

    def test_two_occurrences_pass(self):
        self.assertEqual(problems_of(TWO_TERMS, "Non-surgical body contouring and a "
                                                "non-surgical face lift & rejuvenation."), [])

    def test_no_occurrence_names_every_term(self):
        self.assertEqual(
            problems_of(TWO_TERMS, "Body contouring, face lift and rejuvenation."),
            [f"{PATH}: термины: в русском «коррекция фигуры» (термин «Коррекция фигуры»), "
             "«лифтинг и омоложение» (термин «Лифтинг и омоложение»), в переводе нет «non-surgical»"])

    def test_adjective_and_section_name_are_two_terms(self):
        self.assertEqual(counted("Все они безоперационные. Коррекция фигуры.", "non-surgical"),
                         ["Коррекция фигуры", "безоперационный"])

class SameOccurrenceTest(unittest.TestCase):
    def test_term_inside_longer_term_counts_once(self):
        self.assertEqual(counted("Не требует длительного восстановления.", "recovery"),
                         ["длительное восстановление"])
        self.assertEqual(problems_of("Не требует длительного восстановления.",
                                     "No lengthy recovery is needed."), [])

    def test_term_apart_from_longer_term_counts_separately(self):
        ru = "Восстановление быстрое, без длительного восстановления."
        self.assertEqual(counted(ru, "recovery"), ["восстановление", "длительное восстановление"])
        self.assertEqual(len(problems_of(ru, "A quick recovery, no lengthy downtime.")), 1)

    def test_same_term_in_two_glossary_sections_counts_once(self):
        """«Эндосфера-терапия» — название услуги и термин текста: одно место, одно слово."""
        self.assertEqual(problems_of("Эндосфера-терапия", "Endosphere therapy"), [])

    def test_repeated_term_counts_once(self):
        ru = "LPG-массаж для тела. LPG-массаж для лица."
        self.assertEqual(problems_of(ru, "LPG massage for the body and for the face."), [])

    def test_term_inside_term_of_other_word_still_counts(self):
        """«Игольчатый RF-лифтинг» внутри «…Morpheus 8» требует своё «RF»: длинный
        термин гасит только термины со своим словом required."""
        ru = "Игольчатый RF-лифтинг Morpheus 8"
        self.assertEqual(counted(ru, "RF"), ["игольчатый RF-лифтинг"])
        self.assertEqual(counted(ru, "Morpheus8"), ["Игольчатый RF-лифтинг Morpheus 8"])
        self.assertEqual(problems_of(ru, "Morpheus8 RF microneedling"), [])
        self.assertEqual(len(problems_of(ru, "Morpheus8 microneedling")), 1)


class ExceptionTest(unittest.TestCase):
    def test_term_exception_lifts_count_finding(self):
        exception = {"path": PATH, "check": "terms", "term": "non-surgical", "reason": "намеренно"}
        self.assertEqual(problems_of(TWO_TERMS, ONE_NON_SURGICAL, [exception]), [])


class MissingWordsTest(unittest.TestCase):
    def test_shortfall_is_terms_minus_present(self):
        missing = pair_terms.missing_words(TWO_TERMS, ONE_NON_SURGICAL, TERMS)
        self.assertEqual([(item.required, item.present, item.shortfall) for item in missing],
                         [("non-surgical", 1, 1)])

    def test_enough_occurrences_give_nothing(self):
        english = "non-surgical, Non-Surgical rejuvenation"
        self.assertEqual(pair_terms.missing_words(TWO_TERMS, english, TERMS), [])


class PseudoTranslationTest(unittest.TestCase):
    def test_pseudo_text_gets_one_word_per_term(self):
        pseudo = pseudo_content({"intro": TWO_TERMS})["intro"]
        self.assertEqual(pseudo.lower().count("non-surgical"), 2)
        self.assertEqual(problems_of(TWO_TERMS, pseudo), [])


if __name__ == "__main__":
    unittest.main()
