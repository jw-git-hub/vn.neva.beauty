"""Генерация брендовых растровых ассетов: фавиконы, иконки приложения, карточка превью.

Запускается вручную и только при смене логотипа — результаты коммитятся как статика,
build.py их не трогает и не пересобирает.

Источники (единственные, оба в репозитории):
  assets/icons/lotus.svg          — знак, из него все иконки;
  assets/img/logo-neva-beauty.svg — круглая печать (копия brand/logo-варианты/
                                    E-лотос-печать-светлая-круг.svg), из неё логотип
                                    для разметки организации и карточка превью.

Зачем два разных рендерера: иконкам нужна честная альфа, поэтому лепестки рисуются
напрямую в Pillow. Карточке превью нужны настоящие Cormorant и Manrope из assets/fonts —
их даёт только браузерный движок, поэтому она рендерится системным qlmanage (macOS).

Требования: pip install pillow, macOS.
Запуск: python generator/make_brand_assets.py
"""
import math
import re
import subprocess
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageDraw
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "vn.neva.beauty"
LOTUS_SVG = OUT / "assets" / "icons" / "lotus.svg"
SEAL_SVG = OUT / "assets" / "img" / "logo-neva-beauty.svg"

PLATE = "#FBF4F0"          # фон бренда (токен --bg); он же background_color манифеста
SUPERSAMPLE = 4            # во столько раз рисуем крупнее и уменьшаем — сглаживание краёв
CURVE_STEPS = 96           # на столько отрезков разбивается кубическая кривая лепестка

# Доля кадра под знак. Без плашки лотос почти во весь кадр; на плашке — вписан в
# безопасную зону маски адаптивных иконок Android (центральные 80 % кадра) и в
# скругление иконки iOS, поэтому заметно меньше.
MARK_RATIO_BARE = 0.92
MARK_RATIO_PLATE = 0.58

# Полупрозрачные лепестки на 16 px сливаются с фоном и силуэт пропадает. Корень
# уплотняет слабые слои сильнее плотных: 0.55 → 0.74, а 0.92 → 0.96 почти не меняется.
ICON_OPACITY_GAMMA = 0.5

OG_WIDTH, OG_HEIGHT = 1200, 630   # пропорция, которую мессенджеры показывают целиком
OG_QUALITY = 92
LOGO_SIZE = 512                   # логотип организации для Google и Яндекса
TOUCH_SIZE = 180                  # apple-touch-icon
APP_SIZES = (192, 512)            # иконки манифеста
# Кадры .ico от большего к меньшему: первый задаёт размер отрисовки, остальные Pillow
# уменьшает из него. 48 px — минимальный размер, который просят краулеры фавиконов,
# 32 и 16 — то, что реально показывают вкладка и выдача.
ICO_SIZES = [(48, 48), (32, 32), (16, 16)]

PETAL_RE = re.compile(
    r'<path d="(?P<d>[^"]+)"\s+fill="(?P<fill>#[0-9A-Fa-f]{6})"'
    r'(?:\s+opacity="(?P<opacity>[\d.]+)")?'
    r'\s+transform="rotate\((?P<angle>-?[\d.]+) (?P<cx>[\d.]+) (?P<cy>[\d.]+)\)"'
)


# ---------- знак: разбор SVG и растеризация ----------

def cubic_points(start, control_1, control_2, end):
    """Кубическая кривая Безье как ломаная — Pillow умеет заливать только многоугольники."""
    points = []
    for step in range(CURVE_STEPS + 1):
        t = step / CURVE_STEPS
        u = 1 - t
        points.append(tuple(
            u**3 * start[i] + 3 * u*u*t * control_1[i]
            + 3 * u*t*t * control_2[i] + t**3 * end[i]
            for i in (0, 1)
        ))
    return points


def rotate_around(point, angle_deg, center):
    radians = math.radians(angle_deg)
    dx, dy = point[0] - center[0], point[1] - center[1]
    return (center[0] + dx * math.cos(radians) - dy * math.sin(radians),
            center[1] + dx * math.sin(radians) + dy * math.cos(radians))


def petal_outline(path_d, angle, center):
    """Контур одного лепестка: «M … C … C … Z» из lotus.svg → повёрнутая ломаная."""
    numbers = [float(n) for n in re.findall(r"-?\d+\.?\d*", path_d)]
    start = (numbers[0], numbers[1])
    outline, current, cursor = [start], start, 2
    for _ in range(2):
        control_1 = (numbers[cursor], numbers[cursor + 1])
        control_2 = (numbers[cursor + 2], numbers[cursor + 3])
        end = (numbers[cursor + 4], numbers[cursor + 5])
        outline += cubic_points(current, control_1, control_2, end)
        current, cursor = end, cursor + 6
    return [rotate_around(point, angle, center) for point in outline]


def read_petals():
    """Лепестки знака из lotus.svg в порядке отрисовки: (контур, цвет, непрозрачность)."""
    svg = LOTUS_SVG.read_text(encoding="utf-8")
    petals = [
        (petal_outline(m["d"], float(m["angle"]), (float(m["cx"]), float(m["cy"]))),
         m["fill"], float(m["opacity"] or 1))
        for m in PETAL_RE.finditer(svg)
    ]
    if not petals:
        raise ValueError(f"В {LOTUS_SVG.name} не найдено ни одного лепестка — изменилась разметка?")
    return petals


def outline_bounds(petals):
    """Общая рамка знака — по ней он центрируется и масштабируется в кадре."""
    points = [point for outline, _, _ in petals for point in outline]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def render_mark(petals, size, mark_ratio, plate=None):
    """Знак в квадратном кадре size×size. Каждый лепесток кладётся отдельным слоем и
    накладывается alpha_composite — это тот же source-over, что рисует браузер, поэтому
    перекрытия полупрозрачных лепестков выглядят как в SVG."""
    canvas = size * SUPERSAMPLE
    left, top, right, bottom = outline_bounds(petals)
    scale = canvas * mark_ratio / max(right - left, bottom - top)
    offset_x = canvas / 2 - (left + right) / 2 * scale
    offset_y = canvas / 2 - (top + bottom) / 2 * scale

    image = Image.new("RGBA", (canvas, canvas), plate or (0, 0, 0, 0))
    for outline, fill, opacity in petals:
        layer = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        points = [(x * scale + offset_x, y * scale + offset_y) for x, y in outline]
        alpha = round(opacity ** ICON_OPACITY_GAMMA * 255)
        ImageDraw.Draw(layer).polygon(points, fill=f"{fill}{alpha:02X}")
        image = Image.alpha_composite(image, layer)
    return image.resize((size, size), Image.LANCZOS)


def favicon_svg(petals):
    """Тот же знак векторно: фавикон должен оставаться резким на любом экране.
    Пути берутся из lotus.svg как есть, меняется только непрозрачность и рамка кадра."""
    left, top, right, bottom = outline_bounds(petals)
    side = max(right - left, bottom - top) / MARK_RATIO_BARE
    box_x = (left + right) / 2 - side / 2
    box_y = (top + bottom) / 2 - side / 2

    source = LOTUS_SVG.read_text(encoding="utf-8")
    paths = "\n  ".join(
        f'<path d="{m["d"]}" fill="{m["fill"]}"'
        f' opacity="{float(m["opacity"] or 1) ** ICON_OPACITY_GAMMA:.2f}"'
        f' transform="rotate({m["angle"]} {m["cx"]} {m["cy"]})"/>'
        for m in PETAL_RE.finditer(source)
    )
    return (
        "<!-- Фавикон Neva Beauty. Собран из assets/icons/lotus.svg скриптом\n"
        "     generator/make_brand_assets.py; вручную не правим. Непрозрачность лепестков\n"
        "     поднята: на 16 px исходные полупрозрачные слои сливаются с фоном. -->\n"
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box_x:.1f} {box_y:.1f} '
        f'{side:.1f} {side:.1f}">\n  {paths}\n</svg>\n'
    )


def build_icons():
    """Фавиконы и иконки приложения из знака."""
    petals = read_petals()
    write_text(OUT / "favicon.svg", favicon_svg(petals))

    render_mark(petals, ICO_SIZES[0][0], MARK_RATIO_BARE).save(
        OUT / "favicon.ico", sizes=ICO_SIZES)
    report(OUT / "favicon.ico")

    plated = [(TOUCH_SIZE, OUT / "apple-touch-icon.png")]
    plated += [(size, OUT / f"icon-{size}.png") for size in APP_SIZES]
    for size, path in plated:
        render_mark(petals, size, MARK_RATIO_PLATE, plate=PLATE).convert("RGB").save(path)
        report(path)


# ---------- печать: логотип организации и карточка превью ----------

def render_page(html, width, height):
    """HTML → картинка через системный qlmanage. Страница кладётся в корень собранного
    сайта: только оттуда работают относительные пути к шрифтам, токенам и печати.
    qlmanage рисует квадрат со стороной -s, поэтому кадр обрезаем сами."""
    side = max(width, height)
    with tempfile.TemporaryDirectory() as thumbs:
        page = Path(tempfile.mkstemp(dir=OUT, suffix=".html")[1])
        try:
            page.write_text(html, encoding="utf-8")
            subprocess.run(["qlmanage", "-t", "-s", str(side), "-o", thumbs, str(page)],
                           check=True, capture_output=True)
            thumbnail = next(Path(thumbs).glob("*.png"), None)
            if thumbnail is None:
                raise RuntimeError("qlmanage не отрисовал страницу — доступен ли он в системе?")
            return Image.open(thumbnail).convert("RGB").crop((0, 0, width, height))
        finally:
            page.unlink(missing_ok=True)


def card_html(site, categories):
    """Разметка карточки превью из шаблона og-card.html.j2 и данных сайта."""
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    return env.get_template("og-card.html.j2").render(
        width=OG_WIDTH, height=OG_HEIGHT,
        brand=site["brand"], loc=site["brand_location"],
        services=[cat["title"] for cat in categories],
        logo_src=SEAL_SVG.relative_to(OUT).as_posix(),
    )


def logo_html():
    """Печать на фирменном фоне: прозрачные углы круга не должны стать белыми.
    Размер в долях окна, а не в пикселях, — по той же причине, что и в карточке
    превью (см. комментарий в og-card.html.j2): вьюпорт рендерера нам не подвластен."""
    return (f'<!DOCTYPE html><meta charset="utf-8">'
            f'<style>html,body{{margin:0;overflow:hidden}}'
            f'img{{display:block;width:100vw;height:100vw;background:{PLATE}}}</style>'
            f'<img src="{SEAL_SVG.relative_to(OUT).as_posix()}" alt="">')


def build_social(site, categories):
    """Логотип организации для разметки и карточка превью ссылок."""
    logo = OUT / "assets" / "img" / "logo-neva-beauty.png"
    render_page(logo_html(), LOGO_SIZE, LOGO_SIZE).save(logo)
    report(logo)

    card = OUT / "assets" / "img" / "og-default.jpg"
    render_page(card_html(site, categories), OG_WIDTH, OG_HEIGHT).save(
        card, quality=OG_QUALITY, optimize=True)
    report(card)


# ---------- вспомогательное ----------

def write_text(path, text):
    path.write_text(text, encoding="utf-8")
    report(path)


def report(path):
    print("→", path.relative_to(OUT.parent), f"({path.stat().st_size / 1024:.1f} KB)")


def main():
    site = yaml.safe_load((ROOT / "data/site.yml").read_text(encoding="utf-8"))
    content = yaml.safe_load((ROOT / "data/content.yml").read_text(encoding="utf-8"))
    build_icons()
    build_social(site, content["categories"])


if __name__ == "__main__":
    main()
