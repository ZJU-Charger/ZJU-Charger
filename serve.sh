#!/bin/bash
# ZJU Charger 启动脚本

set -e

echo "=========================================="
echo "  ZJU Charger 服务器启动中..."
echo "=========================================="

# 1. 检查 uv 是否安装
if ! command -v uv >/dev/null 2>&1; then
  echo "❌ 错误: uv 未安装" >&2
  echo "请参考 https://docs.astral.sh/uv/getting-started/ 进行安装。" >&2
  exit 1
fi

echo "✅ uv 包管理器已安装"

# 2. 同步依赖
echo ""
echo "📦 同步项目依赖..."
uv sync --frozen

# 3. 检查 SQLite3 支持（Python 内置）
echo ""
echo "🔍 检查 SQLite3 支持..."
if uv run python -c "import sqlite3; print('✅ SQLite3 支持正常')" 2>/dev/null; then
  :
else
  echo "❌ 错误: SQLite3 不可用" >&2
  echo "SQLite3 是 Python 标准库的一部分，应该是内置的。" >&2
  exit 1
fi

# 4. 初始化数据库（如果需要）
echo ""
echo "🗄️  初始化数据库..."
uv run python -c "
from db import initialize_db_config
import sys

try:
    if initialize_db_config():
        print('✅ 数据库初始化成功')
    else:
        print('❌ 数据库初始化失败')
        sys.exit(1)
except Exception as e:
    print(f'❌ 数据库初始化错误: {e}')
    sys.exit(1)
"

# 5. 启动服务器
echo ""
echo "=========================================="
echo "🚀 启动 API 服务器..."
echo "=========================================="
echo ""

uv run python -m server.run_server "$@"
