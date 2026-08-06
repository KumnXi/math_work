#!/usr/bin/env bash
# 初始化项目：git init + 写 machine.json + 克隆 CUMCMThesis 模板
# 用法：bash scripts/init_project.sh
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "==> git init ..."
git init -q 2>/dev/null || echo "   已初始化或忽略"

echo "==> 检查 machine.json ..."
if [ ! -f config/machine.json ]; then
    /d/Anaconda3/python.exe - <<'PY'
import json, pathlib, shutil
d = {
    "PYTHON_EXE": str(pathlib.Path(".venv/Scripts/python.exe").resolve()),
    "LATEXMK_EXE": "D:\\MiKTeX\\miktex\\bin\\x64\\latexmk.exe",
    "XELATEX_EXE": "D:\\MiKTeX\\miktex\\bin\\x64\\xelatex.exe",
    "TEMPLATE_DIR": str(pathlib.Path("templates/CUMCMThesis").resolve()),
}
pathlib.Path("config").mkdir(exist_ok=True)
pathlib.Path("config/machine.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("   已生成 config/machine.json")
PY
else
    echo "   已存在"
fi

echo "==> 获取 CUMCMThesis 模板 ..."
if [ ! -f templates/CUMCMThesis/cumcmthesis.cls ]; then
    mkdir -p templates/CUMCMThesis
    cd templates/CUMCMThesis
    # 方案一：git clone（smart HTTP 在某些网络下会卡死）
    timeout 60 git clone --depth 1 https://github.com/latexstudio/CUMCMThesis.git . 2>/dev/null || {
        echo "   git clone 超时/失败，改用 zip 下载..."
        curl -sL --max-time 300 -o cumcm.zip "https://codeload.github.com/latexstudio/CUMCMThesis/zip/refs/heads/master"
        unzip -q -o cumcm.zip && mv CUMCMThesis-master/* . && mv CUMCMThesis-master/.[!.]* . 2>/dev/null
        rm -rf CUMCMThesis-master cumcm.zip
    }
    cd "$PROJECT_DIR"
    [ -f templates/CUMCMThesis/cumcmthesis.cls ] && echo "   模板就绪" || { echo "!! 模板获取失败"; exit 1; }
else
    echo "   模板已存在"
fi

echo "==> 写入 problems/README.md ..."
mkdir -p problems
cat > problems/README.md <<'EOF'
# 题目输入区

每个竞赛题目一个子文件夹，放入赛题文件和数据文件：

```
problems/
├── demo-cumcm/          # 示例题（排班 + 产量预测）
│   ├── statement.docx   # 赛题说明
│   └── attachment1.csv  # 数据
└── 2026_CUMCM_B/        # 真实竞赛题（示例）
    ├── 赛题.pdf
    └── 附件1.csv
```

然后启动 claude，说：`按 math-modeling-workflow 跑 problems/<题名> 全流程`
EOF

echo "==> 完成。下一步：bash scripts/first_compile.sh 预热 LaTeX 模板"
