import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_relocking_lists_changed_added_and_removed_paths(self):
        current = dict(self.current, **{"content.home.new": lock.fingerprint("Новое"),
                                        "privacy": lock.fingerprint("Другая политика")})
        del current["ui.nav.home"]
        self.assertEqual(lock.lock_changes(self.current, current),
                         ["изменён privacy", "добавлен content.home.new", "удалён ui.nav.home"])

    def test_relocking_unchanged_source_lists_nothing(self):
        self.assertEqual(lock.lock_changes(self.current, dict(self.current)), [])

    def test_first_lock_lists_nothing(self):
        self.assertEqual(lock.lock_changes(None, self.current), [])

    def test_write_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            lock.write_lock("en", self.current, Path(directory))
            self.assertEqual(lock.load_lock("en", Path(directory)), self.current)
            self.assertEqual(json.loads((Path(directory) / "en" / lock.LOCK_FILE).read_text()),
                             dict(sorted(self.current.items())))

    def test_missing_lock_is_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(lock.load_lock("en", Path(directory)))


class LockTranslationMainTest(unittest.TestCase):
    def test_relocking_prints_changed_paths_before_writing(self):
        import contextlib
        import io

        import lock_translation
        previous = {"content.home.seo_title": "0" * 16, "privacy": "1" * 16}
        with mock.patch("lock_translation.translation.translation_problems",
                        return_value=(None, [])), \
                mock.patch("lock_translation.translation_lock.load_lock", return_value=previous), \
                mock.patch("lock_translation.translation_lock.write_lock") as write, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            lock_translation.main("en")
        self.assertIn("изменён content.home.seo_title", output.getvalue())
        self.assertIn("изменён privacy", output.getvalue())
        write.assert_called_once()
