import unittest

import typography
from typography_rules import NO_BREAK_SPACE as NBSP


def body(text):
    return f"<html><head><title>{text}</title></head><body><p>{text}</p></body></html>"


def paragraph_of(html):
    return html.split("<p>")[1].split("</p>")[0]


def bound(text, language):
    return paragraph_of(typography.bind_short_words(body(text), language))


class RussianRulesTest(unittest.TestCase):
    def test_preposition_stays_with_next_word(self):
        self.assertEqual(bound("в самом сердце Дананга", "ru"), f"в{NBSP}самом сердце Дананга")

    def test_chain_of_short_words(self):
        self.assertEqual(bound("и в самом", "ru"), f"и{NBSP}в{NBSP}самом")

    def test_capitalised_word_is_bound_too(self):
        self.assertEqual(bound("В Neva Beauty", "ru"), f"В{NBSP}Neva Beauty")

    def test_negation_particle_stays_with_next_word(self):
        self.assertEqual(bound("не найдена", "ru"), f"не{NBSP}найдена")

    def test_trailing_particle_stays_with_previous_word(self):
        self.assertEqual(bound("если бы ни один", "ru"), f"если{NBSP}бы ни{NBSP}один")
        self.assertEqual(bound("сделал бы это", "ru"), f"сделал{NBSP}бы это")

    def test_long_word_is_not_bound(self):
        self.assertEqual(bound("аппаратная косметология", "ru"), "аппаратная косметология")

    def test_short_letters_inside_words_and_hyphenated_words_are_left_alone(self):
        self.assertEqual(bound("SMAS лифтинг и по-русски в кафе-баре", "ru"),
                         f"SMAS лифтинг и{NBSP}по-русски в{NBSP}кафе-баре")

    def test_dash_does_not_start_a_line(self):
        self.assertEqual(bound("Дананг — центр", "ru"), f"Дананг{NBSP}— центр")
        self.assertEqual(bound("Дананг – центр", "ru"), f"Дананг{NBSP}– центр")

    def test_hyphen_with_spaces_is_a_dash_too(self):
        self.assertEqual(bound("LPG Массаж - Тело", "ru"), f"LPG Массаж{NBSP}- Тело")

    def test_hyphen_inside_words_is_left_alone(self):
        self.assertEqual(bound("Эндосфера-терапия", "ru"), "Эндосфера-терапия")

    def test_price_stays_whole(self):
        self.assertEqual(bound("стоит 2 500 000 đ за глаза", "ru"),
                         f"стоит 2{NBSP}500{NBSP}000{NBSP}đ за{NBSP}глаза")

    def test_number_stays_with_unit(self):
        self.assertEqual(bound("30 минут, 8 сеансов, 5 см", "ru"),
                         f"30{NBSP}минут, 8{NBSP}сеансов, 5{NBSP}см")

    def test_unit_forms_are_bound(self):
        self.assertEqual(bound("5 минут, 3 часа, 2 месяца, 4 дня, 6 недель, 2 года", "ru"),
                         f"5{NBSP}минут, 3{NBSP}часа, 2{NBSP}месяца, 4{NBSP}дня, 6{NBSP}недель, 2{NBSP}года")

    def test_words_that_only_start_like_a_unit_are_not_bound(self):
        text = "5 минимальный, 2 место, 3 часто, 4 дно, 7 месячных, 1 разный"
        self.assertEqual(bound(text, "ru"), text)

    def test_number_followed_by_ordinary_word_is_free(self):
        self.assertEqual(bound("M22 фотоомоложение, 3 зоны", "ru"), "M22 фотоомоложение, 3 зоны")

    def test_number_does_not_end_a_line_before_short_word(self):
        self.assertEqual(bound("Morpheus 8 и фотоомоложение", "ru"),
                         f"Morpheus 8{NBSP}и{NBSP}фотоомоложение")

    def test_range_with_short_words_is_bound_into_one_chain(self):
        self.assertEqual(bound("с 10 до 20", "ru"), f"с{NBSP}10{NBSP}до{NBSP}20")


class EnglishRulesTest(unittest.TestCase):
    def test_articles_and_prepositions_stay_with_next_word(self):
        self.assertEqual(bound("even in a hot climate", "en"), f"even in{NBSP}a{NBSP}hot climate")
        self.assertEqual(bound("back to the home page", "en"),
                          f"back to{NBSP}the{NBSP}home page")

    def test_ampersand_stays_with_next_word(self):
        self.assertEqual(bound("Face Lift &amp; Rejuvenation", "en"),
                         f"Face Lift &amp;{NBSP}Rejuvenation")

    def test_ampersand_inside_a_word_is_left_alone(self):
        self.assertEqual(bound("R&amp;D team", "en"), "R&amp;D team")

    def test_russian_words_are_not_bound_in_english_text(self):
        self.assertEqual(bound("в самом сердце", "en"), "в самом сердце")

    def test_english_words_are_not_bound_in_russian_text(self):
        self.assertEqual(bound("the best a", "ru"), "the best a")

    def test_price_stays_whole(self):
        self.assertEqual(bound("costs 1 000 000 đ", "en"), f"costs 1{NBSP}000{NBSP}000{NBSP}đ")

    def test_number_stays_with_unit(self):
        self.assertEqual(bound("60 minutes, 10 sessions, 5 cm", "en"),
                         f"60{NBSP}minutes, 10{NBSP}sessions, 5{NBSP}cm")

    def test_number_does_not_end_a_line_before_short_word(self):
        self.assertEqual(bound("Morpheus 8 and facials", "en"), f"Morpheus 8{NBSP}and{NBSP}facials")

    def test_pronoun_i_stays_with_next_word(self):
        self.assertEqual(bound("sessions do I need?", "en"), f"sessions do I{NBSP}need?")

    def test_dash_does_not_start_a_line(self):
        self.assertEqual(bound("only — by appointment", "en"), f"only{NBSP}— by{NBSP}appointment")


class UntouchedPlacesTest(unittest.TestCase):
    def apply(self, html, language="ru"):
        return typography.bind_short_words(html, language)

    def test_head_is_untouched(self):
        html = self.apply(body("в самом сердце"))
        self.assertIn("<title>в самом сердце</title>", html)

    def test_attributes_are_untouched(self):
        source = '<body><a href="/x" aria-label="в самом сердце" title="и в">в самом</a></body>'
        self.assertEqual(self.apply(source),
                         f'<body><a href="/x" aria-label="в самом сердце" title="и в">в{NBSP}самом</a></body>')

    def test_attribute_with_closing_bracket_is_not_split(self):
        source = '<body><p data-x="a > в b">в самом</p></body>'
        self.assertIn('data-x="a > в b"', self.apply(source))

    def test_script_style_code_pre_textarea_svg_are_untouched(self):
        for tag in ("script", "style", "code", "pre", "textarea", "svg"):
            with self.subTest(tag=tag):
                source = f"<body><{tag}>в самом</{tag}><p>в самом</p></body>"
                self.assertEqual(self.apply(source),
                                 f"<body><{tag}>в самом</{tag}><p>в{NBSP}самом</p></body>")

    def test_comments_are_untouched(self):
        self.assertIn("<!-- в самом -->", self.apply("<body><!-- в самом --></body>"))

    def test_nested_elements_inside_untouched_tag_stay_untouched(self):
        source = "<body><pre>в <b>самом</b> в самом</pre><p>в самом</p></body>"
        self.assertEqual(self.apply(source),
                         f"<body><pre>в <b>самом</b> в самом</pre><p>в{NBSP}самом</p></body>")

    def test_short_word_before_tag_is_bound(self):
        self.assertEqual(self.apply("<body><p>в <a>самом</a></p></body>"),
                         f"<body><p>в{NBSP}<a>самом</a></p></body>")

    def test_unknown_language_and_missing_body_leave_page_alone(self):
        self.assertEqual(self.apply(body("в самом"), "de"), body("в самом"))
        self.assertEqual(self.apply("<p>в самом</p>"), "<p>в самом</p>")

    def test_language_with_region_uses_its_base_rules(self):
        self.assertIn(f"in{NBSP}a", self.apply("<body><p>in a</p></body>", "en-US"))

    def test_second_pass_changes_nothing(self):
        once = self.apply(body("в самом сердце — 2 500 000 đ"))
        self.assertEqual(self.apply(once), once)


if __name__ == "__main__":
    unittest.main()
