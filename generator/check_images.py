"""Проверка картинок во всех собранных страницах: каждая локальная <img> ведёт на
существующий файл, и на каждой странице стоит скрипт повторной загрузки картинок.
Падает (exit 1) при нарушении.

Зачем: сорвавшийся запрос картинки браузер сам не повторяет — так во встроенном
браузере Instagram на медленном канале не догрузился hero главной, а на его месте
осталась пустая арка с вылезшим текстом alt. Скрипт-повторщик чинит это, и его
пропажа из шаблона должна ронять сборку. Битый путь к файлу даёт ровно тот же
симптом, только всегда. Проверка локальная, сети не требует.
Запуск: python generator/check_images.py"""
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "vn.neva.beauty"
RETRY_MARKER = "img.dataset.imgError"


def pages():
    """Собранные страницы сайта. Служебные папки (.superpowers и подобные) пропускаем:
    они есть локально, но не в чистом чекауте CI — иначе проверка ведёт себя по-разному."""
    return sorted(page for page in SITE.glob("**/*.html")
                  if not any(part.startswith(".") for part in page.relative_to(SITE).parts))


def local_sources(soup):
    """Пути картинок, лежащих в самом репозитории: без внешних URL и data:."""
    return [src for img in soup.find_all("img")
            if (src := img.get("src", "")) and not urlsplit(src).scheme and not src.startswith("//")]


def missing_file(page, src):
    """Файл, на который ведёт src, — если его нет на диске."""
    path = unquote(urlsplit(src).path)
    target = SITE / path.lstrip("/") if path.startswith("/") else page.parent / path
    return None if target.is_file() else target


def check(page):
    """Нарушения на одной странице."""
    name = page.relative_to(SITE.parent)
    html = page.read_text(encoding="utf-8")
    errors = []
    if RETRY_MARKER not in html:
        errors.append(f"{name}: нет скрипта повторной загрузки картинок")
    for src in local_sources(BeautifulSoup(html, "html.parser")):
        if target := missing_file(page, src):
            errors.append(f"{name}: <img src=\"{src}\"> — файла нет: {target.relative_to(SITE.parent)}")
    return errors


errors = [error for page in pages() for error in check(page)]
print(f"страниц проверено: {len(pages())}")
print("\n".join(errors) if errors else "IMAGES OK — пути картинок целы, повтор загрузки на месте")
sys.exit(1 if errors else 0)
