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
from PIL import Image

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


def srcset_problems(page, soup):
    """Каждый файл из srcset есть на диске, и ширина в дескрипторе — настоящая.

    Набор ширин собирается из имён файлов, поэтому опечатка в лестнице или
    незапущенный make_images.py дают 404 ровно на тех экранах, где браузер
    выберет пропавший вариант, — на своём мониторе этого не увидишь."""
    for img in soup.select("img[srcset]"):
        for candidate in img["srcset"].split(","):
            src, _, descriptor = candidate.strip().rpartition(" ")
            if missing_file(page, src):
                yield f"нет файла из srcset: {src}"
                continue
            with Image.open(SITE / unquote(urlsplit(src).path).lstrip("/")) as frame:
                if f"{frame.width}w" != descriptor:
                    yield (f"ширина в srcset ({descriptor}) не совпадает "
                           f"с файлом ({frame.width}w): {src}")


def preload_problems(soup):
    """Предзагруженный кадр первого экрана есть в разметке, помечен приоритетным,
    и его набор ширин совпадает с набором самой картинки.

    Расхождение imagesrcset и srcset тихое и дорогое: браузер качает один файл
    по предзагрузке и второй по разметке — вместо ускорения выходит лишний вес."""
    preload = soup.select_one('link[rel="preload"][as="image"]')
    if not preload:
        return
    href = preload.get("href", "")
    img = soup.select_one(f'img[src="{href}"]')
    if img is None:
        yield f"предзагружено изображение, которого нет в разметке: {href}"
        return
    if img.get("fetchpriority") != "high":
        yield f'у предзагруженного изображения нет fetchpriority="high": {href}'
    for preload_attr, img_attr in (("imagesrcset", "srcset"), ("imagesizes", "sizes")):
        if preload.get(preload_attr, "") != img.get(img_attr, ""):
            yield f"{preload_attr} предзагрузки не совпадает с {img_attr} картинки: {href}"


def check(page):
    """Нарушения на одной странице."""
    name = page.relative_to(SITE.parent)
    html = page.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    errors = []
    if RETRY_MARKER not in html:
        errors.append(f"{name}: нет скрипта повторной загрузки картинок")
    for src in local_sources(soup):
        if target := missing_file(page, src):
            errors.append(f"{name}: <img src=\"{src}\"> — файла нет: {target.relative_to(SITE.parent)}")
    errors += [f"{name}: {problem}" for problem in srcset_problems(page, soup)]
    errors += [f"{name}: {problem}" for problem in preload_problems(soup)]
    return errors


errors = [error for page in pages() for error in check(page)]
print(f"страниц проверено: {len(pages())}")
print("\n".join(errors) if errors else "IMAGES OK — пути картинок целы, повтор загрузки на месте")
sys.exit(1 if errors else 0)
