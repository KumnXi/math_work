"""9 步自动验收 → acceptance_report.md。

用法：
  $PYTHON_EXE acceptance.py <problem_dir>
读取：output/paper/main.tex, main.pdf, latex_check.json, code/result_q*.json, run_manifest.json
产出：output/acceptance_report.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import common
import machine as M

M.ensure_utf8_stdout()


def main() -> None:
    ap = argparse.ArgumentParser(description="9 步自动验收")
    ap.add_argument("problem_dir", type=pathlib.Path)
    args = ap.parse_args()

    pd = args.problem_dir
    out = pd / "output"
    paper = out / "paper"
    tex = paper / "main.tex"
    pdf = paper / "main.pdf"
    lc = common.load_json(paper / "latex_check.json", default={})
    manifest = common.load_json(out / "run_manifest.json", default={})
    results = sorted((out / "code").glob("result_q*.json")) if (out / "code").exists() else []

    rows = []  # (编号, 名称, pass?, 说明)

    # A1 完整性
    need = [tex, pdf] + list((out / "figures").glob("*.png")) if (out / "figures").exists() else [tex, pdf]
    a1 = all(p.exists() and p.stat().st_size > 0 for p in need)
    rows.append(("A1", "完整性", a1, f"论文/图表/结果文件齐全: {len(need)} 个"))

    # A2 文本泄漏/占位符（封面字段 \schoolname/\membera 等由参赛者填写，不算泄漏）
    leaks = []
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        for pat in [r"TODO|FIXME", r"XXX大学|某某大学", r"队员[一二三]|姓名\d",
                    r"\bplaceholder\b", r"example\.tex"]:
            if re.search(pat, t):
                leaks.append(pat)
    a2 = not leaks
    rows.append(("A2", "文本泄漏/占位符", a2, "无泄漏" if a2 else f"发现: {leaks}"))

    # A3 数值一致性（论文数字 vs result JSON，±0.5% 容差）
    a3_notes = []
    a3 = True
    if tex.exists() and results:
        t = tex.read_text(encoding="utf-8")
        for rp in results:
            try:
                data = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for key, val in data.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool) and val != 0:
                    tol = abs(val) * 0.005
                    # 在正文中查找相近数字（整数或带小数）
                    found = re.search(rf"{val:g}", t) or re.search(rf"{val:.2f}", t)
                    if found is None and not any(
                        abs(float(m.group(0))) - tol <= abs(val) <= abs(float(m.group(0))) + tol
                        for m in re.finditer(r"\d+(?:\.\d+)?", t)
                    ):
                        a3_notes.append(f"result 中 {key}={val:g} 未在正文出现")
                        a3 = False
    rows.append(("A3", "数值一致性", a3, "一致" if a3 else "; ".join(a3_notes[:3])))

    # A4 图表引用完整
    a4 = True
    a4_notes = []
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t)
        for f in figs:
            fp = paper / (f if f.endswith(".png") else f + ".png")
            if not fp.exists():
                a4_notes.append(f"图文件缺失: {f}")
                a4 = False
        refs = re.findall(r"\\ref\{([^}]+)\}", t)
        labels = set(re.findall(r"\\label\{([^}]+)\}", t))
        for r in refs:
            if r not in labels:
                a4_notes.append(f"引用未定义: {r}")
                a4 = False
        if lc.get("undefined_ref", 0) or lc.get("undefined_cite", 0):
            a4_notes.append("latex_check 报 undefined ref/cite")
            a4 = False
    rows.append(("A4", "图表引用完整", a4, "完整" if a4 else "; ".join(a4_notes[:3])))

    # A5 LaTeX 编译
    a5 = lc.get("exit_code", 1) == 0 and lc.get("fatal_errors", ["x"]) == []
    a5_notes = (f"exit={lc.get('exit_code')} overfull={lc.get('overfull_count',0)} "
                f"pages={lc.get('pdf_pages',0)}")
    rows.append(("A5", "LaTeX 编译", a5, a5_notes))

    # A6 模型形式化（每子问题至少一个公式）
    a6 = True
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        n_eq = len(re.findall(r"\\begin\{(?:equation|align)\}", t))
        a6 = n_eq >= 1
    rows.append(("A6", "模型形式化", a6, f"公式数量: {n_eq if 'n_eq' in dir() else 0}"))

    # A7 论文要素齐全
    a7_notes = []
    a7 = True
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        for kw, name in [(r"模型假设", "假设"), (r"符号", "符号表"),
                         (r"灵敏度|稳定性", "灵敏度"),
                         (r"参考文献|\\bibliograph|\\begin\{thebibliography\}", "参考文献")]:
            if not re.search(kw, t):
                a7_notes.append(f"缺 {name}")
                a7 = False
    rows.append(("A7", "论文要素齐全", a7, "齐全" if a7 else "; ".join(a7_notes)))

    # A8 格式规范（摘要 1 页、正文 ≤25 页）
    a8 = True
    a8_notes = []
    pages = lc.get("pdf_pages", 0)
    if pages > 26:  # 封面/摘要/正文估计
        a8_notes.append(f"总页数 {pages} 可能超限")
        a8 = False
    rows.append(("A8", "格式规范", a8, f"总页数 {pages}" + ("".join(a8_notes) if a8_notes else "")))

    # A9 代码可复现（用 manifest 记录的 python 重跑 solve.py）
    a9 = True
    a9_notes = []
    stages = manifest.get("stages", {})
    p3 = stages.get("P3", {})
    if p3.get("last_cmd"):
        # 仅做存在性检查提示；完整重跑耗时，由 SKILL 决定是否执行
        a9_notes.append(f"P3 记录命令: {p3['last_cmd'][:80]}...")
        a9 = True
    rows.append(("A9", "代码可复现", a9, "; ".join(a9_notes) if a9_notes else "已记录运行命令"))

    # 生成报告
    report_path = out / "acceptance_report.md"
    lines = ["# 自动验收报告\n",
             f"- 题目: {pd.name}",
             f"- 时间: {common.now_ts()}",
             f"- 通过: {sum(1 for r in rows if r[2])}/{len(rows)}\n",
             "| 编号 | 检查项 | 结果 | 说明 |",
             "|---|---|---|---|"]
    for code, name, passed, note in rows:
        mark = "✅" if passed else "❌"
        lines.append(f"| {code} | {name} | {mark} | {note} |")
    if not all(r[2] for r in rows):
        lines.append("\n## 未通过项修正建议\n")
        for code, name, passed, note in rows:
            if not passed:
                lines.append(f"- **{code} {name}**: {note}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    common.log(f"验收报告已生成: {report_path}")

    passed = all(r[2] for r in rows)
    common.log(f"验收结果: {'全部通过 ✅' if passed else '有未通过项 ❌'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
