"""将 problems/<题名>/ 的题目文件复制到 solve/<题名>/（工作区）。

默认只复制题目文件 + 数据，不带 output/（problems/ 保持纯存档）。
加 --move-output 时，把 problems/ 下已存在的 output/ 整体移动到 solve/ 对应位置，
并同步 run_manifest.json 的 "problem" 字段为新工作区路径。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def update_manifest_problem(dst: pathlib.Path, new_problem: str) -> None:
    """把 output/run_manifest.json 的 problem 字段指向新工作区（hash 相对路径不变）。"""
    mf = dst / "output" / "run_manifest.json"
    if not mf.exists():
        return
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
        if data.get("problem") == new_problem:
            return
        data["problem"] = new_problem
        mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ run_manifest.json problem → {new_problem}")
    except Exception as e:
        print(f"  ⚠ run_manifest.json 更新失败（可忽略）: {e}")


def migrate(problem_path: str, move_output: bool = False) -> pathlib.Path:
    """将 problems/<题名>/ 的题目文件 + 数据复制到 solve/，返回新工作目录。"""
    src = pathlib.Path(problem_path).resolve()
    if not src.exists():
        print(f"❌ 源目录不存在: {src}")
        sys.exit(1)

    problems_root = (PROJECT_ROOT / "problems").resolve()
    # 支持原始 problems/<year>/<题名> 结构 → solve/<year>-<题名>
    rel = src.relative_to(problems_root)
    target_name = str(rel).replace("/", "-").replace("\\", "-")
    dst = PROJECT_ROOT / "solve" / target_name
    new_problem = str(pathlib.PurePosixPath("solve") / target_name)

    # 题目文件复制（dst 已存在则跳过复制，只处理 output/ 搬迁）
    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)
        copied = 0
        for p in src.iterdir():
            if p.name in ("output", "__pycache__", ".git"):
                continue
            if p.is_dir():
                shutil.copytree(p, dst / p.name, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(p, dst / p.name)
            copied += 1
            print(f"  ✓ {p.name}")
        print(f"✅ 题目文件已复制到 solve/{target_name}/（{copied} 项）")
    else:
        print(f"  solve/{target_name}/ 已存在，跳过题目文件复制")

    # 移动已有 output/（--move-output）
    src_out = src / "output"
    dst_out = dst / "output"
    if move_output:
        if src_out.exists() and src_out.is_dir():
            if dst_out.exists():
                # 目标已有产出 → 不覆盖，提示用户
                print(f"⚠ solve/{target_name}/output/ 已存在，未移动 problems 侧的 output/")
            else:
                shutil.move(str(src_out), str(dst_out))
                print(f"✅ output/ 已从 problems 侧移动到 solve/{target_name}/output/")
                update_manifest_problem(dst, new_problem)
        else:
            print("  problems 侧无 output/（纯题目存档），无需移动")
    else:
        if src_out.exists() and src_out.is_dir():
            print(f"⚠ 未加 --move-output：problems/{rel}/output/ 仍在原处（如需迁移产出请加 --move-output）")

    print(f"   工作目录: {dst}")
    return dst


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    move_output = "--move-output" in sys.argv[1:]
    if len(args) < 1:
        print("用法: $PYTHON_EXE scripts/migrate_to_solve.py [--move-output] <problems/题名>")
        print("示例: $PYTHON_EXE scripts/migrate_to_solve.py --move-output problems/2024/C题")
        print("  --move-output: 额外把 problems/ 侧已有的 output/ 移动到 solve/（默认仅复制题目）")
        sys.exit(1)
    migrate(args[0], move_output=move_output)


if __name__ == "__main__":
    main()
