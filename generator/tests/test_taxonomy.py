import unittest

import taxonomy
from locales import parse_locale
from routes import Routes

RU = parse_locale({"code": "ru", "html_lang": "ru", "og_locale": "ru_RU", "url_prefix": "",
                   "ui": {"nav": {"home": "Главная"}}}, "ru.yml")


def make_content():
    return {
        "categories": [
            {"slug": "korrekciya-figury", "title": "Коррекция фигуры", "nav_label": "Фигура",
             "services": ["lpg-massazh", "endosfera-terapiya"]},
            {"slug": "uhod", "title": "Уход за лицом", "services": ["uhod"]},
        ],
        "services": {
            "lpg-massazh": {"title": "LPG-массаж", "related": ["endosfera-terapiya"]},
            "endosfera-terapiya": {"title": "Эндосфера-терапия"},
            "uhod": {"title": "Эстетический уход за лицом"},
        },
    }


def enriched():
    content = make_content()
    routes = Routes([RU], taxonomy.page_ids(content), "https://vn.neva.beauty", "ru")
    taxonomy.enrich_categories(content, routes, RU)
    return content, routes


class PageIdsTest(unittest.TestCase):
    def test_services_and_multi_service_categories(self):
        self.assertEqual(sorted(taxonomy.page_ids(make_content())),
                         ["endosfera-terapiya", "korrekciya-figury", "lpg-massazh", "uhod"])


class HasOwnPageTest(unittest.TestCase):
    def test_only_category_with_several_services_has_page(self):
        figure, care = make_content()["categories"]
        self.assertTrue(taxonomy.has_own_page(figure))
        self.assertFalse(taxonomy.has_own_page(care))


class EnrichCategoriesTest(unittest.TestCase):
    def test_multi_service_category_is_a_page(self):
        cat = enriched()[0]["categories"][0]
        self.assertTrue(cat["is_page"])
        self.assertEqual(cat["page_id"], "korrekciya-figury")
        self.assertEqual(cat["url"], "/korrekciya-figury/")
        self.assertEqual(cat["href"], "/korrekciya-figury/")

    def test_single_service_category_points_to_service(self):
        cat = enriched()[0]["categories"][1]
        self.assertFalse(cat["is_page"])
        self.assertEqual(cat["page_id"], "uhod")
        self.assertEqual(cat["url"], "/uhod/")

    def test_service_gets_category_title(self):
        services = enriched()[0]["services"]
        self.assertEqual(services["lpg-massazh"]["category"], "Коррекция фигуры")
        self.assertEqual(services["uhod"]["category"], "Уход за лицом")

    def test_category_of(self):
        content = enriched()[0]
        self.assertEqual(taxonomy.category_of(content, "endosfera-terapiya")["slug"],
                         "korrekciya-figury")

    def test_category_of_single_service_category(self):
        content = enriched()[0]
        self.assertEqual(taxonomy.category_of(content, "uhod")["slug"], "uhod")


class FillRelatedTest(unittest.TestCase):
    def test_curated_first_then_siblings_then_others(self):
        content = make_content()
        taxonomy.fill_related(content)
        self.assertEqual(content["services"]["lpg-massazh"]["related"],
                         ["endosfera-terapiya", "uhod"])
        self.assertEqual(content["services"]["uhod"]["related"],
                         ["lpg-massazh", "endosfera-terapiya"])

    def test_self_link_and_unknown_service_are_dropped(self):
        content = make_content()
        content["services"]["lpg-massazh"]["related"] = [
            "lpg-massazh", "net-takoy-uslugi", "uhod"]
        taxonomy.fill_related(content)
        self.assertEqual(content["services"]["lpg-massazh"]["related"],
                         ["uhod", "endosfera-terapiya"])

    def test_repeated_curated_item_is_counted_once(self):
        content = make_content()
        content["services"]["lpg-massazh"]["related"] = ["uhod", "uhod"]
        taxonomy.fill_related(content)
        self.assertEqual(content["services"]["lpg-massazh"]["related"],
                         ["uhod", "endosfera-terapiya"])


class BuildNavTest(unittest.TestCase):
    def setUp(self):
        content, routes = enriched()
        self.nav = taxonomy.build_nav(content, routes, RU)

    def test_home_comes_first(self):
        self.assertEqual(self.nav[0],
                         {"label": "Главная", "title": "Главная", "href": "/", "is_home": True})

    def test_category_with_children(self):
        item = self.nav[1]
        self.assertEqual(item["label"], "Фигура")
        self.assertEqual(item["title"], "Коррекция фигуры")
        self.assertEqual(item["href"], "/korrekciya-figury/")
        self.assertFalse(item["is_home"])
        self.assertEqual(item["children"], [
            {"label": "LPG-массаж", "href": "/lpg-massazh/"},
            {"label": "Эндосфера-терапия", "href": "/endosfera-terapiya/"},
        ])

    def test_label_falls_back_to_title_without_nav_label(self):
        self.assertNotIn("nav_label", make_content()["categories"][1])
        self.assertEqual(self.nav[2]["label"], self.nav[2]["title"])

    def test_single_service_category_has_no_children(self):
        item = self.nav[2]
        self.assertEqual(item["label"], "Уход за лицом")
        self.assertEqual(item["href"], "/uhod/")
        self.assertNotIn("children", item)


if __name__ == "__main__":
    unittest.main()
