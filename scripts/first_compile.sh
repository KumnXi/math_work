#!/usr/bin/env bash
# 预热 CUMCMThesis 模板：首次编译 example.tex，触发 MiKTeX 自动装齐宏包
# 用法：bash scripts/first_compile.sh
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$PROJECT_DIR/templates/CUMCMThesis"
LATEXMK="${LATEXMK_EXE:-D:/MiKTeX/miktex/bin/x64/latexmk.exe}"

if [ ! -f "$TEMPLATE_DIR/cumcmthesis.cls" ]; then
    echo "!! 模板不存在，先运行 bash scripts/init_project.sh"
    exit 1
fi

echo "==> 预热编译 example.tex（首次需联网装宏包，较慢）..."
cd "$TEMPLATE_DIR"
"$LATEXMK" -xelatex -interaction=nonstopmode -halt-on-error example.tex 2>&1 | tail -15

if [ -f "$TEMPLATE_DIR/example.pdf" ]; then
    echo "==> 模板预热成功，已产出 example.pdf"
else
    echo "!! 编译可能仍有问题，请查看上方输出"
    exit 1
fi
