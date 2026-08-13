# 2024 高教社杯 C 题 —— 乡村农作物种植策略优化

> 赛题：`C题.pdf`（官方原题）+ 附件1（耕地与作物基本情况）/ 附件2（2023 种植统计）
> 本目录为完整解题产物，全部结果可复现（证据门禁 hash 校验通过）。

## 一、题目速览

某乡村 54 块地块（平旱地/梯田/山坡地/水浇地/普通大棚/智慧大棚）、41 种作物，需在面积上下限、单季作物数、重茬与豆类轮作、水浇地模式互斥等约束下给出 2024–2030 年逐年最优种植方案：

- **Q1**：参数相对 2023 保持稳定，按两种超产情形给出确定性最优方案（滞销浪费 / 50% 半价出售）
- **Q2**：需求、亩产、成本、价格存在不确定性（小麦/玉米需求年增 5%~10%，亩产 ±10%，成本年增 5% 等），两阶段随机规划 + CVaR 风险度量
- **Q3**：在 Q2 基础上引入作物间可替代/互补性与销量-价格-成本相关性（Gaussian Copula），并与 Q2 对比

## 二、产出文件索引

| 类别 | 位置 | 说明 |
|---|---|---|
| **赛题解释** | `output/analysis/problem_summary.md` | 问题背景、数据字典、逐问拆解 |
| **模型说明** | `output/analysis/model_spec.md` + `symbols.md` | 数学模型 + 符号表 |
| **国一参考留档** | `output/archive/reference/` | 四篇国一论文 C038/C063/C094/C234 + 借鉴说明 |
| **解题代码** | `output/code/solve_q1.py` / `solve_q2.py` / `solve_q3.py` | 每问独立求解器，可重跑 |
| **求解结果** | `output/code/result_q*.json/.txt` | 机器可读 + 人读摘要 |
| **出图代码** | `output/code/make_figures.py` + `make_paper_tables.py` | 一键生成图表 + 论文数值表 |
| **图表产出** | `output/figures/*.png` | 8 张论文级图 + 技术路线图 `fig_pipeline.png` |
| **论文** | `output/paper/main.tex` + `main.pdf` | 最终可提交论文 |
| **验收报告** | `output/acceptance_report.md` | 11 项自动验收记录 |
| **证据链** | `output/run_manifest.json` | 每阶段产物 hash + 运行命令 |

## 三、目录结构

```
output/
├── analysis/          # 赛题解释 + 模型 + 符号表
├── archive/reference/ # 四篇国一论文留档 + 借鉴说明
├── code/              # 求解器 + 出图 + 结果 JSON/TXT + 求解链脚本
├── data/              # 附件解析产物（plots/crops/stats/expected_demand…）
├── figures/           # 论文图表 + check_report.json
├── paper/             # main.tex / main.pdf + LaTeX 编译记录
│   └── archive/       # v1/v2/… 论文版本留档
├── acceptance_report.md
└── run_manifest.json
```

## 四、复现方法

```bash
# 0) 环境
PY="D:/Jupyter code/math_work/.venv/Scripts/python.exe"

# 1) 完整求解链（Q1 两情形 + Q2/Q3 三 λ，后台运行）
bash output/code/run_all_solves.sh

# 2) 出图 + 论文数值表
"$PY" output/code/make_figures.py
"$PY" output/code/make_paper_tables.py
"$PY" ../../tools/check_figures.py output/figures

# 3) 编译论文
"$PY" ../../.claude/skills/math-modeling-workflow/scripts/latex_check.py solve/2024-C题

# 4) 验收
"$PY" ../../.claude/skills/math-modeling-workflow/scripts/acceptance.py solve/2024-C题
```

## 五、核心结论（论文摘要）

- **Q1**：确定性 MILP（两情形共用线性化超产变量）。情形1（滞销浪费）7 年总利润约 2676 万元；情形2（半价出售）约 3876 万元，较情形1 提升约 44.8%
- **Q2**：两阶段随机规划（N=50 情景，期望利润 − λ·CVaR₀.₉）。随 λ 由 0 增至 1，期望利润仅小幅回落（3996→3980 万元，−0.4%）、标准差基本持平（45.1→45.7 万元）、CVaR 尾部损失小幅收窄（3919→3905 万元），风险-收益权衡稳健
- **Q3**：Gaussian Copula 引入相关结构后期望利润与 Q2 基本持平（3993 vs 3996 万元），但利润分布更分散（标准差 68.1 vs 45.1 万元）、尾部下行加剧（尾部 10% 利润 3874 vs 3919 万元）——相关性放大了系统性风险

## 六、建模差异（对照国一论文，避免抄袭）

1. Q1 用**超产变量线性化**统一两种情形，而非两套模型；
2. Q2 用**两阶段随机规划 + Rockafellar–Uryasev 线性化**精确求解 CVaR，而非启发式；
3. Q3 用 **Gaussian Copula** 显式建模相关性，再套用 Q2 求解骨架；
4. 全部数值由本仓库代码实际运行产生，不引用任何参考论文数值。

> 迭代/版本留档见 `output/paper/archive/` 与 `output/archive/reference/README.md`。
