# 模型方法决策矩阵（国赛 CUMCM）

按问题类型选择建模方法。原则：**能用初等方法就不用高级方法**；模型为问题服务而非炫技；获奖论文常用"分层递进"（先 baseline 再精细化）+ 组合模型。

## 一、优化类（排班 / 路径 / 选址 / 分配 / 调度）

| 方法 | 适用场景 | 优点 | 缺点 | 实现 |
|---|---|---|---|---|
| 整数规划 / 0-1 规划 | 变量须为整数（排班、指派、选址、背包） | 全局最优、可证明 | 大规模慢 | ortools CP-SAT / pulp |
| 线性规划 LP | 目标与约束全线性 | 求解器极快 | 需连续变量 | scipy.optimize.linprog / HiGHS |
| 贪心 + 局部搜索 | 大规模组合优化 | 快、易实现 | 局部最优 | 手写（贪心构造 + 2-opt/swap/relocate） |
| 模拟退火 SA | 防局部最优 | 简单通用 | 调参 | 手写 |
| 遗传算法 GA | 离散、非凸、NP 难题 | 全局搜索能力强 | 收敛慢、参数多 | 手写 / DEAP |

**分界经验**：约束变量 ≤ 数千 → 优先精确求解（CP-SAT）；更大 → 启发式（贪心 + 局部搜索 / 元启发式）。

### 最小代码骨架：ortools CP-SAT（整数规划）
```python
from ortools.sat.python import cp_model
m = cp_model.CpModel()
x = [m.NewIntVar(0, 1, f"x{i}") for i in range(n)]
m.Add(sum(x) >= k)                 # 约束
m.Minimize(sum(c[i] * x[i] for i in range(n)))  # 目标
s = cp_model.CpSolver(); st = s.Solve(m)
assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
result = [s.Value(x[i]) for i in range(n)]
```

### 启发式模式（贪心构造 + 2-opt）
```python
# 贪心构造：按优先级排序，每次插入最小边际代价位置
for c in sorted(customers, key=lambda c: c['tw_start']):
    best = min(candidate insertions, key=lambda p: marginal_cost(p))
    place(best)
# 2-opt 局部搜索：迭代交换两段，代价下降即接受，直到无改进
improved = True
while improved:
    improved = any(swap(i, j) < 0 for i in range(len(route)) for j in range(i+1, len(route)))
```
代价函数要点：分项累加（启动 + 能耗 + 碳 + 软时间窗惩罚），分段用 `route_cost(route, vehicle, info)`。

## 二、预测类（产量 / 销量 / 流量 / 趋势）

| 方法 | 适用场景 | 要点 | 实现 |
|---|---|---|---|
| 回归分析（线/非线性） | 相关关系明确、样本足够（n > 3×自变量+1） | 检查多重共线性 | sklearn / scipy.stats |
| 曲线拟合（logistic / Gompertz） | 单调增长、接近饱和 | 有机理背景时优先 | scipy.optimize.curve_fit |
| 时间序列 ARIMA / 指数平滑 | 周期 / 趋势序列，样本较大 | 定阶(p,d,q) + 残差检验 | statsmodels |
| 灰色预测 GM(1,1) | 样本极少（6–15 个）、近似指数增长 | 只适合中短期 | 手写（紧邻均值生成 + 最小二乘） |
| 神经网络 / LSTM | 数据量大、非线性强 | 需标准化 + 训练/测试划分 | sklearn / torch |

**要点**：预测类一定要做**误差分析**（MAE / RMSE / MAPE / R²），并在论文中对比 baseline。

## 三、评价 / 决策类（排序 / 综合评价 / 选优）

| 方法 | 适用场景 | 要点 | 实现 |
|---|---|---|---|
| 层次分析法 AHP | 数据少、指标少、定性为主 | 两两比较矩阵 + 一致性检验（CR<0.1） | 手写 / pyahp |
| TOPSIS | 指标较多、独立排序 | ≥2 对象；可与熵权法/AHP 定权 | 手写 |
| 熵权法 | 有数据、需客观定权 | 常与 TOPSIS 组合 | 手写 |
| 灰色关联分析 | 样本少、信息不完全、时序 | 相对评价，不必归一化 | 手写 |
| 数据包络 DEA | 多投入多产出效率 | — | pyDEA |

### TOPSIS + 熵权法最小骨架
```python
import numpy as np
X = np.array(data)                      # n×m 原始指标
P = X / X.sum(axis=0)                   # 熵权
e = -np.nansum(P * np.log(P + 1e-12), axis=0) / np.log(n)
w = (1 - e) / (1 - e).sum()
Z = (X - X.min(0)) / (X.max(0) - X.min(0))   # 正向化归一（按效益/成本分别处理）
Z = Z * w
Dp = np.sqrt(((Z - Z.max(0))**2).sum(1)); Dn = np.sqrt(((Z - Z.min(0))**2).sum(1))
score = Dn / (Dp + Dn)                  # 贴近度排序
```

## 四、分类 / 聚类类

| 方法 | 适用场景 | 要点 | 实现 |
|---|---|---|---|
| K-means | 明确聚类数 | 先做肘部法则定 K | sklearn.cluster.KMeans |
| 层次聚类 | 聚类数未知 | 画树状图 | scipy.cluster.hierarchy |
| 决策树 / 随机森林 | 分类预测、特征重要性 | 可解释 | sklearn |
| PCA | 降维 / 数据画像 | 先标准化 | sklearn.decomposition |

## 五、机理建模类（连续动态系统）

| 方法 | 适用场景 | 要点 | 实现 |
|---|---|---|---|
| 微分方程（常微分） | 人口 / 传染病 / 传热 / 动态演化 | 建立 → 数值解 → 稳定性分析 | scipy.integrate.odeint / solve_ivp |
| 量纲分析 / 无量纲化 | 简化模型、找相似准则 | Buckingham π | 手写 |
| 排队论 | 服务系统、吞吐 | M/M/1 等 | 手写 |

### 微分方程最小骨架
```python
import numpy as np
from scipy.integrate import solve_ivp
def sir(t, y, beta, gamma):            # SIR 模型
    S, I, R = y
    return [-beta*S*I, beta*S*I - gamma*I, gamma*I]
sol = solve_ivp(sir, [0, T], [S0, I0, R0], args=(beta, gamma), dense_output=True)
```

## 六、灵敏度分析（必做项）

何时必须做：结果依赖关键参数 / 与其他模型竞争对比时。

- **单变量 OAT**：参数 ±10%、±20%，观察目标变化；敏感性指数 `(Δy/y)/(Δx/x)`，>0.5 视为敏感
- **tornado 图**：每个参数取上下界，看目标变动幅度排序
- **蒙特卡洛**：参数服从分布随机抽样（N ≥ 500），看结果分布

```python
# OAT 骨架
base = model(params)
for key in params:
    for factor in (0.9, 1.1, 1.2):
        p = params.copy(); p[key] *= factor
        delta = (model(p) - base) / base
        print(key, factor, delta)
```

## 七、数值求解的迭代与收敛性（机理/数值型题，经验 2024-A）

- **扫描/离散化找极值或临界值**：先粗扫定位大致窗口，再在窗口内**逐级加密步长直到结果稳定**（如 dt: 2.0→0.5→0.1→0.02→0.005）。粗步长会严重低估：Q5 峰值 dt=2.0 只得 1.4213（低估 11%），加密到 0.005 才收敛到 1.6066。各档数值留档，正文用迭代表呈现收敛过程。
- **临界判据（碰撞/可行性）**：用"判据由负到正"粗扫 + **二分穿透过零**精确定位，输出每轮区间宽度收敛表（如 Q3 二分 12 轮把 p_min 区间从 3e-3 压到 7.3e-7）。
- **精确 vs 近似模型**：能建精确模型就建精确模型（如刚体板凳链逐把手反解弧长），并**量化近似误差**（固定弧长偏移在调头段把板凳"压短"最多 14%）——把偏差写成论据。
- **迭代历史必须写进 result JSON**：步号 / 候选值 / 可行性 / 区间宽度 / 步长，供 P4 出收敛图、P5 出迭代表（`references/figure-quality-check.md` 第二节）。

## 选择速查口诀

- 评价：无数据定权→AHP；有数据→熵权；排序→TOPSIS；少样本时序→灰色关联
- 预测：单调增长→Logistic/灰色/指数平滑；周期→ARIMA；非线性大数据→神经网络
- 优化：全线性→LP；整数→ILP/0-1；组合 NP→启发式/元启发式
- **组合模型加分**：PCA+聚类、微分方程+随机森林、熵权+TOPSIS 等混合建模是 O 奖常见特征

## 选型对比表（P2 强制交付）

每个子问题在 `model_spec.md` 中须给出**至少 2 种备选方案对比表**，体现"比较过"且创新与适用兼顾：

| 列 | 内容 |
|---|---|
| 对应问题 | 该方案用于哪个子问题 |
| 算法名称 | 推荐算法/模型名 |
| 算法核心逻辑 | 一两句讲清机理 |
| 实现难度 | 低 / 中 / 高 |
| 优缺点对比 | 至少各一条 |
| 创新性 | 亮点在哪（组合/改进/新视角） |

表中把选中方案标注「选用」，并写一句"选它而非备选"的理由（如精度、可解释性、数据量适配、实现可控）。
