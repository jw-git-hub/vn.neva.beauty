"""IndexNow: Bing и Яндекс узнают о страницах сайта сразу после выкладки, а не при обходе.

Две части. Сборка кладёт в корень сайта файл-ключ `<ключ>.txt` (его содержимое — сам ключ):
по нему поисковик убеждается, что адреса присылает хозяин сайта. После выкладки шаг
деплоя запускает этот файл как скрипт: он берёт адреса из sitemap.xml и одним запросом
отправляет их сервису. Ключ и адрес сервиса — данные в site.yml, не код.

Отказ сервиса не должен ронять выкладку: сайт уже на месте, а уведомление поисковикам —
удобство. Любая ошибка здесь превращается в предупреждение в журнале прогона.

Запуск: `python generator/indexnow.py [--sitemap-file путь]`. Без аргумента sitemap.xml
читается с боевого адреса сайта.
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import yaml

SITE_FILE = Path(__file__).resolve().parent / "data" / "site.yml"
KEY_PATTERN = re.compile(r"[0-9a-f]{32}")
KEY_FILE_EXTENSION = ".txt"
SITEMAP_PATH = "/sitemap.xml"
SITEMAP_NAMESPACE = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAP_FILE_FLAG = "--sitemap-file"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
REQUEST_TIMEOUT_SECONDS = 30
ACCEPTED_STATUSES = (200, 202)  # 202 — ключ принят, проверка файла у сервиса идёт отдельно
WORKFLOW_WARNING = "::warning::IndexNow: "


def check_key(config):
    """Ключ из site.yml; не 32 знака 0-9a-f — ошибка, которую лучше поймать при сборке."""
    key = str(config.get("key", ""))
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError(f"site.yml indexnow.key: нужны 32 знака 0-9a-f, получено {key!r}")
    return key


def key_file_name(config):
    return check_key(config) + KEY_FILE_EXTENSION


def key_file_content(config):
    return check_key(config)


def stale_key_files(directory, config):
    """Файлы-ключи прежних ключей в каталоге сайта: после смены ключа они лишние."""
    current = key_file_name(config)
    return [path for path in sorted(directory.glob("*" + KEY_FILE_EXTENSION))
            if KEY_PATTERN.fullmatch(path.stem) and path.name != current]


def sitemap_urls(sitemap_xml):
    """Адреса страниц из sitemap.xml в порядке файла."""
    root = ElementTree.fromstring(sitemap_xml)
    return [loc.text.strip() for loc in root.findall("sitemap:url/sitemap:loc", SITEMAP_NAMESPACE)]


def build_payload(site, urls):
    """Тело запроса IndexNow: сайт, ключ, где лежит файл-ключ и список адресов."""
    base_url = site["base_url"]
    return {
        "host": urllib.parse.urlsplit(base_url).netloc,
        "key": key_file_content(site["indexnow"]),
        "keyLocation": f"{base_url}/{key_file_name(site['indexnow'])}",
        "urlList": list(urls),
    }


def post_json(endpoint, payload):
    """Отправляет JSON и возвращает код ответа; код ошибки сервиса — тоже ответ, а не исключение."""
    request = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": JSON_CONTENT_TYPE}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def submit(site, urls, send=None):
    """Отправляет адреса сервису из site.yml. `send(endpoint, payload)` → код ответа;
    без `send` — настоящий запрос (post_json)."""
    return (send or post_json)(site["indexnow"]["endpoint"], build_payload(site, urls))


def warn(message):
    print(WORKFLOW_WARNING + message)


def report_submission(site, sitemap_xml, send=None):
    """Отправка + строка итога в журнал. Всегда возвращает 0: выкладку это не роняет."""
    try:
        urls = sitemap_urls(sitemap_xml)
        status = submit(site, urls, send)
    except Exception as error:  # сеть, разбор карты, ключ: любая беда — только предупреждение
        warn(f"не отправлено: {error}")
        return 0
    if status in ACCEPTED_STATUSES:
        print(f"IndexNow: отправлено адресов {len(urls)}, ответ {status}")
    else:
        warn(f"сервис ответил {status}, адресов {len(urls)}")
    return 0


def read_sitemap(site, arguments):
    """Карта сайта из файла (`--sitemap-file путь`) или с боевого адреса."""
    if SITEMAP_FILE_FLAG in arguments:
        return Path(arguments[arguments.index(SITEMAP_FILE_FLAG) + 1]).read_text(encoding="utf-8")
    with urllib.request.urlopen(site["base_url"] + SITEMAP_PATH,
                                timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def main(arguments):
    site = yaml.safe_load(SITE_FILE.read_text(encoding="utf-8"))
    try:
        sitemap_xml = read_sitemap(site, arguments)
    except Exception as error:
        warn(f"не удалось прочитать sitemap.xml: {error}")
        return 0
    return report_submission(site, sitemap_xml)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
