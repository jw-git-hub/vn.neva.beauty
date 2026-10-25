import unittest

import build
import schema


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
