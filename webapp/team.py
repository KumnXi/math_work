"""多 Agent 协作框架：建模手 / 代码手 / 论文手。

每个 Agent：
- 独立多轮对话记忆（messages），持久化到 output/team/<name>_chat.jsonl，
  重跑/续跑时恢复末尾若干条，形成"记得自己之前设计"的连续上下文
- 协作笔记 output/team/<name>_notes.md，任意 agent 可读其他 agent 的笔记

设计取向：agent 有判断力，不机械执行。评审时若无实质问题应回复"无需修订"，
调用方据此跳过重写，减少重复劳动、把多轮往返留给真正的修正。
"""
from __future__ import annotations

import json
import pathlib
import time

from . import config, llm_client

# 角色名 -> 中文标签（pipeline / 前端共用）
AGENTS = {"modeler": "建模手", "coder": "代码手", "writer": "论文手"}

# 重跑恢复记忆时最多保留的消息条数（防上下文膨胀）
MAX_MEMORY = 20


class TeamAgent:
    def __init__(self, task_dir: pathlib.Path, name: str, role_prompt: str):
        if name not in AGENTS:
            raise ValueError(f"未知 agent: {name!r}，可选 {list(AGENTS)}")
        self.task_dir = task_dir
        self.name = name
        self.label = AGENTS[name]
        self.role_prompt = role_prompt
        # per-role 模型配置（llm.json 的 roles[<name>]；未配置则回退全局模型）
        rcfg = config.load_role_config(name)
        self.model = rcfg["model"]
        self.temperature = rcfg["temperature"]
        self.team_dir = task_dir / "output" / "team"
        self.team_dir.mkdir(parents=True, exist_ok=True)
        self.chat_path = self.team_dir / f"{name}_chat.jsonl"
        self.note_path = self.team_dir / f"{name}_notes.md"
        self.memory: list[dict] = [{"role": "system", "content": role_prompt}]
        self._load_memory()

    # ---------- 记忆 ----------

    def _load_memory(self) -> None:
        if not self.chat_path.exists():
            return
        msgs: list[dict] = []
        for line in self.chat_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msgs.append(json.loads(line))
            except Exception:      # noqa: BLE001
                pass
        if msgs:
            self.memory = [{"role": "system", "content": self.role_prompt}] + msgs[-MAX_MEMORY:]

    def _append(self, role: str, content: str) -> None:
        msg = {"role": role, "content": content}
        self.memory.append(msg)
        with open(self.chat_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def reset_memory(self) -> None:
        """清空对话记忆（文件 + 内存），重跑时从头开始。"""
        self.memory = [{"role": "system", "content": self.role_prompt}]
        if self.chat_path.exists():
            self.chat_path.unlink()

    # ---------- 对话 ----------

    def say(self, user_msg: str, *, temperature: float | None = None) -> str:
        """追加 user 消息 → 调 LLM（带完整记忆 + 该角色模型）→ 追加回复 → 落盘 → 返回文本。

        失败时 user 消息保留在记忆里（agent 记得上次被中断的问题），异常向上抛。
        """
        self._append("user", user_msg)
        text = llm_client.chat(
            self.memory,
            model=self.model,
            temperature=temperature if temperature is not None else self.temperature,
        )
        self._append("assistant", text)
        return text

    # ---------- 协作笔记 ----------

    def write_note(self, text: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.note_path.write_text(
            f"# {self.label}协作笔记\n\n（更新于 {ts}）\n\n{text}\n", encoding="utf-8")

    def read_note(self, name: str) -> str:
        """读其他 agent 的笔记；不存在返回空串。"""
        p = self.team_dir / f"{name}_notes.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @staticmethod
    def says_nothing_to_revise(text: str) -> bool:
        """判断 agent 回复是否表示"无需修订"（用于跳过无意义的重写）。"""
        t = text.strip()
        return (not t) or any(k in t for k in ("无需修订", "无需修改", "没有问题", "不需要修订",
                                               "无需补充", "不用修订", "nothing to revise"))


def load_agents(task_dir: pathlib.Path, role_prompts: dict[str, str]) -> dict[str, TeamAgent]:
    """一次性初始化三个 agent（建模手/代码手/论文手）。"""
    return {name: TeamAgent(task_dir, name, role_prompts[name]) for name in AGENTS}
