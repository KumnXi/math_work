"""傻瓜建模网页 — FastAPI 入口。

启动：bash scripts/run_web.sh  （或 .venv/Scripts/python.exe -m uvicorn webapp.app:app --port 8000）
仅本机 127.0.0.1。
"""
from __future__ import annotations

import pathlib
import re
import threading

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, llm_client, pipeline, tasks

app = FastAPI(title="傻瓜建模", version="0.1")

STATIC = pathlib.Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

VALID_TASK_ID = re.compile(r"^[\w\-]{1,64}$")


# ---------- 配置 ----------

class LLMConfigIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3
    roles: dict = Field(default_factory=dict)  # {"modeler":{"model":...},...}


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))


@app.get("/api/config")
def get_config():
    cfg = config.load_llm_config()
    return {"configured": bool(cfg.get("api_key")),
            "base_url": cfg["base_url"], "model": cfg["model"],
            "temperature": cfg["temperature"],
            "roles": cfg.get("roles", {})}


@app.post("/api/config")
def post_config(data: LLMConfigIn):
    cfg = config.save_llm_config(data.model_dump())
    return {"ok": True, "configured": bool(cfg.get("api_key"))}


@app.post("/api/config/test")
def test_config(data: LLMConfigIn):
    # 临时用提交的配置测试连通（不改持久配置）
    saved = config.load_llm_config()
    config.save_llm_config(data.model_dump())
    try:
        r = llm_client.test_connection()
    finally:
        config.save_llm_config(saved)
    return r


# ---------- 任务 ----------

@app.get("/api/tasks")
def list_tasks():
    return tasks.list_tasks()


@app.post("/api/tasks")
async def create_task(
    task_id: str = Form(""),
    statement: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
):
    """创建任务：上传题面 + 数据文件到 solve/<task_id>/（工作区，problems/ 保持纯存档）。"""
    if not task_id.strip():
        if statement and statement.filename:
            task_id = pathlib.Path(statement.filename).stem
        else:
            raise HTTPException(400, "请提供任务名或题面文件")
    task_id = task_id.strip().replace(" ", "_")
    if not VALID_TASK_ID.match(task_id):
        raise HTTPException(400, f"任务名非法：{task_id!r}（仅限字母数字-下划线，≤64字符）")
    d = config.task_dir(task_id)
    d.mkdir(parents=True, exist_ok=True)
    saved = []
    uploads = ([statement] if statement and statement.filename else []) + (files or [])
    for f in uploads:
        if not f.filename:
            continue
        name = pathlib.Path(f.filename).name
        if not name or name in (".", ".."):
            continue
        dest = d / name
        dest.write_bytes(await f.read())
        saved.append(name)
    if not saved:
        raise HTTPException(400, "没有可保存的文件")
    state = config.load_state(d)
    state["status"] = "new"
    config.save_state(d, state)
    return {"ok": True, "task_id": task_id, "files": saved}


def _task_or_404(task_id: str):
    t = tasks.get_task(task_id)
    if t is None:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return t


@app.post("/api/tasks/{task_id:path}/run")
def run_task(task_id: str, from_stage: str = Form("P1")):
    _task_or_404(task_id)
    if from_stage not in pipeline.STAGES:
        raise HTTPException(400, f"from_stage 非法：{from_stage}")
    if not config.llm_configured():
        raise HTTPException(400, "尚未配置 LLM API Key（右上角设置）")
    # 若任务仍在 problems/（只读存档区），先自动迁移到 solve/ 工作区再运行
    _ensure_working_dir(task_id)
    state = config.load_state(config.task_dir(task_id))
    if state.get("status") == "running":
        raise HTTPException(409, "任务已在运行中")
    t = threading.Thread(target=pipeline.run_task, args=(task_id, from_stage),
                         daemon=True, name=f"task-{task_id}")
    t.start()
    return {"ok": True, "task_id": task_id, "from_stage": from_stage}


def _ensure_working_dir(task_id: str) -> None:
    """CLAUDE.md 铁律：problems/ 为只读存档区，禁止出现 output/。
    若任务工作区仍指向 problems/ 下（嵌套 problems/<年>/<题名>），
    用 scripts/migrate_to_solve.py 复制题目到 solve/ 后返回，使 task_dir 解析到 solve/。"""
    import subprocess
    import sys
    d = config.task_dir(task_id).resolve()
    problems_root = (config.PROJECT_ROOT / "problems").resolve()
    if d.parent != problems_root and problems_root not in d.parents:
        return  # 已在 solve/ 工作区
    migrate_script = config.PROJECT_ROOT / "scripts" / "migrate_to_solve.py"
    if not migrate_script.exists():
        raise HTTPException(500, "迁移脚本缺失，无法把题目复制到工作区")
    py_exe = config.project_python_exe()
    result = subprocess.run(
        [py_exe, str(migrate_script), str(d)],
        capture_output=True, text=True, timeout=120,
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "未知错误"
        raise HTTPException(500, f"任务迁移到工作区失败: {err[:200]}")
    # 迁移后 task_dir 应解析到 solve/<年>-<题名>
    if config.task_dir(task_id).resolve().parent == problems_root:
        raise HTTPException(500, "任务迁移后仍指向 problems/，请检查目录命名")


@app.get("/api/tasks/{task_id:path}/status")
def task_status(task_id: str):
    _task_or_404(task_id)
    d = config.task_dir(task_id)
    state = config.load_state(d)
    status = state.get("status", "new")
    # 回退：历史任务（脚手架产出、无 task_state.json）但产物齐全 → 视为完成
    if status in ("new", "idle") and (d / "output" / "run_manifest.json").exists():
        status = "done"
    return {
        "task_id": task_id,
        "status": status,
        "stage": state.get("stage", ""),
        "stage_name": pipeline.STAGE_NAMES.get(state.get("stage", ""), ""),
        "logs": state.get("logs", []),
        "error": state.get("error", ""),
        "team": state.get("team", {}),
        "updated": state.get("updated", ""),
    }


@app.get("/api/tasks/{task_id:path}/artifacts")
def task_artifacts(task_id: str):
    _task_or_404(task_id)
    return tasks.artifacts_tree(task_id)


@app.get("/api/tasks/{task_id:path}/file")
def task_file(task_id: str, path: str):
    """读取产物文本（限制在 output/ 内）。png 用 /preview，pdf 用 /paper。"""
    _task_or_404(task_id)
    p = tasks.safe_artifact_path(task_id, path)
    if p is None or not p.exists() or not p.is_file():
        raise HTTPException(404, f"产物不存在: {path}")
    sfx = p.suffix.lower()
    if sfx == ".png":
        return FileResponse(str(p), media_type="image/png")
    if sfx == ".pdf":
        return FileResponse(str(p), media_type="application/pdf")
    content = p.read_bytes()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="replace")
    return JSONResponse({"name": p.name, "content": text})


@app.post("/api/tasks/{task_id:path}/stages/{stage}/rerun")
def rerun_stage(task_id: str, stage: str):
    _task_or_404(task_id)
    if stage not in pipeline.STAGES:
        raise HTTPException(400, f"stage 非法：{stage}")
    return run_task(task_id, from_stage=stage)


@app.get("/api/tasks/{task_id:path}/paper")
def task_paper(task_id: str):
    _task_or_404(task_id)
    pdf = config.task_dir(task_id) / "output" / "paper" / "main.pdf"
    if not pdf.exists():
        raise HTTPException(404, "论文 PDF 尚未生成（先运行任务）")
    return FileResponse(str(pdf), media_type="application/pdf",
                        filename=f"{task_id}_main.pdf")


@app.get("/api/tasks/{task_id:path}/word")
def task_word(task_id: str):
    """返回 Word 文档（.docx），若尚未生成则自动触发生成。"""
    _task_or_404(task_id)
    d = config.task_dir(task_id)
    docx = d / "output" / "paper" / "main.docx"
    if not docx.exists():
        # 自动触发生成
        gen_script = config.PROJECT_ROOT / "tools" / "generate_docx.py"
        if not gen_script.exists():
            raise HTTPException(404, "Word 生成脚本不存在")
        import subprocess
        import sys
        py_exe = config.project_python_exe()
        try:
            result = subprocess.run(
                [py_exe, str(gen_script), str(d)],
                capture_output=True, text=True, timeout=60,
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(500, "Word 生成超时（>60s），请重试")
        if not docx.exists():
            err = result.stderr.strip() or result.stdout.strip() or "未知错误"
            raise HTTPException(500, f"Word 生成失败: {err[:200]}")
    return FileResponse(str(docx),
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        filename=f"{task_id}_main.docx")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
