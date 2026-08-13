"""提交前敏感信息扫描：拦截疑似密钥/凭据入库。

两种用法：
  1. 作为 git pre-commit 钩子（.githooks/pre-commit 调用），扫描暂存区内容：
       "$PYTHON_EXE" scripts/check_secrets.py --staged
  2. 手动扫描指定文件 / 提交：
       "$PYTHON_EXE" scripts/check_secrets.py path/to/file ...
       "$PYTHON_EXE" scripts/check_secrets.py --commit b581e0d

退出码：0 = 未发现敏感信息；1 = 发现疑似命中（会打印每处位置）。

误报策略：模式刻意收紧 + 内置白名单。命中只是"疑似"，提交者需人工确认；
确认是真密钥 → 改为环境变量/配置文件（gitignore），不要硬编码入库。
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

# 敏感模式（收紧，降低误报；sk-/fc- 要求足够长才认定）
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("OpenAI/DeepSeek key",   re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("Firecrawl key",         re.compile(r"\bfc-[A-Za-z0-9]{20,}")),
    ("AWS AccessKey",         re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub PAT",            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("私钥 PEM",              re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("Bearer token",          re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("密钥字段赋值",           re.compile(
        r"\b(api[_-]?key|secret|token|password|passwd|auth[_-]?key)\b"
        r"\s*[=:]\s*['\"][^'\"]{10,}['\"]", re.IGNORECASE)),
]

# 命中这些 token 的行视为误报（引用名/占位/示例），整行跳过
ALLOW_SUBSTRINGS = (
    "firecrawl-research-index",   # skill 名，非密钥
    "YOUR_", "your-", "YOUR-", "xxx", "XXXX", "...", "<", "example", "placeholder",
    "api_key",                    # 仅字段名（无值）时的兜底
)

# 即便内容干净也不允许入库的路径（密钥/凭据配置文件）
BLOCKED_PATHS = (
    "config/llm.json",
    "config/machine.json",
    ".claude/settings.local.json",
    ".claude/settings.json",
)


def _line_allowed(line: str) -> bool:
    return any(s in line for s in ALLOW_SUBSTRINGS)


def scan_text(text: str, label: str) -> list[str]:
    """对一段文本扫描，返回命中描述列表。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if _line_allowed(line):
            continue
        for name, rx in PATTERNS:
            m = rx.search(line)
            if m:
                hits.append(f"{label}:{i}  [{name}]  {m.group(0)[:60]!r}")
                break  # 一行报一次即可
    return hits


def scan_file(path: str) -> list[str]:
    """扫描单个文件（二进制则仅按字节粗扫）。"""
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError as e:
        return [f"无法读取 {path}: {e}"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # 二进制：仅对可打印片段里的 key 前缀做粗扫
        raw = data.decode("utf-8", errors="ignore")
        hits = []
        for name, rx in PATTERNS[:4]:   # 仅前缀型模式，避免二进制误报
            for m in rx.finditer(raw):
                hits.append(f"{path}  [{name}]  {m.group(0)[:60]!r}")
        return hits
    return scan_text(text, path)


def staged_hits() -> list[str]:
    """扫描暂存区（git diff --cached）。"""
    hits: list[str] = []
    # 1) 暂存区文件路径黑名单（即便只动了其中几行）
    try:
        names = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout.splitlines()
    except Exception:
        names = []
    for n in names:
        if any(bp in n for bp in BLOCKED_PATHS):
            hits.append(f"{n}  命中黑名单路径（配置文件含凭据，禁止入库）")

    # 2) 暂存区内容扫描
    try:
        diff = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
    except Exception as e:
        return hits + [f"git diff --cached 失败: {e}"]
    # 只扫新增行（+ 开头），去掉 diff 的 + 前缀
    added = "\n".join(
        line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    hits += scan_text(added, "(staged)新增行")
    return hits


def main(argv: list[str]) -> int:
    hits: list[str] = []
    if "--staged" in argv:
        hits = staged_hits()
    elif "--commit" in argv:
        c = argv[argv.index("--commit") + 1]
        text = subprocess.run(["git", "show", c], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
        hits = scan_text(text, f"commit {c}")
    else:
        for p in argv:
            hits += scan_file(p)
    if hits:
        print("🔒 提交前敏感信息扫描：发现疑似命中，请人工确认后再提交：", file=sys.stderr)
        for h in hits:
            print(f"  ⚠️  {h}", file=sys.stderr)
        print("    若确认为误报，可在 scripts/check_secrets.py 的 ALLOW_SUBSTRINGS 中追加白名单。",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
