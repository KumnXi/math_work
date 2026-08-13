"""生成 README 配图（docs/images/）：六阶段流水线图 + 证据门禁示意图。

用法：
    "$PYTHON_EXE" scripts/make_readme_figures.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import figure_style as fs  # noqa: E402  SimHei 中文 + 论文配色

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

# 六阶段：颜色取论文 PALETTE，产物为各阶段关键产出
STAGES = [
    ("P1", "读题分析", "problem_summary.md", "#4C72B0"),
    ("P2", "建模", "model_spec.md", "#55A868"),
    ("P3", "求解", "result_q*.json", "#DD8452"),
    ("P4", "出图", "fig_*.png 300dpi", "#C44E52"),
    ("P5", "论文", "main.pdf + docx", "#8172B3"),
    ("P6", "验收", "acceptance_report.md", "#DA8BC3"),
]
HIL_STAGES = {"P1": True, "P2": True, "P3": True, "P5": True}  # 需人工确认的节点


def draw_pipeline() -> None:
    """① 六阶段流水线：横向六框 + 箭头 + HIL 暂停点标注。"""
    fig, ax = plt.subplots(figsize=(16, 6.2))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    n = len(STAGES)
    bw, bh = 2.15, 2.9            # 框宽高
    gap = 0.38
    x0 = 0.35
    y_top = 4.0
    y_arrow = y_top + bh + 0.18   # 框顶箭头基线

    for i, (code, name, artifact, color) in enumerate(STAGES):
        x = x0 + i * (bw + gap)
        box = FancyBboxPatch((x, y_top), bw, bh,
                             boxstyle="round,pad=0.08,rounding_size=0.18",
                             linewidth=2.2, edgecolor=color, facecolor="white")
        ax.add_patch(box)
        # 右上角 P 序号徽章
        ax.add_patch(FancyBboxPatch((x + bw - 0.62, y_top + bh - 0.56), 0.5, 0.42,
                                    boxstyle="round,pad=0.03,rounding_size=0.12",
                                    linewidth=0, facecolor=color))
        ax.text(x + bw - 0.37, y_top + bh - 0.35, code, ha="center", va="center",
                fontsize=13, fontweight="bold", color="white")
        # 阶段名 + 产物
        ax.text(x + bw / 2, y_top + bh / 2 + 0.42, name, ha="center", va="center",
                fontsize=20, fontweight="bold", color=color)
        ax.text(x + bw / 2, y_top + bh / 2 - 0.52, artifact, ha="center", va="center",
                fontsize=11.5, color="#444444")

        # 阶段间大箭头
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.06, y_top + bh / 2),
                                         (x + bw + gap - 0.08, y_top + bh / 2),
                                         arrowstyle="-|>", mutation_scale=34,
                                         linewidth=2.6, color="#999999"))

        # HIL 暂停点（框下方 ▼ 确认）
        if HIL_STAGES.get(code):
            ax.annotate("▼ 确认", xy=(x + bw / 2, y_top - 0.02),
                        xytext=(x + bw / 2, y_top - 0.62), ha="center",
                        fontsize=12, color="#C44E52", fontweight="bold",
                        arrowprops=dict(arrowstyle="-", lw=1.4, color="#C44E52"))

    # 顶部：数据 → 交付 起点/终点
    ax.add_patch(FancyBboxPatch((x0 - 0.06, y_arrow - 0.55), 1.15, 1.0,
                                boxstyle="round,pad=0.05,rounding_size=0.12",
                                linewidth=0, facecolor="#2E4053"))
    ax.text(x0 + 0.51, y_arrow - 0.05, "赛题", ha="center", va="center",
            fontsize=15, fontweight="bold", color="white")
    ax.add_patch(FancyArrowPatch((x0 + 1.28, y_arrow - 0.05),
                                 (x0 + 2.1, y_arrow - 0.05),
                                 arrowstyle="-|>", mutation_scale=30,
                                 linewidth=2.4, color="#2E4053"))

    x_last = x0 + (n - 1) * (bw + gap)
    ax.add_patch(FancyArrowPatch((x_last - 0.28, y_arrow - 0.05),
                                 (x_last + 0.55, y_arrow - 0.05),
                                 arrowstyle="-|>", mutation_scale=30,
                                 linewidth=2.4, color="#2E4053"))
    ax.add_patch(FancyBboxPatch((x_last + 0.68, y_arrow - 0.55), 1.35, 1.0,
                                boxstyle="round,pad=0.05,rounding_size=0.12",
                                linewidth=0, facecolor="#2E4053"))
    ax.text(x_last + 1.36, y_arrow - 0.05, "论文交付", ha="center", va="center",
            fontsize=15, fontweight="bold", color="white")

    # 底部说明：门禁
    ax.text(8.0, 0.55, "每阶段完成即写哈希入 run_manifest.json，gate 不通过不进入下一阶段",
            ha="center", va="center", fontsize=13, color="#666666")

    fs.save(fig, str(OUT / "pipeline.png"))
    print(f"[ok] {OUT / 'pipeline.png'}")


def draw_gate() -> None:
    """② 证据门禁：产物 → 哈希 → 比对 → 放行/拦截。"""
    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.8)
    ax.axis("off")

    def box(x, y, w, h, text, fc, tc="white", fs_=14):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.05,rounding_size=0.14",
                                    linewidth=0, facecolor=fc))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs_, color=tc, fontweight="bold")

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=26, linewidth=2.2, color="#666666"))

    box(0.3, 1.3, 2.0, 1.2, "阶段产物\n(code/figures)", "#4C72B0")
    arrow(2.4, 1.9, 3.1, 1.9)
    box(3.2, 1.3, 2.2, 1.2, "SHA-256\n哈希", "#55A868")
    arrow(5.5, 1.9, 6.2, 1.9)
    box(6.3, 1.3, 2.3, 1.2, "run_manifest\n比对", "#DD8452")
    # 分叉：一致放行 / 不一致拦截
    arrow(8.7, 1.9, 9.4, 2.55)
    box(9.5, 2.05, 2.2, 1.0, "一致 → 放行\n进入下一阶段", "#2ECC71")
    arrow(8.7, 1.55, 9.4, 1.0)
    box(9.5, 0.6, 2.2, 1.0, "不一致 → 拦截\n自动回滚重试", "#C44E52")

    ax.text(6.0, 3.35, "证据门禁：一切数值可溯源，改动立即暴露", ha="center",
            fontsize=14, fontweight="bold", color="#333333")

    fs.save(fig, str(OUT / "evidence_gate.png"))
    print(f"[ok] {OUT / 'evidence_gate.png'}")


if __name__ == "__main__":
    draw_pipeline()
    draw_gate()
