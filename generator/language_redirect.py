"""Конфиг строчного скрипта выбора языка по браузеру (спека, раздел 14).

Сайт статический и до загрузки страницы языка браузера не знает, поэтому выбор делает
скрипт в самом начале <head> (partials/language_redirect.html.j2). Языков по имени
скрипт не знает: группы языков браузера берутся из файлов языков (browser_languages),
язык для остальных — из site.yml (fallback_locale), выключатель — auto_language.
"""
from routes import NOT_FOUND

# Ключи хранилищ браузера. STORAGE_KEY пишет и nav.js (ручной выбор языка).
STORAGE_KEY = "neva.lang"
SOURCE_KEY = "neva.source"  # источник визита на время перехода — для Метрики
# Поисковые и ИИ-краулеры, сборщики превью ссылок, Lighthouse: им — запрошенная страница.
# «google» — инструменты Google, исполняющие JS без «bot» в имени (Google-InspectionTool
# проверки URL в Search Console, GoogleOther): иначе проверка русского адреса показала
# бы переадресацию. В браузерах Chrome и Android этого слова нет. «telegram» нет
# намеренно: превью Telegram ловится по «bot», а встроенный браузер Telegram на Android
# пишет себя в user-agent — это живой гость, ему автовыбор нужен.
BOT_PATTERN = ("bot|crawl|spider|slurp|lighthouse|pagespeed|preview|google|"
               "facebookexternalhit|whatsapp|headless")


def _groups(locales):
    return [[locale.code, list(locale.browser_languages)]
            for locale in locales if locale.browser_languages]


def _fallback(site, locales):
    code = site.get("fallback_locale")
    if code not in {locale.code for locale in locales}:
        raise ValueError(f"site.yml: fallback_locale = {code!r} — нет такого языка в locales")
    return code


def config(site, routes, current, page_id):
    """Данные скрипта для страницы или None: автовыбор выключен, язык один (выбирать
    не из чего) или у страницы нет пары (404 — по любому неизвестному адресу)."""
    locales = routes.locales
    if not site.get("auto_language") or len(locales) < 2 or page_id == NOT_FOUND:
        return None
    return {"current": current.code,
            "pairs": {locale.code: routes.href(locale, page_id) for locale in locales},
            "groups": _groups(locales), "fallback": _fallback(site, locales),
            "storageKey": STORAGE_KEY, "sourceKey": SOURCE_KEY, "bots": BOT_PATTERN}
