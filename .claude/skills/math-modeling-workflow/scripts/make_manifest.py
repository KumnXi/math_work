"""证据记录器：阶段完成时把产物与运行命令写入 run_manifest。

用法：
  $PYTHON_EXE make_manifest.py record <problem_dir> <stage> \
      --inputs a.csv,b.docx --outputs result_q1.json,code/solve.py \
      --cmd "D:\\...\\python.exe code/solve.py" --exit-code 0

- run_log.jsonl     : append-only 流水账（每行一条记录，含时间戳、命令、输入输出哈希）
- run_manifest.json : 最新快照（按阶段聚合输出文件哈希）
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import common
import machine as M

M.ensure_utf8_stdout()


def _split_csv(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


def record(problem_dir: pathlib.Path, stage: str, inputs, outputs, cmd: str, exit_code: int) -> None:
    out_dir = problem_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    rec = {
        "ts": common.now_ts(),
        "stage": stage,
        "cmd": cmd,
        "exit_code": exit_code,
        "inputs": {},
        "outputs": {},
    }
    for name in inputs:
        p = problem_dir / name
        info = common.file_info(p)
        if info is None:
            common.err(f"输入文件不存在: {name}")
            sys.exit(1)
        rec["inputs"][name] = info
    for name in outputs:
        p = out_dir / name
        info = common.file_info(p)
        if info is None:
            common.err(f"输出文件不存在: {name}")
            sys.exit(1)
        rec["outputs"][name] = info

    # append run_log.jsonl
    log_path = out_dir / "run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(common.json.dumps(rec, ensure_ascii=False) + "\n")

    # 更新 run_manifest.json 快照
    manifest_path = out_dir / "run_manifest.json"
    manifest = common.load_json(manifest_path, default={"problem": str(problem_dir), "stages": {}})
    stage_out = {name: info["sha256"] for name, info in rec["outputs"].items()}
    prev = manifest["stages"].get(stage, {})
    prev.update({"done": True, "ts": rec["ts"], "outputs": stage_out,
                 "last_cmd": cmd, "exit_code": exit_code})
    manifest["stages"][stage] = prev
    common.save_json(manifest_path, manifest)

    common.log(f"[manifest] {stage} 已记录 {len(rec['outputs'])} 个产物到 {manifest_path.name}")
    for name in outputs:
        common.log(f"  - {name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="证据记录器")
    # 注意：dest 用 "command"，不能是 "cmd"——否则会被 --cmd 选项覆盖（两个 dest 冲突），
    # 导致 args.command 丢失 "record"，record 分支永远不执行（端到端跑通发现）。
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record", help="记录一次运行")
    r.add_argument("problem_dir", type=pathlib.Path)
    r.add_argument("stage", help="P1..P6")
    r.add_argument("--inputs", default="")
    r.add_argument("--outputs", required=True)
    r.add_argument("--cmd", default="")
    r.add_argument("--exit-code", type=int, default=0)
    args = ap.parse_args()

    if args.command == "record":
        record(args.problem_dir, args.stage,
               _split_csv(args.inputs), _split_csv(args.outputs),
               args.cmd, args.exit_code)


if __name__ == "__main__":
    main()
