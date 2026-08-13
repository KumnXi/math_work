# drawio 论文结构示意图（通用方法）

> 目标：用 `drawio-skill` 绘制 matplotlib 难以胜任的**结构示意图**——建模框架图、求解/算法流程图、
> 问题分解图、技术路线图。产出**可再编辑的 `.drawio` 源文件 + 论文级 PNG + SVG**，并融入 LaTeX 论文。
> 已在 `solve/2024-C题` 落地验证（fig_framework / fig_q1_solve，11/11 验收全绿）。

## 1. 适用场景 vs 数据图

| 用 drawio-skill（结构示意） | 用 matplotlib（数据图） |
|---|---|
| 建模框架图（子问题 × 决策变量—约束—求解器—结果） | 利润曲线、逐年对比 |
| 求解/算法流程图（输入→建模→求解→验证→结果 + 反馈回路） | 面积堆叠、种植结构 |
| 技术路线图（替代 matplotlib 版 fig_pipeline，更专业） | 分布直方图、相关性热图 |
| 问题分解、方案对比、模型结构总览 | 灵敏度曲线、收敛性图 |

**判断**：画面里主要是"方框 + 箭头 + 层级/泳道"→ drawio；主要是"数据坐标轴 + 序列"→ matplotlib。

## 2. 前置依赖

- draw.io desktop CLI（`drawio` 或 `draw.io` on PATH，建议版本 ≥30）。
  - Windows 安装后未进 PATH：`C:\Program Files\draw.io\draw.io.exe`，用
    `[Environment]::SetEnvironmentVariable('Path', $p, 'User')` 追加（新终端生效）。
  - 校验：`drawio --version`。
- Python 仅需标准库（drawio-skill 的 scripts 只用 stdlib）。
- 全局 skill：`drawio-skill`（画图时先 `Skill drawio-skill` 加载其工作流）。

## 3. 标准流程（每步留证据）

1. **调用 drawio-skill**：用 Skill 工具加载，描述要画的图（图型、内容、放置章节）。
2. **选图型并构图**：
   - 建模框架图：每子问题一条泳道，泳道内自上而下四层 = 决策变量 → 关键约束 → 求解算法 → 结果；
     顶部放共享"数据输入"，底部用递进箭头连泳道，边标签写关系（如"模型骨架复用"）。
   - 求解流程图：输入 → 建模（含关键改进约束的侧注框）→ 求解（写求解器/参数）→ 收敛判断 →
     独立验证 → 结果；关键改进/新增约束用虚线侧注 + 反馈回路虚线。
3. **XML 规范**（手写时）：
   - 坐标/尺寸一律取 10 的倍数；泳道内子节点 `parent=泳道 id`、坐标相对泳道。
   - 每个 edge cell 必须带 `<mxGeometry relative="1" as="geometry" />`（自闭合 edge 不渲染）。
   - 一节点多条连接时分配不同 `exitX/entryX`，防堆叠；长边标签加 `labelBackgroundColor=#ffffff`。
   - 中文换行用 `&#xa;`；XML 特殊字符转义 `&amp; &lt; &gt; &quot;`。
   - 若只画标准流程（无自定义样式、CLI ≥30）可用 Mermaid → `drawio -x -f xml -o out.drawio in.mmd` 免手排坐标。
4. **结构校验**：`"$PYTHON_EXE" <drawio-skill>/scripts/validate.py fig.drawio` → 必须 0 error。
5. **预览导出（自查用，禁 `-e`）**：
   `drawio -x -f png --width 2000 -o fig.png fig.drawio`
   - 视觉模型自查；**无视觉能力时**导出 SVG 后 grep 中文关键词，确认标签完整无乱码。
6. **最终导出**（论文引用）：
   - PNG：`drawio -x -f png -e -s 2 -o fig.drawio.png fig.drawio`，**随后立即**
     `"$PYTHON_EXE" <drawio-skill>/scripts/repair_png.py fig.drawio.png`
     （draw.io 的 `-e` PNG 截断 IEND 8 字节，不修复则 A10/视觉/严格解码器报错）。
   - SVG：`drawio -x -f svg -e -o fig.svg fig.drawio`。
   - 预览版 `fig.png`（单扩展名）非交付物，清理或改名避免混淆。
7. **融入论文**：`.drawio.png` 插入 main.tex 对应章节，配 `\includegraphics` + `\label`；正文必须有
   `\ref` 交叉引用（A4）。**图内所有数值必须与正文 / result JSON 一致**（A3，证据门禁）。
8. **留档**：`.drawio` 源文件 + `.drawio.png` + `.svg` 一并存入 `figures/` 与 `paper/archive/v<N>/`，
   保证评审后可再编辑。

## 4. 验收清单

- [ ] `validate.py` 0 error / 0 warning
- [ ] `.drawio.png` 已过 `repair_png.py`（A10：check_figures 可解码）
- [ ] main.tex 每张图有 `\ref`（A4 图表引用完整）
- [ ] 图内数值与正文 / result JSON 一致（A3）
- [ ] 中文标签无乱码（SVG grep 抽查）
- [ ] `.drawio` 源文件随 `archive/v<N>` 留档

## 5. 常见坑

| 现象 | 原因 | 修复 |
|---|---|---|
| 视觉自查 400 | 预览导出误带 `-e`（IEND 截断） | 预览禁 `-e`；最终导出后必跑 repair_png |
| 视觉尺寸超限 | 未限宽 | 预览用 `--width 2000`（≤2576 上限）；最终用 `-s 2` |
| 中文乱码/缺字 | 源文件非 UTF-8 / 标签缺失 | UTF-8 写文件；导出 SVG grep 校验 |
| 箭头不渲染 | edge cell 自闭合、无 geometry 子节点 | 补 `<mxGeometry relative="1" as="geometry" />` |
| 泳道内坐标错位 | 子节点 parent 未指向泳道 | `parent=泳道 id`，坐标相对泳道 |
| 数值更新后图过时 | 结果改后忘同步图 | 每次重跑结果后：重出图 → 重编译 → 重验收 |
| A10 报坏图 | `-e` PNG 未修复 | 跑 `repair_png.py` 后重跑 check_figures |

## 6. 参考案例（可直接改）

- `solve/2024-C题/output/figures/fig_framework.drawio(.png/.svg)`：三问建模框架图（泳道 × 四层结构 + 递进箭头）。
- `solve/2024-C题/output/figures/fig_q1_solve.drawio(.png/.svg)`：Q1 改进求解流程图（C8/C9 侧注 + warm-start + 独立验证 + 反馈回路）。
