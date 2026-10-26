"""Одобренные отступления автотеста пар строк: data/locales/<код>/pair_exceptions.yml.

Исключение снимает одну проверку одной строки (у терминов — один термин, у плейсхолдеров — один плейсхолдер). Оно обязано
иметь причину, называть известную проверку и настоящую строку, и обязано что-то снимать:
устаревшее исключение (строку исправили) — тоже проблема, иначе файл зарастёт мусором.
"""
from dataclasses import dataclass

import yaml

from locales import LOCALES_DIR

EXCEPTIONS_FILE = "pair_exceptions.yml"
TERMS_CHECK = "terms"
PLACEHOLDERS_CHECK = "placeholders"
# Проверки, у которых исключение называет, что именно оно снимает: поле записи и подсказка к нему.
DETAIL_FIELDS = {TERMS_CHECK: ("term", "слово required из глоссария"),
                 PLACEHOLDERS_CHECK: ("placeholder", "плейсхолдер вида {имя}")}
GROUP_PREFIX = "pair_exceptions"


@dataclass(frozen=True)
class Finding:
    """Находка проверки пары: строка, проверка, текст; у терминов — слово required,
    у плейсхолдеров — сам плейсхолдер (detail)."""
    path: str
    check: str
    message: str
    detail: str = None

    @property
    def key(self):
        return (self.path, self.check, self.detail)


def load_exceptions(code, directory=LOCALES_DIR):
    path = directory / code / EXCEPTIONS_FILE
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("exceptions") or []


def _label(entry):
    entry = entry if isinstance(entry, dict) else {}
    return f"{GROUP_PREFIX} «{entry.get('path')}» {entry.get('check')}"


def _entry_problems(entry, known_checks):
    if not isinstance(entry, dict):
        return ["исключение должно быть словарём {path, check, reason}"]
    problems = []
    if not str(entry.get("reason") or "").strip():
        problems.append("нет причины (reason)")
    if entry.get("check") not in known_checks:
        problems.append(f"неизвестная проверка, ожидалась одна из {list(known_checks)}")
    elif entry["check"] in DETAIL_FIELDS and not entry.get(DETAIL_FIELDS[entry["check"]][0]):
        field, hint = DETAIL_FIELDS[entry["check"]]
        problems.append(f"для проверки {entry['check']} нужно поле {field} — {hint}")
    return problems


def _key_of(entry):
    check = entry["check"]
    field = DETAIL_FIELDS.get(check, (None,))[0]
    return (entry.get("path"), check, entry.get(field) if field else None)


def _valid_entries(exceptions, known_checks):
    """([(ключ, исключение)], проблемы) — негодные исключения ничего не снимают."""
    valid, problems = [], []
    for entry in exceptions:
        found = _entry_problems(entry, known_checks)
        problems += [f"{_label(entry)}: {problem}" for problem in found]
        if not found:
            valid.append((_key_of(entry), entry))
    return valid, problems


def apply_exceptions(findings, exceptions, known_checks, known_paths, translated_paths):
    """(находки без снятых, проблемы самих исключений). Строка без перевода уже
    названа другой проверкой, поэтому её исключение не считается устаревшим."""
    valid, problems = _valid_entries(exceptions, known_checks)
    keys = {key for key, _ in valid}
    used = {finding.key for finding in findings} & keys
    for key, entry in valid:
        if key[0] not in known_paths:
            problems.append(f"{_label(entry)}: такой строки среди пар нет")
        elif key not in used and key[0] in translated_paths:
            problems.append(f"{_label(entry)}: исключение ничего не снимает — "
                            f"устарело, удалите его")
    return [finding for finding in findings if finding.key not in keys], problems
