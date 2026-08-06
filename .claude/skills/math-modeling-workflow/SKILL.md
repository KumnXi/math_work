---
name: math-modeling-workflow
description: >
  国赛(CUMCM)数学建模全流程工作流：读题→问题分析→建模→编程求解→出图→LaTeX 论文→自动验收。
  当用户在 problems/ 下放入赛题（PDF/DOCX + 数据）并请求跑完整建模流程时使用。
  人机协作：每阶段关键节点暂停请求用户确认（HIL）。
---

# 数学建模全流程工作流（国赛 CUMCM）

## 0. 触发与前置检查（必读铁律）

**触发条件**：`problems/<赛题名>/` 下存在赛题文件（PDF/DOCX）+ 数据文件，且用户意图是跑完整建模流程。

**开始前先做环境自检**（只读）：
```bash
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py --env
```
任一项失败即停止，先修复环境。

**机器路径铁律**：
- 所有 Python 一律 `$PYTHON_EXE`（`D:\Jupyter code\math_work\.venv\Scripts\python.exe`，读取 `.claude/settings.json` env，回退 `config/machine.json`）。**禁止裸 `python`**（Windows Store 假别名）。
- LaTeX 编译用 `$LATEXMK_EXE` / `$XELATEX_EXE`（MiKTeX）。
- 路径含空格（`D:\Jupyter code`），shell 命令一律双引号包裹；Python 内用 `pathlib`。
- 控制台 GBK 编码，Python 输出中文需 `PYTHONIOENCODING=utf-8`（settings 已配）或脚本内 reconfigure。

## 1. 工作区约定

- 每个赛题一个目录 `problems/<题名>/`；产出都在 `problems/<题名>/output/`。
- `output/` 固定结构：`analysis/`、`code/`、`figures/`、`paper/`、`acceptance_report.md`、`run_manifest.json`（+ append-only `run_log.jsonl`）。
- **`run_manifest.json` 是阶段推进的唯一凭据**。禁止编造任何数值——论文里的结果必须来自实际运行代码并记录。

## 2. 六阶段流水线

每阶段按固定模板执行：**目标 / 输入 / 操作 / 交付物 / 验收标准 / HIL 暂停点**。脚本位于 `.claude/skills/math-modeling-workflow/scripts/`。

### P1 读题 → `analysis/problem_summary.md`

- **目标**：完整理解题目，拆解子问题。
- **操作**：
  1. 赛题为 DOCX → 用 python-docx 提取文本；PDF → PyMuPDF(fitz) 提取（**无文本层则明确提示用户**，不静默）；也可直接读题面。
  2. 用 `tools/preprocess.py` 对每个数据文件做 EDA，记录列名/单位/缺失/异常。
  3. 逐问拆解：每个子问题 Q1..Qn 的目标、约束、输入、输出；列出全部参数。
  4. 写 `analysis/problem_summary.md`（问题背景、数据字典、参数清单、子问题目标/约束文字描述）。
- **交付物**：`analysis/problem_summary.md`
- **验收**：每个子问题有目标函数与约束的文字描述；数据列名/单位全部有解释；参数全部列出。
- **HIL**：⏸ 向用户复述题目理解，**确认后**才进入 P2。

### P2 建模 → `analysis/model_spec.md` + `analysis/symbols.md`

- **目标**：把文字问题形式化为数学模型。
- **操作**：
  1. 查 `references/model-methods-matrix.md` 选型（优化/预测/评价/聚类/机理），按"能用简单方法就不用高级方法"。
  2. 写决策变量、目标函数、约束条件；逐条编号**模型假设**（严格数学语言、可检验）。
  3. 写 `analysis/symbols.md`：符号表（符号—含义—单位）。
  4. 写 `analysis/model_spec.md`：每个子问题的完整数学模型 + 求解算法选择及理由。
- **交付物**：`analysis/model_spec.md`、`analysis/symbols.md`
- **验收**：每子问题有完整数学模型（变量/目标/约束）；假设可检验；方法选择附理由。
- **HIL**：⏸ 确认模型与假设后进入 P3。

### P3 编程求解 → `code/*.py` + `code/result_q*.json/.txt`

- **目标**：得到可复现的真实结果。
- **操作**：
  1. 写自包含求解器 `code/solve_q1.py`、`code/solve_q2.py` …（组合优化用 ortools CP-SAT；启发式用贪心+局部搜索；预测用回归/scipy）。可复用 `tools/`（figure_style/eval_metrics/preprocess/sensitivity）。
  2. 运行求解器 → 输出 `code/result_q1.json`（机器可读）+ `code/result_q1.txt`（人读摘要）。
  3. **每次运行后记录证据**：
     ```bash
     "$PYTHON_EXE" scripts/make_manifest.py record <problem_dir> P3 \
       --inputs statement.docx,attachment1.csv \
       --outputs code/solve_q1.py,code/result_q1.json,code/result_q1.txt \
       --cmd "<运行的完整命令>" --exit-code <退出码>
     ```
- **交付物**：`code/*.py`、`code/result_q*.json`、`code/result_q*.txt`
- **验收**：exit=0；result JSON 含关键指标；P3 记录到 manifest。
- **HIL**：⏸ 展示关键结果数值，确认合理性后进入 P4。

### P4 出图 → `figures/*.png`

- **目标**：论文级图表。
- **操作**：用 `tools/figure_style.py`（中文 + 论文配色 + 300dpi）；优先调用全局 `dataviz` skill 规范。图题/坐标单位/图注齐全。
- **交付物**：`figures/*.png`（记录到 manifest）
- **验收**：每张图有标题/坐标轴单位/图注；论文要引用的图都存在。
- **HIL**：无强制（并入 P5）。

### P5 论文写作 → `paper/main.tex` + `paper/main.pdf`

- **目标**：编译出可提交 PDF。
- **操作**：
  1. 复制 `templates/CUMCMThesis/cumcmthesis.cls` 到 `output/paper/`。
  2. 按 `references/paper-structure-cumcm.md` 的章节骨架写 `main.tex`（摘要独立页 + 正文 ≤25 页；公式编号、三线表、图引用、参考文献 GB/T 7714）。
  3. 写摘要（**最后写，五段式，含具体数值结果**，改 ≥3 版）。
  4. 按 `references/ai-usage-compliance.md` 写入"AI 使用说明"一节。
  5. 编译并检查：
     ```bash
     "$PYTHON_EXE" scripts/latex_check.py <problem_dir>   # latexmk + 扫描 → paper/latex_check.json
     ```
  6. 记录到 manifest（stage=P5）。
- **交付物**：`paper/main.tex`、`paper/main.pdf`
- **验收**：xelatex 零致命错误；无 undefined ref/cite；overfull 在阈值内。
- **HIL**：⏸ 交付前用户审阅全文。

### P6 验收 → `acceptance_report.md`

- **操作**：
  ```bash
  "$PYTHON_EXE" scripts/acceptance.py <problem_dir>
  ```
  9 步：A1 完整性 / A2 文本泄漏与占位符 / A3 数值一致性 / A4 图表引用完整 / A5 LaTeX 编译 / A6 模型形式化 / A7 论文要素齐全 / A8 格式规范 / A9 代码可复现。
- **未通过项**：对照 `references/acceptance-checklist.md` 修复后重跑，直到全绿。
- **HIL**：⏸ 最终确认后交付。

## 3. 证据门禁规则（强制）

- 阶段结束：`make_manifest.py record` 写产物哈希 + 命令 + exit_code。
- 阶段开始：先跑上一阶段的 gate：
  ```bash
  "$PYTHON_EXE" scripts/verify_manifest.py gate <problem_dir> P3   # 校验 P2 产物
  ```
  **gate 不通过（返回非零）不得推进**，先修复产物与记录的差异。
- manifest 是 append-only `run_log.jsonl` + 快照 `run_manifest.json`，不可篡改地记录每一步真实运行。

## 4. 复用资产

- 组合优化/启发式解题模式：见 `references/model-methods-matrix.md`（贪心构造 + 2-opt、CP-SAT、代价函数分项累加等骨架已固化）。
- 出图：优先全局 `dataviz` skill，回退 `tools/figure_style.py`。
- 误差指标：`tools/eval_metrics.py`；灵敏度：`tools/sensitivity.py`。

## 5. 交付物规范

- `solve_q*.py`：自包含可重跑；`result_q*.json`：机器可读；`result_q*.txt`：人读摘要。
- `figures/*.png`：300dpi，论文可引用。
- `paper/main.pdf`：最终可提交论文（含摘要页、承诺书模式、AI 使用说明）。

## 6. 合规红线

- 论文每个数值必须能在 `run_manifest.json` 溯源到实际运行记录（证据门禁保证）。
- 按 `references/ai-usage-compliance.md` 如实声明 AI 使用；核心建模思路由用户主导。
