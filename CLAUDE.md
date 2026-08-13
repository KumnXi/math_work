# 项目说明：数学建模全流程工作流

本工作区用于**国赛 CUMCM 数学建模竞赛**的完整流程：读题 → 建模 → 编程求解 → 出图 → LaTeX 论文 → 自动验收。

## 工作流入口

用户在 `problems/<赛题名>/` 放入赛题（PDF/DOCX）+ 数据文件，然后请求跑完整建模流程时，**必须调用 `math-modeling-workflow` skill**，按其中定义的六阶段流水线执行（P1 读题 → P2 建模 → P3 编程求解 → P4 出图 → P5 论文写作 → P6 验收），每阶段关键节点暂停请求用户确认（HIL）。

## 机器路径铁律（必须遵守）

1. **所有 Python 命令一律用 `$PYTHON_EXE`**（值为 `D:\Jupyter code\math_work\.venv\Scripts\python.exe`，读取 `.claude/settings.json` 的 env，回退 `config/machine.json`）。**禁止裸 `python`** —— PATH 里的 `python` 是 Windows Store 假别名，不可用；且 Anaconda 的 site-packages 不可写，装包必须走 `.venv`（`bash scripts/setup_env.sh`）。
2. LaTeX 编译用 `$LATEXMK_EXE` / `$XELATEX_EXE`（MiKTeX，`D:\MiKTeX\miktex\bin\x64\`）。
3. 本项目路径含空格（`D:\Jupyter code\math_work`），**shell 命令一律双引号包裹**路径；Python 内用 `pathlib`。
4. 控制台为 GBK 编码，运行 Python 时若输出中文需 `PYTHONIOENCODING=utf-8`（settings.json 已设置）或脚本内 `sys.stdout.reconfigure(encoding='utf-8')`。
5. **提交前必须做敏感信息检查**：仓库已注册 pre-commit 钩子（`.githooks/pre-commit` → `scripts/check_secrets.py`），每次 `git commit` 自动扫描暂存区密钥/凭据，命中即拦截。任何人（含 Claude）**不得用 `git commit --no-verify` 绕过**，除非已人工确认命中确为误报；误报应在 `scripts/check_secrets.py` 的 `ALLOW_SUBSTRINGS` 中补充白名单。`config/llm.json`、`config/machine.json`、`.claude/settings*.json` 含密钥/路径凭据，严禁入库。

## 目录约定

- `problems/<赛题名>/`：**题目存档区（只读，仅赛题 + 附件，禁止出现 `output/`）**
- `solve/<赛题名>/`：**唯一工作区**（题目副本 + 全部产出）。新题流程：`scripts/migrate_to_solve.py problems/<题名>` 复制题目到 `solve/`，之后所有阶段在 `solve/` 执行；若 problems/ 侧有历史遗留产出，加 `--move-output` 一并搬走
- `solve/<赛题名>/output/`：工作流产出（`analysis/` `code/` `figures/` `paper/` `acceptance_report.md` `run_manifest.json`，论文含 `paper/main.docx` 完整版 Word）
- `templates/CUMCMThesis/`：国赛 LaTeX 模板（克隆自 latexstudio/CUMCMThesis，只读，不改）
- `tools/`：通用脚本（figure_style 出图风格、preprocess 数据预处理、sensitivity 灵敏度分析、eval_metrics 误差指标、generate_docx 完整版Word生成(pandoc 转 main.tex→main.docx，公式为原生可编辑 OMML)、check_figures 图质量检查）
- `config/machine.json`：机器路径配置（init 脚本生成）；`config/llm.json`：LLM 配置（**含密钥，不入库**）
- `docs/`：工作流参考文档（AI 使用说明、排版规范、提示词模板等，从根目录归档而来）
- `.claude/skills/math-modeling-workflow/`：工作流 skill（SKILL.md + references/ + scripts/）

## 读 PDF / 优秀论文：混合策略（必须遵守）

主模型**现在能直接读 PNG 图片**（`Read` 返回实际图像），但 **PDF 页渲染成图仍不能直接读**（返回 `[Unsupported Image]`）。读赛题和优秀论文 PDF 按需选档，从便宜到贵：

1. **文字打底（最常用）**：用 Read 工具（`pages` 参数）或 Python 库（`pdfplumber` / `PyPDF2` / `fitz`，走 `$PYTHON_EXE`）提取全文，快速掌握框架、思路、方法、结论。**PDF 有文本层就用这条**——纯文字段落文本提取更准更省。
2. **视觉查缺（仅关键页）**：主模型先标出公式 / 图表密集的关键页，对该页用 `qwen-mm-plugins-core` 的 `visualize` 渲染为 PNG（或 `save_view` 落盘）后 **Read 直接读图**；渲染结果可疑时再用 `qwen-mm-plugins-api` 的 `vision_chat` / `ocr` 精读公式与图表（走 DashScope 千问视觉模型）。
3. **精确定位（定位小目标）**：需要"图里某区域/某把手/某参数"时，用 `grounding` 定位目标框 → `crop` 裁剪 → `ocr` / `vision_chat` 精读该区域。视频类数据用 `omni_av_caption` 一次性提取。

原因：数模论文的 LaTeX 公式在文本提取时会乱码、图表会完全丢失，这两类必须走视觉；纯文字段落用文本提取更准更省（避免每页渲染 + 图片 token 的高成本）。**能用文本就不渲染，必须渲染时优先主模型直接读 PNG**。

## 可复用资产

### Skills（按工作流节点调用）

- `math-modeling-workflow`（项目内）：国赛全流程六阶段流水线，**读题→建模→求解→出图→论文→验收**，见 `.claude/skills/math-modeling-workflow/SKILL.md`
- `math-modeling-solver`（全局）：组合优化/启发式解题模式（数据结构、代价函数、贪心插入、2-opt 局部搜索）——P2 建模选型时用，关键模式固化在 `references/model-methods-matrix.md`
- `dataviz`（全局）：出图视觉规范——P4 数据图优先调用
- `drawio-skill`（全局）：画流程图/架构图/ML 模型图——**P4 技术路线图、建模框架图**用，导出 PNG/SVG，方法见 `references/drawio-paper-figures.md`
- `firecrawl-research-index`（全局）：文献检索——P5 找参考文献 / P7 赛后对比时可用（与 paper-search-mcp 互补）
- `token-saver`（全局）：省 token 工作流——长任务迭代中按需启用

### MCP 服务器（mcphub localhost:3000 统一管理）

| 服务器 | 工具数 | 用在哪 |
|---|---|---|
| context7 | 2 | **P3 编程**查库 API 用法（scipy/ortools/matplotlib 等） |
| github | 44 | 找优秀论文的开源实现、复现算法 |
| firecrawl | 26 | 全网检索解题思路、方法综述；网页抓取 |
| paper-search-mcp | 57 | **P5 参考文献**真实检索 + DOI 反查 + 深读；**P2 方法选型佐证**；**P7 赛后对比**（方法见 `references/paper-search-literature.md`） |
| qwen-mm-plugins-core/api | ~19 | 视觉链路：visualize/save_view/read_image 渲染，vision_chat/ocr/omni_av_caption 精读（见"读 PDF"节） |

### 工具脚本

- `tools/figure_style.py`：matplotlib 中文 + 统一风格（P4 出图）
- `tools/eval_metrics.py`：误差指标；`tools/sensitivity.py`：灵敏度；`tools/preprocess.py`：数据预处理

## 证据门禁

每个阶段产出必须通过 `verify_manifest.py gate` 校验（产物存在 + hash 与 `run_manifest.json` 一致）才能推进。**禁止编造任何数值**——论文里的结果必须来自实际运行的代码。
