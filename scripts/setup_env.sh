#!/usr/bin/env bash
# 初始化 Python 环境：创建纯 pip venv 并安装完整科学计算栈
#
# 背景：
#   - 机器上 python 是 Windows Store 假别名，不可用 → 用 Anaconda 的 python 创建 venv
#   - Anaconda 的 site-packages 当前用户不可写 → pip 会退回 user-site
#   - 且 Anaconda 的 scipy/matplotlib 与 ortools 原生 DLL 冲突(WinError 127)
#   → 解法：纯 pip venv（不用 --system-site-packages），全部库统一从 pip 装，
#     消除 DLL 冲突。首次需下载 ~400MB，用清华镜像较快。
#
# 用法：bash scripts/setup_env.sh
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASE_PY="${ANACONDA_PYTHON:-D:/Anaconda3/python.exe}"
VENV_PY="$PROJECT_DIR/.venv/Scripts/python.exe"

echo "==> 创建/检查 venv ..."
if [ ! -f "$VENV_PY" ]; then
    "$BASE_PY" -m venv "$PROJECT_DIR/.venv"
    echo "   venv 已创建"
else
    echo "   venv 已存在"
fi

echo "==> 安装完整科学计算栈 ..."
"$VENV_PY" -m pip install numpy pandas scipy matplotlib sympy scikit-learn python-docx ortools==9.15.6755 PyMuPDF

echo "==> 自检（验证无 DLL 冲突，任意 import 顺序）..."
"$VENV_PY" -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')
# 按最容易触发 DLL 冲突的顺序导入：先 pandas/scipy，再 ortools
import pandas, numpy, scipy, matplotlib, sympy, sklearn, docx, ortools, fitz
print('  pandas', pandas.__version__)
print('  numpy', numpy.__version__)
print('  scipy', scipy.__version__)
print('  matplotlib', matplotlib.__version__)
print('  ortools', ortools.__version__)
print('  PyMuPDF', fitz.__doc__.strip().split(chr(10))[0] if fitz.__doc__ else 'OK')
print('环境就绪，无 DLL 冲突。')
"
