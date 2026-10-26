import contextlib
import copy
import json
import re
import unittest
import urllib.parse
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from markupsafe import Markup

import build
import contacts
import pages
import pricing
import taxonomy
from locales import load_locale
from routes import Routes
from tests.pseudo_translation import (pseudo_content, pseudo_pair_patches, pseudo_prices,
                                      pseudo_site)


class BuildLocaleIsolationTest(unittest.TestCase):
    def test_shared_content_is_not_mutated(self):
        """Сборка языка подставляет цены и ссылки в тексты. Следующий язык должен
        получить исходный контент, а не уже раскрытые плейсхолдеры предыдущего."""
        site, content, prices = build.load()
        snapshot = copy.deepcopy(content)
        site_snapshot, prices_snapshot = copy.deepcopy(site), copy.deepcopy(prices)
        locale = load_locale("ru")
        routes = Routes([locale], taxonomy.page_ids(content), site["base_url"], "ru")
        with mock.patch("build.write", return_value=False):
            build.build_locale(site, content, prices, locale, routes, "", locale)
        self.assertEqual(content, snapshot)
        self.assertEqual(site, site_snapshot)
        self.assertEqual(prices, prices_snapshot)


def build_pages_of_test_english(x_default_locale="en", ui_overrides=None):
    """Собирает страницы тестового английского (префикс /en, псевдоперевод «EN …»)
    рядом с русским, не пиша файлов. Возвращает {путь страницы: html}."""
    site, content, prices = build.load()
    russian = load_locale("ru")
    english = replace(russian, code="en", html_lang="en", og_locale="en_US", url_prefix="/en",
                      ui={**russian.ui, **(ui_overrides or {})},
                      site=pseudo_site(site))
    routes = Routes([russian, english], taxonomy.page_ids(content), site["base_url"],
                    x_default_locale)
    written = {}
    with mock.patch("build.write", side_effect=lambda path, html: written.update({path: html})), \
            mock.patch("build.load_privacy", return_value=Markup("<p>Privacy</p>")), \
            mock.patch("translation.load_overlay", return_value=pseudo_content(content)), \
            mock.patch("translation.load_price_catalog", return_value=pseudo_prices(prices)), \
            mock.patch("translation.privacy_exists", return_value=True), \
            contextlib.ExitStack() as stack:
        for patch in pseudo_pair_patches():
            stack.enter_context(patch)
        build.build_locale(site, content, prices, english, routes, "", russian)
    return {path.relative_to(build.OUT).as_posix(): html for path, html in written.items()}


class HreflangInBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build_pages_of_test_english()

    def test_indexable_page_lists_every_language_and_x_default(self):
        html = self.pages["en/index.html"]
        for hreflang, address in (("ru", "https://vn.neva.beauty/"),
                                  ("en", "https://vn.neva.beauty/en/"),
                                  ("x-default", "https://vn.neva.beauty/en/")):
            self.assertIn(f'<link rel="alternate" hreflang="{hreflang}" href="{address}">', html)


class LoadLocalesTest(unittest.TestCase):
    def test_loads_languages_listed_in_site(self):
        self.assertEqual([locale.code for locale in build.load_locales({"locales": ["ru"]})],
                         ["ru"])

    def test_missing_or_empty_list_is_error(self):
        for site in ({}, {"locales": []}, {"locales": None}):
            with self.assertRaisesRegex(ValueError, "locales"):
                build.load_locales(site)


class LoadXDefaultLocaleTest(unittest.TestCase):
    def test_returns_code_from_site(self):
        self.assertEqual(build.load_x_default_locale({"x_default_locale": "en"}), "en")

    def test_missing_key_is_error(self):
        for site in ({}, {"x_default_locale": None}, {"x_default_locale": ""}):
            with self.assertRaisesRegex(ValueError, "x_default_locale"):
                build.load_x_default_locale(site)


class ConsultationPriceTest(unittest.TestCase):
    def test_price_is_filled_from_site(self):
        tokens = pages.content_tokens(consultation=pages.consultation_price(
            {"consultation": {"price": "500 000 đ"}}))
        self.assertEqual(pages.fill_tokens("стоит {consultation_price}", tokens),
                         "стоит 500 000 đ")

    def test_malformed_empty_or_addon_price_is_error_about_site(self):
        for price in ("500000", " ", "+500 000 đ"):
            with self.subTest(price=price), \
                    self.assertRaisesRegex(ValueError, "site.yml: consultation.price"):
                pages.consultation_price({"consultation": {"price": price}})

    def test_dermatology_price_is_filled_from_site(self):
        site = {"consultation": {"price": "500 000 đ", "dermatology_price": "1 000 000 đ"}}
        tokens = pages.content_tokens(consultation=pages.consultation_price(site),
                                      dermatology=pages.dermatology_consultation_price(site))
        self.assertEqual(
            pages.fill_tokens("{consultation_price}, дерматолога — {dermatology_consultation_price}",
                              tokens), "500 000 đ, дерматолога — 1 000 000 đ")

    def test_malformed_dermatology_price_is_error_about_its_own_field(self):
        for price in ("1000000", " ", "+1 000 000 đ"):
            with self.subTest(price=price), \
                    self.assertRaisesRegex(ValueError, "site.yml: consultation.dermatology_price"):
                pages.dermatology_consultation_price(
                    {"consultation": {"price": "500 000 đ", "dermatology_price": price}})

    def test_unfilled_dermatology_placeholder_is_build_error(self):
        with self.assertRaisesRegex(ValueError, "Нераскрытый плейсхолдер"):
            pages.fill_tokens("дерматолога — {dermatology_consultation_price}", {})


def category_context(prices):
    """Контекст сборки ровно с тем, что нужно цене направления: прайс и «от …»."""
    return SimpleNamespace(prices=prices,
                           locale=SimpleNamespace(format_from=lambda price: f"от {price}"))


class CategoryPriceHintTest(unittest.TestCase):
    PRICES = {
        "face": [{"section": "Цены", "items": [
            {"name": "Лицо", "desc": "1 сеанс", "price": "600 000 đ"}]}],
        "body": [{"section": "Цены", "items": [
            {"name": "Тело", "desc": "1 сеанс", "price": "800 000 đ"},
            {"name": "Костюм", "desc": "", "price": "400 000 đ", "addon": True}]}],
    }

    def hint(self, **cat):
        return pages._category_price_hint(category_context(self.PRICES),
                                          {"services": ["face", "body"], **cat})

    def test_minimum_is_taken_over_all_services(self):
        self.assertEqual(self.hint(), "от 600 000 đ")

    def test_price_names_narrow_the_minimum(self):
        self.assertEqual(self.hint(price_names=["Тело"]), "800 000 đ")

    def test_unknown_price_name_is_error(self):
        with self.assertRaisesRegex(ValueError, "нет позиций"):
            self.hint(price_names=["Тело", "Шея"])


if __name__ == "__main__":
    unittest.main()


WHATSAPP_HREF_RE = re.compile(r'href="(https://wa\.me/[^"]*)"')
TELEGRAM_HREF_RE = re.compile(r'href="(https://t\.me/[^"]*)"')


def contact_texts(html, href_re=WHATSAPP_HREF_RE):
    """Тексты обращения во всех ссылках канала на странице. По умолчанию — WhatsApp:
    у него текст есть всегда, а Telegram зависит от флага telegram_prefill."""
    return {urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("text", [""])[0]
            for url in href_re.findall(html)}


class ContactLinksInBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site, content, prices = build.load()
        locale = load_locale("ru")
        routes = Routes([locale], taxonomy.page_ids(content), site["base_url"], "ru")
        written = {}
        with mock.patch("build.write",
                        side_effect=lambda path, html: written.update({path: html})):
            build.build_locale(site, content, prices, locale, routes, "", locale)
        cls.pages = {path.relative_to(build.OUT).as_posix(): html
                     for path, html in written.items()}

    def test_service_page_links_carry_service_title(self):
        self.assertEqual(contact_texts(self.pages["lpg-massazh/index.html"]),
                         {"Здравствуйте! Хочу записаться на: LPG-массаж"})

    def test_telegram_links_follow_prefill_flag(self):
        prefilled = "telegram" in contacts.prefill_channels(build.load()[0]["contacts"])
        expected = "Здравствуйте! Хочу записаться на: LPG-массаж" if prefilled else ""
        self.assertEqual(contact_texts(self.pages["lpg-massazh/index.html"], TELEGRAM_HREF_RE),
                         {expected})

    def test_home_links_carry_generic_text(self):
        self.assertEqual(contact_texts(self.pages["index.html"]),
                         {"Здравствуйте! Хочу записаться"})

    def test_every_contact_link_is_tagged(self):
        html = self.pages["lpg-massazh/index.html"]
        links = re.findall(r'<a [^>]*href="https://(?:wa\.me|t\.me|instagram\.com)/[^>]*>', html)
        self.assertTrue(links)
        for link in links:
            self.assertIn("data-contact=", link)
            self.assertIn("data-place=", link)

    def test_faq_links_are_tagged_and_carry_text(self):
        html = self.pages["lpg-massazh/index.html"]
        self.assertIn('data-place="faq"', html)
        faq_links = re.findall(r'<a href="(https://wa\.me/[^"]*)" data-contact="whatsapp" '
                               r'data-place="faq"', html)
        self.assertTrue(faq_links)
        self.assertEqual(contact_texts(" ".join(f'href="{url}"' for url in faq_links)),
                         {"Здравствуйте! Хочу записаться на: LPG-массаж"})

    def test_russian_page_has_no_language_note(self):
        self.assertNotIn('hreflang="ru" ', self.pages["index.html"].split("<body>")[1])

    def test_metrika_reports_contact_with_page_id(self):
        html = self.pages["lpg-massazh/index.html"]
        self.assertIn('var PAGE = "lpg-massazh";', html)
        self.assertIn('"reachGoal", "contact"', html)
        self.assertIn('d.addEventListener("click", reportContact);', html)


class MessengerPlaceholderTest(unittest.TestCase):
    def test_messenger_placeholder_outside_href_is_error(self):
        """{whatsapp} вне href="…" дал бы голый адрес без текста и меток — мимо contacts.py."""
        with self.assertRaises(ValueError):
            pages.fill_tokens("пишите {whatsapp}", pages.content_tokens())


class TranslatedEnglishPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build_pages_of_test_english()

    def test_price_list_uses_translated_names(self):
        html = self.pages["en/lpg-massazh/index.html"]
        self.assertIn("EN LPG Массаж - Тело", html)

    def test_combo_survives_translation(self):
        """Комбо узнаётся по русскому «КОМБО» до перевода: в английском прайсе это карточка."""
        html = self.pages["en/lazernaya-epilyaciya/index.html"]
        self.assertIn('<div class="combo__name">EN КОМБО 1', html)

    def test_popular_card_shows_translated_name(self):
        # Дефис с пробелами работает как тире: перед ним неразрывный пробел (typography.py).
        self.assertIn('<span class="popular-card__name">EN LPG Массаж\u00a0- Тело</span>',
                      self.pages["en/index.html"])

    def test_page_text_is_translated(self):
        self.assertIn("<h1>EN LPG-массаж</h1>", self.pages["en/lpg-massazh/index.html"])

    def test_samui_link_says_site_is_russian(self):
        html = self.pages["en/index.html"]
        self.assertIn('href="https://th.neva.beauty" hreflang="ru"', html)
        self.assertIn("сайт на русском", html)  # псевдоперевод берёт строки интерфейса русского


class EnglishHeadingTemplateTest(unittest.TestCase):
    def test_repeated_h2_can_carry_service_title(self):
        """Спека, раздел 12: английские «Prices», «See also», «Why it works» собираются
        с названием услуги, иначе h2 повторяются на всех страницах услуг."""
        pages = build_pages_of_test_english(ui_overrides={
            "service.price_title": "Prices — {title}",
            "service.related_title": "See also — {title}",
            "service.benefits_title": "Why it works — {title}"})
        html = pages["en/lpg-massazh/index.html"]
        for heading in ("Prices", "See also"):
            # Тире не начинает строку: перед ним неразрывный пробел (typography.py).
            self.assertIn(f"<h2>{heading}\u00a0— EN LPG-массаж</h2>", html)
        self.assertNotIn("{title}", html)


def build_real_pages(code):
    """Собирает страницы настоящего языка сайта (ru или en) с обоими языками в таблице
    маршрутов, не пиша файлов. Возвращает {путь страницы: html}."""
    site, content, prices = build.load()
    locales = build.load_locales(site)
    routes = Routes(locales, taxonomy.page_ids(content), site["base_url"],
                    build.load_x_default_locale(site))
    locale = next(item for item in locales if item.code == code)
    written = {}
    with mock.patch("build.write", side_effect=lambda path, html: written.update({path: html})):
        build.build_locale(site, content, prices, locale, routes, "", locales[0])
    return {path.relative_to(build.OUT).as_posix(): html for path, html in written.items()}


class PageHeadInBuiltPagesTest(unittest.TestCase):
    NOINDEX_PATHS = {"ru": ("privacy/index.html", "404.html"),
                     "en": ("en/privacy/index.html", "en/404.html")}

    @classmethod
    def setUpClass(cls):
        cls.ru, cls.en = build_real_pages("ru"), build_real_pages("en")

    @staticmethod
    def head_of(html):
        return html.split("</head>")[0]

    def test_noindex_pages_have_no_hreflang(self):
        for code, pages_of_language in (("ru", self.ru), ("en", self.en)):
            for path in self.NOINDEX_PATHS[code]:
                with self.subTest(path=path):
                    self.assertNotIn('rel="alternate" hreflang', self.head_of(pages_of_language[path]))

    def test_og_locale_alternate_names_other_language(self):
        self.assertIn('<meta property="og:locale:alternate" content="en_US">', self.ru["index.html"])
        self.assertIn('<meta property="og:locale:alternate" content="ru_RU">', self.en["en/index.html"])

    def test_og_locale_alternate_does_not_repeat_own_language(self):
        self.assertNotIn('og:locale:alternate" content="ru_RU"', self.ru["index.html"])
        self.assertNotIn('og:locale:alternate" content="en_US"', self.en["en/index.html"])

    def test_english_page_has_own_manifest_and_card(self):
        head = self.head_of(self.en["en/index.html"])
        self.assertIn('<link rel="manifest" href="/en/site.webmanifest">', head)
        self.assertIn('<meta property="og:image" content="https://vn.neva.beauty/assets/img/og-default-en.jpg">', head)
        self.assertIn('<meta name="twitter:image" content="https://vn.neva.beauty/assets/img/og-default-en.jpg">', head)

    def test_russian_page_keeps_root_manifest_and_card(self):
        head = self.head_of(self.ru["index.html"])
        self.assertIn('<link rel="manifest" href="/site.webmanifest">', head)
        self.assertIn('<meta property="og:image" content="https://vn.neva.beauty/assets/img/og-default.jpg">', head)

    def test_english_head_has_no_cyrillic(self):
        for path, html in self.en.items():
            with self.subTest(path=path):
                self.assertIsNone(re.search("[А-Яа-яЁё]", self.head_of(html)))


class SectionCardImagesInBuiltPagesTest(unittest.TestCase):
    """На первом экране раздела видна первая карточка: она не ленится, остальные лениво."""
    CARD_IMG_RE = re.compile(r'<div class="related-card__media">(<img[^>]*>)</div>')
    SECTION_PATHS = ("lazernye-procedury/index.html", "en/laser-treatments/index.html")

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}

    def card_images(self, path):
        return self.CARD_IMG_RE.findall(self.pages[path])

    def test_first_card_is_eager(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                self.assertIn('loading="eager"', self.card_images(path)[0])

    def test_other_cards_stay_lazy(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                images = self.card_images(path)
                self.assertGreater(len(images), 1)
                for image in images[1:]:
                    self.assertIn('loading="lazy"', image)

    def test_card_images_have_no_high_priority(self):
        """fetchpriority="high" у карточки замедляет LCP телефона на медленном канале."""
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                for image in self.card_images(path):
                    self.assertNotIn("fetchpriority", image)


class TypographyInBuiltPagesTest(unittest.TestCase):
    """Неразрывные пробелы стоят только в видимом тексте: не в <head>, не в разметке, не в атрибутах."""
    NO_BREAK_SPACE = "\u00a0"
    TAG_RE = re.compile(r"<[^>]*>")
    SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S)

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}

    def test_visible_text_of_every_page_has_no_break_spaces(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                self.assertIn(self.NO_BREAK_SPACE, html.split("<body", 1)[1])

    def test_head_has_none(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                self.assertNotIn(self.NO_BREAK_SPACE, html.split("<body", 1)[0])

    def test_scripts_and_json_ld_have_none(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                for script in self.SCRIPT_RE.findall(html):
                    self.assertNotIn(self.NO_BREAK_SPACE, script)

    def test_tags_and_attributes_have_none(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                for tag in self.TAG_RE.findall(self.SCRIPT_RE.sub("", html)):
                    self.assertNotIn(self.NO_BREAK_SPACE, tag)

    def test_each_language_gets_its_own_rules(self):
        self.assertIn(f"в{self.NO_BREAK_SPACE}самом сердце", self.pages["index.html"])
        self.assertIn(f"in{self.NO_BREAK_SPACE}the", self.pages["en/index.html"])

    def test_prices_are_not_broken_inside(self):
        text = self.pages["endosfera-terapiya/index.html"]
        self.assertIn(f"1{self.NO_BREAK_SPACE}000{self.NO_BREAK_SPACE}000{self.NO_BREAK_SPACE}đ", text)


class ImageNamesTest(unittest.TestCase):
    """Файлы картинок услуг названы по английскому адресу страницы, а не русским транслитом."""

    @classmethod
    def setUpClass(cls):
        cls.content = build.load()[1]
        cls.english_slugs = load_locale("en").slugs
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}

    def test_hero_image_is_named_like_english_page_of_service(self):
        for service_id, service in self.content["services"].items():
            with self.subTest(service=service_id):
                self.assertEqual(service["hero_image"], self.english_slugs[service_id])

    def test_source_and_built_files_exist_under_new_names(self):
        sources = build.ROOT / "sources" / "img"
        for service in self.content["services"].values():
            stem = service["hero_image"]
            with self.subTest(stem=stem):
                self.assertTrue((sources / f"{stem}.jpg").is_file())
                for built in (f"{stem}.webp", f"card-{stem}.webp"):
                    self.assertTrue((build.OUT / "assets" / "img" / built).is_file(), built)

    def test_pages_link_only_to_existing_images_with_new_names(self):
        images_dir = build.OUT / "assets" / "img"
        left_under_old_name = [page_id for page_id in self.english_slugs
                               if (images_dir / f"{page_id}.webp").exists()
                               or (images_dir / f"card-{page_id}.webp").exists()]
        self.assertEqual(left_under_old_name, [])
        for path, html in self.pages.items():
            for name in re.findall(r"/assets/img/([\w.-]+\.webp)", html):
                with self.subTest(page=path, image=name):
                    self.assertTrue((build.OUT / "assets" / "img" / name).is_file())


class FirstBlockRevealInBuiltPagesTest(unittest.TestCase):
    """Первый блок разделов виден сразу; анимация появления ниже и на других страницах прежняя."""
    SECTION_PATHS = ("korrekciya-figury/index.html", "lifting-i-omolozhenie/index.html",
                     "lazernye-procedury/index.html", "en/body-contouring/index.html",
                     "en/non-surgical-face-lift/index.html", "en/laser-treatments/index.html")
    SERVICE_PATHS = ("lpg-massazh/index.html", "en/lpg-massage/index.html")
    HOME_PATHS = ("index.html", "en/index.html")
    SECTION_HEAD_RE = re.compile(r'<div class="section-head"([^>]*)>')

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}

    def section_head_attributes(self, path):
        return self.SECTION_HEAD_RE.findall(self.pages[path])

    def test_first_block_of_section_has_no_reveal_animation(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                self.assertNotIn("data-reveal", self.section_head_attributes(path)[0])

    def test_first_block_of_section_is_the_one_with_the_heading(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                first_head = self.pages[path].split('<div class="section-head"', 1)[1]
                self.assertIn("<h1>", first_head.split("</div>", 1)[0])

    def test_blocks_below_the_first_keep_reveal_animation(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                below = self.section_head_attributes(path)[1:]
                self.assertTrue(below)
                for attributes in below:
                    self.assertIn("data-reveal", attributes)

    def test_section_heads_of_other_pages_keep_reveal_animation(self):
        for path in self.SERVICE_PATHS + self.HOME_PATHS:
            with self.subTest(path=path):
                for attributes in self.section_head_attributes(path):
                    self.assertIn("data-reveal", attributes)


class FirstCardRevealInBuiltPagesTest(unittest.TestCase):
    """Первая карточка раздела (на телефоне она на первом экране и даёт LCP) видна сразу.
    Она получает тот же класс видимости, что reveal.js ставит остальным, поэтому наведение
    и переходы у всех карточек одинаковы."""
    CARD_CLASS_RE = re.compile(r'<a class="([^"]*\brelated-card\b[^"]*)"')
    VISIBLE_CLASS = "is-visible"
    SECTION_PATHS = FirstBlockRevealInBuiltPagesTest.SECTION_PATHS
    SERVICE_PATHS = FirstBlockRevealInBuiltPagesTest.SERVICE_PATHS

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}

    def card_classes(self, path):
        return [value.split() for value in self.CARD_CLASS_RE.findall(self.pages[path])]

    def test_only_first_card_of_section_is_visible_from_the_start(self):
        for path in self.SECTION_PATHS:
            with self.subTest(path=path):
                cards = self.card_classes(path)
                self.assertGreater(len(cards), 1)
                self.assertIn(self.VISIBLE_CLASS, cards[0])
                for classes in cards[1:]:
                    self.assertNotIn(self.VISIBLE_CLASS, classes)

    def test_see_also_cards_of_services_keep_animation(self):
        for path in self.SERVICE_PATHS:
            with self.subTest(path=path):
                for classes in self.card_classes(path):
                    self.assertNotIn(self.VISIBLE_CLASS, classes)

    def test_reveal_script_and_styles_treat_every_card_alike(self):
        assets = build.OUT / "assets"
        self.assertNotIn("data-reveal-skip", (assets / "js" / "reveal.js").read_text(encoding="utf-8"))
        self.assertNotIn("data-reveal-skip", (assets / "css" / "reveal.css").read_text(encoding="utf-8"))
        self.assertIn(f'.{self.VISIBLE_CLASS}', (assets / "css" / "reveal.css").read_text(encoding="utf-8"))


class RevealFallbackInBuiltPagesTest(unittest.TestCase):
    """Страница не должна оставаться пустой, если скрипт появлений не доехал."""
    REVEAL_TAG_RE = re.compile(r'<script type="module" src="[^"]*/reveal\.js"[^>]*>')

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}
        cls.reveal_source = (build.OUT / "assets" / "js" / "reveal.js").read_text(encoding="utf-8")

    def test_reveal_script_tag_shows_content_on_load_error(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                self.assertIn('onerror="showWithoutReveal()"', self.REVEAL_TAG_RE.search(html).group(0))

    def test_head_drops_hiding_class_unless_reveal_reported_ready(self):
        for path, html in self.pages.items():
            with self.subTest(path=path):
                head = html.split("</head>")[0]
                self.assertIn("window.showWithoutReveal", head)
                self.assertIn("classList.contains('reveal-ready')", head)
                self.assertIn("root.classList.add('js')", head)

    def test_reveal_script_reports_ready_with_the_class_head_waits_for(self):
        self.assertIn('const READY_CLASS = "reveal-ready";', self.reveal_source)
        self.assertIn("classList.add(READY_CLASS)", self.reveal_source)


class StructuredDataImagesInBuiltPagesTest(unittest.TestCase):
    """Картинки разметки (image, logo) — обещание поисковику: файл должен лежать в сборке.
    Страницы строятся в памяти из текущих исходников, а не читаются с диска: деплой гоняет
    тесты до build.py, и проверка закоммиченной сборки не поймала бы битый путь в site.yml."""
    IMAGE_KEYS = ("image", "logo")
    LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

    @classmethod
    def setUpClass(cls):
        cls.pages = {**build_real_pages("ru"), **build_real_pages("en")}
        cls.base = build.load()[0]["base_url"] + "/"

    @classmethod
    def image_urls_of(cls, node):
        """Все адреса картинок в дереве JSON-LD, на любой глубине."""
        if isinstance(node, dict):
            own = [node[key] for key in cls.IMAGE_KEYS if isinstance(node.get(key), str)]
            return own + [url for value in node.values() for url in cls.image_urls_of(value)]
        if isinstance(node, list):
            return [url for item in node for url in cls.image_urls_of(item)]
        return []

    def test_every_image_of_every_page_exists_in_build(self):
        checked = 0
        for path, html in self.pages.items():
            for block in self.LD_RE.findall(html):
                for url in self.image_urls_of(json.loads(block)):
                    checked += 1
                    self.assertTrue((build.OUT / url.removeprefix(self.base)).is_file(),
                                    f"{path}: нет файла {url}")
        self.assertGreater(checked, 0)


class SalonMarkupInBuiltPagesTest(unittest.TestCase):
    """Узел салона в разметке каждой страницы: логотип, описание на языке страницы, город без дубля."""
    LD_RE = StructuredDataImagesInBuiltPagesTest.LD_RE
    CYRILLIC = re.compile("[А-Яа-яЁё]")

    @classmethod
    def setUpClass(cls):
        cls.pages = {"ru": build_real_pages("ru"), "en": build_real_pages("en")}

    def salon_nodes(self, language):
        for path, html in self.pages[language].items():
            for block in self.LD_RE.findall(html):
                for node in json.loads(block).get("@graph", []):
                    if node.get("@type") == "BeautySalon":
                        yield path, node

    def test_every_page_has_salon_with_logo_and_city_only(self):
        for language in self.pages:
            nodes = list(self.salon_nodes(language))
            self.assertEqual(len(nodes), len(self.pages[language]))
            for path, node in nodes:
                with self.subTest(path=path):
                    self.assertIn("logo", node)
                    self.assertNotIn("addressRegion", node["address"])
                    self.assertEqual(node["address"]["addressLocality"], "Da Nang")

    def test_description_follows_language_of_page(self):
        for path, node in self.salon_nodes("ru"):
            with self.subTest(path=path):
                self.assertRegex(node["description"], self.CYRILLIC)
        for path, node in self.salon_nodes("en"):
            with self.subTest(path=path):
                self.assertNotRegex(node["description"], self.CYRILLIC)
                self.assertTrue(node["description"].startswith("Neva Beauty is a beauty center"))


class LanguageSwitchInBuiltPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ru, cls.en = build_real_pages("ru"), build_real_pages("en")

    def test_russian_page_has_english_pill_in_header_and_drawer(self):
        pill = ('<a class="lang-pill" href="/en/lpg-massage/" hreflang="en" lang="en" '
                'aria-label="EN — English version" data-lang="en">EN</a>')
        html = self.ru["lpg-massazh/index.html"]
        self.assertEqual(html.count(pill), 2)  # шапка (с 1024 px) и мобильное меню
        self.assertIn(pill, self.drawer_home_row(html))
        self.assertNotIn('lang-pill', self.drawer_footer(html))

    def test_english_page_has_russian_pill_in_header_and_drawer(self):
        pill = ('<a class="lang-pill" href="/lpg-massazh/" hreflang="ru" lang="ru" '
                'aria-label="RU — русская версия" data-lang="ru">RU</a>')
        html = self.en["en/lpg-massage/index.html"]
        self.assertEqual(html.count(pill), 2)
        self.assertIn(pill, self.drawer_home_row(html))
        self.assertNotIn('lang-pill', self.drawer_footer(html))

    @staticmethod
    def drawer_footer(html):
        start = html.index('<div class="drawer__footer">')
        return html[start:html.index('</aside>', start)]

    @staticmethod
    def drawer_home_row(html):
        nav = html[html.index('<nav class="drawer__nav">'):]
        nav = nav[:nav.index('</nav>')]
        start = nav.index('<div class="drawer__home-row"')
        return nav[start:nav.index('</div>', start)]

    def test_drawer_pill_follows_home_link_in_one_row(self):
        row = self.drawer_home_row(self.ru["lpg-massazh/index.html"])
        self.assertIn('style="--i:1"', row)  # строка появляется как пункт «Главная»
        self.assertLess(row.index('<a class="drawer__link" href="/"'), row.index('class="lang-pill"'))
        self.assertEqual(row.count('<a '), 2)
        english = self.drawer_home_row(self.en["en/lpg-massage/index.html"])
        self.assertLess(english.index('<a class="drawer__link" href="/en/"'), english.index('class="lang-pill"'))

    def test_drawer_home_row_is_first_in_nav(self):
        nav = self.ru["lpg-massazh/index.html"]
        nav = nav[nav.index('<nav class="drawer__nav">'):]
        self.assertLess(nav.index('drawer__home-row'), nav.index('drawer__group'))

    def test_drawer_has_pill_instead_of_language_line(self):
        footer = self.drawer_footer(self.ru["lpg-massazh/index.html"])
        self.assertNotIn('lang-line', footer)
        self.assertNotIn('drawer__langs', footer)

    def test_language_line_only_in_site_footer(self):
        html = self.ru["lpg-massazh/index.html"]
        self.assertEqual(html.count('<p class="lang-line'), 1)
        self.assertIn('<p class="lang-line site-footer__langs">', html)
        self.assertEqual(html.count('<span class="lang-line__current" lang="ru" aria-current="true">'
                                    'Русский</span>'), 1)  # только подвал
        self.assertEqual(html.count('data-lang="en">English</a>'), 1)


class JsonLdInBuiltPagesTest(unittest.TestCase):
    LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
    SHARED_TYPES = ("Organization", "BeautySalon", "WebSite")

    @classmethod
    def setUpClass(cls):
        cls.ru, cls.en = build_real_pages("ru"), build_real_pages("en")

    @classmethod
    def graph_of(cls, html):
        return json.loads(cls.LD_RE.search(html).group(1))["@graph"]

    @classmethod
    def node_of(cls, html, node_type):
        return next(node for node in cls.graph_of(html) if node["@type"] == node_type)

    def test_business_nodes_have_same_ids_in_both_languages(self):
        for node_type in self.SHARED_TYPES:
            self.assertEqual(self.node_of(self.ru["index.html"], node_type)["@id"],
                             self.node_of(self.en["en/index.html"], node_type)["@id"])

    def test_website_names_both_languages_on_both_sides(self):
        for html in (self.ru["index.html"], self.en["en/index.html"]):
            self.assertEqual(self.node_of(html, "WebSite")["inLanguage"], ["ru", "en"])

    def test_every_page_has_single_in_language_key(self):
        for pages_of_language in (self.ru, self.en):
            for path, html in pages_of_language.items():
                self.assertEqual(html.count('"inLanguage"'), 1, path)

    def test_english_service_has_english_id_and_title_as_name(self):
        _site, content, _prices = build.load()
        service = self.node_of(self.en["en/laser-hair-removal/index.html"], "Service")
        self.assertEqual(service["@id"], "https://vn.neva.beauty/en/laser-hair-removal/#service")
        self.assertEqual(service["name"], "Laser Hair Removal")

    def test_russian_service_keeps_russian_id(self):
        service = self.node_of(self.ru["lazernaya-epilyaciya/index.html"], "Service")
        self.assertEqual(service["@id"], "https://vn.neva.beauty/lazernaya-epilyaciya/#service")


class HeadingsKeepWholeWordsTest(unittest.TestCase):
    """Слова заголовков и названий не рвутся переносом: словарных переносов в стилях нет,
    а кегль заголовков, где слову может не хватить места, считается от токена --word-fit-*."""
    CSS_DIR = build.OUT / "assets" / "css"
    SOURCES = ("tokens.css", "base.css", "components.css", "home.css", "service.css")
    FIT_TOKEN_RE = re.compile(r"var\((--word-fit-[\w-]+)\)")

    @classmethod
    def setUpClass(cls):
        cls.css = {name: (cls.CSS_DIR / name).read_text(encoding="utf-8") for name in cls.SOURCES}

    def test_no_style_turns_on_automatic_hyphenation(self):
        for name, text in self.css.items():
            with self.subTest(file=name):
                self.assertNotIn("hyphens:auto", text.replace(" ", ""))

    def test_every_fit_token_in_use_is_defined(self):
        used = {token for text in self.css.values() for token in self.FIT_TOKEN_RE.findall(text)}
        self.assertEqual(used, {"--word-fit-section", "--word-fit-service", "--word-fit-hero",
                         "--word-fit-faq"})
        for token in used:
            self.assertRegex(self.css["tokens.css"], rf"{token}:\d+(\.\d+)?;")


def plain_text(html):
    """Видимый текст разметки: без тегов, неразрывные пробелы — обычными."""
    return re.sub(r"<[^>]+>", "", html).replace("\u00a0", " ")


class ServicePriceLineTest(unittest.TestCase):
    CONTEXT = SimpleNamespace(t=lambda key, price: f"{key}|{price}")
    SECTIONS = [{"items": [{"name": "A", "price": "700 000 đ"}, {"name": "B", "price": "900 000 đ"},
                           {"name": "Добавка", "price": "+350 000 đ"}]}]

    def test_several_prices_give_line_with_minimum_and_from_form(self):
        self.assertEqual(pages.service_price_line(self.CONTEXT, self.SECTIONS),
                         "service.price_line_from|700 000 đ")

    def test_single_price_gives_exact_form_without_from(self):
        sections = [{"items": [{"name": "A", "price": "1 100 000 đ"}]}]
        self.assertEqual(pages.service_price_line(self.CONTEXT, sections),
                         "service.price_line_exact|1 100 000 đ")

    def test_no_prices_give_no_line(self):
        self.assertIsNone(pages.service_price_line(self.CONTEXT, []))


class ServicePriceLineInBuiltPagesTest(unittest.TestCase):
    """Строка под заголовком услуги на обоих языках: цифра — та же, что в ответе FAQ
    «Сколько стоит», а слова — из строк языка."""
    LINE_RE = re.compile(r'<p class="svc-hero__price">(.*?)</p>', re.S)
    ANSWER_RE = re.compile(r'<p class="faq__a">(.*?)</p>', re.S)
    AMOUNT_RE = re.compile(r"\d[\d ]*\d đ")

    @classmethod
    def setUpClass(cls):
        _site, cls.content, cls.prices = build.load()
        cls.pages = {"ru": build_real_pages("ru"), "en": build_real_pages("en")}
        cls.locales = {code: load_locale(code) for code in cls.pages}

    def page_path(self, code, service_id):
        prefix = "en/" if code == "en" else ""
        return f"{prefix}{self.locales[code].slug(service_id)}/index.html"

    def price_answer_index(self, service_id):
        faq = self.content["services"][service_id]["faq"]
        return next(index for index, item in enumerate(faq) if "{price}" in item["a"])

    def test_every_service_page_has_one_line_in_both_languages(self):
        for code, built in self.pages.items():
            for service_id in self.content["services"]:
                with self.subTest(language=code, service=service_id):
                    html = built[self.page_path(code, service_id)]
                    self.assertEqual(len(self.LINE_RE.findall(html)), 1)

    def test_line_amount_equals_amount_in_price_answer_of_faq(self):
        for code, built in self.pages.items():
            for service_id in self.content["services"]:
                with self.subTest(language=code, service=service_id):
                    html = built[self.page_path(code, service_id)]
                    line = plain_text(self.LINE_RE.search(html).group(1))
                    answer = plain_text(self.ANSWER_RE.findall(html)[self.price_answer_index(service_id)])
                    self.assertEqual(self.AMOUNT_RE.search(line).group(), self.AMOUNT_RE.search(answer).group())

    def test_line_words_come_from_language_strings(self):
        for code, built in self.pages.items():
            for service_id in self.content["services"]:
                with self.subTest(language=code, service=service_id):
                    html = built[self.page_path(code, service_id)]
                    line = plain_text(self.LINE_RE.search(html).group(1))
                    amount, is_range = pricing.price_summary(self.prices[service_id])
                    key = "service.price_line_from" if is_range else "service.price_line_exact"
                    self.assertEqual(line, self.locales[code].t(key, price=amount))


class CategoryCardPricesInBuiltPagesTest(unittest.TestCase):
    """Подпись «от …» на карточках направлений главной обоих языков: цифра — та же, что в ответе
    «Сколько стоит» страницы направления (у ухода за лицом своей страницы нет — страницы услуги)."""
    CAPTION_RE = re.compile(r'<span class="cat-card__price">(.*?)</span>', re.S)
    ANSWER_RE = ServicePriceLineInBuiltPagesTest.ANSWER_RE
    AMOUNT_RE = ServicePriceLineInBuiltPagesTest.AMOUNT_RE

    @classmethod
    def setUpClass(cls):
        _site, cls.content, cls.prices = build.load()
        cls.pages = {"ru": build_real_pages("ru"), "en": build_real_pages("en")}
        cls.locales = {code: load_locale(code) for code in cls.pages}

    def answer_page_and_faq(self, code, cat):
        """Страница с ответом «Сколько стоит» этого направления и FAQ, из которого он взят."""
        prefix = "en/" if code == "en" else ""
        if len(cat["services"]) > 1:
            return f"{prefix}{self.locales[code].slug(cat['slug'])}/index.html", cat["faq"]
        service_id = cat["services"][0]
        return (f"{prefix}{self.locales[code].slug(service_id)}/index.html",
                self.content["services"][service_id]["faq"])

    def price_answer(self, code, cat):
        path, faq = self.answer_page_and_faq(code, cat)
        index = next(i for i, item in enumerate(faq) if "{price}" in item["a"])
        return plain_text(self.ANSWER_RE.findall(self.pages[code][path])[index])

    def test_every_category_card_has_a_caption(self):
        for code, built in self.pages.items():
            home = built["en/index.html" if code == "en" else "index.html"]
            with self.subTest(language=code):
                self.assertEqual(len(self.CAPTION_RE.findall(home)), len(self.content["categories"]))

    def test_caption_amount_equals_amount_in_price_answer(self):
        for code, built in self.pages.items():
            home = built["en/index.html" if code == "en" else "index.html"]
            captions = [plain_text(text) for text in self.CAPTION_RE.findall(home)]
            for cat, caption in zip(self.content["categories"], captions):
                with self.subTest(language=code, category=cat["slug"]):
                    self.assertEqual(self.AMOUNT_RE.search(caption).group(),
                                     self.AMOUNT_RE.search(self.price_answer(code, cat)).group())

    def test_caption_words_come_from_language_strings(self):
        for code, built in self.pages.items():
            home = built["en/index.html" if code == "en" else "index.html"]
            captions = [plain_text(text) for text in self.CAPTION_RE.findall(home)]
            for cat, caption in zip(self.content["categories"], captions):
                with self.subTest(language=code, category=cat["slug"]):
                    amount = self.AMOUNT_RE.search(caption).group()
                    self.assertEqual(caption, self.locales[code].format_from(amount))


class DermatologyConsultationInBuiltPagesTest(unittest.TestCase):
    """Консультация дерматолога названа только в русском тексте: на всех 15 русских страницах
    обе цены, английские страницы прежние и о дерматологе молчат."""
    RUSSIAN_SENTENCE = ("Консультация косметолога стоит {cosmetologist}, дерматолога — "
                        "{dermatologist}; если вы делаете процедуру, консультация входит "
                        "в её стоимость.")
    ENGLISH_SENTENCE = ("A consultation with the aesthetician costs {cosmetologist}; if you have "
                        "a treatment, the consultation is included in the treatment price.")
    PAGES_WITH_BOOKING_ANSWER = 15

    @classmethod
    def setUpClass(cls):
        cls.site, _content, _prices = build.load()
        cls.pages = {"ru": build_real_pages("ru"), "en": build_real_pages("en")}

    def prices(self):
        consultation = self.site["consultation"]
        return {"cosmetologist": consultation["price"], "dermatologist": consultation["dermatology_price"]}

    def pages_with(self, code, sentence):
        return [path for path, html in self.pages[code].items() if sentence in plain_text(html)]

    def test_russian_pages_name_both_prices(self):
        found = self.pages_with("ru", self.RUSSIAN_SENTENCE.format(**self.prices()))
        self.assertEqual(len(found), self.PAGES_WITH_BOOKING_ANSWER)

    def test_russian_pages_do_not_keep_the_old_phrase(self):
        old = "Консультация косметолога стоит {cosmetologist}; если".format(**self.prices())
        self.assertEqual(self.pages_with("ru", old), [])

    def test_english_pages_keep_their_sentence_and_never_name_a_dermatologist(self):
        found = self.pages_with("en", self.ENGLISH_SENTENCE.format(**self.prices()))
        self.assertEqual(len(found), self.PAGES_WITH_BOOKING_ANSWER)
        for path, html in self.pages["en"].items():
            with self.subTest(path=path):
                self.assertNotIn("dermatolog", html.lower())


class HeaderAndHeroTokensTest(unittest.TestCase):
    """Высота шапки и размеры фото героя записаны один раз, в tokens.css, а стили берут их оттуда."""
    CSS_DIR = build.OUT / "assets" / "css"
    MAGIC = {"components.css": ("76px", "77px"), "home.css": ("375px", ".975", "78%")}

    def test_styles_do_not_repeat_header_height_or_hero_photo_numbers(self):
        for name, numbers in self.MAGIC.items():
            text = (self.CSS_DIR / name).read_text(encoding="utf-8")
            for number in numbers:
                with self.subTest(file=name, number=number):
                    self.assertNotIn(number, text)

    def test_tokens_define_header_and_hero_photo(self):
        tokens = (self.CSS_DIR / "tokens.css").read_text(encoding="utf-8")
        for token in ("--header-min", "--header-height", "--hero-photo-share",
                      "--hero-photo-width-max", "--hero-photo-ratio", "--hero-photo-min"):
            with self.subTest(token=token):
                self.assertRegex(tokens, rf"{token}:")
