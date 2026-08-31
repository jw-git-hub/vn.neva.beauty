"""Адаптивные картинки: лестница ширин и `sizes` для каждого места вёрстки.

Один источник правды для двух потребителей: `make_images.py` режет производные
ровно по этим ширинам, сборка подставляет `srcset` и `sizes` в шаблоны. Если
таблицы разъедутся, браузер попросит несуществующий файл — поэтому таблица одна.

Ширины подобраны под реальные размеры контейнеров (см. `sizes`) с запасом на
экраны двойной плотности и ограничены шириной исходника: больше него взять
неоткуда. Самая большая ширина лестницы — это сам исходник без суффикса
(`hero.webp`), меньшие лежат рядом с суффиксом (`hero-480.webp`).
"""

GRID_GAP = 24        # var(--sp-6) — промежуток между карточками в сетках
CONTAINER_PAD = 24   # padding-inline у .container с каждой стороны

# Раскладка карточек: 1 колонка → 2 → 3 или 4. Ширина карточки на каждом шаге
# считается из ширины окна за вычетом полей контейнера и промежутков сетки.
_CARD_NARROW = (f"(min-width:560px) calc((100vw - {CONTAINER_PAD * 2 + GRID_GAP}px) / 2), "
                f"calc(100vw - {CONTAINER_PAD * 2}px)")

SLOTS = {
    # Герой главной: min(78%, 300px) от колонки, с 768px — min(92%, 380px).
    # 433px — окно, на котором 78% ширины колонки упирается в потолок 300px.
    "home_hero": {
        "widths": (320, 480, 560, 800),
        "sizes": ("(min-width:768px) 380px, (min-width:433px) 300px, "
                  f"calc((100vw - {CONTAINER_PAD * 2}px) * 0.78)"),
    },
    # Герой услуги: те же правила, но потолки 290px и 360px.
    "service_hero": {
        "widths": (320, 480, 560, 760),
        "sizes": ("(min-width:768px) 360px, (min-width:420px) 290px, "
                  f"calc((100vw - {CONTAINER_PAD * 2}px) * 0.78)"),
    },
    # Обложка раздела на главной: сетка 1 → 2 → 4 колонки.
    "category_cover": {
        "widths": (320, 480, 700, 900),
        "sizes": ("(min-width:1200px) 270px, "
                  f"(min-width:1024px) calc((100vw - {CONTAINER_PAD * 2 + GRID_GAP * 3}px) / 4), "
                  + _CARD_NARROW),
    },
    # Карточка «Смотрите также»: сетка 1 → 2 → 3 колонки.
    "related_card": {
        "widths": (320, 480, 640, 760),
        "sizes": ("(min-width:1200px) 368px, "
                  f"(min-width:900px) calc((100vw - {CONTAINER_PAD * 2 + GRID_GAP * 2}px) / 3), "
                  + _CARD_NARROW),
    },
}

# Пропорции исходников: (ширина, высота) самого большого файла лестницы.
# Отсюда берутся width/height в разметке — браузер резервирует место до загрузки.
BOX = {
    "home_hero": (800, 1000),
    "service_hero": (760, 950),
    "category_cover": (900, 675),
    "related_card": (760, 570),
}

RELATED_PREFIX = "card-"  # карточке нужен кроп 4:3, герой услуги — 4:5


def related_stem(hero_image):
    """Имя кропа 4:3 для карточки «Смотрите также» по имени героя услуги."""
    return RELATED_PREFIX + hero_image


def srcset(stem, slot, base_path=""):
    """Строка `srcset`: меньшие ширины с суффиксом, самая большая — сам файл."""
    widths = SLOTS[slot]["widths"]
    variants = [f"{base_path}/assets/img/{stem}-{w}.webp {w}w" for w in widths[:-1]]
    variants.append(f"{base_path}/assets/img/{stem}.webp {widths[-1]}w")
    return ", ".join(variants)


def sizes(slot):
    return SLOTS[slot]["sizes"]


def width(slot):
    return BOX[slot][0]


def height(slot):
    return BOX[slot][1]
