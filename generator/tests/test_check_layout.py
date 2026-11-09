import shutil
import tempfile
import unittest
from pathlib import Path

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


class ListSitePagesTest(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        for folder in ("privacy", "lpg-massazh", "en", "en/privacy", "en/carbon-laser-peel"):
            (root / folder).mkdir(parents=True)
            (root / folder / "index.html").write_text("")
        (root / "assets").mkdir()
        (root / "en" / "assets").mkdir()
        (root / "index.html").write_text("")
        self.pages = check_layout.list_site_pages(root)

    def test_russian_pages_go_first_sorted_with_not_found(self):
        self.assertEqual(["/", "/404.html", "/lpg-massazh/", "/privacy/"], self.pages[:4])

    def test_english_pages_follow_sorted_with_not_found(self):
        self.assertEqual(["/en/", "/en/404.html", "/en/carbon-laser-peel/", "/en/privacy/"],
                         self.pages[4:])

    def test_folders_without_index_and_english_root_are_skipped(self):
        self.assertNotIn("/assets/", self.pages)
        self.assertNotIn("/en/assets/", self.pages)
        self.assertNotIn("/en/en/", self.pages)

    def test_english_root_not_in_russian_list(self):
        russian = check_layout.pages_of_language(self.pages, "ru")
        self.assertNotIn("/en/", russian)
        self.assertEqual(4, len(russian))


class PageLanguageTest(unittest.TestCase):
    def test_english_by_prefix(self):
        self.assertEqual("en", check_layout.page_language("/en/"))
        self.assertEqual("en", check_layout.page_language("/en/404.html"))
        self.assertEqual("en", check_layout.page_language("/en/privacy/"))

    def test_russian_otherwise(self):
        self.assertEqual("ru", check_layout.page_language("/"))
        self.assertEqual("ru", check_layout.page_language("/english-lessons/"))


class NarrowErrorTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual("/privacy/ 250 px [меню]: кнопка .drawer__close 38.4×44.0",
                         check_layout.narrow_error("/privacy/", 250, "меню", "кнопка .drawer__close 38.4×44.0"))

    def test_every_finding_becomes_a_line(self):
        errors = check_layout.narrow_errors("/", 320, "закрыто", ["a", "b"])
        self.assertEqual(["/ 320 px [закрыто]: a", "/ 320 px [закрыто]: b"], errors)

    def test_no_pages_is_an_error(self):
        self.assertIn("ни одной страницы", check_layout.no_pages_error())


if __name__ == "__main__":
    unittest.main()
