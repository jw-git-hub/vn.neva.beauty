"""Нарезка производных картинок под лестницу ширин из `images.py`.

Запускается руками, когда меняется набор картинок: `python generator/make_images.py`.
Результат коммитится вместе с исходниками — сборка страниц картинки не трогает,
иначе каждый прогон build.py упирался бы в перекодирование сотни файлов.

Что делает:
  * для каждого кадра режет уменьшенные копии по ширинам своего слота;
  * для карточек «Смотрите также» дополнительно готовит кроп 4:3 из портретного
    героя услуги — тот же кадр, что сейчас обрезает браузер через object-fit,
    только без скачивания лишних пикселей.
"""

import sys
import yaml
from pathlib import Path
from PIL import Image

import images

ROOT = Path(__file__).resolve().parent
# Исходники лежат вне публикуемой папки: посетитель их не запрашивает,
# а в деплое они занимали 1,8 МБ мёртвым грузом.
SRC_DIR = ROOT / "sources" / "img"
IMG_DIR = ROOT.parent / "vn.neva.beauty" / "assets" / "img"

# q78 — граница, за которой вес растёт быстрее, чем качество: на самом сложном
# кадре сайта (волосы крупным планом) PSNR 37.4 дБ, разницы с q82 не видно
# при попиксельном сравнении, а файл легче на 17%.
QUALITY = 78
METHOD = 6     # самый медленный и самый плотный режим кодера WebP


def load_stems():
    """Кадры сайта по слотам: (слот, имя файла без расширения)."""
    content = yaml.safe_load((ROOT / "data/content.yml").read_text(encoding="utf-8"))
    stems = [("home_hero", "hero")]
    stems += [("category_cover", cat["image"]) for cat in content["categories"] if cat.get("image")]
    for svc in content["services"].values():
        stems.append(("service_hero", svc["hero_image"]))
        stems.append(("related_card", images.related_stem(svc["hero_image"])))
    return stems


def source_for(slot, stem):
    """Мастер-кадр в JPG: карточка «Смотрите также» берёт его у своей услуги."""
    if slot == "related_card":
        stem = stem[len(images.RELATED_PREFIX):]
    master = SRC_DIR / f"{stem}.jpg"
    if not master.exists():
        raise FileNotFoundError(f"нет исходника {master}")
    return master


def crop_to_ratio(image, ratio):
    """Центральный кроп до нужной пропорции — то же, что делает object-fit:cover."""
    width, height = image.size
    if width / height > ratio:
        new_width = round(height * ratio)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / ratio)
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def save_webp(image, path):
    image.save(path, format="WEBP", quality=QUALITY, method=METHOD)
    print(f"→ {path.name} {image.width}×{image.height} {path.stat().st_size // 1024} КБ")


def build_variants(slot, stem):
    """Пишет самый большой файл лестницы и все уменьшенные копии."""
    widths = images.SLOTS[slot]["widths"]
    ratio = images.width(slot) / images.height(slot)
    with Image.open(source_for(slot, stem)) as source:
        frame = crop_to_ratio(source.convert("RGB"), ratio)
        for target in widths:
            height = round(target / ratio)
            suffix = "" if target == widths[-1] else f"-{target}"
            save_webp(frame.resize((target, height), Image.LANCZOS),
                      IMG_DIR / f"{stem}{suffix}.webp")


def main():
    for slot, stem in load_stems():
        build_variants(slot, stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
