"""Проверка ссылок связи во всех собранных страницах. Падает (exit 1) при нарушении.

Каждая ссылка на WhatsApp, Telegram и Instagram должна быть собрана через contacts.py:
с метками канала и места (по ним Метрика считает обращения) и с текстом страницы в
адресе (по нему администратор видит, откуда пишут). Ссылка, написанная в шаблоне
руками, выглядит на странице так же, но выпадает из статистики, а в чат приходит
без названия услуги — глазом это не заметить.
Запуск: python generator/check_contacts.py"""
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup

import build
import contacts
import taxonomy
from locales import localized_site
from routes import HOME, NOT_FOUND, PRIVACY, Routes

SITE = build.OUT
GENERIC_PAGES = (HOME, PRIVACY, NOT_FOUND)
# Текст политики (data/locales/<код>/privacy.html) даёт контакты оператора для вопросов
# о персональных данных. Это не кнопки записи: текст «Хочу записаться» и метки
# обращений им не нужны, и проверка их пропускает.
LEGAL_TEXT_CLASS = "legal-page"


def channel_of(href, site_contacts):
    """Канал, на адрес которого ведёт ссылка, или None."""
    for channel in contacts.CHANNELS:
        if href.startswith(site_contacts[f"{channel}_url"]):
            return channel
    return None


def squeeze(text):
    """Пробелы схлопнуты, края обрезаны: h1 на странице и название в адресе — один текст,
    даже если в данных неразрывный или двойной пробел."""
    return re.sub(r"\s+", " ", text).strip()


def text_of(href):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("text", [None])[0]


def text_error(href, channel, site_contacts, expected_message):
    text = text_of(href)
    if channel not in contacts.prefill_channels(site_contacts):
        return f"у {channel} не должно быть текста, а он есть: {text!r}" if text else None
    if text is None or squeeze(text) != squeeze(expected_message):
        return f"текст {channel}: {text!r}, ожидался {expected_message!r}"
    return None


def tag_error(link, channel):
    if link.get("data-contact") != channel:
        return f"ссылка на {channel} без метки data-contact=\"{channel}\""
    if link.get("data-place") not in contacts.PLACES:
        return f"место кнопки {link.get('data-place')!r} не из {contacts.PLACES}"
    return None


def checked_links(soup):
    """Ссылки и помеченные элементы страницы, кроме тех, что внутри текста политики."""
    return [tag for tag in soup.find_all(lambda tag: tag.has_attr("href")
                                         or tag.has_attr("data-contact"))
            if not tag.find_parent(class_=LEGAL_TEXT_CLASS)]


def link_errors(soup, name, site_contacts, expected_message):
    """Нарушения в ссылках связи одной страницы."""
    errors = []
    for link in checked_links(soup):
        href = link.get("href", "")
        channel = channel_of(href, site_contacts)
        if channel is None:
            if link.has_attr("data-contact"):
                errors.append(f"{name}: метка data-contact на чужой ссылке {href!r}")
            continue
        problem = (tag_error(link, channel)
                   or text_error(href, channel, site_contacts, expected_message))
        if problem:
            errors.append(f"{name}: {problem}")
    return errors


def h1_text(soup):
    return squeeze(soup.find("h1").get_text())


def expected_message(soup, page_id, locale):
    title = None if page_id in GENERIC_PAGES else h1_text(soup)
    return contacts.contact_message(locale, title)


def locale_pages(site, content, locales):
    """(язык, идентификатор страницы, файл) для каждой собранной страницы."""
    page_ids = taxonomy.page_ids(content)
    routes = Routes(locales, page_ids, site["base_url"], build.load_x_default_locale(site))
    for locale in locales:
        for page_id in page_ids + list(GENERIC_PAGES):
            yield locale, page_id, SITE / routes.out_file(locale, page_id)


def main():
    site, content, _ = build.load()
    locales = build.load_locales(site)
    errors, checked = [], 0
    for locale, page_id, path in locale_pages(site, content, locales):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        site_contacts = localized_site(site, locale)["contacts"]
        errors += link_errors(soup, str(path.relative_to(SITE.parent)), site_contacts,
                              expected_message(soup, page_id, locale))
        checked += 1
    print(f"страниц проверено: {checked}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("CONTACTS OK — ссылки связи помечены и несут текст своей страницы")


if __name__ == "__main__":
    main()
