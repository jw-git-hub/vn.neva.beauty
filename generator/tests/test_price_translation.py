import unittest

import price_translation as pt

PRICES = {"lpg-massazh": [{"section": "Цены", "items": [
    {"name": "КОМБО 1 (тело)", "desc": "", "price": "1 600 000 đ"},
    {"name": "Лицо", "desc": "5 сеансов — курс 560 000 đ", "price": "2 500 000 đ"},
    {"name": "Лицо", "desc": "10 сеансов — курс 500 000 đ", "price": "4 500 000 đ"}]}]}
CATALOG = {"sections": {"Цены": "Prices"},
           "names": {"КОМБО 1 (тело)": "COMBO 1 (body)", "Лицо": "Face"},
           "descs": {"{0} сеансов — курс {1} đ": "{0} sessions — course {1} đ"}}


class MaskNumbersTest(unittest.TestCase):
    def test_numbers_with_thousand_spaces(self):
        self.assertEqual(pt.mask_numbers("5 сеансов — курс 1 000 000 đ"),
                         ("{0} сеансов — курс {1} đ", ["5", "1 000 000"]))


class CatalogProblemsTest(unittest.TestCase):
    def problems(self, **changes):
        return pt.catalog_problems(PRICES, {**CATALOG, **changes})

    def test_full_catalog_passes(self):
        self.assertEqual(self.problems(), [])

    def test_missing_name_is_named(self):
        self.assertEqual(self.problems(names={"Лицо": "Face"}),
                         ["prices names «КОМБО 1 (тело)»: нет перевода (lpg-massazh)"])

    def test_unused_key_is_error(self):
        self.assertIn("prices names «Лоб»: лишний ключ — в прайсе такой строки нет",
                      self.problems(names={**CATALOG["names"], "Лоб": "Forehead"}))

    def test_digits_before_dong_are_error(self):
        self.assertIn("prices names «Лицо»: в переводе цифры перед đ — цены в переводе нет",
                      self.problems(names={**CATALOG["names"], "Лицо": "Face 2 500 000 đ"}))

    def test_digits_in_desc_translation_are_error(self):
        self.assertIn("prices descs «{0} сеансов — курс {1} đ»: в переводе описания цифры — "
                      "числа подставляются масками {0}, {1}…",
                      self.problems(descs={"{0} сеансов — курс {1} đ": "5 sessions — course {1} đ"}))

    def test_lost_mask_is_error(self):
        self.assertIn("prices descs «{0} сеансов — курс {1} đ»: маски перевода [0] "
                      "не совпадают с масками ключа [0, 1]",
                      self.problems(descs={"{0} сеансов — курс {1} đ": "{0} sessions"}))

    def test_override_for_unknown_service_is_error(self):
        self.assertIn("prices overrides «smas-lifting»: такой услуги в прайсе нет",
                      self.problems(overrides={"smas-lifting": {"names": {"Лицо": "Face"}}}))

    def test_unknown_top_key_is_error(self):
        self.assertIn("prices «extra»: неизвестный раздел словаря", self.problems(extra={}))


class TranslateSectionsTest(unittest.TestCase):
    def setUp(self):
        self.translation = pt.PriceTranslation(CATALOG)

    def test_numbers_come_from_russian_string(self):
        sections = self.translation.translate_sections("lpg-massazh", PRICES["lpg-massazh"])
        self.assertEqual([item["desc"] for item in sections[0]["items"]],
                         ["", "5 sessions — course 560 000 đ", "10 sessions — course 500 000 đ"])

    def test_prices_and_flags_are_untouched(self):
        source = [{**sec, "items": [{**item, "is_combo": True} for item in sec["items"]]}
                  for sec in PRICES["lpg-massazh"]]
        sections = self.translation.translate_sections("lpg-massazh", source)
        self.assertEqual([(item["price"], item["is_combo"]) for item in sections[0]["items"]],
                         [(item["price"], True) for item in PRICES["lpg-massazh"][0]["items"]])
        self.assertEqual(sections[0]["section"], "Prices")

    def test_override_wins(self):
        translation = pt.PriceTranslation({**CATALOG, "overrides": {
            "lpg-massazh": {"names": {"Лицо": "Face (LPG)"}}}})
        self.assertEqual(translation.text("lpg-massazh", "names", "Лицо"), "Face (LPG)")

    def test_identity_returns_source(self):
        identity = pt.PriceTranslation.identity()
        self.assertIs(identity.translate_sections("lpg-massazh", PRICES["lpg-massazh"]),
                      PRICES["lpg-massazh"])
        self.assertEqual(identity.text("lpg-massazh", "names", "Лицо"), "Лицо")
