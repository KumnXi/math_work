# 证据门禁（Evidence Gate）30 秒 Demo GIF 制作素材

> 本文件是 **30 秒 demo gif 的完整制作素材**：时间轴分镜脚本 + 录制指引 + README 嵌入位说明。
> 实际 gif 由人工录制，产物路径：`docs/demo/evidence-gate-30s.gif`（录好后 README 中取消注释即生效，见文末「README 嵌入位」）。

## 0. 一句话脚本

> **P3 求解跑完 → 证据写入 `run_manifest.json` → Gate PASS（绿色）→ 手工篡改一个数值 → 重跑 Gate → FAIL + "hash mismatch"（红色拦截）→ 恢复文件 → Gate 重新通过 → 字幕 "Every number in your paper is traceable."**

## 1. 录制前准备（务必逐条完成）

> 目标：让 `solve/demo-cumcm/output/run_manifest.json` 已含 **P3 记录**，且产物与记录一致，保证录制第一镜就是 Gate PASS。

| # | 步骤 | 命令 | 说明 |
|---|---|---|---|
| 1 | 环境自检 | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py --env` | 全部 `[OK]` 才继续。`$PYTHON_EXE` 指向 `.venv/Scripts/python.exe`（见 `.claude/settings.json` env / `config/machine.json`），**禁止裸 `python`**。 |
| 2 | 重新生成 demo 题 | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_demo.py` | 生成 `solve/demo-cumcm/` 题目与 `output/`（若已有且干净可跳过）。 |
| 3 | 跑 P1–P3 | 在项目根启动 `claude`，对 `solve/demo-cumcm` 按 `math-modeling-workflow` 跑全流程到 P3 结束（HIL 确认处直接继续） | 确保 `output/code/result_q1.json` 等产物已生成。 |
| 4 | P3 证据入账 | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_manifest.py record solve/demo-cumcm P3 --inputs statement.docx,attachment1_demand.csv,attachment2_params.csv,attachment3_history.csv --outputs code/solve_q1.py,code/result_q1.json,code/result_q1.txt --cmd "<求解器的完整运行命令>" --exit-code 0` | 若全流程已自动 record 可跳过。注意 `--outputs` 是相对 `output/` 的路径。 |
| 5 | 预演确认 Gate PASS | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py gate solve/demo-cumcm P4` | 应输出 `[gate] P3 产物校验通过，可推进到 P4`，退出码 0。 |

> ⚠️ `gate <problem_dir> <stage>` 校验的是 **`<stage>` 的前一阶段**：校验 P3 产物用 `P4`（P4 的前置是 P3）。`output/` 被 `.gitignore` 忽略、不入库，篡改后的恢复请用文件备份（见镜头 B），**不要依赖 `git checkout`**。
>
> 💡 脚本本身不输出颜色；`[ERROR]` 走 stderr，在 Claude Code / VS Code 集成终端会**自动显示为红色**。录制时请在这种终端里跑命令，让 FAIL 天然醒目。

## 2. 30 秒时间轴分镜

| 时间 | 镜头 | 屏幕内容 | 字幕/说明 |
|---|---|---|---|
| 00:00–00:08 | A 正常流程 | 终端：跑完 P3 求解器 → `result_q1.json` 显示关键数值（如 `total_cost: 15607`）→ `make_manifest.py record P3` 写入 `run_manifest.json` → 跑 `gate P4` → **绿色 PASS** `[gate] P3 产物校验通过，可推进到 P4` | "每跑完一步，产物哈希自动写入 run_manifest.json" / "Gate: PASS" |
| 00:08–00:22 | B 演示篡改 | 编辑器打开 `code/result_q1.json`，把某数值改动（如 `15607 → 15608`）→ 保存 → 重跑 `gate P4` → **红色 FAIL** `[ERROR] 门禁失败：产物被改动（hash 不一致）code/result_q1.json`，进程退出码非 0 | "手改一个数？" / "重跑 Gate → FAIL: hash mismatch" |
| 00:22–00:30 | C 恢复放行 | 用备份恢复 `result_q1.json` → 重跑 `gate P4` → **绿色 PASS** → 收尾定格 | "恢复文件 → Gate 重新通过" / **"Every number in your paper is traceable."** |

### 镜头 A：正常流程（00:00–00:08）

**要演示的动作序列**（提前把命令敲好，录制时逐个回车，节奏放慢）：

```bash
# ① P3 求解（画面停留在结果 JSON，突出关键数值）
"$PYTHON_EXE" code/solve_q1.py          # 工作目录：solve/demo-cumcm/output
cat code/result_q1.json                 # 展示 total_cost 等关键指标

# ② 证据入账
"$PYTHON_EXE" ../../../.claude/skills/math-modeling-workflow/scripts/make_manifest.py record solve/demo-cumcm P3 \
  --inputs statement.docx,attachment1_demand.csv,attachment2_params.csv,attachment3_history.csv \
  --outputs code/solve_q1.py,code/result_q1.json,code/result_q1.txt \
  --cmd "$PYTHON_EXE code/solve_q1.py" --exit-code 0
# 预期输出：[manifest] P3 已记录 3 个产物到 run_manifest.json

# ③ 打开 run_manifest.json 扫一眼哈希（可切编辑器窗口 1–2 秒）
cat solve/demo-cumcm/output/run_manifest.json

# ④ Gate 校验（前一镜 PASS）
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py gate solve/demo-cumcm P4
# 预期输出：[gate] P3 产物校验通过，可推进到 P4
```

- **屏幕应显示**：终端 + 结果 JSON（编辑器窗口）。
- **字幕文案**：*"跑完 P3，每个产物都被 SHA-256 记录进 run_manifest.json —— 篡改无处可逃。"* → *"Gate: PASS ✓"*
- **操作要点**：给 ④ 的 PASS 行 1–2 秒停留再切下一个镜头；屏幕可放大结果数字便于肉眼看清。

### 镜头 B：演示篡改（00:08–00:22）

**核心卖点镜头，务必拍全红色 FAIL 拦截画面。**

```bash
# ① 备份原文件（恢复用；output 不入库，不能靠 git checkout）
cp solve/demo-cumcm/output/code/result_q1.json solve/demo-cumcm/output/code/result_q1.json.bak

# ② 编辑器打开 code/result_q1.json，把任一数值 +1（例：15607 → 15608），保存
#    （鼠标/光标在改动处停留 2 秒，让观众看到改的是数字）

# ③ 重跑 Gate —— 拦截！
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py gate solve/demo-cumcm P4
# 预期输出（红色）：[ERROR] 门禁失败：产物被改动（hash 不一致）code/result_q1.json
# 退出码非 0 —— 进程被 gate 拦下
```

- **屏幕应显示**：编辑器（改数字的特写）→ 终端红色 `[ERROR] ... hash 不一致`。
- **字幕文案**：*"手改一个数字？"* → *"重跑 Gate → FAIL ✗ hash mismatch"*
- **操作要点**：FAIL 红字至少停留 2–3 秒；建议把 `.bak` 备份命令写进脚本但不在录制中运行（保持动作连贯），或提前建好备份。

### 镜头 C：恢复放行（00:22–00:30）

```bash
# ① 恢复文件
mv solve/demo-cumcm/output/code/result_q1.json.bak solve/demo-cumcm/output/code/result_q1.json

# ② 再次 Gate —— 放行
"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py gate solve/demo-cumcm P4
# 预期输出：[gate] P3 产物校验通过，可推进到 P4
```

- **屏幕应显示**：终端绿色 PASS + 居中大字收尾。
- **字幕文案**：*"恢复文件 → Gate 重新通过 ✓"* → **"Every number in your paper is traceable."**（全片点题，停留到最后，建议 3–4 秒）
- **操作要点**：结尾 2–3 秒定格，字幕可叠加在纯色底/终端上，避免 gif 循环时头尾生硬。

## 3. 录制指引

### 3.1 工具选择（二选一）

| 方案 | 工具 | 备注 |
|---|---|---|
| A（推荐） | **ScreenToGif**（免费） | 直接录屏出 gif；选区录制 + 固定帧率，最省事 |
| B | **OBS** 录 1080p 视频 + **ffmpeg** 转 gif | 需要转码，画质可控但多一步 |

```bash
# 方案 B 转 gif 参考（OBS 录 .mkv/.mp4 后执行）
ffmpeg -i record.mp4 -vf "fps=12,scale=1280:-1:flags=lanczos" -loop 0 out.gif
```

### 3.2 窗口与字体（保证清晰可读）

- **终端**：项目根目录开 `claude`（或 VS Code 集成终端），**字号 ≥ 16pt**、深色主题、行高适中；中文渲染用默认字体即可。
- **编辑器**：只保留相关文件 Tab（`result_q1.json`、`run_manifest.json`），字体 ≥ 16pt；**开启 JSON 语法高亮**，数值改动用高亮色标出。
- **录制区域**：仅录终端 + 必要的编辑器窗口（800×600 到 1280×720 之间），**不要录桌面/无关应用**。
- **分辨率与帧率**：≤ 1280 宽，12–15 fps（gif 体积小且动作够顺滑）。
- **窗口 DPI**：Windows 缩放建议 100% 或 125%，避免文字发虚。

### 3.3 录制节奏

- 全程 **30 秒 ± 3 秒**；每敲完一条命令停顿 1–2 秒再回车。
- 三个镜头按 8s / 14s / 8s 切分；**不抢时间**，重点动作（改数字、红字 FAIL、结尾字幕）各留足停留。
- 可先完整彩排一遍（不录屏），确认命令输出与本文档一致后再正式录制。

### 3.4 验收标准（录完自检）

- [ ] 文件：`docs/demo/evidence-gate-30s.gif`，**≤ 15MB**
- [ ] 包含**红色 FAIL 拦截画面**（`[ERROR] 门禁失败：产物被改动（hash 不一致）`）且清晰可读
- [ ] 含绿色 PASS（前段正常流程 + 后段恢复放行）
- [ ] 结尾出现点题字幕 **"Every number in your paper is traceable."**
- [ ] 窗口文字不糊、无抖动、无无关画面
- [ ] 读 README 后按「README 嵌入位」取消注释即显示（无死链）

## 4. README 嵌入位

在 `README.md` 的**证据门禁章节**（含 🔒 铁律与 `evidence_gate.png` 示意图的段落，位于「六阶段流水线」表格后的说明处）附近，**注释形式**预留 gif 位：

```markdown
<!-- 🎬 Evidence Gate 30s demo：录制完成后取消注释即可生效（文件放 docs/demo/evidence-gate-30s.gif） -->
<!-- ![Evidence Gate demo](docs/demo/evidence-gate-30s.gif) -->
```

- **未录制前**：保持注释/删除，README 渲染无死链。
- **录制完成后**：把文件放到 `docs/demo/evidence-gate-30s.gif`，取消上面两行的注释即可生效（可调整 `<img>` 宽度，建议 `width="700"` 与示意图一致）。

## 5. 参考命令速查（真实可用路径）

| 用途 | 命令 |
|---|---|
| 环境自检 | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py --env` |
| Gate 校验（校验 P3 产物） | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/verify_manifest.py gate solve/demo-cumcm P4` |
| 证据入账（P3） | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_manifest.py record <problem_dir> P3 --outputs code/solve_q1.py,code/result_q1.json,code/result_q1.txt --cmd "<运行命令>" --exit-code 0` |
| 重新生成 demo 题 | `"$PYTHON_EXE" .claude/skills/math-modeling-workflow/scripts/make_demo.py` |

> 所有脚本路径均基于仓库现状：`scripts/` 下的 `make_manifest.py` / `verify_manifest.py` 实际位于 `.claude/skills/math-modeling-workflow/scripts/`，请以完整路径调用。
