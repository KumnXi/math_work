"""证据门禁：阶段推进前校验上一阶段产物存在且 hash 与 manifest 一致。

用法：
  $PYTHON_EXE verify_manifest.py gate <problem_dir> <stage>   # 校验 <stage> 前一阶段
  $PYTHON_EXE verify_manifest.py --env                         # 环境自检

门禁不通过（返回非零）时，SKILL 强制不得推进下一阶段。
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import common
import machine as M

M.ensure_utf8_stdout()


def check_stage(problem_dir: pathlib.Path, stage: str) -> bool:
    idx = common.STAGE_ORDER.index(stage) if stage in common.STAGE_ORDER else None
    if idx is None or idx == 0:
        common.err(f"无法校验阶段 {stage}：没有前置阶段（P1 直接进行）")
        return False
    prev_stage = common.STAGE_ORDER[idx - 1]
    out_dir = problem_dir / "output"
    # glob_many 用 .resolve() 去重 → 返回绝对路径，所以这里用绝对路径比较
    out_dir_abs = out_dir.resolve()
    manifest_path = out_dir / "run_manifest.json"
    manifest = common.load_json(manifest_path, default={})
    stages = manifest.get("stages", {})
    if prev_stage not in stages:
        common.err(f"门禁失败：{prev_stage} 未完成（run_manifest.json 中无记录）")
        return False
    rec = stages[prev_stage]
    ok = True
    patterns = common.REQUIRED_OUTPUTS.get(prev_stage, [])
    files = common.glob_many(patterns, out_dir)
    if not files:
        common.err(f"门禁失败：{prev_stage} 必需产物缺失：{patterns}")
        return False
    recorded = rec.get("outputs", {})
    for p in files:
        rel = str(p.relative_to(out_dir_abs)).replace("\\", "/")
        actual = common.file_info(p)
        if actual is None:
            common.err(f"门禁失败：产物不存在 {rel}")
            ok = False
            continue
        if rel in recorded and recorded[rel] != actual["sha256"]:
            common.err(f"门禁失败：产物被改动（hash 不一致）{rel}")
            ok = False
        elif rel not in recorded:
            common.warn = None  # 额外文件不拦截
    if rec.get("exit_code", 0) != 0:
        common.err(f"门禁失败：{prev_stage} 的运行 exit_code={rec['exit_code']}")
        ok = False
    if ok:
        common.log(f"[gate] {prev_stage} 产物校验通过，可推进到 {stage}")
    return ok


def env_check() -> bool:
    ok = True
    py = M.python_exe()
    if pathlib.Path(py).exists():
        common.log(f"  [OK] PYTHON_EXE = {py}")
    else:
        common.err(f"  [FAIL] PYTHON_EXE 不存在: {py}"); ok = False

    tpl = M.template_dir() / "cumcmthesis.cls"
    if tpl.exists():
        common.log(f"  [OK] 模板 cumcmthesis.cls 存在")
    else:
        common.err(f"  [FAIL] 模板缺失: {tpl}（运行 scripts/init_project.sh）"); ok = False

    mods = ["pandas", "numpy", "scipy", "matplotlib", "sympy", "ortools", "fitz"]
    import importlib
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            common.err(f"  [FAIL] import {m}: {e}"); ok = False
    if ok:
        common.log("环境自检通过。")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description="证据门禁")
    ap.add_argument("--env", action="store_true", help="环境自检")
    ap.add_argument("command", nargs="?", choices=["gate"])
    ap.add_argument("problem_dir", nargs="?", type=pathlib.Path)
    ap.add_argument("stage", nargs="?")
    args = ap.parse_args()

    if args.env:
        sys.exit(0 if env_check() else 1)
    if args.command == "gate":
        if not args.problem_dir or not args.stage:
            ap.error("gate 需要 problem_dir 和 stage")
        sys.exit(0 if check_stage(args.problem_dir, args.stage) else 1)
    ap.print_help()


if __name__ == "__main__":
    main()
