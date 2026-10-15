import json
import tempfile
import unittest
from pathlib import Path

import translation_lock as lock
from locales import load_locale

SITE = {"tagline": "Центр красоты", "location": "Дананг", "hours": "По записи",
        "locations": [{"city": "Самуи", "country": "Таиланд", "url": "https://th"}]}
CONTENT = {"home": {"seo_title": "Главная", "faq": [{"q": "Вопрос?", "a": "Ответ."}]}}


class FingerprintsTest(unittest.TestCase):
    def setUp(self):
        self.main = load_locale("ru")
        self.current = lock.source_fingerprints(SITE, CONTENT, self.main, "<p>Политика</p>")

    def test_paths_cover_content_ui_and_privacy(self):
        self.assertIn("content.home.faq[0].q", self.current)
        self.assertIn("ui.nav.home", self.current)
        self.assertIn("privacy", self.current)
        self.assertIn("site.tagline", self.current)
        self.assertIn("site.locations[0].city", self.current)

    def test_same_source_has_no_problems(self):
        self.assertEqual(lock.lock_problems(self.current, dict(self.current)), [])

    def test_changed_source_is_named(self):
        changed = dict(self.current, **{"content.home.faq[0].q": lock.fingerprint("Другой?")})
        self.assertEqual(lock.lock_problems(self.current, changed),
                         ["замок content.home.faq[0].q: русский текст изменился — "
                          "обновите перевод и поставьте замок заново"])

    def test_new_and_removed_strings_are_named(self):
        current = dict(self.current, **{"content.home.new": lock.fingerprint("Новое")})
        del current["privacy"]
        self.assertEqual(lock.lock_problems(self.current, current),
                         ["замок content.home.new: строки нет в замке — переведите и поставьте замок заново",
                          "замок privacy: в мастере строки больше нет"])

    def test_write_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            lock.write_lock("en", self.current, Path(directory))
            self.assertEqual(lock.load_lock("en", Path(directory)), self.current)
            self.assertEqual(json.loads((Path(directory) / "en" / lock.LOCK_FILE).read_text()),
                             dict(sorted(self.current.items())))

    def test_missing_lock_is_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(lock.load_lock("en", Path(directory)))
