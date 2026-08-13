r"""生成完整版 Word 论文：从 main.tex 用 pandoc 直接转换为 main.docx。

替代旧 pdf2docx 方案（PDF→Word 会把公式转成带 LaTeX Computer Modern 字体名的
文本碎片；Windows 没有 CMMI/CMSY/CMEX 等字体，Word 回退字体渲染导致公式错乱，
且"每行一段 + 每页一节"使版式与 PDF 天差地别）。

pandoc 方案产出：公式为原生可编辑 Word 公式（OMML）、段落正常流动排版、
图/表带编号且引用可解析、摘要标题为中文"摘要"。
公式编号与 \eqref 在预处理阶段自行解析——pandoc-crossref 对 LaTeX 输入 +
docx 公式编号存在已知缺陷（ref 会退化为 [eq:xxx] 字面量），故不依赖它；
图/表引用由 pandoc 核心解析（LaTeX reader 原生支持 \ref 指向带 caption 的浮动体）。

用法: $PYTHON_EXE tools/generate_docx.py <task_dir>
产出: <task_dir>/output/paper/main.docx（与 main.pdf 同内容的完整版，公式可编辑）
依赖: pandoc（PANDOC_EXE，机器配置 config/machine.json；winget install pandoc）
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 本文件位于 tools/ → 项目根在 parents[1]
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 编号公式环境（equation* 不编号）
EQ_RE = re.compile(r"\\begin\{(equation)\*?\}(.*?)\\end\{\1\}", re.S)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(r"\\(?:eqref|ref)\{([^}]+)\}")


def _pandoc_exe() -> str:
    """解析 pandoc 路径：machine.json 的 PANDOC_EXE → 环境变量 → PATH。"""
    mj = PROJECT_ROOT / "config" / "machine.json"
    if mj.exists():
        try:
            v = json.loads(mj.read_text(encoding="utf-8")).get("PANDOC_EXE")
            if v and pathlib.Path(v).exists():
                return v
        except Exception:
            pass
    import os
    if os.environ.get("PANDOC_EXE"):
        return os.environ["PANDOC_EXE"]
    return "pandoc"  # PATH 回退


def preprocess_latex(src: str) -> tuple[str, dict]:
    r"""预处理 main.tex：

    1. abstract 环境 → 中文"摘要"节；
    2. 按文档顺序给 equation 环境编号，末尾注入 (N)，剥离 \label 并记录 label→编号；
    3. \eqref/\ref 指向已编号公式的 → (N)；指向图/表的保留原文交给 pandoc 解析。

    返回 (预处理后文本, 公式 label→编号映射)。
    """
    src = src.replace(r"\begin{abstract}", r"\section*{摘要}")
    src = src.replace(r"\end{abstract}", "")

    labels: dict[str, int] = {}
    counter = 0

    def _eq_repl(m: re.Match) -> str:
        nonlocal counter
        body = m.group(2)
        lb = LABEL_RE.search(body)
        body_clean = LABEL_RE.sub("", body)
        if m.group(0).startswith(r"\begin{equation*}"):
            return rf"\begin{{equation*}}{body_clean}\end{{equation*}}"
        counter += 1
        if lb:
            labels[lb.group(1)] = counter
        # \qquad(N) 使编号显示在公式后（docx 内 OMML 无原生右对齐编号）
        return rf"\begin{{equation}}{body_clean}\qquad({counter})\end{{equation}}"

    src = EQ_RE.sub(_eq_repl, src)

    def _ref_repl(m: re.Match) -> str:
        key = m.group(1)
        n = labels.get(key)
        return f"({n})" if n is not None else m.group(0)

    src = REF_RE.sub(_ref_repl, src)
    return src, labels


def _unresolved_refs(docx: pathlib.Path) -> list[str]:
    """转换后检查是否残留未解析的引用标记。"""
    import zipfile

    try:
        z = zipfile.ZipFile(docx)
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:
        return []
    text = re.sub(r"<[^>]+>", "", xml)
    return [k for k in ("[eq:", "[fig:", "[tab:", r"\eqref", r"\ref{", "eqref") if k in text]


def build_docx(task_dir: pathlib.Path) -> pathlib.Path:
    """main.tex → main.docx（pandoc 直接转换，公式为原生 OMML）。"""
    paper = task_dir / "output" / "paper"
    tex = paper / "main.tex"
    docx = paper / "main.docx"

    if not tex.exists():
        print(f"❌ 未找到 {tex}（先完成 P5 论文编译，产出 main.tex）")
        sys.exit(1)

    # 已有 docx 且比 tex 新 → 跳过（避免每次重复转换）
    if docx.exists() and docx.stat().st_mtime >= tex.stat().st_mtime:
        print(f"✓ main.docx 已存在且未过期: {docx}")
        return docx

    pandoc = _pandoc_exe()
    try:
        probe = subprocess.run([pandoc, "--version"], capture_output=True, text=True)
        if probe.returncode != 0:
            raise FileNotFoundError(pandoc)
    except (OSError, FileNotFoundError):
        print("❌ 未找到 pandoc。请先安装: winget install --id JohnMacFarlane.Pandoc")
        print("   并确认 config/machine.json 中 PANDOC_EXE 指向 pandoc.exe")
        sys.exit(1)

    src = tex.read_text(encoding="utf-8")
    pre, labels = preprocess_latex(src)
    tmp = paper / "_main_pandoc.tex"
    tmp.write_text(pre, encoding="utf-8")

    print(f"正在转换 {tex.name} → {docx.name}（pandoc，公式 {len(labels)} 个带编号）...")
    cmd = [pandoc, str(tmp.name), "-o", str(docx), "--from", "latex", "--to", "docx"]
    proc = subprocess.run(cmd, cwd=str(paper), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not docx.exists():
        print("❌ pandoc 转换失败:")
        for out in (proc.stdout, proc.stderr):
            if out:
                print(out[-2000:])
        print(f"   中间产物保留在 {tmp} 供排查")
        sys.exit(1)

    leftover = _unresolved_refs(docx)
    if leftover:
        print(f"⚠️  检测到未解析的引用标记 {leftover}，请在 Word 中核对相应图表/公式编号")
    tmp.unlink(missing_ok=True)
    print(f"✓ 完整版 Word 文档已生成: {docx}（公式可编辑，编号 {len(labels)} 个）")
    return docx


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: $PYTHON_EXE tools/generate_docx.py <task_dir>")
        print("示例: $PYTHON_EXE tools/generate_docx.py solve/2024-C题")
        sys.exit(1)
    task_dir = pathlib.Path(sys.argv[1]).resolve()
    if not task_dir.exists():
        print(f"错误: 目录不存在: {task_dir}")
        sys.exit(1)
    build_docx(task_dir)


if __name__ == "__main__":
    main()
