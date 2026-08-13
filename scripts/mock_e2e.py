"""端到端冒烟验证（无真实 LLM key 时）：用 mock LLM 让 mock_task 走完 P1→P6。

用法：
  1. 起 mock LLM：   .venv/Scripts/python.exe scripts/mock_llm_server.py   （127.0.0.1:9999）
  2. 跑本脚本：      .venv/Scripts/python.exe scripts/mock_e2e.py
  3. 检查 problems/mock_task/output/ 与验收报告（应 9/9）
  4. 脚本结束自动恢复原 llm.json

说明：mock 只替 LLM 回复（预制各阶段内容），HTTP/生成/运行/编译/验收全部真实执行。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from webapp import config, pipeline  # noqa: E402

PROJ = pathlib.Path(__file__).resolve().parents[1]
TASK = "mock_task"
BAK = PROJ / "config" / "llm.json.mock_bak"


def main() -> None:
    # 1. 备份并配置指向 mock
    if config.LLM_CONF.exists():
        shutil.copy(config.LLM_CONF, BAK)
    cfg = dict(config.DEFAULT_LLM)
    cfg.update(base_url="http://127.0.0.1:9999/v1", api_key="mock-key", model="mock")
    config.save_llm_config(cfg)
    try:
        # 2. 准备任务文件
        d = config.task_dir(TASK)
        d.mkdir(parents=True, exist_ok=True)
        for f in ("statement.docx", "attachment1_demand.csv",
                  "attachment2_params.csv", "attachment3_history.csv"):
            shutil.copy(PROJ / "problems" / "demo-cumcm" / f, d / f)
        # 3. 跑全流程
        pipeline.run_task(TASK)
        # 4. 结果检查
        st = config.load_state(d)
        print("\n===== 最终状态 =====")
        print("status:", st["status"], "| stage:", st["stage"])
        if st["error"]:
            print("error:", st["error"])
        print("\n===== 团队协作 =====")
        team_map = {"modeler": "建模手", "coder": "代码手", "writer": "论文手"}
        for name, label in team_map.items():
            info = st.get("team", {}).get(name, {})
            note = d / "output" / "team" / f"{name}_notes.md"
            print(f"  {label}: {info.get('status','-')} | {info.get('activity','-')} | "
                  f"笔记{'✅' if note.exists() else '❌'}")
        print("  [角色前缀日志]",
              "✅" if any("[建模手]" in l["msg"] or "[代码手]" in l["msg"] or "[论文手]" in l["msg"]
                          for l in st["logs"]) else "❌")
        # 4b. 新增环节验证：审图日志 / check_report / fig_pipeline / 验收 A10 A11
        print("\n===== 数据图质量检查 =====")
        logs_txt = "\n".join(l["msg"] for l in st["logs"])
        print("  [审图日志]  ", "✅" if "审图" in logs_txt else "❌")
        chk = d / "output" / "figures" / "check_report.json"
        pipe_fig = d / "output" / "figures" / "fig_pipeline.png"
        print("  check_report.json:", "存在 ✅" if chk.exists() else "缺失 ❌")
        if chk.exists():
            import json
            rep = json.loads(chk.read_text(encoding="utf-8"))
            bad = [k for k, v in rep.items() if k != "__error__" and not v.get("ok")]
            n_fig = len(rep) - (1 if "__error__" in rep else 0)
            print(f"  图检查: {n_fig} 张" + ("全部 ok ✅" if not bad else f"未通过 ❌ {bad}"))
        print("  fig_pipeline.png:", "存在 ✅" if pipe_fig.exists() else "缺失 ❌")
        report = d / "output" / "acceptance_report.md"
        if report.exists():
            print("\n===== 验收报告 =====")
            print(report.read_text(encoding="utf-8"))
            rt = report.read_text(encoding="utf-8")
            n_pass = rt.split("通过: ")[1].split("/")[0] if "通过: " in rt else "?"
            print(f"  通过率: {n_pass} 项 | A10 图质量: "
                  f"{'✅' if 'A10' in rt else '❌'} | A11 PDF 视觉: "
                  f"{'✅' if 'A11' in rt else '❌'}")
        pdf = d / "output" / "paper" / "main.pdf"
        print("PDF:", "存在" if pdf.exists() else "缺失",
              (f"({pdf.stat().st_size} B)" if pdf.exists() else ""))
    finally:
        # 5. 恢复原配置
        if BAK.exists():
            shutil.copy(BAK, config.LLM_CONF)
            BAK.unlink()
            print("已恢复原 llm.json")


if __name__ == "__main__":
    main()
