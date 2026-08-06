"""机器路径解析 —— 唯一读取机器配置的模块。

优先 .claude/settings.json 的 env，回退 config/machine.json。
供所有 skill 脚本 import，杜绝硬编码路径散落。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

# 本文件位于 .claude/skills/math-modeling-workflow/scripts/ → 项目根在 parents[4]
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]


def _load_machine_json() -> dict:
    p = PROJECT_ROOT / "config" / "machine.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _load_env() -> dict:
    cfg = {}
    for key in ("PYTHON_EXE", "LATEXMK_EXE", "XELATEX_EXE", "TEMPLATE_DIR"):
        v = os.environ.get(key)
        if v:
            cfg[key] = v
    return cfg


_MACHINE = {**_load_machine_json(), **_load_env()}


def get(key: str, default: str = "") -> str:
    return _MACHINE.get(key, default)


def python_exe() -> str:
    return get("PYTHON_EXE", str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"))


def latexmk_exe() -> str:
    return get("LATEXMK_EXE", "latexmk")


def xelatex_exe() -> str:
    return get("XELATEX_EXE", "xelatex")


def template_dir() -> pathlib.Path:
    return pathlib.Path(get("TEMPLATE_DIR", str(PROJECT_ROOT / "templates" / "CUMCMThesis")))


def ensure_utf8_stdout() -> None:
    """Windows 控制台 GBK 编码下，把 stdout/stderr 切到 UTF-8，避免中文 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
