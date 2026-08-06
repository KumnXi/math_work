# 项目说明：数学建模全流程工作流

本工作区用于**国赛 CUMCM 数学建模竞赛**的完整流程：读题 → 建模 → 编程求解 → 出图 → LaTeX 论文 → 自动验收。

## 工作流入口

用户在 `problems/<赛题名>/` 放入赛题（PDF/DOCX）+ 数据文件，然后请求跑完整建模流程时，**必须调用 `math-modeling-workflow` skill**，按其中定义的六阶段流水线执行（P1 读题 → P2 建模 → P3 编程求解 → P4 出图 → P5 论文写作 → P6 验收），每阶段关键节点暂停请求用户确认（HIL）。

## 机器路径铁律（必须遵守）

1. **所有 Python 命令一律用 `$PYTHON_EXE`**（值为 `D:\Jupyter code\math_work\.venv\Scripts\python.exe`，读取 `.claude/settings.json` 的 env，回退 `config/machine.json`）。**禁止裸 `python`** —— PATH 里的 `python` 是 Windows Store 假别名，不可用；且 Anaconda 的 site-packages 不可写，装包必须走 `.venv`（`bash scripts/setup_env.sh`）。
2. LaTeX 编译用 `$LATEXMK_EXE` / `$XELATEX_EXE`（MiKTeX，`D:\MiKTeX\miktex\bin\x64\`）。
3. 本项目路径含空格（`D:\Jupyter code\math_work`），**shell 命令一律双引号包裹**路径；Python 内用 `pathlib`。
4. 控制台为 GBK 编码，运行 Python 时若输出中文需 `PYTHONIOENCODING=utf-8`（settings.json 已设置）或脚本内 `sys.stdout.reconfigure(encoding='utf-8')`。

## 目录约定

- `problems/<赛题名>/`：题目输入区，含赛题文件 + 数据文件
- `problems/<赛题名>/output/`：工作流产出（`analysis/` `code/` `figures/` `paper/` `acceptance_report.md` `run_manifest.json`）
- `templates/CUMCMThesis/`：国赛 LaTeX 模板（克隆自 latexstudio/CUMCMThesis，只读，不改）
- `tools/`：通用脚本（figure_style 出图风格、preprocess 数据预处理、sensitivity 灵敏度分析、eval_metrics 误差指标）
- `config/machine.json`：机器路径配置（init 脚本生成）
- `.claude/skills/math-modeling-workflow/`：工作流 skill（SKILL.md + references/ + scripts/）

## 可复用资产

- 全局 skill `math-modeling-solver`：组合优化/启发式解题模式（数据结构、代价函数、贪心插入、2-opt 局部搜索）——关键模式已固化进 skill 的 `references/model-methods-matrix.md`
- 全局 skill `dataviz`：出图视觉规范
- `tools/figure_style.py`：matplotlib 中文 + 统一风格

## 证据门禁

每个阶段产出必须通过 `verify_manifest.py gate` 校验（产物存在 + hash 与 `run_manifest.json` 一致）才能推进。**禁止编造任何数值**——论文里的结果必须来自实际运行的代码。
