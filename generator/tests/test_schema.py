import unittest

import json
import re

import build
import schema
from locales import load_locale, localized_site


class WebSiteLanguageTest(unittest.TestCase):
    @staticmethod
    def website_of(languages):
        site, _content, _prices = build.load()
        nodes = schema.business_nodes(site, languages)
        return next(node for node in nodes if node["@type"] == "WebSite")

    def test_website_names_every_language_of_the_site(self):
        self.assertEqual(self.website_of(["ru", "en"])["inLanguage"], ["ru", "en"])

    def test_website_language_is_list_even_for_one_language(self):
        self.assertEqual(self.website_of(["ru"])["inLanguage"], ["ru"])

    def test_render_passes_languages_to_graph(self):
        site, _content, _prices = build.load()
        self.assertIn('"inLanguage": [\n        "ru",\n        "en"\n      ]',
                      schema.render(site, ["ru", "en"]))


class BeautySalonNodeTest(unittest.TestCase):
    @staticmethod
    def nodes_of(language):
        site, _content, _prices = build.load()
        nodes = schema.business_nodes(localized_site(site, load_locale(language)), ["ru", "en"])
        return {node["@type"]: node for node in nodes}

    def test_address_has_city_but_no_duplicate_region(self):
        for language in ("ru", "en"):
            with self.subTest(language=language):
                address = self.nodes_of(language)["BeautySalon"]["address"]
                self.assertEqual(address["addressLocality"], "Da Nang")
                self.assertNotIn("addressRegion", address)

    def test_salon_has_the_logo_of_its_organization(self):
        for language in ("ru", "en"):
            with self.subTest(language=language):
                nodes = self.nodes_of(language)
                self.assertTrue(nodes["BeautySalon"]["logo"].endswith("/logo-neva-beauty.png"))
                self.assertEqual(nodes["BeautySalon"]["logo"], nodes["Organization"]["logo"])

    def test_description_is_in_the_language_of_the_page(self):
        cyrillic = re.compile("[А-Яа-яЁё]")
        self.assertRegex(self.nodes_of("ru")["BeautySalon"]["description"], cyrillic)
        english = self.nodes_of("en")["BeautySalon"]["description"]
        self.assertTrue(english.startswith("Neva Beauty is a beauty center in Da Nang"))
        self.assertNotRegex(english, cyrillic)

    def test_rendered_graph_is_valid_json_with_the_description(self):
        site, _content, _prices = build.load()
        rendered = schema.render(site, ["ru", "en"])
        graph = json.loads(re.search(r"\{.*\}", rendered, re.S).group(0))["@graph"]
        salon = next(node for node in graph if node["@type"] == "BeautySalon")
        self.assertIn("description", salon)
