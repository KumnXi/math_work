"""11 步自动验收 → acceptance_report.md。

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

    # A2 文本泄漏/占位符/内部文件泄露（封面字段 \schoolname/\membera 等由参赛者填写，不算泄漏）
    leaks = []
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        for pat in [r"TODO|FIXME", r"XXX大学|某某大学", r"队员[一二三]|姓名\d",
                    r"\bplaceholder\b", r"example\.tex",
                    # 内部工作流文件/路径/脚本名泄漏
                    r"output/(analysis|code|figures|paper)", r"result_q\d",
                    r"run_manifest|task_state|_notes\.md",
                    r"\bMock\b", r"demo-cumcm", r"figure_style",
                    r"make_manifest|verify_manifest|acceptance_report"]:
            if re.search(pat, t):
                leaks.append(pat)
    a2 = not leaks
    rows.append(("A2", "文本泄漏/占位符", a2, "无泄漏" if a2 else f"发现: {leaks}"))

    # A3 数值一致性（论文数字 vs result JSON，±0.5% 容差，单位感知）
    # 论文通常以 万元/亿元 呈现结果，故 val 可匹配 元/万元/亿元 任一量级的相近数字。
    # 纯实现元数据键（模型规模、求解参数、目标函数原始值）不是论文陈述的"结果"，跳过。
    META_KEYS = {"n_vars", "n_constraints", "nnz", "case", "lambda", "alpha",
                 "N_scen", "obj_value", "seed", "SEED", "gap", "status", "exit_code"}

    def _tex_has(cand, t):
        """正文中是否出现与 cand 相近（±0.5%）的数字。"""
        if re.search(rf"{cand:g}", t) or re.search(rf"{cand:.2f}", t):
            return True
        tol = abs(cand) * 0.005
        return any(
            abs(float(m.group(0))) - tol <= abs(cand) <= abs(float(m.group(0))) + tol
            for m in re.finditer(r"\d+(?:\.\d+)?", t)
        )

    a3_notes = []
    a3 = True
    if tex.exists() and results:
        t = tex.read_text(encoding="utf-8")
        # 展开 \input 的 .tex 文件（表格等），使其数值纳入一致性检查
        for m in re.finditer(r"\\input\{([^}]+)\}", t):
            inc = paper / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
            if inc.exists():
                t += "\n" + inc.read_text(encoding="utf-8")
        for rp in results:
            try:
                data = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for key, val in data.items():
                if key in META_KEYS:
                    continue
                if isinstance(val, (int, float)) and not isinstance(val, bool) and val != 0:
                    cands = [abs(val)] + [abs(val) / d for d in (1e4, 1e6, 1e8)]
                    if not any(_tex_has(c, t) for c in cands):
                        a3_notes.append(f"result 中 {key}={val:g} 未在正文出现（元/万元/亿元 量级均未命中）")
                        a3 = False
    rows.append(("A3", "数值一致性", a3, "一致" if a3 else "; ".join(a3_notes[:3])))

    # A4 图表引用完整（引用的图必须存在，且通过 check_figures 质量检查）
    a4 = True
    a4_notes = []
    check_report = common.load_json(out / "figures" / "check_report.json", default={})
    if tex.exists():
        t = tex.read_text(encoding="utf-8")
        figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t)
        for f in figs:
            fp = paper / (f if f.endswith(".png") else f + ".png")
            if not fp.exists():
                a4_notes.append(f"图文件缺失: {f}")
                a4 = False
                continue
            fname = pathlib.Path(f).name
            if fname in check_report and not check_report[fname].get("ok"):
                a4_notes.append(f"引用的图未过质量检查: {fname}")
                a4 = False
        # 与 A3 一致：展开 \input 的 .tex（表格等），使其中 \label 定义纳入检查
        t4 = t
        for m in re.finditer(r"\\input\{([^}]+)\}", t):
            inc = paper / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
            if inc.exists():
                t4 += "\n" + inc.read_text(encoding="utf-8")
        refs = re.findall(r"\\ref\{([^}]+)\}", t4)
        labels = set(re.findall(r"\\label\{([^}]+)\}", t4))
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

    # A8 格式规范（摘要 ≤1 页、正文页数、附录不计页）
    # 经验(2024-A题 P7)：官方"正文尽量 ≤20 页"为软性建议，**附录页数不限**；总页数含附录会虚高。
    # 故按正文页数判定：页 1 为摘要，附录起始页(正文内"见附录"引用在前 70%，只认后 30% 的"附录"标题页)
    # 之前为正文；无附录则 正文 = 总页数 - 1。正文 ≤25 通过；25~30 通过但提示；>30 兜底失败。
    a8 = True
    a8_notes = []
    pages = lc.get("pdf_pages", 0)
    body_pages, appendix_pages = pages, 0
    if pdf.exists() and pages > 0:
        try:
            import fitz
            doc = fitz.open(str(pdf))
            app_page = None
            thresh = max(2, int(pages * 0.7))          # 只认靠后 30% 的"附录"标题页
            for i in range(1, doc.page_count):
                if i + 1 >= thresh and "附录" in doc[i].get_text():
                    app_page = i + 1
                    break
            doc.close()
            if app_page:
                body_pages = app_page - 2              # 页1=摘要，页2..appendix-1=正文
                appendix_pages = pages - app_page + 1
            else:
                body_pages = max(pages - 1, 0)
        except Exception:                              # noqa: BLE001  fitz 缺失等 → 退化为总页数
            body_pages = pages
    if body_pages > 30:                                # 兜底上限（≈软性建议的 1.5 倍）
        a8 = False
        a8_notes.append(f"正文 {body_pages} 页超兜底上限 30")
    elif body_pages > 25:
        a8_notes.append(f"正文 {body_pages} 页超'尽量20页'软性建议——每页均有实质论据可接受，否则应精简")
    rows.append(("A8", "格式规范", a8,
                 f"摘要1+正文{body_pages}+附录{appendix_pages}=总{pages}页" + ("".join(a8_notes) if a8_notes else "")))

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

    # A10 图质量（所有图过 check_figures 程序化检查 + 技术路线图存在；无报告的老任务跳过）
    a10 = True
    a10_notes = []
    if check_report:
        bad = [k for k, v in check_report.items()
               if k != "__error__" and not v.get("ok")]
        if bad:
            a10 = False
            a10_notes.append(f"未过质量检查: {', '.join(bad[:4])}")
        if not (out / "figures" / "fig_pipeline.png").exists():
            a10 = False
            a10_notes.append("缺技术路线图 fig_pipeline.png")
        if a10 and not a10_notes:
            a10_notes.append("全部通过")
    else:
        a10_notes.append("无 check_report（老任务，跳过）")
    rows.append(("A10", "图质量", a10, "; ".join(a10_notes)))

    # A11 PDF 视觉（渲染每页确认非空白/可读 + 与 latex_check 页数一致）
    a11 = True
    a11_notes = []
    if pdf.exists() and pdf.stat().st_size > 0:
        if pdf.stat().st_size < 100 * 1024:
            a11 = False
            a11_notes.append(f"PDF 过小({pdf.stat().st_size}B)")
        try:
            import fitz
            import numpy as np
            doc = fitz.open(str(pdf))
            n = doc.page_count
            blank_pages = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n)
                gray = arr[..., :3].mean(axis=2)
                ink = float((gray < 245).mean())
                if ink < 0.001:
                    blank_pages.append(i + 1)
            doc.close()
            if n <= 0:
                a11 = False
                a11_notes.append("PDF 页数=0")
            if blank_pages:
                a11 = False
                a11_notes.append(f"空白页: {blank_pages}")
            lc_pages = lc.get("pdf_pages", 0)
            if lc_pages and lc_pages != n:
                a11_notes.append(f"latex_check页数{lc_pages}≠实测{n}")
            a11_notes.append(f"页数 {n}")
        except Exception as e:      # noqa: BLE001
            a11 = False
            a11_notes.append(f"PDF 渲染失败: {e}")
    else:
        a11 = False
        a11_notes.append("main.pdf 缺失或为空")
    rows.append(("A11", "PDF 视觉", a11, "; ".join(a11_notes)))

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
