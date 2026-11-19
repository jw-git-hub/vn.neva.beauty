"""Страница записи /zapis/ и /en/booking/: адреса, кнопки связи, цены, ссылки на Google
Карты, разметка, подвал и llms.txt. Страницы собираются в памяти из текущих исходников."""
import json
import re
import unittest
import urllib.parse
from unittest import mock

from bs4 import BeautifulSoup

import build
import check_contacts
import contacts
import pricing
import sitewide
import taxonomy
from locales import load_locale
from routes import BOOKING, Routes
from tests.test_build import build_real_pages

PAGE_FILES = {"ru": "zapis/index.html", "en": "en/booking/index.html"}
PAGE_URLS = {"ru": "https://vn.neva.beauty/zapis/", "en": "https://vn.neva.beauty/en/booking/"}
BOOKING_PLACE = "booking-page"
CHANNELS = ("whatsapp", "telegram", "instagram")
FAQ_COUNT = 4
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
# Слова, которые глоссарий запрещает про Neva Beauty и его специалистов (glossary.yml).
FORBIDDEN_ENGLISH = ("beauty salon", "cosmetologist", "procedure", "clinic", "doctor",
                     "physician", "dermatolog")


def soup_of(code):
    return BeautifulSoup(build_real_pages(code)[PAGE_FILES[code]], "html.parser")


def text_of(element):
    """Видимый текст элемента, неразрывные пробелы типографа — обычными."""
    return element.get_text(" ").replace(" ", " ")


def main_text(code):
    return text_of(soup_of(code).find("main"))


def consultation_text(code):
    """Абзац блока «Консультация»: первый заголовок блока цен."""
    head = soup_of(code).select_one(".pricelist-section .section-head")
    return text_of(head.find_all("p")[-1])


def graph_of(html):
    return json.loads(LD_RE.search(html).group(1))["@graph"]


def node_of(code, node_type):
    return next(node for node in graph_of(build_real_pages(code)[PAGE_FILES[code]])
                if node["@type"] == node_type)


def message_of(link):
    query = urllib.parse.urlsplit(link["href"]).query
    return urllib.parse.parse_qs(query).get(contacts.PREFILL_PARAM, [None])[0]


class BookingRoutesTest(unittest.TestCase):
    def test_addresses_of_both_languages(self):
        _, content, _ = build.load()
        russian, english = load_locale("ru"), load_locale("en")
        routes = Routes([russian, english], taxonomy.page_ids(content),
                        "https://vn.neva.beauty", "en")
        self.assertEqual(routes.path(russian, BOOKING), "/zapis/")
        self.assertEqual(routes.path(english, BOOKING), "/en/booking/")


class BookingHeadingTest(unittest.TestCase):
    def test_single_h1_is_title_from_content(self):
        titles = {"ru": "Запись в Neva Beauty в Дананге",
                  "en": "Book an Appointment at Neva Beauty in Da Nang"}
        for code, title in titles.items():
            with self.subTest(code=code):
                headings = soup_of(code).find_all("h1")
                self.assertEqual([text_of(h) for h in headings], [title])


class BookingContactButtonsTest(unittest.TestCase):
    def test_three_channels_with_own_place(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                links = soup_of(code).select(f'[data-place="{BOOKING_PLACE}"]')
                self.assertEqual([link["data-contact"] for link in links], list(CHANNELS))

    def test_whatsapp_carries_generic_text_of_the_language(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                link = soup_of(code).select_one(
                    f'[data-place="{BOOKING_PLACE}"][data-contact="whatsapp"]')
                self.assertEqual(message_of(link), load_locale(code).t("contact.text_generic"))

    def test_place_is_known_to_contacts_module(self):
        self.assertIn(BOOKING_PLACE, contacts.PLACES)

    def test_check_contacts_expects_generic_text_and_visits_page(self):
        site, content, _ = build.load()
        self.assertIn(BOOKING, check_contacts.GENERIC_PAGES)
        visited = {(locale.code, page_id) for locale, page_id, _ in
                   check_contacts.locale_pages(site, content, build.load_locales(site))}
        self.assertTrue({("ru", BOOKING), ("en", BOOKING)} <= visited)


class BookingConsultationTest(unittest.TestCase):
    """Цены консультаций — из site.yml; дерматолог назван только в русском тексте."""

    @classmethod
    def setUpClass(cls):
        cls.consultation = build.load()[0]["consultation"]

    def test_russian_page_names_both_prices(self):
        self.assertIn(f"Консультация косметолога стоит {self.consultation['price']}, "
                      f"дерматолога — {self.consultation['dermatology_price']}.",
                      consultation_text("ru"))

    def test_english_page_names_aesthetician_price_only(self):
        text = consultation_text("en")
        self.assertIn(f"costs {self.consultation['price']}.", text)
        self.assertNotIn(self.consultation["dermatology_price"], text)

    def test_no_placeholder_is_left(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                self.assertNotRegex(main_text(code), r"\{\w+\}")


class BookingCardsTest(unittest.TestCase):
    """Карточки «Услуги и цены»: каждая услуга в порядке меню, ссылка на её страницу
    и цена одной строкой из prices.json — та же, что в сравнительной таблице."""

    def expected_cards(self, code):
        site, content, prices = build.load()
        locale = load_locale(code)
        routes = Routes(build.load_locales(site), taxonomy.page_ids(content),
                        site["base_url"], "en")
        return [(routes.href(locale, service_id),
                 pricing.price_hint(prices[service_id], locale.format_from))
                for cat in content["categories"] for service_id in cat["services"]]

    def test_every_service_links_to_its_page_with_price(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                cards = [(card["href"], card.select_one(".popular-card__price").get_text()
                          .replace(" ", " "))
                         for card in soup_of(code).select(".popular-card")]
                self.assertEqual(cards, self.expected_cards(code))


class GoogleMapsLinksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.business = build.load()[0]["business"]

    def test_booking_page_links_to_map_and_review_in_new_tab(self):
        for code in PAGE_FILES:
            main = soup_of(code).find("main")
            for key in ("maps_url", "review_url"):
                with self.subTest(code=code, link=key):
                    link = main.find("a", href=self.business[key])
                    self.assertIsNotNone(link)
                    self.assertEqual((link["target"], link["rel"]), ("_blank", ["noopener"]))

    def test_every_page_footer_links_to_booking_and_map(self):
        booking_paths = {"ru": "/zapis/", "en": "/en/booking/"}
        for code, path in booking_paths.items():
            for page, html in build_real_pages(code).items():
                footer = BeautifulSoup(html, "html.parser").find("footer")
                with self.subTest(page=page):
                    self.assertIsNotNone(footer.find("a", href=path))
                    self.assertIsNotNone(footer.find("a", href=self.business["maps_url"]))

    def test_every_page_salon_has_map(self):
        for code in PAGE_FILES:
            for page, html in build_real_pages(code).items():
                salon = next(node for node in graph_of(html) if node["@type"] == "BeautySalon")
                with self.subTest(page=page):
                    self.assertEqual(salon["hasMap"], self.business["maps_url"])


class BookingStructuredDataTest(unittest.TestCase):
    def test_page_types(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                types = {node["@type"] for node in graph_of(build_real_pages(code)[PAGE_FILES[code]])}
                self.assertTrue({"BreadcrumbList", "ContactPage", "FAQPage"} <= types)

    def test_contact_page_points_to_page_site_and_salon(self):
        for code, url in PAGE_URLS.items():
            with self.subTest(code=code):
                node = node_of(code, "ContactPage")
                self.assertEqual((node["@id"], node["url"]), (url + "#webpage", url))
                self.assertEqual(node["isPartOf"]["@id"], "https://vn.neva.beauty/#website")
                self.assertEqual(node["about"]["@id"], "https://vn.neva.beauty/#business")

    def test_breadcrumbs_end_on_booking_page(self):
        for code, url in PAGE_URLS.items():
            with self.subTest(code=code):
                items = node_of(code, "BreadcrumbList")["itemListElement"]
                self.assertEqual([item["item"] for item in items][-1], url)
                self.assertEqual(len(items), 2)

    def test_faq_markup_matches_visible_questions(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                questions = [q["name"] for q in node_of(code, "FAQPage")["mainEntity"]]
                visible = [text_of(q) for q in soup_of(code).select(".faq__q")]
                self.assertEqual(len(questions), FAQ_COUNT)
                self.assertEqual(questions, visible)


class BookingOwnerRulesTest(unittest.TestCase):
    """Правила владельца: на сайте нет фото салона, email и часов работы; английский текст
    обходится без слов, которые глоссарий запрещает."""

    def test_no_photos_or_email_in_page(self):
        for code in PAGE_FILES:
            with self.subTest(code=code):
                main = soup_of(code).find("main")
                self.assertIsNone(main.find("img"))
                self.assertNotIn("mailto:", str(main))

    def test_english_text_avoids_forbidden_words(self):
        text = main_text("en").lower()
        for word in FORBIDDEN_ENGLISH:
            with self.subTest(word=word):
                self.assertNotIn(word, text)


class BookingSitewideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site, content, cls.prices = build.load()
        cls.locales = build.load_locales(cls.site)
        cls.routes = Routes(cls.locales, taxonomy.page_ids(content), cls.site["base_url"],
                            build.load_x_default_locale(cls.site))
        with mock.patch("build.write", return_value=False):
            cls.contents = {locale.code: build.build_locale(
                cls.site, content, cls.prices, locale, cls.routes, "", cls.locales[0])[1]
                for locale in cls.locales}

    def test_sitemap_lists_booking_page_of_each_language(self):
        for locale in self.locales:
            with self.subTest(code=locale.code):
                paths = sitewide.sitemap_paths(self.contents[locale.code], self.routes, locale)
                self.assertIn(self.routes.path(locale, BOOKING), paths)

    def test_llms_lists_booking_page_and_map_in_both_languages(self):
        text = sitewide.build_llms_file(self.site, self.contents, self.prices,
                                        self.locales, self.routes)
        maps_url = self.site["business"]["maps_url"]
        for line in (f"- Запись: {PAGE_URLS['ru']}", f"- Google Карты: {maps_url}",
                     f"- Booking: {PAGE_URLS['en']}", f"- Google Maps: {maps_url}"):
            with self.subTest(line=line):
                self.assertIn(line + "\n", text)


if __name__ == "__main__":
    unittest.main()
