import unittest

import copy
import tempfile
from pathlib import Path

from locales import load_locale, load_privacy, localized_site, merge_overrides, parse_locale

RAW = {
    "code": "ru", "html_lang": "ru", "og_locale": "ru_RU", "url_prefix": "",
    "ui": {"cta": {"book": "Записаться"},
           "faq": {"title": "Частые вопросы — {title}"},
           "price": {"from": "от {price}"}},
}


class ParseLocaleTest(unittest.TestCase):
    def test_flattens_nested_ui_into_dotted_keys(self):
        self.assertEqual(parse_locale(RAW, "ru.yml").ui["cta.book"], "Записаться")

    def test_missing_required_key_is_error(self):
        broken = {key: value for key, value in RAW.items() if key != "og_locale"}
        with self.assertRaisesRegex(ValueError, "og_locale"):
            parse_locale(broken, "ru.yml")

    def test_url_prefix_loses_trailing_slash(self):
        locale = parse_locale({**RAW, "url_prefix": "/en/"}, "en.yml")
        self.assertEqual(locale.url_prefix, "/en")

    def test_url_prefix_must_be_a_string(self):
        for bad in (None, 5):
            with self.assertRaisesRegex(ValueError, "en.yml.*url_prefix"):
                parse_locale({**RAW, "url_prefix": bad}, "en.yml")


class TranslateTest(unittest.TestCase):
    def setUp(self):
        self.locale = parse_locale(RAW, "ru.yml")

    def test_returns_string_by_key(self):
        self.assertEqual(self.locale.t("cta.book"), "Записаться")

    def test_substitutes_params(self):
        self.assertEqual(self.locale.t("faq.title", title="LPG-массаж"),
                         "Частые вопросы — LPG-массаж")

    def test_unknown_key_is_error(self):
        with self.assertRaisesRegex(KeyError, "cta.missing"):
            self.locale.t("cta.missing")

    def test_template_without_params_is_returned_as_is(self):
        self.assertEqual(self.locale.t("price.from"), "от {price}")


class FormatFromTest(unittest.TestCase):
    def test_wraps_price_in_the_locale_phrase(self):
        self.assertEqual(parse_locale(RAW, "ru.yml").format_from("1 500 000 ₫"),
                         "от 1 500 000 ₫")


class SlugTest(unittest.TestCase):
    def test_slug_defaults_to_page_id(self):
        self.assertEqual(parse_locale(RAW, "ru.yml").slug("lpg-massazh"), "lpg-massazh")

    def test_slug_can_be_overridden(self):
        locale = parse_locale({**RAW, "slugs": {"lpg-massazh": "lpg-massage"}}, "en.yml")
        self.assertEqual(locale.slug("lpg-massazh"), "lpg-massage")


class LocalizedSiteTest(unittest.TestCase):
    def test_locale_overrides_site_values_without_touching_original(self):
        locale = parse_locale({**RAW, "site": {"hours": "By appointment"}}, "en.yml")
        site = {"brand": "Neva Beauty", "hours": "Приём по записи"}
        self.assertEqual(localized_site(site, locale),
                         {"brand": "Neva Beauty", "hours": "By appointment"})
        self.assertEqual(site["hours"], "Приём по записи")


class MergeOverridesTest(unittest.TestCase):
    def test_nested_dict_is_merged_by_key(self):
        base = {"business": {"currency": "VND", "city": "Нячанг"}, "brand": "Neva"}
        merged = merge_overrides(base, {"business": {"city": "Nha Trang"}})
        self.assertEqual(merged, {"business": {"currency": "VND", "city": "Nha Trang"},
                                  "brand": "Neva"})

    def test_list_of_dicts_is_merged_item_by_item(self):
        base = {"locations": [{"name": "Один", "url": "/a"}, {"name": "Два", "url": "/b"}]}
        merged = merge_overrides(base, {"locations": [{"name": "One"}, {"name": "Two"}]})
        self.assertEqual(merged["locations"], [{"name": "One", "url": "/a"},
                                               {"name": "Two", "url": "/b"}])

    def test_list_of_dicts_with_other_length_is_error(self):
        base = {"locations": [{"name": "Один"}, {"name": "Два"}]}
        with self.assertRaisesRegex(ValueError, "locations"):
            merge_overrides(base, {"locations": [{"name": "One"}]})

    def test_plain_list_is_replaced_whole(self):
        merged = merge_overrides({"tags": ["а", "б"]}, {"tags": ["x"]})
        self.assertEqual(merged["tags"], ["x"])

    def test_unknown_key_is_error_with_path(self):
        base = {"business": {"city": "Нячанг"}}
        with self.assertRaisesRegex(ValueError, "business.sity"):
            merge_overrides(base, {"business": {"sity": "Nha Trang"}})

    def test_unknown_key_inside_list_item_names_the_index(self):
        base = {"locations": [{"name": "Один"}]}
        with self.assertRaisesRegex(ValueError, r"locations\[0\].nmae"):
            merge_overrides(base, {"locations": [{"nmae": "One"}]})

    def test_other_type_over_dict_or_list_is_error_with_path(self):
        base = {"business": {"city": "Нячанг"}, "tags": ["а"]}
        for key, bad in (("business", None), ("business", "строка"), ("business", ["x"]),
                         ("tags", None), ("tags", {"a": 1})):
            with self.assertRaisesRegex(ValueError, f"site.{key}: "):
                merge_overrides(base, {key: bad}, "site")

    def test_scalar_may_be_replaced_by_another_scalar(self):
        self.assertEqual(merge_overrides({"hours": "Приём"}, {"hours": "Open"}), {"hours": "Open"})

    def test_base_is_not_mutated(self):
        base = {"business": {"city": "Нячанг"}, "locations": [{"name": "Один"}]}
        snapshot = copy.deepcopy(base)
        merge_overrides(base, {"business": {"city": "Nha Trang"},
                               "locations": [{"name": "One"}]})
        self.assertEqual(base, snapshot)


class LocalizedSiteErrorsTest(unittest.TestCase):
    def test_errors_name_the_locale_file(self):
        site = {"business": {"city": "Нячанг"}}
        for patch in ({"business": None}, {"business": {"sity": "x"}}):
            locale = parse_locale({**RAW, "code": "en", "site": patch}, "en.yml")
            with self.assertRaisesRegex(ValueError, r"locales/en\.yml site\.business"):
                localized_site(site, locale)


class RussianLocaleFileTest(unittest.TestCase):
    def test_real_file_loads(self):
        locale = load_locale("ru")
        self.assertEqual(locale.t("cta.book"), "Записаться")
        self.assertEqual(locale.url_prefix, "")


class LoadPrivacyTest(unittest.TestCase):
    def test_real_russian_text_is_loaded(self):
        self.assertIn("<h1>", load_privacy("ru"))

    def test_missing_file_is_error_with_its_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, r"xx[/\\]privacy\.html"):
                load_privacy("xx", Path(directory))


if __name__ == "__main__":
    unittest.main()
