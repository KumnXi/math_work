#!/usr/bin/env bash
# 启动傻瓜建模网页（仅本机 127.0.0.1:8000）
# 用法：bash scripts/run_web.sh  [PORT]
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PORT="${1:-8000}"

PYTHON_EXE="$ROOT/.venv/Scripts/python.exe"
if [ ! -f "$PYTHON_EXE" ]; then
  echo "未找到 $PYTHON_EXE" >&2
  echo "请先运行: bash scripts/setup_env.sh" >&2
  exit 1
fi

# 控制台 GBK → 强制 UTF-8，保证中文日志不乱码
export PYTHONIOENCODING=utf-8

echo "启动傻瓜建模网页: http://127.0.0.1:${PORT}"
exec "$PYTHON_EXE" -m uvicorn webapp.app:app --host 127.0.0.1 --port "$PORT"
