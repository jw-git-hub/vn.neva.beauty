"""Ссылки связи: адрес мессенджера с текстом обращения и метки для статистики.

Администратор видит в чате, с какой страницы и на каком языке пишет гость: текст
несёт название страницы на языке страницы. Владелец видит то же в Метрике: каждая
ссылка помечена каналом (data-contact) и местом кнопки (data-place), а обработчик
в partials/metrika.html.j2 отправляет клик событием contact. Все ссылки связи
собираются здесь — check_contacts.py ловит ссылку, собранную мимо модуля.
"""
import urllib.parse

from markupsafe import Markup, escape

CHANNELS = ("whatsapp", "telegram", "instagram")
# Хосты, по которым ссылка узнаётся как ссылка канала: у каждого канала бывает несколько
# написаний адреса (instagram.com и www.instagram.com, wa.me и api.whatsapp.com), и ссылка
# с любым из них должна пройти через этот модуль, а не лежать в шаблоне руками.
CHANNEL_HOSTS = {"whatsapp": ("wa.me", "api.whatsapp.com"),
                 "telegram": ("t.me", "telegram.me"),
                 "instagram": ("instagram.com",)}
WWW_PREFIX = "www."
# booking — блок записи внизу страниц, booking-page — кнопки первого экрана страницы записи.
PLACES = ("header", "hero", "strip", "booking", "booking-page", "drawer", "footer", "faq")
# Instagram не умеет подставлять текст в директ — у него адрес всегда голый.
ALWAYS_PREFILLED = ("whatsapp",)
FAQ_PLACE = "faq"
TELEGRAM_PREFILL_KEY = "telegram_prefill"
CHANNEL_URL_KEY = "{channel}_url"  # ключ адреса канала в contacts site.yml
PAGE_TITLE_KEY = "contact_title"  # название страницы в её данных для текста обращения
PREFILL_PARAM = "text"  # параметр адреса, в котором мессенджер получает текст обращения


def channel_url_key(channel):
    return CHANNEL_URL_KEY.format(channel=channel)


def channel_of_url(url):
    """Канал, на чей хост ведёт адрес (с www или без), или None."""
    host = (urllib.parse.urlsplit(url.strip()).hostname or "").removeprefix(WWW_PREFIX)
    return next((channel for channel, hosts in CHANNEL_HOSTS.items() if host in hosts), None)


def page_contact_message(locale, page):
    """Текст обращения со страницы: её данные (page) несут название под ключом
    PAGE_TITLE_KEY. Единственный путь названия и в шаблоны, и в ответы FAQ."""
    return contact_message(locale, (page or {}).get(PAGE_TITLE_KEY))


def contact_message(locale, page_title=None):
    """Текст обращения: с названием страницы услуги или раздела, иначе общий."""
    if page_title:
        return locale.t("contact.text_page", title=page_title)
    return locale.t("contact.text_generic")


def prefill_channels(contacts):
    """Каналы, в адрес которых подставляется текст. Telegram — по флагу в site.yml:
    если ссылка с текстом не открывается на каком-то устройстве, флаг выключают.
    Флаг обязателен и только true/false: опечатка в имени или строка "false" молча
    убрали бы текст из всех ссылок Telegram."""
    flag = contacts.get(TELEGRAM_PREFILL_KEY)
    if not isinstance(flag, bool):
        raise ValueError(f"В site.yml contacts.{TELEGRAM_PREFILL_KEY} должен быть true "
                         f"или false, а не {flag!r}")
    if flag:
        return ALWAYS_PREFILLED + ("telegram",)
    return ALWAYS_PREFILLED


def contact_url(contacts, channel, message):
    base = contacts[channel_url_key(channel)]
    if channel not in prefill_channels(contacts):
        return base
    return f"{base}?{PREFILL_PARAM}={urllib.parse.quote(message)}"


def _check(channel, place):
    if channel not in CHANNELS:
        raise ValueError(f"Неизвестный канал связи {channel!r}, ожидался один из {CHANNELS}")
    if place not in PLACES:
        raise ValueError(f"Неизвестное место кнопки {place!r}, ожидалось одно из {PLACES}")


def _tracking_attrs(channel, place):
    return f'data-contact="{channel}" data-place="{place}"'


def link_attrs(contacts, channel, place, message):
    """Атрибуты ссылки связи для шаблона: адрес, новая вкладка, метки канала и места."""
    _check(channel, place)
    url = escape(contact_url(contacts, channel, message))
    return Markup(f'href="{url}" target="_blank" rel="noopener" '
                  f'{_tracking_attrs(channel, place)}')


def fill_contact_links(html, contacts, message):
    """Ссылки на мессенджеры в ответах FAQ: href="{whatsapp}" из content.yml получает
    адрес с текстом и метки. Плейсхолдер вне href не трогается."""
    for channel in CHANNELS:
        url = escape(contact_url(contacts, channel, message))
        html = html.replace(f'href="{{{channel}}}"',
                            f'href="{url}" {_tracking_attrs(channel, FAQ_PLACE)}')
    return html
