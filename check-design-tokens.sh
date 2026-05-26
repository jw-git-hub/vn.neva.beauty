#!/usr/bin/env bash
set -euo pipefail
CSS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/site/assets/css"
hits="$(grep -rnE 'font-weight:[[:space:]]*[0-9]' "$CSS_DIR" \
  --include='*.css' --exclude='fonts.css' || true)"
if [ -n "$hits" ]; then
  echo "✗ Хардкод font-weight (используйте var(--weight-*)):"; echo "$hits"; exit 1
fi
echo "✓ Начертания на токенах — хардкод font-weight не найден."
