"""Клики по ссылкам в коде Метрики: цель contact со страницей и канал, внешние переходы."""
import json
import subprocess
import unittest
from pathlib import Path

from tests.test_build import build_real_pages
from tests.test_language_redirect import METRIKA_RE, NODE

HARNESS = Path(__file__).resolve().parent / "js" / "metrika_clicks.js"
RU_PAGE_PATH, EN_PAGE_PATH = "/lpg-massazh/", "/en/lpg-massage/"
CONTACTS_BY_PAGE, EXITS_BY_PAGE = "contacts by page", "exits by page"
OWN_HOSTNAME = "vn.neva.beauty"
SECOND_SALON = "th.neva.beauty"


def web_link(href, hostname, attrs=None):
    return {"href": href, "protocol": "https:", "hostname": hostname, "attrs": attrs or {}}


def click(link, event_type="click", button=0):
    return {"type": event_type, "button": button, "link": link}


WHATSAPP = web_link("https://wa.me/84900000000", "wa.me",
                    {"data-contact": "whatsapp", "data-place": "booking", "href": "https://wa.me/84900000000"})
SECOND_SALON_LINK = web_link("https://th.neva.beauty/", SECOND_SALON)
MAIL_LINK = {"href": "mailto:a@b.c", "protocol": "mailto:", "hostname": "", "attrs": {}}
OWN_ABSOLUTE = web_link("https://vn.neva.beauty/en/", OWN_HOSTNAME)
OWN_RELATIVE = web_link("/en/", OWN_HOSTNAME)


@unittest.skipUnless(NODE, "нужен node: код Метрики проверяется в нём")
class MetrikaClicksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ru_script = METRIKA_RE.search(build_real_pages("ru")["lpg-massazh/index.html"]).group(1)
        cls.en_script = METRIKA_RE.search(build_real_pages("en")["en/lpg-massage/index.html"]).group(1)

    def calls_after(self, script, *events):
        payload = json.dumps({"script": script, "events": list(events)})
        result = subprocess.run([NODE, str(HARNESS)], input=payload, capture_output=True,
                                text=True, check=True)
        return json.loads(result.stdout)

    def test_contact_click_reports_flat_params_and_page_branch(self):
        """Клик по whatsapp: плоские параметры как раньше плюс ветка «страница → канал → место»."""
        calls = self.calls_after(self.ru_script, click(WHATSAPP))
        self.assertEqual(len(calls), 1)
        counter_id, method, goal, params = calls[0]
        self.assertEqual((method, goal), ("reachGoal", "contact"))
        self.assertIsInstance(counter_id, int)
        self.assertEqual({key: params[key] for key in ("channel", "lang", "page", "place")},
                         {"channel": "whatsapp", "lang": "en", "page": "lpg-massazh", "place": "booking"})
        self.assertEqual(params[CONTACTS_BY_PAGE], {RU_PAGE_PATH: {"whatsapp": "booking"}})

    def test_english_page_branch_starts_with_english_path(self):
        """На английской странице ветка начинается с её адреса /en/lpg-massage/."""
        calls = self.calls_after(self.en_script, click(WHATSAPP))
        self.assertEqual(calls[0][3][CONTACTS_BY_PAGE], {EN_PAGE_PATH: {"whatsapp": "booking"}})

    def test_external_site_click_reports_exit_param(self):
        """Переход на другой сайт уходит параметром визита без цели."""
        calls = self.calls_after(self.ru_script, click(SECOND_SALON_LINK))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], ["params", {EXITS_BY_PAGE: {RU_PAGE_PATH: SECOND_SALON}}])

    def test_mailto_click_reports_email_exit(self):
        """mailto: учитывается как выход «e-mail»."""
        calls = self.calls_after(self.ru_script, click(MAIL_LINK))
        self.assertEqual(calls[0][1:], ["params", {EXITS_BY_PAGE: {RU_PAGE_PATH: "e-mail"}}])

    def test_internal_links_are_not_reported(self):
        """Абсолютная ссылка на свой сайт и относительная ссылка выходом не считаются."""
        self.assertEqual(self.calls_after(self.ru_script, click(OWN_ABSOLUTE), click(OWN_RELATIVE)), [])

    def test_click_outside_link_is_not_reported(self):
        """Клик не по ссылке ничего не отправляет."""
        self.assertEqual(self.calls_after(self.ru_script, click(None)), [])

    def test_middle_button_counts_but_right_button_does_not(self):
        """auxclick: средняя кнопка учитывается, правая нет."""
        middle = self.calls_after(self.ru_script, click(SECOND_SALON_LINK, "auxclick", 1))
        right = self.calls_after(self.ru_script, click(SECOND_SALON_LINK, "auxclick", 2))
        self.assertEqual(len(middle), 1)
        self.assertEqual(right, [])

    def test_contact_link_is_not_reported_as_exit(self):
        """Ссылка связи идёт только в contact, вызова params для неё нет."""
        calls = self.calls_after(self.ru_script, click(WHATSAPP))
        self.assertNotIn("params", [call[1] for call in calls])


if __name__ == "__main__":
    unittest.main()
