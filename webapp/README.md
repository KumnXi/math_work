# 傻瓜建模（mathmodel.top 风格本地版）

把赛题 + 数据文件丢进网页，一键全自动跑完 CUMCM 六阶段流水线（读题 → 建模 → 编程求解 → 出图 → 论文 → 验收），交付可提交的论文 PDF。**仅本机运行（127.0.0.1）。**

## 架构

```
webapp/
├── app.py               # FastAPI 入口 + 全部路由
├── config.py            # LLM 配置（config/llm.json）+ 任务状态读写
├── llm_client.py        # OpenAI 兼容 chat completions 客户端（requests）
├── pipeline.py          # 六阶段执行器：LLM 生成 → 实际运行 → 修复循环 → record manifest
├── team.py              # 三 Agent 协作框架（TeamAgent：独立记忆 + 协作笔记 + 互评修订）
├── tasks.py             # 任务注册表（扫描 problems/*）
├── static/              # 单页前端（原生 HTML/JS/CSS，零 CDN，可离线）
├── scripts/run_web.sh   # 启动脚本
└── README.md
```

每阶段固定套路：**LLM 生成 → 写文件 → 本机真实运行 → stderr 回喂修复（≤4 次）→ record 证据清单**。LLM 只负责写代码/论文，求解、出图、编译、验收全部在本机实际执行——**禁止编造数值**，跑不出来就阶段标失败并展示错误，绝不假装成功。

## 三 Agent 协作

六个阶段由 **建模手 / 代码手 / 论文手** 三个 Agent 分角色执行，按比赛真实节奏"拆解 → 互评 → 修订 → 补充 → 润色"，避免单 Agent 自问自答的重复劳动：

| 角色 | 代号 | 负责阶段 | 职责 |
|---|---|---|---|
| 📐 建模手 | `modeler` | P1 读题、P2 建模 | 拆解子问题、立假设、写 `model_spec.md` + `symbols.md` |
| 💻 代码手 | `coder` | P3 求解、P4 出图 | 实现 `solve_q*.py` / `make_figures.py`，运行验证、补缺口 |
| ✍️ 论文手 | `writer` | P5 论文、P6 验收 | 评审产物、写 `main.tex`、编译 PDF、按验收失败修 |

**互评修订**：下游角色先评审上游产物再动手——代码手评审建模写 `coder_notes.md`，建模手据此修订一轮；论文手评审全部产物写 `writer_notes.md`（缺的数值/图），代码手补充后可继续。评审说"无需修订/无需补充"就跳过重写，不白跑。

**独立记忆**：每个 Agent 有多轮对话记忆（`output/team/<name>_chat.jsonl`，重跑自动恢复末尾 ≤20 条），记得自己此前的设计决策与修改；协作笔记 `output/team/<name>_notes.md` 跨角色传递评审意见，持久化、可复查。

前端"团队协作"面板实时显示三张角色卡片（状态 + 当前活动 + 协作笔记链接），任务状态 `task_state.json` 的 `team` 字段驱动。

## 快速开始

```bash
# 1. 准备环境（首次）
bash scripts/setup_env.sh        # 建 .venv 并装依赖（含 fastapi/uvicorn/python-multipart）

# 2. 配置 LLM（OpenAI 兼容接口，如 DeepSeek / OpenAI / 通义）
#    a. 启动后浏览器打开 http://127.0.0.1:8000
#    b. 右上角 ⚙ LLM 配置 → 填 base_url / api_key / model → 「测试连通」→ 保存
#    也可直接编辑 config/llm.json：
#    {"base_url": "https://api.deepseek.com/v1", "api_key": "sk-...", "model": "deepseek-chat", "temperature": 0.3}

# 3. 启动
bash scripts/run_web.sh

# 4. 使用
#    左侧「新建任务」→ 拖入题面(docx/pdf) + 数据文件 → 创建 → ▶ 开始全流程
#    主区实时显示六阶段时间线 + 日志 + 产物浏览 + 论文 PDF
```

## 无 API key 冒烟验证（可选）

不想配 key 时，可用 **mock LLM** 验证整套执行框架——mock 只替 LLM 回复预制内容，HTTP/生成/运行/编译/验收全部真实执行：

```bash
# 终端 1：起 mock LLM（127.0.0.1:9999）
.venv/Scripts/python.exe scripts/mock_llm_server.py

# 终端 2：跑全流程（自动配置 llm.json 指向 mock，跑完自动恢复原配置）
.venv/Scripts/python.exe scripts/mock_e2e.py
```

脚本结束后检查 `problems/mock_task/output/acceptance_report.md`（应 9/9 全绿）与 `paper/main.pdf`。

## 任务目录约定

- 任务 = `problems/<task_id>/`（上传的题面 + 数据文件留在根下，作为 P1 输入）
- 产物 = `problems/<task_id>/output/`：`analysis/`（读题/建模）、`code/`（求解脚本 + result_*.json）、`figures/`、`paper/`（main.tex + main.pdf + main.docx 完整版 Word，pandoc 生成、公式可编辑）、`team/`（协作笔记 `<角色>_notes.md` + 记忆 `<角色>_chat.jsonl`）、`acceptance_report.md`、`run_manifest.json`（证据清单）、`task_state.json`（进度状态 + `team` 字段）

## API 一览

| 方法/路径 | 功能 |
|---|---|
| GET `/` | 前端首页 |
| GET/POST `/api/config` | 读/写 LLM 配置 |
| POST `/api/config/test` | 临时配置连通测试（不保存） |
| GET `/api/tasks` | 任务列表（含状态/阶段/是否有论文） |
| POST `/api/tasks` | 创建任务（multipart：task_id + files） |
| POST `/api/tasks/{id}/run` | 启动全流程（from_stage=P1） |
| GET `/api/tasks/{id}/status` | 阶段进度 + 日志 + 三 Agent 状态（前端轮询） |
| GET `/api/tasks/{id}/artifacts` | 各阶段产物清单 |
| GET `/api/tasks/{id}/file?path=...` | 读取产物（白名单限 output/ 内，png/pdf 原生返回） |
| POST `/api/tasks/{id}/stages/{stage}/rerun` | 从指定阶段重跑 |
| GET `/api/tasks/{id}/paper` | 下载论文 main.pdf |
| GET `/api/tasks/{id}/word` | 下载完整版 Word main.docx（pandoc 从 main.tex 生成，公式可编辑；P5 已自动生成，未生成时按需触发） |

## 故障排查

- **「尚未配置 LLM API Key」**：右上角 ⚙ 配置并测试连通；key 存在 `config/llm.json`（本机明文，接受）。
- **某阶段标红失败**：错误展示在状态行，点开日志看细节；手动修对应产物文件后可点「从 P1 重跑」或对应阶段重跑。
- **LaTeX 编译慢/失败**：首次需 MiKTeX 自动装宏包，可能耗时数分钟；持续失败看 `output/paper/latex_check.json`。
- **中文乱码**：所有脚本已强制 `PYTHONIOENCODING=utf-8`；控制台如乱码先确认用 `bash scripts/run_web.sh` 启动。
- **路径含空格**：shell 一律双引号；subprocess 用参数 list，不拼 shell 字符串。
