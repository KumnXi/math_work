"""Mock LLM 服务器 —— 无真实 API key 时验证 pipeline 框架。

模拟 OpenAI 兼容 chat/completions：按 user 消息关键词返回预制的阶段产物，
让 mock_task 能真实走完 P1→P6（HTTP/生成/运行/编译/record/验收全真实，
只有 LLM 回复是预制的）。配合 scripts/mock_e2e.py 使用。
运行：.venv/Scripts/python.exe scripts/mock_llm_server.py   （监听 127.0.0.1:9999）
"""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------- 预制响应 ----------

P1_MD = """# 问题分析（Mock）
## 问题重述
这是一道用于框架验证的测试题，含 3 个数据附件。
## 数据字典
- attachment1_demand.csv: 需求数据
- attachment2_params.csv: 参数表
- attachment3_history.csv: 历史产量
## 关键参数
## 子问题定义
- Q1: 统计并求解一个组合优化问题
- Q2: 基于历史数据做产量预测
"""

P2_SPEC = """# 模型规格（Mock）
## 模型假设
1. 假设数据真实可靠。
2. 假设问题 Q1 可用整数规划描述。
## Q1 模型
决策变量 $x_i$，目标 $\min z=\sum c_i x_i$，约束 $\sum x_i \ge D$。
## Q2 模型
线性回归 $y=a+bt$。
## 求解算法
Q1 用 CP-SAT；Q2 用最小二乘。
"""

P2_SYMBOLS = """| 符号 | 含义 | 单位 |
|---|---|---|
| $x_i$ | 决策变量 | 件 |
| $D$ | 总需求 | 件 |
"""

SOLVE_Q1 = '''# Mock 求解脚本 —— 固定值，仅验证执行框架（非真实计算）
import json, pathlib
out = pathlib.Path(__file__).resolve().parent
res = {"nrows": 10, "ncols": 3, "r2": 0.9876, "total_cost": 15607}
(out / "result_q1.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
(out / "result_q1.txt").write_text("nrows=10 ncols=3 r2=0.9876 total_cost=15607", encoding="utf-8")
print("solve_q1 done")'''

SOLVE_Q2 = '''# Mock 求解脚本 —— 固定值
import json, pathlib
out = pathlib.Path(__file__).resolve().parent
res = {"mae": 2.27, "mape": 1.5, "pred_31": 191.0}
(out / "result_q2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
(out / "result_q2.txt").write_text("mae=2.27 mape=1.5 pred_31=191.0", encoding="utf-8")
print("solve_q2 done")'''

SOLVE_BODY = ("===== FILE: solve_q1.py =====\n```python\n" + SOLVE_Q1 +
              "\n```\n===== FILE: solve_q2.py =====\n```python\n" + SOLVE_Q2 + "\n```\n")

MAKE_FIGS = '''# Mock 出图脚本 —— 读 result 画概览图 + 技术路线图
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[4] / "tools"))
import figure_style as fs
import matplotlib.pyplot as plt
code = HERE.parent
figdir = HERE.parents[2] / "output" / "figures"
figdir.mkdir(parents=True, exist_ok=True)
for stem in ("result_q1", "result_q2"):
    res = json.loads((code / (stem + ".json")).read_text(encoding="utf-8"))
    fig, ax = fs.new_axes(6, 4)
    ax.bar(list(res.keys()), [float(v) for v in res.values()])
    ax.set_title("Mock 结果概览 (" + stem + ")")
    fs.save(fig, figdir / ("fig_" + stem.replace("result_q", "q") + ".png"))
# 技术路线图
fig, ax = fs.new_axes(9, 5)
ax.axis('off')
steps = ['读题', '数据 EDA', '子问题拆解', '建模', '求解', '结果校验']
for i, s in enumerate(steps):
    x = 0.06 + i * 0.15
    ax.add_patch(plt.Rectangle((x, 0.38), 0.13, 0.24, facecolor=fs.PALETTE[0], edgecolor='black'))
    ax.text(x + 0.065, 0.5, s, ha='center', va='center', color='white', fontsize=10)
    if i < len(steps) - 1:
        ax.annotate('', xy=(x + 0.13, 0.5), xytext=(x + 0.145, 0.5),
                    arrowprops=dict(arrowstyle='-|>', color='black'))
ax.set_title('问题分析与技术路线（Mock）')
fs.save(fig, figdir / "fig_pipeline.png")
print("make_figures done")'''

MAIN_TEX = r"""\documentclass[withoutpreface,bwprint]{cumcmthesis}
\usepackage{url}
\usepackage{booktabs}
\title{仓储配置优化与产量预测研究}
\tihao{A}
\yearinput{2026}
\monthinput{8}
\dayinput{6}

\begin{document}
 \maketitle
 \begin{abstract}

针对仓储配置与产量预测问题，本文分别建立整数规划与回归模型。问题一数据共 10 行 3 列，求得最优总成本为 \textbf{15607 元}，拟合优度 $R^2=0.9876$。问题二回归模型 MAE 为 2.27 件，MAPE 为 1.5\%，第 31 天预测产量为 191 件。模型结构简洁，结果稳健。

\keywords{整数规划\quad 回归\quad 仓储配置\quad 产量预测}
\end{abstract}

\section{问题重述}
本题为框架验证测试题，数据规模共 10 行 3 列。

\section{问题分析}
总体采用"建模-求解-检验"的规范流程，先建立模型，再数值求解并检验。

\section{模型假设}
\begin{enumerate}
\item 假设附件数据真实可靠，无异常值。
\item 假设各子问题相互独立，可分别求解。
\end{enumerate}

\section{符号说明}
\begin{table}[htbp]\centering
\begin{tabular}{ccc}\toprule 符号 & 含义 & 单位 \\\midrule $x_i$ & 决策变量 & 件 \\ $D$ & 总需求 & 件 \\\bottomrule
\end{tabular}
\caption{符号说明}\label{tab:symbols}
\end{table}

\section{模型建立与求解}
\subsection{问题一}
决策变量为 $x_i$，目标函数为
\begin{equation}
\min z=\sum_{i} c_i x_i, \label{eq:obj}
\end{equation}
约束为 $\sum_i x_i \ge D$。求解得到数据共 10 行 3 列，最优总成本 15607 元，结果见图~\ref{fig:q1}。

\begin{figure}[htbp]\centering
\includegraphics[width=0.9\textwidth]{../figures/fig_q1.png}
\caption{问题一结果}\label{fig:q1}
\end{figure}

\subsection{问题二}
建立线性回归模型，拟合优度 $R^2=0.9876$，MAE 为 2.27 件，MAPE 为 1.5\%，第 31 天预测产量为 191 件，见图~\ref{fig:q2}。

\begin{figure}[htbp]\centering
\includegraphics[width=0.9\textwidth]{../figures/fig_q2.png}
\caption{问题二结果}\label{fig:q2}
\end{figure}

\section{模型的检验与误差分析}
对模型进行误差分析，MAE 与 MAPE 均较小，模型精度可接受。

\section{灵敏度与稳定性分析}
对关键参数进行扰动实验，结果保持稳健。

\section{模型的评价}
本文模型简洁、可解释性强，求解精确高效，具有较好的推广性。

\begin{thebibliography}{9}
\bibitem{ref1} 张三, 李四. 数学建模方法与应用[M]. 北京: 某出版社, 2020.
\end{thebibliography}

\newpage
\section*{AI 使用说明}
本文使用生成式 AI 辅助编程与写作，所有结果经人工核对无误。

\appendix
\section{附录：核心代码}
\lstinputlisting{../code/solve_q1.py}
\end{document}
"""


P2_SPEC_FILES = ("```markdown FILE:model_spec.md\n" + P2_SPEC +
                 "\n```\n```markdown FILE:symbols.md\n" + P2_SYMBOLS + "\n```\n")

# 代码手评审建模 → 指出一个符号缺失（触发建模手修订分支）
REVIEW_MODEL = """需要修订

以下歧义会影响我写代码：
1. model_spec.md 中目标函数出现 $c_i$，但符号表缺少 $c_i$ 的定义与单位。
2. 约束 $\\sum_i x_i \\ge D$ 中的参数 $D$ 未给出数值来源。
建议补充符号 $c_i$ 与参数 $D$。"""

# 建模手按评审修订 → 输出修订后的完整双文档
REVISE_MODEL = ("```markdown FILE:model_spec.md\n" + P2_SPEC +
                "\\n\\n【修订】已补充单位成本符号 $c_i$（单位：元）与总需求 $D$ 的来源说明。\n```\n"
                "```markdown FILE:symbols.md\n" + P2_SYMBOLS +
                "| $c_i$ | 单位成本 | 元 |\n| $D$ | 总需求 | 件 |\n```\n")

# 论文手评审产物 → 无需补充（验证"无缺口跳过补充"路径）
REVIEW_PRODUCTS = """无需补充

当前产物齐全：两个子问题均有 result JSON，图表已生成，数值合理，可以撰写论文。"""

# 代码手总结（P3 完成后的协作笔记）
P3_NOTES = """实现要点：
- Q1：整数规划/CP-SAT 思路（Mock 固定值验证），决策变量 $x_i$
- Q2：线性回归预测
关键数值（来自 result JSON）：nrows=10, ncols=3, r2=0.9876, total_cost=15607
对建模的修正建议：无"""


def route(user: str) -> str:
    if "main.tex" in user or "LaTeX 论文" in user:
        return MAIN_TEX
    if "评审这份模型设计" in user:      # 代码手评审建模
        return REVIEW_MODEL
    if "评审团队当前产物" in user:      # 论文手评审产物
        return REVIEW_PRODUCTS
    if "论文缺口" in user:              # 代码手按论文缺口补充
        return "无需补充"
    if "评审意见" in user:              # 建模手按评审修订
        return REVISE_MODEL
    if "求解脚本" in user or "solve_q" in user:
        return SOLVE_BODY
    if "make_figures" in user:
        return "```python\n" + MAKE_FIGS + "\n```\n"
    if "审图" in user:                  # P4 代码手审图 → 全部可用（跳过修复重跑）
        return "全部可用"
    if "合理性自检" in user:            # P3 代码手结果校验 → 全部合理（跳过修复重算）
        return "数值合理"
    if "协作笔记" in user:              # 代码手实现总结
        return P3_NOTES
    if "数学模型" in user or "model_spec" in user:
        return P2_SPEC_FILES
    if "问题分析" in user:
        return P1_MD
    return "OK"


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n).decode("utf-8", errors="replace"))
        user = body["messages"][-1]["content"]
        content = route(user)
        resp = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]})
        data = resp.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # 静默
        pass


if __name__ == "__main__":
    print("Mock LLM server on 127.0.0.1:9999")
    HTTPServer(("127.0.0.1", 9999), H).serve_forever()
