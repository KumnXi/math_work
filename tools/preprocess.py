"""数据预处理 / 探索性分析（EDA）。

用法：
    $PYTHON_EXE preprocess.py <data.csv> [--out report.md]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None


def eda_report(df: pd.DataFrame) -> str:
    lines = [f"- 形状: {df.shape[0]} 行 × {df.shape[1]} 列", ""]
    lines.append("| 列 | dtype | 非空数 | 缺失 | 唯一值 | 均值 | 标准差 | 最小 | 最大 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for col in df.columns:
        s = df[col]
        lines.append(
            f"| {col} | {s.dtype} | {s.notna().sum()} | {s.isna().sum()} "
            f"| {s.nunique()} | {s.mean() if s.dtype.kind in 'fiu' else '-'}"
            f" | {s.std() if s.dtype.kind in 'fiu' else '-'}"
            f" | {s.min() if s.dtype.kind in 'fiu' else '-'}"
            f" | {s.max() if s.dtype.kind in 'fiu' else '-'} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if args.data.suffix.lower() == ".csv":
        df = pd.read_csv(args.data, comment="#")
    elif args.data.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(args.data)
    else:
        df = pd.read_csv(args.data, sep="\s+", comment="#")

    rep = eda_report(df)
    print(rep)
    if args.out:
        args.out.write_text(rep, encoding="utf-8")
        print(f"已写入 {args.out}")


if __name__ == "__main__":
    main()
