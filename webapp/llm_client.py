"""OpenAI 兼容 chat completions 客户端（requests，不引 openai SDK）。

调用 POST {base_url}/chat/completions，body 含 model/messages/temperature。
任何 API 失败抛 RuntimeError（带中文信息），由 pipeline 捕获处理。
"""
from __future__ import annotations

import requests

from . import config


class LLMError(RuntimeError):
    pass


def chat(messages: list[dict], *, model: str | None = None,
         temperature: float | None = None, max_tokens: int = 8192) -> str:
    """单次 chat 调用，返回助手文本。messages = [{"role","content"},...]
    model 可覆盖全局模型（per-role 用）；temperature 同。"""
    cfg = config.load_llm_config()
    if not cfg.get("api_key"):
        raise LLMError("尚未配置 LLM API Key（右上角设置）。")
    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    body = {
        "model": model or cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"] if temperature is None else temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=180)
    except requests.RequestException as e:
        raise LLMError(f"请求 LLM 失败: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"LLM 返回 {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"LLM 响应格式异常: {r.text[:300]}") from e


def extract_code(text: str) -> str | None:
    """从 LLM 回复中提取第一段 ```python ... ``` 代码块；无则返回 None。"""
    import re
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return m.group(1) if m else None


def test_connection() -> dict:
    """测试连通：发一条最小请求，返回 {ok, msg}。"""
    try:
        chat([{"role": "user", "content": "请只回复 OK 两个字"}], max_tokens=16)
        return {"ok": True, "msg": "连接成功，模型可正常响应。"}
    except LLMError as e:
        return {"ok": False, "msg": str(e)}
