"""matplotlib 统一出图风格：中文 + 论文级排版。

用法：
    import sys; sys.path.insert(0, r"D:\\Jupyter code\\math_work\\tools")
    import figure_style as fs
    fig, ax = fs.new_axes(); ...
    fs.save(fig, "figures/q1_cost.png")
"""
from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")  # 无 GUI 环境
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "Arial Unicode MS"],
    "axes.unicode_minus": False,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.figsize": (7, 4.5),
})

# 论文配色（色盲友好）
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#DA8BC3", "#8C8C8C"]

DEFAULT_CYCLE = plt.cycler(color=PALETTE)
plt.rcParams["axes.prop_cycle"] = DEFAULT_CYCLE


def new_axes(width=7.0, height=4.5):
    fig, ax = plt.subplots(figsize=(width, height))
    return fig, ax


def save(fig, path: str) -> str:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(p), bbox_inches="tight")
    plt.close(fig)
    return str(p)
