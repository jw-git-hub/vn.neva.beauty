import unittest

from locales import load_locale, localized_site, parse_locale

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


class RussianLocaleFileTest(unittest.TestCase):
    def test_real_file_loads(self):
        locale = load_locale("ru")
        self.assertEqual(locale.t("cta.book"), "Записаться")
        self.assertEqual(locale.url_prefix, "")


if __name__ == "__main__":
    unittest.main()
