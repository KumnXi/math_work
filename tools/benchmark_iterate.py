"""优秀论文对比迭代器：OCR 归档参考论文 + 生成对比矩阵骨架（P7 落地工具）。

用法:
  # 指定若干参考论文
  "$PYTHON_EXE" tools/benchmark_iterate.py <solve_dir> <ref1.pdf> [ref2.pdf ...]
  # 自动筛某年某题的优秀论文（--prefix 匹配文件名前缀，如 C 题 → C*.pdf）
  "$PYTHON_EXE" tools/benchmark_iterate.py <solve_dir> --dir "高教社杯…/2024年…" --prefix C
  # 只 OCR 指定页（快速迭代：先摘要/模型页）
  "$PYTHON_EXE" tools/benchmark_iterate.py <solve_dir> <ref.pdf> --pages 1-5,20-28

功能:
  1. 有文本层 PDF → PyMuPDF 直接提取；无文本层 → rapidocr 逐页 OCR
  2. 归档到 <solve_dir>/output/analysis/reference/<name>.txt（可续跑：已存在跳过）
  3. 生成 <solve_dir>/output/analysis/benchmark_study.md 骨架（论文清单 + 对比矩阵模板）
  4. 对比判断由工作流/Claude 完成；本工具只做机械部分。完成后用
     "$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_manifest.py record <solve_dir> P7 \
       --outputs analysis/reference/<name>.txt,... --cmd "<命令>" --exit-code 0
     记入证据门禁。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def parse_pages(spec: str | None) -> set[int] | None:
    """'1-5,12,20-28' → {1,2,3,4,5,12,20..28}；None 表示全页。"""
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        elif part:
            pages.add(int(part))
    return pages


def extract_text_layer(pdf: pathlib.Path, max_pages: int | None = None) -> str:
    """PyMuPDF 提取文本层。无文本层返回 ''。"""
    import fitz

    doc = fitz.open(str(pdf))
    try:
        text = []
        for i, page in enumerate(doc):
            if max_pages is not None and i >= max_pages:
                break
            t = page.get_text()
            if t.strip():
                text.append(f"===== 第 {i+1} 页 =====\n{t}")
        return "\n".join(text)
    finally:
        doc.close()


def ocr_pages(pdf: pathlib.Path, pages: set[int] | None, dpi: int = 200) -> str:
    """rapidocr 逐页 OCR，返回全文（含页码标记）。"""
    import fitz
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    doc = fitz.open(str(pdf))
    out: list[str] = []
    try:
        for i, page in enumerate(doc):
            if pages is not None and (i + 1) not in pages:
                continue
            pix = page.get_pixmap(dpi=dpi)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            img_bgr = img[:, :, ::-1]  # RGB → BGR（OpenCV 惯例）
            result, _elapse = engine(img_bgr)
            texts = [r[1] for r in result] if result else []
            out.append(f"===== 第 {i+1} 页 =====\n" + "\n".join(texts))
            print(f"  [OCR] {pdf.stem} p.{i+1}: {len(texts)} 行")
    finally:
        doc.close()
    return "\n".join(out)


def resolve_refs(solve_dir: pathlib.Path, args) -> list[pathlib.Path]:
    """确定参考论文列表：显式参数或 --dir/--prefix 自动筛。"""
    refs = [pathlib.Path(p).resolve() for p in args.refs]
    if args.dir:
        d = pathlib.Path(args.dir).resolve()
        if not d.is_dir():
            print(f"❌ 目录不存在: {d}")
            sys.exit(1)
        prefix = args.prefix or ""
        for p in sorted(d.glob(f"{prefix}*.pdf")):
            if p.is_file():
                refs.append(p)
    if not refs:
        print("❌ 未指定任何参考论文（传 PDF 或用 --dir 指定目录）")
        sys.exit(1)
    return refs


def write_skeleton(solve_dir: pathlib.Path, refs: list[pathlib.Path],
                   archived: list[tuple[pathlib.Path, str]]) -> None:
    """生成 benchmark_study.md 骨架。"""
    ref_dir = solve_dir / "output" / "analysis" / "reference"
    bench = solve_dir / "output" / "analysis" / "benchmark_study.md"
    lines = [
        f"# 优秀论文对比学习（benchmark study）",
        f"",
        f"> 任务：`{solve_dir.name}`；工具：`tools/benchmark_iterate.py`（P7 落地）。",
        f"> 方法学参考：`.claude/skills/math-modeling-workflow/references/benchmark-iteration.md`。",
        f"> 留档要求：论文版本存 `output/paper/archive/vN/`；本表为逐环节对比。",
        f"",
        f"## 一、参考论文清单",
        f"",
        f"| 论文 | 页数 | 归档文本 | 状态 |",
        f"|---|---|---|---|",
    ]
    for p, status in archived:
        lines.append(f"| {p.stem} | - | `reference/{p.stem}.txt` | {status} |")
    lines += [
        "",
        "## 二、对比矩阵（逐环节填）",
        "",
        "| 环节 | 我们的方案（方法+指标） | 优秀方案（方法+指标） | 差距 | 该修/保留 | 改进动作 |",
        "|---|---|---|---|---|---|",
        "| Q1 确定性优化 | | | | | |",
        "| Q2 风险度量 | | | | | |",
        "| Q3 相关性 | | | | | |",
        "| 检验与灵敏度 | | | | | |",
        "| 论文结构/呈现 | | | | | |",
        "",
        "## 三、差距总结与改进结论",
        "",
        "（待工作流对比后填写：最痛点 / 该修 vs 已验证正确保留 / 改后重跑结果）",
        "",
        "## 四、迭代记录",
        "",
        "- v1：初稿（2024-C 已完成）。本表为 P7 对比迭代起点。",
        "",
    ]
    bench.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 对比矩阵骨架: {bench}")


def main():
    ap = argparse.ArgumentParser(description="优秀论文对比迭代器（OCR 归档 + 对比矩阵骨架）")
    ap.add_argument("solve_dir", help="工作区目录，如 solve/2024-C题")
    ap.add_argument("refs", nargs="*", help="参考论文 PDF 路径")
    ap.add_argument("--dir", help="优秀论文目录（自动筛 <prefix>*.pdf）")
    ap.add_argument("--prefix", default="", help="--dir 模式下的文件名前缀（如 C）")
    ap.add_argument("--pages", help="只 OCR 指定页，如 1-5,12,20-28（默认全页）")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--force", action="store_true", help="强制重 OCR（覆盖已有 txt）")
    args = ap.parse_args()

    solve_dir = pathlib.Path(args.solve_dir).resolve()
    if not solve_dir.exists():
        print(f"❌ 工作区目录不存在: {solve_dir}")
        sys.exit(1)
    ref_dir = solve_dir / "output" / "analysis" / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)

    refs = resolve_refs(solve_dir, args)
    pages = parse_pages(args.pages)

    archived: list[tuple[pathlib.Path, str]] = []
    for pdf in refs:
        if not pdf.exists():
            print(f"⚠ 跳过（不存在）: {pdf}")
            continue
        txt = ref_dir / f"{pdf.stem}.txt"
        if txt.exists() and not args.force:
            print(f"· 跳过（已归档）: {txt.name}")
            archived.append((pdf, "已归档（复用）"))
            continue
        # 1) 试文本层
        text = extract_text_layer(pdf)
        status = "文本层提取"
        if len(text.strip()) < 200:
            status = f"rapidocr OCR（pages={args.pages or 'all'}）"
            text = ocr_pages(pdf, pages, dpi=args.dpi)
        if text.strip():
            txt.write_text(text, encoding="utf-8")
            print(f"✓ {status} → {txt}")
            archived.append((pdf, status))
        else:
            print(f"⚠ {pdf.stem}: OCR 无输出，未生成归档")
            archived.append((pdf, "OCR 无输出"))

    write_skeleton(solve_dir, refs, archived)

    n = len(archived)
    outputs = ",".join(f"analysis/reference/{p.stem}.txt" for p, _ in archived)
    print(f"\n✅ 完成：{n} 篇论文归档。建议记证据门禁：")
    print(f'  "$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_manifest.py record "{args.solve_dir}" P7 \\')
    print(f'    --outputs {outputs} --cmd "benchmark_iterate.py {" ".join(args.refs)}" --exit-code 0')


if __name__ == "__main__":
    main()
