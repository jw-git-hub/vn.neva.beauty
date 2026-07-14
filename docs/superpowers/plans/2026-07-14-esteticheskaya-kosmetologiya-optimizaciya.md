# «Эстетическая косметология и уход» — оптимизация: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Применить оба промта (SEO + AI/GEO) к последней услуге `/esteticheskaya-kosmetologiya-i-uhod/` — переписать `seo_desc` и `intro` в answer-first и добавить блок из 5 реальных Q&A, правя только `content.yml`.

**Architecture:** Статический генератор Python + Jinja2. Структурный слой (крошки, `Service`+`AggregateOffer`, блок FAQ, подстановка мессенджеров) уже готов в `service.html.j2` / `build.py` / `schema.py`. Работа **чисто контентная** — один узел `services.esteticheskaya-kosmetologiya-i-uhod` в `generator/data/content.yml`. Шаблоны и Python не трогаем.

**Tech Stack:** Python 3, PyYAML, Jinja2, markupsafe. Проверка — `generator/build.py` (рендер) + `generator/check_prices.py` (паритет цен). Юнит-тестов в проекте нет; тест-цикл = запуск сборки + сторожа цен + ассерты по отрендеренному HTML/JSON-LD.

## Global Constraints

Копируются дословно из спека `docs/superpowers/specs/2026-07-14-esteticheskaya-kosmetologiya-optimizaciya-design.md`. Требования каждой задачи неявно включают этот раздел.

- **Не менять цены** — диапазон в schema считается автоматически из `prices.json`.
- **Не выдумывать факты** — только реальные процедуры прайса и формулировки benefits. Никаких `Review`/`AggregateRating` (отзывов нет).
- **Не менять URL** `/esteticheskaya-kosmetologiya-i-uhod/`.
- Пользовательский контент — на русском; технические ключи schema.org/HTML — английские.
- **seo_title — без изменений** (56 симв., уже в 50–60).
- **seo_desc — 140–160 симв.**
- **Конкретика процедур — гибрид:** явно называем HydraFacial, карбокситерапию, чистку лица; пилинги/маски/аппаратные — обобщённо по типам.
- **Число процедур/периодичность — «индивидуально на консультации»,** без выдуманных чисел и пакетов.
- **Позиционирование — уход за кожей лица** (весь прайс лицевой; по телу не позиционируем).
- **Крошки — без средней:** `Главная / Эстетическая косметология и уход` (одиночная категория).
- **Граф JSON-LD — 6 узлов;** `AggregateOffer`: `lowPrice 200000` / `highPrice 2000000` / `offerCount 13` / `priceCurrency VND`; в `Service.description` и `Answer.text` нет HTML-тегов.

## Pre-flight: грязное рабочее дерево (прочитать до коммитов)

В рабочем дереве есть **незакоммиченные правки прошлой сессии**: `generator/data/content.yml`, `generator/data/prices.json`, `generator/check_prices.py`, `generator/extract_prices.py` (удалён), HTML четырёх услуг (`fotoomolozhenie-m22`, `morpheus-8-rf-lifting`, `udalenie-tatuirovok-lazerom`, `udalenye-permanentnogo-makiyazha`), три спека `2026-07-13-*`.

Следствие: `git add generator/data/content.yml` в задачах ниже **застейджит и правки прошлой сессии в этом файле** (нельзя изолировать без интерактивного `git add -p`, который в среде недоступен). Перед коммитом Задачи 1 **согласовать с пользователем** один из вариантов:
- (A) закоммитить прошлую работу отдельно/раньше (или застейджить её самому пользователю), затем выполнять план — коммиты плана останутся чистыми; **или**
- (B) осознанно объединить: `content.yml` и пересобранный HTML уедут вместе с завершёнными страницами прошлой сессии.

Не выбирать молча — это решение пользователя. Задача 2 (TODO/журнал) правит отдельный файл и от этого не зависит.

---

### Task 1: Контент услуги в `content.yml` (seo_desc + intro + faq)

**Files:**
- Modify: `generator/data/content.yml` (узел `services.esteticheskaya-kosmetologiya-i-uhod`, сейчас строки ~406–421)
- Regenerated (автоматически сборкой): `vn.neva.beauty/esteticheskaya-kosmetologiya-i-uhod/index.html`

**Interfaces:**
- Consumes: `build.py` читает `svc["intro"]` → `schema.service_node(..., description=intro)` (чистится `_plain`) и `svc["faq"]` → `render_faq_contacts` (подстановка `{whatsapp}`/`{telegram}`/`{instagram}` из `site.yml`) → `schema.faq_node` (чистится `_plain`). Ключ `faq` активирует guard `{% if svc.faq %}` в `service.html.j2`.
- Produces: страница `/esteticheskaya-kosmetologiya-i-uhod/index.html` с 6-узловым графом (…+`Service`+`FAQPage`) и видимым блоком FAQ.

- [ ] **Step 1: Зафиксировать «зелёный» базовый прогон**

Убедиться, что генератор и сторож цен работают ДО правок (baseline).

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
python3 generator/build.py && python3 generator/check_prices.py
```
Expected: сборка без ошибок; последняя строка `PRICE PARITY OK`.

- [ ] **Step 2: Заменить `seo_desc`**

В `generator/data/content.yml`, узел `services.esteticheskaya-kosmetologiya-i-uhod`.

Было:
```yaml
    seo_desc: "Чистки, пилинги, HydraFacial и карбокситерапия для здоровой кожи в центре красоты Neva Beauty, Дананг."
```
Стало:
```yaml
    seo_desc: "Эстетический уход за кожей лица в Neva Beauty (Дананг): чистки, пилинги, HydraFacial и карбокситерапия. Программу подбирают индивидуально, приём по записи."
```
(155 символов — в диапазоне 140–160.)

- [ ] **Step 3: Заменить `intro` (answer-first; идёт и в hero, и в `Service.description`)**

Было:
```yaml
    intro: >
      Подарите своей коже безупречный вид и надёжную защиту.
      Комплексные эстетические программы Neva Beauty — от глубоких чисток до пилингов и карбокситерапии —
      эффективно восстанавливают защитный барьер и глубоко очищают ткани, нейтрализуя последствия тропического климата Дананга.
```
Стало:
```yaml
    intro: >
      Эстетическая косметология и уход в центре красоты Neva Beauty (Дананг) —
      программы профессионального ухода за кожей лица: чистки, профессиональные
      пилинги, HydraFacial и карбокситерапия, а также уходовые маски и аппаратные
      процедуры. Они глубоко очищают кожу, восстанавливают её защитный барьер и
      возвращают ровный тон и сияние, нейтрализуя последствия тропического солнца
      и влажности Дананга. Программу и число процедур подбирают индивидуально под
      тип и состояние кожи. Приём по записи.
```

- [ ] **Step 4: Добавить ключ `faq` (после `related:` — последний ключ узла)**

Вставить блок ровно с отступом 4 пробела на уровне ключа `faq:` (как у соседних услуг). Вопросы — двойные кавычки; ответы с HTML-ссылками — одинарные (плейсхолдеры мессенджеров оставить как есть, их подставит `build.py`):
```yaml
    faq:
      - q: "Какие процедуры входят в эстетический уход в Neva Beauty?"
        a: "Эстетическая косметология и уход в Neva Beauty (Дананг) включает чистку лица и ультразвуковую чистку, профессиональные пилинги, HydraFacial, карбокситерапию, а также уходовые маски и аппаратные процедуры (RF- и ультразвуковую терапию). Конкретную программу подбирают под тип и состояние кожи. Полный список процедур и цены — в разделе «Цены» на этой странице."
      - q: "Больно ли делать процедуры ухода за лицом?"
        a: "Уходовые процедуры в Neva Beauty (Дананг) выполняют по атравматичным методикам, поэтому большинство переносится комфортно и без долгого восстановления. Ощущения зависят от процедуры: чистка и пилинги ощущаются заметнее мягких уходов, а HydraFacial и маски проходят деликатно. Интенсивность подбирают индивидуально под чувствительность кожи."
      - q: "Как часто нужно делать эстетический уход?"
        a: "Число процедур и периодичность ухода за кожей лица в Neva Beauty (Дананг) подбирают индивидуально на консультации — в зависимости от типа, состояния кожи и задачи (очищение, ровный тон, упругость). Часть программ даёт видимый результат уже после первой процедуры, а регулярный уход помогает поддерживать кожу в тонусе. Точный план составляет косметолог после осмотра."
      - q: "Сколько стоит эстетический уход в Дананге?"
        a: 'Стоимость зависит от процедуры: отдельно тарифицируются чистки, пилинги, HydraFacial, карбокситерапия и уходовые маски, а усиления (RF- или ультразвуковая терапия, сыворотка, альгинатная маска) добавляются к базовому уходу. Актуальные цены во вьетнамских донгах (đ) указаны в разделе «Цены» на этой странице. Смежные аппаратные методы омоложения — <a href="/fotoomolozhenie-m22/">фотоомоложение M22</a> и <a href="/morpheus-8-rf-lifting/">игольчатый RF-лифтинг Morpheus 8</a> — тарифицируются отдельно.'
      - q: "Как записаться на уход в Neva Beauty?"
        a: 'Записаться на эстетический уход в центр красоты Neva Beauty (Дананг) можно через <a href="{whatsapp}" target="_blank" rel="noopener">WhatsApp</a>, <a href="{telegram}" target="_blank" rel="noopener">Telegram</a> или <a href="{instagram}" target="_blank" rel="noopener">Instagram</a>. Приём ведётся по предварительной записи, обслуживание — на русском и английском языках.'
```

- [ ] **Step 5: Пересобрать сайт и прогнать сторож цен**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
python3 generator/build.py && python3 generator/check_prices.py
```
Expected: сборка без ошибок (в выводе есть строка `→ vn.neva.beauty/esteticheskaya-kosmetologiya-i-uhod/index.html`); последняя строка `PRICE PARITY OK`.

- [ ] **Step 6: Проверить отрендеренную страницу (это и есть тест задачи)**

Записать скрипт проверки и запустить его.

Create: `/tmp/verify_uhod.py`
```python
import json, re, pathlib, yaml

root = pathlib.Path(".")
html = (root / "vn.neva.beauty/esteticheskaya-kosmetologiya-i-uhod/index.html").read_text(encoding="utf-8")

# --- JSON-LD ---
m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
graph = json.loads(m.group(1))["@graph"]
types = [n["@type"] for n in graph]
assert len(graph) == 6, f"узлов не 6: {types}"

svc = next(n for n in graph if n["@type"] == "Service")
assert "<" not in svc["description"], "в Service.description есть теги"
off = svc["offers"]
assert off["priceCurrency"] == "VND"
assert off["lowPrice"] == 200000 and off["highPrice"] == 2000000 and off["offerCount"] == 13, off

faq = next(n for n in graph if n["@type"] == "FAQPage")
assert len(faq["mainEntity"]) == 5, "в FAQPage не 5 вопросов"
assert all("<" not in q["acceptedAnswer"]["text"] for q in faq["mainEntity"]), "в Answer.text есть теги"

bc = next(n for n in graph if n["@type"] == "BreadcrumbList")
names = [i["name"] for i in bc["itemListElement"]]
assert names == ["Главная", "Эстетическая косметология и уход"], f"крошки не те: {names}"

# --- HTML ---
assert html.count("<h1") == 1, "не ровно один <h1>"
assert html.count("<details") == 5, "не ровно 5 <details>"
assert '<details class="faq__item" open>' in html, "первый <details> не open"
for ph in ("{whatsapp}", "{telegram}", "{instagram}"):
    assert ph not in html, f"несведённый плейсхолдер {ph}"

# --- seo_desc длина + присутствие ---
c = yaml.safe_load((root / "generator/data/content.yml").read_text(encoding="utf-8"))
d = c["services"]["esteticheskaya-kosmetologiya-i-uhod"]["seo_desc"]
assert 140 <= len(d) <= 160, f"seo_desc {len(d)} симв. — вне 140–160"
assert d in html, "seo_desc не попал в HTML"

print("PAGE CHECKS OK — 6 узлов, крошки без средней, 5 FAQ, offer 200000..2000000/13, seo_desc", len(d))
```
Run:
```bash
cd "$(git rev-parse --show-toplevel)" && python3 /tmp/verify_uhod.py
```
Expected: `PAGE CHECKS OK — 6 узлов, крошки без средней, 5 FAQ, offer 200000..2000000/13, seo_desc 155`

- [ ] **Step 7: Коммит**

Сначала выполнить решение из раздела «Pre-flight» (согласовать с пользователем изоляцию прошлой сессии). Затем:
```bash
cd "$(git rev-parse --show-toplevel)"
git add generator/data/content.yml vn.neva.beauty/esteticheskaya-kosmetologiya-i-uhod/index.html
git commit -m "$(cat <<'EOF'
SEO/GEO: страница «Эстетическая косметология и уход»

Answer-first intro (= Service.description), seo_desc → 155 симв.,
блок из 5 реальных Q&A → FAQPage. Гибрид-конкретика процедур, числа
не выдуманы. Крошки без средней (одиночная категория). PRICE PARITY OK.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014eKLroA26sNfPjzwYFmyZS
EOF
)"
```
Expected: коммит создан; в diff — `content.yml` (узел услуги) и пересобранный HTML страницы.

---

### Task 2: Отметить TODO + запись в журнал

**Files:**
- Modify: `Временные скриншоты/TODO-optimization.md` (строка услуги + «Журнал работ»)

**Interfaces:**
- Consumes: результат Задачи 1 (страница готова, проверки пройдены).
- Produces: закрытая строка `[x]` — последняя услуга; оптимизация услуг завершена.

- [ ] **Step 1: Отметить строку услуги `[ ]` → `[x]`**

В `Временные скриншоты/TODO-optimization.md`.

Было:
```markdown
- [ ] Эстетическая косметология и уход (услуга = категория) — `/esteticheskaya-kosmetologiya-i-uhod/`
```
Стало:
```markdown
- [x] Эстетическая косметология и уход (услуга = категория) — `/esteticheskaya-kosmetologiya-i-uhod/`
```

- [ ] **Step 2: Добавить запись в «Журнал работ» (одна строка, в конец журнала)**

Вставить последней строкой раздела «## Журнал работ»:
```markdown
- 2026-07-13 — **Услуга «Эстетическая косметология и уход» `/esteticheskaya-kosmetologiya-i-uhod/` готова** (оба промта) — **последняя услуга, оптимизация услуг завершена**. Контент правился только в `content.yml` (шаблон `service.html.j2` структурный). Единственная «зонтичная» страница (меню процедур, а не один метод); одиночная категория → рендерится страница-услуга, крошки без средней. Решения брейншторма: (1) **гибрид-конкретика** — явно названы HydraFacial, карбокситерапия, чистка лица; пилинги/маски/аппаратные — обобщённо по типам; (2) **число процедур/периодичность — индивидуально на консультации**, курсовых пакетов в прайсе нет, чисел не выдумываем; (3) **позиционирование — уход за кожей лица** (прайс полностью лицевой). seo_title без изменений (56 симв.); seo_desc 102→155 симв. Answer-first intro (он же `Service.description`, чистый текст): программы ухода за кожей лица (чистки, профессиональные пилинги, HydraFacial, карбокситерапия, уходовые маски, аппаратные процедуры) → очищение, восстановление барьера, ровный тон и сияние. Блок FAQ — 5 реальных Q&A: что входит (реальные процедуры прайса) / больно ли (НЕ плоское «безболезненно» — атравматичные методики, но чистки/пилинги ощущаются заметнее мягких уходов; entity-consistent) / как часто (индивидуально на консультации, регулярный поддерживающий уход) / сколько стоит (процедуры + усиления-«+» из прайса; ссылки на `/fotoomolozhenie-m22/` и `/morpheus-8-rf-lifting/`) / как записаться (WhatsApp/Telegram/Instagram из `site.yml`). Проверено: build OK, `PRICE PARITY OK`, JSON-LD валиден (6 узлов: Organization+BeautySalon+WebSite+BreadcrumbList+Service(AggregateOffer low 200000 / high 2000000 / count 13 / VND)+FAQPage, без тегов в description/answer, provider→#business, areaServed=Da Nang), крошки `Главная / Эстетическая косметология и уход` (без средней), ровно 1×`<h1>`, 5 `<details>` (первый open), плейсхолдеры сведены, seo_desc 155 симв. Дизайн-спек: `docs/superpowers/specs/2026-07-14-esteticheskaya-kosmetologiya-optimizaciya-design.md`.
```
(Дату в начале строки при желании заменить на фактический день выполнения; журнал ведёт даты по дню записи.)

- [ ] **Step 3: Коммит**

```bash
cd "$(git rev-parse --show-toplevel)"
git add "Временные скриншоты/TODO-optimization.md"
git commit -m "$(cat <<'EOF'
TODO: закрыта услуга «Эстетическая косметология и уход» — оптимизация услуг завершена

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014eKLroA26sNfPjzwYFmyZS
EOF
)"
```
Expected: коммит создан; строка услуги помечена `[x]`, добавлена запись в журнал.

---

## Self-Review (проведён при написании плана)

- **Покрытие спека:** seo_title (без изменений — Задача 1 Global Constraints) · seo_desc 155 (Task 1 Step 2) · answer-first intro/Service.description (Step 3) · 5 Q&A/FAQPage (Step 4) · гибрид-конкретика (Steps 3–4) · честность «больно ли» и «как часто» (Step 4 Q2/Q3) · крошки без средней (Step 6 assert) · 6 узлов + AggregateOffer 200000/2000000/13 (Step 6 assert) · нет тегов в description/answer (Step 6 assert) · PRICE PARITY (Step 5) · TODO `[x]` + журнал (Task 2). Пробелов нет.
- **Плейсхолдеры:** реальный контент во всех шагах; строковые `{whatsapp}`/`{telegram}`/`{instagram}` в YAML — намеренные (подставляются `build.py`), не заглушки плана.
- **Согласованность типов/имён:** slug `esteticheskaya-kosmetologiya-i-uhod`, числа AggregateOffer `200000/2000000/13`, набор узлов `6` — совпадают в спеке, шагах и ассертах.
