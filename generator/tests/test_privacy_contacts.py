"""Контакты оператора в политике конфиденциальности подставляются из site.yml."""
import unittest

import build
import contacts
import pages
from locales import load_privacy

CONTACTS = {"whatsapp_url": "https://wa.me/100", "whatsapp_phone": "+1 00",
            "telegram_url": "https://t.me/salon", "instagram_url": "https://instagram.com/salon/",
            "privacy_email": "owner@example.com"}
LOCALES = ("ru", "en")


class AccountHandleTest(unittest.TestCase):
    def test_handle_is_path_of_channel_address(self):
        self.assertEqual(contacts.account_handle("https://t.me/doctor_cosmetolog_pro"),
                         "@doctor_cosmetolog_pro")

    def test_trailing_slash_does_not_change_handle(self):
        self.assertEqual(contacts.account_handle("https://www.instagram.com/vn.neva.beauty/"),
                         "@vn.neva.beauty")


class FillPrivacyTest(unittest.TestCase):
    def test_links_get_bare_addresses_and_texts(self):
        body = ('<a href="{whatsapp_url}">{whatsapp_phone}</a> <a href="{telegram_url}">'
                '{telegram_handle}</a> <a href="{instagram_url}">{instagram_handle}</a> '
                '<a href="mailto:{privacy_email}">{privacy_email}</a>')
        self.assertEqual(pages.fill_privacy(body, CONTACTS),
                         '<a href="https://wa.me/100">+1 00</a> <a href="https://t.me/salon">'
                         '@salon</a> <a href="https://instagram.com/salon/">@salon</a> '
                         '<a href="mailto:owner@example.com">owner@example.com</a>')

    def test_unknown_placeholder_is_error(self):
        with self.assertRaisesRegex(ValueError, "{phone}"):
            pages.fill_privacy("<p>{phone}</p>", CONTACTS)

    def test_values_are_escaped(self):
        tricky = dict(CONTACTS, whatsapp_phone="<b>")
        self.assertEqual(pages.fill_privacy("{whatsapp_phone}", tricky), "&lt;b&gt;")


class RealPolicyTest(unittest.TestCase):
    """Тексты политики не держат контакты руками: правка в site.yml доходит до политики."""

    @classmethod
    def setUpClass(cls):
        cls.site_contacts = build.load()[0]["contacts"]

    def test_policy_texts_name_no_contact_by_hand(self):
        values = pages.privacy_tokens(self.site_contacts).values()
        for code in LOCALES:
            text = str(load_privacy(code))
            for value in values:
                with self.subTest(code=code, value=value):
                    self.assertNotIn(value, text)

    def test_filled_policy_has_every_contact(self):
        values = pages.privacy_tokens(self.site_contacts).values()
        for code in LOCALES:
            filled = str(pages.fill_privacy(load_privacy(code), self.site_contacts))
            for value in values:
                with self.subTest(code=code, value=value):
                    self.assertIn(value, filled)


if __name__ == "__main__":
    unittest.main()
