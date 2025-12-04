#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv 未安装，请先安装 uv 以使用 Ruff 格式化与检查。" >&2
  exit 1
fi

# 格式化 + Lint Python 代码
uv run ruff format .
uv run ruff check . --fix

# 格式化 Markdown 代码
markdownlint . --fix -c .github/.markdownlint.json
autocorrect --fix *.md **/*.md
