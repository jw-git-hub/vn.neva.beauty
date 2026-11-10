"""Строчные скрипты страницы: источник визита при переадресации (привязка к цели и сроку),
запоминание ручного выбора языка без nav.js, устойчивость выбора языка к странному хранилищу
и отсутствию URL. Скрипты берутся из настоящей сборки и гоняются в Node."""
import json
import re
import subprocess
import unittest
from pathlib import Path

import language_redirect
from tests.test_build import build_real_pages
from tests.test_language_redirect import BROWSER, EN_PAGE, NODE, RU_PAGE, SCRIPT_RE

HARNESS = Path(__file__).resolve().parent / "js" / "session_handoff.js"
GUARD_RE = re.compile(r"<script>\s*(\(function \(SOURCE_KEY[\s\S]*?)</script>")
CHOICE_RE = re.compile(r"<script>\s*(\(function \(STORAGE_KEY[\s\S]*?)</script>")
SOURCE, TARGET, LANG = (language_redirect.SOURCE_KEY, language_redirect.SOURCE_TARGET_KEY,
                        language_redirect.STORAGE_KEY)
GOOGLE = "https://www.google.com/"
START = 1_000_000
TTL = language_redirect.SOURCE_TTL_MS


def handoff(path, at=START):
    return json.dumps({"path": path, "at": at})


def run(steps, session=None, local=None):
    payload = json.dumps({"steps": steps, "session": session or {}, "local": local or {}})
    output = subprocess.run([NODE, str(HARNESS)], input=payload, capture_output=True,
                            text=True, check=True).stdout
    return json.loads(output)


class PageScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ru_html = build_real_pages("ru")["lpg-massazh/index.html"]
        cls.en_html = build_real_pages("en")["en/lpg-massage/index.html"]
        cls.redirect = SCRIPT_RE.search(cls.ru_html).group(1)
        cls.guard = GUARD_RE.search(cls.ru_html).group(1)
        cls.choice = CHOICE_RE.search(cls.ru_html).group(1)


@unittest.skipUnless(NODE, "нужен node: скрипты проверяются в нём")
class SourceHandoffTest(PageScripts):
    def guard_step(self, pathname=RU_PAGE, now=START + 1000):
        return {"script": self.guard, "pathname": pathname, "now": now}

    def test_source_is_accepted_on_the_target_page(self):
        result = run([self.guard_step()], {SOURCE: GOOGLE, TARGET: handoff(RU_PAGE)})
        self.assertEqual(result["session"], {SOURCE: GOOGLE})

    def test_source_is_dropped_on_another_page(self):
        result = run([self.guard_step("/en/")], {SOURCE: GOOGLE, TARGET: handoff(RU_PAGE)})
        self.assertEqual(result["session"], {})

    def test_stale_source_is_dropped(self):
        result = run([self.guard_step(now=START + TTL)], {SOURCE: GOOGLE, TARGET: handoff(RU_PAGE)})
        self.assertEqual(result["session"], {})

    def test_source_without_target_is_dropped(self):
        self.assertEqual(run([self.guard_step()], {SOURCE: GOOGLE})["session"], {})

    def test_broken_target_record_drops_source(self):
        result = run([self.guard_step()], {SOURCE: GOOGLE, TARGET: "{not json"})
        self.assertEqual(result["session"], {})

    def test_blocked_storage_does_not_throw(self):
        run([dict(self.guard_step(), storageThrows=True)])

    def test_language_redirect_hands_source_to_target_page_only(self):
        redirect = {"script": self.redirect, "pathname": RU_PAGE, "now": START,
                    "referrer": GOOGLE, "languages": ["en-US"]}
        result = run([redirect])
        self.assertEqual(result["steps"][0]["replacedWith"], EN_PAGE)
        self.assertEqual(result["session"][SOURCE], GOOGLE)
        session = result["session"]
        arrived = run([self.guard_step(EN_PAGE)], session)
        self.assertEqual(arrived["session"], {SOURCE: GOOGLE})
        elsewhere = run([self.guard_step("/en/other/")], session)
        self.assertEqual(elsewhere["session"], {})

    def test_every_script_takes_keys_from_the_single_source(self):
        for key in (SOURCE, TARGET):
            self.assertIn(json.dumps(key), self.guard)
        self.assertIn(json.dumps(LANG), self.choice)


@unittest.skipUnless(NODE, "нужен node: скрипты проверяются в нём")
class LanguageChoiceTest(PageScripts):
    def test_click_is_remembered_without_nav_js(self):
        step = {"script": self.choice, "pathname": RU_PAGE, "now": START, "click": {"lang": "en"}}
        self.assertEqual(run([step])["local"], {LANG: "en"})

    def test_blocked_storage_does_not_throw(self):
        step = {"script": self.choice, "pathname": RU_PAGE, "now": START,
                "click": {"lang": "en"}, "storageThrows": True}
        run([step])

    def test_key_name_is_not_repeated_in_nav_js(self):
        nav = (Path(__file__).resolve().parents[2] / "vn.neva.beauty" / "assets" / "js" / "nav.js")
        self.assertNotIn(LANG, nav.read_text(encoding="utf-8"))

    def test_choice_script_is_on_every_page(self):
        for html in (self.ru_html, self.en_html, build_real_pages("ru")["404.html"]):
            self.assertIsNotNone(CHOICE_RE.search(html))


@unittest.skipUnless(NODE, "нужен node: скрипты проверяются в нём")
class ChooseLanguageRobustnessTest(PageScripts):
    def redirect_step(self, **extra):
        return dict({"script": self.redirect, "pathname": RU_PAGE, "now": START,
                     "referrer": "", "userAgent": BROWSER, "languages": ["en-US"]}, **extra)

    def test_saved_value_from_prototype_is_not_a_language(self):
        for saved in ("constructor", "toString", "__proto__", "hasOwnProperty"):
            result = run([self.redirect_step()], local={LANG: saved})
            self.assertEqual(result["steps"][0]["replacedWith"], EN_PAGE, saved)

    def test_saved_language_still_wins(self):
        result = run([self.redirect_step()], local={LANG: "ru"})
        self.assertIsNone(result["steps"][0]["replacedWith"])

    def test_direct_visit_without_url_still_redirects(self):
        result = run([self.redirect_step(withoutUrl=True)])
        self.assertEqual(result["steps"][0]["replacedWith"], EN_PAGE)

    def test_without_url_script_works_and_does_not_redirect(self):
        for referrer in (GOOGLE, "https://vn.neva.beauty/en/"):
            result = run([self.redirect_step(withoutUrl=True, referrer=referrer)])
            self.assertIsNone(result["steps"][0]["replacedWith"], referrer)
