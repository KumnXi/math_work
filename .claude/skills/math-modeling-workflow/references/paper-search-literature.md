# 学术文献检索（paper-search-mcp）通用方法

> 目标：数模流程任何「需要论文」的环节——**P5 参考文献**、**P7 赛后对比深读**、P2 方法选型佐证——统一走
> `paper-search-mcp` 检索**真实存在、可查可引**的学术文献，杜绝编造引用（A2/A8 常见失分点）。
> 已在 2026-08-10 接入 mcphub（stdio：`uvx paper-search-mcp`，57 tools），2024-C 论文的 15 条参考文献即为此类经典方法文献。

## 1. 适用场景

| 环节 | 用途 | 主用工具 |
|---|---|---|
| P5 参考文献 | 按本问模型方法检索可引文献，填 thebibliography | `search_papers`、`search_crossref` |
| P7 赛后对比 | 检索赛题方法的学术文献，深读差距 | `search_papers`、`download_with_fallback` / `read_*` |
| P2 方法选型 | 佐证所选方法（MILP/随机规划/CVaR/Copula 等）有成熟文献依据 | `search_papers` |

**判断**：需要「引用进论文 / 深读全文」的真实文献 → paper-search-mcp；只需要中文获奖新闻/技术博客等 → 走
`benchmark-iteration.md` 的 web 渠道。

## 2. 前置依赖

- `paper-search-mcp` 已由 mcphub 管理（http://localhost:3000），本会话可直接调工具，名如
  `mcp__mcphub__paper-search-mcp-search_papers`。若某会话没连 mcphub：回退 WebSearch / Crossref API。
- 全部 key 可选，不配也能搜大部分源（arXiv/Crossref/OpenAlex/Semantic Scholar 等免费源够用）；
  配置见 mcphub 记忆 `mcphub-mcp-management`。

## 3. 标准流程（P5 参考文献，每步留证据）

1. **列方法关键词**：从 `model_spec.md` / 符号表提取本问核心方法，如
   `two-stage stochastic programming crop planning CVaR`、`Gaussian copula dependence`、`integer programming land allocation`。
2. **检索**：`search_papers`（统一多源、自动去重）`max_results=5~10/源`；逐条看 title/authors/year/abstract，
   只留**与本文方法/题目直接相关**的。
3. **补全信息**：关键条目用 `search_crossref` 按 DOI 反查，补期刊卷期页码（GB/T 7714 [J] 需要）；arXiv 预印本保留
   arXiv id。搜不到卷期页的用 `[EB/OL]`/`[J/OL]` + DOI/arXiv 形式。
4. **格式化**：按 GB/T 7714 排参考文献，写入 `main.tex` 的 `thebibliography`，正文用 `\cite` 一一对应。
   国赛 15~20 篇；中文建模教材（数学模型/数学建模算法与应用等）可占 2~4 篇。
5. **留证据**：把检索词 + 命中并采用的每条（title/DOI/arXiv id/来源 URL）记入 `output/analysis/literature_sources.md`，
   保证每条 ref 可溯源到一次真实检索。
6. **HIL**：⏸ 交付前把参考文献清单连同来源给用户确认（并入 P5 交付前审阅）。

## 4. P7 用法（赛后对比补充）

- 在 `benchmark-iteration.md` 五类 web 渠道之外，用 `search_papers` 检索赛题方法文献
  （如 `"C题关键词" + method + 年份`），下载 PDF（`download_with_fallback`）后深读，对比矩阵多一行
  「学术文献」参考列。
- 获奖方案若已发表（IEEE/ACM 论文），`search_ieee`/`search_crossref` 直接命中真实版本，优于博客转述。

## 5. 验收清单

- [ ] 每条参考文献都能溯源到一次 `search_papers`/`search_crossref` 真实结果（有 DOI / arXiv id / URL）
- [ ] 作者/年份/期刊卷期页与结果一致（DOI 反查核过）
- [ ] GB/T 7714 格式正确（[J]/[M]/[EB/OL] 区分、标点规范）
- [ ] 正文每条 ref 都有 `\cite` 引用（A4/A8）
- [ ] 检索证据已写入 `literature_sources.md`
- [ ] 文献清单已 HIL 给用户确认

## 6. 常见坑

| 现象 | 原因 | 修复 |
|---|---|---|
| 编造/幻觉引用 | 凭记忆写 ref，没走检索 | 每条 ref 必须来自真实工具结果；写不进证据的一律删 |
| 作者/年份错、卷期页对不上 | 凭记忆填 citation 要素 | 用 `search_crossref` 按 DOI 反查补全 |
| 期刊信息缺失 | 检索结果无 volume/pages | DOI 反查；仍缺则用 `[EB/OL]`/`[J/OL]` + DOI/arXiv 形式，不硬编卷期 |
| 引用与正文不呼应 | 参考文献清单与正文 `\cite` 脱节 | 写完即 grep `\cite` 与 thebibliography 核对 |
| 引了不相干文献 | 关键词太宽，命中噪声 | 从 model_spec 提炼精确方法词，只留直接相关的 |
| 整段照搬博客文献 | 把中文博客当学术引用 | 博客渠道归 P7 对比用；P5 引用必须学术源 |

## 7. 参考案例

- `solve/2024-C题/output/paper/main.tex` 的 thebibliography（b1–b15）：随机规划（Birge & Louveaux、
  Shapiro）、CVaR（Rockafellar & Uryasev）、Copula（Nelsen、Sklar、Joe、Embrechts）等经典方法文献，
  均真实可查；P7 可用 `search_papers` 复核 b5/b7（农业水资源的区间两阶段随机规划）这类可查条目。
