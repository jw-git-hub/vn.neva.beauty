#!/usr/bin/env bash
# sync-brand.sh — подтянуть бренд-кит Neva Beauty в этот сайт.
#
# Запуск из корня сайт-репозитория:
#     ./sync-brand.sh [ref]
#   ref — ветка или тег кита (по умолчанию: main)
#
# Скрипт НЕ коммитит изменения — после него проверьте `git diff` и
# закоммитьте сами. Файлы фундамента после синхронизации становятся
# kit-managed: правьте их в репозитории neva-brand, не здесь.
set -euo pipefail

BRAND_REPO="https://github.com/jw-git-hub/neva-brand.git"
BRAND_REF="${1:-main}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSS_DIR="$SCRIPT_DIR/site/assets/css"
FONTS_DIR="$SCRIPT_DIR/site/assets/fonts"
COMPONENTS_DIR="$CSS_DIR/components"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "→ Клонирую бренд-кит ($BRAND_REF)…"
# `-c credential.helper=store` — приватный репозиторий: токен берётся из
# ~/.git-credentials (свежий клон не наследует local-config сайта).
git clone --depth 1 --branch "$BRAND_REF" \
  -c credential.helper=store \
  "$BRAND_REPO" "$TMP_DIR/neva-brand"
KIT="$TMP_DIR/neva-brand/kit"

echo "→ Фундаментный CSS…"
mkdir -p "$CSS_DIR"
cp "$KIT"/css/*.css "$CSS_DIR/"

echo "→ Шрифты…"
mkdir -p "$FONTS_DIR"
cp "$KIT"/fonts/*.woff2 "$FONTS_DIR/"

echo "→ Общие компоненты…"
mkdir -p "$COMPONENTS_DIR"
cp "$KIT"/components/*.css "$COMPONENTS_DIR/"

VERSION="$(cat "$TMP_DIR/neva-brand/VERSION")"
echo "$VERSION" > "$CSS_DIR/.brand-version"

echo "✓ Бренд-кит v$VERSION синхронизирован."
echo "  Проверьте изменения:  git diff"
