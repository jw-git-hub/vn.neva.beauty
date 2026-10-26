"""Неразрывные пробелы в видимом тексте страницы.

Короткое слово в конце строки («в ⏎ самом сердце»), тире в начале строки и число,
оторванное от «đ», — мелкие огрехи, которые на узком экране встречаются в каждом
абзаце. Правила языка (typography_rules.py) применяются к готовому HTML, а не к
данным: тексты в content.yml остаются чистыми, а пары перевода сверяются по ним.

Трогается только видимый текст внутри <body>. Теги с атрибутами, <head> (title,
meta, JSON-LD), скрипты, стили и код остаются как были.
"""
import re

from typography_rules import RULES_BY_LANGUAGE

BODY_OPEN_TAG = re.compile(r"<body\b[^>]*>")
# Тег целиком, значения атрибутов в кавычках могут содержать «>».
TAG_OR_COMMENT = re.compile(r"(<!--.*?-->|<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>)", re.DOTALL)
TAG_NAME = re.compile(r"<(/?)([a-zA-Z][\w:-]*)")
UNTOUCHED_TAGS = frozenset({"script", "style", "pre", "code", "textarea", "svg", "title"})
SELF_CLOSING_END = "/>"


def _language_code(html_lang):
    return html_lang.split("-")[0].lower()


def _apply_rules(text, rules):
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def _untouched_depth_change(tag):
    """+1 при открытии тега, чей текст не трогаем, −1 при закрытии, иначе 0."""
    match = TAG_NAME.match(tag)
    if not match or match.group(2).lower() not in UNTOUCHED_TAGS or tag.endswith(SELF_CLOSING_END):
        return 0
    return -1 if match.group(1) else 1


def _bind_body_text(body, rules):
    pieces = TAG_OR_COMMENT.split(body)
    depth = 0
    for index, piece in enumerate(pieces):
        is_tag = index % 2 == 1
        if is_tag:
            depth += _untouched_depth_change(piece)
        elif depth == 0:
            pieces[index] = _apply_rules(piece, rules)
    return "".join(pieces)


def bind_short_words(html, html_lang):
    """HTML страницы с неразрывными пробелами по правилам её языка.
    Язык без правил — страница без изменений."""
    rules = RULES_BY_LANGUAGE.get(_language_code(html_lang))
    opening = BODY_OPEN_TAG.search(html)
    if not rules or not opening:
        return html
    return html[:opening.end()] + _bind_body_text(html[opening.end():], rules)
