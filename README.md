# 数学建模全流程工作流（国赛 CUMCM）

把赛题丢进来，Claude Code 全流程跑完：**读题 → 建模 → 编程求解 → 出图 → LaTeX 论文 → 自动验收**。

## 快速开始

### 1. 初始化（一次性）

```bash
cd "D:\Jupyter code\math_work"
bash scripts/setup_env.sh      # 装 Python 依赖（ortools、PyMuPDF）
bash scripts/init_project.sh   # 克隆 CUMCMThesis 模板、写 machine.json
bash scripts/first_compile.sh  # 预热 LaTeX 模板（首次需联网装宏包）
```

### 2. 放入赛题

`problems/` 是**只读题目存档区**（只存赛题 + 附件，禁止出现产出）。在 `problems/` 下按题目新建文件夹放入：
- 赛题文件：`*.pdf` 或 `*.docx`（无文本层的扫描版 PDF 需另附文本）
- 数据文件：`*.csv` / `*.xlsx` / `*.txt`

### 3. 迁移到工作区（solve/）

所有解题工作都在 `solve/<题名>/` 进行，先复制题目过去：

```bash
"$PYTHON_EXE" scripts/migrate_to_solve.py problems/2026_CUMCM_B
# 若 problems/ 侧有历史遗留 output/，加 --move-output 一并搬走
```

### 4. 跑全流程

在项目根目录启动 `claude`，然后说：

```
按 math-modeling-workflow 跑 solve/2026_CUMCM_B 全流程
```

工作流会自动按六阶段执行，并在每个关键节点暂停征求你的确认（读题理解、模型假设、关键结果、论文审阅）。

### 5. 产出

```
solve/<赛题名>/output/
├── analysis/              # 题目分析、模型说明、符号表
├── code/                  # 求解代码 + 结果 JSON/TXT
├── figures/               # 论文图表 (300dpi)
├── paper/                 # main.tex + main.pdf（可提交论文）+ main.docx（完整版 Word）
├── acceptance_report.md   # 11 步自动验收报告
└── run_manifest.json      # 证据门禁记录（每步运行的真实证据）
```

## 目录结构

```
├── .claude/skills/math-modeling-workflow/  # 工作流 skill（核心，六阶段 + MCP/skills 挂载点）
├── problems/               # 题目存档区（只读，仅赛题 + 附件）
├── solve/                  # 工作区（题目副本 + 全部产出）
├── templates/CUMCMThesis/  # 国赛 LaTeX 模板
├── tools/                  # 通用 Python 工具（generate_docx 产完整版 Word 等）
├── scripts/                # 初始化脚本
├── docs/                   # 参考文档（AI 使用说明、排版规范、提示词模板）
└── config/                 # machine.json（路径）+ llm.json（密钥，不入库）
```

## 三类工具协同（skills / MCP / 视觉）

工作流在各阶段自动调用以下资产，见 CLAUDE.md「可复用资产」：

| 阶段 | Skills | MCP 服务器 | 视觉链路 |
|---|---|---|---|
| P1 读题 | — | qwen-mm-plugins（扫描版 PDF） | visualize→Read / vision_chat |
| P2 建模 | math-modeling-solver | paper-search-mcp（选型佐证）、context7 | — |
| P3 编程 | — | context7（查库 API）、github（找实现） | — |
| P4 出图 | dataviz、drawio-skill | qwen-mm-plugins（审图） | — |
| P5 论文 | — | paper-search-mcp（参考文献真实检索） | 读优秀论文关键页 |
| P6 验收 | — | — | — |
| P7 赛后迭代 | firecrawl-research-index | paper-search-mcp、firecrawl | 读优秀论文深读 |

## 端到端验证（已跑通）

内置 demo 题 `solve/demo-cumcm`（小型制造厂排班 + 产量预测，由 `make_demo.py` 生成）已完整跑通全流程：

- **六阶段全绿**：P1 读题 → P2 建模 → P3 CP-SAT 求解（总成本 15607 元、OPTIMAL）→ P4 出图（3 张 300dpi 图）→ P5 编译（11 页、零 overfull/undefined ref）→ P6 验收
- **验收 11/11 通过**：完整性、数值一致性、图表引用、LaTeX 编译、模型形式化、论文要素、格式规范、代码可复现、图质量、PDF 视觉等全部达标
- **证据门禁验证**：故意篡改一张产物图后 `gate` 立即拦截（hash 不一致），恢复后放行——防篡改机制生效

复现方式：

```bash
# 1. 重新生成 demo 题（可选，默认已在仓库中）
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_demo.py

# 2. 触发工作流（在项目根启动 claude 后）
#    对 solve/demo-cumcm 跑 math-modeling-workflow 全流程
```

## 常见问题排查

| 现象 | 处理 |
|---|---|
| `python` 找不到 / 是 Store 假别名 | 一律用 `"$PYTHON_EXE"`（`.venv/Scripts/python.exe`），见 CLAUDE.md 机器路径铁律 |
| ortools 导入报 `WinError 127` | 环境被污染，重跑 `bash scripts/setup_env.sh`（纯 pip venv，防 DLL 冲突） |
| 首次 LaTeX 编译很慢/报缺宏包 | MiKTeX 需联网自动装包，先跑 `bash scripts/first_compile.sh` 预热 |
| 编译报字体缺失 | 用 xelatex + SimSun/SimHei，勿用 pdflatex |
| 中文输出乱码 | 控制台 GBK，脚本内 `sys.stdout.reconfigure(encoding='utf-8')` |

## 合规说明

- 使用生成式 AI 辅助竞赛须按国赛规定在论文中**如实声明**（见 skill 的 `references/ai-usage-compliance.md`）
- 论文所有数值必须来自实际运行的代码（证据门禁保证），禁止编造
- 本工作流定位为**人机协作**：核心建模思路由你主导，AI 负责加速实现

---

*本项目工作流由 **Claude Code（Anthropic）** 辅助搭建与优化。*
