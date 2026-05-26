# Инструкции для Claude Code — vn.neva.beauty

Сайт центра красоты Neva Beauty (Дананг, Вьетнам).  
Чистая статика, деплой через **GitHub Pages** из директории `site/`.

---

## Бренд-кит

Дизайн-фундамент управляется репозиторием `neva-brand`:  
GitHub: `https://github.com/jw-git-hub/neva-brand`  
Локально: `/home/john_wick/projects/neva-brand/`

Перед любой UI-правкой:

1. Прочитать `neva-brand/BRAND.md` — визуальный язык, тон, принципы.
2. Прочитать `neva-brand/CLAUDE.md` — правила работы с китом, структура, запреты.

Синхронизировать фундамент при необходимости:

```bash
./sync-brand.sh   # из корня этого репозитория
```

> **Важно:** `neva-brand` — приватный репозиторий; `./sync-brand.sh` требует токен GitHub в `~/.git-credentials` (иначе клон упадёт с ошибкой авторизации).

### Kit-managed файлы — не трогать напрямую

Следующие файлы обновляются только через `sync-brand.sh`. Ручная правка будет
перезаписана при следующей синхронизации:

```
site/assets/css/tokens.css   fonts.css   reset.css   base.css   layout.css
site/assets/css/components/breadcrumbs.css   chip.css   faq.css
site/assets/fonts/*.woff2
```

Текущая версия кита: `site/assets/css/.brand-version`.

---

## Стек и архитектура

- **Статика:** HTML + CSS + vanilla JS. Без фреймворков, без шага сборки.
- **Деплой:** GitHub Pages (директория `site/`); CI через GitHub Actions — файл `.github/workflows/pages.yml` создаётся в Task 2.
- **14 страниц:** главная, 10 процедур (слаги = старые Tilda-URL для SEO), контакты, приватность, 404.
- **Запись:** кнопки-ссылки на WhatsApp / Telegram / Instagram. Бэкенда нет.

---

## Правила кода

**Разделение технологий:**
- HTML — только разметка и семантика.
- CSS — через `<link>` в `<head>`.
- JS — через `<script src defer>` или `type="module"` перед `</body>`.

**Запрещено:**
- Инлайн `style=""`.
- `<script>…</script>` с кодом внутри HTML.
- `on*`-атрибуты (`onclick`, `onchange` и т.д.).
- `element.style.property` в JS — переключать только CSS-классы.
- Сырые hex/px/названия шрифтов в CSS — только `var(--…)`.
- Третья гарнитура или вторая акцентная краска.
- Внешние LLM-API (Anthropic/OpenAI SDK) — вся ИИ-работа через сабагентов сессии.

**Именование:**
- CSS-классы: BEM (`.block__element--modifier`).
- JS-файлы: одна зона ответственности; общие утилиты — в `assets/js/`.
- Компонентный CSS — в `assets/css/components/`; только уникальные стили.

---

## Адаптивность и производительность

- Mobile-first. Приоритет тестирования: 360 × 640 → 768 → 1280.
- Брейкпоинты: 480 / 768 / 1024 / 1440 px.
- Тач-таргеты ≥ 44 × 44 px.
- `<img>` — `loading="lazy"` (кроме hero), `webp`/`avif`, `width` + `height` обязательны.
- Core Web Vitals: LCP < 2.5 s, CLS < 0.1, INP < 200 ms.

---

## SEO

- Уникальные `<title>` и `<meta description>` на каждой странице.
- Open Graph + Twitter Cards.
- JSON-LD: `BeautySalon` (контакты), `BreadcrumbList` на внутренних страницах.
- Слаги файлов совпадают со старыми Tilda-URL (SEO-непрерывность).

---

## Методология

Основной flow — **superpowers**: `brainstorming` → `writing-plans` →
`executing-plans` / `subagent-driven-development` → `requesting-code-review` /
`receiving-code-review` → `verification-before-completion`.  
Для багов — `systematic-debugging`. Перед UI-правкой — `frontend-design`.

---

## Verify-гейт

Перед коммитом любой UI/CSS-правки прогнать из корня репозитория:

```bash
./check-design-tokens.sh
```

Страж следит, что начертания заданы токенами кита (`var(--weight-*)`), а не
магическими числами `font-weight: 600`. Любой хардкод `font-weight` в
`site/assets/css/**` (кроме `fonts.css`) валит гейт с ненулевым кодом — это
дрейф от бренд-кита. Чинить токенизацией на `--weight-regular/medium/semibold/bold`
(см. `tokens.css`), а не правкой числа. Гейт обязан быть зелёным до `git push`.
