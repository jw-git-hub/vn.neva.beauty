"""Замок перевода: отпечатки русских строк, с которых сделан перевод.

После одобрения перевода lock_translation.py записывает data/locales/<код>/content.lock.json.
Дальше сборка сверяет отпечатки с текущим мастером и падает, называя путь строки: русский
текст поправили — перевод нужно обновить. Порядок правки: русский текст → перевод →
python generator/lock_translation.py <код> → один коммит. Цены в замок не входят: в
переводе их нет, а ключи прайса — сами русские строки.
"""
import hashlib
import json

import overlay
from locales import LOCALES_DIR

LOCK_FILE = "content.lock.json"
FINGERPRINT_LENGTH = 16


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def source_fingerprints(content, main_locale, privacy_text):
    """Отпечатки всех русских строк, которые переводятся: тексты, интерфейс, политика."""
    strings = {f"content.{path}": text for path, text in overlay.source_strings(content).items()}
    strings.update({f"ui.{key}": text for key, text in main_locale.ui.items()})
    strings["privacy"] = str(privacy_text)
    return {path: fingerprint(text) for path, text in strings.items()}


def lock_problems(locked, current):
    problems = []
    for path in sorted(set(locked) | set(current)):
        if path not in current:
            problems.append(f"замок {path}: в мастере строки больше нет")
        elif path not in locked:
            problems.append(f"замок {path}: строки нет в замке — переведите и поставьте замок заново")
        elif locked[path] != current[path]:
            problems.append(f"замок {path}: русский текст изменился — "
                            f"обновите перевод и поставьте замок заново")
    return problems


def load_lock(code, directory=LOCALES_DIR):
    path = directory / code / LOCK_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_lock(code, fingerprints, directory=LOCALES_DIR):
    path = directory / code / LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(fingerprints.items())), ensure_ascii=False, indent=2)
                    + "\n", encoding="utf-8")
