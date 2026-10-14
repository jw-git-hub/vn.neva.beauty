import unittest
import urllib.parse

import contacts
from locales import load_locale

CONTACTS = {"whatsapp_url": "https://wa.me/100", "telegram_url": "https://t.me/salon",
            "instagram_url": "https://instagram.com/salon", "telegram_prefill": True}


def text_of(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["text"][0]


class ContactMessageTest(unittest.TestCase):
    def setUp(self):
        self.locale = load_locale("ru")

    def test_page_title_goes_into_text(self):
        self.assertEqual(contacts.contact_message(self.locale, "LPG-массаж"),
                         "Здравствуйте! Хочу записаться на: LPG-массаж")

    def test_no_title_gives_generic_text(self):
        self.assertEqual(contacts.contact_message(self.locale),
                         "Здравствуйте! Хочу записаться")


class ContactUrlTest(unittest.TestCase):
    def test_whatsapp_carries_text(self):
        url = contacts.contact_url(CONTACTS, "whatsapp", "Привет")
        self.assertTrue(url.startswith("https://wa.me/100?text="))
        self.assertEqual(text_of(url), "Привет")

    def test_telegram_carries_text_when_prefill_on(self):
        self.assertEqual(text_of(contacts.contact_url(CONTACTS, "telegram", "Привет")), "Привет")

    def test_telegram_without_prefill_has_no_text(self):
        plain = dict(CONTACTS, telegram_prefill=False)
        self.assertEqual(contacts.contact_url(plain, "telegram", "Привет"), "https://t.me/salon")

    def test_instagram_never_carries_text(self):
        self.assertEqual(contacts.contact_url(CONTACTS, "instagram", "Привет"),
                         "https://instagram.com/salon")

    def test_special_characters_are_encoded(self):
        url = contacts.contact_url(CONTACTS, "whatsapp", "A&B + «C»: D/E")
        query = urllib.parse.urlsplit(url).query
        self.assertNotIn("&", query)
        self.assertNotIn("+", query)
        self.assertEqual(text_of(url), "A&B + «C»: D/E")


class LinkAttrsTest(unittest.TestCase):
    def test_attributes_in_fixed_order(self):
        attrs = contacts.link_attrs(CONTACTS, "instagram", "footer", "Привет")
        self.assertEqual(str(attrs), 'href="https://instagram.com/salon" target="_blank" '
                                     'rel="noopener" data-contact="instagram" data-place="footer"')

    def test_unknown_channel_is_error(self):
        with self.assertRaises(ValueError):
            contacts.link_attrs(CONTACTS, "viber", "footer", "Привет")

    def test_unknown_place_is_error(self):
        with self.assertRaises(ValueError):
            contacts.link_attrs(CONTACTS, "whatsapp", "sidebar", "Привет")


class FillContactLinksTest(unittest.TestCase):
    def test_placeholder_href_becomes_tracked_link(self):
        html = '<a href="{whatsapp}" target="_blank" rel="noopener">WhatsApp</a>'
        filled = contacts.fill_contact_links(html, CONTACTS, "Привет")
        self.assertIn('data-contact="whatsapp" data-place="faq" target="_blank"', filled)
        self.assertIn(contacts.contact_url(CONTACTS, "whatsapp", "Привет"), filled)

    def test_bare_placeholder_is_left_for_tokens(self):
        """Плейсхолдер не в href — не ссылка связи; на нём упадёт pages.fill_tokens."""
        self.assertEqual(contacts.fill_contact_links("{telegram}", CONTACTS, "Привет"),
                         "{telegram}")


class PrefillFlagTest(unittest.TestCase):
    def test_missing_flag_is_error(self):
        """Опечатка в имени флага не должна молча убирать текст из ссылок Telegram."""
        flagless = {key: value for key, value in CONTACTS.items() if key != "telegram_prefill"}
        with self.assertRaises(ValueError):
            contacts.prefill_channels(flagless)

    def test_string_flag_is_error(self):
        with self.assertRaises(ValueError):
            contacts.prefill_channels(dict(CONTACTS, telegram_prefill="false"))
