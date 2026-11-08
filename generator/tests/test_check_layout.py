import unittest

import check_layout


def rect(left, top, right, bottom):
    return {"left": left, "top": top, "right": right, "bottom": bottom}


PRICE = rect(100, 0, 200, 20)


def card(name, *lines):
    return {"name": name, "price": PRICE, "lines": list(lines)}


class RectsOverlapTest(unittest.TestCase):
    def test_intersecting_rects_overlap(self):
        self.assertTrue(check_layout.rects_overlap(rect(0, 0, 150, 20), PRICE))

    def test_touching_edges_do_not_overlap(self):
        self.assertFalse(check_layout.rects_overlap(rect(0, 0, 100, 20), PRICE))
        self.assertFalse(check_layout.rects_overlap(rect(100, 20, 200, 40), PRICE))

    def test_separate_rects_do_not_overlap(self):
        self.assertFalse(check_layout.rects_overlap(rect(0, 50, 90, 70), PRICE))


class CardOverlapsTest(unittest.TestCase):
    def test_any_line_over_price_counts(self):
        lines = (rect(0, 0, 50, 20), rect(0, 0, 120, 20))
        self.assertTrue(check_layout.card_overlaps(card("A", *lines)))

    def test_no_lines_over_price(self):
        self.assertFalse(check_layout.card_overlaps(card("A", rect(0, 0, 50, 20))))


class CardErrorsTest(unittest.TestCase):
    def test_overlap_is_reported_with_page_width_and_name(self):
        cards = [card("OK", rect(0, 0, 50, 20)), card("M22 PHOTOREJUVENATION", rect(90, 0, 150, 20))]
        self.assertEqual(
            ["/en/ 290 px: карточка «M22 PHOTOREJUVENATION» — текст наезжает на цену"],
            check_layout.card_errors("/en/", 290, cards))

    def test_clean_cards_give_no_errors(self):
        self.assertEqual([], check_layout.card_errors("/", 320, [card("A", rect(0, 0, 50, 20))]))

    def test_page_without_cards_is_an_error(self):
        errors = check_layout.card_errors("/", 320, [])
        self.assertEqual(1, len(errors))
        self.assertIn("нет ни одной карточки", errors[0])


if __name__ == "__main__":
    unittest.main()
