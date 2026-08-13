"""任务注册表：扫描 solve/* 和 problems/* 目录，维护任务列表与元信息。"""
from __future__ import annotations

import pathlib

from . import config


def _scan_dir(root: pathlib.Path) -> list[dict]:
    """扫描单个根目录下的任务（单层扁平结构）。"""
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        out.append(_task_entry(d))
    return out


def _task_entry(d: pathlib.Path, task_id: str | None = None) -> dict:
    """从目录路径构建任务条目。"""
    tid = task_id or d.name
    state = config.load_state(d)
    if state.get("status") == "idle" and not state.get("logs"):
        status = "new"
    else:
        status = state.get("status", "new")
    if status in ("new", "idle") and (d / "output" / "run_manifest.json").exists():
        status = "done"
    return {
        "id": tid,
        "status": status,
        "stage": state.get("stage", ""),
        "updated": state.get("updated", ""),
        "has_output": (d / "output").exists(),
        "paper": (d / "output" / "paper" / "main.pdf").exists(),
        "acceptance": (d / "output" / "acceptance_report.md").exists(),
        "source_dir": d.parent.name if d.parent.name in ("solve", "problems") else str(d.parent.relative_to(config.PROJECT_ROOT)),
    }


def list_tasks() -> list[dict]:
    """扫描 solve/* 和 problems/*，合并去重（solve/ 优先）。
    problems/ 支持嵌套结构（problems/<年>/<题名>）。"""
    seen = set()
    out = []

    # solve/ —— 扁平结构
    for t in _scan_dir(config.PROJECT_ROOT / "solve"):
        if t["id"] not in seen:
            seen.add(t["id"])
            out.append(t)

    # problems/ —— 可能嵌套（problems/<年>/<题名>）
    problems_root = config.PROJECT_ROOT / "problems"
    if problems_root.exists():
        for d in sorted(problems_root.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            # 检查是否直接有 output/（扁平）还是嵌套子目录
            if (d / "output").exists() or any(f.suffix.lower() in (".pdf", ".docx", ".xlsx") for f in d.iterdir() if f.is_file()):
                # 扁平：problems/<task_id>/
                if d.name not in seen:
                    seen.add(d.name)
                    out.append(_task_entry(d))
            else:
                # 嵌套：problems/<年>/<题名>/
                for sub in sorted(d.iterdir()):
                    if not sub.is_dir() or sub.name.startswith("."):
                        continue
                    tid = f"{d.name}/{sub.name}"
                    # 若 solve/<年>-<题名> 工作区已存在，则 problems 存档任务
                    # 已迁移到 solve/，跳过（避免列表出现指向同一题的两个条目）
                    flat = f"{d.name}-{sub.name}"
                    if (config.PROJECT_ROOT / "solve" / flat).exists():
                        continue
                    if tid not in seen:
                        seen.add(tid)
                        out.append(_task_entry(sub, tid))
    return out


def get_task(task_id: str) -> dict | None:
    for t in list_tasks():
        if t["id"] == task_id:
            return t
    # 兼容：ID 含斜杠的嵌套任务（problems/<年>/<题名>）迁移后工作区在 solve/<年>-<题名>，
    # list_tasks 已把它 dedup 掉，但前端仍用斜杠 ID 轮询 → 从 task_dir 反查已迁移工作区
    d = config.task_dir(task_id)
    if d.exists():
        return _task_entry(d, task_id)
    return None


def list_input_files(task_id: str) -> list[str]:
    """problems/<task_id>/ 下的上传文件（非 output）。"""
    d = config.task_dir(task_id)
    if not d.exists():
        return []
    return [p.name for p in d.iterdir() if p.is_file()]


def safe_artifact_path(task_id: str, rel: str) -> pathlib.Path | None:
    """校验 rel 在 output/ 内（防路径穿越），返回绝对路径或 None。"""
    d = config.task_dir(task_id)
    base = (d / "output").resolve()
    p = (base / rel).resolve()
    if base in p.parents or p == base:
        return p
    return None


def artifacts_tree(task_id: str) -> dict:
    """output/ 下按阶段分组的产物清单。"""
    out = config.task_dir(task_id) / "output"
    if not out.exists():
        return {}
    tree = {}
    for sub in sorted(p for p in out.iterdir() if p.is_dir()):
        files = []
        for p in sorted(sub.rglob("*")):
            if p.is_file():
                rel = p.relative_to(out).as_posix()
                files.append({"path": rel, "size": p.stat().st_size})
        if files:
            tree[sub.name] = files
    for f in ("acceptance_report.md", "run_manifest.json", "run_log.jsonl", "task_state.json"):
        p = out / f
        if p.exists():
            tree.setdefault("root", []).append(
                {"path": f, "size": p.stat().st_size})
    return tree
