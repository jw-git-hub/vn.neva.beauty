"""Поле h1 услуги: заголовок страницы с городом, а название в меню, крошках, карточках
и тексте обращения — прежнее короткое title. Нет поля — заголовок равен title."""
import unittest
import urllib.parse

from bs4 import BeautifulSoup

import build
import check_headings
import contacts
import overlay
import pair_terms
import translation_pairs
from locales import load_locale
from tests.test_build import build_real_pages
from translation import load_overlay

SERVICE_WITH_H1 = "lazernaya-epilyaciya"
SERVICE_WITHOUT_H1 = "lpg-massazh"
CATEGORY_OF_SERVICE = "lazernye-procedury"
PAGE_FILES = {"ru": {SERVICE_WITH_H1: "lazernaya-epilyaciya/index.html",
                     SERVICE_WITHOUT_H1: "lpg-massazh/index.html",
                     CATEGORY_OF_SERVICE: "lazernye-procedury/index.html"},
              "en": {SERVICE_WITH_H1: "en/laser-hair-removal/index.html",
                     SERVICE_WITHOUT_H1: "en/lpg-massage/index.html",
                     CATEGORY_OF_SERVICE: "en/laser-treatments/index.html"}}


def services_of(code):
    """Тексты услуг языка: русский мастер или английская накладка."""
    if code == "ru":
        return build.load()[1]["services"]
    return load_overlay(code)["services"]


class ServiceH1InBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {code: build_real_pages(code) for code in PAGE_FILES}

    def soup(self, code, page_id):
        return BeautifulSoup(self.pages[code][PAGE_FILES[code][page_id]], "html.parser")

    def test_h1_comes_from_field(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                h1 = self.soup(code, SERVICE_WITH_H1).find("h1").get_text()
                self.assertEqual(check_headings.squeeze(h1),
                                 services_of(code)[SERVICE_WITH_H1]["h1"])

    def test_service_without_field_keeps_title_as_h1(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                h1 = self.soup(code, SERVICE_WITHOUT_H1).find("h1").get_text()
                self.assertEqual(check_headings.squeeze(h1),
                                 services_of(code)[SERVICE_WITHOUT_H1]["title"])

    def test_breadcrumbs_keep_title(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                self.assertEqual(check_headings.page_title(self.soup(code, SERVICE_WITH_H1)),
                                 services_of(code)[SERVICE_WITH_H1]["title"])

    def test_menu_and_category_cards_keep_title(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                svc = services_of(code)[SERVICE_WITH_H1]
                soup = self.soup(code, CATEGORY_OF_SERVICE)
                menu = [check_headings.squeeze(link.get_text())
                        for link in soup.select("nav.nav a.nav__sub")]
                cards = [check_headings.squeeze(heading.get_text())
                         for heading in soup.select(".related-card h2")]
                self.assertIn(svc["title"], menu)
                self.assertIn(svc["title"], cards)
                self.assertNotIn(svc["h1"], menu + cards)

    def test_contact_text_names_service_by_title(self):
        """Администратор видит в чате короткое название услуги, а не заголовок с городом."""
        for code in PAGE_FILES:
            with self.subTest(code=code):
                link = self.soup(code, SERVICE_WITH_H1).find(
                    "a", attrs={"data-contact": "whatsapp", "data-place": "hero"})
                text = urllib.parse.parse_qs(urllib.parse.urlsplit(link["href"]).query)["text"][0]
                expected = contacts.contact_message(load_locale(code),
                                                    services_of(code)[SERVICE_WITH_H1]["title"])
                self.assertEqual(text, expected)


class H1TranslationTest(unittest.TestCase):
    MASTER = {"services": {"x": {"title": "Лазерная эпиляция",
                                 "h1": "Лазерная эпиляция в Дананге"}}}

    def test_missing_translation_of_h1_is_named(self):
        _, problems = overlay.merge_translation(self.MASTER,
                                                {"services": {"x": {"title": "Laser"}}})
        self.assertEqual(problems, ["services.x.h1: нет перевода"])

    def test_h1_without_russian_field_is_extra_key(self):
        master = {"services": {"x": {"title": "LPG-массаж"}}}
        _, problems = overlay.merge_translation(
            master, {"services": {"x": {"title": "LPG Massage", "h1": "LPG Massage in Da Nang"}}})
        self.assertEqual(problems, ["services.x.h1: лишний ключ — в мастере его нет"])

    def test_h1_is_locked_with_other_texts(self):
        self.assertEqual(overlay.source_strings(self.MASTER)["services.x.h1"],
                         "Лазерная эпиляция в Дананге")

    def test_h1_without_city_fails_required_term(self):
        """Глоссарий требует «Da Nang» там, где в русском стоит Дананг, — и в заголовке."""
        merged = {"services": {"x": {"title": "Laser Hair Removal", "h1": "Laser Hair Removal"}}}
        pairs = [pair for pair in translation_pairs.content_pairs(self.MASTER, merged, [])
                 if pair.path == "services.x.h1"]
        problems = translation_pairs.pair_problems(pairs, pair_terms.load_terms("en"), [])
        self.assertEqual(len(problems), 1)
        self.assertIn("Da Nang", str(problems[0]))


def crumbs_and_h1(name, h1, hero_class=check_headings.SERVICE_HERO_CLASS):
    return BeautifulSoup(f'<nav class="breadcrumbs"><span aria-current="page">{name}</span></nav>'
                         f'<section class="{hero_class}"><h1>{h1}</h1></section>', "html.parser")


class H1NameRuleTest(unittest.TestCase):
    def test_h1_with_city_after_title_passes(self):
        soup = crumbs_and_h1("Лазерная эпиляция", "Лазерная эпиляция в\xa0Дананге")
        self.assertIsNone(check_headings.h1_name_error("page.html", soup))

    def test_h1_equal_to_title_passes(self):
        self.assertIsNone(check_headings.h1_name_error(
            "page.html", crumbs_and_h1("LPG-массаж", "LPG-массаж")))

    def test_other_h1_is_error_with_page_name(self):
        error = check_headings.h1_name_error("epil/index.html",
                                             crumbs_and_h1("Лазерная эпиляция", "Эпиляция в Дананге"))
        self.assertIn("epil/index.html", error)
        self.assertIn("Лазерная эпиляция", error)

    def test_title_must_be_whole_words(self):
        self.assertIsNotNone(check_headings.h1_name_error(
            "page.html", crumbs_and_h1("LPG-массаж", "LPG-массажный курс")))

    def test_page_other_than_service_is_skipped(self):
        """Страница записи: крошка «Booking», h1 «Book an Appointment…» — своё, не поле услуги."""
        soup = crumbs_and_h1("Booking", "Book an Appointment at Neva Beauty in Da Nang",
                             hero_class="section--lead")
        self.assertIsNone(check_headings.h1_name_error("en/booking/index.html", soup))

    def test_page_without_breadcrumbs_is_skipped(self):
        soup = BeautifulSoup("<h1>Центр красоты в Дананге</h1>", "html.parser")
        self.assertIsNone(check_headings.h1_name_error("index.html", soup))


if __name__ == "__main__":
    unittest.main()
