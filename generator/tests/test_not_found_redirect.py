import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.test_build import build_real_pages

NODE = shutil.which("node")
HARNESS = Path(__file__).resolve().parent / "js" / "not_found_redirect.js"
SCRIPT_RE = re.compile(r"<script>\s*(\(function \(R\)[\s\S]*?)</script>")
ENGLISH_NOT_FOUND = "/en/404.html"


@unittest.skipUnless(NODE, "нужен node: логика строчного скрипта проверяется в нём")
class NotFoundRedirectScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.russian_pages = build_real_pages("ru")
        cls.english_pages = build_real_pages("en")
        cls.script = SCRIPT_RE.search(cls.russian_pages["404.html"]).group(1)

    def redirects(self, pathnames):
        payload = json.dumps({"script": self.script, "pathnames": pathnames})
        output = subprocess.run([NODE, str(HARNESS)], input=payload, capture_output=True,
                                text=True, check=True).stdout
        return json.loads(output)

    def test_unknown_english_address_goes_to_english_page(self):
        self.assertEqual(self.redirects(["/en/no-such-page/", "/en/laser-hair-removal/x"]),
                         [ENGLISH_NOT_FOUND, ENGLISH_NOT_FOUND])

    def test_english_page_itself_stays(self):
        self.assertEqual(self.redirects([ENGLISH_NOT_FOUND]), [None])

    def test_russian_and_lookalike_addresses_stay(self):
        self.assertEqual(self.redirects(["/no-such-page/", "/english/"]), [None, None])

    def test_script_only_on_root_not_found(self):
        self.assertNotIn("location.replace", self.english_pages["en/404.html"])
        for pages in (self.russian_pages, self.english_pages):
            for path, html in pages.items():
                if path != "404.html":
                    self.assertIsNone(SCRIPT_RE.search(html), path)

    def test_script_has_no_cyrillic(self):
        self.assertIsNone(re.search("[а-яА-ЯёЁ]", self.script))
