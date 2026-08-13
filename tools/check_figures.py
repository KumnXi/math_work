"""数据图质量程序化检查：可解码 / 尺寸 / 非空白 / 大小。

跑完出图后调用，判定 figures/*.png 是否有资格进论文：
- 可解码（matplotlib.image.imread 抛错 = 损坏文件）
- 宽≥600 高≥400（论文级清晰度）
- 文件 >5KB（防占位）
- 非空白（灰度数组非白像素比例 > 1%，防全白/全黑空图）

用法：
  $PYTHON_EXE tools/check_figures.py <figures_dir>
产出：<figures_dir>/check_report.json（每张图 ok/尺寸/ink_ratio/issues）
任一图不通过 → exit 1（P4 据此回喂修复，acceptance A10 据此门禁）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

MIN_W = 600
MIN_H = 400
MIN_SIZE = 5 * 1024
INK_MIN = 0.01          # 非白像素比例下限（防空白图）


def check_file(p: pathlib.Path) -> dict:
    size = p.stat().st_size
    issues: list[str] = []
    if size < MIN_SIZE:
        issues.append(f"文件过小({size}B<{MIN_SIZE}B)")
    try:
        import matplotlib.image as mpimg
        img = mpimg.imread(str(p))          # HxWxC float 0..1
        h, w = img.shape[:2]
        gray = img[..., :3].mean(axis=2) if img.ndim == 3 else img
        ink = float((gray < 0.95).mean())   # 非白像素比例
        if w < MIN_W:
            issues.append(f"宽 {w}<{MIN_W}")
        if h < MIN_H:
            issues.append(f"高 {h}<{MIN_H}")
        if ink <= INK_MIN:
            issues.append(f"疑似空白图(ink={ink:.3%})")
        info = {"ok": not issues, "width": w, "height": h,
                "ink_ratio": round(ink, 4), "size": size, "issues": issues}
    except Exception as e:                  # noqa: BLE001
        info = {"ok": False, "width": 0, "height": 0, "ink_ratio": 0.0,
                "size": size, "issues": [f"解码失败: {e}"]}
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description="数据图质量程序化检查")
    ap.add_argument("figures_dir", type=pathlib.Path)
    args = ap.parse_args()

    d = args.figures_dir
    figs = sorted(d.glob("*.png")) if d.exists() else []
    report: dict = {}
    if not figs:
        report = {"__error__": "目录无 png"}
    for p in figs:
        report[p.name] = check_file(p)
    (d / "check_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    bad = [k for k, v in report.items()
           if k != "__error__" and not v.get("ok")]
    print(f"图检查: {len(figs)} 张, 通过 {len(figs) - len(bad)}, 失败 {len(bad)}")
    for k in bad:
        print(f"  ❌ {k}: {report[k]['issues']}")
    if "__error__" in report:
        print(f"  {report['__error__']}")
    sys.exit(1 if (bad or "__error__" in report) else 0)


if __name__ == "__main__":
    main()
