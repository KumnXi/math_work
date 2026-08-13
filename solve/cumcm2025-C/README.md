# 2025 高教社杯 C 题 —— 无创产前检测（NIPT）数据分析

> 赛题：`../2025高教社杯/C题/C题.pdf`（官方原题 PDF）+ 数据附件
> 本目录为完整解题产物，全部结果可复现（证据门禁 hash 校验通过）。

## 一、题目速览

无创产前检测（NIPT）通过孕妇外周血游离 DNA 测序判断胎儿染色体是否异常。本题给出一批男胎/女胎孕妇的检测记录，要求：

- **Q1**：Y 染色体浓度随孕周、BMI 的变化规律（非线性关系建模）
- **Q2**：按 BMI 分组给出最佳检测时点（有序聚类分组 + 风险最小化）
- **Q3**：多因素（年龄/孕次/产次/BMI）影响 + 分组最佳时点（生存分析）
- **Q4**：女胎染色体异常判定（小样本差异分析 + 三级判定）

## 二、产出文件索引

| 类别 | 位置 | 说明 |
|---|---|---|
| **赛题解释** | `output/analysis/problem_summary.md` | 问题背景、数据字典、逐问拆解 |
| **模型说明** | `output/analysis/model_spec.md` + `symbols.md` | 数学模型 + 符号表 |
| **国一对比** | `output/analysis/benchmark_study.md` | 与真实国一论文 C023/C132 逐题对比、迭代记录 |
| **解题代码** | `output/code/solve_q1.py`…`solve_q4_stat.py` | 每问独立求解器，可重跑 |
| **求解结果** | `output/code/result_q*.json/.txt` | 机器可读 + 人读摘要 |
| **出图代码** | `output/code/make_figures.py` | 一键生成全部图表 |
| **图表产出** | `output/figures/*.png` | 9 张论文级图 + 技术路线图 `fig_pipeline.png` |
| **论文** | `output/paper/main.tex` + `main.pdf` | 最终可提交论文（17 页，11/11 验收） |
| **验收报告** | `output/acceptance_report.md` | 11 项自动验收记录 |
| **证据链** | `output/run_manifest.json` | 每阶段产物 hash + 运行命令 |

## 三、目录结构

```
output/
├── analysis/        # 赛题解释 + 模型 + 国一对比
├── code/            # 求解器 + 出图 + 结果 JSON/TXT
├── figures/         # 论文图表 + check_report.json
├── paper/           # main.tex / main.pdf + LaTeX 编译记录
│   └── archive/     # v1/v2/v3 论文版本留档
├── acceptance_report.md
├── run_manifest.json
└── run_log.jsonl
```

## 四、复现方法

```bash
# 0) 环境
PY="D:/Jupyter code/math_work/.venv/Scripts/python.exe"

# 1) 求解（每问独立，输出 code/result_q*.json）
"$PY" code/solve_q1_gam.py      # Q1（二次+混合效应+GAM）
"$PY" code/solve_q2.py          # Q2 有序聚类+风险时点
"$PY" code/solve_q3.py          # Q3 Cox+组合时点
"$PY" code/solve_q4_stat.py     # Q4 差异分析+三级判定

# 2) 出图
"$PY" code/make_figures.py
"$PY" ../../tools/check_figures.py output/figures

# 3) 编译论文
"$PY" ../../.claude/skills/math-modeling-workflow/scripts/latex_check.py problems/cumcm2025-C

# 4) 验收
"$PY" ../../.claude/skills/math-modeling-workflow/scripts/acceptance.py problems/cumcm2025-C
```

## 五、核心结论（论文摘要）

- **Q1**：Y 浓度与孕周弱正相关（ρ=0.070）、与 BMI 显著负相关（ρ=-0.155）；非线性响应稳健（GAM 个体级 R² 提升至 0.2145，ICC≈0.746）
- **Q2**：BMI 有序聚类 K=2（<34.5 / ≥34.5），风险最小化时点 13 / 16 周（3:1 权重），误差 ≤±0.6 周
- **Q3**：多因素 Cox 仅 BMI 独立显著（HR=0.886）；年龄×BMI 组合时点：高龄高 BMI → 19 周
- **Q4**：男胎校准 + 差异分析 + 三级判定；X 染色体浓度是唯一强区分特征（p=5.3e-13，AUC=0.77），1% FPR 检出 13 例

## 六、版本留档

| 版本 | 位置 | 说明 |
|---|---|---|
| v1 | `output/paper/archive/v1/` | 初稿（二次多项式/GBDT/RF） |
| v2 | `output/paper/archive/v2/` | 加 GAM/RF（错误方向，被否） |
| **v3** | `output/paper/archive/v3/` | **按官方标准重构（当前定稿）** |
| 旧ML代码 | `output/archive/legacy_ml/` | v1/v2 机器学习求解器（已弃用，留档） |

> 迭代逻辑见 `output/analysis/benchmark_study.md`：v1/v2 抄了网络平庸 ML 方案，违反官方评阅要点（Q2 K-means 错误、Q4 小样本 ML 不可信）；v3 按真实国一 C023 的统计路线重构。
