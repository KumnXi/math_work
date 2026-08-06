"""LaTeX 编译 + 扫描：编译 paper/main.tex，检查错误/引用/overfull/页数。

用法：
  $PYTHON_EXE latex_check.py <problem_dir>
产出：paper/latex_check.json（SKILL 与 acceptance.py 读取）
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import common
import machine as M

M.ensure_utf8_stdout()


def compile_tex(paper_dir: pathlib.Path, main_tex: pathlib.Path) -> dict:
    latexmk = M.latexmk_exe()
    # cwd 是 paper_dir，必须传绝对路径，否则 latexmk 在 paper_dir 下找不到 main.tex
    cmd = [latexmk, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-synctex=1",
           str(main_tex.resolve())]
    common.log("==> latexmk: " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=str(paper_dir), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        common.err("latexmk 编译超时"); exit_code = -1
    log_path = paper_dir / "main.log"
    log_text = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")

    # 只按 ASCII 关键字匹配（日志可能 GBK 乱码）
    report = {"exit_code": exit_code}
    report["fatal_errors"] = re.findall(r"(?:^|\n)(?:!|Error:|! LaTeX Error:).*", log_text)[:10]
    report["undefined_ref"] = len(re.findall(r"Reference .* undefined", log_text))
    report["undefined_cite"] = len(re.findall(r"Citation .* undefined", log_text))
    report["undefined_cs"] = len(re.findall(r"Undefined control sequence", log_text))
    overfull = re.findall(r"Overfull \\hbox.*line (\d+)", log_text)
    report["overfull_count"] = len(overfull)
    report["overfull_lines"] = overfull[:10]

    # 页数统计（PyMuPDF）
    pdf = paper_dir / "main.pdf"
    report["pdf_exists"] = pdf.exists()
    report["pdf_pages"] = 0
    if pdf.exists():
        try:
            import fitz
            doc = fitz.open(str(pdf))
            report["pdf_pages"] = doc.page_count
            doc.close()
        except Exception as e:
            report["pdf_pages_error"] = str(e)

    common.save_json(paper_dir / "latex_check.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="LaTeX 编译 + 扫描")
    ap.add_argument("problem_dir", type=pathlib.Path)
    args = ap.parse_args()
    paper_dir = args.problem_dir / "output" / "paper"
    main_tex = paper_dir / "main.tex"
    if not main_tex.exists():
        common.err(f"缺少 {main_tex}"); sys.exit(1)
    r = compile_tex(paper_dir, main_tex)
    common.log(f"exit={r['exit_code']} pages={r['pdf_pages']} "
               f"undef_ref={r['undefined_ref']} undef_cite={r['undefined_cite']} "
               f"overfull={r['overfull_count']} fatal={len(r['fatal_errors'])}")
    sys.exit(0 if r["exit_code"] == 0 else 1)


if __name__ == "__main__":
    main()
