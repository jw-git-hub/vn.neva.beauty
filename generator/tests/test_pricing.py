import copy
import unittest

import build
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


PRICE_TOKEN = "{price}"
WOMEN, SINGLE_SECTION, ONE_SESSION = "Цены - Женщины", "Цены", "1 сеанс"


def cheapest_positions(prices, service_ids):
    """Позиции с самой низкой ценой среди услуг: {(услуга, раздел, название, описание)}.
    Отбор тот же, что у pricing.price_hint: доплаты и позиции без цены не в счёт."""
    payable = [((slug, sec.get("section"), item["name"], item.get("desc", "")), value)
               for slug in service_ids for sec in prices.get(slug, []) for item in sec["items"]
               if not pricing.is_addon(item)
               and (value := pricing.price_value(item["price"])) is not None]
    low = min(value for _, value in payable)
    return {position for position, value in payable if value == low}


def pages_with_price_in_faq(content):
    """Услуги и направления, в ответах FAQ которых стоит {price}: {страница: её услуги}."""
    pages = {slug: [slug] for slug, svc in content["services"].items()
             if any(PRICE_TOKEN in item["a"] for item in svc.get("faq", []))}
    pages.update({cat["slug"]: cat["services"] for cat in content["categories"]
                  if any(PRICE_TOKEN in item["a"] for item in cat.get("faq", []))})
    return pages


class CheapestPositionNamedInFaqTest(unittest.TestCase):
    """Ответ «Сколько стоит…» начинается с цены и называет словами позицию прайса, к которой
    она относится: «стоит от 700 000 đ (лицо, 1 сеанс)». Цифру подставляет сборка из
    prices.json, а название позиции написано в content.yml и в накладке en. Тест падает,
    если самой дешёвой стала другая позиция: тогда поправьте скобки в обоих языках и NAMED."""
    NAMED = {
        "lazernaya-epilyaciya": {("lazernaya-epilyaciya", WOMEN, "Лоб", ""),
                                 ("lazernaya-epilyaciya", WOMEN, "Верхняя губа", "")},
        "lpg-massazh": {("lpg-massazh", SINGLE_SECTION, "LPG Массаж - Лицо", ONE_SESSION)},
        "endosfera-terapiya": {("endosfera-terapiya", SINGLE_SECTION, "Эндосфера-терапия - Лицо",
                                ONE_SESSION)},
        "ultrazvukovaya-kavitaciya": {("ultrazvukovaya-kavitaciya", SINGLE_SECTION, "УЗ-кавитация",
                                       ONE_SESSION)},
        "esteticheskaya-kosmetologiya-i-uhod": {("esteticheskaya-kosmetologiya-i-uhod",
                                                 SINGLE_SECTION, "Маска HydroPeptid", "")},
        "smas-lifting": {("smas-lifting", SINGLE_SECTION, "Глаза", "")},
        "udalenie-tatuirovok-lazerom": {("udalenie-tatuirovok-lazerom", SINGLE_SECTION,
                                         "3 × 5 см", "")},
        "udalenye-permanentnogo-makiyazha": {("udalenye-permanentnogo-makiyazha", SINGLE_SECTION,
                                              "Брови", "")},
        "karbonovyy-lazernyy-piling": {("karbonovyy-lazernyy-piling", SINGLE_SECTION,
                                        "Карбоновый лазерный пилинг", "")},
        "morpheus-8-rf-lifting": {("morpheus-8-rf-lifting", SINGLE_SECTION, "Кисти", "")},
        "fotoomolozhenie-m22": {("fotoomolozhenie-m22", SINGLE_SECTION, "Кисти рук", "")},
        "korrekciya-figury": {("endosfera-terapiya", SINGLE_SECTION, "Эндосфера-терапия - Лицо",
                               ONE_SESSION)},
        "lifting-i-omolozhenie": {("morpheus-8-rf-lifting", SINGLE_SECTION, "Кисти", "")},
        "lazernye-procedury": {("lazernaya-epilyaciya", WOMEN, "Лоб", ""),
                               ("lazernaya-epilyaciya", WOMEN, "Верхняя губа", "")},
    }

    @classmethod
    def setUpClass(cls):
        _, content, cls.prices = build.load()
        cls.pages = pages_with_price_in_faq(content)

    def test_every_page_with_price_in_faq_is_listed(self):
        self.assertEqual(set(self.pages), set(self.NAMED))

    def test_named_position_is_still_the_cheapest(self):
        for page, services in self.pages.items():
            with self.subTest(page=page):
                self.assertEqual(cheapest_positions(self.prices, services), self.NAMED.get(page))
