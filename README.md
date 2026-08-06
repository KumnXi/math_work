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

在 `problems/` 下新建文件夹，例如 `problems/2026_CUMCM_B/`，放入：
- 赛题文件：`*.pdf` 或 `*.docx`（无文本层的扫描版 PDF 需另附文本）
- 数据文件：`*.csv` / `*.xlsx` / `*.txt`

### 3. 跑全流程

在项目根目录启动 `claude`，然后说：

```
按 math-modeling-workflow 跑 problems/2026_CUMCM_B 全流程
```

工作流会自动按六阶段执行，并在每个关键节点暂停征求你的确认（读题理解、模型假设、关键结果、论文审阅）。

### 4. 产出

```
problems/<赛题名>/output/
├── analysis/              # 题目分析、模型说明、符号表
├── code/                  # 求解代码 + 结果 JSON/TXT
├── figures/               # 论文图表 (300dpi)
├── paper/                 # main.tex + main.pdf（可提交论文）
├── acceptance_report.md   # 9 步自动验收报告
└── run_manifest.json      # 证据门禁记录（每步运行的真实证据）
```

## 目录结构

```
├── .claude/skills/math-modeling-workflow/  # 工作流 skill（核心）
├── problems/               # 题目输入区
├── templates/CUMCMThesis/  # 国赛 LaTeX 模板
├── tools/                  # 通用 Python 工具
├── scripts/                # 初始化脚本
└── config/machine.json     # 机器路径配置
```

## 端到端验证（已跑通）

内置 demo 题 `problems/demo-cumcm`（小型制造厂排班 + 产量预测，由 `make_demo.py` 生成）已完整跑通全流程：

- **六阶段全绿**：P1 读题 → P2 建模 → P3 CP-SAT 求解（总成本 15607 元、OPTIMAL）→ P4 出图（3 张 300dpi 图）→ P5 编译（11 页、零 overfull/undefined ref）→ P6 验收
- **验收 9/9 通过**：完整性、数值一致性、图表引用、LaTeX 编译、模型形式化、论文要素、格式规范、可复现等全部达标
- **证据门禁验证**：故意篡改一张产物图后 `gate` 立即拦截（hash 不一致），恢复后放行——防篡改机制生效

复现方式：

```bash
# 1. 重新生成 demo 题（可选，默认已在仓库中）
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_demo.py

# 2. 触发工作流（在项目根启动 claude 后）
#    对 problems/demo-cumcm 跑 math-modeling-workflow 全流程
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
