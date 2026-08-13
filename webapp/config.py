"""配置与任务状态读写：config/llm.json + problems/<task>/output/task_state.json。

机器路径解析复用 skill 的 machine.py（parents 推断项目根）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading

# 本文件位于 webapp/ → 项目根在 parents[1]
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

LLM_CONF = PROJECT_ROOT / "config" / "llm.json"
CONF_DIR = LLM_CONF.parent

_lock = threading.Lock()

DEFAULT_LLM = {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "roles": {},  # {"modeler": {"model": "...", "temperature": ...}, "coder": ..., "writer": ...}
}

# 三角色（与 team.AGENTS 一致；此处常量避免循环导入）
ROLES = ("modeler", "coder", "writer")


def ensure_utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_llm_config() -> dict:
    """读取 LLM 配置；不存在则返回默认。api_key 若为空表示未配置。"""
    if LLM_CONF.exists():
        try:
            data = json.loads(LLM_CONF.read_text(encoding="utf-8"))
            cfg = dict(DEFAULT_LLM)
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_LLM})
            if not isinstance(cfg.get("roles"), dict):
                cfg["roles"] = {}
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_LLM)


def load_role_config(role: str) -> dict:
    """返回某角色的模型配置：roles[role] 覆盖全局；未配置时完全回退全局。"""
    cfg = load_llm_config()
    r = (cfg.get("roles") or {}).get(role) or {}
    return {
        "model": r.get("model") or cfg["model"],
        "temperature": (r.get("temperature")
                        if r.get("temperature") is not None else cfg["temperature"]),
    }


def save_llm_config(data: dict) -> dict:
    """保存 LLM 配置（只保留合法字段）。"""
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULT_LLM)
    cfg.update({k: v for k, v in data.items() if k in DEFAULT_LLM})
    cfg["base_url"] = cfg["base_url"].rstrip("/")
    LLM_CONF.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def llm_configured() -> bool:
    return bool(load_llm_config().get("api_key"))


def project_python_exe() -> str:
    """返回项目 .venv 的 Python 路径，回退到当前解释器。"""
    import os as _os
    machine_json = PROJECT_ROOT / "config" / "machine.json"
    if machine_json.exists():
        try:
            cfg = json.loads(machine_json.read_text(encoding="utf-8"))
            exe = cfg.get("PYTHON_EXE", "")
            if exe and pathlib.Path(exe).exists():
                return exe
        except Exception:
            pass
    return _os.environ.get("PYTHON_EXE", sys.executable)


def claude_exe() -> str:
    """查找 claude CLI 路径：machine.json 登记优先，回退 PATH 查找。"""
    import shutil as _shutil
    machine_json = PROJECT_ROOT / "config" / "machine.json"
    if machine_json.exists():
        try:
            cfg = json.loads(machine_json.read_text(encoding="utf-8"))
            exe = cfg.get("CLAUDE_CLI", "")
            if exe and pathlib.Path(exe).exists():
                return exe
        except Exception:
            pass
    found = _shutil.which("claude")
    if found:
        return found
    return "claude"  # 最后回退，让 subprocess 报清晰错误


def claude_model() -> str:
    """返回 webapp 使用的 Claude Code 模型名。默认为 deepseek-v4-flash，
    也可在 config/llm.json 的 webapp.claude_model 字段指定。
    """
    cfg = load_llm_config()
    return cfg.get("webapp", {}).get("claude_model", "deepseek-v4-flash") \
           if isinstance(cfg.get("webapp"), dict) else "deepseek-v4-flash"


def task_dir(task_id: str) -> pathlib.Path:
    """solve/<task_id>/ 优先；嵌套 ID（含 /，problems/<年>/<题名>）解析到 solve/<年>-<题名>
    （与 migrate_to_solve.py 命名一致）；最后回退 problems/<task_id>/（历史兼容）。
    新任务默认创建在 solve/ 下。"""
    solve_dir = PROJECT_ROOT / "solve" / task_id
    if solve_dir.exists():
        return solve_dir
    # 嵌套 problems 任务：solve/<年>-<题名>
    flat = task_id.replace("/", "-").replace("\\", "-")
    if flat != task_id:
        solve_flat = PROJECT_ROOT / "solve" / flat
        if solve_flat.exists():
            return solve_flat
    legacy = PROJECT_ROOT / "problems" / task_id
    if legacy.exists():
        return legacy
    return solve_dir  # 新任务默认 solve/


def state_path(task_dir_: pathlib.Path) -> pathlib.Path:
    return task_dir_ / "output" / "task_state.json"


def _empty_state(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "stage": "",            # 当前阶段 P1..P6
        "status": "idle",       # idle | running | done | failed
        "logs": [],             # [{ts, level, msg}]
        "error": "",
        "artifacts": {},        # stage -> [relpath,...]
        "updated": "",
    }


def load_state(task_dir_: pathlib.Path) -> dict:
    p = state_path(task_dir_)
    if p.exists():
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
            st.setdefault("logs", [])
            st.setdefault("artifacts", {})
            return st
        except Exception:
            pass
    return _empty_state(task_dir_.name)


def save_state(task_dir_: pathlib.Path, state: dict) -> None:
    import time
    state["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    p = state_path(task_dir_)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
