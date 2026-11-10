"""Проблема перевода: строка сообщения, к которой приложена группа.

Группа задаётся там, где проблема найдена (стадия проверки), а не угадывается по тексту
сообщения. Problem — подкласс str: сборка, замок и тесты по-прежнему видят обычный текст,
а translation_status.py группирует по полю group.
"""
UI, SITE, PRICES, PRIVACY, LOCK, PAIR_EXCEPTIONS, CONTENT = (
    "ui", "site", "prices", "privacy", "замок", "pair_exceptions", "content")


class Problem(str):
    def __new__(cls, text, group):
        problem = super().__new__(cls, text)
        problem.group = group
        return problem


def tag(group, texts):
    """Список проблем одной группы из списка сообщений."""
    return [Problem(text, group) for text in texts]
