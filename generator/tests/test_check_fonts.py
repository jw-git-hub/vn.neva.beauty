import tempfile
import unittest
from pathlib import Path

import check_fonts


class VisibleCharsTest(unittest.TestCase):
    def chars_of(self, body):
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
            return check_fonts.visible_chars(page)

    def test_no_break_space_must_be_in_fonts(self):
        self.assertIn(" ", self.chars_of("<p>в самом</p>"))

    def test_ordinary_whitespace_and_script_are_ignored(self):
        self.assertEqual(self.chars_of("<p>a b\n</p><script>ж</script>"), {"a", "b"})

    def test_site_fonts_cover_no_break_space(self):
        self.assertIn(" ", check_fonts.font_charset())


if __name__ == "__main__":
    unittest.main()
