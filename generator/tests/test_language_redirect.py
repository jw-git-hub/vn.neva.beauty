import itertools
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import build
import language_redirect
import taxonomy
from locales import load_locale
from routes import Routes
from tests.test_build import build_real_pages

NODE = shutil.which("node")
HARNESS = Path(__file__).resolve().parent / "js" / "choose_language.js"
SCRIPT_RE = re.compile(r"<script>\s*(\(function \(C\)[\s\S]*?)</script>")
RU_PAGE, EN_PAGE = "/lpg-massazh/", "/en/lpg-massage/"
BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
ROBOTS = ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
          "Mozilla/5.0 (Linux; Android 11) Chrome/120.0 Mobile Safari/537.36 Chrome-Lighthouse",
          "TelegramBot (like TwitterBot)", "facebookexternalhit/1.1",
          "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.1)")
RUSSIAN_GROUP = ("ru", "uk", "be", "kk")


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.site, content, _ = build.load()
        self.ru, self.en = load_locale("ru"), load_locale("en")
        self.routes = Routes([self.ru, self.en], taxonomy.page_ids(content),
                             self.site["base_url"], "en")

    def test_pairs_groups_and_fallback(self):
        config = language_redirect.config(self.site, self.routes, self.ru, "lpg-massazh")
        self.assertEqual(config["pairs"], {"ru": RU_PAGE, "en": EN_PAGE})
        self.assertEqual(config["groups"], [["ru", list(RUSSIAN_GROUP)]])
        self.assertEqual((config["current"], config["fallback"]), ("ru", "en"))

    def test_not_found_page_has_no_redirect(self):
        self.assertIsNone(language_redirect.config(self.site, self.routes, self.ru, "404"))

    def test_switch_off_removes_redirect(self):
        site = dict(self.site, auto_language=False)
        self.assertIsNone(language_redirect.config(site, self.routes, self.ru, "home"))

    def test_single_language_has_no_redirect(self):
        _, content, _ = build.load()
        routes = Routes([self.ru], taxonomy.page_ids(content), self.site["base_url"], "ru")
        self.assertIsNone(language_redirect.config(self.site, routes, self.ru, "home"))

    def test_unknown_fallback_is_error(self):
        with self.assertRaises(ValueError):
            language_redirect.config(dict(self.site, fallback_locale="de"), self.routes,
                                     self.ru, "home")


def expected_target(case, current):
    """Правило спеки, раздел 14: робот или вход изнутри — без перехода; иначе сохранённый
    выбор, иначе группа языков браузера, иначе язык для остальных."""
    internal = case["referrer"].startswith("https://vn.neva.beauty/")
    if case["userAgent"] != BROWSER or internal:
        return None
    saved = None if case.get("storageFails") else case["saved"]
    russian = any(tag.split("-")[0] in RUSSIAN_GROUP for tag in case["languages"])
    target = saved or ("ru" if russian else "en")
    if target == current:
        return None
    return {"ru": RU_PAGE, "en": EN_PAGE}[target] + case.get("search", "") + case.get("hash", "")


@unittest.skipUnless(NODE, "нужен node: логика строчного скрипта проверяется в нём")
class ChooseLanguageScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scripts = {"ru": SCRIPT_RE.search(build_real_pages("ru")["lpg-massazh/index.html"]).group(1),
                       "en": SCRIPT_RE.search(build_real_pages("en")["en/lpg-massage/index.html"]).group(1)}

    def run_cases(self, current, cases):
        payload = json.dumps({"script": self.scripts[current], "cases": cases})
        output = subprocess.run([NODE, str(HARNESS)], input=payload, capture_output=True,
                                text=True, check=True).stdout
        return json.loads(output)

    def test_case_table_from_spec(self):
        languages = [["ru"], ["uk"], ["be"], ["kk-KZ"], ["en-US"], ["vi"], ["en", "ru"]]
        cases = [{"languages": langs, "saved": saved, "referrer": referrer, "userAgent": agent}
                 for langs, saved, referrer, agent in itertools.product(
                     languages, [None, "ru", "en"],
                     ["", "https://www.google.com/", "https://vn.neva.beauty/"],
                     (BROWSER,) + ROBOTS)]
        for current in ("ru", "en"):
            self.assertEqual(self.run_cases(current, cases),
                             [expected_target(case, current) for case in cases], current)

    def test_saved_choice_wins(self):
        case = {"languages": ["en-US"], "saved": "ru", "referrer": "https://www.google.com/",
                "userAgent": BROWSER}
        self.assertEqual(self.run_cases("en", [case]), [RU_PAGE])

    def test_query_and_hash_survive(self):
        case = {"languages": ["en-US"], "saved": None, "referrer": "", "userAgent": BROWSER,
                "search": "?utm_source=fb&fbclid=1", "hash": "#prices"}
        self.assertEqual(self.run_cases("ru", [case]), [EN_PAGE + "?utm_source=fb&fbclid=1#prices"])

    def test_uses_replace(self):
        case = {"languages": ["vi"], "saved": None, "referrer": "", "userAgent": BROWSER}
        self.assertNotEqual(self.run_cases("ru", [case]), ["ASSIGNED"])
        self.assertEqual(self.run_cases("ru", [case]), [EN_PAGE])

    def test_storage_failure_is_harmless(self):
        case = {"languages": ["ru"], "saved": "en", "referrer": "", "userAgent": BROWSER,
                "storageFails": True}
        self.assertEqual(self.run_cases("en", [case]), [RU_PAGE])


METRIKA_RE = re.compile(r"<script>\s*(\(function \(w, d\)[\s\S]*?)</script>")
METRIKA_HARNESS = Path(__file__).resolve().parent / "js" / "metrika_source.js"


@unittest.skipUnless(NODE, "нужен node: код Метрики проверяется в нём")
class MetrikaSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = METRIKA_RE.search(build_real_pages("en")["en/index.html"]).group(1)

    def run_metrika(self, source):
        payload = json.dumps({"script": self.script, "source": source,
                              "key": language_redirect.SOURCE_KEY})
        return json.loads(subprocess.run([NODE, str(METRIKA_HARNESS)], input=payload,
                                         capture_output=True, text=True, check=True).stdout)

    def test_redirect_source_reaches_metrika(self):
        result = self.run_metrika("https://www.google.com/")
        init = next(call for call in result["calls"] if call[1] == "init")
        hit = next(call for call in result["calls"] if call[1] == "hit")
        self.assertTrue(init[2]["defer"])
        self.assertEqual(hit[2:], ["https://vn.neva.beauty/en/",
                                   {"referer": "https://www.google.com/", "title": "Page"}])
        self.assertIsNone(result["left"])

    def test_direct_entry_after_redirect_keeps_empty_source(self):
        hit = next(call for call in self.run_metrika("")["calls"] if call[1] == "hit")
        self.assertEqual(hit[3]["referer"], "")

    def test_normal_visit_is_unchanged(self):
        result = self.run_metrika(None)
        init = next(call for call in result["calls"] if call[1] == "init")
        self.assertFalse(init[2].get("defer"))
        self.assertFalse(any(call[1] == "hit" for call in result["calls"]))
