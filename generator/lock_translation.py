"""Ставит замок перевода языка: python generator/lock_translation.py <код>.

Запускается после одобрения перевода и после каждой правки русского текста вместе
с переводом. Незаконченный перевод не запирается: сначала translation_status.py
должен показать ноль проблем."""
import sys

import build
import translation
import translation_lock
from locales import load_locale, load_privacy


def main(code):
    site, content, prices = build.load()
    main_locale = build.load_locales(site)[0]
    _, problems = translation.translation_problems(site, content, prices, load_locale(code),
                                                   main_locale, check_lock=False)
    if problems:
        sys.exit(f"Перевод {code} не готов, проблем: {len(problems)} — замок не ставлю.\n"
                 + "\n".join(problems))
    fingerprints = translation_lock.source_fingerprints(site, content, main_locale,
                                                        load_privacy(main_locale.code))
    translation_lock.write_lock(code, fingerprints)
    print(f"Замок {code}: строк {len(fingerprints)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Использование: python generator/lock_translation.py <код языка>")
    main(sys.argv[1])
