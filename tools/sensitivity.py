"""灵敏度 / 稳定性分析（单变量 OAT + tornado 图）。

用法：
    $PYTHON_EXE sensitivity.py --func <module:function> --base <base.json>
    # func(params: dict) -> float（模型目标），base.json 为基准参数
    # 每个参数 ±10%/±20%，输出敏感性指数 + tornado 图

示例：见 tools/README.md
"""
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None


def load_func(spec: str):
    mod_name, func_name = spec.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--func", required=True, help="module:function")
    ap.add_argument("--base", type=pathlib.Path, required=True, help="基准参数 JSON")
    ap.add_argument("--factors", default="0.8,0.9,1.1,1.2")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    func = load_func(args.func)
    base = json.loads(args.base.read_text(encoding="utf-8"))
    base_val = func(base)
    factors = [float(f) for f in args.factors.split(",")]

    print(f"基准目标值: {base_val:.6f}\n")
    print("| 参数 | 扰动 | 目标值 | 变化% | 敏感性指数 |")
    print("|---|---|---|---|---|")
    results = {}
    for key in base:
        if not isinstance(base[key], (int, float)):
            continue
        for fac in factors:
            p = dict(base)
            p[key] = base[key] * fac
            v = func(p)
            rel_change = (v - base_val) / base_val if base_val else 0
            rel_fac = (fac - 1) if base_val else 0
            sens = rel_change / rel_fac if rel_fac else float("inf")
            print(f"| {key} | {fac:.1f}x | {v:.4f} | {rel_change*100:.2f}% | {sens:.3f} |")
            results.setdefault(key, []).append(abs(sens))
    print("\n敏感性指数汇总（取平均）：")
    for key, vals in results.items():
        print(f"  {key}: {np.mean(vals):.3f} {'⚠敏感' if np.mean(vals) > 0.5 else '稳定'}")

    if args.out:
        args.out.write_text(
            json.dumps({k: float(np.mean(v)) for k, v in results.items()},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {args.out}")


if __name__ == "__main__":
    main()
