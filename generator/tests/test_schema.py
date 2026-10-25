import json
import re
import unittest

import build
import schema

IMAGE_KEYS = ("image", "logo")
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def image_urls_of(node):
    """Все адреса картинок (image, logo) в дереве JSON-LD, на любой глубине."""
    if isinstance(node, dict):
        own = [node[key] for key in IMAGE_KEYS if isinstance(node.get(key), str)]
        return own + [url for value in node.values() for url in image_urls_of(value)]
    if isinstance(node, list):
        return [url for item in node for url in image_urls_of(item)]
    return []


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


class StructuredDataImagesTest(unittest.TestCase):
    """Картинки разметки — обещание поисковику: файл должен лежать в сборке."""

    def test_every_image_of_every_page_exists_in_build(self):
        site, _content, _prices = build.load()
        base = site["base_url"] + "/"
        checked = 0
        for page in build.OUT.rglob("*.html"):
            for block in JSON_LD_RE.findall(page.read_text(encoding="utf-8")):
                for url in image_urls_of(json.loads(block)):
                    checked += 1
                    self.assertTrue((build.OUT / url.removeprefix(base)).is_file(),
                                    f"{page.relative_to(build.OUT)}: нет файла {url}")
        self.assertGreater(checked, 0)
