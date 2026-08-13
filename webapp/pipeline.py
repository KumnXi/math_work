"""六阶段执行器：每阶段用独立 claude -p 调用（上下文隔离，仿 MathModelAgent 模式）。

每个任务 = solve/<task_id>/（回退 problems/<task_id>/），产出 output/{analysis,code,figures,paper,*.json,*.md}。
阶段状态写入 output/task_state.json，前端轮询 /status 获取进度。

关键设计：每阶段是一个独立的 claude -p 子进程，只通过磁盘文件传递上下文，
不存在跨阶段累积的 LLM 对话。这解决了原 DeepSeek API 单次长对话上下文爆炸的问题。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time

from . import config

# 定位 skill scripts 与 tools（复用现有脚本）
SCRIPTS = config.PROJECT_ROOT / ".claude" / "skills" / "math-modeling-workflow" / "scripts"
TOOLS = config.PROJECT_ROOT / "tools"
TEMPLATES = config.PROJECT_ROOT / "templates" / "CUMCMThesis"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TOOLS))

import machine as M            # noqa: E402  机器路径（PYTHON_EXE 等）
import preprocess               # noqa: E402  eda_report(df)

STAGES = ["P1", "P2", "P3", "P4", "P5", "P6"]
STAGE_NAMES = {"P1": "读题分析", "P2": "建模", "P3": "编程求解",
               "P4": "出图", "P5": "论文写作", "P6": "验收"}

# 阶段失败自动重试次数（回滚 output/ 到阶段前快照后重跑，应对网络瞬断等瞬态错误）
MAX_STAGE_RETRY = 3

# 每阶段默认的 claude -p 配置
STAGE_CONFIG = {
    "P1": {"max_turns": 30, "timeout": 900},
    "P2": {"max_turns": 30, "timeout": 900},
    "P3": {"max_turns": 200, "timeout": 7200},
    "P4": {"max_turns": 100, "timeout": 3600},
    "P5": {"max_turns": 120, "timeout": 3600},
    "P6": {"max_turns": 60, "timeout": 1800},
}


# ---------- 基础工具 ----------

def _py_exe() -> str:
    return M.python_exe()


def _task_dir(task_id: str) -> pathlib.Path:
    return config.task_dir(task_id)


def log(state: dict, task_dir: pathlib.Path, msg: str, level: str = "info") -> None:
    import time
    state["logs"].append({"ts": time.strftime("%H:%M:%S"), "level": level, "msg": msg})
    if len(state["logs"]) > 2000:
        state["logs"] = state["logs"][-1500:]
    config.save_state(task_dir, state)


def run_script(cmd: list[str], cwd: pathlib.Path, timeout: int = 600) -> tuple[int, str, str]:
    """运行本机脚本（env 强制 UTF-8），返回 (exit_code, stdout, stderr)。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"运行超时（>{timeout}s）"
    except Exception as e:      # noqa: BLE001
        return -1, "", f"启动失败: {e}"


def record(task_id: str, stage: str, inputs: list[str], outputs: list[str],
           cmd: str, exit_code: int) -> None:
    """subprocess 调 make_manifest.py record（inputs 相对 problem_dir 根，outputs 相对 output/）。"""
    p = _task_dir(task_id)
    args = [_py_exe(), str(SCRIPTS / "make_manifest.py"), "record", str(p), stage,
            "--inputs", ",".join(inputs), "--outputs", ",".join(outputs),
            "--cmd", cmd, "--exit-code", str(exit_code)]
    run_script(args, p)


def _gate(task_id: str, stage: str) -> bool:
    """校验 <stage> 前一阶段产物。P1 无前置返回 True。"""
    if stage == "P1":
        return True
    p = _task_dir(task_id)
    rc, _, _err = run_script(
        [_py_exe(), str(SCRIPTS / "verify_manifest.py"), "gate", str(p), stage], p)
    return rc == 0


# 阶段失败回退：快照 + 回滚，允许自动重试（如 Claude Code 网络瞬断）
# 排除进程日志/状态文件——它们是审计与运行状态，不参与回滚。
_SNAP_EXCLUDE = {"task_state.json", "claude_run.log"}


def _snapshot_output(out_dir: pathlib.Path) -> dict[str, bytes]:
    """快照 output/ 全部文件内容（排除状态/日志），供失败回滚。"""
    snap: dict[str, bytes] = {}
    if not out_dir.exists():
        return snap
    for root, _dirs, files in os.walk(out_dir):
        root_p = pathlib.Path(root)
        for fn in files:
            if fn in _SNAP_EXCLUDE:
                continue
            p = root_p / fn
            try:
                snap[p.relative_to(out_dir).as_posix()] = p.read_bytes()
            except OSError:
                pass      # 文件被并发删除，忽略
    return snap


def _rollback_output(out_dir: pathlib.Path, snap: dict[str, bytes]) -> int:
    """把 output/ 恢复到快照状态：删除新增文件、还原被改动文件。返回处理文件数。"""
    if not out_dir.exists():
        return 0
    restored = 0
    for root, _dirs, files in os.walk(out_dir):
        root_p = pathlib.Path(root)
        for fn in files:
            if fn in _SNAP_EXCLUDE:
                continue
            p = root_p / fn
            rel = p.relative_to(out_dir).as_posix()
            if rel not in snap:
                p.unlink(missing_ok=True)            # 本次新增 → 删除
                restored += 1
            else:
                try:
                    if p.read_bytes() != snap[rel]:  # 本次被改动 → 还原
                        p.write_bytes(snap[rel])
                        restored += 1
                except OSError:
                    pass
    # 清理删除产生的空目录（含 .snapshot 之类临时目录）
    for root, dirs, _files in os.walk(out_dir, topdown=False):
        for dn in dirs:
            try:
                (pathlib.Path(root) / dn).rmdir()
            except OSError:
                pass
    return restored


# ---------- Claude Code 调用 ----------

def run_claude(prompt: str, cwd: pathlib.Path, *,
               model: str | None = None,
               max_turns: int = 30,
               timeout: int = 1200) -> tuple[int, str, str]:
    """运行单次 `claude -p` 调用（headless，无交互权限提示）。
    返回 (exit_code, stdout, stderr)。

    Claude Code 通过 --cwd 感知项目根目录（自动发现 CLAUDE.md）并继承
    机器路径铁律（$PYTHON_EXE 等）。
    """
    if model is None:
        model = config.claude_model()

    cli = config.claude_exe()
    # prompt 经 stdin 传入（而非命令行参数）：多行/含引号/路径反斜杠的 prompt
    # 作为 argv 传给 claude -p 会在 Windows 上触发 CreateProcess 参数转义问题，
    # 导致 claude 异常退出（rc=143、空输出）。
    cmd = [
        cli, "-p",
        "--model", model,
        "--max-turns", str(max_turns),
        "--dangerously-skip-permissions",
        "--add-dir", str(config.PROJECT_ROOT),
        "--output-format", "text",
    ]

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = "200000"

    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            env=env, timeout=timeout, input=prompt,
        )
        # 记录 claude -p 原始输出，便于诊断（append 到 output/claude_run.log）
        try:
            log_path = cwd / "output" / "claude_run.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"\n===== claude -p (rc={proc.returncode}) =====\n")
                lf.write(f"[STDOUT]\n{proc.stdout or '(空)'}\n")
                lf.write(f"[STDERR]\n{proc.stderr or '(空)'}\n")
        except Exception:
            pass
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"claude -p 超时（>{timeout}s）"
    except FileNotFoundError:
        return -1, "", (
            f"找不到 claude CLI（{cli}）。请确认已安装 Claude Code：\n"
            "  npm install -g @anthropic-ai/claude-code\n"
            "或设置 config/machine.json 中的 CLAUDE_CLI 字段。"
        )
    except Exception as e:      # noqa: BLE001
        return -1, "", f"claude -p 启动失败: {e}"


# ---------- 文件读取 ----------

def read_input_files(task_id: str) -> tuple[str, list[str]]:
    """读取题面文本 + 数据文件列表。"""
    d = _task_dir(task_id)
    statement_text = ""
    data_files: list[str] = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.suffix.lower() in (".json", ".jsonl"):
            continue
        sfx = f.suffix.lower()
        try:
            if sfx == ".docx":
                from docx import Document
                doc = Document(str(f))
                statement_text += "\n".join(p.text for p in doc.paragraphs if p.text)
            elif sfx == ".pdf":
                import fitz
                doc = fitz.open(str(f))
                statement_text += "\n".join(pg.get_text() for pg in doc)
            elif sfx in (".csv", ".xlsx", ".xls", ".txt"):
                data_files.append(f.name)
        except Exception as e:      # noqa: BLE001
            log({}, d, f"读取 {f.name} 失败: {e}", "error")
    return statement_text, data_files


def eda_markdown(task_id: str, data_files: list[str]) -> str:
    """对每个数据附件生成 EDA markdown 片段。"""
    d = _task_dir(task_id)
    chunks = []
    import pandas as pd
    for name in data_files:
        p = d / name
        try:
            if p.suffix.lower() == ".csv":
                df = pd.read_csv(p, comment="#")
            elif p.suffix.lower() in (".xlsx", ".xls"):
                df = pd.read_excel(p)
            else:
                df = pd.read_csv(p, sep=r"\s+", comment="#")
            chunks.append(f"## 附件 {name}\n\n{preprocess.eda_report(df)}\n")
        except Exception as e:      # noqa: BLE001
            chunks.append(f"## 附件 {name}\n\n（无法解析: {e}）\n")
    return "\n".join(chunks)


def collect_results(task_id: str) -> dict:
    """读取 code/result_q*.json 合并为 dict。"""
    code_dir = _task_dir(task_id) / "output" / "code"
    merged = {}
    if code_dir.exists():
        for rp in sorted(code_dir.glob("result_q*.json")):
            try:
                merged[rp.stem] = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                pass
    return merged


def _prev_p1_inputs(task_id: str) -> list[str]:
    """P1 输入 = 上传文件（非 output）。"""
    d = _task_dir(task_id)
    return [f.name for f in d.iterdir()
            if f.is_file() and f.suffix.lower() not in (".json", ".jsonl")]


# ---------- 提示词构建 ----------

def _ctx_prefix(task_id: str) -> str:
    """所有阶段共用的上下文前缀：机器路径 + 项目约定。"""
    d = _task_dir(task_id)
    return (
        f"你是数学建模竞赛团队的执行引擎，负责完成一个独立阶段的任务。\n\n"
        f"【项目环境】\n"
        f"- 工作目录：{d}\n"
        f"- 项目根目录：{config.PROJECT_ROOT}\n"
        f"- Python 解释器：{M.python_exe()}（**禁止裸 python**，一律用此路径）\n"
        f"- LaTeX：{os.environ.get('LATEXMK_EXE', 'latexmk')} / {os.environ.get('XELATEX_EXE', 'xelatex')}\n"
        f"- 控制台 GBK 编码，Python 输出中文需 PYTHONIOENCODING=utf-8\n"
        f"- 路径含空格（D:\\Jupyter code\\math_work），shell 命令一律双引号包裹\n\n"
        f"【产出目录约定】\n"
        f"- 所有产出在 {d / 'output'}/ 下\n"
        f"- analysis/：分析文档\n"
        f"- code/：求解代码 + result JSON\n"
        f"- figures/：论文图表（PNG，300dpi）\n"
        f"- paper/：LaTeX 论文 + PDF + DOCX\n"
        f"- run_manifest.json：产物清单（由 make_manifest.py 管理）\n\n"
        f"【铁律】\n"
        f"- 所有 Python 命令一律用 {M.python_exe()}，禁止裸 python\n"
        f"- 所有数值必须来自实际运行代码，禁止编造\n"
        f"- 每个阶段完成后必须运行 manifest gate 检查\n"
        f"- 代码放在 {d / 'output' / 'code'}/ 下，读取数据文件从 {d}/ 目录\n\n"
        f"【执行方式（必须遵守）】\n"
        f"你必须用工具真实执行，不能只在回复里描述步骤：\n"
        f"- 用 Write 工具真实创建/覆盖文件（不要只在回复里粘贴代码或文字）\n"
        f"- 用 Bash 工具真实运行命令（运行 Python 脚本、编译 LaTeX 等）\n"
        f"- 每个输出文件都必须实际写入磁盘、每次运行都必须真实执行才算完成\n"
        f"- 完成后用一两句话简要回复完成情况即可\n"
    )


def _build_p1_prompt(task_id: str) -> str:
    """P1 读题分析：阅读题面 + 数据 EDA → 产出 problem_summary.md"""
    d = _task_dir(task_id)
    prefix = _ctx_prefix(task_id)
    stmt, data_files = read_input_files(task_id)
    eda = eda_markdown(task_id, data_files)
    return (
        f"{prefix}\n"
        f"===== 阶段 P1：读题分析 =====\n\n"
        f"【任务】分析赛题，拆解子问题，形成《问题分析》文档。\n\n"
        f"【题面文本】\n{stmt[:20000]}\n\n"
        f"【数据附件 EDA】\n{eda}\n\n"
        f"【操作步骤】\n"
        f"1. 先读取题面文件（{d}/ 下的 PDF/DOCX）和数据文件（{d}/ 下的 CSV/XLSX）\n"
        f"2. 对每个数据文件用 tools/preprocess.py 做 EDA（或直接 pd.read + describe）\n"
        f"3. 撰写 {d}/output/analysis/problem_summary.md\n\n"
        f"【输出要求】\n"
        f"文件路径：{d}/output/analysis/problem_summary.md\n"
        f"结构必须包含：\n"
        f"1. 问题重述（用自己的话转述题目背景与要解决的问题）\n"
        f"2. 数据字典（每个附件每列的列名/含义/单位）\n"
        f"3. 关键参数清单（题目中给出的所有数字参数及其含义）\n"
        f"4. 子问题定义（Q1..Qn：每个子问题的目标、约束、输入、输出）\n\n"
        f"用中文撰写，标题层级用 #/##/###。不要输出 markdown 以外的内容。\n"
    )


def _build_p2_prompt(task_id: str) -> str:
    """P2 建模：读 P1 → 产出 model_spec.md + symbols.md"""
    prefix = _ctx_prefix(task_id)
    d = _task_dir(task_id)
    p1_path = d / "output" / "analysis" / "problem_summary.md"
    return (
        f"{prefix}\n"
        f"===== 阶段 P2：建模 =====\n\n"
        f"【任务】基于问题分析，为每个子问题建立完整数学模型。\n\n"
        f"【输入】请先完整阅读 {p1_path}\n\n"
        f"【操作步骤】\n"
        f"1. 读取 {d}/output/analysis/problem_summary.md\n"
        f"2. 撰写以下两个文件：\n\n"
        f"【输出要求】\n\n"
        f"文件 1：{d}/output/analysis/model_spec.md\n"
        f"- 0. 模型假设（逐条编号，严格数学语言，可检验，3-8 条）\n"
        f"- 1..n. 每个子问题：决策变量、目标函数、约束条件的 LaTeX 数学表达\n"
        f"- 求解算法选择及理由（优化用整数规划/启发式；预测用回归；评价用 TOPSIS 等，宁简勿繁）\n"
        f"- **每个子问题至少给出 2 种备选方案对比表**（列 = 对应问题 | 算法名称 | 算法核心逻辑 | "
        f"实现难度(低/中/高) | 优缺点对比 | 创新性；选中方案在表中标注「选用」并写一句理由）\n\n"
        f"文件 2：{d}/output/analysis/symbols.md\n"
        f"- 符号表（| 符号 | 含义 | 单位 | 三线表），覆盖全部变量\n\n"
        f"用中文撰写。\n"
    )


def _build_p3_prompt(task_id: str) -> str:
    """P3 编程求解：读 P1+P2 → 写求解脚本 → 运行 → 产出 result JSON/TXT"""
    prefix = _ctx_prefix(task_id)
    d = _task_dir(task_id)
    p1_path = d / "output" / "analysis" / "problem_summary.md"
    p2_path = d / "output" / "analysis" / "model_spec.md"
    inputs = _prev_p1_inputs(task_id)
    return (
        f"{prefix}\n"
        f"===== 阶段 P3：编程求解 =====\n\n"
        f"【任务】把数学模型落实为可运行 Python 代码，产出每个子问题的求解结果。\n\n"
        f"【输入文件】\n"
        f"- 问题分析：{p1_path}\n"
        f"- 模型规格：{p2_path}\n"
        f"- 数据文件（在 {d}/ 下）：{inputs}\n\n"
        f"【硬性要求】\n"
        f"- 为每个子问题写一个独立、可运行的 Python 脚本 solve_qN.py，放在 {d}/output/code/ 下\n"
        f"- 每个脚本用 `pathlib.Path(__file__).resolve().parents[2]` 定位到 {d}/ 目录来读取附件\n"
        f"- 每个脚本输出两个文件到同目录：`result_qN.json`（机器可读，全部数值用原生 int/float）"
        f"和 `result_qN.txt`（人读摘要）\n"
        f"- 只允许用已安装的库：numpy/pandas/scipy/matplotlib/ortools\n"
        f"- 组合优化用 CP-SAT（from ortools.sat.python import cp_model）或启发式；预测用回归\n"
        f"- 务必真实求解，禁止编造结果；运行前先确保脚本能跑通\n"
        f"- Python 解释器一律用 {M.python_exe()}；运行设置 PYTHONIOENCODING=utf-8\n\n"
        f"【操作流程】\n"
        f"1. 阅读 P1 和 P2 的输出，确认子问题数量\n"
        f"2. 对每个子问题 N：编写 solve_qN.py → 运行 → 检查 exit code → 有错就修 → 直到成功\n"
        f"3. 每个脚本跑通后，核对 result JSON 数值合理性（非空/量纲正确/数量级合理）\n\n"
        f"【质量要求】\n"
        f"- 每个子问题必须有对应的 solve_qN.py 和 result_qN.json + result_qN.txt\n"
        f"- JSON 内容不能为空，不能是占位值（如全 0）；数值量纲要合理\n"
        f"- 若某个脚本反复修不好（超过 4 次），记录错误信息并继续下一个"
    )


def _build_p4_prompt(task_id: str) -> str:
    """P4 出图：读 result JSON → 生成论文图表 + 技术路线图"""
    prefix = _ctx_prefix(task_id)
    d = _task_dir(task_id)
    code_dir = d / "output" / "code"
    return (
        f"{prefix}\n"
        f"===== 阶段 P4：出图 =====\n\n"
        f"【任务】根据求解结果生成论文级图表（300dpi PNG）。\n\n"
        f"【输入】读取 {code_dir}/ 下所有 result_q*.json 文件\n\n"
        f"【操作步骤】\n"
        f"1. 先读取所有 result_q*.json，了解有哪些数据可用\n"
        f"2. 编写 {code_dir}/make_figures.py 脚本\n"
        f"3. 运行脚本，检查输出，如有错误修复后重试\n"
        f"4. 运行 tools/check_figures.py 检查图质量\n"
        f"5. 如有空白/损坏图，修复 make_figures.py 重出\n\n"
        f"【硬性要求】\n"
        f"- 脚本开头加：sys.path.insert(0, '{TOOLS}') 然后用 `import figure_style as fs`\n"
        f"  （fs 提供 fs.PALETTE 论文配色、fs.new_axes(w,h) 创建画布、fs.save(fig, path) 保存 300dpi）\n"
        f"- 图表保存到 {d}/output/figures/ 下，文件名 fig_*.png\n"
        f"- 中文标题/坐标轴/图例；坐标轴带单位\n"
        f"- **必须生成一张 `fig_pipeline.png`**：《问题分析与技术路线图》——方框+箭头表达\n"
        f"  「读题→数据→子问题拆解→建模→求解→验证」的整体技术路线，中文标注\n"
        f"- 数据必须来自 result JSON 或附件，禁止编造\n"
        f"- 典型图表：轨迹图、碰撞检测结果、参数灵敏度曲线、速度分布图等（根据实际数据内容决定）\n\n"
        f"【质量检查】\n"
        f"生成图表后运行：{M.python_exe()} {TOOLS / 'check_figures.py'} {d / 'output' / 'figures'}\n"
        f"检查报告写入 {d}/output/figures/check_report.json。有问题（空白/损坏/缺轴标签）必须修复。\n"
    )


def _build_p5_prompt(task_id: str) -> str:
    """P5 论文写作：读全部产出 → 写 LaTeX 论文 → 编译 → 生成 DOCX"""
    prefix = _ctx_prefix(task_id)
    d = _task_dir(task_id)
    paper_dir = d / "output" / "paper"
    return (
        f"{prefix}\n"
        f"===== 阶段 P5：论文写作 =====\n\n"
        f"【任务】撰写完整可编译的国赛 CUMCM LaTeX 论文，编译 PDF，生成完整版 Word。\n\n"
        f"【输入文件】\n"
        f"- 问题分析：{d}/output/analysis/problem_summary.md\n"
        f"- 模型规格：{d}/output/analysis/model_spec.md\n"
        f"- 符号表：{d}/output/analysis/symbols.md\n"
        f"- 求解结果：{d}/output/code/result_q*.json\n"
        f"- 图表：{d}/output/figures/fig_*.png\n\n"
        f"【操作步骤】\n"
        f"1. 先通读以上全部文件，了解建模与求解全貌\n"
        f"2. 复制 {TEMPLATES / 'cumcmthesis.cls'} 到 {paper_dir}/cumcmthesis.cls\n"
        f"3. 编写 {paper_dir}/main.tex（完整论文正文，不依赖外部章节文件）\n"
        f"4. 用 latex_check.py 编译：{M.python_exe()} {SCRIPTS / 'latex_check.py'} {d}\n"
        f"5. 编译如有错误（exit≠0、undefined ref、undefined cite、fatal error），修复后重编译\n"
        f"6. 编译通过后生成 Word：{M.python_exe()} {TOOLS / 'generate_docx.py'} {d}\n\n"
        f"【论文硬性要求】\n"
        f"- 文档类：\\documentclass[withoutpreface,bwprint]{{cumcmthesis}}\n"
        f"- 图路径：\\includegraphics[width=0.9\\textwidth]{{../figures/fig_xxx.png}}\n"
        f"- 代码附录：\\lstinputlisting{{../code/solve_q1.py}}\n"
        f"- 排版规范：一级标题黑体三号加黑居中/二级黑体四号加黑/三级宋体小四加黑/正文宋体小四；\n"
        f"  每段首行缩进 2 字符、单倍行距、正文字体不加宽；图片/表格/公式全部居中；\n"
        f"  表注在表格上面(段前0.3-0.5行)、图注在图形下面(段后0.3-0.5行)；\n"
        f"  表格用三线表(booktabs)、表内居中；图用 figure[H] 嵌入模式固定位置\n"
        f"- 章节骨架：摘要(独立页,第一段3-4排,必含每问具体数值结果,不插公式,无第一人称) + 关键词(靠底部)；\n"
        f"  一问题重述(1.1问题背景/1.2题设数据/1.3需解决的问题,用自己的话不照抄,不处理数据不做图)；\n"
        f"  二模型假设(3-5个)；三符号说明(不设表头,字母用公式排版,整表一页内不跨页)；\n"
        f"  四问题分析(先分析后建模,不出现模型公式/字母,各问不严重失衡,必含技术路线图 fig_pipeline.png)；\n"
        f"  五数据分析(只分析有用数据,图表不要竖着连续放,每个图表前后有文字)；\n"
        f"  六问题一的模型建立与求解(6.1模型建立-公式前1-3行解释/6.2模型求解-方法步骤或算法框图+答案必放/"
        f"6.3结果分析-不只重复数据,要结合数据解释结果差异产生的原因,并说明实际指导价值)；\n"
        f"  七问题二的模型建立与求解(同结构)；八模型的评价(8.1优点 8.2缺点,优点>缺点)；九模型的改进与推广；\n"
        f"  参考文献(GB/T 7714 真实文献)；附录(代码)\n"
        f"- AI 工具使用声明（2026 国赛规定）：在参考文献之前插入 "
        f"\\section*{{AI 工具使用声明}}，内容为：\"本参赛队在竞赛过程中使用了 AI 工具，"
        f"主要用于语言润色、代码调试与论文排版，详细使用情况见支撑材料。\"\n"
        f"- 所有数值只能来自实际求解结果 JSON —— 禁止编造；公式用 equation 环境并 label\n"
        f"- 不要加载 hyperref（cls 已加载），避免选项冲突\n"
        f"- 参考文献必须是真实可查的，使用 GB/T 7714 格式\n"
        f"- 正文 ≤25 页，摘要独立页 ≤1 页\n"
    )


def _build_p6_prompt(task_id: str) -> str:
    """P6 验收：运行 acceptance.py → 修复失败项 → 重跑直到全部通过"""
    prefix = _ctx_prefix(task_id)
    d = _task_dir(task_id)
    return (
        f"{prefix}\n"
        f"===== 阶段 P6：验收 =====\n\n"
        f"【任务】运行全面验收，修复所有不通过项，直到全部通过。\n\n"
        f"【操作步骤】\n"
        f"1. 运行验收脚本：{M.python_exe()} {SCRIPTS / 'acceptance.py'} {d}\n"
        f"2. 查看输出——exit code 0 表示全部通过，非 0 表示有未通过项\n"
        f"3. 若未通过：阅读 {d}/output/acceptance_report.md 查看具体失败项\n"
        f"4. 根据失败项定位并修复：\n"
        f"   - LaTeX 编译问题 → 修复 main.tex 重编译\n"
        f"   - 代码可复现问题 → 修复对应 solve_qN.py 重跑\n"
        f"   - 图质量问题 → 修复 make_figures.py 重出图\n"
        f"   - 数值一致性问题 → 核对 result JSON 与论文中的数字\n"
        f"   - 论文要素缺失 → 补充缺失章节（如灵敏度分析、参考文献）\n"
        f"5. 修复后重新运行验收，直到全部通过（最多 3 轮）\n\n"
        f"【验收 11 项（A1-A11）】\n"
        f"A1 完整性 / A2 文本泄漏与占位符 / A3 数值一致性 / A4 图表引用完整 /\n"
        f"A5 LaTeX 编译 / A6 模型形式化 / A7 论文要素齐全 / A8 格式规范 /\n"
        f"A9 代码可复现 / A10 图质量 / A11 PDF 视觉\n"
    )


# ---------- 阶段函数 ----------

def stage_p1(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    cfg = STAGE_CONFIG["P1"]
    prompt = _build_p1_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P1 读题分析…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P1 Claude Code 退出码 {rc}\n{err[-1500:]}")
    p1_out = d / "output" / "analysis" / "problem_summary.md"
    if not p1_out.exists():
        raise RuntimeError("P1: problem_summary.md 未生成")
    record(task_id, "P1", _prev_p1_inputs(task_id),
           ["analysis/problem_summary.md"],
           "claude -p (P1 读题分析)", rc)
    log(state, d, "[Claude Code] P1 完成 ✅")


def stage_p2(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    cfg = STAGE_CONFIG["P2"]
    prompt = _build_p2_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P2 建模…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P2 Claude Code 退出码 {rc}\n{err[-1500:]}")
    for name in ("model_spec.md", "symbols.md"):
        if not (d / "output" / "analysis" / name).exists():
            raise RuntimeError(f"P2: {name} 未生成")
    record(task_id, "P2", ["output/analysis/problem_summary.md"],
           ["analysis/model_spec.md", "analysis/symbols.md"],
           "claude -p (P2 建模)", rc)
    log(state, d, "[Claude Code] P2 完成 ✅")


def stage_p3(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    cfg = STAGE_CONFIG["P3"]
    prompt = _build_p3_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P3 编程求解…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P3 Claude Code 退出码 {rc}\n{err[-1500:]}")
    code_dir = d / "output" / "code"
    results = sorted(code_dir.glob("result_q*.json"))
    if not results:
        raise RuntimeError("P3: 没有生成任何 result_q*.json")
    scripts = sorted(code_dir.glob("solve_q*.py"))
    outputs = [f"code/{p.name}" for p in scripts + results]
    for p in sorted(code_dir.glob("result_q*.txt")):
        outputs.append(f"code/{p.name}")
    record(task_id, "P3",
           _prev_p1_inputs(task_id) + ["output/analysis/model_spec.md"],
           outputs, "claude -p (P3 编程求解)", rc)
    log(state, d, f"[Claude Code] P3 完成 ✅ ({len(scripts)} 个脚本, {len(results)} 个结果)")


def stage_p4(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    results = collect_results(task_id)
    if not results:
        raise RuntimeError("P4: 缺少 result_q*.json（P3 未产出）")
    cfg = STAGE_CONFIG["P4"]
    prompt = _build_p4_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P4 出图…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P4 Claude Code 退出码 {rc}\n{err[-1500:]}")
    fig_dir = d / "output" / "figures"
    figs = sorted(fig_dir.glob("*.png")) if fig_dir.exists() else []
    if not figs:
        raise RuntimeError("P4: 没有生成任何 fig_*.png")
    if "fig_pipeline.png" not in [f.name for f in figs]:
        raise RuntimeError("P4: 缺少技术路线图 fig_pipeline.png")
    outputs = ["code/make_figures.py"] + [f"figures/{p.name}" for p in figs]
    if (fig_dir / "check_report.json").exists():
        outputs.append("figures/check_report.json")
    code_dir = d / "output" / "code"
    result_inputs = [f"output/code/{p.name}"
                     for p in sorted(code_dir.glob("result_q*.json"))]
    record(task_id, "P4", result_inputs or ["output/analysis/model_spec.md"],
           outputs, "claude -p (P4 出图)", rc)
    log(state, d, f"[Claude Code] P4 完成 ✅ ({len(figs)} 张图)")


def stage_p5(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    results = collect_results(task_id)
    if not results:
        raise RuntimeError("P5: 缺少求解结果")
    cfg = STAGE_CONFIG["P5"]
    prompt = _build_p5_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P5 论文写作…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P5 Claude Code 退出码 {rc}\n{err[-1500:]}")
    paper_dir = d / "output" / "paper"
    pdf = paper_dir / "main.pdf"
    if not pdf.exists():
        raise RuntimeError("P5: main.pdf 未生成")
    # 收集输入输出用于 manifest
    fig_dir = d / "output" / "figures"
    fig_names = [f"output/figures/{f.name}" for f in sorted(fig_dir.glob("*.png"))] if fig_dir.exists() else []
    code_dir = d / "output" / "code"
    scr_names = [f"output/code/{p.name}" for p in sorted(code_dir.glob("solve_q*.py"))]
    inputs = ["output/paper/cumcmthesis.cls"] + fig_names + scr_names
    p5_outputs = ["paper/main.tex", "paper/main.pdf", "paper/cumcmthesis.cls",
                  "paper/latex_check.json"]
    if (paper_dir / "main.docx").exists():
        p5_outputs.insert(2, "paper/main.docx")
    record(task_id, "P5", inputs, p5_outputs, "claude -p (P5 论文写作)", rc)
    log(state, d, "[Claude Code] P5 完成 ✅")


def stage_p6(task_id: str, state: dict) -> None:
    d = _task_dir(task_id)
    cfg = STAGE_CONFIG["P6"]
    prompt = _build_p6_prompt(task_id)
    log(state, d, "[Claude Code] 启动 P6 验收…")
    rc, _out, err = run_claude(prompt, cwd=d, **cfg)
    if rc != 0:
        raise RuntimeError(f"P6 Claude Code 退出码 {rc}\n{err[-1500:]}")
    report = d / "output" / "acceptance_report.md"
    if not report.exists():
        raise RuntimeError("P6: acceptance_report.md 未生成")
    record(task_id, "P6",
           ["output/paper/main.tex", "output/paper/main.pdf"],
           ["acceptance_report.md"], "claude -p (P6 验收)", rc)
    log(state, d, "[Claude Code] P6 完成 ✅ 验收报告已生成")


# ---------- 主入口 ----------

def run_task(task_id: str, from_stage: str = "P1") -> None:
    """后台线程入口：从 from_stage 开始，逐阶段调用 claude -p 执行到 P6。

    每阶段是独立的 Claude Code 子进程（上下文隔离），只通过磁盘文件传递上下文。
    前端通过 output/task_state.json 轮询进度。
    """
    d = _task_dir(task_id)
    if not d.exists():
        return
    state = config.load_state(d)
    if state.get("status") == "running":
        return
    state.update(status="running", error="", logs=[], artifacts={},
                 team={"claude": {"status": "starting", "activity": "初始化"}})
    start_idx = STAGES.index(from_stage)
    for stage in STAGES[start_idx:]:
        state["stage"] = stage
        state["status"] = "running"
        state.setdefault("team", {})["claude"] = {
            "status": "working", "activity": f"执行 {STAGE_NAMES[stage]}"}
        config.save_state(d, state)
        log(state, d, f"===== 开始阶段 {stage}（{STAGE_NAMES[stage]}）=====")
        try:
            if not _gate(task_id, stage):
                raise RuntimeError(f"{stage} 前置门禁未通过（前一阶段产物缺失或被改动）")
            # 快照阶段开始前 output/，供失败回滚后自动重试
            out_dir = d / "output"
            snap = _snapshot_output(out_dir)
            last_err: Exception | None = None
            for attempt in range(1, MAX_STAGE_RETRY + 1):
                try:
                    fn = globals()[f"stage_{stage.lower()}"]
                    fn(task_id, state)
                    last_err = None
                    break
                except Exception as e:      # noqa: BLE001
                    last_err = e
                    if attempt < MAX_STAGE_RETRY:
                        n = _rollback_output(out_dir, snap)
                        log(state, d,
                            f"⚠️ {stage} 第 {attempt} 次失败：{e}"
                            f"（已回滚 {n} 个文件，第 {attempt + 1}/{MAX_STAGE_RETRY} 次重试）",
                            "error")
                        time.sleep(5)
            if last_err is not None:
                raise last_err
        except Exception as e:      # noqa: BLE001
            state["status"] = "failed"
            state["error"] = str(e)
            config.save_state(d, state)
            log(state, d, f"❌ {stage} 失败: {e}", "error")
            return
    state["stage"] = ""
    state["status"] = "done"
    state.setdefault("team", {})["claude"] = {"status": "done", "activity": "全部完成"}
    config.save_state(d, state)
    log(state, d, "🎉 全流程完成！论文与验收报告已就绪。")
