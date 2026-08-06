"""公共工具：路径 / 哈希 / 日志。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from typing import Iterable, Optional

import machine as M


def sha256(path: pathlib.Path, chunk: int = 1 << 16) -> Optional[str]:
    """返回文件 SHA-256；不存在返回 None。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def file_info(path: pathlib.Path) -> Optional[dict]:
    if not path.exists() or not path.is_file():
        return None
    st = path.stat()
    return {"sha256": sha256(path), "size": st.st_size, "mtime": st.st_mtime}


def glob_many(patterns: Iterable[str], base: pathlib.Path) -> list[pathlib.Path]:
    """按多个 glob 模式收集文件（相对 base）。"""
    out = []
    for pat in patterns:
        out.extend(base.glob(pat))
    return sorted({p.resolve() for p in out})


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: pathlib.Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    print(msg, flush=True)


def err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)


# 各阶段必需交付物（gate 强校验用）
REQUIRED_OUTPUTS = {
    "P1": ["analysis/problem_summary.md"],
    "P2": ["analysis/model_spec.md", "analysis/symbols.md"],
    "P3": ["code/solve_q*.py", "code/result_q*.json"],
    "P4": ["figures/*.png"],
    "P5": ["paper/main.tex", "paper/main.pdf"],
    "P6": ["acceptance_report.md"],
}

# 阶段顺序
STAGE_ORDER = ["P1", "P2", "P3", "P4", "P5", "P6"]
