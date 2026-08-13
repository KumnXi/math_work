---
name: math-modeling-workflow
description: >
  国赛(CUMCM)数学建模全流程工作流：读题→问题分析→建模→编程求解→出图→LaTeX 论文→自动验收。
  当用户在 problems/ 下放入赛题（PDF/DOCX + 数据）并请求跑完整建模流程时使用。
  人机协作：每阶段关键节点暂停请求用户确认（HIL）。
---

# 数学建模全流程工作流（国赛 CUMCM）

## 0. 触发与前置检查（必读铁律）

**触发条件**：`solve/<赛题名>/` 下存在赛题文件（PDF/DOCX）+ 数据文件，且用户意图是跑完整建模流程。
**若用户指定的是 `problems/<题名>`（存档区）**：先迁移到工作区再执行——
```bash
"$PYTHON_EXE" scripts/migrate_to_solve.py --move-output problems/<题名>
```
迁移后所有阶段一律在 `solve/<题名>/` 下进行；`problems/` 保持纯题目存档（禁止写入任何产出）。

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

- 每个赛题一个目录 `solve/<题名>/`；产出都在 `solve/<题名>/output/`。**`problems/` 只存题目，禁止写入产出**。
- `output/` 固定结构：`analysis/`、`code/`、`figures/`、`paper/`、`acceptance_report.md`、`run_manifest.json`（+ append-only `run_log.jsonl`）。论文交付含 `paper/main.docx`（完整版 Word，见 P5）。
- **`run_manifest.json` 是阶段推进的唯一凭据**。禁止编造任何数值——论文里的结果必须来自实际运行代码并记录。

## 2. 六阶段流水线

每阶段按固定模板执行：**目标 / 输入 / 操作 / 交付物 / 验收标准 / HIL 暂停点**。脚本位于 `.claude/skills/math-modeling-workflow/scripts/`。

### P1 读题 → `analysis/problem_summary.md`

- **目标**：完整理解题目，拆解子问题。
- **操作**：
  1. 赛题为 DOCX → 用 python-docx 提取文本；PDF → PyMuPDF(fitz) 提取（**无文本层则明确提示用户**，不静默）；也可直接读题面。**扫描版/无文本层 PDF（MCP）**：走视觉链路——`qwen-mm-plugins-core` 的 `visualize` 渲染关键页为 PNG 后 `Read` 直接读图，或 `qwen-mm-plugins-api` 的 `vision_chat`/`ocr` 精读（方法见 CLAUDE.md「读 PDF / 优秀论文」节）。
  2. 用 `tools/preprocess.py` 对每个数据文件做 EDA，记录列名/单位/缺失/异常。
  3. 逐问拆解：每个子问题 Q1..Qn 的目标、约束、输入、输出；列出全部参数。
  4. 写 `analysis/problem_summary.md`（问题背景、数据字典、参数清单、子问题目标/约束文字描述）。
- **交付物**：`analysis/problem_summary.md`
- **验收**：每个子问题有目标函数与约束的文字描述；数据列名/单位全部有解释；参数全部列出。
- **HIL**：⏸ 向用户复述题目理解，**确认后**才进入 P2。

### P2 建模 → `analysis/model_spec.md` + `analysis/symbols.md`

- **目标**：把文字问题形式化为数学模型。
- **操作**：
  1. 查 `references/model-methods-matrix.md` 选型（优化/预测/评价/聚类/机理），按"能用简单方法就不用高级方法"；**组合优化/启发式类问题先调用全局 `math-modeling-solver` skill**（数据结构、代价函数、贪心插入、2-opt 骨架直接复用）。**选型佐证（MCP）**：方法不确定或要证明"这题就该用这方法"时，用 `paper-search-mcp` 检索本问方法文献（`search_papers` 搜"问题域 + 方法"），把文献结论写进 model_spec 的选型理由；方法本身拿不准实现是否可行时可用 `context7` 查库文档（scipy/ortools 等）确认算法 API 存在。
  2. 写决策变量、目标函数、约束条件；逐条编号**模型假设**（严格数学语言、可检验）。
  3. 写 `analysis/symbols.md`：符号表（符号—含义—单位）。
  4. 写 `analysis/model_spec.md`：每个子问题的完整数学模型 + 求解算法选择及理由 + **每个子问题至少 2 种备选方案对比表**（对应问题/算法/核心逻辑/实现难度/优缺点/创新性，标注选用及理由，见 `references/model-methods-matrix.md` 选型对比表）。
- **交付物**：`analysis/model_spec.md`、`analysis/symbols.md`
- **验收**：每子问题有完整数学模型（变量/目标/约束）；假设可检验；方法选择附理由。
- **HIL**：⏸ 确认模型与假设后进入 P3。

### P3 编程求解 → `code/*.py` + `code/result_q*.json/.txt`

- **目标**：得到可复现的真实结果。
- **操作**：
  1. 写自包含求解器 `code/solve_q1.py`、`code/solve_q2.py` …（组合优化用 ortools CP-SAT；启发式用贪心+局部搜索；预测用回归/scipy）。可复用 `tools/`（figure_style/eval_metrics/preprocess/sensitivity）。**查 API / 找实现（MCP）**：库用法不确定（参数/边界行为）用 `context7` 查官方文档（如 scipy.optimize.milp、ortools CP-SAT 用法）；算法想参考成熟实现用 `github` 搜索开源代码（`search_code`）。
  2. 运行求解器 → 输出 `code/result_q1.json`（机器可读）+ `code/result_q1.txt`（人读摘要）。
  3. **求解过程可呈现（论据，经验 2024-A）**：二分/扫描/迭代类算法把**每一轮写进 result JSON**（步号、候选值、可行性、区间/步长、中间量）；"扫参数找极值/临界值"一律**粗扫定位 + 峰值窗口逐级加密直到结果稳定**，各档数值留档（粗步长会低估极值最多 11%）。P5 用迭代表呈现。
  4. **每次运行后记录证据**：
     ```bash
     "$PYTHON_EXE" scripts/make_manifest.py record <problem_dir> P3 \
       --inputs statement.docx,attachment1.csv \
       --outputs code/solve_q1.py,code/result_q1.json,code/result_q1.txt \
       --cmd "<运行的完整命令>" --exit-code <退出码>
     ```
- **交付物**：`code/*.py`、`code/result_q*.json`、`code/result_q*.txt`
- **验收**：exit=0；result JSON 含关键指标；P3 记录到 manifest。
- **HIL**：⏸ 展示关键结果数值，确认合理性后进入 P4。

### P4 出图 → `figures/*.png` + 结构示意图（`figures/*.drawio`）

- **目标**：论文级图表 + 技术路线图。
- **操作**：
  1. **数据图**：用 `tools/figure_style.py`（中文 + 论文配色 + 300dpi）；优先调用全局 `dataviz` skill 规范。图题/坐标单位/图注齐全。按 `references/figure-quality-check.md` 的标准出图。
  2. **论证性图表（论据充分的硬要求，经验 2024-A）**：每个关键判据/临界值/极值配一张图或迭代表——判据过零图（碰撞/可行性零穿越）、极值/分布图（标峰值）、收敛/迭代过程表、效应/偏差图（近似 vs 精确）。数据取自 result JSON 的迭代历史，标准见 `references/figure-quality-check.md`。
  3. **技术路线图 `fig_pipeline.png`**：问题分析/技术路线流程图——优先调用全局 `drawio-skill` 绘制（结构示意更专业），matplotlib 方框+箭头兜底。
  4. **结构示意图（论文加分项，推荐）**：建模框架图（子问题泳道 × 决策变量—约束—求解器—结果四层）、求解/算法流程图、问题分解图。一律用 `drawio-skill` 绘制，方法见 `references/drawio-paper-figures.md`：产出 `.drawio` 源文件 + `.drawio.png`（论文引用）+ `.svg`；`-e` PNG 必须跑 `repair_png.py` 修复后使用。
  5. **程序化检查**：`"$PYTHON_EXE" tools/check_figures.py <figures_dir>`（可解码/尺寸/非空白/大小 → `figures/check_report.json`），有损坏/空白图必须修复重出。
  6. **审图**：代码手对照 check_report + 求解结果逐张核对数据来源与可用性，结论写入 `team/coder_notes.md` 的『P4 审图结论』段。
- **交付物**：`figures/*.png` + `figures/*.drawio`（结构图源文件）+ `figures/check_report.json`（记录到 manifest）
- **验收**：每张图过 check_figures；技术路线图存在；审图结论写入笔记。
- **HIL**：无强制（并入 P5）。

### P5 论文写作 → `paper/main.tex` + `paper/main.pdf` + `paper/main.docx`

- **目标**：编译出可提交 PDF，并产出**完整版 Word**。
- **操作**：
  1. 复制 `templates/CUMCMThesis/cumcmthesis.cls` 到 `output/paper/`。
  2. 按 `references/paper-structure-cumcm.md` 的章节骨架 + `references/layout-norms-cumcm.md` 的排版规范写 `main.tex`（摘要独立页 ≤1 页、**正文 ≤25 页、附录不限页**；标题字体字号、首行缩进、单倍行距、图表公式居中、表注在图注位、公式编号、三线表、图引用、参考文献 GB/T 7714）。P4 产出的结构示意图插入对应章节并 `\ref` 交叉引用，**图内数值与正文 / result JSON 一致**。**每问"求解"小节放迭代表（二分/收敛/加密收敛）、结果与分析配必要的对比表**（方案对比、与优秀论文/文献数值交叉验证），论据与篇幅标准见 `references/benchmark-iteration.md` 第七节。**参考文献必须真实可查**：写 thebibliography 前用 `paper-search-mcp` 检索本问方法文献（`search_papers` + DOI 反查），核对 DOI/arXiv 后按 GB/T 7714 格式化，禁止编造引用，方法见 `references/paper-search-literature.md`，证据记入 `output/analysis/literature_sources.md`。
  3. 写摘要（**最后写，五段式，含具体数值结果**，改 ≥3 版）。
  4. 按 `references/ai-usage-compliance.md` 写入 **"AI 工具使用声明"（2026 规定：放参考文献之前，二选一官方文本）**；使用 AI 的须提醒准备支撑材料 `AI 工具使用详情.pdf`。
  5. 编译并检查：
     ```bash
     "$PYTHON_EXE" scripts/latex_check.py <problem_dir>   # latexmk + 扫描 → paper/latex_check.json
     ```
  6. 生成完整版 Word（pandoc 直接转 main.tex → main.docx，公式为**原生可编辑 OMML**、图/表带编号与引用、摘要为中文"摘要"）：
     ```bash
     "$PYTHON_EXE" tools/generate_docx.py <problem_dir>
     ```
     - 依赖 pandoc（`winget install --id JohnMacFarlane.Pandoc`），路径登记在 `config/machine.json` 的 `PANDOC_EXE`（首次由 init 登记）。
     - 公式编号与 `\eqref` 由脚本预处理自行解析（不用 pandoc-crossref——它对 LaTeX 输入 + docx 公式编号有缺陷）。
  7. 记录到 manifest（stage=P5）。
- **交付物**：`paper/main.tex`、`paper/main.pdf`、`paper/main.docx`（完整版 Word）
- **验收**：xelatex 零致命错误；无 undefined ref/cite；overfull 在阈值内；main.docx 生成成功。
- **HIL**：⏸ 交付前用户审阅全文。

### P6 验收 → `acceptance_report.md`

- **操作**：
  ```bash
  "$PYTHON_EXE" scripts/acceptance.py <problem_dir>
  ```
  11 步：A1 完整性 / A2 文本泄漏与占位符（含内部文件泄露）/ A3 数值一致性 / A4 图表引用完整（引用图须过质量检查）/ A5 LaTeX 编译 / A6 模型形式化 / A7 论文要素齐全 / A8 格式规范（**按正文页数判定、附录不计页**：正文 ≤25 通过，25~30 通过但提示，>30 失败）/ A9 代码可复现 / **A10 图质量**（全部图过 check_figures + 技术路线图存在）/ **A11 PDF 视觉**（渲染每页非空白、页数一致）。
- **未通过项**：对照 `references/acceptance-checklist.md` 与 `references/writing-norms.md` 修复后重跑，直到全绿。
- **HIL**：⏸ 最终确认后交付。

### P7 赛后对比学习与迭代（可选，但实战/留档推荐）

- **目标**：跑完论文后检索该赛题优秀/获奖论文，逐环节对比，迭代改进并沉淀。
- **操作**：按 `references/benchmark-iteration.md` 的渠道检索（高校获奖新闻 / IEEE-ACM 论文 / 技术博客 / GitHub / 期刊评述）+ **paper-search-mcp 学术检索**（`search_papers` 搜赛题方法文献并 `download_with_fallback` 深读，方法见 `references/paper-search-literature.md`）→ 填"我们的 vs 优秀方案"对比矩阵 → 识别差距并判断"该修 vs 已验证正确可保留" → 对最痛点新增求解器重跑（证据门禁同 P3）→ 更新论文 → 重跑 latex_check + acceptance。
- **留档（强制）**：① 论文每个提交版存档 `output/paper/archive/v<N>/`（含结构示意图的 `.drawio` 源文件）；② 优秀论文资料与对比表存 `output/analysis/benchmark_study.md`（含外链）；③ 新增求解器与 result JSON 记入 run_manifest。
- **HIL**：⏸ 对比结论与改动向用户汇报，确认后定稿。

## 3. 证据门禁规则（强制）

- 阶段结束：`make_manifest.py record` 写产物哈希 + 命令 + exit_code。
- 阶段开始：先跑上一阶段的 gate：
  ```bash
  "$PYTHON_EXE" scripts/verify_manifest.py gate <problem_dir> P3   # 校验 P2 产物
  ```
  **gate 不通过（返回非零）不得推进**，先修复产物与记录的差异。
- manifest 是 append-only `run_log.jsonl` + 快照 `run_manifest.json`，不可篡改地记录每一步真实运行。

## 4. 复用资产

**Skills（按节点调用）**：
- 组合优化/启发式解题模式（P2/P3 建模选型）：调用全局 `math-modeling-solver`，模式固化在 `references/model-methods-matrix.md`（贪心构造 + 2-opt、CP-SAT、代价函数分项累加等骨架）。
- 出图（数据图，P4）：优先全局 `dataviz` skill，回退 `tools/figure_style.py`。数据图能否进论文的标准见 `references/figure-quality-check.md`。
- 出图（结构示意图，P4）：调用全局 `drawio-skill`，方法见 `references/drawio-paper-figures.md`（建模框架图 / 求解流程图 / 技术路线图）。
- 文献检索（P5 参考文献 / P7 赛后对比 / P2 选型佐证）：调用 `paper-search-mcp`，方法见 `references/paper-search-literature.md`（真实可查、DOI 反查、GB/T 7714、防编造）；`firecrawl-research-index` 作补充检索。

**MCP 服务器（mcphub 提供，P1–P7 按需调用）**：
- `paper-search-mcp`（57 工具）：学术文献检索/下载/精读——P2 方法佐证、P5 参考文献、P7 赛后对比深读。
- `context7`（2 工具）：库文档查询——P3 编程确认 scipy/ortools/matplotlib 等 API 用法（参数、边界行为）。
- `github`（44 工具）：开源实现搜索——P3 参考成熟算法代码、P7 找优秀论文开源仓库。
- `firecrawl`（26 工具）：全网检索——P2 方法综述、P7 赛后检索解题思路。
- `qwen-mm-plugins-core/api`（~19 工具）：视觉链路——P1 读扫描版赛题、P4 审图、P5 读优秀论文关键页（visualize/vision_chat/ocr/omni_av_caption，方法见 CLAUDE.md）。

**工具脚本**：误差指标 `tools/eval_metrics.py`；灵敏度 `tools/sensitivity.py`；预处理 `tools/preprocess.py`；图检查 `tools/check_figures.py`。

## 5. 交付物规范

- `solve_q*.py`：自包含可重跑；`result_q*.json`：机器可读；`result_q*.txt`：人读摘要。
- `figures/*.png`：300dpi，论文可引用；结构示意图保留 `.drawio` 源文件可再编辑。
- `paper/main.pdf`：最终可提交论文（含摘要页、承诺书模式、AI 使用说明）。
- `paper/main.docx`：完整版 Word（由 main.tex 用 pandoc 转换，公式为原生可编辑 OMML；图/表带编号与引用）。

## 6. 合规红线

- 论文每个数值必须能在 `run_manifest.json` 溯源到实际运行记录（证据门禁保证）。
- 按 `references/ai-usage-compliance.md` 如实声明 AI 使用；核心建模思路由用户主导。
