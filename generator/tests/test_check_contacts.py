import unittest
import urllib.parse

from bs4 import BeautifulSoup

import check_contacts

CONTACTS = {"whatsapp_url": "https://wa.me/100", "telegram_url": "https://t.me/salon",
            "instagram_url": "https://instagram.com/salon", "telegram_prefill": True}
MESSAGE = "Привет"
TEXT = "?text=" + urllib.parse.quote(MESSAGE)


def errors(body, site_contacts=CONTACTS):
    soup = BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")
    return check_contacts.link_errors(soup, "page.html", site_contacts, MESSAGE)


class LinkErrorsTest(unittest.TestCase):
    def test_tracked_links_pass(self):
        body = (f'<a href="https://wa.me/100{TEXT}" data-contact="whatsapp" data-place="hero">W</a>'
                f'<a href="https://t.me/salon{TEXT}" data-contact="telegram" data-place="faq">T</a>'
                '<a href="https://instagram.com/salon" data-contact="instagram" '
                'data-place="footer">I</a>')
        self.assertEqual(errors(body), [])

    def test_raw_contact_link_is_error(self):
        self.assertTrue(errors(f'<a href="https://wa.me/100{TEXT}">W</a>'))

    def test_unknown_place_is_error(self):
        self.assertTrue(errors(f'<a href="https://wa.me/100{TEXT}" data-contact="whatsapp" '
                               'data-place="sidebar">W</a>'))

    def test_tag_on_foreign_link_is_error(self):
        self.assertTrue(errors('<a href="/prices/" data-contact="whatsapp" data-place="hero">W</a>'))

    def test_whatsapp_without_text_is_error(self):
        self.assertTrue(errors('<a href="https://wa.me/100" data-contact="whatsapp" '
                               'data-place="faq">W</a>'))

    def test_wrong_text_is_error(self):
        other = "?text=" + urllib.parse.quote("Другое")
        self.assertTrue(errors(f'<a href="https://wa.me/100{other}" data-contact="whatsapp" '
                               'data-place="hero">W</a>'))

    def test_telegram_without_text_is_fine_when_prefill_off(self):
        plain = dict(CONTACTS, telegram_prefill=False)
        body = '<a href="https://t.me/salon" data-contact="telegram" data-place="footer">T</a>'
        self.assertEqual(errors(body, plain), [])

    def test_instagram_with_text_is_error(self):
        self.assertTrue(errors(f'<a href="https://instagram.com/salon{TEXT}" '
                               'data-contact="instagram" data-place="footer">I</a>'))

    def test_links_in_legal_text_are_skipped(self):
        """В политике это контакты оператора для вопросов о данных, а не кнопки записи:
        текст «Хочу записаться» и метки обращений им не нужны."""
        body = '<div class="legal-page"><a href="https://wa.me/100">+100</a></div>'
        self.assertEqual(errors(body), [])

    def test_whitespace_differences_are_not_errors(self):
        """Ожидаемый текст строится по h1, где пробелы схлопнуты; в адресе — исходное
        название с неразрывным или двойным пробелом. Это один и тот же текст."""
        raw = "?text=" + urllib.parse.quote("Хочу на: M\xa022  лифтинг\n")
        soup = BeautifulSoup(f'<a href="https://wa.me/100{raw}" data-contact="whatsapp" '
                             'data-place="hero">W</a>', "html.parser")
        self.assertEqual(check_contacts.link_errors(soup, "page.html", CONTACTS,
                                                    "Хочу на: M 22 лифтинг"), [])
