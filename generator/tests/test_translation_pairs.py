import tempfile
import unittest
from pathlib import Path

import pair_exceptions
import pair_terms
import translation_pairs as tp
import yaml

TERMS = pair_terms.load_terms("en")
NEBSP = " "
NARROW = " "


def page(path, ru, en):
    return tp.Pair(path, ru, en, tp._page_checks(path))


def problems_of(pair, exceptions=()):
    return tp.pair_problems([pair], TERMS, list(exceptions))


def exception(path, check, reason="намеренно", **extra):
    return {"path": path, "check": check, "reason": reason, **extra}


class NumbersTest(unittest.TestCase):
    def test_lost_number_is_named(self):
        pair = tp.Pair("x", "6 сеансов за 8 недель", "6 sessions", tp.CHECKS_OF_SITE)
        self.assertEqual(problems_of(pair),
                         ["x: числа: в русском [6, 8], в переводе [6]"])

    def test_reordered_numbers_pass(self):
        pair = tp.Pair("x", "6 сеансов за 8 недель", "within 8 weeks, 6 sessions", tp.CHECKS_OF_SITE)
        self.assertEqual(problems_of(pair), [])

    def test_decimal_comma_equals_point(self):
        pair = tp.Pair("x", "1,5 часа", "1.5 hours", tp.CHECKS_OF_SITE)
        self.assertEqual(problems_of(pair), [])

    def test_thousand_groups_are_one_number(self):
        for separator in (" ", NEBSP, NARROW):
            pair = tp.Pair("x", f"4{separator}000{separator}000 đ", "4000000 dong", tp.CHECKS_OF_SITE)
            self.assertEqual(problems_of(pair), [], repr(separator))

    def test_glued_unit_is_caught(self):
        pair = tp.Pair("prices names «Курс»", "Курс 500000 VND", "Course 500000VND", tp.CHECKS_OF_PRICE)
        self.assertEqual(problems_of(pair), [])
        lost = tp.Pair("prices names «Курс»", "Курс 500 000 VND", "Course VND", tp.CHECKS_OF_PRICE)
        self.assertEqual(problems_of(lost),
                         ["prices names «Курс»: числа: в русском [500000], в переводе []"])

    def test_numbers_in_href_placeholder_and_attributes_do_not_count(self):
        ru = '<a href="/page-2/" title="3 шага">ссылка</a> {price2} и 5 дней'
        en = '<a href="/page-2/">link</a> {price2} and 5 days'
        self.assertEqual(problems_of(page("home.intro", ru, en)), [])


class PlaceholdersTest(unittest.TestCase):
    def test_lost_placeholder_is_named(self):
        pair = tp.Pair("site tagline", "от {price}, {price}", "from {price}", tp.CHECKS_OF_SITE)
        self.assertEqual(problems_of(pair),
                         ["site tagline: плейсхолдеры: в русском [{price}, {price}], в переводе [{price}]"])

    def test_same_placeholders_in_other_order_pass(self):
        pair = tp.Pair("x", "{a} и {b}", "{b} and {a}", tp.CHECKS_OF_SITE)
        self.assertEqual(problems_of(pair), [])


class SeveralPlaceholdersTest(unittest.TestCase):
    def test_each_differing_placeholder_is_its_own_finding(self):
        pair = tp.Pair("x", "{a} {b} {c}", "{c}", tp.CHECKS_OF_SITE)
        problems = problems_of(pair)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].endswith("— {a}") and problems[1].endswith("— {b}"))


class LinksTest(unittest.TestCase):
    RU = 'Запись в <a href="{whatsapp}">WhatsApp</a>, <a href="/lpg-massazh/">LPG</a>.'

    def test_lost_and_extra_links_are_named(self):
        en = 'Book via <a href="/lpg-massage/">LPG</a>, <a href="/lpg-massazh/">LPG</a>.'
        self.assertEqual(problems_of(page("home.faq[0].a", self.RU, en)),
                         ["home.faq[0].a: плейсхолдеры: в русском [{whatsapp}], в переводе []",
                          "home.faq[0].a: ссылки: нет в переводе [{whatsapp}]; "
                          "лишнее в переводе [/lpg-massage/]"])

    def test_internal_links_keep_russian_identifier(self):
        en = 'Book via <a href="{whatsapp}">WhatsApp</a>, <a href="/lpg-massazh/">LPG</a>.'
        self.assertEqual(problems_of(page("home.faq[0].a", self.RU, en)), [])

    def test_links_in_other_order_pass(self):
        en = '<a href="/lpg-massazh/">LPG</a> and <a href="{whatsapp}">WhatsApp</a>'
        self.assertEqual(problems_of(page("home.faq[0].a", self.RU, en)), [])


class TagsTest(unittest.TestCase):
    def test_lost_and_extra_tags_are_named(self):
        ru = "<p>Один</p><p>Два</p><strong>важно</strong>"
        en = "<p>One</p><em>important</em>"
        self.assertEqual(problems_of(page("home.intro", ru, en)),
                         ["home.intro: теги: нет в переводе [p, strong]; лишнее в переводе [em]"])

    def test_same_tags_in_other_order_pass(self):
        self.assertEqual(problems_of(page("home.intro", "<b>а</b> <i>б</i>", "<i>b</i> <b>a</b>")), [])

    def test_plain_text_has_no_tags(self):
        self.assertEqual(problems_of(page("home.title", "Заголовок", "Title")), [])


POLICY_RU = "<section><h1>Политика</h1><p>1. Текст <a href='https://a'>сайт</a></p><ul><li>раз</li></ul></section>"
DISCLAIMER = ('<p>Перевод для удобства. Русская версия: '
              '<a href="https://vn.neva.beauty/privacy/" hreflang="ru">здесь</a></p>')


def policy(russian, english):
    return tp.privacy_pairs((russian, english))[0]


class PrivacyTest(unittest.TestCase):
    def test_disclaimer_paragraph_is_ignored(self):
        english = ("<section><h1>Policy</h1>" + DISCLAIMER +
                   "<p>1. Text <a href='https://a'>site</a></p><ul><li>one</li></ul></section>")
        self.assertEqual(problems_of(policy(POLICY_RU, english)), [])

    def test_tag_order_matters_in_document(self):
        english = ("<section><h1>Policy</h1><ul><li>one</li></ul>"
                   "<p>1. Text <a href='https://a'>site</a></p></section>")
        message = problems_of(policy(POLICY_RU, english))[0]
        self.assertTrue(message.startswith("privacy: теги: порядок расходится на позиции 3 "), message)
        self.assertIn("в русском <p>, в переводе <ul>", message)

    def test_lost_link_is_named(self):
        english = "<section><h1>Policy</h1><p>1. Text site</p><ul><li>one</li></ul></section>"
        self.assertIn("privacy: ссылки: нет в переводе [https://a]", problems_of(policy(POLICY_RU, english)))

    def test_link_is_checked_without_disclaimer_link(self):
        english = ("<section><h1>Policy</h1>" + DISCLAIMER +
                   "<p>1. Text <a href='https://b'>site</a></p><ul><li>one</li></ul></section>")
        self.assertEqual(problems_of(policy(POLICY_RU, english)),
                         ["privacy: ссылки: нет в переводе [https://a]; лишнее в переводе [https://b]"])

    def test_no_privacy_translation_gives_no_pair(self):
        self.assertEqual(tp.privacy_pairs(None), [])


class RequiredTermsTest(unittest.TestCase):
    def check(self, ru, en, path="services.x.faq[0].a"):
        return problems_of(page(path, ru, en))

    def test_missing_required_word_is_named(self):
        self.assertEqual(
            self.check("Подбирается на консультации.", "Chosen individually."),
            ["services.x.faq[0].a: термины: в русском «консультации» (термин «консультация»), "
             "в переводе нет «consultation»"])

    def test_present_word_passes_in_any_case(self):
        self.assertEqual(self.check("Подбирается на консультации.", "Chosen at the CONSULTATION."), [])

    def test_stem_finds_case_forms(self):
        for ru, word in (("Подходит для LPG-массажа.", "LPG"),
                         ("Есть противопоказания.", "contraindication"),
                         ("О противопоказаниях скажем.", "contraindication"),
                         ("Лечение целлюлита", "cellulite")):
            found = [problem for problem in self.check(ru, "Text.") if f"«{word}»" in problem]
            self.assertEqual(len(found), 1, ru)

    def test_stem_does_not_fire_on_other_word(self):
        self.assertEqual(self.check("Процедура противоядие и консервация.", "Text."), [])

    def test_yo_and_ye_are_the_same(self):
        self.assertEqual(len(self.check("Тепло и лёгкое покалывание.", "Warm.")), 1)
        self.assertEqual(len(self.check("Тепло и легкое покалывание.", "Warm.")), 1)

    def test_words_of_term_must_follow_each_other(self):
        self.assertEqual(self.check("Лёгкое тепло, а ещё покалывание.", "Warm."), [])

    def test_latin_word_needs_word_boundary(self):
        self.assertEqual(self.check("Метод XRFX", "Text."), [])
        self.assertEqual(len(self.check("Метод RF", "Text.")), 1)

    def test_required_word_takes_english_endings_only(self):
        self.assertEqual(self.check("Рубцы", "Scars are visible."), [])
        self.assertEqual(self.check("Проводится безболезненно", "Done painlessly."), [])
        self.assertEqual(len(self.check("Рубцы", "Scarcity.")), 1)

    def test_required_phrase_and_non_ascii_symbols(self):
        self.assertEqual(self.check("Лимфодренаж", "Lymphatic drainage."), [])
        self.assertEqual(len(self.check("Лимфодренаж", "Drainage of lymph.")), 1)

    def test_tags_are_not_text(self):
        ru = '<a href="/lpg-massazh/" title="консультация">LPG-массаж</a>'
        self.assertEqual(self.check(ru, '<a href="/lpg-massazh/">LPG massage</a>'), [])

    def test_seo_fields_skip_terms(self):
        self.assertEqual(self.check("Консультация", "Booking", path="home.seo_title"), [])
        self.assertEqual(self.check("Консультация", "Booking", path="home.seo_desc"), [])

    def test_ru_match_replaces_stems(self):
        entry = {"ru": "Вьетнам", "required": "Vietnam", "ru_match": r"вьетнам(?!ск)"}
        terms = (pair_terms._term_of(entry),)
        self.assertEqual(tp.pair_problems([page("a.b", "Цены во вьетнамских донгах", "dong")],
                                          terms, []), [])
        self.assertEqual(len(tp.pair_problems([page("a.b", "Отдых во Вьетнаме", "rest")],
                                              terms, [])), 1)
        stems = (pair_terms._term_of({"ru": "Вьетнам", "required": "Vietnam"}),)
        self.assertEqual(len(tp.pair_problems([page("a.b", "во вьетнамских донгах", "dong")],
                                              stems, [])), 1)


class ExceptionsTest(unittest.TestCase):
    PAIR = page("home.faq[0].a", "6 сеансов", "sessions")
    NUMBERS = exception("home.faq[0].a", "numbers")

    def test_exception_removes_one_check_of_one_string(self):
        self.assertEqual(problems_of(self.PAIR, [self.NUMBERS]), [])

    def test_exception_for_other_check_keeps_finding(self):
        problems = problems_of(self.PAIR, [exception("home.faq[0].a", "tags")])
        self.assertEqual(problems[0], "home.faq[0].a: числа: в русском [6], в переводе []")
        self.assertIn("исключение ничего не снимает", problems[1])

    def test_exception_for_term_removes_only_that_term(self):
        pair = page("home.faq[0].a", "Консультация и осмотр", "Text")
        problems = problems_of(pair, [exception("home.faq[0].a", "terms", term="consultation")])
        self.assertEqual(len(problems), 1)
        self.assertIn("«assessment»", problems[0])

    def test_terms_exception_needs_term(self):
        pair = page("home.faq[0].a", "Консультация", "Text")
        problems = problems_of(pair, [exception("home.faq[0].a", "terms")])
        self.assertTrue(any("нужно поле term" in problem for problem in problems))
        self.assertTrue(any(problem.endswith("в переводе нет «consultation»") for problem in problems))

    def test_exception_for_placeholder_removes_only_that_placeholder(self):
        pair = page("home.faq[1].a", "{consultation_price}, дерматолога — {dermatology_price}",
                    "A consultation")
        problems = problems_of(pair, [exception("home.faq[1].a", "placeholders",
                                                placeholder="{dermatology_price}")])
        self.assertEqual(len(problems), 1)
        self.assertIn("{consultation_price}", problems[0])

    def test_lost_whatsapp_placeholder_is_still_caught_next_to_exception(self):
        ru = 'Запись в <a href="{whatsapp}">WhatsApp</a>, дерматолога — {dermatology_price}'
        en = 'Booking by <a href="https://wa.me/1">WhatsApp</a>'
        problems = problems_of(page("home.faq[1].a", ru, en), [
            exception("home.faq[1].a", "placeholders", placeholder="{dermatology_price}")])
        self.assertTrue(any("плейсхолдеры" in problem and "{whatsapp}" in problem
                            for problem in problems))
        self.assertFalse(any("{dermatology_price}" in problem and "исключение" in problem
                             for problem in problems))

    def test_placeholders_exception_needs_placeholder(self):
        pair = page("home.faq[1].a", "{a}", "text")
        problems = problems_of(pair, [exception("home.faq[1].a", "placeholders")])
        self.assertTrue(any("нужно поле placeholder" in problem for problem in problems))
        self.assertTrue(any(problem.startswith("home.faq[1].a: плейсхолдеры") for problem in problems))

    def test_stale_placeholder_exception_is_a_problem(self):
        fixed = page("home.faq[1].a", "{a}", "{a}")
        problems = problems_of(fixed, [exception("home.faq[1].a", "placeholders", placeholder="{a}")])
        self.assertIn("исключение ничего не снимает", problems[0])

    def test_stale_exception_is_a_problem(self):
        fixed = page("home.faq[0].a", "6 сеансов", "6 sessions")
        self.assertEqual(problems_of(fixed, [self.NUMBERS]),
                         ["pair_exceptions «home.faq[0].a» numbers: исключение ничего не снимает — "
                          "устарело, удалите его"])

    def test_exception_without_reason_is_a_problem_and_removes_nothing(self):
        problems = problems_of(self.PAIR, [exception("home.faq[0].a", "numbers", reason=" ")])
        self.assertEqual(problems, ["home.faq[0].a: числа: в русском [6], в переводе []",
                                    "pair_exceptions «home.faq[0].a» numbers: нет причины (reason)"])

    def test_unknown_check_is_a_problem(self):
        problems = problems_of(self.PAIR, [exception("home.faq[0].a", "spelling")])
        self.assertTrue(any("неизвестная проверка" in problem for problem in problems))

    def test_exception_for_missing_path_is_a_problem(self):
        problems = problems_of(self.PAIR, [self.NUMBERS, exception("home.nothing", "numbers")])
        self.assertEqual(problems, ["pair_exceptions «home.nothing» numbers: такой строки среди пар нет"])

    def test_exception_of_untranslated_string_is_not_stale(self):
        pair = tp.Pair("home.faq[0].a", "6 сеансов", None, tp.CHECKS_OF_PAGE)
        self.assertEqual(problems_of(pair, [self.NUMBERS]), [])

    def test_group_prefix_is_known_to_status(self):
        import translation_status
        self.assertEqual(translation_status.group_of("pair_exceptions «x» numbers: нет причины"),
                         "pair_exceptions")


class LoadExceptionsTest(unittest.TestCase):
    def test_missing_and_empty_file_give_no_exceptions(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(pair_exceptions.load_exceptions("en", Path(directory)), [])
            (Path(directory) / "en").mkdir()
            (Path(directory) / "en" / pair_exceptions.EXCEPTIONS_FILE).write_text("exceptions: []\n")
            self.assertEqual(pair_exceptions.load_exceptions("en", Path(directory)), [])

    def test_real_file_has_only_valid_shape(self):
        entries = pair_exceptions.load_exceptions("en")
        self.assertTrue(all(isinstance(entry, dict) for entry in entries))


class CollectPairsTest(unittest.TestCase):
    CONTENT = {"home": {"seo_title": "Главная", "faq": [{"q": "Что?", "a": "От 2 до 3"}]}}

    def test_untranslated_paths_have_no_english_side(self):
        merged = {"home": {"seo_title": "Home", "faq": [{"q": "What?", "a": "От 2 до 3"}]}}
        pairs = tp.content_pairs(self.CONTENT, merged, {"home.faq[0].a"})
        self.assertEqual([(pair.path, pair.en) for pair in pairs],
                         [("home.seo_title", "Home"), ("home.faq[0].q", "What?"),
                          ("home.faq[0].a", None)])

    def test_site_pairs_use_site_paths(self):
        site = {"tagline": "Центр", "locations": [{"city": "Самуи", "country": "Таиланд"}]}
        pairs = tp.site_pairs(site, {"tagline": "Center"})
        self.assertEqual([(pair.path, pair.en) for pair in pairs],
                         [("site tagline", "Center"), ("site locations[0].city", None),
                          ("site locations[0].country", None)])

    def test_price_pairs_cover_names_and_sections_not_descs(self):
        prices = {"lpg": [{"section": "Цены", "items": [
            {"name": "Лицо", "desc": "5 сеансов", "price": "1 đ"}]}]}
        catalog = {"sections": {"Цены": "Prices"}, "names": {}, "descs": {"{0} сеансов": "{0} sessions"}}
        pairs = tp.price_pairs(prices, catalog)
        self.assertEqual([(pair.path, pair.en) for pair in pairs],
                         [("prices sections «Цены»", "Prices"), ("prices names «Лицо»", None)])

    def test_price_override_gets_service_suffix(self):
        catalog = {"overrides": {"lpg": {"names": {"Лицо": "Face"}}}}
        pairs = tp.price_pairs({}, catalog)
        self.assertEqual([pair.path for pair in pairs], ["prices names «Лицо» (lpg)"])


class RealGlossaryTest(unittest.TestCase):
    def test_every_required_term_is_recognised_in_its_own_russian_term(self):
        """Основа каждого термина находит сам термин: иначе проверка молча пропускала бы его."""
        entries = yaml.safe_load((Path(__file__).resolve().parent.parent / "data" / "locales" / "en"
                                  / "glossary.yml").read_text(encoding="utf-8"))["terms"]
        required = [entry for entry in entries if entry.get("required")]
        self.assertGreater(len(required), 60)
        for entry in required:
            found = pair_terms.required_terms(entry["ru"], TERMS)
            self.assertIn(entry["required"], [term.required for term, _ in found], entry["ru"])


if __name__ == "__main__":
    unittest.main()
