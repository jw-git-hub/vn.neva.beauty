import unittest

from bs4 import BeautifulSoup

import build
import long_words

SOFT = long_words.SOFT_HYPHEN
LONG_WORD = "высококонцентрированная"


class SoftHyphenateTest(unittest.TestCase):
    def test_long_word_gets_breaks_at_least_8_letters_from_edges(self):
        self.assertEqual(f"Сыворотка высококон{SOFT}цен{SOFT}три{SOFT}рованная",
                         long_words.soft_hyphenate(f"Сыворотка {LONG_WORD}", "ru"))

    def test_word_shorter_than_20_letters_is_kept(self):
        for word in ("высококачественного", "Карбокситерапия"):
            with self.subTest(word=word):
                self.assertEqual(word, long_words.soft_hyphenate(word, "ru"))

    def test_language_without_dictionary_is_kept(self):
        self.assertEqual(LONG_WORD, long_words.soft_hyphenate(LONG_WORD, "zz"))

    def test_punctuation_and_numbers_are_kept(self):
        text = long_words.soft_hyphenate(f"{LONG_WORD}, 30 мин", "ru")
        self.assertTrue(text.endswith(", 30 мин"))
        self.assertEqual(f"{LONG_WORD}, 30 мин", text.replace(SOFT, ""))


class SoftHyphensInBuiltSiteTest(unittest.TestCase):
    """Мягкие переносы — только в названиях прайса (не в подписях под ними) и только
    в словах от 20 букв: исключение владельца не расползается по сайту."""

    def soft_hyphen_hosts(self):
        for path in sorted(build.OUT.rglob("*.html")):
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            for node in soup.find_all(string=lambda text: SOFT in text):
                yield path, node

    def test_only_long_words_of_price_names_have_soft_hyphens(self):
        hosts = list(self.soft_hyphen_hosts())
        self.assertTrue(hosts, "в собранном прайсе нет ни одного мягкого переноса")
        for path, node in hosts:
            with self.subTest(page=str(path.relative_to(build.OUT)), text=node.strip()):
                self.assertIn("pricelist__name", node.parent.get("class", []))
                for chunk in (chunk for chunk in node.split() if SOFT in chunk):
                    word = max(long_words.WORD_RE.findall(chunk.replace(SOFT, "")), key=len)
                    self.assertGreaterEqual(len(word), long_words.MIN_WORD_LETTERS)


if __name__ == "__main__":
    unittest.main()
