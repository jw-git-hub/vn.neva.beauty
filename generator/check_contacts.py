"""Проверка ссылок связи во всех собранных страницах. Падает (exit 1) при нарушении.

Каждая ссылка на WhatsApp, Telegram и Instagram должна быть собрана через contacts.py:
с метками канала и места (по ним Метрика считает обращения) и с текстом страницы в
адресе (по нему администратор видит, откуда пишут). Ссылка, написанная в шаблоне
руками, выглядит на странице так же, но выпадает из статистики, а в чат приходит
без названия услуги — глазом это не заметить.
Запуск: python generator/check_contacts.py"""
import sys
import urllib.parse

from bs4 import BeautifulSoup

import build
import check_headings
import contacts
import taxonomy
from locales import localized_site
from routes import BOOKING, FIXED_PAGES, HOME, NOT_FOUND, PRIVACY, Routes

SITE = build.OUT
# Страницы с общим текстом обращения: у них нет названия услуги. Страница записи — тоже:
# на неё приходят из карточки Google Карт и профиля Instagram, не выбрав услугу.
GENERIC_PAGES = (HOME, BOOKING, PRIVACY, NOT_FOUND)
# Текст политики (data/locales/<код>/privacy.html) даёт контакты оператора для вопросов
# о персональных данных. Это не кнопки записи: текст «Хочу записаться» и метки
# обращений им не нужны, и проверка их пропускает.
LEGAL_TEXT_CLASS = "legal-page"


def channel_of(href):
    """Канал, на хост которого ведёт ссылка, или None. Узнаётся по хосту, а не по точному
    адресу из site.yml: любое написание хоста канала обязано пройти через contacts.py."""
    return contacts.channel_of_url(href)


def text_of(href):
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    return query.get(contacts.PREFILL_PARAM, [None])[0]


def text_error(href, channel, site_contacts, expected_message):
    text = text_of(href)
    if channel not in contacts.prefill_channels(site_contacts):
        return f"у {channel} не должно быть текста, а он есть: {text!r}" if text else None
    # Пробелы схлопнуты: название на странице и в адресе — один текст, даже если
    # в данных неразрывный или двойной пробел.
    if text is None or (check_headings.squeeze(text)
                        != check_headings.squeeze(expected_message)):
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
        channel = channel_of(href)
        if channel is None:
            if link.has_attr("data-contact"):
                errors.append(f"{name}: метка data-contact на чужой ссылке {href!r}")
            continue
        problem = (tag_error(link, channel)
                   or text_error(href, channel, site_contacts, expected_message))
        if problem:
            errors.append(f"{name}: {problem}")
    return errors


def page_title(soup, name):
    """Название страницы из хлебных крошек — то же title, что в меню и карточках. Не h1:
    он бывает длиннее («… в Дананге», поле h1 в content.yml), а текст обращения называет
    услугу коротко. Страница услуги или раздела без названия — ошибка с именем файла."""
    title = check_headings.page_title(soup)
    if title is None:
        raise ValueError(f"{name}: на странице нет названия в хлебных крошках, "
                         f"нужно для текста обращения")
    return title


def expected_message(soup, name, page_id, locale):
    title = None if page_id in GENERIC_PAGES else page_title(soup, name)
    return contacts.contact_message(locale, title)


def page_errors(path, page_id, locale, site, name):
    """Нарушения одной собранной страницы; страница без названия даёт одну строку с её именем."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    site_contacts = localized_site(site, locale)["contacts"]
    try:
        message = expected_message(soup, name, page_id, locale)
    except ValueError as error:
        return [str(error)]
    return link_errors(soup, name, site_contacts, message)


def locale_pages(site, content, locales):
    """(язык, идентификатор страницы, файл) для каждой собранной страницы."""
    page_ids = taxonomy.page_ids(content)
    routes = Routes(locales, page_ids, site["base_url"], build.load_x_default_locale(site))
    for locale in locales:
        for page_id in page_ids + list(FIXED_PAGES):
            yield locale, page_id, SITE / routes.out_file(locale, page_id)


def main():
    site, content, _ = build.load()
    locales = build.load_locales(site)
    errors, checked = [], 0
    for locale, page_id, path in locale_pages(site, content, locales):
        errors += page_errors(path, page_id, locale, site, str(path.relative_to(SITE.parent)))
        checked += 1
    print(f"страниц проверено: {checked}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("CONTACTS OK — ссылки связи помечены и несут текст своей страницы")


if __name__ == "__main__":
    main()
