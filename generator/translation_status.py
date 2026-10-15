"""Что ещё не переведено: python generator/translation_status.py <код>.

Печатает тот же список, на котором упадёт сборка языка, по группам. Пустой
перевод даёт полный список — это задание на перевод."""
import sys
from collections import defaultdict

import build
import translation
from locales import load_locale

GROUP_OF_PREFIX = (("ui ", "ui"), ("prices", "prices"), ("privacy", "privacy"), ("замок", "замок"))
CONTENT_GROUP = "content"


def group_of(problem):
    return next((group for prefix, group in GROUP_OF_PREFIX if problem.startswith(prefix)),
                CONTENT_GROUP)


def grouped(problems):
    groups = defaultdict(list)
    for problem in problems:
        groups[group_of(problem)].append(problem)
    return groups


def main(code):
    site, content, prices = build.load()
    _, problems = translation.translation_problems(content, prices, load_locale(code),
                                                   build.load_locales(site)[0])
    for group, items in sorted(grouped(problems).items()):
        print(f"## {group}: {len(items)}")
        print("\n".join(items))
    print(f"Проблем перевода {code}: {len(problems)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Использование: python generator/translation_status.py <код языка>")
    main(sys.argv[1])
