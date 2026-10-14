import copy
import unittest

import pricing

SECTIONS = [
    {"section": "Цены - Женщины", "items": [
        {"name": "КОМБО 1 (подмышки, голени)", "desc": "", "price": "1 600 000 đ"},
        {"name": "Лоб", "desc": "", "price": "150 000 đ"},
        {"name": "Сыворотка", "desc": "Дополнительно к процедурам", "price": "+350 000 đ"},
        {"name": "Костюм для LPG", "desc": "", "price": "400 000 đ", "addon": True},
        {"name": "Консультация", "desc": "", "price": ""},
    ]},
    {"section": "Цены - Мужчины", "items": [
        {"name": "Лоб", "desc": "", "price": "200 000 đ"},
    ]},
]
SINGLE = [{"items": [{"name": "Карбоновый пилинг", "desc": "", "price": "1 100 000 đ"}]}]


def from_ru(price):
    return f"от {price}"


class PriceValueTest(unittest.TestCase):
    def test_plain_price(self):
        self.assertEqual(pricing.price_value("1 500 000 đ"), 1500000)

    def test_addon_price(self):
        self.assertEqual(pricing.price_value("+350 000 đ"), 350000)

    def test_empty_price_is_none(self):
        self.assertIsNone(pricing.price_value("  "))

    def test_range_is_error(self):
        with self.assertRaisesRegex(ValueError, "Непонятная цена"):
            pricing.price_value("1 000 000 – 2 000 000 đ")


class AddonTest(unittest.TestCase):
    def test_plus_sign_marks_addon(self):
        self.assertTrue(pricing.is_addon(SECTIONS[0]["items"][2]))

    def test_flag_marks_addon(self):
        self.assertTrue(pricing.is_addon(SECTIONS[0]["items"][3]))

    def test_regular_position_is_not_addon(self):
        self.assertFalse(pricing.is_addon(SECTIONS[0]["items"][1]))


class AggregateTest(unittest.TestCase):
    def test_range_skips_addons_and_empty_prices(self):
        self.assertEqual(pricing.price_aggregate(SECTIONS, "VND"),
                         {"low": 150000, "high": 1600000, "count": 3, "currency": "VND"})

    def test_no_prices_is_none(self):
        self.assertIsNone(pricing.price_aggregate([], "VND"))


class HintTest(unittest.TestCase):
    def test_several_prices_give_from_minimum(self):
        self.assertEqual(pricing.price_hint(SECTIONS, from_ru), "от 150 000 đ")

    def test_single_price_is_shown_exactly(self):
        self.assertEqual(pricing.price_hint(SINGLE, from_ru), "1 100 000 đ")

    def test_no_prices_is_none(self):
        self.assertIsNone(pricing.price_hint([], from_ru))

    def test_from_label_comes_from_caller(self):
        self.assertEqual(pricing.price_hint(SECTIONS, lambda price: f"from {price}"),
                         "from 150 000 đ")


class PopularPriceTest(unittest.TestCase):
    def test_same_name_in_two_sections_gives_from_minimum(self):
        self.assertEqual(pricing.popular_price({"epil": SECTIONS}, "epil", "Лоб", from_ru),
                         "от 150 000 đ")

    def test_unique_name_gives_exact_price(self):
        name = "КОМБО 1 (подмышки, голени)"
        self.assertEqual(pricing.popular_price({"epil": SECTIONS}, "epil", name, from_ru),
                         "1 600 000 đ")

    def test_missing_position_is_error(self):
        with self.assertRaisesRegex(ValueError, "нет позиции"):
            pricing.popular_price({"epil": SECTIONS}, "epil", "Нос", from_ru)


class OfferSectionsTest(unittest.TestCase):
    def test_keeps_only_payable_positions(self):
        self.assertEqual(pricing.offer_sections(SECTIONS, "Цены"), [
            {"title": "Цены - Женщины", "items": [
                {"name": "КОМБО 1 (подмышки, голени)", "desc": "", "price": 1600000},
                {"name": "Лоб", "desc": "", "price": 150000}]},
            {"title": "Цены - Мужчины", "items": [
                {"name": "Лоб", "desc": "", "price": 200000}]},
        ])

    def test_default_title_for_unnamed_section(self):
        self.assertEqual(pricing.offer_sections(SINGLE, "Цены")[0]["title"], "Цены")


class CompareRowsTest(unittest.TestCase):
    SERVICES = {"epil": {"title": "Лазерная эпиляция"}}
    ROWS = [{"slug": "epil", "task": "Нежелательные волосы"}]

    def test_row_gets_title_and_price(self):
        rows = pricing.compare_rows(self.ROWS, self.SERVICES, {"epil": SECTIONS}, from_ru)
        self.assertEqual(rows, [{"title": "Лазерная эпиляция", "task": "Нежелательные волосы",
                                 "price": "от 150 000 đ"}])

    def test_unknown_service_is_error(self):
        with self.assertRaisesRegex(ValueError, "нет услуги"):
            pricing.compare_rows([{"slug": "net", "task": ""}], self.SERVICES, {}, from_ru)

    def test_service_without_price_is_error(self):
        with self.assertRaisesRegex(ValueError, "нет цены"):
            pricing.compare_rows(self.ROWS, self.SERVICES, {}, from_ru)


class ComboTest(unittest.TestCase):
    def test_combo_is_detected_by_name(self):
        self.assertTrue(pricing.is_combo({"name": "КОМБО 1 (подмышки)"}))
        self.assertTrue(pricing.is_combo({"name": "Комбо лицо"}))
        self.assertFalse(pricing.is_combo({"name": "Лоб"}))

    def test_price_view_marks_combos_without_touching_source(self):
        source = copy.deepcopy(SECTIONS)
        view = pricing.price_view(SECTIONS)
        self.assertTrue(view[0]["items"][0]["is_combo"])
        self.assertFalse(view[0]["items"][1]["is_combo"])
        self.assertEqual(view[0]["section"], "Цены - Женщины")
        self.assertEqual(SECTIONS, source)


if __name__ == "__main__":
    unittest.main()
