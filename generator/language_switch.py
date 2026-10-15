"""Ссылки на ту же страницу на каждом языке сайта: пилюля в шапке, строка в меню
и подвале. Подписи берутся из языка цели: «EN — English version» по-английски,
«RU — русская версия» по-русски — так гость узнаёт свой язык, не зная чужого."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageLink:
    code: str
    html_lang: str
    short: str
    name: str
    label: str
    href: str
    is_current: bool


def language_links(routes, current, page_id):
    return [LanguageLink(code=locale.code, html_lang=locale.html_lang,
                         short=locale.t("language.short"), name=locale.t("language.name"),
                         label=locale.t("language.switch_label"),
                         href=routes.href(locale, page_id),
                         is_current=locale.code == current.code)
            for locale in routes.locales]
