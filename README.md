# vn.neva.beauty

Сайт-визитка центра красоты **Neva Beauty** в Дананге (Вьетнам).  
Аппаратная косметология — лазерная эпиляция, LPG-массаж, RF-лифтинг и другие процедуры.

Аудитория — русскоязычные. Язык сайта — только русский.

---

## Структура

```
site/                  ← публикуемый корень (GitHub Pages)
  index.html           ← главная
  *.html               ← страницы процедур (слаги = старые Tilda-URL)
  contacts.html
  privacy.html
  404.html
  CNAME                ← vn.neva.beauty
  robots.txt
  sitemap.xml
  favicon.svg
  assets/
    css/               ← фундамент (kit-managed) + компоненты vn
      components/
    fonts/             ← 4 woff2 (Manrope + Lora, kit-managed)
    js/
      components/
    images/
.github/workflows/     ← CI: деплой на GitHub Pages (workflow добавляется в Task 2)
sync-brand.sh          ← синхронизация бренд-кита
```

---

## Бренд-кит

Дизайн-фундамент подключён из репозитория [`neva-brand`](https://github.com/jw-git-hub/neva-brand) через скрипт `sync-brand.sh`.

Он копирует в `site/assets/`:
- `css/tokens.css`, `fonts.css`, `reset.css`, `base.css`, `layout.css` — фундаментный CSS;
- `css/components/breadcrumbs.css`, `chip.css`, `faq.css` — кросс-сайтовые компоненты;
- `fonts/*.woff2` — 4 шрифтовых файла (Manrope + Lora, latin + cyrillic).

Синхронизация:

```bash
./sync-brand.sh          # подтянуть актуальный main кита
./sync-brand.sh v1.2.0   # зафиксировать конкретную версию
```

После запуска проверить `git diff` и закоммитить изменения.  
**Не редактировать** kit-managed файлы напрямую — только через `neva-brand`.

Текущая версия кита: `site/assets/css/.brand-version`.

---

## Деплой — GitHub Pages

- Ветка `main` → GitHub Actions публикует `site/` как Pages-артефакт (файл `.github/workflows/pages.yml` создаётся в Task 2).
- Кастомный домен: `vn.neva.beauty` (файл `site/CNAME`).
- DNS: CNAME-запись `vn` → `jw-git-hub.github.io`.
- HTTPS принудительно включён в настройках репозитория.
- Сборка отсутствует — выкладывается готовая статика.

---

## Разработка

Перед правкой UI — прочитать `neva-brand/BRAND.md` и `neva-brand/CLAUDE.md`.  
Инструкция для Claude Code — в `CLAUDE.md` этого репозитория.
