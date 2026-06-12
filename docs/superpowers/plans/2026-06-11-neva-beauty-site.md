# Neva Beauty Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить многостраничный статический сайт Neva Beauty (Дананг) на чистом HTML/CSS/JS, генерируемый из шаблонов + данных, с дословным переносом прайс-листов старого сайта, тёплой палитрой Blush & Nude и ДНК-героем на Three.js, готовый к публикации на GitHub Pages (`vn.neva.beauty`).

**Architecture:** Локальный генератор (Python + Jinja2) рендерит **статический** HTML из шаблонов и данных в папку `vn.neva.beauty/` (публикуемый репозиторий). Деплой — обычные статические файлы, без рантайм-сборки и фреймворков. Прайсы извлекаются скриптом из старых Tilda-страниц в `prices.json`; автоматический parity-тест сверяет цены в **сгенерированном** HTML с независимым разбором старого сайта (защита требования 100% точности цен). Изображения скачиваются с Unsplash локально, ключи в `.env` (вне git).

**Tech Stack:** Python 3 (Jinja2, BeautifulSoup4, PyYAML, requests) — только инструментарий; вывод — HTML5 + CSS (отдельные файлы) + ES-модули JS + Three.js (CDN, только на главной). Хостинг: GitHub Pages, кастомный домен.

**Раскладка источника и вывода:**
```
Project - vn.neva.beauty/          # рабочее пространство (НЕ публикуется)
  generator/
    build.py                       # рендер шаблонов → vn.neva.beauty/
    extract_prices.py              # старый сайт → data/prices.json
    check_prices.py                # parity-тест цен (old HTML vs new HTML)
    templates/  *.html.j2
    data/   site.yml  content.yml  prices.json
  scripts/fetch_images.py          # Unsplash → vn.neva.beauty/assets/img/
  requirements.txt
  .env                             # ключи Unsplash (gitignored, в workspace)
  vn.neva.beauty/                  # ВЫВОД = публикуемый репозиторий GitHub Pages
    index.html
    <slug>/index.html  (×10 + privacy)
    assets/css|js|img|icons/
    CNAME robots.txt sitemap.xml 404.html favicon.svg .gitignore
```

**Соответствие слаг → исходная страница (источник прайса):**
| slug | old file | услуга |
|---|---|---|
| lazernaya-epilyaciya | page116772006.html | Лазерная эпиляция |
| lpg-massazh | page116853986.html | LPG-массаж |
| endosfera-terapiya | page116855366.html | Эндосфера-терапия |
| ultrazvukovaya-kavitaciya | page116856706.html | Ультразвуковая кавитация |
| esteticheskaya-kosmetologiya-i-uhod | page117250526.html | Эстетическая косметология и уход |
| smas-lifting | page117589196.html | Ультразвуковой SMAS-лифтинг |
| udalenie-tatuirovok-lazerom | page118008586.html | Лазерное удаление татуировок |
| udalenye-permanentnogo-makiyazha | page118018046.html | Удаление перманентного макияжа |
| morpheus-8-rf-lifting | page118032546.html | Игольчатый RF-лифтинг Morpheus 8 |
| fotoomolozhenie-m22 | page118049356.html | Фотоомоложение M22 |
| (home) | page116726206.html | — |
| privacy | page124964646.html | Политика конфиденциальности |

OLD_DIR = `../lданные старого сайта` (относительно `generator/`).

---

## Phase 0 — Scaffold & tooling

### Task 0.1: Рабочее пространство и зависимости

**Files:**
- Create: `requirements.txt`, `.gitignore` (workspace), `generator/`, `scripts/`, `vn.neva.beauty/`

- [ ] **Step 1: Создать структуру папок и requirements**

`requirements.txt`:
```
Jinja2==3.1.4
beautifulsoup4==4.12.3
PyYAML==6.0.2
requests==2.32.3
```

- [ ] **Step 2: venv + установка**

Run:
```bash
cd "Project - vn.neva.beauty" && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
mkdir -p generator/templates generator/data scripts vn.neva.beauty/assets/{css,js,img,icons}
```
Expected: `Successfully installed Jinja2 ... beautifulsoup4 ... PyYAML ... requests ...`

- [ ] **Step 3: Workspace `.gitignore`** (защита ключей; этот gitignore для будущего репо генератора, если появится)

`.gitignore`:
```
.venv/
.env
.superpowers/
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 4: Вывод-репозиторий `vn.neva.beauty/.gitignore`** (минимальный — туда не должно попасть лишнее)

`vn.neva.beauty/.gitignore`:
```
.DS_Store
.superpowers/
```

- [ ] **Step 5: Verify** — `ls vn.neva.beauty/assets` → `css js img icons`

---

## Phase 1 — Извлечение данных (критичные цены)

### Task 1.1: Парсер прайсов старого сайта → prices.json

**Files:**
- Create: `generator/extract_prices.py`, `generator/data/prices.json` (вывод)

- [ ] **Step 1: Написать экстрактор** (`generator/extract_prices.py`)

```python
"""Извлекает прайс-листы из старых Tilda-страниц в data/prices.json.
Источник истины по ценам. Цены и названия НЕ нормализуются (переносятся дословно)."""
import json, re
from pathlib import Path
from bs4 import BeautifulSoup

OLD = Path(__file__).resolve().parent.parent.parent / "lданные старого сайта"
OUT = Path(__file__).resolve().parent / "data" / "prices.json"

SLUG_FILE = {
    "lazernaya-epilyaciya": "page116772006.html",
    "lpg-massazh": "page116853986.html",
    "endosfera-terapiya": "page116855366.html",
    "ultrazvukovaya-kavitaciya": "page116856706.html",
    "esteticheskaya-kosmetologiya-i-uhod": "page117250526.html",
    "smas-lifting": "page117589196.html",
    "udalenie-tatuirovok-lazerom": "page118008586.html",
    "udalenye-permanentnogo-makiyazha": "page118018046.html",
    "morpheus-8-rf-lifting": "page118032546.html",
    "fotoomolozhenie-m22": "page118049356.html",
}

def clean(s): return re.sub(r"\s+", " ", s).strip()

def parse_page(html):
    """Возвращает [{section: str|None, items: [{name, price}]}] в порядке документа.
    Секции — блоки t812__title (напр. 'Цены - Женщины'); элементы — t812__pricelist-item."""
    soup = BeautifulSoup(html, "html.parser")
    sections, current = [], {"section": None, "items": []}
    # Обходим все узлы прайс-листа и заголовки секций в порядке документа
    nodes = soup.select(".t812__title, .t812__pricelist-item")
    for node in nodes:
        cls = node.get("class", [])
        if "t812__title" in cls:
            txt = clean(node.get_text())
            if not txt:
                continue
            if current["items"]:
                sections.append(current)
            current = {"section": txt, "items": []}
        else:  # pricelist-item
            title = node.select_one(".t812__pricelist-item__title")
            price = node.select_one(".t812__pricelist-item__price")
            if not title or not price:
                continue
            name, val = clean(title.get_text()), clean(price.get_text())
            if not val:
                continue
            current["items"].append({"name": name, "price": val})
    if current["items"]:
        sections.append(current)
    return sections

def main():
    data = {}
    for slug, fname in SLUG_FILE.items():
        html = (OLD / fname).read_text(encoding="utf-8")
        data[slug] = parse_page(html)
        n = sum(len(s["items"]) for s in data[slug])
        print(f"{slug}: {n} позиций в {len(data[slug])} секциях")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить и проверить счётчики**

Run: `cd generator && python extract_prices.py`
Expected (порядок цен/секций — дословно из источника): каждая услуга печатает ненулевое число позиций; `lazernaya-epilyaciya` — две секции (Женщины/Мужчины) и > 30 позиций суммарно.

- [ ] **Step 3: Ручная сверка 3 страниц** — открыть `prices.json` и соответствующие старые HTML (через браузер или grep) и глазами сверить названия+цены для `lazernaya-epilyaciya`, `lpg-massazh`, `smas-lifting`. Исправить парсер, если потеряны/смещены позиции.

- [ ] **Step 4: Commit (output repo не трогаем; коммитов в git пока нет — отметить выполнение галочкой).**

---

## Phase 2 — Дизайн-токены и база CSS

### Task 2.1: Токены, сброс, типографика

**Files:**
- Create: `vn.neva.beauty/assets/css/tokens.css`, `base.css`

- [ ] **Step 1: `tokens.css`** — семантические переменные (палитра Blush & Nude, типографика, отступы, тени, радиусы, z-index, длительности)

```css
:root{
  /* палитра */
  --bg:#FBF4F0; --surface:#F5E8E2; --surface-2:#F8ECE6;
  --rose-soft:#CE9B91; --rose:#B07A72; --rose-deep:#9E6960;
  --taupe:#B9A89A; --ink:#4A3B38; --muted:#A4928B; --line:#EFDDD5;
  --white:#FFFFFF;
  /* типографика */
  --font-head:'Cormorant',Georgia,serif;
  --font-body:'Manrope',system-ui,sans-serif;
  --fs-200:.8125rem; --fs-300:.9375rem; --fs-400:1rem; --fs-500:1.25rem;
  --fs-600:1.5rem; --fs-700:2rem; --fs-800:2.75rem; --fs-900:3.75rem;
  --lh-tight:1.08; --lh-body:1.6;
  /* пространство (шаг 4/8) */
  --sp-1:.25rem; --sp-2:.5rem; --sp-3:.75rem; --sp-4:1rem; --sp-6:1.5rem;
  --sp-8:2rem; --sp-12:3rem; --sp-16:4rem; --sp-24:6rem;
  --radius:14px; --radius-lg:20px; --radius-pill:999px;
  --shadow-sm:0 2px 10px rgba(74,59,56,.06);
  --shadow-md:0 12px 40px rgba(74,59,56,.10);
  --container:1200px;
  --z-header:100; --z-drawer:200; --z-overlay:190;
  --t-fast:160ms; --t-mid:240ms; --ease:cubic-bezier(.2,.65,.3,.9);
}
```

- [ ] **Step 2: `base.css`** — современный сброс, базовая типографика, фокус-стили, контейнер, утилиты, `prefers-reduced-motion`

```css
*,*::before,*::after{box-sizing:border-box}
*{margin:0}
html{scroll-behavior:smooth}
body{font-family:var(--font-body);font-size:var(--fs-400);line-height:var(--lh-body);
  color:var(--ink);background:var(--bg);-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:var(--font-head);line-height:var(--lh-tight);font-weight:600}
img,svg{display:block;max-width:100%}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid var(--rose);outline-offset:2px;border-radius:4px}
.container{max-width:var(--container);margin-inline:auto;padding-inline:var(--sp-6)}
.section{padding-block:var(--sp-24)}
.eyebrow{font-family:var(--font-body);font-size:var(--fs-200);letter-spacing:.2em;
  text-transform:uppercase;color:var(--rose)}
@media (prefers-reduced-motion:reduce){
  *{animation-duration:.01ms!important;animation-iteration-count:1!important;
    transition-duration:.01ms!important;scroll-behavior:auto!important}
}
```

- [ ] **Step 3: Verify** — открыть временный HTML, подключить оба файла, убедиться, что фон `--bg`, текст `--ink`, фокус виден.

---

## Phase 3 — Шаблоны, общие компоненты, генератор

### Task 3.1: Данные сайта и контента

**Files:**
- Create: `generator/data/site.yml`, `generator/data/content.yml`

- [ ] **Step 1: `site.yml`** — контакты, навигация, футер (дословные контакты)

```yaml
brand: "Neva Beauty"
tagline: "Центр красоты · Дананг"
location: "Да Нанг, Вьетнам"
hours: "Ежедневно 10:00 – 20:00"
contacts:
  whatsapp_number: "84357132621"
  whatsapp_url: "https://wa.me/84357132621"
  telegram_url: "https://t.me/doctor_cosmetolog_pro"
  instagram_url: "https://instagram.com/vn.neva.beauty"
nav:
  - {label: "Главная", url: "/"}
  - label: "Аппаратная косметология"
    children:
      - {label: "LPG-массаж", slug: "lpg-massazh"}
      - {label: "Эндосфера-терапия", slug: "endosfera-terapiya"}
      - {label: "Ультразвуковая кавитация", slug: "ultrazvukovaya-kavitaciya"}
      - {label: "Ультразвуковой SMAS-лифтинг", slug: "smas-lifting"}
      - {label: "Лазерное удаление татуировок", slug: "udalenie-tatuirovok-lazerom"}
      - {label: "Удаление перманентного макияжа", slug: "udalenye-permanentnogo-makiyazha"}
      - {label: "Morpheus 8 RF-лифтинг", slug: "morpheus-8-rf-lifting"}
      - {label: "Фотоомоложение M22", slug: "fotoomolozhenie-m22"}
  - label: "Эпиляция"
    children:
      - {label: "Лазерная эпиляция", slug: "lazernaya-epilyaciya"}
  - label: "Уход"
    children:
      - {label: "Эстетическая косметология и уход", slug: "esteticheskaya-kosmetologiya-i-uhod"}
```

- [ ] **Step 2: `content.yml`** — редакционный контент по каждой услуге (intro/benefits/seo/hero_image/related). Цены сюда НЕ дублируются (берутся из prices.json). Названия `title` должны совпадать с источником.

Структура (заполнить для всех 10 слагов; интро/преимущества можно адаптировать из старого сайта — тексты уже извлечены в footer-странице):
```yaml
services:
  lazernaya-epilyaciya:
    title: "Лазерная эпиляция"
    category: "Эпиляция"
    seo_title: "Лазерная эпиляция в Дананге — Neva Beauty"
    seo_desc: "Деликатная лазерная эпиляция любых зон в центре красоты Neva Beauty, Дананг."
    hero_image: "epilyaciya-hero"   # имя файла (без расширения) из fetch_images
    intro: >
      Обретите безупречную гладкость кожи и уверенность в каждом движении.
      В условиях солнца и влажности Дананга лазерная эпиляция деликатно
      устраняет нежелательные волосы, делая кожу шелковистой.
    benefits:
      - {icon: "sparkles", title: "Решение разных проблем", text: "Борется не только с волосами, но и с гиперпигментацией и воспалениями."}
      - {icon: "shield", title: "Безопасность и комфорт", text: "Защита эпидермиса, без повреждений кожи даже в жару."}
      - {icon: "target", title: "Глубинный эффект", text: "Воздействие на корень волоса, долгосрочная гладкость."}
      - {icon: "check", title: "Универсальность", text: "Подходит для любых зон тела."}
    related: ["fotoomolozhenie-m22", "morpheus-8-rf-lifting"]
  # ... остальные 9 услуг по тому же шаблону
home:
  hero_title_lines: ["Сияние,", "заложенное", "в вас"]
  hero_sub: "Аппаратная косметология, лазерная эпиляция и уход на современных аппаратах в самом сердце Дананга."
  benefits: [ ... 4 пункта ... ]
  categories:   # 4 карточки на главной
    - {title: "Аппаратная косметология", slug: "lpg-massazh", image: "cat-apparat"}
    - {title: "Лазерная эпиляция", slug: "lazernaya-epilyaciya", image: "cat-epil"}
    - {title: "Уход и косметология", slug: "esteticheskaya-kosmetologiya-i-uhod", image: "cat-care"}
    - {title: "Лифтинг и омоложение", slug: "smas-lifting", image: "cat-lift"}
  popular:   # 6-8 позиций для прайс-тизера (slug + name + берём цену из prices.json по name)
    - {slug: "lazernaya-epilyaciya", name: "Лицо полностью"}
    # ...
```

- [ ] **Step 3: Verify** — `python -c "import yaml; yaml.safe_load(open('generator/data/site.yml')); yaml.safe_load(open('generator/data/content.yml'))"` → без ошибок.

### Task 3.2: Базовые Jinja-шаблоны (layout, header, footer)

**Files:**
- Create: `generator/templates/base.html.j2`, `partials/header.html.j2`, `partials/footer.html.j2`, `partials/head.html.j2`

- [ ] **Step 1: `partials/head.html.j2`** — `<head>` с мета, OG, шрифтами, фавиконом, общими CSS

```jinja
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page.seo_title }}</title>
  <meta name="description" content="{{ page.seo_desc }}">
  <link rel="canonical" href="https://vn.neva.beauty{{ page.url }}">
  <meta property="og:title" content="{{ page.seo_title }}">
  <meta property="og:description" content="{{ page.seo_desc }}">
  <meta property="og:type" content="website">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant:wght@500;600&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/tokens.css">
  <link rel="stylesheet" href="/assets/css/base.css">
  <link rel="stylesheet" href="/assets/css/components.css">
  {% block extra_css %}{% endblock %}
</head>
```

- [ ] **Step 2: `partials/header.html.j2`** — прилипающий хедер, меню из `site.nav` с дропдауном, бургер; мобайл-drawer

```jinja
<header class="site-header" data-header>
  <div class="container site-header__inner">
    <a class="site-header__logo" href="/">{{ site.brand }}</a>
    <nav class="nav" aria-label="Основная навигация">
      {% for item in site.nav %}
        {% if item.children %}
        <div class="nav__group">
          <button class="nav__link nav__toggle" aria-expanded="false">{{ item.label }}<span class="nav__chev" aria-hidden="true">▾</span></button>
          <div class="nav__menu">
            {% for c in item.children %}<a class="nav__sub" href="/{{ c.slug }}/">{{ c.label }}</a>{% endfor %}
          </div>
        </div>
        {% else %}
        <a class="nav__link" href="{{ item.url }}">{{ item.label }}</a>
        {% endif %}
      {% endfor %}
    </nav>
    <a class="btn btn--primary site-header__cta" href="{{ site.contacts.whatsapp_url }}?text={{ 'Здравствуйте! Хочу записаться' | urlencode }}" target="_blank" rel="noopener">Записаться</a>
    <button class="burger" data-drawer-open aria-label="Открыть меню"><span></span><span></span><span></span></button>
  </div>
  {% include 'partials/drawer.html.j2' %}
</header>
```

- [ ] **Step 3: `partials/drawer.html.j2`** + `partials/footer.html.j2`** — мобильное меню (overlay + панель + ✕) и футер (лого, меню услуг, соцсети, ©, privacy). Соцссылки только из `site.contacts`.

- [ ] **Step 4: `base.html.j2`** — корневой layout

```jinja
<!DOCTYPE html>
<html lang="ru">
{% include 'partials/head.html.j2' %}
<body>
  {% include 'partials/header.html.j2' %}
  <main id="main">{% block content %}{% endblock %}</main>
  {% include 'partials/footer.html.j2' %}
  <script type="module" src="/assets/js/nav.js"></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 5: Verify** — шаблоны парсятся (проверится в Task 3.4 при первом рендере).

### Task 3.3: Общие компоненты CSS + JS навигации

**Files:**
- Create: `vn.neva.beauty/assets/css/components.css`, `vn.neva.beauty/assets/js/nav.js`

- [ ] **Step 1: `components.css`** — кнопки (`.btn`, `.btn--primary` на `--rose`, контраст AA), хедер, nav-дропдаун (hover на десктоп / click на тач), бургер, drawer + overlay (scrim 50%), карточки, секции-заголовки. Тач-цели ≥44px.
- [ ] **Step 2: `nav.js`** (ES-модуль) — открытие/закрытие drawer (`data-drawer-open`/`✕`/overlay/Esc), блокировка скролла body, тоггл дропдаунов по клику на тач, тень хедера при скролле (IntersectionObserver/scroll). Без инлайна.

```js
// nav.js
const header = document.querySelector('[data-header]');
const openBtn = document.querySelector('[data-drawer-open]');
const drawer = document.querySelector('[data-drawer]');
const overlay = document.querySelector('[data-overlay]');
const closeEls = document.querySelectorAll('[data-drawer-close]');

function setDrawer(open){
  drawer?.classList.toggle('is-open', open);
  overlay?.classList.toggle('is-open', open);
  document.body.classList.toggle('no-scroll', open);
  openBtn?.setAttribute('aria-expanded', String(open));
}
openBtn?.addEventListener('click', ()=>setDrawer(true));
closeEls.forEach(el=>el.addEventListener('click', ()=>setDrawer(false)));
document.addEventListener('keydown', e=>{ if(e.key==='Escape') setDrawer(false); });

// тень хедера при скролле
const onScroll = ()=> header?.classList.toggle('is-scrolled', window.scrollY > 12);
onScroll(); window.addEventListener('scroll', onScroll, {passive:true});

// дропдаун по клику (тач/клавиатура)
document.querySelectorAll('.nav__toggle').forEach(btn=>{
  btn.addEventListener('click', e=>{
    e.preventDefault();
    const open = btn.getAttribute('aria-expanded')==='true';
    btn.setAttribute('aria-expanded', String(!open));
    btn.closest('.nav__group')?.classList.toggle('is-open', !open);
  });
});
```

- [ ] **Step 3: Verify** — проверится после первого рендера (Task 3.4) в браузере: drawer открывается/закрывается, Esc, overlay-клик, тень хедера.

### Task 3.4: build.py — генератор

**Files:**
- Create: `generator/build.py`

- [ ] **Step 1: Написать `build.py`** — собирает контекст (site.yml + content.yml + prices.json), рендерит главную, 10 услуг, privacy в `vn.neva.beauty/`. Добавляет Jinja-фильтр `urlencode`.

```python
import json, urllib.parse, yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "vn.neva.beauty"

def load():
    site = yaml.safe_load((ROOT/"data/site.yml").read_text(encoding="utf-8"))
    content = yaml.safe_load((ROOT/"data/content.yml").read_text(encoding="utf-8"))
    prices = json.loads((ROOT/"data/prices.json").read_text(encoding="utf-8"))
    return site, content, prices

def env():
    e = Environment(loader=FileSystemLoader(ROOT/"templates"),
                    autoescape=select_autoescape(["html","j2"]))
    e.filters["urlencode"] = lambda s: urllib.parse.quote(str(s))
    return e

def write(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("→", path.relative_to(OUT.parent))

def main():
    site, content, prices = load()
    e = env()
    # главная
    page = {"url":"/", "seo_title": content["home"].get("seo_title","Neva Beauty — центр красоты в Дананге"),
            "seo_desc": content["home"].get("seo_desc","")}
    write(OUT/"index.html", e.get_template("home.html.j2").render(
        site=site, page=page, home=content["home"], prices=prices))
    # услуги
    tpl = e.get_template("service.html.j2")
    for slug, svc in content["services"].items():
        page = {"url": f"/{slug}/", "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"]}
        write(OUT/slug/"index.html", tpl.render(
            site=site, page=page, svc=svc, slug=slug,
            sections=prices.get(slug, []), services=content["services"]))
    # privacy
    page = {"url":"/privacy/", "seo_title":"Политика конфиденциальности — Neva Beauty", "seo_desc":""}
    write(OUT/"privacy"/"index.html", e.get_template("privacy.html.j2").render(site=site, page=page))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Заглушки шаблонов** — создать минимальные `home.html.j2`, `service.html.j2`, `privacy.html.j2` (наследуют base, выводят `{{ svc.title }}` и т.п.), чтобы рендер прошёл. Наполнятся в Phase 4–5.
- [ ] **Step 3: Запустить** — `cd generator && python build.py`
Expected: печатает `→ vn.neva.beauty/index.html`, `→ vn.neva.beauty/<slug>/index.html` ×10, `→ vn.neva.beauty/privacy/index.html`.
- [ ] **Step 4: Verify в браузере** — `python3 -m http.server -d vn.neva.beauty 8080`, открыть `http://localhost:8080/` и `/lazernaya-epilyaciya/`: хедер, навигация, drawer, футер работают; ссылки услуг ведут на свои страницы.

---

## Phase 4 — Главная страница + ДНК-герой

### Task 4.1: Секции главной (HTML/CSS)

**Files:**
- Create: `generator/templates/home.html.j2`, `vn.neva.beauty/assets/css/home.css`
- Modify: `generator/templates/partials/head.html.j2` (доп. CSS через block)

- [ ] **Step 1: `home.html.j2`** — 8 секций по спеку: hero (контейнер для канваса + текст), контакт-полоса, сетка 4 категорий (`home.categories`), преимущества (`home.benefits`), популярные процедуры (`home.popular`, цену тянуть из `prices` по совпадению `name`), блок записи (WhatsApp/Telegram/Instagram), футер из base. Подключить `home.css` и `hero-helix.js` через блоки.

Хелпер для цены популярной позиции (Jinja macro в шаблоне):
```jinja
{% macro price_of(prices, slug, name) -%}
  {%- for sec in prices.get(slug, []) -%}{%- for it in sec['items'] -%}
    {%- if it.name == name %}{{ it.price }}{% endif -%}
  {%- endfor -%}{%- endfor -%}
{%- endmacro %}
```

- [ ] **Step 2: `home.css`** — стили секций: hero (grid текст/канвас, min-height dvh, светлый радиальный градиент фоном), контакт-полоса (плашка внахлёст, тень), карточки категорий (фото + заголовок, hover-подъём transform/opacity), преимущества (иконки SVG), прайс-тизер, блок записи. Мобайл-first, брейкпоинты 768/1024.
- [ ] **Step 3: Rebuild + verify** — `python build.py`; в браузере главная: все секции на месте, адаптив на 375/768/1024, нет горизонтального скролла, контраст текста на градиенте ≥4.5:1.

### Task 4.2: ДНК-спираль на Three.js

**Files:**
- Create: `vn.neva.beauty/assets/js/hero-helix.js`
- Modify: `generator/templates/home.html.j2` (контейнер `#hero-canvas`, подключение модуля)

- [ ] **Step 1: Контейнер в hero** — `<div id="hero-canvas" class="hero__canvas" aria-hidden="true"></div>`; подключить `import * as THREE from 'https://unpkg.com/three@0.160/build/three.module.js'` внутри `hero-helix.js` (ES-модуль).
- [ ] **Step 2: `hero-helix.js`** — построить **двойную спираль ДНК** из точек (две нити по параметрике спирали + перемычки), цвета из палитры (роза/бронза/тауп), светлый аддитивный/нормальный блендинг под светлый фон, медленное вращение + «дыхание» (масштаб по времени) + мягкое смещение к курсору, ресайз, остановка при `prefers-reduced-motion`.

Ключевая геометрия (вместо torus knot оригинала):
```js
// две нити: угол a = t*turns*2π; смещение второй нити на π
// strand point: x = sin(a)*R, y = (t-0.5)*height, z = cos(a)*R
// перемычки — отрезки/точки между нитями каждые k шагов
const TURNS = 6, R = 1.2, HEIGHT = 7, PER_TURN = 60;
```
Реализация: `BufferGeometry` + `PointsMaterial(vertexColors, size, transparent)`; в анимации — вращение `points.rotation.y += dt*0.15`, «дыхание» `points.scale.setScalar(1+Math.sin(t*0.8)*0.02)`, курсор через `lerp` целевой ротации. Очистка ресурсов в `dispose()`.

- [ ] **Step 3: reduced-motion fallback** — если `matchMedia('(prefers-reduced-motion: reduce)').matches`, не запускать анимацию (отрисовать один кадр или скрыть канвас, оставив градиентный фон).
- [ ] **Step 4: Verify в браузере** — спираль видна справа в герое, вращается/дышит, реагирует на курсор; на мобиле не ломает раскладку; с включённым reduced-motion анимации нет; FPS приемлемый (визуально без рывков).

---

## Phase 5 — Страница услуги + прайс-компонент

### Task 5.1: Шаблон услуги и прайс-лист

**Files:**
- Create: `generator/templates/service.html.j2`, `vn.neva.beauty/assets/css/service.css`, `vn.neva.beauty/assets/js/price-tabs.js`

- [ ] **Step 1: `service.html.j2`** — секции: интро-герой (фото `svc.hero_image` + `svc.title` + `svc.intro` + CTA), «Преимущества процедуры» (`svc.benefits`, 4 карточки с SVG-иконкой), **прайс-лист** (рендер `sections`: если >1 секции — табы; КОМБО-позиции (name начинается с «КОМБО») выносить карточками; остальное — строки name/price с табличными цифрами), блок записи (WhatsApp с текстом «…записаться на {{ svc.title }}»), «Дополните ваш уход» (`svc.related` → карточки из `services`). Все цены — статический HTML.

Рендер прайса (Jinja):
```jinja
<div class="pricelist" data-pricelist>
  {% if sections|length > 1 %}
  <div class="pricelist__tabs" role="tablist">
    {% for sec in sections %}
      <button class="pricelist__tab{{ ' is-active' if loop.first }}" role="tab"
        aria-selected="{{ 'true' if loop.first else 'false' }}"
        data-tab="{{ loop.index0 }}">{{ sec.section or 'Цены' }}</button>
    {% endfor %}
  </div>
  {% endif %}
  {% for sec in sections %}
  <div class="pricelist__panel{{ ' is-active' if loop.first }}" data-panel="{{ loop.index0 }}">
    {% set combos = sec['items'] | selectattr('name','match','^КОМБО') | list %}
    {% set rows = sec['items'] | rejectattr('name','match','^КОМБО') | list %}
    {% if combos %}<div class="pricelist__combos">
      {% for c in combos %}<div class="combo"><div class="combo__name">{{ c.name }}</div><div class="combo__price">{{ c.price }}</div></div>{% endfor %}
    </div>{% endif %}
    <div class="pricelist__rows">
      {% for it in rows %}<div class="pricelist__row"><span class="pricelist__name">{{ it.name }}</span><span class="pricelist__price">{{ it.price }}</span></div>{% endfor %}
    </div>
  </div>
  {% endfor %}
</div>
```
(Подключить Jinja-тест `match` — добавить в `build.py`: `e.tests['match'] = lambda s, pat: re.match(pat, s) is not None`.)

- [ ] **Step 2: `service.css`** — стили интро-героя, карточек преимуществ, прайса (табы, комбо-карточки grid, строки с пунктиром, `font-variant-numeric:tabular-nums`), related-сетки. Адаптив.
- [ ] **Step 3: `price-tabs.js`** — переключение табов (ARIA `aria-selected`, показ/скрытие панелей). Без инлайна. Подключить через `{% block extra_js %}` только на странице услуги.
- [ ] **Step 4: Обновить `build.py`** — добавить тест `match` (Step 1). Rebuild.
- [ ] **Step 5: Verify** — открыть `/lazernaya-epilyaciya/` (две секции, табы, комбо), `/lpg-massazh/`, `/morpheus-8-rf-lifting/`: все цены на месте, табы переключаются, цифры выровнены, на мобиле читаемо.

### Task 5.2: privacy + наполнение content.yml на все услуги

**Files:**
- Create: `generator/templates/privacy.html.j2`
- Modify: `generator/data/content.yml` (заполнить 10 услуг + home полностью)

- [ ] **Step 1: privacy** — перенести текст политики из `page124964646.html` (адаптировать, бренд/домен Neva Beauty).
- [ ] **Step 2: Заполнить `content.yml`** для всех 10 услуг (title строго как в источнике, intro/benefits — на основе текстов старого сайта из footer-дампа), и `home` (categories/benefits/popular).
- [ ] **Step 3: Rebuild + verify** — все 12 страниц рендерятся без ошибок Jinja; пройти по каждой в браузере, проверить заголовки/интро/прайсы.

---

## Phase 6 — Изображения (Unsplash, локально)

### Task 6.1: Скрипт загрузки и привязка

**Files:**
- Create: `scripts/fetch_images.py`, `.env` (gitignored), `generator/data/images.yml`

- [ ] **Step 1: `.env`** (в workspace, gitignored) — ключи Unsplash:
```
UNSPLASH_ACCESS_KEY=KKwCA0kzmKr2cLpFQMR1cVqW8Keq-MYwKBfxAXKS6ms
```
(Secret key для скачивания не нужен — используется Access Key. Ключи НЕ коммитятся.)

- [ ] **Step 2: `images.yml`** — карта `имя_файла → поисковый запрос Unsplash` (hero, 4 категории, hero каждой услуги, related). Напр.:
```yaml
images:
  hero-bg: "spa beige minimal skincare"
  cat-apparat: "beauty device cosmetology"
  cat-epil: "laser hair removal smooth skin"
  epilyaciya-hero: "smooth skin legs spa"
  # ... по одному на каждый hero_image/category/popular
```

- [ ] **Step 3: `fetch_images.py`** — для каждого имени: запрос к Unsplash Search API (`/search/photos?query=...&orientation=...`), скачать первый результат в `vn.neva.beauty/assets/img/<name>.jpg`, сжать до разумной ширины (напр. через параметр `w=1600` в URL Unsplash), записать кредит автора в `assets/img/CREDITS.txt`. Читает ключ из `.env` (python-dotenv не обязателен — парсить вручную). Пропускать уже скачанные.

```python
import os, re, requests, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def access_key():
    for line in (ROOT/".env").read_text().splitlines():
        if line.startswith("UNSPLASH_ACCESS_KEY="): return line.split("=",1)[1].strip()
KEY = access_key()
IMG = ROOT/"vn.neva.beauty/assets/img"; IMG.mkdir(parents=True, exist_ok=True)
imgs = yaml.safe_load((ROOT/"generator/data/images.yml").read_text())["images"]
credits = []
for name, query in imgs.items():
    dst = IMG/f"{name}.jpg"
    if dst.exists(): print("skip", name); continue
    r = requests.get("https://api.unsplash.com/search/photos",
        params={"query":query,"per_page":1,"orientation":"landscape"},
        headers={"Authorization":f"Client-ID {KEY}"}, timeout=30).json()
    res = r["results"][0]
    url = res["urls"]["raw"] + "&w=1600&q=80&fm=jpg"
    dst.write_bytes(requests.get(url, timeout=60).content)
    credits.append(f"{name}: {res['user']['name']} (@{res['user']['username']}) — {res['links']['html']}")
    print("saved", name)
(IMG/"CREDITS.txt").write_text("\n".join(credits)+"\n")
```

- [ ] **Step 4: Запустить** — `. .venv/bin/activate && python scripts/fetch_images.py`
Expected: `saved hero-bg`, `saved cat-apparat`, … все файлы в `assets/img/`, создан `CREDITS.txt`.
- [ ] **Step 5: Привязка в шаблонах** — заменить плейсхолдеры на `<img src="/assets/img/{{ ... }}.jpg" width=.. height=.. loading="lazy" alt="...">` (hero первого экрана — без lazy, с приоритетом). Заполнить осмысленные `alt`.
- [ ] **Step 6: Verify** — все изображения грузятся локально (вкладка Network — нет запросов на unsplash.com), заданы размеры (нет сдвигов CLS), alt присутствуют.

---

## Phase 7 — SEO, мета-файлы, финальный QA

### Task 7.1: Мета-файлы и фавикон

**Files:**
- Create: `vn.neva.beauty/CNAME`, `robots.txt`, `sitemap.xml`, `404.html`, `favicon.svg`
- Modify: `generator/build.py` (генерация sitemap)

- [ ] **Step 1: `CNAME`** — одна строка `vn.neva.beauty`.
- [ ] **Step 2: `robots.txt`** — allow all + ссылка на sitemap.
- [ ] **Step 3: Генерация `sitemap.xml`** в build.py — все 12 URL (`https://vn.neva.beauty/...`), `lastmod` = дата сборки.
- [ ] **Step 4: `404.html`** — фирменная страница «не найдено» с навигацией домой (статическая, со встроенным минимальным хедером).
- [ ] **Step 5: `favicon.svg`** — простой монограмм-фавикон «N» в палитре.
- [ ] **Step 6: Verify** — sitemap содержит 12 url; CNAME присутствует; 404 открывается и стилизована.

### Task 7.2: Parity-тест цен (защита критичного требования)

**Files:**
- Create: `generator/check_prices.py`

- [ ] **Step 1: `check_prices.py`** — независимо разобрать **старые** страницы (тем же селектором) и **сгенерированные** `vn.neva.beauty/<slug>/index.html` (по классам `.pricelist__name/.pricelist__price/.combo__*`), собрать множества `(slug, normalized_name, normalized_price)` и проверить, что каждая цена старого сайта присутствует в новом. Нормализация — только схлопывание пробелов (значения не меняем).

```python
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup
from extract_prices import OLD, SLUG_FILE, parse_page, clean
NEW = Path(__file__).resolve().parent.parent / "vn.neva.beauty"

def old_set():
    s=set()
    for slug,f in SLUG_FILE.items():
        for sec in parse_page((OLD/f).read_text(encoding="utf-8")):
            for it in sec["items"]:
                s.add((slug, clean(it["name"]), clean(it["price"])))
    return s

def new_set():
    s=set()
    for slug in SLUG_FILE:
        soup=BeautifulSoup((NEW/slug/"index.html").read_text(encoding="utf-8"),"html.parser")
        # строки
        for row in soup.select(".pricelist__row"):
            n=row.select_one(".pricelist__name"); p=row.select_one(".pricelist__price")
            if n and p: s.add((slug, clean(n.text), clean(p.text)))
        # комбо
        for c in soup.select(".combo"):
            n=c.select_one(".combo__name"); p=c.select_one(".combo__price")
            if n and p: s.add((slug, clean(n.text), clean(p.text)))
    return s

old, new = old_set(), new_set()
missing = old - new
print(f"old={len(old)} new={len(new)} missing={len(missing)}")
for m in sorted(missing): print("  MISSING:", m)
sys.exit(1 if missing else 0)
```

- [ ] **Step 2: Запустить** — `cd generator && python check_prices.py`
Expected: `missing=0` и exit 0. Если есть MISSING — исправить шаблон/данные, **не** правя цены руками, и перезапустить build + тест.
- [ ] **Step 3: Commit-маркер** — отметить галочкой при `missing=0`.

### Task 7.3: A11y / адаптив / производительность — финальный проход

- [ ] **Step 1: A11y** — пройти по чеклисту: контраст ≥4.5:1 (проверить пары палитры), alt у всех картинок, aria-label у иконочных кнопок (бургер, соцсети), порядок заголовков h1→h6 (по одному h1 на страницу), focus-видимость, drawer закрывается с клавиатуры.
- [ ] **Step 2: Адаптив** — проверить 375 / 768 / 1024 / 1440: нет горизонтального скролла, тач-цели ≥44px, прайс читаем, hero не ломается; landscape на мобиле.
- [ ] **Step 3: reduced-motion** — включить системно, убедиться: ДНК-герой статичен, переходы убраны.
- [ ] **Step 4: Производительность** — изображения с размерами и lazy ниже первого экрана; шрифты `display=swap`; нет крупных сдвигов (CLS). Прогнать Lighthouse (если доступен) — отметить очевидные провалы.
- [ ] **Step 5: Verify** — зафиксировать результаты прохода, исправить найденное.

---

## Phase 8 — Подготовка к публикации GitHub Pages

### Task 8.1: git-репозиторий вывода и инструкция деплоя

**Files:**
- Modify: `vn.neva.beauty/` (git init здесь — это публикуемый репозиторий)

- [ ] **Step 1: Инициализировать git в выводе** — `cd vn.neva.beauty && git init && git add . && git commit -m "feat: Neva Beauty static site"` (CNAME, .gitignore уже на месте; `.superpowers/` исключён).
- [ ] **Step 2: Инструкция пользователю** (вывести в чат, не выполнять самому без подтверждения): создать репозиторий на GitHub, `git remote add origin …`, `git push`, включить Pages (branch `main`, `/root`), указать кастомный домен `vn.neva.beauty`, прописать DNS (CNAME/ALIAS на `<user>.github.io`). Напомнить про HTTPS-галочку.
- [ ] **Step 3: Финальный verify** — локальный прогон `python3 -m http.server -d vn.neva.beauty 8080`, клик по всем 12 страницам, всем CTA (открывают WhatsApp с текстом), соцссылкам.

---

## Self-Review (выполнено при написании)

- **Покрытие спека:** палитра/токены (Ph2), типографика (head/base), структура 12 URL (build.py, Ph3–5), навигация+drawer (3.2–3.3), главная 8 секций (4.1), ДНК-герой (4.2), шаблон услуги + прайс табы/комбо (5.1), контакты дословно (site.yml), цены дословно + parity-тест (Ph1, 7.2), изображения локально + ключи вне git (Ph6), запись→WhatsApp (header/service), SEO/мета (7.1), a11y/адаптив/reduced-motion (7.3), деплой (Ph8). Все требования спека имеют задачу.
- **Плейсхолдеры:** содержательные шаги содержат код/команды; «заполнить content.yml на все услуги» — это данные по явному образцу (Task 5.2), не код-плейсхолдер.
- **Согласованность типов:** классы прайса (`.pricelist__row/__name/__price`, `.combo/__name/__price`) совпадают между `service.html.j2` (5.1) и `check_prices.py` (7.2); `parse_page`/`SLUG_FILE`/`clean` переиспользуются из `extract_prices.py`.
